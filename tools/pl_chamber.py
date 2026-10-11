#!/usr/bin/env python3
"""Poland: the Sejm's interpellations, written questions and speeches.

    python3 tools/pl_chamber.py                      # the last three weeks
    python3 tools/pl_chamber.py --since 2026-09-01
    python3 tools/pl_chamber.py --dry-run
    python3 tools/pl_chamber.py --reclassify

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. From the
Sejm's open API (api.sejm.gov.pl, keyless; the source tools/pl_rollcalls.py
reads); the rest is src/chamber_store.py.

QUESTIONS. Interpelacje (/sejm/term10/interpellations, about 600 a month)
and zapytania poselskie (/writtenQuestions), each with its number, the date
received, the title ("Interpelacja w sprawie ..."), the deputies who signed
it (`from`, API member ids) and the minister asked (`to`), and the replies
received. Read newest first (`sort_by=-receiptDate`, honoured on questions),
a page at a time, until a page reaches back past --since. Classified on the
title alone; the deputies' clubs come from pl_members (the Polish weekly's
own roster) when it holds them. A reply's arrival is recorded as the date
answered; its text is never read.

THE API IS SLOW on these lists: 2.8 seconds for a page of interpellations
but 80 seconds for two written questions on 10 October 2026 (the list
endpoint sorts the whole term). The timeout here is two and a half minutes
a page; a list that does not answer is a gap and the next run's three-week
lookback reads it again.

SPEECHES (11 October 2026, branch gaps-speeches). The transcripts endpoint
gave no answer within 30 to 45 seconds on 9 and 10 October 2026; retried
politely on 11 October it answered at once: the statement list of a day
(/proceedings/<n>/<date>/transcripts, 55 KB, about 290 statements for 8
October) and each statement alone as HTML (/transcripts/<num>, 15 KB, under
a second): the agenda point(s) debated ("29. i 30. punkt porządku
dziennego" and their titles), the speaker's office and name ("Poseł Mateusz
Morawiecki:") and the words, with the House's interjections in brackets
("(Oklaski)", "(Głos z sali: ...)", "(Poseł Joanna Frydrych: ...)"), which
are cut before matching: they are other members' words. The list gives each
statement's API member id (memberID, pl_members.mp_id), office, times and
whether it was delivered ("unspoken": a statement handed in for the record).
The chair (statement 0, "Marszałek", the whole day) and the secretaries'
readings are never fetched.

BUDGET. A sitting day is about 290 requests, so speeches drain: days newest
first, statements in order, each statement read remembered in
pl_record_reads (feed 'speech-file') so nothing is fetched twice; a day left
part-read is 'partial' and finished next run. The step runs after the
questions. Not a same-day source as measured (the record of Thursday 8
October was there on Sunday 11 October; the delay was not measured), so no
live read.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import html as htmlmod  # noqa: E402
import re  # noqa: E402

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402

CC = "pl"
FEED = "pl-chamber"
API = "https://api.sejm.gov.pl/sejm"
TERM = 10
PAGE = 200
MAX_PAGES = 10
TIMEOUT = 150
LISTS = (("interpellation", "interpellations"), ("written", "writtenQuestions"))


def members(conn):
    """{api id: (name, club)} from pl_members, the weekly's roster; {} without it."""
    try:
        return {str(r[0]): (r[1], r[2]) for r in conn.execute(
            "SELECT mp_id, name, club FROM pl_members WHERE term=?", (TERM,))}
    except Exception:                               # noqa: BLE001
        return {}


def parse(rec, kind, roster):
    signers = [str(int(x)) if str(x).isdigit() else str(x) for x in rec.get("from") or []]
    first = roster.get(signers[0]) if signers else None
    asker = first[0] if first else ("deputy {0}".format(signers[0]) if signers else None)
    if asker and len(signers) > 1:
        asker = "{0} and {1} other(s)".format(asker, len(signers) - 1)
    replies = [r for r in rec.get("replies") or [] if r.get("receiptDate")]
    link = next((l.get("href") for l in rec.get("links") or []
                 if l.get("rel") == "web-description"), None)
    return {"question_id": "{0} {1}/{2}".format("I" if kind == "interpellation" else "Z",
                                                TERM, rec.get("num")),
            "kind": kind, "date": (rec.get("receiptDate") or "")[:10],
            "title": rec.get("title") or "", "text": None, "asker": asker,
            "party": first[1] if first else None,
            "addressee": "; ".join(rec.get("to") or []) or None,
            "answered": min(r["receiptDate"][:10] for r in replies) if replies else None,
            "url": link}


def questions(run):
    roster = members(run.conn)
    for kind, path in LISTS:
        listed, page, done = [], 0, False
        while page < MAX_PAGES and not done:
            url = "{0}/term{1}/{2}?limit={3}&offset={4}&sort_by=-receiptDate".format(
                API, TERM, path, PAGE, page * PAGE)
            try:
                got = run.client.get_json(url, FEED, "{0}-{1}-p{2}".format(path, run.since, page),
                                          timeout=TIMEOUT)
            except (FetchError, ValueError) as exc:
                run.gap("{0} since {1}, page {2}: {3}".format(path, run.since, page,
                                                              str(exc)[:100]))
                break
            for rec in got or []:
                if (rec.get("receiptDate") or "")[:10] <= run.since:
                    done = True
                    continue
                listed.append(rec)
            if len(got or []) < PAGE:
                done = True
            page += 1
        matched = 0
        for rec in listed:
            q = parse(rec, kind, roster)
            m = cs.classify_question(run.taxes, q["title"])
            if not m:
                continue
            matched += 1
            run.question(q, m)
        run.read("{0}:{1}:{2}".format(path, run.since, run.today), "questions", run.today, None,
                 len(listed), matched, 0)
        run.log("  [{0}] {1} received since {2}, {3} on our ground".format(
            path, len(listed), run.since, matched))
        if run.out_of_time("question lists", len(listed)):
            return


# --- speeches ------------------------------------------------------------------------

STATEMENT_TIMEOUT = 60
# The House's reactions and other members' interjections, in brackets.
_NOISE = re.compile(r"\((?:[^()]{1,80}?:[^()]*|(?:Oklaski|Poruszenie|Wesołość|Gwar|Dzwonek|Głos|"
                    r"Głosy|Przerwa|Sygnał|Posłowie|Posłanki|Część|Burzliwe|Okrzyki|Śmiech|"
                    r"Brawa|Wrzawa|Oklaski|Posłanka|Poseł|Marszałek|Wicemarszałek)[^()]*)\)")
_POINT = re.compile(r'(?is)(?:<h2 class="punkt">(.*?)</h2>\s*)?<p class="punkt-tytul">(.*?)</p>|'
                    r'<h2 class="punkt">(.*?)</h2>')
_SPEAKER = re.compile(r'(?is)<h2 class="mowca">(.*?)</h2>')
_PARA = re.compile(r"(?is)<p(?:\s[^>]*)?>(.*?)</p>")


def _plain(fragment):
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def parse_statement(page):
    """{'point': 'debate title', 'label': 'Poseł X', 'text': words} from one
    statement's HTML; the interjections and the House's reactions are cut."""
    point = _POINT.search(page or "")
    debate = None
    if point:
        debate = (_plain(point.group(2)) or _plain(point.group(1)) or _plain(point.group(3))
                  ).rstrip(".") or None
    speaker = _SPEAKER.search(page or "")
    body = page[speaker.end():] if speaker else (page or "")
    paras = []
    for p in _PARA.findall(body):
        if 'class="punkt' in p:
            continue
        t = _NOISE.sub(" ", _plain(p)).strip()
        if t:
            paras.append(" ".join(t.split()))
    return {"point": debate, "label": _plain(speaker.group(1)).rstrip(":") if speaker else None,
            "text": "\n".join(paras)}


def sitting_days(run):
    """[(proceeding number, ISO date)] of sitting days from --since to today,
    newest first."""
    got = run.client.get_json("{0}/term{1}/proceedings".format(API, TERM), FEED, "proceedings",
                              timeout=TIMEOUT)
    out = []
    for p in got or []:
        if not p.get("number"):
            continue
        for d in p.get("dates") or []:
            if run.since <= d <= run.today:
                out.append((p["number"], d))
    return sorted(out, key=lambda x: x[1], reverse=True)


def wanted(st):
    """A member's or a government speaker's statement: never the chair's day
    record (number 0, 'Marszałek') or a secretary reading the announcements."""
    func = (st.get("function") or "").lower()
    return bool(st.get("num")) and not st.get("secretary") and "marszałek" not in func


def role_of(st):
    func = (st.get("function") or "").strip()
    role = "member" if func.lower() in ("poseł", "posłanka", "") else func
    if st.get("unspoken"):
        role += " (not delivered: handed in for the record)"
    return role


def speeches(run):
    roster = members(run.conn)
    try:
        days = sitting_days(run)
    except (FetchError, ValueError) as exc:
        run.gap("proceedings list unreadable: {0}".format(str(exc)[:100]))
        return
    run.log("  [posiedzenia] {0} sitting day(s) since {1}".format(len(days), run.since))
    fetched = 0
    for num, date in days:
        doc_id = "{0}/{1}".format(num, date)
        if cs.read_state(run.conn, CC, doc_id)[1] == "read":
            if not run.dry_run:
                cs.seen(run.conn, CC, doc_id, run.today)
            continue
        if run.out_of_time("speeches", fetched):
            return
        base = "{0}/term{1}/proceedings/{2}/{3}/transcripts".format(API, TERM, num, date)
        try:
            listed = run.client.get_json(base, FEED, "transcripts-{0}-{1}".format(num, date),
                                         timeout=STATEMENT_TIMEOUT)
        except (FetchError, ValueError) as exc:
            if cs.not_found(exc):
                continue
            run.gap("statement list {0} unreadable: {1}".format(doc_id, str(exc)[:100]))
            continue
        statements = [st for st in (listed or {}).get("statements") or [] if wanted(st)]
        if not statements:
            # Listed before its record is published (Friday 9 October 2026 on
            # the Sunday after): not read, so the next run asks again.
            run.log("  [posiedzenie] {0}: no statements published yet".format(doc_id))
            continue
        titles, matched, done, chars = {}, 0, 0, 0
        for st in statements:
            file_id = "{0}#{1}".format(doc_id, st["num"])
            if cs.read_state(run.conn, CC, file_id)[1] == "read":
                done += 1
                continue
            if run.out_of_time("speeches", fetched):
                break
            url = "{0}/{1}".format(base, st["num"])
            try:
                page = run.client.get_text(url, FEED, "transcript-{0}-{1}-{2}".format(
                    num, date, st["num"]), timeout=STATEMENT_TIMEOUT)
            except FetchError as exc:
                if cs.not_found(exc):
                    continue
                run.gap("statement {0} unreadable: {1}".format(file_id, str(exc)[:80]))
                continue
            fetched += 1
            done += 1
            got = parse_statement(page)
            chars += len(got["text"])
            debate = got["point"] or "(agenda point not printed)"
            if debate not in titles:
                titles[debate] = cs.classify_title(run.taxes, debate)
            m = cs.classify_speech(run.taxes, got["text"], titles[debate])
            hit = 0
            if m:
                hit = 1
                matched += 1
                mid = str(st.get("memberID") or "")
                member = roster.get(mid) if mid and mid != "0" else None
                run.speech({"speech_id": file_id, "doc_id": doc_id, "date": date,
                            "chamber": None, "debate_id": cs.short_id(num, debate),
                            "debate": debate, "speaker": st.get("name") or got["label"],
                            "party": member[1] if member else None, "role": role_of(st),
                            "person_id": "{0}/{1}".format(TERM, mid) if member else None,
                            "text": got["text"], "url": url,
                            "title_areas": titles[debate].areas}, m)
            if not run.dry_run:
                cs.mark_read(run.conn, CC, file_id, "speech-file", date, None, 1, hit,
                             len(got["text"]), run.today)
        complete = done >= len(statements)
        prior = run.conn.execute("SELECT matched FROM pl_record_reads WHERE doc_id=?",
                                 (doc_id,)).fetchone()
        run.read(doc_id, "speeches", date, None, len(statements),
                 matched + ((prior[0] or 0) if prior else 0), chars,
                 "read" if complete else "partial")
        run.log("  [posiedzenie] {0}: {1} statement(s), {2} read this run, {3} on our ground{4}"
                .format(doc_id, len(statements), done, matched,
                        "" if complete else "; part-read, the rest next run"))
        if not complete and run.stopped:
            return


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"questions": questions, "speeches": speeches}, doc=__doc__))
