"""Regional parliaments' forward business: one table, one collector, one
source module per country (16 October 2026, UK parity for the devolved
forward agendas: src/devolved_agenda.py, tools/sp_agenda.py, PR #204).

The monitor already collects regional parliaments' PAST business in about a
dozen countries. This is the forward half: plenary and committee agendas,
orders of the day, notice papers and session calendars, from today to as
far ahead as each parliament publishes (aim 2-8 weeks), in `regional_agenda`
(src/db.py has the column notes).

WHAT A COUNTRY SUPPLIES (src/regional_agendas/<cc>.py):

    CC = "de"
    TAXONOMIES = (("taxonomy-de.yaml", "de"),)   # config file, country code
    REGIONS = {                                  # every region, read or not
        "BY": region("Bayern", reader=read_by),
        "HB": region("Bremen", status="no-route",
                     note="agendas only as scanned PDFs"),
        ...
    }

A reader is `read(client, ctx) -> RegionRead`: ctx carries today, the
horizon (`ctx.until`) and `ctx.log`. It returns the items it read and the
UNITS it read in full (`window(start, end)`, `meeting(id)`, `day(date)`):
rows of a unit read in full that this run did not see are removed (a
placeholder replaced by named business, a moved item, a cancelled
meeting). A reader raises FetchError (or anything else) when the region
cannot be read: the region's stored rows are kept and a gap is recorded.
A region whose route is refused by robots.txt or has no permitted route at
all is declared `status="blocked"` / `"no-route"` with a note, so the
coverage lines say so every run.

Items are built with `item()`. A booked sitting with no subject yet (a
calendar date, an empty order of the day) is `item(..., business="")`: it is
stored once per sitting as item_type 'to be announced', never presented as
business.

CLASSIFICATION. The business text (and detail) is matched with the
country's taxonomy, or the region's language (`region(..., langs=...)`:
Swiss French and Italian cantons, Quebec, Wallonia, Catalonia ...).

ONE WRITER AT A TIME on data/parl-monitor.db: run as a step of the
country's own weekly job, after its regional collector.
"""

from __future__ import annotations

import collections
import datetime
import importlib
import json
import os
import re
import time as _time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")

DEFAULT_DAYS = 56
TABLE = "regional_agenda"
RUNS = "regional_agenda_runs"
TBA = "to be announced"

COUNTRIES = ("de", "at", "ch", "be", "ca", "au", "us", "es", "it", "br", "mx",
             "pe", "pl", "ar")


# --- what a source module declares ------------------------------------------

Region = collections.namedtuple("Region", "name reader status note langs")


def region(name, reader=None, status=None, note="", langs=None):
    """One regional parliament. `status` is None for a region with a
    reader, else 'no-route' (nothing published in a permitted, readable
    form) or 'blocked' (robots.txt or a bot wall refuses the route)."""
    if reader is None and status is None:
        status = "no-route"
    return Region(name, reader, status, note, tuple(langs) if langs else None)


class RegionRead:
    """What a reader returns: the items, the units read in full, the
    route's name, an optional note and any partial gaps (a committee page
    that failed while the plenary read): those are recorded but the region
    still counts as read."""

    def __init__(self, items=(), units=(), source="", note="", gaps=()):
        self.items = list(items)
        self.units = list(units)
        self.source = source
        self.note = note
        self.gaps = list(gaps)


def window(start, end):
    """Every row of the region dated start..end (inclusive) is this run's."""
    return ("window", str(start), str(end))


def meeting(meeting_id):
    return ("meeting", str(meeting_id))


def day(dated, body=None):
    return ("day", str(dated), body)


class Ctx:
    def __init__(self, today, until, log=print, budget_end=None):
        self.today = today            # ISO date
        self.until = until            # ISO date: the horizon asked for
        self.log = log
        self.budget_end = budget_end

    @property
    def today_date(self):
        return datetime.date.fromisoformat(self.today)

    @property
    def until_date(self):
        return datetime.date.fromisoformat(self.until)

    def in_window(self, dated):
        return bool(dated) and self.today <= dated <= self.until

    def out_of_time(self):
        return self.budget_end is not None and _time.monotonic() > self.budget_end


def item(dated, business, body="Plenary", item_time=None, order=None, meeting_id=None,
         detail=None, reference=None, url=None, item_type=None, lang=None, key=None):
    """One forward agenda item as a reader returns it."""
    return {"dated": (dated or "")[:10], "business": one_line(business),
            "body": one_line(body) or "Plenary", "item_time": one_line(item_time) or None,
            "item_order": order, "meeting_id": (str(meeting_id) if meeting_id not in (None, "")
                                                else None),
            "detail": (" ".join(str(detail).split())[:4000] if detail else None),
            "reference": one_line(reference) or None, "url": url or None,
            "item_type": item_type, "lang": lang, "key": key}


def one_line(text):
    return " ".join(str(text or "").replace("\xa0", " ").split())


def slug(text, limit=60):
    s = re.sub(r"[^a-z0-9]+", "-", _fold(text or "").lower()).strip("-")
    return s[:limit].rstrip("-") or "item"


def _fold(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))


# --- item types (multilingual, coarse) ----------------------------------------

_TYPES = (
    ("procedural", re.compile(
        r"^(?:er[öo]ffnung|begr[üu]ßung|mitteilungen|genehmigung (?:des|der) (?:protokoll|niederschrift)|"
        r"feststellung der beschlussf|aprobaci[óo]n(?:,? si procede,?)? del acta|lectura y aprobaci|"
        r"approbation du proc[èe]s|approvazione (?:del )?verbal|comunicazioni del presidente|"
        r"leitura e aprova|aprova[çc][ãa]o da ata|goedkeuring van de (?:agenda|notulen)|"
        r"prayers?$|routine (?:proceedings|business)|introduction of (?:visitors|guests)|"
        r"pledge of allegiance|roll call|call to order|adjournment|apologies|"
        r"approval of (?:the )?(?:minutes|agenda)|declarations? of interest|"
        r"orden del d[íi]a$|ordine del giorno$|tagesordnung$|"
        r"pase de lista|declaratoria de qu[óo]rum|lectura del orden del d[íi]a)", re.I)),
    ("questions", re.compile(
        r"\bfragestunde\b|\baktuelle stunde\b|\banfragen?\b|\bkleine anfrage|\bgro(?:ß|ss)e anfrage|"
        r"\binterpellation|\bquestions?\b(?! of privilege)|question period|question time|"
        r"\bpreguntas?\b|\binterpelaci[óo]n|\binterrogazion|\binterpellanz|"
        r"\bquestion(?:s)? (?:orales?|d'actualit[ée])|\bvragen?\b|\binterpellatie|"
        r"\bquestion(?:es)? de urgencia|\bperguntas?\b|\bfragen\b", re.I)),
    ("petition", re.compile(
        r"\bpetition|\bpetici[óo]n|\bp[ée]tition|\bpetizion|\bverzoekschrift|"
        r"\bpeti[çc][ãa]o|\beingaben\b", re.I)),
    # Before bill stage: a Spanish "proposición no de ley" says "ley".
    ("motion", re.compile(r"proposici[óo]n no de ley|\bpunto de acuerdo|\bmoci[óo]n\b", re.I)),
    ("bill stage", re.compile(
        r"gesetz|lesung\b|\bgesetzentwurf|\bverordnung\b|\bstaatsvertrag|"
        r"\bproyecto de (?:ley|decreto)|\bproposici[óo]n de ley|\biniciativa (?:de|con proyecto de) (?:ley|decreto)|"
        r"\bdictamen|\bley\b|\breforma(?:s)? (?:a|al|del?) (?:la|el|los|art)|"
        r"\bprojet de (?:loi|d[ée]cret|r[èe]glement)|\bproposition de (?:loi|d[ée]cret)|\bd[ée]cret\b|"
        r"\bprogetto di legge|\bproposta di legge|\bdisegno di legge|\bp\.?d\.?l\.?\b|"
        r"\bprojeto de (?:lei|decreto|resolu)|\bproposta de emenda|\bPL\s*\d|\bPEC\b|"
        r"\bontwerp van (?:decreet|ordonnantie)|\bvoorstel van (?:decreet|ordonnantie)|"
        r"\bbill\b|\b(?:first|second|third) reading|\breport stage|\bcommittee of the whole|"
        r"\b(?:H|S|A|SB|HB|AB|LB|SF|HF)\s?\d{1,5}\b|\bact\b", re.I)),
    ("motion", re.compile(
        r"\bantrag\b|\bantr[äa]ge\b|\bentschlie(?:ß|ss)ung|\bmotion\b|\bmotions\b|"
        r"\bmoci[óo]n|\bproposici[óo]n no de ley|\bpunto de acuerdo|\bmozion|\brisoluzion|"
        r"\bordine del giorno n|\br[ée]solution|\bmotie\b|\bresolutie|\bindica[çc][ãa]o|"
        r"\brequerimento|\bmo[çc][ãa]o|\bresolution\b|\bmemorial\b|\bpostulat|\bvorsto(?:ß|ss)", re.I)),
    ("statement", re.compile(
        r"regierungserkl[äa]rung|ministerial statement|statement by|d[ée]claration (?:du|de la) gouvernement|"
        r"comparecencia|informaci[óo]n del (?:presidente|gobierno|consejo)|comunicazion|"
        r"members'? statements|statements by members", re.I)),
    ("committee evidence", re.compile(
        r"\banh[öo]rung|\bhearing\b|\baudiencia|\baudici[óo]n|\baudition|\baudizion|"
        r"\baudi[êe]ncia p[úu]blica|\bhoorzitting|\bevidence\b|\bpublic testimony", re.I)),
    ("debate", re.compile(r"\bdebat|\bdebate\b|\bdibattit|\baussprache\b|\bdebatte\b", re.I)),
)


def item_type(business, committee=False):
    """A coarse kind for one item, read off its own words in any of the
    monitor's languages. 'to be announced' is set by the store for a
    booked sitting with no subject, never here."""
    text = one_line(business)
    if not text:
        return TBA
    for kind, pattern in _TYPES:
        if pattern.search(text):
            return kind
    return "committee business" if committee else "chamber business"


_PLENARY = re.compile(
    r"^(?:plen|chamber|house|senate|assembly|legislative|landtag|grand conseil|gran consiglio|"
    r"kantonsrat|grosser rat|gro(?:ß|ss)er rat|landrat|parlament|pleno|plenário|plenario|"
    r"sesi[óo]n|sess[ãa]o|seduta|assembl|consiglio|conseil|council|congreso|congress|"
    r"general assembly|gemeinderat|vlaams parlement$|parlement de wallonie$|house of)", re.I)


def is_committee(body):
    b = one_line(body)
    return bool(b) and not _PLENARY.match(b)


# --- classification ------------------------------------------------------------

_TAX = {}


def taxonomy(name, code):
    from src import filter as filt
    k = (name, code)
    if k not in _TAX:
        path = os.path.join(CONFIG, name)
        _TAX[k] = filt.load_taxonomy(path, country=code) if os.path.exists(path) else None
    return _TAX[k]


def classify(taxes, business, detail):
    """(areas, matched_terms) over every taxonomy given (a bilingual region
    is read in both languages)."""
    from src import filter as filt
    empty = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])
    areas, terms = set(), []
    for tax in taxes:
        if tax is None:
            continue
        res = filt.filter_item(tax, empty, business or "", detail or "", title=business or "")
        areas.update(res.issue_areas or [])
        terms += [t for t in (res.matched_terms or []) if t not in terms]
    return sorted(areas), terms


def taxes_for(mod, reg, lang=None):
    """The taxonomies for one item: the item's own `lang` (a taxonomy file
    name) first, else the region's, else the country's."""
    country_code = mod.TAXONOMIES[0][1] if mod.TAXONOMIES else None
    if lang:
        return [taxonomy(lang, country_code)], lang
    pairs = []
    for l in (reg.langs or ()):
        pairs.append((l, country_code) if isinstance(l, str) else tuple(l))
    if not pairs:
        pairs = list(mod.TAXONOMIES)
    return [taxonomy(n, c) for n, c in pairs], "+".join(n for n, _ in pairs)


# --- the store ---------------------------------------------------------------

COLUMNS = ("key", "cc", "region", "region_name", "body", "dated", "item_time",
           "item_order", "meeting_id", "business", "detail", "item_type", "reference",
           "url", "source", "lang", "areas", "matched_terms")


def rows_for(mod, code, reg, read):
    """Store rows for one region's items: keys made, types set, classified."""
    out, seen = [], {}
    for it in read.items:
        if not it.get("dated"):
            continue
        body = it["body"]
        unit = it.get("meeting_id") or "{0}:{1}".format(it["dated"], slug(body, 40))
        tba = not it["business"]
        business = it["business"] or "Sitting booked; agenda to be announced"
        # The business slug, not the order: a re-read that renumbers the
        # order of the day keeps each item's first_seen.
        ikey = it.get("key") or ("tba" if tba else slug(business))
        key = "{0}:{1}:{2}:{3}".format(mod.CC, code, unit, ikey)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = "{0}#{1}".format(key, seen[key])
        if tba:
            areas, terms, lang = [], [], None
            kind = TBA
        else:
            taxes, lang = taxes_for(mod, reg, it.get("lang"))
            areas, terms = classify(taxes, business, it.get("detail"))
            kind = it.get("item_type") or item_type(business, is_committee(body))
        out.append(dict(it, key=key, cc=mod.CC, region=code, region_name=reg.name,
                        business=business, item_type=kind, source=read.source or None,
                        lang=lang, areas=areas, matched_terms=terms))
    return out


def upsert(conn, row, today):
    existing = conn.execute("SELECT first_seen FROM regional_agenda WHERE key = ?",
                            (row["key"],)).fetchone()
    values = [row.get(c) for c in COLUMNS]
    values[COLUMNS.index("areas")] = json.dumps(row.get("areas") or [], ensure_ascii=False)
    values[COLUMNS.index("matched_terms")] = json.dumps(row.get("matched_terms") or [],
                                                        ensure_ascii=False)
    conn.execute(
        "INSERT OR REPLACE INTO regional_agenda ({0}, first_seen, last_seen) VALUES ({1})".format(
            ", ".join(COLUMNS), ", ".join("?" * (len(COLUMNS) + 2))),
        values + [existing[0] if existing else today, today])
    return existing is None


def prune(conn, cc, code, units, keys):
    """Remove rows of the units read in full that this run did not see."""
    keys = list(keys)
    gone = 0
    for unit in units:
        if unit[0] == "window":
            where, params = "dated >= ? AND dated <= ?", [unit[1], unit[2]]
        elif unit[0] == "meeting":
            where, params = "meeting_id = ?", [unit[1]]
        elif unit[0] == "day":
            where, params = "dated = ?", [unit[1]]
            if unit[2]:
                where += " AND body = ?"
                params.append(unit[2])
        else:
            raise ValueError("unknown unit {0!r}".format(unit))
        sql = "DELETE FROM regional_agenda WHERE cc = ? AND region = ? AND {0}".format(where)
        if keys:
            sql += " AND key NOT IN ({0})".format(",".join("?" * len(keys)))
        cur = conn.execute(sql, [cc, code] + params + keys)
        gone += cur.rowcount or 0
    return gone


def record_run(conn, cc, code, today, status, items=0, on_ground=0, horizon=None, note=""):
    conn.execute(
        "INSERT OR REPLACE INTO regional_agenda_runs (cc, region, run_date, status, items, "
        "on_ground, horizon, note) VALUES (?,?,?,?,?,?,?,?)",
        (cc, code, today, status, items, on_ground, horizon, (note or "")[:500]))


def module(cc):
    return importlib.import_module("src.regional_agendas.{0}".format(cc))


def feed(cc):
    return "{0}-regional-agenda".format(cc)


def collect(conn, cc, client, today, days=DEFAULT_DAYS, regions=None, log=print,
            mod=None, budget_seconds=None):
    """Read one country's regional forward agendas into regional_agenda.
    Returns a summary dict; every region gets a regional_agenda_runs row and
    every failure a [gap] line and a gaps row."""
    from src import db
    mod = mod or module(cc)
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    budget_end = _time.monotonic() + budget_seconds if budget_seconds else None
    ctx = Ctx(today, until, log=log, budget_end=budget_end)
    summary = {"read": [], "gap": [], "no-route": [], "blocked": [], "rows": 0, "new": 0,
               "ours": 0, "tba": 0, "pruned": 0, "per_region": {}}

    def gap(code, detail):
        line = "{0} {1}: {2}".format(cc.upper(), code, detail)
        db.record_gap(conn, feed(cc), line)

    wanted = [r for r in (regions or mod.REGIONS) if r in mod.REGIONS]
    for code in wanted:
        reg = mod.REGIONS[code]
        if reg.reader is None:
            status = reg.status or "no-route"
            summary[status].append(code)
            record_run(conn, cc, code, today, status, note=reg.note)
            summary["per_region"][code] = {"status": status, "rows": 0, "ours": 0,
                                           "horizon": None, "note": reg.note}
            log("  [{0}] {1} {2} ({3}): {4}".format(status, cc.upper(), code, reg.name,
                                                   reg.note or "no route"))
            continue
        if ctx.out_of_time():
            gap(code, "not read: the step's time budget ran out")
            summary["gap"].append(code)
            record_run(conn, cc, code, today, "gap", note="time budget ran out")
            summary["per_region"][code] = {"status": "gap", "rows": 0, "ours": 0,
                                           "horizon": None, "note": "time budget"}
            continue
        try:
            read = reg.reader(client, ctx)
        except Exception as exc:                        # noqa: BLE001 - a gap, never fatal
            from src.http import RobotsRefused
            cause = getattr(exc, "cause", None) or exc
            status = "blocked" if isinstance(exc, RobotsRefused) else "gap"
            gap(code, "{0} ({1}) not read{2}: {3}".format(
                reg.name, status, "; stored rows kept", str(cause)[:240]))
            summary[status].append(code)
            record_run(conn, cc, code, today, status, note=str(cause)[:300])
            summary["per_region"][code] = {"status": status, "rows": 0, "ours": 0,
                                           "horizon": None, "note": str(cause)[:160]}
            continue
        for g in read.gaps:
            gap(code, g)
        rows = rows_for(mod, code, reg, read)
        new = ours = tba = 0
        for row in rows:
            new += upsert(conn, row, today)
            if row["areas"] or row["matched_terms"]:
                ours += 1
            if row["item_type"] == TBA:
                tba += 1
        pruned = prune(conn, cc, code, read.units, [r["key"] for r in rows])
        dates = [r["dated"] for r in rows]
        horizon = max(dates) if dates else None
        note = read.note or ""
        if not rows and not note:
            note = "read; nothing scheduled in the window"
        record_run(conn, cc, code, today, "read", len(rows), ours, horizon,
                   "; ".join(x for x in (read.source, note) if x))
        conn.commit()
        summary["read"].append(code)
        summary["rows"] += len(rows)
        summary["new"] += new
        summary["ours"] += ours
        summary["tba"] += tba
        summary["pruned"] += pruned
        summary["per_region"][code] = {"status": "read", "rows": len(rows), "ours": ours,
                                       "horizon": horizon, "note": note}
        for row in rows:
            if row["areas"] or row["matched_terms"]:
                log("  [agenda] {0} {1} {2} {3}: {4} {5}".format(
                    cc.upper(), code, row["dated"], row["body"][:40], row["business"][:90],
                    row["areas"]))
        log("  {0} {1} ({2}): {3} item(s) to {4}, {5} on our ground, {6} to be announced, "
            "{7} stale removed{8}".format(cc.upper(), code, reg.name, len(rows),
                                          horizon or "-", ours, tba, pruned,
                                          "; " + note if note else ""))
    conn.commit()
    return summary


def summary_line(cc, s):
    n = len(s["read"]) + len(s["gap"]) + len(s["no-route"]) + len(s["blocked"])
    return ("{0} regional agendas: {1} of {2} region(s) read ({3} item(s), {4} new, {5} on our "
            "ground, {6} to be announced, {7} stale removed); gaps: {8}; no route: {9}; "
            "blocked: {10}.".format(
                cc.upper(), len(s["read"]), n, s["rows"], s["new"], s["ours"], s["tba"],
                s["pruned"], ", ".join(s["gap"]) or "none",
                ", ".join(s["no-route"]) or "none", ", ".join(s["blocked"]) or "none"))


# --- shared parsing helpers ------------------------------------------------------

def clean(fragment):
    """Text of an HTML fragment: entities decoded, tags dropped, block tags
    as line breaks, spaces folded."""
    import html as _html
    text = _html.unescape(fragment or "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.I)
    text = re.sub(r"<(?:br|/p|/li|/div|/h\d|/tr|/td|/dt|/dd)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


MONTHS = {
    # en
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    # de
    "januar": 1, "jänner": 1, "jaenner": 1, "februar": 2, "feber": 2, "märz": 3, "maerz": 3,
    "mai": 5, "juni": 6, "juli": 7, "oktober": 10, "dezember": 12,
    # fr
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
    # it
    "gennaio": 1, "febbraio": 2, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
    "agosto": 8, "settembre": 9, "ottobre": 10, "dicembre": 12,
    # es
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    # pt
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "maio": 5, "junho": 6,
    "julho": 7, "setembro": 9, "outubro": 10, "dezembro": 12,
    # nl
    "januari": 1, "februari": 2, "maart": 3, "mei": 5, "augustus": 8,
}


def month(name):
    n = (name or "").strip(". ").lower()
    if n in MONTHS:
        return MONTHS[n]
    for k, v in MONTHS.items():
        if len(n) >= 3 and k.startswith(n):
            return v
    return None


def iso(dd, mm, yyyy):
    """ISO date from day, month (number or name) and year; None if invalid."""
    try:
        m = int(mm) if str(mm).isdigit() else month(str(mm))
        y = int(yyyy)
        if y < 100:
            y += 2000
        return datetime.date(y, int(m), int(dd)).isoformat()
    except (TypeError, ValueError):
        return None


_NUM_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_NAME_DATE = re.compile(r"\b(\d{1,2})\.?\s+(?:de\s+)?([A-Za-zÀ-ÿ]{3,10})\.?\s+(?:de\s+)?(\d{4})\b")
_EN_DATE = re.compile(r"\b([A-Z][a-z]{2,8})\.?\s+(\d{1,2}),?\s+(\d{4})\b")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def find_date(text, numeric_order="dmy"):
    """The first date in free text, in any of the forms the sources print
    (15.10.2026, 15/10/2026, 15 octobre 2026, 15 de octubre de 2026,
    October 15, 2026, 2026-10-15). numeric_order 'mdy' for US pages."""
    t = text or ""
    found = []
    for m in _ISO_DATE.finditer(t):
        found.append((m.start(), iso(m.group(3), m.group(2), m.group(1))))
    for m in _NUM_DATE.finditer(t):
        a, b, y = m.groups()
        d, mo = (b, a) if numeric_order == "mdy" else (a, b)
        found.append((m.start(), iso(d, mo, y)))
    for m in _NAME_DATE.finditer(t):
        if month(m.group(2)):
            found.append((m.start(), iso(m.group(1), m.group(2), m.group(3))))
    for m in _EN_DATE.finditer(t):
        if month(m.group(1)):
            found.append((m.start(), iso(m.group(2), m.group(1), m.group(3))))
    found = [f for f in found if f[1]]
    return min(found)[1] if found else None
