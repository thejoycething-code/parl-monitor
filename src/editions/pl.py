"""Poland: the Sejm, from the pl_* tables (src/pl_store.py,
tools/pl_rollcalls.py).

Every deputy's position on every vote is stored (X15), with the club the
vote record itself names, so each vote carries its club split and the
deputies who voted against their club's majority; nothing is derived.

A sitting often votes a bill's amendments one by one and then the whole:
those votes are one group, keyed on the legislative process the vote cites,
with the vote on the whole ("głosowanie nad całością") as the decisive one.
New items are legislative processes opened in the week; stage moves are
processes whose latest stage (read from the process detail) fell in it.
The Senate is not collected (PL2: the gap is accepted).
"""

from __future__ import annotations

import json

from src import country_edition as ce

SEJM = "https://www.sejm.gov.pl/Sejm{0}.nsf"
FINAL = ("nad caloscia",)          # folded: "głosowanie nad całością"
POS_YES, POS_NO, POS_ABST = ("yes",), ("no",), ("abstain",)


def process_url(key):
    term, _, number = (key or "").partition("/")
    return "{0}/PrzebiegProc.xsp?nr={1}".format(SEJM.format(term), number) if number else None


def vote_url(term, sitting, number):
    return ("{0}/agent.xsp?symbol=glosowania&NrKadencji={1}&NrPosiedzenia={2}&NrGlosowania={3}"
            .format(SEJM.format(term), term, sitting, number))


def _processes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM pl_processes WHERE ({0}) OR ({1})".format(
            ce.window_sql("start_date"), ce.window_sql("last_stage_date")),
            (since, until, since, until)):
        w = r["process_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        new = since < ce.day(r["start_date"]) <= until
        take = "Legislative process {0}{1}".format(
            r["process_key"], ", " + r["document_type"] if r["document_type"] else "")
        if r["passed"]:
            take += "; passed{0}".format(", published as " + r["eli"] if r["eli"] else "")
        status = r["last_stage"]
        if not new and r["last_stage_date"]:
            take += "; latest stage on {0}".format(ce.long_date(ce.day(r["last_stage_date"])))
        out.append(ce.item("pl", "new" if new else "moved", r["process_key"],
                           r["start_date"] if new else r["last_stage_date"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], w, status=status,
                           url=process_url(r["process_key"]), terms=r["matched_terms"],
                           takeaway=take))
    return out


def _votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM pl_divisions WHERE " + ce.window_sql("voted_at"),
                     (since, until)):
        procs = json.loads(r["process_keys"] or "[]")
        hit = next((k for k in procs if k in wl), None)
        w = hit is not None
        if not ce.on_ground(r["areas"], w):
            continue
        lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], None,
                               "electronic vote" if r["kind"] == "ELECTRONIC" else r["kind"])]
        got = ce.rows(conn, "SELECT m.name, v.club, v.position FROM pl_votes v LEFT JOIN "
                            "pl_members m USING (mp_key) WHERE v.division_key=?",
                            (r["division_key"],))
        pairs = [(v["name"] or "?", v["club"], v["position"]) for v in got]
        reb = ce.rebels(pairs, POS_YES, POS_NO, skip=("niez.",)) if pairs else None
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(c, p) for _, c, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST), "By club"))
            lines.append(ce.members_line(len(pairs), reb,
                                         "Clubs as the vote record names them."))
        else:
            lines.append("Deputies' positions not read yet; the collector reads them next run.")
        topic = ce.clean(r["topic"]) or ce.clean(r["title"])
        group = procs[0] if procs else "{0}/{1}".format(r["sitting"], ce.clean(r["title"])[:60])
        out.append(ce.vote("pl", r["division_key"], r["voted_at"], topic,
                           ce.areas_of(r["areas"]), r["tier"], w, lines,
                           url=vote_url(r["term"], r["sitting"], r["number"]),
                           terms=r["matched_terms"],
                           takeaway="Sejm vote {0} at sitting {1}{2}".format(
                               r["number"], r["sitting"],
                               ", on process " + ", ".join(procs) if procs else ""),
                           group=group, group_title=r["title"], refs=[r["title"]],
                           final=any(f in ce.noise_mod.fold(topic) for f in FINAL),
                           own=bool(ce.areas_of(r["own_areas"])), watch_key=hit,
                           positions=pairs or None, rebels=reb))
    return out


def items(conn, since, until, wl):
    return _processes(conn, since, until, wl) + _votes(conn, since, until, wl)


COUNTRY = ce.Country(
    cc="pl", name="Poland", chamber="Sejm", language="Polish",
    taxonomies=(("taxonomy-pl.yaml", "pl"),),
    items=items, flag=":flag-pl:",
    members_note="Every deputy's position on every vote is stored, with the club at the vote",
    coverage=("The Senate is not collected (PL2: the gap is accepted).",
              "The Sejm's planned sittings and agendas (the week ahead) are phase 2."),
)
