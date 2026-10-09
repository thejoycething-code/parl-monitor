#!/usr/bin/env python3
"""Ireland: parliamentary questions (written and oral) on our ground.

    python3 tools/ie_questions.py                       # due weeks, newest first
    python3 tools/ie_questions.py --budget-seconds 300  # stop after five minutes; the rest drains later
    python3 tools/ie_questions.py --since 2026-09-01    # only weeks from this date
    python3 tools/ie_questions.py --dry-run             # list the due weeks, fetch nothing
    python3 tools/ie_questions.py --reclassify          # re-derive areas, offline
    python3 tools/ie_questions.py --db /tmp/ie.db --raw-dir /tmp/ie-raw   # a scratch run

PHASE 2 (9 October 2026); see docs/ireland-scope.md. One source, open and
keyless: the Oireachtas Open Data API, /questions with show_answers=true,
read a WEEK at a time (Monday to Sunday). The Dáil takes about 2,000
questions a sitting week (9,241 between 1 September and 9 October 2026:
written about 98 in 100); the Seanad has no PQs (the API's chamber filter
is ignored on /questions and every record is the Dáil's).

PAGING. Counts saturate at 10,000 and `skip` above 10,000 is a 422, so a
month can overflow; a week cannot (about 2,000), and pages of 1,000 run to
a short page, never to the count.

STORED ON OUR GROUND ONLY: a row in ie_questions is written when the
QUESTION's own text (the question, its heading) is on our ground, with the
Minister's office struck first (tools/ie_rollcalls.strip_offices: the
'Minister for Justice, Home Affairs and Migration' would otherwise file
every justice question under migration). The ANSWER never lends an area:
a Minister's words are not the asker's ground (src/ni_answers.py). Every
week read records its volume in ie_windows (questions read, stored, by
area), so the measurement survives without the rows.

NEVER THE ANSWER IN AN EDITION (CLAUDE.md). The row keeps one sentence of
the answer (answer_takeaway, at most 200 characters: the sentence carrying
a decline, src/ni_answers.shape, or else the first substantive sentence),
its shape and who gave it. The full answer stays at the link.

INCREMENTAL BY WEEK (src/ie_store.due_weeks): every week since the 34th
Dáil met not yet read, any week whose read stopped, and the last
REREAD_DAYS (a written answer can be corrected or a deferred one appear).
Newest first, so a budget-capped backfill fills the weeks the edition
needs before the old ones. A week stopped by the budget is read again
whole.

RAW ARCHIVE. Not archived: a week is 3 to 6 MB with its answers (2 MB for
692 questions, measured), about 300 MB for the backfill, every byte of it
re-fetchable from the same URL. The precedent is the division lists in
tools/ie_rollcalls.py.

Separation guarantee: writes ie_questions, ie_windows (feed 'questions'),
the shared gaps table and its own source_runs heartbeat ('IE questions').
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from urllib.parse import quote, urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, drain, filter as filt, ie_store, ni_answers  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
import ie_rollcalls as roll  # noqa: E402

FEED = "ie-questions"
WINDOW_FEED = "questions"
HEARTBEAT = "IE questions"
API = roll.API
TAXONOMY = roll.TAXONOMY
PAGE = 1000
BUDGET_S = 600.0
REREAD_DAYS = 14
QUESTION_CHARS = 600
TAKEAWAY_CHARS = 200
HIDDEN_AREAS = roll.HIDDEN_AREAS
WEB = "https://www.oireachtas.ie/en/debates/question/{0}/{1}/"

# '1. Deputy Matt Carthy asked the Minister for ...' -> 'the Minister for ...'
ASKED = re.compile(r"^\s*\d+\.\s+(?:Deputy|Senator)\s.*?\basked\s+", re.S)
REF = re.compile(r"\s*\[(\d+/\d+)\]\s*$")
# The office a question is put to: capitalised words joined by commas,
# 'and', 'the', 'of' ('Minister for Agriculture, Food and the Marine').
_WORD = r"[A-Z][\w’']*"
_JOIN = r"(?:,| and(?: the)?| of(?: the)?)? "
OFFICE = re.compile(r"^the\s+(Taoiseach|Tánaiste(?: and Minister for {0}(?:{1}{0})*)?"
                    r"|Minister(?: of State)?(?: at the Department of| for) {0}(?:{1}{0})*)".format(
                        _WORD, _JOIN))
# The answering speaker's label: 'Minister for Health (Deputy Jennifer
# Carroll MacNeill) ...' or 'The Taoiseach ...'.
LABEL = re.compile(r"^((?:An |The )?(?:Taoiseach|Tánaiste)\b(?:\s*\([^)]*\))?"
                   r"|[^()\n]{3,200}?\((?:Deputy|Senator) [^)]{2,80}\))\s*")
# Openers that carry nothing: thanks, and the grouping line of written answers.
EMPTY = re.compile(r"^(?:I (?:wish to )?thank|Thank you|I propose to take Questions?|"
                   r"I propose to answer|I am taking Questions?)", re.I)
# The Irish non-answer the Northern Irish shapes miss (src/ni_answers.py):
# the question is an operational one and the HSE (or another body) will
# reply to the Deputy directly. Checked before ni_answers' own shapes.
IRISH_SHAPES = (
    ("deferred",
     re.compile(r"deferred reply|have requested (?:the )?information|"
                r"(?:will|shall) (?:write|revert|respond) to the Deputy", re.I)),
    ("referred for direct reply",
     re.compile(r"(?:asked|referred[^.]{0,80}?to) (?:the )?(?:HSE|Health Service Executive|"
                r"[A-Z][\w ]{2,40}?) to (?:respond|reply)|for (?:direct )?reply to the Deputy|"
                r"(?:respond|reply) (?:to the Deputy )?directly", re.I)),
)
# 'not our remit' is devolution's shape (reserved and excepted matters); in
# Ireland its loosest pattern ('responsibility of') caught "a shared
# responsibility of myself as Minister" and nothing that declined.
NOT_IRISH = frozenset({"not our remit"})
_SENTENCE = re.compile(r"(?<=[.;])(?<!\bNo\.)(?<!\bNos\.)\s+(?=[A-Z0-9‘'\"(])")


def question_key(uri):
    """'.../question/2026-10-07/pq_1' -> '2026-10-07/pq_1'."""
    hit = re.search(r"/question/(\d{4}-\d{2}-\d{2}/pq_\d+)$", uri or "")
    return hit.group(1) if hit else None


def answer_turn(answer, asker=None, offices=()):
    """(label, text) of the first answering turn, or (None, '').

    A written answer is one turn, its label either with the Minister's name
    ('Minister of State at the Department of Health (Deputy X) Text') or the
    bare office run straight into the text ('Minister for Health As this is
    an operational matter...'); an oral answer is the exchange, the asker
    first ('Deputy Matt Carthy ...'). The first turn carrying an office label
    is the Minister's. A bare office is struck only when it is one of
    `offices` (the office the question was put to, and every office seen
    asked this run), longest first: the office's last word and the answer's
    first are both capitalised, so no pattern can tell where one ends."""
    for turn in (answer or "").split("\n"):
        turn = turn.strip()
        if not turn or (asker and turn.startswith("Deputy " + asker)):
            continue
        hit = LABEL.match(turn)
        if hit:
            return " ".join(hit.group(1).split()), turn[hit.end():].strip()
        for office in sorted({o for o in offices if o}, key=len, reverse=True):
            if turn.startswith(office + " "):
                return office, turn[len(office):].strip()
    return None, ""


def takeaway(text, limit=TAKEAWAY_CHARS):
    """(shape, one sentence): the sentence carrying a decline when there is
    one (src/ni_answers.shape), else the first that says something. Never
    more than `limit` characters, never the answer."""
    text = " ".join((text or "").split())
    if not text:
        return "", ""
    shape, pattern = next(((n, p) for n, p in IRISH_SHAPES if p.search(text)), ("", None))
    if not shape:
        shape = ni_answers.shape(text)
        if shape in NOT_IRISH:
            shape = ""
        pattern = dict(ni_answers._COMPILED).get(shape)
    sentences = [s.strip() for s in _SENTENCE.split(text) if s.strip()]
    chosen = next((s for s in sentences if not EMPTY.match(s)), sentences[0] if sentences else text)
    if pattern is not None:
        chosen = next((s for s in sentences if pattern.search(s)), chosen)
    if len(chosen) > limit:
        chosen = chosen[:limit - 3].rsplit(" ", 1)[0] + "..."
    return shape, chosen


# Every office a question was put to, as parsed: the bare labels answers
# open with (answer_turn).
SEEN_OFFICES = set()


def with_juniors(offices):
    """Each 'Minister for X' with its 'Minister of State at the Department of
    X' and 'Tánaiste and Minister for X': a junior or the Tánaiste often
    answers a question put to the senior Minister."""
    out = set()
    for o in offices:
        if not o:
            continue
        out.add(o)
        if o.startswith("Minister for "):
            dept = o[len("Minister for "):]
            out.add("Minister of State at the Department of " + dept)
            out.add("Tánaiste and Minister for " + dept)
    return out


def parse_question(rec):
    q = rec.get("question") or rec
    show = " ".join((q.get("showAs") or "").split())
    ref = REF.search(show)
    body = REF.sub("", show)
    body = ASKED.sub("", body, count=1) if ASKED.match(body) else body
    office = OFFICE.match(body)
    by = q.get("by") or {}
    house = q.get("house") or {}
    if office:
        SEEN_OFFICES.add(office.group(1))
    label, answer = answer_turn(q.get("answerText"), by.get("showAs"), with_juniors(
        SEEN_OFFICES | {office.group(1) if office else None,
                        "Minister for " + ((q.get("to") or {}).get("showAs") or "?")}))
    shape, line = takeaway(answer)
    date = q.get("date")
    key = question_key(q.get("uri"))
    section = q.get("debateSection") or {}
    return {
        "key": key, "ref": ref.group(1) if ref else None, "date": date,
        "qtype": q.get("questionType"), "number": q.get("questionNumber"),
        "house_key": roll.house_key(house.get("uri")),
        "member_code": by.get("memberCode"), "asker": by.get("showAs"),
        "department": (q.get("to") or {}).get("showAs"),
        "minister": office.group(1) if office else None,
        "heading": section.get("showAs"),
        "question": body[:QUESTION_CHARS],
        "answered": int(bool((q.get("answerText") or "").strip())),
        "answer_by": label, "answer_shape": shape, "answer_takeaway": line or None,
        "debate_uri": section.get("uri"), "debate_section": section.get("debateSectionId"),
        "url": WEB.format(date, key.rsplit("pq_", 1)[-1]) if key and date else None,
    }


def classify(tax, wl, q):
    """The question's own text, the office struck first. Never the answer."""
    return filt.filter_item(tax, wl, roll.strip_offices(q["heading"]),
                            roll.strip_offices(q["question"]),
                            title=roll.strip_offices(q["heading"]))


def store_question(conn, q, res, party, today):
    conn.execute(
        "INSERT INTO ie_questions (question_key, ref, date, qtype, number, house_key, member_code, "
        "asker, party, department, minister, heading, question, answered, answer_by, answer_shape, "
        "answer_takeaway, debate_uri, debate_section, areas, matched_terms, tier, url, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(question_key) DO UPDATE SET ref=excluded.ref, date=excluded.date, "
        "qtype=excluded.qtype, number=excluded.number, house_key=excluded.house_key, "
        "member_code=excluded.member_code, asker=excluded.asker, party=excluded.party, "
        "department=excluded.department, minister=excluded.minister, heading=excluded.heading, "
        "question=excluded.question, answered=excluded.answered, answer_by=excluded.answer_by, "
        "answer_shape=excluded.answer_shape, answer_takeaway=excluded.answer_takeaway, "
        "debate_uri=excluded.debate_uri, debate_section=excluded.debate_section, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "url=excluded.url, last_seen=excluded.last_seen",
        (q["key"], q["ref"], q["date"], q["qtype"], q["number"], q["house_key"], q["member_code"],
         q["asker"], party, q["department"], q["minister"], q["heading"], q["question"],
         q["answered"], q["answer_by"], q["answer_shape"], q["answer_takeaway"], q["debate_uri"],
         q["debate_section"], ie_store.dumps(res.issue_areas),
         ie_store.dumps(res.matched_terms), res.tier, q["url"], today, today))


def fetch_week(client, week_of, budget=None):
    """Every question of one week. Returns (records, complete)."""
    start = datetime.date.fromisoformat(week_of)
    end = start + datetime.timedelta(days=6)
    out, skip = [], 0
    while True:
        if budget is not None and budget.exhausted():
            return out, False
        query = urlencode({"date_start": week_of, "date_end": end.isoformat(),
                           "show_answers": "true", "limit": PAGE, "skip": skip},
                          safe=":/", quote_via=quote)
        data = client.get_json("{0}questions?{1}".format(API, query), FEED,
                               "questions-{0}-{1}".format(week_of, skip), archive=False)
        page = (data or {}).get("results")
        if not isinstance(page, list):
            raise ValueError("questions {0}: no results list in the answer".format(week_of))
        out.extend(page)
        if len(page) < PAGE:
            return out, True
        skip += PAGE
        if skip >= 10000:
            # The API's ceiling; a week has never come near it (about 2,000).
            raise ValueError("questions {0}: 10,000 or more in one week".format(week_of))


def pull(conn, client, today, since=roll.DAIL_START, tax=None, wl=None, budget=None, log=print):
    """Returns (weeks read, questions read, stored on our ground, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else roll.empty_watchlist()
    parties = roll.PartyBook(conn)
    weeks = ie_store.due_weeks(conn, WINDOW_FEED, since, today, REREAD_DAYS)
    read = total = ours = gaps = 0
    for done, week in enumerate(weeks):
        if budget is not None and budget.exhausted():
            log("  " + budget.disclose("question weeks ({0} still due)".format(len(weeks) - done),
                                       done))
            break
        try:
            recs, complete = fetch_week(client, week, budget)
        except (FetchError, ValueError) as exc:
            roll._gap(conn, today, "questions week of {0}: {1}".format(week, str(exc)[:200]))
            ie_store.record_week(conn, WINDOW_FEED, week, "gap", 0, 0, 0, {}, today)
            conn.commit()
            log("  [gap] questions week of {0}: {1}".format(week, str(exc)[:70]))
            gaps += 1
            continue
        if not complete:
            log("  " + budget.disclose("question pages (week of {0}, read again next run)".format(
                week), len(recs)))
            ie_store.record_week(conn, WINDOW_FEED, week, "partial", len(recs), len(recs), 0, {},
                                 today)
            conn.commit()
            break
        stored, by_area = 0, {}
        for rec in recs:
            try:
                q = parse_question(rec)
            except (KeyError, TypeError, ValueError) as exc:
                roll._gap(conn, today, "question record unreadable: {0}".format(exc))
                gaps += 1
                continue
            if not q["key"]:
                continue
            res = classify(tax, wl, q)
            if not roll.on_our_ground(res.issue_areas):
                continue
            party = parties.at(q["member_code"], q["date"], q["house_key"]) \
                if q["member_code"] and q["date"] else None
            store_question(conn, q, res, party, today)
            stored += 1
            for a in res.issue_areas or []:
                by_area[a] = by_area.get(a, 0) + 1
        ie_store.record_week(conn, WINDOW_FEED, week, "read", len(recs), len(recs), stored, by_area,
                             today)
        conn.commit()
        read += 1
        total += len(recs)
        ours += stored
    return read, total, ours, gaps


def reclassify(conn, tax=None, log=print):
    """Re-derive stored questions' areas, offline. A question that falls off
    our ground is kept with its new (empty) areas: rows are never deleted."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = roll.empty_watchlist()
    changed = 0
    for key, heading, question, areas in conn.execute(
            "SELECT question_key, heading, question, areas FROM ie_questions").fetchall():
        res = classify(tax, wl, {"heading": heading, "question": question})
        new = ie_store.dumps(res.issue_areas)
        changed += new != (areas or "[]")
        conn.execute("UPDATE ie_questions SET areas=?, matched_terms=?, tier=? WHERE question_key=?",
                     (new, ie_store.dumps(res.matched_terms), res.tier, key))
    conn.commit()
    log("ie-questions: reclassified; {0} question(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    log("  store: {0} question(s) on our ground ({1} oral), {2} week(s) read, {3} question(s) "
        "read in them".format(
            n("SELECT COUNT(*) FROM ie_questions"),
            n("SELECT COUNT(*) FROM ie_questions WHERE qtype='oral'"),
            n("SELECT COUNT(*) FROM ie_windows WHERE feed='questions' AND status='read'"),
            n("SELECT COALESCE(SUM(records),0) FROM ie_windows WHERE feed='questions' "
              "AND status='read'")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--since", default=roll.DAIL_START)
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="list the due weeks; fetch nothing")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        return 0
    if args.dry_run:
        weeks = ie_store.due_weeks(conn, WINDOW_FEED, args.since, today, REREAD_DAYS)
        print("ie-questions: {0} week(s) due, newest {1}, oldest {2}. Nothing fetched.".format(
            len(weeks), weeks[0] if weeks else "-", weeks[-1] if weeks else "-"))
        return 0
    client = HttpClient(raw_dir=args.raw_dir)
    weeks, total, ours, gaps = pull(conn, client, today, since=args.since,
                                    budget=drain.Budget(args.budget_seconds))
    print("ie-questions: {0} week(s) read, {1} question(s), {2} on our ground, {3} gap(s)".format(
        weeks, total, ours, gaps))
    if not gaps:
        ie_store.stamp(conn, HEARTBEAT, today, "step heartbeat: tools/ie_questions.py")
        conn.commit()
    summary(conn)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
