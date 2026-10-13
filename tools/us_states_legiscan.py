#!/usr/bin/env python3
"""The fifty state legislatures, same day, from LegiScan's FREE public API
(13 October 2026). Optional: it runs only when LEGISCAN_API_KEY is set.

    LEGISCAN_API_KEY=... python3 tools/us_states_legiscan.py --db /tmp/uss.db
    python3 tools/us_states_legiscan.py --states tx,fl --dry-run

Christopher, 13 October 2026: "We can't pay for Open States access so may
need to explore alternatives whilst keeping the current tier we have." The
Open States route (tools/us_states.py) is unchanged; this adds the last day
it cannot see on its free key, for every state at once.

THE KEY. A free "public service" key, from a free OneVote account at
https://legiscan.com/legiscan (Christopher creates it himself; we never sign
up for anything). It is read from LEGISCAN_API_KEY (or legiscan_api_key in
config/secrets.yaml); absent, the step prints one line and exits 0, writing
nothing. LegiScan takes the key ONLY in the query string
(https://api.legiscan.com/?key=...&op=...), so a keyed URL is never logged,
archived, put in a gap row or a FetchError message: requests go through
HttpClient's keyed path (not archived), refusals are re-raised with the key
cut out, and the JSON bodies (which never carry the key) are archived here.

THE ALLOWANCE. The API manual (revision 20250317, api.legiscan.com) says
"Public service keys have a monthly limit of 30,000 queries"; LegiScan's
features page, read through a search engine on 13 October 2026, says 10,000.
We plan for the lower: at most --monthly-cap (9,000) a calendar month across
all runs (uss_source_ledger), --run-budget (1,500) a run. A weekly run is
about 1 + one master list per current session (about 60 to 70) + one getBill
per changed bill on our ground (tens in recess, a few hundred in a sitting
week) + roll calls for the six states where Open States has no positions.

THE LICENCE. LegiScan's API and dataset data are CC BY 4.0 (its API page and
home page): the edition names LegiScan wherever a bill it gave is shown.

WHAT IT DOES, per run:
  1. getSessionList (one query, every state): the sessions not adjourned
     sine die, or ending this year or later.
  2. getMasterList per session (one query each): every bill with its title,
     description, last action and change_hash.
  3. A bill is a candidate when it is stored already (Open States' row or an
     earlier LegiScan one) or its title and description match an area (the
     shared taxonomy, the watchlist by key), its change_hash differs from
     the one last read, and it moved in the last --live-days. Candidates are
     fetched with getBill in order: watched, tier 1, then latest action.
  4. merge_foreign (tools/us_states.py) adds what Open States lacks to its
     row, or stores a new row 'legiscan:<bill_id>' that Open States
     supersedes when its own file catches up.
  5. Roll calls (getRollCall) only for the states where Open States has no
     votes or no positions (us_states_store.OPENSTATES_VOTE_GAPS), with
     names from getSessionPeople; person_id stays NULL (a LegiScan people_id
     is not an Open States person: never guessed).

Exit status 1 when a gap was recorded. Writes uss_* tables and gaps only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_states_store as uss  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from tools import us_states as ust  # noqa: E402

FEED = "us-states-legiscan"
SOURCE = "legiscan"
API = "https://api.legiscan.com/"
MONTHLY_CAP = 9000          # of the 30,000 the manual names (10,000 on one LegiScan page)
RUN_BUDGET = 1500
LIVE_DAYS = 30
BUDGET_S = 900.0
SPACING_S = 1.0             # LegiScan asks for no rate; one a second is polite

# LegiScan's progress events (manual, "Status / Progress").
EV_INTRO, EV_ENGROSSED, EV_ENROLLED, EV_PASSED, EV_VETOED, EV_CHAPTERED = 1, 2, 3, 4, 5, 8
VOTE_TEXT = {"yea": "yes", "nay": "no", "nv": "not voting", "absent": "absent"}


def legiscan_key():
    from src import publish
    return publish.load_secrets().get("legiscan_api_key") or os.environ.get("LEGISCAN_API_KEY")


class LegiScanError(Exception):
    """A refused or failed query, with the key cut out of every word."""


class LegiScan:
    """Keyed GETs, counted against a run budget and the month's ledger."""

    def __init__(self, client, key, ledger, budget=RUN_BUDGET, archive=True, log=print):
        self.client, self.key, self.ledger, self.budget = client, key, ledger, budget
        self.archive, self.log = archive, log
        self.used = 0

    def remaining(self):
        return min(max(0, self.budget - self.used), self.ledger.left())

    def _scrub(self, text):
        return str(text).replace(self.key, "<key>") if self.key else str(text)

    def get(self, op, slug, **params):
        if not self.remaining():
            raise ust.ApiSpent("LegiScan: {0}".format(
                "the month's cap is reached ({0} of {1})".format(self.ledger.spent(), self.ledger.cap)
                if not self.ledger.left() else "run budget of {0} spent".format(self.budget)))
        self.used += 1
        self.ledger.add()
        url = API + "?" + urlencode(dict(key=self.key, op=op, **params))
        try:
            # A header makes HttpClient take its keyed path: no archive copy
            # of a reply fetched by a keyed URL.
            raw = self.client.get_bytes(url, FEED, slug, headers={"Accept": "application/json"})
        except FetchError as exc:
            raise LegiScanError(self._scrub("{0}: {1}".format(
                op, getattr(exc.cause, "code", None) or exc.cause))) from None
        try:
            d = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise LegiScanError("{0}: not JSON".format(op)) from None
        if d.get("status") != "OK":
            msg = ((d.get("alert") or {}).get("message") or "status " + str(d.get("status")))
            raise LegiScanError(self._scrub("{0}: {1}".format(op, msg)))
        if self.archive:
            self.client._archive(raw, FEED, slug)
        return d


# --- sessions -----------------------------------------------------------------

def current_sessions(sessions, today):
    """LegiScan sessions worth reading: not adjourned sine die, or ending
    this year or later; never a 'prior' (superseded) one. Fifty states only."""
    year = int(today[:4])
    out = []
    for s in sessions:
        st = (s.get("state") or s.get("state_abbr") or "").lower()
        if st and st not in uss.STATES:
            continue
        if s.get("prior"):
            continue
        if not s.get("sine_die") or int(s.get("year_end") or 0) >= year:
            out.append(s)
    return out


def os_session(conn, st, s):
    """Open States' identifier for a LegiScan session, or a LegiScan label
    when the store has none (the key then matches nothing Open States holds,
    and the row stands alone until it does)."""
    found = uss.session_for(conn, st, int(s.get("year_start") or 0),
                            int(s.get("year_end") or 0), special=bool(s.get("special")))
    if found:
        return found
    ys, ye = s.get("year_start"), s.get("year_end")
    label = str(ys) if ys == ye else "{0}-{1}".format(ys, ye)
    return label + ("-ls{0}".format(s.get("session_id")) if s.get("special") else "")


# --- one bill -------------------------------------------------------------------

def chamber_of(body, st):
    if st == "ne":
        return "legislature"
    return "upper" if (body or "").upper().startswith("S") else "lower"


def bill_from_legiscan(d, st, session):
    """A getBill payload in the shape of tools/us_states.bills_from_bulk."""
    origin = chamber_of(d.get("body"), st)
    other = "upper" if origin == "lower" else "lower"
    acts = []
    for i, h in enumerate(d.get("history") or []):
        acts.append({"date": h.get("date"), "description": h.get("action"), "classification": [],
                     "chamber": chamber_of(h.get("chamber"), st), "ord": i})
    # LegiScan's progress events carry the steps; history lines do not.
    for p in d.get("progress") or []:
        ev, day = p.get("event"), p.get("date")
        cls, ch = {EV_INTRO: ("introduction", origin), EV_ENGROSSED: ("passage", origin),
                   EV_ENROLLED: ("passage", other), EV_PASSED: ("became-law", "executive"),
                   EV_VETOED: ("executive-veto", "executive"),
                   EV_CHAPTERED: ("became-law", "executive")}.get(ev, (None, None))
        if not cls or not day:
            continue
        same = [a for a in acts if a["date"] == day and (ch == "executive" or a["chamber"] == ch)]
        if same:
            same[-1]["classification"].append(cls)
            if ch == "executive":
                same[-1]["chamber"] = "executive"
        else:
            acts.append({"date": day, "description": {
                "introduction": "Introduced", "passage": "Passed",
                "became-law": "Became law", "executive-veto": "Vetoed"}[cls] + " (LegiScan)",
                "classification": [cls], "chamber": ch, "ord": len(acts)})
    votes = []
    for v in d.get("votes") or []:
        votes.append({"id": "legiscan-rc:{0}".format(v.get("roll_call_id")),
                      "roll_call_id": v.get("roll_call_id"), "date": v.get("date"),
                      "motion": v.get("desc"), "motion_classification": [],
                      "result": "pass" if v.get("passed") else "fail",
                      "chamber": chamber_of(v.get("chamber"), st),
                      "counts": {"yes": int(v.get("yea") or 0), "no": int(v.get("nay") or 0),
                                 "not voting": int(v.get("nv") or 0),
                                 "absent": int(v.get("absent") or 0)},
                      "url": v.get("state_link") or v.get("url"), "people": []})
    return {
        "id": None, "state": st, "session": session, "identifier": d.get("bill_number"),
        "title": d.get("title"), "classification": [
            "resolution" if (d.get("bill_type") or "B") not in ("B",) else "bill"],
        "subjects": [s.get("subject_name") for s in d.get("subjects") or [] if s.get("subject_name")],
        "abstracts": [d["description"]] if d.get("description") and d.get("description") != d.get(
            "title") else [],
        "other_titles": [], "chamber": origin,
        "url": d.get("state_link") or d.get("url"),
        "actions": acts,
        "sponsors": [{"name": s.get("name"), "person_id": None,
                      "primary": int(s.get("sponsor_type_id") or 0) == 1,
                      "classification": "primary" if int(s.get("sponsor_type_id") or 0) == 1
                      else "cosponsor"} for s in d.get("sponsors") or []],
        "votes": votes,
    }


def master_entries(d):
    ml = d.get("masterlist") or {}
    return [v for k, v in ml.items() if k != "session" and isinstance(v, dict) and v.get("bill_id")]


def candidates(conn, tax, wl, st, session, entries, since, index):
    """[(rank, entry)] master-list bills worth a getBill (see the docstring)."""
    out = []
    for e in entries:
        if (e.get("last_action_date") or "") < since:
            continue
        if ust.source_unchanged(conn, SOURCE, e["bill_id"], e.get("change_hash")):
            continue
        b = {"state": st, "session": session, "identifier": e.get("number"),
             "title": e.get("title") or "", "other_titles": [], "subjects": [],
             "abstracts": [e["description"]] if e.get("description") else []}
        res = ust.classify(tax, wl, b)
        known = uss.norm_ident(e.get("number")) in index
        if not (res.issue_areas or known):
            continue
        watched = any(h.startswith("watch:") for h in res.watchlist_hits or [])
        rank = (not watched, res.tier != 1, ust._neg(e.get("last_action_date")), e["bill_id"])
        out.append((rank, e))
    return sorted(out, key=lambda x: x[0])


def roll_calls(api, bill, people, slug):
    """Positions for each vote, by name; person_id never guessed."""
    for v in bill["votes"]:
        rc = api.get("getRollCall", "{0}-rc-{1}".format(slug, v["roll_call_id"]),
                     id=v["roll_call_id"])["roll_call"]
        v["people"] = [{"name": people.get(p.get("people_id"), "people_id {0}".format(
                        p.get("people_id"))), "person_id": None,
                        "option": VOTE_TEXT.get((p.get("vote_text") or "").lower(),
                                                (p.get("vote_text") or "").lower())}
                       for p in rc.get("votes") or []]


def collect(conn, api, tax, wl, states, today, budget, live_days=LIVE_DAYS, log=print):
    """One run. Returns a dict of counts."""
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=live_days)).isoformat()
    n = {"sessions": 0, "listed": 0, "fetched": 0, "merged": 0, "stored": 0, "replaced": 0,
         "skipped": 0, "rollcalls": 0, "states": set(), "left": []}
    sessions = current_sessions(api.get("getSessionList", "sessions")["sessions"], today)
    by_state = {}
    for s in sessions:
        st = (s.get("state") or s.get("state_abbr") or "").lower()
        if not st:
            # getSessionList without a state gives state_id only. LegiScan
            # numbers the states alphabetically by NAME, 1 Alabama .. 50
            # Wyoming (DC 51, US Congress 52): the manual's examples agree
            # (California 5, Maryland 20).
            st = _STATE_BY_ID.get(int(s.get("state_id") or 0))
        if st in states:
            by_state.setdefault(st, []).append(s)
    order = sorted(by_state, key=lambda st: (-ust.salience(conn, st, today)[0], st))
    for st in order:
        for s in by_state[st]:
            if budget.exhausted() or not api.remaining():
                n["left"].append(st)
                continue
            session = os_session(conn, st, s)
            try:
                ml = api.get("getMasterList", "master-{0}-{1}".format(st, s["session_id"]),
                             id=s["session_id"])
            except LegiScanError as exc:
                ust._gap(conn, today, "LegiScan {0} {1}: {2}".format(st.upper(), session, exc))
                continue
            except ust.ApiSpent:
                n["left"].append(st)
                break
            entries = master_entries(ml)
            # The state_id mapping (_STATE_BY_ID) is checked against the
            # bills' own LegiScan URLs ('https://legiscan.com/CA/bill/...'):
            # a mismatch is a gap, never a bill filed under the wrong state.
            url_states = {m.group(1).lower() for m in (
                re.search(r"legiscan\.com/([A-Z]{2})/", e.get("url") or "") for e in entries[:20])
                if m}
            if url_states and url_states != {st}:
                ust._gap(conn, today, "LegiScan session {0}: mapped to {1} but its bills are "
                         "{2}; not read".format(s["session_id"], st.upper(),
                                                ", ".join(sorted(url_states)).upper()))
                continue
            n["sessions"] += 1
            n["listed"] += len(entries)
            index = ust.session_index(conn, st, session)
            people = None
            for _, e in candidates(conn, tax, wl, st, session, entries, since, index):
                if budget.exhausted() or not api.remaining():
                    n["left"].append(st)
                    break
                slug = "bill-{0}-{1}".format(st, e["bill_id"])
                try:
                    d = api.get("getBill", slug, id=e["bill_id"])["bill"]
                    b = bill_from_legiscan(d, st, session)
                    if st in uss.OPENSTATES_VOTE_GAPS and b["votes"]:
                        recent = [v for v in b["votes"] if (v["date"] or "") >= since]
                        if recent and api.remaining() > len(recent) + 1:
                            if people is None:
                                sp = api.get("getSessionPeople", "people-{0}-{1}".format(
                                    st, s["session_id"]), id=s["session_id"])
                                people = {p.get("people_id"): p.get("name") for p in
                                          (sp.get("sessionpeople") or {}).get("people") or []}
                            b["votes"] = recent
                            roll_calls(api, b, people, slug)
                            n["rollcalls"] += len(recent)
                except LegiScanError as exc:
                    ust._gap(conn, today, "LegiScan {0} {1} {2}: {3}".format(
                        st.upper(), session, e.get("number"), exc))
                    continue
                except ust.ApiSpent:
                    n["left"].append(st)
                    break
                n["fetched"] += 1
                what, _bid, _res = ust.merge_foreign(
                    conn, tax, wl, SOURCE, e["bill_id"], b, today,
                    change_hash=d.get("change_hash") or e.get("change_hash"),
                    url=d.get("url"), index=index)
                n[what] += 1
                if what != "skipped":
                    n["states"].add(st)
            conn.commit()
            log("  {0} {1}: LegiScan, {2} bill(s) listed".format(st.upper(), session, len(entries)))
    n["left"] = sorted(set(n["left"]))
    return n


_STATE_BY_ID = {i + 1: st for i, st in enumerate(sorted(uss.STATES, key=uss.STATES.get))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--states", default="")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--run-budget", type=int, default=RUN_BUDGET)
    ap.add_argument("--monthly-cap", type=int,
                    default=int(os.environ.get("LEGISCAN_MONTHLY_CAP") or MONTHLY_CAP))
    ap.add_argument("--live-days", type=int, default=LIVE_DAYS)
    ap.add_argument("--dry-run", action="store_true",
                    help="the session list only (one query), nothing stored")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    states = [s.strip().lower() for s in args.states.split(",") if s.strip()] or sorted(uss.STATES)
    key = legiscan_key()
    if not key:
        print("us-states-legiscan: no LEGISCAN_API_KEY; skipped (optional: a free key from "
              "https://legiscan.com/legiscan, see docs/us-states-scope.md)")
        return 0
    conn = db.init_db(db.connect(args.db))
    ledger = ust.SourceLedger(conn, SOURCE, args.monthly_cap)
    client = HttpClient(raw_dir=args.raw_dir, throttle=SPACING_S, max_retries=1)
    api = LegiScan(client, key, ledger, budget=args.run_budget, archive=not args.dry_run)
    print("us-states-legiscan: {0} quer(ies) spent this month; this run may spend {1}".format(
        ledger.spent(), api.remaining()))
    if args.dry_run:
        try:
            ss = current_sessions(api.get("getSessionList", "sessions")["sessions"], today)
        except (LegiScanError, ust.ApiSpent) as exc:
            print("  [gap] LegiScan session list: {0}".format(exc))
            return 1
        print("us-states-legiscan: dry run, {0} current session(s); a run would spend about "
              "{1} master-list quer(ies) plus one per changed bill".format(len(ss), len(ss)))
        return 0
    tax = filt.load_taxonomy(ust.TAXONOMY)
    wl = ust.empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    try:
        n = collect(conn, api, tax, wl, states, today, budget, live_days=args.live_days)
    except (LegiScanError, ust.ApiSpent) as exc:
        ust._gap(conn, today, "LegiScan: {0}".format(exc))
        conn.commit()
        print("  [gap] LegiScan: {0}".format(exc))
        return 1
    gaps = conn.execute("SELECT COUNT(*) FROM gaps WHERE edition=? AND detail LIKE 'LegiScan%'",
                        (today,)).fetchone()[0]
    print("us-states-legiscan: {0} session(s), {1} bill(s) listed, {2} fetched: {3} merged into "
          "Open States rows, {4} stored new, {5} refreshed, {6} off our ground; {7} roll call(s); "
          "{8} state(s) touched; {9} quer(ies) this run, {10} this month (cap {11}){12}".format(
              n["sessions"], n["listed"], n["fetched"], n["merged"], n["stored"], n["replaced"],
              n["skipped"], n["rollcalls"], len(n["states"]), api.used, ledger.spent(), ledger.cap,
              "; not reached: " + ", ".join(s.upper() for s in n["left"]) if n["left"] else ""))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
