"""Holyrood forward business: the Chamber and committee agenda, day by day.

Routes, probed from the laptop 15 October 2026 with the identified UA
(docs/devolved-forward-scope.md has the full table):

  * www.parliament.scot/chamber-and-committees/business-bulletin and every
    other old path (future-business, business-programme, todays-business)
    answer 301 to webarchive.nrscotland.gov.uk: the new site sends any path
    it does not know to the National Records archive. Not used.
  * www.parliament.scot/chamber-and-committees/whats-on-and-watch-live/whats-on
    ?dateFrom=YYYY-MM-DD is the new site's own "What's on": the Business
    Bulletin's forward sections rendered per day -- the Chamber's programme
    (each item's title, and inside it the members' business motion or the
    oral questions lodged) and each committee meeting's numbered agenda with
    the committee's page link. robots.txt (www.parliament.scot) disallows only
    /sitecore, /temp, /upload and similar; /chamber-and-committees is open.
    The day strip runs about four weeks ahead; past the agreed programme a day
    reads "There are no meetings today", and a committee agenda appears about
    a week ahead ("Information will be published when available").
  * data.parliament.scot/api/MotionsQuestionsAnswersMotionsBusiness
    ?motionfilter=programme is the open-data API's list of Business Programme
    motions (S7M-...): the Bureau's agreed programme, two to three sitting
    weeks ahead, as one text per motion. It is the machine fallback for the
    Chamber when the What's on page cannot be read, and it fills a programmed
    day the page does not show yet.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
from dataclasses import dataclass, field

from src.devolved_agenda import clean

SITE = "https://www.parliament.scot"
WHATS_ON = SITE + "/chamber-and-committees/whats-on-and-watch-live/whats-on?dateFrom={0}"
PROGRAMME_URL = ("https://data.parliament.scot/api/"
                 "MotionsQuestionsAnswersMotionsBusiness?motionfilter=programme")
MOTION_URL = SITE + "/chamber-and-committees/votes-and-motions/{0}"

_NO_MEETINGS = "There are no meetings today"
_DATE_H2 = re.compile(r'<h2 class="h2">\s*(?:[A-Za-z]+day)\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*</h2>')
_MONTHS = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"))}
_MOTION_REF = re.compile(r"\bS\d+M-\d{5}\b")


class PageShapeError(ValueError):
    """The page answered but carried neither business nor the no-meetings
    line: the site changed shape, which is a gap, never an empty day."""


@dataclass
class Item:
    dated: str
    body: str                  # "Chamber" or the committee's name
    business: str
    item_time: str = ""
    order: int = 0
    detail: str = ""
    reference: str = ""
    meeting_id: str = ""       # committee meetings: the page's panel id
    url: str = ""
    committee: bool = False
    source: str = "whats-on"


@dataclass
class Day:
    dated: str
    sitting: bool              # False: "There are no meetings today"
    chamber: list = field(default_factory=list)
    committees: list = field(default_factory=list)
    committee_pending: bool = False   # "Information will be published when available"


def _iso(day, month, year):
    m = _MONTHS.get(month.lower())
    return "{0}-{1:02d}-{2:02d}".format(int(year), m, int(day)) if m else None


def _between(text, start, end_markers):
    i = text.find(start)
    if i < 0:
        return ""
    j = len(text)
    for marker in end_markers:
        k = text.find(marker, i + len(start))
        if 0 <= k < j:
            j = k
    return text[i:j]


def parse_whats_on(page, dated):
    """One Day from a What's on page asked for `dated` (YYYY-MM-DD)."""
    page = page or ""
    m = _DATE_H2.search(page)
    if not m or _iso(*m.groups()) != dated:
        raise PageShapeError("What's on {0}: the page names no such day".format(dated))
    url = WHATS_ON.format(dated)
    if _NO_MEETINGS in page and 'id="paneltab1"' not in page:
        return Day(dated=dated, sitting=False)
    if 'id="paneltab1"' not in page and 'id="paneltab2"' not in page:
        raise PageShapeError("What's on {0}: no Chamber or committee panel".format(dated))
    day = Day(dated=dated, sitting=True)

    chamber = _between(page, 'id="paneltab1"', ('id="buttontab2"',))
    blocks = re.split(r'<li class="event content-list__block"', chamber)[1:]
    for n, block in enumerate(blocks, 1):
        title = re.search(r'<h4 class="h4">([\s\S]*?)</h4>', block)
        if not title:
            continue
        business = clean(title.group(1)).replace("\n", " ")
        when = re.search(r'data-date="([^"]*)"', "x" + block[:200])
        acc = re.search(r'class="accordionContent"[^>]*>([\s\S]*)', block)
        detail = clean(acc.group(1)) if acc else ""
        detail = "\n".join(l for l in detail.splitlines()
                           if not l.startswith(("Show Parliamentary", "Further details",
                                                "Official Report available")))
        refs = _MOTION_REF.findall(detail)
        day.chamber.append(Item(
            dated=dated, body="Chamber", business=business,
            item_time=(when.group(1) if when else ""), order=n,
            detail=detail[:4000],
            reference=(refs[0] if len(refs) == 1 else ""),
            url=(MOTION_URL.format(refs[0]) if len(refs) == 1 and
                 business.lower().startswith("members") else url)))

    panel = _between(page, 'id="paneltab2"', ('Questions and answers</', '<footer'))
    if "Information will be published when available" in panel:
        day.committee_pending = True
    for block in re.split(r'<div class="stage-panel__header">', panel)[1:]:
        name = re.search(r'<h4 class="h4">\s*(?:<a href="([^"]*)">)?([\s\S]*?)(?:</a>)?\s*</h4>', block)
        if not name:
            continue
        committee = clean(name.group(2)).replace("\n", " ")
        href = name.group(1) or ""
        curl = (SITE + href) if href.startswith("/") else (href or url)
        when = re.search(r"<p><strong>([^<]*)</strong></p>", block)
        mid = re.search(r'accordionPanelCommittee(\d+)', block)
        meeting = re.search(r"<p>\s*([^<]*Meeting, \d{4}[^<]*)</p>", block)
        acc = re.search(r'class="accordionContent"[^>]*>([\s\S]*)', block)
        body_html = acc.group(1) if acc else ""
        body_html = re.sub(r"<ul[\s\S]*?</ul>", " ", body_html)     # witness lists
        lines = clean(body_html).splitlines()
        items, cur = [], None
        for line in lines:
            num = re.match(r"^(\d{1,2})\.\s+(.*)$", line)
            if num:
                cur = [int(num.group(1)), num.group(2)]
                items.append(cur)
            elif cur is not None and not line.startswith(("For further information",
                                                          "The committee will meet")):
                cur[1] += " " + line
        for order, text in items:
            # "2. Rural Support Plan:  The Committee will take evidence from--"
            split = re.match(r"^(.{3,250}?):(?:\s+|$)(.*)$", text)
            business = (split.group(1) if split else text).strip()
            detail = (split.group(2) if split else "").strip()
            if detail.startswith("(In Private)"):
                business += " (in private)"
                detail = detail[len("(In Private)"):].strip()
            day.committees.append(Item(
                dated=dated, body=committee, business=business,
                item_time=(when.group(1).strip() if when else ""), order=order,
                detail=" ".join([meeting.group(1).strip() if meeting else "", detail]).strip()[:4000],
                reference="", meeting_id=(mid.group(1) if mid else ""),
                url=curl, committee=True))
    if not day.chamber and not day.committees and not day.committee_pending:
        if _NO_MEETINGS in page:
            return Day(dated=dated, sitting=False)
        raise PageShapeError("What's on {0}: panels present but no items read".format(dated))
    return day


# -- the open-data fallback: Business Programme motions --------------------

_DAY = re.compile(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
                  r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")
_SPLIT = re.compile(r"\s*(?:followed by|(?<![\d.])\d{1,2}\.\d{2}\s*[ap]m)\s*")
_TIME = re.compile(r"(\d{1,2}\.\d{2})\s*([ap]m)")


def _text(item_text):
    t = _html.unescape(_html.unescape(item_text or ""))
    t = re.sub(r"<[^>]+>", " ", t).replace("\xa0", " ")
    return t


def parse_programme(motions):
    """{date: [(time, business)]} from Business Programme motions, newest
    motion winning per date. Revisions ("Revision to Business Programme") are
    edits, not programmes, and are skipped: the What's on page carries their
    effect, and this is only the fallback."""
    rows = [m for m in (motions or []) if isinstance(m, dict)
            and (m.get("Title") or "").strip().lower() == "business programme"]
    rows.sort(key=lambda m: str(m.get("SubmissionDateTime") or m.get("ApprovedDate") or ""))
    out, ref = {}, {}
    for m in rows:
        text = _text(m.get("ItemText"))
        text = re.split(r"\(b\)\s", text, maxsplit=1)[0]
        hits = list(_DAY.finditer(text))
        for i, h in enumerate(hits):
            dated = _iso(h.group(2), h.group(3), h.group(4))
            seg = text[h.end(): hits[i + 1].start() if i + 1 < len(hits) else len(text)]
            items, cur_time = [], ""
            pos = 0
            for piece in re.finditer(r"followed by|(?<![\d.])\d{1,2}\.\d{2}\s*[ap]m", seg):
                chunk = " ".join(seg[pos:piece.start()].split())
                if chunk:
                    items.append((cur_time, chunk))
                tm = _TIME.match(piece.group(0))
                if tm:
                    cur_time = tm.group(1).replace(".00", "") + tm.group(2)
                pos = piece.end()
            tail = " ".join(seg[pos:].split()).rstrip(";,. ")
            if tail:
                items.append((cur_time, tail))
            if dated and items:
                out[dated] = items
                ref[dated] = m.get("EventID") or ""
    return out, ref


def programme_items(programme, refs, dated):
    """Chamber Items for one date from parse_programme's output."""
    out = []
    for n, (when, business) in enumerate(programme.get(dated) or [], 1):
        out.append(Item(dated=dated, body="Chamber", business=business,
                        item_time=when, order=n, reference=refs.get(dated, ""),
                        url=MOTION_URL.format(refs[dated]) if refs.get(dated) else WHATS_ON.format(dated),
                        source="business-programme"))
    return out


def weekdays(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += _dt.timedelta(days=1)
