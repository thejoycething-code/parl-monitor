#!/usr/bin/env python3
"""Ireland: debate speeches on our ground, Hansard-style, per member per section.

    python3 tools/ie_debates.py                         # due weeks, newest first
    python3 tools/ie_debates.py --budget-seconds 300    # stop after five minutes; the rest drains later
    python3 tools/ie_debates.py --since 2026-09-01      # only weeks from this date
    python3 tools/ie_debates.py --no-committees         # the Dáil and Seanad only
    python3 tools/ie_debates.py --dry-run               # list the due weeks, fetch nothing
    python3 tools/ie_debates.py --reclassify            # re-derive areas, offline
    python3 tools/ie_debates.py --db /tmp/ie.db --raw-dir /tmp/ie-raw   # a scratch run

PHASE 2 (9 October 2026); see docs/ireland-scope.md. One source, open and
keyless: the Oireachtas Open Data API, /debates, read a WEEK at a time
(Monday to Sunday), plenary (chamber_type=house: the Dáil and the Seanad)
and committee (chamber_type=committee) apart. Each debate record is one
House's (or committee's) sitting day, and carries every debate section with
its full text inline, utterance by utterance, each with the speaker's
memberCode. About 230 KB a record; a sitting week is 5 to 8 MB.

WHAT A SPEECH IS. Everything one member said in one debate section:
speech_key '<record>/<dbsect_N>/<memberCode>'. The label the record prints
before each utterance ('Deputy Mary Lou McDonald', 'Minister for Health
(Deputy Jennifer Carroll MacNeill)') is struck, and an office label is kept
as `role`. Utterances with no memberCode (committee witnesses, the clerk)
are nobody's and are not stored: committee HEARINGS are an open question
(docs/ireland-scope.md). Oral PQ sections (debateType 'question', the
Priority and Other Questions exchanges) are skipped: tools/ie_questions.py
holds them, with the answer kept to one line. Leaders' Questions, Questions
on Policy or Legislation, Topical Issues and Commencement Matters are
debate here, not PQs, and are read.

THE BILL, BY ID. A section's bill is the bill whose record lists that debate
section (ie_bill_debates, the join tools/ie_rollcalls.py uses for
divisions), or, where no bill record lists it, the bill the section itself
names by URI (`debateSection.bill.uri`, '.../bill/2026/34'). Never a title.

THE RULE (classify_speech; the one place it lives), copied from the US
Congressional Record (tools/us_record.py) and made narrower:
  * `own_areas` is what the member's OWN WORDS matched, passage by passage
    (src/filter.match_passages: a passage counts only on a tier-1 term),
    the Minister's office struck first. Never the section heading, never a
    bill's areas.
  * `areas` adds something lent in exactly three cases, and only when the
    member's own words matched NOTHING and the member spoke at least
    MIN_WORDS words (a Leas-Cheann Comhairle's "Is that agreed?" stands on
    nothing):
      - 'watch': the section's bill is on config/watchlist-ie.yaml (by KEY).
      - 'bill': the section's bill's SHORT TITLE is on our ground. Not its
        long title: the Mental Health Bill 2024's long title mentions
        parental consent, which put its 31 divisions in area 6 (the NDAA
        lesson again, docs/ireland-scope.md), and the US lends from a bill's
        display and official titles only for the same reason.
      - 'heading': no bill, and the section's own title matched a tier-1
        term ('Parental Choice in Education: Motion').
  * Otherwise `areas` is `own_areas`.

INCREMENTAL BY WEEK (src/ie_store.due_weeks): every week since the 34th
Dáil met not yet read, any week whose read stopped, and the last
REREAD_DAYS (the record is revised from the draft for days after a
sitting). Newest first, so a budget-capped backfill fills the weeks the
edition needs before the old ones. A stopped week is read again whole.

RAW ARCHIVE. Not archived: the backfill is about 600 MB of JSON, every
byte of it re-fetchable from the same URL (as for tools/ie_questions.py).

Separation guarantee: writes ie_speeches, ie_windows (feeds 'debates-house'
and 'debates-committee'), the shared gaps table and its own source_runs
heartbeat ('IE debates'). ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from urllib.parse import quote, urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, drain, filter as filt, ie_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
import ie_rollcalls as roll  # noqa: E402

FEED = "ie-debates"
HEARTBEAT = "IE debates"
API = roll.API
TAXONOMY = roll.TAXONOMY
PAGE = 10                 # records are about 230 KB each, with every utterance inline
BUDGET_S = 600.0
REREAD_DAYS = 14
MIN_WORDS = 150
EXCERPT = 400
HIDDEN_AREAS = roll.HIDDEN_AREAS
SKIP_TYPES = frozenset({"question"})   # oral PQ exchanges: tools/ie_questions.py
KINDS = (("debates-house", "house"), ("debates-committee", "committee"))
WEB = "https://www.oireachtas.ie/en/debates/debate/{0}/{1}/{2}/"
# The label before each utterance: an office with the member's name in
# brackets, or 'Deputy X' / 'Senator X' (X being the speaker's showAs).
OFFICE_LABEL = re.compile(r"^\s*([^()\n]{3,200}?\((?:Deputy|Senator) [^)]{2,80}\))\s*")
# The offices printed with no name: the Taoiseach, the Tánaiste and the chair.
CHAIR_LABEL = re.compile(r"^\s*((?:An |The )?(?:Taoiseach|Tánaiste|Ceann Comhairle|Leas-Cheann Comhairle|"
                         r"Cathaoirleach|Leas-Chathaoirleach|Cathaoirleach Gníomhach|Chairman|"
                         r"Chairperson|Acting Chairperson|Acting Chairman))\b\s*")


def record_path(uri):
    """'.../debateRecord/dail/2026-10-07/debate/main' -> 'dail/2026-10-07/debate'."""
    hit = re.search(r"/debateRecord/(.+?)/main$", uri or "")
    return hit.group(1) if hit else None


def bill_key_from_uri(uri):
    hit = re.search(r"/bill/(\d{4})/(\d+)$", uri or "")
    return roll.bill_key(hit.group(1), hit.group(2)) if hit else None


def strip_label(text, speaker):
    """(role or None, text without its label)."""
    text = (text or "").strip()
    hit = OFFICE_LABEL.match(text)
    if hit and (not speaker or speaker.split()[-1] in hit.group(1)):
        return " ".join(hit.group(1).split()), text[hit.end():].strip()
    hit = CHAIR_LABEL.match(text)
    if hit:
        return hit.group(1), text[hit.end():].strip()
    for prefix in ("Deputy ", "Senator ", ""):
        label = prefix + (speaker or "")
        if speaker and text.startswith(label):
            return None, text[len(label):].strip()
    return None, text


def section_url(record, date, section_id):
    """The Oireachtas page for a debate section: /en/debates/debate/<dail|
    seanad|committee code>/<date>/<n>/."""
    house = record.get("house") or {}
    where = house.get("committeeCode") or house.get("houseCode") or "dail"
    n = (section_id or "").replace("dbsect_", "")
    return WEB.format(where, date, n)


def speeches_in(rec):
    """Every member's speech in every section of one debate record.

    Yields dicts: the record's day and House, the section, the member and
    their joined text."""
    r = rec.get("debateRecord") or rec
    house = r.get("house") or {}
    is_cmte = house.get("chamberType") == "committee" or bool(house.get("committeeCode"))
    chamber = "committee" if is_cmte else house.get("houseCode")
    hk = ("{0}/{1}".format(house.get("houseCode"), house.get("houseNo"))
          if house.get("houseCode") in ("dail", "seanad") and str(house.get("houseNo") or "").isdigit()
          else None)
    date = r.get("date")
    for s in r.get("debateSections") or []:
        ds = s.get("debateSection") or {}
        if (ds.get("debateType") or "") in SKIP_TYPES:
            continue
        by_member, order = {}, []
        for t in ds.get("text") or []:
            if t.get("textType") != "speech":
                continue
            sp = t.get("speaker") or {}
            code = sp.get("memberCode")
            if not code:
                continue
            role, body = strip_label(t.get("text"), sp.get("showAs"))
            if code not in by_member:
                by_member[code] = {"speaker": sp.get("showAs"), "role": role, "parts": []}
                order.append(code)
            if role and not by_member[code]["role"]:
                by_member[code]["role"] = role
            by_member[code]["parts"].append(body)
        for code in order:
            m = by_member[code]
            text = "\n".join(p for p in m["parts"] if p)
            yield {
                "record_uri": r.get("uri"), "date": date, "chamber": chamber, "house_key": hk,
                "committee": house.get("showAs") if is_cmte else None,
                "section": ds.get("debateSectionId"), "title": ds.get("showAs"),
                "debate_type": ds.get("debateType"),
                "section_bill": bill_key_from_uri((ds.get("bill") or {}).get("uri")),
                "member_code": code, "speaker": m["speaker"], "role": m["role"],
                "text": text, "words": len(text.split()), "turns": len(m["parts"]),
                "url": section_url(r, date, ds.get("debateSectionId")),
            }


class Bills:
    """A section's bill by ID, and what a bill may lend (its SHORT title's
    areas, and the watchlist by key), cached."""

    def __init__(self, conn, tax, wl, watch=None):
        self.conn, self.tax, self.wl = conn, tax, wl
        self.watch = watch if watch is not None else ie_store.watchlist()
        self._join, self._lend = {}, {}

    def key(self, record_uri, section, section_bill=None):
        k = (record_uri, section)
        if k not in self._join:
            rows = [r[0] for r in self.conn.execute(
                "SELECT DISTINCT bill_key FROM ie_bill_debates WHERE debate_uri=? AND "
                "debate_section=?", (record_uri, section))]
            self._join[k] = rows[0] if len(rows) == 1 else (section_bill if not rows or
                                                           section_bill in rows else None)
        return self._join[k]

    def lends(self, key):
        """(areas, 'watch' | 'bill' | None)."""
        if not key:
            return [], None
        if key in self.watch:
            return sorted(self.watch[key][0]), "watch"
        if key not in self._lend:
            row = self.conn.execute("SELECT title FROM ie_bills WHERE bill_key=?", (key,)).fetchone()
            areas = []
            if row and row[0]:
                res = filt.filter_item(self.tax, self.wl, roll.strip_offices(row[0]),
                                       title=roll.strip_offices(row[0]))
                areas = sorted(set(res.issue_areas or [])) if res.tier == 1 else []
            self._lend[key] = areas
        return self._lend[key], ("bill" if self._lend[key] else None)


def lead(text, n=EXCERPT):
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[:n - 3].rsplit(" ", 1)[0] + "..."


def classify_speech(tax, wl, sp, bills):
    """(own_areas, areas, areas_from, terms, tier, excerpt): the rule in the
    module docstring."""
    text = roll.strip_offices(sp["text"])
    matches = filt.match_passages(tax, wl, text)
    own, terms, excerpt = filt.aggregate_passages(matches, max_excerpt=EXCERPT)
    if excerpt and len(excerpt) > EXCERPT:
        excerpt = lead(excerpt)
    if own:
        return sorted(own), sorted(own), "own", terms, 1, excerpt
    if sp["words"] < MIN_WORDS:
        return [], [], None, [], None, None
    bkey = sp.get("bill_key")
    lent, source = bills.lends(bkey)
    if [a for a in lent if a not in HIDDEN_AREAS]:
        terms = ["{0}:{1}".format(source, bkey)]
    else:
        lent, source = [], None
        if not bkey and sp.get("title"):
            head = filt.filter_item(tax, wl, roll.strip_offices(sp["title"]),
                                    title=roll.strip_offices(sp["title"]))
            if head.tier == 1 and roll.on_our_ground(head.issue_areas):
                lent, source = sorted(set(head.issue_areas)), "heading"
                terms = list(head.matched_terms or [])
    if not source:
        return [], [], None, [], None, None
    # The member's first substantive paragraph, not "I move amendment No. 1".
    paras = [p for p in (sp["text"] or "").split("\n") if len(p.split()) >= 40]
    return [], lent, source, terms, 2, lead(paras[0] if paras else sp["text"])


def store_speech(conn, sp, cls, party, today):
    own, areas, source, terms, tier, excerpt = cls
    key = "{0}/{1}/{2}".format(record_path(sp["record_uri"]), sp["section"], sp["member_code"])
    conn.execute(
        "INSERT INTO ie_speeches (speech_key, date, chamber, house_key, committee, debate_uri, "
        "debate_section, section_title, debate_type, member_code, speaker, party, role, words, "
        "turns, bill_key, own_areas, areas, areas_from, matched_terms, tier, excerpt, url, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(speech_key) DO UPDATE SET date=excluded.date, chamber=excluded.chamber, "
        "house_key=excluded.house_key, committee=excluded.committee, "
        "section_title=excluded.section_title, debate_type=excluded.debate_type, "
        "speaker=excluded.speaker, party=excluded.party, role=excluded.role, words=excluded.words, "
        "turns=excluded.turns, bill_key=excluded.bill_key, own_areas=excluded.own_areas, "
        "areas=excluded.areas, areas_from=excluded.areas_from, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, excerpt=excluded.excerpt, "
        "url=excluded.url, last_seen=excluded.last_seen",
        (key, sp["date"], sp["chamber"], sp["house_key"], sp["committee"], sp["record_uri"],
         sp["section"], sp["title"], sp["debate_type"], sp["member_code"], sp["speaker"], party,
         sp["role"], sp["words"], sp["turns"], sp.get("bill_key"), ie_store.dumps(own),
         ie_store.dumps(areas), source, ie_store.dumps(terms), tier, excerpt, sp["url"],
         today, today))
    return key


def fetch_week(client, kind, week_of, budget=None):
    """Every debate record of one kind ('house' / 'committee') in one week.
    Returns (records, complete)."""
    start = datetime.date.fromisoformat(week_of)
    end = start + datetime.timedelta(days=6)
    out, skip = [], 0
    while True:
        if budget is not None and budget.exhausted():
            return out, False
        query = urlencode({"chamber_type": kind, "date_start": week_of, "date_end": end.isoformat(),
                           "limit": PAGE, "skip": skip}, safe=":/", quote_via=quote)
        data = client.get_json("{0}debates?{1}".format(API, query), FEED,
                               "debates-{0}-{1}-{2}".format(kind, week_of, skip), archive=False)
        page = (data or {}).get("results")
        if not isinstance(page, list):
            raise ValueError("debates {0} {1}: no results list in the answer".format(kind, week_of))
        out.extend(page)
        if len(page) < PAGE:
            return out, True
        skip += PAGE


def pull(conn, client, today, since=roll.DAIL_START, committees=True, tax=None, wl=None,
         budget=None, log=print):
    """Returns (weeks read, speeches read, stored on our ground, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else roll.empty_watchlist()
    parties = roll.PartyBook(conn)
    bills = Bills(conn, tax, wl)
    weeks_read = total = ours = gaps = 0
    stopped = False
    for feed, kind in KINDS:
        if kind == "committee" and not committees:
            continue
        weeks = ie_store.due_weeks(conn, feed, since, today, REREAD_DAYS)
        for done, week in enumerate(weeks):
            if budget is not None and budget.exhausted():
                log("  " + budget.disclose("{0} weeks ({1} still due)".format(
                    feed, len(weeks) - done), done))
                stopped = True
                break
            try:
                recs, complete = fetch_week(client, kind, week, budget)
            except (FetchError, ValueError) as exc:
                roll._gap(conn, today, "{0} week of {1}: {2}".format(feed, week, str(exc)[:200]))
                ie_store.record_week(conn, feed, week, "gap", 0, 0, 0, {}, today)
                conn.commit()
                log("  [gap] {0} week of {1}: {2}".format(feed, week, str(exc)[:70]))
                gaps += 1
                continue
            if not complete:
                log("  " + budget.disclose("{0} pages (week of {1}, read again next run)".format(
                    feed, week), len(recs)))
                ie_store.record_week(conn, feed, week, "partial", len(recs), 0, 0, {}, today)
                conn.commit()
                stopped = True
                break
            read = stored = 0
            by_area = {}
            for rec in recs:
                try:
                    speeches = list(speeches_in(rec))
                except (KeyError, TypeError, ValueError, AttributeError) as exc:
                    roll._gap(conn, today, "{0} record unreadable: {1}".format(feed, exc))
                    gaps += 1
                    continue
                for sp in speeches:
                    read += 1
                    sp["bill_key"] = bills.key(sp["record_uri"], sp["section"], sp["section_bill"])
                    cls = classify_speech(tax, wl, sp, bills)
                    if not roll.on_our_ground(cls[1]):
                        continue
                    party = parties.at(sp["member_code"], sp["date"],
                                       None if sp["chamber"] == "committee" else sp["house_key"])
                    store_speech(conn, sp, cls, party, today)
                    stored += 1
                    for a in cls[1]:
                        by_area[a] = by_area.get(a, 0) + 1
            ie_store.record_week(conn, feed, week, "read", len(recs), read, stored, by_area, today)
            conn.commit()
            weeks_read += 1
            total += read
            ours += stored
        if stopped:
            break
    return weeks_read, total, ours, gaps


def reclassify(conn, tax=None, log=print):
    """Re-derive what was LENT (a bill's or the watchlist's areas), offline,
    after a taxonomy or watchlist change. A speech's own words are not
    stored (only its excerpt), so own-words rows are re-judged only when
    their week is read again: delete its ie_windows rows to force that."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    bills = Bills(conn, tax, roll.empty_watchlist())
    changed = 0
    for key, bkey, source, areas in conn.execute(
            "SELECT speech_key, bill_key, areas_from, areas FROM ie_speeches "
            "WHERE areas_from IN ('bill', 'watch')").fetchall():
        lent, how = bills.lends(bkey)
        new = ie_store.dumps(lent if how else [])
        changed += new != (areas or "[]")
        conn.execute("UPDATE ie_speeches SET areas=?, areas_from=? WHERE speech_key=?",
                     (new, how, key))
    conn.commit()
    log("ie-debates: reclassified; {0} lent speech(es) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    log("  store: {0} speech(es) on our ground ({1} on their own words, {2} with a bill, {3} in "
        "committee); {4} week(s) read, {5} member speech(es) read in them".format(
            n("SELECT COUNT(*) FROM ie_speeches"),
            n("SELECT COUNT(*) FROM ie_speeches WHERE areas_from='own'"),
            n("SELECT COUNT(*) FROM ie_speeches WHERE bill_key IS NOT NULL"),
            n("SELECT COUNT(*) FROM ie_speeches WHERE chamber='committee'"),
            n("SELECT COUNT(*) FROM ie_windows WHERE feed LIKE 'debates-%' AND status='read'"),
            n("SELECT COALESCE(SUM(items),0) FROM ie_windows WHERE feed LIKE 'debates-%' "
              "AND status='read'")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--since", default=roll.DAIL_START)
    ap.add_argument("--no-committees", action="store_true")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="list the due weeks; fetch nothing")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        return 0
    if args.dry_run:
        for feed, _kind in KINDS:
            weeks = ie_store.due_weeks(conn, feed, args.since, today, REREAD_DAYS)
            print("ie-debates: {0}: {1} week(s) due, newest {2}, oldest {3}. Nothing fetched.".format(
                feed, len(weeks), weeks[0] if weeks else "-", weeks[-1] if weeks else "-"))
        return 0
    client = HttpClient(raw_dir=args.raw_dir)
    weeks, total, ours, gaps = pull(conn, client, today, since=args.since,
                                    committees=not args.no_committees,
                                    budget=drain.Budget(args.budget_seconds))
    print("ie-debates: {0} week(s) read, {1} member speech(es), {2} on our ground, "
          "{3} gap(s)".format(weeks, total, ours, gaps))
    if not gaps:
        ie_store.stamp(conn, HEARTBEAT, today, "step heartbeat: tools/ie_debates.py")
        conn.commit()
    summary(conn)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
