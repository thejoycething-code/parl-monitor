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

The week ahead is the Camera's calendar of the Assembly's work
(src/agendas/it.py); the Senate's is not read (senato.it refuses us).

Regional councils (IT3, 12 October 2026): the acts of the councils read by
tools/it_regions.py (it_reg_acts) get a section of their own, "Regional
councils", before the Watchlist (`post_render`), so national counts and the
lead stay national. Same rules as the national items: on our ground by
taxonomy-it or watchlist-it's `regional` section by key, through the
edition's noise filters; an act presented in the window is new, an older one
whose status changed in the window is a stage move. Where the council dates
the status (Lombardia) the date is its own; elsewhere the edition says the
change was seen by the weekly run, not when it happened.
"""

from __future__ import annotations

import datetime
import json
import re

from src import agenda
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
        reb = ce.rebels(pairs, POS_YES, POS_NO, skip=NO_LINE) if pairs else None
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST), "By group"))
            lines.append(ce.members_line(len(pairs), reb, "Groups as at the vote."))
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
                           final=bool(r["is_final"]), watch_key=hit, refs=keys or None,
                           positions=pairs or None, rebels=reb))
    return out


def items(conn, since, until, wl):
    return _bills(conn, since, until, wl) + _votes(conn, since, until, wl)


# --- regional councils (IT3) -------------------------------------------------------

REGIONS = (("lom", "Lombardia"), ("cam", "Campania"), ("mar", "Marche"),
           ("tn", "Provincia autonoma di Trento"))
REGION_NAMES = dict(REGIONS)
REGIONS_DOC = ce.REPO + "docs/italy-regions-scope.md"


def _reg_takeaway(r, new):
    where = REGION_NAMES.get(r["region"], r["region"])
    bits = ["{0}, {1}".format(ce.clean(r["label"]) or r["kind"],
                              where if r["region"] == "tn" else "Consiglio regionale, " + where)]
    if r["initiative"]:
        bits.append("presented by {0}".format(ce.clean(r["initiative"])))
    if r["committee"]:
        bits.append("committee: {0}".format(ce.clean(r["committee"])))
    if not new and r["status_date"]:
        if r["status_seen"]:
            bits.append("status change seen by the weekly run of {0}".format(
                ce.long_date(ce.day(r["status_date"]))))
        else:
            bits.append("status changed on {0}".format(ce.long_date(ce.day(r["status_date"]))))
    if r["law"]:
        bits.append("enacted as {0}".format(r["law"]))
    return "; ".join(bits)


def regional_items(conn, since, until, wl):
    """The regional acts on our ground, new or moved in the window."""
    out = []
    for r in ce.rows(conn, "SELECT * FROM it_reg_acts WHERE ({0}) OR ({1})".format(
            ce.window_sql("presented"), ce.window_sql("status_date")),
            (since, until, since, until)):
        w = r["act_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        new = since < ce.day(r["presented"]) <= until
        it = ce.item("it", "new" if new else "moved", r["act_key"],
                     r["presented"] if new else r["status_date"], r["title"],
                     ce.areas_of(r["areas"]), r["tier"], w, status=r["status"], url=r["url"],
                     terms=r["matched_terms"], takeaway=_reg_takeaway(r, new))
        it["region"] = r["region"]
        out.append(it)
    return out


_LONG = re.compile(r"covering (\d{1,2} [A-Z][a-z]+ \d{4}) to (\d{1,2} [A-Z][a-z]+ \d{4})")


def _iso_long(text):
    d, m, y = text.split()
    return datetime.date(int(y), ce.MONTHS.index(m) + 1, int(d)).isoformat()


def _rendered_window(text, today):
    """(since, until) as the rendered edition states them (its 'covering A to
    B' line), so --since and the edition directory are honoured."""
    m = _LONG.search(text)
    if not m:
        return ce.window("it", today)
    first = datetime.date.fromisoformat(_iso_long(m.group(1)))
    return (first - datetime.timedelta(days=1)).isoformat(), _iso_long(m.group(2))


def regional_section(conn, country, since, until, wl):
    got = regional_items(conn, since, until, wl)
    kept, dropped = ce.noise_for(country).split(got)
    kept = ce.score(kept)
    first = (datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()
    names = ", ".join(n for _, n in REGIONS)
    out = ["## Regional councils", ""]
    if not kept:
        out.append("Nothing on our ground in the councils read ({0}) between {1} and {2}.".format(
            names, ce.long_date(first), ce.long_date(until)))
    else:
        out.append("**{0} regional item(s) on our ground**: {1}; {2} watched. Read from {3}; "
                   "the other councils are not read yet ([scope]({4})).".format(
                       len(kept), ce.count_text(kept) or "none",
                       sum(it["watched"] for it in kept) or "none", names, REGIONS_DOC))
        for code, name in REGIONS:
            these = [it for it in kept if it.get("region") == code]
            if not these:
                continue
            out += ["", "### " + name, ""]
            for it in these[:ce.MAX_PER_SECTION]:
                out += ce.item_lines(it, wl)
            if len(these) > ce.MAX_PER_SECTION:
                out.append("- _And {0} more, lower in the order; in the store._".format(
                    len(these) - ce.MAX_PER_SECTION))
    if dropped:
        out += ["", "- Left out by the noise filters: {0}.".format(ce.dropped_text(dropped))]
    out.append("")
    return out


def post_render(conn, country, today, text, wl):
    """The regional section, before the Watchlist (or at the end of a quiet week).
    Nothing is added when the store has no regional table or no regional act."""
    try:
        if not conn.execute("SELECT 1 FROM it_reg_acts LIMIT 1").fetchone():
            return text
    except Exception:   # a store from before IT3
        return text
    since, until = _rendered_window(text, today)
    section = "\n".join(regional_section(conn, country, since, until, wl))
    marker = "\n## Watchlist\n"
    if marker in text:
        return text.replace(marker, "\n" + section + marker, 1)
    return text.rstrip("\n") + "\n\n" + section


COUNTRY = ce.Country(
    cc="it", name="Italy", chamber="Senato and Camera dei Deputati", language="Italian",
    taxonomies=(("taxonomy-it.yaml", "it"),),
    items=items, flag=":flag-it:", post_render=post_render,
    week_ahead=agenda.week_ahead_fn("it"), ahead_note=agenda.ahead_note_fn("it"),
    members_note=("Both chambers record every member's position, with the group at the vote; "
                  "nothing is derived"),
    coverage=("Bills of both chambers and every recorded vote come from dati.senato.it; the "
              "Camera's votes from Openpolis (IT2: dati.camera.it as backup is a later phase).",
              "Bill statuses are the Senate's own terse words ('assegnato (no esame)', 'esame "
              "in comm.'). A bill lapses with the 19th legislature (by October 2027).",
              "Regional councils (IT3): bills and motions of Lombardia (dati.lombardia.it), "
              "Campania, Marche and the Provincia autonoma di Trento (its open-data XML) are "
              "read; the other sixteen councils are not, each for a reason in "
              "docs/italy-regions-scope.md. No council publishes member positions in a form "
              "we read.",
              "The week ahead is the Camera's Assembly calendar only: the Senate's calendar "
              "is not read (senato.it refuses us), nor are committee convocations."),
)
