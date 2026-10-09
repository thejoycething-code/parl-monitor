#!/usr/bin/env python3
"""Croatia: members, agenda items and recorded votes of the Hrvatski sabor.

    python3 tools/hr_rollcalls.py                    # the current Sabor (11th)
    python3 tools/hr_rollcalls.py --all-sessions     # re-read every agenda
    python3 tools/hr_rollcalls.py --dry-run          # count, store nothing
    python3 tools/hr_rollcalls.py --reclassify       # re-derive areas, offline
    python3 tools/hr_rollcalls.py --db /tmp/hr.db    # anywhere but the store

PHASE 1 (9 October 2026); see docs/croatia-scope.md. Every source is the
Sabor's own website, open and keyless. There is no API and no open dataset
(the Sabor's organisation on data.gov.hr holds 0 datasets), so this reads
what the website's own pages and scripts read:

  * www.sabor.hr/hr/sjednice/pregled-dnevnih-redova?field_saziv_target_id=
    <saziv>&field_plenarna_sjednica_target_id=<session> -- one session's
    whole agenda on one page (254 items at most so far), each item with its
    tid, its status (8 = "Glasovanje provedeno", vote held) and its title,
    which carries the bill number ("P.Z.E. br. 328").
  * www.sabor.hr/hr/rezultati-glasovanja-servis/<tid>/ -- JSON the item
    page's script calls: the vote's time, totals and an HTML list of every
    member who voted, with their position. One vote per agenda item.
  * www.sabor.hr/hr/zastupnici?field_saziv_target_id_all=<saziv>
    &field_status_mandata_target_id=&page=<n> -- every member of the Sabor,
    50 a page, with party, constituency and mandate status (active, resting
    or ended: 209 records for 151 seats in the 11th Sabor).

THE VOTE SERVICE ANSWERS 200 FOR AN ITEM WITH NO VOTE. The body is a zeroed
record (`"total_count":0`, time "01.01.0001. 00:00"), not an error. That is
"no recorded vote", stored as vote_state 'none', never as a division.

NOTHING IS CLASSIFIED UNTIL taxonomy-hr EXISTS. The English taxonomy is
blind to Croatian (measured: docs/croatia-scope.md). Until Chris approves
the proposed Croatian terms and config/taxonomy-hr.yaml is generated, areas
come only from config/watchlist-hr.yaml (by key) and are otherwise NULL,
meaning "not classified", which is different from "classified, none".
--reclassify fills them, offline, the day the file lands.

Separation guarantee: writes hr_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store. Exit 0 clean, 3 stored-with-gaps.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, hr_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "hr-rollcalls"
SITE = "https://www.sabor.hr"
CURRENT_SAZIV = 11
# The Sabor's own node id for each saziv, as its search form prints them.
SAZIV_NODE = {11: 144982, 10: 117053}
AGENDA = (SITE + "/hr/sjednice/pregled-dnevnih-redova?field_saziv_target_id={0}"
          "&field_plenarna_sjednica_target_id={1}")
AGENDA_INDEX = SITE + "/hr/sjednice/pregled-dnevnih-redova?field_saziv_target_id={0}"
VOTE = SITE + "/hr/rezultati-glasovanja-servis/{0}/"
MEMBERS = (SITE + "/hr/zastupnici?field_saziv_target_id_all={0}"
           "&field_status_mandata_target_id=&page={1}")
TAXONOMY_HR = os.path.join(ROOT, "config", "taxonomy-hr.yaml")
# sabor.hr answers a session agenda in 4-10 seconds; one request a second is
# polite and the first full read (about 1,050 votes) takes 20-25 minutes.
THROTTLE_S = 1.0
RECENT_SESSIONS = 2
VOTED = 8
STATUS = {6: "neraspravljen", 7: "rasprava u tijeku", 8: "glasovanje provedeno",
          9: "rasprava zaključena", 10: "povučen"}


# --- parsing (pure; the tests drive these with saved pages) -----------------

def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def session_no(label):
    """'12. sjednica Hrvatskoga sabora' -> '12';
    '11., izvanredna sjednica Hrvatskoga sabora' -> '11-izvanredna'."""
    m = re.match(r"\s*(\d+)\.", label or "")
    if not m:
        return None
    return m.group(1) + ("-izvanredna" if "izvanredn" in label.lower() else "")


def parse_sessions(page):
    """[(session_id, session_no, label)] from the agenda search form, newest
    first, as the Sabor sorts them."""
    m = re.search(r'name="field_plenarna_sjednica_target_id".*?</select>', page, re.S)
    if not m:
        return []
    out = []
    for value, label in re.findall(r'<option value="(\d+)"[^>]*>([^<]+)', m.group(0)):
        label = html.unescape(label).strip()
        out.append((int(value), session_no(label), label))
    return out


_ITEM = re.compile(
    r'<div class="dnevni-red-stavka[^"]*"\s+data-nadtocka="(\d*)"\s+data-tocka="(\d+)"'
    r'\s+data-status="(\d+)"[^>]*>\s*<span[^>]*>\s*<a href="([^"]+)">(.*?)</a>', re.S)


def parse_agenda(page):
    """(items, declared_total) for one session's agenda page."""
    items = []
    for parent, tocka, status, href, title in _ITEM.findall(page):
        href = html.unescape(href)
        tid = re.search(r"[?&]tid=(\d+)", href)
        if not tid:
            continue
        items.append({"tid": int(tid.group(1)), "tocka": int(tocka),
                      "parent": int(parent) if parent else None,
                      "status_id": int(status), "url": SITE + href, "title": _clean(title)})
    total = re.search(r"Ukupno rezultata:\s*<strong>(\d+)", page)
    return items, (int(total.group(1)) if total else None)


_BILL = re.compile(r"P\.\s*Z\.\s*(E\.?)?\s*br\.\s*(\d+)", re.I)


def parse_bill(title, saziv=CURRENT_SAZIV):
    """('11/328', 'PZE') from '... P.Z.E. br. 328 ...', or (None, None)."""
    m = _BILL.search(title or "")
    if not m:
        return None, None
    return "{0}/{1}".format(saziv, int(m.group(2))), ("PZE" if m.group(1) else "PZ")


def parse_members(page):
    """(rows, declared_total). Each row: slug, name, party, constituency, mandate."""
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 4:
            continue
        slug = re.search(r'href="/hr/zastupnici/([^"/?]+)"', tds[0])
        if not slug:
            continue
        rows.append({"slug": slug.group(1), "name": _clean(tds[0]), "party": _clean(tds[1]) or None,
                     "constituency": _clean(tds[2]) or None, "mandate": _clean(tds[3]) or None})
    total = re.search(r"Ukupno rezultata:\s*<strong>(\d+)", page)
    return rows, (int(total.group(1)) if total else None)


def iso_time(text):
    """'25.09.2026. 12:22' -> '2026-09-25T12:22'; the zero date -> None."""
    m = re.match(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\.?\s*(\d{1,2}):(\d{2})", text or "")
    if not m or m.group(3) == "0001":
        return None
    d, mo, y, h, mi = m.groups()
    return "{0}-{1:02d}-{2:02d}T{3:02d}:{4}".format(y, int(mo), int(d), int(h), mi)


_ROW = re.compile(r'<div class="export-row vote-row (for|against|abstained)">(.*?)</div>', re.S)


def parse_vote(record):
    """The vote service's JSON -> a vote dict, or None when it holds no vote."""
    if not isinstance(record, dict) or not record.get("total_count"):
        return None
    positions = []
    for position, chunk in _ROW.findall(record.get("votes") or ""):
        slug = re.search(r'href="/hr/zastupnici/([^"/?]+)"', chunk)
        name = re.search(r"<a[^>]*>([^<]+)</a>", chunk)
        if slug:
            positions.append((slug.group(1), html.unescape(name.group(1)).strip() if name else None,
                              position))
    session = _clean(record.get("session") or "")
    return {"title": _clean(record.get("title") or ""), "voted_at": iso_time(record.get("time")),
            "yes": int(record.get("for_count") or 0), "no": int(record.get("against_count") or 0),
            "abstain": int(record.get("abstained_count") or 0),
            "total": int(record.get("total_count") or 0), "session": session,
            "positions": positions}


def vote_problems(v):
    """What does not add up in a parsed vote; [] when it is consistent."""
    out = []
    if v["yes"] + v["no"] + v["abstain"] != v["total"]:
        out.append("totals {0}+{1}+{2} != {3}".format(v["yes"], v["no"], v["abstain"], v["total"]))
    if len(v["positions"]) != v["total"]:
        out.append("{0} position(s) listed for {1} voting".format(len(v["positions"]), v["total"]))
    if not v["voted_at"]:
        out.append("no vote time")
    return out


# --- classification ----------------------------------------------------------

def load_taxonomy(path=TAXONOMY_HR):
    """The Croatian taxonomy, or None until Chris approves it."""
    return filt.load_taxonomy(path) if os.path.exists(path) else None


def empty_watchlist():
    """Watched keys are applied by hr_store.add_watch_areas, not by title."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, title, tid, bill_key, watch_path=None):
    """(areas_json_or_None, matched_json, tier). NULL areas = not classified."""
    res = (filt.filter_item(tax, empty_watchlist(), title or "") if tax is not None
           else filt.FilterResult())
    hr_store.add_watch_areas(res, hr_store.watch_keys(tid, bill_key), watch_path)
    if tax is None and not res.watchlist_hits:
        return None, None, None
    return (hr_store.dumps(res.issue_areas),
            hr_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier)


# --- collecting --------------------------------------------------------------

def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def pull_members(conn, client, today, saziv=CURRENT_SAZIV, log=print):
    """Every member record of the saziv. Returns (stored, gaps)."""
    node = SAZIV_NODE[saziv]
    seen, gaps, page, total = {}, 0, 0, None
    while page < 20:
        try:
            text = client.get_text(MEMBERS.format(node, page), FEED, "members-{0}-p{1}".format(saziv, page))
        except FetchError as exc:
            _gap(conn, today, "members page {0}: {1}".format(page, exc))
            log("  [gap] members page {0}: {1}".format(page, str(exc)[:70]))
            return len(seen), gaps + 1
        rows, declared = parse_members(text)
        total = declared if declared is not None else total
        fresh = [r for r in rows if r["slug"] not in seen]
        for r in fresh:
            seen[r["slug"]] = r
        if not fresh or (total is not None and len(seen) >= total):
            break
        page += 1
    if total is not None and len(seen) != total:
        _gap(conn, today, "members: {0} read of {1} declared".format(len(seen), total))
        log("  [gap] members: {0} read of {1} declared".format(len(seen), total))
        gaps += 1
    for r in seen.values():
        conn.execute(
            "INSERT INTO hr_members (slug, name, party, constituency, mandate, saziv, first_seen, "
            "last_seen) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET "
            "name=excluded.name, party=COALESCE(excluded.party, hr_members.party), "
            "constituency=COALESCE(excluded.constituency, hr_members.constituency), "
            "mandate=excluded.mandate, saziv=excluded.saziv, last_seen=excluded.last_seen",
            (r["slug"], r["name"], r["party"], r["constituency"], r["mandate"], saziv, today, today))
    conn.commit()
    return len(seen), gaps


def store_item(conn, it, saziv, session_id, sess_no, tax, today, watch_path=None):
    bill_key, marker = parse_bill(it["title"], saziv)
    areas, matched, tier = classify(tax, it["title"], it["tid"], bill_key, watch_path)
    conn.execute(
        "INSERT INTO hr_items (tid, tocka, parent, saziv, session_id, session_no, status_id, title, "
        "url, bill_key, bill_marker, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tid) DO UPDATE SET "
        "tocka=excluded.tocka, parent=excluded.parent, session_id=excluded.session_id, "
        "session_no=excluded.session_no, status_id=excluded.status_id, title=excluded.title, "
        "url=excluded.url, bill_key=excluded.bill_key, bill_marker=excluded.bill_marker, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (it["tid"], it["tocka"], it["parent"], saziv, session_id, sess_no, it["status_id"],
         it["title"], it["url"], bill_key, marker, areas, matched, tier, today, today))


def pull_agendas(conn, client, today, saziv=CURRENT_SAZIV, tax=None, all_sessions=False,
                 recent=RECENT_SESSIONS, log=print, budget=None, watch_path=None):
    """Read session agendas: every session on the first run (or when asked),
    otherwise the latest `recent`. Returns (items, sessions_read_ids, gaps)."""
    node = SAZIV_NODE[saziv]
    try:
        index = client.get_text(AGENDA_INDEX.format(node), FEED, "agenda-index-{0}".format(saziv))
    except FetchError as exc:
        _gap(conn, today, "agenda index: {0}".format(exc))
        log("  [gap] agenda index: {0}".format(str(exc)[:70]))
        return 0, [], 1
    sessions = parse_sessions(index)
    if not sessions:
        _gap(conn, today, "agenda index: no sessions in the search form")
        log("  [gap] agenda index: no sessions in the search form")
        return 0, [], 1
    have = conn.execute("SELECT COUNT(*) FROM hr_items WHERE saziv=?", (saziv,)).fetchone()[0]
    todo = sessions if (all_sessions or not have) else sessions[:recent]
    n = gaps = 0
    read = []
    for sid, sno, label in todo:
        if budget is not None and budget.exhausted():
            log(budget.disclose("session agendas", len(read)))
            break
        try:
            page = client.get_text(AGENDA.format(node, sid), FEED, "agenda-{0}-{1}".format(saziv, sid))
        except FetchError as exc:
            _gap(conn, today, "agenda {0}: {1}".format(label, exc))
            log("  [gap] agenda {0}: {1}".format(label, str(exc)[:70]))
            gaps += 1
            continue
        items, declared = parse_agenda(page)
        if declared is not None and len(items) != declared:
            _gap(conn, today, "agenda {0}: {1} item(s) parsed of {2} declared".format(
                label, len(items), declared))
            log("  [gap] agenda {0}: {1} parsed of {2}".format(label, len(items), declared))
            gaps += 1
        for it in items:
            store_item(conn, it, saziv, sid, sno, tax, today, watch_path)
        conn.commit()
        read.append(sid)
        n += len(items)
    return n, read, gaps


def _party_map(conn):
    return dict(conn.execute("SELECT slug, party FROM hr_members"))


def store_vote(conn, tid, v, saziv, today):
    row = conn.execute("SELECT session_no, bill_key, areas, matched_terms, tier FROM hr_items "
                       "WHERE tid=?", (tid,)).fetchone()
    sess_no, bill_key, areas, matched, tier = row or (None, None, None, None, None)
    key = "hr-{0}-{1}".format(saziv, tid)
    conn.execute(
        "INSERT INTO hr_divisions (division_key, tid, saziv, session_no, voted_at, title, bill_key, "
        "yes, no, abstain, total, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(division_key) DO UPDATE SET "
        "voted_at=excluded.voted_at, title=excluded.title, yes=excluded.yes, no=excluded.no, "
        "abstain=excluded.abstain, total=excluded.total, last_seen=excluded.last_seen",
        (key, tid, saziv, sess_no, v["voted_at"], v["title"], bill_key, v["yes"], v["no"],
         v["abstain"], v["total"], areas, matched, tier, today, today))
    parties = _party_map(conn)
    for slug, name, position in v["positions"]:
        if slug not in parties:
            # A member the list did not show (it should list ended mandates
            # too): keep their name under the source's own key, no guess.
            conn.execute("INSERT OR IGNORE INTO hr_members (slug, name, saziv, first_seen, last_seen) "
                         "VALUES (?,?,?,?,?)", (slug, name, saziv, today, today))
        conn.execute("INSERT OR REPLACE INTO hr_votes (division_key, slug, position, party_seen) "
                     "VALUES (?,?,?,?)", (key, slug, position, parties.get(slug)))
    conn.execute("UPDATE hr_items SET vote_state='stored' WHERE tid=?", (tid,))
    return key


def pull_votes(conn, client, today, saziv=CURRENT_SAZIV, sessions_read=(), log=print,
               limit=None, budget=None):
    """The vote on every voted item not yet held, newest first. Items whose
    service said 'no vote' are asked again only while their session is one
    read this run. Returns (stored, none, gaps)."""
    marks = ",".join("?" * len(sessions_read)) or "NULL"
    todo = [r[0] for r in conn.execute(
        "SELECT tid FROM hr_items WHERE saziv=? AND status_id=? AND (vote_state IS NULL OR "
        "(vote_state='none' AND session_id IN ({0}))) ORDER BY tid DESC".format(marks),
        (saziv, VOTED) + tuple(sessions_read))]
    stored = none = gaps = 0
    for i, tid in enumerate(todo):
        if limit is not None and i >= limit:
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("votes", stored))
            break
        try:
            record = client.get_json(VOTE.format(tid), FEED, "vote-{0}".format(tid))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "vote {0}: {1}".format(tid, exc))
            log("  [gap] vote {0}: {1}".format(tid, str(exc)[:70]))
            gaps += 1
            continue
        v = parse_vote(record)
        if v is None:
            conn.execute("UPDATE hr_items SET vote_state='none' WHERE tid=?", (tid,))
            none += 1
        else:
            for problem in vote_problems(v):
                _gap(conn, today, "vote {0}: {1}".format(tid, problem))
                log("  [gap] vote {0}: {1}".format(tid, problem))
                gaps += 1
            store_vote(conn, tid, v, saziv, today)
            stored += 1
        if (stored + none) % 50 == 0:
            conn.commit()
    conn.commit()
    return stored, none, gaps


# --- offline -----------------------------------------------------------------

def reclassify(conn, tax=None, log=print, watch_path=None):
    """Re-derive item areas, then copy them to their divisions, offline."""
    tax = tax if tax is not None else load_taxonomy()
    changed = 0
    for tid, title, bill_key, areas in conn.execute(
            "SELECT tid, title, bill_key, areas FROM hr_items").fetchall():
        new, matched, tier = classify(tax, title, tid, bill_key, watch_path)
        changed += (new or "") != (areas or "")
        conn.execute("UPDATE hr_items SET areas=?, matched_terms=?, tier=? WHERE tid=?",
                     (new, matched, tier, tid))
    conn.execute("UPDATE hr_divisions SET areas=(SELECT areas FROM hr_items i WHERE i.tid=hr_divisions.tid), "
                 "matched_terms=(SELECT matched_terms FROM hr_items i WHERE i.tid=hr_divisions.tid), "
                 "tier=(SELECT tier FROM hr_items i WHERE i.tid=hr_divisions.tid)")
    conn.commit()
    log("hr-rollcalls: reclassified ({0}); {1} item(s) changed area".format(
        "taxonomy-hr" if tax is not None else "no taxonomy-hr yet: watchlist only", changed))
    return changed


def on_our_ground(areas_json):
    return any(a != 11 for a in json.loads(areas_json or "[]"))


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = sum(on_our_ground(a) for (a,) in conn.execute("SELECT areas FROM hr_items"))
    log("  store: {0} agenda item(s) ({1} classified, {2} on our ground), {3} bill(s); "
        "{4} recorded vote(s), {5} position(s); {6} member(s)".format(
            n("SELECT COUNT(*) FROM hr_items"), n("SELECT COUNT(*) FROM hr_items WHERE areas IS NOT NULL"),
            ours, n("SELECT COUNT(DISTINCT bill_key) FROM hr_items WHERE bill_key IS NOT NULL"),
            n("SELECT COUNT(*) FROM hr_divisions"), n("SELECT COUNT(*) FROM hr_votes"),
            n("SELECT COUNT(*) FROM hr_members")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saziv", type=int, default=CURRENT_SAZIV, choices=sorted(SAZIV_NODE))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--all-sessions", action="store_true", help="re-read every session's agenda")
    ap.add_argument("--recent", type=int, default=RECENT_SESSIONS,
                    help="sessions re-read on a normal run (default 2)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored items and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--limit", type=int, help="stop after this many vote fetches")
    ap.add_argument("--dry-run", action="store_true",
                    help="read the agenda index and the newest session, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    if args.dry_run:
        node = SAZIV_NODE[args.saziv]
        sessions = parse_sessions(client.get_text(AGENDA_INDEX.format(node), FEED, "dry-index",
                                                  archive=False))
        if not sessions:
            print("hr-rollcalls: no sessions in the agenda search form")
            return 1
        sid, sno, label = sessions[0]
        items, declared = parse_agenda(client.get_text(AGENDA.format(node, sid), FEED, "dry",
                                                       archive=False))
        print("hr-rollcalls: {0} session(s); {1}: {2} item(s) of {3} declared, {4} voted".format(
            len(sessions), label, len(items), declared,
            sum(1 for i in items if i["status_id"] == VOTED)))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    tax = load_taxonomy()
    if tax is None:
        print("hr-rollcalls: no config/taxonomy-hr.yaml yet; areas come from watchlist-hr only")
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        stored, g = pull_members(conn, client, today, args.saziv)
        gaps += g
        print("hr-rollcalls: {0} member record(s), {1} gap(s)".format(stored, g))
    items, read, g = pull_agendas(conn, client, today, args.saziv, tax=tax,
                                  all_sessions=args.all_sessions, recent=args.recent, budget=budget)
    gaps += g
    print("hr-rollcalls: {0} agenda item(s) from {1} session(s), {2} gap(s)".format(items, len(read), g))
    if not args.no_votes:
        stored, none, g = pull_votes(conn, client, today, args.saziv, sessions_read=read,
                                     limit=args.limit, budget=budget)
        gaps += g
        print("hr-rollcalls: {0} new recorded vote(s), {1} voted item(s) with no record, "
              "{2} gap(s)".format(stored, none, g))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
