"""General comments and recommendations from the treaty bodies.

A General Comment is how a treaty gets reinterpreted. General Comment 36 read
abortion into the right to life, and that outlasts any resolution -- it becomes
the lens every future review applies. So this is the most consequential thing
the monitor can watch, and until 2026-08-17 it watched none of it.

WHAT THIS GIVES AND DOES NOT GIVE. tbinternet's document search
(`TBSearch.aspx?DocTypeID=11`) lists general comments that have been ADOPTED,
with their treaty body and year. That is worth having: knowing a binding
interpretation has landed on our ground matters even after the fact.

It is NOT the consultation window. Draft general comments go out for public
comment before adoption, and that is the campaignable moment -- but every
OHCHR page that lists open consultations answers 403 to a non-browser client
(Cloudflare challenge, the same block as the UPR pages). So this feed tells you
what the treaty bodies have DECIDED, not what they are deciding. Recorded
rather than glossed, because the difference is the difference between a
campaign and a briefing.

ROBOTS.TXT (13 October 2026). tbinternet.ohchr.org/robots.txt now reads
"User-agent: * / Disallow: /". fetch_general_comments therefore sends every
request through the robots guard (src/robots_guard.GuardedClient, the reader
the provinces use: RFC 9309 matcher, patient read, 24-hour cache): while the
host disallows us it raises RobotsRefused (a FetchError) and the search is
never fetched; tools/un_comments.py prints "could not read: robots.txt
disallows ..." and stores nothing. It resumes by itself if the robots.txt
relents. Never routed around: no cache, no Wayback copy, no other agent.

ALTERNATIVE ROUTES TRIED, 13 October 2026 (docs/un-sources.md keeps the
table). The standing rule is to look for a legitimate other route before
recording a gap. None was found for general comments or for calls for
comments on draft general comments:

  - docs.un.org by symbol (CEDAW/C/GC/40, CRC/C/GC/26, CCPR/C/GC/37 ...):
    the page is a frame over documents.un.org/api/symbol/access, and
    ?direct=true answers 302 to the same address. documents.un.org's
    robots.txt disallows /api, /doc and /access; so do daccess-ods.un.org and
    documents-dds-ny.un.org. Not used.
  - UN Digital Library (digitallibrary.un.org): record pages are allowed but
    can only be found through /search, which robots.txt disallows (it
    answers 202 with an empty body in any case); the sitemap answers the same
    empty 202. Not used.
  - Universal Human Rights Index (uhri.ohchr.org): a documented REST API and
    a daily full export, but of treaty body RECOMMENDATIONS (concluding
    observations, UPR, special procedures), not general comments; the API
    itself is by arrangement (uhrisupport@ohchr.org). A lead for concluding
    observations, not for this feed.
  - Indico.UN (indico.un.org, no robots.txt): carries the committees'
    sessions (now the treaty body calendar, src/ingest/un_calendar.py), but
    no general comments and no calls for comments.
  - UN Journal, Geneva (journal-api.un.org): treaty body meetings by number
    only ("3022nd meeting, 93rd session"), closed, no agenda.
  - The calls for comments on draft general comments are listed only on
    www.ohchr.org (Cloudflare challenge since 13 October 2026) and tbinternet
    (robots.txt Disallow: /).
Still worth asking, by a human: whether OHCHR would allow an identified
monitor on tbinternet, or offers the treaty body documents as a feed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TB_SEARCH = ("https://tbinternet.ohchr.org/_layouts/15/treatybodyexternal/"
             "TBSearch.aspx?Lang=en&DocTypeID=11")

# Flagged by COMMITTEE, not by keyword. The listing TRUNCATES titles -- "
# Addendum to General Recommendation No. 30 on women i..." -- so classifying on
# them missed all ten rows on the first run. CEDAW, CRC and CCPR general
# comments are our ground by definition: these are the bodies that have read
# abortion and sexuality education into treaty text. CMW, CERD, CAT and CESCR
# are listed but never flagged.
OURS = ("CEDAW", "CRC", "CCPR")

_TAGS = re.compile(r"<[^>]+>")
# "General comment No. 27 (2025) on ..." / "Joint general recommendation No. 39"
_NUMBER = re.compile(r"No\.?\s*(\d+)", re.I)
_YEAR = re.compile(r"\((20\d\d)\)")


@dataclass
class GeneralComment:
    treaty: str                   # CEDAW | CRC | CCPR | CESCR | ...
    number: str
    year: str
    title: str

    @property
    def ours(self):
        return any(self.treaty.upper().startswith(t) for t in OURS)

    @property
    def symbol(self):
        """A stable id. Not an official document symbol -- the listing does not
        give one -- so it is constructed and marked as ours by shape."""
        return "{0}/GC/{1}".format(self.treaty, self.number or "?")

    @property
    def url(self):
        # The listing links through a JavaScript grid, so the search page is
        # the honest destination rather than a fabricated deep link.
        return TB_SEARCH


def _clean(html):
    return re.sub(r"\s+", " ", _TAGS.sub("", html)).replace("\xa0", " ").strip()


def parse_general_comments(html):
    """Rows from the treaty body document search.

    The table is Title | Document type | Treaty | Country. Rows are kept only
    where the document type says general comment, so a layout change that
    reorders columns yields nothing rather than nonsense.
    """
    out, seen = [], set()
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html or "", re.S):
        cells = [_clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue
        title, doctype, treaty = cells[0], cells[1], cells[2]
        if "general comment" not in doctype.lower():
            continue
        number = _NUMBER.search(title)
        year = _YEAR.search(title)
        item = GeneralComment(treaty=treaty, number=number.group(1) if number else "",
                              year=year.group(1) if year else "", title=title)
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        out.append(item)
    return out


def guarded(client, log=print):
    """`client` with every request asking robots.txt first; a client that is
    already a GuardedClient (a caller's, a test's) is used as it is."""
    from src.robots_guard import GuardedClient
    if isinstance(client, GuardedClient):
        return client
    return GuardedClient(client, "tb", log=log)


def fetch_general_comments(client, log=print):
    """General comments from the treaty body search, robots.txt permitting.

    Raises RobotsRefused (src/robots_guard, a FetchError) without sending the
    request while tbinternet's robots.txt disallows it.
    """
    return parse_general_comments(
        guarded(client, log=log).get_text(TB_SEARCH, "tb", "general-comments"))
