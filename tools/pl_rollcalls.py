#!/usr/bin/env python3
"""Poland: deputies, prints, legislative processes and recorded votes of the Sejm.

    python3 tools/pl_rollcalls.py                    # the current term (10th)
    python3 tools/pl_rollcalls.py --dry-run          # count, store nothing
    python3 tools/pl_rollcalls.py --reclassify       # re-derive areas, offline
    python3 tools/pl_rollcalls.py --db /tmp/pl.db    # anywhere but the store

PHASE 1 (9 October 2026); see docs/poland-scope.md. Every source is the
Sejm's own open API, api.sejm.gov.pl: JSON, keyless, no account, no stated
rate limit (we keep to one request a second).

  * /sejm/term                      every term; the current one and its print count
  * /sejm/term{N}/MP                every deputy of the term (499 for 460 seats)
  * /sejm/term{N}/prints            every print (druk) of the term in ONE reply
                                    (3,415, 1.8 MB); limit/offset are ignored
  * /sejm/term{N}/processes         legislative processes, 50 a page by default,
                                    limit=500&offset=n for the rest (1,739)
  * /sejm/term{N}/processes/{num}   one process with its stages (detail)
  * /sejm/term{N}/votings           vote count per sitting day
  * /sejm/term{N}/votings/{sitting} every vote of a sitting, with totals, no positions
  * /sejm/term{N}/votings/{s}/{n}   one vote with every deputy's position and club

A VOTE NAMES ITS PRINTS, NOT ITS PROCESS. The title and topic cite "druki nr
3030, 3080 i 3080-A"; the print list's `processPrint` says which process each
print belongs to. Measured on the whole 10th term: 4,527 of 4,941 votes cite
at least one print, and every cited print resolved.

NOTHING IS CLASSIFIED UNTIL taxonomy-pl EXISTS. The English taxonomy is
blind to Polish (measured: docs/poland-scope.md, one match in 1,739 process
titles and summaries, none in 4,941 votes). Until Chris approves the proposed
Polish terms and config/taxonomy-pl.yaml is generated, areas come only from
config/watchlist-pl.yaml (by process key) and are otherwise NULL, meaning
"not classified", which is different from "classified, none". --reclassify
fills them, offline, the day the file lands.

Separation guarantee: writes pl_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store. Exit 0 clean, 3 stored-with-gaps.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, pl_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "pl-rollcalls"
API = "https://api.sejm.gov.pl/sejm"
TERMS = API + "/term"
MEMBERS = API + "/term{0}/MP"
PRINTS = API + "/term{0}/prints"
PROCESSES = API + "/term{0}/processes?limit={1}&offset={2}"
PROCESS = API + "/term{0}/processes/{1}"
VOTE_INDEX = API + "/term{0}/votings"
SITTING = API + "/term{0}/votings/{1}"
VOTE = API + "/term{0}/votings/{1}/{2}"
TAXONOMY_PL = os.path.join(ROOT, "config", "taxonomy-pl.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "pl"
THROTTLE_S = 1.0
PAGE = 500
# Sittings re-read on every run even when their count already matches: a
# sitting's last day is often voted after the weekly pull of the day before.
RECENT_SITTINGS = 2


# --- parsing (pure; the tests drive these with saved replies) ---------------

def current_term(terms):
    """(term number, declared print count) of the term marked current."""
    for t in terms or []:
        if t.get("current"):
            return int(t["num"]), int((t.get("prints") or {}).get("count") or 0)
    return None, None


_PRINT_LIST = re.compile(
    r"druk(?:i|u|ów|ach|iem)?\s*(?:nr\.?\s*)?"
    r"(\d+(?:-[A-Za-z]+)?(?:\s*(?:,|\bi\b|\boraz\b)\s*\d+(?:-[A-Za-z]+)?)*)", re.I)
_PRINT_NO = re.compile(r"\d+(?:-[A-Za-z]+)?")


def print_numbers(*texts):
    """Every print a vote's text cites, in order, once each:
    '(druki nr 3030, 3080 i 3080-A)' -> ['3030', '3080', '3080-A']."""
    out = []
    for text in texts:
        for m in _PRINT_LIST.finditer(text or ""):
            out += [n.upper() for n in _PRINT_NO.findall(m.group(1))]
    return list(dict.fromkeys(out))


def member_row(m, term):
    """The MP list's record -> a pl_members row dict."""
    district = m.get("districtName")
    if district and m.get("districtNum"):
        district = "{0} ({1})".format(district, m["districtNum"])
    name = m.get("firstLastName") or " ".join(x for x in (m.get("firstName"), m.get("lastName")) if x)
    return {"mp_key": pl_store.mp_key(term, m["id"]), "term": term, "mp_id": int(m["id"]),
            "name": name, "club": m.get("club"), "district": district,
            "voivodeship": m.get("voivodeship"), "active": 1 if m.get("active") else 0,
            "inactive_cause": m.get("inactiveCause")}


def last_stage(stages):
    """(name, date) of the latest top-level stage of a process's detail."""
    best = (None, None)
    for st in stages or []:
        if st.get("date") and (best[1] is None or st["date"] >= best[1]):
            best = (st.get("stageName"), st["date"])
    return best


def vote_problems(v):
    """What does not add up in a vote detail; [] when it is consistent."""
    out = []
    votes = v.get("votes") or []
    if not votes:
        return ["no positions in the reply"]
    if v.get("kind") == "ELECTRONIC":
        tally = {"YES": 0, "NO": 0, "ABSTAIN": 0, "ABSENT": 0}
        for p in votes:
            if p.get("vote") in tally:
                tally[p["vote"]] += 1
        for field, pos in (("yes", "YES"), ("no", "NO"), ("abstain", "ABSTAIN")):
            if field in v and v[field] != tally[pos]:
                out.append("{0} {1} declared, {2} listed".format(field, v[field], tally[pos]))
        # A quorum call ('Głosowanie kworum') counts in `present`, not yes/no.
        if v.get("present") and not (v.get("yes") or v.get("no") or v.get("abstain")):
            out = []
    return out


# --- classification ----------------------------------------------------------

def load_taxonomy(path=TAXONOMY_PL):
    """The Polish taxonomy, or None until Chris approves it."""
    return filt.load_taxonomy(path, country=TAXONOMY_COUNTRY) if os.path.exists(path) else None


def empty_watchlist():
    """Watched keys are applied by pl_store.add_watch_areas, not by title."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify_process(tax, title, description, key, watch_path=None):
    """(areas_json_or_None, matched_json, tier). NULL areas = not classified."""
    res = (filt.filter_item(tax, empty_watchlist(), title or "", description or "")
           if tax is not None else filt.FilterResult())
    pl_store.add_watch_areas(res, key, watch_path)
    if tax is None and not res.watchlist_hits:
        return None, None, None
    return (pl_store.dumps(res.issue_areas),
            pl_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier)


def classify_division(tax, texts, linked):
    """A vote's areas: matched on its own text, then united with every linked
    process's stored areas. linked = [(areas_json, matched_json, tier)].
    Returns (own_areas, areas, matched, tier); NULL areas = not classified."""
    own = (filt.filter_item(tax, empty_watchlist(), *texts) if tax is not None
           else filt.FilterResult())
    areas, matched = set(own.issue_areas or []), list(own.matched_terms or [])
    tiers = [own.tier] if own.tier else []
    classified = tax is not None
    for a, m, t in linked:
        if a is None:
            continue
        classified = True
        areas |= set(json.loads(a))
        matched += [x for x in json.loads(m or "[]") if x not in matched]
        if t:
            tiers.append(t)
    if not classified:
        return None, None, None, None
    own_json = pl_store.dumps(own.issue_areas) if tax is not None else None
    return own_json, pl_store.dumps(sorted(areas)), pl_store.dumps(matched), (min(tiers) if tiers else None)


# --- collecting --------------------------------------------------------------

def _gap(conn, today, detail, log=print):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    log("  [gap] " + detail[:110])


def pull_members(conn, client, term, today, log=print):
    """Every deputy of the term. Returns (stored, gaps)."""
    try:
        rows = client.get_json(MEMBERS.format(term), FEED, "members-{0}".format(term))
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "members: {0}".format(exc), log)
        return 0, 1
    for m in rows or []:
        r = member_row(m, term)
        conn.execute(
            "INSERT INTO pl_members (mp_key, term, mp_id, name, club, district, voivodeship, active, "
            "inactive_cause, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(mp_key) DO UPDATE SET name=excluded.name, club=excluded.club, "
            "district=excluded.district, voivodeship=excluded.voivodeship, active=excluded.active, "
            "inactive_cause=excluded.inactive_cause, last_seen=excluded.last_seen",
            (r["mp_key"], term, r["mp_id"], r["name"], r["club"], r["district"], r["voivodeship"],
             r["active"], r["inactive_cause"], today, today))
    conn.commit()
    return len(rows or []), 0


def pull_prints(conn, client, term, today, declared=None, log=print):
    """Every print of the term, in one reply. Returns (stored, gaps)."""
    try:
        rows = client.get_json(PRINTS.format(term), FEED, "prints-{0}".format(term))
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "prints: {0}".format(exc), log)
        return 0, 1
    gaps = 0
    if declared and len(rows or []) != declared:
        _gap(conn, today, "prints: {0} listed of {1} declared".format(len(rows or []), declared), log)
        gaps += 1
    for p in rows or []:
        procs = p.get("processPrint") or []
        conn.execute(
            "INSERT INTO pl_prints (print_key, term, number, process_key, title, document_date, "
            "delivery_date, change_date, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(print_key) DO UPDATE SET process_key=excluded.process_key, "
            "title=excluded.title, document_date=excluded.document_date, "
            "delivery_date=excluded.delivery_date, change_date=excluded.change_date, "
            "last_seen=excluded.last_seen",
            (pl_store.process_key(term, p["number"]), term, p["number"],
             pl_store.process_key(term, procs[0]) if procs else None, p.get("title"),
             p.get("documentDate"), p.get("deliveryDate"), p.get("changeDate"), today, today))
    conn.commit()
    return len(rows or []), gaps


def store_process(conn, p, term, tax, today, watch_path=None):
    key = pl_store.process_key(term, p["number"])
    areas, matched, tier = classify_process(tax, p.get("title"), p.get("description"), key, watch_path)
    conn.execute(
        "INSERT INTO pl_processes (process_key, term, number, title, title_final, description, "
        "document_type, document_type_enum, start_date, closure_date, passed, eli, change_date, "
        "areas, matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(process_key) DO UPDATE SET title=excluded.title, title_final=excluded.title_final, "
        "description=excluded.description, document_type=excluded.document_type, "
        "document_type_enum=excluded.document_type_enum, start_date=excluded.start_date, "
        "closure_date=excluded.closure_date, passed=excluded.passed, eli=excluded.eli, "
        "change_date=excluded.change_date, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (key, term, str(p["number"]), p.get("title"), p.get("titleFinal"), p.get("description"),
         p.get("documentType"), p.get("documentTypeEnum"), p.get("processStartDate"),
         p.get("closureDate"), 1 if p.get("passed") else 0, p.get("ELI"), p.get("changeDate"),
         areas, matched, tier, today, today))
    return key


def pull_processes(conn, client, term, tax, today, log=print, watch_path=None):
    """Every process of the term, a page of 500 at a time. Returns (stored, gaps)."""
    seen, offset = 0, 0
    while offset < 20000:
        try:
            page = client.get_json(PROCESSES.format(term, PAGE, offset), FEED,
                                   "processes-{0}-{1}".format(term, offset))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "processes offset {0}: {1}".format(offset, exc), log)
            conn.commit()
            return seen, 1
        for p in page or []:
            store_process(conn, p, term, tax, today, watch_path)
        conn.commit()
        seen += len(page or [])
        if len(page or []) < PAGE:
            break
        offset += PAGE
    return seen, 0


def pull_stages(conn, client, term, today, log=print, budget=None):
    """The stage list of every classified, on-ground process whose list
    changeDate moved since its detail was last read. Returns (read, gaps)."""
    todo = conn.execute(
        "SELECT process_key, number, change_date FROM pl_processes WHERE term=? AND areas IS NOT NULL "
        "AND areas != '[]' AND (stages_read IS NULL OR stages_read != COALESCE(change_date, '')) "
        "ORDER BY change_date DESC", (term,)).fetchall()
    read = gaps = 0
    for key, number, changed in todo:
        if budget is not None and budget.exhausted():
            log(budget.disclose("process details", read))
            break
        try:
            d = client.get_json(PROCESS.format(term, number), FEED, "process-{0}-{1}".format(term, number))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "process {0}: {1}".format(key, exc), log)
            gaps += 1
            continue
        name, date = last_stage(d.get("stages"))
        conn.execute("UPDATE pl_processes SET last_stage=?, last_stage_date=?, stages_read=? "
                     "WHERE process_key=?", (name, date, changed or "", key))
        read += 1
    conn.commit()
    return read, gaps


def _linked(conn, process_keys):
    if not process_keys:
        return []
    marks = ",".join("?" * len(process_keys))
    return conn.execute("SELECT areas, matched_terms, tier FROM pl_processes WHERE process_key IN "
                        "({0})".format(marks), tuple(process_keys)).fetchall()


def _process_keys(conn, term, prints):
    keys = []
    for n in prints:
        row = conn.execute("SELECT process_key FROM pl_prints WHERE print_key=?",
                           (pl_store.process_key(term, n),)).fetchone()
        if row and row[0] and row[0] not in keys:
            keys.append(row[0])
    return keys


def store_division(conn, v, term, tax, today):
    key = pl_store.division_key(term, v["sitting"], v["votingNumber"])
    prints = print_numbers(v.get("title"), v.get("topic"), v.get("description"))
    procs = _process_keys(conn, term, prints)
    own, areas, matched, tier = classify_division(
        tax, (v.get("title") or "", v.get("topic") or "", v.get("description") or ""), _linked(conn, procs))
    conn.execute(
        "INSERT INTO pl_divisions (division_key, term, sitting, sitting_day, number, voted_at, kind, title, "
        "topic, description, print_numbers, process_keys, majority_type, majority_votes, yes, no, abstain, "
        "present, not_participating, total_voted, against_all, options, own_areas, areas, matched_terms, "
        "tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET voted_at=excluded.voted_at, kind=excluded.kind, "
        "title=excluded.title, topic=excluded.topic, description=excluded.description, "
        "print_numbers=excluded.print_numbers, process_keys=excluded.process_keys, "
        "majority_type=excluded.majority_type, majority_votes=excluded.majority_votes, yes=excluded.yes, "
        "no=excluded.no, abstain=excluded.abstain, present=excluded.present, "
        "not_participating=excluded.not_participating, total_voted=excluded.total_voted, "
        "against_all=excluded.against_all, options=excluded.options, own_areas=excluded.own_areas, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (key, term, v["sitting"], v.get("sittingDay"), v["votingNumber"], v.get("date"), v.get("kind"),
         v.get("title"), v.get("topic"), v.get("description"), pl_store.dumps(prints),
         pl_store.dumps(procs), v.get("majorityType"), v.get("majorityVotes"), v.get("yes"), v.get("no"),
         v.get("abstain"), v.get("present"), v.get("notParticipating"), v.get("totalVoted"),
         v.get("againstAll"), pl_store.dumps(v["votingOptions"]) if v.get("votingOptions") else None,
         own, areas, matched, tier, today, today))
    return key


def sittings_to_read(conn, term, index, recent=RECENT_SITTINGS):
    """Sittings whose stored vote count falls short of the index's, plus the
    latest `recent` sittings always. Newest first."""
    declared = {}
    for day in index or []:
        declared[day["proceeding"]] = declared.get(day["proceeding"], 0) + int(day.get("votingsNum") or 0)
    have = dict(conn.execute("SELECT sitting, COUNT(*) FROM pl_divisions WHERE term=? GROUP BY sitting",
                             (term,)))
    newest = sorted(declared, reverse=True)
    return [s for s in newest if have.get(s, 0) < declared[s] or s in newest[:recent]], declared


def pull_divisions(conn, client, term, tax, today, log=print, recent=RECENT_SITTINGS, budget=None):
    """Vote headers for every sitting that needs reading. Returns (stored, sittings, gaps)."""
    try:
        index = client.get_json(VOTE_INDEX.format(term), FEED, "votings-{0}".format(term))
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "votings index: {0}".format(exc), log)
        return 0, 0, 1
    todo, declared = sittings_to_read(conn, term, index, recent)
    n = gaps = sittings = 0
    for s in todo:
        if budget is not None and budget.exhausted():
            log(budget.disclose("sittings", sittings))
            break
        try:
            votes = client.get_json(SITTING.format(term, s), FEED, "sitting-{0}-{1}".format(term, s))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "sitting {0}: {1}".format(s, exc), log)
            gaps += 1
            continue
        if len(votes or []) != declared[s]:
            _gap(conn, today, "sitting {0}: {1} vote(s) listed of {2} in the index".format(
                s, len(votes or []), declared[s]), log)
            gaps += 1
        for v in votes or []:
            store_division(conn, v, term, tax, today)
        conn.commit()
        n += len(votes or [])
        sittings += 1
    return n, sittings, gaps


def store_positions(conn, key, v, term):
    conn.execute("DELETE FROM pl_votes WHERE division_key=?", (key,))
    for p in v.get("votes") or []:
        conn.execute("INSERT OR REPLACE INTO pl_votes (division_key, mp_key, position, club, list_votes) "
                     "VALUES (?,?,?,?,?)",
                     (key, pl_store.mp_key(term, p["MP"]), p.get("vote"), p.get("club"),
                      json.dumps(p["listVotes"], ensure_ascii=False) if p.get("listVotes") else None))
    conn.execute("UPDATE pl_divisions SET positions=? WHERE division_key=?", (len(v.get("votes") or []), key))


def pull_positions(conn, client, term, today, log=print, limit=None, budget=None):
    """Every deputy's position on every vote not yet held, newest first.
    Returns (stored, gaps)."""
    todo = conn.execute("SELECT division_key, sitting, number FROM pl_divisions WHERE term=? AND "
                        "positions IS NULL ORDER BY sitting DESC, number DESC", (term,)).fetchall()
    stored = gaps = failed = 0
    for i, (key, sitting, number) in enumerate(todo):
        if limit is not None and i >= limit:
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("vote details", stored))
            break
        try:
            v = client.get_json(VOTE.format(term, sitting, number), FEED,
                                "vote-{0}-{1}-{2}".format(term, sitting, number))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "vote {0}: {1}".format(key, exc), log)
            gaps += 1
            failed += 1
            continue
        problems = vote_problems(v)
        for problem in problems:
            _gap(conn, today, "vote {0}: {1}".format(key, problem), log)
            gaps += 1
        if v.get("votes"):
            store_positions(conn, key, v, term)
            stored += 1
        if stored % 100 == 0:
            conn.commit()
    conn.commit()
    left = len(todo) - stored - failed
    if left > 0:
        log("  {0} vote(s) still without positions; later runs continue newest-first".format(left))
    return stored, gaps


# --- offline -----------------------------------------------------------------

def reclassify(conn, tax=None, log=print, watch_path=None):
    """Re-derive process areas, then every division's, offline."""
    tax = tax if tax is not None else load_taxonomy()
    changed = 0
    for key, title, desc, areas in conn.execute(
            "SELECT process_key, title, description, areas FROM pl_processes").fetchall():
        new, matched, tier = classify_process(tax, title, desc, key, watch_path)
        changed += (new or "") != (areas or "")
        conn.execute("UPDATE pl_processes SET areas=?, matched_terms=?, tier=? WHERE process_key=?",
                     (new, matched, tier, key))
    for key, title, topic, desc, procs in conn.execute(
            "SELECT division_key, title, topic, description, process_keys FROM pl_divisions").fetchall():
        own, areas, matched, tier = classify_division(
            tax, (title or "", topic or "", desc or ""), _linked(conn, json.loads(procs or "[]")))
        conn.execute("UPDATE pl_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?", (own, areas, matched, tier, key))
    conn.commit()
    log("pl-rollcalls: reclassified ({0}); {1} process(es) changed area".format(
        "taxonomy-pl" if tax is not None else "no taxonomy-pl yet: watchlist only", changed))
    return changed


def on_our_ground(areas_json):
    return any(a != 11 for a in json.loads(areas_json or "[]"))


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = sum(on_our_ground(a) for (a,) in conn.execute("SELECT areas FROM pl_processes"))
    log("  store: {0} process(es) ({1} classified, {2} on our ground), {3} print(s); "
        "{4} vote(s) ({5} with positions), {6} position(s); {7} deputy record(s)".format(
            n("SELECT COUNT(*) FROM pl_processes"),
            n("SELECT COUNT(*) FROM pl_processes WHERE areas IS NOT NULL"), ours,
            n("SELECT COUNT(*) FROM pl_prints"), n("SELECT COUNT(*) FROM pl_divisions"),
            n("SELECT COUNT(*) FROM pl_divisions WHERE positions IS NOT NULL"),
            n("SELECT COUNT(*) FROM pl_votes"), n("SELECT COUNT(*) FROM pl_members")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--term", type=int, help="Sejm term (default: the one the API marks current)")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--recent", type=int, default=RECENT_SITTINGS,
                    help="sittings re-read on every run (default 2)")
    ap.add_argument("--no-positions", action="store_true", help="vote headers only")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored processes and votes, offline")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--limit", type=int, help="stop after this many vote details")
    ap.add_argument("--dry-run", action="store_true",
                    help="read the term list and the votings index, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=args.raw_dir, throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    if args.reclassify:
        conn = db.init_db(db.connect(args.db))
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    try:
        term, declared_prints = current_term(client.get_json(TERMS, FEED, "terms",
                                                             archive=not args.dry_run))
    except (FetchError, ValueError) as exc:
        print("pl-rollcalls: the term list failed: {0}".format(exc))
        return 1
    term = args.term or term
    if term is None:
        print("pl-rollcalls: no current term in the API's term list")
        return 1
    if args.dry_run:
        index = client.get_json(VOTE_INDEX.format(term), FEED, "dry", archive=False)
        print("pl-rollcalls: term {0}, {1} print(s) declared; {2} sitting day(s) with {3} vote(s)".format(
            term, declared_prints, len(index), sum(int(d.get("votingsNum") or 0) for d in index)))
        return 0
    conn = db.init_db(db.connect(args.db))
    tax = load_taxonomy()
    if tax is None:
        print("pl-rollcalls: no config/taxonomy-pl.yaml yet; areas come from watchlist-pl only")
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    stored, g = pull_members(conn, client, term, today)
    gaps += g
    print("pl-rollcalls: {0} deputy record(s), {1} gap(s)".format(stored, g))
    stored, g = pull_prints(conn, client, term, today, declared_prints)
    gaps += g
    print("pl-rollcalls: {0} print(s), {1} gap(s)".format(stored, g))
    stored, g = pull_processes(conn, client, term, tax, today)
    gaps += g
    print("pl-rollcalls: {0} process(es), {1} gap(s)".format(stored, g))
    stored, g = pull_stages(conn, client, term, today, budget=budget)
    gaps += g
    print("pl-rollcalls: {0} process detail(s) read, {1} gap(s)".format(stored, g))
    stored, sittings, g = pull_divisions(conn, client, term, tax, today, recent=args.recent, budget=budget)
    gaps += g
    print("pl-rollcalls: {0} vote header(s) from {1} sitting(s), {2} gap(s)".format(stored, sittings, g))
    if not args.no_positions:
        stored, g = pull_positions(conn, client, term, today, limit=args.limit, budget=budget)
        gaps += g
        print("pl-rollcalls: positions for {0} vote(s), {1} gap(s)".format(stored, g))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
