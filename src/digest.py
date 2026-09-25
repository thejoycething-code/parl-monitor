"""Edition renderer (handoff section 8, docs/digest-template.md).

The digest is a byproduct: this module turns stored records + the bills board
into the Monday markdown edition. Rules enforced here:

  * recess mode (no Commons/Lords chamber events in the edition week): render
    sections 1, 2, 6, 7, 11 plus a return-dates line; deadlines always render;
  * caps: top lines 3-6 (raised from 5 on 2026-08-31 so the RE Core
    Syllabus consultation renders the week the devolved fix landed --
    seven urgent items competed for five lines, and the Slack summary
    already quoted up to six), PQs 5, EDMs 5, demoting NOTE items first;
  * the editorial loop (ACT/WATCH/NOTE, owners, review files) was REMOVED at
    Christopher's decision, 2026-08-21: he creates Asana tasks himself from
    what the monitor surfaces and the briefs it produces. Inclusion and
    prominence are score-driven (triage_score 3 = top line, 2 = section);
  * British spelling, no em dashes;
  * footer discloses any gaps rows for the edition.
"""

from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass, field

from src.board import TBA, order_board

AREA_NAMES = {
    1: "Abortion", 2: "Assisted dying", 3: "Gender medicine (children)",
    4: "Conversion practices", 5: "Sex-based rights", 6: "Parental rights and education",
    7: "Free speech and online safety", 8: "Freedom of religion", 9: "Marriage and family",
    10: "Surrogacy and embryology",
    11: "Migration",
    12: "Prostitution, trafficking and sexual exploitation",
}
# Ordering by triage score, highest first, replacing the retired
# ACT/WATCH/NOTE editorial tags. Line.tag now carries the SCORE (int or None).
TAG_ORDER = {3: 0, 2: 1, 1: 2}


@dataclass
class Line:
    text: str
    tag: str = "NOTE"
    owner: str = None
    url: str = None
    deadline: str = None
    date: str = None      # ISO date, for the Week ahead day grouping
    event: dict = None    # What's On fields for the Week ahead table (2026-09-07)


@dataclass
class Edition:
    week_commencing: str          # ISO date
    number: int
    mode: str                     # 'recess' | 'normal'
    top_lines: list = field(default_factory=list)
    # The recess status line. NOT a top line: it is a standing fact about the
    # week, not something anyone can act on, and while it was inserted at
    # position 0 it pushed five live consultation deadlines down the page
    # (Christopher, 2026-09-24: "Top lines should lead with what's
    # actionable, not recess"). Held separately so it renders LAST and
    # outside the cap -- it can neither lead nor be squeezed out by a busy
    # week. Still one line in Top lines, not a banner: the 2026-08 decision
    # against a separate recess banner or footer stands.
    recess_note: str = None
    board_rows: list = field(default_factory=list)     # board.BoardRow (live + closing)
    week_ahead: list = field(default_factory=list)
    further_ahead: list = field(default_factory=list)   # the 3 weeks after
    votes: list = field(default_factory=list)
    pqs: list = field(default_factory=list)
    pq_rows: list = field(default_factory=list)   # dicts: member/party/seat/heading/url/department/area/date/tag/why
    pq_background: list = field(default_factory=list)  # triage-1 questions: companion page only
    companion_url: str = None                     # full-detail questions page
    taxonomy_version: str = None                  # read from taxonomy.yaml, never hardcoded
    deadlines: list = field(default_factory=list)   # dicts: type/title/url/why/deadline
    si_rows: list = field(default_factory=list)      # dicts: name/url/procedure/act/status/...
    edms: list = field(default_factory=list)
    devolved: list = field(default_factory=list)
    statements: list = field(default_factory=list)
    mp_notes: list = field(default_factory=list)
    spoke: list = field(default_factory=list)      # src/spoke.collect(): debates with speakers and direction
    decisions: dict = None                         # src/decisions.collect(): open / decided / unlogged
    amendment_rows: list = field(default_factory=list)   # amendments to watched Bills, new or decided this week
    report_rows: list = field(default_factory=list)      # committee reports and Government responses
    judgment_rows: list = field(default_factory=list)    # UK court judgments on our ground
    return_dates: dict = field(default_factory=dict)   # {house: ISO date}
    gaps: list = field(default_factory=list)            # [(feed, detail)]
    late_detections: int = 0   # actionable devolved items first seen <21 days from deadline


class DigestError(Exception):
    pass


# -- validation and caps ----------------------------------------------------

def validate(edition):
    """The ACT-owner refusal is retired with the editorial loop: nothing in an
    edition is an assignment any more, so there is nothing to refuse. Kept as
    a hook so render()'s contract (validate first) survives."""
    return None


def _cap(lines, limit):
    """Enforce a section cap: lowest scores demoted first, and WITHIN a
    score, later deadlines demoted before sooner ones (2026-08-31, with
    the devolved fix). Seven score-3 items competed for five lines the
    week the action-window rule landed, and the old stable order kept
    whichever were appended first -- Westminster's -- rather than the
    most urgent. Urgency belongs in Top lines; the cap should agree.
    Undated lines rank after dated ones at the same score."""
    if len(lines) <= limit:
        return lines
    ordered = sorted(lines, key=lambda l: (TAG_ORDER.get(l.tag, 3),
                                           l.deadline or "9999"))
    return ordered[:limit]


# -- line/section rendering -------------------------------------------------

def _fmt_line(line):
    label = line.text
    if line.url:
        label = "[{0}]({1})".format(line.text, line.url)
    body = "- " + label
    extras = []
    if line.deadline:
        extras.append("Deadline: {0}".format(line.deadline))
    if extras:
        body += " (" + "; ".join(extras) + ")"
    return body


def _areas_label(area_csv):
    if not area_csv:
        return ""
    nums = [int(a) for a in str(area_csv).split(",") if str(a).strip().isdigit()]
    return ", ".join(AREA_NAMES.get(n, str(n)) for n in nums)


def recess_line(return_dates):
    """One combined recess top line (single source for recess + return dates).

    Collapses to "Both Houses return <date>" when the dates agree; renders
    per-House otherwise.
    """
    if not return_dates:
        return "Recess: neither House sits this week. Deadlines still apply."
    dates = set(return_dates.values())
    if len(dates) == 1:
        returns = "Both Houses return {0}".format(dates.pop())
    else:
        returns = "; ".join("{0} returns {1}".format(h, d) for h, d in sorted(return_dates.items()))
    return "Recess: neither House sits this week. {0}. Deadlines still apply.".format(returns)


MOVEMENT_KEY = ("*Movement: NEW = first appearance on the board; ▲ moved = stage or next date "
                "changed since last edition; no change = as last edition; closing = final entry, "
                "the bill leaves the board next week.*")


def render_board(rows):
    lines = ["## Active bills board", "",
             "| Bill | Why we track it | House and stage | Next key date | What happens next | Areas | Movement |",
             "|---|---|---|---|---|---|---|"]
    live = [r for r in rows if r.status == "live"]
    closing = [r for r in rows if r.status == "closed"]
    for r in order_board(live) + closing:
        bill = "[{0}]({1})".format(r.title, r.link)
        why = getattr(r, "why", None) or ""
        house_stage = ", ".join(x for x in (r.house, r.stage) if x)
        if r.status == "closed":
            nxt, what, move = "-", r.closed_note or "Closed", "closing"
        else:
            nxt = r.next_key_date
            what = "Awaiting {0}".format(r.stage) if r.next_key_date != TBA else "Date to be announced"
            move = r.movement or "no change"
        areas = _areas_label(getattr(r, "areas", None))
        lines.append("| {0} | {1} | {2} | {3} | {4} | {5} | {6} |".format(
            bill, why, house_stage, nxt, what, areas, move))
    lines.append("")
    lines.append(MOVEMENT_KEY)
    lines.append("")
    return "\n".join(lines)


_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _weekday(iso_date):
    import datetime
    try:
        return _WEEKDAYS[datetime.date.fromisoformat(iso_date).weekday()]
    except (ValueError, TypeError):
        return ""



def render_further_ahead(lines, weeks=8, bill_ids=None):
    """Business on our ground in the EIGHT weeks after this one.

    Three weeks until 2026-09-01, when Caroline's forward-look request
    (2026-08-28) stretched it: a month or two of runway is what turns a
    sighting into a campaign. It sits inside the Week ahead section as a
    sub-block rather than competing with it as a heading of its own
    (Christopher, 2026-08-24). Since 2026-09-07 it is the same five-column
    table as Week ahead: When, What, Where, Why it matters, Sources.
    """
    rows = _event_rows(lines, bill_ids=bill_ids)
    if not rows:
        return None
    out = ["**Further afield** (next {0} weeks)".format(weeks), ""]
    out.extend(_event_table(rows))
    return "\n".join(out).rstrip() + "\n"


def render_week_ahead(lines, week_start=None, bill_ids=None, heading="## What's on"):
    """Section 3: the diary as a table (Christopher, 2026-09-07, option C).

    Until then each line was the judge's why-line alone -- no time, no
    venue, no petition or Bill named, no link -- and every event printed
    twice because its id was a per-process string hash. Now one row per
    event: When (day and clock time), What (the business, linked to its
    substantive source), Where (house and location), Why it matters (the
    judge's line, unedited, with no score badge), Sources (petition, Bill,
    What's On). Business before week_start is dropped: it belongs with the
    votes, not under "ahead".
    """
    rows = _event_rows(lines, week_start=week_start, bill_ids=bill_ids)
    if not rows:
        return None
    out = [heading, ""]
    out.extend(_event_table(rows))
    out.append("")
    return "\n".join(out)



WHATS_ON = "## What's on"


def render_whats_on(edition, bill_ids=None, recess=False):
    """What is coming, in BOTH modes (Christopher, 2026-09-24).

    Until now this block lived only in the sitting-week branch of render(),
    so a recess edition dropped it entirely -- and recess is exactly when
    forward notice is worth most. Measured on the 2026-09-21 edition: two
    scored events were held in further_ahead and shown to nobody, both of
    them after the House returns on 12 October.

    Named "What's on" rather than "Week ahead" because in recess every row
    in it is weeks out, and a heading promising *this* week would be a
    plain misdescription of its own contents. Sub-blocks keep the old
    distinction: the week itself, then Further afield.

    Empty-state wording is mode-specific. "Nothing on our ground in the
    chamber this week" is true but misleading in recess, where the chamber
    is empty for everyone; the recess line says so instead.
    """
    week_ahead = render_week_ahead(edition.week_ahead, edition.week_commencing,
                                   bill_ids, heading=WHATS_ON)
    further = render_further_ahead(edition.further_ahead, bill_ids=bill_ids)
    if not week_ahead and not further:
        return None
    if not week_ahead:
        empty = ("*Neither House sits this week, so nothing is scheduled in "
                 "the chamber. What is already in the diary for their return:*"
                 if recess else
                 "*Nothing on our ground in the chamber this week.*")
        week_ahead = "{0}\n\n{1}".format(WHATS_ON, empty)
    return "\n\n".join(p for p in (week_ahead, further) if p)


_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _clock(hhmm):
    """'16:30' -> '4.30pm'; '' -> None."""
    raw = (hhmm or "").strip()
    if not raw:
        return None
    try:
        h, m = raw.replace(".", ":").split(":")[:2]
        h, m = int(h), int(m)
    except (ValueError, IndexError):
        return raw
    suffix = "am" if h < 12 else "pm"
    return "{0}.{1:02d}{2}".format(h % 12 or 12, m, suffix)


def _when(date_iso, start, end):
    import datetime
    try:
        d = datetime.date.fromisoformat(date_iso)
        day = "{0} {1} {2}".format(_WEEKDAYS[d.weekday()][:3], d.day, _MONTHS[d.month])
    except (ValueError, TypeError):
        day = "date to be announced"
    s, e = _clock(start), _clock(end)
    if s and e:
        clock = "{0}\u2013{1}".format(s.rstrip("am").rstrip("pm") if s[-2:] == e[-2:] else s, e)
    elif s:
        clock = s
    else:
        clock = "after other business"
    return "{0} \u00b7 {1}".format(day, clock)


def _legacy_split(title):
    """'4.30pm, Commons Westminster Hall debate. e-petition ...' -> parts.

    Rows stored before 2026-09-07 carry only the diary label; this reads
    the label back so the table degrades to the same shape.
    """
    head, _, what = (title or "").partition(". ")
    when, _, where = head.partition(", ")
    return when.strip() or None, where.strip() or None, (what or head).strip()


def _minutes(text):
    """Sort key for a clock in either form: '16:30' or '4.30pm'; sequenced
    business ("after other business") sorts last within its day."""
    import re
    m = re.match(r"\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?", text or "")
    if not m:
        return 24 * 60 + 1
    h, mins, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return h * 60 + mins


def _sort_key(line):
    ev = getattr(line, "event", None) or {}
    clock = ev.get("start_time") or _legacy_split(ev.get("title") or "")[0] or ""
    return ((getattr(line, "date", None) or "9999"), _minutes(clock))


def _bill_link(what, ev, bill_ids):
    """The Bill's page: from the event's own BillId, else from the board,
    which knows every Bill on our ground by title. What's On leaves BillId
    empty on most Private Members' Bill entries (the TIA Second Reading of
    2026-09-11 among them), so the board is the usual route."""
    if ev.get("bill_id"):
        return ev["bill_id"]
    text = (what or "").lower()
    for title, bid in (bill_ids or {}).items():
        if title and title.lower() in text:
            return bid
    return None


def _event_rows(lines, week_start=None, bill_ids=None):
    """Deduplicated, sorted rows for the table."""
    import re
    rows, seen = [], set()
    for line in sorted(lines, key=_sort_key):
        date = getattr(line, "date", None)
        if week_start and date and date < week_start:
            continue
        ev = getattr(line, "event", None) or {}
        what = ev.get("description") or ev.get("bill_name")
        legacy_when = legacy_where = None
        if not what:
            legacy_when, legacy_where, what = _legacy_split(ev.get("title") or getattr(line, "text", ""))
        key = (date, ev.get("event_id")) if ev.get("event_id") else (date, (what or "").lower()[:80])
        if key in seen:
            continue
        seen.add(key)
        if ev.get("start_time") or ev.get("house"):
            when = _when(date, ev.get("start_time"), ev.get("end_time"))
            where = ", ".join(x for x in (ev.get("house"), ev.get("type") or ev.get("category")) if x)
        else:
            when = "{0} \u00b7 {1}".format(_when(date, None, None).split(" \u00b7 ")[0], legacy_when or "after other business")
            where = legacy_where or ""
        members = ev.get("members") or []
        lead = (" \u2014 led by " + members[0]) if members else ""
        sources = []
        m = re.search(r"e-petition (\d{5,7})", what or "")
        if m:
            sources.append("[petition](https://petition.parliament.uk/petitions/{0})".format(m.group(1)))
        bid = _bill_link(what, ev, bill_ids)
        if bid:
            sources.append("[Bill](https://bills.parliament.uk/bills/{0})".format(bid))
        url = getattr(line, "url", None) or (
            "https://whatson.parliament.uk/event/cal{0}".format(ev["event_id"]) if ev.get("event_id") else None)
        if url:
            sources.append("[What's On]({0})".format(url))
        # Once the debate has happened and the pull has matched it to its
        # Hansard section, the record itself is the first source
        # (Christopher, 2026-09-07).
        if ev.get("hansard_url"):
            sources.insert(0, "[Hansard]({0})".format(ev["hansard_url"]))
        why = ""
        if ev:  # a why-line exists only when the line text is the judge's, not the label
            why = line.text if line.text != ev.get("title") else ""
        elif getattr(line, "text", "") and not (legacy_when or legacy_where):
            why = line.text
        rows.append({"when": when, "what": (what or "").replace("|", "/") + lead,
                     "where": where, "why": (why or "").replace("|", "/").rstrip(),
                     "sources": " \u00b7 ".join(sources)})
    return rows


def _event_table(rows):
    out = ["| When | What | Where | Why it matters | Sources |", "|---|---|---|---|---|"]
    for r in rows:
        out.append("| {when} | **{what}** | {where} | {why} | {sources} |".format(**r))
    return out


def _fmt_close(deadline_iso, week_start):
    """'Fri 4 Sep . 32 days' merged cell; 'rolling' when no deadline."""
    import datetime
    if not deadline_iso:
        return "rolling"
    d = datetime.date.fromisoformat(deadline_iso)
    days = (d - datetime.date.fromisoformat(week_start)).days
    return "{0} {1} {2} \u00b7 {3} days".format(
        ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d.weekday()], d.day,
        ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][d.month], days)


def render_deadlines(edition):
    """Section 5: consultations + calls for evidence, one date-sorted table.

    Two columns (B2 layout): the item leads with a bold type marker riding in
    front of the title; Closes merges day-date and countdown. Priority tags do
    not appear here: this section is purely what-closes-when, urgency belongs
    in Top lines. SIs (events, not deadlines) follow as note lines.
    """
    # A deadline before the week began is not a deadline, it is a result:
    # Edition 6 (2026-09-07) printed two consultations at "-6 days" and
    # "-3 days" under a heading that promises what closes WHEN. They drop
    # off here; the store keeps them (Christopher, 2026-09-07).
    rows = [r for r in edition.deadlines
            if not (r.get("deadline") and r["deadline"] < edition.week_commencing)]
    if not rows:
        return None
    out = ["## Consultations and calls for evidence", ""]
    if True:
        out.append("| Consultation / call for evidence | Closes |")
        out.append("|---|---|")
        rows = sorted(rows, key=lambda r: r.get("deadline") or "9999")
        for r in rows:
            why = (" " + r["why"].rstrip(".") + ".") if r.get("why") else ""
            out.append("| **{0}** [{1}]({2}).{3} | {4} |".format(
                r["type"], r["title"], r["url"] or "#", why,
                _fmt_close(r.get("deadline"), edition.week_commencing)))
        out.append("")
    return "\n".join(out)


# Absolute by default so the link works from a Slack canvas and an Asana task
# as well as from the partner site itself; settings.partner_site_url overrides.
COMPANION_URL = "https://parl-monitor-partner.vercel.app/questions.html"

QUESTIONS_HEADING = "What ministers were asked - and what they said"


def companion_note(url):
    return ("*Questions and answers are trimmed above. Both in full, for "
            "every question captured, are on the [companion data page]({0}).*"
            .format(url or COMPANION_URL))


def _fmt_pq_date(iso):
    if not iso:
        return "-"
    try:
        d = datetime.date.fromisoformat(iso)
    except ValueError:
        return iso
    return "{0} {1}".format(d.day, d.strftime("%b"))


# "To ask His Majesty's Government," / "To ask the Secretary of State for
# Health and Social Care," / "To ask the hon. Member for Battersea,
# representing the Church Commissioners," -- boilerplate on every single row,
# and the department is already named in the line above. Matched generically
# up to the first comma rather than by a list of offices, which missed the
# Church Commissioners form on its first outing. Bounded at 140 characters
# and refused if the prefix contains a full stop, so a question with no
# preamble at all cannot have its first clause eaten.
# "To ask the Secretary of State for Health and Social Care," / "To ask His
# Majesty's Government," / "To ask the hon. Member for Battersea,
# representing the Church Commissioners," -- boilerplate on every single
# row, and the department is already named in the line above.
#
# Cut at the INTERROGATIVE, not at the first comma. Cutting at the comma
# left "Commonwealth and Development Affairs, if he will hold discussions"
# on the page, because the office is "the Secretary of State for Foreign,
# Commonwealth and Development Affairs" and the comma is inside its name
# (2026-09-25). Non-greedy and bounded, so a question that never reaches an
# interrogative is left whole rather than half-eaten.
_ASK_PREAMBLE = re.compile(
    r"^To ask (?:the |His |Her )?.{0,160}?"
    r"(?=\b(?:what|whether|how|if|when|why|which|pursuant|further to|"
    r"for what|by what|with reference to|in (?:the )?light of|following the|"
    r"given the|to ask)\b)",
    re.I)


def _trim(text, words):
    """The opening of a passage, VERBATIM, cut at a sentence end where one
    falls near the budget and mid-sentence with an ellipsis otherwise.

    Nothing here paraphrases or summarises. A minister's answer is a thing
    they are on the record as having said, and a generated precis of it
    would be words put in their mouth; the standing rule is that we never
    invent a parliamentarian's words. So the edition shortens by DELETING
    from the end and marks the cut, and the companion page carries the
    whole thing.
    """
    parts = (text or "").split()
    if not parts:
        return ""
    if len(parts) <= words:
        return " ".join(parts)
    head = " ".join(parts[:words])
    # Prefer a full stop inside the last third of the budget: a clean
    # sentence reads better than an ellipsis and costs at most a clause.
    cut = head.rfind(". ")
    if cut > len(head) * 0.6:
        return head[:cut + 1]
    return head.rstrip(",;:") + "..."


# -- what kind of reply was it -------------------------------------------
#
# Christopher, 2026-09-25, after seeing four display mockups: "Build A with
# B's labels and D." The three parts are one section -- a lead block of
# quotable positions, the body by area, and a tail of replies that added
# nothing.
#
# Only these four classes are detected by RULE, and only because departments
# phrase them formulaically. Everything else carries no label: "substantive"
# is the absence of one, never a guess. A first attempt classified by
# richer criteria and filed four palliative-care answers under "figures
# given" with no figure in any of them, so the bar here is precision
# measured against the archive, not coverage.
#
#   POSITION  132 of 5,529 archived answers (2.4%). Hand-checked 14 at
#             random on 2026-09-25: 14 genuine stated positions. An earlier
#             pattern also took "will not be", which caught "will not be
#             eligible for relocation" and "will not be made in future" --
#             incidental futures, not positions -- and was dropped.
#   REFERRED / NOT HELD / DEFERRED  the three ways a department answers
#             without answering. These are the tail.
#
# The remaining classes in the mockup -- figures given, policy restated --
# are judgements and belong to the triage model alongside the why-line, not
# to a regex here.
ANSWER_RULES = (
    ("DEFERRED", "Deferred",
     re.compile(r"not be possible to answer this question within the usual", re.I)),
    ("REFERRED", "Referred to an earlier answer",
     re.compile(r"\bI refer the (?:Hon|Rt Hon|right hon|noble)[^.]*to the answer", re.I)),
    ("POSITION", "Position stated",
     re.compile(r"\bno (?:current |immediate |specific )?plans\b"
                r"|\b(?:does|do) not intend to\b", re.I)),
    ("NOT HELD", "Information not held",
     re.compile(r"\bnot (?:centrally )?held\b|\bis not available from published\b"
                r"|\bnot held in a reportable\b", re.I)),
)

# The judge's answer_kind (src/triage.py ANSWER_KINDS), for the two classes
# no rule can reach. Consulted only when no rule fires: a formulaic phrase
# is cheaper and more certain than a model, and the model does not get to
# overrule "I refer the Hon Member to the answer provided on 13 July".
JUDGED_LABELS = {
    "position": ("POSITION", "Position stated"),
    "figures": ("FIGURES", "Figures given"),
    "restated": ("RESTATED", "Existing policy restated"),
}

# Labels whose rows add nothing new, and so go to the tail rather than the
# body. POSITION is deliberately NOT here: "no plans to change the law on
# assisted dying" answers nothing the member asked and is the most
# quotable thing in the edition. RESTATED is (Christopher, 2026-09-25:
# "the questions still take up too much space") -- an answer that restates
# policy without engaging the question is the definition of the tail, and
# the body is 82% of the section's bytes, so this is the only lever that
# moves it.
NO_NEWS = ("REFERRED", "NOT HELD", "DEFERRED", "RESTATED")


def answer_label(row):
    """(key, display) for a reply, or (None, None) when nothing places it.

    Rules first, the judge second. A row the judge never saw simply has no
    label and stays in the body, which is the safe direction: an unjudged
    reply is shown in full rather than silently demoted to a one-liner.
    """
    key, display, _by_rule = _label_and_source(row)
    return key, display


def _label_and_source(row):
    """(key, display, "rule"|"judge"|None). WHO decided matters: only a rule
    match may lead the section, because only a rule identifies the single
    sentence that IS the position."""
    if row.get("holding"):
        return "DEFERRED", "Deferred", "rule"
    answer = " ".join((row.get("answer_text") or "").split())
    if not answer:
        return None, None, None
    for key, display, pattern in ANSWER_RULES:
        if pattern.search(answer):
            return key, display, "rule"
    key, display = JUDGED_LABELS.get((row.get("answer_kind") or "").lower(),
                                     (None, None))
    return key, display, ("judge" if key else None)


def lead_sentence(answer, pattern):
    """The ONE sentence carrying the match, verbatim.

    Verbatim matters more here than anywhere else in the edition: this
    sentence is printed as a quotation with a minister's department against
    it. Sentence bounds are taken from the text itself and nothing is
    rewritten, so the worst failure is an over-long quote, never a
    reworded one. Drafting this section by hand I pluralised "safe access
    zone" to "zones" in a mockup, which is exactly the mistake that must be
    impossible in the renderer.
    """
    text = " ".join((answer or "").split())
    match = pattern.search(text)
    if not match:
        return ""
    start = text.rfind(". ", 0, match.start())
    start = 0 if start < 0 else start + 2
    end = text.find(". ", match.end())
    end = len(text) if end < 0 else end + 1
    return text[start:end].strip()


def _who(r):
    who = r.get("member") or "A member"
    detail = ", ".join(x for x in (r.get("party"), r.get("seat")) if x)
    return "{0} ({1})".format(who, detail) if detail else who


def _cluster(rows):
    """Questions answered with the SAME words, kept together.

    Departments answer related questions with one reply and the API's own
    groupedQuestions field is empty on every record we hold (checked over
    4,750 archived details, 2026-09-24), so the answer text is the only
    evidence of grouping we have. Untreated it is badly misleading: the
    2026-09-21 edition repeated one Cheshire and Merseyside paragraph five
    times under Assisted dying, and a reply that openly read "the
    information requested in HL3448, HL3450, and HL3451" was printed four
    times as though it answered each question separately. 18 of that
    edition's 44 rows were a repeat of an answer already on the page.

    Order is preserved: clusters appear where their first question did.
    """
    order, groups = [], {}
    for r in rows:
        answer = " ".join((r.get("answer_text") or "").split())
        # No answer, or a holding line, means nothing to share.
        key = answer if answer and not r.get("holding") else id(r)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    return [groups[k] for k in order]


def _pq_block(rows):
    """One reply as a block: who asked whom, the questions, then the answer
    in the minister's own words."""
    lead = rows[0]
    headings, seen = [], set()
    for r in rows:
        h = r.get("heading") or "Question"
        if h in seen:
            continue
        seen.add(h)
        headings.append("[{0}]({1})".format(h, r["url"]) if r.get("url") else h)
    askers = []
    for r in rows:
        w = _who(r)
        if w not in askers:
            askers.append(w)
    who = askers[0] if len(askers) == 1 else "{0} and {1} other{2}".format(
        askers[0], len(askers) - 1, "" if len(askers) == 2 else "s")
    out = ["**{0}** - {1} asked {2}, answered {3}".format(
        ", ".join(headings), who, lead.get("department") or "the government",
        _fmt_pq_date(lead.get("date"))), ""]

    # A question is trimmed harder inside a cluster: five questions at the
    # single-question budget would bury the answer they share.
    budget = 38 if len(rows) == 1 else 26
    shown = rows[:4]
    for r in shown:
        asked = _ASK_PREAMBLE.sub("", (r.get("question_text") or "").strip())
        if asked:
            out.append("*Asked:* {0}".format(_trim(asked, budget)))
    if len(rows) > len(shown):
        out.append("*Asked:* and {0} further question{1} in the same group.".format(
            len(rows) - len(shown), "" if len(rows) - len(shown) == 1 else "s"))

    answer = " ".join((lead.get("answer_text") or "").split())
    if lead.get("holding"):
        # A holding answer is the department saying it will answer later.
        # Printed as a real answer it would read as a government position.
        out.append("*Answered:* holding answer only - the department has not "
                   "yet given a substantive reply.")
    elif answer:
        label = ("*Answered:*" if len(rows) == 1
                 else "*Answered* (one reply to all {0}){1}".format(len(rows), ":"))
        out.append("{0} {1}".format(label, _trim(answer, 50)))
    else:
        out.append("*Answered:* answer text not captured; follow the link for "
                   "the reply.")
    why = next((r["why"] for r in rows if r.get("why")), "")
    if why:
        out.append("*Why it matters:* {0}".format(why.rstrip(".") + "."))
    out.append("")
    return out


def _lead_block(group):
    """A stated position, quoted, with what was asked underneath."""
    lead = group[0]
    quote = lead_sentence(lead.get("answer_text"),
                          dict((k, p) for k, _d, p in ANSWER_RULES)["POSITION"])
    if not quote:
        # No rule phrase, so there is no sentence we can point at as THE
        # position. An earlier version fell back to bolding the first forty
        # words, which put an arbitrary opening in a minister's mouth as
        # their stated position and printed the same child-safety
        # boilerplate twice in one edition (2026-09-25). A lead with no
        # identifiable sentence is not a lead.
        return []
    who = _who(lead)
    url = lead.get("url")
    who_linked = "[{0}]({1})".format(who, url) if url else who
    asked = _ASK_PREAMBLE.sub("", (lead.get("question_text") or "").strip())
    out = ["> **{0}**".format(quote), ">"]
    tail = "> {0}, {1} - to {2}".format(
        lead.get("department") or "the government",
        _fmt_pq_date(lead.get("date")), who_linked)
    if asked:
        tail += ", who asked {0}".format(_trim(asked, 30).rstrip("."))
    out.append(tail + ". - *{0}*".format(lead.get("area_label") or "Other"))
    out.append("")
    return out


def _tail_line(group, display):
    """One line for a reply that added nothing: label, what was asked, and
    the department's own words for refusing, so the reader can see it was
    a refusal rather than take our word for it."""
    lead = group[0]
    heading = lead.get("heading") or "Question"
    url = lead.get("url")
    title = "[{0}]({1})".format(heading, url) if url else heading
    who = _who(lead)
    count = ("" if len(group) == 1
             else ", {0} questions".format(len(group)))
    quote = " ".join((lead.get("answer_text") or "").split())
    said = ' "{0}"'.format(_trim(quote, 22)) if quote else ""
    # The area is on every line. Once "restated" joins the tail an area can
    # have nothing at all in the body -- Assisted dying did, on the first
    # run -- and a reader scanning for their issue would conclude the week
    # was silent on it (2026-09-25).
    return "- **{0}** - *{1}* - {2} - {3}, {4}{5}.{6}".format(
        display, lead.get("area_label") or "Other", title, who,
        lead.get("department") or "the government", count, said)


def render_pqs(edition, companion=True):
    """Written questions in three parts (Christopher, 2026-09-25).

    Built from four mockups he compared: "Build A with B's labels and D."

      On the record   replies that state a government position, quoted.
                      One a week on average, and the most usable thing in
                      the section: "no plans to hold talks with the
                      Georgian Government regarding surrogacy services"
                      answers nothing the member asked and is exactly what
                      a campaign quotes.
      By area         everything else, as blocks, grouped by issue area.
      Asked, but not  the replies that pointed elsewhere, said the data is
      answered        not held, or deferred -- one line each rather than a
                      block, because a reader loses nothing by skimming
                      them and loses the section by wading through them.
                      11 of this week's 26 replies.

    A row appears in exactly ONE part. Nothing is capped by count; each
    passage is trimmed by length, verbatim, per _trim().
    """
    # An issue area is the precondition for appearing at all, and so is an
    # ANSWER (Christopher, 2026-09-25: "remove those that are questions but
    # don't yet have answers"). A holding answer is the department saying it
    # will reply later, which is not news; a row with no answer text is one
    # the detail archive has not reached yet and would print an apology
    # where the reply goes. Both are still captured, still on the companion
    # page, and return to the edition the week they are answered.
    #
    # Worth knowing how little this removes on its own: the sweep only ever
    # fetches answered=Answered, so on the 2026-09-21 edition it was ONE row
    # of 44, and 1.5% of the section. The size came out of the body.
    rows_with_area = [r for r in edition.pq_rows
                      if r.get("area")
                      and (r.get("answer_text") or "").strip()
                      and not r.get("holding")]
    if not rows_with_area:
        return None

    grouped = {}
    for row in rows_with_area:
        grouped.setdefault(row["area_label"] or "Other", []).append(row)

    leads, body, tail = [], {}, []
    for label in sorted(grouped, key=lambda k: (-len(grouped[k]), k)):
        for group in _cluster(grouped[label]):
            key, display, source = _label_and_source(group[0])
            if key == "POSITION" and source == "rule":
                leads.append(group)
            elif key in NO_NEWS:
                tail.append((group, display))
            else:
                body.setdefault(label, []).append(group)

    total = len(rows_with_area)
    replies = len(leads) + len(tail) + sum(len(gs) for gs in body.values())
    dropped = sum(len(group) for group, _display in tail)
    out = ["## {0}".format(QUESTIONS_HEADING), ""]
    # Both numbers, because they differ and each answers a different
    # question: how much was asked, and how much is worth reading.
    summary = "*{0} question{1} on our issues, answered in {2} repl{3}.".format(
        total, "" if total == 1 else "s", replies, "y" if replies == 1 else "ies")
    if tail:
        summary += (" {0} repl{1}, covering {2} question{3}, added nothing new "
                    "and {4} listed at the end.").format(
            len(tail), "y" if len(tail) == 1 else "ies", dropped,
            "" if dropped == 1 else "s",
            "is" if len(tail) == 1 else "are")
    out.extend([summary.rstrip() + "*", ""])

    if leads:
        out.extend(["### On the record", ""])
        for group in leads:
            out.extend(_lead_block(group))

    for label in sorted(body, key=lambda k: (-len(body[k]), k)):
        groups = body[label]
        asked = sum(len(g) for g in groups)
        out.append("**{0}** ({1} question{2})".format(
            label, asked, "" if asked == 1 else "s"))
        out.append("")
        for group in groups:
            out.extend(_pq_block(group))

    if tail:
        out.extend(["### Asked, but not answered", "",
                    "*The department restated existing policy, pointed to an "
                    "earlier answer, said it does not hold the information, or "
                    "deferred. The full exchange is behind each link.*", ""])
        for group, display in tail:
            out.append(_tail_line(group, display))
        out.append("")

    if companion:
        out.extend([companion_note(edition.companion_url), ""])
    return "\n".join(out).rstrip() + "\n"


BULK_KINDS = {"vote", "edm-signed"}
# Kinds that have a section of their own: repeating them here would print the
# same question twice in one edition, the second time with less detail
# (Christopher, 2026-08-05). Every captured question reaches the questions
# section or its companion page, so nothing is lost by omitting them, and the
# section is simply quiet in recess.
OWN_SECTION_KINDS = {"pq"}


MP_SECTION_MAX = 12
MP_SUBTITLE = ("*Debates and motions from any member of either House touching our "
               "campaign areas this week. Written questions have their own section "
               "above; division votes are counted on member profiles rather than "
               "listed here.*")


def _has_area(event):
    """True when a ledger row carries at least one issue area."""
    try:
        areas = event["areas"]
    except (KeyError, IndexError, TypeError):
        return True          # callers without the column (older fixtures)
    if not areas:
        return False
    return bool(json.loads(areas) if isinstance(areas, str) else areas)


def mp_lines_from_events(events, max_members=MP_SECTION_MAX, skip_kinds=()):
    """V1 lines: one per member, activities merged; bulk kinds never listed.

    Division votes and EDM co-signatures are recorded to the ledger for
    profiles and 5CA, but a single tagged division (hundreds of votes) or a
    popular motion (dozens of signatures) would flood this section -- the
    division renders once in Votes and amendments, the motion once with its
    signature count (Christopher, 2026-08-03: truncate or link, never a big
    list).
    """
    members_seen = []   # ordered member ids
    grouped = {}        # member_id -> {"who": str, "acts": ordered {(kind, line): count}}
    for e in events:
        if e["kind"] in BULK_KINDS or e["kind"] in OWN_SECTION_KINDS or e["kind"] in skip_kinds:
            continue
        # An issue area is the precondition for appearing in a section headed
        # "on our issues". Watchlist name/process hits admit rows to the
        # ledger without one, and a routine dementia question printed here
        # would discredit the whole section.
        if not _has_area(e):
            continue
        mid = e["member_id"]
        if mid not in grouped:
            members_seen.append(mid)
            who = e["name"] or "Member {0}".format(mid)
            detail = ", ".join(x for x in (e["party"], e["seat"]) if x)
            grouped[mid] = {"who": who + (" ({0})".format(detail) if detail else ""), "acts": {}}
        key = (e["kind"].upper(), e["line"] or "")
        grouped[mid]["acts"][key] = grouped[mid]["acts"].get(key, 0) + 1

    lines = []
    for mid in members_seen[:max_members]:
        g = grouped[mid]
        acts = []
        for (kind, line), count in g["acts"].items():
            suffix = " (x{0})".format(count) if count > 1 else ""
            acts.append("**{0}** {1}{2}".format(kind, line, suffix))
        lines.append("**{0}**: {1}".format(g["who"], "; ".join(acts)))
    overflow = len(members_seen) - max_members
    if overflow > 0:
        lines.append("...and {0} more members active this week; all recorded to profiles.".format(overflow))
    return lines


DIRECTION = {
    2: "With us, strongly", 1: "With us", 0: "Neutral or unclear",
    -1: "Against us", -2: "Against us, strongly", None: "Not yet scored",
}
SPOKE_SUBTITLE = ("*Every member who spoke in a debate on our ground, with the "
                  "direction the stance pass read from their own words -- not "
                  "their party's whip. \"Not yet scored\" means the pass has not "
                  "reached that speech.*")
SPOKE_SPEAKERS_CAP = 15
SPOKE_DEBATES_CAP = 8


def render_spoke(blocks, speakers_cap=SPOKE_SPEAKERS_CAP, debates_cap=SPOKE_DEBATES_CAP):
    """Who spoke, and which way (Christopher, 2026-09-07).

    One table per debate on our ground: the member (linked to their exact
    contribution), the direction the stance pass read, and its one-line
    reason. Speeches already sit in the ledger and the stance table -- 20,706
    scored as of today -- but the edition only ever printed "DEBATE Spoke:
    <title>" with no direction, and since the July recess not even that,
    because the weekly sweep searched the coming week instead of the one
    just ended. Committed speakers come first so the cap keeps the members
    who took a side; the profiles hold the rest.
    """
    if not blocks:
        return None
    out = ["**Who spoke, and which way**", "", SPOKE_SUBTITLE, ""]
    ordered = sorted(blocks, key=lambda b: -len(b.get("speakers") or []))
    for b in ordered[:debates_cap]:
        speakers = b.get("speakers") or []
        head = "**{0}**".format((b.get("title") or "Debate").replace("|", "/"))
        bits = [x for x in (b.get("house"), _day(b.get("date"))) if x]
        if b.get("url"):
            bits.append("[Hansard]({0})".format(b["url"]))
        bits.append("{0} speaker{1} on our ground".format(len(speakers), "" if len(speakers) == 1 else "s"))
        out.append(head + " \u00b7 " + " \u00b7 ".join(bits))
        out.append("")
        out.append("| Member | Direction | What they argued |")
        out.append("|---|---|---|")
        ranked = sorted(speakers, key=lambda s: (-(abs(s["stance"]) if s.get("stance") is not None else -1),
                                                 -(s["stance"] or 0) if s.get("stance") is not None else 0,
                                                 s.get("name") or ""))
        for s in ranked[:speakers_cap]:
            who = s.get("name") or "Member {0}".format(s.get("member_id"))
            if s.get("url"):
                who = "[{0}]({1})".format(who, s["url"])
            detail = ", ".join(x for x in (s.get("party"), s.get("seat")) if x)
            if detail:
                who += " ({0})".format(detail)
            times = " (x{0})".format(s["count"]) if (s.get("count") or 1) > 1 else ""
            why = (s.get("why") or "").replace("|", "/").strip()
            out.append("| {0}{1} | {2} | {3} |".format(who, times, DIRECTION.get(s.get("stance"), DIRECTION[None]), why))
        more = len(speakers) - speakers_cap
        if more > 0:
            out.append("")
            out.append("*...and {0} more; every contribution is recorded on the member profiles.*".format(more))
        out.append("")
    more_debates = len(ordered) - debates_cap
    if more_debates > 0:
        out.append("*...and {0} more debate{1} on our ground this week, on the profiles.*".format(
            more_debates, "" if more_debates == 1 else "s"))
        out.append("")
    mentions = sum(b.get("omitted_mentions") or 0 for b in blocks)
    if mentions:
        # Never suppress silently: the passing mentions are not tabled,
        # but the reader is told they exist and where they are.
        out.append("*{0} passing mention{1} of our issues in other business {2} recorded on the "
                   "member profiles, not tabled here.*".format(
                       mentions, "" if mentions == 1 else "s", "is" if mentions == 1 else "are"))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _day(date_iso):
    import datetime
    try:
        d = datetime.date.fromisoformat(date_iso)
    except (TypeError, ValueError):
        return None
    return "{0} {1} {2}".format(_WEEKDAYS[d.weekday()][:3], d.day, _MONTHS[d.month])


def render_mp_section(mp_lines, spoke=None):
    """Parliamentarians on our issues: who spoke (with direction) first,
    then the motions and other acts as one line per member."""
    spoke_md = render_spoke(spoke) if spoke else None
    if not mp_lines and not spoke_md:
        return None
    out = ["## Parliamentarians on our issues", "", MP_SUBTITLE, ""]
    if spoke_md:
        out.append(spoke_md)
    if mp_lines:
        out.extend("- " + (line.text if hasattr(line, "text") else line) for line in mp_lines)
    out.append("")
    return "\n".join(out)


def render_si(edition):
    """Secondary legislation: the bills board's sibling. Primary legislation
    sits on the board; the instruments implementing it sit here."""
    if not edition.si_rows:
        return None
    out = ["## Secondary legislation", ""]
    out.append("| Instrument | Procedure | Status |")
    out.append("|---|---|---|")
    for r in edition.si_rows:
        cell = "[{0}]({1})".format(r["name"], r["url"] or "#")
        context = []
        if r.get("act"):
            context.append("Under the {0}.".format(r["act"]))
        if r.get("why"):
            context.append(r["why"])
        if context:
            cell += " " + " ".join(context)
        links = []
        if r.get("division"):
            d = r["division"]
            links.append("[Commons vote {0}]({1})".format(d.get("result"), d.get("url") or "#"))
        if r.get("text_link"):
            links.append("[full text]({0})".format(r["text_link"]))
        if links:
            cell += " " + " \u00b7 ".join(links)
        out.append("| {0} | {1} | {2} |".format(cell, r.get("procedure") or "TBC", r.get("status") or ""))
    out.append("")
    return "\n".join(out)


def render_amendments(rows, cap=25):
    """Amendments to watched Bills, new or decided this week (2026-09-07)."""
    if not rows:
        return None
    out = ["## Amendments to watched Bills", "",
           "*Every amendment tabled to a Bill on the board is read each week; these are the ones on our "
           "ground that were tabled or decided since the last edition.*", "",
           "| Bill | Amendment | Moved by | What it does | Decision | Why it matters |", "|---|---|---|---|---|---|"]
    ordered = sorted(rows, key=lambda r: ((r.get("bill") or ""), -(r.get("tag") or 0), r.get("label") or ""))
    for r in ordered[:cap]:
        what = (r.get("explanatory") or r.get("summary") or "").replace("|", "/")
        if len(what) > 260:
            what = what[:260].rsplit(" ", 1)[0] + "..."
        flag = "**new** " if r.get("new") else ("**decided** " if r.get("newly_decided") else "")
        out.append("| {0} ({1}) | [{2}]({3}) | {4} | {5} | {6}{7} | {8} |".format(
            (r.get("bill") or "").replace("|", "/"), r.get("stage") or "", r.get("label") or "amendment",
            r.get("url") or "#", r.get("lead") or "", what, flag, r.get("decision_word") or "",
            (r.get("why") or "").replace("|", "/")))
    if len(ordered) > cap:
        out.append("")
        out.append("*...and {0} more on our ground this week, in the store.*".format(len(ordered) - cap))
    out.append("")
    return "\n".join(out)


def render_reports(rows):
    """Committee reports and Government responses on our ground (2026-09-07)."""
    if not rows:
        return None
    out = ["## Committee reports and Government responses", "",
           "| Published | Committee | Publication | Why it matters |", "|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r.get("date") or "", r.get("committee") or "")):
        kind = "**Government response**" if r.get("is_response") else (r.get("type") or "Report")
        dept = " ({0})".format(r["responding_department"]) if r.get("responding_department") else ""
        title = (r.get("title") or "").split(": ", 1)[-1].rsplit(" (", 1)[0].replace("|", "/")
        out.append("| {0} | {1} | {2} [{3}]({4}){5} | {6} |".format(
            _day(r.get("date")) or r.get("date") or "", (r.get("committee") or "").replace("|", "/"),
            kind, title, r.get("url") or "#", dept, (r.get("why") or "").replace("|", "/")))
    out.append("")
    return "\n".join(out)


def render_courts(rows):
    """UK judgments on our ground (2026-09-07)."""
    if not rows:
        return None
    # Christopher, 2026-09-07: judgments are scored for relevance and DESCRIBED,
    # never agreed or disagreed with. The column says so.
    out = ["## Courts", "",
           "*Judgments handed down this week whose text touches our areas, stated as decided. "
           "The monitor takes no view on a judgment.*",
           "", "| Handed down | Court | Case | What was decided |", "|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r.get("date") or "", r.get("court") or "")):
        case = (r.get("title") or "").split(": ", 1)[-1].replace("|", "/")
        # No excerpt fallback: a matched passage from deep in a judgment read as
        # nonsense in the cell ("He was enthusiastic in science lessons").
        # A blank says a line has not been written; junk says nothing true.
        why = (r.get("why") or "").replace("|", "/")
        out.append("| {0} | {1} | [{2}]({3}) | {4} |".format(
            _day(r.get("date")) or r.get("date") or "", r.get("court") or "", case, r.get("url") or "#", why))
    out.append("")
    return "\n".join(out)


def _render_section(title, lines, cap=None):
    if cap is not None:
        lines = _cap(lines, cap)
    if not lines:
        return None
    out = ["## {0}".format(title), ""]
    out.extend(_fmt_line(l) for l in lines)
    out.append("")
    return "\n".join(out)


# -- edition assembly -------------------------------------------------------


def render_devolved(edition):
    """Devolved matters, at the VERY BOTTOM of the edition.

    Christopher's decision 2026-08-24: the devolved legislatures get a place
    in the published monitor. The watching-brief SEPARATION still holds and
    is unchanged -- sp_*/sd_*/ni_* tables still never write items or
    mp_events. This section is a READ at render time, so the structural
    guarantee (a devolved tool cannot inject into the Westminster flow) is
    exactly as it was; only the display changed.

    Deadlines lead, because they are the only part anyone can act on.
    """
    d = edition.devolved or {}
    if not any(d.get(k) for k in ("consultations", "bills", "divisions")):
        return None
    # The old subheading asserted non-actionability as a blanket --
    # jurisdiction as a proxy for actionability -- which is the design
    # assumption docs/parl-monitor-devolved-fix.md removed (2026-08-31).
    # "Devolved" said where; this says what. Christopher, 2026-09-06,
    # deciding that the three chambers stay as a section of this edition
    # rather than an edition of their own (a standalone would have carried
    # two items the week it was measured). Revisit mid-October on four or
    # five sitting weeks of scored volume.
    out = ["## Scotland, Wales and Northern Ireland", "",
           "*Items with an open "
           "response window are briefed and appear in Top lines; the "
           "remainder are a watching brief, recorded because they bear on "
           "our issues.*", ""]

    if d.get("consultations"):
        out.append("**Open government consultations**")
        out.append("")
        out.append("| Consultation | Nation | Closes | Status |")
        out.append("|---|---|---|---|")
        for c in d["consultations"]:
            status = "Briefed" if c.get("actionable") else "Watching"
            if c.get("late"):
                status += " · late detection"
            out.append("| [{0}]({1}) | {2} | {3} | {4} |".format(
                c["title"], c["url"], c["nation"], c["closes"], status))
        out.append("")

    if d.get("bills"):
        out.append("**Bills on our ground**")
        out.append("")
        for b in d["bills"]:
            out.append("- {0} ({1}) - {2}{3}".format(
                b["title"], b["where"], b["stage"],
                " on " + b["date"] if b.get("date") else ""))
        out.append("")

    if d.get("divisions"):
        out.append("**Recent votes**")
        out.append("")
        for v in d["divisions"]:
            out.append("- {0} - {1} ({2})".format(
                v["dated"], v["title"], v["result"]))
        out.append("")
    return "\n".join(out).rstrip()


def render(edition):
    validate(edition)
    recess = edition.mode == "recess"
    parts = ["# Parliamentary Monitor",
             "### Week commencing Monday {0} | Edition {1}{2}".format(
                 edition.week_commencing, edition.number, " | RECESS" if recess else ""),
             ""]

    top_lines = list(_cap(edition.top_lines, 6))
    if edition.recess_note:
        top_lines.append(Line(edition.recess_note, "NOTE"))
    top = _render_section("Top lines", top_lines)
    if top:
        parts.append(top)
    # Decisions needed sit directly under Top lines (Christopher, 2026-09-07):
    # the questions the monitor is waiting on, with owner and date, so a
    # why-line's "still an open decision" cannot recur unlogged.
    from src import decisions as _decisions
    block = _decisions.render(edition.decisions) if edition.decisions else None
    if block:
        parts.append(block)

    # What's on sits directly under Top lines in BOTH modes (Christopher,
    # 2026-09-24). It used to live inside the sitting-week branch alone.
    bill_ids = {r.title: r.bill_id for r in (edition.board_rows or [])
                if getattr(r, "bill_id", None)}
    whats_on = render_whats_on(edition, bill_ids, recess=recess)
    if whats_on:
        parts.append(whats_on)

    if recess:
        # Recess status + return dates render once, as a top line (composed via
        # recess_line() by the orchestrator); no separate banner or footer.
        deadlines = render_deadlines(edition)
        if deadlines:
            parts.append(deadlines)
        # Committees publish and courts sit through recess.
        for block in (render_reports(edition.report_rows), render_courts(edition.judgment_rows)):
            if block:
                parts.append(block)
        # Departments answer written questions through recess, so the section
        # belongs here too: omitting it hid a whole week of real activity
        # (Christopher, 2026-08-05 -- show everything gathered).
        pqs = render_pqs(edition)
        if pqs:
            parts.append(pqs)
        parts.append(render_board(edition.board_rows))
        si = render_si(edition)
        if si:
            parts.append(si)
        mp = render_mp_section(edition.mp_notes, edition.spoke)
        if mp:
            parts.append(mp)
        devolved = render_devolved(edition)
        if devolved:
            parts.append(devolved)
    else:
        section = _render_section("Votes and amendments", edition.votes, None)
        if section:
            parts.append(section)
        amend = render_amendments(edition.amendment_rows)
        if amend:
            parts.append(amend)
        pqs = render_pqs(edition)
        if pqs:
            parts.append(pqs)
        deadlines = render_deadlines(edition)
        if deadlines:
            parts.append(deadlines)
        for block in (render_reports(edition.report_rows), render_courts(edition.judgment_rows)):
            if block:
                parts.append(block)
        for title, lines, cap in [
            ("Early day motions", edition.edms, 5),
            ("Statements and announcements", edition.statements, None),
        ]:
            section = _render_section(title, lines, cap)
            if section:
                parts.append(section)
        parts.append(render_board(edition.board_rows))
        si = render_si(edition)
        if si:
            parts.append(si)
        mp = render_mp_section(edition.mp_notes, edition.spoke)
        if mp:
            parts.append(mp)
        devolved = render_devolved(edition)
        if devolved:
            parts.append(devolved)

    # Footer: disclose gaps.
    parts.append("---")
    if edition.gaps:
        parts.append("**Coverage gaps this edition:**")
        for feed, detail in edition.gaps:
            parts.append("- {0}: {1}".format(feed, detail))
    else:
        parts.append("*No coverage gaps recorded this edition.*")
    if edition.late_detections:
        # The deadline-proximity guard's counter: how many actionable items
        # the monitor first saw under 21 days from their deadline. Visible,
        # not silent -- the Scottish justice consultation reached an edition
        # with 0 days left.
        parts.append("*Late detection: {0} item{1} first surfaced under 21 "
                     "days before the deadline.*".format(
                         edition.late_detections,
                         "" if edition.late_detections == 1 else "s"))
    parts.append("")
    # The version is read from the taxonomy, never hardcoded: the footer sat at
    # v0.2 while the taxonomy had moved to v0.4, on a page partners read.
    parts.append("*Compiled from Parliament's open data feeds via the CitizenGO issue "
                 "taxonomy{0} with human review.*".format(
                     " v" + edition.taxonomy_version if edition.taxonomy_version else ""))
    return "\n".join(parts) + "\n"


def write_edition(conn, edition, editions_dir, generated_at):
    """Render, write the file, and record the edition + gaps rows."""
    import os

    markdown = render(edition)
    os.makedirs(editions_dir, exist_ok=True)
    path = os.path.join(editions_dir, "parliamentary-monitor-{0}.md".format(edition.week_commencing))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    conn.execute(
        "INSERT OR REPLACE INTO editions (week_commencing, generated_at, mode, path) VALUES (?, ?, ?, ?)",
        (edition.week_commencing, generated_at, edition.mode, path),
    )
    # Idempotent per edition: gap rows may already exist (written at pull time
    # and read back into edition.gaps), so rewrite rather than append.
    conn.execute("DELETE FROM gaps WHERE edition = ?", (edition.week_commencing,))
    for feed, detail in edition.gaps:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?, ?, ?)",
                     (edition.week_commencing, feed, detail))
    conn.commit()
    return path
