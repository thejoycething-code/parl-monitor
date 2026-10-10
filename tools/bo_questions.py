#!/usr/bin/env python3
"""Bolivia: written questions to the executive, both chambers (BO4).

    python3 tools/bo_questions.py               # the weekly read: the newest pages
    python3 tools/bo_questions.py --backfill    # every question, once (Mini)
    python3 tools/bo_questions.py --reclassify
    python3 tools/bo_questions.py --db /tmp/bo.db

Chris, 10 October 2026: "Bolivia: bills-only (BO2); phase 2 written
questions (BO4)". docs/bolivia-scope.md, "Questions": the peticiones de
informe escrito are the ONE member-attributed record Bolivia publishes,
since neither chamber releases how members voted.

THE SOURCES, both keyless, probed 10 October 2026:

  * Senado: the API the chamber's own site uses,
    apisi.senado.gob.bo/page/peticion-informe-escrito?per_page=100&page=N
    (Laravel paging, newest first; 4,770 questions back to 2015). Each:
    'P.I.E. N°1039/2025-2026', received date, summary, addressee (office and
    minister), the question's PDF and the answer's PDF with its date, and
    the asking senators as API ids (`peticionario[].senador_id`), resolved
    to names through bo_members ('senado/<id>', the current chamber); an id
    the store does not know (a senator of an earlier Assembly) is kept as
    its key, unnamed.
  * Diputados: the chamber's WordPress, wp/v2/peticiones-informe (2,312
    posts). Each: 'P.I.E. N° 0957/2024-2025', filing date, the asking
    deputies BY NAME (`acf.peticionario`), addressee, summary. Names are
    matched to bo_members ('diputados/<slug>') by folded name; an
    unmatched name is kept as printed. The newest post is of 15 September
    2025: the Diputados list has not been updated since the new Assembly
    took office (November 2025). Read anyway, so the edition notices when it
    resumes.

WEEKLY: the newest WEEKLY_PAGES pages of each (Senado answers arrive weeks
later, so recent pages are re-read to catch the answer dates). --backfill
reads every page once.

CLASSIFIED: the summary and the addressee, with taxonomy-es for `bo`. A
question names its askers, so it is member-attributed, but it is a QUESTION:
it records what a member asked about, never a position, and it never enters
a 5CA on its own.

PERSONAL DATA: names and the chamber's member keys only.

ONE WRITER AT A TIME on data/parl-monitor.db. Exit 3: stored what it could
and recorded gaps.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import courts, db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

CC = "bo"
FEED = "bo-questions"
SEN = "https://apisi.senado.gob.bo/page/peticion-informe-escrito"
SEN_FILES = "https://apisi.senado.gob.bo/"
DIP = "https://diputados.gob.bo/wp-json/wp/v2/peticiones-informe"
DIP_FIELDS = "id,date,modified,slug,link,title,acf"
PER_PAGE = 100
WEEKLY_PAGES = 3
THROTTLE_S = 1.0

NUMBER = re.compile(r"P\.?\s*I\.?\s*(?P<kind>[EO])\.?\s*N?\s*[°º]?\s*(?P<n>\d+)\s*/\s*"
                    r"(?P<leg>\d{4}\s*-\s*\d{4})", re.I)


def fold(text):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", text or "")
                            if not unicodedata.combining(c)).lower().split())


def number_of(text):
    """'P.I.E. N°1039/2025-2026 RESPUESTA' -> ('PIE', 1039, '2025-2026')."""
    m = NUMBER.search(text or "")
    if not m:
        return None, None, None
    return "PI" + m.group("kind").upper(), int(m.group("n")), re.sub(r"\s", "", m.group("leg"))


def qkey(chamber, kind, number, leg, fallback):
    if number is None:
        return "{0}/id {1}".format(chamber, fallback)
    return "{0}/{1} {2}/{3}".format(chamber, kind, number, leg)


def iso(value):
    s = str(value or "").strip()
    m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", s)
    return "{0}-{1}-{2}".format(*m.groups()) if m else None


def members(conn):
    """{member_key: name} and {folded name: member_key} for the Diputados."""
    keys, names = {}, {}
    for key, chamber, name in conn.execute("SELECT member_key, chamber, name FROM bo_members"):
        keys[key] = name
        if chamber == "diputados" and name:
            names.setdefault(fold(name), key)
    return keys, names


def parse_senado(records, known):
    out = []
    for r in records or []:
        kind, number, leg = number_of(r.get("titulo"))
        askers, keys = [], []
        for p in r.get("peticionario") or []:
            k = "senado/{0}".format(p.get("senador_id"))
            keys.append(k if k in known else None)
            askers.append(known.get(k) or k)
        dest = r.get("destinatario") or {}
        addressee = " - ".join(x for x in (courts.flat(dest.get("name")),
                                           courts.flat(r.get("tipo_destinatario"))) if x)
        out.append({
            "question_key": qkey("senado", kind or "PIE", number, leg, r.get("id")),
            "chamber": "senado", "kind": kind or "PIE", "number": number, "legislatura": leg,
            "date": iso(r.get("fecha_recepcion")), "addressee": addressee or None,
            "summary": courts.flat(r.get("resumen")) or None,
            "askers": askers, "asker_keys": keys,
            "answered": iso(r.get("fecha_respuesta")),
            "answer_url": SEN_FILES + r["doc_archivo_respuesta"] if r.get("doc_archivo_respuesta") else None,
            "doc_url": SEN_FILES + r["doc_archivo"] if r.get("doc_archivo") else None,
            "url": "https://senado.gob.bo/", "source_id": r.get("id"),
            "updated": (r.get("updated_at") or "")[:10] or None,
        })
    return out


def parse_diputados(posts, by_name):
    out = []
    for p in posts or []:
        acf = p.get("acf") if isinstance(p.get("acf"), dict) else {}
        label = acf.get("nro_pie_o_pio") or (p.get("title") or {}).get("rendered")
        kind, number, leg = number_of(courts.flat(label))
        names = [courts.flat(n) for n in (acf.get("peticionario") or []) if courts.flat(n)]
        keys = [by_name.get(fold(n)) for n in names]
        out.append({
            "question_key": qkey("diputados", kind or "PIE", number, leg, p.get("id")),
            "chamber": "diputados", "kind": kind or "PIE", "number": number, "legislatura": leg,
            "date": iso(acf.get("fecha_de_ingreso")) or (p.get("date") or "")[:10] or None,
            "addressee": courts.flat(acf.get("destino")) or None,
            "summary": courts.flat(acf.get("resumen")) or None,
            "askers": names, "asker_keys": keys, "answered": None, "answer_url": None,
            "doc_url": acf.get("archivo") or None, "url": p.get("link"),
            "source_id": p.get("id"), "updated": (p.get("modified") or "")[:10] or None,
        })
    return out


def upsert(conn, q, tax, today):
    areas, terms, tier = courts.classify(tax, q["summary"] or "", q["addressee"] or "")
    held = conn.execute("SELECT source_id FROM bo_questions WHERE question_key=?",
                        (q["question_key"],)).fetchone()
    if held and held[0] is not None and q["source_id"] is not None and held[0] != q["source_id"]:
        # Measured: 9 of the Senado's 4,770 share a printed number with
        # another record (a re-filed question). Keep both.
        q = dict(q, question_key="{0} (id {1})".format(q["question_key"], q["source_id"]))
    before = conn.execute("SELECT 1 FROM bo_questions WHERE question_key=?",
                          (q["question_key"],)).fetchone()
    conn.execute(
        "INSERT INTO bo_questions (question_key, chamber, kind, number, legislatura, date, "
        "addressee, summary, askers, asker_keys, answered, answer_url, doc_url, url, source_id, "
        "updated, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(question_key) DO UPDATE SET "
        "date=excluded.date, addressee=excluded.addressee, summary=excluded.summary, "
        "askers=excluded.askers, asker_keys=excluded.asker_keys, "
        "answered=COALESCE(excluded.answered, bo_questions.answered), "
        "answer_url=COALESCE(excluded.answer_url, bo_questions.answer_url), "
        "doc_url=excluded.doc_url, url=excluded.url, source_id=excluded.source_id, "
        "updated=excluded.updated, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (q["question_key"], q["chamber"], q["kind"], q["number"], q["legislatura"], q["date"],
         q["addressee"], q["summary"], json.dumps(q["askers"], ensure_ascii=False),
         json.dumps(q["asker_keys"]), q["answered"], q["answer_url"], q["doc_url"], q["url"],
         q["source_id"], q["updated"], json.dumps(areas), json.dumps(terms, ensure_ascii=False),
         tier, today, today))
    return not before, areas


def _pages(conn, client, today, label, url_of, rows_of, parse, pages, tax, log):
    read = new = ours = 0
    page, last = 1, pages
    while page <= last:
        try:
            reply = client.get_json(url_of(page), FEED, "{0}-p{1}".format(label, page))
        except (FetchError, ValueError) as exc:
            if label == "dip" and page > 1 and "400" in str(exc):
                break                       # WordPress: past the last page
            db.record_gap(conn, FEED, "{0} questions page {1} unreadable: {2}".format(
                label, page, str(exc)[:110]), today)
            conn.commit()
            return read, new, ours, 1
        recs, total_pages = rows_of(reply)
        last = min(pages, total_pages) if total_pages else pages
        for q in parse(recs):
            read += 1
            is_new, areas = upsert(conn, q, tax, today)
            new += is_new
            if courts.on_ground(areas):
                ours += 1
                if is_new:
                    log("  [question] {0} {1}: {2}".format(q["question_key"], areas,
                                                         (q["summary"] or "")[:70]))
        conn.commit()
        if len(recs) < PER_PAGE:
            break
        page += 1
    return read, new, ours, 0


def pull(conn, client, today, tax, backfill=False, log=print):
    """Returns {chamber: (read, new, ours)}, gaps."""
    known, by_name = members(conn)
    pages = 10 ** 6 if backfill else WEEKLY_PAGES
    out, gaps = {}, 0

    def sen_rows(reply):
        data = reply.get("data", reply) if isinstance(reply, dict) else reply
        if isinstance(data, dict):
            return data.get("data") or [], int(data.get("last_page") or 1)
        return data or [], 1

    *res, g = _pages(conn, client, today, "sen",
                     lambda n: "{0}?per_page={1}&page={2}".format(SEN, PER_PAGE, n), sen_rows,
                     lambda recs: parse_senado(recs, known), pages, tax, log)
    out["senado"], gaps = tuple(res), gaps + g
    *res, g = _pages(conn, client, today, "dip",
                     lambda n: "{0}?per_page={1}&page={2}&_fields={3}".format(
                         DIP, PER_PAGE, n, DIP_FIELDS),
                     lambda reply: (reply if isinstance(reply, list) else [], None),
                     lambda recs: parse_diputados(recs, by_name), pages, tax, log)
    out["diputados"], gaps = tuple(res), gaps + g
    return out, gaps


def reclassify(conn, tax):
    n = 0
    for key, summary, addressee in conn.execute(
            "SELECT question_key, summary, addressee FROM bo_questions").fetchall():
        areas, terms, tier = courts.classify(tax, summary or "", addressee or "")
        conn.execute("UPDATE bo_questions SET areas=?, matched_terms=?, tier=? WHERE question_key=?",
                     (json.dumps(areas), json.dumps(terms, ensure_ascii=False), tier, key))
        n += 1
    conn.commit()
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--backfill", action="store_true", help="every page, once")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    tax = courts.load_taxonomy(CC)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        print("bo-questions: {0} question(s) reclassified".format(reclassify(conn, tax)))
        return 0
    client = HttpClient(raw_dir=args.raw_dir, throttle=THROTTLE_S)
    got, gaps = pull(conn, client, today, tax, args.backfill)
    print("bo-questions: " + "; ".join(
        "{0} {1} read, {2} new, {3} on our ground".format(ch, *v) for ch, v in got.items()) + ".")
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
