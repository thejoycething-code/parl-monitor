#!/usr/bin/env python3
"""Ecuador, Asamblea Nacional: plenary votes, every member's position, the
member register and the sitting roster with party.

    python3 tools/ec_rollcalls.py                      # the current period
    python3 tools/ec_rollcalls.py --period 7           # a named one (backfill)
    python3 tools/ec_rollcalls.py --index-only         # vote list, no positions
    python3 tools/ec_rollcalls.py --reclassify         # re-derive areas, offline
    python3 tools/ec_rollcalls.py --taxonomy x.yaml    # classify with a draft list
    python3 tools/ec_rollcalls.py --db /tmp/ec.db      # anywhere but the store

PHASE 1 (9 October 2026); see docs/ecuador-scope.md. Every source is open
and keyless, measured live:

  * datos.asambleanacional.gob.ec/ecurul/ -- the JSON service behind the
    Asamblea's "Sistema de Consulta de Datos Parlamentarios" page:
      reports/period?idPeriod=            the legislative periods (8 = 2025-2029)
      reports/votingList?datePeriod=&dateIn=&dateOut=&sessionNumber=&theme=&proposal=
                                          every plenary vote in a date window,
                                          with totals (521 in period 8 to 6 Oct 2026)
      assemblyman/votingDetail?idVoting=  every position on one vote
      assemblyman/assemblymemberlist      the member register (798 names since 2009)
    A vote number that does not exist and an empty window both answer
    HTTP 200 with `[]`, so emptiness is checked, never the status.
  * www.asambleanacional.gob.ec/es/pleno-asambleistas -- the sitting 151,
    with constituency, and party read off each member's avatar image.

NO BILL NUMBER, NO MEMBER ID, NO PARTY ON A VOTE: see src/ec_store.py.

CLASSIFICATION waits for a Spanish taxonomy (config/taxonomy-ec.yaml,
proposed in docs/ecuador-scope.md, generated only once Christopher approves
it). Until then areas stay NULL -- unclassified, not "nothing found" -- and
only config/watchlist-ec.yaml, applied by division KEY, lends areas.

Separation guarantee: writes ec_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

Exit codes: 0 clean, 3 stored what it could and recorded gaps, 1 otherwise.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, ec_store, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ec-rollcalls"
API = "https://datos.asambleanacional.gob.ec/ecurul/"
PERIODS_URL = API + "reports/period?idPeriod="
VOTES_URL = (API + "reports/votingList?datePeriod={period}&dateIn={start}&dateOut={end}"
             "&sessionNumber=&theme=&proposal=")
DETAIL_URL = API + "assemblyman/votingDetail?idVoting={vid}"
MEMBERS_URL = API + "assemblyman/assemblymemberlist"
ROSTER_URL = "https://www.asambleanacional.gob.ec/es/pleno-asambleistas"
TAXONOMY_EC = os.path.join(ROOT, "config", "taxonomy-ec.yaml")
BUDGET_S = drain.DEFAULT_S
# The www robots.txt asks for Crawl-delay 1; the datos service answers a
# detail in about 1.1 s (up to 4 s) and is the same institution's server.
THROTTLE_S = 1.0
# Votes re-listed even when already stored: a late correction to a vote's
# totals or text is picked up within two weeks.
REREAD_DAYS = 14
# The roster page held 151 named members on 9 October 2026; fewer than this
# means the page changed shape, not that the Asamblea shrank.
ROSTER_FLOOR = 120
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)
POSITIONS = ("SI", "NO", "ABSTENCION", "BLANCO")
PARTIES = {
    "adn": "Acción Democrática Nacional (ADN)",
    "revolucion-ciudadana": "Revolución Ciudadana",
    "pachakutik": "Pachakutik",
    "psc": "Partido Social Cristiano",
}
ECUADOR_UTC_OFFSET = datetime.timedelta(hours=-5)   # no daylight saving


# --- small helpers ------------------------------------------------------------

def fold(text):
    """Strip tags, unescape, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def local_date(stamp):
    """'2026-09-03T19:21:04.000+00:00' -> '2026-09-03' in Ecuador; else None."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", stamp or "")
    if not m:
        return None
    dt = datetime.datetime.fromisoformat(m.group(1) + "T" + m.group(2) + ":" + m.group(3))
    return (dt + ECUADOR_UTC_OFFSET).date().isoformat()


def division_key(voting_id):
    return "ec-{0}".format(int(voting_id))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, UnicodeDecodeError):
        return None


# --- parsing ------------------------------------------------------------------

def parse_periods(raw):
    """[(period_id, start, end)] oldest first, from reports/period."""
    data = _json(raw)
    if not isinstance(data, list):
        return []
    out = [(int(p["periodId"]), p.get("periodDateIn"), p.get("periodDateOut"))
           for p in data if isinstance(p, dict) and p.get("periodId") is not None]
    return sorted(out, key=lambda p: p[1] or "")


def current_period(periods, today):
    """The period whose dates hold `today`, else the latest that has begun."""
    started = [p for p in periods if (p[1] or "9999") <= today]
    for p in started:
        if p[2] and p[1] <= today <= p[2]:
            return p
    return started[-1] if started else None


def parse_vote_list(raw):
    """Votes from reports/votingList, or None when the reply is not a list."""
    data = _json(raw)
    if not isinstance(data, list):
        return None
    out = []
    for v in data:
        if not isinstance(v, dict) or v.get("votingId") is None:
            continue
        out.append({
            "voting_id": int(v["votingId"]),
            "session": v.get("sessionNumber"),
            "voted_at": v.get("voteDate"),
            "date": local_date(v.get("voteDate")),
            "theme": fold(v.get("theme")) or None,
            "proposal": fold(v.get("proposalType")) or None,
            "yes": v.get("contYes"), "no": v.get("contNo"),
            "blank": v.get("contWhite"), "abstain": v.get("contAbstention"),
        })
    return out


def parse_detail(raw):
    """[(name, name_key, position, seat)] from assemblyman/votingDetail, or
    None when the reply is not a list. Surnames first, as the register prints."""
    data = _json(raw)
    if not isinstance(data, list):
        return None
    out = []
    for r in data:
        if not isinstance(r, dict):
            continue
        surnames, given = fold(r.get("lastname")), fold(r.get("firstName"))
        name = " ".join(p for p in (surnames, given) if p)
        pos = (r.get("description") or "").strip().upper()
        if not name or not pos:
            continue
        seat = r.get("territorial")
        out.append((name, ec_store.name_key(name), pos, None if seat is None else str(seat)))
    return out


def parse_members(raw):
    """[(member_id, name, name_key)] from the register. Its `firstName`
    holds the SURNAMES and `lastname` the given names (the vote detail has
    them the other way round)."""
    data = _json(raw)
    if not isinstance(data, list):
        return None
    out = []
    for m in data:
        if not isinstance(m, dict) or m.get("id") is None:
            continue
        name = " ".join(p for p in (fold(m.get("firstName")), fold(m.get("lastname"))) if p)
        if name:
            out.append((int(m["id"]), name, ec_store.name_key(name)))
    return out


_CARD = re.compile(
    r'class="icon-asambleitas-partido[^"]*"[^>]*>\s*<img src="([^"]+)"(.*?)'
    r'(?=class="icon-asambleitas-partido|\Z)', re.S)
_CARD_NAME = re.compile(r"<strong>(.*?)<br\s*/?>\s*<em>(.*?)</em>", re.S)


def party_slug(img_url):
    """'.../avatar-mujer-adn.png?itok=..' -> 'adn'; 'avartar-psc-hombre.png' ->
    'psc'; 'avatar-26.png' -> '26'; the presidency icons -> None."""
    base = img_url.rsplit("/", 1)[-1].split("?", 1)[0]
    base = re.sub(r"\.(png|jpe?g|gif)$", "", base, flags=re.I)
    if not re.match(r"ava?r?tar-", base):
        return None
    slug = re.sub(r"^ava?r?tar-", "", base)
    slug = re.sub(r"(^|-)(hombre|mujer)(-|$)", r"\1\3", slug).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or None


def parse_roster(page):
    """[(name, name_key, constituency, slug, party)] from the plenary page."""
    out, seen = [], set()
    for m in _CARD.finditer(page or ""):
        nm = _CARD_NAME.search(m.group(2))
        if not nm:
            continue          # the presidency icons carry no card
        name = fold(nm.group(1))
        where = fold(nm.group(2))
        where = re.sub(r"^Asamble[ií]st[ao]\s*(por\s+(la\s+provincia\s+de(l)?\s+)?)?", "",
                       where, flags=re.I).strip() or None
        slug = party_slug(m.group(1))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append((name, ec_store.name_key(name), where, slug, PARTIES.get(slug)))
    return out


# --- classification ---------------------------------------------------------------

def load_taxonomy(path=None):
    """The Spanish (Ecuador) taxonomy, or None while none exists (areas NULL)."""
    path = path or TAXONOMY_EC
    return filt.load_taxonomy(path) if os.path.exists(path) else None


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, key, *texts):
    """(own areas, combined areas, matched terms, tier) for one vote: its
    own text, then its watchlist entry by KEY. Both None only when there is
    no taxonomy AND no watchlist entry: unclassified, not empty."""
    watched = ec_store.watch_areas(key)
    if tax is None:
        if watched:
            return None, sorted(set(watched)), ["watch:" + key], 2
        return None, None, [], None
    res = filt.filter_item(tax, empty_watchlist(), *[t for t in texts if t])
    own = sorted(set(res.issue_areas or []))
    terms = list(res.matched_terms or [])
    tier = res.tier
    combined = set(own)
    if watched:
        combined |= set(watched)
        terms.append("watch:" + key)
        tier = tier or 2
    return own, sorted(combined), terms, tier


# --- storing ---------------------------------------------------------------------

def store_division(conn, v, period_id, tax, today):
    key = division_key(v["voting_id"])
    own, combined, terms, tier = classify(tax, key, v.get("theme"), v.get("proposal"))
    conn.execute(
        "INSERT INTO ec_divisions (division_key, voting_id, period_id, session, voted_at, date, "
        "theme, proposal, yes, no, blank, abstain, own_areas, areas, matched_terms, tier, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET period_id=COALESCE(excluded.period_id, "
        "ec_divisions.period_id), session=excluded.session, voted_at=excluded.voted_at, "
        "date=excluded.date, theme=excluded.theme, proposal=excluded.proposal, "
        "yes=excluded.yes, no=excluded.no, blank=excluded.blank, abstain=excluded.abstain, "
        "own_areas=excluded.own_areas, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (key, v["voting_id"], period_id, v.get("session"), v.get("voted_at"), v.get("date"),
         v.get("theme"), v.get("proposal"), v.get("yes"), v.get("no"), v.get("blank"),
         v.get("abstain"), None if own is None else ec_store.dumps(own),
         None if combined is None else ec_store.dumps(combined), ec_store.dumps(terms), tier,
         today, today))
    return key, combined


def store_positions(conn, key, positions):
    conn.execute("DELETE FROM ec_votes WHERE division_key=?", (key,))
    conn.executemany(
        "INSERT OR REPLACE INTO ec_votes (division_key, name, name_key, position, seat) "
        "VALUES (?,?,?,?,?)", [(key,) + p for p in positions])
    conn.execute("UPDATE ec_divisions SET positions=? WHERE division_key=?",
                 (len(positions), key))


def totals_agree(conn, key, positions):
    """True when the detail's row count equals the vote's four totals (the
    detail lists only those who voted; measured equal on 15 of 15 samples)."""
    row = conn.execute("SELECT yes, no, blank, abstain FROM ec_divisions WHERE division_key=?",
                       (key,)).fetchone()
    if not row or any(x is None for x in row):
        return True
    return sum(row) == len(positions)


# --- pulling ---------------------------------------------------------------------

def pull_periods(conn, client, today, log=print):
    try:
        raw = client.get_bytes(PERIODS_URL, FEED, "periods")
    except FetchError as exc:
        _gap(conn, today, "periods: {0}".format(exc))
        log("  [gap] periods: {0}".format(str(exc)[:90]))
        return []
    periods = parse_periods(raw)
    if not periods:
        _gap(conn, today, "periods: the reply listed no period")
        log("  [gap] periods: the reply listed no period")
    return periods


def pull_votes(conn, client, today, period, tax=None, log=print, budget=None,
               index_only=False, limit=None, full=False):
    """List the period's votes from the last stored date (less REREAD_DAYS)
    to today, or the whole period on a first run or with full=True; then read
    every detail not yet stored. Returns (listed, stored, details read, gaps)."""
    pid, start, end = period
    gaps = 0
    last = conn.execute("SELECT MAX(date) FROM ec_divisions WHERE period_id=?",
                        (pid,)).fetchone()[0]
    window_start = start
    if last and not full:
        back = (datetime.date.fromisoformat(last) - datetime.timedelta(days=REREAD_DAYS)).isoformat()
        window_start = max(start, back)
    window_end = min(end or today, today)
    listed = stored = 0
    try:
        raw = client.get_bytes(VOTES_URL.format(period=pid, start=window_start, end=window_end),
                               FEED, "votes-{0}-{1}-{2}".format(pid, window_start, window_end))
        votes = parse_vote_list(raw)
    except FetchError as exc:
        _gap(conn, today, "vote list {0}..{1}: {2}".format(window_start, window_end, exc))
        log("  [gap] vote list {0}..{1}: {2}".format(window_start, window_end, str(exc)[:90]))
        votes, gaps = [], gaps + 1
    else:
        if votes is None:
            _gap(conn, today, "vote list {0}..{1}: the reply was not a list".format(
                window_start, window_end))
            log("  [gap] vote list {0}..{1}: the reply was not a list".format(
                window_start, window_end))
            votes, gaps = [], gaps + 1
    listed = len(votes)
    log("ec-rollcalls: period {0} ({1} to {2}): {3} vote(s) listed for {4}..{5}".format(
        pid, start, end, listed, window_start, window_end))
    for v in votes:
        store_division(conn, v, pid, tax, today)
        stored += 1
    conn.commit()
    details = attempts = 0
    if index_only:
        return listed, stored, details, gaps
    pending = conn.execute(
        "SELECT division_key, voting_id FROM ec_divisions WHERE period_id=? AND positions IS NULL "
        "ORDER BY date, voting_id", (pid,)).fetchall()
    for key, vid in pending:
        if limit is not None and attempts >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("vote details", details))
            break
        attempts += 1
        try:
            raw = client.get_bytes(DETAIL_URL.format(vid=vid), FEED, "detail-{0}".format(vid))
        except FetchError as exc:
            _gap(conn, today, "{0}: {1}".format(key, exc))
            log("  [gap] {0}: {1}".format(key, str(exc)[:90]))
            gaps += 1
            continue
        positions = parse_detail(raw)
        if not positions:
            _gap(conn, today, "{0}: the detail listed no position".format(key))
            log("  [gap] {0}: the detail listed no position".format(key))
            gaps += 1
            continue
        if not totals_agree(conn, key, positions):
            # Stored anyway (it is what the Asamblea published), but said.
            _gap(conn, today, "{0}: {1} position(s) against the vote's totals".format(
                key, len(positions)))
            log("  [gap] {0}: {1} position(s) do not add up to the vote's totals".format(
                key, len(positions)))
            gaps += 1
        store_positions(conn, key, positions)
        conn.commit()
        details += 1
    return listed, stored, details, gaps


def pull_members(conn, client, today, log=print):
    try:
        members = parse_members(client.get_bytes(MEMBERS_URL, FEED, "members"))
    except FetchError as exc:
        _gap(conn, today, "member register: {0}".format(exc))
        log("  [gap] member register: {0}".format(str(exc)[:90]))
        return 0, 1
    if not members:
        _gap(conn, today, "member register: the reply listed nobody")
        log("  [gap] member register: the reply listed nobody")
        return 0, 1
    conn.executemany(
        "INSERT INTO ec_members (member_id, name, name_key, first_seen, last_seen) "
        "VALUES (?,?,?,?,?) ON CONFLICT(member_id) DO UPDATE SET name=excluded.name, "
        "name_key=excluded.name_key, last_seen=excluded.last_seen",
        [m + (today, today) for m in members])
    conn.commit()
    return len(members), 0


def pull_roster(conn, client, today, log=print):
    try:
        roster = parse_roster(client.get_text(ROSTER_URL, FEED, "roster"))
    except FetchError as exc:
        _gap(conn, today, "roster page: {0}".format(exc))
        log("  [gap] roster page: {0}".format(str(exc)[:90]))
        return 0, 1
    if len(roster) < ROSTER_FLOOR:
        _gap(conn, today, "roster page: {0} member(s) parsed, under {1}; not stored".format(
            len(roster), ROSTER_FLOOR))
        log("  [gap] roster page: {0} member(s) parsed; the page changed shape".format(len(roster)))
        return len(roster), 1
    conn.executemany(
        "INSERT INTO ec_roster (name, name_key, constituency, party_slug, party, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET "
        "name_key=excluded.name_key, constituency=excluded.constituency, "
        "party_slug=excluded.party_slug, party=excluded.party, last_seen=excluded.last_seen",
        [r + (today, today) for r in roster])
    conn.commit()
    return len(roster), 0


def reclassify(conn, tax=None, log=print):
    """Re-derive every stored division's areas, offline, after a taxonomy or
    watchlist change."""
    changed = 0
    for key, theme, proposal, areas in conn.execute(
            "SELECT division_key, theme, proposal, areas FROM ec_divisions").fetchall():
        own, combined, terms, tier = classify(tax, key, theme, proposal)
        new_s = None if combined is None else ec_store.dumps(combined)
        changed += new_s != areas
        conn.execute("UPDATE ec_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (None if own is None else ec_store.dumps(own), new_s,
                      ec_store.dumps(terms), tier, key))
    conn.commit()
    log("ec-rollcalls: reclassified; {0} division(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = sum(on_our_ground(json.loads(a)) for (a,) in conn.execute(
        "SELECT areas FROM ec_divisions WHERE areas IS NOT NULL"))
    log("  store: {0} division(s), {1} on our ground, {2} unclassified, {3} awaiting "
        "positions; {4} position(s); {5} member(s) in the register, {6} on the roster".format(
            n("SELECT COUNT(*) FROM ec_divisions"), ours,
            n("SELECT COUNT(*) FROM ec_divisions WHERE areas IS NULL"),
            n("SELECT COUNT(*) FROM ec_divisions WHERE positions IS NULL"),
            n("SELECT COUNT(*) FROM ec_votes"), n("SELECT COUNT(*) FROM ec_members"),
            n("SELECT COUNT(*) FROM ec_roster")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", type=int, help="default: the one holding today")
    ap.add_argument("--full", action="store_true",
                    help="list the whole period, not just from the last stored date")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--taxonomy", help="classify with this taxonomy file "
                                       "(default config/taxonomy-ec.yaml when it exists)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--index-only", action="store_true",
                    help="list votes with their totals but read no details")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many vote details")
    args = ap.parse_args()
    tax = load_taxonomy(args.taxonomy)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    if tax is None:
        print("ec-rollcalls: no Spanish taxonomy yet (config/taxonomy-ec.yaml); "
              "areas stay NULL, only watchlist-ec lends areas")
    client = HttpClient(raw_dir=args.raw_dir, throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_votes:
        periods = pull_periods(conn, client, today)
        if not periods:
            gaps += 1
        else:
            if args.period is not None:
                period = next((p for p in periods if p[0] == args.period), None)
            else:
                period = current_period(periods, today)
            if period is None:
                _gap(conn, today, "period {0} is not listed".format(args.period))
                print("  [gap] period {0} is not listed".format(args.period))
                gaps += 1
            else:
                listed, stored, details, g = pull_votes(
                    conn, client, today, period, tax=tax, budget=budget,
                    index_only=args.index_only, limit=args.limit, full=args.full)
                gaps += g
                print("ec-rollcalls: {0} vote(s) stored, {1} detail(s) read, {2} gap(s)".format(
                    stored, details, g))
    if not args.no_members:
        n, g = pull_members(conn, client, today)
        gaps += g
        r, g2 = pull_roster(conn, client, today)
        gaps += g2
        print("ec-rollcalls: {0} register record(s), {1} roster member(s), {2} gap(s)".format(
            n, r, g + g2))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
