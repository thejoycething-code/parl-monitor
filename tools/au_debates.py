#!/usr/bin/env python3
"""Australia's Federal Parliament: speeches and Senate motions on our ground.

    python3 tools/au_debates.py                          # unread days of the Parliament, newest first
    python3 tools/au_debates.py --budget-seconds 600     # stop after ten minutes, resume next run
    python3 tools/au_debates.py --dry-run                # list the days that would be read
    python3 tools/au_debates.py --reclassify             # re-derive areas, offline
    python3 tools/au_debates.py --db /tmp/au.db --raw-dir /tmp/au-raw   # a scratch run

Built 9 October 2026 (Christopher: "build Australian debates"); see
docs/australia-scope.md, "Debates". Modelled on tools/us_record.py.

THE SOURCE is the same as the divisions': the OpenAustralia Foundation's
parse of the official Hansard, data.openaustralia.org.au/scrapedxml/
<chamber>_debates/<date>.xml, one file per chamber per sitting day, open and
keyless. Each <speech> carries the speaker's office ID (resolved to a person
and the party of that spell through au_offices, which tools/au_rollcalls.py
fills), a time, a talktype ('speech', 'continuation', 'interjection') and
the ParlInfo page it came from. The debate's headings and its <bills> tags
(the Parliament's own bill IDs) come before it in the same file.

NOT ARCHIVED AGAIN. tools/au_rollcalls.py archives every day file it reads
(feed au-rollcalls) and reads a day again when OpenAustralia re-parses it;
this step reads the same URLs, so it does not archive a second copy.

WHAT A SPEECH IS. Everything one person said in one section of the day
(a minor heading and what follows it): their 'speech' and 'continuation'
segments, as tools/us_record.py takes everything one member said in one
granule. So a senator's four contributions to one committee-stage debate
are one speech, keyed on the first segment. Interjections are skipped; a
segment whose speaker OpenAustralia could not identify ('unknown',
"Honourable senators interjecting") is counted per day
(au_debate_days.unresolved) and never given to anyone. A speech is a
'motion' when the speaker opens by moving one ("I move: That the Senate
...", "by leave, I move ..."), unless it is only the routine motion for a
bill's second or third reading or the closure; a 'notice' under the
Senate's NOTICES heading.

ONLY SPEECHES ON OUR GROUND ARE STORED, with an excerpt (the best-matching
passage, at most 400 characters) and a word count, never the text.

THE RULE (classify_speech; the one place it lives), copied from
tools/us_record.py:
  * `own_areas` is what the speaker's OWN WORDS matched, passage by passage
    (src/filter.match_passages: a passage counts only on a tier-1 term). The
    debate's minor heading counts as a passage of its own only for a speech
    of MIN_WORDS words or more: in the Australian Hansard the minor heading
    of a bill debate IS the bill's title, so letting it count for a
    one-line contribution would make every "I move that the question be now
    put" on the bill a speech on our ground.
  * `areas` adds a bill's areas in exactly two cases, and `areas_from` says
    which:
      - 'watch': the debate is ON a bill on config/watchlist-au.yaml (it is
        tagged in the debate's <bills>), and the speaker said at least
        WATCH_MIN_WORDS words. By KEY. (The one departure from the US rule:
        an Australian section holds the chair's and the whips' one-liners
        on the bill, "I move that the question be now put", which a US
        granule rarely does.)
      - 'bill': the speech's own text matched nothing AND the debate is ON a
        bill AND that bill's own TITLE is on our ground (the taxonomy on the
        title alone, not the watchlist) AND the speaker spoke at least
        MIN_WORDS words. A senator arguing for s1500 who never says
        "biological sex" is still speaking to it; one moving the closure is
        not.
  * Otherwise `areas` is `own_areas`.

INCREMENTAL BY DATE, NEWEST FIRST. Every run lists both chambers' day
files, re-stamps the ones it already holds, and reads every day of the
Parliament not yet read, or whose listing stamp moved (OpenAustralia
re-parses old days), newest first, so a budget-capped backfill fills the
weeks the edition needs before the old ones. A day stopped by the budget is
not marked read and is read whole next time.

Separation guarantee: writes au_speeches, au_debate_days, the shared gaps
table and its own source_runs heartbeat. ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402


def _rollcalls():
    spec = importlib.util.spec_from_file_location(
        "au_rollcalls", os.path.join(ROOT, "tools", "au_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aur = _rollcalls()

FEED = "au-debates"
HEARTBEAT = "AU debates"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
BUDGET_S = 900.0
# Below this a contribution is procedure ("I move that the question be now
# put"), not a speech that can stand on its bill or its heading.
MIN_WORDS = 150
# A watched bill lends to anything longer than procedure.
WATCH_MIN_WORDS = 40
EXCERPT = 400
HIDDEN_AREAS = (11,)
OA_PAGE = {"house": "https://www.openaustralia.org.au/debate/?id={0}",
           "senate": "https://www.openaustralia.org.au/senate/?id={0}"}
_MOVE = re.compile(r"^(?:by leave\W*|pursuant to [^,]{0,80},\s*)?I move\b", re.I)
_ROUTINE = re.compile(r"I move\W*(?:that )?(?:this bill be now read a (?:second|third) time|"
                      r"the question be now put|that the bill be now read)", re.I)


def _squash(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def segment_id(raw):
    """'uk.org.publicwhip/lords/2026-09-16.10.1' -> '2026-09-16.10.1'."""
    return (raw or "").rsplit("/", 1)[-1] or None


def paragraphs(el):
    """A speech element's paragraphs, one per line, tags dropped."""
    paras = [_squash("".join(p.itertext())) for p in el.iter("p")]
    paras = [p for p in paras if p]
    return paras or [_squash("".join(el.itertext()))]


# --- parsing ---------------------------------------------------------------------

def parse_speeches(raw, chamber, date):
    """One day file -> (speeches, unresolved). A speech is a dict with the
    speaker's office ID, the section's headings and bills, and its text."""
    root = ET.fromstring(raw)
    major = minor = None
    section_bills = []
    speeches, unresolved = [], 0
    by_speaker = {}
    for el in root:
        tag = el.tag
        if tag in ("major-heading", "minor-heading"):
            text = _squash("".join(el.itertext()))
            if tag == "major-heading":
                major, minor = text, None
            else:
                minor = text
            section_bills, by_speaker = [], {}
        elif tag == "bills":
            for b in el.iter("bill"):
                bid = (b.get("id") or "").strip()
                if aur.BILL_ID.match(bid) and bid not in section_bills:
                    section_bills.append(bid)
        elif tag == "speech":
            kind = el.get("talktype") or "speech"
            office = aur.office_id(el.get("speakerid"))
            if kind == "interjection":
                continue
            if not office:
                unresolved += 1
                continue
            paras = paragraphs(el)
            if office in by_speaker:
                by_speaker[office]["paras"] += paras
                continue
            by_speaker[office] = {"segment": segment_id(el.get("id")), "office_id": office,
                                  "name": el.get("speakername"), "time": el.get("time"),
                                  "chamber": chamber, "date": date, "major": major,
                                  "minor": minor, "bills": list(section_bills), "paras": paras,
                                  "source_url": el.get("url")}
            speeches.append(by_speaker[office])
    for s in speeches:
        s["text"] = "\n".join(s["paras"])
        s["words"] = len(s["text"].split())
        s["kind"] = speech_kind(s["major"], s["paras"])
    return speeches, unresolved


def speech_kind(major, paras):
    """'notice' under NOTICES; 'motion' when the speaker opens by moving one
    that is not a bill's routine reading or the closure; else 'speech'."""
    if (major or "").upper() == "NOTICES":
        return "notice"
    opening = " ".join((paras or [""])[:2])
    if _MOVE.search(opening) and not _ROUTINE.search(opening):
        return "motion"
    return "speech"


# --- classification --------------------------------------------------------------

def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def lead(text, n=EXCERPT):
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[:n - 3].rsplit(" ", 1)[0] + "..."


class BillTitles:
    """A bill's areas from its OWN TITLE alone (the taxonomy, never the
    watchlist: that case is 'watch'), cached."""

    def __init__(self, conn, tax, wl):
        self.conn, self.tax, self.wl, self.cache = conn, tax, wl, {}

    def areas(self, bill_id):
        if bill_id not in self.cache:
            row = self.conn.execute("SELECT title FROM au_bills WHERE bill_id=?",
                                    (bill_id,)).fetchone()
            areas = []
            if row and row[0]:
                res = filt.filter_item(self.tax, self.wl, row[0], title=row[0])
                areas = sorted(set(res.issue_areas or []))
            self.cache[bill_id] = areas
        return self.cache[bill_id]


def classify_speech(tax, wl, heading, text, words, bills, bill_titles, watch=None):
    """(own_areas, areas, areas_from, terms, tier, excerpt): the rule in the
    module docstring."""
    title = heading if (heading and words >= MIN_WORDS) else None
    matches = filt.match_passages(tax, wl, text, title=title)
    own, terms, excerpt = filt.aggregate_passages(matches, max_excerpt=EXCERPT)
    if excerpt and title and " ".join(title.split()).startswith(excerpt.rstrip(".")[:40]):
        # The heading matched best; the excerpt should be the speaker's words.
        body = filt.match_passages(tax, wl, text)
        excerpt = filt.aggregate_passages(body, max_excerpt=EXCERPT)[2] or lead(text)
    tier = 1 if any(m.result.tier == 1 for m in matches) else (2 if matches else None)
    areas, source = set(own), ("own" if own else None)
    terms = list(terms)
    watch = watch if watch is not None else au_store.watchlist()
    watched = [b for b in bills or [] if b in watch] if words >= WATCH_MIN_WORDS else []
    if watched:
        for b in watched:
            areas |= set(watch[b][0])
            terms.append("watch:" + b)
        source = source or "watch"
    elif not own and bills and words >= MIN_WORDS:
        for b in bills:
            lent = bill_titles(b) if callable(bill_titles) else bill_titles.areas(b)
            if on_our_ground(lent):
                areas |= set(lent)
                source = source or "bill"
                terms.append("bill:" + b)
    if source in ("watch", "bill") and not excerpt:
        paras = [p for p in (text or "").split("\n") if len(p.split()) >= 40]
        excerpt = lead(paras[1] if len(paras) > 1 else (paras or [text])[0])
    if excerpt and len(excerpt) > EXCERPT:
        excerpt = lead(excerpt)
    return sorted(own), sorted(areas), source, terms, tier or (2 if areas else None), excerpt


# --- storing ---------------------------------------------------------------------

def _people(conn):
    """{office_id: (person_id, party, phid)}."""
    return {oid: (pid, party, phid) for oid, pid, party, phid in conn.execute(
        "SELECT o.office_id, o.person_id, o.party, m.phid FROM au_offices o "
        "LEFT JOIN au_members m ON m.person_id = o.person_id")}


def store_speech(conn, s, cls, who, today):
    own, areas, source, terms, tier, excerpt = cls
    person, party, phid = who
    key = "{0}/{1}".format(s["chamber"], s["segment"])
    conn.execute(
        "INSERT INTO au_speeches (speech_key, chamber, parliament, date, time, person_id, "
        "office_id, phid, name, party, kind, major_heading, minor_heading, bill_ids, words, "
        "own_areas, areas, areas_from, matched_terms, tier, excerpt, url, source_url, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(speech_key) DO UPDATE SET time=excluded.time, person_id=excluded.person_id, "
        "office_id=excluded.office_id, phid=excluded.phid, name=excluded.name, "
        "party=excluded.party, kind=excluded.kind, major_heading=excluded.major_heading, "
        "minor_heading=excluded.minor_heading, bill_ids=excluded.bill_ids, words=excluded.words, "
        "own_areas=excluded.own_areas, areas=excluded.areas, areas_from=excluded.areas_from, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, excerpt=excluded.excerpt, "
        "url=excluded.url, source_url=excluded.source_url, last_seen=excluded.last_seen",
        (key, s["chamber"], aur.parliament_of(s["date"]), s["date"], s["time"], person,
         s["office_id"], phid, s["name"], party, s["kind"], s["major"], s["minor"],
         au_store.dumps(s["bills"]), s["words"], au_store.dumps(own), au_store.dumps(areas),
         source, au_store.dumps(terms), tier, excerpt,
         OA_PAGE[s["chamber"]].format(s["segment"]), s["source_url"], today, today))
    return key


def read_day(conn, raw, chamber, date, today, tax, wl, people, titles, watch=None):
    """Parse and store one day. Returns (speeches, ours, unresolved)."""
    speeches, unresolved = parse_speeches(raw, chamber, date)
    # A re-parsed day replaces what was stored for it: a speech the new parse
    # no longer has on our ground must not linger.
    conn.execute("DELETE FROM au_speeches WHERE chamber=? AND date=? AND triage_score IS NULL",
                 (chamber, date))
    read = ours = 0
    for s in speeches:
        who = people.get(s["office_id"])
        if not who:
            unresolved += 1
            continue
        read += 1
        cls = classify_speech(tax, wl, s["minor"] or s["major"], s["text"], s["words"],
                              s["bills"], titles, watch)
        if on_our_ground(cls[1]):
            store_speech(conn, s, cls, who, today)
            ours += 1
    return read, ours, unresolved


def pull(conn, client, today, tax=None, wl=None, log=print, budget=None, limit=None,
         dry=False, watch=None, parliament=aur.CURRENT_PARLIAMENT):
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    first, last = aur.PARLIAMENTS[parliament]
    stats = {"days": 0, "speeches": 0, "ours": 0, "unresolved": 0, "gaps": 0, "left": 0}
    todo = []
    for chamber, folder in aur.CHAMBERS:
        try:
            listing = aur.parse_listing(client.get_text(aur.LISTING.format(folder), FEED,
                                                        "listing-" + folder, archive=False))
        except FetchError as exc:
            _gap(conn, today, "listing {0}: {1}".format(folder, exc))
            log("  [gap] {0} listing: {1}".format(folder, str(exc)[:70]))
            stats["gaps"] += 1
            continue
        if not listing:
            _gap(conn, today, "listing {0}: no day files on the page".format(folder))
            stats["gaps"] += 1
            continue
        held = dict(conn.execute("SELECT path, listed_modified FROM au_debate_days "
                                 "WHERE chamber=?", (chamber,)))
        for date, modified in listing:
            if date < first or (last and date > last):
                continue
            path = "{0}_debates/{1}.xml".format(folder, date)
            if held.get(path) == modified:
                if not dry:
                    conn.execute("UPDATE au_debate_days SET last_seen=? WHERE path=?", (today, path))
                continue
            todo.append((date, chamber, folder, path, modified))
    todo.sort(reverse=True)
    if dry:
        stats["left"] = len(todo)
        return stats
    people = _people(conn)
    titles = BillTitles(conn, tax, wl)
    for n, (date, chamber, folder, path, modified) in enumerate(todo):
        if (limit is not None and n >= limit) or (budget is not None and budget.exhausted()):
            stats["left"] = len(todo) - n
            log("  {0} day file(s) left for the next run (newest read first) -- disclosed, "
                "not silent".format(stats["left"]))
            break
        try:
            raw = client.get_bytes(aur.DAY.format(folder, date), FEED,
                                   "{0}-{1}".format(chamber, date), archive=False)
            read, ours, unresolved = read_day(conn, raw, chamber, date, today, tax, wl,
                                              people, titles, watch)
        except (FetchError, ET.ParseError) as exc:
            _gap(conn, today, "{0}: {1}".format(path, exc))
            log("  [gap] {0}: {1}".format(path, str(exc)[:70]))
            stats["gaps"] += 1
            continue
        conn.execute("INSERT OR REPLACE INTO au_debate_days (path, chamber, date, listed_modified, "
                     "read_at, speeches, ours, unresolved, last_seen) VALUES (?,?,?,?,?,?,?,?,?)",
                     (path, chamber, date, modified, today, read, ours, unresolved, today))
        conn.commit()
        stats["days"] += 1
        stats["speeches"] += read
        stats["ours"] += ours
        stats["unresolved"] += unresolved
    return stats


def reclassify(conn, tax=None, log=print, watch=None):
    """Re-derive stored speeches' areas from their excerpt is NOT possible (the
    text is not stored), so a taxonomy change re-reads the days: every
    au_debate_days stamp is cleared and the next run reads them again."""
    n = conn.execute("UPDATE au_debate_days SET listed_modified = NULL").rowcount
    conn.commit()
    log("au-debates: {0} day(s) queued to be read again".format(n))
    return n


def stamp_heartbeat(conn, today, note):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"), note))
    conn.commit()


def make_client(raw_dir=None):
    client = HttpClient(raw_dir=raw_dir or os.path.join(ROOT, "data", "raw"))
    client.set_host_throttle("data.openaustralia.org.au", aur.OA_THROTTLE_S)
    return client


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", help="raw tree for the client (nothing is archived)")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many day files")
    ap.add_argument("--dry-run", action="store_true", help="list the days that would be read")
    ap.add_argument("--reclassify", action="store_true",
                    help="queue every day to be read again (the text is not stored)")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    today = datetime.date.today().isoformat()
    if args.reclassify:
        reclassify(conn)
        return 0
    s = pull(conn, make_client(args.raw_dir), today, budget=drain.Budget(args.budget_seconds),
             limit=args.limit, dry=args.dry_run)
    if args.dry_run:
        print("au-debates: {0} day file(s) to read; nothing read (dry run)".format(s["left"]))
        return 0
    if not s["gaps"]:
        stamp_heartbeat(conn, today, "step heartbeat: tools/au_debates.py ({0} day(s), {1} "
                        "on our ground, {2} left)".format(s["days"], s["ours"], s["left"]))
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    print("au-debates: {0} day file(s) read, {1} speech(es), {2} on our ground stored, {3} "
          "segment(s) with no speaker, {4} day(s) left, {5} gap(s); store: {6} speech(es) on "
          "our ground from {7} day(s)".format(
              s["days"], s["speeches"], s["ours"], s["unresolved"], s["left"], s["gaps"],
              n("SELECT COUNT(*) FROM au_speeches"), n("SELECT COUNT(*) FROM au_debate_days")))
    conn.close()
    return 3 if s["gaps"] else 0


if __name__ == "__main__":
    sys.exit(main())
