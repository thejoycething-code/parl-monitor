#!/usr/bin/env python3
"""Bundestag Vorgänge and Drucksachen from DIP, matched on their body.

    python3 tools/de_documents.py                      # term mode, the default
    python3 tools/de_documents.py --mode window        # a date sweep
    python3 tools/de_documents.py --since 2026-06-01 --limit 40
    python3 tools/de_documents.py --dry-run

THIS IS WHERE GERMANY'S VOLUME IS. Recorded votes gave five relevant items
across two whole legislatures; DIP gives 11 Vorgänge on Schwangerschaftsabbruch,
17 on Selbstbestimmungsgesetz and 18 on Meinungsfreiheit by title alone since
March 2025 (measured 22 September 2026).

TWO MODES, and they answer different questions.

  terms  -- ask DIP for each tier-1 German term by title. Precise, cheap, and
            its volume is measured. This is the default and the one that runs
            weekly.
  window -- sweep every Drucksache in a date range and match on the BODY. The
            recall play, and the EU lesson applied: Parliament's titles are
            generic and the body is where the subject lives. About 150
            documents a week, so it is affordable, but it is the mode that can
            surprise you, so it is never the default.

THE BODY IS THE STRONG SIGNAL. /drucksache-text returns the text, so there is
no PDF to parse. The strongest matching passage is stored as the excerpt; the
full text is never stored, because a Plenarprotokoll is a whole sitting day
and the store travels as a release asset. Raw payloads go to data/raw/.

Matching is against config/taxonomy-de.yaml, an AI first draft
(docs/keyword-taxonomy-de.md): treat an area from here as provisional until
the German team has verified the terms.

Separation guarantee: writes de_vorgaenge and de_documents only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, dip, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

TAXONOMY = os.path.join(ROOT, "config", "taxonomy-de.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-de.yaml")
LOOKBACK_DAYS = 120
BODY_LIMIT = 60          # documents read per run; the rest drains next time
BUDGET_S = drain.DEFAULT_S


def tier1_terms(tax):
    """The German tier-1 terms, as DIP title queries.

    Tier 1 only: these are the high-precision compounds, and a tier-2 term
    like `Prostitution*` would pull the whole German debate on a topic we
    triage rather than campaign. A stem's trailing * is dropped -- DIP does
    its own matching and has no wildcard syntax of ours.
    """
    out = []
    # Taxonomy.terms is {area: {tier: [(raw, pattern, case_sensitive, guards)]}}
    for _area, tiers in sorted((getattr(tax, "terms", None) or {}).items()):
        for entry in (tiers.get(1) or []):
            raw = str(entry[0] or "").strip().strip('"').rstrip("*").strip()
            # A one-word section number ("§ 218") is a title query DIP cannot
            # use, and a very short stem would flood. Both are dropped here
            # and still work in the window mode, where matching is ours.
            if len(raw) >= 8 and not raw.startswith("§"):
                out.append(raw)
    return sorted(set(out))


def store_vorgang(conn, today, v, res):
    """Upsert one Vorgang, recording a stage change as a movement."""
    vid = str(v.get("id"))
    stand = v.get("beratungsstand")
    prev = conn.execute("SELECT stand FROM de_vorgaenge WHERE vorgang_id = ?",
                        (vid,)).fetchone()
    moved = prev and prev[0] and stand and prev[0] != stand
    conn.execute(
        "INSERT INTO de_vorgaenge (vorgang_id, wahlperiode, titel, vorgangstyp, "
        "sachgebiet, initiative, datum, stand, prev_stand, moved_date, areas, "
        "matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(vorgang_id) DO UPDATE SET titel=excluded.titel, "
        "stand=excluded.stand, "
        "prev_stand=CASE WHEN excluded.stand IS NOT de_vorgaenge.stand "
        "THEN de_vorgaenge.stand ELSE de_vorgaenge.prev_stand END, "
        "moved_date=CASE WHEN excluded.stand IS NOT de_vorgaenge.stand "
        "THEN excluded.last_seen ELSE de_vorgaenge.moved_date END, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (vid, str(v.get("wahlperiode") or ""), v.get("titel"),
         v.get("vorgangstyp"),
         "; ".join(v.get("sachgebiet") or []) or None,
         "; ".join(v.get("initiative") or []) or None,
         v.get("datum"), stand, prev[0] if moved else None,
         today if moved else None,
         json.dumps(res.issue_areas or []),
         json.dumps(res.matched_terms or []), res.tier, today, today))
    return bool(moved)


def pull_terms(conn, client, key, today, tax, wl, since, log=print,
               budget=None, limit=None):
    """Ask DIP for each tier-1 term by title. Returns (seen, new, moved, gaps)."""
    known = {r[0] for r in conn.execute("SELECT vorgang_id FROM de_vorgaenge")}
    seen = new = moved = gaps = 0
    for term in tier1_terms(tax):
        if budget is not None and budget.exhausted():
            log(budget.disclose("title searches", seen))
            break
        if limit is not None and new >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        try:
            reply = client.get_json(
                dip.url("vorgang", key, **{"f.titel": term, "f.datum.start": since}),
                "de-documents", "vorgang-" + term[:40], archive=False)
        except (FetchError, ValueError) as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (today, "de-documents", "{0}: {1}".format(term, exc)))
            log("  [gap] {0}: {1}".format(term, str(exc)[:70]))
            gaps += 1
            continue
        for v in (reply or {}).get("documents") or []:
            seen += 1
            res = filt.filter_item(tax, wl, v.get("titel") or "")
            if store_vorgang(conn, today, v, res):
                moved += 1
                log("  moved: {0} -> {1}  {2}".format(
                    "?", v.get("beratungsstand"), (v.get("titel") or "")[:52]))
            if str(v.get("id")) not in known:
                new += 1
    conn.commit()
    return seen, new, moved, gaps


def read_bodies(conn, client, key, today, tax, wl, log=print,
                limit=BODY_LIMIT, budget=None):
    """Fetch each unread Drucksache's TEXT and match the body.

    The title is the weak signal. Read once: body_read is stamped whether the
    read succeeded or not, so a document that cannot be read is not retried
    for ever.
    """
    rows = conn.execute(
        "SELECT doc_id, titel, areas FROM de_documents WHERE body_read IS NULL "
        "ORDER BY datum DESC LIMIT ?", (int(limit),)).fetchall()
    read = gained = failed = 0
    for r in rows:
        if budget is not None and budget.exhausted():
            log(budget.disclose("document bodies", read))
            break
        doc_id = r["doc_id"]
        nummer = doc_id.split(":", 1)[1] if ":" in doc_id else doc_id
        try:
            reply = client.get_json(
                dip.url("drucksache-text", key, **{"f.dokumentnummer": nummer}),
                "de-documents", "text-" + nummer.replace("/", "-"), archive=False)
            docs = (reply or {}).get("documents") or []
            body = (docs[0].get("text") if docs else "") or ""
        except (FetchError, ValueError) as exc:
            log("  [body] {0}: unreadable ({1})".format(doc_id, str(exc)[:60]))
            conn.execute("UPDATE de_documents SET body_read = ? WHERE doc_id = ?",
                         (today, doc_id))
            failed += 1
            continue
        if not body:
            conn.execute("UPDATE de_documents SET body_read = ? WHERE doc_id = ?",
                         (today, doc_id))
            failed += 1
            continue
        read += 1
        matches = filt.match_passages(tax, wl, body, title=r["titel"] or "")
        areas, terms, excerpt = filt.aggregate_passages(matches)
        before = json.loads(r["areas"] or "[]")
        merged = sorted(set(before) | set(areas or []))
        if merged != sorted(before):
            gained += 1
            log("  [body] {0}: {1} -> {2}  {3}".format(
                doc_id, before or "[]", merged, (r["titel"] or "")[:52]))
        conn.execute(
            "UPDATE de_documents SET areas = ?, matched_terms = ?, excerpt = ?, "
            "body_read = ? WHERE doc_id = ?",
            (json.dumps(merged), json.dumps(sorted(set(terms or []))),
             (excerpt or "")[:400] or None, today, doc_id))
    conn.commit()
    return read, gained, failed


def pull_window(conn, client, key, today, tax, wl, since, log=print,
                budget=None, limit=None):
    """Sweep Drucksachen by date so the body can be matched. (seen, new, gaps)."""
    known = {r[0] for r in conn.execute("SELECT doc_id FROM de_documents")}
    seen = new = gaps = 0
    try:
        for reply in dip.pages(client, "drucksache", key, slug="drucksache",
                               log=log, budget=budget,
                               **{"f.datum.start": since}):
            for d in reply.get("documents") or []:
                seen += 1
                nummer = d.get("dokumentnummer") or str(d.get("id"))
                doc_id = "drucksache:" + nummer
                if doc_id in known:
                    continue
                if limit is not None and new >= limit:
                    log("  fetch cap ({0}) reached; the rest lands on the next "
                        "run -- disclosed, not silent".format(limit))
                    conn.commit()
                    return seen, new, gaps
                new += 1
                conn.execute(
                    "INSERT OR IGNORE INTO de_documents (doc_id, kind, "
                    "wahlperiode, nummer, datum, titel, url, areas, "
                    "matched_terms, first_seen, last_seen) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (doc_id, "drucksache", str(d.get("wahlperiode") or ""),
                     nummer, d.get("datum"), d.get("titel"),
                     (d.get("fundstelle") or {}).get("pdf_url"),
                     "[]", "[]", today, today))
    except (FetchError, ValueError) as exc:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                     "VALUES (?,?,?)", (today, "de-documents", str(exc)))
        log("  [gap] drucksache window: {0}".format(str(exc)[:70]))
        gaps += 1
    conn.commit()
    return seen, new, gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("terms", "window"), default="terms")
    ap.add_argument("--since", help="ISO date; default {0} days back".format(LOOKBACK_DAYS))
    ap.add_argument("--limit", type=int, help="stop after this many NEW rows")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve the key and list the term queries, store nothing")
    args = ap.parse_args()

    today = datetime.date.today().isoformat()
    since = args.since or (datetime.date.today()
                           - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(TAXONOMY)
    wl = filt.load_watchlist(WATCHLIST)

    secrets = {}
    try:
        from src import publish
        secrets = publish.load_secrets() or {}
    except Exception:                                       # noqa: BLE001
        pass
    key = dip.api_key(client=client, secrets=secrets)
    if not key:
        print("de-documents: no DIP key; nothing collected (disclosed above).")
        return 1
    if args.dry_run:
        terms = tier1_terms(tax)
        print("de-documents: {0} tier-1 term(s) would be asked of DIP since {1}"
              .format(len(terms), since))
        print("  " + ", ".join(terms[:12]) + (" ..." if len(terms) > 12 else ""))
        return 0

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    budget = drain.Budget(args.budget_seconds)
    if args.mode == "terms":
        seen, new, moved, gaps = pull_terms(conn, client, key, today, tax, wl,
                                            since, budget=budget, limit=args.limit)
        print("de-documents: {0} Vorgang result(s) seen, {1} new, {2} moved, "
              "{3} gap(s).".format(seen, new, moved, gaps))
    else:
        seen, new, gaps = pull_window(conn, client, key, today, tax, wl, since,
                                      budget=budget, limit=args.limit)
        print("de-documents: {0} Drucksache(n) seen, {1} new, {2} gap(s)."
              .format(seen, new, gaps))
        read, gained, failed = read_bodies(conn, client, key, today, tax, wl,
                                           budget=budget)
        print("  bodies: {0} read, {1} gained ground, {2} unreadable."
              .format(read, gained, failed))
    ours = conn.execute("SELECT COUNT(*) FROM de_vorgaenge WHERE areas NOT IN "
                        "('[]','') AND areas IS NOT NULL").fetchone()[0]
    print("  {0} Vorgang/Vorgänge on our ground. Matched against "
          "config/taxonomy-de.yaml, an AI first draft: treat an area as "
          "provisional.".format(ours))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
