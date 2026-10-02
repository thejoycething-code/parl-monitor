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

WHO SPOKE: full names ("Hon. David Eby", "Korky Neufeld"), against the LIMS
members API terms of the parliament (src/ingest/prov_bc.fetch_roster, read
here once if the vote collector has not stored that parliament yet).
"""

from __future__ import annotations

import json
import re

from src import prov_names as pn, prov_speeches as sp
from src.ingest import prov_bc as base

PROV = "bc"
LANGUAGE = "en"
CURRENT_SESSION = base.CURRENT_SESSION

_BLOCK = re.compile(r'<p class="([^"]*)"[^>]*>(.*?)</p>|<table class="DivisionTable[^"]*"[^>]*>.*?</table>',
                    re.S)
_NAME = re.compile(r'^\s*(?:<a[^>]*>\s*</a>\s*)?<span class="Speaker-Name">(.*?)</span>\s*'
                   r'(?:<span class="Bold">\s*:\s*</span>|:)?(.*)$', re.S)


def parse_day(html):
    blocks = []
    for m in _BLOCK.finditer(html or ""):
        cls, inner = m.group(1), m.group(2)
        if cls is None:
            blocks.append(("break",))
            continue
        if cls in ("Business-Heading", "Business-continued"):
            blocks.append(("rubric", sp.text_of(inner)))
        elif cls == "Subject-Heading":
            blocks.append(("subject", sp.text_of(inner), sp.bill_number(sp.text_of(inner))))
        elif cls.startswith("SpeakerBegins"):
            lab = _NAME.match(inner)
            if lab:
                blocks.append(("label", sp.text_of(lab.group(1)), sp.text_of(lab.group(2)).lstrip(": ")))
            else:
                blocks.append(("para", sp.text_of(inner)))
        elif cls == "SpeakerContinues":
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
    return pn.Resolver.from_conn(ctx.conn, PROV)
