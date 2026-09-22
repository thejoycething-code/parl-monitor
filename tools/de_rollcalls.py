#!/usr/bin/env python3
"""Bundestag namentliche Abstimmungen, with every member's position.

    python3 tools/de_rollcalls.py                  # the current legislature
    python3 tools/de_rollcalls.py --legislature 132
    python3 tools/de_rollcalls.py --dry-run

Source: abgeordnetenwatch.de's open API (no key). One call lists the
legislature's recorded votes; one call per NEW vote returns all ~630 member
positions with the member's Fraktion, so a completed vote is never refetched.

EVERY recorded vote is stored, matched or not. Volume is tiny -- 68 in the
current Bundestag, about 114 across all sixteen Landtage put together -- so
storing everything costs less than deciding badly which to keep, and the
watching list in the edition is the proof it was looked at.

Classification is against config/taxonomy-de.yaml, NEVER the English one,
which matched one useful vote in sixty-eight over this House. The German
lists are an AI first draft awaiting the German team, so an area here is a
weaker claim than an English one. A vote label is also terse
("Sportfoerdergesetz"), and the Drucksache linked from document_url is where
the subject actually lives -- so a label that matches nothing is expected,
and inherits its ground from the document later.

All seventeen parliaments: --parliament <id> for one, --all for every one
abgeordnetenwatch serves. Poll ids are a single global id space (probed
22 September 2026), so vote_id stays the primary key across all of them.

Separation guarantee: writes de_members, de_divisions and de_votes only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

API = "https://www.abgeordnetenwatch.de/api/v2"
PARLIAMENTS = API + "/parliaments?range_end=100"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-de.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-de.yaml")
BUDGET_S = drain.DEFAULT_S
BUNDESTAG = 5
PERIODS = (API + "/parliament-periods?parliament={0}&type=legislature"
                 "&sort_by=start_date_period&sort_direction=desc&range_end=4")
POLLS = API + "/polls?field_legislature={0}&range_end=999"
POLL = API + "/polls/{0}?related_data=votes"

# The Drucksache the House voted on lives in the intro's HTML, as the first
# dserver/dip link. Phase 3 reads its text the way src/eudoc.py reads an
# adopted text; phase 1 only records where it is.
DOC_LINK = re.compile(r'href="(https?://(?:dserver|dip)\.bundestag\.de/[^"]+)"')



# abgeordnetenwatch labels a mandate "Sanae Abdi (Bundestag 2025 - 2029)" and a
# fraction "SPD (Bundestag 2025 - 2029)": the legislature is welded onto both.
# Stored raw, every German member's NAME and PARTY carried that suffix, which
# broke any join on a name and would have printed "SPD (Bundestag 2025 - 2029)
# 2/1/0" in the edition's Fraktion splits. The period is already held in its
# own column, so the suffix is redundant as well as wrong.
PERIOD_SUFFIX = re.compile(r"\s*\((?:[^()]*\b(?:19|20)\d{2}\s*[-\u2013]\s*(?:19|20)\d{2}[^()]*)\)\s*$")


def clean_label(label):
    """The name or party, without the legislature abgeordnetenwatch welds on.

    Only a trailing bracket containing a YEAR RANGE is removed. A real name
    with brackets -- and German members do carry them -- is left alone.
    """
    return PERIOD_SUFFIX.sub("", (label or "").strip()).strip() or None


def current_legislature(client, parliament=BUNDESTAG):
    """(id, label) of one parliament's newest legislature, or (None, None)."""
    reply = client.get_json(PERIODS.format(parliament), "de-rollcalls",
                            "periods-{0}".format(parliament), archive=False)
    rows = (reply or {}).get("data") or []
    if not rows:
        return None, None
    return str(rows[0]["id"]), rows[0].get("label") or ""


def parliaments(client):
    """[(id, label)] for every parliament abgeordnetenwatch serves, minus the
    European Parliament, which tools/eu_rollcalls.py already covers properly
    from the Parliament's own data."""
    reply = client.get_json(PARLIAMENTS, "de-rollcalls", "parliaments", archive=False)
    out = []
    for p in (reply or {}).get("data") or []:
        label = p.get("label") or ""
        if "EU-Parlament" in label:
            continue
        out.append((str(p.get("id")), label))
    return sorted(out, key=lambda x: int(x[0]))


def classify(tax, wl, label, topics):
    """Areas for one vote, from its label and the API's own German topics."""
    text = " ".join([label or ""] + list(topics or []))
    return filt.filter_item(tax, wl, text)


def document_url(intro):
    hit = DOC_LINK.search(intro or "")
    return hit.group(1) if hit else None


def tally(votes):
    """{'yes': n, ...} counted from the member rows, not from any summary."""
    out = {"yes": 0, "no": 0, "abstain": 0, "no_show": 0}
    for v in votes:
        pos = v.get("vote")
        if pos in out:
            out[pos] += 1
    return out


def pull(conn, client, today, legislature=None, log=print, limit=None,
         parliament=BUNDESTAG, parliament_label=None, tax=None, wl=None,
         budget=None):
    """Store every recorded vote of one legislature. Returns (seen, new, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    if legislature is None:
        legislature, label = current_legislature(client, parliament)
        if legislature is None:
            log("  {0}: no legislature listed".format(parliament_label or parliament))
            return 0, 0, 0
        parliament_label = parliament_label or label
        log("de-rollcalls: {0}, legislature {1}".format(label, legislature))
    reply = client.get_json(POLLS.format(legislature), "de-rollcalls",
                            "polls-{0}".format(legislature), archive=False)
    polls = (reply or {}).get("data") or []
    # A ROW MISSING A COLUMN THE SCHEMA GAINED IS NOT DONE (22 September 2026).
    # Skipping a stored vote is what makes this cheap, and it is also why the
    # 68 votes collected before `parliament` existed would have kept their
    # NULL for ever: they were known, so nothing looked at them again. The EU
    # side learned this with `outcome` and needed a --refetch pass; here the
    # skip simply asks whether the row is complete.
    known = {r[0] for r in conn.execute(
        "SELECT vote_id FROM de_divisions WHERE parliament IS NOT NULL")}
    seen = new = gaps = ours = 0
    for p in polls:
        seen += 1
        vote_id = str(p.get("id"))
        if vote_id in known:
            continue
        if limit is not None and new >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("recorded votes", new))
            break
        try:
            detail = client.get_json(POLL.format(vote_id), "de-rollcalls",
                                     "poll-" + vote_id, archive=False)
        except (FetchError, ValueError) as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)", (today, "de-rollcalls",
                                            "{0}: {1}".format(vote_id, exc)))
            log("  [gap] poll {0}: {1}".format(vote_id, str(exc)[:70]))
            gaps += 1
            continue
        d = (detail or {}).get("data") or {}
        votes = (d.get("related_data") or {}).get("votes") or []
        counts = tally(votes)
        accepted = d.get("field_accepted")
        topics = [t.get("label") for t in (d.get("field_topics") or [])]
        res = classify(tax, wl, d.get("label"), topics)
        areas = res.issue_areas or []
        if areas:
            ours += 1
        conn.execute(
            "INSERT INTO de_divisions (vote_id, parliament, parliament_label, "
            "legislature, date, label, yes, no, abstain, absent, accepted, "
            "committee, topics, document_url, areas, matched_terms, tier, "
            "first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(vote_id) DO UPDATE SET label=excluded.label, "
            "yes=excluded.yes, no=excluded.no, abstain=excluded.abstain, "
            "absent=excluded.absent, accepted=excluded.accepted, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "tier=excluded.tier, last_seen=excluded.last_seen, "
            # A refetched row must COMPLETE itself, or narrowing the skip
            # above buys a fetch and writes nothing.
            "parliament=excluded.parliament, "
            "parliament_label=excluded.parliament_label",
            (vote_id, str(parliament), parliament_label, str(legislature),
             d.get("field_poll_date"),
             d.get("label"), counts["yes"], counts["no"], counts["abstain"],
             counts["no_show"],
             None if accepted is None else int(bool(accepted)),
             ((d.get("field_committees") or [{}])[0] or {}).get("label"),
             json.dumps(topics, ensure_ascii=False),
             document_url(d.get("field_intro")),
             json.dumps(areas), json.dumps(res.matched_terms or []), res.tier,
             today, today))
        for v in votes:
            mandate = v.get("mandate") or {}
            person = str(mandate.get("id") or "")
            if not person:
                continue
            fraction = (v.get("fraction") or {}).get("label")
            conn.execute(
                "INSERT INTO de_members (person_id, name, party, parliament, "
                "parliament_label, legislature, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?) "
                # parliament, parliament_label and legislature are set on
                # CONFLICT too. They were not, so the 637 members stored in
                # phase 1 -- before the column existed -- kept parliament NULL
                # for ever: every later run hit the conflict branch and never
                # filled it in. That is the same shape as the reclassify bug,
                # a collector skipping work it believes it has already done.
                "ON CONFLICT(person_id) DO UPDATE SET name=excluded.name, "
                "party=excluded.party, parliament=excluded.parliament, "
                "parliament_label=excluded.parliament_label, "
                "legislature=excluded.legislature, "
                "last_seen=excluded.last_seen",
                (person, clean_label(mandate.get("label")),
                 clean_label(fraction), str(parliament),
                 parliament_label, str(legislature), today, today))
            conn.execute(
                "INSERT OR REPLACE INTO de_votes (vote_id, person_id, position) "
                "VALUES (?,?,?)", (vote_id, person, v.get("vote")))
        new += 1
    conn.commit()
    if ours:
        log("  {0} of {1} new vote(s) on our ground".format(ours, new))
    return seen, new, gaps


def reclassify(conn, today, log=print, tax=None, wl=None):
    """Re-derive areas for votes already stored, offline.

    A collector only classifies what it sees again, and a stored vote is
    never refetched, so a taxonomy change reaches nothing without this. The
    Westminster precedent is tools/retag_items.py. No network, no API calls.
    """
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    changed = gained = lost = 0
    for r in conn.execute("SELECT vote_id, label, topics, areas FROM de_divisions").fetchall():
        before = json.loads(r[3] or "[]")
        res = classify(tax, wl, r[1], json.loads(r[2] or "[]"))
        after = res.issue_areas or []
        if after == before:
            continue
        changed += 1
        if after and not before:
            gained += 1
        if before and not after:
            lost += 1
        conn.execute("UPDATE de_divisions SET areas = ?, matched_terms = ?, "
                     "tier = ?, last_seen = ? WHERE vote_id = ?",
                     (json.dumps(after), json.dumps(res.matched_terms or []),
                      res.tier, today, r[0]))
    conn.commit()
    log("reclassify: {0} vote(s) changed, {1} newly on our ground, {2} dropped off"
        .format(changed, gained, lost))
    return changed, gained, lost


def repair_members(conn, today, log=print):
    """Clean labels already stored, and fill in the parliament that was never
    written (--repair-members).

    Two repairs, because a fix to the writer does NOTHING for rows already in
    the store and this collector deliberately skips votes it has seen -- so
    those members are never re-stamped by an ordinary run. Left alone, the
    bug is fixed for members we meet in future and permanent for everyone
    already here.

    PARLIAMENT IS DERIVED, NOT GUESSED: from the divisions the member actually
    voted in. A member with votes in one parliament gets that parliament; one
    with votes in several, or none, is left NULL, because a wrong parliament
    is worse than a missing one -- it would put a Landtag member in the
    Bundestag's Fraktion splits.
    """
    cleaned = 0
    for pid, name, party in conn.execute(
            "SELECT person_id, name, party FROM de_members").fetchall():
        fixed_name, fixed_party = clean_label(name), clean_label(party)
        if fixed_name != name or fixed_party != party:
            conn.execute("UPDATE de_members SET name = ?, party = ? WHERE "
                         "person_id = ?", (fixed_name, fixed_party, pid))
            cleaned += 1
    filled = ambiguous = 0
    rows = conn.execute(
        "SELECT v.person_id, COUNT(DISTINCT d.parliament) AS n, "
        "MIN(d.parliament) AS p, MIN(d.parliament_label) AS lbl "
        "FROM de_votes v JOIN de_divisions d ON d.vote_id = v.vote_id "
        "WHERE d.parliament IS NOT NULL GROUP BY v.person_id").fetchall()
    for pid, n, parliament, label in rows:
        if n != 1:
            ambiguous += 1
            continue
        cur = conn.execute("SELECT parliament FROM de_members WHERE "
                           "person_id = ?", (pid,)).fetchone()
        if cur and cur[0] in (None, ""):
            conn.execute("UPDATE de_members SET parliament = ?, "
                         "parliament_label = COALESCE(parliament_label, ?) "
                         "WHERE person_id = ?", (parliament, label, pid))
            filled += 1
    conn.commit()
    log("de-rollcalls repair: {0} label(s) cleaned, {1} member(s) given a "
        "parliament from their own votes, {2} left NULL (votes in more than "
        "one parliament).".format(cleaned, filled, ambiguous))
    return cleaned, filled, ambiguous


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", help="abgeordnetenwatch legislature id")
    ap.add_argument("--parliament", help="abgeordnetenwatch parliament id (5 = Bundestag)")
    ap.add_argument("--all", action="store_true",
                    help="every parliament abgeordnetenwatch serves: the Bundestag and the sixteen Landtage")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored votes, offline, after a taxonomy change")
    ap.add_argument("--repair-members", action="store_true",
                    help="clean stored member labels and fill the parliament "
                         "column from each member's own votes, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many NEW votes")
    ap.add_argument("--dry-run", action="store_true",
                    help="list the legislature and its vote count, store nothing")
    args = ap.parse_args()
    import datetime
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    if args.dry_run:
        leg, label = (args.legislature, "") if args.legislature else current_legislature(client)
        polls = (client.get_json(POLLS.format(leg), "de-rollcalls",
                                 "polls-{0}".format(leg), archive=False) or {}).get("data") or []
        print("de-rollcalls: legislature {0} {1}, {2} recorded vote(s)".format(leg, label, len(polls)))
        return 0
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    if args.reclassify:
        reclassify(conn, today)
        conn.close()
        return 0
    if args.repair_members:
        repair_members(conn, today)
        conn.close()
        return 0
    tax = filt.load_taxonomy(TAXONOMY)
    wl = filt.load_watchlist(WATCHLIST)
    budget = drain.Budget(args.budget_seconds)
    targets = ([(pid, label) for pid, label in parliaments(client)] if args.all
               else [(args.parliament or BUNDESTAG, None)])
    seen = new = gaps = 0
    for pid, label in targets:
        if budget.exhausted():
            print(budget.disclose("parliaments", len(targets)))
            break
        s1, n1, g1 = pull(conn, client, today, legislature=args.legislature,
                          limit=args.limit, parliament=pid,
                          parliament_label=label, tax=tax, wl=wl, budget=budget)
        seen, new, gaps = seen + s1, new + n1, gaps + g1
    print("de-rollcalls: {0} recorded vote(s) listed across {1} parliament(s), "
          "{2} new, {3} gap(s).".format(seen, len(targets), new, gaps))
    members = conn.execute("SELECT COUNT(*) FROM de_members").fetchone()[0]
    rows = conn.execute("SELECT COUNT(*) FROM de_votes").fetchone()[0]
    ours = conn.execute("SELECT COUNT(*) FROM de_divisions WHERE areas NOT IN ('[]','')"
                        " AND areas IS NOT NULL").fetchone()[0]
    print("  {0} member(s), {1} recorded position(s), {2} vote(s) on our ground."
          .format(members, rows, ours))
    print("  Matched against config/taxonomy-de.yaml, an AI first draft "
          "(docs/keyword-taxonomy-de.md): treat an area as provisional.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
