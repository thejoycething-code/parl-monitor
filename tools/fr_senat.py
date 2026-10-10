#!/usr/bin/env python3
"""France, the Senat (FR5, Chris, 10 October 2026: go ahead with the Senat
phase): senators and their groups, the Senate's dossiers, its scrutins
publics and every senator's position, from data.senat.fr.

    python3 tools/fr_senat.py                     # the weekly step (downloads only when due)
    python3 tools/fr_senat.py --force             # download even if not due
    python3 tools/fr_senat.py --dump /tmp/dosleg.zip   # read a local copy (development)
    python3 tools/fr_senat.py --reclassify        # offline, after a taxonomy change
    python3 tools/fr_senat.py --db /tmp/fr.db     # anywhere but the store

SOURCES, all data.senat.fr (Licence Ouverte; robots.txt allows everything):

  * data/dosleg/dosleg.zip: the Dosleg database as a PostgreSQL dump, 16 MB
    zipped, 126 MB of SQL (10 October 2026). Scrutins are in it, not in a
    dataset of their own: `scr` (4,764 scrutins, 696 since the 2024-25
    session) and `votsen` (1.66 million positions; 245,879 since 2024),
    with the dossiers (`loi`), their readings (`lecture`), sittings
    (`date_seance`) and texts (`texte`). Every COPY block is tab-separated
    text: the stdlib reads it.
  * data/senateurs/ODSEN_GENERAL.json (senators, 1.1 MB) and
    ODSEN_HISTOGROUPES.json (every group spell with its dates, 1.6 MB), so
    a senator's group AT THE VOTE comes from the spell covering its date.

AT MOST WEEKLY, AND ONLY WHEN CHANGED. The dump is regenerated nightly, so
before downloading, a one-byte ranged request reads its Last-Modified, ETag
and size (fr_senat_dump). It is downloaded only when it changed since the
last download AND that download is at least six days old; --force overrides.
A download is archived to data/raw like the Assemblee's zips (FR3): the
Senate overwrites it, so the archive is the only provenance.

BROKEN ENCODING, REPAIRED. The dump is valid UTF-8 but carries Windows-1252
bytes decoded as Latin-1: U+0092 for an apostrophe (923 titles across the
dump's scrutins and dossiers, 10 October 2026), U+009C for "oe" (38) and
U+0096 for a dash (30). A terminal shows none of them, which is why the
scope read "lensemble" and "lannee" as apostrophes lost outright: measured
here, every one of them is a U+0092, and no title has truly lost one. Each
C1 character (U+0080 to U+009F) is read back as the Windows-1252 character
it was (fix_c1), and apostrophes are written straight ("'"), as most of the
Senate's titles are and as the Assemblee's title matching expects.

JOINED TO THE ASSEMBLEE. A scrutin reaches its dossier by the Senate's own
chain (scr.code -> date_seance -> lecture -> loi; 16 of 696 recent scrutins,
as the scope measured) or else by the text it names, matched against the
Senate's dossier titles (the kind and full title, "proposition de loi
visant a ...") when exactly one dossier carries it. A Senate dossier is
the Assemblee's dossier when the Senate links it (loi.url_an) or the
Assemblee does (fr_dossiers.senat_url); then the scrutin's dossier_ref is
the Assemblee's uid, so both chambers' votes on one law are one group, the
watchlist keyed on the Assemblee's uid (aide a mourir) applies, and the
Assemblee's dossier lends its areas. Otherwise it is 'SEN-<signet>', a row
of fr_senat_dossiers.

CLASSIFICATION, as the Assemblee's (tools/fr_rollcalls.py, reused): the
France list (taxonomy-fr for `fr`) on the scrutin's own repaired title
with the same false-friend masks, plus the dossier's areas.

NO RESULT WORD. The dump records votes for and against and the majority
required, never adopte or rejete; `result` stays NULL and the edition
shows the counts and the majority. Abstentions and non-votes are tallied
from the positions.

Separation guarantee: writes fr_* rows with chamber 'senat', the
fr_senat_* tables and the shared gaps table only. ONE WRITER AT A TIME on
the store. Exit 3 when it stored what it could and recorded gaps, 0 when
clean (or when nothing was due).
"""

from __future__ import annotations

import argparse
import collections
import datetime
import importlib.util
import io
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, fr_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402


def _fr_rollcalls():
    spec = importlib.util.spec_from_file_location(
        "fr_rollcalls_for_senat", os.path.join(ROOT, "tools", "fr_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


frr = _fr_rollcalls()

FEED = "fr-senat"
CHAMBER = "senat"
DOSLEG = "https://data.senat.fr/data/dosleg/dosleg.zip"
SENATORS = "https://data.senat.fr/data/senateurs/ODSEN_GENERAL.json"
GROUP_SPELLS = "https://data.senat.fr/data/senateurs/ODSEN_HISTOGROUPES.json"
SCRUTIN_URL = "https://www.senat.fr/scrutin-public/{0}/scr{0}-{1}.html"
DOSSIER_URL = "https://www.senat.fr/dossier-legislatif/{0}.html"
# The first session read: 2024-25, the Assemblee's 17th legislature.
FIRST_SESSION = 2024
# Download at most this often (days), and only when the file changed.
MIN_DAYS = 6
TABLES_READ = ("scr", "votsen", "loi", "lecture", "date_seance", "lecass", "texte",
               "typloi", "etaloi", "stavot")
# votsen.posvotcod -> the word fr_votes already uses for the Assemblee.
POSITIONS = {"1": "pour", "2": "contre", "3": "abstention", "4": "nonVotant"}


# --- the dump ------------------------------------------------------------------

def unescape_copy(value):
    """One field of a PostgreSQL COPY text line: '\\N' is NULL; backslash
    escapes as the format defines them."""
    if value == "\\N":
        return None
    if "\\" not in value:
        return value
    out, i = [], 0
    simple = {"t": "\t", "n": "\n", "r": "\r", "\\": "\\", "b": "\b", "f": "\f", "v": "\v"}
    while i < len(value):
        c = value[i]
        if c == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
            m = re.match(r"[0-7]{1,3}", value[i + 1:])
            if m:
                out.append(chr(int(m.group(0), 8)))
                i += 1 + len(m.group(0))
                continue
            out.append(nxt)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def read_tables(lines, wanted=TABLES_READ):
    """{table: (columns, [row dicts])} for the COPY blocks named in `wanted`,
    from an iterable of text lines (the dump is never held whole)."""
    out, current, cols = {}, None, None
    for line in lines:
        if current is None:
            if line.startswith("COPY "):
                m = re.match(r"COPY (\w+) \(([^)]*)\) FROM stdin;", line)
                if m and m.group(1) in wanted:
                    current, cols = m.group(1), [c.strip() for c in m.group(2).split(",")]
                    out[current] = (cols, [])
            continue
        if line.startswith("\\."):
            current = None
            continue
        fields = line.rstrip("\n").split("\t")
        out[current][1].append({c: unescape_copy(v) for c, v in zip(cols, fields)})
    return out


def dump_lines(blob):
    """Text lines of the .sql inside the zip, streamed."""
    zf = zipfile.ZipFile(io.BytesIO(blob))
    name = next(n for n in zf.namelist() if n.endswith(".sql"))
    with zf.open(name) as fh:
        for line in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
            yield line


# --- repairing the encoding -------------------------------------------------------

def fix_c1(text):
    """U+0080..U+009F read back as Windows-1252: U+0092 -> ’ (then ')."""
    if not text:
        return text
    out = []
    for ch in text:
        if "\x80" <= ch <= "\x9f":
            try:
                ch = ch.encode("latin-1").decode("cp1252")
            except UnicodeDecodeError:
                ch = " "
        out.append(ch)
    return "".join(out).replace("’", "'").replace("‘", "'")


# --- parsing the tables (pure) -----------------------------------------------------

def _date(value):
    return (value or "")[:10] or None


def _strip(value):
    return (value or "").strip() or None


def an_uid(url):
    """'https://www.assemblee-nationale.fr/dyn/17/dossiers/DLR5L17N53656' or
    'http://www.assemblee-nationale.fr/17/dossiers/DLR5L17N53225.asp' ->
    'DLR5L17N53225'; None for an AN path slug (resolved by fr_dossiers)."""
    m = re.search(r"(DLR5L\d+N\d+)", url or "")
    return m.group(1) if m else None


def an_slug(url):
    """'http://www.assemblee-nationale.fr/17/dossiers/fin_de_vie_17e.asp' ->
    'fin_de_vie_17e', the Assemblee's titreChemin (fr_dossiers.an_path)."""
    m = re.search(r"/dossiers/([A-Za-z0-9_-]+?)(?:\.asp)?(?:[?#].*)?$", url or "")
    return m.group(1) if m and not m.group(1).startswith("DLR5") else None


def senat_signet(url):
    """The Senate dossier signet in an Assemblee record's senat_url."""
    m = re.search(r"dossier-legislatif/([a-z]+\d{2}-\d+)", url or "")
    return m.group(1) if m else None


def sessions_since(tables, first=FIRST_SESSION):
    """The loicod of every dossier with a reading in a session >= first."""
    lecture = {_strip(r["lecidt"]): _strip(r["loicod"]) for r in tables["lecture"][1]}
    keep = set()
    for r in tables["lecass"][1]:
        try:
            ses = int(r["sesann"] or 0)
        except ValueError:
            continue
        if ses >= first and _strip(r["lecidt"]) in lecture:
            keep.add(lecture[_strip(r["lecidt"])])
    for r in tables["date_seance"][1]:
        if (_date(r["date_s"]) or "") >= "{0}-10-01".format(first):
            loi = lecture.get(_strip(r["lecidt"]))
            if loi:
                keep.add(loi)
    return keep


def parse_dossiers(tables, fix, first=FIRST_SESSION):
    """{loicod: dossier} for the dossiers active since `first`."""
    kinds = {_strip(r["typloicod"]): _strip(r["typloiden"]) or _strip(r["typloilib"])
             for r in tables["typloi"][1]}
    states = {_strip(r["etaloicod"]): _strip(r["etaloilib"]) for r in tables["etaloi"][1]}
    lecture = {}
    for r in tables["lecture"][1]:
        lecture.setdefault(_strip(r["loicod"]), []).append(_strip(r["lecidt"]))
    sittings = collections.defaultdict(list)
    for r in tables["date_seance"][1]:
        sittings[_strip(r["lecidt"])].append(_date(r["date_s"]))
    lecass = collections.defaultdict(list)
    for r in tables["lecass"][1]:
        lecass[_strip(r["lecidt"])].append(_strip(r["lecassidt"]))
    texts = collections.defaultdict(list)
    for r in tables["texte"][1]:
        texts[_strip(r["lecassidt"])].append(_date(r["txtoritxtdat"]))
    keep = sessions_since(tables, first)
    out = {}
    for r in tables["loi"][1]:
        code = _strip(r["loicod"])
        if code not in keep or not _strip(r["signet"]):
            continue
        kind = kinds.get(_strip(r["typloicod"])) or ""
        title = fix(_strip(r["loiint"]) or _strip(r["loitit"]) or "")
        lecs = lecture.get(code, [])
        dates = [d for lec in lecs for d in sittings.get(lec, []) if d]
        deposits = [d for lec in lecs for la in lecass.get(lec, []) for d in texts.get(la, []) if d]
        out[code] = {
            "loicod": code, "signet": _strip(r["signet"]), "kind": kind,
            "title": " ".join(x for x in (kind, title) if x),
            "short_title": fix(_strip(r["loient"])), "state": states.get(_strip(r["etaloicod"])),
            "an_uid": an_uid(r.get("url_an")), "an_url": _strip(r.get("url_an")),
            "deposited": min(deposits) if deposits else None,
            "last_sitting": max(dates) if dates else None,
            "lecidts": lecs}
    return out


def parse_scrutins(tables, fix, first=FIRST_SESSION):
    """[scrutin] since the session `first`, with positions and the loi the
    Senate's own chain reaches (or None)."""
    seance_lec = {_strip(r["code"]): _strip(r["lecidt"]) for r in tables["date_seance"][1]}
    lec_loi = {_strip(r["lecidt"]): _strip(r["loicod"]) for r in tables["lecture"][1]}
    status = {_strip(r["stavotidt"]): _strip(r["stavotlib"]) for r in tables["stavot"][1]}
    positions = collections.defaultdict(list)
    for r in tables["votsen"][1]:
        if int(r["sesann"]) < first:
            continue
        positions[(int(r["sesann"]), int(r["scrnum"]))].append({
            "senmat": _strip(r["senmat"]), "position": POSITIONS.get(_strip(r["posvotcod"])),
            "status": None if _strip(r["stavotidt"]) in (None, "0") else
            status.get(_strip(r["stavotidt"]), _strip(r["stavotidt"])),
            "by_delegation": 1 if _strip(r["senmatdel"]) else 0})
    out = []
    headers = {(int(r["sesann"]), int(r["scrnum"])) for r in tables["scr"][1]}
    # Positions whose scrutin has no header in `scr` (11 scrutins of the
    # 2024-25 session, 3,821 positions, on 10 October 2026): nothing says
    # what was voted, so they are not stored, and the log names them.
    parse_scrutins.orphans = sorted(k for k in positions if k not in headers)
    for r in tables["scr"][1]:
        ses, num = int(r["sesann"]), int(r["scrnum"])
        if ses < first:
            continue
        lec = seance_lec.get(_strip(r["code"]))
        pos = positions.get((ses, num), [])
        out.append({
            "session": ses, "number": num, "date": _date(r["scrdat"]),
            "title": fix(_strip(r["scrint"]) or ""), "pour": frr._int(r["scrpou"]),
            "contre": frr._int(r["scrcon"]), "majority": frr._int(r["scrmaj"]),
            "abstentions": sum(1 for p in pos if p["position"] == "abstention"),
            "non_votants": sum(1 for p in pos if p["position"] == "nonVotant"),
            "loicod": lec_loi.get(lec) if lec else None, "positions": pos})
    return out


TEXT_NAME = re.compile(r"(?:\b(?:du|de la|de l'|sur la|sur le|sur les|des)\s+)"
                       r"((?:projet|proposition)s? de loi\b.*)$", re.I)


def text_name(title):
    hit = TEXT_NAME.search(frr.nfc(title).replace("’", "'"))
    return frr.norm_title(hit.group(1)) if hit else None


def title_index(dossiers):
    index = collections.defaultdict(set)
    for d in dossiers.values():
        if d["title"]:
            index[frr.norm_title(d["title"])].add(d["loicod"])
    return index


def join_loi(s, index):
    """(loicod, via): the Senate's chain first, then a unique title."""
    if s["loicod"]:
        return s["loicod"], "ref"
    name = text_name(s["title"])
    hits = index.get(name) if name else None
    if hits and len(hits) == 1:
        return next(iter(hits)), "title"
    return None, None


def parse_senators(general, spells):
    """({matricule: senator}, {matricule: [(from, to, code)]}, {code: label})."""
    members = {}
    for r in (general or {}).get("results") or []:
        mat = _strip(r.get("Matricule"))
        if not mat:
            continue
        members[mat] = {"name": " ".join(x for x in (r.get("Prenom_usuel"), r.get("Nom_usuel")) if x),
                        "civility": r.get("Qualite"), "group": r.get("Groupe_politique"),
                        "department": r.get("Circonscription"),
                        "current": 1 if r.get("Etat") == "ACTIF" else 0}
    by_mat, labels, seen = collections.defaultdict(list), {}, set()
    for r in (spells or {}).get("results") or []:
        mat, code = _strip(r.get("Matricule")), _strip(r.get("Code_du_groupe_politique"))
        ident = (mat, r.get("Id_appartenance"))
        if not mat or not code or ident in seen:
            continue
        seen.add(ident)
        start = (r.get("Date_de_debut_d_appartenance") or "")[:10].replace("/", "-") or None
        end = (r.get("Date_de_fin_d_appartenance") or "")[:10].replace("/", "-") or None
        by_mat[mat].append((start, end, code))
        labels.setdefault(code, r.get("Nom_court_du_groupe_politique"))
    return members, dict(by_mat), labels


def group_on(spells, date):
    for start, end, code in spells or []:
        if (start or "") <= (date or "") and (not end or (date or "") <= end):
            return code
    return None


# --- downloading ----------------------------------------------------------------

def remote_state(client):
    """(last_modified, etag, size) from a one-byte ranged request."""
    client.get_bytes(DOSLEG, FEED, "dosleg-head", first_bytes=1)
    h = {k.lower(): v for k, v in (client.last_headers or {}).items()}
    size = None
    m = re.search(r"/(\d+)$", h.get("content-range") or "")
    if m:
        size = int(m.group(1))
    return h.get("last-modified"), h.get("etag"), size


def due(conn, today, remote, min_days=MIN_DAYS):
    """(True/False, why). Due when never fetched, or when the file changed
    AND the last download is at least `min_days` old."""
    row = conn.execute("SELECT last_modified, etag, size, fetched_at FROM fr_senat_dump "
                       "WHERE url=?", (DOSLEG,)).fetchone()
    if not row or not row[3]:
        return True, "never downloaded"
    age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(row[3])).days
    changed = tuple(remote) != tuple(row[:3]) and any(remote)
    if not changed:
        return False, "unchanged since {0}".format(row[3])
    if age < min_days:
        return False, "changed, but downloaded {0} day(s) ago".format(age)
    return True, "changed; last download {0} day(s) ago".format(age)


def record_download(conn, today, remote):
    conn.execute("INSERT INTO fr_senat_dump (url, last_modified, etag, size, fetched_at) "
                 "VALUES (?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET "
                 "last_modified=excluded.last_modified, etag=excluded.etag, "
                 "size=excluded.size, fetched_at=excluded.fetched_at",
                 (DOSLEG,) + tuple(remote) + (today,))


# --- storing --------------------------------------------------------------------

def _gap(conn, today, detail, log=print):
    log("  [gap] " + detail)
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def an_crosswalk(conn):
    """{signet: AN uid} from the Assemblee's own dossiers' senat_url, and
    {AN path slug: AN uid} from their titreChemin (the Senate's url_an often
    names the slug, 'fin_de_vie_17e', not the uid)."""
    out, slugs = {}, {}
    for ref, url, path in conn.execute("SELECT dossier_ref, senat_url, an_path FROM fr_dossiers"):
        sig = senat_signet(url)
        if sig:
            out.setdefault(sig, ref)
        if path:
            slugs.setdefault(path, ref)
    out["__slugs__"] = slugs
    return out


def dossier_ref_for(d, an_known, crosswalk):
    """The Assemblee's uid when either side links them and the store holds
    it; else 'SEN-<signet>'."""
    slugs = crosswalk.get("__slugs__") or {}
    uid = (d.get("an_uid") or slugs.get(an_slug(d.get("an_url")) or "")
           or crosswalk.get(d["signet"]))
    if uid and uid in an_known:
        return uid
    return "SEN-" + d["signet"]


def classify_dossier(tax, wl, d):
    res = filt.filter_item(tax, wl, frr.mask(d["title"] or ""), frr.mask(d.get("short_title") or ""))
    res = fr_store.add_watch_areas(res, "SEN-" + d["signet"])
    if d.get("an_uid"):
        res = fr_store.add_watch_areas(res, d["an_uid"])
    return res


def store_dossier(conn, d, res, today, an_ref):
    conn.execute(
        "INSERT INTO fr_senat_dossiers (dossier_ref, signet, loicod, kind, title, short_title, "
        "state, an_dossier_ref, deposited, last_sitting, areas, matched_terms, tier, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(dossier_ref) DO UPDATE SET "
        "loicod=excluded.loicod, kind=excluded.kind, title=excluded.title, "
        "short_title=excluded.short_title, state=excluded.state, "
        "an_dossier_ref=excluded.an_dossier_ref, deposited=excluded.deposited, "
        "last_sitting=excluded.last_sitting, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        ("SEN-" + d["signet"], d["signet"], d["loicod"], d["kind"], d["title"], d["short_title"],
         d["state"], an_ref if not an_ref.startswith("SEN-") else None, d["deposited"],
         d["last_sitting"], fr_store.dumps(res.issue_areas),
         fr_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier,
         today, today))


def display_names(members, spells):
    """{group code: the name the Senate prints for it}. The spells use
    internal codes ('UMP' for Les Républicains, 'SOC' for the SER group);
    the senators' file prints the name in use ('Les Républicains', 'SER').
    Each code takes the name most of its sitting members carry."""
    votes = collections.defaultdict(collections.Counter)
    for mat, m in members.items():
        if not m.get("current") or not m.get("group") or not spells.get(mat):
            continue
        latest = max(spells[mat], key=lambda s: s[0] or "")
        if not latest[1]:
            votes[latest[2]][m["group"]] += 1
    return {code: c.most_common(1)[0][0] for code, c in votes.items()}


def store_members(conn, members, spells, labels, today):
    shown = display_names(members, spells)
    for code, label in labels.items():
        conn.execute("INSERT INTO fr_groups (organe_ref, chamber, abbr, label) VALUES (?,?,?,?) "
                     "ON CONFLICT(organe_ref) DO UPDATE SET abbr=excluded.abbr, "
                     "label=excluded.label", ("senat:" + code, CHAMBER, shown.get(code, code), label))
    for mat, m in members.items():
        latest = (spells.get(mat) or [])
        latest = max(latest, key=lambda s: s[0] or "")[2] if latest else m["group"]
        conn.execute(fr_store.MEMBER_UPSERT,
                     (mat, CHAMBER, m["name"], m["civility"], "senat:" + latest if latest else None,
                      m["department"], None, m["current"], today, today, today))


def store_scrutin(conn, s, tax, wl, today, ref, via, spells):
    key = "senat-{0}-{1}".format(s["session"], s["number"])
    own, areas = frr.classify_division(tax, wl, s, frr._dossier_areas(conn, ref))
    conn.execute(
        "INSERT INTO fr_divisions (division_key, chamber, legislature, number, date, vote_type, "
        "result, title, dossier_ref, dossier_via, pour, contre, abstentions, non_votants, "
        "own_areas, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET title=excluded.title, "
        "dossier_ref=excluded.dossier_ref, dossier_via=excluded.dossier_via, "
        "pour=excluded.pour, contre=excluded.contre, abstentions=excluded.abstentions, "
        "non_votants=excluded.non_votants, own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (key, CHAMBER, s["session"], s["number"], s["date"], "SPO", None, s["title"], ref, via,
         s["pour"], s["contre"], s["abstentions"], s["non_votants"],
         fr_store.dumps(own.issue_areas), fr_store.dumps(areas),
         fr_store.dumps(own.matched_terms), own.tier, today, today))
    conn.execute("DELETE FROM fr_votes WHERE division_key=?", (key,))
    for p in s["positions"]:
        grp = group_on(spells.get(p["senmat"]), s["date"])
        conn.execute("INSERT OR REPLACE INTO fr_votes (division_key, acteur_ref, position, "
                     "group_ref, by_delegation, cause, intended) VALUES (?,?,?,?,?,?,NULL)",
                     (key, p["senmat"], p["position"], "senat:" + grp if grp else None,
                      p["by_delegation"], p["status"]))
    return areas


def load(conn, tables, general, spells_json, today, tax=None, wl=None, log=print,
         first=FIRST_SESSION):
    """Everything from parsed tables into the store. Returns (dossiers,
    scrutins, ours, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(frr.taxonomy_path(),
                                                         country=frr.TAXONOMY_COUNTRY)
    wl = wl if wl is not None else frr.empty_watchlist()
    gaps = 0
    fix = fix_c1
    members, spells, labels = parse_senators(general, spells_json)
    store_members(conn, members, spells, labels, today)
    dossiers = parse_dossiers(tables, fix, first)
    an_known = {r for (r,) in conn.execute("SELECT dossier_ref FROM fr_dossiers")}
    crosswalk = an_crosswalk(conn)
    refs = {}
    for d in dossiers.values():
        ref = dossier_ref_for(d, an_known, crosswalk)
        refs[d["loicod"]] = ref
        store_dossier(conn, d, classify_dossier(tax, wl, d), today, ref)
    index = title_index(dossiers)
    ours = n = 0
    unknown = set()
    for s in parse_scrutins(tables, fix, first):
        loi, via = join_loi(s, index)
        ref = refs.get(loi) if loi else None
        if loi and not ref:
            # Reached by the chain but older than `first`: no row for it.
            ref, via = None, None
        areas = store_scrutin(conn, s, tax, wl, today, ref, via, spells)
        ours += frr.on_our_ground(areas)
        n += 1
        unknown |= {p["senmat"] for p in s["positions"] if p["senmat"] not in members}
        if not s["positions"]:
            _gap(conn, today, "Senat scrutin {0}-{1}: no positions".format(s["session"],
                                                                           s["number"]), log)
            gaps += 1
    if unknown:
        _gap(conn, today, "{0} senator(s) named in no ODSEN file".format(len(unknown)), log)
        gaps += 1
    orphans = getattr(parse_scrutins, "orphans", [])
    if orphans:
        log("  {0} scrutin(s) have positions but no header in the dump ({1}); "
            "not stored".format(
                len(orphans), ", ".join("{0}-{1}".format(*k) for k in orphans[:5])))
    conn.execute("UPDATE fr_senat_dump SET parsed_at=? WHERE url=?", (today, DOSLEG))
    conn.commit()
    return len(dossiers), n, ours, gaps


def reclassify(conn, tax=None, log=print):
    """Senate dossiers, then Senate scrutins, offline."""
    tax = tax if tax is not None else filt.load_taxonomy(frr.taxonomy_path(),
                                                         country=frr.TAXONOMY_COUNTRY)
    wl = frr.empty_watchlist()
    for ref, signet, title, short, an in conn.execute(
            "SELECT dossier_ref, signet, title, short_title, an_dossier_ref "
            "FROM fr_senat_dossiers").fetchall():
        res = classify_dossier(tax, wl, {"signet": signet, "title": title, "short_title": short,
                                         "an_uid": an})
        conn.execute("UPDATE fr_senat_dossiers SET areas=?, matched_terms=?, tier=? "
                     "WHERE dossier_ref=?",
                     (fr_store.dumps(res.issue_areas),
                      fr_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, ref))
    changed = 0
    for key, ref, title, areas in conn.execute(
            "SELECT division_key, dossier_ref, title, areas FROM fr_divisions WHERE chamber=?",
            (CHAMBER,)).fetchall():
        own, combined = frr.classify_division(tax, wl, {"title": title},
                                              frr._dossier_areas(conn, ref))
        new = fr_store.dumps(combined)
        changed += new != (areas or "[]")
        conn.execute("UPDATE fr_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?", (fr_store.dumps(own.issue_areas), new,
                                              fr_store.dumps(own.matched_terms), own.tier, key))
    conn.commit()
    log("fr-senat: reclassified; {0} Senate scrutin(s) changed area".format(changed))
    return changed


HEARTBEAT = "FR Senat"


def stamp(conn, today):
    """The step's own heartbeat (tools/coverage.py AWAITING_FIRST_RUN): the
    weekly it belongs to had its heartbeat before this step's tables existed."""
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/fr_senat.py"))
    conn.commit()


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = sum(frr.on_our_ground(json.loads(a or "[]")) for (a,) in conn.execute(
        "SELECT areas FROM fr_divisions WHERE chamber='senat'"))
    log("  store: {0} Senate dossier(s); {1} Senate scrutin(s), {2} on our ground, {3} joined "
        "to a dossier; {4} senator(s); {5} Senate position(s)".format(
            n("SELECT COUNT(*) FROM fr_senat_dossiers"),
            n("SELECT COUNT(*) FROM fr_divisions WHERE chamber='senat'"), ours,
            n("SELECT COUNT(*) FROM fr_divisions WHERE chamber='senat' AND dossier_ref IS NOT NULL"),
            n("SELECT COUNT(*) FROM fr_members WHERE chamber='senat'"),
            n("SELECT COUNT(*) FROM fr_votes WHERE division_key LIKE 'senat-%'")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--force", action="store_true", help="download even if not due")
    ap.add_argument("--dump", help="read this local dosleg.zip instead of downloading")
    ap.add_argument("--first-session", type=int, default=FIRST_SESSION)
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=1.0)
    today = datetime.date.today().isoformat()
    if args.dump:
        with open(args.dump, "rb") as fh:
            blob = fh.read()
    else:
        try:
            remote = remote_state(client)
        except FetchError as exc:
            _gap(conn, today, "Senat dump headers: {0}".format(exc))
            conn.commit()
            return 3
        ok, why = due(conn, today, remote)
        print("fr-senat: dosleg.zip {0} ({1}, {2} bytes): {3}".format(
            "due" if ok or args.force else "not due", remote[0], remote[2], why))
        if not (ok or args.force):
            summary(conn)
            conn.close()
            return 0
        try:
            # Archived (as FR3 archives the Assemblee's zips): the Senate
            # overwrites it nightly.
            blob = client.get_bytes(DOSLEG, FEED, "dosleg", timeout=600, archive=True)
        except FetchError as exc:
            _gap(conn, today, "Senat dump: {0}".format(exc))
            conn.commit()
            return 3
        record_download(conn, today, remote)
        conn.commit()
    try:
        general = client.get_json(SENATORS, FEED, "odsen-general")
        spells = client.get_json(GROUP_SPELLS, FEED, "odsen-histogroupes")
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "Senat senators: {0}".format(exc))
        conn.commit()
        return 3
    tables = read_tables(dump_lines(blob))
    missing = [t for t in TABLES_READ if t not in tables]
    if missing:
        _gap(conn, today, "Senat dump lacks {0}".format(", ".join(missing)))
        conn.commit()
        return 3
    dossiers, scrutins, ours, gaps = load(conn, tables, general, spells, today,
                                          first=args.first_session)
    print("fr-senat: {0} dossier(s), {1} scrutin(s) since the {2} session, {3} on our ground, "
          "{4} gap(s)".format(dossiers, scrutins, args.first_session, ours, gaps))
    stamp(conn, today)
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
