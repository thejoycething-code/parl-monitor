"""Canada (federal): a READER adapter over the ca_* tables, for the shared
country frameworks only (16 October 2026).

WHY A READER AND NOT AN EDITION. The Canada federal edition has rendered
its own document since 9 October 2026 (tools/ca_monitor.py, its own send
path and DM); nothing here changes it, and this module is NOT in
src/edition_review.OWN. The shared frameworks reach a country through its
adapter (src/country_edition.adapter): member profiles
(src/member_profiles.py), the public vote pages, tracker and bill timelines
(src/country_votes.py), the same-day vote briefs
(src/country_vote_brief.py) and the week-ahead table (src/agenda.py). This
adapter gives them Canada's items, from the store the Canada weekly
collects; ca_monitor.py reads the same rows its own way.

ITEMS: every recorded division on our ground, House of Commons
(tools/ca_rollcalls.py) and Senate (tools/ca_senate.py), with its tally,
the chamber's own word for the result, the split by caucus AT THE VOTE (the
House prints each member's caucus on the division itself; the Senate's vote
page each senator's affiliation), and the members who voted against their
caucus's majority; and the bills on our ground that were introduced, moved
a stage or had Royal Assent in the window. On our ground is the store's own
classification (the English taxonomy plus config/watchlist-ca.yaml, keyed
'<parl>-<sess>/<number>') or a watched bill key, never a keyword here.

A division's areas can be its bill's (a watched key, src/ca_store.
add_bill_key_areas): `own` says whether the division's subject alone
matched, re-read as tools/ca_monitor.own_areas does. Paired members place
nobody and are counted apart; independents and non-affiliated senators have
no caucus line to break and are never named against one.

THE WEEK AHEAD is src/agenda.py's shared table under cc='ca', filled by
tools/country_agenda.py ca from src/agendas/ca.py (House committee
meetings, the House's Projected Order of Business, the Senate's committee
schedule and Order Paper). tools/ca_monitor.py renders it in the countdown
layout (This week, Further afield); `week_ahead` here serves the frameworks.

READINGS (the vote pages): Canada's 5CA predates src/country5ca.py, so its
readings are config/ca_stance.yaml's own format, read with
src/readings5ca.py (the reader tools/ca_5ca.py and the US, Irish and
Australian briefs share). `READINGS` hands src/country_votes.py what
country5ca's Spec would: the store's divisions with tallies, the entries,
the position words, the labels. A reading is shown as confirmed only when
readings5ca.status says so; the file signs readings in its header (2, 8 and
10 October 2026, Christopher or on his delegation), not per entry, so the
page says that and gives no per-entry date.

Read-only on the store.
"""

from __future__ import annotations

import os
import re

from src import agenda
from src import country_edition as ce

CHAMBER = {"commons": "House of Commons", "senate": "Senate"}
POS_YES, POS_NO, POS_ABST = ("yea",), ("nay",), ("abstention",)
# Members with no caucus line to break, as the House and the Senate print them.
NO_LINE = ("Independent", "Non-affiliated", "Conservative Independent",
           "Independent Conservative")
FINAL = re.compile(r"\b(3rd|third) reading\b|concurrence in (the )?senate amendments|"
                   r"\bmessage from the (house of commons|senate)\b", re.I)
STANCE = os.path.join(ce.CONFIG, "ca_stance.yaml")


def bill_key(parliament, session, number):
    return "{0}-{1}/{2}".format(parliament, session, number) if number else None


def bill_url(parliament, session, number):
    return "https://www.parl.ca/legisinfo/en/bill/{0}-{1}/{2}".format(
        parliament, session, (number or "").lower())


def division_url(r):
    if r["chamber"] == "senate":
        return "https://sencanada.ca/en/in-the-chamber/votes/details/{0}/{1}-{2}".format(
            r["number"], r["parliament"], r["session"])
    return "https://www.ourcommons.ca/members/en/votes/{0}/{1}/{2}".format(
        r["parliament"], r["session"], r["number"])


def ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "{0}{1}".format(n, suffix)


_OWN = {}


def own_areas(text):
    """The visible areas a division's own subject matches, with no bill key
    (tools/ca_monitor.own_areas, the same taxonomy and watchlist)."""
    if "tax" not in _OWN:
        from src import filter as filt
        _OWN["tax"] = filt.load_taxonomy(os.path.join(ce.CONFIG, "taxonomy.yaml"))
        _OWN["wl"] = filt.load_watchlist(os.path.join(ce.CONFIG, "watchlist-ca.yaml"))
    if text not in _OWN:
        from src import filter as filt
        res = filt.filter_item(_OWN["tax"], _OWN["wl"], text or "")
        _OWN[text] = [a for a in (res.issue_areas or []) if a not in ce.HIDDEN_AREAS]
    return _OWN[text]


POSITIONS_SQL = ("SELECT v.person_id, COALESCE(m.name, s.name, v.person_id) AS name, v.party, "
                 "v.position FROM ca_votes v LEFT JOIN ca_members m ON m.person_id = v.person_id "
                 "LEFT JOIN ca_senators s ON s.person_id = v.person_id WHERE v.division_key = ?")


def positions(conn, key):
    """[(name, caucus at the vote, position)] for one division, as stored."""
    return [(r[1], r[2], r[3]) for r in ce.rows(conn, POSITIONS_SQL, (key,))]


def _votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT d.*, b.long_title, b.short_title FROM ca_divisions d "
                           "LEFT JOIN ca_bills b ON b.parliament = d.parliament AND "
                           "b.session = d.session AND b.number = d.bill_number WHERE "
                           + ce.window_sql("d.date"), (since, until)):
        bkey = bill_key(r["parliament"], r["session"], r["bill_number"])
        watched = bkey in wl if bkey else False
        if not ce.on_ground(r["areas"], watched):
            continue
        chamber = CHAMBER.get(r["chamber"], r["chamber"])
        abst = r["abstentions"] if "abstentions" in r.keys() else None
        lines = [ce.tally_line(r["yeas"], r["nays"], abst, r["result"],
                               "recorded division, {0}".format(chamber))]
        if r["paired"]:
            lines.append("Paired: {0} member(s), who place nobody.".format(r["paired"]))
        pairs = positions(conn, r["division_key"]) if r["positions_fetched"] else []
        reb = None
        if pairs:
            reb = ce.rebels(pairs, POS_YES, POS_NO, skip=NO_LINE)
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST),
                                       "By caucus at the vote"))
            lines.append(ce.members_line(len(pairs), reb,
                                         "Caucus or affiliation as the record names it at "
                                         "the vote."))
        else:
            lines.append("Member positions not read yet; the next Canada weekly run fetches "
                         "them.")
        if r["chamber"] == "senate":
            take = "Senate recorded vote, {0} Parliament, {1} session".format(
                ordinal(r["parliament"]), ordinal(r["session"]))
        else:
            take = "House of Commons division No. {0}, {1} Parliament, {2} session".format(
                r["number"], ordinal(r["parliament"]), ordinal(r["session"]))
        if r["bill_number"]:
            take += ", on Bill {0}".format(r["bill_number"])
        own = bool(own_areas(r["subject"]))
        out.append(ce.vote("ca", r["division_key"], r["date"], r["subject"],
                           ce.areas_of(r["areas"]), r["tier"], watched, lines,
                           url=division_url(r), terms=r["matched_terms"], takeaway=take,
                           own=own, group=bkey, group_title=r["long_title"],
                           final=bool(FINAL.search(r["subject"] or "")),
                           watch_key=bkey if watched else None,
                           refs=[r["long_title"]] if r["long_title"] else None,
                           positions=pairs or None, rebels=reb))
    return out


def _bill_takeaway(r, kind):
    bits = ["{0} {1}".format(r["bill_type"] or "Bill", r["number"])]
    if r["sponsor"]:
        bits.append("sponsor {0}".format(ce.clean(r["sponsor"])))
    if kind == "law":
        bits.append("Royal Assent {0}".format(ce.long_date(ce.day(r["royal_assent_at"]))))
    elif kind == "moved" and r["last_stage"]:
        bits.append("{0} completed {1}".format(ce.clean(r["last_stage"]),
                                              ce.long_date(ce.day(r["last_stage_at"]))))
    return "; ".join(bits)


def _bills(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM ca_bills WHERE ({0}) OR ({1}) OR ({2})".format(
            ce.window_sql("introduced_at"), ce.window_sql("last_stage_at"),
            ce.window_sql("royal_assent_at")), (since, until) * 3):
        watched = r["bill_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        if r["royal_assent_at"] and since < ce.day(r["royal_assent_at"]) <= until:
            kind, date = "law", r["royal_assent_at"]
        elif r["introduced_at"] and since < ce.day(r["introduced_at"]) <= until:
            kind, date = "new", r["introduced_at"]
        else:
            kind, date = "moved", r["last_stage_at"]
        out.append(ce.item("ca", kind, r["bill_key"], date,
                           r["short_title"] or r["long_title"], ce.areas_of(r["areas"]),
                           r["tier"], watched,
                           status="Royal Assent" if kind == "law" else r["status"],
                           url=bill_url(r["parliament"], r["session"], r["number"]),
                           terms=r["matched_terms"], takeaway=_bill_takeaway(r, kind)))
    return out


def items(conn, since, until, wl):
    return _bills(conn, since, until, wl) + _votes(conn, since, until, wl)


# --- the vote pages' readings (src/country_votes.py) -------------------------------

DIVISIONS_SQL = (
    "SELECT d.division_key AS key, d.chamber, d.date, d.subject AS question, "
    "b.long_title AS subject, d.areas, d.tier, d.yeas AS yes, d.nays AS no, "
    "d.abstentions AS abstain, d.paired, d.result, d.bill_number, "
    "CASE WHEN d.bill_number IS NOT NULL THEN d.parliament || '-' || d.session || '/' || "
    "d.bill_number END AS bill_key FROM ca_divisions d LEFT JOIN ca_bills b ON "
    "b.parliament = d.parliament AND b.session = d.session AND b.number = d.bill_number")


def store_divisions(conn):
    """Every division of the store as dicts, oldest first (country5ca.divisions' shape)."""
    rows_ = [dict(r) for r in ce.rows(conn, DIVISIONS_SQL)]
    rows_.sort(key=lambda r: (str(r.get("date") or ""), str(r["key"])))
    for r in rows_:
        r["date"] = str(r.get("date") or "")[:10]
    return rows_


def stance_entries(config_dir=None):
    """{division key: entry} from config/ca_stance.yaml, drafts included."""
    from src import readings5ca as r5
    path = os.path.join(config_dir, "ca_stance.yaml") if config_dir else STANCE
    return r5.load_stance(path, "divisions") if os.path.exists(path) else {}


def stance_status(entry):
    from src import readings5ca as r5
    return r5.status(entry)


SIGNED_BY = ("Christopher Joyce, in person or on his delegation, as config/ca_stance.yaml "
             "records (2, 8 and 10 October 2026)")


def signed(entry):
    """(by, on) for a confirmed reading: the entry's own stamp where it has
    one, else the file's header (it signs in batches, not per entry)."""
    return (ce.clean(entry.get("confirmed_by")) or SIGNED_BY,
            str(entry["confirmed_on"]) if entry.get("confirmed_on") else None)


def side(word):
    w = (word or "").strip().lower()
    return {"yea": "yea", "nay": "nay", "abstention": "abstain"}.get(w)


READINGS = {
    "divisions": store_divisions,
    "entries": stance_entries,
    "status": stance_status,
    "signed": signed,
    "side": side,
    "labels": ("Yea", "Nay"),
    "chambers": dict(CHAMBER),
    "note": ("House of Commons divisions record every member's position with the caucus "
             "printed on the division; Senate votes every senator's, with the affiliation "
             "the Senate's vote page names. Paired members place nobody. Positions are "
             "fetched for divisions on our ground."),
    "signing": ("config/ca_stance.yaml, applied by tools/ca_5ca.py; a reading is signed by "
                "deleting its draft line, as the file's header records"),
}


COUNTRY = ce.Country(
    cc="ca", name="Canada", chamber="House of Commons and Senate", language="English",
    taxonomies=(("taxonomy.yaml", None),),
    items=items, flag=":flag-ca:",
    week_ahead=agenda.week_ahead_fn("ca"), ahead_note=agenda.ahead_note_fn("ca"),
    members_note=("The House records every member's position with the caucus at the vote; "
                  "the Senate every senator's, with the affiliation at the vote"),
    coverage=("A reader for the shared frameworks (profiles, vote pages, vote briefs, the week "
              "ahead): the Canada federal edition itself is tools/ca_monitor.py.",),
)
