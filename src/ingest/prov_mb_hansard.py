"""Manitoba Hansard speeches (tools/prov_speeches.py --prov mb).

Collected on Christopher's decision of 2 October 2026, as the vote collector
is: gov.mb.ca's robots.txt bans named AI crawlers, not us, and is read on
every run (src/prov_fetch.Robots); if it names us, every fetch is a gap and
we stop. If Manitoba asks us to stop, we stop.

THE SOURCE, never constructed: hansard/hansard_archive.html -> the session's
Hansard calendar (the vote collector's own listing) -> each day's
"vol_77/summary.html" (14 KB) -> the HTML transcript it links, "h77.html"
(about 600 KB of Word HTML, windows-1252, measured 2 October 2026 on 14
October 2021). A day printed in two parts (vol_78a, vol_78b) is two records.

  <h3>Petitions</h3>                                    the rubric
  <h4>Louise Bridge</h4>                                 the subject
  <p class=MsoNormal><b>Mr. Jim </b><b>Maloway</b><b> (Elmwood):</b> ...</p>
  <p class=MsoNormal>      (2) The current structure ...</p>

The day's sitting includes the Committee of Supply when it sits in the
Chamber; "Mr. Chairperson" is the chair.

WHO SPOKE: a member's first label carries the riding ("Hon. Jon Gerrard
(River Heights)") or the office ("Hon. Kelvin Goertzen (Government House
Leader)"); later ones only the surname ("Mr. Goertzen", "MLA Asagwara").
Resolved against the member page of THAT DAY's Hansard PDF -- read through
prov_mb.roster_for_day, as the vote collector reads it on a division day,
when no term covers the day yet. Hansard lags the sitting by days: a day
whose transcript is not out yet is simply not listed.
"""

from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin

from src import prov_names as pn, prov_speeches as sp
from src.ingest import prov_mb as base

PROV = "mb"
LANGUAGE = "en"
CURRENT_SESSION = base.CURRENT_SESSION

_VOL = re.compile(r"/vol_(\d+)([a-z]?)/summary(?:_[a-z])?\.html$", re.I)
# Private members' business prints the bill's question period and its debate
# as headings of the same level as the bill's own.
SUB_HEADINGS = ("Questions", "Debate", "Debate (Continued)", "Questions (Continued)")
_TRANSCRIPT = re.compile(r'href="?(h\d+[a-z]?\.html)"?', re.I)


def parse_day(html):
    return sp.word_html_turns(html, ("h1", "h2", "h3"), ("h4", "h5", "h6"), SUB_HEADINGS)


def list_days(ctx, session):
    leg, sess = base.parse_session(session)
    hl = ctx.text(base.HANSARD_SESSIONS, "hansard-sessions")
    h_url = base.session_pages(hl, base.HANSARD_SESSIONS, "hansard").get((leg, sess)) if hl else None
    if hl and not h_url:
        ctx.gap("mb Hansard: session {0} is not on {1}".format(session, base.HANSARD_SESSIONS))
        return []
    hp = ctx.text(h_url, "hansard-list-{0}".format(session)) if h_url else None
    if not hp:
        return []
    pdfs = base.list_hansard(hp, h_url)
    out, seen = [], set()
    for date, url, _label in base.parse_calendar(hp, h_url, r"summary(?:_[a-z])?\.html(?:#.*)?$"):
        url = urldefrag(url)[0]
        m = _VOL.search(url)
        if not date or not m or url in seen:
            continue
        seen.add(url)
        part = m.group(2) or None
        out.append({"key": "mb-{0}-{1}-{2}".format(leg, sess, date) + ("-" + part if part else ""),
                    "date": date, "part": part, "legislature": leg, "session": sess,
                    "summary": url, "url": url, "pdfs": pdfs})
    if not out:
        ctx.gap("mb Hansard {0}: no day summaries parsed from {1}".format(session, h_url))
    return sorted(out, key=lambda d: d["key"])


def read_day(ctx, day):
    page = ctx.text(day["summary"], "hansard-summary-{0}".format(day["key"]), encoding="cp1252")
    if page is None:
        return None, ["the day's summary page was not fetched"]
    m = _TRANSCRIPT.search(page)
    if not m:
        return None, ["the summary {0} links no HTML transcript".format(day["summary"])]
    url = urljoin(day["summary"], m.group(1))
    day["url"] = url
    html = ctx.text(url, "hansard-{0}".format(day["key"]), encoding="cp1252", archive=True)
    if html is None:
        return None, ["the transcript {0} was not fetched".format(url)]
    turns = parse_day(html)
    problems = []
    if not base.roster_for_day(ctx, day["legislature"], day["date"], day["pdfs"]):
        problems.append("no member page read for the day")
    return turns, problems


def resolver(ctx):
    return pn.Resolver.from_conn(ctx.conn, PROV)
