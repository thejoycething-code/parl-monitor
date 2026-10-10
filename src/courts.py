"""Constitutional courts for the new country editions (X8, approved 10 October
2026; docs/country-decisions-2026-10-10.md). Shared by tools/co_courts.py,
tools/ec_courts.py, tools/pe_courts.py and tools/pt_courts.py.

WHY. On our ground several of these courts move first and the chamber
follows: Colombia's Corte Constitucional decriminalised abortion to 24 weeks
(C-055 of 2022) and then exhorted Congress to legislate; Ecuador's widened
abortion for rape (34-19-IN/21) and opened civil marriage (11-18-CN/19);
Portugal's Tribunal Constitucional struck the euthanasia decree twice before
it became law. The parliamentary monitors watched only the chamber.

ONE TABLE PER COUNTRY, ONE SHAPE. `<cc>_rulings` (co, ec, pe, pt), created
by each country's store module (src/<cc>_store.py calls schema() below), so
the separation guarantee holds: only tools/<cc>_courts.py writes it. The
shape is shared so the Latam monitor and the Portuguese edition read all of
them one way:

    ruling_key   the court's own number, never a title: 'C-055/22',
                 'ec:92-22-IN/26', 'pe:<press-note slug>', '2023/5'
    court        the court's name, as it calls itself
    kind         'ruling'       a decision (judgment, acórdão, sentencia)
                 'exhortation'  a judgment's order to the legislature
                 'hearing'      a case heard or listed, not yet decided
                 'press'        a court press note that reports none of these
    case_no      the case number as printed ('34-19-IN', 'Proc. 1030/26')
    date         ISO date of the decision (or of the note, for press/hearing)
    title        the court's own words: headline, ruling's name, or the
                 exhortation's opening; verbatim, Spanish or Portuguese
    summary      the text that was CLASSIFIED (see below), first 4,000 chars
    decision     the operative words, short, verbatim, where the source has them
    url          the ruling or note
    areas, matched_terms, tier   from src/filter.py over title + summary,
                 with the country's taxonomy (taxonomy-es for co/ec/pe,
                 taxonomy-pt for pt)

WHAT IS CLASSIFIED: THE COURT'S SUMMARY, NOT THE JUDGMENT. A judgment cites
every precedent it leans on, so its full text drags in areas it does not
decide (the Canadian lesson, tools/ca_courts.py). Each tool classifies the
narrowest text that says what was decided: Colombia's exhortation order,
Ecuador's plain-language "Novedad jurisprudencial", Peru's press note,
Portugal's opening report and its dispositivo.

CONTEXT ONLY. A ruling never places a member and never enters a 5CA. No
verdict is drawn here; the edition prints the court's own words.

Read and write helpers only; no network here.
"""

from __future__ import annotations

import datetime
import html as htmllib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
SUMMARY_CHARS = 4000
KINDS = ("ruling", "exhortation", "hearing", "press")
# Kinds an edition shows. A press note that reports no decision or hearing
# (a magistrate's lecture, a book fair) is stored for the record and never
# shown, whatever its words match.
SHOWN = ("ruling", "exhortation", "hearing")
# How long after a decision a late-published ruling still counts as news:
# Colombia's exhortations file and Portugal's site list rulings weeks after
# the date they carry.
LATE_DAYS = 120


def schema(cc):
    """The CREATE statements for `<cc>_rulings`, for a store's SCHEMA."""
    t = "{0}_rulings".format(cc)
    return (
        """CREATE TABLE IF NOT EXISTS {0} (
            ruling_key    TEXT PRIMARY KEY,
            court         TEXT NOT NULL,
            kind          TEXT NOT NULL,      -- ruling / exhortation / hearing / press
            case_no       TEXT,
            date          TEXT,               -- ISO date of the decision or note
            title         TEXT,               -- the court's own words, verbatim
            summary       TEXT,               -- the text classified, first 4,000 characters
            decision      TEXT,               -- the operative words, short, verbatim
            formation     TEXT,               -- Plenário, Sala, Secção, as printed
            url           TEXT,
            source        TEXT,               -- which feed wrote the row
            areas         TEXT,               -- JSON list
            matched_terms TEXT,               -- JSON list
            tier          INTEGER,
            first_seen    TEXT,
            last_seen     TEXT
        )""".format(t),
        "CREATE INDEX IF NOT EXISTS {0}_date ON {0} (date)".format(t),
    )


def table(cc):
    return "{0}_rulings".format(cc)


# --- text helpers ------------------------------------------------------------------

def flat(fragment):
    """HTML (or a WordPress Divi body) to one line of plain text."""
    text = re.sub(r"\[/?et_pb[^\]]*\]", " ", fragment or "")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmllib.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clip(text, n=SUMMARY_CHARS):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rstrip()


# --- classification -----------------------------------------------------------------

def load_taxonomy(cc, path=None):
    """The country's taxonomy: taxonomy-pt for Portugal, taxonomy-es for the
    rest, with the country's own [only:] terms kept. None when the file is
    missing (the row is stored unclassified, never dropped)."""
    from src import filter as filt
    path = path or os.path.join(CONFIG, "taxonomy-pt.yaml" if cc == "pt" else "taxonomy-es.yaml")
    if not os.path.exists(path):
        return None
    return filt.load_taxonomy(path, country=cc)


def empty_watchlist():
    from src import filter as filt
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


# Court prose uses some of our terms in a legal sense. Measured on Ecuador's
# 555 summaries of 2024-2026 (10 October 2026): "causales" (meant for the
# abortion "causales") matched fourteen rulings on grounds for annulling an
# arbitral award, for a cassation appeal or for dismissal, and none on
# abortion. That guard lived here as a court-side mask until the taxonomy
# carried it: since taxonomy-es v0.2 (10 October 2026) "causales" needs
# abortion, pregnancy, gestation or unborn company in the term list itself,
# for every Spanish-language collector, so no court-side mask is needed.


def classify(tax, title, *texts):
    """(areas, matched_terms, tier) for a ruling: the taxonomy over its title
    and the classified text. Accents fold in src/filter.py (X3)."""
    if tax is None:
        return [], [], None
    from src import filter as filt
    fields = [title or ""] + [t for t in texts if t]
    res = filt.filter_item(tax, empty_watchlist(), *fields)
    return sorted(set(res.issue_areas or [])), list(res.matched_terms or []), res.tier


# --- store -----------------------------------------------------------------------------

def upsert(conn, cc, row, tax, today):
    """Insert or refresh one ruling. Returns (new, areas). `row` carries the
    table's columns (ruling_key, court, kind, case_no, date, title, summary,
    decision, formation, url, source); classification happens here."""
    areas, terms, tier = classify(tax, row.get("title"), row.get("summary"), row.get("decision"))
    t = table(cc)
    before = conn.execute("SELECT 1 FROM {0} WHERE ruling_key=?".format(t),
                          (row["ruling_key"],)).fetchone()
    conn.execute(
        "INSERT INTO {0} (ruling_key, court, kind, case_no, date, title, summary, decision, "
        "formation, url, source, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(ruling_key) DO UPDATE SET "
        "court=excluded.court, kind=excluded.kind, case_no=excluded.case_no, date=excluded.date, "
        "title=excluded.title, summary=COALESCE(excluded.summary, {0}.summary), "
        "decision=COALESCE(excluded.decision, {0}.decision), "
        "formation=COALESCE(excluded.formation, {0}.formation), url=excluded.url, "
        "source=excluded.source, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen".format(t),
        (row["ruling_key"], row["court"], row["kind"], row.get("case_no"), row.get("date"),
         row.get("title"), clip(row.get("summary")) or None, clip(row.get("decision"), 600) or None,
         row.get("formation"), row.get("url"), row.get("source"), json.dumps(areas),
         json.dumps(terms, ensure_ascii=False), tier, today, today))
    return (not before), areas


def reclassify(conn, cc, tax):
    """Re-derive every stored ruling's areas offline (after a taxonomy change)."""
    t = table(cc)
    n = 0
    for key, title, summary, decision in conn.execute(
            "SELECT ruling_key, title, summary, decision FROM {0}".format(t)).fetchall():
        areas, terms, tier = classify(tax, title, summary, decision)
        conn.execute("UPDATE {0} SET areas=?, matched_terms=?, tier=? WHERE ruling_key=?".format(t),
                     (json.dumps(areas), json.dumps(terms, ensure_ascii=False), tier, key))
        n += 1
    conn.commit()
    return n


def on_ground(areas_raw, hidden=(11,)):
    try:
        got = json.loads(areas_raw) if isinstance(areas_raw, str) else (areas_raw or [])
    except (TypeError, ValueError):
        return False
    return any(int(a) not in hidden for a in got if str(a).isdigit())


# --- reading, for the editions -------------------------------------------------------

def news_rows(conn, cc, since, until, late_days=LATE_DAYS):
    """Rulings on our ground that are news in the window (since exclusive,
    until inclusive): decided in it, or first seen in it when decided at most
    `late_days` before it (a ruling the court published late). The first run
    of a collector seeds years of rulings with first_seen = that day: rows
    first seen on the table's first day count only by their own date, so
    switching a court on never floods an edition or the alerts. Shown kinds
    only."""
    import sqlite3
    conn.row_factory = sqlite3.Row
    try:
        floor = (datetime.date.fromisoformat(since) - datetime.timedelta(days=late_days)).isoformat()
    except ValueError:
        floor = since
    try:
        seed = conn.execute("SELECT MIN(substr(first_seen,1,10)) FROM {0}".format(
            table(cc))).fetchone()[0] or ""
        got = conn.execute(
            "SELECT * FROM {0} WHERE kind IN ({1}) AND ("
            "(substr(date,1,10) > ? AND substr(date,1,10) <= ?) OR "
            "(substr(first_seen,1,10) > ? AND substr(first_seen,1,10) <= ? "
            " AND substr(first_seen,1,10) != ? AND substr(date,1,10) > ?)) "
            "ORDER BY date DESC".format(table(cc), ",".join("?" * len(SHOWN))),
            SHOWN + (since, until, since, until, seed, floor)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [r for r in got if on_ground(r["areas"])]


KIND_WORDS = {"ruling": "Ruling", "exhortation": "Exhortation to the legislature",
              "hearing": "Hearing", "press": "Press note"}


def takeaway(r):
    """The English line under a ruling: what it is, where it came from."""
    bits = ["{0} of the {1}".format(KIND_WORDS.get(r["kind"], "Item"), r["court"])]
    if r["case_no"]:
        bits.append("case {0}".format(r["case_no"]))
    if r["formation"]:
        bits.append(r["formation"])
    return ", ".join(bits) + "."


def lines(r):
    """The decision in the court's words, where the source gives it."""
    out = []
    if r["decision"]:
        out.append("Decision as the court words it: \u201c{0}\u201d".format(
            clip(re.sub(r"\s+", " ", r["decision"]), 400)))
    return out
