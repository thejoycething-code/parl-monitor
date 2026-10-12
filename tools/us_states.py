#!/usr/bin/env python3
"""The fifty state legislatures, through Open States (phase 4).

    python3 tools/us_states.py                         # the weekly: every state, in rotation
    python3 tools/us_states.py --states tx,fl --dry-run   # the plan, store nothing
    python3 tools/us_states.py --states mn --since 2026-09-01
    python3 tools/us_states.py --full --states ny      # re-read the bulk files whole
    python3 tools/us_states.py --reclassify            # re-derive stored areas, offline
    python3 tools/us_states.py --db /tmp/uss.db --raw-dir /tmp/uss-raw

Decided by Christopher, 9 October 2026: all 50 state legislatures, after
Congress, through Open States. Measured the same day; docs/us-states-scope.md
has the numbers.

NO PAID TIER (Christopher, 9 October 2026: "upgrading tiers costs a huge
amount"; Open States quoted $2,900 a year for 1,000 requests a day). So the
bulk files carry the weekly read and the free key only fills the last day.

  * BULK, keyless, for EVERY read: Open States publishes one CSV zip per
    session (bills, abstracts, actions, sponsorships, sources, votes, every
    legislator's position). Its exporter runs nightly (about 23:00 UTC) and
    writes a NEW file, under a new random name, for every session with a
    bill changed that day (openstates.org bulk/management/commands/
    bulk_export.py; measured: 25 sessions stamped 8 October 23:02-23:21 UTC,
    and 43 to 48 of the year's sessions stamped the day of each archived
    in-session listing, 2022 and 2023). So a session whose stamp is newer
    than the one we read has changed, and one whose stamp is not has not.
    The URL and stamp come from the API's jurisdiction list (two keyed
    requests a run: the files cannot be listed without it). A first read
    takes the file whole; after that only bills with an action since the
    session's data_through (less OVERLAP_DAYS). Not archived (the URL and
    stamp, kept in uss_sessions, are the provenance).
  * THE FILE LAGS THE API BY ABOUT A DAY: actions scraped after the night's
    export are in the next file (Pennsylvania, 9 October: five resolutions
    acted on 8 October were in the API and not in the file of 8 October
    23:18). So data_through is the stamp's date less ZIP_LAG_DAYS.
  * API TOP-UP, keyed, for that last day only, and only for bills already on
    our ground that moved in the last LIVE_DAYS: /bills with session,
    action_since and up to 20 identifiers a request (the API's own cap),
    states in order of salience (live bills on our ground, then tier-1
    bills). Measured: 68 to 90 requests in a sitting week of spring 2026,
    a handful in recess. Never updated_since: Open States re-stamps
    'updated' whenever its scrapers re-run.
  * THE KEY'S DAY IS GUARDED BY A LEDGER in the store (uss_api_ledger, per
    UTC day): a run spends at most --api-budget (150) and never takes the
    day past --daily-cap (225 of the tier's 250), so a backup run the same
    day, or a hand probe, cannot overrun. A 429 for the day closes the
    ledger for the rest of it. Requests are spaced 6.5 s apart (10 a minute).
  * A session with no bulk file yet (a special session called this week) is
    read by the API for the last month, as before.

THE KEY is openstates_api_key in config/secrets.yaml or OPENSTATES_API_KEY
in the environment; it travels only as the X-API-KEY header, never in a
URL, a log, a gap row or the archive. No key: one [gap], and the step skips.

WHICH SESSIONS. Open States' session dates are not reliable (Mississippi's
2026 session is dated January 2025; Alaska's two-year 34th Legislature
ends in May 2025), so a session is current if it is the latest non-special
session, started in the last year, ends in the last month or later, starts
in the future (pre-filing: Virginia 2027), or its bulk file was regenerated
in the last 45 days.

WHAT IS STORED: bills on any area (taxonomy + config/watchlist-us-states.yaml,
by key), with actions, sponsors, votes and every position. Everything else
is counted in uss_sessions. See src/us_states_store.py.

ROTATION. States never read go first, then the longest unread. A run stops
at --budget-seconds and says so; the rest go first next week.

Exit status 1 when any gap was recorded. ONE WRITER AT A TIME on the store.
Separation guarantee: writes uss_* tables, gaps and its own source_runs row.
"""

from __future__ import annotations

import argparse
import ast
import csv
import datetime
import io
import json
import os
import sys
import time
import zipfile
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_states_store as uss  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "us-states"
HEARTBEAT = "US states"
API = "https://v3.openstates.org"
PEOPLE = "https://data.openstates.org/people/current/{0}.csv"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
INCLUDES = ("sponsorships", "abstracts", "actions", "votes", "sources", "other_titles")
PER_PAGE = 20                   # the API refuses more: "must be in [1, 20]"
API_SPACING_S = 6.5             # default tier: 10 a minute
API_BUDGET = 150                # one run's keyed requests (two of them the jurisdiction list)
DAILY_CAP = 225                 # all runs in a UTC day, of the tier's 250: room for a hand probe
TIER_DAY = 250                  # the default tier's day (measured from a 429 body)
MAX_PAGES = 10                  # a no-bulk session needing more API pages waits for its file
IDS_PER_REQUEST = 20            # the API refuses more ("up to 20 identifiers in one request")
OVERLAP_DAYS = 3                # a late-posted action is re-seen
ZIP_LAG_DAYS = 1                # the nightly file holds actions scraped before it, not that day's
LIVE_DAYS = 30                  # top-up only bills on our ground that moved this recently
STALE_DAYS = 3                  # a file this far behind (an export missed) is topped up first
MAX_LOOKBACK_DAYS = 30          # the API window for a session with no bulk file
BUDGET_S = 1500.0
CURRENT_DAYS = 365
ZIP_FRESH_DAYS = 45
BULK_TIMEOUT = 300
HIDDEN_AREAS = (11,)
SPECIAL_WORDS = ("special", "extraordinary", "fiscal", "called", "extra session")

csv.field_size_limit(1 << 30)


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def iso(value):
    return (value or "")[:10] or None


def openstates_key():
    from src import publish
    return publish.load_secrets().get("openstates_api_key") or None


# --- the API, spaced and counted ---------------------------------------------

class ApiSpent(Exception):
    """The run's request budget, or the key's day, is used up."""


def utc_day():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


class Ledger:
    """Keyed requests per UTC day, kept in the store (uss_api_ledger).

    Every runner fetches the store before it runs and publishes it after,
    so a GitHub backup on the day the Mini ran, or a second run by hand,
    sees what the day has already spent. Each request is written (and
    committed) BEFORE it is sent: a refused or crashed request still
    counted against Open States' day."""

    def __init__(self, conn, cap=DAILY_CAP, day=utc_day):
        self.conn, self.cap, self._day = conn, cap, day

    def spent(self):
        row = self.conn.execute("SELECT requests FROM uss_api_ledger WHERE day=?",
                                (self._day(),)).fetchone()
        return row[0] if row else 0

    def left(self):
        return max(0, self.cap - self.spent())

    def add(self, n=1):
        self.conn.execute(
            "INSERT INTO uss_api_ledger (day, requests, last_at) VALUES (?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET requests=requests+excluded.requests, "
            "last_at=excluded.last_at",
            (self._day(), n, datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="seconds")))
        self.conn.commit()

    def close_day(self):
        """Open States refused for the day: nothing more today, from any run."""
        spent = self.spent()
        if spent < TIER_DAY:
            self.add(TIER_DAY - spent)


class OpenStates:
    """Keyed GETs, spaced API_SPACING_S apart and counted against a run
    budget and, when given one, the day's ledger.

    A 429 for the minute waits the minute out once; a 429 for the day ends
    the API for this run and closes the ledger for the day."""

    def __init__(self, client, key, budget=API_BUDGET, spacing=API_SPACING_S,
                 sleep=time.sleep, clock=time.monotonic, archive=True, log=print, ledger=None):
        self.client, self.key, self.budget, self.spacing = client, key, budget, spacing
        self.sleep, self.clock, self.archive, self.log = sleep, clock, archive, log
        self.ledger = ledger
        self.used = 0
        self.refused = None
        self._last = None

    def remaining(self):
        if self.refused:
            return 0
        left = max(0, self.budget - self.used)
        return min(left, self.ledger.left()) if self.ledger else left

    def _wait(self):
        if self._last is not None:
            gap = self.spacing - (self.clock() - self._last)
            if gap > 0:
                self.sleep(gap)
        self._last = self.clock()

    def get(self, path, params, slug):
        for attempt in (1, 2):
            if not self.remaining():
                if self.refused:
                    raise ApiSpent(self.refused)
                if self.ledger and not self.ledger.left():
                    raise ApiSpent("the day's ledger is at its cap ({0} of {1} keyed requests "
                                   "today, UTC)".format(self.ledger.spent(), self.ledger.cap))
                raise ApiSpent("request budget of {0} spent".format(self.budget))
            self._wait()
            self.used += 1
            if self.ledger:
                self.ledger.add()
            url = API + path + ("?" + urlencode(params, doseq=True) if params else "")
            try:
                raw = self.client.get_bytes(url, FEED, slug, headers={"X-API-KEY": self.key})
            except FetchError as exc:
                code = getattr(exc.cause, "code", None)
                body = ""
                try:
                    body = exc.cause.read().decode("utf-8", "replace")[:200]
                except Exception:                            # noqa: BLE001
                    pass
                if code == 429 and "/min" in body and attempt == 1:
                    self.log("  open states: minute limit reached ({0}); waiting a minute".format(
                        body.strip()))
                    self.sleep(61)
                    continue
                if code == 429:
                    self.refused = "Open States refused for the rest of the day: {0}".format(
                        body.strip() or "429")
                    if self.ledger:
                        self.ledger.close_day()
                    raise ApiSpent(self.refused)
                if attempt == 1 and (code is None or code >= 500):
                    # A timeout or a server error (measured: a 'read operation
                    # timed out' on a Florida page, 9 October): once more.
                    self.log("  open states: {0}; trying once more".format(
                        code or str(exc.cause)[:60]))
                    continue
                raise

            if self.archive:
                # The body never carries the key (it travels as a header).
                self.client._archive(raw, FEED, slug)
            return json.loads(raw.decode("utf-8"))
        raise ApiSpent("minute limit hit twice")


# --- sessions -----------------------------------------------------------------

def jurisdictions(api):
    """Every state's sessions, from two keyed requests."""
    out = []
    page = 1
    while True:
        d = api.get("/jurisdictions", {"classification": "state",
                                       "include": "legislative_sessions",
                                       "per_page": 52, "page": page}, "jurisdictions-{0}".format(page))
        out += d.get("results") or []
        if page >= ((d.get("pagination") or {}).get("max_page") or 1):
            return out
        page += 1


def session_rows(jur):
    """[{state, session, name, classification, start_date, end_date, zip_url,
    zip_updated}] for one jurisdiction record."""
    st = uss.state_of(jur.get("id"))
    rows = []
    for s in jur.get("legislative_sessions") or []:
        dl = [d for d in (s.get("downloads") or []) if d.get("data_type") == "csv"]
        rows.append({"state": st, "session": s.get("identifier"), "name": s.get("name"),
                     "classification": s.get("classification") or "",
                     "start_date": s.get("start_date") or None, "end_date": s.get("end_date") or None,
                     "zip_url": dl[0]["url"] if dl else None,
                     "zip_updated": dl[0].get("updated_at") if dl else None})
    return rows


def is_special(s):
    return (s.get("classification") == "special"
            or any(w in (s.get("name") or "").lower() for w in SPECIAL_WORDS))


def current_sessions(sessions, today):
    """The sessions worth reading on `today` (see WHICH SESSIONS above)."""
    t = datetime.date.fromisoformat(today)
    year_ago = (t - datetime.timedelta(days=CURRENT_DAYS)).isoformat()
    month_ago = (t - datetime.timedelta(days=30)).isoformat()
    fresh = (t - datetime.timedelta(days=ZIP_FRESH_DAYS)).isoformat()
    started = [s for s in sessions if s.get("start_date") and s["start_date"] <= today]
    regular = sorted((s for s in started if not is_special(s)), key=lambda s: s["start_date"])
    keep = {regular[-1]["session"]} if regular else set()
    for s in sessions:
        start, end = s.get("start_date") or "", s.get("end_date") or ""
        if ((start and start >= year_ago and start <= today) or (end and end >= month_ago)
                or (start > today and s.get("zip_url"))
                or (iso(s.get("zip_updated")) or "") >= fresh):
            keep.add(s["session"])
    return [s for s in sessions if s["session"] in keep]


def store_session_meta(conn, s, today):
    conn.execute(
        "INSERT INTO uss_sessions (state, session, name, classification, start_date, end_date, "
        "zip_url, zip_updated, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(state, session) DO UPDATE SET name=excluded.name, "
        "classification=excluded.classification, start_date=excluded.start_date, "
        "end_date=excluded.end_date, zip_url=excluded.zip_url, zip_updated=excluded.zip_updated, "
        "last_seen=excluded.last_seen",
        (s["state"], s["session"], s["name"], s["classification"], s["start_date"],
         s["end_date"], s["zip_url"], s["zip_updated"], today, today))


def read_state(conn, state, session):
    conn.row_factory = None
    row = conn.execute("SELECT read_zip_updated, data_through, read_at FROM uss_sessions "
                       "WHERE state=? AND session=?", (state, session)).fetchone()
    return row or (None, None, None)


# --- one bill, from either route ----------------------------------------------

def best_source(urls, identifier):
    """The state's own bill page, not a data endpoint, where one is listed."""
    if not urls:
        return None
    digits = "".join(ch for ch in identifier or "" if ch.isdigit())

    def rank(u):
        low = u.lower()
        data = any(w in low for w in ("api.", "/api/", "load", ".json", ".xml", "rss", "rollcall"))
        return (data, not (digits and digits in u), urls.index(u))
    return sorted(urls, key=rank)[0]


def bill_from_api(b):
    st = uss.state_of((b.get("jurisdiction") or {}).get("id"))
    actions = [{"date": iso(a.get("date")), "description": a.get("description"),
                "classification": a.get("classification") or [],
                "chamber": (a.get("organization") or {}).get("classification"),
                "ord": int(a.get("order") or i)} for i, a in enumerate(b.get("actions") or [])]
    votes = []
    for v in b.get("votes") or []:
        counts = {c.get("option"): int(c.get("value") or 0) for c in v.get("counts") or []}
        votes.append({
            "id": v.get("id"), "date": iso(v.get("start_date")), "motion": v.get("motion_text"),
            "motion_classification": v.get("motion_classification") or [],
            "result": v.get("result"),
            "chamber": (v.get("organization") or {}).get("classification"),
            "counts": counts,
            "url": ((v.get("sources") or [{}])[0] or {}).get("url"),
            "people": [{"name": p.get("voter_name"),
                        "person_id": (p.get("voter") or {}).get("id"),
                        "option": p.get("option")} for p in v.get("votes") or []]})
    return {
        "id": b.get("id"), "state": st, "session": b.get("session"),
        "identifier": b.get("identifier"), "title": b.get("title"),
        "classification": b.get("classification") or [], "subjects": b.get("subject") or [],
        "abstracts": [a.get("abstract") for a in b.get("abstracts") or [] if a.get("abstract")],
        "other_titles": [t.get("title") for t in b.get("other_titles") or [] if t.get("title")],
        "chamber": (b.get("from_organization") or {}).get("classification"),
        "url": best_source([s.get("url") for s in b.get("sources") or [] if s.get("url")],
                           b.get("identifier")),
        "actions": actions,
        "sponsors": [{"name": s.get("name"), "person_id": (s.get("person") or {}).get("id"),
                      "primary": bool(s.get("primary")), "classification": s.get("classification")}
                     for s in b.get("sponsorships") or []],
        "votes": votes,
    }


def _rows(z, kind):
    names = [n for n in z.namelist() if n.endswith("_{0}.csv".format(kind))]
    if not names:
        return
    with z.open(names[0]) as fh:
        yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"))


def _list(text):
    try:
        v = ast.literal_eval(text or "[]")
        return list(v) if isinstance(v, (list, tuple)) else []
    except (ValueError, SyntaxError):
        return []


def bills_from_bulk(raw, keep, since=None):
    """(bills read, [bill dicts kept]) from one session's CSV zip.

    keep(bill) -> bool decides, on the bill's text alone, what is kept; only
    kept bills have their sponsors, sources and votes read. With `since`,
    only bills with an action on or after it are considered at all."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    orgs = {r["id"]: r["classification"] for r in _rows(z, "organizations")}
    bills = {r["id"]: r for r in _rows(z, "bills")}
    actions = {}
    for r in _rows(z, "bill_actions"):
        actions.setdefault(r["bill_id"], []).append(
            {"date": iso(r["date"]), "description": r["description"],
             "classification": _list(r["classification"]),
             "chamber": orgs.get(r["organization_id"]), "ord": int(r["order"] or 0)})
    abstracts = {}
    for r in _rows(z, "bill_abstracts"):
        if r["abstract"]:
            abstracts.setdefault(r["bill_id"], []).append(r["abstract"])
    titles = {}
    for r in _rows(z, "bill_titles"):
        if r.get("title"):
            titles.setdefault(r["bill_id"], []).append(r["title"])
    kept = {}
    for bid, r in bills.items():
        acts = actions.get(bid) or []
        if since and not any((a["date"] or "") >= since for a in acts):
            continue
        b = {"id": bid, "state": None, "session": r["session_identifier"],
             "identifier": r["identifier"], "title": r["title"],
             "classification": _list(r["classification"]), "subjects": _list(r["subject"]),
             "abstracts": abstracts.get(bid, []), "other_titles": titles.get(bid, []),
             "chamber": r.get("organization_classification") or None, "url": None,
             "actions": acts, "sponsors": [], "votes": []}
        if keep(b):
            kept[bid] = b
    sources = {}
    for r in _rows(z, "bill_sources"):
        if r["bill_id"] in kept and r["url"]:
            sources.setdefault(r["bill_id"], []).append(r["url"])
    for bid, urls in sources.items():
        kept[bid]["url"] = best_source(urls, kept[bid]["identifier"])
    for r in _rows(z, "bill_sponsorships"):
        if r["bill_id"] in kept:
            kept[r["bill_id"]]["sponsors"].append(
                {"name": r["name"], "person_id": r["person_id"] or None,
                 "primary": r["primary"] == "True", "classification": r["classification"]})
    votes = {}
    for r in _rows(z, "votes"):
        if r["bill_id"] in kept:
            votes[r["id"]] = {"id": r["id"], "bill_id": r["bill_id"], "date": iso(r["start_date"]),
                              "motion": r["motion_text"],
                              "motion_classification": _list(r["motion_classification"]),
                              "result": r["result"], "chamber": orgs.get(r["organization_id"]),
                              "counts": {}, "url": None, "people": []}
    for r in _rows(z, "vote_counts"):
        if r["vote_event_id"] in votes:
            votes[r["vote_event_id"]]["counts"][r["option"]] = int(r["value"] or 0)
    for r in _rows(z, "vote_sources"):
        v = votes.get(r["vote_event_id"])
        if v and not v["url"]:
            v["url"] = r["url"]
    for r in _rows(z, "vote_people"):
        v = votes.get(r["vote_event_id"])
        if v:
            v["people"].append({"name": r["voter_name"], "person_id": r["voter_id"] or None,
                                "option": r["option"]})
    for v in votes.values():
        kept[v["bill_id"]]["votes"].append(v)
    return len(bills), list(kept.values())


# --- classify and store ---------------------------------------------------------

def classify(tax, wl, b):
    """Title first (filter_item's convention), then other titles, subject
    terms and abstracts; then the watchlist, by key."""
    res = filt.filter_item(tax, wl, b["title"] or "", *b["other_titles"],
                           " ; ".join(b["subjects"]), *b["abstracts"], title=b["title"] or "")
    return uss.add_watch_areas(res, uss.bill_key(b["state"], b["session"], b["identifier"]))


def stage_dates(actions):
    """(introduced, latest action text, latest date, passed lower, passed upper,
    law, veto) from a bill's actions. A unicameral passage (Nebraska,
    'legislature') counts as the lower date."""
    acts = sorted((a for a in actions if a.get("date")), key=lambda a: (a["date"], a["ord"]))

    def first(test):
        hits = [a["date"] for a in acts if test(a)]
        return hits[0] if hits else None
    passed = lambda ch: (lambda a: "passage" in a["classification"]  # noqa: E731
                         and a.get("chamber") in ch)
    return (acts[0]["date"] if acts else None,
            acts[-1]["description"] if acts else None,
            acts[-1]["date"] if acts else None,
            first(passed(("lower", "legislature"))),
            first(passed(("upper",))),
            first(lambda a: "became-law" in a["classification"]
                  or "executive-signature" in a["classification"]),
            first(lambda a: "executive-veto" in a["classification"]))


def store_bill(conn, b, res, today):
    key = uss.bill_key(b["state"], b["session"], b["identifier"])
    intro, latest, latest_at, lower, upper, law, veto = stage_dates(b["actions"])
    primary = [s["name"] for s in b["sponsors"] if s["primary"]]
    conn.execute(
        "INSERT INTO uss_bills (bill_id, bill_key, state, session, identifier, title, "
        "classification, subjects, abstract, chamber, url, introduced_at, latest_action, "
        "latest_action_at, passed_lower_at, passed_upper_at, law_at, vetoed_at, sponsor, "
        "sponsors, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_id) DO UPDATE SET bill_key=excluded.bill_key, title=excluded.title, "
        "classification=excluded.classification, subjects=excluded.subjects, "
        "abstract=excluded.abstract, chamber=excluded.chamber, "
        "url=COALESCE(excluded.url, uss_bills.url), introduced_at=excluded.introduced_at, "
        "latest_action=excluded.latest_action, latest_action_at=excluded.latest_action_at, "
        "passed_lower_at=excluded.passed_lower_at, passed_upper_at=excluded.passed_upper_at, "
        "law_at=excluded.law_at, vetoed_at=excluded.vetoed_at, sponsor=excluded.sponsor, "
        "sponsors=excluded.sponsors, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (b["id"], key, b["state"], b["session"], b["identifier"], b["title"],
         uss.dumps(b["classification"]), uss.dumps(b["subjects"]),
         " | ".join(b["abstracts"]) or None, b["chamber"], b["url"], intro, latest, latest_at,
         lower, upper, law, veto, primary[0] if primary else None, len(b["sponsors"]),
         uss.dumps(res.issue_areas),
         uss.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier,
         today, today))
    conn.execute("DELETE FROM uss_actions WHERE bill_id=?", (b["id"],))
    seen = set()
    for a in b["actions"]:
        ordn = a["ord"]
        while ordn in seen:         # a source that repeats an order number
            ordn += 10000
        seen.add(ordn)
        conn.execute("INSERT INTO uss_actions (bill_id, ord, date, description, classification, "
                     "chamber) VALUES (?,?,?,?,?,?)",
                     (b["id"], ordn, a["date"], a["description"], uss.dumps(a["classification"]),
                      a["chamber"]))
    conn.execute("DELETE FROM uss_sponsors WHERE bill_id=?", (b["id"],))
    for i, s in enumerate(b["sponsors"]):
        conn.execute("INSERT INTO uss_sponsors (bill_id, seq, name, person_id, is_primary, "
                     "classification) VALUES (?,?,?,?,?,?)",
                     (b["id"], i, s["name"], s["person_id"], int(bool(s["primary"])),
                      s["classification"]))
    for v in b["votes"]:
        c = v["counts"]
        conn.execute(
            "INSERT INTO uss_votes (vote_id, bill_id, state, session, date, motion, "
            "motion_classification, result, chamber, yes, no, other, url, positions, "
            "positions_ok, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(vote_id) DO UPDATE SET "
            "date=excluded.date, motion=excluded.motion, result=excluded.result, "
            "yes=excluded.yes, no=excluded.no, other=excluded.other, "
            "url=COALESCE(excluded.url, uss_votes.url), positions=excluded.positions, "
            "positions_ok=excluded.positions_ok, last_seen=excluded.last_seen",
            (v["id"], b["id"], b["state"], b["session"], v["date"], v["motion"],
             uss.dumps(v["motion_classification"]), v["result"], v["chamber"],
             c.get("yes", 0), c.get("no", 0),
             sum(n for o, n in c.items() if o not in ("yes", "no")), v["url"],
             len(v["people"]), int(len(v["people"]) == sum(c.values())), today, today))
        conn.execute("DELETE FROM uss_vote_people WHERE vote_id=?", (v["id"],))
        for i, p in enumerate(v["people"]):
            conn.execute("INSERT INTO uss_vote_people (vote_id, seq, voter_name, person_id, option) "
                         "VALUES (?,?,?,?,?)", (v["id"], i, p["name"], p["person_id"], p["option"]))
    return key


class Tally:
    def __init__(self):
        self.read = self.ours = self.stored = self.votes = self.positions = 0

    def add(self, b, res):
        self.stored += 1
        self.ours += on_our_ground(res.issue_areas)
        self.votes += len(b["votes"])
        self.positions += sum(len(v["people"]) for v in b["votes"])


def keep_and_store(conn, tax, wl, bills, today, tally, known):
    """Store what is on any area, and any bill already stored (so a bill the
    net no longer catches has its areas emptied, not left stale)."""
    for b in bills:
        res = classify(tax, wl, b)
        if res.issue_areas or b["id"] in known:
            store_bill(conn, b, res, today)
            tally.add(b, res)


def known_ids(conn, state):
    conn.row_factory = None
    return {r[0] for r in conn.execute("SELECT bill_id FROM uss_bills WHERE state=?", (state,))}


# --- the two routes --------------------------------------------------------------

def zip_through(stamp):
    """How far a bulk file is good for: the day before its stamp. The
    nightly export holds what the scrapers had by then, and the day's own
    actions are mostly scraped after it (measured, Pennsylvania 8 October)."""
    day = iso(stamp)
    if not day:
        return None
    return (datetime.date.fromisoformat(day) - datetime.timedelta(days=ZIP_LAG_DAYS)).isoformat()


def bulk_read(conn, client, tax, wl, s, today, tally, since=None, log=print):
    """Read one session's bulk file: whole (first read, --full) or only bills
    with an action since `since`. Returns True when read."""
    st = s["state"]
    try:
        raw = client.get_bytes(s["zip_url"], FEED, "bulk-{0}-{1}".format(st, s["session"]),
                               timeout=BULK_TIMEOUT, archive=False)
    except FetchError as exc:
        _gap(conn, today, "{0} {1}: bulk file refused ({2})".format(
            st.upper(), s["session"], getattr(exc.cause, "code", exc.cause)))
        log("  [gap] {0} {1}: bulk file refused".format(st.upper(), s["session"]))
        return False
    known = known_ids(conn, st)

    def keep(b):
        b["state"] = st
        b["_res"] = classify(tax, wl, b)
        return bool(b["_res"].issue_areas) or b["id"] in known
    try:
        n, bills = bills_from_bulk(raw, keep, since=since)
    except (zipfile.BadZipFile, KeyError, csv.Error) as exc:
        _gap(conn, today, "{0} {1}: bulk file unreadable ({2})".format(st.upper(), s["session"], exc))
        log("  [gap] {0} {1}: bulk file unreadable: {2}".format(st.upper(), s["session"], exc))
        return False
    before = tally.ours
    for b in bills:
        store_bill(conn, b, b["_res"], today)
        tally.add(b, b["_res"])
    tally.read += n
    stamp = s.get("zip_updated")
    if since:
        conn.execute("UPDATE uss_sessions SET read_zip_updated=?, read_via='bulk', "
                     "data_through=?, read_at=? WHERE state=? AND session=?",
                     (stamp, zip_through(stamp), today, st, s["session"]))
    else:
        conn.execute("UPDATE uss_sessions SET read_zip_updated=?, read_via='bulk', "
                     "data_through=?, bills_read=?, bills_ours=?, read_at=? "
                     "WHERE state=? AND session=?",
                     (stamp, zip_through(stamp), n, tally.ours - before, today, st, s["session"]))
    conn.commit()
    log("  {0} {1}: bulk ({2}), {3} bill(s) {4}, {5} on our ground".format(
        st.upper(), s["session"], iso(stamp), n, "with an action since " + since if since else "read",
        tally.ours - before))
    return True


def api_read(conn, api, tax, wl, st, since, today, tally, max_pages=MAX_PAGES, log=print):
    """Every bill of the state with an action since `since`, all sessions.
    Returns 'done', or 'too-big' / 'spent' / 'failed' for the caller to fall back."""
    params = {"jurisdiction": st, "action_since": since, "include": list(INCLUDES),
              "per_page": PER_PAGE, "sort": "first_action_asc"}
    try:
        first = api.get("/bills", dict(params, page=1), "bills-{0}-{1}-p1".format(st, since))
    except ApiSpent:
        return "spent"
    except FetchError as exc:
        _gap(conn, today, "{0}: API refused ({1}); the bulk file stands in".format(
            st.upper(), getattr(exc.cause, "code", None) or str(exc.cause)[:60]))
        log("  [gap] {0}: API refused".format(st.upper()))
        return "failed"
    pages = (first.get("pagination") or {}).get("max_page") or 1
    total = (first.get("pagination") or {}).get("total_items") or 0
    if pages > max_pages or pages - 1 > api.remaining():
        log("  {0}: {1} bill(s) moved since {2}, {3} page(s): beyond the API budget, "
            "reading the bulk files instead".format(st.upper(), total, since, pages))
        return "too-big"
    results = list(first.get("results") or [])
    for page in range(2, pages + 1):
        try:
            d = api.get("/bills", dict(params, page=page), "bills-{0}-{1}-p{2}".format(st, since, page))
        except ApiSpent:
            return "spent"
        except FetchError as exc:
            _gap(conn, today, "{0}: API page {1} refused ({2}); the bulk file stands in".format(
                st.upper(), page, getattr(exc.cause, "code", None) or str(exc.cause)[:60]))
            log("  [gap] {0}: API page {1} refused".format(st.upper(), page))
            return "failed"
        results += d.get("results") or []
    known = known_ids(conn, st)
    before = tally.ours
    keep_and_store(conn, tax, wl, [bill_from_api(b) for b in results], today, tally, known)
    tally.read += len(results)
    conn.commit()
    log("  {0}: API, {1} bill(s) with an action since {2} ({3} request(s)), {4} on our "
        "ground".format(st.upper(), len(results), since, pages, tally.ours - before))
    return "done"


def pull_people(conn, client, st, today, log=print):
    try:
        text = client.get_text(PEOPLE.format(st), FEED, "people-{0}".format(st))
    except FetchError as exc:
        _gap(conn, today, "{0}: people file refused ({1})".format(
            st.upper(), getattr(exc.cause, "code", exc.cause)))
        return 0
    n = 0
    for r in csv.DictReader(io.StringIO(text)):
        if not r.get("id"):
            continue
        conn.execute(
            "INSERT INTO uss_people (person_id, state, name, party, chamber, district, given_name, "
            "family_name, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(person_id) DO UPDATE SET name=excluded.name, party=excluded.party, "
            "chamber=excluded.chamber, district=excluded.district, given_name=excluded.given_name, "
            "family_name=excluded.family_name, last_seen=excluded.last_seen",
            (r["id"], st, r.get("name"), r.get("current_party"), r.get("current_chamber"),
             r.get("current_district"), r.get("given_name"), r.get("family_name"), today, today))
        n += 1
    return n


def bulk_window(through):
    """Bills with an action since this date are re-read from a changed file."""
    if not through:
        return None
    return (datetime.date.fromisoformat(through)
            - datetime.timedelta(days=OVERLAP_DAYS)).isoformat()


def collect_state(conn, client, tax, wl, st, sessions, today, args, tally, log=print):
    """One state's bulk files: a session never read is read whole; one whose
    file has a newer stamp than the one read, only for bills with an action
    since its data_through (less the overlap); one whose file has not
    changed is not downloaded at all (Open States writes a new file whenever
    a bill of the session changes). Returns the current sessions with no
    bulk file and never read, for the API."""
    cur = current_sessions(sessions, today)
    for s in cur:
        if not s.get("zip_url"):
            continue
        read_stamp, through, read_at = read_state(conn, st, s["session"])
        if args.full or not read_at:
            bulk_read(conn, client, tax, wl, s, today, tally, log=log)
        elif args.since or (s.get("zip_updated") or "") > (read_stamp or ""):
            bulk_read(conn, client, tax, wl, s, today, tally,
                      since=args.since or bulk_window(through) or today, log=log)
    return [s for s in cur if not s.get("zip_url") and not read_state(conn, st, s["session"])[2]]


def read_new_sessions(conn, api, tax, wl, st, sessions, today, args, tally, log=print):
    """A current session with no bulk file yet (a special session called this
    week): the API, for the last month, all of the state's sessions."""
    since = args.since or (datetime.date.fromisoformat(today)
                           - datetime.timedelta(days=MAX_LOOKBACK_DAYS)).isoformat()
    if api_read(conn, api, tax, wl, st, since, today, tally, max_pages=args.max_pages,
                log=log) == "done":
        for s in sessions:
            conn.execute("UPDATE uss_sessions SET read_via='api', data_through=?, read_at=? "
                         "WHERE state=? AND session=?", (today, today, st, s["session"]))
        conn.commit()
    else:
        log("  {0}: {1} has no bulk file yet and the API could not read it; next week".format(
            st.upper(), ", ".join(s["session"] for s in sessions)))


# --- the top-up: the last day, by API, bills on our ground only --------------------

def live_bills(conn, st, session, today, live_days=LIVE_DAYS):
    """Identifiers of the session's bills on our ground that moved in the
    last live_days, most recent first."""
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=live_days)).isoformat()
    conn.row_factory = None
    rows = conn.execute("SELECT identifier, areas FROM uss_bills WHERE state=? AND session=? "
                        "AND latest_action_at >= ? ORDER BY latest_action_at DESC, "
                        "COALESCE(tier, 9), identifier", (st, session, cutoff)).fetchall()
    return [ident for ident, areas in rows if on_our_ground(json.loads(areas or "[]"))]


def salience(conn, st, today, live_days=LIVE_DAYS):
    """(bills on our ground that moved lately, tier-1 bills on our ground)."""
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=live_days)).isoformat()
    conn.row_factory = None
    live = tier1 = 0
    for areas, at, tier in conn.execute(
            "SELECT areas, latest_action_at, tier FROM uss_bills WHERE state=?", (st,)):
        if on_our_ground(json.loads(areas or "[]")):
            live += (at or "") >= cutoff
            tier1 += tier == 1
    return live, tier1


def topup_plan(conn, by_state, states, today):
    """[(state, session, since, [identifiers])], states in order of
    salience: a file more than STALE_DAYS behind first (an export missed),
    then live bills on our ground, then tier-1 bills. Only sessions read
    from a bulk file with days still to cover, and only live bills."""
    stale_day = (datetime.date.fromisoformat(today)
                 - datetime.timedelta(days=STALE_DAYS)).isoformat()
    per_state = []
    for st in states:
        items = []
        for s in current_sessions(by_state.get(st, []), today):
            _, through, read_at = read_state(conn, st, s["session"])
            if not read_at or not through or through >= today:
                continue
            ids = live_bills(conn, st, s["session"], today)
            if ids:
                items.append((st, s["session"], through, ids))
        if items:
            stale = min(i[2] for i in items) < stale_day
            live, tier1 = salience(conn, st, today)
            per_state.append(((not stale, -live, -tier1, st), items))
    return [i for _, items in sorted(per_state) for i in items]


def topup(conn, api, tax, wl, plan, today, tally, log=print):
    """Read the plan's bills that moved since their file's data_through, 20
    identifiers a request. Returns (requests, bills refreshed, states done,
    states left for want of budget)."""
    used0 = api.used
    refreshed = 0
    done, left = [], []
    for st, session, since, ids in plan:
        if not api.remaining():
            left.append(st)
            continue
        got = []
        complete = True
        for i in range(0, len(ids), IDS_PER_REQUEST):
            batch = ids[i:i + IDS_PER_REQUEST]
            params = {"jurisdiction": st, "session": session, "action_since": since,
                      "identifier": batch, "include": list(INCLUDES), "per_page": PER_PAGE}
            try:
                d = api.get("/bills", params, "topup-{0}-{1}-{2}-{3}".format(
                    st, session, since, i // IDS_PER_REQUEST + 1))
            except ApiSpent:
                complete = False
                break
            except FetchError as exc:
                _gap(conn, today, "{0} {1}: top-up refused ({2}); the next bulk file "
                     "stands in".format(st.upper(), session,
                                        getattr(exc.cause, "code", None) or str(exc.cause)[:60]))
                complete = False
                break
            got += d.get("results") or []
        known = known_ids(conn, st)
        keep_and_store(conn, tax, wl, [bill_from_api(b) for b in got], today, tally, known)
        conn.commit()
        refreshed += len(got)
        (done if complete else left).append(st)
        log("  {0} {1}: top-up, {2} of {3} live bill(s) on our ground moved since {4}{5}".format(
            st.upper(), session, len(got), len(ids), since, "" if complete else " (stopped short)"))
    return api.used - used0, refreshed, sorted(set(done)), sorted(set(left) - set(done))


def order_states(conn, states):
    """Never read first, then the longest since a read: the rotation."""
    conn.row_factory = None
    last = dict(conn.execute("SELECT state, MAX(read_at) FROM uss_sessions GROUP BY state"))
    return sorted(states, key=lambda st: (last.get(st) is not None, last.get(st) or "", st))


# --- offline -------------------------------------------------------------------------

def empty_watchlist():
    """The states watchlist is applied by KEY (us_states_store.add_watch_areas)."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def reclassify(conn, tax=None, log=print):
    """Re-derive stored bills' areas, offline. It can only NARROW: a bill
    the old net missed was never stored (re-read with --full to widen)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    conn.row_factory = None
    changed = 0
    for (bid, st, session, ident, title, subjects, abstract, areas) in conn.execute(
            "SELECT bill_id, state, session, identifier, title, subjects, abstract, areas "
            "FROM uss_bills").fetchall():
        b = {"state": st, "session": session, "identifier": ident, "title": title,
             "other_titles": [], "subjects": json.loads(subjects or "[]"),
             "abstracts": [a for a in (abstract or "").split(" | ") if a]}
        res = classify(tax, wl, b)
        new = uss.dumps(res.issue_areas)
        changed += new != (areas or "[]")
        conn.execute("UPDATE uss_bills SET areas=?, matched_terms=?, tier=? WHERE bill_id=?",
                     (new, uss.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, bid))
    conn.commit()
    log("us-states: reclassified; {0} bill(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    conn.row_factory = None
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = sum(on_our_ground(json.loads(a or "[]"))
               for (a,) in conn.execute("SELECT areas FROM uss_bills"))
    log("  store: {0} state bill(s) kept, {1} on our ground, in {2} state(s); {3} vote(s) "
        "({8} whose positions do not match the tally), {4} position(s) ({5} unlinked to a "
        "person); {6} legislator(s); {7} session(s) read".format(
            n("SELECT COUNT(*) FROM uss_bills"), ours,
            n("SELECT COUNT(DISTINCT state) FROM uss_bills"),
            n("SELECT COUNT(*) FROM uss_votes"), n("SELECT COUNT(*) FROM uss_vote_people"),
            n("SELECT COUNT(*) FROM uss_vote_people WHERE person_id IS NULL"),
            n("SELECT COUNT(*) FROM uss_people"),
            n("SELECT COUNT(*) FROM uss_sessions WHERE read_at IS NOT NULL"),
            n("SELECT COUNT(*) FROM uss_votes WHERE positions_ok = 0")))


def stamp_heartbeat(conn, today):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/us_states.py"))
    conn.commit()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--states", default="",
                    help="postal codes, comma-separated (default: all fifty)")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--since", help="ISO date: re-read every current bulk file for bills with an "
                                    "action since then (default: each session's data_through)")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--api-budget", type=int, default=API_BUDGET,
                    help="keyed requests this run may spend, the jurisdiction list included")
    ap.add_argument("--daily-cap", type=int, default=DAILY_CAP,
                    help="keyed requests all runs may spend in a UTC day (the tier allows 250)")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES,
                    help="API pages a session with no bulk file may take")
    ap.add_argument("--no-topup", action="store_true",
                    help="bulk files only: two keyed requests (the jurisdiction list)")
    ap.add_argument("--full", action="store_true",
                    help="re-read every current session's bulk file whole (after a taxonomy "
                         "change that widens the net)")
    ap.add_argument("--no-people", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive stored bills' areas, offline")
    ap.add_argument("--dry-run", action="store_true",
                    help="list the plan (two keyed requests, in the ledger), store nothing else")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    states = [s.strip().lower() for s in args.states.split(",") if s.strip()] or sorted(uss.STATES)
    bad = [s for s in states if s not in uss.STATES]
    if bad:
        ap.error("not a state: {0}".format(", ".join(bad)))
    if args.reclassify:
        conn = db.init_db(db.connect(args.db))
        reclassify(conn)
        summary(conn)
        return 0
    key = openstates_key()
    if not key:
        print("  [gap] us-states: no openstates_api_key (config/secrets.yaml or "
              "OPENSTATES_API_KEY); the fifty states were not read")
        if not args.dry_run:
            conn = db.init_db(db.connect(args.db))
            _gap(conn, today, "no openstates_api_key: the state legislatures were not read")
            conn.commit()
        return 0
    conn = db.init_db(db.connect(args.db))
    ledger = Ledger(conn, cap=args.daily_cap)
    client = HttpClient(raw_dir=args.raw_dir)
    api_client = HttpClient(raw_dir=args.raw_dir, max_retries=0)
    api = OpenStates(api_client, key, budget=args.api_budget, archive=not args.dry_run,
                     ledger=ledger)
    print("us-states: {0} keyed request(s) already spent today (UTC); this run may spend {1}".format(
        ledger.spent(), api.remaining()))
    try:
        jurs = jurisdictions(api)
    except (FetchError, ApiSpent) as exc:
        print("  [gap] us-states: the jurisdiction list was refused ({0})".format(
            getattr(getattr(exc, "cause", None), "code", exc)))
        if not args.dry_run:
            _gap(conn, today, "Open States jurisdiction list refused; no state read")
            conn.commit()
        return 1
    by_state = {}
    for j in jurs:
        st = uss.state_of(j.get("id"))
        if st in uss.STATES:
            by_state[st] = session_rows(j)
    if args.dry_run:
        for st in states:
            cur = current_sessions(by_state.get(st, []), today)
            parts = []
            for s in cur:
                stamp, through, read_at = read_state(conn, st, s["session"])
                state = ("unread" if not read_at else
                         "changed since read" if (s["zip_updated"] or "") > (stamp or "")
                         else "unchanged")
                parts.append("{0} ({1}, {2})".format(
                    s["session"], "bulk " + iso(s["zip_updated"]) if s["zip_url"]
                    else "no bulk file", state))
            print("  {0}: {1}".format(st.upper(), "; ".join(parts) or "no current session"))
        plan = topup_plan(conn, by_state, [s for s in states if s in by_state], today)
        need = sum(-(-len(ids) // IDS_PER_REQUEST) for _, _, _, ids in plan)
        print("us-states: dry run, {0} keyed request(s) spent; a top-up now would take {1} "
              "request(s) for {2} live bill(s) in {3} state(s); nothing stored".format(
                  api.used, need, sum(len(i[3]) for i in plan), len({i[0] for i in plan})))
        return 0
    for st in by_state:
        for s in by_state[st]:
            store_session_meta(conn, s, today)
    conn.commit()
    missing = [st for st in states if st not in by_state]
    for st in missing:
        _gap(conn, today, "{0}: not in Open States' jurisdiction list".format(st.upper()))
    tax = filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    tally = Tally()
    done = 0
    people = 0
    no_bulk = {}
    present = [s for s in states if s in by_state]
    # 1. The bulk files, every state, in rotation.
    for st in order_states(conn, present):
        if budget.exhausted():
            print(budget.disclose("state(s)", done))
            break
        if not args.no_people:
            people += pull_people(conn, client, st, today)
        new = collect_state(conn, client, tax, wl, st, by_state[st], today, args, tally)
        if new:
            no_bulk[st] = new
        done += 1
    conn.commit()
    # 2. Sessions with no bulk file yet, by API (rare: a special session).
    for st, sessions in no_bulk.items():
        if args.full or budget.exhausted() or not api.remaining():
            break
        read_new_sessions(conn, api, tax, wl, st, sessions, today, args, tally)
    # 3. The top-up: the last day, by API, live bills on our ground only.
    if not (args.no_topup or args.full):
        plan = topup_plan(conn, by_state, present, today)
        if budget.exhausted():
            print("  us-states: no time left for the top-up; the bulk files stand "
                  "({0} state(s) would have been topped up)".format(len({p[0] for p in plan})))
        elif plan:
            before = api.used
            reached = set()
            for item in plan:
                if budget.exhausted() or not api.remaining():
                    break
                reached.add(item[0])
                topup(conn, api, tax, wl, [item], today, tally)
            skipped = sorted({p[0] for p in plan} - reached)
            print("  us-states: top-up spent {0} keyed request(s) over {1} state(s){2}".format(
                api.used - before, len(reached),
                "; not reached (time or request budget): " + ", ".join(
                    s.upper() for s in skipped) if skipped else ""))
    if api.refused:
        _gap(conn, today, api.refused)
        print("  [gap] " + api.refused)
    gaps = conn.execute("SELECT COUNT(*) FROM gaps WHERE edition=? AND feed=?",
                        (today, FEED)).fetchone()[0]
    stamp_heartbeat(conn, today)
    print("us-states: {0} of {1} state(s) read; {2} bill(s) read, {3} kept, {4} on our ground; "
          "{5} vote(s) with {6} position(s); {7} legislator(s); {8} keyed request(s) this run, "
          "{9} today (cap {10}); {11:.0f}s".format(
              done, len(states), tally.read, tally.stored, tally.ours, tally.votes,
              tally.positions, people, api.used, ledger.spent(), ledger.cap, budget.spent()))
    summary(conn)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
