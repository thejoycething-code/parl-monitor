"""Mexico's edition: the adapter for src/country_edition.py. FORTNIGHTLY.

Mexico's collector runs on GitHub Actions every second week (X9, odd ISO
weeks: the Chamber's hosts refuse UK addresses, so the Mini only keeps the
clock), and its edition is rendered at the end of that GitHub job, so it
covers a fortnight (Country.cadence_days=14).

THE CHAMBER OF DEPUTIES ONLY. The Senate stays out per its robots.txt
(MX4); it appears only where its minutas reach the Chamber.

The store (tools/mx_rollcalls.py) holds every iniciativa of the LXVI
Legislature from the Gaceta Parlamentaria, with its progress lines verbatim
("Turnada a la Comisión de Salud.", "Dictaminada y aprobada en la Cámara de
Diputados con 344 votos en pro ... el martes 26 de noviembre de 2024"), and
every recorded vote from SITL with each deputy's position and group at the
vote. Our ground is in the iniciativas (presented, sent to committee,
extended, rarely voted); votes on it are rare.

  * new: iniciativas presented in the window;
  * moved: an older iniciativa whose progress gained a DATED line in the
    window (dictaminada, aprobada, desechada, publicada, retirada). A
    committee's deadline extension ("Prórroga hasta ...") is not a stage
    and is not shown;
  * vote: SITL recorded votes, with the group split from SITL's own totals.

Titles are the Gaceta's and SITL's own Spanish, verbatim (a page number the
Gaceta's PDF index glues to a title, "81Que reforma...", is dropped). A
provisional entry ('66/p/<gaceta anchor>') is re-keyed in place when its
real number appears.
"""

from __future__ import annotations

import datetime
import json
import re

from src import country_edition as ce
from src.filter import _fold

CC = "mx"
GACETA = "https://gaceta.diputados.gob.mx"
SITL_VOTE = "https://sitl.diputados.gob.mx/LXVI_leg/estadistico_votacionnplxvi.php?votaciont={0}"
CADENCE_DAYS = 14

MONTHS = {m: i + 1 for i, m in enumerate((
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre"))}
DATE = re.compile(r"\b(\d{1,2}) de (" + "|".join(MONTHS) + r") de (\d{4})")
STAGES = (
    (r"^publicad", "published in the Diario Oficial (law)"),
    (r"aprobada en la camara de senadores", "approved by the Senate"),
    (r"aprobada en la camara de diputados|^aprobada", "approved by the Chamber"),
    (r"desechada", "rejected (desechada)"),
    (r"^dictaminada", "committee report (dictamen)"),
    (r"^retirada", "withdrawn by its author"),
    (r"^devuelta", "returned to the other chamber"),
)
STATUS = {"turnada": "sent to committee", "prorroga": "committee deadline extended",
          "dictaminada": "committee report (dictamen)", "aprobada": "approved by the Chamber",
          "desechada": "rejected (desechada)", "publicada": "published in the Diario Oficial (law)",
          "retirada": "withdrawn by its author"}
ORIGINS = {"diputados": "a deputy or group", "senado": "the Senate or a senator",
           "ejecutivo": "the Executive", "congreso_local": "a state congress",
           "ciudadanos": "citizens", "otro": "another body"}
YES, NO, ABSTAIN = ("a favor",), ("en contra",), ("abstención", "abstencion")


def clean_title(title):
    return re.sub(r"^\d+(?=Que\b)", "", ce.clean(title))


def line_date(line):
    """The ISO date a progress line records, or None ('Prórroga' lines: None)."""
    text = _fold(line or "").lower()
    if text.startswith("prorroga"):
        return None
    hit = DATE.search(text)
    if not hit:
        return None
    try:
        return datetime.date(int(hit.group(3)), MONTHS[hit.group(2)], int(hit.group(1))).isoformat()
    except ValueError:
        return None


def stage(line):
    text = _fold(line or "").lower().strip()
    return next((label for pat, label in STAGES if re.search(pat, text)), None)


def gaceta_url(r):
    ref = r["gaceta_ref"]
    return GACETA + ref if ref and ref.startswith("/") else None


def ini_takeaway(r, line=None):
    bits = []
    origin = ORIGINS.get(r["origin"] or "")
    kind = "Minuta from the Senate" if r["kind"] == "minuta" else "Iniciativa"
    bits.append("{0}{1}{2}".format(kind, " from " + origin if origin and r["kind"] != "minuta"
                                   else "", " ({0})".format(r["party"]) if r["party"] else ""))
    if line:
        what = stage(line)
        if what:
            bits.append("New stage: {0}".format(what))
    else:
        where = STATUS.get(r["status"] or "")
        if where:
            bits.append("Now: {0}".format(where))
    shown = line if line else (progress(r) or [None])[-1]
    if r["turno"] and (r["turno"] not in (shown or "")):
        bits.append("Committee: {0}".format(r["turno"]))
    if r["provisional"]:
        bits.append("Provisional Gaceta entry; it takes its real number within weeks")
    return ". ".join(bits)


def progress(r):
    try:
        return [ln for ln in json.loads(r["status_lines"] or "[]") if ln]
    except (TypeError, ValueError):
        return []


def watched_votes(wl):
    out = {}
    for key, entry in wl.items():
        for v in (entry.get("votaciones") or []) if isinstance(entry, dict) else []:
            out[int(v)] = key
    return out


def group_split(raw):
    try:
        got = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return {g: list(v[:3]) for g, v in got.items() if isinstance(v, list)}


def rebels(conn, dkey):
    got = ce.rows(conn, "SELECT m.name, v.party, v.position FROM mx_votes v LEFT JOIN mx_members m "
                        "USING (member_key) WHERE v.division_key=?", (dkey,))
    return ce.rebels([(r["name"], r["party"], r["position"]) for r in got], YES, NO)


def items(conn, since, until, wl):
    out = []
    by_vote = watched_votes(wl)
    inis = {r["ini_key"]: r for r in ce.rows(conn, "SELECT * FROM mx_iniciativas")}
    for d in ce.rows(conn, "SELECT * FROM mx_divisions WHERE " + ce.window_sql("date")
                     + " ORDER BY date, votaciont", (since, until)):
        keys = json.loads(d["ini_keys"] or "[]")
        wkey = next((k for k in keys if k in wl), None) or by_vote.get(d["votaciont"])
        watched = wkey is not None
        if not ce.on_ground(d["areas"], watched):
            continue
        terms = list(ce.terms_of(d["matched_terms"]))
        refs = []
        for k in keys:
            if k in inis:
                terms += ce.terms_of(inis[k]["matched_terms"])
                refs.append(inis[k]["title"] or "")
        take = "Chamber of Deputies, recorded vote"
        if keys:
            take += " on iniciativa {0}".format(", ".join(keys[:4]) + (
                " and {0} more".format(len(keys) - 4) if len(keys) > 4 else ""))
        if d["solo_asistencia"] or d["ausente"]:
            take += "; present without voting {0}, absent {1}".format(
                d["solo_asistencia"] or 0, d["ausente"] or 0)
        out.append(ce.vote(
            CC, d["division_key"], d["date"], d["title"], ce.areas_of(d["areas"]), d["tier"],
            watched,
            [ce.tally_line(d["favor"], d["contra"], d["abstencion"]),
             ce.split_line(group_split(d["groups"]), "By group"),
             ce.members_line(d["positions"], rebels(conn, d["division_key"]))],
            url=SITL_VOTE.format(d["votaciont"]) if d["legislature"] == 66 else None, terms=terms, refs=refs,
            takeaway=take, own=bool(ce.areas_of(d["own_areas"])), watch_key=wkey))
    for r in inis.values():
        watched = r["ini_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        presented = (r["presented"] or "")[:10]
        if since < presented <= until:
            lines = progress(r)
            out.append(ce.item(CC, "new", r["ini_key"], presented, clean_title(r["title"]),
                               ce.areas_of(r["areas"]), r["tier"], watched,
                               status=lines[-1] if lines else None, url=gaceta_url(r),
                               terms=r["matched_terms"], takeaway=ini_takeaway(r)))
            continue
        moves = [(line_date(ln), ln) for ln in progress(r)]
        moves = [(d, ln) for d, ln in moves if d and since < d <= until]
        if moves:
            when, line = moves[-1]
            out.append(ce.item(CC, "moved", r["ini_key"], when, clean_title(r["title"]),
                               ce.areas_of(r["areas"]), r["tier"], watched, status=line,
                               url=gaceta_url(r), terms=r["matched_terms"],
                               takeaway=ini_takeaway(r, line)))
    return out


COUNTRY = ce.Country(
    cc=CC, name="Mexico", chamber="Cámara de Diputados", language="Spanish",
    taxonomies=(("taxonomy-es.yaml", "mx"),), items=items, flag=":flag-mx:",
    cadence_days=CADENCE_DAYS, frequency="Fortnightly (X9)",
    members_note=("Every recorded vote carries each deputy's position and group at the vote. "
                  "The Senate is not read (MX4, its robots.txt) and appears only where its "
                  "minutas reach the Chamber. This edition is fortnightly (X9)"),
    coverage=(
        "Collected on a GitHub runner every second week (X9; the Chamber refuses UK "
        "addresses): every iniciativa of the LXVI from the Gaceta Parlamentaria with its "
        "progress lines, and every SITL recorded vote with each deputy's position.",
        "Committee deadline extensions ('Prórroga hasta ...') are stored but not shown as "
        "stage moves.",
        "Not collected: the Senate (MX4), the Diario de los Debates, committee dictámenes' "
        "texts, the Supreme Court and the 32 state congresses.",
    ),
)
