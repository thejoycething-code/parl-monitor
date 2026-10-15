"""The countdown: what is coming up on our issues, nearest days first.

Christopher approved the "A · Countdown" layout on 15 October 2026 for the UK
weekly edition (the canvas) and its Monday channel post. One timeline holds
Westminster, the Northern Ireland Assembly, Holyrood, the Senedd and the
devolved governments, every row tagged with where it happens:

  * BIG DATES: the rows the judge scored 3, at most three, inside the 8-week
    horizon, nearest first. Each gets When, Where, issue, a linked title with
    its lead member, and one line of Context (the last Commons vote on the
    issue where the vote tracker has one, else the judge's why-line).
  * THIS WEEK: Monday to Sunday of the edition week, plus "All week" rows for
    bills in committee (Westminster and devolved).
  * FURTHER AFIELD: next Monday to the end of the 8-week horizon.

Slack canvas markdown has no row shading, so a big date is marked in its
table row by bold text and a "BIG DATE" marker in the When cell.

Nothing here writes to the store. The devolved tables are READ, exactly as
the old Devolved section read them: the watching-brief separation stands.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass, field

HORIZON_WEEKS = 8
BIG_MAX = 3
BIG_SCORE = 3
BIG_LABEL = "BIG DATE"

COMMONS, LORDS = "COMMONS", "LORDS"
NI_ASSEMBLY, NI_GOVT = "NI ASSEMBLY", "NI GOVT"
HOLYROOD, SCOT_GOVT = "HOLYROOD", "SCOT GOVT"
SENEDD, WELSH_GOVT = "SENEDD", "WELSH GOVT"
DEADLINE = "DEADLINE"
TAGS = (COMMONS, LORDS, NI_ASSEMBLY, NI_GOVT, HOLYROOD, SCOT_GOVT, SENEDD,
        WELSH_GOVT, DEADLINE)
NATION_GOVT = {"ni": NI_GOVT, "scotland": SCOT_GOVT, "wales": WELSH_GOVT}

# The devolved watching briefs hide migration (area 11) everywhere they are
# shown, as the old Devolved section did (run_weekly.devolved_from_store).
DEVOLVED_HIDDEN = (11,)

NOT_COLLECTED = "Holyrood and Senedd: forward business not collected yet."

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DAYS_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
              "Saturday", "Sunday"]
_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec"]
_MONTHS_LONG = ["", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November",
                "December"]

# What's On categories that add nothing to the title they sit beside.
_QUIET_CATEGORIES = {"private members' bills", "legislation", "main business",
                     "main chamber business"}


# -- dates --------------------------------------------------------------------

def _date(iso):
    try:
        return datetime.date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return None


def day_label(iso):
    """The one date format everywhere: 'Thu 22 Oct'."""
    d = _date(iso)
    if not d:
        return "Not yet dated"
    return "{0} {1} {2}".format(_DAYS[d.weekday()], d.day, _MONTHS[d.month])


def short_day(iso):
    """The Slack post's date column: 'Thu 22'."""
    d = _date(iso)
    return "{0} {1}".format(_DAYS[d.weekday()], d.day) if d else ""


def long_day(iso):
    """'Thursday 22 October', for a big date's heading line."""
    d = _date(iso)
    if not d:
        return "Not yet dated"
    return "{0} {1} {2}".format(_DAYS_LONG[d.weekday()], d.day, _MONTHS_LONG[d.month])


def windows(week_commencing):
    """(week_start, week_end, further_start, horizon_end) as dates. Further
    afield runs from next Monday for 8 weeks -- exactly the window the What's
    On ingest reads (run_weekly.ingest_whatson), so nothing gathered falls
    off the page: from Mon 19 Oct it is Mon 26 Oct to Sun 20 Dec."""
    ws = _date(week_commencing)
    we = ws + datetime.timedelta(days=6)
    fs = we + datetime.timedelta(days=1)
    return ws, we, fs, fs + datetime.timedelta(days=7 * HORIZON_WEEKS - 1)


def span_label(start, end, long=False):
    """'Mon 19 to Sun 25 October' / 'Mon 26 October to 13 December'."""
    if long:
        return "{0} {1} {2} to {3} {4}".format(
            _DAYS[start.weekday()], start.day, _MONTHS_LONG[start.month],
            end.day, _MONTHS_LONG[end.month])
    if start.month == end.month:
        return "{0} {1} to {2} {3} {4}".format(
            _DAYS[start.weekday()], start.day, _DAYS[end.weekday()], end.day,
            _MONTHS_LONG[end.month])
    return "{0} {1} {2} to {3} {4} {5}".format(
        _DAYS[start.weekday()], start.day, _MONTHS_LONG[start.month],
        _DAYS[end.weekday()], end.day, _MONTHS_LONG[end.month])


# -- rows ---------------------------------------------------------------------

@dataclass
class Row:
    date: str = None           # ISO; None for a running ("All week") row
    where: str = ""            # one of TAGS
    title: str = ""            # plain text
    url: str = None
    detail: str = None         # "short debate", "committee stage", ...
    lead: str = None           # lead member
    note: str = None           # the judge's why-line, or a fact about the row
    areas: list = field(default_factory=list)
    score: int = None
    bill_id: int = None
    running: bool = False
    clock: int = 24 * 60 + 1   # minutes, for ordering within a day
    kind: str = "event"        # event | deadline | consultation | ni | sp | sd | running
    extra_md: str = None       # pre-rendered markdown after the title (running rows)
    context: str = None        # set on big dates
    big: bool = False
    venue: str = None          # What's On venue ("Main Chamber", "General Committee", ...)
    session: str = None        # NI committee session line ("Closed, 10:30 AM - 11:00 AM")
    also: list = field(default_factory=list)   # later sittings folded into this row (ISO dates)

    @property
    def when(self):
        return "All week" if self.running else day_label(self.date)

    def sort_key(self):
        return (self.date or "", self.clock, TAGS.index(self.where) if self.where in TAGS else 99,
                self.title.lower())


def issue_label(areas, names=None):
    if names is None:
        from src.digest import AREA_NAMES as names
    seen = []
    for a in areas or []:
        try:
            label = names.get(int(a))
        except (TypeError, ValueError):
            label = None
        if label and label not in seen:
            seen.append(label)
    return " · ".join(seen)


def _clean(text):
    return " ".join(str(text or "").replace("|", "/").split())


_PROCEDURAL = re.compile(r"\b(stage|reading|motion|consent|extension|amendment)\b", re.I)


def _plain_title(title):
    """'Extension of Committee Stage: Conversion Practices (Criminalisation)
    Bill (NIA Bill 45/22-27)' -> 'Conversion Practices (Criminalisation)
    Bill: extension of committee stage'. Bracketed housekeeping goes."""
    t = re.sub(r"\s*\((?:NIA Bill [^)]*|dinner break business|[A-Z][a-z]+ Committee)\)", "", _clean(title))
    m = re.match(r"^([^:]+):\s+(.+\bBill\b.*)$", t)
    if m and _PROCEDURAL.search(m.group(1)) and "Bill" not in m.group(1):
        t = "{0}: {1}".format(m.group(2), m.group(1)[:1].lower() + m.group(1)[1:].lower())
    return t


# Parliamentary filler a reader does not need in a one-line post (round 2,
# Chris, 16 October 2026: "Baroness Deech: age of consent to puberty
# blockers", not a title cut off with "...").
_FILLER = [
    (re.compile(r"^(?:the )?age (?:at which|it would be considered appropriate for) an? "
                r"(?:individual|person|child|young person) (?:to be able to |can |could |should be able to )?"
                r"consent to (?:the administration of )?", re.I), "age of consent to "),
    (re.compile(r"^(?:provision for|the provision of) the ", re.I), ""),
    (re.compile(r"^(?:the )?(?:government's|his majesty's government's) (?:plans|policy|approach) (?:for|on|to) ",
                re.I), ""),
    (re.compile(r"^(?:the )?potential merits of ", re.I), ""),
    (re.compile(r"\s+-\s+(?=(?:committee|report|second|third) (?:stage|reading))", re.I), ", "),
]
_BOUNDARIES = (": ", " - ", ", ", " and ", " on the ", " of the ", " for ", " in ")


def compress(text, limit=64):
    """A title made short by sense, not by length: filler phrases go, then
    the title is cut at the last natural boundary (colon, dash, comma, 'and')
    that fits, and only as a last resort at a word. Never an ellipsis.
    Returns (text, rewritten): rewritten says a filler phrase was removed,
    so the text now starts mid-sentence and reads lower case after a name."""
    t = _clean(text)
    rewritten = False
    for pattern, sub in _FILLER:
        t2 = pattern.sub(sub, t)
        if t2 != t and pattern.pattern.startswith("^"):
            rewritten = True
        t = t2
    if not rewritten and t:
        t = t[:1].upper() + t[1:]
    if len(t) > limit:
        t = re.sub(r"\s*\([^)]*\)", "", t)
    if len(t) > limit:
        head = t[:limit]
        cut = max((head.rfind(b) for b in _BOUNDARIES), default=-1)
        t = head[:cut].rstrip(" ,;:-") if cut >= limit // 2 else head.rsplit(" ", 1)[0].rstrip(" ,;:-")
    return t, rewritten


def short_title(row):
    """The Slack post's text for a row: 'Lead: short title'."""
    title = _plain_title(row.title)
    if row.lead:
        short, rewritten = compress(title, 72)
        base = "{0}: {1}".format(row.lead, short)
    else:
        short, rewritten = compress(title, 80)
        base = short[:1].upper() + short[1:]
    if row.kind in ("deadline", "consultation") and "closes" not in base.lower():
        base += " closes" if row.kind == "consultation" else ", evidence closes"
    return base


def _minutes(hhmm):
    m = re.match(r"\s*(\d{1,2})[:.](\d{2})", hhmm or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 24 * 60 + 1


def house_tag(house, venue=None):
    """What's On house + venue -> tag. Westminster Hall is the Commons; Grand
    Committee is the Lords."""
    h = (house or "").lower()
    v = (venue or "").lower()
    if "grand committee" in v or h.startswith("lord"):
        return LORDS
    if "westminster hall" in v or h.startswith("common"):
        return COMMONS
    if h.startswith("joint"):
        return COMMONS
    return (house or "").upper()


def _legacy(title):
    """Rows stored before 2026-09-07 carry only the diary label:
    '4.30pm, Commons Westminster Hall debate. e-petition ...'."""
    head, _, what = (title or "").partition(". ")
    when, _, where = head.partition(", ")
    return when.strip(), where.strip(), (what or head).strip()


def _bill_for(title, ev, board_titles):
    if ev.get("bill_id"):
        try:
            return int(ev["bill_id"])
        except (TypeError, ValueError):
            pass
    low = (title or "").lower()
    for t, bid in (board_titles or {}).items():
        tl = (t or "").lower()
        if tl and (low.startswith(tl) or low.startswith("the " + tl)):
            return bid
    return None


def from_whatson(line, board_titles=None):
    """A What's On line (digest.Line with .event) -> Row."""
    ev = getattr(line, "event", None) or {}
    title = ev.get("description") or ev.get("bill_name")
    venue = ev.get("type")
    legacy_when = None
    if not title:
        legacy_when, legacy_where, title = _legacy(ev.get("title") or line.text)
        venue = venue or legacy_where
        if not ev.get("house"):
            ev = dict(ev, house=(legacy_where or line.text or "").split(" ")[0].rstrip(":"))
    url = getattr(line, "url", None) or (
        "https://whatson.parliament.uk/event/cal{0}".format(ev["event_id"])
        if ev.get("event_id") else None)
    category = (ev.get("category") or "").strip()
    detail = category.lower() if category and category.lower() not in _QUIET_CATEGORIES \
        and category.lower() not in (title or "").lower() else None
    if (venue or "") == "General Committee":
        detail = "Public Bill Committee"
    members = ev.get("members") or []
    why = ""
    if ev.get("title") is not None or ev.get("event_id"):
        why = line.text if line.text and line.text != ev.get("title") else ""
    tag = line.tag if isinstance(line.tag, int) else None
    return Row(date=getattr(line, "date", None), where=house_tag(ev.get("house"), venue),
               title=_clean(title), url=url, detail=detail,
               lead=members[0] if members else None, note=_clean(why) or None,
               areas=list(getattr(line, "areas", None) or []), score=tag,
               bill_id=_bill_for(title, ev, board_titles),
               clock=_minutes(ev.get("start_time") or legacy_when), kind="event", venue=venue)


def from_deadline(d):
    """A Westminster consultation or committee call for evidence -> Row."""
    evidence = d.get("type") == "Evidence"
    title = _clean(d.get("title"))
    why = _clean(d.get("why"))
    committee = d.get("committee")
    if evidence and committee and why.startswith(committee):
        why = why[len(committee):].lstrip("; ").strip()
    return Row(date=d.get("deadline"), where=DEADLINE, title=title, url=d.get("url"),
               detail="written evidence closes" if evidence else "consultation closes",
               lead=None, note=why or None, areas=list(d.get("areas") or []),
               score=d.get("score"), kind="deadline",
               extra_md=committee)


def board_titles(edition):
    return {r.title: r.bill_id for r in (edition.board_rows or [])
            if getattr(r, "bill_id", None) and r.bill_id > 0}


def rows_from_edition(edition, titles=None):
    """The rows the edition already carries: What's On lines (week_ahead and
    further_ahead) and Westminster deadlines closing inside the horizon."""
    ws, _we, _fs, he = windows(edition.week_commencing)
    titles = board_titles(edition) if titles is None else titles
    rows = [from_whatson(l, titles) for l in list(edition.week_ahead or []) + list(edition.further_ahead or [])]
    rows += [from_deadline(d) for d in edition.deadlines or []
             if d.get("deadline") and ws.isoformat() <= d["deadline"] <= he.isoformat()]
    return rows


def timeline_for(edition):
    """The edition's timeline: as built from the store (run_weekly), or, for
    an edition assembled by hand (tests, tools/make_sample.py), from the
    lines it carries."""
    if edition.timeline:
        return list(edition.timeline)
    rows = rows_from_edition(edition)
    ws, _we, _fs, he = windows(edition.week_commencing)
    nation = {"Scotland": SCOT_GOVT, "Wales": WELSH_GOVT, "N. Ireland": NI_GOVT}
    for c in (edition.devolved or {}).get("consultations") or []:
        d = _date((c.get("closes") or "")[:10])
        if d and ws <= d <= he:
            rows.append(Row(date=d.isoformat(), where=nation.get(c.get("nation"), NI_GOVT),
                            title=_clean(c.get("title")), url=c.get("url"),
                            detail="consultation closes", kind="consultation"))
    rows = fold_sittings(dedupe(rows), edition.week_commencing)
    for r in mark_big(rows, edition.week_commencing):
        r.context = r.note
    return rows


# -- reading the store (read only) -------------------------------------------

def _areas(raw, hidden=DEVOLVED_HIDDEN):
    try:
        got = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [a for a in got if a not in hidden]


def _table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def devolved_consultations(conn, start, end):
    """dg_consultations on our ground closing inside the window."""
    if not _table_exists(conn, "dg_consultations"):
        return []
    cols = [c[1] for c in conn.execute("PRAGMA table_info(dg_consultations)")]
    score_col = "triage_score" if "triage_score" in cols else "NULL"
    why_col = "why_it_matters" if "why_it_matters" in cols else "NULL"
    out = []
    for r in conn.execute(
            "SELECT nation, title, url, closes, areas, {0} AS score, {1} AS why "
            "FROM dg_consultations WHERE closes IS NOT NULL AND closes >= ? AND closes <= ? "
            "ORDER BY closes".format(score_col, why_col), (start.isoformat(), end.isoformat())):
        areas = _areas(r["areas"])
        if not areas:
            continue
        out.append(Row(date=r["closes"], where=NATION_GOVT.get(r["nation"], (r["nation"] or "").upper()),
                       title=_clean(r["title"]), url=r["url"], detail="consultation closes",
                       note=_clean(r["why"]) or None, areas=areas, score=r["score"],
                       kind="consultation"))
    return out


_BILL_NAME = re.compile(r"^(?:[A-Za-z ]*Stage[^:]*:\s*)?(.*?\bBill\b(?:\s*\(NIA Bill [^)]*\))?)")


def _ni_bill_name(text):
    """'Conversion Practices (Criminalisation) Bill: Oral evidence from RaISe'
    -> 'Conversion Practices (Criminalisation) Bill'."""
    m = _BILL_NAME.match(_clean(text))
    if not m or "Bill" not in m.group(1):
        return None
    name = re.sub(r"\s*\(NIA Bill [^)]*\)$", "", m.group(1)).strip(" -:")
    return name or None


def ni_rows(conn, start, end):
    """NI Assembly business on our ground: the forward Order Paper (ni_items
    kind 'plenary') and committee agendas (ni_agenda)."""
    out = []
    if _table_exists(conn, "ni_items"):
        cols = [c[1] for c in conn.execute("PRAGMA table_info(ni_items)")]
        score_col = "triage_score" if "triage_score" in cols else "NULL"
        for r in conn.execute(
                "SELECT title, dated, category, areas, url, {0} AS score FROM ni_items "
                "WHERE kind = 'plenary' AND dated >= ? AND dated <= ? ORDER BY dated".format(score_col),
                (start.isoformat(), end.isoformat())):
            areas = _areas(r["areas"])
            if not areas:
                continue
            cat = (r["category"] or "").strip()
            out.append(Row(date=r["dated"], where=NI_ASSEMBLY, title=_clean(r["title"]),
                           url=r["url"], detail=("plenary" if not cat or cat == "Motion"
                                                 else "plenary, " + cat.lower()),
                           areas=areas, score=r["score"], kind="ni"))
    if _table_exists(conn, "ni_agenda"):
        seen = set()
        for r in conn.execute(
                "SELECT committee, business, item_type, session, dated, areas FROM ni_agenda "
                "WHERE dated >= ? AND dated <= ? ORDER BY dated, item_order",
                (start.isoformat(), end.isoformat())):
            areas = _areas(r["areas"])
            if not areas:
                continue
            key = (r["dated"], (r["business"] or "").lower())
            if key in seen:
                continue
            seen.add(key)
            session = r["session"] or ""
            m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", session)
            clock = 24 * 60 + 1
            if m:
                h = int(m.group(1)) % 12 + (12 if m.group(3) == "PM" else 0)
                clock = h * 60 + int(m.group(2))
            out.append(Row(date=r["dated"], where=NI_ASSEMBLY, title=_clean(r["business"]),
                           detail=_clean(r["committee"]) or None, areas=areas, clock=clock,
                           kind="ni", session=session or None))
    return out


def ni_running(conn, week_start, horizon_end, lookback_days=42):
    """NI bills on our ground in committee: a committee agenda (or an Order
    Paper motion on the committee stage) names them inside the window.
    Returns [(bill name, committee, areas)]."""
    if not _table_exists(conn, "ni_agenda"):
        return []
    since = (week_start - datetime.timedelta(days=lookback_days)).isoformat()
    bills = {}
    for r in conn.execute(
            "SELECT committee, business, item_type, dated, areas FROM ni_agenda "
            "WHERE dated >= ? AND dated <= ? ORDER BY dated DESC",
            (since, horizon_end.isoformat())):
        areas = _areas(r["areas"])
        if not areas:
            continue
        name = _ni_bill_name(r["business"])
        if not name:
            continue
        kind = (r["item_type"] or "").lower()
        if "committee" not in kind and "evidence" not in kind and "deliberation" not in (r["business"] or "").lower():
            continue
        bills.setdefault(name, (name, _clean(r["committee"]), areas))
    return list(bills.values())


def forward_business(conn, start, end):
    """Holyrood and Senedd forward business, from sp_agenda / sd_agenda when
    those tables exist (another collector builds them). Returns
    (rows, note): note is the line to print for whatever is not collected."""
    rows, missing = [], []
    for table, parl, govt, label in (("sp_agenda", HOLYROOD, SCOT_GOVT, "Holyrood"),
                                     ("sd_agenda", SENEDD, WELSH_GOVT, "Senedd")):
        # db.init_db creates both tables (PR #204), so "collected" means the
        # collector has written rows, not that the table exists.
        if not _table_exists(conn, table) or \
                conn.execute("SELECT COUNT(*) FROM {0}".format(table)).fetchone()[0] == 0:
            missing.append(label)
            continue
        cols = [c[1] for c in conn.execute("PRAGMA table_info({0})".format(table))]
        body_col = next((c for c in ("body", "house", "house_body", "chamber") if c in cols), None)
        got = conn.execute(
            "SELECT dated, {0} AS body, business, item_type, {1} AS url, areas, {3} AS item_time FROM {2} "
            "WHERE dated >= ? AND dated <= ? ORDER BY dated".format(
                body_col or "NULL", "url" if "url" in cols else "NULL", table,
                "item_time" if "item_time" in cols else "NULL"),
            (start.isoformat(), end.isoformat())).fetchall()
        for r in got:
            areas = _areas(r["areas"])
            # A booked slot with no subject ("to be announced") or a
            # procedural item cannot be on our ground, whatever it matched.
            if not areas or (r["item_type"] or "").lower() in ("to be announced", "procedural"):
                continue
            body = _clean(r["body"])
            tag = govt if "government" in body.lower() or "minister" in body.lower() else parl
            item_type = _clean(r["item_type"])
            detail = ", ".join(x for x in (item_type[:1].lower() + item_type[1:] if item_type else "",
                                           body if body and body.lower() not in (label.lower(), "chamber", "plenary")
                                           else "") if x) or None
            rows.append(Row(date=(r["dated"] or "")[:10], where=tag, title=_clean(r["business"]),
                            url=r["url"], detail=detail, areas=areas, clock=_minutes(r["item_time"]),
                            kind="sp" if table == "sp_agenda" else "sd"))
    if len(missing) == 2:
        note = NOT_COLLECTED
    elif missing:
        note = "{0}: forward business not collected yet.".format(missing[0])
    else:
        note = None
    return rows, note


def devolved_running(conn, week_start, days=90):
    """Holyrood and Senedd bills on our ground at a committee stage (Stage 1
    or 2) that moved in the last `days`: their own "All week" rows."""
    since = (week_start - datetime.timedelta(days=days)).isoformat()
    out = []
    for table, sql, tag in (
            ("sp_bills", "SELECT name AS title, latest_stage AS stage, latest_stage_date AS dated, areas FROM sp_bills",
             HOLYROOD),
            ("sd_bills", "SELECT title, latest_stage AS stage, stage_date AS dated, areas FROM sd_bills", SENEDD)):
        if not _table_exists(conn, table):
            continue
        for r in conn.execute(sql):
            if not _areas(r["areas"]) or not re.match(r"Stage [12]\b", r["stage"] or ""):
                continue
            if not r["dated"] or r["dated"] < since:
                continue
            out.append((tag, _clean(r["title"]), r["stage"], _areas(r["areas"])))
    return out


# -- vote tracker context -----------------------------------------------------

def load_tracker(conn, path):
    """Signed-off Commons divisions from config/vote_tracker.yaml joined to
    cv_divisions: [{id, date, title, ayes, noes, area, issue, short, bill, url}]."""
    import yaml
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    hidden = set(cfg.get("hidden_areas") or [])
    issues = {i.get("id"): i for i in cfg.get("issues") or [] if i.get("id")}
    out = []
    if not _table_exists(conn, "cv_divisions"):
        return out
    for d in cfg.get("divisions") or []:
        if not d.get("signed_off") or d.get("source") == "hansard":
            continue
        issue = issues.get(d.get("issue")) or {}
        if issue.get("area") in hidden:
            continue
        row = conn.execute("SELECT date, title, ayes, noes FROM cv_divisions WHERE division_id = ?",
                           (d.get("id"),)).fetchone()
        if not row:
            continue
        out.append({"id": d["id"], "date": row["date"], "title": row["title"],
                    "ayes": row["ayes"], "noes": row["noes"], "area": issue.get("area"),
                    "issue": issue.get("name") or d.get("issue"), "short": d.get("short"),
                    "bill": (issue.get("bill") or "").split(" - ")[0].strip(),
                    "url": "https://votes.parliament.uk/Votes/Commons/Division/{0}".format(d["id"])})
    out.sort(key=lambda v: (v["date"], v["id"]), reverse=True)
    return out


def _result(v):
    if v.get("ayes") is None or v.get("noes") is None:
        return ""
    word = "carried" if v["ayes"] > v["noes"] else "rejected"
    return "{0} {1} to {2}".format(word, v["ayes"], v["noes"])


def _on(iso, year):
    d = _date(iso)
    if not d:
        return ""
    return "{0} {1}".format(d.day, _MONTHS_LONG[d.month]) + ("" if d.year == year else " {0}".format(d.year))


def context_for(row, tracker, board_titles=None, year=None, devolved_votes=None):
    """One line of Context: the Commons votes on this bill, else the last
    vote on it in its own legislature (devolved_votes: dicts with where,
    title, date), else the last Commons vote on the row's issue, else the
    judge's why-line."""
    year = year or (_date(row.date).year if _date(row.date) else datetime.date.today().year)
    if row.where in (NI_ASSEMBLY, HOLYROOD, SENEDD):
        name = _ni_bill_name(row.title)
        label = {NI_ASSEMBLY: "NI Assembly", HOLYROOD: "Holyrood", SENEDD: "Senedd"}[row.where]
        if name:
            for v in sorted(devolved_votes or [], key=lambda v: v.get("date") or "", reverse=True):
                if v.get("where") == label and name.lower() in (v.get("title") or "").lower():
                    what = re.split(r":\s+", v["title"])[0] if ":" in v["title"] else v["title"]
                    return "the last Assembly vote on this bill was at {0} on {1}{2}.".format(
                        what if what.lower() != name.lower() else "the bill", _on(v["date"], year),
                        ", " + v["result"].lower() if v.get("result") else "") if row.where == NI_ASSEMBLY \
                        else "the last {0} vote on this bill was on {1}.".format(label, _on(v["date"], year))
    bill_title = None
    if row.bill_id and board_titles:
        bill_title = next((t for t, b in board_titles.items() if b == row.bill_id), None)
    if not bill_title:
        low = row.title.lower()
        bill_title = next((v["bill"] for v in tracker if v["bill"] and low.startswith(v["bill"].lower())), None)
    if bill_title:
        # The division itself must be on the bill (its title starts with the
        # bill's name): an issue card can also hold an Opposition Day vote.
        on_bill = [v for v in tracker if v["bill"] and v["bill"].lower() == bill_title.lower()
                   and (v["title"] or "").lower().startswith(bill_title.lower())]
        if on_bill:
            parts = ["[{0}]({1}) ({2}, {3})".format(v["short"] or "the division", v["url"],
                                                    _topic_case(v["issue"] or ""), _result(v))
                     for v in sorted(on_bill, key=lambda v: v["id"])[:3]]
            return "in the Commons this bill carried votes on {0}, on {1}. {2}".format(
                " and ".join(parts), _on(on_bill[0]["date"], year),
                "Amendments on the same ground can be tabled again at this stage."
                if row.where == LORDS else "").strip()
    for v in tracker:
        if v["area"] in (row.areas or []):
            return "the last Commons vote on this issue was [{0}]({1}), {2} on {3}.".format(
                _clean(v["title"]), v["url"], _result(v), _on(v["date"], year))
    return row.note


# -- key questions ---------------------------------------------------------------

KEY_QUESTIONS_DAYS = 21
KEY_QUESTIONS_MAX = 6
KEY_HIDDEN = (11,)     # migration: collated, never campaigned (as the judgments and the devolved tables)


_TO_ASK = re.compile(r"^(?:To ask (?:the )?(?:Scottish|Welsh|Northern Ireland)? ?(?:Government|Executive|"
                     r"First Minister|Cabinet Secretary[^,]*|Minister[^,]*)[, ]*|To ask the [A-Z][^,]*?,\s*)", re.I)


def _person(name):
    """'Mochan, Carol' -> 'Carol Mochan'."""
    name = _clean(name)
    if name.count(", ") == 1:
        last, first = name.split(", ")
        return "{0} {1}".format(first, last)
    return name


def _first_sentence(text, limit=160):
    t = _clean(re.sub(r"<[^>]+>", " ", text or ""))
    t = _TO_ASK.sub("", t)
    t = t[:1].upper() + t[1:] if t else t
    m = re.match(r"^(.+?[.!?])(\s|$)", t)
    t = m.group(1) if m else t
    return compress(t, limit)[0]


def _numbers(refs):
    """['HL3714', 'HL3710', 'HL3711', ...] -> 'HL3710–HL3714' when they run
    on; else a short list."""
    refs = sorted(set(r for r in refs if r), key=lambda r: (re.sub(r"\d+", "", r),
                                                           int(re.sub(r"\D", "", r) or 0)))
    if len(refs) > 2:
        pre = {re.sub(r"\d+.*$", "", r) for r in refs}
        nums = [re.search(r"(\d+)", r) for r in refs]
        if len(pre) == 1 and all(nums):
            n = [int(x.group(1)) for x in nums]
            if n == list(range(n[0], n[0] + len(n))):
                return "{0}\u2013{1}".format(refs[0], refs[-1])
    if len(refs) > 4:
        return ", ".join(refs[:4]) + " and {0} more".format(len(refs) - 4)
    return ", ".join(refs)


def key_questions(conn, week_commencing, days=KEY_QUESTIONS_DAYS, limit=KEY_QUESTIONS_MAX):
    """Key questions (round 2, 16 October 2026): the most important
    parliamentary questions on our issues answered since the last edition.

    Window: answered in the `days` before the edition's Monday (three weeks,
    not one, so a week whose questions sweep came back thin still surfaces
    the answers the last edition missed). Sources, read only: Westminster
    written questions (items 'pq:%', judge-scored at the Sunday pull),
    Holyrood (sp_items kind 'question'), the Senedd (sd_items) and the NI
    Assembly (ni_items kind 'question'). Only rows on our ground: their areas
    less migration (KEY_HIDDEN).

    Score: the judge's triage_score where the row has one. A devolved row
    the judge has not reached ranks by its taxonomy tier instead (tier 1 ->
    2, tier 2 -> 1); NI rows carry no tier, so an unscored NI question
    counts as 1. Only score 2 or 3 is shown.

    Clusters: several questions from one member, answered the same day, on
    the same area (Westminster: the same department too) become ONE row --
    Baroness Maclean's HL3710-HL3714 of 2 October 2026 is one row, not five.
    Ranked by score, then most recent; at most `limit` rows. Upcoming oral
    questions are rows of the This week / Further afield tables already and
    are not repeated here: only ANSWERED questions are read.
    """
    ws = _date(week_commencing)
    since = (ws - datetime.timedelta(days=days)).isoformat()
    until = ws.isoformat()
    qs = []

    def on_ground(raw):
        return [a for a in _areas(raw, hidden=KEY_HIDDEN)]

    for r in conn.execute(
            "SELECT id, title, url, event_date, triage_score, why_it_matters, issue_areas, extra "
            "FROM items WHERE id LIKE 'pq:%' AND triage_score >= 2 AND event_date >= ? AND event_date < ?",
            (since, until)):
        areas = on_ground(r["issue_areas"])
        if not areas:
            continue
        ex = json.loads(r["extra"]) if r["extra"] else {}
        house = (ex.get("house") or "").lower()
        qs.append({"where": LORDS if house.startswith("lord") else COMMONS, "answered": r["event_date"],
                   "ref": ex.get("uin") or "", "asker": ex.get("member") or "", "url": r["url"],
                   "heading": ex.get("heading") or r["title"], "group": ex.get("department") or "",
                   "score": r["triage_score"], "why": _clean(r["why_it_matters"]), "areas": areas})

    def col(table, name):
        cols = [c[1] for c in conn.execute("PRAGMA table_info({0})".format(table))]
        return name if name in cols else "NULL AS {0}".format(name)

    def tier_score(score, tier):
        if score is not None:
            return score
        return 2 if tier == 1 else 1

    if _table_exists(conn, "sp_items"):
        names = {}
        if _table_exists(conn, "sp_members"):
            names = {m["person_id"]: m["name"] for m in conn.execute("SELECT person_id, name FROM sp_members")}
        for r in conn.execute(
                "SELECT reference, title, answered, msp_id, areas, {0}, {1}, {2}, answer "
                "FROM sp_items WHERE kind = 'question' AND answered >= ? AND answered < ?".format(
                    col("sp_items", "tier"), col("sp_items", "triage_score"), col("sp_items", "why_it_matters")),
                (since, until)):
            areas = on_ground(r["areas"])
            if areas:
                qs.append({"where": HOLYROOD, "answered": r["answered"][:10], "ref": r["reference"] or "",
                           "asker": _person(names.get(r["msp_id"]) or ""), "url": None, "heading": _first_sentence(r["title"], 90),
                           "group": "", "score": tier_score(r["triage_score"], r["tier"]),
                           "why": _clean(r["why_it_matters"]) or _first_sentence(r["answer"]), "areas": areas})
    if _table_exists(conn, "sd_items"):
        for r in conn.execute(
                "SELECT reference, body, answered, member_name, areas, {0}, {1}, {2}, answer "
                "FROM sd_items WHERE kind = 'question' AND answered >= ? AND answered < ?".format(
                    col("sd_items", "tier"), col("sd_items", "triage_score"), col("sd_items", "why_it_matters")),
                (since, until)):
            areas = on_ground(r["areas"])
            if areas:
                qs.append({"where": SENEDD, "answered": r["answered"][:10], "ref": r["reference"] or "",
                           "asker": r["member_name"] or "", "url": None, "heading": _first_sentence(r["body"], 90),
                           "group": "", "score": tier_score(r["triage_score"], r["tier"]),
                           "why": _clean(r["why_it_matters"]) or _first_sentence(r["answer"]), "areas": areas})
    if _table_exists(conn, "ni_items"):
        for r in conn.execute(
                "SELECT reference, title, answered, {0}, areas, {1}, {2}, answer, url "
                "FROM ni_items WHERE kind = 'question' AND answered >= ? AND answered < ?".format(
                    col("ni_items", "tabler"), col("ni_items", "triage_score"), col("ni_items", "why_it_matters")),
                (since, until)):
            areas = on_ground(r["areas"])
            if areas:
                qs.append({"where": NI_ASSEMBLY, "answered": r["answered"][:10], "ref": r["reference"] or "",
                           "asker": r["tabler"] or "", "url": r["url"], "heading": _first_sentence(r["title"], 90),
                           "group": "", "score": tier_score(r["triage_score"], None),
                           "why": _clean(r["why_it_matters"]) or _first_sentence(r["answer"]), "areas": areas})

    clusters, index = [], {}
    for q in sorted(qs, key=lambda q: (-(q["score"] or 0), q["answered"]), reverse=False):
        if (q["score"] or 0) < 2:
            continue
        key = (q["where"], q["asker"].lower(), q["answered"], q["group"], q["areas"][0])
        c = index.get(key)
        if c is None:
            c = {"where": q["where"], "answered": q["answered"], "asker": q["asker"], "score": q["score"],
                 "url": q["url"], "why": q["why"], "areas": list(q["areas"]), "refs": [], "headings": []}
            index[key] = c
            clusters.append(c)
        c["refs"].append(q["ref"])
        h = _clean(q["heading"])
        if h and h not in c["headings"]:
            c["headings"].append(h)
        if not c["why"] and q["why"]:
            c["why"] = q["why"]
    clusters.sort(key=lambda c: c["answered"], reverse=True)
    clusters.sort(key=lambda c: -(c["score"] or 0))
    return clusters[:limit]


def render_key_questions(rows, names=None):
    if not rows:
        return None
    out = ["## Key questions", "",
           "*The most important questions on our issues answered since the last edition, "
           "several from one member on one day as one row.*", "",
           "| Answered | Where | Question | What the answer said / why it matters |", "|---|---|---|---|"]
    for c in rows:
        nums = _numbers(c["refs"])
        label = "[{0}]({1})".format(nums, c["url"]) if c.get("url") and nums else nums
        theme = "; ".join(c["headings"][:3]) + ("; and more" if len(c["headings"]) > 3 else "")
        q = ", ".join(x for x in (label, c["asker"]) if x)
        if theme:
            q += ": " + theme
        out.append("| {0} | {1} | {2} | {3} |".format(
            day_label(c["answered"]), c["where"], q.replace("|", "/"), (c["why"] or "-").replace("|", "/")))
    out.append("")
    return "\n".join(out)


_PROPER = {"england", "scotland", "wales", "welsh", "scottish", "northern", "ireland", "irish", "uk",
           "british", "britain", "government", "parliament", "lords", "commons", "christian", "christians",
           "muslim", "muslims", "jewish", "islam", "church", "bbc", "ofcom", "europe", "european"}


def _topic_case(text):
    """'Gender Dysphoria: Hormone Treatments' -> 'gender dysphoria: hormone
    treatments' (a Hansard heading in Title Case, read in a sentence);
    acronyms and the names in _PROPER keep their capitals."""
    def word(w):
        bare = re.sub(r"[^A-Za-z]", "", w)
        if not bare or bare.isupper() and len(bare) > 1 or bare.lower() in _PROPER:
            return w
        return w.lower()
    return " ".join(word(w) for w in (text or "").split())


def key_question_line(rows):
    """The Slack post's one line: the top row, and how many more."""
    if not rows:
        return None
    c = rows[0]
    n = len([r for r in c["refs"] if r]) or 1
    house = {COMMONS: "Commons", LORDS: "Lords", HOLYROOD: "Holyrood", SENEDD: "Senedd",
             NI_ASSEMBLY: "NI Assembly"}.get(c["where"], c["where"])
    theme = c["headings"][0] if c["headings"] else issue_label(c["areas"])
    theme = _topic_case(compress(theme, 60)[0])
    line = "*Key questions:* {0} {1} question{2}{3} on {4} (answered {5})".format(
        n, house, "" if n == 1 else "s", " from " + c["asker"] if c["asker"] else "",
        theme, day_label(c["answered"])[4:])
    if len(rows) > 1:
        line += " · + {0} more in the edition".format(len(rows) - 1)
    return line


# -- latest votes ---------------------------------------------------------------

_SENEDD_PART = re.compile(r"^(.*?)[.,]?\s+((?:Motion|Amendment)\b.*)$")
_NI_AMENDMENT = re.compile(r"^Amendment (\d+) - (.*?)(?:\s*\(Day \d+\))?$")


def _vote_base(title):
    """(debate, part) for one division's title, so the votes of one debate
    group: Senedd 'Item 5. Reform UK Debate - grooming gangs. Amendment 1,
    tabled...' -> ('Item 5. Reform UK Debate - grooming gangs', 'Amendment 1...');
    NI 'Amendment 97 - Consideration Stage: Justice Bill (NIA Bill 7/22-27)
    (Day 4)' -> ('Consideration Stage: Justice Bill (NIA Bill 7/22-27)',
    'Amendment 97'); Commons 'Health Bill: Report Stage: New Clause 142' ->
    ('Health Bill: Report Stage', 'New Clause 142')."""
    t = _clean(title)
    m = _NI_AMENDMENT.match(t)
    if m:
        return m.group(2), "Amendment " + m.group(1)
    m = _SENEDD_PART.match(t)
    if m and m.group(1).strip(" .-"):
        return m.group(1).strip(" .-"), m.group(2).strip(" .")
    if t.count(": ") >= 2:
        base, part = t.rsplit(": ", 1)
        return base, part
    return t, None


def _part_text(part, result):
    """One vote within a debate: the result says it best when it names what
    was voted on ('Amendment has been agreed' -> 'amendment agreed')."""
    res = _clean(result).replace(" has been ", " ").replace(" have been ", " ")
    if res and re.match(r"^(motion|amendment)", res, re.I):
        return res[:1].lower() + res[1:]
    return ", ".join(x for x in (part, res) if x)


def group_votes(votes):
    """Votes of one debate on one day in one legislature become ONE entry
    (round 2, 16 October 2026: the Senedd grooming-gangs motion and its
    amendments were four lines). Order is kept (newest first)."""
    out, index = [], {}
    for v in votes:
        base, part = _vote_base(v.get("title") or "")
        key = (v.get("date"), v.get("where"), base.lower())
        entry = index.get(key)
        if entry is None:
            entry = {"date": v.get("date"), "where": v.get("where"), "title": base,
                     "url": v.get("url"), "result": v.get("result"), "parts": []}
            index[key] = entry
            out.append(entry)
        entry["parts"].append({"label": part, "url": v.get("url"), "result": v.get("result")})
    for e in out:
        if len(e["parts"]) == 1:
            only = e["parts"][0]
            e["title"] = e["title"] + (": " + only["label"] if only["label"] else "")
            e["parts"] = []
    return out


def vote_line(v):
    """The markdown for one (grouped) vote: '16 Sep · **Senedd** · debate:
    motion without amendment rejected; amendment agreed; ...'."""
    head = "{0} · **{1}** · ".format(day_label(v.get("date"))[4:], v.get("where") or "")
    if not v.get("parts"):
        title = v.get("title") or ""
        if v.get("url"):
            title = "[{0}]({1})".format(title, v["url"])
        return head + title + (", " + v["result"] if v.get("result") else "")
    bits = []
    for p in v["parts"]:
        text = _part_text(p["label"], p["result"])
        if p["url"] and p["label"]:
            label = "[{0}]({1})".format(p["label"], p["url"])
            text = label + (", " + _clean(p["result"]).replace(" has been ", " ") if p.get("result") else "")
        bits.append(text)
    return head + "{0}: {1}".format(v.get("title") or "", "; ".join(bits))


# -- assembly -----------------------------------------------------------------

_PRIVATE = re.compile(r"\b(private|closed|in camera)\b", re.I)


def is_private(row):
    """A meeting the public cannot attend (a select committee's private
    meeting, an NI committee's closed session) is never a BIG DATE (round 2,
    16 October 2026); it can still be a row in the tables."""
    return bool(_PRIVATE.search(row.detail or "") or _PRIVATE.search(row.session or ""))


def mark_big(rows, week_commencing, limit=BIG_MAX):
    """Flag up to `limit` score-3 dated rows inside the horizon, nearest first."""
    ws, _we, _fs, he = windows(week_commencing)
    for r in rows:
        r.big = False
    cands = sorted((r for r in rows if not r.running and r.score == BIG_SCORE and _date(r.date)
                    and ws <= _date(r.date) <= he and not is_private(r)), key=Row.sort_key)
    for r in cands[:limit]:
        r.big = True
    return cands[:limit]


def split(rows, week_commencing):
    """(this_week, further_afield) by date; running rows lead this week."""
    ws, we, fs, he = windows(week_commencing)
    this_week, further = [], []
    for r in sorted(rows, key=Row.sort_key):
        if r.running:
            continue
        d = _date(r.date)
        if not d:
            continue
        if ws <= d <= we:
            this_week.append(r)
        elif fs <= d <= he:
            further.append(r)
    this_week += [r for r in rows if r.running]
    return this_week, further


_SITTING = re.compile(r"\s*\((?:day|sitting|part) [^)]*\)", re.I)


def fold_sittings(rows, week_commencing):
    """One row per run of sittings. A Bill in committee sits many times: the
    Health Bill's Lords committee has seven days booked, the Immigration and
    Asylum Bill's Public Bill Committee two sittings a day. Within each table
    the first sitting keeps the row and the later dates ride on it; a Bill
    whose "All week" row already says it is in committee this week loses its
    committee sittings from the week's table."""
    ws, we, fs, he = windows(week_commencing)
    running_titles = set()
    for r in rows:
        if r.running and r.where in (COMMONS, LORDS):
            running_titles.update(t.strip().lower() for t in r.title.split(", "))
    out, groups = [], {}
    for r in sorted(rows, key=Row.sort_key):
        d = _date(r.date)
        if r.running or r.kind != "event" or not d:
            out.append(r)
            continue
        base = _SITTING.sub("", r.title).strip().lower()
        committee = r.venue == "General Committee" or "committee stage" in base
        if not committee:
            out.append(r)
            continue
        bill = re.split(r"\s+-\s+|:\s+", base)[0]
        if d <= we and r.venue == "General Committee" and bill in running_titles:
            continue
        table = "week" if d <= we else "further"
        key = (table, r.where, base)
        first = groups.get(key)
        if first is None:
            groups[key] = r
            out.append(r)
            continue
        if r.date != first.date and r.date not in first.also:
            first.also.append(r.date)
        if (r.score or 0) > (first.score or 0):
            first.score = r.score
            first.note = r.note or first.note
    return out


def _also(row, cap=4):
    if not row.also:
        return None
    dates = [day_label(x) for x in sorted(row.also)]
    more = len(dates) - cap
    text = ", ".join(dates[:cap])
    return "then " + text + (" and {0} more".format(more) if more > 0 else "")


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        key = (r.date, r.where, r.title.lower()[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# -- rendering: the canvas -----------------------------------------------------

def _title_md(row, bold=False):
    title = row.title
    if row.url:
        title = "[{0}]({1})".format(title, row.url)
    return "**{0}**".format(title) if bold else title


def _note(row):
    """A why-line shows only where the judge kept the row (score 2 or 3, or
    unscored): on a low score it argues against the row it sits in."""
    if row.score is not None and row.score < 2:
        return None
    return row.note


def what_cell(row):
    if row.extra_md and row.running:
        return row.extra_md
    parts = []
    if row.kind == "deadline" and row.extra_md:
        parts.append("{0}, {1}".format(_clean(row.extra_md), _title_md(row, row.big)))
    else:
        parts.append(_title_md(row, row.big))
    if row.detail:
        parts.append(row.detail)
    if row.lead:
        parts.append(row.lead)
    if _also(row):
        parts.append(_also(row))
    cell = ", ".join(parts)
    if _note(row):
        cell += ". *{0}*".format(_note(row).rstrip(".") + ".")
    return cell


def when_cell(row):
    if row.big:
        return "**{0} · {1}**".format(row.when, BIG_LABEL)
    return row.when


def render_table(rows, names=None):
    out = ["| When | Where | What | Issue |", "|---|---|---|---|"]
    for r in rows:
        out.append("| {0} | {1} | {2} | {3} |".format(
            when_cell(r), r.where, what_cell(r).replace("|", "/"),
            issue_label(r.areas, names) or "-"))
    return out


def render_big_dates(big, names=None):
    if not big:
        return None
    out = ["## Big dates", ""]
    for r in big:
        head = "> **{0}** · **{1}** · {2}".format(BIG_LABEL, long_day(r.date), r.where)
        issue = issue_label(r.areas, names)
        if issue:
            head += " · " + issue
        body = _title_md(r, bold=True)
        tail = [x for x in (r.detail, r.lead) if x]
        if tail:
            body += ", " + ", ".join(tail)
        out.append(head)
        out.append(">")
        out.append("> " + body.rstrip(".") + ".")
        if r.context:
            out.append(">")
            out.append("> *Context:* " + r.context.rstrip(".") + ".")
        out.append("")
    return "\n".join(out)


# -- rendering: the Slack channel post ----------------------------------------

SLACK_TEXT_CAP = 3500        # well inside chat.postMessage's limits
THIS_WEEK_POST_CAP = 8
FURTHER_POST_ROWS = 3


def _mrkdwn_link(text, url):
    text = text.replace("<", "").replace(">", "").replace("|", "/")
    return "<{0}|{1}>".format(url, text) if url else text


def slack_post(edition, canvas_url=None, tracker_url=None):
    """The channel post: header, BIG DATE lines, THIS WEEK rows, the next few
    FURTHER AFIELD rows and a '+ N more to <date>' line, then the links."""
    ws, we, fs, he = windows(edition.week_commencing)
    rows = list(edition.timeline or [])
    big = [r for r in rows if r.big]
    this_week, further = split(rows, edition.week_commencing)
    this_week = [r for r in this_week if not r.running]
    lines = ["*On our issues, from {0}* · Edition {1}".format(day_label(ws.isoformat()), edition.number), ""]
    for r in big:
        lines.append("*{0}* *{1}* · `{2}` {3}".format(
            BIG_LABEL, day_label(r.date), r.where, _mrkdwn_link(short_title(r), r.url)))
    if big:
        lines.append("")
    lines.append("*THIS WEEK*")
    if this_week:
        for r in this_week[:THIS_WEEK_POST_CAP]:
            text = short_title(r)
            lines.append("{0} · `{1}` {2}".format(short_day(r.date), r.where,
                                                   "*{0}*".format(text) if r.big else text))
        if len(this_week) > THIS_WEEK_POST_CAP:
            lines.append("+ {0} more this week, in the edition".format(len(this_week) - THIS_WEEK_POST_CAP))
    elif edition.mode == "recess":
        lines.append("Neither House sits this week.")
    else:
        lines.append("Nothing on our issues in the diary this week.")
    if further:
        lines.append("")
        lines.append("*FURTHER AFIELD*")
        for r in further[:FURTHER_POST_ROWS]:
            text = short_title(r)
            lines.append("{0} · `{1}` {2}".format(short_day(r.date), r.where,
                                                   "*{0}*".format(text) if r.big else text))
        rest = further[FURTHER_POST_ROWS:]
        if rest:
            main = sorted(rest, key=lambda r: (-(r.score or 0), r.sort_key()))[:3]
            main.sort(key=Row.sort_key)
            named = " · ".join("{0} {1}".format(compress(_plain_title(r.title), 44)[0], day_label(r.date)[4:])
                               for r in main)
            lines.append("+ {0} more to {1} {2}: {3}".format(
                len(rest), he.day, _MONTHS[he.month], named))
    kq = key_question_line(getattr(edition, "key_questions", None) or [])
    if kq:
        lines += ["", kq]
    text = "\n".join(lines)
    if len(text) > SLACK_TEXT_CAP:
        text = text[:SLACK_TEXT_CAP].rsplit("\n", 1)[0] + "\n(more in the edition)"
    links = []
    if canvas_url:
        links.append(_mrkdwn_link("Open the edition", canvas_url))
    if tracker_url:
        links.append(_mrkdwn_link("Vote tracker", tracker_url))
    if links:
        text += "\n\n" + " · ".join(links)
    return text
