#!/usr/bin/env python3
"""Paraguay scoping: measure the PROPOSED Spanish terms, and the shared English
taxonomy, against Paraguayan legislative text. OFFLINE: reads only the raw
probe archive of 9 October 2026 (data/raw/2026-10-09/py-probe_*). Nothing here
is a taxonomy file and nothing is stored; see docs/paraguay-scope.md.

    python3 tools/py_measure.py            # counts per area, both corpora
    python3 tools/py_measure.py --list     # and every matched item

Two corpora:
  * VOTES: every recorded (nominal/electronic) vote SILpy lists for both
    chambers, parliamentary years 2023-24 to 2026-27 (the listing pages
    /web/votaciones/<S|D>/<periodo>). Text = the motion, the result line and
    the acapite of the expediente voted on.
  * BILLS: the six newest pages (6,000 expedientes, October 2020 to May 2023,
    all types) of the open-data API listing (datos.congreso.gov.py), whose
    listing stops at May 2023. Text = the acapite.

SILpy text is mostly upper case with inconsistent accents ("EDUCACION Y
CIENCAS", "TITULO"), so text AND terms are accent-folded before matching
(the PROPOSED terms are written unaccented). The shared filter does not
fold accents; that is a decision for the Spanish taxonomy (see the scope doc).
"""

from __future__ import annotations

import glob
import gzip
import html
import json
import os
import re
import sys
import tempfile
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from src import filter as filt  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw", "2026-10-09")
HIDDEN = (11,)

W = lambda term, *guards: {"term": term, "with": list(guards)}  # noqa: E731

# PROPOSED, v0.1, for Chris's approval. (PY) marks a Paraguay-specific term in
# the scope doc; the dict itself does not care.
PROPOSED = {
    "1_abortion": {
        "tier1": ["aborto*", "abortiv*", "interrupcion voluntaria del embarazo",
                  "interrupcion legal del embarazo", "interrupcion del embarazo",
                  "por nacer", "no nacido*", "vida desde la concepcion", "desde la concepcion",
                  W("derecho a la vida", "concepcion", "nacer", "embarazo", "aborto", "gestacion"),
                  "provida", "pro vida", "misoprostol", "mifepristona",
                  "pildora del dia despues", "pildora del dia siguiente",
                  W("objecion de conciencia", "aborto", "salud", "medic", "sanitari"),
                  "consenso de ginebra"],
        "tier2": ["salud sexual y reproductiva", "derechos sexuales y reproductivos",
                  "derechos reproductivos", "embarazo adolescente", "embarazo infantil",
                  "embarazo* precoz*", W("no madres", "ninas"), "anticoncepci*", "anticonceptiv*",
                  "planificacion familiar", "duelo gestacional", "muerte perinatal",
                  W("embarazada*", "apoyo", "vulnerab", "proteccion integral")],
    },
    "2_assisted_dying": {
        "tier1": ["eutanasi*", "suicidio asistido", "suicidio medicamente asistido", "muerte digna",
                  "muerte asistida", "ayuda para morir", "homicidio motivado por suplica"],
        "tier2": ["cuidados paliativos", "medicina paliativa", "voluntades anticipadas", "testamento vital",
                  "final de la vida", "fin de la vida", "enfermedades terminales",
                  "prevencion del suicidio"],
    },
    "3_gender_medicine_children": {
        "tier1": ["bloqueador* de la pubertad", "bloqueador* puberal*", "hormonizacion",
                  "terapia hormonal cruzada", "hormonas cruzadas", "disforia de genero",
                  "incongruencia de genero", "menores trans", "ninez trans", "infancias trans",
                  "reasignacion de sexo", "reasignacion sexual", "afirmacion de genero",
                  "detransici*", W("cambio de sexo", "menor", "nino", "nina", "adolescente")],
        "tier2": [W("transicion de genero", "menor", "nino", "nina", "adolescente"),
                  W("tratamiento hormonal", "menor", "adolescente", "genero", "trans")],
    },
    "4_conversion_practices": {
        "tier1": ["terapia* de conversion", "terapias reparativas", "ECOSIEG",
                  "esfuerzos de cambio de orientacion sexual", "practicas de conversion"],
        "tier2": [],
    },
    "5_sex_based_rights": {
        "tier1": ["ideologia de genero", "teoria de genero", "identidad de genero",
                  "expresion de genero", "identidad autopercibida", "personas trans",
                  "transgenero*", "transexual*", "no binari*", "LGBT*", "LGTB*", "LGBTI*",
                  "LGTBI*", W("29664", "educacion", "MEC", "genero")],
        "tier2": ["enfoque de genero", "perspectiva de genero", "igualdad de genero",
                  "equidad de genero", "razones de genero", "violencia de genero",
                  "feminicidio*", "femicidio*", "Ley 5777", "Ley N 5777", "orientacion sexual",
                  "diversidad sexual", "lenguaje inclusivo",
                  "Belem do Para", "CEDAW", "paridad"],
    },
    "6_parental_rights_education": {
        "tier1": ["derecho de los padres", "derechos de los padres", "derechos parentales",
                  "derecho preferente de los padres", "educacion sexual integral",
                  "educacion integral de la sexualidad", "educacion sexual",
                  "marco rector pedagogico", "transformacion educativa",
                  W("plan nacional 2040", "educa", "MEC", "transformacion"), "PNTE",
                  "con mis hijos no te metas", "homeschooling", "educacion en casa",
                  "educacion en el hogar", "libertad de ensenanza"],
        "tier2": ["padres de familia", "mesa tecnica de padres", "patria potestad",
                  W("malla curricular", "genero", "sexual", "valores", "familia"),
                  W("curricul*", "genero", "sexual", "valores", "familia", "religio"),
                  W("materiales educativos", "genero", "sexual"), "textos escolares",
                  W("redes sociales", "menores", "ninos", "ninas", "adolescentes")],
    },
    "7_free_speech_online_safety": {
        "tier1": ["libertad de expresion", "discurso* de odio", "delito* de odio",
                  "incitacion al odio", "censura previa", "pornograf*", "verificacion de edad"],
        "tier2": ["libertad de prensa", "libertad de informacion", "desinformacion",
                  "noticias falsas", W("censura", "expresion", "redes", "prensa", "internet"),
                  "proteccion de datos personales", "ciberacoso"],
    },
    "8_freedom_of_religion": {
        "tier1": ["libertad religiosa", "libertad de culto", "libertad de conciencia",
                  "objecion de conciencia", "entidades religiosas", "confesion* religios*",
                  "educacion religiosa", "simbolos religiosos", "persecucion religiosa",
                  "cristianos perseguidos", "minorias religiosas"],
        "tier2": ["iglesia catolica", "conferencia episcopal", "santa sede",
                  "iglesia evangelica", "lugares de culto", "instituciones religiosas",
                  "capellan*"],
    },
    "9_marriage_family": {
        "tier1": ["matrimonio igualitario", "matrimonio entre personas del mismo sexo",
                  "matrimonio homosexual", "union civil", "uniones civiles",
                  "adopcion homoparental", "proteccion de la familia",
                  "proteccion integral de la familia", "pro familia", "profamilia",
                  "familia natural"],
        "tier2": ["divorcio*", "union* de hecho", "familias numerosas", "natalidad",
                  "licencia por maternidad", "licencia de paternidad", "permiso de paternidad",
                  "lactancia materna", "Ley 5508", "Ministerio de la Familia",
                  "dia de la familia"],
    },
    "10_surrogacy_embryology": {
        "tier1": ["gestacion subrogada", "maternidad subrogada", "vientre* de alquiler",
                  "gestacion por sustitucion", "reproduccion humana asistida",
                  "tecnicas de reproduccion asistida", "fecundacion in vitro", "clonacion"],
        "tier2": ["reproduccion asistida", "embrion*", "donacion de gametos",
                  "donacion de ovulos"],
    },
    "11_migration": {
        "tier1": ["migracion", "migraciones", "migrante*", "inmigra*",
                  {"term": "refugiad*", "without": ["connacionales", "repatriados"]},
                  W("asilo", "politico", "refugi", "proteccion internacional"), "Ley 6984"],
        "tier2": ["migratori*", W("extranjeros", "radicacion", "expulsion", "migra"),
                  "deportaci*"],
    },
    "12_prostitution": {
        "tier1": ["trata de personas", "trata de seres humanos", "Ley 4788", "prostituci*",
                  "proxenetismo", "proxeneta*", "explotacion sexual", "pornografia infantil",
                  "material de abuso sexual infantil"],
        "tier2": ["abuso sexual infantil", W("abuso sexual", "nino", "nina", "menor", "adolescente"),
                  "criadazgo", "agresores sexuales", "turismo sexual"],
    },
    "13_organ_donation": {
        "tier1": ["donacion de organos", "trasplante* de organos", "trafico de organos",
                  "donante* de organos", "Ley Anita", "donacion presunta", "consentimiento presunto"],
        "tier2": ["trasplante*", "ablacion y trasplante"],
    },
}


def fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c))


def proposed_taxonomy():
    raw = {"version": "py-0.1", "areas": PROPOSED}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as fh:
        yaml.safe_dump(raw, fh, allow_unicode=True)
        path = fh.name
    try:
        return filt.load_taxonomy(path)
    finally:
        os.unlink(path)


def _clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse_vote_listing(page):
    """One SILpy /web/votaciones/<chamber>/<periodo> page -> one dict per vote."""
    out = []
    for row in re.split(r'<tr data-ri="', page)[1:]:
        vid = re.search(r"votacion/(\d+)", row)
        if not vid:
            continue
        g = lambda pat: (lambda m: _clean(m.group(1)) if m else None)(re.search(pat, row, re.S))  # noqa: E731
        aca = re.search(r':acapite" href="[^"]*expediente/(\d+)"[^>]*>(.*?)</a>', row, re.S)
        out.append({"votacion_id": int(vid.group(1)), "motion": g(r'<span title="([^"]*)"'),
                    "result": g(r'insignia resultado-tramite">([^<]*)<'),
                    "date": g(r"(\d\d/\d\d/\d{4})"),
                    "expediente_id": aca.group(1) if aca else None,
                    "acapite": _clean(aca.group(2)) if aca else None,
                    "expediente": g(r':expediente" href[^>]*>([^<]*)<')})
    return out


def load_votes():
    votes = []
    for path in sorted(glob.glob(os.path.join(RAW, "py-probe_vl_*_*.html.gz"))):
        chamber = os.path.basename(path).split("_")[2]
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for v in parse_vote_listing(fh.read()):
                v["chamber"] = chamber
                v["text"] = " ".join(x for x in (v["motion"], v["result"], v["acapite"]) if x)
                votes.append(v)
    return votes


def load_bills():
    bills = []
    for path in sorted(glob.glob(os.path.join(RAW, "py-probe_api_proyecto_o*.json.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for b in json.load(fh):
                b["text"] = b.get("acapite") or ""
                bills.append(b)
    return bills


def scan(tax, items, folded):
    hits = []
    for it in items:
        text = fold(it["text"]) if folded else it["text"]
        res = filt.filter_item(tax, filt.Watchlist(entities=[], bill_titles=[], act_shorts=[]),
                               text, title=text)
        if res.issue_areas:
            hits.append((it, res))
    return hits


def report(name, items, hits, key, log=print, listing=False):
    ours = [(it, r) for it, r in hits if any(a not in HIDDEN for a in r.issue_areas)]
    log("{0}: {1} item(s), {2} matched any area, {3} on our ground (area 11 hidden); "
        "{4} distinct expediente(s) on our ground".format(
            name, len(items), len(hits), len(ours), len({it[key] for it, _ in ours})))
    by_area = {}
    for it, r in hits:
        for a in r.issue_areas:
            by_area.setdefault(a, set()).add(it[key])
    for a in sorted(by_area):
        log("    area {0:2d}: {1} expediente(s)".format(a, len(by_area[a])))
    if listing:
        seen = set()
        for it, r in hits:
            if it[key] in seen:
                continue
            seen.add(it[key])
            log("      {0} {1} {2}".format(r.issue_areas, ",".join(r.matched_terms[:3]),
                                          (it.get("acapite") or "")[:120]))


def main():
    listing = "--list" in sys.argv
    votes, bills = load_votes(), load_bills()
    es = proposed_taxonomy()
    en = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    print("== PROPOSED Spanish terms (accent-folded)")
    report("VOTES 2023-2027", votes, scan(es, votes, True), "expediente_id", listing=listing)
    report("BILLS 2020-2023", bills, scan(es, bills, True), "idProyecto", listing=listing)
    print("== Shared ENGLISH taxonomy (config/taxonomy.yaml), as is")
    report("VOTES 2023-2027", votes, scan(en, votes, False), "expediente_id", listing=listing)
    report("BILLS 2020-2023", bills, scan(en, bills, False), "idProyecto", listing=listing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
