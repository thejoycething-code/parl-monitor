"""Brazil's weekly edition: the adapter for src/country_edition.py.

The store (tools/br_rollcalls.py, phase 1) holds every NOMINAL vote of the
Câmara dos Deputados and the Senado Federal with each member's position and
party at the vote, the Câmara leaders' orientations, and the proposições
those votes are about. Most decisions in both houses are symbolic votes,
which record no position and are not stored. The bill register (phase 2)
is not collected yet, so a bill appears only once a nominal vote names it,
or under "new" when its presentation date falls in the window.

BR5 (Chris, 10 October 2026): Portuguese source text with English
takeaways. Titles are the chamber's own words, verbatim; the takeaway is
built from the record's structure (which chamber or committee, what kind of
vote, where the bill stands), never a machine translation.

A BILL CAN BE RENUMBERED. An older Câmara bill takes a new number on
reaching the Senate, and the Câmara's own record then shows it (PL 3179/2012
became PL 1338/2022). The collector renames the bill in place and keeps the
old number in br_bills.former_keys; every line here shows both, and a
watchlist entry still keyed on the old number keeps matching.

Areas 14 (gambling and betting) and 15 (drug decriminalisation) are
Brazil's own (BR3, BR4; taxonomy-pt, every term [only: br]); their labels
are added to the shared label map here, additively.
"""

from __future__ import annotations

import json
import re

from src import agenda
from src import country_edition as ce
from src.filter import _fold

CC = "br"
CAMARA_BILL = "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={0}"
SENADO_BILL = "https://www25.senado.leg.br/web/atividade/materias/-/materia/{0}"

# Brazil's own areas (BR3, BR4). Additive: no other country's store carries them.
ce.AREA_LABELS.setdefault(14, "gambling and betting")
ce.AREA_LABELS.setdefault(15, "drug decriminalisation")

ORGANS = {"PLEN": "plenary"}

# What kind of vote, from the chamber's own words (folded). First match wins.
VOTE_KINDS = (
    (r"requerimento de urgencia", "urgency request (puts the bill on a fast track to the floor)"),
    (r"retirada de pauta", "motion to take the item off the agenda"),
    (r"adiamento", "motion to postpone"),
    (r"preferencia", "vote on which text is voted first (preference)"),
    (r"em primeiro turno", "first-round vote on the constitutional amendment"),
    (r"em segundo turno", "second-round vote on the constitutional amendment"),
    (r"redacao final", "vote on the final wording"),
    (r"mantido o texto|mantida a materia", "separate vote on a passage (destaque): the text was kept"),
    (r"suprimid|retirado o texto", "separate vote on a passage (destaque): the text was removed"),
    (r"emenda", "vote on an amendment"),
    (r"substitutivo", "vote on the substitute text"),
    (r"parecer", "vote on the rapporteur's report"),
    (r"requerimento", "vote on a procedural motion"),
    (r"(aprovad|rejeitad)[oa] o projeto|(aprovad|rejeitad)[oa] a (proposta|materia)",
     "vote on the bill itself"),
)
FINAL = re.compile(r"em segundo turno|redacao final|(aprovad|rejeitad)[oa] o projeto|"
                   r"(aprovad|rejeitad)[oa] a (proposta|materia)|aprovado o substitutivo")

# Where a bill stands, in English, from the Câmara's situação (folded).
STATUS = (
    (r"transformad[oa] em norma juridica", "became law"),
    (r"aguardando sancao", "awaiting presidential sanction"),
    (r"aguardando apreciacao pelo senado", "passed the Câmara; awaiting the Senate"),
    (r"arquivad", "archived"),
    (r"pronta para pauta", "ready for the floor"),
    (r"aguardando designacao de relator", "awaiting a rapporteur"),
    (r"aguardando parecer", "awaiting a rapporteur's report"),
    (r"aguardando (deliberacao|votacao)", "awaiting a vote"),
    (r"tramitando em conjunto", "attached to another bill"),
)

POSITIONS_YES = ("sim",)
POSITIONS_NO = ("não", "nao")
POSITIONS_ABSTAIN = ("abstenção", "abstencao")
LEADERS = ("Governo", "Oposição", "Maioria", "Minoria")


def vote_kind(description):
    text = _fold(description or "").lower()
    return next((label for pat, label in VOTE_KINDS if re.search(pat, text)), None)


def status_english(status):
    text = _fold(status or "").lower()
    return next((label for pat, label in STATUS if re.search(pat, text)), None)


def chamber_name(chamber, organ=None):
    if chamber == "senado":
        return "Senado Federal"
    if not organ or organ == "PLEN":
        return "Câmara dos Deputados, plenary"
    return "Câmara dos Deputados, committee {0}".format(organ)


def bill_label(b):
    """'PL 1338/2022 (formerly PL 3179/2012)' for a renumbered bill."""
    if b is None:
        return None
    former = _former(b)
    return "{0} (formerly {1})".format(b["bill_key"], ", ".join(former)) if former else b["bill_key"]


def _former(b):
    try:
        return json.loads(b["former_keys"] or "[]") if "former_keys" in b.keys() else []
    except (TypeError, ValueError):
        return []


def watched_key(b, key, wl):
    """The watchlist key for a bill: its key, or a number it had before a
    renumbering (an entry not yet re-keyed); None when it is not watched."""
    for k in [key] + (_former(b) if b is not None else []):
        if k and k in wl:
            return k
    return None


def watched_bill(b, key, wl):
    return watched_key(b, key, wl) is not None


def bill_url(b):
    if b is None:
        return None
    if b["camara_id"]:
        return CAMARA_BILL.format(b["camara_id"])
    if b["senado_codigo"]:
        return SENADO_BILL.format(b["senado_codigo"])
    return b["url"]


def bills(conn):
    return {r["bill_key"]: r for r in ce.rows(conn, "SELECT * FROM br_bills")}


def bill_takeaway(b):
    bits = []
    where = status_english(b["status"])
    if where:
        bits.append("Where it stands (Câmara record): {0}".format(where))
    if _former(b):
        bits.append("Renumbered on reaching the Senate: the same bill was {0}".format(
            ", ".join(_former(b))))
    if b["presented"]:
        bits.append("Presented {0}".format(ce.long_date(b["presented"][:10])))
    return ". ".join(bits) or None


def party_split(conn, dkey):
    pairs = [(r["party"], r["position"]) for r in ce.rows(
        conn, "SELECT party, position FROM br_votes WHERE division_key=?", (dkey,))]
    return ce.group_counts(pairs, POSITIONS_YES, POSITIONS_NO, POSITIONS_ABSTAIN), len(pairs)


def rebels(conn, dkey):
    got = ce.rows(conn, "SELECT m.name, v.party, v.position FROM br_votes v LEFT JOIN br_members m "
                        "USING (member_key) WHERE v.division_key=?", (dkey,))
    return ce.rebels([(r["name"], r["party"], r["position"]) for r in got],
                     POSITIONS_YES, POSITIONS_NO)


def orientation_line(conn, dkey):
    got = {r["bloc"]: r["orientation"] for r in ce.rows(
        conn, "SELECT bloc, orientation FROM br_orientations WHERE division_key=?", (dkey,))}
    shown = ["{0} {1}".format(b, got[b]) for b in LEADERS if got.get(b)]
    return ("Leaders' orientations (as recorded): " + ", ".join(shown) + ".") if shown else None


def vote_lines(conn, d):
    yes, no = d["yes"], d["no"]
    if d["secret"]:
        return [ce.tally_line(yes, no, None, d["result"], how="secret ballot"),
                "Secret ballot: the record says only who voted, not how."]
    groups, n = party_split(conn, d["division_key"])
    caveat = None
    if d["chamber"] == "camara":
        caveat = ("'Obstrução' and 'Artigo 17' (the presiding deputy) are stored as printed "
                  "and not counted for or against.")
    abstain = sum(v[2] for v in groups.values()) or None
    return [ce.tally_line(yes, no, abstain, d["result"]),
            ce.split_line(groups),
            orientation_line(conn, d["division_key"]),
            ce.members_line(n, rebels(conn, d["division_key"]), caveat)]


def items(conn, since, until, wl):
    out = []
    bill_rows = bills(conn)
    for d in ce.rows(conn, "SELECT * FROM br_divisions WHERE " + ce.window_sql("date")
                     + " ORDER BY date, division_key", (since, until)):
        b = bill_rows.get(d["bill_key"]) if d["bill_key"] else None
        linked = json.loads(d["linked_bills"] or "[]")
        wkey = watched_key(b, d["bill_key"], wl) or next(
            (watched_key(bill_rows.get(k), k, wl) for k in linked
             if watched_key(bill_rows.get(k), k, wl)), None)
        watched = wkey is not None
        if not ce.on_ground(d["areas"], watched):
            continue
        own = bool(ce.areas_of(d["own_areas"]))
        terms = list(ce.terms_of(d["matched_terms"]))
        refs = []
        for k in ([d["bill_key"]] if d["bill_key"] else []) + linked:
            lb = bill_rows.get(k)
            if lb is not None:
                terms += ce.terms_of(lb["matched_terms"])
                refs.append(lb["ementa"] or "")
        what = vote_kind(d["description"])
        take = "{0}: {1}".format(chamber_name(d["chamber"], d["organ"]),
                                 what or "nominal vote")
        if b is not None:
            take += ", on {0}".format(bill_label(b))
            where = status_english(b["status"])
            if where:
                take += " (bill now: {0})".format(where)
        group_title = ("{0}: {1}".format(bill_label(b), b["ementa"]) if b is not None and b["ementa"]
                       else None)
        out.append(ce.vote(
            CC, d["division_key"], d["date"], d["description"], ce.areas_of(d["areas"]),
            d["tier"], watched, vote_lines(conn, d), url=bill_url(b),
            terms=terms, refs=refs, takeaway=take, own=own, watch_key=wkey,
            group=("bill", d["chamber"], d["bill_key"]) if d["bill_key"] else None,
            group_title=group_title,
            final=bool(FINAL.search(_fold(d["description"] or "").lower()))))
    for b in ce.rows(conn, "SELECT * FROM br_bills WHERE " + ce.window_sql("presented"),
                     (since, until)):
        wkey = watched_key(b, b["bill_key"], wl)
        if not ce.on_ground(b["areas"], wkey is not None):
            continue
        out.append(ce.item(CC, "new", b["bill_key"], b["presented"], b["ementa"],
                           ce.areas_of(b["areas"]), b["tier"], wkey is not None,
                           status=b["status"], url=bill_url(b), terms=b["matched_terms"],
                           watch_key=wkey,
                           body=" ".join(x for x in (b["ementa_detalhada"], b["keywords"]) if x),
                           takeaway=bill_takeaway(b)))
    for b in ce.rows(conn, "SELECT * FROM br_bills WHERE renamed_on IS NOT NULL AND "
                           + ce.window_sql("renamed_on"), (since, until)):
        wkey = watched_key(b, b["bill_key"], wl)
        if not ce.on_ground(b["areas"], wkey is not None):
            continue
        out.append(ce.item(CC, "updated", b["bill_key"], b["renamed_on"], b["ementa"],
                           ce.areas_of(b["areas"]), b["tier"], wkey is not None,
                           status=b["status"], url=bill_url(b), terms=b["matched_terms"],
                           watch_key=wkey,
                           takeaway="Renumbered: the Câmara's record now shows {0} for what was "
                                    "{1} (same Câmara ID {2}). A watchlist entry under the old "
                                    "number still matches; re-key it by hand".format(
                                        b["bill_key"], ", ".join(_former(b)), b["camara_id"])))
    return out


COUNTRY = ce.Country(
    cc=CC, name="Brazil", chamber="Câmara dos Deputados and Senado Federal",
    language="Portuguese", taxonomies=(("taxonomy-pt.yaml", "br"),), items=items,
    flag=":flag-br:", week_ahead=agenda.week_ahead_fn(CC), ahead_note=agenda.ahead_note_fn(CC),
    members_note=("Positions are stored for every nominal vote, with each member's party at "
                  "the vote; most decisions in both houses are symbolic votes, which record no "
                  "position and are not in the store. A Senate secret ballot records only who "
                  "voted. A renumbered bill shows both numbers"),
    coverage=(
        "Collected: every nominal vote of both houses with positions, the Câmara leaders' "
        "orientations, and the proposições those votes name (tools/br_rollcalls.py, phase 1).",
        "Not yet collected: the bill register (phase 2), so a bill filed but never voted is "
        "not seen; tramitação steps (phase 3); the state assemblies.",
        "The week ahead is the Câmara's pauta (plenary and committees) and the Senado's "
        "plenary agenda, matched to bills by number.",
        "Areas 14 (gambling and betting) and 15 (drug decriminalisation) are Brazil's own "
        "(BR3, BR4).",
    ),
)
