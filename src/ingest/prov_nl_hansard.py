"""Newfoundland and Labrador Hansard speeches (tools/prov_speeches.py --prov nl).

THE SOURCE: the session's Hansard calendar the vote collector reads
(/HouseBusiness/Hansard/ga51session1/, src/ingest/prov_nl.list_records),
one Word-HTML file per sitting ("26-04-01.htm", about 560 KB measured 2
October 2026). The vote collector reads the same files for divisions; this
reader keeps its own record of days read (prov_speech_sittings) and never
touches prov_sittings, so neither marks the other's work done.

  <p align=center><strong>Oral Questions</strong></p>          the rubric
  <p><span><strong>S. STOODLEY: </strong>Thank you ...</span></p>

There are no subject headings. The Clerk reads each bill's title at each
stage -- "CLERK: A bill, An Act to Amend the Schools Act, 1997. (Bill 7)" --
and that reading, never a speech, sets the subject and the bill for what
follows, until the next rubric or the next such reading.

WHO SPOKE: initial and surname in capitals ("S. CROCKER", "PREMIER
WAKEHAM"), resolved with the vote collector's resolver (prov_nl.make_resolver:
the NameResolver plus the reviewed aliases) against the calendar-year terms
of the Members' Attendance summaries, read here for any year the vote
collector has not read yet.
"""

from __future__ import annotations

import re

from src import prov_speeches as sp
from src.ingest import prov_nl as base

PROV = "nl"
LANGUAGE = "en"
CURRENT_SESSION = base.CURRENT_SESSION

_BLOCK = re.compile(r"<p\b([^>]*)>(.*?)</p\s*>", re.S | re.I)
_BILL_READ = re.compile(r"^(?:A bill,?\s*)?[“\"]?(?P<title>An Act\b.*?)[”\"]?[.,]?\s*\(Bill\s+(?P<n>\d+)\)", re.S)
NOT_RUBRICS = ("Division", "Recess", "")


def parse_day(html):
    i = (html or "").find("<body")
    body = (html or "")[i:] if i >= 0 else (html or "")
    blocks = []
    for attrs, inner in _BLOCK.findall(body):
        text = sp.text_of(inner)
        if re.search(r"text-align:\s*center|align=\"?center", attrs, re.I) and not sp.bold_label(inner):
            if text not in NOT_RUBRICS and len(text) <= 120:
                blocks.append(("rubric", text))
            continue
        lab = sp.bold_label(inner)
        if lab:
            label, rest = lab
            if sp.fold_label(label).startswith("clerk"):
                read = _BILL_READ.match(rest)
                if read:
                    blocks.append(("subject", " ".join(read.group("title").split()) +
                                   " (Bill {0})".format(read.group("n")), read.group("n")))
            blocks.append(("label", label, rest))
        elif text:
            blocks.append(("para", text))
    return sp.turns_from_blocks(blocks)


def list_days(ctx, session):
    leg, sess = base.parse_session(session)
    listing_url = base.HANSARD.format(leg, sess)
    html = ctx.text(listing_url, "hansard-{0}-{1}".format(leg, sess))
    records = base.list_records(html or "", listing_url)
    if html and not records:
        ctx.gap("nl Hansard {0}: no sittings parsed from the listing".format(session))
    days = [{"key": "nl-{0}-{1}-{2}".format(leg, sess, r["date"]) + ("-" + r["part"] if r.get("part") else ""),
             "date": r["date"], "part": r.get("part"), "legislature": leg, "session": sess,
             "url": r["url"], "document": r["url"]} for r in records]
    if not ctx.dry_run and not ctx.refresh:
        owe_unresolved(ctx, [d for d in days if ctx.in_window(d["date"])])
    wanted = sorted({int(d["date"][:4]) for d in days if ctx.in_window(d["date"])})
    missing = [y for y in wanted if not ctx.conn.execute(
        "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source NOT LIKE 'party%' "
        "AND COALESCE(start, '0000') <= ? AND COALESCE(end, '9999') >= ?",
        (PROV, "{0}-07-01".format(y), "{0}-07-01".format(y))).fetchone()[0]]
    if missing and not ctx.dry_run:
        base.fetch_roster(ctx, leg, set(missing))
    return days


# Every day read before this date with a speaker turn left unresolved is read
# once more: the roster fixes of 7 October 2026 (credentials read as names,
# 'Ms Burke' under her later surname, terms dated to the by-elections and
# general elections) resolve most of 2012-2015's turns, and a day stored 'ok'
# is otherwise never read again. Turns the new roster still cannot resolve
# (Committee of the Whole witnesses, 2010 with no roster) stay unresolved.
REREAD_BEFORE = "2026-10-08"


def owe_unresolved(ctx, days):
    """Make OWED every listed day stored 'ok' before REREAD_BEFORE with an
    unresolved speaker turn. Returns how many."""
    owed = 0
    for d in days:
        owed += ctx.conn.execute(
            "UPDATE prov_speech_sittings SET status='owed' WHERE sitting_key=? AND status='ok' "
            "AND read_at < ? AND COALESCE(members, 0) > COALESCE(resolved, 0)",
            (d["key"], REREAD_BEFORE)).rowcount
    ctx.conn.commit()
    if owed:
        ctx.log("  nl: {0} Hansard day(s) read before {1} with unresolved speakers; read again".format(
            owed, REREAD_BEFORE))
    return owed


def read_day(ctx, day):
    raw = ctx.text(day["url"], "hansard-{0}".format(day["key"]), encoding="cp1252", archive=True)
    if raw is None:
        return None, ["the Hansard file was not fetched"]
    if "</html>" not in raw[-4000:].lower():
        return None, ["truncated Hansard (no closing </html>)"]
    return parse_day(raw), []


def resolver(ctx):
    return base.make_resolver(ctx.conn)
