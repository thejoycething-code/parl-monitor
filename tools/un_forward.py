"""The UN forward look: what is coming, and what closes before it.

    python3 tools/un_forward.py              # next 180 days, recorded in the store
    python3 tools/un_forward.py --days 90    # a shorter horizon
    python3 tools/un_forward.py --days 3650  # everything published
    python3 tools/un_forward.py --no-store   # a pure read: nothing recorded
    python3 tools/un_forward.py --db PATH    # a scratch copy of the store
    python3 tools/un_forward.py --no-walk    # skip the docs.un.org walks

One chronological list, because that is how a campaign is planned: a call for
input closing three weeks before a Council session is a different thing from
one closing after it, and two separate lists hide that relationship.

WHAT GOES FIRST (13 October 2026). Above the list: everything on our ground
due within 14 days, then the FIRST SIGNS on our ground: a draft tabled, a
plenary listed, a PGA letter naming a date (src/un_signals.py). Added after
the General Assembly voted on the political declaration on pandemic
prevention, preparedness and response on 12 October 2026 with the monitor
silent, although the draft (5 October), the PGA's letter (7 October) and the
plenary listing were all public beforehand.

COVERAGE, as of 13 October 2026 (src/ingest/un_calendar.py has the detail):
Human Rights Council, CSW and UPR working group sessions (UPR at month
precision), the General Assembly window, GA PLENARIES and high-level
meetings with their agendas (UN Journal; near-term, about a week ahead),
Third Committee meetings (UN Journal; near-term), the PGA's letters to member
states (src/ingest/pga_letters.py), draft resolutions by symbol for the GA
plenary (A/81/L.n) and the Third Committee (A/C.3/81/L.n) (docs.un.org),
treaty body reporting deadlines (CEDAW/CRC/CCPR flagged) and OHCHR calls for
input. HRC drafts (A/HRC/NN/L.n) are walked by tools/un_drafts.py --hrc,
not here.

THE CHECK LOG. Every source reports "read OK", "read but empty" or "could
not read" with the newest item it gave (src/un_checks.py), printed on every
run and in the footer. A source that could not be read is never rendered as
"nothing new": the no-changes line says which sources were not read.

The draft walks cost about 10 s a symbol. With a store they resume after the
highest symbol already recorded, so a weekly run checks only the new end of
each series; --no-store walks from L.1 and is slow (minutes) once a session
is under way.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, robots_guard, un_checks, un_signals, un_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.ingest import ohchr_calls, pga_letters, un_calendar, un_docs  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
from pull_un_calls import areas_for, load_un_filter  # noqa: E402
from un_drafts import read_drafts  # noqa: E402


# Six months. Without a default the UPR list alone runs to January 2031,
# which is a schedule rather than a forward look. --days 3650 for everything.
DEFAULT_HORIZON_DAYS = 180
JOURNAL_DAYS = 30
DRAFT_SERIES = (
    ("GA plenary drafts", un_docs.GA_PLENARY_DRAFTS, "General Assembly"),
    ("Third Committee drafts", un_docs.THIRD_COMMITTEE_DRAFTS, "Third Committee"),
)


def to_item(row):
    """One calendar row as a store record."""
    when, kind, title, _detail, areas, url, ident, obj = row
    ends = getattr(obj, "ends", None) or getattr(obj, "deadline", None) or when
    if hasattr(ends, "date"):
        ends = ends.date()
    return {
        "id": ident, "kind": kind.lower(), "title": title,
        "body": getattr(obj, "body", None) or getattr(obj, "organ", None)
                or getattr(obj, "treaty", None),
        "starts": when.isoformat(), "ends": ends.isoformat(),
        "approximate": getattr(obj, "approximate", False),
        # Only real area numbers are stored; "committee" is a display marker.
        "areas": [int(a) for a in areas.split(",") if a.strip().isdigit()],
        "url": url,
    }


def _why(exc):
    """The reason a source could not be read, in words a reader can act on.

    www.ohchr.org answered every request with a Cloudflare challenge
    (cf-mitigated: challenge, "Just a moment...") on 13 October 2026, the
    HRC branch included, which it had not on 17 August. That is a block to
    route around, never to defeat, so it is named as one.
    """
    cause = str(getattr(exc, "cause", None) or exc)
    url = str(getattr(exc, "url", "") or "")
    if "hrcportal.ohchr.org" in (url + cause) or "robots.txt" in cause:
        return cause            # already says which route failed, and why
    if "403" in cause and "ohchr.org" in (url + cause):
        return ("HTTP 403 from www.ohchr.org (a Cloudflare bot challenge since "
                "13 October 2026; not bypassed)")
    return cause


def known_drafts(conn):
    """Drafts already in the store: symbol -> DraftInfo (not re-read)."""
    out = {}
    if conn is None:
        return out
    for r in conn.execute("SELECT symbol, title, subject, dated, areas, url, agenda_item "
                          "FROM un_documents"):
        out[r["symbol"]] = un_signals.DraftInfo(
            symbol=r["symbol"], title=r["title"] or r["subject"] or "",
            dated=un_signals.parse_un_date(r["dated"] or ""),
            areas=json.loads(r["areas"] or "[]"), url=r["url"] or "",
            agenda_item=r["agenda_item"])
    return out


def _series_start(known, pattern, session):
    """1 + the highest L number the store holds for this series."""
    prefix = pattern.format(session=session, n="")
    best = 0
    for symbol in known:
        if symbol.startswith(prefix):
            m = re.match(r"(\d+)$", symbol[len(prefix):])
            if m:
                best = max(best, int(m.group(1)))
    return best + 1


def _info(doc, draft, areas):
    return un_signals.DraftInfo(symbol=doc.symbol, title=draft.topic or "",
                                dated=un_signals.parse_un_date(draft.dated or ""),
                                areas=list(areas), url=doc.url,
                                agenda_item=draft.agenda_item)


def collect_drafts(client, checks, session, known, named, tax, wl, walk=True, log=print):
    """Drafts for linking: the store's, a resumed walk of each series, and
    any symbol a plenary agenda or PGA letter names. Returns (DraftInfo
    list, rows to store in un_documents as (doc, draft, areas, body))."""
    infos = dict(known)
    stored = []
    if walk:
        for label, pattern, body in DRAFT_SERIES:
            start = _series_start(known, pattern, session)
            try:
                found, checked, errors = un_docs.walk_drafts(client, pattern, session, start=start)
            except Exception as exc:   # pragma: no cover - walk_drafts catches per symbol
                checks.failed("docs.un.org " + label, exc)
                continue
            if errors and len(errors) >= checked:
                checks.failed("docs.un.org " + label,
                              "every check failed ({0}, ...)".format(errors[0]))
                continue
            rows = read_drafts(client, found, tax, wl, log=log)
            for doc, draft, areas in rows:
                infos[doc.symbol] = _info(doc, draft, areas)
                stored.append((doc, draft, areas, body))
            series = [i for s, i in infos.items() if s.startswith(pattern.format(session=session, n=""))]
            detail = "walked L.{0} upward, {1} checks".format(start, checked)
            if errors:
                detail += ", {0} failed".format(len(errors))
            checks.read("docs.un.org " + label, series, detail=detail,
                        key=lambda i: (i.dated or datetime.date.min),
                        title=lambda i: "{0} {1}".format(i.symbol, i.title))
    missing = [s for s in named if s not in infos]
    if missing:
        docs, failed = [], []
        for symbol in missing:
            try:
                doc = un_docs.head(client, symbol)
            except Exception as exc:
                failed.append("{0} ({1})".format(symbol, str(_why(exc))[:60]))
                continue
            if doc.is_document:
                docs.append(doc)
        for doc, draft, areas in read_drafts(client, docs, tax, wl, log=log):
            infos[doc.symbol] = _info(doc, draft, areas)
            body = "Third Committee" if "/C.3/" in doc.symbol else "General Assembly"
            stored.append((doc, draft, areas, body))
        if failed and not docs:
            checks.failed("docs.un.org named drafts", "; ".join(failed))
        else:
            checks.read("docs.un.org named drafts", docs,
                        detail="symbols named by plenaries and PGA letters"
                               + ("; failed: " + "; ".join(failed) if failed else ""),
                        newest=(docs[-1].symbol, None) if docs else None)
    elif not walk:
        checks.read("docs.un.org named drafts", [],
                    detail="no new symbol named; walk skipped this run")
    return list(infos.values()), stored


@dataclass
class Collected:
    rows: list              # the chronological list (when, kind, title, detail, areas, url, id, obj)
    gaps: list              # human-readable gap lines
    checks: object          # un_checks.CheckLog
    signals: list           # un_signals.Signal, linked
    drafts_to_store: list   # (doc, draft, areas, body) for un_documents
    calls: list             # open OHCHR calls (for the DM)


def collect(client, today, days, tax, wl, conn=None, walk=True, pga_client=None, log=print):
    """Read every UN source into a Collected. Nothing is written.

    rows are the chronological list; signals the linked ground items
    (un_signals.build_signals); checks the CheckLog.
    """
    rows, gaps, checks = [], [], un_checks.CheckLog()
    open_calls = []

    try:
        # hrcportal.ohchr.org first: www.ohchr.org is behind a Cloudflare
        # challenge since 13 October 2026 (src/ingest/un_calendar.py).
        sessions, route = un_calendar.fetch_sessions_routed(client)
        checks.read("HRC sessions (OHCHR)", sessions, key=lambda s: s.starts,
                    title=lambda s: s.name, detail="via " + route)
        for s in un_calendar.upcoming(sessions, today=today, horizon_days=days):
            rows.append((s.starts, "SESSION", s.name, s.when, "", s.url,
                         un_store.item_id("session", s.body, s.number), s))
    except FetchError as exc:
        checks.failed("HRC sessions (OHCHR)", _why(exc))
        gaps.append("HRC sessions: {0}".format(_why(exc)))

    try:
        csw, csw_failures = un_calendar.fetch_csw_sessions(client, today=today)
        gaps.extend(csw_failures)
        if csw_failures and not csw:
            checks.failed("CSW sessions (UN Women)", "; ".join(csw_failures))
        else:
            checks.read("CSW sessions (UN Women)", csw, key=lambda s: s.starts,
                        title=lambda s: s.name, detail="; ".join(csw_failures))
        for s in un_calendar.upcoming(csw, today=today, horizon_days=days):
            rows.append((s.starts, "SESSION", s.name, s.when, "committee", s.url,
                         un_store.item_id("session", s.body, s.number), s))
    except FetchError as exc:
        checks.failed("CSW sessions (UN Women)", _why(exc))
        gaps.append("CSW sessions: {0}".format(_why(exc)))

    try:
        meetings, why = un_calendar.fetch_journal_meetings(client, start=today,
                                                           days=min(days, JOURNAL_DAYS))
        if why:
            # A range past the last Journal issue: the source answered, and
            # said it has nothing that far ahead. Read, empty, with the reason.
            gaps.append("Third Committee: {0}".format(why))
        checks.read("UN Journal: Third Committee", meetings, key=lambda m: m.starts,
                    title=lambda m: m.title, detail=why or "")
        for m in meetings:
            rows.append((m.starts.date(), "MEETING",
                         "{0}: {1}".format(m.organ, m.title),
                         m.starts.strftime("%Y-%m-%d %H:%M") + " " + m.kind,
                         "committee", m.url,
                         un_store.item_id("meeting", m.organ, m.title,
                                          m.starts.strftime("%Y%m%d%H%M")), m))
    except Exception as exc:
        checks.failed("UN Journal: Third Committee", _why(exc))
        gaps.append("Third Committee meetings: {0}".format(_why(exc)))

    # GA plenaries and high-level meetings (13 October 2026). Listed only
    # when on our ground; un_signals decides, after the drafts are known.
    # Asked from a week back, so a plenary listed since the last weekly run
    # and already held still counts as read.
    plenaries = []
    try:
        plenaries, why, failures = un_calendar.fetch_ga_plenaries(
            client, start=today - datetime.timedelta(days=7), days=min(days, JOURNAL_DAYS) + 7)
        if why:
            gaps.append("GA plenaries: {0}".format(why))
        gaps.extend("GA plenaries: " + f for f in failures)
        if plenaries and len(failures) == len(plenaries):
            checks.failed("UN Journal: GA plenaries", "no agenda could be read: " + failures[0])
        else:
            detail = why or ""
            if failures:
                detail = "{0} agenda(s) not read".format(len(failures))
            checks.read("UN Journal: GA plenaries", plenaries, key=lambda m: m.starts,
                        title=lambda m: m.title, detail=detail)
    except Exception as exc:
        checks.failed("UN Journal: GA plenaries", _why(exc))
        gaps.append("GA plenaries: {0}".format(_why(exc)))

    letters = []
    try:
        pc = pga_client or robots_guard.guard(client, "pga", log=log)
        letters, failures = pga_letters.fetch_letters(pc, today=today)
        gaps.extend("PGA letters: " + f for f in failures)
        detail = "{0} letter page(s) not read".format(len(failures)) if failures else ""
        checks.read("PGA letters (un.org/pga)", letters, key=lambda l: l.dated,
                    title=lambda l: l.title, detail=detail)
    except Exception as exc:
        checks.failed("PGA letters (un.org/pga)", _why(exc))
        gaps.append("PGA letters: {0}".format(_why(exc)))

    named = []
    for item in list(plenaries) + list(letters):
        for s in un_signals.draft_symbols(item.symbols):
            if s not in named:
                named.append(s)
    session = pga_letters.session_for(today)
    known = known_drafts(conn)
    drafts, drafts_to_store = collect_drafts(client, checks, session, known, named,
                                             tax, wl, walk=walk, log=log)

    try:
        upr = un_calendar.fetch_upr_sessions(client)
        if not upr:
            checks.failed("UPR sessions (UPR Info)", "parsed to nothing (layout change?)")
            gaps.append("UPR sessions: parsed to nothing (layout change?)")
        else:
            checks.read("UPR sessions (UPR Info)", upr, key=lambda s: s.starts,
                        title=lambda s: s.name)
        for s in un_calendar.upcoming(upr, today=today, horizon_days=days):
            rows.append((s.starts, "SESSION", s.name,
                         s.when + " (month only)", "committee", s.url,
                         un_store.item_id("session", s.body, s.number), s))
    except FetchError as exc:
        checks.failed("UPR sessions (UPR Info)", _why(exc))
        gaps.append("UPR sessions: {0}".format(_why(exc)))

    try:
        ga = un_calendar.fetch_ga_session(client, today=today)
        if ga and ga.ends >= today and not (days and ga.days_until > days):
            rows.append((ga.starts, "SESSION", ga.name,
                         "{0} to {1} (plenaries and the Third Committee sit within this)".format(
                             ga.starts, ga.ends), "", ga.url,
                         un_store.item_id("session", ga.body, ga.number), ga))
        if ga:
            checks.read("GA session window (un.org)", [ga], newest=(ga.name, ga.starts))
        else:
            checks.failed("GA session window (un.org)", "page loaded but no session window found")
            gaps.append("GA session: page loaded but no session window found")
    except FetchError as exc:
        checks.failed("GA session window (un.org)", _why(exc))
        gaps.append("GA session: {0}".format(_why(exc)))

    try:
        deadlines = un_calendar.fetch_treaty_deadlines(client)
        if not deadlines:
            checks.failed("Treaty bodies (OHCHR)", "parsed to nothing (layout change?)")
            gaps.append("treaty body calendar: parsed to nothing (layout change?)")
        else:
            checks.read("Treaty bodies (OHCHR)", deadlines, key=lambda d: d.due,
                        title=lambda d: "{0}: {1}".format(d.treaty, d.country))
        for d in deadlines:
            if d.due < today or (days and (d.due - today).days > days):
                continue
            rows.append((d.due, "TREATY", "{0}: {1} ({2})".format(
                d.treaty, d.country, d.document[:40]),
                "due {0}".format(d.due), "committee" if d.ours else "", d.url,
                un_store.item_id("treaty", d.treaty, d.country, d.document), d))
    except FetchError as exc:
        checks.failed("Treaty bodies (OHCHR)", _why(exc))
        gaps.append("treaty body calendar: {0}".format(_why(exc)))

    try:
        calls = ohchr_calls.fetch_calls(client)
        if not calls:
            checks.failed("OHCHR calls for input", "parsed to nothing (layout change?)")
            gaps.append("calls for input: parsed to nothing (layout change?)")
        else:
            checks.read("OHCHR calls for input", calls, key=lambda c: c.deadline,
                        title=lambda c: c.title)
        open_calls = ohchr_calls.open_calls(calls, today=today)
        for c in ohchr_calls.open_calls(calls, today=today, horizon_days=days):
            areas = areas_for(c, tax, wl)
            rows.append((c.deadline, "DEADLINE", c.title,
                         "closes {0}".format(c.deadline),
                         ",".join(str(a) for a in areas), c.url,
                         un_store.item_id("call", c.url.rsplit("/", 1)[-1]), c))
    except FetchError as exc:
        checks.failed("OHCHR calls for input", _why(exc) + "; no unchallenged "
                      "alternative found (docs/un-sources.md)")
        gaps.append("calls for input: {0}".format(_why(exc)))

    signals = un_signals.build_signals(letters, plenaries, drafts, tax, wl, as_of=today)
    for s in signals:
        if not un_signals.in_forward_look(s, today, days):
            continue
        when = s.due if (s.due and s.due >= today) else (s.sign_date or today)
        rows.append((when, s.kind, s.title, s.detail,
                     ",".join(str(a) for a in s.areas), s.url, s.id, s))
    rows.sort(key=lambda r: r[0])
    return Collected(rows, gaps, checks, signals, drafts_to_store, open_calls)


def store_drafts(conn, drafts_to_store, session, today):
    """Record drafts in un_documents, as tools/un_drafts.py does."""
    from un_drafts import store
    by_body = {}
    for doc, draft, areas, body in drafts_to_store:
        by_body.setdefault(body, []).append((doc, draft, areas))
    for body, rows in by_body.items():
        store(conn, rows, body, session, today.isoformat())


def render(rows, today, days, signals, checks, gaps, changes=None, stored=False, new_ids=None):
    """The forward look as text lines. Plain, British, no em dashes."""
    out = ["UN forward look (next {0} days), as of {1}: {2} item(s)".format(days, today, len(rows)), ""]
    due = un_signals.due_soon(signals, today)
    first = un_signals.first_signs(signals, today, new_ids=new_ids)
    out.extend(un_signals.render_top(due, first, today))
    out.append("")
    for when, kind, title, detail, areas, url, _id, _obj in rows:
        left = (when - today).days
        flag = "OURS" if areas and areas != "committee" else "    "
        out.append("{0}  {1:>4}d  {2:<8} {3}".format(flag, left, kind, title[:60]))
        # The marker is an area list for calls and the word "committee" for
        # treaty rows; label it rather than printing "areas committee".
        suffix = ""
        if areas == "committee":
            suffix = "  (one of our committees)"
        elif areas:
            suffix = "  areas " + areas
        out.append("            {0}{1}".format(detail, suffix))
        out.append("            {0}".format(url))

    if changes:
        out.append("")
        out.append("--- CHANGES SINCE THE LAST RUN ---")
        out.extend(changes)
    elif stored:
        out.append("")
        out.append(checks.nothing_new())
    elif checks.unread():
        out.append("")
        out.append(checks.nothing_new())

    out.append("")
    out.append("Coverage: Human Rights Council, CSW and UPR working group sessions "
               "(UPR at month precision), the General Assembly window, GA plenaries "
               "and high-level meetings with their agendas, Third Committee meetings, "
               "the PGA's letters, GA plenary and Third Committee drafts by symbol, "
               "treaty body reporting deadlines (CEDAW/CRC/CCPR flagged) and OHCHR "
               "calls for input. Journal rows are NEAR-TERM only (about a week "
               "ahead). See src/ingest/un_calendar.py.")
    out.append("")
    out.append("CHECK LOG ({0} sources, {1} could not be read):".format(
        len(checks.checks), len(checks.unread())))
    out.extend("  " + l for l in checks.lines())
    if gaps:
        out.append("")
        out.append("GAPS ({0}):".format(len(gaps)))
        out.extend("  " + g for g in gaps)
    return out


def main():
    argv = sys.argv[1:]
    days = DEFAULT_HORIZON_DAYS
    if "--days" in argv:
        days = int(argv[argv.index("--days") + 1])
    db_path = os.path.join(ROOT, "data", "parl-monitor.db")
    if "--db" in argv:
        db_path = argv[argv.index("--db") + 1]
    no_store = "--no-store" in argv
    today = datetime.date.today()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax, wl = load_un_filter()

    # Store, then diff. --no-store makes this a pure read, which is what a
    # dry run wants: recording items would make the NEXT run think it had
    # already seen them and report nothing new.
    conn = None if no_store else db.init_db(db.connect(db_path))
    got = collect(client, today, days, tax, wl, conn=conn, walk="--no-walk" not in argv)
    rows, gaps, checks, signals = got.rows, got.gaps, got.checks, got.signals

    changes, new_ids = [], None
    if conn is not None:
        store_drafts(conn, got.drafts_to_store, pga_letters.session_for(today), today)
        items = [to_item(r) for r in rows]
        new_ids, moved = un_store.record(conn, items, today=today)
        gone = un_store.mark_gone(conn, today + datetime.timedelta(days=days),
                                  today=today, seen_ids={i["id"] for i in items})
        changes = un_store.summarise(conn, new_ids, moved, gone)
        conn.close()
    for line in render(rows, today, days, signals, checks, gaps, changes=changes,
                       stored=conn is not None, new_ids=new_ids):
        print(line)
    return 1 if (gaps or checks.unread()) else 0


if __name__ == "__main__":
    sys.exit(main())
