#!/usr/bin/env python3
"""Portugal's Tribunal Constitucional: its acórdãos (X8), read very slowly.

    python3 tools/pt_courts.py                 # the weekly read
    python3 tools/pt_courts.py --max-read 4    # fewer rulings read this run
    python3 tools/pt_courts.py --dry-run
    python3 tools/pt_courts.py --reclassify
    python3 tools/pt_courts.py --db /tmp/pt.db

X8, approved 10 October 2026; docs/portugal-scope.md, phase 4. The Court
matters in Portugal more than in most countries on our list: the President
may send any decree for preventive review, and the euthanasia law was struck
down by it twice (Acórdãos 123/2021 and 5/2023) before it was passed.

THE SOURCE: www.tribunalconstitucional.pt/tc/acordaos/, keyless HTML; its
robots.txt is empty. IT RATE-LIMITS HARD: a second request one second after
the first answered 429 (9 October 2026). So every request to the host is at
least THROTTLE_S (30) seconds after the last, the client does not retry a
429 here (max_retries=0: a retry ladder against a rate limiter is the wrong
shape), and the first refusal ends the run with one gap; the next week
carries on, since nothing unread is marked read.

  * The landing page lists the 30 newest acórdãos (number, process,
    formation, kind, date, rapporteur). One request.
  * When the newest stored number is more than 30 behind, the hundred-index
    pages (20260801-0900.html: the same table for 801 to 900) fill the hole,
    at most MAX_INDEX a run.
  * Every listed acórdão is REGISTERED (kind 'ruling', no text). Only those
    of the Plenário and the Secções are READ, newest Plenário first, at most
    MAX_READ a run (ten pages: five minutes). Decisions "em Conferência"
    (reclamações against a rapporteur's summary decision, about two thirds of
    the 850 a year) decide procedure and are never read.

WHAT IS CLASSIFIED: the ruling's OPENING (its first 2,500 characters: who
asked, which norms of which decree or law) and its DISPOSITIVO (from the
"Decisão" heading, before any declaração de voto), with taxonomy-pt for
`pt`. Never the whole ruling: Acórdão 5/2023 is 725 KB and cites every
precedent, and the dissenting votes argue the right to life whatever the
case was about. Pages are not archived (the URL is the provenance, and
these are large); the store keeps the text classified.

ONE WRITER AT A TIME on data/parl-monitor.db. Exit 3: stored what it could
and recorded gaps (a 429 is one).
"""

from __future__ import annotations

import argparse
import datetime
import html as htmllib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import courts, db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

CC = "pt"
FEED = "pt-courts"
COURT = "Tribunal Constitucional"
HOST = "www.tribunalconstitucional.pt"
BASE = "https://www.tribunalconstitucional.pt/tc/acordaos/"
THROTTLE_S = 30.0
MAX_READ = 10
MAX_INDEX = 2
OPENING_CHARS = 2500
DISPOSITIVO_CHARS = 2500

LINK = re.compile(r'<a href="(\d{4})(\d{4})\.html" title="([^"]+)"')
TITLE = re.compile(r"Ac[oó]rd[aã]o\s+(\d+)/(\d+)\s+Proc\.\s*([^,]*),\s*Form\.\s*([^,]+),\s*"
                   r"Esp\.\s*([^,]+),\s*(\d{2})\.(\d{2})\.(\d{4}),\s*(.*?)\s*\(relator\)", re.S)
DECISAO = re.compile(r"\b(?:[IVX]+|\d+)\s*[.–—-]\s*(?:Decis[ãa]o|DECIS[ÃA]O)\b")
VOTO = re.compile(r"DECLARA[ÇC][ÃA]O DE VOTO|Declara[çc][ãa]o de voto|Vencid[oa]", re.S)


def key(year, number):
    return "{0}/{1}".format(int(year), int(number))


def url_of(year, number):
    return "{0}{1:04d}{2:04d}.html".format(BASE, int(year), int(number))


def parse_list(page_html):
    """[{year, number, process, formation, especie, date, relator}] from the
    landing page or a hundred-index page: the link's own title carries every
    column, so one pattern reads both."""
    out, seen = [], set()
    for year, num, title in LINK.findall(page_html or ""):
        t = htmllib.unescape(title)
        m = TITLE.search(t)
        k = key(year, num)
        if k in seen:
            continue
        seen.add(k)
        row = {"year": int(year), "number": int(num), "process": None, "formation": None,
               "especie": None, "date": None, "relator": None}
        if m:
            row.update(process=m.group(3).strip() or None, formation=m.group(4).strip(),
                       especie=m.group(5).strip(),
                       date="{0}-{1}-{2}".format(m.group(8), m.group(7), m.group(6)),
                       relator=re.sub(r"\s+", " ", m.group(9)).strip())
        out.append(row)
    return out


def readable(formation):
    """Plenário and the Secções decide the merits; 'Conf.' (em Conferência)
    decides a reclamação."""
    f = (formation or "").lower()
    return f.startswith("plen") or "sec" in f


def page_text(page_html):
    i = page_html.find("textoacordao")
    seg = page_html[i:] if i >= 0 else page_html
    txt = courts.flat(seg[seg.find(">") + 1:] if i >= 0 else seg)
    # Word's document properties precede the ruling: start at its heading.
    m = re.search(r"AC[ÓO]RD[ÃA]O\s+N", txt)
    return txt[m.start():] if m else txt


def parts(text):
    """(opening, dispositivo) of a ruling's text."""
    opening = courts.clip(text, OPENING_CHARS)
    heads = list(DECISAO.finditer(text))
    disp = ""
    if heads:
        tail = text[heads[-1].start():]
        stop = VOTO.search(tail, 20)
        disp = tail[:stop.start()] if stop else tail
    else:
        # No heading: the last "Pelo exposto" before any declaração de voto
        # (an earlier one may be the Ministério Público's alegações).
        stop = VOTO.search(text)
        body = text[:stop.start()] if stop else text
        j = body.rfind("Pelo exposto")
        if j > 0:
            disp = body[j:]
    return opening, courts.clip(disp, DISPOSITIVO_CHARS)


def register(conn, entry, tax, today):
    """Store a listed acórdão without its text (or refresh its listing data)."""
    k = key(entry["year"], entry["number"])
    if conn.execute("SELECT 1 FROM pt_rulings WHERE ruling_key=?", (k,)).fetchone():
        conn.execute("UPDATE pt_rulings SET last_seen=? WHERE ruling_key=?", (today, k))
        return False
    courts.upsert(conn, CC, {
        "ruling_key": k, "court": COURT, "kind": "ruling",
        "case_no": "Acórdão {0}/{1}{2}".format(entry["number"], str(entry["year"])[2:],
                                               ", Proc. " + entry["process"]
                                               if entry["process"] else ""),
        "date": entry["date"],
        "title": "Acórdão n.º {0}/{1} ({2}, {3})".format(
            entry["number"], entry["year"], entry["especie"] or "?", entry["formation"] or "?"),
        "summary": None, "decision": None, "formation": entry["formation"],
        "url": url_of(entry["year"], entry["number"]), "source": "tribunalconstitucional.pt",
    }, tax, today)
    return True


def to_read(conn, limit):
    """Registered, readable, not yet read: Plenário first, newest first."""
    got = conn.execute(
        "SELECT ruling_key, formation, date, title, case_no, url FROM pt_rulings "
        "WHERE summary IS NULL AND (lower(formation) LIKE 'plen%' OR lower(formation) LIKE '%sec%') "
        "ORDER BY (lower(formation) LIKE 'plen%') DESC, date DESC, ruling_key DESC").fetchall()
    return got[:limit]


def read_one(conn, client, row, tax, today):
    k, formation, date, title, case_no, url = row
    page = client.get_text(url, FEED, "acordao-" + k.replace("/", "-"), archive=False)
    opening, disp = parts(page_text(page))
    courts.upsert(conn, CC, {"ruling_key": k, "court": COURT, "kind": "ruling",
                             "case_no": case_no, "date": date, "title": title,
                             "summary": opening or "(no text found)", "decision": disp or None,
                             "formation": formation, "url": url,
                             "source": "tribunalconstitucional.pt"}, tax, today)
    # A ruling becomes news when it is READ (classified), not when it was
    # listed: the edition's late-ruling rule (src/courts.news_rows) keys on
    # first_seen, so it is the reading date.
    conn.execute("UPDATE pt_rulings SET first_seen=? WHERE ruling_key=?", (today, k))
    return courts.on_ground(conn.execute("SELECT areas FROM pt_rulings WHERE ruling_key=?",
                                         (k,)).fetchone()[0])


def pull(conn, client, today, tax, max_read=MAX_READ, log=print):
    """Returns (listed, new, read, ours, gaps)."""
    client.set_host_throttle(HOST, THROTTLE_S)
    try:
        landing = client.get_text(BASE, FEED, "landing")
    except FetchError as exc:
        db.record_gap(conn, FEED, "acórdãos landing unreadable: {0}".format(str(exc)[:120]), today)
        conn.commit()
        return 0, 0, 0, 0, 1
    listed = parse_list(landing)
    if not listed:
        db.record_gap(conn, FEED, "acórdãos landing parsed to zero rulings; its markup may "
                                  "have changed", today)
        conn.commit()
        return 0, 0, 0, 0, 1
    gaps = 0
    year = max(e["year"] for e in listed)
    lowest = min(e["number"] for e in listed if e["year"] == year)
    got = conn.execute("SELECT ruling_key FROM pt_rulings WHERE ruling_key LIKE ?",
                       ("{0}/%".format(year),)).fetchall()
    have = max((int(r[0].split("/")[1]) for r in got), default=None)
    if have is not None and have + 1 < lowest:
        start = (have // 100) * 100
        for n, lo in enumerate(range(start, lowest, 100)):
            if n >= MAX_INDEX:
                break
            idx = "{0}{1}{2:04d}-{3:04d}.html".format(BASE, year, lo + 1, lo + 100)
            try:
                listed += parse_list(client.get_text(idx, FEED, "index-{0}-{1}".format(year, lo + 1)))
            except FetchError as exc:
                gaps += 1
                db.record_gap(conn, FEED, "acórdãos index {0} unreadable: {1}".format(
                    idx, str(exc)[:100]), today)
                break
    new = sum(register(conn, e, tax, today) for e in listed)
    conn.commit()
    read = ours = 0
    for row in to_read(conn, max_read):
        if gaps:
            break
        try:
            hit = read_one(conn, client, row, tax, today)
        except FetchError as exc:
            gaps += 1
            db.record_gap(conn, FEED, "acórdão {0} unreadable ({1}); the run stopped there and "
                                      "the next one resumes".format(row[0], str(exc)[:80]), today)
            break
        read += 1
        conn.commit()
        if hit:
            ours += 1
            log("  [court] {0} {1}".format(row[0], row[3]))
    conn.commit()
    return len(listed), new, read, ours, gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--max-read", type=int, default=MAX_READ)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    tax = courts.load_taxonomy(CC)
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    if args.reclassify:
        print("pt-courts: {0} ruling(s) reclassified".format(courts.reclassify(conn, CC, tax)))
        return 0
    # No retries against a rate limiter: one refusal ends the run.
    client = HttpClient(raw_dir=args.raw_dir, throttle=1.0, max_retries=0)
    listed, new, read, ours, gaps = pull(conn, client, today, tax, args.max_read)
    pending = conn.execute(
        "SELECT COUNT(*) FROM pt_rulings WHERE summary IS NULL AND (lower(formation) LIKE "
        "'plen%' OR lower(formation) LIKE '%sec%')").fetchone()[0]
    print("pt-courts: {0} acórdão(s) listed, {1} new, {2} read ({3} on our ground), {4} "
          "waiting to be read{5}.".format(listed, new, read, ours, pending,
                                          " (dry run, nothing stored)" if args.dry_run else ""))
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
