"""Ontario Hansard speeches (tools/prov_speeches.py --prov on).

THE SOURCE IS THE DAY'S HUB. The page the vote collector already lists for
each sitting (house-documents -> the session page -> .../<date>/hansard,
src/ingest/prov_on.list_sittings) IS the Hansard, in HTML: about 500 KB a
day, measured 2 October 2026 on 24 November 2025 (324 speaker turns). No
query string is ever requested (robots.txt: Disallow: /*?).

  <h2>Members' Statements</h2>                       the rubric
  <h3>Second Tracks</h3>                             the subject
  <p class="speakerStart"><strong>Mr. Brian Saunderson:</strong> ...</p>
  <p>...</p>                                          the same turn
  <p class="procedure">Resuming the debate ... Bill 46 ...</p>
  <p class="voteText">...</p>                         a division list: skipped

Headings are bilingual ("Tenant protection / Protection des locataires");
the English half is kept. A resumed debate names its bill in the procedure
line under the heading, or by its short title only, which is joined to
prov_bills through the title.

WHO SPOKE: full names ("Hon. Doug Ford", "MPP Jamie West"), resolved
against the members list printed in the back of THAT DAY's Hansard PDF --
read through prov_on.roster_for_day, exactly as the vote collector reads it
on a division day, unless a term already starts or ends on the day (trust_store).
"""

from __future__ import annotations

import re

from src import prov_names as pn, prov_speeches as sp
from src.ingest import prov_on as base

PROV = "on"
LANGUAGE = "en"
CURRENT_SESSION = base.CURRENT_SESSION

_BLOCK = re.compile(r"<(h2|h3|p)\b([^>]*)>(.*?)</\1\s*>", re.S | re.I)
# The label may sit inside an OPENING span as well as after empty ones: some
# days print <p class="speakerStart"><span id="para263"><strong>The Speaker
# (...):</strong> ...</span></p>, and 51 sittings (2010-2026) parsed to no turns
# when only self-closing spans were allowed (9 October 2026).
# ... and some print an EMPTY pair first: <span id="para248"></span><strong>
# (3 June 2025; 19 more days, 2010-2026, read on 9 October 2026).
# ... or an anchor first: <a id="para253" name="para253"></a><strong> (2 Nov 2016).
_STRONG = re.compile(r"^\s*(?:</?(?:span|a)\b[^>]*>\s*)*<strong>(.*?)</strong>(.*)$", re.S | re.I)
_START = re.compile(r'<p class="(?:procedure|speakerStart)"')
# The OLDER layout (some 2010-2011 days): no paragraph classes; the day
# opens on "The House met at", speaker turns are plain <p> with a <strong>
# label, rubrics are <p class="th">, subjects <p class="td"> (9 Oct 2026).
# The opening may sit inside an OPEN span: <p><span id="PARA23"><em>The House met (22 Nov 2010).
_START_OLD = re.compile(r"<p>\s*(?:<span[^>]*>\s*)*<em>The House met at", re.I)


def english(heading):
    return re.split(r"\s+/\s+", heading or "")[0].strip() or None


def parse_day(html):
    """Turns from one day's Hansard HTML."""
    m = _START.search(html or "")
    old = False
    if not m:
        m = _START_OLD.search(html or "")
        old = bool(m)
    body = (html or "")[m.start():] if m else ""
    blocks = []
    for tag, attrs, inner in _BLOCK.findall(body):
        tag, cls = tag.lower(), re.search(r'class="([^"]*)"', attrs)
        cls = cls.group(1) if cls else ""
        if tag == "h2":
            blocks.append(("rubric", english(sp.text_of(inner))))
        elif tag == "h3":
            text = english(sp.text_of(inner))
            blocks.append(("subject", text, sp.bill_number(text)))
        elif old and cls == "th":
            blocks.append(("rubric", english(sp.text_of(inner))))
        elif old and cls == "td":
            text = english(sp.text_of(inner))
            blocks.append(("subject", text, sp.bill_number(text)))
        elif "speakerStart" in cls or (old and not cls and _STRONG.match(inner)):
            lab = _STRONG.match(inner)
            if lab:
                blocks.append(("label", sp.text_of(lab.group(1)), sp.text_of(lab.group(2))))
            else:
                blocks.append(("para", sp.text_of(inner)))
        elif "procedure" in cls:
            blocks.append(("proc", sp.text_of(inner)))
        elif cls in ("voteText", "voteDirection", "timeStamp"):
            continue
        elif not cls:
            text = sp.text_of(inner)
            if text:
                blocks.append(("para", text))
    return sp.turns_from_blocks(blocks)


def list_days(ctx, session):
    legislature, sess = base.parse_session(session)
    index = ctx.text(base.HOUSE_DOCS, "house-documents")
    s_url = base.session_page(index, legislature, sess) if index else None
    if index and not s_url:
        ctx.gap("on: session {0} is not on {1}".format(session, base.HOUSE_DOCS))
    page = ctx.text(s_url, "sittings-{0}".format(session)) if s_url else None
    listed = base.list_sittings(page, legislature, sess) if page else []
    if page and not listed:
        ctx.gap("on {0}: no sitting days parsed from {1}".format(session, s_url))
    return [{"key": "on-{0}-{1}-{2}".format(legislature, sess, date), "date": date,
             "legislature": legislature, "session": sess, "url": hub} for date, hub in listed]


def read_day(ctx, day, roster=True):
    html = ctx.text(day["url"], "hansard-on-{0}-{1}-{2}".format(day["legislature"], day["session"], day["date"]),
                    archive=True)
    if html is None:
        return None, ["the day's Hansard page was not fetched"]
    turns = parse_day(html)
    problems = []
    if roster:
        _vps, pdf_url = base.hub_documents(html, day["date"])
        if not base.roster_for_day(ctx, day["legislature"], day["date"], pdf_url, trust_store=True):
            problems.append("no members list read for the day")
    return turns, problems


def resolver(ctx):
    return pn.Resolver.from_conn(ctx.conn, PROV)
