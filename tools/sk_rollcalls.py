#!/usr/bin/env python3
"""Slovakia, Národná rada SR: members, prints (tlače), recorded votes with
every member's position on our ground, and interpellations.

    python3 tools/sk_rollcalls.py                       # the current term
    python3 tools/sk_rollcalls.py --term 8              # an earlier one
    python3 tools/sk_rollcalls.py --dry-run             # count, store nothing
    python3 tools/sk_rollcalls.py --reclassify          # re-derive areas, offline
    python3 tools/sk_rollcalls.py --positions all       # every vote's positions (slow)
    python3 tools/sk_rollcalls.py --taxonomy draft.yaml # classify with another term list
    python3 tools/sk_rollcalls.py --db /tmp/sk.db       # anywhere but the store

PHASE 1 (9 October 2026); see docs/slovakia-scope.md. Two sources, both the
parliament's own, open and keyless:

  * www.nrsr.sk/opendata/1/sk/... -- a JSON API that is in the national
    open-data catalogue (data.slovensko.sk, publisher "Kancelária Národnej
    rady SR") but documented nowhere; the endpoints below were found there
    and by probing. Each answers in under seven seconds:
      MP/MembersOfParliament?termNr=9    194 members (150 seats + substitutes)
      MP/Clubs?termNr=9                  7 clubs
      Bill/Bills?termNr=9                1,551 prints, every type, one call
      Voting/Votings?termNr=9            4,606 votes with totals, one call (3 MB)
      Interpellation/Interpellations?termNr=9   358 interpellations
    The vote list carries totals but NOT positions.
  * www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=<id>
    -- one HTML page per vote, every member's position grouped by club.
    The only source of positions. It is SLOW: 1.7 to 96 seconds a page on
    9 October 2026, the same page at different hours. So positions are read
    only for votes on our ground (or every vote with --positions all, which
    would take days for a whole term), and the clock budget stops the drain
    cleanly; the next run resumes from what is still unread.

THE TITLE SAYS WHICH LAW, NOT WHAT FOR. A Slovak print is titled by the
act it amends ("...ktorým sa mení a dopĺňa zákon č. 36/2005 Z. z. o
rodine..."), so the taxonomy has to know the law numbers as well as the
words, and a constitutional amendment says nothing at all. That is what
config/watchlist-sk.yaml is for, applied by print KEY.

A VOTE IS CLASSIFIED WITH ITS PRINT, as in the US: `areas` is the vote's
own label plus the print's areas; `own_areas` keeps the first set apart.

THE TAXONOMY IS NOT YET APPROVED. config/taxonomy-sk.yaml is generated only
after Christopher signs off the term list proposed in the scope doc. Until
then this runs with NO terms: everything is stored, only watchlist prints
are on our ground, and only their votes get positions. --taxonomy points it
at a draft for measuring.

CHECKED, NOT TRUSTED. A vote page whose positions do not add up to the
totals in the open data is stored and recorded as a gap. A page with no
position table (a secret ballot, an ID that is not a vote) stores nothing.

Separation guarantee: writes sk_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
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

from src import db, drain, filter as filt, sk_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "sk-rollcalls"
CURRENT_TERM = 9
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-sk.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "sk"
OPENDATA = "https://www.nrsr.sk/opendata/1/sk/"
VOTE_PAGE = "https://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID={0}"
BUDGET_S = drain.DEFAULT_S
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)
NO_CLUB = "Poslanci, ktorí nie sú členmi poslaneckých klubov"

_CELL = re.compile(
    r'<td>\[(.)\]\s*<a href="Default\.aspx\?sid=poslanci/poslanec&amp;PoslanecID=(\d+)'
    r'&amp;CisObdobia=(\d+)">([^<]*)</a></td>')
_BLOCK = re.compile(r'<td class="hpo_result_block_title"[^>]*>([^<]*)</td>')


# --- helpers -----------------------------------------------------------------

def bill_key(term, tlac):
    tlac = (str(tlac) if tlac is not None else "").strip()
    return "{0}/{1}".format(int(term), tlac) if tlac else None


def iso_date(value):
    """'2023-10-25T00:00:00' -> '2023-10-25'; the time is kept when it says
    something ('2026-10-06T18:44:40')."""
    if not value:
        return None
    return value[:10] if value.endswith("T00:00:00") else value


def empty_taxonomy():
    return filt.Taxonomy(version="none", terms={}, exclusions=set())


def empty_watchlist():
    """The Slovak watchlist is applied by KEY (sk_store.add_watch_areas), so
    the filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def load_taxonomy(path=None):
    """The approved Slovak taxonomy, or none at all. Never the English one:
    on 9 October 2026 it matched 1 of 1,551 Slovak prints."""
    path = path or TAXONOMY
    return filt.load_taxonomy(path, country=TAXONOMY_COUNTRY) if os.path.exists(path) else empty_taxonomy()


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def _od(client, path, slug):
    return client.get_json(OPENDATA + path, FEED, slug)


# --- members -------------------------------------------------------------------

def parse_members(records):
    out = []
    for r in records or []:
        if r.get("mpId") is None:
            continue
        out.append({"mp_id": int(r["mpId"]), "name": r.get("name"),
                    "first_name": r.get("firstname"), "last_name": r.get("lastName"),
                    "party": r.get("partyDepartmentName"), "club": r.get("lastClubAbbr"),
                    "club_id": r.get("lastClubId"), "region": r.get("addressRegion"),
                    "term": r.get("termNr")})
    return out


def store_member(conn, m, today):
    conn.execute(
        "INSERT INTO sk_members (mp_id, name, first_name, last_name, party, club, club_id, "
        "region, term, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(mp_id) DO UPDATE SET name=COALESCE(excluded.name, sk_members.name), "
        "first_name=COALESCE(excluded.first_name, sk_members.first_name), "
        "last_name=COALESCE(excluded.last_name, sk_members.last_name), "
        "party=CASE WHEN excluded.term >= COALESCE(sk_members.term, 0) "
        "THEN COALESCE(excluded.party, sk_members.party) ELSE sk_members.party END, "
        "club=CASE WHEN excluded.term >= COALESCE(sk_members.term, 0) "
        "THEN COALESCE(excluded.club, sk_members.club) ELSE sk_members.club END, "
        "club_id=CASE WHEN excluded.term >= COALESCE(sk_members.term, 0) "
        "THEN COALESCE(excluded.club_id, sk_members.club_id) ELSE sk_members.club_id END, "
        "region=COALESCE(excluded.region, sk_members.region), "
        "term=MAX(COALESCE(excluded.term, 0), COALESCE(sk_members.term, 0)), "
        "last_seen=excluded.last_seen",
        (m["mp_id"], m["name"], m["first_name"], m["last_name"], m["party"], m["club"],
         m["club_id"], m["region"], m["term"], today, today))


def pull_members(conn, client, today, term=CURRENT_TERM):
    members = parse_members(_od(client, "MP/MembersOfParliament?termNr={0}".format(term),
                                "members-{0}".format(term)))
    for m in members:
        store_member(conn, m, today)
    conn.commit()
    return len(members)


# --- prints (tlače) -------------------------------------------------------------

def parse_bills(records):
    out = []
    for r in records or []:
        if not r.get("billNr") or r.get("termNr") is None:
            continue
        out.append({"term": int(r["termNr"]), "tlac": str(r["billNr"]).strip(),
                    "od_id": r.get("id"), "type_id": r.get("typeId"),
                    "type_name": r.get("typeName"), "title": (r.get("description") or "").strip(),
                    "delivered": iso_date(r.get("deliveryDate"))})
    return out


def classify_bill(tax, wl, b):
    key = bill_key(b["term"], b["tlac"])
    res = filt.filter_item(tax, wl, b.get("title") or "")
    return sk_store.add_watch_areas(res, key)


def store_bill(conn, b, res, today):
    key = bill_key(b["term"], b["tlac"])
    conn.execute(
        "INSERT INTO sk_bills (bill_key, term, tlac, od_id, type_id, type_name, title, delivered, "
        "areas, matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET od_id=excluded.od_id, type_id=excluded.type_id, "
        "type_name=excluded.type_name, title=excluded.title, delivered=excluded.delivered, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (key, b["term"], b["tlac"], b["od_id"], b["type_id"], b["type_name"], b["title"],
         b["delivered"], sk_store.dumps(res.issue_areas),
         sk_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier,
         today, today))
    return key


def pull_bills(conn, client, today, term=CURRENT_TERM, tax=None, wl=None):
    tax = tax if tax is not None else load_taxonomy()
    wl = wl if wl is not None else empty_watchlist()
    bills = parse_bills(_od(client, "Bill/Bills?termNr={0}".format(term), "bills-{0}".format(term)))
    ours = 0
    for b in bills:
        res = classify_bill(tax, wl, b)
        store_bill(conn, b, res, today)
        ours += on_our_ground(res.issue_areas)
    conn.commit()
    return len(bills), ours


# --- votes ---------------------------------------------------------------------

def parse_votings(records):
    out = []
    for r in records or []:
        if r.get("id") is None or r.get("termNr") is None:
            continue
        out.append({"voting_id": int(r["id"]), "term": int(r["termNr"]),
                    "meeting": r.get("meetingNr"), "number": r.get("votingNr"),
                    "date": iso_date(r.get("date")), "name": (r.get("name") or "").strip(),
                    "tlac": (r.get("billNr") or "").strip() or None,
                    "vote_type": r.get("typeName"), "is_secret": bool(r.get("isSecretVoting")),
                    "is_constitutional": bool(r.get("isConstitutionalLaw")),
                    "result": r.get("stateName"), "present": r.get("countPresent"),
                    "agreed": r.get("countAgreed"), "disagreed": r.get("countDisagreed"),
                    "abstained": r.get("countAbstained"), "not_voting": r.get("countNotVoting"),
                    "absent": r.get("countNotPresent")})
    return out


def _bill_areas(conn, key):
    if not key:
        return []
    row = conn.execute("SELECT areas FROM sk_bills WHERE bill_key=?", (key,)).fetchone()
    return json.loads(row[0] or "[]") if row else []


def classify_division(tax, wl, v, bill_areas):
    """(own FilterResult, combined areas). The print lends its areas."""
    own = filt.filter_item(tax, wl, v.get("name") or "")
    return own, sorted(set(own.issue_areas or []) | set(bill_areas or []))


def store_division(conn, v, tax, wl, today):
    bkey = bill_key(v["term"], v["tlac"])
    own, areas = classify_division(tax, wl, v, _bill_areas(conn, bkey))
    conn.execute(
        "INSERT INTO sk_divisions (voting_id, term, meeting, number, date, name, bill_key, "
        "vote_type, is_secret, is_constitutional, result, present, agreed, disagreed, abstained, "
        "not_voting, absent, own_areas, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(voting_id) DO UPDATE SET name=excluded.name, bill_key=excluded.bill_key, "
        "result=excluded.result, present=excluded.present, agreed=excluded.agreed, "
        "disagreed=excluded.disagreed, abstained=excluded.abstained, "
        "not_voting=excluded.not_voting, absent=excluded.absent, own_areas=excluded.own_areas, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (v["voting_id"], v["term"], v["meeting"], v["number"], v["date"], v["name"], bkey,
         v["vote_type"], int(v["is_secret"]), int(v["is_constitutional"]), v["result"],
         v["present"], v["agreed"], v["disagreed"], v["abstained"], v["not_voting"], v["absent"],
         sk_store.dumps(own.issue_areas), sk_store.dumps(areas),
         sk_store.dumps(own.matched_terms), own.tier, today, today))
    return areas


def pull_votings(conn, client, today, term=CURRENT_TERM, tax=None, wl=None):
    """Every vote of the term, in one call, re-stamped every run."""
    tax = tax if tax is not None else load_taxonomy()
    wl = wl if wl is not None else empty_watchlist()
    votes = parse_votings(_od(client, "Voting/Votings?termNr={0}".format(term),
                              "votings-{0}".format(term)))
    ours = 0
    for v in votes:
        ours += on_our_ground(store_division(conn, v, tax, wl, today))
    conn.commit()
    return len(votes), ours


def parse_vote_page(text):
    """Every member's position from a hlasklub page, as a list of
    {mp_id, position, club, name, term}. None when the page has no position
    table at all (a secret ballot, or an ID that is not a vote)."""
    if not text or "hpo_result_table" not in text:
        return None
    start = text.index("hpo_result_table")
    end = text.find("</table>", start)
    body = text[start:end if end > 0 else len(text)]
    out, club = [], None
    marks = sorted([(m.start(), "club", m) for m in _BLOCK.finditer(body)]
                   + [(m.start(), "cell", m) for m in _CELL.finditer(body)], key=lambda x: x[0])
    for _pos, kind, m in marks:
        if kind == "club":
            title = html.unescape(m.group(1)).strip()
            club = None if title == NO_CLUB else re.sub(r"^Klub\s+", "", title)
            continue
        code, mp_id, term, name = m.groups()
        out.append({"mp_id": int(mp_id), "position": code, "club": club,
                    "name": html.unescape(name).strip(), "term": int(term)})
    return out or None


def tally(positions):
    counts = {}
    for p in positions:
        counts[p["position"]] = counts.get(p["position"], 0) + 1
    return counts


def check_totals(positions, row):
    """Differences between the page's positions and the open data's totals,
    as a list of strings; empty when they agree.

    The absent count is NOT checked: the open data's countNotPresent is
    wrong on 568 of the term's 4,570 open votes (present + absent comes to
    152, 149 or 148 seats, never 150; measured 9 October 2026). Present
    always equals for + against + abstained + not voting, so those four are
    the check."""
    c = tally(positions)
    pairs = (("Z", "agreed"), ("P", "disagreed"), ("?", "abstained"), ("N", "not_voting"))
    return ["{0} page {1} != open data {2}".format(code, c.get(code, 0), row[col])
            for code, col in pairs if row[col] is not None and c.get(code, 0) != row[col]]


def store_positions(conn, voting_id, positions, today):
    for p in positions:
        conn.execute("INSERT OR IGNORE INTO sk_members (mp_id, name, term, first_seen, last_seen) "
                     "VALUES (?,?,?,?,?)", (p["mp_id"], p["name"], p["term"], today, today))
        conn.execute("INSERT OR REPLACE INTO sk_votes (voting_id, mp_id, position, club) "
                     "VALUES (?,?,?,?)", (voting_id, p["mp_id"], p["position"], p["club"]))
    conn.execute("UPDATE sk_divisions SET positions_at=? WHERE voting_id=?", (today, voting_id))


def pending_positions(conn, term, everything=False):
    """Votes whose positions are still unread, newest first: on our ground
    only, unless everything. Secret ballots have none to read."""
    rows = conn.execute(
        "SELECT voting_id, areas, agreed, disagreed, abstained, not_voting, absent "
        "FROM sk_divisions WHERE term=? AND positions_at IS NULL AND is_secret=0 "
        "ORDER BY voting_id DESC", (term,)).fetchall()
    cols = ("voting_id", "areas", "agreed", "disagreed", "abstained", "not_voting", "absent")
    out = [dict(zip(cols, r)) for r in rows]
    ours = [r for r in out if on_our_ground(json.loads(r["areas"] or "[]"))]
    if everything:
        # X15 (10 October 2026): every position, but our ground first, so the
        # backlog of the rest never delays a vote that matters.
        return ours + [r for r in out if r not in ours]
    return ours


def pull_positions(conn, client, today, term=CURRENT_TERM, everything=False, budget=None,
                   limit=None, log=print):
    """Read the vote pages still owed. Returns (read, gaps)."""
    read = gaps = 0
    for row in pending_positions(conn, term, everything):
        if limit is not None and read >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("vote pages", read))
            break
        vid = row["voting_id"]
        try:
            text = client.get_text(VOTE_PAGE.format(vid), FEED, "vote-{0}".format(vid))
        except FetchError as exc:
            _gap(conn, today, "vote {0}: {1}".format(vid, exc))
            log("  [gap] vote {0}: {1}".format(vid, str(exc)[:70]))
            gaps += 1
            continue
        positions = parse_vote_page(text)
        if positions is None:
            _gap(conn, today, "vote {0}: page carried no positions".format(vid))
            log("  [gap] vote {0}: page carried no positions".format(vid))
            gaps += 1
            continue
        diff = check_totals(positions, row)
        if diff:
            # Stored all the same: the page is the only source of positions.
            _gap(conn, today, "vote {0}: positions disagree with totals ({1})".format(
                vid, "; ".join(diff)))
            log("  [gap] vote {0}: {1}".format(vid, "; ".join(diff)))
            gaps += 1
        store_positions(conn, vid, positions, today)
        conn.commit()
        read += 1
    return read, gaps


# --- interpellations ------------------------------------------------------------

def parse_interpellations(records):
    out = []
    for r in records or []:
        if r.get("id") is None:
            continue
        out.append({"int_id": int(r["id"]), "term": r.get("termNr"),
                    "subject": (r.get("description") or "").strip(),
                    "questioner": r.get("questionerPersonName"),
                    "addressee": r.get("addresseePostName"), "state": r.get("stateName"),
                    "submitted": iso_date(r.get("submissionDateInt")),
                    "answered": iso_date(r.get("answerDeliveryDate")),
                    "satisfactory": (None if r.get("isAnswerSatisfactory") is None
                                     else int(bool(r.get("isAnswerSatisfactory"))))})
    return out


def store_interpellation(conn, i, res, today):
    conn.execute(
        "INSERT INTO sk_interpellations (int_id, term, subject, questioner, addressee, state, "
        "submitted, answered, satisfactory, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(int_id) DO UPDATE SET "
        "subject=excluded.subject, state=excluded.state, answered=excluded.answered, "
        "satisfactory=excluded.satisfactory, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (i["int_id"], i["term"], i["subject"], i["questioner"], i["addressee"], i["state"],
         i["submitted"], i["answered"], i["satisfactory"], sk_store.dumps(res.issue_areas),
         sk_store.dumps(res.matched_terms), res.tier, today, today))


def pull_interpellations(conn, client, today, term=CURRENT_TERM, tax=None, wl=None):
    tax = tax if tax is not None else load_taxonomy()
    wl = wl if wl is not None else empty_watchlist()
    items = parse_interpellations(_od(client, "Interpellation/Interpellations?termNr={0}".format(
        term), "interpellations-{0}".format(term)))
    ours = 0
    for i in items:
        res = filt.filter_item(tax, wl, i["subject"])
        store_interpellation(conn, i, res, today)
        ours += on_our_ground(res.issue_areas)
    conn.commit()
    return len(items), ours


# --- offline -------------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    """Re-derive print, vote and interpellation areas, offline, after a
    taxonomy or watchlist change. Prints first: votes inherit from them. A
    vote newly on our ground has positions_at NULL and is read next run."""
    tax = tax if tax is not None else load_taxonomy()
    wl = empty_watchlist()
    changed_b = changed_d = 0
    for (key, term, tlac, title, areas) in conn.execute(
            "SELECT bill_key, term, tlac, title, areas FROM sk_bills").fetchall():
        res = classify_bill(tax, wl, {"term": term, "tlac": tlac, "title": title})
        new = sk_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE sk_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (new, sk_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for (vid, bkey, name, areas) in conn.execute(
            "SELECT voting_id, bill_key, name, areas FROM sk_divisions").fetchall():
        own, combined = classify_division(tax, wl, {"name": name}, _bill_areas(conn, bkey))
        new = sk_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE sk_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE voting_id=?", (sk_store.dumps(own.issue_areas), new,
                                           sk_store.dumps(own.matched_terms), own.tier, vid))
    for (iid, subject) in conn.execute("SELECT int_id, subject FROM sk_interpellations").fetchall():
        res = filt.filter_item(tax, wl, subject or "")
        conn.execute("UPDATE sk_interpellations SET areas=?, matched_terms=?, tier=? "
                     "WHERE int_id=?", (sk_store.dumps(res.issue_areas),
                                        sk_store.dumps(res.matched_terms), res.tier, iid))
    conn.commit()
    log("sk-rollcalls: reclassified; {0} print(s) and {1} vote(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} print(s), {1} on our ground; {2} vote(s), {3} on our ground, {4} with "
        "positions; {5} member(s), {6} position(s); {7} interpellation(s), {8} on our ground".format(
            n("SELECT COUNT(*) FROM sk_bills"), ours("sk_bills"),
            n("SELECT COUNT(*) FROM sk_divisions"), ours("sk_divisions"),
            n("SELECT COUNT(*) FROM sk_divisions WHERE positions_at IS NOT NULL"),
            n("SELECT COUNT(*) FROM sk_members"), n("SELECT COUNT(*) FROM sk_votes"),
            n("SELECT COUNT(*) FROM sk_interpellations"), ours("sk_interpellations")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--term", type=int, default=CURRENT_TERM)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--taxonomy", help="term list to classify with (default: config/taxonomy-sk.yaml "
                                       "when it exists, otherwise none)")
    # X15 (Chris, 10 October 2026): store every member position. "all" reads
    # our ground first, then the rest as the budget allows, week by week.
    ap.add_argument("--positions", choices=("ours", "all", "none"), default="all",
                    help="which votes' per-member pages to read (default: ours)")
    ap.add_argument("--no-interpellations", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored prints, votes and interpellations, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many vote pages")
    ap.add_argument("--dry-run", action="store_true",
                    help="read the vote list and count, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    # The web pages are slow, not fragile: a full second between them costs
    # little against pages that take a minute.
    client.set_host_throttle("www.nrsr.sk", 1.0)
    today = datetime.date.today().isoformat()
    tax = load_taxonomy(args.taxonomy)
    if args.dry_run:
        votes = parse_votings(client.get_json(OPENDATA + "Voting/Votings?termNr={0}".format(
            args.term), FEED, "dry", archive=False))
        print("sk-rollcalls: term {0}: {1} vote(s), newest {2}; taxonomy {3}".format(
            args.term, len(votes), max((v["date"] or "" for v in votes), default="-"),
            tax.version))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    print("sk-rollcalls: taxonomy {0}".format(tax.version))
    print("sk-rollcalls: {0} member(s)".format(pull_members(conn, client, today, args.term)))
    read, ours = pull_bills(conn, client, today, args.term, tax, wl)
    print("sk-rollcalls: {0} print(s), {1} on our ground".format(read, ours))
    read, ours = pull_votings(conn, client, today, args.term, tax, wl)
    print("sk-rollcalls: {0} vote(s), {1} on our ground".format(read, ours))
    if not args.no_interpellations:
        read, ours = pull_interpellations(conn, client, today, args.term, tax, wl)
        print("sk-rollcalls: {0} interpellation(s), {1} on our ground".format(read, ours))
    if args.positions != "none":
        read, g = pull_positions(conn, client, today, args.term,
                                 everything=args.positions == "all", budget=budget,
                                 limit=args.limit)
        gaps += g
        print("sk-rollcalls: {0} vote page(s) read, {1} gap(s)".format(read, g))
    summary(conn)
    conn.close()
    # 3 = stored what it could and recorded gaps (jobs/sk-weekly.sh publishes it).
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
