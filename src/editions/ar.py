"""Argentina's weekly edition: the adapter for src/country_edition.py.

The store (tools/ar_rollcalls.py) holds the Senate's roll calls with every
senator's position and bloc at the vote, the Senate expedientes those actas
name, and the Diputados register of expedientes. DIPUTADOS ROLL CALLS ARE
NOT COLLECTED: votaciones.hcdn.gob.ar refuses every client tried (AR2 asks
the Mini to try); so Diputados appears through its register only.

Titles are the chamber's own Spanish, verbatim (HCDN prints most in
capitals); the English takeaway says what kind of item it is (a bill, a
resolution, a declaration; a motion of approval or of repudiation; a
request for information), who filed it, and, for a bill, when it lapses.

LEY 13.640 (AR7, confirmed 10 October 2026). A bill (proyecto de ley) with
no sanction in either chamber lapses at the end of the parliamentary year
after the one it entered in; one sanctioned by one chamber has a year more.
A parliamentary year runs from 1 March to the end of February. So a bill
that entered between 1 March 2025 and 28 February 2026 lapses on
28 February 2027 unless a chamber passes it first. `lapse_date()` computes
this; the edition lists the bills on our ground that lapse within
LAPSE_HORIZON_DAYS (`post_render()`, the framework's Country.post_render
hook, inserts the section).

Approximations, said in the edition: the Diputados register gives the
Trámite Parlamentario date (entry); a Senate expediente gives only the year
of its number, taken as the parliamentary year starting that March. Half
sanction is read from the store: a Senate expediente that came from
Diputados ('CD' origin, or a Diputados number in exp_other), or one the
Senate voted AFIRMATIVO en general.
"""

from __future__ import annotations

import datetime
import json
import re

from src import country_edition as ce
from src.filter import _fold

CC = "ar"
HCDN_EXP = "https://www.hcdn.gob.ar/proyectos/proyectoTP.jsp?exp={0}"
SENADO_EXP = "https://www.senado.gob.ar/parlamentario/comisiones/verExp/{0}.{1:02d}/{2}/{3}"
LAPSE_HORIZON_DAYS = 183

TIPOS = {"LEY": "bill", "PL": "bill", "RESOLUCION": "draft resolution", "PR": "draft resolution",
         "DECLARACION": "draft declaration", "PD": "draft declaration",
         "DC": "draft declaration", "AC": "agreement (nomination)", "PC": "communication",
         "OV": "official communication"}
# What the item does, from its own opening words (folded). First match wins.
OPENINGS = (
    (r"^pedido de informes", "a request for information to the Executive"),
    (r"^expresar (beneplacito|satisfaccion|reconocimiento|adhesion|beneplacito)",
     "a motion of approval or recognition"),
    (r"^expresar (repudio|rechazo|preocupacion)|^repudiar|^rechazar",
     "a motion of repudiation, rejection or concern"),
    (r"^expresar (solidaridad|acompanamiento)", "a motion of solidarity"),
    (r"^declarar de interes", "declares something of interest to the Chamber"),
    (r"^citar|^convocar", "summons a minister or official, or calls a consultation"),
    (r"^promover juicio politico", "seeks impeachment proceedings"),
    (r"^derog", "repeals a measure"),
    (r"^codigo penal", "amends the Penal Code"),
    (r"^codigo civil", "amends the Civil and Commercial Code"),
)
VOTE_TYPES = {"EN GENERAL": "vote on the whole (en general)",
              "EN PARTICULAR": "article or title vote (en particular)",
              "EN GENERAL Y EN PARTICULAR": "single vote on the whole and the articles"}
YES, NO, ABSTAIN = ("afirmativo",), ("negativo",), ("abstencion", "abstención")


def opening(title):
    text = _fold(title or "").lower().strip()
    return next((label for pat, label in OPENINGS if re.search(pat, text)), None)


def is_bill(row):
    return (row["tipo"] or "").upper() in ("LEY", "PL")


def exp_url(row):
    key = row["exp_key"]
    if key.startswith("dip/"):
        return HCDN_EXP.format(key[4:])
    hit = re.match(r"sen/(\d+)-([A-Z]+)-(\d{4})$", key)
    if hit and row["tipo"]:
        return SENADO_EXP.format(hit.group(1), int(hit.group(3)) % 100, hit.group(2),
                                 row["tipo"].upper())
    return None


# --- Ley 13.640 -------------------------------------------------------------------

def parliamentary_year(iso_date=None, year=None):
    """The calendar year in which the entry's parliamentary year began (1 March)."""
    if iso_date:
        d = datetime.date.fromisoformat(iso_date[:10])
        return d.year if d.month >= 3 else d.year - 1
    return year


def end_of_february(year):
    return (datetime.date(year, 3, 1) - datetime.timedelta(days=1)).isoformat()


def half_sanctioned(conn, row):
    if row["law"]:
        return True
    if row["exp_key"].startswith("sen/") and (row["origin"] == "CD" or
                                              (row["exp_other"] or "").startswith("dip/")):
        return True
    for d in ce.rows(conn, "SELECT vote_type, result FROM ar_divisions WHERE exp_keys LIKE ?",
                     ('%"' + row["exp_key"] + '"%',)):
        if "GENERAL" in (d["vote_type"] or "") and (d["result"] or "").upper() == "AFIRMATIVO":
            return True
    return False


def lapse_date(conn, row):
    """ISO date a bill lapses under Ley 13.640, or None (not a bill, a law, no year)."""
    if not is_bill(row) or row["law"]:
        return None
    start = parliamentary_year(row["published"], row["year"])
    if not start:
        return None
    extra = 1 if half_sanctioned(conn, row) else 0
    return end_of_february(start + 2 + extra)


def bills_by_lapse(conn, wl):
    """[(lapse date, row)] for every bill on our ground that has not become law."""
    out = []
    for r in ce.rows(conn, "SELECT * FROM ar_bills"):
        watched = r["exp_key"] in wl or (r["exp_other"] or "") in wl
        if not ce.on_ground(r["areas"], watched) or not is_bill(r):
            continue
        when = lapse_date(conn, r)
        if when:
            out.append((when, r))
    return sorted(out, key=lambda p: (p[0], p[1]["exp_key"]))


def lapse_section(conn, today, wl):
    """Markdown lines: on-our-ground bills lapsing within the horizon, then a
    count per later lapse date."""
    horizon = (datetime.date.fromisoformat(today)
               + datetime.timedelta(days=LAPSE_HORIZON_DAYS)).isoformat()
    every = [(d, r) for d, r in bills_by_lapse(conn, wl) if d >= today]
    near = [(d, r) for d, r in every if d <= horizon]
    out = ["## Nearing lapse (Ley 13.640)", "",
           "_A bill with no sanction lapses at the end of February of the parliamentary year "
           "after the one it entered in (a year more once one chamber has passed it). Bills on "
           "our ground only; entry is the Trámite Parlamentario date for Diputados, the "
           "number's year for the Senate._", ""]
    if near:
        for when, r in near:
            watched = r["exp_key"] in wl or (r["exp_other"] or "") in wl
            out.append("- **{0}** · lapses {1} · {2}{3}".format(
                r["exp_key"], ce.long_date(when), ce.area_text(ce.areas_of(r["areas"]))
                or "watched", " · **watched**" if watched else ""))
            out.append("  *{0}*".format(ce.clip(r["title"], 300)))
            url = exp_url(r)
            if url:
                out.append("  [Source]({0})".format(url))
    else:
        out.append("No bill on our ground lapses before {0}.".format(ce.long_date(horizon)))
    later = {}
    for when, _ in every:
        if when > horizon:
            later[when] = later.get(when, 0) + 1
    if later:
        out.append("")
        out.append("Later: " + "; ".join("{0} bill(s) lapse on {1}".format(n, ce.long_date(d))
                                          for d, n in sorted(later.items())) + ".")
    out.append("")
    return out


# --- items ------------------------------------------------------------------------

def bill_takeaway(conn, r):
    bits = []
    kind = TIPOS.get((r["tipo"] or "").upper())
    what = opening(r["title"])
    chamber = "Diputados" if r["exp_key"].startswith("dip/") else "Senate"
    bits.append("{0} {1}{2}".format(chamber, kind or "expediente",
                                    ": " + what if what else ""))
    if r["author"]:
        bits.append("Filed by {0}".format(r["author"].title()))
    if r["exp_other"]:
        bits.append("In the other chamber: {0}".format(r["exp_other"]))
    if r["law"]:
        bits.append("Became {0}".format(r["law"]))
    when = lapse_date(conn, r)
    if when:
        bits.append("Lapses {0} without a sanction (Ley 13.640)".format(ce.long_date(when)))
    return ". ".join(bits)


def senate_split(conn, dkey):
    got = ce.rows(conn, "SELECT m.name, v.bloc, v.position FROM ar_votes v LEFT JOIN ar_members m "
                        "USING (member_key) WHERE v.division_key=?", (dkey,))
    pairs = [(r["bloc"], r["position"]) for r in got]
    triples = [(r["name"], r["bloc"], r["position"]) for r in got]
    reb = ce.rebels(triples, YES, NO)
    return ce.group_counts(pairs, YES, NO, ABSTAIN), len(got), reb, triples


def items(conn, since, until, wl):
    out = []
    bills = {r["exp_key"]: r for r in ce.rows(conn, "SELECT * FROM ar_bills")}
    for d in ce.rows(conn, "SELECT * FROM ar_divisions WHERE " + ce.window_sql("date")
                     + " ORDER BY date, acta_id", (since, until)):
        keys = json.loads(d["exp_keys"] or "[]")
        wkey = next((w for k in keys for w in (k, bills[k]["exp_other"] if k in bills else None)
                     if w and w in wl), None)
        watched = wkey is not None
        if not ce.on_ground(d["areas"], watched):
            continue
        groups, n, reb, triples = senate_split(conn, d["division_key"])
        terms = list(ce.terms_of(d["matched_terms"]))
        refs = []
        for k in keys:
            if k in bills:
                terms += ce.terms_of(bills[k]["matched_terms"])
                refs.append(bills[k]["title"] or "")
        take = "Senate, {0}".format(VOTE_TYPES.get((d["vote_type"] or "").upper(), "roll call"))
        if d["majority"]:
            take += "; majority required: {0}".format(d["majority"].lower())
        if keys:
            take += "; on {0}".format(", ".join(keys[:4]) + (" and {0} more".format(len(keys) - 4)
                                                            if len(keys) > 4 else ""))
        title_root = re.split(r"\.\s", d["title"] or "", maxsplit=1)[0]
        out.append(ce.vote(
            CC, d["division_key"], d["date"], d["title"], ce.areas_of(d["areas"]), d["tier"],
            watched,
            [ce.tally_line(d["ayes"], d["noes"], d["abstentions"], d["result"]),
             "Absent: {0}.".format(d["absent"]) if d["absent"] else None,
             ce.split_line(groups, "By bloc"),
             ce.members_line(n, reb, None if d["has_detail"] else
                             "Only the acta's PDF was published: no positions.")],
            url=d["source_url"], terms=terms, refs=refs, takeaway=take, watch_key=wkey,
            own=bool(ce.areas_of(d["own_areas"])),
            group=("acta", d["date"], tuple(keys) if keys else title_root),
            group_title=refs[0] if refs else None,
            final="GENERAL" in (d["vote_type"] or "").upper(),
            positions=triples or None, rebels=reb if triples else None))
    for r in ce.rows(conn, "SELECT * FROM ar_bills WHERE " + ce.window_sql("published"),
                     (since, until)):
        wkey = r["exp_key"] if r["exp_key"] in wl else (
            r["exp_other"] if (r["exp_other"] or "") in wl else None)
        if not ce.on_ground(r["areas"], wkey is not None):
            continue
        out.append(ce.item(CC, "new", r["exp_key"], r["published"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], wkey is not None,
                           url=exp_url(r), watch_key=wkey,
                           terms=r["matched_terms"], takeaway=bill_takeaway(conn, r)))
    return out


def post_render(conn, country, today, text, wl):
    """The Ley 13.640 section, before the Watchlist (or at the end of a quiet week)."""
    section = "\n".join(lapse_section(conn, today, wl))
    marker = "\n## Watchlist\n"
    if marker in text:
        return text.replace(marker, "\n" + section + marker, 1)
    return text.rstrip("\n") + "\n\n" + section


COUNTRY = ce.Country(
    cc=CC, name="Argentina", chamber="Senado and Cámara de Diputados de la Nación",
    language="Spanish", taxonomies=(("taxonomy-es.yaml", "ar"),), items=items,
    flag=":flag-ar:", post_render=post_render,
    members_note=("Senate roll calls carry every senator's position and bloc at the vote; "
                  "Diputados roll calls are not collected (votaciones.hcdn.gob.ar refuses our "
                  "clients), so Diputados appears through its register of expedientes only"),
    coverage=(
        "Collected: Senate roll calls with every position, the Senate expedientes they name, "
        "and the Diputados register of expedientes, read gently (one month a request, a few "
        "requests a run) because datos.hcdn.gob.ar turns clients away.",
        "Blocked: Diputados roll calls (AR2: to be tried from the Mini).",
        "Not yet collected: the full Senate register, both chambers' agendas, committee "
        "dictámenes, and the provincial legislatures.",
        "Lapse dates follow Ley 13.640 (AR7) and are computed, not printed by either chamber.",
    ),
)
