"""Portugal: the Assembleia da República, from the pt_* tables
(src/pt_store.py, tools/pt_rollcalls.py).

Items: every initiative on our ground (taxonomy-pt for `pt`, plus
config/watchlist-pt.yaml by key, 'XVII/J/479'). An initiative whose first
event fell in the window is new; an older one whose latest phase fell in
it is a stage move, with the phase in the Assembleia's own words.

Votes: PORTUGAL VOTES BY GROUP. The plenary votes by sitting and standing,
so the record is each group's position; a deputy is named only when they
broke from their group. Each vote therefore carries the result in the
record's own word, the groups on each side (and any counted breakaway
block, '13-PS'), the deputies the record names, and, per X5, the member
positions DERIVED from the group vote (pt_store.derived_member_positions:
every sitting deputy of a group with a whole-group line is given that
group's position; counted blocks on a free vote are never spread over
unnamed deputies). Derived positions are labelled as derived. An
initiative's votes (generality, specialty, final global) are one group, the
final global vote decisive.

No agenda is collected, so there is no week ahead.
"""

from __future__ import annotations

import json

from src import country_edition as ce
from src import pt_store

SITE = "https://www.parlamento.pt/ActividadeParlamentar/Paginas/DetalheIniciativa.aspx?BID={0}"
SIDES = (("A Favor", "for"), ("Contra", "against"), ("Abstenção", "abstaining"),
         ("Ausente", "absent"))
FINAL = ("final global", "votacao final", "votação final")


def ini_url(ini_id):
    return SITE.format(ini_id) if ini_id else None


def _authors(r):
    try:
        gp = json.loads(r["authors_gp"] or "[]")
    except (TypeError, ValueError):
        gp = []
    if gp:
        return ", ".join(gp)
    return ce.clean(r["author_other"]) or None


def _takeaway(r, new):
    bits = ["{0} {1}/{2}".format(ce.clean(r["type_desc"]) or "Initiative", r["number"],
                                 r["legislature"])]
    who = _authors(r)
    if who:
        bits.append("by {0}".format(who))
    if not new and r["latest_phase_at"]:
        bits.append("latest phase on {0}".format(ce.long_date(ce.day(r["latest_phase_at"]))))
    if r["law_published"]:
        bits.append("published as law on {0}".format(ce.long_date(ce.day(r["law_published"]))))
    if r["vetoes"]:
        bits.append("{0} presidential veto(es) received".format(r["vetoes"]))
    return "; ".join(bits)


def _initiatives(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM pt_initiatives WHERE ({0}) OR ({1})".format(
            ce.window_sql("entered"), ce.window_sql("latest_phase_at")),
            (since, until, since, until)):
        w = r["ini_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        new = since < ce.day(r["entered"]) <= until
        out.append(ce.item("pt", "new" if new else "moved", r["ini_key"],
                           r["entered"] if new else r["latest_phase_at"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], w, status=r["latest_phase"],
                           url=ini_url(r["ini_id"]), terms=r["matched_terms"],
                           takeaway=_takeaway(r, new)))
    return out


def sides_line(group_rows):
    """'By group: for PSD, CDS-PP; against CH, IL; abstaining PS (13-PS for).'
    from pt_group_votes rows: a whole group by name, a counted block as
    the record prints it."""
    parts = []
    for word, label in SIDES:
        names = ["{0}-{1}".format(g["members"], g["party"]) if g["members"] else g["party"]
                 for g in group_rows if g["position"] == word]
        if names:
            parts.append("{0} {1}".format(label, ", ".join(names)))
    return "By group, as the record prints it: {0}.".format("; ".join(parts)) if parts else None


def named_line(named):
    if not named:
        return None
    shown = ["{0} ({1}, {2})".format(ce.clean(n["name"]), n["party"],
                                     dict(SIDES).get(n["position"], n["position"]))
             for n in named[:8]]
    more = len(named) - 8
    return "Named in the record (broke from their group): {0}{1}.".format(
        ", ".join(shown), " and {0} more".format(more) if more > 0 else "")


def _votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT d.*, i.title AS ini_title, i.ini_id, i.type_desc, "
                           "i.number AS ini_number FROM pt_divisions d LEFT JOIN pt_initiatives "
                           "i USING (ini_key) WHERE " + ce.window_sql("d.date"), (since, until)):
        w = bool(r["ini_key"]) and r["ini_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        how = "committee vote" if r["meeting_type"] == "CP" else "plenary vote by group"
        result = ce.clean(r["result"]) or "?"
        if r["unanimous"]:
            result += ", por unanimidade"
        groups = ce.rows(conn, "SELECT party, position, members FROM pt_group_votes WHERE "
                               "division_key=? ORDER BY members IS NOT NULL, party",
                         (r["division_key"],))
        named = ce.rows(conn, "SELECT name, party, position FROM pt_votes WHERE division_key=? "
                              "ORDER BY name", (r["division_key"],))
        derived = [m for m in pt_store.derived_member_positions(conn, r["division_key"])
                   if m["derived"]]
        lines = ["Result as recorded: “{0}” ({1}).".format(result, how),
                 sides_line(groups), named_line(named),
                 ce.derived_line(len(derived), "the deputy's latest group, sitting deputies "
                                               "only")]
        if any(g["members"] for g in groups) and not any(g["members"] is None for g in groups):
            lines.append("A free vote: only counted blocks, so no member position is derived "
                         "for unnamed deputies.")
        phase = ce.clean(r["phase"]) or "Votação"
        title = phase + (": " + ce.clean(r["description"]) if r["description"] else "")
        take = "{0} {1}/{2}".format(ce.clean(r["type_desc"]) or "Initiative",
                                    r["ini_number"] or "?", r["legislature"]) \
            if r["ini_key"] else "Vote {0}".format(r["division_key"])
        out.append(ce.vote("pt", r["division_key"], r["date"], title, ce.areas_of(r["areas"]),
                           r["tier"], w, lines, url=ini_url(r["ini_id"]),
                           terms=r["matched_terms"], takeaway="Vote on " + take,
                           own=bool(ce.areas_of(r["own_areas"])),
                           group=r["ini_key"] or None, group_title=r["ini_title"],
                           final=any(f in phase.lower() for f in FINAL),
                           watch_key=r["ini_key"] if w else None,
                           rebels=["{0} ({1}, {2})".format(ce.clean(n["name"]), n["party"],
                                                           dict(SIDES).get(n["position"], n["position"]))
                                   for n in named],
                           rebels_note="Group votes; member positions DERIVED (X5). Only the "
                                       "deputies the record names as voting apart from their "
                                       "group are named."))
    return out


def items(conn, since, until, wl):
    return _initiatives(conn, since, until, wl) + _votes(conn, since, until, wl)


COUNTRY = ce.Country(
    cc="pt", name="Portugal", chamber="Assembleia da República", language="Portuguese",
    taxonomies=(("taxonomy-pt.yaml", "pt"),),
    items=items, flag=":flag-pt:",
    members_note=("Portugal votes by group: the record names a deputy only when they broke "
                  "from their group, so member positions shown are DERIVED from the group "
                  "vote (X5), with the deputy's latest group, and labelled as derived"),
    coverage=("Initiatives, votes and deputies come from the Assembleia's open data "
              "(Iniciativas and InformacaoBase, XVII legislature).",
              "A vote's areas are mostly its initiative's: the record describes amendments and "
              "requerimentos only. The record does not tell a deputy who voted with their group "
              "from one who was absent."),
)
