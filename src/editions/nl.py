"""The Netherlands: the Tweede Kamer's votes, from the nl_* tables
(src/nl_store.py, tools/nl_rollcalls.py).

VOTES FIRST (NL3, Chris, 10 October 2026: the DM carries votes only). The
store holds the zaken the Kamer voted on, so the edition is its votes on our
ground: motions, amendments and bills, each with the Kamer's own words for
the result, the seats for and against and the fracties on each side. Since
parity layer 5 (10 October 2026) the edition also carries what was said in
the plenary and the Kamervragen on our ground (tools/nl_chamber.py,
src/chamber_store.py); the DM stays votes only.

A show of hands records one position per fractie; per X5 each member is
given their fractie's position and the edition says so, DERIVED, with the
fractie at the member's latest sighting (nl_store.derived_member_positions).
A hoofdelijke stemming (roll call) records every member, and the edition
names any who voted against their fractie's majority.

Amendments and the bill they amend are one group (the dossier), with the
bill's own vote as the decisive one; motions stand alone, since motions
filed in one dossier are separate questions.

THE EERSTE KAMER (NL4, added 10 October 2026): its votes on our ground from
the nl_ek_* tables (tools/nl_eerstekamer.py, read from eerstekamer.nl's vote
pages), in the same section, each titled as the Senate prints it and said
to be the Eerste Kamer's. A show of hands names the fracties for and
against; nothing is derived for members (the collector reads no member
list). A roll call names every senator with their fractie at the vote. A
hamerstuk passed without a vote, with any fracties that asked for their
dissent to be recorded.
"""

from __future__ import annotations

import json

from src import agenda
from src import country_edition as ce
from src import nl_store

SOORT = {"Motie": "Motion", "Amendement": "Amendment", "Wetgeving": "Bill",
         "Initiatiefwetgeving": "Members' bill", "Verzoekschrift": "Petition",
         "Brief regering": "Government letter"}
BILLS = ("Wetgeving", "Initiatiefwetgeving")


def zaak_url(nummer):
    return "https://www.tweedekamer.nl/zoeken?qry={0}".format(nummer)


def _sides(conn, besluit_id):
    sides = {"Voor": [], "Tegen": []}
    for v in ce.rows(conn, "SELECT fractie, position, zetels FROM nl_votes WHERE besluit_id=? "
                           "AND kind='fractie' ORDER BY zetels DESC, fractie", (besluit_id,)):
        if v["position"] in sides:
            sides[v["position"]].append("{0} ({1})".format(v["fractie"], v["zetels"])
                                        if v["zetels"] else v["fractie"])
    return sides


EK = "Eerste Kamer"


def _ek_watched(dossier, wl):
    """'36945-I' is watched as itself or as '36945'."""
    if not dossier:
        return None
    for k in (dossier, dossier.split("-")[0]):
        if k in wl:
            return k
    return None


def eerste_kamer(conn, since, until, wl):
    """The Eerste Kamer's votes on our ground in the window (NL4)."""
    out = []
    bill_titles = {r["dossier"]: r["title"] for r in
                   ce.rows(conn, "SELECT dossier, title FROM nl_ek_bills")}
    for r in ce.rows(conn, "SELECT * FROM nl_ek_divisions WHERE " + ce.window_sql("date"),
                     (since, until)):
        hit = _ek_watched(r["dossier"], wl)
        if not ce.on_ground(r["areas"], hit is not None):
            continue
        sides = ce.rows(conn, "SELECT kind, actor, fractie, position FROM nl_ek_votes "
                              "WHERE division_key=? ORDER BY actor", (r["division_key"],))
        method = r["method"] or "vote"
        if r["roll_call"]:
            pairs = [(v["actor"], v["fractie"], v["position"]) for v in sides
                     if v["kind"] == "lid"]
            lines = [ce.tally_line(r["voor"], r["tegen"], None, r["result"],
                                   "Eerste Kamer, roll call, senators"),
                     ce.split_line(ce.group_counts([(f, p) for _, f, p in pairs],
                                                   ("voor",), ("tegen",), ()), "By fractie"),
                     ce.members_line(len(pairs), ce.rebels(pairs, ("voor",), ("tegen",)),
                                     "Fracties as printed at the vote.")]
        elif method.lower() == "hamerstuk":
            noted = [v["actor"] for v in sides if v["position"] == "aantekening"]
            lines = ["Passed as a hamerstuk, without a vote; result as recorded: “{0}”.".format(
                r["result"] or "aangenomen")]
            if noted:
                lines.append("Asked for their dissent to be recorded (aantekening): {0}.".format(
                    ", ".join(noted)))
        else:
            voor = [v["actor"] for v in sides if v["position"] == "voor"]
            tegen = [v["actor"] for v in sides if v["position"] == "tegen"]
            lines = ["Eerste Kamer, {0}; result as recorded: “{1}”.".format(
                         method[0].lower() + method[1:], r["result"] or "?"),
                     ce.side_line(voor, tegen, "By fractie"),
                     "No member positions: a show of hands records fracties only, and none "
                     "are derived for the Eerste Kamer." if voor or tegen else None]
        what = {"bill": "Bill", "motion": "Motion", "amendment": "Amendment"}.get(
            r["kind"], "Item")
        take = "{0}: {1} {2}".format(EK, what, r["ref"])
        if r["kind"] != "bill" and r["dossier"]:
            take += ", in dossier {0}".format(r["dossier"])
        out.append(ce.vote("nl", r["division_key"], r["date"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], hit is not None, lines,
                           url=r["url"], terms=r["matched_terms"], takeaway=ce.clip(take, 260),
                           group="ek-" + r["dossier"] if r["kind"] != "motion" and r["dossier"]
                           else None,
                           group_title=(bill_titles.get(r["dossier"]) or
                                        "{0}: {1}".format(EK, r["dossier"]))
                           if r["kind"] != "motion" and r["dossier"] else None,
                           final=r["kind"] == "bill", own=bool(ce.areas_of(r["own_areas"])),
                           watch_key=hit))
    return out


def items(conn, since, until, wl):
    return tweede_kamer(conn, since, until, wl) + eerste_kamer(conn, since, until, wl)


def tweede_kamer(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT d.*, z.soort, z.onderwerp, z.titel, z.dossiers, "
                           "z.dossier_titels, z.own_areas, z.matched_terms, z.tier "
                           "FROM nl_divisions d JOIN nl_zaken z USING (zaak_nummer) WHERE "
                           + ce.window_sql("d.date"), (since, until)):
        dossiers = json.loads(r["dossiers"] or "[]")
        titles = json.loads(r["dossier_titels"] or "[]")
        hit = r["zaak_nummer"] if r["zaak_nummer"] in wl else \
            next((k for k in dossiers if k in wl), None)
        w = hit is not None
        if not ce.on_ground(r["areas"], w):
            continue
        roll = (r["stemmingssoort"] or "").lower().startswith("hoofdelijk")
        lines = [ce.tally_line(r["voor"], r["tegen"], None, r["besluit_tekst"],
                               "roll call, members" if roll else "show of hands, seats")]
        if r["positions_pending"]:
            lines.append("Positions not yet published by the Kamer; the result stands.")
        elif roll:
            got = ce.rows(conn, "SELECT actor, fractie, position FROM nl_votes WHERE besluit_id=? "
                                "AND kind='lid'", (r["besluit_id"],))
            pairs = [(v["actor"], v["fractie"], v["position"]) for v in got]
            lines.append(ce.split_line(ce.group_counts([(f, p) for _, f, p in pairs],
                                                       ("voor",), ("tegen",), ()), "By fractie"))
            lines.append(ce.members_line(len(pairs), ce.rebels(pairs, ("voor",), ("tegen",))))
        else:
            sides = _sides(conn, r["besluit_id"])
            lines.append(ce.side_line(sides["Voor"], sides["Tegen"], "By fractie (seats)"))
            derived = [m for m in nl_store.derived_member_positions(conn, r["besluit_id"])
                       if m["derived"]]
            lines.append(ce.derived_line(len(derived),
                                         "fractie vote; every member the store lists under that fractie, former members included"))
        soort = r["soort"] or ""
        group = dossiers[0] if dossiers and soort not in ("Motie",) else None
        dossier = "{0}{1}".format(dossiers[0], ": " + titles[0] if titles else "") \
            if dossiers else None
        take = "{0} {1}".format(SOORT.get(soort, soort or "Item"), r["zaak_nummer"])
        if dossier:
            take += ", in dossier {0}".format(dossier)
        out.append(ce.vote("nl", r["zaak_nummer"], r["date"], r["onderwerp"],
                           ce.areas_of(r["areas"]), r["tier"], w, lines,
                           url=zaak_url(r["zaak_nummer"]), terms=r["matched_terms"],
                           takeaway=ce.clip(take, 260), group=group,
                           group_title=titles[0] if group and titles else None,
                           final=soort in BILLS, own=bool(ce.areas_of(r["own_areas"])),
                           watch_key=hit, refs=titles, division=r["besluit_id"]))
    return out


COUNTRY = ce.Country(
    cc="nl", name="Netherlands", chamber="Tweede Kamer and Eerste Kamer", language="Dutch",
    taxonomies=(("taxonomy-nl.yaml", "nl"),),
    items=items, kinds=("vote", "speech", "question"), dm_kinds=("vote",), flag=":flag-nl:",
    week_ahead=agenda.week_ahead_fn("nl"), ahead_note=agenda.ahead_note_fn("nl"),
    members_note=("Most votes are by show of hands, one position per fractie; member "
                  "positions shown for them are DERIVED from the fractie vote (X5), given to "
                  "every member the store lists under that fractie by their latest fractie. "
                  "Roll calls record every member"),
    coverage=("Votes, plenary speeches and Kamervragen; the DM carries votes only (NL3). New "
              "bills and stage moves are not collected; committee debates are not read.",
              "The Eerste Kamer (NL4) is read from eerstekamer.nl's vote pages, the only source "
              "of its votes: fracties for and against on a show of hands, every senator on a "
              "roll call.",
              "Positions can arrive days after the vote; the collector re-reads six weeks."),
)
