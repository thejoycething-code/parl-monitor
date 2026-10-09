#!/usr/bin/env python3
"""Mexico, Chamber of Deputies: members, iniciativas, recorded votes and
every deputy's position.

    python3 tools/mx_rollcalls.py                    # the current legislature (LXVI)
    python3 tools/mx_rollcalls.py --dry-run          # count, store nothing
    python3 tools/mx_rollcalls.py --reclassify       # re-derive areas, offline
    python3 tools/mx_rollcalls.py --db /tmp/mx.db    # anywhere but the store

PHASE 1 (9 October 2026); see docs/mexico-scope.md. Every source is open,
keyless and official, and every one is HTML:

  * sitl.diputados.gob.mx/LXVI_leg/ (SITL, the Chamber's information
    system): the deputies, the recorded votes by period, each vote's totals
    by group, and one list per group with every deputy's position and SITL
    id. 285 votes in the LXVI to 2 October 2026.
  * gaceta.diputados.gob.mx (the Gaceta Parlamentaria): one static list of
    iniciativas per period (8,247 in the LXVI, with turno, every later step
    and a link to the vote that decided it), and one list of votes per
    period, whose 'Votación' links are what ties a vote to its iniciativas.

THESE HOSTS REFUSE THE UK. Every diputados.gob.mx address times out from
the laptop in London; GitHub's runners reach them. So this runs on GitHub
Actions (mx-weekly.yml), and the Mac Mini's job is only the clock that
dispatches it (jobs/mx-weekly.sh).

SITL AND THE SIL HOST FORGET THEIR INTERMEDIATE CERTIFICATE. sitl and web
send only the leaf, so urllib and curl both refuse them. Verification stays
on: config/mx-ca-intermediates.pem adds the missing public intermediate
(the same one gaceta.diputados.gob.mx sends) to the system's roots.

THE TAXONOMY IS NOT HERE YET. The English taxonomy is blind to Spanish, as
it was to German, and a Spanish term list is a proposal in the scope doc
awaiting Christopher. Until config/taxonomy-es.yaml exists, nothing is
classified by terms: areas come only from config/watchlist-mx.yaml, keyed by
iniciativa number. --reclassify fills them in once the file lands.

Separation guarantee: writes mx_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import ssl
import sys
import unicodedata
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, mx_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "mx-rollcalls"
LEGISLATURE = 66
ROMAN = {64: "LXIV", 65: "LXV", 66: "LXVI", 67: "LXVII"}
TAXONOMY_ES = os.path.join(ROOT, "config", "taxonomy-es.yaml")
EXTRA_CA = os.path.join(ROOT, "config", "mx-ca-intermediates.pem")
SITL = "https://sitl.diputados.gob.mx/{leg}_leg/"
GACETA = "https://gaceta.diputados.gob.mx"
# One request a second per host: these are a parliament's own small servers.
HOST_DELAY = 1.0
BUDGET_S = 2400.0
HIDDEN_AREAS = (11,)

MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
          "noviembre": 11, "diciembre": 12}
# The party logos on SITL's list of deputies (it names the group only by image).
LOGOS = {"logomorena": "MORENA", "pan": "PAN", "logvrd": "PVEM", "pt": "PT",
         "pri01": "PRI", "logo_movimiento_ciudadano": "MC", "ind": "IND", "prd": "PRD"}


# --- small helpers -------------------------------------------------------------

def leg_path(legislature):
    return SITL.format(leg=ROMAN[legislature])


def suffix(legislature):
    """'nplxvi': SITL's page names end in the legislature, lower case."""
    return "np" + ROMAN[legislature].lower()


def fold(text):
    """Strip accents: SITL titles are upper case and not always accented."""
    return "".join(c for c in unicodedata.normalize("NFD", text or "")
                   if unicodedata.category(c) != "Mn")


def clean(markup):
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))
    return re.sub(r"\s+", " ", text).strip() or None


def decode(raw):
    """SITL serves UTF-8; the Gaceta ISO-8859-1. Neither always says so, and
    SITL mixes them: its vote lists are UTF-8 with one Latin-1 byte in a CSS
    comment ('l\xednea'), so a whole-page fallback would garble every name.
    Line by line, each line in the first encoding that reads it."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    out = []
    for line in raw.split(b"\n"):
        try:
            out.append(line.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(line.decode("cp1252", errors="replace"))
    return "\n".join(out)


def iso_date(text):
    """'3 Septiembre 2024', '3-Septiembre-2024' or 'martes 1 de septiembre de
    2026' -> ISO; None if unreadable."""
    hit = re.search(r"(\d{1,2})[\s\-]+(?:de\s+)?([A-Za-zÁÉÍÓÚáéíóú]+)[\s\-]+(?:de\s+)?(\d{4})",
                    text or "")
    if not hit:
        return None
    month = MONTHS.get(fold(hit.group(2)).lower())
    if not month:
        return None
    try:
        return datetime.date(int(hit.group(3)), month, int(hit.group(1))).isoformat()
    except ValueError:
        return None


def _int(text):
    try:
        return int(re.sub(r"[^\d]", "", text or ""))
    except ValueError:
        return None


def make_client(raw_dir=None, extra_ca=EXTRA_CA):
    ctx = ssl.create_default_context()
    if extra_ca and os.path.exists(extra_ca):
        ctx.load_verify_locations(cafile=extra_ca)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    client = HttpClient(raw_dir or os.path.join(ROOT, "data", "raw"), opener=opener)
    for host in ("sitl.diputados.gob.mx", "gaceta.diputados.gob.mx"):
        client.set_host_throttle(host, HOST_DELAY)
    return client


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


# --- SITL parsers --------------------------------------------------------------

def parse_members(page):
    """SITL's list of deputies by group: [{dipt, name, party, entidad, distrito}].
    The group is named only by the logo heading each table."""
    out, party = [], None
    for m in re.finditer(r'<img src="[^"]*?images/([\w\-]+)\.\w+"|'
                         r'<a href="curricula\.php\?dipt=(\d+)"[^>]*>(.*?)</a>\s*</td>\s*'
                         r'<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>', page, flags=re.S):
        if m.group(1):
            stem = m.group(1).lower()
            if stem in ("logo_lxvi", "ig_gdap", "background", "favicon"):
                continue
            party = LOGOS.get(stem, stem.upper())
            continue
        name = re.sub(r"^\d+\s+", "", clean(m.group(3)) or "")
        out.append({"dipt": int(m.group(2)), "name": name or None, "party": party,
                    "entidad": clean(m.group(4)), "distrito": clean(m.group(5))})
    return out


def parse_periods(page):
    """[(pert, label)] from SITL's list of periods with votes."""
    seen, out = set(), []
    for pert, label in re.findall(r'pert=(\d+)"\s*>\s*([^<]+)<', page):
        if int(pert) not in seen:
            seen.add(int(pert))
            out.append((int(pert), clean(label)))
    return out


def parse_period_votes(page):
    """(period label, [(votaciont, iso date, title)]) from one period's page.
    Dates are row headings above the votes they cover."""
    label = re.search(r'class="Estilo61enex">\s*([^<]+)<', page)
    out, date = [], None
    for m in re.finditer(r'<TD[^>]*colspan=2[^>]*>\s*([^<]+?)\s*</TD>|'
                         r'votaciont=(\d+)"[^>]*>\d+</a></td>\s*<td[^>]*>(.*?)</td>',
                         page, flags=re.S | re.I):
        if m.group(1):
            date = iso_date(m.group(1)) or date
        else:
            out.append((int(m.group(2)), date, clean(m.group(3))))
    return (clean(label.group(1)) if label else None), out


def parse_estadistico(page):
    """A vote's totals: {title, date, groups: {group: [6 ints]}, total: [6 ints],
    lists: [(partidot, group)]}. The columns are a favor, en contra,
    abstención, solo asistencia, ausente, total."""
    body = page.split("GRUPO PARLAMENTARIO", 1)
    head = body[0]
    title = date = None
    for text in re.findall(r'<span class="Estilo61en\w*[^"]*"[^>]*>(.*?)</span>', head, flags=re.S):
        text = clean(text)
        if not text:
            continue
        if len(text) < 30 and iso_date(text):
            date = date or iso_date(text)
        elif len(text) > 20 and title is None:
            title = text
    if date is None:
        hit = re.search(r"\d{1,2}-[A-Za-zÁÉÍÓÚáéíóú]+-\d{4}", head)
        date = iso_date(hit.group(0)) if hit else None
    groups, lists, total = {}, [], None
    if len(body) == 2:
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body[1], flags=re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)
            if len(cells) != 7:
                continue
            link = re.search(r"partidot=(\d+)&(?:amp;)?votaciont=\d+", cells[0])
            name = clean(cells[0])
            nums = [_int(clean(c)) for c in cells[1:]]
            if name == "TOTAL":
                total = nums
            elif name:
                groups[name] = nums
                if link:
                    lists.append((int(link.group(1)), name))
    return {"title": title, "date": date, "groups": groups, "total": total, "lists": lists}


def parse_listado(page):
    """[(iddipt, name, position)] from one group's list on one vote."""
    out = []
    for dipt, name, pos in re.findall(
            r"iddipt=(\d+)[^\"]*\"[^>]*>(.*?)</a>.*?<span class=\"Estiloparrafoc\">(.*?)</span>",
            page, flags=re.S):
        out.append((int(dipt), clean(name), clean(pos)))
    return out


# --- Gaceta parsers ------------------------------------------------------------

def _blocks(page):
    return re.findall(r"<ul><li>(.*?)</li></ul>", page, flags=re.S | re.I)


def origin_of(presenter, kind):
    p = fold(presenter or "").lower()
    if kind == "minuta" or "camara de senadores" in p:
        return "senado"
    if "senador" in p:
        return "senado"
    if "diputad" in p:
        return "diputados"
    if "ejecutivo" in p:
        return "ejecutivo"
    if "congreso" in p or "legislatura" in p:
        return "congreso_local"
    if "ciudadan" in p:
        return "ciudadanos"
    return "otro" if p else None


# The furthest step an entry's progress lines record. "Dictaminada y aprobada
# ..., Turnada a la Cámara de Senadores" is approved, not merely turned:
# the last line is not the furthest step.
STEPS = (("publicad", "publicada", 5), ("aprobad", "aprobada", 4),
         ("desechad", "desechada", 4), ("retirad", "retirada", 4),
         ("devuelt", "devuelta", 3), ("dictaminad", "dictaminada", 3),
         ("prorroga", "prorroga", 2), ("turnad", "turnada", 1), ("turno", "turnada", 1))


def furthest_step(lines):
    best, rank = None, 0
    for line in lines or []:
        low = fold(line).lower()
        for stem, name, r in STEPS:
            if re.search(r"\b" + stem, low) and r > rank:
                best, rank = name, r
    return best


def parse_iniciativas(page, legislature=LEGISLATURE, period=None):
    """Every entry of one Gaceta iniciativas list."""
    out = []
    for blk in _blocks(page):
        parts = [p for p in re.split(r"<br\s*/?>", blk, flags=re.I)]
        title = clean(parts[0])
        if not title:
            continue
        lines = [clean(p) for p in parts[1:]]
        lines = [x for x in lines if x]
        gaceta_line = next((x for x in reversed(lines) if x.startswith("Gaceta Parlamentaria")), None)
        num = re.search(r"\(([0-9]+X?)\)\s*$", gaceta_line or clean(blk) or "")
        number = int(num.group(1)) if num and num.group(1).isdigit() else None
        refs = re.findall(r'<a href="([^"]+)"[^>]*>\s*Gaceta Parlamentaria', blk, flags=re.I)
        ref = refs[-1] if refs else None
        presenter = next((x for x in lines if re.match(r"(Presentada|Presentado|Enviada|Enviado|Suscrita)\b", x)), None)
        kind = "minuta" if title.lower().startswith("minuta") else "iniciativa"
        party = None
        if presenter and "," in presenter:
            tail = presenter.rsplit(",", 1)[1].strip().rstrip(".").strip()
            if tail and len(tail) <= 40 and "diputad" not in tail.lower():
                party = tail
        turno = next((x for x in lines if re.match(r"Turnad[ao]\b", x)), None)
        status_lines = [x for x in lines if x is not gaceta_line and x is not presenter
                        and not x.startswith("Gaceta Parlamentaria")]
        status = furthest_step(status_lines)
        if number is not None:
            key = "{0}/{1}".format(legislature, number)
        elif ref:
            key = "{0}/p/{1}".format(legislature, ref.rsplit("/", 1)[-1])
        else:
            continue
        out.append({
            "ini_key": key, "legislature": legislature, "number": number,
            "provisional": int(number is None), "kind": kind, "title": title,
            "presenter": presenter, "origin": origin_of(presenter, kind), "party": party,
            "turno": re.sub(r"^Turnad[ao]\s+(a\s+)?(las|la|los|el)?\s*", "", turno or "").rstrip(".") or None,
            "status": status, "status_lines": status_lines,
            "presented": iso_date(gaceta_line), "period": period, "gaceta_ref": ref,
            "vote_tables": sorted(set(re.findall(r'href="(/Gaceta/Votaciones/[^"]+\.php3)"', blk,
                                                 flags=re.I))),
        })
    return out


def parse_gaceta_votes(page):
    """{tabla: {date, title, favor, contra, abstencion}} from one Gaceta list of
    votes. A block can hold several votes (in general, then in particular);
    each 'Votación' link is read with the sentence just before it. The
    particular vote's sentence usually carries NO counts: those come from
    the table itself (parse_tabla). The date is the session heading above
    the block, which is right where the sentence is not: the LXVI's first
    vote is printed as 'el jueves 29 de agosto de 2021'."""
    out = {}
    date = None
    for m in re.finditer(r'<font color="#CC0000">([^<]+)</font>|<ul><li>(.*?)</li></ul>', page,
                         flags=re.S | re.I):
        if m.group(1):
            date = iso_date(m.group(1)) or date
            continue
        blk = m.group(2)
        title = clean(re.split(r"<br\s*/?>", blk, flags=re.I)[0])
        for link in re.finditer(r'href="(/Gaceta/Votaciones/[^"]+\.php3)"', blk, flags=re.I):
            before = blk[:link.start()]
            sentence = clean(re.split(r"<br\s*/?>", before, flags=re.I)[-1]) or ""
            fav = re.search(r"(\d+)\s+votos?\s+en\s+pro", sentence)
            con = re.search(r"(\d+)\s+en\s+contra", sentence)
            abst = re.search(r"(\d+)\s+abstenci", sentence)
            out[link.group(1)] = {"date": date or iso_date(sentence), "title": title,
                                  "favor": int(fav.group(1)) if fav else None,
                                  "contra": (int(con.group(1)) if con else 0) if fav else None,
                                  "abstencion": (int(abst.group(1)) if abst else 0) if fav else None}
    return out


def parse_tabla(page):
    """(favor, contra, abstencion) from a Gaceta vote table's Total column."""
    got = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S | re.I):
        label = re.search(r'<FONT COLOR="#000099">([^<]+)</font>', row, flags=re.I)
        first = re.search(r'<input[^>]*value="\s*(\d+)\s*"', row, flags=re.I)
        if label and first:
            got[fold(label.group(1)).strip().lower()] = int(first.group(1))
    if "favor" not in got:
        return None
    return got.get("favor"), got.get("contra", 0), got.get("abstencion", 0)


def gaceta_lists(index_page, folder, legislature=LEGISLATURE):
    """The per-period list pages a Gaceta index links, current legislature only.
    folder is 'Iniciativas' or 'Votaciones'."""
    pat = r'href="(/Gaceta/{0}/{1}/[^"]+\.html)"'.format(folder, legislature)
    seen, out = set(), []
    for href in re.findall(pat, index_page, flags=re.I):
        if href not in seen:
            seen.add(href)
            out.append(href)
    return out


def match_tabla(gaceta, est):
    """The one Gaceta table with this vote's date and counts, or None."""
    if not est.get("total") or not est.get("date"):
        return None
    fav, con, abst = est["total"][0], est["total"][1], est["total"][2]
    hits = [t for t, g in gaceta.items()
            if g["date"] == est["date"] and g["favor"] == fav and g["contra"] == con
            and g["abstencion"] == abst]
    return hits[0] if len(hits) == 1 else None


# --- classification ------------------------------------------------------------

def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def load_taxonomy(path=TAXONOMY_ES):
    """The Spanish taxonomy, or None until Christopher approves it."""
    return filt.load_taxonomy(path) if path and os.path.exists(path) else None


_FOLDED = {}


def folded_taxonomy(tax):
    """The same taxonomy with every term's accents stripped. SITL prints
    titles in capitals and often without accents ('INTERRUPCION LEGAL DEL
    EMBARAZO'), and the shared filter does not fold accents; matching the
    folded text against folded terms, beside the plain match, catches both
    spellings without touching src/filter.py."""
    if id(tax) not in _FOLDED:
        terms = {}
        for area, tiers in tax.terms.items():
            terms[area] = {}
            for tier, entries in tiers.items():
                out = []
                for t, _pattern, _cs, guards, vetoes in entries:
                    # Guards and vetoes stay as compiled: their source words
                    # are not kept by the loader, so an accented guard word
                    # must also be written unaccented in taxonomy-es.
                    pattern, cs = filt._compile_term(fold(t))
                    out.append((fold(t), pattern, cs, guards, vetoes))
                terms[area][tier] = out
        _FOLDED[id(tax)] = (tax, filt.Taxonomy(version=tax.version, terms=terms,
                                               exclusions=tax.exclusions))
    return _FOLDED[id(tax)][1]


def classify(tax, text, ini_key=None, watch_path=None):
    """FilterResult over the text, and over its accent-free copy against the
    accent-free terms, merged; plus watchlist-mx by key."""
    res = filt.FilterResult()
    if tax is not None:
        wl = empty_watchlist()
        plain = filt.filter_item(tax, wl, text or "", title=text or "")
        bare = filt.filter_item(folded_taxonomy(tax), wl, fold(text or ""),
                                title=fold(text or ""))
        res.issue_areas = sorted(set(plain.issue_areas or []) | set(bare.issue_areas or []))
        res.matched_terms = list(dict.fromkeys((plain.matched_terms or []) +
                                               (bare.matched_terms or [])))
        tiers = [t for t in (plain.tier, bare.tier) if t is not None]
        res.tier = min(tiers) if tiers else None
    if ini_key:
        mx_store.add_watch_areas(res, ini_key, watch_path)
    return res


# --- stores --------------------------------------------------------------------

def store_member(conn, legislature, m, today):
    key = "{0}/{1}".format(legislature, m["dipt"])
    conn.execute(
        "INSERT INTO mx_members (member_key, legislature, dipt, name, party, entidad, distrito, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET "
        "name=COALESCE(excluded.name, mx_members.name), "
        "party=COALESCE(excluded.party, mx_members.party), "
        "entidad=COALESCE(excluded.entidad, mx_members.entidad), "
        "distrito=COALESCE(excluded.distrito, mx_members.distrito), last_seen=excluded.last_seen",
        (key, legislature, m["dipt"], m.get("name"), m.get("party"), m.get("entidad"),
         m.get("distrito"), today, today))
    return key


def store_iniciativa(conn, i, res, today):
    if not i["provisional"] and i["gaceta_ref"]:
        # The provisional row this entry used to be, re-keyed in place.
        old = conn.execute("SELECT ini_key FROM mx_iniciativas WHERE provisional=1 AND "
                           "gaceta_ref=? AND legislature=?",
                           (i["gaceta_ref"], i["legislature"])).fetchall()
        if len(old) == 1 and not conn.execute("SELECT 1 FROM mx_iniciativas WHERE ini_key=?",
                                              (i["ini_key"],)).fetchone():
            conn.execute("UPDATE mx_iniciativas SET ini_key=?, number=?, provisional=0 "
                         "WHERE ini_key=?", (i["ini_key"], i["number"], old[0][0]))
    conn.execute(
        "INSERT INTO mx_iniciativas (ini_key, legislature, number, provisional, kind, title, "
        "presenter, origin, party, turno, status, status_lines, presented, period, gaceta_ref, "
        "vote_tables, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(ini_key) DO UPDATE SET "
        "title=excluded.title, presenter=excluded.presenter, origin=excluded.origin, "
        "party=excluded.party, turno=excluded.turno, status=excluded.status, "
        "status_lines=excluded.status_lines, presented=COALESCE(excluded.presented, "
        "mx_iniciativas.presented), period=excluded.period, gaceta_ref=excluded.gaceta_ref, "
        "vote_tables=excluded.vote_tables, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (i["ini_key"], i["legislature"], i["number"], i["provisional"], i["kind"], i["title"],
         i["presenter"], i["origin"], i["party"], i["turno"], i["status"],
         mx_store.dumps(i["status_lines"]), i["presented"], i["period"], i["gaceta_ref"],
         mx_store.dumps(i["vote_tables"]), mx_store.dumps(res.issue_areas),
         mx_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])), res.tier,
         today, today))


def division_areas(conn, own, ini_keys, votaciont, watch_path=None):
    """The vote's own areas, its iniciativas' areas and any watchlist entry
    that names this vote."""
    areas = set(own.issue_areas or [])
    for key in ini_keys or []:
        row = conn.execute("SELECT areas FROM mx_iniciativas WHERE ini_key=?", (key,)).fetchone()
        if row:
            areas |= set(json.loads(row[0] or "[]"))
    hit = mx_store.watched_votes(watch_path).get(votaciont)
    if hit:
        areas |= set(hit[1])
    return sorted(areas)


def ini_keys_for(conn, tabla):
    if not tabla:
        return []
    return [k for (k,) in conn.execute(
        "SELECT ini_key FROM mx_iniciativas WHERE vote_tables LIKE ? ORDER BY ini_key",
        ('%"' + tabla + '"%',))]


# --- pulls ---------------------------------------------------------------------

def pull_members(conn, client, today, legislature=LEGISLATURE):
    page = decode(client.get_bytes(leg_path(legislature) + "listado_diputados_gpnp.php?tipot=TOTAL",
                                   FEED, "sitl-{0}-diputados".format(legislature)))
    rows = parse_members(page)
    for m in rows:
        store_member(conn, legislature, m, today)
    conn.commit()
    return len(rows)


def pull_iniciativas(conn, client, today, legislature=LEGISLATURE, tax=None, log=print,
                     watch_path=None):
    """Every Gaceta iniciativas list of the legislature, re-read whole each
    run: an old entry gains its dictamen, vote and publication lines in place.
    Returns (read, ours, gaps)."""
    read = ours = gaps = 0
    try:
        index = decode(client.get_bytes(GACETA + "/gp_iniciativas.html", FEED, "gaceta-iniciativas"))
    except FetchError as exc:
        _gap(conn, today, "gaceta iniciativas index: {0}".format(exc.cause))
        log("  [gap] gaceta iniciativas index: {0}".format(str(exc.cause)[:80]))
        return 0, 0, 1
    for href in gaceta_lists(index, "Iniciativas", legislature):
        period = re.sub(r"^gp\d+_|\.html$", "", href.rsplit("/", 1)[-1])
        try:
            page = decode(client.get_bytes(GACETA + href, FEED,
                                           "gaceta-inis-{0}-{1}".format(legislature, period)))
        except FetchError as exc:
            _gap(conn, today, "gaceta {0}: {1}".format(href, exc.cause))
            log("  [gap] {0}: {1}".format(href, str(exc.cause)[:80]))
            gaps += 1
            continue
        n = 0
        for i in parse_iniciativas(page, legislature, period):
            res = classify(tax, i["title"], i["ini_key"], watch_path)
            store_iniciativa(conn, i, res, today)
            ours += on_our_ground(res.issue_areas)
            n += 1
        conn.commit()
        read += n
        log("  iniciativas {0}: {1}".format(period, n))
    return read, ours, gaps


def pull_gaceta_votes(conn, client, today, legislature=LEGISLATURE, log=print):
    """{tabla: facts} from every Gaceta list of votes of the legislature."""
    out = {}
    try:
        index = decode(client.get_bytes(GACETA + "/gp_votaciones.html", FEED, "gaceta-votaciones"))
    except FetchError as exc:
        _gap(conn, today, "gaceta votaciones index: {0}".format(exc.cause))
        log("  [gap] gaceta votaciones index: {0}".format(str(exc.cause)[:80]))
        return out
    for href in gaceta_lists(index, "Votaciones", legislature):
        name = href.rsplit("/", 1)[-1].replace(".html", "")
        try:
            out.update(parse_gaceta_votes(decode(client.get_bytes(
                GACETA + href, FEED, "gaceta-{0}".format(name)))))
        except FetchError as exc:
            _gap(conn, today, "gaceta {0}: {1}".format(href, exc.cause))
            log("  [gap] {0}: {1}".format(href, str(exc.cause)[:80]))
    # Counts the list does not print (votes in particular) come from the
    # table itself, fetched once: a table already matched to a vote is done.
    matched = {t for (t,) in conn.execute(
        "SELECT gaceta_tabla FROM mx_divisions WHERE gaceta_tabla IS NOT NULL")}
    for tabla, facts in sorted(out.items()):
        if facts["favor"] is not None or tabla in matched:
            continue
        try:
            counts = parse_tabla(decode(client.get_bytes(
                GACETA + tabla, FEED, "gaceta-" + tabla.rsplit("/", 1)[-1])))
        except FetchError as exc:
            log("  [gap] {0}: {1}".format(tabla, str(exc.cause)[:80]))
            continue
        if counts:
            facts["favor"], facts["contra"], facts["abstencion"] = counts
    return out


def pull_votes(conn, client, today, legislature=LEGISLATURE, tax=None, gaceta=None,
               log=print, budget=None, limit=None, watch_path=None):
    """Index every period's votes, then read totals and positions for each
    vote that has none yet, oldest first. A vote whose lists fail keeps
    positions NULL and is retried next run. Returns (new, read, ours, gaps)."""
    base, sfx = leg_path(legislature), suffix(legislature)
    gaps = new = read = ours = 0
    try:
        periods = parse_periods(decode(client.get_bytes(
            base + "votaciones_por_periodo{0}.php".format(sfx), FEED,
            "sitl-{0}-periodos".format(legislature))))
    except FetchError as exc:
        _gap(conn, today, "sitl periods: {0}".format(exc.cause))
        log("  [gap] sitl periods: {0}".format(str(exc.cause)[:80]))
        return 0, 0, 0, 1
    for pert, label in periods:
        try:
            plabel, votes = parse_period_votes(decode(client.get_bytes(
                base + "votacionesxperiodo{0}.php?pert={1}".format(sfx, pert), FEED,
                "sitl-{0}-pert-{1}".format(legislature, pert))))
        except FetchError as exc:
            _gap(conn, today, "sitl pert {0}: {1}".format(pert, exc.cause))
            log("  [gap] sitl pert {0}: {1}".format(pert, str(exc.cause)[:80]))
            gaps += 1
            continue
        for vt, date, title in votes:
            key = "dip-{0}-{1}".format(legislature, vt)
            cur = conn.execute("INSERT OR IGNORE INTO mx_divisions (division_key, chamber, "
                               "legislature, votaciont, pert, period, date, title, first_seen, "
                               "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (key, "diputados", legislature, vt, pert, plabel or label, date,
                                title, today, today))
            new += cur.rowcount
            conn.execute("UPDATE mx_divisions SET last_seen=? WHERE division_key=?", (today, key))
        conn.commit()
    todo = conn.execute("SELECT division_key, votaciont, title FROM mx_divisions WHERE "
                        "legislature=? AND positions IS NULL ORDER BY votaciont",
                        (legislature,)).fetchall()
    for key, vt, title in todo:
        if limit is not None and read >= limit:
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("votes", read))
            break
        try:
            est = parse_estadistico(decode(client.get_bytes(
                base + "estadistico_votacion{0}.php?votaciont={1}".format(sfx, vt), FEED,
                "sitl-{0}-est-{1}".format(legislature, vt))))
            positions = []
            for partidot, group in est["lists"]:
                rows = parse_listado(decode(client.get_bytes(
                    base + "listados_votaciones{0}.php?partidot={1}&votaciont={2}".format(
                        sfx, partidot, vt), FEED,
                    "sitl-{0}-list-{1}-{2}".format(legislature, vt, partidot))))
                positions += [(dipt, name, pos, group) for dipt, name, pos in rows]
        except FetchError as exc:
            _gap(conn, today, "sitl vote {0}: {1}".format(vt, exc.cause))
            log("  [gap] sitl vote {0}: {1}".format(vt, str(exc.cause)[:80]))
            gaps += 1
            continue
        expected = est["total"][5] if est.get("total") else None
        if expected is not None and len(positions) != expected:
            _gap(conn, today, "sitl vote {0}: {1} position(s) listed, totals say {2}".format(
                vt, len(positions), expected))
            log("  [gap] sitl vote {0}: {1} positions, totals say {2}".format(
                vt, len(positions), expected))
            gaps += 1
            continue
        for dipt, name, pos, group in positions:
            mkey = store_member(conn, legislature, {"dipt": dipt, "name": name}, today)
            conn.execute("INSERT OR REPLACE INTO mx_votes (division_key, member_key, position, "
                         "party) VALUES (?,?,?,?)", (key, mkey, pos, group))
        tabla = match_tabla(gaceta or {}, est)
        ini = ini_keys_for(conn, tabla)
        own = classify(tax, est["title"] or title)
        areas = division_areas(conn, own, ini, vt, watch_path)
        t = est.get("total") or [None] * 6
        conn.execute("UPDATE mx_divisions SET title=COALESCE(?, title), date=COALESCE(?, date), "
                     "favor=?, contra=?, abstencion=?, solo_asistencia=?, ausente=?, total=?, "
                     "groups=?, gaceta_tabla=?, ini_keys=?, positions=?, own_areas=?, areas=?, "
                     "matched_terms=?, tier=?, last_seen=? WHERE division_key=?",
                     (est["title"], est["date"], t[0], t[1], t[2], t[3], t[4], t[5],
                      json.dumps(est["groups"], ensure_ascii=False), tabla, mx_store.dumps(ini),
                      len(positions), mx_store.dumps(own.issue_areas), mx_store.dumps(areas),
                      mx_store.dumps(own.matched_terms), own.tier, today, key))
        conn.commit()
        read += 1
        ours += on_our_ground(areas)
    return new, read, ours, gaps


def relink(conn, gaceta, legislature=LEGISLATURE):
    """Re-match stored votes to Gaceta tables (a table published after its
    vote was first read). Returns how many votes gained a table."""
    gained = 0
    for key, total, date in conn.execute(
            "SELECT division_key, json_array(favor, contra, abstencion), date FROM mx_divisions "
            "WHERE legislature=? AND gaceta_tabla IS NULL AND positions IS NOT NULL",
            (legislature,)).fetchall():
        f, c, a = json.loads(total)
        tabla = match_tabla(gaceta, {"total": [f, c, a, 0, 0, 0], "date": date})
        if tabla:
            conn.execute("UPDATE mx_divisions SET gaceta_tabla=? WHERE division_key=?", (tabla, key))
            gained += 1
    conn.commit()
    return gained


# --- offline -------------------------------------------------------------------

def reclassify(conn, tax=None, log=print, watch_path=None):
    """Re-derive iniciativa areas, then vote areas, offline (after taxonomy-es
    lands or watchlist-mx changes). Iniciativas first: votes inherit."""
    changed_i = changed_d = 0
    for key, title, areas in conn.execute(
            "SELECT ini_key, title, areas FROM mx_iniciativas").fetchall():
        res = classify(tax, title, key, watch_path)
        new = mx_store.dumps(res.issue_areas)
        changed_i += new != (areas or "[]")
        conn.execute("UPDATE mx_iniciativas SET areas=?, matched_terms=?, tier=? WHERE ini_key=?",
                     (new, mx_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for key, vt, title, tabla, areas in conn.execute(
            "SELECT division_key, votaciont, title, gaceta_tabla, areas FROM mx_divisions "
            "WHERE positions IS NOT NULL").fetchall():
        ini = ini_keys_for(conn, tabla)
        own = classify(tax, title)
        combined = division_areas(conn, own, ini, vt, watch_path)
        new = mx_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE mx_divisions SET ini_keys=?, own_areas=?, areas=?, matched_terms=?, "
                     "tier=? WHERE division_key=?",
                     (mx_store.dumps(ini), mx_store.dumps(own.issue_areas), new,
                      mx_store.dumps(own.matched_terms), own.tier, key))
    conn.commit()
    log("mx-rollcalls: reclassified; {0} iniciativa(s) and {1} vote(s) changed area".format(
        changed_i, changed_d))
    return changed_i, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} iniciativa(s) ({1} provisional), {2} on our ground; {3} vote(s), "
        "{4} with positions, {5} linked to a Gaceta table, {6} on our ground; {7} deputy(ies), "
        "{8} position(s)".format(
            n("SELECT COUNT(*) FROM mx_iniciativas"),
            n("SELECT COUNT(*) FROM mx_iniciativas WHERE provisional=1"), ours("mx_iniciativas"),
            n("SELECT COUNT(*) FROM mx_divisions"),
            n("SELECT COUNT(*) FROM mx_divisions WHERE positions IS NOT NULL"),
            n("SELECT COUNT(*) FROM mx_divisions WHERE gaceta_tabla IS NOT NULL"),
            ours("mx_divisions"), n("SELECT COUNT(*) FROM mx_members"),
            n("SELECT COUNT(*) FROM mx_votes")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", type=int, default=LEGISLATURE, choices=sorted(ROMAN))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-iniciativas", action="store_true")
    ap.add_argument("--no-votes", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored iniciativas and votes, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="read positions for at most this many votes")
    ap.add_argument("--dry-run", action="store_true",
                    help="read the periods and the first vote's totals, store nothing")
    args = ap.parse_args(argv)
    client = make_client()
    today = datetime.date.today().isoformat()
    tax = load_taxonomy()
    if args.dry_run:
        base, sfx = leg_path(args.legislature), suffix(args.legislature)
        periods = parse_periods(decode(client.get_bytes(
            base + "votaciones_por_periodo{0}.php".format(sfx), FEED, "dry-periodos",
            archive=False)))
        _label, votes = parse_period_votes(decode(client.get_bytes(
            base + "votacionesxperiodo{0}.php?pert={1}".format(sfx, periods[0][0]), FEED,
            "dry-pert", archive=False)))
        est = parse_estadistico(decode(client.get_bytes(
            base + "estadistico_votacion{0}.php?votaciont={1}".format(sfx, votes[0][0]), FEED,
            "dry-est", archive=False)))
        print("mx-rollcalls: {0} period(s); first vote {1} on {2}: totals {3}, {4} group list(s)"
              .format(len(periods), votes[0][0], est["date"], est["total"], len(est["lists"])))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    if tax is None:
        print("mx-rollcalls: config/taxonomy-es.yaml not approved yet; areas come from "
              "watchlist-mx only")
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        try:
            print("mx-rollcalls: {0} sitting deputy(ies)".format(
                pull_members(conn, client, today, args.legislature)))
        except FetchError as exc:
            _gap(conn, today, "sitl members: {0}".format(exc.cause))
            print("  [gap] sitl members: {0}".format(str(exc.cause)[:80]))
            gaps += 1
    if not args.no_iniciativas:
        read, ours, g = pull_iniciativas(conn, client, today, args.legislature, tax)
        gaps += g
        print("mx-rollcalls: {0} iniciativa(s) read, {1} on our ground, {2} gap(s)".format(
            read, ours, g))
    if not args.no_votes:
        gaceta = pull_gaceta_votes(conn, client, today, args.legislature)
        new, read, ours, g = pull_votes(conn, client, today, args.legislature, tax, gaceta,
                                        budget=budget, limit=args.limit)
        gaps += g
        print("mx-rollcalls: {0} new vote(s) indexed, {1} read with positions, {2} on our "
              "ground, {3} gap(s); {4} Gaceta table(s) known, {5} older vote(s) newly linked"
              .format(new, read, ours, g, len(gaceta), relink(conn, gaceta, args.legislature)))
    conn.commit()
    summary(conn)
    conn.close()
    # 3: stored what it could and recorded gaps (jobs/mx-collect.sh publishes it).
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
