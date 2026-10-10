"""What was said and asked in the chamber, for the new country editions.

Parity layer 5 (docs/country-parity-handover.md, 10 October 2026): debates,
speeches and parliamentary questions for the countries built on 9-10 October,
generalised from Germany's speeches (tools/de_speeches.py) and Ireland's
questions and debates (tools/ie_questions.py, tools/ie_debates.py). Each
country keeps its own collector,
because every source has its own shape: tools/<cc>_chamber.py, one per country,
holding only the fetch and the parse. Everything after the fetch lives here,
once: the tables, the classification, the store writes, the run loop (budget,
gaps, heartbeat, exit codes) and the edition items.

THE TABLES, per country, created for every code in COUNTRIES by db.init_db
(declared in db.TABLES, as every store's are):

    <cc>_speeches      one row per SPEECH on our ground (a member's turn at
                       the lectern, an interjection), never a whole sitting
    <cc>_questions     one row per written or oral question, interpellation
                       or request for information on our ground
    <cc>_record_reads  one row per source document read (a sitting's report,
                       a week of questions), with what it held and how much
                       of it was ours, whether or not anything matched, so
                       "nothing on our ground" can be told from "never read"

SEPARATION GUARANTEE. Only tools/<cc>_chamber.py writes a country's tables, through the functions below; nothing here touches
another jurisdiction's table.

THE LONG-TRANSCRIPT GUARD. A sitting's report runs to hundreds of thousands
of characters and brushes every subject, so a speech is classified on ITS OWN
WORDS, passage by passage (src/filter.match_passages, as Germany's and the
Westminster ledger's are): a passage must carry a tier-1 term (or a watchlist
entity) with its guards in the same passage. A tier-2 passage counts only when
the debate's own title is on our ground at tier 1. The chair calling the next
speaker is never stored. Nothing is matched against the sitting as a whole.

QUESTIONS are short: the question's title and, where the source gives it, its
subject index and summary, through src/filter.filter_item (tier 1 or 2). The
ANSWER never lends an area (a minister's words are not the asker's ground) and
is never pasted into an edition: the row keeps at most whether and when it
was answered.

IN THE EDITION (src/country_edition.py, kinds "speech" and "question"):
speeches are grouped by debate, one entry per debate and sitting, naming the
speakers on our ground with a short excerpt each (the source's own words,
verbatim, in the original language); questions are one entry each. A
country's coverage lines say what was read in the window.

Read-only except for the store_* functions.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The countries with a chamber collector (tools/<cc>_chamber.py) and what it
# reads. A code here gets its three tables. HEARTBEAT is the STEP heartbeat
# each collector stamps in source_runs after a run with no gap
# (tools/coverage.py AWAITING_FIRST_RUN), as Ireland's phase-2 steps do.
COUNTRIES = {
    "nl": ("speeches", "questions"),
    "ch": ("speeches",),
    "at": ("speeches",),
    "pl": ("questions",),
    "fr": ("speeches", "questions"),
    "br": ("questions",),
}


def heartbeat(cc):
    return "{0} chamber".format(cc.upper())


# A country's first run reads from here (its tables are watched from the
# first heartbeat, so they must not start empty): the September 2026
# sittings, the month the new countries were built.
FIRST_RUN_FROM = "2026-09-01"

SPEECH_CAP = 20000          # a whole speech, as Germany keeps (src/stance.py reads it)
EXCERPT = 260
MAX_SPEAKERS = 6            # speakers named under one debate in the edition
QUESTION_TEXT_CAP = 2000

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS {cc}_speeches (
        speech_id    TEXT PRIMARY KEY,   -- '<document>#<n>': stable within a report
        doc_id       TEXT,               -- the report it came from ({cc}_record_reads)
        date         TEXT,               -- ISO date of the sitting
        chamber      TEXT,               -- where the source has two
        debate_id    TEXT,               -- the agenda item / debate, as the source keys it
        debate       TEXT,               -- its title, verbatim
        speaker      TEXT,               -- as printed
        party        TEXT,               -- AT THE SPEECH, as printed
        role         TEXT,               -- 'member', 'minister', 'interjection', ...
        person_id    TEXT,               -- the source's own member id, when it gives one
        excerpt      TEXT,               -- the strongest matching passage, clipped
        text         TEXT,               -- the speech, capped at SPEECH_CAP
        url          TEXT,
        areas        TEXT,               -- JSON: from the speech's own passages
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        title_areas  TEXT,               -- JSON: the debate title's areas (context only)
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS {cc}_questions (
        question_id  TEXT PRIMARY KEY,   -- the source's own number
        kind         TEXT,               -- 'written', 'oral', 'interpellation', 'request', ...
        date         TEXT,               -- ISO date tabled
        title        TEXT,               -- verbatim
        text         TEXT,               -- summary or question text where given, capped
        asker        TEXT,               -- as printed; several joined by '; '
        party        TEXT,               -- at the question, where given
        addressee    TEXT,               -- the minister or office asked
        answered     TEXT,               -- ISO date of the answer, 'yes' (answered, date not
                                         -- given), 'untracked' (the source does not say),
                                         -- or NULL (no answer yet)
        url          TEXT,
        areas        TEXT,               -- JSON: the question's own words only
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS {cc}_record_reads (
        doc_id       TEXT PRIMARY KEY,   -- a report, a sitting, a week of questions
        feed         TEXT,               -- 'speeches' or 'questions'
        date         TEXT,               -- the sitting's or window's date
        version      TEXT,               -- the source's status ('Ongecorrigeerd', ...)
        segments     INTEGER,            -- speeches or questions it held
        matched      INTEGER,            -- of which on our ground
        chars        INTEGER,            -- characters read, so a short read shows
        status       TEXT,               -- 'read', or 'partial' when a budget stopped it
        read_on      TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS {cc}_speeches_date ON {cc}_speeches (date)",
    "CREATE INDEX IF NOT EXISTS {cc}_questions_date ON {cc}_questions (date)",
)


def tables(cc):
    """The country's tables: speeches and questions only for the feeds it
    collects (an empty questions table for a country that collects none
    would read as a wipe to tools/coverage.py), and always its reads."""
    feeds = COUNTRIES.get(cc, ("speeches", "questions"))
    return tuple("{0}_{1}".format(cc, f) for f in ("speeches", "questions") if f in feeds) + \
        ("{0}_record_reads".format(cc),)


TABLES = tuple(t for cc in COUNTRIES for t in tables(cc))


def ensure_schema(conn, codes=None):
    """Create each country's tables (and their indexes) for the feeds it has."""
    for cc in codes or COUNTRIES:
        mine = tables(cc)
        for stmt in SCHEMA:
            target = re.search(r" ON \{cc\}_(\w+)", stmt) or re.search(r"EXISTS \{cc\}_(\w+)",
                                                                        stmt)
            table = "{0}_{1}".format(cc, target.group(1))
            if table in mine:
                conn.execute(stmt.format(cc=cc))
    conn.commit()
    return conn


# --- classification ----------------------------------------------------------------

def load_taxonomies(cc, by_file=False):
    """[Taxonomy] from the country's edition adapter (src/editions/<cc>.py),
    so the collector and the edition can never read different lists; with
    by_file, {file name: Taxonomy}, for a bilingual country that routes each
    speech to the list of its language (Switzerland)."""
    from src import filter as filt
    import importlib
    country = importlib.import_module("src.editions.{0}".format(cc)).COUNTRY
    out = {}
    for fname, code in country.taxonomies:
        path = os.path.join(ROOT, "config", fname)
        if os.path.exists(path):
            out[fname] = filt.load_taxonomy(path, country=code)
    return out if by_file else list(out.values())


def empty_watchlist():
    """The new countries' watchlists key on numbers, never words
    (config/watchlist-<cc>.yaml), so nothing is matched on a name here."""
    from src import filter as filt
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


class Match:
    """What a speech or question matched: areas, terms, tier, excerpt."""

    def __init__(self, areas=(), terms=(), tier=None, excerpt=None):
        self.areas = sorted(set(areas))
        self.terms = list(terms)
        self.tier = tier
        self.excerpt = excerpt

    def __bool__(self):
        return bool(self.areas)


def classify_title(taxes, title):
    """The debate title's own match (context for the tier-2 rule; never stored
    as a speech's areas)."""
    from src import filter as filt
    wl = empty_watchlist()
    areas, terms, tier = set(), [], None
    for tax in taxes:
        res = filt.filter_item(tax, wl, title or "", title=title or "")
        areas.update(res.issue_areas or [])
        terms += [t for t in res.matched_terms if t not in terms]
        if res.tier and (tier is None or res.tier < tier):
            tier = res.tier
    return Match(areas, terms, tier)


def classify_speech(taxes, body, title_match=None):
    """A speech on its own words, passage by passage (see the module docstring:
    tier 1 in a passage, or tier 2 when the debate title is tier 1)."""
    from src import filter as filt
    wl = empty_watchlist()
    matches = []
    for tax in taxes:
        matches += filt.match_passages(tax, wl, body or "")
    tier = 1 if matches else None
    if not matches and title_match is not None and title_match.tier == 1:
        for tax in taxes:
            for passage in filt.split_passages(body or ""):
                res = filt.filter_item(tax, wl, passage, title="")
                if res.tier == 2 and res.issue_areas:
                    matches.append(filt.PassageMatch(passage=passage, result=res))
        tier = 2 if matches else None
    areas, terms, excerpt = filt.aggregate_passages(matches, max_excerpt=EXCERPT)
    return Match(areas, terms, tier if areas else None, excerpt)


def classify_question(taxes, *fields):
    """A question on its own words (title first, then subject and summary)."""
    from src import filter as filt
    wl = empty_watchlist()
    areas, terms, tier = set(), [], None
    for tax in taxes:
        res = filt.filter_item(tax, wl, *[f or "" for f in fields])
        areas.update(res.issue_areas or [])
        terms += [t for t in res.matched_terms if t not in terms]
        if res.issue_areas and res.tier and (tier is None or res.tier < tier):
            tier = res.tier
    return Match(areas, terms, tier if areas else None)


# --- text helpers --------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def html_text(html):
    """Plain text from an HTML or XML fragment, paragraphs kept as lines."""
    import html as htmlmod
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html or "")
    t = re.sub(r"(?i)<\s*(br|/p|/div|/li|/h\d|/tr)\b[^>]*>", "\n", t)
    t = htmlmod.unescape(_TAG.sub(" ", t))
    lines = [_WS.sub(" ", ln).strip() for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def short_id(*parts):
    """A stable short key from text parts (a debate with no id of its own)."""
    return hashlib.sha1("|".join(str(p or "") for p in parts).encode("utf-8")).hexdigest()[:12]


def dumps(areas):
    """Area numbers as stored everywhere in this repo: a sorted JSON list."""
    return json.dumps(sorted(set(int(a) for a in areas or [])))


# --- writes --------------------------------------------------------------------------

def store_speech(conn, cc, rec, match, today):
    """Insert or refresh one speech on our ground. `rec` keys: speech_id,
    doc_id, date, chamber, debate_id, debate, speaker, party, role,
    person_id, text, url, title_areas."""
    conn.execute(
        "INSERT INTO {0}_speeches (speech_id, doc_id, date, chamber, debate_id, debate, "
        "speaker, party, role, person_id, excerpt, text, url, areas, matched_terms, tier, "
        "title_areas, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(speech_id) DO UPDATE SET doc_id=excluded.doc_id, date=excluded.date, "
        "debate=excluded.debate, speaker=excluded.speaker, party=excluded.party, "
        "role=excluded.role, excerpt=excluded.excerpt, text=excluded.text, url=excluded.url, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "title_areas=excluded.title_areas, last_seen=excluded.last_seen".format(cc),
        (rec["speech_id"], rec.get("doc_id"), rec.get("date"), rec.get("chamber"),
         rec.get("debate_id"), rec.get("debate"), rec.get("speaker"), rec.get("party"),
         rec.get("role"), rec.get("person_id"), match.excerpt,
         (rec.get("text") or "")[:SPEECH_CAP], rec.get("url"), dumps(match.areas),
         json.dumps(match.terms, ensure_ascii=False), match.tier,
         dumps(rec.get("title_areas") or []), today, today))


def forget_speeches(conn, cc, doc_id, keep):
    """A report re-read in a newer version: drop its rows that no longer
    match (a corrected transcript can lose a passage), keep the rest."""
    keep = set(keep)
    for (sid,) in conn.execute("SELECT speech_id FROM {0}_speeches WHERE doc_id=?".format(cc),
                               (doc_id,)).fetchall():
        if sid not in keep:
            conn.execute("DELETE FROM {0}_speeches WHERE speech_id=?".format(cc), (sid,))


def store_question(conn, cc, rec, match, today):
    """Insert or refresh one question on our ground. `rec` keys: question_id,
    kind, date, title, text, asker, party, addressee, answered, url."""
    conn.execute(
        "INSERT INTO {0}_questions (question_id, kind, date, title, text, asker, party, "
        "addressee, answered, url, areas, matched_terms, tier, first_seen, last_seen) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(question_id) DO UPDATE SET "
        "kind=excluded.kind, date=excluded.date, title=excluded.title, text=excluded.text, "
        "asker=excluded.asker, party=excluded.party, addressee=excluded.addressee, "
        "answered=COALESCE(excluded.answered, {0}_questions.answered), url=excluded.url, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen".format(cc),
        (rec["question_id"], rec.get("kind"), rec.get("date"), rec.get("title"),
         (rec.get("text") or "")[:QUESTION_TEXT_CAP] or None, rec.get("asker"),
         rec.get("party"), rec.get("addressee"), rec.get("answered"), rec.get("url"),
         dumps(match.areas), json.dumps(match.terms, ensure_ascii=False), match.tier,
         today, today))


def mark_read(conn, cc, doc_id, feed, date, version, segments, matched, chars, today,
              status="read"):
    conn.execute(
        "INSERT INTO {0}_record_reads (doc_id, feed, date, version, segments, matched, chars, "
        "status, read_on, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(doc_id) DO UPDATE SET version=excluded.version, "
        "segments=excluded.segments, matched=excluded.matched, chars=excluded.chars, "
        "status=excluded.status, read_on=excluded.read_on, last_seen=excluded.last_seen"
        .format(cc), (doc_id, feed, date, version, segments, matched, chars, status, today,
                      today, today))


def seen(conn, cc, doc_id, today):
    """Re-stamp a document the listing still shows (the source answered)."""
    conn.execute("UPDATE {0}_record_reads SET last_seen=? WHERE doc_id=?".format(cc),
                 (today, doc_id))


def read_state(conn, cc, doc_id):
    """(version, status) of a document already read, or (None, None)."""
    row = conn.execute("SELECT version, status FROM {0}_record_reads WHERE doc_id=?".format(cc),
                       (doc_id,)).fetchone()
    return (row[0], row[1]) if row else (None, None)


def stamp(conn, heartbeat, today, note):
    """A STEP heartbeat in source_runs (tools/coverage.py AWAITING_FIRST_RUN)."""
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (heartbeat, today, os.environ.get("GITHUB_RUN_ID"), note))


def gap(conn, feed, detail, log=print):
    """A gap in the shared gaps table and a [gap] line in the log."""
    from src import db
    try:
        db.record_gap(conn, feed, detail)           # prints the [gap] line itself
    except Exception:                               # noqa: BLE001
        log("  [gap] {0}: {1}".format(feed, detail))


def not_found(exc):
    """True when a fetch failed on a 404 (a document listed before it is
    published), which is not a gap: it is read when it appears."""
    return "HTTP Error 404" in str(exc) or "404" in str(getattr(exc, "cause", "") or "")


# --- the edition ---------------------------------------------------------------------

QUESTION_KINDS = {
    "written": "Written question", "oral": "Oral question",
    "interpellation": "Interpellation", "request": "Request for information",
    "government": "Question to the government", "urgent": "Urgent question",
}


def _speaker(r):
    who = r["speaker"] or "Unnamed speaker"
    if r["party"]:
        who += " ({0})".format(r["party"])
    if r["role"] and r["role"] not in ("member",):
        who += ", " + r["role"]
    return who


def edition_items(conn, cc, since, until, wl):
    """The country's speeches (one item per debate and sitting) and questions
    on our ground in the window, for src/country_edition.py. [] when the
    country has no such tables."""
    from src import country_edition as ce
    out = []
    groups = {}
    for r in ce.rows(conn, "SELECT * FROM {0}_speeches WHERE {1} ORDER BY date, speech_id"
                     .format(cc, ce.window_sql("date")), (since, until)):
        if not ce.areas_of(r["areas"]):
            continue
        k = (r["date"], r["chamber"] or "", r["debate_id"] or r["debate"] or r["doc_id"])
        groups.setdefault(k, []).append(r)
    for (date, chamber, debate_id), rs in groups.items():
        areas = sorted({a for r in rs for a in ce.areas_of(r["areas"])})
        tiers = [r["tier"] for r in rs if r["tier"]]
        names = []
        for r in rs:
            n = r["speaker"] or "an unnamed speaker"
            if n not in names:
                names.append(n)
        lines = []
        for r in rs[:MAX_SPEAKERS]:
            lines.append("{0}: “{1}”".format(_speaker(r), ce.clip(ce.clean(r["excerpt"]), EXCERPT)))
        if len(rs) > MAX_SPEAKERS:
            lines.append("And {0} more speech(es) on our ground in this debate, in the store."
                         .format(len(rs) - MAX_SPEAKERS))
        take = "{0} speech{1} on our ground{2}, each matched in its own words: {3}".format(
            len(rs), "" if len(rs) == 1 else "es", " ({0})".format(chamber) if chamber else "",
            ", ".join(names[:8]) + (" and others" if len(names) > 8 else ""))
        key = "debate-" + short_id(date, chamber, debate_id)
        out.append(ce.item(cc, "speech", key, date,
                           rs[0]["debate"] or "(debate title not published)", areas,
                           min(tiers) if tiers else None, False, url=rs[0]["url"],
                           lines=lines, terms=rs[0]["matched_terms"], takeaway=take))
    for r in ce.rows(conn, "SELECT * FROM {0}_questions WHERE {1} ORDER BY date, question_id"
                     .format(cc, ce.window_sql("date")), (since, until)):
        watched = r["question_id"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        what = QUESTION_KINDS.get(r["kind"], (r["kind"] or "Question").capitalize())
        take = what
        if r["asker"]:
            take += " from {0}{1}".format(r["asker"], " ({0})".format(r["party"])
                                          if r["party"] else "")
        if r["addressee"]:
            asked = [a.strip() for a in r["addressee"].split(";") if a.strip()]
            take += " to {0}{1}".format("; ".join(asked[:2]), " and {0} more".format(
                len(asked) - 2) if len(asked) > 2 else "")
        answered = r["answered"]
        if answered and re.match(r"\d{4}-\d{2}-\d{2}", answered):
            take += "; answered {0}".format(ce.short_date(answered[:10]))
        elif answered == "untracked":
            pass
        elif answered:
            take += "; answered"
        else:
            take += "; no answer recorded yet"
        out.append(ce.item(cc, "question", r["question_id"], r["date"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], watched, url=r["url"],
                           terms=r["matched_terms"], takeaway=ce.clip(take, 300)))
    return out


def coverage_lines(conn, cc, since, until):
    """What was read in the window: English lines for the edition's Coverage.
    [] when the country has no such tables or read nothing in the window."""
    from src import country_edition as ce
    out = []
    for feed, what, unit in (("speeches", "Said in the chamber", "speeches"),
                             ("questions", "Questions", "questions")):
        got = ce.rows(conn, "SELECT COUNT(*), COALESCE(SUM(segments),0), COALESCE(SUM(matched),0),"
                            " SUM(status='partial') FROM {0}_record_reads WHERE feed=? AND {1}"
                      .format(cc, ce.window_sql("date")), (feed, since, until))
        if not got or not got[0][0]:
            continue
        n, segs, matched, partial = got[0][0], got[0][1], got[0][2], got[0][3] or 0
        line = "{0}: {1} {2} read in the window, {3} {4} in them, {5} on our ground".format(
            what, n, "report(s)" if feed == "speeches" else "batch(es)", segs, unit, matched)
        if feed == "speeches":
            line += " (each speech matched in its own words, never the whole sitting)"
        if partial:
            line += "; {0} read only in part (a time budget), to finish next run".format(partial)
        out.append(line + ".")
    return out


# --- the run loop every tools/<cc>_chamber.py shares ---------------------------------

class Run:
    """What a country's fetch functions are handed: the store, the client, the
    window, the time budget, the taxonomies, and the counters the summary and
    the exit code read. A fetch function calls the store_* functions through
    `speech()` / `question()` and reports trouble with `gap()`; it checks
    `budget.exhausted()` between documents and marks a document it could not
    finish 'partial' so the next run reads it again whole."""

    def __init__(self, cc, conn, client, today, since, budget, taxes, dry_run=False, log=print):
        self.cc, self.conn, self.client, self.today = cc, conn, client, today
        self.since, self.budget, self.taxes = since, budget, taxes
        self.dry_run, self.log = dry_run, log
        self.docs = self.segments = self.speeches = self.questions = self.gaps = 0
        self.stopped = False

    def gap(self, detail):
        self.gaps += 1
        gap(self.conn, "{0}-chamber".format(self.cc), detail, self.log)

    def speech(self, rec, match):
        self.speeches += 1
        if not self.dry_run:
            store_speech(self.conn, self.cc, rec, match, self.today)

    def question(self, rec, match):
        self.questions += 1
        if not self.dry_run:
            store_question(self.conn, self.cc, rec, match, self.today)

    def read(self, doc_id, feed, date, version, segments, matched, chars, status="read"):
        self.docs += 1
        self.segments += segments
        if not self.dry_run:
            mark_read(self.conn, self.cc, doc_id, feed, date, version, segments, matched, chars,
                      self.today, status)
            self.conn.commit()

    def out_of_time(self, what, done):
        if self.budget.exhausted():
            if not self.stopped:
                self.log(self.budget.disclose(what, done))
            self.stopped = True
            return True
        return False


def reclassify(conn, cc, taxes=None, log=print, route=None):
    """Re-derive stored speeches' and questions' areas, offline, after a
    taxonomy change. Rows that fall off our ground keep their (now empty)
    areas: rows are never deleted here, and the edition skips them."""
    taxes = taxes if taxes is not None else load_taxonomies(cc)
    changed = 0
    for sid, debate, text, areas in conn.execute(
            "SELECT speech_id, debate, text, areas FROM {0}_speeches".format(cc)).fetchall():
        use, words = route(text) if route else (taxes, text)
        m = classify_speech(use, words, classify_title(taxes, debate))
        new = dumps(m.areas)
        changed += new != (areas or "[]")
        conn.execute("UPDATE {0}_speeches SET areas=?, matched_terms=?, tier=?, excerpt=? "
                     "WHERE speech_id=?".format(cc),
                     (new, json.dumps(m.terms, ensure_ascii=False), m.tier, m.excerpt, sid))
    for qid, title, text, areas in conn.execute(
            "SELECT question_id, title, text, areas FROM {0}_questions".format(cc)).fetchall():
        m = classify_question(taxes, title, text)
        new = dumps(m.areas)
        changed += new != (areas or "[]")
        conn.execute("UPDATE {0}_questions SET areas=?, matched_terms=?, tier=? "
                     "WHERE question_id=?".format(cc),
                     (new, json.dumps(m.terms, ensure_ascii=False), m.tier, qid))
    conn.commit()
    log("{0}-chamber: reclassified; {1} row(s) changed area".format(cc, changed))
    return changed


def main(cc, steps, argv=None, lookback_days=21, budget_seconds=900.0, doc=None,
         configure=None, route=None):
    """The entry point of tools/<cc>_chamber.py. `steps` is {'speeches': fn,
    'questions': fn}, each fn(run) fetching and storing its feed.

    Exit codes, as the weekly jobs read them: 0 all read; 3 stored what it
    could and recorded gaps (the job still publishes); 1 nothing usable."""
    import argparse
    import datetime
    from src import db, drain
    from src.http import HttpClient
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--since", help="ISO date; default {0} days back (documents dated "
                                    "after it are read or re-read)".format(lookback_days))
    ap.add_argument("--only", choices=sorted(steps), help="one feed only")
    ap.add_argument("--budget-seconds", type=float, default=budget_seconds)
    ap.add_argument("--dry-run", action="store_true", help="fetch and count; store nothing")
    ap.add_argument("--reclassify", action="store_true", help="re-derive areas, offline")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    taxes = load_taxonomies(cc)
    if args.reclassify:
        reclassify(conn, cc, taxes, route=route)
        return 0
    since = args.since or (datetime.date.today()
                           - datetime.timedelta(days=lookback_days)).isoformat()
    if not args.since and not conn.execute(
            "SELECT 1 FROM {0}_record_reads LIMIT 1".format(cc)).fetchone():
        since = min(since, FIRST_RUN_FROM)
        print("{0}-chamber: first run, reading from {1}".format(cc, since))
    client = HttpClient(raw_dir=args.raw_dir)
    if configure:
        configure(client)
    run = Run(cc, conn, client, today, since, drain.Budget(args.budget_seconds), taxes,
              dry_run=args.dry_run)
    for name, fn in steps.items():
        if args.only and name != args.only:
            continue
        if run.budget.exhausted():
            run.log("  {0}-chamber: no time left for {1}; next run".format(cc, name))
            break
        try:
            fn(run)
        except Exception as exc:                    # noqa: BLE001
            run.gap("{0} failed: {1}: {2}".format(name, type(exc).__name__, str(exc)[:160]))
        if not args.dry_run:
            conn.commit()
    print("{0}-chamber: {1} document(s) read since {2}, {3} segment(s) in them; {4} speech(es) "
          "and {5} question(s) on our ground{6}; {7} gap(s){8}.".format(
              cc, run.docs, since, run.segments, run.speeches, run.questions,
              " (dry run, nothing stored)" if args.dry_run else "", run.gaps,
              "; stopped by the time budget, the rest next run" if run.stopped else ""))
    if not args.dry_run and not run.gaps:
        stamp(conn, heartbeat(cc), today,
              "step heartbeat: tools/{0}_chamber.py".format(cc))
        conn.commit()
    conn.close()
    if run.gaps:
        return 3 if (run.docs or run.speeches or run.questions) else 1
    return 0
