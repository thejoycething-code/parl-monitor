"""Spain: the weekly edition's adapter (src/country_edition.py).

Reads the es_* tables tools/es_rollcalls.py fills (src/es_store.py): the
Congreso de los Diputados' plenary votes with every deputy's position and
the group printed at the vote, and its legislative initiatives. The Senado
refuses us (docs/spain-scope.md), so the edition is the Congreso's.

ES6 (docs/country-decisions-2026-10-10.md): build the edition now, although
the Cortes were dissolved on 6 October 2026 (Real Decreto 806/2026; election
29 November; the XVI legislature convenes on 23 December). While the store
holds nothing newer than a dissolved legislature, every edition opens with a
short notice saying so and naming the next sitting; a week with nothing on
our ground is then the short "quiet week" form under that notice. The
notice goes by itself the day the store holds a row of the next
legislature, which the collector reads off the Congreso's own selector, so
the XVI's first items appear with no edit here.

THE NOTICE is the framework's `Country.notice` hook (`edition_notice()`
below): the framework puts it under the edition's subtitle and on the DM's
second line.

Votes on one initiative in one week (points voted separately, amendments,
the vote of the whole) render as one entry; the vote's sub-heading leads
its title so that each line of the group says which vote it was.
"""

from __future__ import annotations

import datetime
import re
import sys

from src import agenda
from src import country_edition as ce

CC = "es"
BASE = "https://www.congreso.es"
DAY_PAGE = (BASE + "/es/opendata/votaciones?p_p_id=votaciones&p_p_lifecycle=0"
            "&p_p_state=normal&p_p_mode=view&targetLegislatura={leg}&targetDate={date}")
ROMAN = {14: "XIV", 15: "XV", 16: "XVI", 17: "XVII", 18: "XVIII"}

# A dissolved legislature, from the decree in the BOE. Add a row at the next
# dissolution; nothing else changes.
DISSOLUTIONS = {
    15: {"dissolved": "2026-10-06",
         "decree": "Real Decreto 806/2026 (BOE-A-2026-20742)",
         "election": "2026-11-29",
         "convenes": "2026-12-23"},
}

# The Congreso's agenda sections, in English, by the folded start of the
# section heading ("NUEVO PUNTO." and "PUNTO UNICO." are stripped first).
SECTIONS = (
    ("toma en consideracion", "Taking into consideration: whether the Congreso takes the bill up"),
    ("proposiciones no de ley", "Non-binding motion (proposición no de ley)"),
    ("votacion de las proposiciones no de ley", "Non-binding motion (proposición no de ley)"),
    ("mociones consecuencia", "Motion following an urgent interpellation"),
    ("convalidacion o derogacion", "Validation of a royal decree-law"),
    ("debates de totalidad", "Totality debate: amendments seeking the bill's return or a whole new text"),
    ("dictamenes de comisiones sobre iniciativas", "Committee report on a bill, with amendments kept alive for the plenary"),
    ("dictamenes de la comision de asuntos exteriores", "International treaty"),
    ("enmiendas del senado", "The Senado's amendments, back in the Congreso"),
    ("veto del senado", "The Senado's veto, back in the Congreso"),
    ("acuerdos de comisiones relativos a informes", "Report of a subcommittee"),
    ("propuestas de creacion", "Proposal to create a committee or subcommittee"),
    ("solicitud", "Request about a committee's work"),
    ("tramitacion directa", "Direct passage in a single reading"),
    ("acuerdo de tramitacion directa", "Direct passage in a single reading"),
    ("avocacion", "The plenary takes the final say on a bill from its committee"),
)

INITIATIVE_TYPES = (
    ("proyecto de ley", "Government bill"),
    ("proposicion de ley de grupos", "Bill from parliamentary groups"),
    ("proposicion de ley de diputados", "Bill from deputies"),
    ("proposicion de ley del senado", "Bill from the Senado"),
    ("proposicion de ley de comunidades", "Bill from a regional parliament"),
)


def _fold(text):
    from src.noise import fold
    return fold(text)


def _lookup(table, text):
    t = re.sub(r"^\s*(nuevo punto|punto unico)\.\s*", "", _fold(text))
    return next((en for start, en in table if t.startswith(start)), None)


def sentence(text):
    """A takeaway ends with a full stop: a group's decisive vote prints it as is."""
    text = (text or "").strip()
    return text if not text or text.endswith((".", "…", "?", "!")) else text + "."


def roman(n):
    return ROMAN.get(int(n)) if n else None


# --- the state of the legislature -------------------------------------------------

def latest_legislature(conn):
    best = None
    for table in ("es_divisions", "es_initiatives", "es_members"):
        got = ce.rows(conn, "SELECT MAX(legislature) FROM {0}".format(table))
        v = got[0][0] if got else None
        if v and (best is None or v > best):
            best = int(v)
    return best


def state(conn, today):
    """{'legislature', 'dissolved', ...} while the store's newest legislature
    is one dissolved by `today`; None otherwise (a sitting legislature, or a
    store that already holds the next one)."""
    leg = latest_legislature(conn)
    d = DISSOLUTIONS.get(leg) if leg else None
    if not d or today < d["dissolved"]:
        return None
    return dict(d, legislature=leg, next=leg + 1)


def notice(conn, today):
    """The edition's opening lines while the Cortes are dissolved; [] otherwise."""
    s = state(conn, today)
    if not s:
        return []
    nxt = roman(s["next"]) or str(s["next"])
    old = roman(s["legislature"]) or str(s["legislature"])
    if today < s["convenes"]:
        if today < s["election"]:
            when = "The general election is on {0}, and the {1} legislature convenes on {2}.".format(
                ce.long_date(s["election"]), nxt, ce.long_date(s["convenes"]))
        else:
            when = "The general election was held on {0}; the {1} legislature convenes on {2}.".format(
                ce.long_date(s["election"]), nxt, ce.long_date(s["convenes"]))
        head = "**The Cortes Generales are dissolved; next sitting {0}.**".format(
            ce.long_date(s["convenes"]))
        rest = ("Until then only the Diputación Permanente can meet (chiefly to validate "
                "decree-laws); a vote it holds appears here when the Congreso publishes it.")
    else:
        when = ("The {0} legislature convened on {1}, but the Congreso has not yet published "
                "its open data; this edition picks it up on the first run that finds it.".format(
                    nxt, ce.long_date(s["convenes"])))
        head = "**The {0} legislature has convened; its data is not out yet.**".format(nxt)
        rest = ""
    lines = ["> {0} The Congreso and the Senado were dissolved on {1} by {2}. {3} Every "
             "initiative of the {4} still pending lapsed with the dissolution, whatever its "
             "status line says. {5}".format(head, ce.long_date(s["dissolved"]), s["decree"],
                                             when, old, rest).rstrip(), ""]
    return lines


def dm_notice(conn, today):
    s = state(conn, today)
    if not s:
        return None
    nxt = roman(s["next"]) or str(s["next"])
    if today < s["convenes"]:
        return "_Cortes dissolved on {0}; next sitting {1} ({2} legislature)._".format(
            ce.short_date(s["dissolved"]), ce.long_date(s["convenes"]), nxt)
    return "_The {0} legislature convened on {1}; its data is not out yet._".format(
        nxt, ce.long_date(s["convenes"]))


def edition_notice(conn, today, dm=False):
    """Country.notice: notice() for the edition, dm_notice() for the DM."""
    if dm:
        return dm_notice(conn, today)
    return "\n".join(notice(conn, today))


# --- items ----------------------------------------------------------------------

def _terms(*raws):
    out = []
    for raw in raws:
        for t in ce.terms_of(raw):
            if t not in out:
                out.append(t)
    return out


def vote_title(title, subgroup):
    """The sub-heading first ('Votación separada por puntos. Punto 3.'), then
    the item, both verbatim: a group's lines then say which vote each was."""
    title, subgroup = ce.clean(title), ce.clean(subgroup)
    if not subgroup:
        return title
    return "{0}{1} {2}".format(subgroup, "" if subgroup.endswith(".") else ".", title)


def is_final(subgroup, title):
    s = _fold(subgroup or "") + " " + _fold(title or "")
    return "votacion de conjunto" in s


def _positions(conn, key):
    return [(r["name"], r["grupo"], r["position"]) for r in ce.rows(
        conn, "SELECT name, grupo, position FROM es_votes WHERE division_key = ?", (key,))]


YES, NO, ABSTAIN = ("sí", "si"), ("no",), ("abstención", "abstencion")


def _brief_positions(conn, r):
    """The same-day vote brief's fields (src/country_vote_brief.py)."""
    pos = [] if r["assent"] else _positions(conn, r["division_key"])
    return {"positions": pos or None, "rebels": ce.rebels(pos, YES, NO) if pos else None}


def vote_lines(conn, r):
    if r["assent"]:
        return ["Tally: agreed by assent, with no recorded vote."]
    how = "{0} not voting".format(r["not_voting"]) if r["not_voting"] else None
    lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], how=how)]
    pos = _positions(conn, r["division_key"])
    if pos:
        lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pos], YES, NO, ABSTAIN),
                                   label="By group at the vote"))
        lines.append(ce.members_line(len(pos), ce.rebels(pos, YES, NO)))
    elif not r["json_url"]:
        lines.append("Published as a chart only (a public roll call or an image-only vote): "
                     "no member positions in the open data.")
    elif r["positions"] == 0:
        lines.append("A secret ballot: the vote file names no one.")
    else:
        lines.append("Member positions not read yet; the next run fetches them.")
    return lines


def divisions(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM es_divisions WHERE " + ce.window_sql("date")
                     + " ORDER BY date, session, vote_number", (since, until)):
        key = r["initiative_key"] or r["division_key"]
        watched = key in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        init = None
        if r["initiative_key"]:
            got = ce.rows(conn, "SELECT matched_terms FROM es_initiatives WHERE initiative_key = ?",
                          (r["initiative_key"],))
            init = got[0]["matched_terms"] if got else None
        own = bool(ce.areas_of(r["own_areas"])) if r["own_areas"] is not None else None
        section = _lookup(SECTIONS, r["section"])
        takeaway = "{0}{1}".format(section or ce.clean(r["section"]).rstrip("."),
                                   ", {0} legislature".format(roman(r["legislature"]))
                                   if roman(r["legislature"]) else "")
        out.append(ce.vote(
            CC, key, r["date"], vote_title(r["title"], r["subgroup"]),
            ce.areas_of(r["areas"]), r["tier"], watched, vote_lines(conn, r),
            terms=_terms(r["matched_terms"], init), body=ce.clean(r["section"]),
            url=DAY_PAGE.format(leg=roman(r["legislature"]) or r["legislature"],
                                date=_ddmmyyyy(r["date"])),
            takeaway=sentence(takeaway), group=("es", key), group_title=r["title"],
            final=is_final(r["subgroup"], r["title"]),
            own=False if own is False else None, division=r["division_key"],
            **_brief_positions(conn, r)))
    return out


def _ddmmyyyy(iso):
    try:
        d = datetime.date.fromisoformat(ce.day(iso))
    except ValueError:
        return ""
    return "{0:02d}/{1:02d}/{2}".format(d.day, d.month, d.year)


def initiatives(conn, since, until, wl, today=None):
    out = []
    s = state(conn, today or until)
    for r in ce.rows(conn, "SELECT * FROM es_initiatives WHERE " + ce.window_sql("presentada")
                     + " ORDER BY presentada", (since, until)):
        watched = r["initiative_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        kind = _lookup(INITIATIVE_TYPES, r["tipo"]) or ce.clean(r["tipo"])
        bits = [kind]
        if r["autor"]:
            bits.append("from {0}".format(ce.clean(r["autor"])))
        takeaway = ", ".join(bits)
        if s and r["legislature"] == s["legislature"] and "caducad" not in _fold(r["situacion"]):
            takeaway += ". Lapsed with the dissolution of {0}, whatever its status says".format(
                ce.long_date(s["dissolved"]))
        out.append(ce.item(
            CC, "new", r["initiative_key"], r["presentada"], r["objeto"],
            ce.areas_of(r["areas"]), r["tier"], watched, status=r["situacion"],
            url=r["bocg"] or None, terms=r["matched_terms"], takeaway=takeaway))
    return out


def items(conn, since, until, wl):
    return divisions(conn, since, until, wl) + initiatives(conn, since, until, wl)


COUNTRY = ce.Country(
    cc=CC, name="Spain", chamber="Congreso de los Diputados", language="Spanish",
    taxonomies=(("taxonomy-es.yaml", "es"),),
    items=items, notice=edition_notice,
    week_ahead=agenda.week_ahead_fn(CC), ahead_note=agenda.ahead_note_fn(CC),
    members_note=("Member positions are the Congreso's own, by name, with the parliamentary "
                  "group printed in each vote file, so a member against their group's majority "
                  "is named"),
    coverage=(
        "The Congreso only: www.senado.es refuses our requests (Akamai 403, ES5 pending); "
        "the Senado's amendments and vetoes show when the Congreso votes on them.",
        "Non-binding motions and motions appear when the plenary votes on them; written "
        "questions are not collected yet (phase 2), and no stage-move history is stored, so "
        "there is no stage-moves section.",
        "The week ahead is the Congreso's weekly agenda page, classified on its own words; "
        "the plenary's order of the day (a PDF) is not read.",
    ),
)


# --- the entry point --------------------------------------------------------------

def render(conn, today, since=None, sample=False, config_dir=None, directory=None):
    """The edition, notice included (for tests and callers)."""
    return ce.render(conn, COUNTRY, today, since, sample, config_dir, directory)


def dm_summary(conn, today, since=None, path=None, config_dir=None, directory=None):
    return ce.dm_summary(conn, COUNTRY, today, since, path, config_dir, directory)


def main(argv=None):
    return ce.main(CC, argv)


if __name__ == "__main__":
    sys.exit(main())
