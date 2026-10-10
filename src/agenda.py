"""The week ahead for the country editions: one agenda table, one collector,
one renderer, a small source module per country (handover item 4, 10
October 2026).

WHY ONE TABLE. Every new country's agenda has the same shape once parsed: a
dated point on a sitting (plenary or committee) with its own words and the
identifiers it prints (a Kamerstuk, a druk, a Geschäftsnummer, a dossier
ref). So the points live in one table, `country_agenda`, keyed (cc,
item_id), and each country's collector writes only its own `cc` rows. The
older agendas (de_agenda, eu_agenda, ie_schedule, au_schedule, us_schedule,
hr_items) keep their own tables: this generalises their pattern for the
new countries without moving them.

WHAT A COUNTRY SUPPLIES (src/agendas/<cc>.py):

    CC = "nl"
    SOURCE = "the Tweede Kamer's open data (Activiteit, Agendapunt)"
    BILLS = ("nl_zaken", "zaak_nummer", "onderwerp")   # table, key, title;
                                       # None when the store has no such table
    def fetch(client, today, days, log=print) -> Fetched
    def resolve(conn, refs) -> refs    # optional: printed numbers to store keys

`fetch` reads the source through src/http.py (archived to data/raw/) and
returns `Fetched(points, horizon, next_sitting, note, gaps)`. A point is a
dict built with `point()`. Its `refs` are candidate keys already in the
store's key format ('19/C.2830', 'PL 2665/2022', 'DLR5L17N54445'); the
parsers are pure functions over the raw reply, so tests run on fixtures.

MATCHING TO BILLS BY ID, never by title (CLAUDE.md). A point's refs are
looked up in the country's bill table (`BILLS`): the keys that exist become
`bill_keys`, and their stored areas and tier are joined to the point's own
classification (own_areas is the point's own words alone, so a point on our
ground only through its bill says so). Watched items: any ref or bill key in
config/watchlist-<cc>.yaml, re-checked at render so a watchlist edit needs
no recollection. Tier 1 comes from the point's own words or its bill's.

THE EDITION. `week_ahead_fn(cc)` is the adapter's `week_ahead` hook
(src/country_edition.py): the latest run's points dated from the edition
day to AHEAD_DAYS on, on our ground or watched, one entry per bill (its
other dates listed). `ahead_note_fn(cc)` is the Coverage line: when the
agenda was read, how far it reaches, the next sitting. A country whose
source has nothing ahead (a recess, an unpublished programme, a dissolved
chamber) gets no section and the Coverage line says why.

Nothing here makes a verdict or guesses what a body will decide: it says
what is on the paper and when.

ONE WRITER AT A TIME on data/parl-monitor.db: run as a step of the
country's own weekly job (jobs/<cc>-weekly.sh), after its collector.
"""

from __future__ import annotations

import collections
import datetime
import importlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AHEAD_DAYS = 14          # what the edition shows
FETCH_DAYS = 21          # what the collector reads: a week's slack for a late run
MAX_LINES_DETAIL = 260

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS country_agenda (
        cc           TEXT NOT NULL,      -- 'nl', 'pl', ...
        item_id      TEXT NOT NULL,      -- the source's own id for the point
        date         TEXT,               -- ISO date of the sitting
        time         TEXT,               -- 'HH:MM' when printed
        body         TEXT,               -- 'Plenary', or the committee's name
        kind         TEXT,               -- 'plenary' / 'committee' / 'hearing' / 'other'
        title        TEXT,               -- the point's own words, verbatim
        detail       TEXT,               -- more of the source's words, when printed
        refs         TEXT,               -- JSON: candidate keys the point prints
        bill_keys    TEXT,               -- JSON: refs found in the store's bill table
        url          TEXT,
        status       TEXT,               -- the source's own word ('Gepland', 'Convocada')
        own_areas    TEXT,               -- JSON: matched on the point's own words
        areas        TEXT,               -- JSON: + the linked bills' stored areas
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,            -- 1 or 2; NULL when not on our ground
        watch_keys   TEXT,               -- JSON: watchlist keys at collection
        first_seen   TEXT,
        last_seen    TEXT,               -- the run that last saw it
        PRIMARY KEY (cc, item_id)
    )""",
    "CREATE INDEX IF NOT EXISTS country_agenda_date ON country_agenda (cc, date)",
    """CREATE TABLE IF NOT EXISTS country_agenda_runs (
        cc           TEXT NOT NULL,
        run_date     TEXT NOT NULL,
        items        INTEGER,            -- points read
        on_ground    INTEGER,            -- of which on our ground or watched
        horizon      TEXT,               -- the latest dated point read
        next_sitting TEXT,               -- the next sitting the source names
        note         TEXT,               -- the source's state in a line
        PRIMARY KEY (cc, run_date)
    )""",
)

TABLES = ("country_agenda", "country_agenda_runs")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


Fetched = collections.namedtuple("Fetched", "points horizon next_sitting note gaps")


def fetched(points, horizon=None, next_sitting=None, note=None, gaps=()):
    """A source module's reply; `horizon` defaults to the latest point."""
    if horizon is None:
        dates = [p["date"] for p in points if p.get("date")]
        horizon = max(dates) if dates else None
    return Fetched(list(points), horizon, next_sitting, note, list(gaps))


def point(item_id, date, title, body=None, kind="plenary", time=None, detail=None,
          refs=(), url=None, status=None, text=None):
    """One agenda point, as a source module returns it. `text`, when given,
    is what is classified instead of the title and detail (Argentina: a
    committee's Temario, not its name, which says 'Culto')."""
    seen, out = set(), []
    for r in refs or ():
        r = str(r).strip()
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return {"item_id": str(item_id), "date": (date or "")[:10] or None,
            "time": time or None, "body": _one_line(body), "kind": kind,
            "title": _one_line(title), "detail": _one_line(detail) or None, "refs": out,
            "url": url, "status": _one_line(status) or None,
            "text": _one_line(text) or None}


def _one_line(text):
    return " ".join(str(text or "").replace(" ", " ").split())


def dumps(values):
    return json.dumps(list(values or []), ensure_ascii=False)


def loads(raw):
    try:
        got = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        return []
    return list(got) if isinstance(got, list) else []


def module(cc):
    return importlib.import_module("src.agendas.{0}".format(cc))


# --- classification ----------------------------------------------------------

def taxonomies(country, config_dir=None):
    """The country's compiled taxonomies, from its edition adapter's list."""
    from src import filter as filt
    out = []
    for name, code in country.taxonomies:
        path = os.path.join(config_dir or os.path.join(ROOT, "config"), name)
        if os.path.exists(path):
            out.append(filt.load_taxonomy(path, country=code))
    return out


def _empty_watchlist():
    from src import filter as filt
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def bill_rows(conn, bills, keys):
    """{key: (areas, tier, title)} for the keys present in the bill table."""
    if not bills or not keys:
        return {}
    table, keycol, titlecol = bills
    out = {}
    for k in keys:
        try:
            r = conn.execute("SELECT areas, tier, {0} FROM {1} WHERE {2} = ?".format(
                titlecol, table, keycol), (k,)).fetchone()
        except Exception:                       # noqa: BLE001 - table missing
            return out
        if r is not None:
            out[k] = (loads(r[0]), r[1], r[2])
    return out


def classify(conn, mod, points, taxes, wl):
    """Each point with own_areas, areas, matched_terms, tier, bill_keys and
    watch_keys set. Bills are matched by key only."""
    from src import filter as filt
    empty = _empty_watchlist()
    resolve = getattr(mod, "resolve", None)
    bills = getattr(mod, "BILLS", None)
    out = []
    for p in points:
        refs = list(p["refs"])
        if resolve:
            refs = list(dict.fromkeys(refs + list(resolve(conn, refs) or [])))
        linked = bill_rows(conn, bills, refs)
        own, terms, tiers = set(), [], set()
        for tax in taxes:
            if p.get("text"):
                res = filt.filter_item(tax, empty, p["text"], title="")
            else:
                res = filt.filter_item(tax, empty, p["title"] or "", p["detail"] or "",
                                       title=p["title"] or "")
            own.update(res.issue_areas or [])
            terms += [t for t in res.matched_terms or [] if t not in terms]
            if res.tier:
                tiers.add(res.tier)
        areas = set(own)
        for k, (b_areas, b_tier, _title) in linked.items():
            areas.update(int(a) for a in b_areas if str(a).isdigit())
            if b_tier and b_areas:
                tiers.add(int(b_tier))
        watch = [k for k in refs if k in wl]
        q = dict(p, refs=refs, bill_keys=list(linked), own_areas=sorted(own),
                 areas=sorted(areas), matched_terms=terms,
                 tier=min(tiers) if tiers else (2 if watch else None),
                 watch_keys=watch)
        out.append(q)
    return out


def on_ground(p):
    from src import latam
    return bool(latam.areas_of(p.get("areas"))) or bool(p.get("watch_keys"))


# --- the store ---------------------------------------------------------------

def store(conn, cc, points, today):
    """Upsert the run's points; returns (stored, new). A point an earlier
    run of the same day stored and this run no longer carries (a rerun after
    a sitting was cancelled) loses its last_seen, so it leaves the edition."""
    ids = [p["item_id"] for p in points]
    conn.execute("UPDATE country_agenda SET last_seen = NULL WHERE cc = ? AND last_seen = ? "
                 "AND item_id NOT IN ({0})".format(",".join("?" * len(ids)) or "''"),
                 [cc, today] + ids)
    new = 0
    for p in points:
        before = conn.execute("SELECT 1 FROM country_agenda WHERE cc = ? AND item_id = ?",
                              (cc, p["item_id"])).fetchone()
        if not before:
            new += 1
        conn.execute(
            "INSERT INTO country_agenda (cc, item_id, date, time, body, kind, title, detail, "
            "refs, bill_keys, url, status, own_areas, areas, matched_terms, tier, watch_keys, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(cc, item_id) DO UPDATE SET date=excluded.date, time=excluded.time, "
            "body=excluded.body, kind=excluded.kind, title=excluded.title, "
            "detail=excluded.detail, refs=excluded.refs, bill_keys=excluded.bill_keys, "
            "url=excluded.url, status=excluded.status, own_areas=excluded.own_areas, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
            "watch_keys=excluded.watch_keys, last_seen=excluded.last_seen",
            (cc, p["item_id"], p["date"], p["time"], p["body"], p["kind"], p["title"],
             p["detail"], dumps(p["refs"]), dumps(p.get("bill_keys")), p["url"], p["status"],
             dumps(p.get("own_areas")), dumps(p.get("areas")), dumps(p.get("matched_terms")),
             p.get("tier"), dumps(p.get("watch_keys")), today, today))
    conn.commit()
    return len(points), new


def record_run(conn, cc, today, result, n_ground):
    conn.execute(
        "INSERT INTO country_agenda_runs (cc, run_date, items, on_ground, horizon, "
        "next_sitting, note) VALUES (?,?,?,?,?,?,?) ON CONFLICT(cc, run_date) DO UPDATE SET "
        "items=excluded.items, on_ground=excluded.on_ground, horizon=excluded.horizon, "
        "next_sitting=excluded.next_sitting, note=excluded.note",
        (cc, today, len(result.points), n_ground, result.horizon, result.next_sitting,
         result.note))
    conn.commit()


def collect(conn, cc, client, today, days=FETCH_DAYS, config_dir=None, log=print,
            mod=None, country=None):
    """One country's agenda: fetch, classify, store. Returns (points, on
    ground, gaps). Gaps are recorded in the gaps table as '<cc>-agenda'."""
    from src import country_edition as ce
    from src import db
    mod = mod or module(cc)
    country = country or ce.adapter(cc)
    ensure_schema(conn)
    result = mod.fetch(client, today, days, log)
    for g in result.gaps:
        db.record_gap(conn, "{0}-agenda".format(cc), g, today)
    if result.gaps and not result.points:
        # The source failed outright: keep the last good read (the edition's
        # Coverage line names its date) rather than record an empty agenda.
        log("{0}-agenda: nothing read ({1} gap(s)); the last good read stands.".format(
            cc, len(result.gaps)))
        return 0, 0, len(result.gaps)
    wl = ce.watchlist_of(country, config_dir)
    got = classify(conn, mod, result.points, taxonomies(country, config_dir), wl)
    store(conn, cc, got, today)
    ours = [p for p in got if on_ground(p)]
    record_run(conn, cc, today, result, len(ours))
    for p in ours:
        log("  [agenda] {0} {1} {2}{3}: {4}".format(
            cc, p["date"], p["areas"] or "", " watched " + ",".join(p["watch_keys"])
            if p["watch_keys"] else "", (p["title"] or "")[:70]))
    log("{0}-agenda: {1} point(s) read, {2} on our ground or watched; reaches {3}{4}.".format(
        cc, len(got), len(ours), result.horizon or "no dated point",
        "; next sitting " + result.next_sitting if result.next_sitting else ""))
    return len(got), len(ours), len(result.gaps)


# --- the edition ---------------------------------------------------------------

def latest_run(conn, cc):
    try:
        r = conn.execute("SELECT run_date, items, on_ground, horizon, next_sitting, note "
                         "FROM country_agenda_runs WHERE cc = ? ORDER BY run_date DESC LIMIT 1",
                         (cc,)).fetchone()
    except Exception:                           # noqa: BLE001 - table missing
        return None
    return tuple(r) if r else None


def _weekday_date(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or "?"
    return "{0} {1} {2}".format(d.strftime("%a"), d.day, d.strftime("%b"))


def ahead_items(conn, cc, today, wl, days=AHEAD_DAYS, kinds=None):
    """The edition's week-ahead items from the latest run: on our ground or
    watched, one per bill (or per point when it names none)."""
    from src import country_edition as ce
    run = latest_run(conn, cc)
    if not run:
        return []
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    rows_ = ce.rows(conn, "SELECT * FROM country_agenda WHERE cc = ? AND last_seen = ? "
                          "AND date >= ? AND date <= ? ORDER BY date, time, item_id",
                    (cc, run[0], today, until))
    groups = collections.OrderedDict()
    for r in rows_:
        if kinds and r["kind"] not in kinds:
            continue
        refs = loads(r["refs"])
        bills = loads(r["bill_keys"])
        watched = [k for k in list(dict.fromkeys(bills + refs)) if k in wl]
        areas = ce.areas_of(r["areas"])
        if not areas and not watched:
            continue
        gkey = (watched[0] if watched else bills[0] if bills else "item:" + r["item_id"])
        groups.setdefault(gkey, []).append((r, watched, bills, areas))
    out = []
    for gkey, members in groups.items():
        r, watched, bills, areas = members[0]
        when = _weekday_date(r["date"]) + (" at {0}".format(r["time"]) if r["time"] else "")
        take = "{0}, {1}".format(r["body"] or "Sitting", when)
        if bills or watched:
            take += "; {0}".format(", ".join(list(dict.fromkeys(watched + bills))[:3]))
        lines = []
        if r["detail"] and r["detail"] != r["title"]:
            lines.append("On the paper: *{0}*".format(ce.clip(r["detail"], MAX_LINES_DETAIL)))
        more = [m for m in members[1:]]
        if more:
            lines.append("Also on the agenda: {0}.".format("; ".join(
                "{0} ({1})".format(_weekday_date(m[0]["date"]), m[0]["body"] or "sitting")
                for m in more[:6])))
        tiers = [m[0]["tier"] for m in members if m[0]["tier"]]
        out.append(ce.item(cc, "agenda", r["item_id"], r["date"], r["title"], areas,
                           min(tiers) if tiers else None, bool(watched),
                           status=r["status"], url=r["url"], lines=lines,
                           terms=r["matched_terms"], takeaway=take,
                           own=(True if ce.areas_of(r["own_areas"]) else
                                False if areas else None),
                           watch_key=watched[0] if watched else None))
    return out


def week_ahead_fn(cc, days=AHEAD_DAYS, kinds=None):
    """The adapter's `week_ahead` hook for a country with a src/agendas module."""
    def week_ahead(conn, today, wl):
        return ahead_items(conn, cc, today, wl, days, kinds)
    return week_ahead


def ahead_note(conn, cc, today, source=None):
    """The Coverage line for the week ahead."""
    from src import country_edition as ce
    src_text = " ({0})".format(source) if source else ""
    run = latest_run(conn, cc)
    if not run:
        return "Week ahead{0}: the agenda has not been read yet.".format(src_text)
    run_date, items, ground, horizon, next_sitting, note = run
    bits = ["Week ahead{0}: read {1}, {2} point(s), {3} on our ground or watched".format(
        src_text, ce.long_date(run_date), items or 0, ground or 0)]
    if horizon:
        bits.append("the agenda reaches {0}".format(ce.long_date(horizon)))
    if next_sitting and next_sitting >= today:
        bits.append("next sitting {0}".format(ce.long_date(next_sitting)))
    line = "; ".join(bits) + "."
    if note:
        line += " " + ce.clean(note).rstrip(".") + "."
    return line


def ahead_note_fn(cc):
    def note(conn, today):
        mod = module(cc)
        return ahead_note(conn, cc, today, getattr(mod, "SOURCE", None))
    return note
