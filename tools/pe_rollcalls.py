"""Peru's Congress, phase 1: members of both chambers, proyectos de ley, and
plenary votes with every member's position. Built 9 October 2026; see
docs/peru-scope.md for every number behind it.

    python3 tools/pe_rollcalls.py                  # members, bills, votes
    python3 tools/pe_rollcalls.py --period 2021    # also the 2021-2026 Congress's bills
    python3 tools/pe_rollcalls.py --reclassify     # offline, after a taxonomy change

SOURCES, all open and keyless:

  * Members: each chamber's WordPress REST API, `/wp-json/wp/v2/senador`
    (60) and `/wp-json/wp/v2/diputado` (130). The bancada, party, district
    and status ride in the post's class list as taxonomy slugs.
  * Proyectos de ley: the Sistema de Proyectos de Ley's own JSON API,
    `api.congreso.gob.pe/spley-portal-service/proyecto-ley/lista-con-filtro`
    (POST, offset paging, 1,000 rows a page accepted). One list per chamber
    code: S (Senado), D (Diputados), C (the Congress as a whole, and the
    whole of every period before 2026).
  * Votes: the plenary vote records are PDFs in each chamber's WordPress
    media library, found through `/wp-json/wp/v2/media?search=`. The signed
    records are printer scans with no text; the provisional "copia
    informativa" uploaded first is a digital export that pypdf reads. Every
    file is read once and remembered in pe_vote_files.

CLASSIFICATION. `config/taxonomy-es.yaml` when it exists (Chris approves the
Spanish term list in docs/peru-scope.md first); until then the English
`config/taxonomy.yaml`, which is blind to Spanish and is used only so the
plumbing runs and the blindness is measured. Both text and terms are
accent-folded before matching: titles in the Congress's own records drop
accents often enough ('RECONOCIMEINTO', 'TERAPEUTICO') that an accented term
alone would miss them. `config/watchlist-pe.yaml` adds areas by proyecto
key, never by title. A vote inherits the areas of the proyectos its subject
names, as US votes inherit their bill's.

Exit codes: 0 clean; 3 stored what it could and recorded gaps (the job
script publishes that run); anything else, nothing worth publishing.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys
import tempfile
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, pe_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "pe-rollcalls"
CURRENT_PERIOD = 2026
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
TAXONOMY_EN = os.path.join(ROOT, "config", "taxonomy.yaml")
BUDGET_S = 2400.0
HIDDEN_AREAS = (11,)   # migration is collated, never campaigned

SPLEY = "https://api.congreso.gob.pe/spley-portal-service/proyecto-ley/lista-con-filtro"
PAGE_SIZE = 1000
CHAMBER_CODES = {"S": "senado", "D": "diputados", "C": "congreso"}
SITES = {"senado": ("https://senado.congreso.gob.pe", "senador"),
         "diputados": ("https://diputados.congreso.gob.pe", "diputado")}
MEMBER_FIELDS = "id,slug,title,link,class_list,modified"
MEDIA_SEARCHES = ("votaci", "asistencia")
VOTE_FILE = re.compile(r"(?i)(votaci|asistencia)[^/]*\.pdf$")

# The vote system's position tokens -> what we store.
POSITIONS = {"SI": "SI", "NO": "NO", "Abst.": "ABST", "AUS": "AUS", "LO": "LO",
             "LE": "LE", "LP": "LP", "LV": "LV", "SUS": "SUS", "***": "PRES",
             "SinRes": "SR"}
_POS_RE = "|".join(re.escape(p) for p in sorted(POSITIONS, key=len, reverse=True))
RECORD_ID = re.compile(r"(\d{5}) - (\d{5}) - (\d{5}) - ([SDC])\b")
RECORD_CHAMBER = {"S": "senado", "D": "diputados"}


# --- text helpers --------------------------------------------------------------

def fold(text):
    """Accents off, case kept: 'Proposición' -> 'Proposicion', 'ñ' -> 'n'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _fold_tree(value):
    if isinstance(value, str):
        return fold(value)
    if isinstance(value, list):
        return [_fold_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: _fold_tree(v) for k, v in value.items()}
    return value


def taxonomy_path():
    return TAXONOMY_ES if os.path.exists(TAXONOMY_ES) else TAXONOMY_EN


def load_taxonomy(path=None):
    """The taxonomy with every term accent-folded, through filter's own loader
    (so guards, vetoes and inner stars behave exactly as elsewhere)."""
    import yaml
    with open(path or taxonomy_path(), "r", encoding="utf-8") as handle:
        raw = _fold_tree(yaml.safe_load(handle))
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as tmp:
        yaml.safe_dump(raw, tmp, allow_unicode=True)
    try:
        return filt.load_taxonomy(tmp.name)
    finally:
        os.unlink(tmp.name)


def empty_watchlist():
    """watchlist-pe is applied by KEY (pe_store.add_watch_areas)."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    print("[gap] " + detail)


# --- members -------------------------------------------------------------------

def _class_value(classes, prefix):
    for c in classes or []:
        if c.startswith(prefix + "-"):
            return c[len(prefix) + 1:]
    return None


def parse_member(chamber, rec):
    classes = rec.get("class_list") or []
    title = (rec.get("title") or {}).get("rendered") or ""
    import html
    return {
        "member_key": "{0}/{1}".format(chamber, rec["slug"]),
        "chamber": chamber,
        "name": html.unescape(title).strip(),
        "bancada": _class_value(classes, "grupo_parlamentario"),
        "party": _class_value(classes, "partido_politico"),
        "district": _class_value(classes, "distrito_electoral"),
        "period": _class_value(classes, "periodo_parlamentario"),
        "status": _class_value(classes, "condicion"),
        "wp_id": rec.get("id"),
        "link": rec.get("link"),
        "as_of": (rec.get("modified") or "")[:10] or None,
    }


def store_member(conn, m, today):
    conn.execute(
        "INSERT INTO pe_members (member_key, chamber, name, bancada, party, district, period, "
        "status, wp_id, link, as_of, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(member_key) DO UPDATE SET name=excluded.name, bancada=excluded.bancada, "
        "party=excluded.party, district=excluded.district, period=excluded.period, "
        "status=excluded.status, wp_id=excluded.wp_id, link=excluded.link, "
        "as_of=excluded.as_of, last_seen=excluded.last_seen",
        (m["member_key"], m["chamber"], m["name"], m["bancada"], m["party"], m["district"],
         m["period"], m["status"], m["wp_id"], m["link"], m["as_of"], today, today))


def pull_members(conn, client, today, log=print):
    """Both chambers, every page. Returns (stored, gaps)."""
    stored = gaps = 0
    for chamber, (base, kind) in SITES.items():
        page = 1
        while True:
            url = "{0}/wp-json/wp/v2/{1}?per_page=100&page={2}&_fields={3}".format(
                base, kind, page, MEMBER_FIELDS)
            try:
                recs = client.get_json(url, FEED, "members-{0}-p{1}".format(chamber, page))
            except FetchError as exc:
                if page > 1 and "400" in str(exc):
                    break   # WordPress answers 400 past the last page
                _gap(conn, today, "members {0} page {1}: {2}".format(chamber, page, exc))
                gaps += 1
                break
            for rec in recs:
                store_member(conn, parse_member(chamber, rec), today)
                stored += 1
            if len(recs) < 100:
                break
            page += 1
    conn.commit()
    log("pe-rollcalls: {0} member(s) from the two chamber sites".format(stored))
    return stored, gaps


# --- bills ---------------------------------------------------------------------

def parse_bill(rec):
    chamber = CHAMBER_CODES.get(rec.get("codTipoParl") or "C", "congreso")
    authors = [a.strip() for a in (rec.get("autores") or "").split(";") if a.strip()]
    return {
        "bill_key": rec["proyectoLey"].strip(),
        "period": int(rec["perParId"]),
        "chamber": chamber,
        "number": int(rec["pleyNum"]),
        "title": re.sub(r"\s+", " ", rec.get("titulo") or "").strip(),
        "status": (rec.get("desEstado") or "").strip() or None,
        "presented": (rec.get("fecPresentacion") or "")[:10] or None,
        "proponent": (rec.get("desProponente") or "").strip() or None,
        "authors": authors,
    }


def classify_bill(tax, wl, b, watch=None):
    res = filt.filter_item(tax, wl, fold(b["title"]), title=fold(b["title"]))
    return pe_store.add_watch_areas(res, b["bill_key"], wl=watch)


def store_bill(conn, b, res, today):
    conn.execute(
        "INSERT INTO pe_bills (bill_key, period, chamber, number, title, status, presented, "
        "proponent, authors, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET title=excluded.title, status=excluded.status, "
        "presented=excluded.presented, proponent=excluded.proponent, authors=excluded.authors, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (b["bill_key"], b["period"], b["chamber"], b["number"], b["title"], b["status"],
         b["presented"], b["proponent"], pe_store.dumps(b["authors"]),
         pe_store.dumps(res.issue_areas),
         pe_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))


def bill_request(period, code, row_start, page_size=PAGE_SIZE):
    return json.dumps({"perParId": period, "codTipoParl": code, "perLegId": None,
                       "comisionId": None, "estadoId": None, "congresistaId": None,
                       "grupoParlamentarioId": None, "proponenteId": None,
                       "legislaturaId": None, "fecPresentacionDesde": None,
                       "fecPresentacionHasta": None, "pleyNum": None, "palabras": None,
                       "tipoFirmanteId": None, "conAcumulado": False,
                       "pageSize": page_size, "rowStart": row_start})


def pull_bills(conn, client, today, period=CURRENT_PERIOD, codes=("S", "D", "C"),
               tax=None, wl=None, watch=None, log=print, budget=None):
    """Every proyecto of a period, per chamber code. Returns (read, ours, gaps)."""
    tax = tax if tax is not None else load_taxonomy()
    wl = wl if wl is not None else empty_watchlist()
    watch = watch if watch is not None else pe_store.watchlist()
    read = ours = gaps = 0
    for code in codes:
        row_start, total = 0, None
        while total is None or row_start < total:
            if budget is not None and budget.exhausted():
                log(budget.disclose("proyectos", read))
                _gap(conn, today, "budget spent before proyectos {0}/{1} row {2}".format(
                    period, code, row_start))
                return read, ours, gaps + 1
            try:
                reply = client.post_json(SPLEY, bill_request(period, code, row_start), FEED,
                                         "spley-{0}-{1}-{2}".format(period, code, row_start))
            except (FetchError, ValueError) as exc:
                _gap(conn, today, "proyectos {0}/{1} row {2}: {3}".format(
                    period, code, row_start, exc))
                gaps += 1
                break
            data = (reply or {}).get("data") or {}
            rows = data.get("proyectos") or []
            total = int(data.get("rowsTotal") or (rows[0].get("rowsTotal") if rows else 0) or 0)
            if not rows:
                break
            for rec in rows:
                b = parse_bill(rec)
                res = classify_bill(tax, wl, b, watch)
                store_bill(conn, b, res, today)
                read += 1
                ours += on_our_ground(res.issue_areas)
            row_start += len(rows)
        conn.commit()
    return read, ours, gaps


# --- vote records ----------------------------------------------------------------

def _int(pattern, text):
    hit = re.search(pattern, text)
    return int(hit.group(1)) if hit else None


def bancada_table(totals):
    """The group table under a vote's totals: 'FP FUERZA POPULAR 17 0 0 1'
    -> ({code: name}, [si, no, abst, sin_resp] summed over the groups).
    The Senate prints it a row a line, the Diputados record a cell a line,
    so it is read flattened."""
    flat = re.sub(r"\s+", " ", totals or "")
    head = flat.find("Sin Resp.")
    flat = flat[head + len("Sin Resp."):] if head >= 0 else flat
    flat = flat.split("***")[0]
    codes, sums = {}, [0, 0, 0, 0]
    for code, name, a, b, c, d in re.findall(
            r"(?<!\S)([A-Z]{2,6}) ([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ .]*?[A-ZÁÉÍÓÚÑÜ])"
            r" (\d+) (\d+) (\d+) (\d+)(?!\S)", flat):
        codes[code] = name.strip()
        for i, n in enumerate((a, b, c, d)):
            sums[i] += int(n)
    return codes, sums


def bancada_codes(totals):
    return bancada_table(totals)[0]


def _entry_re(codes):
    alt = "|".join(re.escape(c) for c in sorted(codes, key=len, reverse=True))
    return re.compile(
        r"(?<!\S)(?P<b>{0}) (?P<name>\S.*?) (?P<pos>{1})(?: ---| \+\+\+)?"
        r"(?=\s+(?:{0}) \S|\s*$)".format(alt, _POS_RE), re.S)


HEADER_LINE = re.compile(
    r"(?m)^(SENADO DE LA REP[ÚU]BLICA DEL PER[ÚU]|C[ÁA]MARA DE DIPUTADOS[^\n]*|"
    r"CONGRESO DE LA REP[ÚU]BLICA[^\n]*)\s*$")
FOOTER = re.compile(r"COPIA INFORMATIVA|INFORMACI[ÓO]N PROVISIONAL|SIN (?:LOS VOTOS|REGISTROS) ORALES")


ORAL_NOTE = re.compile(r"(?:El|La) (?:diputad[oa]|senador[a]?) [^.]*? deja constancia [^.]*(?:\.|$)\s*")


def _flat(text):
    return re.sub(r"\s+", " ", HEADER_LINE.sub("", text or "")).strip()


def parse_vote_page(text, chamber):
    """One page's text -> [division dicts]. A page holds one record, or an
    attendance record and a vote run together; each record opens with its
    'Sesion del ...' line. Attendance records are skipped."""
    out = []
    # Split before the line ahead of 'Sesion del' (the presiding member's
    # name or the chamber's heading), so it opens the record it belongs to.
    for block in re.split(r"(?m)^(?=[^\n]*\n\s*Sesi[óo]n del )", text or ""):
        d = parse_vote_block(block, chamber)
        if d:
            out.append(d)
    return out


def parse_vote_block(block, chamber):
    """One VOTACION record -> a division dict, or None."""
    marker = re.search(r"VOTACI[ÓO]N:", block)
    rid = RECORD_ID.search(block)
    if not marker or not rid:
        return None
    end = block.find("Resultado de", marker.end())
    if end < 0:
        return None
    codes, group_sums = bancada_table(block[end:])
    if not codes:
        return None
    entry_re = _entry_re(codes)
    date = re.search(r"Fecha:\s*(\d{2})/(\d{2})/(\d{4})\s*Hora:\s*([\d:]+\s*[AP]M)", block)
    area = block[marker.end():end]
    subject = ""
    if "Asunto:" in area:
        # The subject follows 'Asunto:' and runs until the first position.
        pre, post = area.split("Asunto:", 1)
        post_flat = _flat(post)
        post_entries = list(entry_re.finditer(post_flat))
        subject = post_flat[:post_entries[0].start()] if post_entries else post_flat
        entries = list(entry_re.finditer(_flat(pre))) + post_entries
    else:
        entries = list(entry_re.finditer(_flat(area)))
    if not subject.strip():
        # Otherwise it is printed at the foot, after the record id.
        tail = block[rid.end():]
        tail = tail.split("Asunto:", 1)[1] if "Asunto:" in tail else tail
        subject = _flat(FOOTER.sub(" ", tail))
    # The signed record prefixes notes of oral votes; they are not the subject.
    subject = ORAL_NOTE.sub("", subject)
    positions = [{"bancada": m.group("b"), "name_raw": m.group("name").strip(),
                  "position": POSITIONS[m.group("pos")]} for m in entries]
    totals = block[end:]
    d = {
        "record": "{0}-{1}-{2}".format(rid.group(1), rid.group(2), rid.group(3)),
        # The record's own suffix says whose vote it is: the Senate's media
        # library holds at least one Diputados record (18 August 2026).
        "chamber": RECORD_CHAMBER.get(rid.group(4), chamber),
        "date": "{0}-{1}-{2}".format(date.group(3), date.group(2), date.group(1)) if date else None,
        "time": date.group(4) if date else None,
        "subject": subject.strip() or None,
        "yes": _int(r"A FAVOR \(SI\)\s+(\d+)", totals),
        "no": _int(r"EN CONTRA \(NO\)\s+(\d+)", totals),
        "abstain": _int(r"ABSTENCI[ÓO]N\s+(\d+)", totals),
        "no_answer": _int(r"SIN RESPUESTA\s+(\d+)", totals),
        "absent": _int(r"AUSENTE\s+(\d+)", totals),
        "on_leave": sum(int(n) for n in re.findall(r"LIC\. [A-ZÁÉÍÓÚ. ]+?\s+(\d+)", totals)),
        "bancadas": codes,
        "group_sums": group_sums,
        "positions": positions,
        "provisional": int("PROVISIONAL" in block),
    }
    d["counts_match"] = int(counts_match(d))
    return d


def counts_match(d):
    """True when the positions parsed add up to the totals the record prints,
    or to its own group table: the two disagree on at least one record
    (Diputados, 5 August 2026: 'A FAVOR 119' over a group table and 130 rows
    that both give 121), and the rows are what is stored."""
    tally = {}
    for p in d["positions"]:
        tally[p["position"]] = tally.get(p["position"], 0) + 1
    if not d["positions"]:
        return False
    # The presiding member is printed as '***' and counted in SIN RESPUESTA.
    tally["SR"] = tally.get("SR", 0) + tally.get("PRES", 0)
    printed = {"SI": d["yes"], "NO": d["no"], "ABST": d["abstain"], "AUS": d["absent"],
               "SR": d["no_answer"]}
    if all(v is None or tally.get(k, 0) == v for k, v in printed.items()):
        return True
    groups = d.get("group_sums")
    return bool(groups) and [tally.get(k, 0) for k in ("SI", "NO", "ABST", "SR")] == groups


def parse_vote_pdf(raw, chamber):
    """(text_layer, [division dicts]) for one vote record PDF."""
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(raw))
    texts = [(p.extract_text() or "") for p in reader.pages]
    if sum(len(t.strip()) for t in texts) < 200:
        return False, []
    out = []
    for t in texts:
        out.extend(parse_vote_page(t, chamber))
    return True, out


BILL_REF = re.compile(
    r"(?:PROYECTOS? DE (?:LEY|RESOLUCI[ÓO]N LEGISLATIVA)(?: DEL SENADO| DE LA C[ÁA]MARA)?|"
    r"PROPOSICI[ÓO]N(?:ES)? (?:LEGISLATIVAS?|DE LEY)|PROPUESTAS? LEGISLATIVAS?)\s+"
    r"((?:N[°º.]+\s*)?\d+(?:/\d{4}-[A-Z]+)?(?:\s*(?:,|Y|E)\s*\d+(?:/\d{4}-[A-Z]+)?)*)")


def bill_numbers(subject):
    nums = []
    for group in BILL_REF.findall(fold(subject or "").upper().replace("º", "°")):
        for n in re.findall(r"(?<![/\d])(\d+)(?!\d)(?!/?\d{0,3}-)", group):
            if int(n) not in nums:
                nums.append(int(n))
    return nums


def resolve_bills(conn, chamber, subject, period=CURRENT_PERIOD):
    """bill_keys the subject names, resolved in this chamber first, then the
    Congress as a whole; a number that matches nothing (or several) is left out."""
    keys = []
    for n in bill_numbers(subject):
        for ch in (chamber, "congreso"):
            rows = conn.execute("SELECT bill_key FROM pe_bills WHERE period=? AND chamber=? "
                                "AND number=?", (period, ch, n)).fetchall()
            if len(rows) == 1:
                keys.append(rows[0][0])
                break
    return keys


def _surname_given(name):
    name = fold(name).upper().strip().rstrip(",")
    if "," in name:
        s, g = name.split(",", 1)
        return s.strip(), g.strip()
    return name, ""


def resolve_member(members, name_raw, bancada_name=None):
    """members: [(member_key, folded upper surname, folded upper given, bancada slug)].
    Exactly one match or None. The record cuts names to its column, so both
    halves are prefixes; the bancada breaks a tie between two Velasquezes."""
    s, g = _surname_given(name_raw)
    slug = (re.sub(r"[^a-z0-9]+", "-", fold(bancada_name).lower()).strip("-")
            if bancada_name else None)
    hits = [m for m in members if m[1].startswith(s) and (not g or m[2].startswith(g))]
    if len(hits) > 1 and slug:
        hits = [m for m in hits if m[3] == slug] or hits
    if not hits and slug and s:
        # The site and the record do not always print the same surnames
        # ('Duarte, Georgina' on the site, 'DUARTE PATINO DE PEZET' on the
        # record): the first surname inside the same bancada, if unique.
        first = s.split()[0]
        hits = [m for m in members if m[3] == slug and m[1].split()[:1] == [first]]
    return hits[0][0] if len(hits) == 1 else None


def member_index(conn, chamber):
    out = []
    for key, name, bancada in conn.execute(
            "SELECT member_key, name, bancada FROM pe_members WHERE chamber=?", (chamber,)):
        s, g = _surname_given(name or "")
        out.append((key, s, g, bancada))
    return out


def classify_division(tax, wl, d, bill_areas):
    own = filt.filter_item(tax, wl, fold(d.get("subject") or ""))
    return own, sorted(set(own.issue_areas or []) | set(bill_areas or []))


def _bill_areas(conn, keys):
    areas = set()
    for k in keys or []:
        row = conn.execute("SELECT areas FROM pe_bills WHERE bill_key=?", (k,)).fetchone()
        if row:
            areas.update(json.loads(row[0] or "[]"))
    return sorted(areas)


def store_division(conn, d, url, tax, wl, today, members=None):
    key = "{0}/{1}".format(d["chamber"], d["record"])
    refs = resolve_bills(conn, d["chamber"], d["subject"])
    own, areas = classify_division(tax, wl, d, _bill_areas(conn, refs))
    conn.execute(
        "INSERT INTO pe_divisions (division_key, chamber, date, time, subject, bill_refs, "
        "source_url, provisional, yes, no, abstain, no_answer, absent, on_leave, counts_match, "
        "own_areas, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET subject=excluded.subject, "
        "bill_refs=excluded.bill_refs, source_url=excluded.source_url, "
        "provisional=excluded.provisional, yes=excluded.yes, no=excluded.no, "
        "abstain=excluded.abstain, no_answer=excluded.no_answer, absent=excluded.absent, "
        "on_leave=excluded.on_leave, counts_match=excluded.counts_match, "
        "own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, d["chamber"], d["date"], d["time"], d["subject"], pe_store.dumps(refs), url,
         d["provisional"], d["yes"], d["no"], d["abstain"], d["no_answer"], d["absent"],
         d["on_leave"], d["counts_match"], pe_store.dumps(own.issue_areas),
         pe_store.dumps(areas), pe_store.dumps(own.matched_terms), own.tier, today, today))
    members = members if members is not None else member_index(conn, d["chamber"])
    for p in d["positions"]:
        mkey = resolve_member(members, p["name_raw"], d["bancadas"].get(p["bancada"]))
        conn.execute("INSERT OR REPLACE INTO pe_votes (division_key, name_raw, member_key, "
                     "bancada, position) VALUES (?,?,?,?,?)",
                     (key, p["name_raw"], mkey, p["bancada"], p["position"]))
    return key, areas


def list_vote_files(client, chamber, log=print):
    base = SITES[chamber][0]
    seen = {}
    for q in MEDIA_SEARCHES:
        page = 1
        while True:
            url = ("{0}/wp-json/wp/v2/media?search={1}&per_page=100&page={2}"
                   "&_fields=id,date,source_url,mime_type").format(base, q, page)
            try:
                items = client.get_json(url, FEED, "media-{0}-{1}-p{2}".format(chamber, q, page))
            except FetchError as exc:
                if page > 1 and "400" in str(exc):
                    break
                raise
            for it in items:
                src = it.get("source_url") or ""
                if VOTE_FILE.search(src) and src not in seen:
                    seen[src] = (it.get("date") or "")[:10]
            if len(items) < 100:
                break
            page += 1
    return seen


def pull_votes(conn, client, today, tax=None, wl=None, log=print, budget=None):
    """Every vote record PDF not read before. Returns (divisions, ours, gaps)."""
    tax = tax if tax is not None else load_taxonomy()
    wl = wl if wl is not None else empty_watchlist()
    stored = ours = gaps = 0
    done = {u for (u,) in conn.execute("SELECT url FROM pe_vote_files")}
    members = {ch: member_index(conn, ch) for ch in SITES}
    for chamber in SITES:
        try:
            files = list_vote_files(client, chamber)
        except FetchError as exc:
            _gap(conn, today, "vote file list {0}: {1}".format(chamber, exc))
            gaps += 1
            continue
        for url, uploaded in sorted(files.items(), key=lambda kv: kv[1]):
            if url in done:
                continue
            if budget is not None and budget.exhausted():
                log(budget.disclose("vote records", stored))
                _gap(conn, today, "budget spent before vote records were all read ({0})".format(
                    chamber))
                return stored, ours, gaps + 1
            slug = "vote-{0}-{1}".format(chamber, url.rsplit("/", 1)[1])
            try:
                # Not archived on fetch: most of these are scans of 1-14 MB
                # with nothing to read. A file with a text layer is archived
                # below, before it is parsed into the store.
                raw = client.get_bytes(url, FEED, slug, archive=False)
                text_layer, divisions = parse_vote_pdf(raw, chamber)
            except FetchError as exc:
                _gap(conn, today, "vote record {0}: {1}".format(url, exc))
                gaps += 1
                continue
            except Exception as exc:  # a PDF pypdf cannot read is a gap, not a crash
                _gap(conn, today, "vote record {0} unreadable: {1}".format(url, exc))
                gaps += 1
                continue
            if text_layer:
                client._archive(raw, FEED, slug)
            for d in divisions:
                _key, areas = store_division(conn, d, url, tax, wl, today,
                                             members.get(d["chamber"]))
                stored += 1
                ours += on_our_ground(areas)
                if not d["counts_match"]:
                    _gap(conn, today, "vote {0}/{1}: positions parsed do not add up to the "
                         "printed totals ({2})".format(chamber, d["record"], url))
                    gaps += 1
            conn.execute("INSERT OR REPLACE INTO pe_vote_files (url, chamber, uploaded, "
                         "text_layer, divisions, read_at) VALUES (?,?,?,?,?,?)",
                         (url, chamber, uploaded, int(text_layer), len(divisions), today))
            conn.commit()
    return stored, ours, gaps


# --- offline -------------------------------------------------------------------------

def reclassify(conn, tax=None, log=print):
    """Re-derive bill areas, then division areas, offline. Bills first."""
    tax = tax if tax is not None else load_taxonomy()
    wl = empty_watchlist()
    watch = pe_store.watchlist()
    changed_b = changed_d = 0
    for key, title, areas in conn.execute(
            "SELECT bill_key, title, areas FROM pe_bills").fetchall():
        res = classify_bill(tax, wl, {"bill_key": key, "title": title or ""}, watch)
        new = pe_store.dumps(res.issue_areas)
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE pe_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (new, pe_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for key, chamber, subject, areas in conn.execute(
            "SELECT division_key, chamber, subject, areas FROM pe_divisions").fetchall():
        refs = resolve_bills(conn, chamber, subject)
        own, combined = classify_division(tax, wl, {"subject": subject}, _bill_areas(conn, refs))
        new = pe_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE pe_divisions SET bill_refs=?, own_areas=?, areas=?, "
                     "matched_terms=?, tier=? WHERE division_key=?",
                     (pe_store.dumps(refs), pe_store.dumps(own.issue_areas), new,
                      pe_store.dumps(own.matched_terms), own.tier, key))
    conn.commit()
    log("pe-rollcalls: reclassified; {0} bill(s) and {1} division(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} proyecto(s), {1} on our ground; {2} vote(s), {3} on our ground, "
        "{4} adding up; {5} position(s), {6} resolved to a member; {7} member(s); "
        "{8} vote file(s), {9} of them scans".format(
            n("SELECT COUNT(*) FROM pe_bills"), ours("pe_bills"),
            n("SELECT COUNT(*) FROM pe_divisions"), ours("pe_divisions"),
            n("SELECT COUNT(*) FROM pe_divisions WHERE counts_match=1"),
            n("SELECT COUNT(*) FROM pe_votes"),
            n("SELECT COUNT(*) FROM pe_votes WHERE member_key IS NOT NULL"),
            n("SELECT COUNT(*) FROM pe_members"),
            n("SELECT COUNT(*) FROM pe_vote_files"),
            n("SELECT COUNT(*) FROM pe_vote_files WHERE text_layer=0")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--period", type=int, action="append",
                    help="also read this period's proyectos (2021: the old Congress, C only)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-bills", action="store_true")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored proyectos and votes, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    tax = load_taxonomy()
    print("pe-rollcalls: taxonomy {0}".format(os.path.basename(taxonomy_path())))
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        _n, g = pull_members(conn, client, today)
        gaps += g
    if not args.no_bills:
        for period in [CURRENT_PERIOD] + [p for p in (args.period or []) if p != CURRENT_PERIOD]:
            codes = ("S", "D", "C") if period >= 2026 else ("C",)
            read, ours, g = pull_bills(conn, client, today, period=period, codes=codes,
                                       tax=tax, wl=wl, budget=budget)
            gaps += g
            print("pe-rollcalls: {0} proyecto(s) of {1} read, {2} on our ground, {3} gap(s)".format(
                read, period, ours, g))
    if not args.no_votes:
        stored, ours, g = pull_votes(conn, client, today, tax=tax, wl=wl, budget=budget)
        gaps += g
        print("pe-rollcalls: {0} new vote(s) parsed, {1} on our ground, {2} gap(s)".format(
            stored, ours, g))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
