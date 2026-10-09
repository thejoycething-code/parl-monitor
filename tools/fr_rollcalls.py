#!/usr/bin/env python3
"""France: the Assemblee nationale's deputies, dossiers legislatifs and
scrutins publics with every deputy's position.

    python3 tools/fr_rollcalls.py                      # the current legislature
    python3 tools/fr_rollcalls.py --zip-dir /tmp/fr    # reuse downloads (dev)
    python3 tools/fr_rollcalls.py --reclassify         # re-derive areas, offline
    python3 tools/fr_rollcalls.py --db /tmp/fr.db      # anywhere but the store

PHASE 1 (9 October 2026); see docs/france-scope.md. Every source is the
Assemblee's own open data (data.assemblee-nationale.fr, Licence Ouverte),
keyless, refreshed nightly, one zip per dataset:

  * Scrutins.json.zip (27 MB; 8,621 scrutins on 9 October 2026, 176 MB
    unzipped): one file per scrutin with EVERY deputy's position, grouped by
    political group, so the group at the vote comes free.
  * Dossiers_Legislatifs.json.zip (11 MB): 3,248 dossiers and the 7,304
    documents filed under them (bills, reports, adopted texts), each with
    its title.
  * AMO10 (5 MB): sitting deputies, their mandates and every organ,
    including the political groups. AMO30 (14 MB, every deputy since 2002)
    is read only when a vote names someone who has left.

THE BULK FILES ARE NOT ARCHIVED to data/raw (archive=False), as with the
US BILLSTATUS zips: 43 MB a week would go into the raw-archive release
for files whose URL serves the same data tomorrow. The difference from the
US is that the AN overwrites them nightly, so last week's copy cannot be
re-fetched; whether that is worth 43 MB a week is a decision listed in the
scope doc. --zip-dir keeps a local copy for development.

TWO SCRUTINS IN THREE DO NOT NAME THEIR DOSSIER. Only 2,795 of the 8,621
carry objet.dossierLegislatif.dossierRef. The rest are amendment and article
votes whose title names the text in full ("l'amendement n 238 de Mme Lorho a
l'article 17 de la proposition de loi relative au droit a l'aide a mourir
(premiere lecture)"). So a scrutin is joined by its dossierRef when it has
one, else by the text's name matched against every document title, and only
when exactly one dossier carries that title (the budget bills carry theirs
in several dossiers and are left unjoined, which costs nothing: a budget
lends no area). `dossier_via` records which.

A VOTE IS CLASSIFIED ON ITS OWN TITLE FIRST. Unlike the House of
Representatives, the scrutin's title names the text, so own-text matching
works; the dossier then lends its areas (`own_areas` keeps the first set
apart).

CLASSIFICATION, FOR NOW, IS THE QUEBEC FRENCH LIST (config/taxonomy-qc.yaml),
read-only, plus config/watchlist-fr.yaml applied by dossier KEY. A France
list (config/taxonomy-fr.yaml) is proposed in the scope doc and awaits
Christopher; when it exists this collector uses it without a code change.
Two French false friends are masked before matching (FALSE_FRIENDS below),
because the Quebec list was never run over French Republic text.

Separation guarantee: writes fr_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store. Exit 3 when it stored what it could
and recorded gaps (jobs/fr-weekly.sh publishes those runs), 0 when clean.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys
import unicodedata
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, fr_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "fr-rollcalls"
LEGISLATURE = 17
CHAMBER = "an"
TAXONOMY_FR = os.path.join(ROOT, "config", "taxonomy-fr.yaml")
TAXONOMY_QC = os.path.join(ROOT, "config", "taxonomy-qc.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "fr"
BASE = "https://data.assemblee-nationale.fr/static/openData/repository/{0}/"
SCRUTINS = BASE + "loi/scrutins/Scrutins.json.zip"
DOSSIERS = BASE + "loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip"
AMO10 = (BASE + "amo/deputes_actifs_mandats_actifs_organes/"
         "AMO10_deputes_actifs_mandats_actifs_organes.json.zip")
AMO30 = (BASE + "amo/tous_acteurs_mandats_organes_xi_legislature/"
         "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip")
# A scrutin already stored is re-read for this many days: a mise au point
# is published after the vote, and the positions file is replaced whole.
REFRESH_DAYS = 30
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)

# The AN's position groups -> our stored word.
POSITIONS = (("pours", "pour"), ("contres", "contre"), ("abstentions", "abstention"),
             ("nonVotants", "nonVotant"), ("nonVotantsVolontaires", "nonVotantVolontaire"))

# French words the Quebec list reads as ours when they are not. MEASURED in
# the scope probe: "censure" (Quebec area 7, tier 2) matched all 23 motions
# de censure and 20 engagements de responsabilite; "euthanasie" (area 2)
# matched a bill on seized animals. Masked, not deleted from any list: the
# taxonomy is Christopher's, and a France list will carry its own guards.
FALSE_FRIENDS = (
    re.compile(r"motions?\s+de\s+censure", re.I),
    re.compile(r"euthanasie\s+(?:des|d'|de)\s*animaux", re.I),
)


def taxonomy_path():
    """The France list when Christopher has approved one, else Quebec's."""
    return TAXONOMY_FR if os.path.exists(TAXONOMY_FR) else TAXONOMY_QC


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def ref_text(value):
    """The AMO files give some uids as {'#text': 'PA1008', '@xsi:type': ...}."""
    if isinstance(value, dict):
        return value.get("#text")
    return value


def nfc(text):
    return unicodedata.normalize("NFC", text or "")


def mask(text):
    text = nfc(text)
    for pat in FALSE_FRIENDS:
        text = pat.sub(" ", text)
    return text


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def empty_watchlist():
    """The France watchlist is applied by KEY (fr_store.add_watch_areas), so
    the filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


# --- fetching ----------------------------------------------------------------

def get_zip(client, url, slug, zip_dir=None, log=print):
    """One bulk zip as a ZipFile. With zip_dir, a copy under 20 hours old is
    reused and a fresh download is kept there (development only)."""
    path = os.path.join(zip_dir, url.rsplit("/", 1)[1]) if zip_dir else None
    if path and os.path.exists(path):
        age_h = (datetime.datetime.now().timestamp() - os.path.getmtime(path)) / 3600
        if age_h < 20:
            log("  {0}: reusing {1} ({2:.0f} h old)".format(slug, path, age_h))
            return zipfile.ZipFile(path)
    blob = client.get_bytes(url, FEED, slug, archive=False)
    if path:
        os.makedirs(zip_dir, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(blob)
    return zipfile.ZipFile(io.BytesIO(blob))


def members_of(zf, folder):
    """Every JSON record in one folder of a zip ('json/acteur/', ...)."""
    for name in zf.namelist():
        if name.startswith(folder) and name.endswith(".json"):
            yield name, json.loads(zf.read(name))


# --- deputies and groups -----------------------------------------------------

def parse_organe(obj):
    o = obj.get("organe") or {}
    vt = o.get("viMoDe") or {}
    return {"uid": ref_text(o.get("uid")), "type": o.get("codeType"),
            "label": o.get("libelle"), "abbr": o.get("libelleAbrev") or o.get("libelleAbrege"),
            "start": vt.get("dateDebut"), "end": vt.get("dateFin")}


def parse_acteur(obj):
    """A deputy: name, current group and seat, from their mandates."""
    a = obj.get("acteur") or {}
    ident = ((a.get("etatCivil") or {}).get("ident")) or {}
    out = {"acteur_ref": ref_text(a.get("uid")),
           "name": " ".join(x for x in (ident.get("prenom"), ident.get("nom")) if x) or None,
           "civility": ident.get("civ"), "group_ref": None, "department": None,
           "constituency": None, "as_of": None, "deputy": False}
    best_gp = None
    for m in as_list((a.get("mandats") or {}).get("mandat")):
        kind, start, end = m.get("typeOrgane"), m.get("dateDebut"), m.get("dateFin")
        organe = ref_text((m.get("organes") or {}).get("organeRef"))
        if kind == "GP" and not end and (best_gp is None or (start or "") > best_gp[0]):
            best_gp = (start or "", organe)
        if kind == "ASSEMBLEE" and not end:
            lieu = ((m.get("election") or {}).get("lieu")) or {}
            out.update(deputy=True, department=lieu.get("departement"),
                       constituency=lieu.get("numCirco"), as_of=start)
    if best_gp:
        out["group_ref"] = best_gp[1]
    return out


def store_member(conn, m, today, current):
    conn.execute(fr_store.MEMBER_UPSERT,
                 (m["acteur_ref"], CHAMBER, m["name"], m["civility"], m["group_ref"],
                  m["department"], m["constituency"], current, m["as_of"], today, today))


def store_group(conn, g):
    conn.execute("INSERT INTO fr_groups (organe_ref, chamber, abbr, label, date_start, date_end) "
                 "VALUES (?,?,?,?,?,?) ON CONFLICT(organe_ref) DO UPDATE SET "
                 "abbr=excluded.abbr, label=excluded.label, date_start=excluded.date_start, "
                 "date_end=excluded.date_end",
                 (g["uid"], CHAMBER, g["abbr"], g["label"], g["start"], g["end"]))


def load_members(conn, zf, today, only=None, current=1):
    """Deputies and political groups from an AMO zip. `only` limits the
    deputies to a set of acteur refs (AMO30, read for departed members).
    Returns the number of deputies stored."""
    for _name, obj in members_of(zf, "json/organe/"):
        g = parse_organe(obj)
        if g["type"] == "GP" and g["uid"]:
            store_group(conn, g)
    n = 0
    if current:
        conn.execute("UPDATE fr_members SET current=0 WHERE chamber=?", (CHAMBER,))
    for _name, obj in members_of(zf, "json/acteur/"):
        m = parse_acteur(obj)
        if not m["acteur_ref"] or (only is not None and m["acteur_ref"] not in only):
            continue
        if current and not m["deputy"]:
            continue
        store_member(conn, m, today, current)
        n += 1
    conn.commit()
    return n


def pull_members(conn, client, today, legislature=LEGISLATURE, zip_dir=None):
    return load_members(conn, get_zip(client, AMO10.format(legislature), "amo10", zip_dir), today)


def fill_departed(conn, client, today, legislature=LEGISLATURE, zip_dir=None, log=print):
    """Names for deputies who voted and have since left (AMO30, read only
    when the store holds a position for someone it cannot name)."""
    missing = {r for (r,) in conn.execute(
        "SELECT DISTINCT v.acteur_ref FROM fr_votes v LEFT JOIN fr_members m "
        "ON m.acteur_ref = v.acteur_ref WHERE m.acteur_ref IS NULL")}
    if not missing:
        return 0, 0
    zf = get_zip(client, AMO30.format(legislature), "amo30", zip_dir)
    n = load_members(conn, zf, today, only=missing, current=0)
    still = len(missing) - n
    log("  departed deputies: {0} named from AMO30, {1} unknown".format(n, still))
    return n, still


# --- dossiers ----------------------------------------------------------------

def _walk_acts(acts, out):
    for a in as_list(acts):
        if not isinstance(a, dict):
            continue
        date = (a.get("dateActe") or "")[:10] or None
        if date:
            out.append((date, a.get("codeActe"),
                        ((a.get("libelleActe") or {}).get("nomCanonique"))))
        _walk_acts((a.get("actesLegislatifs") or {}).get("acteLegislatif"), out)
    return out


def parse_dossier(obj):
    d = obj.get("dossierParlementaire") or {}
    titre = d.get("titreDossier") or {}
    acts = sorted(_walk_acts((d.get("actesLegislatifs") or {}).get("acteLegislatif"), []),
                  key=lambda x: x[0])
    initiators = as_list(((d.get("initiateur") or {}).get("acteurs") or {}).get("acteur"))
    prom = [x[0] for x in acts if (x[1] or "").startswith("PROM")]
    return {"uid": d.get("uid"), "legislature": _int(d.get("legislature")),
            "title": titre.get("titre"), "an_path": titre.get("titreChemin"),
            "senat_url": titre.get("senatChemin"),
            "procedure": (d.get("procedureParlementaire") or {}).get("libelle"),
            "initiator": ref_text(initiators[0].get("acteurRef")) if initiators else None,
            "last_act": acts[-1][1] if acts else None,
            "last_act_label": acts[-1][2] if acts else None,
            "last_act_at": acts[-1][0] if acts else None,
            "promulgated_at": prom[-1] if prom else None,
            "doc_titles": []}


def parse_document(obj):
    """(dossierRef, title) of one document record."""
    d = obj.get("document") or {}
    return d.get("dossierRef"), ((d.get("titres") or {}).get("titrePrincipal") or "").strip()


def classify_dossier(tax, wl, d):
    res = filt.filter_item(tax, wl, mask(d["title"]), *[mask(t) for t in d["doc_titles"]],
                           title=mask(d["title"]))
    return fr_store.add_watch_areas(res, d["uid"])


def store_dossier(conn, d, res, today):
    conn.execute(
        "INSERT INTO fr_dossiers (dossier_ref, legislature, title, procedure, an_path, senat_url, "
        "initiator, doc_titles, last_act, last_act_label, last_act_at, promulgated_at, areas, "
        "matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(dossier_ref) DO UPDATE SET title=excluded.title, "
        "procedure=excluded.procedure, an_path=excluded.an_path, senat_url=excluded.senat_url, "
        "initiator=excluded.initiator, doc_titles=excluded.doc_titles, "
        "last_act=excluded.last_act, last_act_label=excluded.last_act_label, "
        "last_act_at=excluded.last_act_at, promulgated_at=excluded.promulgated_at, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (d["uid"], d["legislature"], d["title"], d["procedure"], d["an_path"], d["senat_url"],
         d["initiator"], fr_store.dumps(d["doc_titles"]), d["last_act"], d["last_act_label"],
         d["last_act_at"], d["promulgated_at"], fr_store.dumps(res.issue_areas),
         fr_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier,
         today, today))


def read_dossiers(zf):
    """{uid: dossier dict with its documents' titles} from the dossiers zip."""
    dossiers = {}
    for _name, obj in members_of(zf, "json/dossierParlementaire/"):
        d = parse_dossier(obj)
        if d["uid"]:
            dossiers[d["uid"]] = d
    for _name, obj in members_of(zf, "json/document/"):
        ref, title = parse_document(obj)
        if ref in dossiers and title and title not in dossiers[ref]["doc_titles"]:
            dossiers[ref]["doc_titles"].append(title)
    for d in dossiers.values():
        d["doc_titles"].sort()
    return dossiers


def pull_dossiers(conn, client, today, legislature=LEGISLATURE, tax=None, wl=None,
                  zip_dir=None):
    """Every dossier of the legislature, re-read whole. Returns (dossiers,
    read, ours): the dict is what the scrutins are joined against."""
    tax = tax if tax is not None else filt.load_taxonomy(taxonomy_path(), country=TAXONOMY_COUNTRY)
    wl = wl if wl is not None else empty_watchlist()
    dossiers = read_dossiers(get_zip(client, DOSSIERS.format(legislature), "dossiers", zip_dir))
    ours = 0
    for d in dossiers.values():
        res = classify_dossier(tax, wl, d)
        store_dossier(conn, d, res, today)
        ours += on_our_ground(res.issue_areas)
    conn.commit()
    return dossiers, len(dossiers), ours


# --- joining a scrutin to its dossier by the text's name ----------------------

# The text a scrutin is about, named at the end of its title: "... de la
# proposition de loi relative au droit a l'aide a mourir (premiere lecture)."
TEXT_NAME = re.compile(r"(?:\bdu |\bde la |\bde l'|^la |^le )"
                       r"((?:projet|proposition) de (?:loi|résolution)\b.*)$", re.I)
TEXT_TITLE = re.compile(r"^\s*(?:projet|proposition) de", re.I)


def norm_title(text):
    """Lower case, straight apostrophes, no parenthesised reading or stage,
    no trailing punctuation: what the scrutin title and the document title
    share."""
    t = nfc(text).replace("’", "'").replace(" ", " ").lower()
    t = re.sub(r"\s*\([^()]*\)", "", t)
    t = re.sub(r"[\s.,;:]+$", "", t)
    return re.sub(r"\s+", " ", t).strip()


def title_index(dossiers):
    """{normalised text title: {dossier refs}} from every bill or resolution
    title filed under a dossier, and every dossier's own title."""
    index = {}
    for uid, d in dossiers.items():
        for t in [d["title"] or ""] + [x for x in d["doc_titles"] if TEXT_TITLE.match(x)]:
            if t:
                index.setdefault(norm_title(t), set()).add(uid)
    return index


def text_name(title):
    hit = TEXT_NAME.search(nfc(title).replace("’", "'"))
    return norm_title(hit.group(1)) if hit else None


def join_dossier(s, index):
    """(dossier_ref, via) for one parsed scrutin."""
    if s["dossier_ref"]:
        return s["dossier_ref"], "ref"
    name = text_name(s["title"] or "")
    refs = index.get(name) if name else None
    if refs and len(refs) == 1:
        return next(iter(refs)), "title"
    return None, None


# --- scrutins ----------------------------------------------------------------

def _votants(block):
    """The votant records under one position, whatever shape the XML-to-JSON
    conversion left them in: None, {'votant': {...}}, {'votant': [...]},
    or a list of those with nulls in it (the miseAuPoint blocks)."""
    out = []
    for item in as_list(block):
        if isinstance(item, dict):
            out.extend(v for v in as_list(item.get("votant")) if isinstance(v, dict))
    return out


def parse_scrutin(obj):
    """One scrutin file -> dict, or None if it is not a scrutin."""
    s = obj.get("scrutin") if isinstance(obj, dict) else None
    if not s or not s.get("numero"):
        return None
    synth = ((s.get("syntheseVote") or {}).get("decompte")) or {}
    dossier = (((s.get("objet") or {}).get("dossierLegislatif")) or {})
    out = {"uid": s.get("uid"), "legislature": _int(s.get("legislature")),
           "number": _int(s.get("numero")), "date": s.get("dateScrutin"),
           "vote_type": (s.get("typeVote") or {}).get("codeTypeVote"),
           "result": (s.get("sort") or {}).get("code"),
           "title": (s.get("titre") or "").strip() or None,
           "dossier_ref": dossier.get("dossierRef"),
           "pour": _int(synth.get("pour")), "contre": _int(synth.get("contre")),
           "abstentions": _int(synth.get("abstentions")),
           "non_votants": _int(synth.get("nonVotants")), "positions": []}
    groups = ((((s.get("ventilationVotes") or {}).get("organe") or {}).get("groupes") or {})
              .get("groupe"))
    seen = set()
    for g in as_list(groups):
        nominal = ((g.get("vote") or {}).get("decompteNominatif")) or {}
        for key, word in POSITIONS:
            for v in _votants(nominal.get(key)):
                ref = v.get("acteurRef")
                if not ref or ref in seen:
                    continue
                seen.add(ref)
                out["positions"].append({
                    "acteur_ref": ref, "position": word, "group_ref": g.get("organeRef"),
                    "by_delegation": 1 if v.get("parDelegation") == "true" else 0,
                    "cause": v.get("causePositionVote"), "intended": None})
    corrections = {}
    for key, word in POSITIONS:
        for v in _votants((s.get("miseAuPoint") or {}).get(key)):
            if v.get("acteurRef"):
                corrections[v["acteurRef"]] = word
    for p in out["positions"]:
        p["intended"] = corrections.get(p["acteur_ref"])
    return out


def division_key(s):
    return "{0}-{1}-{2}".format(CHAMBER, s["legislature"], s["number"])


def classify_division(tax, wl, s, dossier_areas):
    """(own FilterResult, combined areas). The dossier lends its areas."""
    own = filt.filter_item(tax, wl, mask(s.get("title") or ""))
    return own, sorted(set(own.issue_areas or []) | set(dossier_areas or []))


def _dossier_areas(conn, ref):
    if not ref:
        return []
    row = conn.execute("SELECT areas FROM fr_dossiers WHERE dossier_ref=?", (ref,)).fetchone()
    return json.loads(row[0] or "[]") if row else []


def store_division(conn, s, tax, wl, today, index):
    key = division_key(s)
    ref, via = join_dossier(s, index)
    own, areas = classify_division(tax, wl, s, _dossier_areas(conn, ref))
    conn.execute(
        "INSERT INTO fr_divisions (division_key, chamber, legislature, number, date, vote_type, "
        "result, title, dossier_ref, dossier_via, pour, contre, abstentions, non_votants, "
        "own_areas, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET result=excluded.result, "
        "title=excluded.title, dossier_ref=excluded.dossier_ref, "
        "dossier_via=excluded.dossier_via, pour=excluded.pour, contre=excluded.contre, "
        "abstentions=excluded.abstentions, non_votants=excluded.non_votants, "
        "own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, CHAMBER, s["legislature"], s["number"], s["date"], s["vote_type"], s["result"],
         s["title"], ref, via, s["pour"], s["contre"], s["abstentions"], s["non_votants"],
         fr_store.dumps(own.issue_areas), fr_store.dumps(areas),
         fr_store.dumps(own.matched_terms), own.tier, today, today))
    for p in s["positions"]:
        conn.execute("INSERT OR REPLACE INTO fr_votes (division_key, acteur_ref, position, "
                     "group_ref, by_delegation, cause, intended) VALUES (?,?,?,?,?,?,?)",
                     (key, p["acteur_ref"], p["position"], p["group_ref"], p["by_delegation"],
                      p["cause"], p["intended"]))
    return key, areas


def pull_scrutins(conn, client, today, dossiers, legislature=LEGISLATURE, tax=None, wl=None,
                  zip_dir=None, log=print):
    """Scrutins not yet stored, and those of the last REFRESH_DAYS again.
    Returns (stored, ours, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(taxonomy_path(), country=TAXONOMY_COUNTRY)
    wl = wl if wl is not None else empty_watchlist()
    zf = get_zip(client, SCRUTINS.format(legislature), "scrutins", zip_dir)
    return store_scrutins(conn, zf, today, dossiers, legislature, tax, wl, log)


def store_scrutins(conn, zf, today, dossiers, legislature, tax, wl, log=print):
    have = {n: d for n, d in conn.execute(
        "SELECT number, date FROM fr_divisions WHERE chamber=? AND legislature=?",
        (CHAMBER, legislature))}
    cutoff = (datetime.date.fromisoformat(today)
              - datetime.timedelta(days=REFRESH_DAYS)).isoformat()
    index = title_index(dossiers)
    stored = ours = gaps = 0
    for name, obj in members_of(zf, "json/"):
        s = parse_scrutin(obj)
        if s is None:
            _gap(conn, today, "{0}: not a scrutin".format(name))
            gaps += 1
            continue
        if s["number"] in have and (have[s["number"]] or "") < cutoff:
            continue
        if not s["positions"]:
            _gap(conn, today, "scrutin {0}: no positions".format(s["number"]))
            gaps += 1
        _key, areas = store_division(conn, s, tax, wl, today, index)
        stored += 1
        ours += on_our_ground(areas)
        if stored % 500 == 0:
            conn.commit()
    conn.commit()
    return stored, ours, gaps


# --- offline -----------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    """Re-derive dossier areas, then division areas, offline, after a
    taxonomy or watchlist change. Dossiers first: divisions inherit."""
    tax = tax if tax is not None else filt.load_taxonomy(taxonomy_path(), country=TAXONOMY_COUNTRY)
    wl = empty_watchlist()
    changed_d = changed_v = 0
    for (ref, title, docs, areas) in conn.execute(
            "SELECT dossier_ref, title, doc_titles, areas FROM fr_dossiers").fetchall():
        d = {"uid": ref, "title": title or "", "doc_titles": json.loads(docs or "[]")}
        res = classify_dossier(tax, wl, d)
        new = fr_store.dumps(res.issue_areas)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE fr_dossiers SET areas=?, matched_terms=?, tier=? WHERE dossier_ref=?",
                     (new, fr_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, ref))
    for (key, ref, title, areas) in conn.execute(
            "SELECT division_key, dossier_ref, title, areas FROM fr_divisions").fetchall():
        own, combined = classify_division(tax, wl, {"title": title}, _dossier_areas(conn, ref))
        new = fr_store.dumps(combined)
        changed_v += new != (areas or "[]")
        conn.execute("UPDATE fr_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (fr_store.dumps(own.issue_areas), new, fr_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("fr-rollcalls: reclassified; {0} dossier(s) and {1} division(s) changed area".format(
        changed_d, changed_v))
    return changed_d, changed_v


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} dossier(s), {1} on our ground; {2} scrutin(s), {3} on our ground; "
        "{4} deputy(ies), {5} position(s)".format(
            n("SELECT COUNT(*) FROM fr_dossiers"), ours("fr_dossiers"),
            n("SELECT COUNT(*) FROM fr_divisions"), ours("fr_divisions"),
            n("SELECT COUNT(*) FROM fr_members"), n("SELECT COUNT(*) FROM fr_votes")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", type=int, default=LEGISLATURE)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--zip-dir", help="keep and reuse the bulk zips here (development)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-scrutins", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored dossiers and divisions, offline")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    print("fr-rollcalls: classifying with {0}".format(os.path.relpath(taxonomy_path(), ROOT)))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=1.0)
    today = datetime.date.today().isoformat()
    tax = filt.load_taxonomy(taxonomy_path(), country=TAXONOMY_COUNTRY)
    wl = empty_watchlist()
    gaps = 0
    if not args.no_members:
        try:
            print("fr-rollcalls: {0} sitting deputy(ies)".format(
                pull_members(conn, client, today, args.legislature, args.zip_dir)))
        except (FetchError, zipfile.BadZipFile) as exc:
            _gap(conn, today, "AMO10: {0}".format(exc))
            print("  [gap] AMO10: {0}".format(str(exc)[:90]))
            gaps += 1
    try:
        dossiers, read, ours = pull_dossiers(conn, client, today, args.legislature, tax, wl,
                                             args.zip_dir)
        print("fr-rollcalls: {0} dossier(s) read, {1} on our ground".format(read, ours))
    except (FetchError, zipfile.BadZipFile) as exc:
        # Without the dossiers the scrutins would be stored unjoined, and
        # their areas would be wrong until the next run. Stop here instead.
        _gap(conn, today, "dossiers: {0}".format(exc))
        conn.commit()
        print("  [gap] dossiers: {0}; scrutins not read".format(str(exc)[:90]))
        summary(conn)
        conn.close()
        return 3
    if not args.no_scrutins:
        try:
            stored, ours, g = pull_scrutins(conn, client, today, dossiers, args.legislature,
                                            tax, wl, args.zip_dir)
            gaps += g
            print("fr-rollcalls: {0} scrutin(s) stored or refreshed, {1} on our ground, "
                  "{2} gap(s)".format(stored, ours, g))
        except (FetchError, zipfile.BadZipFile) as exc:
            _gap(conn, today, "scrutins: {0}".format(exc))
            print("  [gap] scrutins: {0}".format(str(exc)[:90]))
            gaps += 1
        try:
            _n, unknown = fill_departed(conn, client, today, args.legislature, args.zip_dir)
            if unknown:
                _gap(conn, today, "{0} voter(s) named in no AMO file".format(unknown))
                gaps += 1
        except (FetchError, zipfile.BadZipFile) as exc:
            _gap(conn, today, "AMO30: {0}".format(exc))
            print("  [gap] AMO30: {0}".format(str(exc)[:90]))
            gaps += 1
    conn.commit()
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
