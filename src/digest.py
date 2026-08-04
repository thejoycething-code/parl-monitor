"""Edition renderer (handoff section 8, docs/digest-template.md).

The digest is a byproduct: this module turns stored records + the bills board
into the Monday markdown edition. Rules enforced here:

  * recess mode (no Commons/Lords chamber events in the edition week): render
    sections 1, 2, 6, 7, 11 plus a return-dates line; deadlines always render;
  * caps: top lines 3-5, PQs 5, EDMs 5, demoting NOTE items first;
  * every ACT line needs a non-null owner: render is refused otherwise;
  * British spelling, no em dashes;
  * footer discloses any gaps rows for the edition.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.board import TBA, order_board

AREA_NAMES = {
    1: "Abortion", 2: "Assisted dying", 3: "Gender medicine (children)",
    4: "Conversion practices", 5: "Sex-based rights", 6: "Parental rights and education",
    7: "Free speech and online safety", 8: "Freedom of religion", 9: "Marriage and family",
    10: "Surrogacy and embryology",
    11: "Migration",
}
TAG_ORDER = {"ACT": 0, "WATCH": 1, "NOTE": 2}


@dataclass
class Line:
    text: str
    tag: str = "NOTE"
    owner: str = None
    url: str = None
    deadline: str = None
    date: str = None      # ISO date, for the Week ahead day grouping


@dataclass
class Edition:
    week_commencing: str          # ISO date
    number: int
    mode: str                     # 'recess' | 'normal'
    top_lines: list = field(default_factory=list)
    board_rows: list = field(default_factory=list)     # board.BoardRow (live + closing)
    week_ahead: list = field(default_factory=list)
    votes: list = field(default_factory=list)
    pqs: list = field(default_factory=list)
    deadlines: list = field(default_factory=list)   # dicts: type/title/url/why/deadline
    si_rows: list = field(default_factory=list)      # dicts: name/url/procedure/act/status/...
    edms: list = field(default_factory=list)
    devolved: list = field(default_factory=list)
    statements: list = field(default_factory=list)
    mp_notes: list = field(default_factory=list)
    return_dates: dict = field(default_factory=dict)   # {house: ISO date}
    gaps: list = field(default_factory=list)            # [(feed, detail)]


class DigestError(Exception):
    pass


# -- validation and caps ----------------------------------------------------

def validate(edition):
    """Refuse to render an ACT line without an owner (handoff section 8)."""
    # mp_notes are plain strings from the ledger (no tags); not validated here.
    for section in (edition.top_lines, edition.week_ahead, edition.votes, edition.pqs,
                    edition.edms, edition.devolved, edition.statements):
        for line in section:
            if line.tag == "ACT" and not line.owner:
                raise DigestError("ACT line without owner: %r" % line.text)


def _cap(lines, limit):
    """Enforce a section cap, demoting NOTE (then WATCH) items first."""
    if len(lines) <= limit:
        return lines
    ordered = sorted(lines, key=lambda l: TAG_ORDER.get(l.tag, 3))
    return ordered[:limit]


# -- line/section rendering -------------------------------------------------

def _fmt_line(line):
    label = line.text
    if line.url:
        label = "[{0}]({1})".format(line.text, line.url)
    bits = ["- **[{0}]**".format(line.tag), label]
    body = " ".join(bits)
    extras = []
    if line.deadline:
        extras.append("Deadline: {0}".format(line.deadline))
    if line.owner:
        extras.append("Owner: {0}".format(line.owner))
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


def render_week_ahead(lines):
    """Section 3: the diary, grouped by day (handoff digest-template section 3)."""
    if not lines:
        return None
    out = ["## Week ahead", ""]
    current = object()
    for line in sorted(lines, key=lambda l: (l.date or "")):
        if line.date != current:
            current = line.date
            out.append("**{0} {1}**".format(_weekday(line.date), line.date or "TBA"))
        out.append(_fmt_line(line))
    out.append("")
    return "\n".join(out)


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
    if not edition.deadlines:
        return None
    out = ["## Consultations and calls for evidence", ""]
    if True:
        out.append("| Consultation / call for evidence | Closes |")
        out.append("|---|---|")
        rows = sorted(edition.deadlines, key=lambda r: r.get("deadline") or "9999")
        for r in rows:
            why = (" " + r["why"].rstrip(".") + ".") if r.get("why") else ""
            out.append("| **{0}** [{1}]({2}).{3} | {4} |".format(
                r["type"], r["title"], r["url"] or "#", why,
                _fmt_close(r.get("deadline"), edition.week_commencing)))
        out.append("")
    return "\n".join(out)


MP_SECTION_MAX = 12
MP_SUBTITLE = ("*Questions, debates, votes and motions from any member of either House "
               "touching our campaign areas this week.*")


def mp_lines_from_events(events, max_members=MP_SECTION_MAX):
    """V1 lines: one per member, activities merged; votes never listed.

    Division votes are recorded to the ledger for profiles and 5CA, but a
    single tagged division would otherwise flood this section with hundreds
    of lines -- the division renders once in Votes and amendments instead
    (Christopher, 2026-08-03).
    """
    members_seen = []   # ordered member ids
    grouped = {}        # member_id -> {"who": str, "acts": ordered {(kind, line): count}}
    for e in events:
        if e["kind"] == "vote":
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


def render_mp_section(mp_lines):
    if not mp_lines:
        return None
    out = ["## Parliamentarians on our issues", "", MP_SUBTITLE, ""]
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

def render(edition):
    validate(edition)
    recess = edition.mode == "recess"
    parts = ["# Parliamentary Monitor",
             "### Week commencing Monday {0} | Edition {1}{2}".format(
                 edition.week_commencing, edition.number, " | RECESS" if recess else ""),
             ""]

    top = _render_section("Top lines", _cap(edition.top_lines, 5))
    if top:
        parts.append(top)

    if recess:
        # Recess status + return dates render once, as a top line (composed via
        # recess_line() by the orchestrator); no separate banner or footer.
        deadlines = render_deadlines(edition)
        if deadlines:
            parts.append(deadlines)
        parts.append(render_board(edition.board_rows))
        si = render_si(edition)
        if si:
            parts.append(si)
        mp = render_mp_section(edition.mp_notes)
        if mp:
            parts.append(mp)
    else:
        week_ahead = render_week_ahead(edition.week_ahead)
        if week_ahead:
            parts.append(week_ahead)
        for title, lines, cap in [
            ("Votes and amendments", edition.votes, None),
            ("Written questions worth reading", edition.pqs, 5),
        ]:
            section = _render_section(title, lines, cap)
            if section:
                parts.append(section)
        deadlines = render_deadlines(edition)
        if deadlines:
            parts.append(deadlines)
        for title, lines, cap in [
            ("EDMs and petitions", edition.edms, 5),
            ("Devolved round-up", edition.devolved, None),
            ("Statements and announcements", edition.statements, None),
        ]:
            section = _render_section(title, lines, cap)
            if section:
                parts.append(section)
        parts.append(render_board(edition.board_rows))
        si = render_si(edition)
        if si:
            parts.append(si)
        mp = render_mp_section(edition.mp_notes)
        if mp:
            parts.append(mp)

    # Footer: disclose gaps.
    parts.append("---")
    if edition.gaps:
        parts.append("**Coverage gaps this edition:**")
        for feed, detail in edition.gaps:
            parts.append("- {0}: {1}".format(feed, detail))
    else:
        parts.append("*No coverage gaps recorded this edition.*")
    parts.append("")
    parts.append("*Compiled from Parliament's open data feeds via the CitizenGO issue taxonomy v0.2 with human review.*")
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
        conn.execute("INSERT INTO gaps (edition, feed, detail) VALUES (?, ?, ?)",
                     (edition.week_commencing, feed, detail))
    conn.commit()
    return path
