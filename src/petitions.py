"""Petitions and consultations for the new country editions: one table, one
collector, one renderer, a small source module per country (parity layer
"committees, courts, petitions, consultations", 11 October 2026).

WHAT IT COVERS. Parliamentary e-petitions and citizens' initiatives (the
Assemblée nationale's and the Sénat's petition platforms, Austria's
Petitionen and Bürgerinitiativen, Swiss Petitionen, ...) and government
consultations with a deadline (Austria's Ministerialentwürfe in
Begutachtung, the Dutch internetconsultatie, ...). Each is the one section
of an edition that can say RESPOND BY A DATE, which is why Germany's
petitions (tools/de_petitions.py) were built; this generalises that file
and Westminster's (tools/pull_petitions.py), gov.uk's consultations
(tools/dg_consultations.py) and the ECI watch (tools/eu_eci.py) for the new
countries, without moving them.

WHY ONE TABLE. Once parsed, every source has the same shape: an id, a
title, a summary or text, a status, an opening and a closing date, maybe a
signature count and the thresholds that make it matter. So the rows live in
one table, `country_petitions`, keyed (cc, item_id) with the source's short
code in the id ('an:i-7242'), and each country's collector writes only its
own `cc` rows. Signature counts are snapshotted per run
(`country_petition_snapshots`) so a threshold crossed this week can be
told from one crossed last month; each run is recorded per source
(`country_petition_runs`) so "nothing on our ground" can be told from
"never read".

WHAT A COUNTRY SUPPLIES (src/petition_sources/<cc>.py):

    CC = "fr"
    SOURCES = (Source(code="an", name="...", kind="petition", fetch=fn,
                      detail=fn_or_None, detail_all=False,
                      thresholds=((100000, "what reaching it does"),)),)

`fetch(client, today, log)` reads the source through src/http.py (archived
to data/raw/) and returns `fetched(entries, note, gaps)`; an entry is built
with `entry()`. `detail(client, entry, log)`, when given, reads one item's
own page and returns a dict of fields to update (its text, closing date,
status); the collector calls it for new items that matched on their listed
words (or every new item when `detail_all`), within a per-run cap. The
parsers are pure functions over the raw reply, so tests run on fixtures.

CLASSIFICATION, on the item's own words only, with the country's taxonomies
from its edition adapter: the title and the summary through
src/filter.filter_item (tier 1 or 2, as a question is); a long text (a
petition's full wording, a draft's explanatory note) passage by passage
through filter.match_passages (tier 1 in a passage, the chamber layer's
long-text guard). Watched: the item id or any ref in
config/watchlist-<cc>.yaml. Never a keyword alone without the taxonomy.

THE EDITION (src/country_edition.py, kind "petition", section "Petitions
and consultations"). An item on our ground or watched appears when, in the
edition's window, it is NEW (first seen), crossed a THRESHOLD (a signature
milestone between the last snapshot before the window and the latest in
it), SURGED (gained SURGE signatures or votes in the window: a public vote
on a bill has no threshold, only movement), or CLOSES (in the window or within CLOSING_DAYS after it). Lines give
the signatures and the week's movement, the threshold and what reaching it
does, and the dates. A "For campaigns" line flags what could matter to a
CitizenGO campaign: open, on our ground, and near a threshold or closing
soon (or a consultation still taking responses). No verdicts: the line says
what is open and when, never which side to take.

Read-only except for store(), record_run() and reclassify().
ONE WRITER AT A TIME on data/parl-monitor.db: run as a step of the
country's own weekly job, after its collector and before its edition.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime
import importlib
import json
import os
import re
from typing import Callable, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEXT_CAP = 8000           # an item's own text kept for classification
SUMMARY_CAP = 600
CLOSING_DAYS = 14         # "closes soon": in the window or this many days after
NEAR_SHARE = 0.5          # "near a threshold": at least half way to the next one
SURGE = 10000             # signatures or votes gained in the window that make news alone
DETAIL_LIMIT = 60         # item pages read per source per run
DETAIL_SECONDS = 600      # and no new item page once a country's run is this old

KINDS = {
    "petition": "Petition", "initiative": "Citizens' initiative",
    "consultation": "Consultation", "idea": "Citizens' idea",
    "public_vote": "Public vote on a bill", "referendum": "Referendum or popular initiative",
}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS country_petitions (
        cc           TEXT NOT NULL,      -- 'fr', 'at', ...
        item_id      TEXT NOT NULL,      -- '<source>:<the source's own id>'
        source       TEXT,               -- the source's short code ('an', 'senat', 'me')
        kind         TEXT,               -- petition / initiative / consultation / idea / ...
        title        TEXT,               -- verbatim
        summary      TEXT,               -- the source's own short text, verbatim, capped
        text         TEXT,               -- the item's own full text when read, capped
        status       TEXT,               -- the source's own word ('En cours', 'Enregistrée')
        opened       TEXT,               -- ISO date it opened for signatures or responses
        closes       TEXT,               -- ISO date it closes (NULL: no deadline published)
        signatures   INTEGER,            -- the latest count, when the source gives one
        prev_signatures INTEGER,         -- the count at the previous run that differed
        yes_count    INTEGER,            -- a public vote's for / against (e-Cidadania)
        no_count     INTEGER,
        thresholds   TEXT,               -- JSON [[n, what reaching it does], ...]
        body         TEXT,               -- the committee, ministry or office it goes to
        author       TEXT,               -- the petitioner or ministry, as printed
        url          TEXT,
        refs         TEXT,               -- JSON: bill keys it names, when the source links one
        areas        TEXT,               -- JSON: from its own words
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        watch_keys   TEXT,               -- JSON: watchlist keys at collection
        detail_read  TEXT,               -- ISO date its own page was read (NULL: never)
        first_seen   TEXT,
        last_seen    TEXT,               -- the run that last listed it
        PRIMARY KEY (cc, item_id)
    )""",
    "CREATE INDEX IF NOT EXISTS country_petitions_seen ON country_petitions (cc, first_seen)",
    """CREATE TABLE IF NOT EXISTS country_petition_snapshots (
        cc           TEXT NOT NULL,
        item_id      TEXT NOT NULL,
        captured_at  TEXT NOT NULL,      -- ISO date of the run
        signatures   INTEGER,
        PRIMARY KEY (cc, item_id, captured_at)
    )""",
    """CREATE TABLE IF NOT EXISTS country_petition_runs (
        cc           TEXT NOT NULL,
        source       TEXT NOT NULL,
        run_date     TEXT NOT NULL,
        listed       INTEGER,            -- items the source listed
        on_ground    INTEGER,            -- of which on our ground or watched
        details      INTEGER,            -- item pages read this run
        note         TEXT,
        PRIMARY KEY (cc, source, run_date)
    )""",
)

TABLES = ("country_petitions", "country_petition_snapshots", "country_petition_runs")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


# --- what a source module returns --------------------------------------------

@dataclasses.dataclass
class Source:
    code: str
    name: str
    kind: str
    fetch: Callable
    detail: Optional[Callable] = None
    detail_all: bool = False
    thresholds: tuple = ()
    url: str = ""


Fetched = collections.namedtuple("Fetched", "entries note gaps")


def fetched(entries, note=None, gaps=()):
    return Fetched(list(entries), note, list(gaps))


def one_line(text):
    return " ".join(str(text or "").replace("\xa0", " ").split())


def iso(value):
    """An ISO date from 'YYYY-MM-DD...', 'DD/MM/YYYY' or 'DD.MM.YYYY'; else None."""
    s = str(value or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "{0}-{1}-{2}".format(*m.groups())
    m = re.match(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
    if m:
        return "{2}-{1:0>2}-{0:0>2}".format(*m.groups())
    return None


def number(value):
    """An int from '2 228', '12.345', '1,234', 2228; else None."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def entry(source, item_id, title, kind=None, summary=None, text=None, status=None,
          opened=None, closes=None, signatures=None, thresholds=None, body=None, author=None,
          url=None, refs=(), yes_count=None, no_count=None):
    """One petition or consultation, as a source module returns it."""
    return {"source": source, "item_id": "{0}:{1}".format(source, item_id),
            "kind": kind, "title": one_line(title), "summary": one_line(summary)[:SUMMARY_CAP] or None,
            "text": (str(text).strip()[:TEXT_CAP] if text else None),
            "status": one_line(status) or None, "opened": iso(opened), "closes": iso(closes),
            "signatures": number(signatures), "yes_count": number(yes_count),
            "no_count": number(no_count),
            "thresholds": [list(t) for t in thresholds] if thresholds is not None else None,
            "body": one_line(body) or None, "author": one_line(author) or None, "url": url,
            "refs": [str(r) for r in refs or () if str(r).strip()]}


def dumps(values):
    return json.dumps(list(values or []), ensure_ascii=False)


def loads(raw):
    try:
        got = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        return []
    return list(got) if isinstance(got, list) else []


def module(cc):
    return importlib.import_module("src.petition_sources.{0}".format(cc))


def countries():
    """The codes with a source module."""
    here = os.path.join(ROOT, "src", "petition_sources")
    return tuple(sorted(f[:-3] for f in os.listdir(here)
                        if f.endswith(".py") and not f.startswith("_")))


# --- classification ----------------------------------------------------------

def _adapter(cc):
    """The country's edition adapter, or None (a Latam country in the monthly
    Latam edition, which names its own TAXONOMIES in its source module)."""
    from src import country_edition as ce
    try:
        return ce.adapter(cc)
    except ImportError:
        return None


def taxonomies(cc, config_dir=None, mod=None):
    """The country's taxonomies: its edition adapter's list, or the source
    module's TAXONOMIES ((file, code), ...) for a country without one."""
    from src import agenda
    country = _adapter(cc)
    if country is None:
        mod = mod or module(cc)
        country = collections.namedtuple("C", "taxonomies")(getattr(mod, "TAXONOMIES", ()))
    return agenda.taxonomies(country, config_dir)


def watchlist(cc, config_dir=None):
    from src import country_edition as ce
    from src import latam
    country = _adapter(cc)
    return ce.watchlist_of(country, config_dir) if country else latam.watchlist(cc, config_dir)


def classify(e, taxes, wl):
    """The entry with areas, matched_terms, tier and watch_keys set."""
    from src import filter as filt
    empty = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])
    areas, terms, tiers = set(), [], set()
    for tax in taxes:
        res = filt.filter_item(tax, empty, e["title"] or "", e.get("summary") or "",
                               title=e["title"] or "")
        if res.issue_areas:
            areas.update(res.issue_areas)
            terms += [t for t in res.matched_terms if t not in terms]
            if res.tier:
                tiers.add(res.tier)
        if e.get("text"):
            got, t_terms, _ = filt.aggregate_passages(filt.match_passages(tax, empty, e["text"]))
            if got:
                areas.update(got)
                terms += [t for t in t_terms if t not in terms]
                tiers.add(1)
    key = e["item_id"].split(":", 1)[-1]
    watch = [k for k in [e["item_id"], key] + list(e.get("refs") or []) if k in wl]
    return dict(e, areas=sorted(int(a) for a in areas), matched_terms=terms,
                tier=min(tiers) if tiers and areas else (2 if watch else None),
                watch_keys=watch)


def on_ground(e):
    from src import latam
    return bool(latam.areas_of(e.get("areas"))) or bool(e.get("watch_keys"))


# --- the store ---------------------------------------------------------------

def store(conn, cc, entries, today, src=None):
    """Upsert the run's entries and snapshot their counts; returns new ids."""
    new = []
    for e in entries:
        before = conn.execute("SELECT signatures FROM country_petitions WHERE cc=? AND item_id=?",
                              (cc, e["item_id"])).fetchone()
        if before is None:
            new.append(e["item_id"])
        prev = before[0] if before is not None else None
        th = e.get("thresholds")
        if th is None and src is not None:
            th = [list(t) for t in src.thresholds]
        conn.execute(
            "INSERT INTO country_petitions (cc, item_id, source, kind, title, summary, text, "
            "status, opened, closes, signatures, prev_signatures, yes_count, no_count, "
            "thresholds, body, author, url, refs, areas, matched_terms, tier, watch_keys, "
            "detail_read, first_seen, last_seen) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(cc, item_id) DO UPDATE SET source=excluded.source, kind=excluded.kind, "
            "title=excluded.title, summary=COALESCE(excluded.summary, country_petitions.summary), "
            "text=COALESCE(excluded.text, country_petitions.text), status=excluded.status, "
            "opened=COALESCE(excluded.opened, country_petitions.opened), "
            "closes=COALESCE(excluded.closes, country_petitions.closes), "
            "prev_signatures=CASE WHEN excluded.signatures IS NOT NULL AND "
            "country_petitions.signatures IS NOT NULL AND excluded.signatures != "
            "country_petitions.signatures THEN country_petitions.signatures ELSE "
            "country_petitions.prev_signatures END, "
            "signatures=COALESCE(excluded.signatures, country_petitions.signatures), "
            "yes_count=COALESCE(excluded.yes_count, country_petitions.yes_count), "
            "no_count=COALESCE(excluded.no_count, country_petitions.no_count), "
            "thresholds=excluded.thresholds, body=COALESCE(excluded.body, country_petitions.body), "
            "author=COALESCE(excluded.author, country_petitions.author), url=excluded.url, "
            "refs=excluded.refs, areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "tier=excluded.tier, watch_keys=excluded.watch_keys, "
            "detail_read=COALESCE(excluded.detail_read, country_petitions.detail_read), "
            "last_seen=excluded.last_seen",
            (cc, e["item_id"], e["source"], e.get("kind"), e["title"], e.get("summary"),
             e.get("text"), e.get("status"), e.get("opened"), e.get("closes"),
             e.get("signatures"), prev if before is not None else None, e.get("yes_count"),
             e.get("no_count"), json.dumps(th or [], ensure_ascii=False), e.get("body"),
             e.get("author"), e.get("url"), dumps(e.get("refs")), dumps(e.get("areas")),
             dumps(e.get("matched_terms")), e.get("tier"), dumps(e.get("watch_keys")),
             e.get("detail_read"), today, today))
        if e.get("signatures") is not None:
            conn.execute("INSERT OR REPLACE INTO country_petition_snapshots (cc, item_id, "
                         "captured_at, signatures) VALUES (?,?,?,?)",
                         (cc, e["item_id"], today, e["signatures"]))
    conn.commit()
    return new


def record_run(conn, cc, source, today, listed, ground, details, note):
    conn.execute(
        "INSERT INTO country_petition_runs (cc, source, run_date, listed, on_ground, details, "
        "note) VALUES (?,?,?,?,?,?,?) ON CONFLICT(cc, source, run_date) DO UPDATE SET "
        "listed=excluded.listed, on_ground=excluded.on_ground, details=excluded.details, "
        "note=excluded.note", (cc, source, today, listed, ground, details, note))
    conn.commit()


def needs_detail(conn, cc, e, src):
    """True when the item's own page should be read this run."""
    if not src.detail:
        return False
    r = conn.execute("SELECT detail_read FROM country_petitions WHERE cc=? AND item_id=?",
                     (cc, e["item_id"])).fetchone()
    if r is not None and r[0]:
        return False
    return src.detail_all or on_ground(e)


def collect(conn, cc, client, today, config_dir=None, log=print, mod=None, detail=True,
            detail_limit=DETAIL_LIMIT, detail_seconds=DETAIL_SECONDS):
    """One country's petitions and consultations: fetch, classify, read the
    pages that need it, store. Returns (listed, on ground, gaps). Item pages
    stop at detail_limit per source or once the run is detail_seconds old
    (Brazil's pages take up to a minute each); the rest are read next run."""
    import time
    started = time.monotonic()
    from src import db
    mod = mod or module(cc)
    ensure_schema(conn)
    taxes = taxonomies(cc, config_dir, mod)
    wl = watchlist(cc, config_dir)
    total = ground_total = gaps_total = 0
    for src in mod.SOURCES:
        feed = "{0}-petitions-{1}".format(cc, src.code)
        try:
            result = src.fetch(client, today, log)
        except Exception as exc:                    # noqa: BLE001
            result = fetched([], gaps=["fetch failed: {0}: {1}".format(
                type(exc).__name__, str(exc)[:160])])
        for g in result.gaps:
            db.record_gap(conn, feed, g, today)
        gaps_total += len(result.gaps)
        if result.gaps and not result.entries:
            log("{0}: nothing read ({1} gap(s)); the last good read stands.".format(
                feed, len(result.gaps)))
            continue
        got, details = [], 0
        for e in result.entries:
            e = dict(e, kind=e.get("kind") or src.kind)
            e = classify(e, taxes, wl)
            if detail and details < detail_limit and \
                    time.monotonic() - started < detail_seconds and needs_detail(conn, cc, e, src):
                try:
                    upd = src.detail(client, e, log) or {}
                    details += 1
                    e = classify(dict(e, **{k: v for k, v in upd.items() if v is not None},
                                      detail_read=today), taxes, wl)
                except Exception as exc:            # noqa: BLE001
                    db.record_gap(conn, feed, "page of {0} unreadable: {1}".format(
                        e["item_id"], str(exc)[:120]), today)
                    gaps_total += 1
                    e = dict(e, detail_read=today)   # not retried for ever
            got.append(e)
        new = store(conn, cc, got, today, src)
        ours = [e for e in got if on_ground(e)]
        record_run(conn, cc, src.code, today, len(got), len(ours), details, result.note)
        for e in ours:
            log("  [petition] {0} {1}{2} {3}: {4}".format(
                cc, e["item_id"], " new" if e["item_id"] in new else "", e["areas"] or "watched",
                (e["title"] or "")[:70]))
        log("{0}: {1} listed, {2} new, {3} on our ground, {4} page(s) read.".format(
            feed, len(got), len(new), len(ours), details))
        total += len(got)
        ground_total += len(ours)
    return total, ground_total, gaps_total


def reclassify(conn, cc, config_dir=None, log=print):
    """Re-derive stored rows' areas offline (after a taxonomy change)."""
    ensure_schema(conn)
    taxes = taxonomies(cc, config_dir)
    wl = watchlist(cc, config_dir)
    changed = 0
    for r in conn.execute("SELECT item_id, title, summary, text, refs, areas FROM "
                          "country_petitions WHERE cc=?", (cc,)).fetchall():
        e = classify({"item_id": r[0], "title": r[1], "summary": r[2], "text": r[3],
                      "refs": loads(r[4])}, taxes, wl)
        new = dumps(e["areas"])
        changed += new != (r[5] or "[]")
        conn.execute("UPDATE country_petitions SET areas=?, matched_terms=?, tier=?, "
                     "watch_keys=? WHERE cc=? AND item_id=?",
                     (new, dumps(e["matched_terms"]), e["tier"], dumps(e["watch_keys"]), cc, r[0]))
    conn.commit()
    log("{0}-petitions: reclassified; {1} row(s) changed area".format(cc, changed))
    return changed


# --- the edition ---------------------------------------------------------------

def _count_at(conn, cc, item_id, on_or_before):
    try:
        r = conn.execute("SELECT signatures FROM country_petition_snapshots WHERE cc=? AND "
                         "item_id=? AND captured_at <= ? ORDER BY captured_at DESC LIMIT 1",
                         (cc, item_id, on_or_before)).fetchone()
    except Exception:                               # noqa: BLE001 - table missing
        return None
    return r[0] if r else None


def _fmt(n):
    return "{0:,}".format(int(n)) if n is not None else "?"


def _days(a, b):
    try:
        return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
    except (TypeError, ValueError):
        return None


def next_threshold(signatures, thresholds):
    for t in sorted(thresholds, key=lambda x: x[0]):
        if signatures is None or signatures < t[0]:
            return t
    return None


def crossed(before, now, thresholds):
    """The thresholds passed between two counts."""
    if now is None:
        return []
    lo = before if before is not None else -1
    return [t for t in sorted(thresholds, key=lambda x: x[0]) if lo < t[0] <= now]


def is_open(r, today):
    closes = r["closes"]
    return not closes or closes >= today


def campaign_note(r, today, signatures, thresholds):
    """Why an open item on our ground could matter to a CitizenGO campaign, or None."""
    if not is_open(r, today):
        return None
    bits = []
    left = _days(today, r["closes"]) if r["closes"] else None
    nxt = next_threshold(signatures, thresholds)
    if nxt and signatures is not None and signatures >= NEAR_SHARE * nxt[0]:
        bits.append("{0:.0f}% of the way to {1} signatures".format(
            100.0 * signatures / nxt[0], _fmt(nxt[0])))
    if left is not None and 0 <= left <= CLOSING_DAYS:
        bits.append("closes in {0} day{1}".format(left, "" if left == 1 else "s"))
    if r["kind"] == "consultation":
        bits.append("still taking responses")
    if not bits:
        return None
    return "For campaigns: open, on our ground, " + ", ".join(bits) + "."


def edition_items(conn, cc, since, until, wl):
    """The country's petitions and consultations for the edition window (see
    the module docstring). [] when the country has none."""
    from src import country_edition as ce
    out = []
    soon = (datetime.date.fromisoformat(until)
            + datetime.timedelta(days=CLOSING_DAYS)).isoformat()
    rows_ = ce.rows(conn, "SELECT * FROM country_petitions WHERE cc = ? AND ("
                          "(first_seen > ? AND first_seen <= ?) OR (closes > ? AND closes <= ?) "
                          "OR last_seen > ?) ORDER BY item_id", (cc, since, until, since, soon, since))
    # A source's first run lists everything already open: those rows are the
    # baseline, not news, unless they opened inside the window.
    baseline = {r[0]: r[1] for r in ce.rows(
        conn, "SELECT source, MIN(run_date) FROM country_petition_runs WHERE cc = ? "
              "GROUP BY source", (cc,))}
    for r in rows_:
        watch = [k for k in loads(r["watch_keys"]) + [r["item_id"], r["item_id"].split(":", 1)[-1]]
                 + loads(r["refs"]) if k in wl]
        if not ce.on_ground(r["areas"], bool(watch)):
            continue
        thresholds = [t for t in loads(r["thresholds"]) if isinstance(t, list) and t]
        now = _count_at(conn, cc, r["item_id"], until)
        if now is None:
            now = r["signatures"]
        before = _count_at(conn, cc, r["item_id"], since)
        is_new = since < (r["first_seen"] or "") <= until and (
            (r["first_seen"] or "") > baseline.get(r["item_id"].split(":", 1)[0], "")
            or since < (r["opened"] or "") <= until)
        # A crossing needs a count from before the window: on a source's first
        # run there is none, and a threshold passed long ago is not news.
        passed = crossed(before, now, thresholds) if before is not None and not is_new else []
        closing = bool(r["closes"]) and since < r["closes"] <= soon
        surge = (not is_new and before is not None and now is not None
                 and now - before >= SURGE)
        if not (is_new or passed or closing or surge):
            continue
        what = KINDS.get(r["kind"], (r["kind"] or "Petition").capitalize())
        take = what
        if r["body"]:
            take += " ({0})".format(r["body"])
        events = []
        if is_new:
            events.append("new in this edition")
        if passed:
            events.append("passed {0} signatures".format(_fmt(passed[-1][0])))
        elif surge:
            events.append("{0:+,} {1} in the window".format(
                now - before, "votes" if r["kind"] == "public_vote" else "signatures"))
        if closing:
            events.append("closed {0}".format(ce.short_date(r["closes"])) if r["closes"] <= until
                          else "closes {0}".format(ce.short_date(r["closes"])))
        take += ": " + ", ".join(events)
        lines = []
        if now is not None:
            line = "{0}: {1}".format("Votes cast" if r["kind"] == "public_vote" else
                                     "Signatures", _fmt(now))
            if before is not None and now != before and not is_new:
                line += " ({0:+,} since {1})".format(now - before, ce.short_date(since))
            nxt = next_threshold(now, thresholds)
            if nxt:
                line += "; {0} needed: {1}".format(_fmt(nxt[0]), ce.clean(nxt[1]) if len(nxt) > 1
                                                   else "the next threshold")
            elif thresholds:
                line += "; every threshold passed ({0})".format(
                    "; ".join("{0}: {1}".format(_fmt(t[0]), t[1]) for t in thresholds if len(t) > 1))
            lines.append(line.rstrip(".") + ".")
        for t in passed:
            if len(t) > 1:
                lines.append("Threshold passed: {0} ({1}).".format(_fmt(t[0]), ce.clean(t[1])))
        if r["yes_count"] is not None or r["no_count"] is not None:
            lines.append("Public vote so far: {0} for, {1} against.".format(
                _fmt(r["yes_count"]), _fmt(r["no_count"])))
        dates = []
        if r["opened"]:
            dates.append("opened {0}".format(ce.long_date(r["opened"])))
        if r["closes"]:
            dates.append("{0} {1}".format("closed" if r["closes"] < until else "closes",
                                          ce.long_date(r["closes"])))
        else:
            dates.append("no closing date published")
        lines.append("Dates: " + ", ".join(dates) + ".")
        if r["summary"] and r["summary"] != r["title"]:
            lines.append("In its own words: “{0}”".format(ce.clip(r["summary"], 260)))
        note = campaign_note(r, until, now, thresholds)
        if note:
            lines.append(note)
        opened_in = since < (r["opened"] or "") <= until
        date = (r["opened"] if opened_in else r["first_seen"]) if is_new else (r["closes"] if closing and r["closes"] <= until
                                               else until)
        out.append(ce.item(cc, "petition", r["item_id"], date, r["title"], ce.areas_of(r["areas"]),
                           r["tier"], bool(watch), status=r["status"], url=r["url"], lines=lines,
                           terms=r["matched_terms"], body=r["summary"] or "",
                           takeaway=take, watch_key=watch[0] if watch else None))
    return out


def coverage_lines(conn, cc, since, until):
    """What was read: one Coverage line per source, from its latest run."""
    from src import country_edition as ce
    got = ce.rows(conn, "SELECT r.source, r.run_date, r.listed, r.on_ground, r.note FROM "
                        "country_petition_runs r WHERE r.cc = ? AND r.run_date = (SELECT "
                        "MAX(run_date) FROM country_petition_runs s WHERE s.cc = r.cc AND "
                        "s.source = r.source) ORDER BY r.source", (cc,))
    if not got:
        return []
    names = {}
    try:
        names = {s.code: s.name for s in module(cc).SOURCES}
    except Exception:                               # noqa: BLE001
        pass
    bits = []
    for r in got:
        bit = "{0}: read {1}, {2} listed, {3} on our ground".format(
            names.get(r[0], r[0]), ce.long_date(r[1]), r[2] or 0, r[3] or 0)
        if r[4]:
            bit += " ({0})".format(ce.clean(r[4]).rstrip("."))
        bits.append(bit)
    return ["Petitions and consultations: " + "; ".join(bits) + "."]


# --- the campaign view ------------------------------------------------------------

def campaign_report(conn, cc, today, limit=25):
    """Markdown: the country's OPEN items on our ground (or watched), those
    nearest a threshold or a deadline first, each with what makes it matter
    to a campaign. For Chris and the country team; never posted."""
    from src import country_edition as ce
    wl = watchlist(cc)
    rows_ = ce.rows(conn, "SELECT * FROM country_petitions WHERE cc = ? AND last_seen = "
                          "(SELECT MAX(last_seen) FROM country_petitions WHERE cc = ?)", (cc, cc))
    scored = []
    for r in rows_:
        watched = any(k in wl for k in [r["item_id"], r["item_id"].split(":", 1)[-1]]
                      + loads(r["refs"]))
        if not ce.on_ground(r["areas"], watched) or not is_open(r, today):
            continue
        thresholds = [t for t in loads(r["thresholds"]) if isinstance(t, list) and t]
        nxt = next_threshold(r["signatures"], thresholds)
        share = (r["signatures"] or 0) / float(nxt[0]) if nxt and r["signatures"] is not None else 0
        left = _days(today, r["closes"]) if r["closes"] else None
        scored.append((-(share), left if left is not None else 10 ** 6, r, nxt, watched))
    scored.sort(key=lambda x: (x[0], x[1]))
    out = ["## {0}: open on our ground ({1})".format(cc.upper(), len(scored)), ""]
    if not scored:
        return out + ["Nothing open on our ground in the latest read.", ""]
    for _, left, r, nxt, watched in scored[:limit]:
        bits = [KINDS.get(r["kind"], r["kind"] or "Item")]
        if r["signatures"] is not None:
            bits.append("{0} {1}".format(_fmt(r["signatures"]), "votes" if r["kind"] ==
                                         "public_vote" else "signatures"))
        if nxt and r["signatures"] is not None:
            bits.append("{0:.0f}% of {1}".format(100.0 * (r["signatures"] or 0) / nxt[0],
                                                  _fmt(nxt[0])))
        elif nxt:
            bits.append("{0} needed, no count published".format(_fmt(nxt[0])))
        if r["yes_count"] is not None:
            bits.append("{0} for, {1} against".format(_fmt(r["yes_count"]), _fmt(r["no_count"])))
        if r["closes"]:
            bits.append("closes {0}".format(ce.long_date(r["closes"])))
        if watched:
            bits.append("watched")
        note = campaign_note(r, today, r["signatures"], [t for t in loads(r["thresholds"])
                                                          if isinstance(t, list) and t])
        out.append("- *{0}* ({1}). {2}.{3} [Source]({4})".format(
            ce.clip(r["title"], 200), ce.area_text(ce.areas_of(r["areas"])) or "watched",
            "; ".join(bits), " " + note if note else "", r["url"]))
    if len(scored) > limit:
        out.append("- _And {0} more in the store._".format(len(scored) - limit))
    return out + [""]
