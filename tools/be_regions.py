#!/usr/bin/env python3
"""Belgium's community and regional parliaments (13 October 2026): bills for
decrees and ordinances, resolutions, motions, petitions, the Flemish
Parliament's recorded votes with every member's position, and members, into
the ber_* tables (src/be_regions_store.py).

    python3 tools/be_regions.py                       # every parliament below
    python3 tools/be_regions.py --parliament vl pw    # some of them
    python3 tools/be_regions.py --reclassify          # offline, after a taxonomy change
    python3 tools/be_regions.py --dry-run             # read each once, store nothing

Scoped, live-probed, in docs/belgium-regions-scope.md. Education, youth,
family allowances, health prevention and culture are community matters, so
school sex education (EVRAS), gender in schools, family policy and
religious-symbol rules land here, not in the federal Chamber.

  vl   Vlaams Parlement. Its open data (ws.vlpar.be): the documents of the
       legislature (bills for decrees, resolutions, motions, concept notes,
       petitions) from the search service, one query per type, re-read whole
       each run (about 12 pages of 100); each status is dated. For documents
       on our ground or watched that reached the plenary in the vote window,
       the document's open-data record gives every recorded vote with each
       member's position and fractie. Members from /vv/op-datum.
  pw   Parlement de Wallonie. Its documented Open Data (/opendata/): every
       publication of the legislature of the types DECRET, RES, MOTION and
       PARCHEMIN (four requests), grouped into one row per document number;
       the latest publication is the status. Members from
       composition_dep_od.php (name, group, constituency only).
  bru  Parlement bruxellois and cocom, the United Assembly of the Common
       Community Commission (ARCCC): the legislative-dossier list the
       parliament's website loads (one JSON file for the legislature), with
       the French and Dutch titles and every document of the dossier.
  fwb  Parlement de la Fédération Wallonie-Bruxelles (the French Community:
       education, so EVRAS). PARTIAL: the newest-documents page (18 cards)
       and the plenary agendas listed on /agenda. The full index is an
       Algolia search whose key sits in the site's code; it is not used.

Not read: the German-speaking Community's parliament (pdg.be answers with a
Cloudflare bot challenge, robots.txt included: never bypassed), COCOF and
the VGC (src/be_regions_store.BLOCKED). No parliament but Flanders publishes
its votes outside PDF reports.

CLASSIFICATION as the federal collector does it (tools/be_rollcalls.py):
Dutch text against config/taxonomy-nl.yaml and French text against
config/taxonomy-fr.yaml, both loaded for country "be" (Brussels has both
titles, each matched against its own list), plus config/watchlist-be.yaml's
`regions` section BY KEY. German has no source yet (taxonomy-atch would be
the list). Nothing is hand-classified.

Exit 0, or 3 when it stored what it could and recorded gaps (the gaps table
and [gap] lines): jobs/be-weekly.sh treats its failure as a [gap] line and
never as the run's.

ROBOTS.TXT AT RUN TIME: every request goes through src/robots_guard.guard():
the two documented open-data APIs (ws.vlpar.be/e/opendata/,
www.parlement-wallonie.be/opendata/) are fetched as they are; every website
request (the Flemish search route, the Brussels dossier file, the PFWB
pages) asks robots.txt first, read once per host per run. A refusal is a
[gap] line and a gaps row, never fetched and never fatal.
"""

from __future__ import annotations

import argparse
import datetime
import html
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import be_regions_store as store  # noqa: E402
from src import db, drain  # noqa: E402
from src import filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import guard  # noqa: E402

FEED = "be-regions"
TAXONOMY_NL = os.path.join(ROOT, "config", "taxonomy-nl.yaml")
TAXONOMY_FR = os.path.join(ROOT, "config", "taxonomy-fr.yaml")
TAXONOMY_COUNTRY = "be"
BUDGET_S = 300
ORDER = ("vl", "pw", "bru", "fwb")
_EMPTY_WL = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])
HIDDEN = {11}              # migration: stored, never counted or shown (src/latam.HIDDEN_AREAS)

# --- Vlaams Parlement --------------------------------------------------------
VL_LEGISLATURE_START = "2024-06-09"
VL_SEARCH = ("https://ws.vlpar.be/api/search/query/inmeta:publicatiedatum:daterange:"
             "{a}..{b}%20{f}?collection=vp_collection&max=100&page={p}&sort=date")
# One query per document type (the search's requiredfields parameter is
# ignored; an inmeta: term in the path filters). ~ is a partial match.
VL_FILTERS = ("inmeta:aggregaattype~decreet", "inmeta:aggregaattype~resolutie",
              "inmeta:aggregaattype=Motie", "inmeta:aggregaattype~Conceptnota",
              "inmeta:aggregaattype=Verzoekschrift")
VL_MAX_PAGES = 40
VL_PI = "https://ws.vlpar.be/e/opendata/pi/{0}"
VL_MEMBERS = "https://ws.vlpar.be/e/opendata/vv/op-datum?datum={0}"
VL_VOTE_DAYS = 21          # a plenary status this recent has its votes read
VL_FIRST_VOTE_DAYS = 400   # ... on the first read of the store (capped below)
VL_MAX_VOTE_READS = 40

# --- Parlement de Wallonie ---------------------------------------------------
PW_LEGISLATURE = "12"      # 2024-2029 (legislatures_od.php)
PW_PUB = ("https://www.parlement-wallonie.be/opendata/publications_od.php"
          "?f=json&idleg={0}&type={1}")
PW_TYPES = ("DECRET", "RES", "MOTION", "PARCHEMIN")
PW_MEMBERS = "https://www.parlement-wallonie.be/opendata/composition_dep_od.php?f=json"

# --- Brussels ------------------------------------------------------------------
BRU_LEGISLATURE = "24-29"
BRU_HOST = "https://www.parlement.brussels"
BRU_JSON = BRU_HOST + "/prb_includes/weblex/data/dos_leg_legis_{0}.json"

# --- Parlement de la Fédération Wallonie-Bruxelles -----------------------------
FWB_HOST = "https://www.pfwb.be"
FWB_LIST = FWB_HOST + "/documents-parlementaires"
FWB_AGENDA = FWB_HOST + "/agenda"
FWB_MAX_AGENDAS = 4


# --- small helpers -------------------------------------------------------------

def text(s):
    """Tags dropped, entities decoded, whitespace folded."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\x92", "’")
    return re.sub(r"\s+", " ", s).strip()


def iso(s):
    """'2026-10-02T00:00:00+0200', '2026-10-02' or '08/10/2026' -> '2026-10-02'."""
    s = (s or "").strip()
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)", s)
    if m:
        return "-".join(m.groups())
    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", s)
    if m:
        return "{2}-{1}-{0}".format(*m.groups())
    return None


MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")


def long_date(iso_date):
    """'2026-10-07' -> '7 October 2026'."""
    try:
        d = datetime.date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return iso_date or ""
    return "{0} {1} {2}".format(d.day, MONTHS[d.month - 1], d.year)


def session_name(s):
    """'26-27' -> '2026-2027'; '2025-2026' and 'se2024' as they are."""
    s = (s or "").strip()
    m = re.match(r"^(\d\d)-(\d\d)$", s)
    if m:
        return "20{0}-20{1}".format(*m.groups())
    return s


def bill_kind(doc_type):
    """Our kind from the source's words, in Dutch or French."""
    t = (doc_type or "").lower()
    if "begroting" in t or "rekening" in t or "budget" in t or "compte" in t:
        return "other"
    if "decreet" in t or "décret" in t or "ordonnan" in t or "règlement" in t \
            or "reglement" in t or "parchemin" in t:
        return "bill"
    if "resolutie" in t or "résolution" in t:
        return "resolution"
    if "motie" in t or "motion" in t:
        return "motion"
    if "conceptnota" in t:
        return "concept"
    if "verzoekschrift" in t or "pétition" in t or "petition" in t:
        return "petition"
    if "question" in t or "vraag" in t or "interpellation" in t:
        return "question"
    return "other"


# --- Vlaams Parlement: parsers ------------------------------------------------

def vl_search_url(f, page, today, start=VL_LEGISLATURE_START):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=1)).isoformat()
    return VL_SEARCH.format(a=start, b=end, f=f, p=page)


def _metatags(result):
    out = {}
    for t in (result.get("metatags") or {}).get("metatag") or []:
        out.setdefault(t.get("name"), []).append(t.get("value"))
    return out


def parse_vl_search(data):
    """Documents from one page of the search service's JSON."""
    out = []
    for r in (data or {}).get("result") or []:
        m = _metatags(r)

        def one(name):
            v = m.get(name)
            return (v[0] or "").strip() if v else ""
        number, year = one("nummer"), one("zittingsjaar")
        pi = re.search(r"/(pi|vzs)/(\d+)", one("opendata"))
        if not number or not year or not pi:
            continue
        # petitions (verzoekschriften) have their own number series
        key = "vl/{0}/{1}{2}".format(year, "vzs-" if pi.group(1) == "vzs" else "", number)
        doc_type = one("aggregaattype") or one("initiatief")
        dates = [iso(v) for k, vs in m.items() if (k or "").startswith("statusdatum_")
                 for v in vs]
        dates = [d for d in dates if d]
        # 'Daniëls, Koen' -> 'Koen Daniëls'; 'de Vlaamse Regering' as it is
        authors = [" ".join(reversed([x.strip() for x in a.split(",", 1)])) if "," in a else a
                   for a in m.get("indiener") or [] if a]
        out.append({
            "key": key, "parliament": "vl", "seq": _pw_n(one("volgnummer")) or 99,
            "kind": bill_kind(doc_type), "doc_type": doc_type, "session": year,
            "number": number, "title": one("titel") or one("basisstuk"), "title_alt": None,
            "lang": "nl", "subject": "; ".join(t for t in m.get("thema") or [] if t) or None,
            "authors": ", ".join(authors[:8]) + (" and {0} other(s)".format(len(authors) - 8)
                                                if len(authors) > 8 else "") or None,
            "date": iso(one("statusdatum_ingediend")) or iso(one("eerstepublicatie"))
            or iso(one("publicatiedatum")),
            "status": one("status") or None, "status_date": max(dates) if dates else None,
            "url": one("displayurl") or r.get("url"),
            "pi": pi.group(2) if pi.group(1) == "pi" else None})
    return out


def _person_name(p):
    return " ".join(x for x in ((p or {}).get("voornaam"), (p or {}).get("naam")) if x).strip()


def parse_vl_votes(data, doc_key):
    """[(vote, [(member_key, name, group, position)])] from a document's
    open-data record (/pi/<id>): every recorded vote it carries."""
    blocks = (data or {}).get("journaallijn-stemmingen") or []
    if isinstance(blocks, dict):
        blocks = [blocks]
    out = []
    for b in blocks:
        jln = b.get("journaalLijn") or b.get("journaallijn") or {}
        jid = jln.get("id")
        verg = jln.get("vergadering") or {}
        date = iso(jln.get("datum")) or iso(verg.get("datumbegin"))
        title = text(jln.get("titel"))
        for n, s in enumerate(b.get("stemming") or [], 1):
            positions = []
            for field, pos in (("stemming-voor", "yes"), ("stemming-tegen", "no"),
                               ("stemming-onthouding", "abstain")):
                for v in s.get(field) or []:
                    p = v.get("persoon") or {}
                    if p.get("id") is None:
                        continue
                    positions.append(("vl/{0}".format(p["id"]), _person_name(p),
                                      ((p.get("fractie") or {}).get("naam")), pos))
            adopted = s.get("aangenomen")
            out.append(({
                "key": "vl/{0}/{1}".format(jid, n), "parliament": "vl", "doc_key": doc_key,
                "date": date, "title": title, "yes": s.get("aantal-voor"),
                "no": s.get("aantal-tegen"), "abstain": s.get("aantal-onthouding"),
                "adopted": None if adopted is None else int(bool(adopted)),
                "matter": s.get("materie"),
                "url": ("https://www.vlaamsparlement.be/nl/parlementair-werk/plenaire-vergaderingen/"
                        "{0}/verslag/{1}".format(verg["id"], jid) if verg.get("id") and jid
                        else None)}, positions))
    return out


def parse_vl_members(data):
    out = []
    for it in (data or {}).get("items") or []:
        p = it.get("volksvertegenwoordiger") or {}
        if p.get("id") is None:
            continue
        out.append({"key": "vl/{0}".format(p["id"]), "parliament": "vl", "name": _person_name(p),
                    "group": (p.get("fractie") or {}).get("naam"),
                    "constituency": p.get("kieskring")})
    return out


# --- Parlement de Wallonie: parsers ----------------------------------------------

_PW_REF = re.compile(r"^\s*(\w+)\s+(\d+)(?:\s*N°\s*(\w+))?\s*\(([^)]+)\)")
_PW_BY = re.compile(r",?\s+déposée?s?\s+par\s+(.+?)(?:\s*\(Doc\..*)?$", re.I)


def _pw_n(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


def parse_pw(pubs):
    """One row per document number from the Open Data publications (every
    type), the first publication giving the title, the latest the status."""
    groups = {}
    for p in pubs or []:
        m = _PW_REF.match(p.get("PUB_REFERENCE") or "")
        if not m:
            continue
        typ, num, sub, ses = m.groups()
        groups.setdefault((ses, num), []).append((typ, sub, p))
    out = []
    for (ses, num), docs in groups.items():
        # by date; on one day the parchemin (the adopted text sent on) comes last
        docs.sort(key=lambda d: (iso(d[2].get("PUB_DATUM")) or "", d[0] == "PARCHEMIN",
                                 _pw_n(d[1])))
        base = [d for d in docs if d[0] != "PARCHEMIN"]
        first = min(base, key=lambda d: (_pw_n(d[1]) or 99, iso(d[2].get("PUB_DATUM")) or "")) \
            if base else docs[0]
        raw_title = text(first[2].get("PUB_TITRE"))
        raw_title = re.sub(r"\s*\(Doc\.\s*\d+.*?\)\s*$", "", raw_title)
        title, authors = raw_title, None
        by = _PW_BY.search(raw_title)
        if by and first[0] != "PARCHEMIN":
            authors = by.group(1).strip()
            title = raw_title[:by.start()].strip()
        title = re.split(r"\s+-\s+(?=Texte adopté|Rapport|Amendement)", title)[0].strip()
        last = docs[-1]
        if last[0] == "PARCHEMIN":
            status = "texte adopté et transmis au Gouvernement (parchemin)"
        elif last is first:
            status = "déposé"
        else:
            parts = text(last[2].get("PUB_TITRE")).rsplit(" - ", 1)
            status = parts[1] if len(parts) == 2 else "document n° {0}".format(last[1])
        typ = first[2].get("PUB_TYPECOMPLET") or first[0]
        doc_type = (re.match(r"^(Projet|Proposition) de (décret|résolution|motion)", title)
                    or re.match(r"^(Projet) de (motion)", title))
        doc_type = doc_type.group(0) if doc_type else typ
        out.append({
            "key": "pw/{0}/{1}".format(ses, num), "parliament": "pw",
            "kind": bill_kind(doc_type), "doc_type": doc_type, "session": ses, "number": num,
            "title": title, "title_alt": None, "lang": "fr", "subject": None,
            "authors": authors, "date": iso(first[2].get("PUB_DATUM")), "status": status,
            "status_date": iso(last[2].get("PUB_DATUM")),
            "url": (first[2].get("PUB_LIEN") or "").replace("http://", "https://", 1) or None})
    return out


def parse_pw_members(data):
    out = []
    for d in (data or {}).get("deputes") or []:
        if not d.get("dep_id"):
            continue
        name = " ".join(x for x in (d.get("dep_prenom"), (d.get("dep_nom") or "").title()) if x)
        out.append({"key": "pw/{0}".format(d["dep_id"]), "parliament": "pw", "name": name,
                    "group": d.get("dep_parti"), "constituency": d.get("dep_circons")})
    return out


# --- Brussels: parser -------------------------------------------------------------

_BRU_DOC = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>\s*-\s*(.*?)(?=<br\s*/?>|$)', re.S | re.I)


def _bru_docs(cell):
    return [(href, text(code), text(title).rstrip(".")) for href, code, title in _BRU_DOC.findall(cell or "")]


def parse_bru(data, leg=BRU_LEGISLATURE):
    """Dossiers of the Brussels Parliament (PRB) and the ARCCC (COCOM)."""
    out = []
    for r in (data or {}).get("data") or []:
        if len(r) < 10:
            continue
        parl = {"PRB": "bru", "ARCCC": "cocom"}.get(text(r[0]))
        fiche = re.search(r'href="([^"]+)"[^>]*>\s*Fiche\s+([^<]+?)\s*<', r[2] or "")
        if not parl or not fiche:
            continue
        fr, nl = _bru_docs(r[8]), _bru_docs(r[9])
        if not fr and not nl:
            continue
        first_fr = fr[0][2] if fr else None
        first_nl = nl[0][2] if nl else None
        status = None
        if len(fr) > 1:
            status = fr[-1][2]
        number = fiche.group(2).strip()
        doc_type = text(r[6]) or text(r[7])
        out.append({
            "key": "{0}/{1}/{2}".format(parl, leg, number), "parliament": parl,
            "kind": bill_kind(doc_type), "doc_type": doc_type, "session": leg, "number": number,
            "title": first_fr or first_nl, "title_alt": first_nl if first_fr else None,
            "lang": "fr", "subject": None, "authors": None, "date": iso(text(r[5])),
            "status": status, "status_date": None,
            "url": BRU_HOST + html.unescape(fiche.group(1))})
    return out


# --- Parlement de la Fédération Wallonie-Bruxelles: parsers -------------------------

_FWB_CARD = re.compile(r'<a href="(/documents-parlementaires/document-([a-z]+)-(\d+))"(.*?)</a>', re.S)


def _cls(block, name):
    m = re.search(r'class="[^"]*\b{0}\b[^"]*"[^>]*>(.*?)</(?:span|p|div)>'.format(re.escape(name)),
                  block, re.S)
    return text(m.group(1)) if m else ""


def parse_fwb_list(page):
    """Documents from the newest-documents page."""
    out = []
    for path, code, pid, body in _FWB_CARD.findall(page or ""):
        head = re.search(r'a-title--size-medium[^>]*>(.*?)<span class="m-card-documents__title-complement',
                         body, re.S)
        label = text(head.group(1)) if head else ""
        comp = re.search(r'm-card-documents__title-complement(.*?)m-card-documents__content',
                         body, re.S)
        comp = comp.group(1) if comp else ""
        number = re.search(r">\s*(\d+)\s*<", comp)
        number = number.group(1) if number else None
        ses = re.search(r"\(\s*(\d{4}-\d{4})\s*\)", comp)
        ses = ses.group(1) if ses else None
        title = _cls(body, "m-card-documents__subtitle")
        authors = _cls(body, "m-card-documents__text") or None
        date = iso(_cls(body, "m-card-documents__date"))
        if code == "presea" or not title:
            continue            # the chair's list of a sitting: not a document on any ground
        doc_type, status = label, None
        if code == "texadopt":
            # the text adopted in plenary: a status of the document it adopts
            m = re.match(r"^(Projet|Proposition) de (décret|résolution|motion)", title)
            doc_type = m.group(0) if m else label
            status = "texte adopté en séance plénière"
        kind = bill_kind(doc_type)
        if number and ses:
            key = "fwb/{0}/{1}".format(ses, number)
        else:
            key = "fwb/{0}/{1}".format("q" if kind == "question" else code, pid)
        out.append({
            "key": key, "parliament": "fwb", "kind": kind, "doc_type": doc_type,
            "session": ses, "number": number, "title": title, "title_alt": None, "lang": "fr",
            "subject": None, "authors": authors, "date": None if status else date,
            "status": status, "status_date": date if status else None,
            "url": FWB_HOST + path})
    return out


def parse_fwb_agenda_index(page):
    """[(url, ISO date)] of the plenary sittings the agenda page lists."""
    out = []
    for path in re.findall(r'href="(/agendas/seances-plenieres-(\d{4}-\d\d-\d\d)[^"]*)"', page or ""):
        url = FWB_HOST + path[0]
        if url not in [u for u, _ in out]:
            out.append((url, path[1]))
    return out


_FWB_ITEM = re.compile(r"^\s*\d+\.\s*(.+?)\s*\(doc\.\s*(\d+)\s*\(([0-9se-]+)\)", re.I | re.S)


def parse_fwb_plenary(page, date, url):
    """Documents on a plenary agenda: '3. Proposition de résolution ...
    (doc. 285 (2025-2026) n°1 à 4)'."""
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", page or "", flags=re.S)
    lines = [text(x) for x in re.split(r"</(?:p|li|div|h\d)>", body)]
    out, seen = [], set()
    for ln in lines:
        m = _FWB_ITEM.match(ln)
        if not m:
            continue
        what, num, ses = m.group(1), m.group(2), session_name(m.group(3))
        what = re.split(r",\s+déposée?s?\s+par\s+", what)[0].strip()
        key = "fwb/{0}/{1}".format(ses, num)
        if key in seen or len(what) < 12:
            continue
        seen.add(key)
        doc_type = re.match(r"^(Projets? de motion|(Projet|Proposition) de (décret|résolution))",
                            what)
        out.append({
            "key": key, "parliament": "fwb", "kind": bill_kind(doc_type.group(0) if doc_type else what),
            "doc_type": doc_type.group(0) if doc_type else None, "session": ses, "number": num,
            "title": what, "title_alt": None, "lang": "fr", "subject": None, "authors": None,
            "date": None, "status": "on the plenary agenda of {0}".format(long_date(date)),
            "status_date": date, "url": url})
    return out


# --- classification and storing --------------------------------------------------

_TAX = {}


def taxonomies():
    """{'nl': Taxonomy, 'fr': Taxonomy} for Belgium, loaded once; None where absent."""
    if not _TAX:
        for lang, path in (("nl", TAXONOMY_NL), ("fr", TAXONOMY_FR)):
            _TAX[lang] = (filt.load_taxonomy(path, country=TAXONOMY_COUNTRY)
                          if os.path.exists(path) else None)
    return _TAX


def classify(doc, watch_path=None):
    """(areas, matched_terms, tier): each title against its own language's
    list (Brussels: French and Dutch), unioned with the watchlist by key."""
    tax = taxonomies()
    areas, terms, tier = set(), [], None
    alt_lang = "nl" if doc.get("lang") == "fr" else "fr"
    for lang, title, extra in ((doc.get("lang"), doc.get("title"), doc.get("subject")),
                               (alt_lang, doc.get("title_alt"), None)):
        t = tax.get(lang)
        if t is None or not title:
            continue
        res = filt.filter_item(t, _EMPTY_WL, title, extra or "", title=title)
        areas.update(res.issue_areas or [])
        terms += [x for x in res.matched_terms or [] if x not in terms]
        if res.tier is not None:
            tier = res.tier if tier is None else min(tier, res.tier)
    hit = store.watchlist(watch_path).get(doc["key"])
    if hit:
        areas |= set(hit[0])
        terms.append("watch:" + doc["key"])
        tier = tier or 2
    return sorted(areas), terms, tier


def store_doc(conn, d, today, watch_path=None):
    """Insert or update one document. Returns ('new'|'moved'|'same', on_ground)."""
    areas, terms, tier = classify(d, watch_path)
    old = conn.execute("SELECT status, status_date, status_seen, title, date, kind, doc_type, "
                       "authors, title_alt, url FROM ber_docs WHERE doc_key=?",
                       (d["key"],)).fetchone()
    status_date, seen = d.get("status_date"), 0
    state = "new" if old is None else "same"
    if old is not None:
        if d.get("status_date"):
            if d["status_date"] != old[1] or (d.get("status") or None) != (old[0] or None):
                state = "moved"
        elif d.get("status") is None:
            # a source that carries no status (an older FWB card): keep the stored one
            d = dict(d, status=old[0])
            status_date, seen = old[1], old[2] or 0
        elif (d.get("status") or None) != (old[0] or None):
            status_date, seen, state = today, 1, "moved"
        else:
            status_date, seen = old[1], old[2] or 0
        # A partial source (an FWB agenda line or texadopt card: no deposit
        # date) keeps what a fuller read stored: title, link, kind, authors.
        partial = d.get("date") is None
        d = dict(d, date=d.get("date") or old[4],
                 title=old[3] if (partial and old[3]) else d.get("title"),
                 url=old[9] if (partial and old[9]) else d.get("url"),
                 kind=old[5] if (partial and old[5]) else d.get("kind"),
                 doc_type=d.get("doc_type") or old[6],
                 authors=d.get("authors") or old[7], title_alt=d.get("title_alt") or old[8])
        if (d["title"] or "") != (old[3] or ""):
            areas, terms, tier = classify(d, watch_path)
    conn.execute(
        "INSERT INTO ber_docs (doc_key, parliament, kind, doc_type, session, number, title, "
        "title_alt, lang, subject, authors, date, status, status_date, status_seen, url, areas, "
        "matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(doc_key) DO UPDATE SET kind=excluded.kind, doc_type=excluded.doc_type, "
        "session=excluded.session, number=excluded.number, title=excluded.title, "
        "title_alt=excluded.title_alt, subject=COALESCE(excluded.subject, ber_docs.subject), "
        "authors=excluded.authors, date=excluded.date, status=excluded.status, "
        "status_date=excluded.status_date, status_seen=excluded.status_seen, url=excluded.url, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (d["key"], d["parliament"], d.get("kind"), d.get("doc_type"), d.get("session"),
         d.get("number"), d.get("title"), d.get("title_alt"), d.get("lang"), d.get("subject"),
         d.get("authors"), d.get("date"), d.get("status"), status_date, seen, d.get("url"),
         store.dumps(areas), store.dumps(terms), tier, today, today))
    return state, bool(set(areas) - HIDDEN)


def store_docs(conn, docs, today, watch_path=None):
    """(read, on our ground, new, moved)."""
    n = ours = new = moved = 0
    for d in docs:
        state, ground = store_doc(conn, d, today, watch_path)
        n += 1
        ours += ground
        new += state == "new"
        moved += state == "moved"
    conn.commit()
    return n, ours, new, moved


def store_vote(conn, vote, positions, today):
    row = conn.execute("SELECT areas, matched_terms FROM ber_docs WHERE doc_key=?",
                       (vote["doc_key"],)).fetchone()
    conn.execute(
        "INSERT INTO ber_votes (vote_key, parliament, doc_key, date, title, yes, no, abstain, "
        "adopted, matter, url, areas, matched_terms, first_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(vote_key) DO UPDATE SET doc_key=excluded.doc_key, date=excluded.date, "
        "title=excluded.title, yes=excluded.yes, no=excluded.no, abstain=excluded.abstain, "
        "adopted=excluded.adopted, matter=excluded.matter, url=excluded.url, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms",
        (vote["key"], vote["parliament"], vote["doc_key"], vote["date"], vote["title"],
         vote["yes"], vote["no"], vote["abstain"], vote["adopted"], vote["matter"], vote["url"],
         row[0] if row else "[]", row[1] if row else "[]", today))
    conn.execute("DELETE FROM ber_positions WHERE vote_key=?", (vote["key"],))
    conn.executemany("INSERT OR REPLACE INTO ber_positions (vote_key, member_key, member_name, "
                     "group_name, position) VALUES (?,?,?,?,?)",
                     [(vote["key"],) + tuple(p) for p in positions])


def store_members(conn, parliament, members, today):
    conn.execute("UPDATE ber_members SET current=0 WHERE parliament=?", (parliament,))
    for m in members:
        conn.execute(
            "INSERT INTO ber_members (member_key, parliament, name, group_name, constituency, "
            "current, first_seen, last_seen) VALUES (?,?,?,?,?,1,?,?) "
            "ON CONFLICT(member_key) DO UPDATE SET name=excluded.name, "
            "group_name=excluded.group_name, constituency=excluded.constituency, current=1, "
            "last_seen=excluded.last_seen",
            (m["key"], parliament, m["name"], m["group"], m["constituency"], today, today))
    conn.commit()


def note_read(conn, parliament, today, seen, ours, gap=None):
    conn.execute(
        "INSERT INTO ber_reads (parliament, last_read, last_ok, rows_seen, rows_ours, note) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(parliament) DO UPDATE SET last_read=excluded.last_read, "
        "last_ok=COALESCE(excluded.last_ok, ber_reads.last_ok), rows_seen=excluded.rows_seen, "
        "rows_ours=excluded.rows_ours, note=excluded.note",
        (parliament, today, None if gap else today, seen, ours, gap))
    conn.commit()


def _gap(conn, today, detail, log=print):
    log("  [gap] " + detail)
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    conn.commit()


# --- the readers -------------------------------------------------------------------
# Each returns (docs, members, votes, gaps): votes are [(vote, positions)] and
# are read after the documents are stored, so the documents' areas decide
# which votes are read (read_vl_votes).

def read_vl(client, today, budget=None, log=print):
    docs, gaps = [], []
    for f in VL_FILTERS:
        page, pages = 1, 1
        while page <= pages and page <= VL_MAX_PAGES:
            if budget is not None and budget.exhausted():
                gaps.append("Flemish documents read in part (time budget)")
                return docs, None, gaps
            data = client.get_json(vl_search_url(f, page, today), FEED,
                                   "vl-search-{0}-p{1}".format(re.sub(r"\W+", "", f[20:]), page))
            docs += parse_vl_search(data)
            pages = -(-int((data or {}).get("count") or 0) // 100)
            page += 1
    members = None
    try:
        d = datetime.date.fromisoformat(today)
        members = parse_vl_members(client.get_json(VL_MEMBERS.format(d.strftime("%d%m%Y")),
                                                   FEED, "vl-members"))
    except (FetchError, ValueError) as e:
        gaps.append("Flemish members not read ({0})".format(str(e)[:120]))
    # one row per key (the search can list a document under two types)
    # (the service lists a document once per published part: keep its first part)
    uniq = {}
    for doc in sorted(docs, key=lambda d: d.get("seq") or 99):
        uniq.setdefault(doc["key"], doc)
    return list(uniq.values()), members, gaps


def vl_vote_candidates(conn, today, first_read):
    """Documents on our ground or watched whose status reached the plenary
    recently: their open-data record is read for votes."""
    days = VL_FIRST_VOTE_DAYS if first_read else VL_VOTE_DAYS
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT doc_key, url FROM ber_docs WHERE parliament='vl' AND areas NOT IN ('[]', '', '[11]') "
        "AND status LIKE '%plenaire%' AND status_date >= ? ORDER BY status_date DESC",
        (since,)).fetchall()
    return rows[:VL_MAX_VOTE_READS]


def read_vl_votes(conn, client, today, pis, first_read, budget=None, log=print):
    """(votes stored, gaps)."""
    n, gaps = 0, []
    for key, _url in vl_vote_candidates(conn, today, first_read):
        pi = pis.get(key)
        if not pi:
            continue
        if budget is not None and budget.exhausted():
            gaps.append("Flemish votes read in part (time budget)")
            break
        try:
            data = client.get_json(VL_PI.format(pi), FEED, "vl-pi-{0}".format(pi))
        except FetchError as e:
            gaps.append("Flemish votes of {0} not read ({1})".format(key, str(e)[:120]))
            continue
        for vote, positions in parse_vl_votes(data, key):
            store_vote(conn, vote, positions, today)
            n += 1
    conn.commit()
    return n, gaps


def read_pw(client, today, budget=None, log=print):
    pubs, gaps = [], []
    for t in PW_TYPES:
        if budget is not None and budget.exhausted():
            gaps.append("Walloon documents read in part (time budget)")
            break
        data = client.get_json(PW_PUB.format(PW_LEGISLATURE, t), FEED, "pw-" + t.lower())
        pubs += (data or {}).get("publications") or []
    members = None
    try:
        members = parse_pw_members(client.get_json(PW_MEMBERS, FEED, "pw-members"))
    except (FetchError, ValueError) as e:
        gaps.append("Walloon members not read ({0})".format(str(e)[:120]))
    return parse_pw(pubs), members, gaps


def read_bru(client, today, budget=None, log=print):
    data = client.get_json(BRU_JSON.format(BRU_LEGISLATURE), FEED, "bru-dossiers")
    return parse_bru(data), None, []


def read_fwb(client, today, budget=None, log=print):
    gaps = []
    docs = parse_fwb_list(client.get_text(FWB_LIST, FEED, "fwb-documents",
                                          headers={"Accept": "text/html"}))
    try:
        index = parse_fwb_agenda_index(client.get_text(FWB_AGENDA, FEED, "fwb-agenda",
                                                       headers={"Accept": "text/html"}))
    except FetchError as e:
        gaps.append("FWB agenda not read ({0})".format(str(e)[:120]))
        index = []
    for url, date in index[:FWB_MAX_AGENDAS]:
        if budget is not None and budget.exhausted():
            gaps.append("FWB plenary agendas read in part (time budget)")
            break
        try:
            page = client.get_text(url, FEED, "fwb-plenary-" + date,
                                   headers={"Accept": "text/html"})
        except FetchError as e:
            gaps.append("FWB plenary agenda {0} not read ({1})".format(date, str(e)[:120]))
            continue
        docs += parse_fwb_plenary(page, date, url)
    return docs, None, gaps


READERS = {"vl": read_vl, "pw": read_pw, "bru": read_bru, "fwb": read_fwb}


def run_parliament(conn, client, code, today, budget=None, log=print, watch_path=None):
    """Read, store and record one source. Returns the number of gaps."""
    first_read = not store.reads(conn).get("vl" if code == "vl" else code)
    try:
        docs, members, gaps = READERS[code](client, today, budget=budget, log=log)
    except (FetchError, ValueError, KeyError, TypeError) as e:
        detail = "{0}: not read ({1})".format(store.HOUSE[code], str(e)[:200])
        _gap(conn, today, detail, log)
        for p in (("bru", "cocom") if code == "bru" else (code,)):
            note_read(conn, p, today, 0, 0, detail)
        return 1
    for g in gaps:
        _gap(conn, today, g, log)
    if not docs:
        detail = "{0}: the source answered with no documents".format(store.HOUSE[code])
        _gap(conn, today, detail, log)
        note_read(conn, code, today, 0, 0, detail)
        return len(gaps) + 1
    parls = ("bru", "cocom") if code == "bru" else (code,)
    for p in parls:
        mine = [d for d in docs if d["parliament"] == p]
        n, ours, new, moved = store_docs(conn, mine, today, watch_path)
        log("be-regions: {0}: {1} document(s) read, {2} on our ground, {3} new to the store, "
            "{4} with a changed status".format(store.HOUSE[p], n, ours, new, moved))
        note_read(conn, p, today, n, ours, "; ".join(gaps)[:300] or None)
    if members:
        store_members(conn, code, members, today)
        log("be-regions: {0}: {1} member(s)".format(store.HOUSE[code], len(members)))
    if code == "vl":
        pis = {d["key"]: d.get("pi") for d in docs}
        n, vgaps = read_vl_votes(conn, client, today, pis, first_read, budget, log)
        for g in vgaps:
            _gap(conn, today, g, log)
        gaps = list(gaps) + vgaps
        log("be-regions: Vlaams Parlement: {0} recorded vote(s) stored".format(n))
    return len(gaps)


def reclassify(conn, watch_path=None, log=print):
    n = 0
    for r in conn.execute("SELECT doc_key, lang, title, title_alt, subject FROM ber_docs").fetchall():
        areas, terms, tier = classify({"key": r[0], "lang": r[1], "title": r[2],
                                       "title_alt": r[3], "subject": r[4]}, watch_path)
        conn.execute("UPDATE ber_docs SET areas=?, matched_terms=?, tier=? WHERE doc_key=?",
                     (store.dumps(areas), store.dumps(terms), tier, r[0]))
        n += 1
    conn.execute("UPDATE ber_votes SET areas=(SELECT areas FROM ber_docs d WHERE "
                 "d.doc_key=ber_votes.doc_key), matched_terms=(SELECT matched_terms FROM "
                 "ber_docs d WHERE d.doc_key=ber_votes.doc_key) WHERE doc_key IN "
                 "(SELECT doc_key FROM ber_docs)")
    conn.commit()
    log("be-regions: reclassified {0} document(s)".format(n))


def summary(conn, log=print):
    for code in store.READ:
        row = conn.execute("SELECT COUNT(*), SUM(CASE WHEN areas NOT IN ('[]','','[11]') THEN 1 ELSE 0 "
                           "END), MAX(date) FROM ber_docs WHERE parliament=?", (code,)).fetchone()
        log("be-regions: {0}: {1} document(s) stored, {2} on our ground, newest {3}".format(
            store.HOUSE[code], row[0], row[1] or 0, row[2] or "-"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--parliament", nargs="*", choices=ORDER, help="default: every one")
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="read each parliament once, print what was parsed, store nothing")
    args = ap.parse_args(argv)
    client = guard(HttpClient(raw_dir=os.path.join(ROOT, "data", "raw")), FEED)
    today = datetime.date.today().isoformat()
    codes = args.parliament or list(ORDER)
    if args.dry_run:
        for code in codes:
            try:
                docs, members, gaps = READERS[code](client, today, budget=drain.Budget(90))
            except (FetchError, ValueError, KeyError, TypeError) as e:
                print("be-regions: {0}: FAILED {1}".format(store.HOUSE[code], e))
                continue
            newest = max((d["date"] or "" for d in docs), default="-")
            print("be-regions: {0}: {1} document(s), {2} member(s), newest {3}{4}".format(
                store.HOUSE[code], len(docs), len(members or []), newest,
                "; gaps: " + "; ".join(gaps) if gaps else ""))
        return 0
    conn = db.init_db(db.connect(args.db))
    tax = taxonomies()
    print("be-regions: taxonomy-nl v{0}, taxonomy-fr v{1} (country be)".format(
        getattr(tax.get("nl"), "version", "-"), getattr(tax.get("fr"), "version", "-")))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    for code in codes:
        if budget.exhausted():
            print(budget.disclose("parliaments", codes.index(code)))
            _gap(conn, today, "{0}: time budget spent before it was read".format(store.HOUSE[code]))
            gaps += 1
            continue
        gaps += run_parliament(conn, client, code, today, budget=budget)
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
