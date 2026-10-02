"""Alberta Hansard speeches (tools/prov_speeches.py --prov ab).

PDF ONLY, and readable: pypdf gives the two-column pages in reading order
(measured 2 October 2026 on 3 December 2024: a megabyte, 39 pages).

THE SOURCE: the session's transcripts listing,
/assembly-business/transcripts/transcripts-by-type?legl=31&session=1, which
links every sitting's Hansard ("...\\legislature_31\\session_1\\
20241203_1330_01_han.pdf"; the backslashes are turned, nothing is built).
The time token is the sitting's own: a day with a morning, afternoon and
evening sitting is three records (_1000_, _1330_, _1930_).

  head: Oral Question Period                    the rubric ('head:' is printed)
   Support for Firefighters, Doctors, and Nurses   a subject: one line, then a label
  Ms Gray: Mr. Speaker, we all know ...          a turn
   Other front-line workers deserve ...          an indented line opens a paragraph
  head: Government Bills and Orders
   Third Reading / Bill 26 / Health Statutes Amendment Act, 2024 (No. 2)

Running heads ("2300 Alberta Hansard December 3, 2024"), clock lines and
"[The Deputy Speaker in the chair]" are dropped. The labels carry a narrow
no-break space ("Ms\\u202fGray").

WHO SPOKE: surnames only ("Mr. Nicolaides", "Member Irwin", "Ms Smith"),
against the dated terms of the members' own pages (prov_ab.fetch_roster,
read here once if the vote collector has not read that legislature yet).
Two members of one surname on the day (the Sigurdsons, the Wrights) are
ambiguous and stay unattributed: the Hansard prints no riding for them.
"""

from __future__ import annotations

import html as _html
import re

from src import prov_names as pn, prov_speeches as sp
from src.ingest import prov_ab as base
from src.prov_fetch import pdf_text

PROV = "ab"
LANGUAGE = "en"
CURRENT_SESSION = base.CURRENT_SESSION
LISTING = base.BASE + "/assembly-business/transcripts/transcripts-by-type?legl={0}&session={1}"

_HREF = re.compile(r'href="([^"]*?(\d{8})_(\d{4})_\d{2}_han\.pdf)"', re.I)
_SPACES = re.compile("[  -​  　]")
_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_FURNITURE = re.compile(
    r"^(?:=====PAGE|" + _MONTH + r"\s+\d{1,2},\s+\d{4}\s+Alberta Hansard\s+\d+|\d+\s+Alberta Hansard\s+"
    + _MONTH + r"\s+\d{1,2},\s+\d{4}|Legislative Assembly of Alberta|Title:.*|"
    r"\d{1,2}:\d{2}(?:\s*[ap]\.m\.)?(?:\s+\w+day,.*)?|\d{1,4})$")
_LABEL = re.compile(r"^(?P<l>(?:The|An|Some|Hon\.|Mr\.?|Mrs\.?|Ms\.?|Miss|Dr\.|Member|MLA)\s+[^:]{1,60}?)\s*:\s+(?P<r>.*)$")
_THE = re.compile(r"^The\s+(?:Deputy\s+|Acting\s+)?(?:Speaker|Chair|Clerk|Premier|Sergeant)", re.I)
_PARTICLES = {"de", "van", "von", "la", "le", "of", "the", "for"}
_CLOCK = re.compile(r"^\d{1,2}:\d{2}\s+(?=\S)")
_BILL_LINE = re.compile(r"^Bill\s+(?:Pr\s?)?\d{1,3}\s*$")
# Headings inside a debate, not a new one: the bill and its debate go on.
SUB_HEADINGS = ("Debate Continued", "Point of Order", "Points of Order", "Speaker’s Ruling",
                "Speaker's Ruling")


def is_label(line):
    m = _LABEL.match(line)
    if not m:
        return None
    lab = m.group("l").strip()
    words = re.sub(r"\([^)]*\)", "", lab).split()
    if len(words) > 6:
        return None
    if lab.startswith("The ") and not _THE.match(lab):
        return None
    if lab.startswith(("An ", "Some ")) and "Member" not in lab:
        return None
    if any(w[:1].islower() and w.lower() not in _PARTICLES for w in words[1:]):
        return None
    return lab, m.group("r")


def parse_pdf(text):
    lines = [_SPACES.sub(" ", l).rstrip() for l in (text or "").splitlines()]
    start = next((i for i, l in enumerate(lines) if l.startswith("head:")), len(lines))
    kept = []
    for l in lines[start:]:
        s = l.strip()
        if not s or _FURNITURE.match(s):
            continue
        kept.append(l)
    blocks, para, heading = [], None, None

    def flush():
        nonlocal para
        if para is not None:
            blocks.append(para)
            para = None

    for i, l in enumerate(kept):
        s = _CLOCK.sub("", l.strip())
        if s.startswith("head:"):
            flush()
            blocks.append(("rubric", s[5:].strip()))
            heading = []
            continue
        lab = None if l.startswith(" ") else is_label(s)
        if lab:
            flush()
            if heading:
                text = " — ".join(heading)
                blocks.append(("subject", text, sp.bill_number(text)))
            heading = None
            para = ("label", lab[0], lab[1])
            continue
        if s.startswith("[") and s.endswith("]"):
            flush()
            blocks.append(("proc", s))
            continue
        if heading is not None:
            heading.append(s)
            continue
        if _BILL_LINE.match(s):
            # "3:50  Bill 27" then " Education Amendment Act, 2024": the next
            # bill's heading, printed without a 'head:' line.
            flush()
            heading = [s]
            continue
        if s in SUB_HEADINGS:
            flush()
            blocks.append(("subsubject", s))
            continue
        nxt = kept[i + 1] if i + 1 < len(kept) else ""
        if (l.startswith(" ") and len(s) <= 100 and not re.search(r"[.?!:;,”\"]$", s)
                and not nxt.startswith(" ") and is_label(nxt.strip())):
            flush()
            blocks.append(("subject", s, sp.bill_number(s)))
            continue
        if l.startswith(" ") or para is None:
            flush()
            para = ("para", s)
        else:
            para = para[:-1] + (para[-1] + " " + s,)
    flush()
    return sp.turns_from_blocks(blocks)


def list_days(ctx, session):
    leg, sess = base.parse_session(session)
    url = LISTING.format(leg, sess)
    html = ctx.text(url, "transcripts-{0}-{1}".format(leg, sess))
    out, seen = [], set()
    for href, ymd, hhmm in _HREF.findall(html or ""):
        link = _html.unescape(href).replace("\\", "/")
        if "/hansards/han/legislature_{0}/session_{1}/".format(leg, sess) not in link or link in seen:
            continue
        seen.add(link)
        date = "{0}-{1}-{2}".format(ymd[:4], ymd[4:6], ymd[6:])
        out.append({"key": "ab-{0}-{1}-{2}-{3}".format(leg, sess, date, hhmm), "date": date, "part": hhmm,
                    "legislature": leg, "session": sess, "url": link})
    if html and not out:
        ctx.gap("ab transcripts {0}: no Hansard PDFs parsed from {1}".format(session, url))
    have = ctx.conn.execute("SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND legislature=? "
                            "AND source='member-page'", (PROV, leg)).fetchone()[0]
    if out and not have and not ctx.dry_run:
        base.fetch_roster(ctx, leg)
    return sorted(out, key=lambda d: d["key"])


def read_day(ctx, day):
    raw = ctx.bytes(day["url"], "hansard-{0}".format(day["key"]), archive=True)
    if raw is None:
        return None, ["the Hansard PDF was not fetched"]
    return parse_pdf(pdf_text(raw)), []


def resolver(ctx):
    return pn.Resolver.from_conn(ctx.conn, PROV)
