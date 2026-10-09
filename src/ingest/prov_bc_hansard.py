"""British Columbia Hansard speeches (tools/prov_speeches.py --prov bc).

THE SOURCE: the House transcripts the vote collector already lists, from the
session's debates JSON (src/ingest/prov_bc.list_records: one file per
morning or afternoon, "20260219am-Hansard-n119.html", 175 KB measured 2
October 2026). Committee rooms' transcripts are not in that listing and are
not read.

  <p class="Business-Heading">Oral Questions</p>          the rubric
  <p class="Subject-Heading">Lavina "Lee" Charles</p>      the subject
  <p class="SpeakerBegins"><span class="Speaker-Name">Hon. Ravi Parmar</span>
     <span class="Bold">:</span> ...</p>
  <p class="SpeakerContinues">...</p>                     the same turn
  <table class="DivisionTable">                           a division: ends the turn

That is the 2025- markup. Before it the label is an 'Attribution' span with
the colon inside (2009-2017, upper-case and unquoted in 2015) or an
'attribution' span with an id (2018-2024); the blocks are read with the vote
reader's grammar (prov_bc._BLOCK), which knows every markup since 2009.
Until 7 October 2026 only 2025- was read: the speeches backfill left 1,481
days of 2010-2024 owed with "no speaker turns parsed".

WHO SPOKE: full names ("Hon. David Eby", "Korky Neufeld") from 2025, initial
and surname before ("Hon. P. Bell", "N. Macdonald"), against BC's dated terms
of the day (the LIMS members API, and members the API's roster lacks found
on the Hansard lists, source 'hansard-list'), unique-or-nothing, with the
reviewed other surnames ('Herbert', 2009). The roster is read here once if
the vote collector has not stored that parliament yet.
"""

from __future__ import annotations

import json
import re

from src import prov_names as pn, prov_speeches as sp
from src.ingest import prov_bc as base

PROV = "bc"
LANGUAGE = "en"
CURRENT_SESSION = base.CURRENT_SESSION

# The speaker label, in every markup since 2009, read on the vote reader's
# block grammar (prov_bc._BLOCK: classes compared folded, upper-case and
# unquoted markup, a paragraph never running into a table):
#   2025-   <span class="Speaker-Name">Hon. Ravi Parmar</span><span class="Bold">:</span>
#   2018-24 <span class="attribution" id="tt5945">S. Cadieux: </span>
#   2009-17 <span class="Attribution">Hon. C. Oakes: </span>   (2015: <SPAN class=Attribution>)
# Before 2025 a member is printed by initial and surname ("N. Macdonald"),
# which the resolver matches against the day's terms, unique-or-nothing.
# Some days split one name over several spans -- <span class="Speaker-Name">Sheldon</span>
# <span class="Speaker-Name"> Clare</span> (13 May 2025 pm, 20 Apr 2026 am: no turn
# resolved until the spans were joined, 9 Oct 2026).
_NAME = re.compile(r'^\s*(?:<a\b[^>]*>\s*</a>\s*)?'
                   r'((?:<span\b[^>]*\bclass="?(?:Speaker-Name|attribution)"?[^>]*>.*?</span>\s*)+)'
                   r'(?:<span\b[^>]*\bclass="?Bold"?[^>]*>\s*:\s*</span>|:)?(.*)$', re.S | re.I)


def parse_day(html):
    blocks = []
    for m in base._BLOCK.finditer(html or ""):
        cls, inner = m.group(1) or m.group(2), m.group(3)
        # the printed page number inside a speech ('[ Page 5678 ]', 2009-2017) is not speech
        inner = base._PAGE_NUMBER.sub(" ", inner or "")
        if m.group(4) is not None:
            blocks.append(("break",))
            continue
        k = base._klass(cls)
        if k in ("businessheading", "businesscontinued", "proceduralheading", "procedureheading"):
            blocks.append(("rubric", sp.text_of(inner)))
        elif k == "subjectheading":
            blocks.append(("subject", sp.text_of(inner), sp.bill_number(sp.text_of(inner))))
        elif k.startswith("speakerbegins"):
            lab = _NAME.match(inner)
            if lab:
                blocks.append(("label", " ".join(sp.text_of(lab.group(1)).split()).rstrip(": "),
                               sp.text_of(lab.group(2)).lstrip(": ")))
            else:
                blocks.append(("para", sp.text_of(inner)))
        elif k == "speakercontinues":
            blocks.append(("para", sp.text_of(inner)))
        else:
            blocks.append(("proc", sp.text_of(inner)))
    return sp.turns_from_blocks(blocks)


def _session(ctx, session):
    leg, sess = base.parse_session(session)
    reply = ctx.post_json(base.GRAPHQL, json.dumps({"query": base.Q_SESSIONS}), "sessions")
    s = base.find_session((((reply or {}).get("data") or {}).get("allSessions") or {}).get("nodes"), leg, sess)
    if not s:
        ctx.gap("bc: session {0} not found in the LIMS sessions list".format(session))
    return leg, sess, s


def list_days(ctx, session):
    leg, sess, s = _session(ctx, session)
    if not s:
        return []
    have = ctx.conn.execute("SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND legislature=? "
                            "AND source='api'", (PROV, leg)).fetchone()[0]
    if not have and not ctx.dry_run:
        base.fetch_roster(ctx, s)
    code = base.session_code(s)
    listing = ctx.text(base.DEBATES.format(code), "debates-{0}".format(code))
    try:
        listing = json.loads(listing) if listing else None
    except ValueError:
        ctx.gap("bc debates list {0}: not JSON".format(code))
        listing = None
    return [{"key": "bc-{0}-{1}-{2}-{3}".format(leg, sess, date, part), "date": date, "part": part,
             "legislature": leg, "session": sess, "url": url, "issue": issue}
            for date, part, issue, url in base.list_records(listing, code)]


def read_day(ctx, day):
    html = ctx.text(day["url"], "hansard-bc-{0}-{1}-{2}-{3}".format(
        day["legislature"], day["session"], day["date"], day["part"]), archive=True)
    if html is None:
        return None, ["the transcript was not fetched"]
    return parse_day(html), []


def resolver(ctx):
    # BC's dated terms, 'hansard-list' members included, and the reviewed
    # other surnames ('Herbert', 2009)
    return pn.Resolver.from_conn(ctx.conn, PROV).with_record(PROV)
