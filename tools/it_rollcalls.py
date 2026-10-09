#!/usr/bin/env python3
"""Italian Parliament, phase 1: bills of both chambers, the recorded votes of
the Senato and the Camera dei Deputati, and every member's position on the
votes on our ground (docs/italy-scope.md).

    python3 tools/it_rollcalls.py                    # the weekly pull
    python3 tools/it_rollcalls.py --reclassify       # offline, after a taxonomy change
    python3 tools/it_rollcalls.py --dry-run          # one live query each, store nothing

SOURCES, both open and keyless, probed 9 October 2026:

  * dati.senato.it/sparql, the Senate's own Virtuoso endpoint. It carries
    EVERY bill of the legislature, the Camera's readings included (3,159 C.
    and 2,092 S. readings in the 19th), each with the Senate library's TESEO
    subject terms, and every Senate vote with every senator's position and
    the bill it was on. Virtuoso caps an answer at 10,000 rows and refuses an
    ORDER BY ... OFFSET past that cap (HTTP 500), so every large query here
    is cut into ranges by a numeric field instead of paged.
  * Openpolis (service.opdm.openpolis.io/api-openparlamento/v1), for the
    Camera's votes. The Camera's own SPARQL endpoint (dati.camera.it/sparql)
    answered 502 all day and its download portal sits behind a reCAPTCHA,
    which we do not pass. Openpolis keeps the Camera's own vote identifiers
    ('vs19_723_001'), so the day dati.camera.it answers, the source can be
    swapped without re-keying a single row.

CLASSIFICATION. The English taxonomy is blind to Italian: measured on
9 October 2026 it matched 0 of 8,411 bill titles and 0 of 28,150 votes of
the 19th legislature. The Italian term list is a proposal awaiting
Christopher (docs/italy-scope.md), so this collector reads
config/taxonomy-it.yaml when it exists and the English file until then, plus
config/watchlist-it.yaml BY BILL KEY. Run --reclassify once the Italian file
lands: positions for every vote it brings onto our ground follow on the next
run, because a division on our ground with positions_fetched = 0 is fetched.

A VOTE INHERITS ITS BILL'S AREAS. Neither chamber's vote label says what the
vote was about ('Em. 1.1', 'Votazione finale', 'ODG 9/2886/76'); the bill
does. The Senate names the bill on every vote (osr:oggetto). The Camera's
vote titles do in most years ('... DDL n. 0887', 'Ordine del giorno
9/887/19'), but since 2025 its amendment titles are bare ('EM 19.7 -
Votazione'). Those take the bill of the nearest titled vote in the same
sitting (forward for amendments and articles, which precede the bill's
orders of the day; backward for a final vote, which follows them), and say
so in bill_inferred. Motions and resolutions take no bill.

OMNIBUS. TESEO classifies a bill as a whole ('Generale') and article by
article ('Articoli'). Only the general terms are used: the article terms of
a single budget law span half the thesaurus, and they put 243 Camera votes
on the 2024 budget onto our ground in the first measurement.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, it_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "it-rollcalls"
LEGISLATURE = 19
SENATO_SPARQL = "https://dati.senato.it/sparql"
OPENPOLIS = "https://service.opdm.openpolis.io/api-openparlamento/v1/{0}/"
TAXONOMY_IT = os.path.join(ROOT, "config", "taxonomy-it.yaml")
TAXONOMY_EN = os.path.join(ROOT, "config", "taxonomy.yaml")
BUDGET_S = drain.DEFAULT_S
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)
# Virtuoso's answer cap. A range that comes back this full may be truncated:
# it is a gap, never silently accepted.
SPARQL_CAP = 10000
BILL_RANGE = 400       # idFase values per bill query (about 400 rows, 1 s)
SITTING_RANGE = 25     # Senate sittings per vote query (about 450 votes)
# Camera votes are re-read for this many days behind the newest one stored:
# Openpolis publishes a vote the night after, with positions still 'SEC'
# until the Camera's own record arrives (seen on vs19_723_001, 9 October).
CAMERA_LOOKBACK_DAYS = 14
OPENPOLIS_PAGE = 500   # the API's maximum page size

# The Senate's position predicates. osr:votante and osr:presente are
# supersets of these and are not read; a senator on none of them was absent.
SENATE_POSITIONS = {"favorevole": "aye", "contrario": "no", "astenuto": "abstain",
                    "presenteNonVotante": "present", "richiedenteNonVotante": "present",
                    "inCongedoMissione": "mission"}
CAMERA_POSITIONS = {"AYE": "aye", "NO": "no", "ABST": "abstain", "PRES": "present",
                    "MIS": "mission", "ABSE": "absent", "SEC": "secret"}


# --- SPARQL ------------------------------------------------------------------

def sparql(client, query, slug):
    """Rows of a SELECT as plain {var: value} dicts. The Senate's answers carry
    raw control characters inside some titles, which strict JSON refuses."""
    url = SENATO_SPARQL + "?" + urllib.parse.urlencode(
        {"query": query, "format": "application/sparql-results+json"})
    raw = client.get_bytes(url, FEED, slug)
    data = json.loads(raw.decode("utf-8"), strict=False)
    return [{k: v.get("value") for k, v in b.items()}
            for b in (data.get("results") or {}).get("bindings") or []]


PREFIXES = ("PREFIX osr: <http://dati.senato.it/osr/>\n"
            "PREFIX ocd: <http://dati.camera.it/ocd/>\n"
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
            "PREFIX dc: <http://purl.org/dc/terms/>\n"
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n")


def q_bill_range(leg):
    return PREFIXES + ("SELECT (MIN(?f) AS ?lo) (MAX(?f) AS ?hi) WHERE {{ ?d a osr:Ddl ; "
                       "osr:legislatura {0} ; osr:idFase ?f }}").format(int(leg))


def q_bills(leg, lo, hi):
    return PREFIXES + """SELECT ?d ?fase ?iddl ?titolo ?breve ?natura ?iniz ?pres ?stato ?statodata ?nlegge ?dlegge WHERE {{
 ?d a osr:Ddl ; osr:legislatura {0} ; osr:idFase ?f ; osr:fase ?fase ; osr:titolo ?titolo .
 OPTIONAL {{ ?d osr:idDdl ?iddl }} OPTIONAL {{ ?d osr:titoloBreve ?breve }}
 OPTIONAL {{ ?d osr:natura ?natura }} OPTIONAL {{ ?d osr:descrIniziativa ?iniz }}
 OPTIONAL {{ ?d osr:dataPresentazione ?pres }} OPTIONAL {{ ?d osr:statoDdl ?stato }}
 OPTIONAL {{ ?d osr:dataStatoDdl ?statodata }} OPTIONAL {{ ?d osr:numeroLegge ?nlegge }}
 OPTIONAL {{ ?d osr:dataLegge ?dlegge }}
 FILTER(?f >= {1} && ?f < {2}) }} LIMIT {3}""".format(int(leg), int(lo), int(hi), SPARQL_CAP)


def q_teseo(leg, lo, hi):
    return PREFIXES + """SELECT DISTINCT ?d ?label WHERE {{
 ?d a osr:Ddl ; osr:legislatura {0} ; osr:idFase ?f ; osr:classificazione ?c .
 ?c osr:livello ?liv ; dc:subject ?t . ?t skos:prefLabel ?label
 FILTER(?f >= {1} && ?f < {2} && STR(?liv) = "Generale") }} LIMIT {3}""".format(int(leg), int(lo), int(hi), SPARQL_CAP)


def q_senators(leg):
    return PREFIXES + """SELECT DISTINCT ?s ?name ?inizio ?fine ?grp WHERE {{
 ?s a osr:Senatore ; rdfs:label ?name ; ocd:aderisce ?a .
 ?a osr:legislatura {0} ; osr:inizio ?inizio ; osr:gruppo ?g .
 OPTIONAL {{ ?a osr:fine ?fine }}
 OPTIONAL {{ ?g osr:denominazione ?dn . ?dn osr:titoloBreve ?grp FILTER NOT EXISTS {{ ?dn osr:fine ?x }} }}
}} LIMIT {1}""".format(int(leg), SPARQL_CAP)


def q_senate_votes(leg, lo, hi):
    return PREFIXES + """SELECT ?v ?label ?num ?date ?esito ?fav ?con ?ast ?fase WHERE {{
 ?v a osr:Votazione ; osr:legislatura {0} ; osr:seduta ?s ; rdfs:label ?label .
 ?s osr:numeroSeduta ?num ; osr:dataSeduta ?date .
 OPTIONAL {{ ?v osr:esito ?esito }} OPTIONAL {{ ?v osr:favorevoli ?fav }}
 OPTIONAL {{ ?v osr:contrari ?con }} OPTIONAL {{ ?v osr:astenuti ?ast }}
 OPTIONAL {{ ?v osr:oggetto ?o . ?o osr:relativoA ?atto . ?atto osr:fase ?fase }}
 FILTER(?num >= {1} && ?num < {2}) }} LIMIT {3}""".format(int(leg), int(lo), int(hi), SPARQL_CAP)


def q_senate_max_sitting(leg):
    return PREFIXES + ("SELECT (MAX(?n) AS ?hi) WHERE {{ ?s a osr:SedutaAssemblea ; "
                       "osr:legislatura {0} ; osr:numeroSeduta ?n }}").format(int(leg))


def q_senate_positions(vote_id):
    """vote_id: '19-232-24'. The IRI is an identifier, written in SPARQL's
    angle brackets, never fetched (the dataset's IRIs are http://)."""
    preds = ", ".join("osr:" + p for p in SENATE_POSITIONS)
    return PREFIXES + ("SELECT ?p ?s WHERE {{ <http://dati.senato.it/votazione/{0}> ?p ?s "
                       "FILTER(?p IN ({1})) }} LIMIT {2}").format(vote_id, preds, SPARQL_CAP)


# --- parsing (pure) ------------------------------------------------------------

_TESEO_ACCENT = {"A": "à", "E": "è", "I": "ì", "O": "ò", "U": "ù"}


def teseo_label(raw):
    """'LIBERTA\\' RELIGIOSA' -> 'libertà religiosa'. TESEO writes accented
    capitals as a vowel plus apostrophe; 'DELL\\' UNIONE' is an elision and
    is left alone."""
    text = re.sub(r"([AEIOU])'(?=\s|$|[,;)])", lambda m: _TESEO_ACCENT[m.group(1)], raw or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def bill_key(leg, fase):
    """'C.2822-B' -> '19/C.2822-B'."""
    return "{0}/{1}".format(int(leg), (fase or "").strip())


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_bills(rows, leg=LEGISLATURE):
    """{bill_key: bill}. OPTIONAL fields can repeat a row; the first value of
    each field wins and later ones only fill blanks."""
    out = {}
    for r in rows:
        fase = (r.get("fase") or "").strip()
        if not re.match(r"^[CS]\.\d", fase):
            continue
        key = bill_key(leg, fase)
        b = out.setdefault(key, {"key": key, "legislature": int(leg), "chamber": fase[0],
                                 "number": fase[2:], "uri": r.get("d"), "subjects": []})
        for field, src in (("id_ddl", "iddl"), ("title", "titolo"), ("short_title", "breve"),
                           ("nature", "natura"), ("initiative", "iniz"), ("presented", "pres"),
                           ("status", "stato"), ("status_date", "statodata")):
            if not b.get(field) and r.get(src):
                b[field] = r[src].strip()
        if not b.get("law") and r.get("nlegge"):
            year = (r.get("dlegge") or "")[:4]
            b["law"] = "Legge {0}/{1}".format(r["nlegge"], year) if year else "Legge " + r["nlegge"]
    return out


def attach_subjects(bills, rows):
    by_uri = {b["uri"]: b for b in bills.values()}
    for r in rows:
        b = by_uri.get(r.get("d"))
        label = teseo_label(r.get("label"))
        if b is not None and label and label not in b["subjects"]:
            b["subjects"].append(label)
    for b in bills.values():
        b["subjects"].sort()
    return bills


def senate_vote_key(uri):
    """'<dati.senato.it>/votazione/19-167-42' -> ('senato-19-167-42', 19, 167, 42)."""
    hit = re.search(r"/votazione/(\d+)-(\d+)-(\d+)$", uri or "")
    if not hit:
        return None
    leg, sitting, num = (int(x) for x in hit.groups())
    return "senato-{0}-{1}-{2}".format(leg, sitting, num), leg, sitting, num


def parse_senate_votes(rows):
    """{division_key: division}. A vote on a joint text names every reading
    examined with it (the 16 October 2024 surrogacy votes name S.163, S.245,
    S.475 and S.824): all of them are kept in bill_keys and all lend their
    areas; bill_key is the lowest-numbered, for display only."""
    out = {}
    for r in rows:
        k = senate_vote_key(r.get("v"))
        if not k:
            continue
        key, leg, sitting, num = k
        d = out.setdefault(key, {
            "key": key, "uri": r["v"], "chamber": "senato", "legislature": leg,
            "sitting": sitting, "number": num, "date": r.get("date"),
            "title": (r.get("label") or "").strip(), "outcome": r.get("esito"),
            "ayes": _int(r.get("fav")), "noes": _int(r.get("con")),
            "abstentions": _int(r.get("ast")), "bill_keys": [], "bill_inferred": 0})
        if r.get("fase"):
            bk = bill_key(leg, r["fase"])
            if bk not in d["bill_keys"]:
                d["bill_keys"].append(bk)
    for d in out.values():
        d["bill_keys"].sort(key=_reading_order)
        d["bill_key"] = d["bill_keys"][0] if d["bill_keys"] else None
        d["is_final"] = int("finale" in d["title"].lower())
    return out


def _reading_order(key):
    hit = re.match(r"^\d+/([CS])\.(\d+)", key or "")
    return (hit.group(1), int(hit.group(2)), key) if hit else ("", 0, key or "")


def parse_senators(rows):
    """{member_key: {name, groups [{from, to, grp}], grp}} from the group spells."""
    out = {}
    for r in rows:
        hit = re.search(r"/senatore/(\d+)$", r.get("s") or "")
        if not hit:
            continue
        key = "S:" + hit.group(1)
        m = out.setdefault(key, {"key": key, "name": (r.get("name") or "").strip(), "groups": []})
        spell = {"from": r.get("inizio"), "to": r.get("fine"), "grp": r.get("grp")}
        if spell not in m["groups"]:
            m["groups"].append(spell)
    for m in out.values():
        m["groups"].sort(key=lambda s: (s["from"] or "", s["to"] or "9999"))
        m["grp"] = m["groups"][-1]["grp"] if m["groups"] else None
    return out


def group_on(groups, date):
    """The group a senator sat in on a date, from the spells; None if unknown."""
    for s in groups or []:
        if (s.get("from") or "") <= (date or "") and (not s.get("to") or date <= s["to"]):
            return s.get("grp")
    return None


def parse_senate_positions(rows):
    """[(member_key, position)]; a senator on two lists keeps the first in
    SENATE_POSITIONS order (aye before present, never both)."""
    order = list(SENATE_POSITIONS)
    best = {}
    for r in rows:
        pred = re.sub(r"^.*/osr/", "", r.get("p") or "")
        hit = re.search(r"/senatore/(\d+)$", r.get("s") or "")
        if pred not in SENATE_POSITIONS or not hit:
            continue
        key = "S:" + hit.group(1)
        if key not in best or order.index(pred) < order.index(best[key]):
            best[key] = pred
    return sorted((k, SENATE_POSITIONS[p]) for k, p in best.items())


# --- the Camera's votes (Openpolis) ------------------------------------------

_CAMERA_BILL = (re.compile(r"\b(?:DDL|PDL|DL)\s+(?:n\.\s*)?(?:C\.\s*)?0*(\d+)(-[A-Z]+)?", re.I),
                re.compile(r"\b9/0*(\d+)(-[A-Z]+)?\b"))
_CAMERA_NO_BILL = re.compile(r"^\s*(?:Mozion|MOZ\b|Risoluzion|RIS\b|Doc\b|Question)", re.I)
_CAMERA_FORWARD = re.compile(r"^\s*(?:EM\b|Emendament|Identic|SUBEM|Subemendament|Articol|ART\b|"
                             r"MANTENIMENTO)", re.I)


def camera_own_bill(title, leg=LEGISLATURE):
    """The bill a Camera vote title names, or None. The reading suffix is
    kept ('PDL 2822-B' -> '19/C.2822-B'), the committee's '-A' is not
    ('DDL 3083-A' -> '19/C.3083'); the order-of-the-day form
    '9/887 E ABB./19' names the bill as 887."""
    for pat in _CAMERA_BILL:
        hit = pat.search(title or "")
        if hit:
            # '-A' marks the committee's text of the same reading, not a new
            # reading; '-B' (back from the Senate) is a reading of its own.
            suffix = (hit.group(2) or "").upper()
            return bill_key(leg, "C.{0}{1}".format(int(hit.group(1)), "" if suffix == "-A" else suffix))
    return None


def infer_camera_bills(votes, leg=LEGISLATURE):
    """{division_key: (bill_key, inferred)} for the votes of ONE sitting,
    given as dicts with key, number, title. See the module docstring."""
    vs = sorted(votes, key=lambda v: v["number"] or 0)
    own = [camera_own_bill(v["title"], leg) for v in vs]
    out = {}
    for i, v in enumerate(vs):
        title = v["title"] or ""
        if own[i]:
            out[v["key"]] = (own[i], 0)
        elif _CAMERA_NO_BILL.search(title):
            out[v["key"]] = (None, 0)
        else:
            rng = range(i + 1, len(vs)) if _CAMERA_FORWARD.search(title) else range(i - 1, -1, -1)
            k = next((own[j] for j in rng if own[j]), None)
            out[v["key"]] = (k, 1 if k else 0)
    return out


def parse_camera_list(results, leg=LEGISLATURE):
    out = []
    for r in results or []:
        ident = r.get("identifier") or r.get("slug")
        sitting = r.get("sitting") or {}
        if not ident or sitting.get("branch") not in (None, "C"):
            continue
        out.append({"key": "camera-" + ident, "ident": ident, "chamber": "camera",
                    "legislature": int(leg), "sitting": _int(sitting.get("number")),
                    "number": _int(r.get("number")), "date": sitting.get("date"),
                    "title": (r.get("title") or "").strip(), "is_final": int(bool(r.get("is_final"))),
                    "is_secret": bool(r.get("is_secret")), "outcome": r.get("outcome")})
    return out


def parse_camera_detail(rec):
    """(counts, [(member_key, name, grp, position)], published). published is
    False while every position is still 'SEC' on a vote that was not secret:
    Openpolis has the result but not yet the Camera's record of who voted how."""
    counts = {"ayes": _int(rec.get("n_ayes")), "noes": _int(rec.get("n_nos")),
              "abstentions": _int(rec.get("n_abstained"))}
    positions = []
    for mv in rec.get("members_votes") or []:
        m = mv.get("membership") or {}
        # Keyed on the membership's numeric ID, not its slug: a slug carries
        # the birth date and reads '...-none' until Openpolis has one
        # ('fabio-roscioli-none', 9 October 2026), so it can change.
        if m.get("id") is None:
            continue
        name = " ".join(x for x in (m.get("given_name"), m.get("family_name")) if x) or None
        grp = (mv.get("group") or {}).get("acronym")
        positions.append(("C:{0}".format(m["id"]), name, grp,
                          CAMERA_POSITIONS.get(mv.get("vote"), (mv.get("vote") or "").lower() or None)))
    published = rec.get("is_secret") or any(p[3] != "secret" for p in positions)
    return counts, positions, bool(positions) and bool(published)


# --- classification ------------------------------------------------------------

def empty_watchlist():
    """The Italian watchlist is applied by KEY (it_store.add_watch_areas), so
    the filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def taxonomy_path():
    return TAXONOMY_IT if os.path.exists(TAXONOMY_IT) else TAXONOMY_EN


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def classify_bill(tax, wl, b, watch_path=None):
    res = filt.filter_item(tax, wl, b.get("title") or "", b.get("short_title") or "",
                           " ; ".join(b.get("subjects") or []), title=b.get("title") or "")
    return it_store.add_watch_areas(res, b["key"], watch_path)


def _bill_areas(conn, keys):
    out = set()
    for k in keys or []:
        row = conn.execute("SELECT areas FROM it_bills WHERE bill_key=?", (k,)).fetchone()
        if row:
            out |= set(json.loads(row[0] or "[]"))
    return out


def classify_division(conn, tax, wl, title, bill_keys):
    own = filt.filter_item(tax, wl, title or "")
    return own, sorted(set(own.issue_areas or []) | _bill_areas(conn, bill_keys))


# --- storing -------------------------------------------------------------------

def store_bill(conn, b, res, today):
    conn.execute(
        "INSERT INTO it_bills (bill_key, legislature, chamber, number, id_ddl, title, short_title, "
        "nature, initiative, presented, status, status_date, law, subjects, areas, matched_terms, "
        "tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET id_ddl=excluded.id_ddl, title=excluded.title, "
        "short_title=excluded.short_title, nature=excluded.nature, initiative=excluded.initiative, "
        "presented=excluded.presented, status=excluded.status, status_date=excluded.status_date, "
        "law=excluded.law, subjects=excluded.subjects, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (b["key"], b["legislature"], b["chamber"], b["number"], b.get("id_ddl"), b.get("title"),
         b.get("short_title"), b.get("nature"), b.get("initiative"), b.get("presented"),
         b.get("status"), b.get("status_date"), b.get("law"), it_store.dumps(b.get("subjects")),
         it_store.dumps(res.issue_areas),
         it_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))


def _keys(d):
    return d.get("bill_keys") or ([d["bill_key"]] if d.get("bill_key") else [])


def store_division(conn, d, tax, wl, today):
    own, areas = classify_division(conn, tax, wl, d["title"], _keys(d))
    conn.execute(
        "INSERT INTO it_divisions (division_key, chamber, legislature, sitting, number, date, "
        "title, bill_key, bill_keys, bill_inferred, is_final, outcome, ayes, noes, abstentions, "
        "own_areas, areas, matched_terms, tier, positions_fetched, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET date=excluded.date, title=excluded.title, "
        "bill_key=excluded.bill_key, bill_keys=excluded.bill_keys, "
        "bill_inferred=excluded.bill_inferred, "
        "is_final=excluded.is_final, outcome=excluded.outcome, "
        "ayes=COALESCE(excluded.ayes, it_divisions.ayes), "
        "noes=COALESCE(excluded.noes, it_divisions.noes), "
        "abstentions=COALESCE(excluded.abstentions, it_divisions.abstentions), "
        "own_areas=excluded.own_areas, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (d["key"], d["chamber"], d["legislature"], d.get("sitting"), d.get("number"), d.get("date"),
         d["title"], d.get("bill_key"), it_store.dumps(_keys(d)), d.get("bill_inferred") or 0,
         d.get("is_final"),
         d.get("outcome"), d.get("ayes"), d.get("noes"), d.get("abstentions"),
         it_store.dumps(own.issue_areas), it_store.dumps(areas), it_store.dumps(own.matched_terms),
         own.tier, today, today))
    return areas


def upsert_member(conn, key, chamber, name, grp, groups, today):
    conn.execute(
        "INSERT INTO it_members (member_key, chamber, name, grp, groups, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET "
        "name=COALESCE(excluded.name, it_members.name), grp=COALESCE(excluded.grp, it_members.grp), "
        "groups=COALESCE(excluded.groups, it_members.groups), last_seen=excluded.last_seen",
        (key, chamber, name, grp, json.dumps(groups, ensure_ascii=False) if groups else None,
         today, today))


def store_positions(conn, division_key, positions):
    conn.execute("DELETE FROM it_votes WHERE division_key=?", (division_key,))
    for member, position, grp in positions:
        conn.execute("INSERT OR REPLACE INTO it_votes (division_key, member_key, position, grp) "
                     "VALUES (?,?,?,?)", (division_key, member, position, grp))
    conn.execute("UPDATE it_divisions SET positions_fetched=1 WHERE division_key=?", (division_key,))


def _gap(conn, today, detail, log=print):
    log("  [gap] " + detail)
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


# --- the pulls -------------------------------------------------------------------

def pull_bills(conn, client, today, tax, wl, leg=LEGISLATURE, log=print, budget=None):
    """Every bill reading of the legislature, both chambers, re-read whole
    (which is what re-stamps last_seen). Returns (read, ours, gaps)."""
    try:
        rng = sparql(client, q_bill_range(leg), "bills-range-{0}".format(leg))
        lo, hi = int(rng[0]["lo"]), int(rng[0]["hi"])
    except (FetchError, KeyError, IndexError, TypeError, ValueError) as exc:
        _gap(conn, today, "Senate SPARQL bill range: {0}".format(exc), log)
        return 0, 0, 1
    read = ours = gaps = 0
    for start in range(lo, hi + 1, BILL_RANGE):
        if budget is not None and budget.exhausted():
            log(budget.disclose("bill ranges", read))
            _gap(conn, today, "bills: budget spent at idFase {0}".format(start), log)
            return read, ours, gaps + 1
        end = start + BILL_RANGE
        try:
            rows = sparql(client, q_bills(leg, start, end), "bills-{0}-{1}".format(leg, start))
            subj = sparql(client, q_teseo(leg, start, end), "teseo-{0}-{1}".format(leg, start))
        except FetchError as exc:
            _gap(conn, today, "bills idFase {0}-{1}: {2}".format(start, end, exc), log)
            gaps += 1
            continue
        if len(rows) >= SPARQL_CAP or len(subj) >= SPARQL_CAP:
            _gap(conn, today, "bills idFase {0}-{1}: answer at the {2}-row cap".format(
                start, end, SPARQL_CAP), log)
            gaps += 1
        bills = attach_subjects(parse_bills(rows, leg), subj)
        for b in bills.values():
            res = classify_bill(tax, wl, b)
            store_bill(conn, b, res, today)
            read += 1
            ours += on_our_ground(res.issue_areas)
        conn.commit()
    return read, ours, gaps


def pull_senators(conn, client, today, leg=LEGISLATURE, log=print):
    try:
        members = parse_senators(sparql(client, q_senators(leg), "senators-{0}".format(leg)))
    except FetchError as exc:
        _gap(conn, today, "Senate SPARQL senators: {0}".format(exc), log)
        return {}, 1
    for m in members.values():
        upsert_member(conn, m["key"], "senato", m["name"], m["grp"], m["groups"], today)
    conn.commit()
    return members, 0


def pull_senate_votes(conn, client, today, tax, wl, leg=LEGISLATURE, log=print, budget=None):
    """New and recent Senate votes, by sitting range. The first run reads the
    legislature; later runs start two sittings before the newest stored.
    Returns (read, ours, gaps)."""
    row = conn.execute("SELECT MAX(sitting) FROM it_divisions WHERE chamber='senato' "
                       "AND legislature=?", (leg,)).fetchone()
    start = max(0, (row[0] or 0) - 2)
    try:
        hi = int(sparql(client, q_senate_max_sitting(leg), "senate-max-sitting-{0}".format(leg))
                 [0]["hi"])
    except (FetchError, KeyError, IndexError, TypeError, ValueError) as exc:
        _gap(conn, today, "Senate SPARQL sittings: {0}".format(exc), log)
        return 0, 0, 1
    read = ours = gaps = 0
    for lo in range(start, hi + 1, SITTING_RANGE):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Senate sitting ranges", read))
            _gap(conn, today, "Senate votes: budget spent at sitting {0}".format(lo), log)
            return read, ours, gaps + 1
        try:
            rows = sparql(client, q_senate_votes(leg, lo, lo + SITTING_RANGE),
                          "senate-votes-{0}-{1}".format(leg, lo))
        except FetchError as exc:
            _gap(conn, today, "Senate votes sittings {0}-{1}: {2}".format(
                lo, lo + SITTING_RANGE, exc), log)
            gaps += 1
            continue
        if len(rows) >= SPARQL_CAP:
            _gap(conn, today, "Senate votes sittings {0}-{1}: answer at the cap".format(
                lo, lo + SITTING_RANGE), log)
            gaps += 1
        for d in parse_senate_votes(rows).values():
            ours += on_our_ground(store_division(conn, d, tax, wl, today))
            read += 1
        conn.commit()
    return read, ours, gaps


def pull_camera_votes(conn, client, today, tax, wl, leg=LEGISLATURE, log=print, budget=None):
    """Camera votes from Openpolis, newest first, down to CAMERA_LOOKBACK_DAYS
    behind the newest stored (the whole legislature on the first run).
    Returns (read, ours, gaps)."""
    row = conn.execute("SELECT MAX(date) FROM it_divisions WHERE chamber='camera' "
                       "AND legislature=?", (leg,)).fetchone()
    cutoff = None
    if row[0]:
        cutoff = (datetime.date.fromisoformat(row[0]) -
                  datetime.timedelta(days=CAMERA_LOOKBACK_DAYS)).isoformat()
    url = OPENPOLIS.format(leg) + "votings/?branch=C&page_size={0}".format(OPENPOLIS_PAGE)
    seen, page, gaps = [], 0, 0
    while url:
        if budget is not None and budget.exhausted():
            log(budget.disclose("Camera vote pages", page))
            _gap(conn, today, "Camera votes: budget spent at page {0}".format(page + 1), log)
            gaps += 1
            break
        try:
            data = client.get_json(url, FEED, "camera-votings-{0}-p{1}".format(leg, page + 1))
        except FetchError as exc:
            _gap(conn, today, "Camera votes page {0}: {1}".format(page + 1, exc), log)
            gaps += 1
            break
        page += 1
        batch = parse_camera_list(data.get("results"), leg)
        seen.extend(v for v in batch if not cutoff or (v["date"] or "") >= cutoff)
        if cutoff and batch and min(v["date"] or "" for v in batch) < cutoff:
            break
        url = data.get("next")
    # Bills by sitting: a sitting's votes may straddle two pages, and the
    # inference reads the whole sitting, stored rows included.
    sittings = {}
    for v in seen:
        sittings.setdefault(v["sitting"], {})[v["key"]] = v
    ours = 0
    for sitting, votes in sittings.items():
        for key, number, title in conn.execute(
                "SELECT division_key, number, title FROM it_divisions WHERE chamber='camera' "
                "AND legislature=? AND sitting=?", (leg, sitting)):
            votes.setdefault(key, {"key": key, "number": number, "title": title, "stored": True})
        bills = infer_camera_bills(votes.values(), leg)
        for key, v in votes.items():
            if v.get("stored"):
                continue
            v["bill_key"], v["bill_inferred"] = bills.get(key, (None, 0))
            ours += on_our_ground(store_division(conn, v, tax, wl, today))
    conn.commit()
    return len(seen), ours, gaps


def pull_positions(conn, client, today, members, leg=LEGISLATURE, log=print, budget=None):
    """Positions for every division on our ground that has none yet, newest
    first. Returns (fetched, gaps)."""
    todo = [(k, ch, d, a) for k, ch, d, a in conn.execute(
        "SELECT division_key, chamber, date, areas FROM it_divisions WHERE legislature=? "
        "AND positions_fetched=0 ORDER BY date DESC, division_key DESC", (leg,))
        if on_our_ground(json.loads(a or "[]"))]
    fetched = gaps = 0
    for key, chamber, date, _areas in todo:
        if budget is not None and budget.exhausted():
            log(budget.disclose("division positions", fetched))
            _gap(conn, today, "positions: budget spent with {0} division(s) left".format(
                len(todo) - fetched), log)
            return fetched, gaps + 1
        try:
            if chamber == "senato":
                _, lg, sitting, num = key.split("-")
                vote_id = "{0}-{1}-{2}".format(lg, sitting, num)
                rows = sparql(client, q_senate_positions(vote_id), "senate-positions-" + key)
                positions = []
                for member, position in parse_senate_positions(rows):
                    groups = (members.get(member) or {}).get("groups")
                    positions.append((member, position, group_on(groups, date)))
            else:
                ident = key[len("camera-"):]
                rec = client.get_json(OPENPOLIS.format(leg) + "votings/{0}/".format(ident),
                                      FEED, "camera-voting-" + ident)
                counts, plist, published = parse_camera_detail(rec)
                if not published:
                    log("  {0}: positions not yet published (all 'SEC'); next run".format(key))
                    continue
                conn.execute("UPDATE it_divisions SET ayes=?, noes=?, abstentions=? "
                             "WHERE division_key=?",
                             (counts["ayes"], counts["noes"], counts["abstentions"], key))
                positions = []
                for member, name, grp, position in plist:
                    upsert_member(conn, member, "camera", name, grp, None, today)
                    positions.append((member, position, grp))
        except FetchError as exc:
            _gap(conn, today, "positions {0}: {1}".format(key, exc), log)
            gaps += 1
            continue
        store_positions(conn, key, positions)
        conn.commit()
        fetched += 1
    return fetched, gaps


# --- offline ---------------------------------------------------------------------

def reclassify(conn, tax=None, log=print, watch_path=None):
    """Re-derive bill areas, then division areas, offline, after a taxonomy or
    watchlist change. Bills first: divisions inherit from them, through every
    reading in bill_keys."""
    tax = tax if tax is not None else filt.load_taxonomy(taxonomy_path())
    wl = empty_watchlist()
    changed_b = changed_d = 0
    for key, title, short, subjects, areas in conn.execute(
            "SELECT bill_key, title, short_title, subjects, areas FROM it_bills").fetchall():
        b = {"key": key, "title": title, "short_title": short,
             "subjects": json.loads(subjects or "[]")}
        res = classify_bill(tax, wl, b, watch_path)
        new = it_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE it_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (new, it_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for key, title, bkeys, areas in conn.execute(
            "SELECT division_key, title, bill_keys, areas FROM it_divisions").fetchall():
        own, combined = classify_division(conn, tax, wl, title, json.loads(bkeys or "[]"))
        new = it_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE it_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (it_store.dumps(own.issue_areas), new, it_store.dumps(own.matched_terms),
                      own.tier, key))
    conn.commit()
    log("it-rollcalls: reclassified; {0} bill(s) and {1} division(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} bill reading(s), {1} on our ground; {2} division(s) (Senate and Camera), "
        "{3} on our ground; {4} member(s), {5} position(s)".format(
            n("SELECT COUNT(*) FROM it_bills"), ours("it_bills"),
            n("SELECT COUNT(*) FROM it_divisions"), ours("it_divisions"),
            n("SELECT COUNT(*) FROM it_members"), n("SELECT COUNT(*) FROM it_votes")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", type=int, default=LEGISLATURE)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--taxonomy", help="taxonomy file (default: taxonomy-it.yaml if present, "
                                       "else the English taxonomy)")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--no-senate", action="store_true")
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--no-positions", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="one live query to each source, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    leg = args.legislature
    tax_path = args.taxonomy or taxonomy_path()
    if args.dry_run:
        rng = sparql(client, q_bill_range(leg), "dry-bills")
        data = client.get_json(OPENPOLIS.format(leg) + "votings/?branch=C&page_size=1",
                               FEED, "dry-camera", archive=False)
        print("it-rollcalls: Senate SPARQL idFase {0}-{1}; Openpolis {2} Camera vote(s), "
              "newest {3}".format(rng[0].get("lo"), rng[0].get("hi"), data.get("count"),
                                  (data.get("results") or [{}])[0].get("identifier")))
        return 0
    conn = db.init_db(db.connect(args.db))
    tax = filt.load_taxonomy(tax_path)
    print("it-rollcalls: taxonomy {0} (v{1})".format(os.path.basename(tax_path), tax.version))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    members, g = pull_senators(conn, client, today, leg)
    gaps += g
    print("it-rollcalls: {0} senator(s) of the {1}th legislature".format(len(members), leg))
    if not args.no_bills:
        read, ours, g = pull_bills(conn, client, today, tax, wl, leg, budget=budget)
        gaps += g
        print("it-rollcalls: {0} bill reading(s) read, {1} on our ground, {2} gap(s)".format(
            read, ours, g))
    if not args.no_senate:
        read, ours, g = pull_senate_votes(conn, client, today, tax, wl, leg, budget=budget)
        gaps += g
        print("it-rollcalls: {0} Senate vote(s) read, {1} on our ground, {2} gap(s)".format(
            read, ours, g))
    if not args.no_camera:
        read, ours, g = pull_camera_votes(conn, client, today, tax, wl, leg, budget=budget)
        gaps += g
        print("it-rollcalls: {0} Camera vote(s) read, {1} on our ground, {2} gap(s)".format(
            read, ours, g))
    if not args.no_positions:
        fetched, g = pull_positions(conn, client, today, members, leg, budget=budget)
        gaps += g
        print("it-rollcalls: positions for {0} division(s), {1} gap(s)".format(fetched, g))
    summary(conn)
    conn.close()
    # 3: stored what it could and recorded gaps (jobs/it-weekly.sh publishes it).
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
