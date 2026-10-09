"""Italy: the Senato and the Camera dei Deputati, from the it_* tables
(src/it_store.py, tools/it_rollcalls.py).

Items: every bill reading on our ground (taxonomy-it for `it`, plus
config/watchlist-it.yaml by reading key, '19/S.1056'). A reading presented
in the window is new; an older one whose status changed in the window is a
stage move, with the Senate's own words for the status.

Votes: both chambers record every member's position (X15), with the group
at the vote, so each vote carries its tally, the outcome in the chamber's
own words, the group split and the members who voted against their group's
majority; nothing is derived. A bill's amendments, ordini del giorno and
final vote are one group, keyed on the reading, with the final vote
(`is_final`) as the decisive one. A Camera vote whose title names no bill
had its bill inferred by the collector (`bill_inferred`); its areas then
come from that bill, and the edition says so.

No agenda is collected, so there is no week ahead.
"""

from __future__ import annotations

import json

from src import country_edition as ce

POS_YES, POS_NO, POS_ABST = ("aye",), ("no",), ("abstain",)
CHAMBER = {"S": "Senato", "C": "Camera", "senato": "Senato", "camera": "Camera"}
# Independents and the mixed group have no group line to break.
NO_LINE = ("Misto", "MISTO", "Nessun gruppo")
NATURE = {
    "ordinaria": "Ordinary bill",
    "costituzionale": "Constitutional bill",
    "di conversione di decreto-legge": "Bill converting a decree-law",
    "di approvazione di bilancio": "Budget bill",
}


def bill_url(key, id_ddl=None):
    """The reading's page on its chamber's site."""
    leg, _, rest = (key or "").partition("/")
    chamber, _, number = rest.partition(".")
    if chamber == "S" and id_ddl:
        return "https://www.senato.it/leg/{0}/BGT/Schede/Ddliter/{1}.htm".format(leg, id_ddl)
    if chamber == "C" and number:
        return "https://www.camera.it/leg{0}/126?leg={0}&idDocumento={1}".format(
            leg, number.split("-")[0])
    return None


def _takeaway(r, new):
    bits = ["{0} {1} in the {2}".format(NATURE.get(r["nature"], "Bill"), r["bill_key"],
                                        CHAMBER.get(r["chamber"], r["chamber"]))]
    if r["initiative"]:
        bits.append("presented by {0}".format(ce.clean(r["initiative"])))
    if not new and r["status_date"]:
        bits.append("status changed on {0}".format(ce.long_date(ce.day(r["status_date"]))))
    if r["law"]:
        bits.append("enacted as {0}".format(r["law"]))
    return "; ".join(bits)


def _bills(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM it_bills WHERE ({0}) OR ({1})".format(
            ce.window_sql("presented"), ce.window_sql("status_date")),
            (since, until, since, until)):
        w = r["bill_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        new = since < ce.day(r["presented"]) <= until
        out.append(ce.item("it", "new" if new else "moved", r["bill_key"],
                           r["presented"] if new else r["status_date"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], w, status=r["status"],
                           url=bill_url(r["bill_key"], r["id_ddl"]), terms=r["matched_terms"],
                           takeaway=_takeaway(r, new)))
    return out


def _bill_keys(r):
    try:
        keys = json.loads(r["bill_keys"] or "[]")
    except (TypeError, ValueError):
        keys = []
    if r["bill_key"] and r["bill_key"] not in keys:
        keys.insert(0, r["bill_key"])
    return keys


def _votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT d.*, b.title AS bill_title, b.id_ddl FROM it_divisions d "
                           "LEFT JOIN it_bills b USING (bill_key) WHERE "
                           + ce.window_sql("d.date"), (since, until)):
        keys = _bill_keys(r)
        hit = next((k for k in keys if k in wl), None)
        w = hit is not None
        if not ce.on_ground(r["areas"], w):
            continue
        chamber = CHAMBER.get(r["chamber"], r["chamber"])
        lines = [ce.tally_line(r["ayes"], r["noes"], r["abstentions"], r["outcome"],
                               "electronic vote, {0}".format(chamber))]
        got = ce.rows(conn, "SELECT m.name, v.member_key, v.grp, v.position FROM it_votes v LEFT JOIN "
                            "it_members m USING (member_key) WHERE v.division_key=?",
                            (r["division_key"],))
        pairs = [(v["name"] or v["member_key"], v["grp"], v["position"]) for v in got]
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST), "By group"))
            lines.append(ce.members_line(len(pairs), ce.rebels(pairs, POS_YES, POS_NO,
                                                               skip=NO_LINE),
                                         "Groups as at the vote."))
        else:
            lines.append("Member positions not read yet; the next weekly run fetches them.")
        if r["bill_inferred"]:
            lines.append("The vote's title names no bill; the collector linked it to {0} by "
                         "its sitting.".format(r["bill_key"]))
        own = bool(ce.areas_of(r["own_areas"]))
        bill = r["bill_key"]
        take = "{0}, sitting {1}, vote {2}".format(chamber, r["sitting"], r["number"])
        if bill:
            take += ", on {0}".format(bill)
        out.append(ce.vote("it", r["division_key"], r["date"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], w, lines,
                           url=bill_url(bill, r["id_ddl"]) if bill else None,
                           terms=r["matched_terms"], takeaway=take, own=own,
                           group=bill or None, group_title=r["bill_title"],
                           final=bool(r["is_final"]), watch_key=hit, refs=keys or None))
    return out


def items(conn, since, until, wl):
    return _bills(conn, since, until, wl) + _votes(conn, since, until, wl)


COUNTRY = ce.Country(
    cc="it", name="Italy", chamber="Senato and Camera dei Deputati", language="Italian",
    taxonomies=(("taxonomy-it.yaml", "it"),),
    items=items, flag=":flag-it:",
    members_note=("Both chambers record every member's position, with the group at the vote; "
                  "nothing is derived"),
    coverage=("Bills of both chambers and every recorded vote come from dati.senato.it; the "
              "Camera's votes from Openpolis (IT2: dati.camera.it as backup is a later phase).",
              "Bill statuses are the Senate's own terse words ('assegnato (no esame)', 'esame "
              "in comm.'). A bill lapses with the 19th legislature (by October 2027).",
              "Regional councils are a later phase (IT3)."),
)
