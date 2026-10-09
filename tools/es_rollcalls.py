#!/usr/bin/env python3
"""Spain, Congreso de los Diputados: deputies, legislative initiatives,
plenary votes and every deputy's position.

    python3 tools/es_rollcalls.py                      # the current legislature
    python3 tools/es_rollcalls.py --legislature 15     # a named one
    python3 tools/es_rollcalls.py --index-only         # vote titles, no positions
    python3 tools/es_rollcalls.py --reclassify         # re-derive areas, offline
    python3 tools/es_rollcalls.py --taxonomy x.yaml    # classify with a draft list
    python3 tools/es_rollcalls.py --db /tmp/es.db      # anywhere but the store

PHASE 1 (9 October 2026); see docs/spain-scope.md. Every source is the
Congreso's own open data, keyless, measured live:

  * /es/opendata/votaciones -- ONE PAGE PER DAY WITH VOTES. The landing page
    embeds `diasVotaciones`, every voting day of the legislature (146 in the
    XV, 19 September 2023 to 30 September 2026), and `targetDate=DD/MM/YYYY`
    selects a day. The page lists each vote under its item, with the
    initiative's expediente number ('162/000814') and links to one JSON file
    per vote. THE FILE NAMES CARRY A GENERATION TIMESTAMP
    (VOT_20260930153547.json) and cannot be guessed, so the day page is
    read first, always.
  * the vote JSON (about 32 KB): totals and all 350 positions, each
    {asiento, diputado, grupo, voto}. It carries the item's text but NOT its
    expediente number, which is why the day page is kept (and archived):
    it is the only place the vote is joined to its initiative.
  * /es/opendata/diputados and /es/opendata/iniciativas -- daily-regenerated
    JSON files (DiputadosActivos, DiputadosDeBaja, ProyectosDeLey,
    ProposicionesDeLey), again under timestamped names read off the page.

A DEPUTY HAS NO PUBLISHED ID: see src/es_store.py. Positions are stored
under the name the vote file printed.

A DISSOLVED CORTES STILL HAS DAYS TO READ. The Cortes were dissolved on
6 October 2026 (Real Decreto 806/2026; elections 29 November, the XVI
legislature convenes on 23 December). The landing page then still shows the
XV, and the weekly finds nothing new until the Diputación Permanente votes
or the XVI sits; the current legislature is read off the page's own
selector, so the switch needs no edit here.

CLASSIFICATION waits for a Spanish taxonomy (config/taxonomy-es.yaml,
proposed in docs/spain-scope.md, generated only once Christopher approves
it). Until then areas stay NULL -- unclassified, not "nothing found" -- and
only config/watchlist-es.yaml, applied by initiative KEY, lends areas.

Separation guarantee: writes es_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

Exit codes: 0 clean, 3 stored what it could and recorded gaps, 1 otherwise.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, es_store, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "es-rollcalls"
BASE = "https://www.congreso.es"
VOTES_PAGE = (BASE + "/es/opendata/votaciones?p_p_id=votaciones&p_p_lifecycle=0"
              "&p_p_state=normal&p_p_mode=view&targetLegislatura={leg}&targetDate={date}")
VOTES_LANDING = BASE + "/es/opendata/votaciones"
MEMBERS_PAGE = BASE + "/es/opendata/diputados"
INITIATIVES_PAGE = BASE + "/es/opendata/iniciativas"
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "es"
BUDGET_S = drain.DEFAULT_S
# congreso.es is a Liferay portal serving the whole public site; a second
# between requests keeps a first-run backfill (about 3,000 vote files for
# the XV) to roughly an hour, spread over runs by the budget.
THROTTLE_S = 1.0
# Days re-read even when already stored: a vote added to a day's page after
# our first read (it has not been seen, but nothing forbids it) is picked up
# within two weeks.
REREAD_DAYS = 14
HIDDEN_AREAS = (11,)   # migration: collated, never campaigned (repo-wide rule)
ROMAN = {14: "XIV", 15: "XV", 16: "XVI", 17: "XVII", 18: "XVIII"}


# --- small helpers ------------------------------------------------------------

def iso(ddmmyyyy):
    """'30/9/2026' or '30/09/2026' -> '2026-09-30'; anything else -> None."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", ddmmyyyy or "")
    if not m:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def fold(text):
    """Strip tags, unescape, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def expediente(raw):
    """'121/000001/0000' or '162/000814' -> '121/000001'; else None."""
    m = re.match(r"\s*(\d{3})/(\d{6})", raw or "")
    return "{0}/{1}".format(m.group(1), m.group(2)) if m else None


def initiative_key(legislature, exp):
    exp = expediente(exp)
    return "{0}/{1}".format(int(legislature), exp) if exp else None


def roman(n):
    return ROMAN.get(int(n)) or str(n)


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return bool(set(areas or []) - set(HIDDEN_AREAS))


# --- the votes landing page and the day pages --------------------------------

def parse_landing(page):
    """(current legislature, [ISO voting days]) from a votaciones page.

    The page embeds `diasVotaciones = [20230919, ...]`, and its legislature
    selector marks the one shown as selected."""
    m = re.search(r'id="_votaciones_legislatura".*?<option[^>]*\bselected\b[^>]*value="(\d+)"',
                  page, re.S)
    if not m:
        m = re.search(r'<option[^>]*\bselected\b[^>]*value="(\d+)"[^>]*>\s*[XVI]+ Legislatura',
                      page)
    leg = int(m.group(1)) if m else None
    d = re.search(r"diasVotaciones\s*=\s*\[([^\]]*)\]", page)
    days = []
    for tok in re.findall(r"\d{8}", d.group(1) if d else ""):
        days.append("{0}-{1}-{2}".format(tok[:4], tok[4:6], tok[6:]))
    return leg, sorted(set(days))


_DAY_TOKENS = re.compile(
    r'<h3>\s*(?P<session>Sesi[^<]+?)\s*</h3>'
    r'|<h4>(?P<section>.*?)</h4>'
    r'|<h5 class="con_est">(?P<item>.*?)</h5>'
    r'|<h5>(?P<group>.*?)</h5>'
    r'|<h6 class="con_est">(?P<point>.*?)</h6>'
    r'|_iniciativas_id=(?P<exp>\d{3}/\d{6})'
    r'|<p>Si: (?P<yes>\d+)</p>\s*<p>No: (?P<no>\d+)</p>\s*<p>Abstenciones: (?P<abs>\d+)</p>'
    r'|(?:href|src)="(?P<file>/webpublica/opendata/votaciones/Leg(?P<leg>\d+)/Sesion(?P<ses>\d+)/'
    r'(?P<ymd>\d{8})/Votacion(?P<num>\d+)/[^"]+?\.(?P<ext>json|png))"',
    re.S)


def parse_day(page):
    """Every vote a day page lists, in order, as dicts.

    The page is a nest of accordions: a section (h4), an item (h5.con_est)
    followed by its expediente link, sometimes a sub-group (a bare h5, such
    as 'Votación separada por puntos.') and points (h6.con_est), and then the
    vote's totals and file links. Read as a stream of tokens: an item resets
    the expediente, the group and the point; the first file link of a vote
    number opens the vote.

    AN INVESTITURE HAS NO VOTE FILE. A vote 'pública por llamamiento' (the
    investitures of 27 and 29 September and 16 November 2023, and the reform
    of article 49 of the Constitution on 18 January 2024) is published as a
    chart image only: totals on the page,
    no JSON, no positions. It is stored with json_url NULL rather than
    dropped, so the vote exists in the store even though the names do not."""
    votes, by_num = [], {}
    session = section = item = group = point = exp = None
    counts = (None, None, None)
    for m in _DAY_TOKENS.finditer(page):
        if m.group("session") is not None:
            session = fold(m.group("session"))
        elif m.group("section") is not None:
            # 'II.<i ...></i> Proposiciones no de Ley.' -> 'Proposiciones no de Ley.'
            section = re.sub(r"^[IVXLC]+\.\s*", "", fold(m.group("section")))
            item = group = point = exp = None
        elif m.group("item") is not None:
            item, group, point, exp = fold(m.group("item")), None, None, None
        elif m.group("group") is not None:
            group, point = fold(m.group("group")), None
        elif m.group("point") is not None:
            point = fold(m.group("point"))
        elif m.group("exp") is not None:
            exp = m.group("exp")
        elif m.group("yes") is not None:
            counts = (int(m.group("yes")), int(m.group("no")), int(m.group("abs")))
        elif m.group("file") is not None:
            num = (int(m.group("ses")), int(m.group("num")))
            url = BASE + m.group("file") if m.group("ext") == "json" else None
            if num in by_num:
                if url and not by_num[num]["json_url"]:
                    by_num[num]["json_url"] = url
                continue
            ymd = m.group("ymd")
            votes.append({
                "legislature": int(m.group("leg")), "session": num[0], "vote_number": num[1],
                "date": "{0}-{1}-{2}".format(ymd[:4], ymd[4:6], ymd[6:]),
                "session_title": session, "section": section, "title": item or section,
                "subgroup": " ".join(dict.fromkeys(x for x in (group, point) if x)) or None,
                "expediente": exp, "yes": counts[0], "no": counts[1], "abstain": counts[2],
                "json_url": url})
            by_num[num] = votes[-1]
            counts = (None, None, None)
    return votes


def division_key(d):
    return "congreso-{0}-{1}-{2}".format(d["legislature"], d["session"], d["vote_number"])


def parse_vote_json(raw):
    """The vote file -> {totals..., positions: [(name, grupo, voto, seat)]}, or
    None when it is not a vote file."""
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or "informacion" not in data:
        return None
    info, tot = data.get("informacion") or {}, data.get("totales") or {}
    sub = " ".join(x for x in (fold(info.get("tituloSubGrupo")), fold(info.get("textoSubGrupo")))
                   if x) or None
    return {
        "session": info.get("sesion"), "vote_number": info.get("numeroVotacion"),
        "date": iso(info.get("fecha")), "text": fold(info.get("textoExpediente")),
        "section": fold(info.get("titulo")), "subgroup": sub,
        "assent": 1 if (tot.get("asentimiento") or "").strip().lower().startswith("s") else 0,
        "present": tot.get("presentes"), "yes": tot.get("afavor"), "no": tot.get("enContra"),
        "abstain": tot.get("abstenciones"), "not_voting": tot.get("noVotan"),
        "positions": [(fold(v.get("diputado")), (v.get("grupo") or "").strip() or None,
                       (v.get("voto") or "").strip() or None, str(v.get("asiento") or "") or None)
                      for v in (data.get("votaciones") or []) if v.get("diputado")],
    }


# --- classification ---------------------------------------------------------------

def load_taxonomy(path=None):
    """The Spanish taxonomy, or None while none exists (areas stay NULL)."""
    path = path or TAXONOMY_ES
    return filt.load_taxonomy(path, country=TAXONOMY_COUNTRY) if os.path.exists(path) else None


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, key, *texts):
    """(areas or None, matched terms, tier) for one row's text plus the
    watchlist entry of its initiative KEY. areas is None only when there is
    no taxonomy AND no watchlist entry: unclassified, not empty."""
    watched = es_store.watch_areas(key)
    if tax is None:
        if watched:
            return sorted(set(watched)), ["watch:" + key], 2
        return None, [], None
    res = filt.filter_item(tax, empty_watchlist(), *[t for t in texts if t])
    areas = set(res.issue_areas or [])
    terms = list(res.matched_terms or [])
    tier = res.tier
    if watched:
        areas |= set(watched)
        terms.append("watch:" + key)
        tier = tier or 2
    return sorted(areas), terms, tier


def _initiative_areas(conn, key):
    if not key:
        return None
    row = conn.execute("SELECT areas FROM es_initiatives WHERE initiative_key=?",
                       (key,)).fetchone()
    return json.loads(row[0]) if row and row[0] is not None else None


def classify_division(conn, tax, d):
    """(own areas, combined areas, terms, tier). A vote is classified on its
    own text, then inherits its initiative's areas: the US lesson, where a
    vote's own line is often bare. Here it rarely is -- the item title is
    printed with every vote -- but an amendment vote on a bill still needs
    the bill."""
    own, terms, tier = classify(tax, d.get("initiative_key"), d.get("title"),
                                d.get("subgroup"), d.get("section"))
    parent = _initiative_areas(conn, d.get("initiative_key"))
    if own is None and parent is None:
        return None, None, terms, tier
    combined = sorted(set(own or []) | set(parent or []))
    return own, combined, terms, tier


# --- storing ---------------------------------------------------------------------

def store_division(conn, d, tax, today):
    key = division_key(d)
    d["initiative_key"] = initiative_key(d["legislature"], d.get("expediente"))
    own, combined, terms, tier = classify_division(conn, tax, d)
    conn.execute(
        "INSERT INTO es_divisions (division_key, chamber, legislature, session, vote_number, "
        "date, session_title, section, title, subgroup, expediente, initiative_key, yes, no, "
        "abstain, json_url, own_areas, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET date=excluded.date, "
        "session_title=excluded.session_title, section=excluded.section, title=excluded.title, "
        "subgroup=COALESCE(es_divisions.subgroup, excluded.subgroup), "
        "expediente=excluded.expediente, initiative_key=excluded.initiative_key, "
        "yes=COALESCE(es_divisions.yes, excluded.yes), no=COALESCE(es_divisions.no, excluded.no), "
        "abstain=COALESCE(es_divisions.abstain, excluded.abstain), json_url=excluded.json_url, "
        "own_areas=excluded.own_areas, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (key, "congreso", d["legislature"], d["session"], d["vote_number"], d["date"],
         d.get("session_title"), d.get("section"), d.get("title"), d.get("subgroup"),
         d.get("expediente"), d["initiative_key"], d.get("yes"), d.get("no"), d.get("abstain"),
         d.get("json_url"), None if own is None else es_store.dumps(own),
         None if combined is None else es_store.dumps(combined), es_store.dumps(terms), tier,
         today, today))
    return key, combined


def store_positions(conn, key, v):
    """Write a vote file's totals and positions. The JSON's own subgroup
    text (an amendment's number, a point) fills what the day page lacked."""
    conn.execute("DELETE FROM es_votes WHERE division_key=?", (key,))
    conn.executemany(
        "INSERT OR REPLACE INTO es_votes (division_key, name, grupo, position, seat) "
        "VALUES (?,?,?,?,?)", [(key,) + p for p in v["positions"]])
    conn.execute(
        "UPDATE es_divisions SET assent=?, present=?, yes=?, no=?, abstain=?, not_voting=?, "
        "subgroup=COALESCE(subgroup, ?), positions=? WHERE division_key=?",
        (v["assent"], v["present"], v["yes"], v["no"], v["abstain"], v["not_voting"],
         v["subgroup"], len(v["positions"]), key))


def pull_votes(conn, client, today, legislature=None, tax=None, log=print, budget=None,
               index_only=False, limit=None, days=None):
    """Read the voting days not yet stored (and the last REREAD_DAYS), then
    every vote file whose positions are not stored. Returns
    (legislature, days read, divisions stored, positions files read, gaps)."""
    gaps = 0
    try:
        landing = client.get_text(
            VOTES_LANDING if legislature is None else
            VOTES_PAGE.format(leg=roman(legislature), date=""),
            FEED, "landing-{0}".format(legislature or "current"))
    except FetchError as exc:
        _gap(conn, today, "votes landing page: {0}".format(exc))
        log("  [gap] votes landing page: {0}".format(str(exc)[:90]))
        return legislature, 0, 0, 0, 1
    page_leg, all_days = parse_landing(landing)
    leg = legislature or page_leg
    if not leg or not all_days:
        _gap(conn, today, "votes landing page carried no legislature or no voting days")
        log("  [gap] votes landing page carried no legislature or no voting days")
        return leg, 0, 0, 0, 1
    done = {r[0] for r in conn.execute(
        "SELECT day FROM es_vote_days WHERE legislature=?", (leg,))}
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=REREAD_DAYS)).isoformat()
    todo = [d for d in all_days if (d not in done or d >= cutoff) and d <= today]
    if days:
        todo = [d for d in todo if d in set(days)]
    log("es-rollcalls: legislature {0}: {1} voting day(s) listed, {2} to read".format(
        roman(leg), len(all_days), len(todo)))
    read_days = stored = 0
    for day in todo:
        if budget is not None and budget.exhausted():
            log(budget.disclose("voting days", read_days))
            break
        y, m, dd = day.split("-")
        try:
            page = client.get_text(VOTES_PAGE.format(leg=roman(leg), date="{0}/{1}/{2}".format(dd, m, y)),
                                   FEED, "day-{0}-{1}".format(leg, day))
        except FetchError as exc:
            _gap(conn, today, "votes {0}: {1}".format(day, exc))
            log("  [gap] votes {0}: {1}".format(day, str(exc)[:90]))
            gaps += 1
            continue
        votes = [v for v in parse_day(page) if v["date"] == day]
        if not votes:
            _gap(conn, today, "votes {0}: the day page listed no vote".format(day))
            log("  [gap] votes {0}: the day page listed no vote".format(day))
            gaps += 1
            continue
        for v in votes:
            store_division(conn, v, tax, today)
            stored += 1
        conn.execute("INSERT INTO es_vote_days (legislature, day, listed, fetched_at) "
                     "VALUES (?,?,?,?) ON CONFLICT(legislature, day) DO UPDATE SET "
                     "listed=excluded.listed, fetched_at=excluded.fetched_at",
                     (leg, day, len(votes), today))
        conn.commit()
        read_days += 1
    files = 0
    if not index_only:
        pending = conn.execute(
            "SELECT division_key, json_url FROM es_divisions WHERE legislature=? AND "
            "positions IS NULL AND json_url IS NOT NULL ORDER BY date, session, vote_number",
            (leg,)).fetchall()
        for key, url in pending:
            if limit is not None and files >= limit:
                log("  fetch cap ({0}) reached; the rest lands on the next run "
                    "-- disclosed, not silent".format(limit))
                break
            if budget is not None and budget.exhausted():
                log(budget.disclose("vote files", files))
                break
            try:
                raw = client.get_bytes(url, FEED, "vote-" + key)
            except FetchError as exc:
                _gap(conn, today, "{0}: {1}".format(key, exc))
                log("  [gap] {0}: {1}".format(key, str(exc)[:90]))
                gaps += 1
                continue
            v = parse_vote_json(raw)
            if v is None:
                _gap(conn, today, "{0}: the vote file was not a vote".format(key))
                log("  [gap] {0}: the vote file was not a vote".format(key))
                gaps += 1
                continue
            store_positions(conn, key, v)
            conn.commit()
            files += 1
    return leg, read_days, stored, files, gaps


# --- members ---------------------------------------------------------------------

_FILE_LINK = r'href="(/webpublica/opendata/{0}/{1}__\d+\.json)"'


def discover(page, folder, stem):
    """The current timestamped JSON link for one open-data file, or None."""
    links = re.findall(_FILE_LINK.format(folder, stem), page)
    return BASE + sorted(links)[-1] if links else None


def parse_members(records, sitting):
    out = []
    for r in records or []:
        name = fold(r.get("NOMBRE"))
        if not name:
            continue
        out.append({"name": name, "circunscripcion": fold(r.get("CIRCUNSCRIPCION")) or None,
                    "formacion": fold(r.get("FORMACIONELECTORAL")) or None,
                    "grupo": fold(r.get("GRUPOPARLAMENTARIO")) or None,
                    "alta": iso(r.get("FECHAALTA")),
                    "baja": None if sitting else iso(r.get("FECHABAJA"))})
    return out


def store_member(conn, leg, m, today):
    conn.execute(
        "INSERT INTO es_members (legislature, name, circunscripcion, formacion, grupo, alta, "
        "baja, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(legislature, name) DO UPDATE SET "
        "circunscripcion=COALESCE(excluded.circunscripcion, es_members.circunscripcion), "
        "formacion=COALESCE(excluded.formacion, es_members.formacion), "
        "grupo=COALESCE(excluded.grupo, es_members.grupo), "
        "alta=COALESCE(excluded.alta, es_members.alta), baja=excluded.baja, "
        "last_seen=excluded.last_seen",
        (leg, m["name"], m["circunscripcion"], m["formacion"], m["grupo"], m["alta"],
         m["baja"], today, today))


def pull_members(conn, client, today, leg, log=print):
    """Sitting and departed deputies. A deputy who left and came back appears
    in both files; the sitting record is written last and wins (baja NULL).
    Returns (count, gaps)."""
    try:
        page = client.get_text(MEMBERS_PAGE, FEED, "members-page")
    except FetchError as exc:
        _gap(conn, today, "members page: {0}".format(exc))
        log("  [gap] members page: {0}".format(str(exc)[:90]))
        return 0, 1
    n = gaps = 0
    for stem, sitting in (("DiputadosDeBaja", False), ("DiputadosActivos", True)):
        url = discover(page, "diputados", stem)
        if not url:
            _gap(conn, today, "members page: no {0} file linked".format(stem))
            log("  [gap] members page: no {0} file linked".format(stem))
            gaps += 1
            continue
        try:
            records = client.get_json(url, FEED, "members-" + stem)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "{0}: {1}".format(stem, exc))
            log("  [gap] {0}: {1}".format(stem, str(exc)[:90]))
            gaps += 1
            continue
        for m in parse_members(records, sitting):
            store_member(conn, leg, m, today)
            n += 1
    conn.commit()
    return n, gaps


# --- legislative initiatives -------------------------------------------------------

def parse_initiatives(records):
    out = []
    for r in records or []:
        exp = expediente(r.get("NUMEXPEDIENTE"))
        lm = re.search(r"(\d+)", r.get("LEGISLATURA") or "")
        if not exp or not lm:
            continue
        bocg = re.search(r"https?://\S+", r.get("ENLACESBOCG") or "")
        out.append({
            "legislature": int(lm.group(1)), "expediente": exp,
            "tipo": fold(r.get("TIPO")) or None, "objeto": fold(r.get("OBJETO")) or None,
            "autor": fold(r.get("AUTOR")) or None,
            "presentada": iso(r.get("FECHAPRESENTACION")),
            "calificada": iso(r.get("FECHACALIFICACION")),
            "tipo_tramitacion": fold(r.get("TIPOTRAMITACION")) or None,
            "comision": fold(r.get("COMISIONCOMPETENTE")) or None,
            "situacion": fold(r.get("SITUACIONACTUAL")) or None,
            "resultado": fold(r.get("RESULTADOTRAMITACION")) or None,
            "tramitacion": (r.get("TRAMITACIONSEGUIDA") or "").strip() or None,
            "bocg": bocg.group(0) if bocg else None})
    return out


def store_initiative(conn, i, tax, today):
    key = initiative_key(i["legislature"], i["expediente"])
    areas, terms, tier = classify(tax, key, i["objeto"])
    conn.execute(
        "INSERT INTO es_initiatives (initiative_key, legislature, expediente, tipo, objeto, autor, "
        "presentada, calificada, tipo_tramitacion, comision, situacion, resultado, tramitacion, "
        "bocg, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(initiative_key) DO UPDATE SET tipo=excluded.tipo, objeto=excluded.objeto, "
        "autor=excluded.autor, presentada=excluded.presentada, calificada=excluded.calificada, "
        "tipo_tramitacion=excluded.tipo_tramitacion, comision=excluded.comision, "
        "situacion=excluded.situacion, resultado=excluded.resultado, "
        "tramitacion=excluded.tramitacion, bocg=excluded.bocg, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, i["legislature"], i["expediente"], i["tipo"], i["objeto"], i["autor"],
         i["presentada"], i["calificada"], i["tipo_tramitacion"], i["comision"], i["situacion"],
         i["resultado"], i["tramitacion"], i["bocg"],
         None if areas is None else es_store.dumps(areas), es_store.dumps(terms), tier,
         today, today))
    return key, areas


def pull_initiatives(conn, client, today, tax=None, log=print):
    """Proyectos and proposiciones de ley. Returns (read, on our ground, gaps)."""
    try:
        page = client.get_text(INITIATIVES_PAGE, FEED, "initiatives-page")
    except FetchError as exc:
        _gap(conn, today, "initiatives page: {0}".format(exc))
        log("  [gap] initiatives page: {0}".format(str(exc)[:90]))
        return 0, 0, 1
    read = ours = gaps = 0
    for stem in ("ProyectosDeLey", "ProposicionesDeLey"):
        url = discover(page, "iniciativas", stem)
        if not url:
            _gap(conn, today, "initiatives page: no {0} file linked".format(stem))
            log("  [gap] initiatives page: no {0} file linked".format(stem))
            gaps += 1
            continue
        try:
            records = client.get_json(url, FEED, "initiatives-" + stem)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "{0}: {1}".format(stem, exc))
            log("  [gap] {0}: {1}".format(stem, str(exc)[:90]))
            gaps += 1
            continue
        for i in parse_initiatives(records):
            _key, areas = store_initiative(conn, i, tax, today)
            read += 1
            ours += on_our_ground(areas)
    conn.commit()
    return read, ours, gaps


# --- offline -----------------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    """Re-derive initiative areas, then division areas, offline, after a
    taxonomy or watchlist change. Initiatives first: divisions inherit."""
    changed_i = changed_d = 0
    for key, objeto, areas in conn.execute(
            "SELECT initiative_key, objeto, areas FROM es_initiatives").fetchall():
        new, terms, tier = classify(tax, key, objeto)
        new_s = None if new is None else es_store.dumps(new)
        changed_i += new_s != areas
        conn.execute("UPDATE es_initiatives SET areas=?, matched_terms=?, tier=? "
                     "WHERE initiative_key=?", (new_s, es_store.dumps(terms), tier, key))
    for row in conn.execute(
            "SELECT division_key, initiative_key, title, subgroup, section, areas "
            "FROM es_divisions").fetchall():
        d = {"initiative_key": row[1], "title": row[2], "subgroup": row[3], "section": row[4]}
        own, combined, terms, tier = classify_division(conn, tax, d)
        new_s = None if combined is None else es_store.dumps(combined)
        changed_d += new_s != row[5]
        conn.execute("UPDATE es_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (None if own is None else es_store.dumps(own), new_s,
                      es_store.dumps(terms), tier, row[0]))
    conn.commit()
    log("es-rollcalls: reclassified; {0} initiative(s) and {1} division(s) changed area".format(
        changed_i, changed_d))
    return changed_i, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731

    def ours(table):
        rows = conn.execute("SELECT areas FROM {0} WHERE areas IS NOT NULL".format(table))
        return sum(on_our_ground(json.loads(a)) for (a,) in rows)
    log("  store: {0} initiative(s), {1} on our ground; {2} division(s), {3} on our ground, "
        "{4} unclassified, {5} published without a vote file; {6} member(s), "
        "{7} position(s)".format(
            n("SELECT COUNT(*) FROM es_initiatives"), ours("es_initiatives"),
            n("SELECT COUNT(*) FROM es_divisions"), ours("es_divisions"),
            n("SELECT COUNT(*) FROM es_divisions WHERE areas IS NULL"),
            n("SELECT COUNT(*) FROM es_divisions WHERE json_url IS NULL"),
            n("SELECT COUNT(*) FROM es_members"), n("SELECT COUNT(*) FROM es_votes")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", type=int, help="default: the one the Congreso shows")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--taxonomy", help="classify with this taxonomy file "
                                       "(default config/taxonomy-es.yaml when it exists)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-initiatives", action="store_true")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--index-only", action="store_true",
                    help="read the day pages (titles, expedientes, totals) but no vote files")
    ap.add_argument("--days", help="only these ISO days, comma-separated")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored initiatives and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many vote files")
    args = ap.parse_args()
    tax = load_taxonomy(args.taxonomy)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    if tax is None:
        print("es-rollcalls: no Spanish taxonomy yet (config/taxonomy-es.yaml); "
              "areas stay NULL, only watchlist-es lends areas")
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    leg = args.legislature
    if not args.no_initiatives:
        read, ours, g = pull_initiatives(conn, client, today, tax=tax)
        gaps += g
        print("es-rollcalls: {0} legislative initiative(s) read, {1} on our ground, "
              "{2} gap(s)".format(read, ours, g))
    if not args.no_votes:
        days = [d.strip() for d in args.days.split(",")] if args.days else None
        leg, nd, ns, nf, g = pull_votes(conn, client, today, legislature=leg, tax=tax,
                                        budget=budget, index_only=args.index_only,
                                        limit=args.limit, days=days)
        gaps += g
        print("es-rollcalls: {0} day(s) read, {1} division(s) stored, {2} vote file(s) read, "
              "{3} gap(s)".format(nd, ns, nf, g))
    if not args.no_members:
        if leg is None:
            row = conn.execute("SELECT MAX(legislature) FROM es_divisions").fetchone()
            leg = row[0] if row and row[0] else None
        if leg is None:
            print("es-rollcalls: members skipped: legislature unknown (pass --legislature)")
        else:
            n, g = pull_members(conn, client, today, leg)
            gaps += g
            print("es-rollcalls: {0} member record(s), {1} gap(s)".format(n, g))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
