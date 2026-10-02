#!/usr/bin/env python3
"""Who said what on the floor of the Senate of Canada, on our issues.

    python3 tools/ca_senate_debates.py                  # the newest unread sittings of 45-1
    python3 tools/ca_senate_debates.py --session 43-2 --limit 5
    python3 tools/ca_senate_debates.py --session 43-2 --sittings 28,29,30
    python3 tools/ca_senate_debates.py --dry-run        # parse, resolve and match; store nothing
    python3 tools/ca_senate_debates.py --backfill --limit 400 --budget-seconds 2700
    python3 tools/ca_senate_debates.py --db /tmp/ca.db

GROUNDWORK (2 October 2026). Nothing schedules this yet: it joins ca-weekly
after ca_hansard, and coverage.py needs its entry, the day it is scheduled.

THE SOURCE IS HTML, one page per sitting, keyless:
  * the session index /en/in-the-chamber/debates/<P-S> links every sitting.
    ITS HREFS USE BACKSLASHES (/en\\content\\sen\\chamber\\432\\debates\\
    029db_2021-02-17-e) and are normalised here; the one forward-slash link
    on the page is the "latest sitting" box, the latest sitting OVERALL, and
    is dropped (it is in its own session's calendar with backslashes too).
  * the sitting /en/content/sen/chamber/<PS>/debates/<NNN>db_<date>-e.
URLS COME ONLY FROM THE INDEX. A wrong number/date pair returns 200 with a
47 KB page and an empty <title> (the soft-404, measured 2 October 2026), so
a URL is never built from a number, and a page with no "THE SENATE" heading
or no interventions is a GAP -- recorded, retried next run -- never an empty
sitting. Sittings are read by key, so a gap never blocks the next one; three
gaps in a row stop the session (a redesign looks exactly like that).

WHAT A SPEECH IS. A paragraph opening with a bold speaker label --
<b>Hon. Donald Neil Plett (Leader of the Opposition):</b> -- and the
paragraphs after it up to the next label or heading. Two markup generations:
2010 wraps every paragraph in <span lang="en-ca"> and splits a label over
tags (<b>The Hon. the Speaker</b><i> pro tempore</i><b>:</b>); a senator
who MOVES has no colon (<b>Hon. Kristopher Wells</b> moved third reading of
Bill C-9). Headings: <h1> the rubric (ORDERS OF THE DAY), <h2> the subject
("Criminal Code"), <h3> the stage ("Bill to Amend--Third Reading"). Inline
(1500) markers every ten minutes give the time, as Hansard's Timestamp does.

THE BILL is not in the headings. It is read, as ca_hansard.subject_bill
reads the House's, from the procedural text before the section's first
speech ("On the Order: ... third reading of Bill C-7, An Act to amend the
Criminal Code (medical assistance in dying), as amended") or from a mover's
own opening sentence -- never from a speech, which can cite any bill.

WHO SPOKE. The page carries no ids. A senator's first label in a sitting is
"Hon. First [Middle] Last (role)", resolved against ca_senators ("Last,
First Middle") on surname + any given name ("Hon. Margaret Dawn Anderson" is
"Anderson, Dawn"), a UNIQUE hit only; later labels are "Senator Last", or
"Senator K. Last" where two share a surname, resolved WITHIN THE SITTING to
the Hon. label already seen (learn-then-resolve, both passes over the whole
sitting, as ca_hansard.store_sitting does). ca_senators is built from
recorded votes, which the Senate publishes only from 42-1, so senators who
left before December 2015 do not resolve: they are stored with person_id
NULL and speaker_key, the folded full name, consistent across sittings.
NEVER IS AN ID MINTED FROM A NAME. A "Senator Last" with no Hon. label in
the sitting keeps speaker_key NULL too: a surname alone is not an identity.

NOT SENATORS. The chair and the collective labels (The Hon. the Speaker
[pro tempore], Hon. Senators, Some Hon. Senators, An Hon. Senator, the Chair
of a Committee of the Whole) are COUNTED, NOT STORED. A minister answering
in the Senate is labelled "..., M.P."; that speech, on our ground, is stored
with the House PersonId only if the name resolves UNIQUELY in ca_members,
else person_id NULL -- and no speaker_key, which is for senators. Witnesses
in Committee of the Whole (no Hon./Senator label) are stored unattributed.
None of these ever writes ca_members or ca_senators, and none reaches a 5CA:
a Senate sheet lists only ca_senators, a Commons sheet only chamber='commons'.

MATCHING, per passage (src/filter.match_passages) against the English
taxonomy plus config/watchlist-ca.yaml exactly as ca_hansard does, with the
title passage h2 + h3 plus the bill's LONG TITLE from ca_bills, joined on
(parliament, session, number) -- NEVER on the number alone: the scope's probe
tagged a 2010 Museums Act debate as areas 6 and 7 from a later session's
bill of the same number. "Criminal Code -- Bill to Amend--Third Reading" says
nothing about C-9; with its long title the 4 June 2026 sitting went from 9
speeches on our ground to 21. ca_store.speech_title builds that passage for
this collector and for tools/ca_retag.py, so a retag re-reads what was read.

STORAGE. Only speeches on our ground go into ca_speeches, with
chamber='senate', forum='floor', speech_id 'sen-<PS>-<NNN>-<seq>' (seq is
the intervention's place in the sitting, chair included, so it is stable).
Every sitting READ gets a ca_senate_sittings row with its totals -- NOT
ca_sittings, whose MAX(number) is the House frontier in
ca_hansard.next_sitting: Senate sitting 79 would move it.

A BACKFILL (--backfill: every session since 40-3, ~1,170 sittings, ~350 MB,
~25 minutes at a request a second) is announced and hand-dispatched, under
the Bundestag rule. ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import importlib.util
import json
import os
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402


def _load_hansard():
    spec = importlib.util.spec_from_file_location(
        "ca_hansard", os.path.join(ROOT, "tools", "ca_hansard.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


han = _load_hansard()

FEED = "ca-senate-debates"
CURRENT_SESSION = "45-1"
# Every session sencanada.ca publishes debates for since March 2010, oldest
# first (the index's own session menu, read 2 October 2026).
SESSIONS = ("40-3", "41-1", "41-2", "42-1", "43-1", "43-2", "44-1", "45-1")
BASE = "https://sencanada.ca"
INDEX = BASE + "/en/in-the-chamber/debates/{0}"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")
DEFAULT_LIMIT = 10          # 2-3 sittings a week; ten covers a missed fortnight
PAUSE = 1.0                 # seconds between requests to sencanada.ca
MAX_RUN_OF_GAPS = 3

TAG = re.compile(r"<[^>]+>")
HREF = re.compile(r'href="([^"]*)"', re.I)
SITTING_PATH = re.compile(
    r"^/en/content/sen/chamber/(\d{3,4})/debates/(\d{3})db_(\d{4}-\d{2}-\d{2})-e$", re.I)
TOKEN = re.compile(r"<(h[1-4]|p)\b[^>]*>(.*?)</\1\s*>", re.S | re.I)
# Case-blind tags, case-SENSITIVE words: "The Senate" is also an ordinary subject.
THE_SENATE = re.compile(r"<[hH]2\b[^>]*>(?:\s|<[^>]+>)*THE SENATE(?:\s|<[^>]+>)*</[hH]2\s*>", re.S)
CONTENT_END = re.compile(r'id="backtotop"|<footer\b', re.I)
# The opening bold run of a paragraph, after any wrapper (<span lang="en-ca">).
LEAD = re.compile(r"^\s*(?:<(?!/?b\b)[^>]*>\s*)*<b\b[^>]*>(.*?)</b\s*>", re.S | re.I)
# A label split over tags: <i> pro tempore</i><b>:</b>, or a trailing <b>,</b>.
MORE = re.compile(r"^\s*(?:<i\b[^>]*>([^<]{0,40})</i\s*>\s*)?<b\b[^>]*>(\s*[:,]\s*)</b\s*>",
                  re.S | re.I)
SPEAKERISH = re.compile(r"^(?:The\s+Hon\.|Hon\.|Senator\b|Some\s+Hon\.|An\s+Hon\.|"
                        r"The\s+(?:Acting\s+)?(?:Speaker|Chair))", re.I)
CHAIR = re.compile(r"^The\s+(?:Hon\.\s+the\s+)?(?:Acting\s+)?(?:Speaker|Chair)\b", re.I)
# "Hon Senators", no full stop, on 15 March and 16 February 2021.
COLLECTIVE = re.compile(r"^(?:(?:Some|An)\s+)?(?:Hon\.?\s+|Honourable\s+)?Senators?$", re.I)
SENATOR_LABEL = re.compile(r"^Senator\s+(?:(?P<initial>[A-Z])\.\s+)?(?P<surname>[^()]+?)\s*(?:\(.*\))?$")
TIME_MARK = re.compile(r"^\((\d{2})(\d{2})\)$")
MET_AT = re.compile(r"The Senate met at (\d{1,2})(?::(\d{2}))?\s*([ap])\.m\.", re.I)
NOT_TEXT = re.compile(r"^\[(?:Translation|English|French)\]$", re.I)


def _clean(fragment):
    return " ".join(htmlmod.unescape(TAG.sub(" ", fragment or "")).split())


def ps_code(parl, sess):
    return "{0}{1}".format(parl, sess)


def namefold(text):
    """han.fold, with full stops as spaces: 'Percy E. Downe' -> 'percy e downe'."""
    return " ".join(han.fold(text).replace(".", " ").split())


# ---------------------------------------------------------------- the index

def parse_index(page, session):
    """[{key, url, number, date}] for every sitting the session index links,
    oldest first. Only backslash hrefs: the calendar. The forward-slash
    "latest sitting" link is the latest sitting of ANY session and is dropped,
    as is anything outside this session's chamber folder."""
    parl, sess = han.parse_session(session)
    want = ps_code(parl, sess)
    out = {}
    for href in HREF.findall(page or ""):
        if "\\" not in href:
            continue
        path = htmlmod.unescape(href).replace("\\", "/")
        hit = SITTING_PATH.match(path)
        if not hit or hit.group(1) != want:
            continue
        key = "{0}/{1}db_{2}".format(hit.group(1), hit.group(2), hit.group(3))
        out[key] = {"key": key, "url": BASE + path, "number": int(hit.group(2)),
                    "date": hit.group(3), "parliament": parl, "session": sess}
    return sorted(out.values(), key=lambda s: (s["number"], s["date"]))


# -------------------------------------------------------------- the sitting

def split_label(body):
    """(label, rest_html, had_colon) if the paragraph opens with a speaker
    label, else None. A mover's label has no colon: "<b>Hon. X</b> moved"."""
    hit = LEAD.match(body or "")
    if not hit:
        return None
    label, rest = hit.group(1), body[hit.end():]
    while not _clean(label).endswith(":"):
        more = MORE.match(rest)
        if not more:
            break
        label += " " + (more.group(1) or "") + more.group(2)
        rest = rest[more.end():]
    text = _clean(label)
    if not text or len(text) > 200:
        return None
    if not (text.endswith(":") or SPEAKERISH.match(text)):
        return None            # emphasis, not a speaker ("<b>Fact</b>")
    return " ".join(text.rstrip(":, ").split()), rest, text.endswith(":")


def label_kind(label):
    """'chair', 'collective', 'member' (an MP: a minister in the Senate),
    'senator' (Hon. or Senator), or 'other' (a witness)."""
    if CHAIR.match(label):
        return "chair"
    if COLLECTIVE.match(label):
        return "collective"
    if re.search(r"\bM\.P\.", label):
        return "member"
    if label.startswith("Hon.") or SENATOR_LABEL.match(label):
        return "senator"
    return "other"


def parse_sitting(page):
    """(problem, [intervention dicts]). problem is None for a readable page,
    else why it is a gap -- a soft-404, a page with no THE SENATE heading, or
    one with no interventions."""
    page = page or ""
    title = re.search(r"<title[^>]*>(.*?)</title\s*>", page, re.S | re.I)
    if not title or not _clean(title.group(1)):
        return "empty <title> (the soft-404)", []
    start = THE_SENATE.search(page)
    if not start:
        return "no THE SENATE heading (markup changed?)", []
    end = CONTENT_END.search(page, start.end())
    region = page[start.end():end.start() if end else len(page)]
    ivs = []
    state = {"h1": None, "h2": None, "h3": None, "time": None}
    met = MET_AT.search(_clean(region[:4000]))
    if met:
        hour = int(met.group(1)) % 12 + (12 if met.group(3).lower() == "p" else 0)
        state["time"] = "{0:02d}:{1}".format(hour, met.group(2) or "00")
    section = {"pre": [], "bill": None, "h2_bill": None, "spoken": False}
    cur = None

    def new_section(keep_h2_bill):
        prior = section["bill"] or section["h2_bill"]
        section.update(pre=[], bill=None, spoken=False,
                       h2_bill=prior if keep_h2_bill else None)

    def bill_from(text):
        hit = han.BILL.search(text or "")
        return "{0}-{1}".format(hit.group(1), hit.group(2)) if hit else None

    for m in TOKEN.finditer(region):
        tag, body = m.group(1).lower(), m.group(2)
        if tag == "h1":
            state.update(h1=_clean(body) or None, h2=None, h3=None)
            new_section(False)
            cur = None
            continue
        if tag == "h2":
            state.update(h2=_clean(body) or None, h3=None)
            new_section(False)
            cur = None
            continue
        if tag in ("h3", "h4"):
            state["h3"] = _clean(body) or None
            new_section(True)      # a stage under the same subject may inherit its bill
            cur = None
            continue
        text = _clean(body)
        tm = TIME_MARK.match(text)
        if tm:
            state["time"] = "{0}:{1}".format(tm.group(1), tm.group(2))
            continue
        if not text or NOT_TEXT.match(text):
            continue
        lab = split_label(body)
        if lab:
            label, rest, colon = lab
            rest_text = _clean(rest)
            if not section["spoken"]:
                # The procedural text before the section's first speech, and a
                # mover's own opening sentence ("moved third reading of Bill C-9").
                section["bill"] = bill_from(" ".join(section["pre"]))
                if not section["bill"] and not colon and re.match(
                        r"^(?:moved|introduced|presented|tabled)\b", rest_text):
                    section["bill"] = bill_from(rest_text.split(".")[0])
                section["spoken"] = True
            subject = " — ".join(x for x in (state["h2"], state["h3"]) if x) or None
            cur = {"seq": len(ivs) + 1, "label": label, "kind": label_kind(label),
                   "rubric": state["h1"], "subject": subject, "h2": state["h2"],
                   "bill": section["bill"] or section["h2_bill"], "time": state["time"],
                   "paras": [rest_text] if rest_text else []}
            ivs.append(cur)
            continue
        if not section["spoken"]:
            section["pre"].append(text)
        if cur is not None:
            cur["paras"].append(text)
    for iv in ivs:
        iv["text"] = "\n".join(iv.pop("paras"))
    if not ivs:
        return "no interventions parsed (markup changed?)", []
    return None, ivs


# ------------------------------------------------------------ who spoke

class Senators:
    """ca_senators by (first name, surname), folded. Only a UNIQUE hit resolves."""

    def __init__(self, conn):
        self.by = {}
        for pid, name in conn.execute("SELECT person_id, name FROM ca_senators"):
            last, _, first = (name or "").partition(",")
            first_toks = namefold(first).split()
            if first_toks and last.strip():
                self.by.setdefault((first_toks[0], namefold(last)), set()).add(pid)

    def resolve(self, full_name):
        """Every split of the label into given names + surname, with ANY
        given name as the one the Senate files under: the floor says "Hon.
        Margaret Dawn Anderson", the vote pages "Anderson, Dawn"."""
        toks = namefold(full_name).split()
        hits = set()
        for k in range(1, len(toks)):
            surname = " ".join(toks[k:])
            for given in toks[:k]:
                hits |= self.by.get((given, surname), set())
        return next(iter(hits)) if len(hits) == 1 else None


class Members:
    """ca_members by folded full name: for a minister answering in the Senate."""

    def __init__(self, conn):
        self.by = {}
        for pid, name in conn.execute("SELECT person_id, name FROM ca_members"):
            if name:
                self.by.setdefault(namefold(name), set()).add(pid)

    def resolve(self, name):
        hits = self.by.get(namefold(name)) or set()
        return next(iter(hits)) if len(hits) == 1 else None


def hon_name(label):
    """'Hon. Donald Neil Plett (Leader of the Opposition)' -> 'Donald Neil Plett'.

    The role is the bracket at the END; a bracket inside the name is a
    nickname and is dropped: 'Hon. Flordeliz (Gigi) Osler' -> 'Flordeliz
    Osler' (28 September 2026). A minister's label ends at its first comma."""
    if not (label or "").startswith("Hon."):
        return None
    name = label[4:].split(",")[0]
    name = re.sub(r"\s*\([^()]*\)\s*$", "", name)
    name = re.sub(r"\([^()]*\)", " ", name)
    return " ".join(name.split()) or None


def reresolve(conn, senators=None):
    """Give a person_id to stored Senate speeches whose speaker_key now
    resolves: a senator appointed since the last recorded vote is missing
    from ca_senators until they vote (28 September 2026: four new senators
    spoke). The same unique-hit rule; a speaker_key is never an id itself.
    Returns how many rows gained one."""
    senators = senators or Senators(conn)
    n = 0
    for key in [r[0] for r in conn.execute(
            "SELECT DISTINCT speaker_key FROM ca_speeches WHERE chamber='senate' "
            "AND person_id IS NULL AND speaker_key IS NOT NULL")]:
        pid = senators.resolve(key)
        if pid:
            n += conn.execute("UPDATE ca_speeches SET person_id=? WHERE chamber='senate' "
                              "AND person_id IS NULL AND speaker_key=?", (pid, key)).rowcount
    conn.commit()
    return n


def attribute(ivs, senators, members):
    """Set person_id and speaker_key on every intervention, in place.

    Pass 1 learns every Hon. label in the sitting; pass 2 resolves each
    "Senator [I.] Last" to the one Hon. label seen with that surname (and
    initial). Two candidates and no initial resolves nothing."""
    hon = {}                                   # speaker_key -> person_id or None
    by_surname = {}                            # folded surname -> {speaker_key}
    for iv in ivs:
        iv["person_id"] = iv["speaker_key"] = None
        if iv["kind"] == "member":
            name = hon_name(iv["label"]) or iv["label"].split(",")[0]
            iv["person_id"] = members.resolve(name)
        elif iv["kind"] == "senator" and iv["label"].startswith("Hon."):
            name = hon_name(iv["label"])
            if not name:
                continue
            key = namefold(name)
            if key not in hon:
                hon[key] = senators.resolve(name)
                toks = key.split()
                for k in range(1, len(toks)):
                    by_surname.setdefault(" ".join(toks[k:]), set()).add(key)
            iv["speaker_key"], iv["person_id"] = key, hon[key]
    for iv in ivs:
        if iv["kind"] != "senator" or iv["label"].startswith("Hon."):
            continue
        hit = SENATOR_LABEL.match(iv["label"])
        if not hit:
            continue
        cands = by_surname.get(namefold(hit.group("surname")), set())
        if hit.group("initial"):
            cands = {c for c in cands if c.startswith(hit.group("initial").lower())}
        if len(cands) == 1:
            key = next(iter(cands))
            iv["speaker_key"], iv["person_id"] = key, hon[key]
    return ivs


# ------------------------------------------------------------- storing

def long_title(conn, parl, sess, number):
    """The bill's long title for THIS session only -- never by number alone."""
    if not number:
        return None
    row = conn.execute("SELECT long_title FROM ca_bills WHERE parliament=? AND session=? "
                       "AND number=?", (parl, sess, number)).fetchone()
    return row[0] if row else None


def store_sitting(conn, sitting, ivs, tax, wl, today, senators=None, members=None,
                  write=True):
    """Store one sitting's speeches on our ground and its totals row.
    Returns the totals. write=False (the dry run) computes them and writes nothing."""
    parl, sess, number = sitting["parliament"], sitting["session"], sitting["number"]
    attribute(ivs, senators or Senators(conn), members or Members(conn))
    by_title = han.bills_by_title(conn, parl, sess)
    titles = {}
    chair = stored = unresolved = 0
    speakers, resolved = set(), set()
    for iv in ivs:
        if iv["kind"] in ("chair", "collective"):
            chair += 1
            continue
        who = iv["speaker_key"] or iv["person_id"] or iv["label"]
        speakers.add(who)
        if iv["person_id"]:
            resolved.add(who)
        bill = iv["bill"] or (by_title.get(han.fold(iv["h2"])) if iv["h2"] else None)
        if bill not in titles:
            titles[bill] = long_title(conn, parl, sess, bill)
        title = ca_store.speech_title(iv["subject"], bill, titles[bill])
        areas, terms, excerpt = filt.aggregate_passages(
            filt.match_passages(tax, wl, iv["text"] or "", title=title))
        if not han.on_our_ground(areas):
            continue
        stored += 1
        unresolved += iv["person_id"] is None
        if not write:
            continue
        conn.execute(
            "INSERT INTO ca_speeches (speech_id, sitting_key, date, time, rubric, subject, "
            "bill_number, kind, db_id, person_id, speaker, party, text, areas, matched_terms, "
            "excerpt, first_seen, chamber, forum, committee, speaker_key) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(speech_id) DO UPDATE SET text=excluded.text, "
            "person_id=COALESCE(excluded.person_id, ca_speeches.person_id), "
            "speaker_key=COALESCE(excluded.speaker_key, ca_speeches.speaker_key), "
            "bill_number=excluded.bill_number, areas=excluded.areas, "
            "matched_terms=excluded.matched_terms, excerpt=excluded.excerpt",
            ("sen-{0}-{1:03d}-{2}".format(ps_code(parl, sess), number, iv["seq"]),
             sitting["key"], sitting["date"], iv["time"], iv["rubric"], iv["subject"], bill,
             None, None, iv["person_id"], iv["label"], None, iv["text"],
             json.dumps(areas), json.dumps(terms), excerpt, today,
             "senate", "floor", None, iv["speaker_key"]))
    totals = {"interventions": len(ivs), "chair": chair, "speakers": len(speakers),
              "members_resolved": len(resolved), "on_ground": stored, "unresolved": unresolved}
    if write:
        conn.execute(
            "INSERT OR REPLACE INTO ca_senate_sittings (sitting_key, parliament, session, "
            "number, date, url, interventions, chair, speakers, members_resolved, on_ground, "
            "unresolved, read_on) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sitting["key"], parl, sess, number, sitting["date"], sitting["url"], len(ivs),
             chair, len(speakers), len(resolved), stored, unresolved, today))
        conn.commit()
    return totals


def read_keys(conn, parl, sess):
    return {r[0] for r in conn.execute(
        "SELECT sitting_key FROM ca_senate_sittings WHERE parliament=? AND session=?",
        (parl, sess))}


def pull(conn, client, today, sessions=(CURRENT_SESSION,), limit=DEFAULT_LIMIT,
         tax=None, wl=None, log=print, budget=None, dry_run=False, newest_first=True,
         sleep=time.sleep, pause=PAUSE, only=None):
    """Read the unread sittings of each session. Returns
    {read, stored, gaps, listed, pending}: pending is what a cap left unread.
    `only` restricts a run to these sitting numbers -- still as the index
    links them, never built from the number."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    senators, members = Senators(conn), Members(conn)
    out = {"read": 0, "stored": 0, "gaps": 0, "listed": 0, "pending": 0, "reresolved": 0}
    if not dry_run:
        out["reresolved"] = reresolve(conn, senators)
        if out["reresolved"]:
            log("  {0} stored speech(es) now resolve to a senator".format(out["reresolved"]))
    gaps = []
    fetched = [0]

    def get(url, slug):
        if fetched[0]:
            sleep(pause)
        fetched[0] += 1
        return client.get_text(url, FEED, slug, archive=False)

    stop = False
    for n_done, session in enumerate(sessions):
        parl, sess = han.parse_session(session)
        if stop:
            log("  not reached this run: {0} -- disclosed, not silent".format(
                ", ".join(sessions[n_done:])))
            break
        try:
            sittings = parse_index(get(INDEX.format(session), "index-" + session), session)
        except FetchError as exc:
            gaps.append("index {0}: {1}".format(session, exc))
            log("  [gap] index {0}: {1}".format(session, str(exc)[:70]))
            continue
        if not sittings:
            gaps.append("index {0}: no sitting links (markup changed?)".format(session))
            log("  [gap] index {0} linked no sittings".format(session))
            continue
        held = read_keys(conn, parl, sess)
        todo = [s for s in sittings if s["key"] not in held
                and (not only or s["number"] in only)]
        if newest_first:
            todo.reverse()
        out["listed"] += len(sittings)
        log("  {0}: {1} sitting(s) listed, {2} already read, {3} to read{4}".format(
            session, len(sittings), sum(1 for s in sittings if s["key"] in held), len(todo),
            " (--sittings)" if only else ""))
        run_of_gaps = 0
        for i, s in enumerate(todo):
            if limit is not None and out["read"] >= limit:
                out["pending"] += len(todo) - i
                log("  cap ({0}) reached; {1} sitting(s) of {2} left -- disclosed, "
                    "not silent".format(limit, len(todo) - i, session))
                stop = True
                break
            if budget is not None and budget.exhausted():
                out["pending"] += len(todo) - i
                log(budget.disclose("Senate sittings", out["read"]))
                stop = True
                break
            out["read"] += 1
            try:
                problem, ivs = parse_sitting(get(s["url"], "sitting-" + s["key"].replace("/", "-")))
            except FetchError as exc:
                problem, ivs = str(exc), []
            if problem:
                gaps.append("{0}: {1}".format(s["key"], problem))
                log("  [gap] {0}: {1}".format(s["key"], problem[:80]))
                run_of_gaps += 1
                if run_of_gaps >= MAX_RUN_OF_GAPS:
                    out["pending"] += len(todo) - i - 1
                    log("  {0} gaps in a row on {1}: stopping the session "
                        "(a redesign looks like this)".format(run_of_gaps, session))
                    break
                continue
            run_of_gaps = 0
            t = store_sitting(conn, s, ivs, tax, wl, today, senators, members,
                              write=not dry_run)
            out["stored"] += t["on_ground"]
            log("  {0} {1}: {2} interventions, {3} chair/collective, {4} speaker(s) "
                "({5} resolved), {6} on our ground{7}".format(
                    s["key"], s["date"], t["interventions"], t["chair"], t["speakers"],
                    t["members_resolved"], t["on_ground"],
                    ", {0} unattributed".format(t["unresolved"]) if t["unresolved"] else ""))
    out["gaps"] = len(gaps)
    if gaps and not dry_run:
        db.record_gaps(conn, FEED, gaps, edition=today)
    return out


def dry_run_store(path):
    """An in-memory store holding READ-ONLY copies of what resolution and
    resume need from `path` (senators, members, bills, sittings read). The dry
    run writes nothing anywhere; without a store it resolves nobody."""
    conn = ca_store.ensure_schema(db.init_db(db.connect(":memory:")))
    if not os.path.exists(path):
        return conn
    src = sqlite3.connect("file:{0}?mode=ro".format(path), uri=True)
    try:
        for table in ("ca_senators", "ca_members", "ca_bills", "ca_senate_sittings"):
            try:
                cur = src.execute("SELECT * FROM {0}".format(table))
            except sqlite3.OperationalError:
                continue          # an older store without the table
            cols = [d[0] for d in cur.description]
            mine = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
            keep = [i for i, c in enumerate(cols) if c in mine]
            conn.executemany("INSERT OR IGNORE INTO {0} ({1}) VALUES ({2})".format(
                table, ", ".join(cols[i] for i in keep), ",".join("?" * len(keep))),
                ([row[i] for i in keep] for row in cur))
    finally:
        src.close()
    conn.commit()
    return conn


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=CURRENT_SESSION)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="sittings per run")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="parse, resolve and match against a read-only copy; store nothing")
    ap.add_argument("--sittings", help="only these sitting numbers of --session, e.g. 28,29,30 "
                                       "(taken from the index, never built)")
    ap.add_argument("--backfill", action="store_true",
                    help="every unread sitting of every session since 40-3, oldest first "
                         "(announced, from CI)")
    args = ap.parse_args()
    han.parse_session(args.session)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    conn = (dry_run_store(args.db) if args.dry_run
            else ca_store.ensure_schema(db.init_db(db.connect(args.db))))
    sessions = SESSIONS if args.backfill else (args.session,)
    out = pull(conn, client, today, sessions=sessions, limit=args.limit,
               budget=drain.Budget(args.budget_seconds), dry_run=args.dry_run,
               newest_first=not args.backfill,
               only={int(x) for x in args.sittings.split(",")} if args.sittings else None)
    print("ca-senate-debates: {0} sitting(s) read of {1} listed, {2} speech(es) on our "
          "ground, {3} gap(s){4}{5}.".format(
              out["read"], out["listed"], out["stored"], out["gaps"],
              "; {0} left for later runs".format(out["pending"]) if out["pending"] else "",
              " (dry run: nothing stored)" if args.dry_run else ""))
    if not args.dry_run:
        n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        print("  store: {0} Senate sitting(s) read, {1} Senate speech(es), {2} unattributed".format(
            n("SELECT COUNT(*) FROM ca_senate_sittings"),
            n("SELECT COUNT(*) FROM ca_speeches WHERE chamber='senate'"),
            n("SELECT COUNT(*) FROM ca_speeches WHERE chamber='senate' AND person_id IS NULL")))
    conn.close()
    return 1 if out["gaps"] else 0


if __name__ == "__main__":
    sys.exit(main())
