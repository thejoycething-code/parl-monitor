"""Government consultations and publications for the country editions: the
UK's GOV.UK layer (tools/govuk_docs.py) for every other country the monitor
covers (Chris, 16 October 2026: "UK parity for government consultations and
publications").

ONE TABLE, `gov_docs` (src/db.py), keyed (cc, doc_id), the source's short
code in the id ('bmj:referentenentwurf-xyz'). One reader per country in
src/gov_doc_sources/<cc>.py; tools/country_gov_docs.py runs it as a step of
the country's weekly job, after the petitions step and before the edition.
Each run is recorded per source in `gov_doc_runs`, so "nothing on our
ground" can be told from "never read" and from "read with gaps".

WHAT A COUNTRY SUPPLIES (src/gov_doc_sources/<cc>.py):

    CC = "de"
    TAXONOMIES = (("taxonomy-de.yaml", "de"),)   # only if the country has no
                                                 # edition adapter
    SOURCES = (Source(code="bmj", name="BMJ Referentenentwürfe", fetch=fn,
                      url="https://www.bmj.de/..."),)

`fetch(client, today, log)` reads the source through the guarded client
(robots.txt asked for every URL and every redirect hop, documented APIs
excepted: src/robots_guard.guard) and returns `fetched(entries, note, gaps)`;
an entry is built with `entry()`. Parsers are pure functions over the raw
reply so tests run on fixtures captured live (tests/fixtures/gov_docs/<cc>/).
A source may instead set `mirror=fn(conn, cc, today)` to re-file rows another
collector already stored this week (Austria's Begutachtung and Switzerland's
Vernehmlassungen from country_petitions, the US Federal Register's proposed
rules from us_fr_documents): no second fetch, one place for the countdown.

ON OUR GROUND. The country's own taxonomies (its edition adapter's list, or
the module's TAXONOMIES) over title + summary, through src/filter.filter_item,
the same pass as petitions (src/petitions.classify). Precision gate, as the
UK's: a document of a DEADLINE_TYPES type is kept on any match; anything else
needs tier 1 or a watchlist key, since tier-2 vocabulary ("Kinder", "école")
would otherwise admit much of an education ministry's output. Only rows on
our ground (or watched) are stored. Area 11 (migration) is never counted as
on our ground (src/latam.HIDDEN_AREAS), as everywhere: a row whose only area
is 11 is not stored; a row stored for another area keeps 11 in its areas.

DEADLINES. `deadline_rows()` is the contract with the country countdown: a
row of a DEADLINE_TYPES type, on our ground, whose closing_date falls in the
asked window. The renderer reads that; nothing here renders.

FAILING LOUD. A source that failed (or answered with nothing parsable) is a
[gap] line, a gaps row under feed '<cc>-govdocs-<source>' and an ok=0 run
row; the tool exits 3 (stored with gaps) or 1 (nothing stored). The weekly
job prints a [gap] line and carries on: gov docs never cost the store.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime
import html
import importlib
import json
import os
import re
import time
from typing import Callable, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUMMARY_CAP = 1000
SOURCE_SECONDS = 600         # no new page fetch once one source has run this long
WINDOW_DAYS = 92             # a reader lists what was published (or closes) in this window
DEADLINE_TYPES = ("consultation", "call_for_evidence", "regulation_draft", "bill_draft")
DOC_TYPES = DEADLINE_TYPES + ("regulation", "law", "publication", "guidance", "statistics",
                              "report", "press_release", "consultation_outcome")

Fetched = collections.namedtuple("Fetched", "entries note gaps")


@dataclasses.dataclass
class Source:
    code: str
    name: str
    fetch: Optional[Callable] = None
    url: str = ""
    mirror: Optional[Callable] = None     # fn(conn, cc, today) -> fetched(...)


def fetched(entries, note=None, gaps=()):
    return Fetched(list(entries), note, list(gaps))


_TAG = re.compile(r"<[^>]+>")


def text(fragment):
    """Plain text from an HTML fragment: tags out, entities decoded, spaces folded."""
    return one_line(html.unescape(_TAG.sub(" ", fragment or "")))


def one_line(value):
    return " ".join(str(value or "").replace("\xa0", " ").split())


def iso(value):
    """An ISO date from 'YYYY-MM-DD...', 'DD/MM/YYYY', 'DD.MM.YYYY'; else None."""
    s = str(value or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "{0}-{1}-{2}".format(*m.groups())
    m = re.match(r"(\d{1,2})[./-]\s?(\d{1,2})[./-]\s?(\d{4})", s)
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


MONTHS = {
    # en, de, fr, nl, it, es, pt, pl (genitive), hr, sk, hu: lowercase, unaccented
    # forms are added by month_number()
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "januar": 1, "jänner": 1, "februar": 2, "märz": 3, "mai": 5, "juni": 6, "juli": 7,
    "oktober": 10, "dezember": 12,
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "juin": 6, "juillet": 7, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "januari": 1, "februari": 2, "maart": 3, "mei": 5, "augustus": 8,
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "dicembre": 12,
    "enero": 1, "febrero": 2, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "janeiro": 1, "fevereiro": 2, "março": 3, "maio": 5, "junho": 6, "julho": 7,
    "setembro": 9, "outubro": 10, "dezembro": 12,
}


def month_number(word):
    w = (word or "").strip().lower().rstrip(".")
    if w in MONTHS:
        return MONTHS[w]
    import unicodedata
    folded = "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")
    for k, v in MONTHS.items():
        kf = "".join(c for c in unicodedata.normalize("NFD", k) if unicodedata.category(c) != "Mn")
        if kf == folded:
            return v
    return None


def long_date(value):
    """An ISO date from '4 November 2026', '4. November 2026', '4 de noviembre de 2026'."""
    m = re.search(r"(\d{1,2})\.?\s*(?:de\s+)?([^\W\d_]+)\.?\s+(?:de\s+)?(\d{4})", str(value or ""))
    if not m:
        return None
    n = month_number(m.group(2))
    if not n:
        return None
    try:
        return datetime.date(int(m.group(3)), n, int(m.group(1))).isoformat()
    except ValueError:
        return None


def entry(source, doc_id, title, doc_type, body=None, published=None, closing_date=None,
          url=None, summary=None, status=None, refs=(), classified=None):
    """One document, as a reader returns it. `classified` (a mirror's own
    collector already matched it, on more than title and summary): a tuple
    (areas, matched_terms, tier) kept as it is instead of re-matching."""
    if doc_type not in DOC_TYPES:
        raise ValueError("unknown doc_type {0!r}".format(doc_type))
    pre = {}
    if classified is not None:
        areas, terms, tier = classified
        pre = {"areas": sorted(int(a) for a in loads(areas) if str(a).isdigit()),
               "matched_terms": loads(terms), "tier": tier, "preclassified": True}
    return dict(pre, **{"source": source, "doc_id": "{0}:{1}".format(source, doc_id),
            "title": one_line(title), "doc_type": doc_type, "body": one_line(body) or None,
            "published": iso(published), "closing_date": iso(closing_date), "url": url,
            "summary": one_line(summary)[:SUMMARY_CAP] or None, "status": one_line(status) or None,
            "refs": [str(r) for r in refs or () if str(r).strip()]})


def dumps(values):
    return json.dumps(list(values or []), ensure_ascii=False)


def loads(raw):
    try:
        got = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        return []
    return list(got) if isinstance(got, list) else []


def module(cc):
    return importlib.import_module("src.gov_doc_sources.{0}".format(cc))


def countries():
    """The codes with a reader module."""
    here = os.path.join(ROOT, "src", "gov_doc_sources")
    return tuple(sorted(f[:-3] for f in os.listdir(here)
                        if f.endswith(".py") and not f.startswith("_")))


def window_start(today, days=WINDOW_DAYS):
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()


def in_window(e, today, days=WINDOW_DAYS):
    """Published in the window, or still open for comment."""
    start = window_start(today, days)
    if e.get("closing_date") and e["closing_date"] >= today:
        return True
    return (e.get("published") or "") >= start or (e.get("closing_date") or "") >= start


# --- classification ---------------------------------------------------------------

def taxonomies(cc, config_dir=None, mod=None):
    """The country's taxonomies: its edition adapter's, else the module's TAXONOMIES."""
    from src import agenda, petitions
    mod = mod or module(cc)
    if getattr(mod, "TAXONOMIES", None):
        country = collections.namedtuple("C", "taxonomies")(mod.TAXONOMIES)
        return agenda.taxonomies(country, config_dir)
    return petitions.taxonomies(cc, config_dir, mod)


def watchlist(cc, config_dir=None):
    from src import latam, petitions
    try:
        return petitions.watchlist(cc, config_dir)
    except Exception:                                   # noqa: BLE001
        return latam.watchlist(cc, config_dir)


def classify(e, taxes, wl):
    """The entry with areas, matched_terms, tier and watch_keys set (title + summary)."""
    from src import filter as filt
    empty = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])
    areas, terms, tiers = set(), [], set()
    for tax in (() if e.get("preclassified") else taxes):
        res = filt.filter_item(tax, empty, e["title"] or "", e.get("summary") or "",
                               title=e["title"] or "")
        if res.issue_areas:
            areas.update(res.issue_areas)
            terms += [t for t in res.matched_terms if t not in terms]
            if res.tier:
                tiers.add(res.tier)
    key = e["doc_id"].split(":", 1)[-1]
    watch = [k for k in [e["doc_id"], key] + list(e.get("refs") or []) if k in wl]
    if e.get("preclassified"):
        return dict(e, tier=e.get("tier") if e.get("areas") else (2 if watch else None),
                    watch_keys=watch)
    return dict(e, areas=sorted(int(a) for a in areas), matched_terms=terms,
                tier=min(tiers) if tiers and areas else (2 if watch else None),
                watch_keys=watch)


def on_ground(e):
    """Kept: on our ground (visible areas) under the precision gate, or watched."""
    from src import latam
    if e.get("watch_keys"):
        return True
    if not latam.areas_of(e.get("areas")):
        return False
    return e.get("doc_type") in DEADLINE_TYPES or e.get("tier") == 1


# --- the store ---------------------------------------------------------------------

def store(conn, cc, entries, today):
    """Upsert the run's kept entries; returns the new doc_ids."""
    new = []
    for e in entries:
        before = conn.execute("SELECT 1 FROM gov_docs WHERE cc=? AND doc_id=?",
                              (cc, e["doc_id"])).fetchone()
        if before is None:
            new.append(e["doc_id"])
        conn.execute(
            "INSERT INTO gov_docs (cc, doc_id, title, doc_type, body, published, closing_date, url, "
            "areas, matched_terms, tier, first_seen, last_seen, source, summary, status, watch_keys) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(cc, doc_id) DO UPDATE SET "
            "title=excluded.title, doc_type=excluded.doc_type, body=COALESCE(excluded.body, gov_docs.body), "
            "published=COALESCE(excluded.published, gov_docs.published), "
            "closing_date=COALESCE(excluded.closing_date, gov_docs.closing_date), url=excluded.url, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
            "last_seen=excluded.last_seen, source=excluded.source, "
            "summary=COALESCE(excluded.summary, gov_docs.summary), status=excluded.status, "
            "watch_keys=excluded.watch_keys",
            (cc, e["doc_id"], e["title"], e["doc_type"], e.get("body"), e.get("published"),
             e.get("closing_date"), e.get("url"), dumps(e.get("areas")), dumps(e.get("matched_terms")),
             e.get("tier"), today, today, e["source"], e.get("summary"), e.get("status"),
             dumps(e.get("watch_keys"))))
    conn.commit()
    return new


def record_run(conn, cc, source, today, ok, listed, kept, note):
    conn.execute(
        "INSERT INTO gov_doc_runs (cc, source, run_date, ok, listed, kept, note) VALUES "
        "(?,?,?,?,?,?,?) ON CONFLICT(cc, source, run_date) DO UPDATE SET ok=excluded.ok, "
        "listed=excluded.listed, kept=excluded.kept, note=excluded.note",
        (cc, source, today, 1 if ok else 0, listed, kept, (note or None) and str(note)[:500]))
    conn.commit()


def feed_name(cc, code):
    return "{0}-govdocs-{1}".format(cc, code)


def collect(conn, cc, client, today, config_dir=None, log=print, mod=None, window_days=WINDOW_DAYS):
    """One country's gov docs: fetch (or mirror), classify, keep what is on our
    ground, store. Returns (listed, kept, gaps)."""
    from src import db
    mod = mod or module(cc)
    taxes = taxonomies(cc, config_dir, mod)
    if not taxes:
        raise RuntimeError("{0}: no taxonomy file found".format(cc))
    wl = watchlist(cc, config_dir)
    total = kept_total = gaps_total = 0
    for src in mod.SOURCES:
        feed = feed_name(cc, src.code)
        started = time.monotonic()
        try:
            if src.mirror is not None:
                result = src.mirror(conn, cc, today)
            else:
                result = src.fetch(client, today, log)
        except Exception as exc:                        # noqa: BLE001
            result = fetched([], gaps=["read failed: {0}: {1}".format(
                type(exc).__name__, str(exc)[:200])])
        gaps = list(result.gaps)
        if not result.entries and not gaps and src.mirror is None:
            gaps.append("answered but nothing parsed (layout changed?)")
        for g in gaps:
            db.record_gap(conn, feed, g, today)       # prints the [gap] line too
        gaps_total += len(gaps)
        entries = [e for e in result.entries if in_window(e, today, window_days)]
        got = [classify(e, taxes, wl) for e in entries]
        ours = [e for e in got if on_ground(e)]
        new = store(conn, cc, ours, today)
        note = "; ".join(gaps) if gaps else result.note
        record_run(conn, cc, src.code, today, not gaps, len(entries), len(ours), note)
        for e in ours:
            log("  [govdoc] {0} {1}{2} {3} {4}{5}: {6}".format(
                cc, e["doc_id"], " new" if e["doc_id"] in new else "", e["doc_type"],
                e["areas"] or "watched",
                " closes " + e["closing_date"] if e.get("closing_date") else "", (e["title"] or "")[:80]))
        log("{0}: {1} listed in the window, {2} on our ground ({3} new){4}, {5:.0f} s.".format(
            feed, len(entries), len(ours), len(new), "; {0} gap(s)".format(len(gaps)) if gaps else "",
            time.monotonic() - started))
        total += len(entries)
        kept_total += len(ours)
    return total, kept_total, gaps_total


def reclassify(conn, cc, config_dir=None, log=print):
    """Re-derive stored rows' areas offline (after a taxonomy change). Rows that
    fall off our ground keep their row (areas emptied), as elsewhere."""
    taxes = taxonomies(cc, config_dir)
    wl = watchlist(cc, config_dir)
    changed = 0
    for r in conn.execute("SELECT doc_id, title, summary, doc_type, areas FROM gov_docs WHERE cc=?",
                          (cc,)).fetchall():
        e = classify({"doc_id": r[0], "title": r[1], "summary": r[2], "doc_type": r[3]}, taxes, wl)
        new = dumps(e["areas"])
        changed += new != (r[4] or "[]")
        conn.execute("UPDATE gov_docs SET areas=?, matched_terms=?, tier=?, watch_keys=? "
                     "WHERE cc=? AND doc_id=?",
                     (new, dumps(e["matched_terms"]), e["tier"], dumps(e["watch_keys"]), cc, r[0]))
    conn.commit()
    log("{0}-govdocs: reclassified; {1} row(s) changed area".format(cc, changed))
    return changed


# --- what the renderers read ---------------------------------------------------------

def deadline_rows(conn, cc, start, end):
    """The countdown contract: dicts for the consultations (DEADLINE_TYPES) on our
    ground whose closing_date is in [start, end], soonest first."""
    from src import latam
    marks = ",".join("?" * len(DEADLINE_TYPES))
    out = []
    for r in conn.execute(
            "SELECT * FROM gov_docs WHERE cc = ? AND doc_type IN ({0}) AND closing_date >= ? "
            "AND closing_date <= ? ORDER BY closing_date, doc_id".format(marks),
            (cc,) + DEADLINE_TYPES + (start, end)).fetchall():
        d = dict(r)
        if latam.areas_of(d["areas"]) or loads(d.get("watch_keys")):
            out.append(d)
    return out


def publication_rows(conn, cc, since, until, limit=10):
    """Documents on our ground published (or first seen) in (since, until],
    not of a deadline type, tier 1 first, then most matched terms."""
    from src import latam
    marks = ",".join("?" * len(DEADLINE_TYPES))
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM gov_docs WHERE cc = ? AND doc_type NOT IN ({0}) AND "
        "COALESCE(published, first_seen) > ? AND COALESCE(published, first_seen) <= ?".format(marks),
        (cc,) + DEADLINE_TYPES + (since, until)).fetchall()]
    rows = [r for r in rows if latam.areas_of(r["areas"]) or loads(r.get("watch_keys"))]
    rows.sort(key=lambda r: (r["tier"] or 9, -len(loads(r["matched_terms"])), r["published"] or ""))
    return rows[:limit]


def in_preparation_rows(conn, cc, since, until, limit=10):
    """Draft bills and regulations on our ground first seen in (since, until]
    with no closing date published (Poland's government register lists its
    drafts; the deadlines live on a host that refuses us): neither a deadline
    nor a publication, so they get their own list."""
    from src import latam
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM gov_docs WHERE cc = ? AND doc_type IN ('bill_draft', 'regulation_draft') "
        "AND closing_date IS NULL AND first_seen > ? AND first_seen <= ?", (cc, since, until)).fetchall()]
    rows = [r for r in rows if latam.areas_of(r["areas"]) or loads(r.get("watch_keys"))]
    rows.sort(key=lambda r: (r["tier"] or 9, -len(loads(r["matched_terms"])), r["published"] or ""))
    return rows[:limit]


def coverage_lines(conn, cc, mod=None):
    """One Coverage line: each source's latest run, gaps named."""
    got = conn.execute(
        "SELECT r.source, r.run_date, r.ok, r.listed, r.kept, r.note FROM gov_doc_runs r WHERE "
        "r.cc = ? AND r.run_date = (SELECT MAX(run_date) FROM gov_doc_runs s WHERE s.cc = r.cc "
        "AND s.source = r.source) ORDER BY r.source", (cc,)).fetchall()
    if not got:
        return []
    names = {}
    try:
        names = {s.code: s.name for s in (mod or module(cc)).SOURCES}
    except Exception:                                   # noqa: BLE001
        pass
    bits = []
    for source, run_date, ok, listed, kept, note in got:
        bit = "{0}: read {1}, {2} listed, {3} on our ground".format(
            names.get(source, source), run_date, listed or 0, kept or 0)
        if not ok:
            bit += " (gap: {0})".format((note or "partial read").rstrip("."))
        bits.append(bit)
    return ["Government consultations and publications: " + "; ".join(bits) + "."]
