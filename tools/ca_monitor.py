#!/usr/bin/env python3
"""The Canada federal edition: its own document, and a DM to Christopher.

    python3 tools/ca_monitor.py --edition              # write editions/ca-monitor-<date>.md
    python3 tools/ca_monitor.py --edition --dm         # and DM the summary
    python3 tools/ca_monitor.py --print                # render to stdout, write nothing
    python3 tools/ca_monitor.py --print --date 2026-10-09 --db /tmp/scratch.db

Christopher, 9 October 2026: a Canada federal edition. Like the US and Irish
editions it goes to him alone, as a DM (U05LJP0BT61); nothing posts to a
channel. Modelled on tools/us_monitor.py and tools/ie_monitor.py, and it
reads only what the Canada weekly collects (docs/canada-scope.md).

WHAT LEADS. Parliament moves our ground through recorded divisions (House
and Senate), bills completing stages, and new bills; petitions, debate,
committee witnesses, the Canada Gazette and the Supreme Court are the
context around them. The edition leads with the week and says so plainly
when nothing on our ground was divided on.

NO VERDICTS. A division carries the House's own result, its tally and its
party split, never "a win" or "a defeat". What a Yea meant is a signed human
reading in config/ca_stance.yaml (tools/ca_5ca.py applies it). The 5CA
section here says only whether a reading exists and is signed: it never
states a direction, signed or not.

INHERITED AREAS ARE MARKED. A Commons division is classified on its own
subject plus the areas of a watched bill key (config/watchlist-ca.yaml); a
Senate vote also on its bill's long title. So every division line says
whether its own text matched or only its bill did, re-read here from the
subject alone.

SCORES ARE OPTIONAL. tools/ca_triage.py scores petitions and Supreme Court
judgments (0-3 and a why-line). Those are ranked by score and shown at 2 or
more; an unscored one is shown only on a tier-1 match (never a raw tier-2
keyword hit), and says it is unscored. Everything else (divisions, bills,
speeches, testimony, the Gazette) is unscored and says so. The edition
renders whole with no judge run at all (CLAUDE.md: TRIAGE=stub).

A SESSION ENDS. The current session is the newest in the store. A bill of an
earlier session that never had Royal Assent fell at that session's
prorogation or dissolution whatever its stored status says (the hard rule:
a status is not a life sign).

Read-only on the store.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db  # noqa: E402

TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")
STANCE = os.path.join(ROOT, "config", "ca_stance.yaml")
OVERRIDES = os.path.join(ROOT, "config", "stance_overrides.yaml")
REPO = "https://github.com/thejoycething-code/parl-monitor/blob/main/"
HIDDEN_AREAS = (11,)
WEEK_DAYS = 7
MONTH_DAYS = 30
RECENT_DAYS = 21              # a past date stays on the list this long
FALLEN_SECTION_DAYS = 60      # a new session lists the last one's falls this long
LATEST_GROUPS = 6             # a quiet month still shows the latest divisions
SPEECH_LINES = 15
PETITION_LINES = 12
SHOW_SCORE = 2                # a scored petition or judgment is shown at this or above

# Fixed dates and what each means. The statutory ones say so.
DATES = (
    ("2027-03-17", "MAID for mental illness as the sole underlying condition comes into force, "
                   "under the delay C-62 enacted in 2024, unless Parliament acts again"),
    ("2029-10-15", "The fixed date of the next general election (Canada Elections Act s.56.1: "
                   "the third Monday of October in the fourth calendar year after the 2025 "
                   "election), earlier if the House is dissolved first. Every bill not given "
                   "Royal Assent dies at the dissolution"),
)
PROROGATION_NOTE = ("At a prorogation, government bills die unless the House reinstates them by "
                    "motion, and private members' bills carry over at their stage (Standing "
                    "Order 86.1); at a dissolution every bill dies. The edition treats a bill of "
                    "an earlier session without Royal Assent as fallen, whatever its status says.")

HONESTY = (
    "> **How to read this edition.** Areas come from the shared taxonomy (v{0}), with Canadian "
    "names it cannot read added by key (config/watchlist-ca.yaml); its Canadian terms have not "
    "yet been reviewed by anyone who campaigns in Canada. Bills are matched on their long and "
    "short titles. A division can take its bill's areas, so every division says whether its "
    "**own** text matched or only its **bill** did. Results, tallies and party splits are the "
    "record; whether a vote helped or hurt is a human call and is never made here. {1}"
)

PARTY_SHORT = {"Liberal": "Lib", "Lib.": "Lib", "Conservative": "CPC", "Bloc Québécois": "BQ",
               "NDP": "NDP", "Green Party": "GP", "Independent": "Ind"}
PARTY_ORDER = ("Lib", "CPC", "BQ", "NDP", "GP", "Ind", "ISG", "CSG", "PSG", "C", "GRO",
               "Non-affiliated")
CHAMBER = {"commons": "House", "senate": "Senate"}


def area_names():
    from src import intel
    return intel.area_names(TAXONOMY)


def taxonomy_version():
    import yaml
    with open(TAXONOMY, encoding="utf-8") as fh:
        return str(yaml.safe_load(fh).get("version"))


def oneline(text):
    """One line, and no em dashes (CLAUDE.md: rendered editions carry none)."""
    text = (text or "").replace(" — ", " - ").replace("—", "-")
    return " ".join(text.split())


def clip(text, n):
    text = oneline(text)
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def visible(areas_json):
    try:
        return [a for a in json.loads(areas_json or "[]") if a not in HIDDEN_AREAS]
    except (TypeError, ValueError):
        return []


def names_of(areas, names):
    return ", ".join(names.get(a, str(a)) for a in areas)


def score_mark(score):
    return "**[{0}]**".format(score) if score is not None else "·"


def day_of(value):
    return (value or "")[:10]


def long_date(iso):
    d = datetime.date.fromisoformat(iso[:10])
    return "{0} {1}".format(d.day, d.strftime("%B %Y"))


def lower_first(text):
    text = oneline(text) or "?"
    return text[:1].lower() + text[1:]


def ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "{0}{1}".format(n, suffix)


# --- links -------------------------------------------------------------------

def bill_url(parliament, session, number):
    return "https://www.parl.ca/legisinfo/en/bill/{0}-{1}/{2}".format(
        parliament, session, (number or "").lower())


def division_url(r):
    if r["chamber"] == "senate":
        return "https://sencanada.ca/en/in-the-chamber/votes/details/{0}/{1}-{2}".format(
            r["number"], r["parliament"], r["session"])
    return "https://www.ourcommons.ca/members/en/votes/{0}/{1}/{2}".format(
        r["parliament"], r["session"], r["number"])


def hansard_url(sitting_key):
    parl, sess, number = sitting_key.split("-")
    return "https://www.ourcommons.ca/DocumentViewer/en/{0}-{1}/house/sitting-{2}/hansard".format(
        parl, sess, number)


def petition_url(petition_id):
    return "https://www.ourcommons.ca/petitions/en/Petition/Details?Petition={0}".format(petition_id)


# --- the store ---------------------------------------------------------------

def rows(conn, sql, params=()):
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []


def count(conn, sql, params=()):
    try:
        row = conn.execute(sql, params).fetchone()
        return (row[0] or 0) if row else 0
    except sqlite3.OperationalError:
        return 0


def current_session(conn):
    """(parliament, session): the newest in the store's bills or divisions."""
    row = conn.execute(
        "SELECT parliament, session FROM (SELECT parliament, session FROM ca_bills "
        "UNION SELECT parliament, session FROM ca_divisions) "
        "ORDER BY parliament DESC, session DESC LIMIT 1").fetchone()
    return (row[0], row[1]) if row else (45, 1)


def session_began(conn, parl, sess):
    return conn.execute("SELECT MIN(introduced_at) FROM ca_bills WHERE parliament=? AND session=?",
                        (parl, sess)).fetchone()[0]


def last_pull(conn):
    return count(conn, "SELECT last_run FROM source_runs WHERE source='Canada weekly'") or None


def edition_number(today):
    dates = {os.path.basename(f)[len("ca-monitor-"):-len(".md")]
             for f in glob.glob(os.path.join(ROOT, "editions", "ca-monitor-*.md"))}
    dates.add(today)
    return sorted(dates).index(today) + 1


_FILTER = {}


def own_areas(text):
    """The visible areas the division's own text matches, with no bill key."""
    if "tax" not in _FILTER:
        from src import filter as filt
        _FILTER["tax"] = filt.load_taxonomy(TAXONOMY)
        _FILTER["wl"] = filt.load_watchlist(WATCHLIST)
        _FILTER["f"] = filt.filter_item
    res = _FILTER["f"](_FILTER["tax"], _FILTER["wl"], text or "")
    return [a for a in (res.issue_areas or []) if a not in HIDDEN_AREAS]


# --- divisions ---------------------------------------------------------------

def divisions_on_our_ground(conn, since, until):
    found = rows(conn,
                 "SELECT d.*, b.long_title, b.short_title FROM ca_divisions d "
                 "LEFT JOIN ca_bills b ON b.parliament = d.parliament AND b.session = d.session "
                 "AND b.number = d.bill_number "
                 "WHERE substr(d.date, 1, 10) > ? AND substr(d.date, 1, 10) <= ? "
                 "ORDER BY d.date DESC, d.number DESC", (since, until))
    return [r for r in found if visible(r["areas"])]


def matched_on(r):
    return "own text" if own_areas(r["subject"]) else "bill only"


def fold_divisions(found):
    """One line per (chamber, bill or subject, result): a report stage can take
    a run of motions on one bill, each its own division."""
    groups, order = {}, []
    for r in found:
        key = (r["chamber"], r["bill_number"] or (r["subject"] or "")[:60], r["result"],
               (r["subject"] or "")[:25])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    return [groups[k] for k in order]


def party_split(conn, division_key):
    """'Lib 0-160, CPC 137-0' (Yea-Nay, and -Abst where any), by caucus AT THE
    VOTE; paired members and senators who did not vote are not counted."""
    counts = {}
    for party, position, n in conn.execute(
            "SELECT party, position, COUNT(*) FROM ca_votes WHERE division_key=? "
            "GROUP BY party, position", (division_key,)):
        counts.setdefault(PARTY_SHORT.get(party, party or "?"), {})[position] = n
    parts = []
    for p in sorted(counts, key=lambda p: (PARTY_ORDER.index(p) if p in PARTY_ORDER else 99, p)):
        c = counts[p]
        if not (c.get("Yea") or c.get("Nay") or c.get("Abstention")):
            continue
        parts.append("{0} {1}-{2}{3}".format(p, c.get("Yea", 0), c.get("Nay", 0),
                                             "-{0}".format(c["Abstention"]) if c.get("Abstention") else ""))
    return ", ".join(parts)


def tally(r):
    extra = ""
    if r["chamber"] == "senate" and r["abstentions"]:
        extra = "-{0} (Yea-Nay-Abst)".format(r["abstentions"])
    elif r["paired"]:
        extra = ", {0} paired".format(r["paired"])
    return "{0}-{1}{2}".format(r["yeas"] or 0, r["nays"] or 0, extra)


def measure(r):
    if r["bill_number"]:
        title = r["short_title"] or r["long_title"]
        return "[{0}]({1}){2}".format(
            r["bill_number"], bill_url(r["parliament"], r["session"], r["bill_number"]),
            " " + clip(title, 70) if title else "")
    return clip(r["subject"], 90)


def division_lines(conn, groups, names, stance):
    out = []
    for g in groups:
        r = g[0]
        times = " (x{0}, {1} to {2})".format(len(g), day_of(g[-1]["date"]), day_of(r["date"])) \
            if len(g) > 1 else ""
        split = party_split(conn, r["division_key"]) if r["positions_fetched"] else ""
        out.append("- **{0}**, [division {1}]({2}) {3}{4}: {5}. **{6}** {7}; {8}. "
                   "*Areas: {9} (matched on {10}).*".format(
                       CHAMBER.get(r["chamber"], r["chamber"]), r["number"], division_url(r),
                       day_of(r["date"]), times, measure(r), r["result"] or "?", tally(r),
                       split or "no party split fetched", names_of(visible(r["areas"]), names),
                       matched_on(r)))
        if r["bill_number"] and oneline(r["subject"]) != measure(r):
            out.append("  - {0}".format(clip(r["subject"], 200)))
        readings = sorted({reading_status(stance.get(x["division_key"])) for x in g})
        out.append("  - *5CA: {0}.*".format("; ".join(readings)))
    return out


# --- the 5CA readings ----------------------------------------------------------

def load_stance(path=None):
    """({division key: entry}, {bill key: entry}) from config/ca_stance.yaml."""
    import yaml
    path = path or STANCE
    if not os.path.exists(path):
        return {}, {}
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    pick = lambda sec: {str(e["key"]): e for e in (cfg.get(sec) or []) if e.get("key")}  # noqa: E731
    return pick("divisions"), pick("bills")


def stance_status(entry):
    """As tools/ca_5ca.status: 'confirmed', 'draft', 'unplaceable', 'unread', 'none'."""
    if not entry:
        return "none"
    if entry.get("placeable") is False:
        return "unplaceable"
    if entry.get("yea") is None and entry.get("nay") is None and entry.get("sponsored") is None:
        return "unread"
    if entry.get("draft"):
        return "draft"
    return "confirmed"


def reading_status(entry):
    """What the 5CA can say about one division, never its direction."""
    return {"confirmed": "a signed reading places members",
            "draft": "reading drafted, awaiting sign-off: places nobody",
            "unread": "text not read yet: places nobody",
            "unplaceable": "never places anyone (unanimous or procedural)",
            "none": "no reading yet: places nobody until one is written and signed"}[
        stance_status(entry)]


def excluded_from_5ca():
    import yaml
    try:
        with open(OVERRIDES, encoding="utf-8") as fh:
            return {int(a) for a in (yaml.safe_load(fh) or {}).get("excluded_from_5ca") or []}
    except OSError:
        return set(HIDDEN_AREAS)


def five_ca_section(conn, today, parl, sess, stance, bill_stance, names):
    excluded = excluded_from_5ca()
    every = list(stance.values()) + list(bill_stance.values())
    st = {k: sum(1 for e in every if stance_status(e) == k)
          for k in ("confirmed", "draft", "unread", "unplaceable")}
    out = ["## 5CA status", "",
           "*config/ca_stance.yaml holds what a Yea, a Nay or a sponsorship meant, written and "
           "signed by a person; tools/ca_5ca.py applies only the signed ones. This section says "
           "where a reading is missing or unsigned, never which way a vote cut.*", "",
           "- **Readings:** {confirmed} signed, {draft} drafted and awaiting sign-off, {unread} "
           "not yet read, {unplaceable} that never place anyone.".format(**st)]
    pending = [(k, e) for k, e in list(stance.items()) + list(bill_stance.items())
               if stance_status(e) in ("draft", "unread")]
    for key, e in pending[:15]:
        out.append("  - `{0}` {1}: {2}.".format(key, clip(e.get("title") or "", 80),
                                                "drafted, awaiting sign-off"
                                                if stance_status(e) == "draft" else "not read"))
    if len(pending) > 15:
        out.append("  - and {0} more.".format(len(pending) - 15))

    def campaigned(areas_json):
        return [a for a in visible(areas_json) if a not in excluded]

    unread = [r for r in rows(conn, "SELECT * FROM ca_divisions ORDER BY date DESC, number DESC")
              if campaigned(r["areas"]) and stance_status(stance.get(r["division_key"])) == "none"]
    current = [r for r in unread if (r["parliament"], r["session"]) == (parl, sess)]
    out.append("- **Divisions on our ground with no reading:** {0} in this session, {1} in "
               "all. Each places nobody until a reading is written and signed.".format(
                   len(current), len(unread)))
    for r in current[:10]:
        out.append("  - [{0} division {1}]({2}), {3}: {4} ({5}).".format(
            CHAMBER.get(r["chamber"], r["chamber"]), r["number"], division_url(r),
            day_of(r["date"]), clip(r["subject"], 90), names_of(campaigned(r["areas"]), names)))
    # Sponsorship places House members only (tools/ca_5ca.py): C- bills.
    bills = [b for b in rows(conn, "SELECT * FROM ca_bills WHERE parliament=? AND session=? "
                                   "AND COALESCE(is_government, 0) = 0 AND number LIKE 'C-%' "
                                   "AND sponsor_person_id IS NOT NULL ORDER BY number", (parl, sess))
             if campaigned(b["areas"]) and stance_status(bill_stance.get(b["bill_key"])) == "none"]
    out.append("- **Private members' bills on our ground with no sponsorship reading:** "
               "{0}{1}".format(
                   len(bills), ": " + ", ".join("[{0}]({1})".format(
                       b["number"], bill_url(b["parliament"], b["session"], b["number"]))
                       for b in bills) + "." if bills else "."))
    sheets = sorted(glob.glob(os.path.join(ROOT, "data", "5ca", "ca-5ca-*.csv")))
    out += ["- **Sheets:** {0} in data/5ca (one per chamber and area). Speeches, petitions and "
            "witness testimony are evidence on them, never direction; a Supreme Court judgment "
            "never places anyone.".format(len(sheets)), ""]
    return out


# --- bills -------------------------------------------------------------------

def bills_where(conn, where, params=()):
    return [r for r in rows(conn, "SELECT * FROM ca_bills WHERE " + where, params)
            if visible(r["areas"])]


def kind_of(r):
    kind = r["bill_type"] or ""
    if kind:
        return kind.replace("House ", "").replace("Senate ", "Senate ").replace("’", "'")
    return "Government Bill" if r["is_government"] else "?"


def stage_of(r):
    if r["royal_assent_at"]:
        return "Royal Assent {0}".format(day_of(r["royal_assent_at"]))
    status = r["status"] or "?"
    if r["last_stage"] and r["last_stage_at"] and status != "Bill defeated":
        return "{0} (last stage: {1}, {2})".format(status, r["last_stage"], r["last_stage_at"])
    return status


STAGE_RANK = (("First reading", 1), ("Second reading", 2), ("Consideration in committee", 3),
              ("Report stage", 4), ("Third reading", 5))


def stage_rank(r):
    """How far through: the originating chamber's stages 1-5, the other
    chamber's 6-10, Royal Assent 11. A Senate bill starts in the Senate."""
    stage = r["last_stage"] or ""
    if r["royal_assent_at"] or stage.startswith("Royal assent"):
        return 11
    origin = "Senate" if (r["number"] or "").startswith("S-") else "House"
    for text, rank in STAGE_RANK:
        if stage.startswith(text):
            return rank if origin in stage else rank + 5
    return 0


def rank_bills(found):
    """Furthest through first; within a stage, the most recent stage first."""
    found = sorted(found, key=lambda r: (r["last_stage_at"] or "", r["number"]), reverse=True)
    return sorted(found, key=lambda r: -stage_rank(r))


BILL_HEAD = ("| Bill | Areas | Kind | Stage | Sponsor |\n"
             "|---|---|---|---|---|")


def bill_row(r, names):
    title = r["short_title"] or r["long_title"]
    return "| [{0}]({1}) {2} | {3} | {4} | {5} | {6} |".format(
        r["number"], bill_url(r["parliament"], r["session"], r["number"]), clip(title, 90),
        names_of(visible(r["areas"]), names), kind_of(r), stage_of(r), clip(r["sponsor"] or "?", 40))


def divided_bills(found):
    """{(parliament, session, number): latest division date} for bills divided on."""
    out = {}
    for r in found:
        if r["bill_number"]:
            k = (r["parliament"], r["session"], r["bill_number"])
            out[k] = max(out.get(k, ""), day_of(r["date"]))
    return out


# --- debate, committees, petitions, Gazette, courts -----------------------------

def speeches_week(conn, since, today):
    return [r for r in rows(conn,
                            "SELECT * FROM ca_speeches WHERE date > ? AND date <= ? "
                            "AND COALESCE(forum, 'floor') = 'floor' ORDER BY date, time",
                            (since, today)) if visible(r["areas"])]


def senate_sitting_url(conn, sitting_key):
    row = conn.execute("SELECT url FROM ca_senate_sittings WHERE sitting_key=?",
                       (sitting_key,)).fetchone()
    return row[0] if row and row[0] else "https://sencanada.ca/en/in-the-chamber/debates/"


def debate_section(conn, since, today, names):
    found = speeches_week(conn, since, today)
    groups, order = {}, []
    for r in found:
        key = (r["chamber"] or "commons", r["date"], r["bill_number"] or oneline(r["subject"])[:80])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    out = ["## Debate on our ground ({0} speeches, {1} debates)".format(len(found), len(groups)), "",
           "*One line per debate and day, with a link to the day's record; never the text. A "
           "speech is activity, not a stance: who speaks on these issues, for or against. "
           "Unscored.*", ""]
    if not found:
        last = count(conn, "SELECT MAX(date) FROM ca_sittings")
        return out + ["*No speech on our ground in the sittings read this week. The last House "
                      "sitting read is {0}.*".format(last or "none"), ""]
    lines = []
    for key in order:
        g = groups[key]
        r = g[0]
        chamber = key[0]
        link = (senate_sitting_url(conn, r["sitting_key"]) if chamber == "senate"
                else hansard_url(r["sitting_key"]))
        people = []
        for s in g:
            who = clip((s["speaker"] or "?").split(" (")[0], 40)
            if who not in people:
                people.append(who)
        parties = {}
        for s in g:
            p = PARTY_SHORT.get(s["party"], s["party"]) if s["party"] else None
            if p:
                parties[p] = parties.get(p, 0) + 1
        areas = sorted({a for s in g for a in visible(s["areas"])})
        subject = oneline(r["subject"]) or "?"
        if r["bill_number"]:
            subject = "{0} ({1})".format(subject, r["bill_number"])
        lines.append("- **{0}**, [{1}]({2}): {3}. {4} speech(es) by {5}{6}. *Areas: {7}.*".format(
            "Senate" if chamber == "senate" else "House", r["date"], link, clip(subject, 90),
            len(g), ", ".join(people[:5]) + (" and {0} more".format(len(people) - 5)
                                            if len(people) > 5 else ""),
            " ({0})".format(", ".join("{0} {1}".format(p, n) for p, n in sorted(
                parties.items(), key=lambda x: -x[1]))) if parties else "",
            names_of(areas, names)))
    out += lines[:SPEECH_LINES]
    if len(lines) > SPEECH_LINES:
        out.append("- and {0} more debate(s).".format(len(lines) - SPEECH_LINES))
    return out + [""]


def committee_section(conn, since, today, names):
    month = (datetime.date.fromisoformat(today) - datetime.timedelta(days=MONTH_DAYS)).isoformat()
    week = [r for r in rows(conn, "SELECT * FROM ca_testimony WHERE date > ? AND date <= ? "
                                  "ORDER BY date DESC", (since, today)) if visible(r["areas"])]
    window, label = since, "this week"
    if not week:
        week = [r for r in rows(conn, "SELECT * FROM ca_testimony WHERE date > ? AND date <= ? "
                                      "ORDER BY date DESC", (month, today)) if visible(r["areas"])]
        window, label = month, "none this week; last 30 days"
    meetings = count(conn, "SELECT COUNT(*) FROM ca_committee_meetings WHERE date > ? AND date <= ? "
                           "AND status='read'", (since, today))
    member = count(conn, "SELECT COUNT(*) FROM ca_speeches WHERE forum='committee' AND date > ? "
                         "AND date <= ?", (since, today))
    out = ["## Committees: witnesses on our ground ({0}: {1} testimony)".format(label, len(week)), "",
           "*Who testified, for whom, with a link to the evidence; never the text. {0} committee "
           "meeting(s) read this week, {1} member intervention(s) on our ground in them.*".format(
               meetings, member), ""]
    by_meeting, order = {}, []
    for r in week:
        if r["meeting_key"] not in by_meeting:
            by_meeting[r["meeting_key"]] = []
            order.append(r["meeting_key"])
        by_meeting[r["meeting_key"]].append(r)
    for key in order:
        g = by_meeting[key]
        m = conn.execute("SELECT evidence_url, number FROM ca_committee_meetings WHERE meeting_key=?",
                         (key,)).fetchone()
        url = m[0] if m and m[0] else "#"
        witnesses = []
        for t in g:
            w = "{0} ({1})".format(oneline(t["witness"]) or "?", oneline(t["organisation"]) or "?")
            if w not in witnesses:
                witnesses.append(w)
        areas = sorted({a for t in g for a in visible(t["areas"])})
        out.append("- **{0}** [meeting {1}]({2}), {3}: {4}. Witnesses: {5}. *Areas: {6}.*".format(
            g[0]["committee"], key.split("-")[-1], url, g[0]["date"],
            clip(g[0]["subject"], 90), "; ".join(clip(w, 70) for w in witnesses[:6]),
            names_of(areas, names)))
    if not order:
        out.append("*No witness testimony on our ground in the last 30 days.*")
    return out + [""], window


def _prayer_key(p):
    text = " ".join((p["prayer"] or "").lower().split())[:400]
    return text or "id:" + p["petition_id"]


def shown(score, tier):
    """A judged item at SHOW_SCORE or more; an unjudged one only on tier 1."""
    return score >= SHOW_SCORE if score is not None else tier == 1


def petitions_week(conn, since, today):
    return [r for r in rows(conn,
                            "SELECT * FROM ca_petitions WHERE (presented > ? AND presented <= ?) "
                            "OR (opened > ? AND opened <= ? AND presented IS NULL)",
                            (since, today, since, today)) if visible(r["areas"])]


def fold_petitions(found):
    groups, order = {}, []
    for p in found:
        k = _prayer_key(p)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(p)
    out = [groups[k] for k in order]
    best = lambda g: max((p["triage_score"] for p in g if p["triage_score"] is not None),  # noqa: E731
                         default=None)
    return sorted(out, key=lambda g: (-(best(g) if best(g) is not None else 1.5),
                                      -sum(p["signatures"] or 0 for p in g))), best


def petition_section(conn, since, today, names):
    found = petitions_week(conn, since, today)
    groups, best = fold_petitions(found)
    listed = [g for g in groups if shown(best(g), min(p["tier"] or 2 for p in g))]
    held = len(groups) - len(listed)
    out = ["## Petitions ({0} on our ground this week, {1} distinct texts)".format(
        len(found), len(groups)), "",
           "*Presented to the House this week, or opened for signature. One line per text: a "
           "drive presented by many members is one line. The takeaway is the judge's why-line "
           "where scored. Presenting a petition does not mean a member endorses it.*", ""]
    for g in listed[:PETITION_LINES]:
        p = g[0]
        score = best(g)
        why = next((x["why_it_matters"] for x in g if x["why_it_matters"]), None)
        mps = []
        for x in g:
            n = oneline(x["mp_name"])
            if n and n not in mps:
                mps.append(n)
        sigs = sum(x["signatures"] or 0 for x in g)
        copies = " ({0} copies)".format(len(g)) if len(g) > 1 else ""
        out.append("- {0} [{1}]({2}){3}, {4}, {5} signature(s): {6} *Presented by {7}. "
                   "Areas: {8}.*".format(
                       score_mark(score), p["petition_id"], petition_url(p["petition_id"]), copies,
                       (p["kind"] or "petition").lower(), sigs,
                       clip(why, 200) if why else "*Unscored.* " + clip(p["prayer"], 160),
                       ", ".join(mps[:4]) + (" and {0} more".format(len(mps) - 4) if len(mps) > 4 else "")
                       if mps else "?",
                       names_of(sorted({a for x in g for a in visible(x["areas"])}), names)))
    if len(listed) > PETITION_LINES:
        out.append("- and {0} more text(s) at the same bar.".format(len(listed) - PETITION_LINES))
    if not listed:
        out.append("*None this week at the bar (judged {0}+, or unjudged on a tier-1 term).*".format(
            SHOW_SCORE))
    if held:
        out.append("- *{0} text(s) held back: judged below {1}, or unjudged and matched only on "
                   "a tier-2 term.*".format(held, SHOW_SCORE))
    return out + [""], groups, best


def gazette_section(conn, since, today, names):
    week = [r for r in rows(conn, "SELECT * FROM ca_gazette_items WHERE date > ? AND date <= ? "
                                  "ORDER BY date DESC", (since, today)) if visible(r["areas"])]
    comment = [r for r in rows(conn, "SELECT * FROM ca_gazette_items WHERE comment_until >= ? "
                                     "AND date <= ? ORDER BY comment_until", (today, today))
               if visible(r["areas"])]
    issues = count(conn, "SELECT COUNT(*) FROM ca_gazette_issues WHERE date > ? AND date <= ?",
                   (since, today))
    listed = [r for r in week if r["tier"] == 1]
    out = ["## Canada Gazette ({0} issue(s) this week, {1} item(s) on our ground)".format(
        issues, len(week)), "",
           "*Part I: notices and proposed regulations with their comment period. Part II: "
           "regulations made. Unscored: listed on a tier-1 match only.*", ""]
    for r in listed:
        out.append("- [{0}]({1}), Part {2}, {3}{4}{5}. *Areas: {6} (matched on {7}).*".format(
            clip(r["title"], 110), r["url"] or r["item_key"], "I" * (r["part"] or 0) or "?", r["date"],
            ", " + oneline(r["registration"]) if r["registration"] else "",
            ", " + clip(r["department"] or r["section"], 50) if (r["department"] or r["section"]) else "",
            names_of(visible(r["areas"]), names), r["matched_on"] or "?"))
    if not listed:
        out.append("*No item on our ground on a tier-1 term this week.*")
    if len(week) > len(listed):
        out.append("- *{0} item(s) matched only on a tier-2 term, held back.*".format(
            len(week) - len(listed)))
    if comment:
        out.append("- **Open for comment:** " + "; ".join(
            "[{0}]({1}) until {2}".format(clip(r["title"], 70), r["url"] or r["item_key"],
                                          r["comment_until"]) for r in comment) + ".")
    return out + [""], comment


def courts_section(conn, since, today, names):
    quarter = (datetime.date.fromisoformat(today) - datetime.timedelta(days=90)).isoformat()
    judged = [r for r in rows(conn, "SELECT * FROM ca_judgments WHERE court='SCC' AND date > ? "
                                    "AND date <= ? ORDER BY date DESC", (quarter, today))
              if visible(r["areas"])]
    week = [r for r in judged if r["date"] > since]
    leave = [r for r in rows(conn, "SELECT * FROM ca_leave WHERE status='Granted' AND decided > ? "
                                   "AND decided <= ? ORDER BY decided DESC", (quarter, today))
             if visible(r["areas"])]
    out = ["## Supreme Court of Canada", "",
           "*Context only: a judgment never places a parliamentarian. Judgments carry the "
           "judge's score where scored; leave to appeal is the early warning.*", ""]
    out.append("- **Judgments on our ground this week: {0}.**{1}".format(
        len(week), "" if week else " Last 90 days: {0}.".format(len(judged))))
    for r in (week or judged):
        if not shown(r["triage_score"], r["tier"]) and r["triage_score"] is not None:
            out.append("  - · [{0}]({1}) {2}, {3}: judged {4}, held back.".format(
                r["citation"] or "?", r["url"] or "#", clip(r["title"], 70), r["date"],
                r["triage_score"]))
            continue
        out.append("  - {0} [{1}]({2}) {3}, {4}. {5} *Areas: {6}.*".format(
            score_mark(r["triage_score"]), r["citation"] or "?", r["url"] or "#",
            clip(r["title"], 70), r["date"],
            clip(r["why_it_matters"], 200) if r["why_it_matters"] else "*Unscored.*",
            names_of(visible(r["areas"]), names)))
    out.append("- **Leave to appeal granted on our ground, last 90 days: {0}.**".format(len(leave)))
    for r in leave:
        out.append("  - [{0}]({1}) {2}, granted {3}{4}. *Areas: {5}. Unscored.*".format(
            r["docket"], r["url"] or "#", clip(r["title"], 80), r["decided"],
            ", from " + oneline(r["on_appeal_from"]) if r["on_appeal_from"] else "",
            names_of(visible(r["areas"]), names)))
    return out + [""], week, leave


# --- the edition ---------------------------------------------------------------

def render_edition(conn, today):
    conn.row_factory = sqlite3.Row
    ca_store.ensure_schema(conn)
    names = area_names()
    day = datetime.date.fromisoformat(today)
    since = (day - datetime.timedelta(days=WEEK_DAYS)).isoformat()
    month = (day - datetime.timedelta(days=MONTH_DAYS)).isoformat()
    parl, sess = current_session(conn)
    stance, bill_stance = load_stance()
    scored = count(conn, "SELECT COUNT(*) FROM ca_petitions WHERE triage_score IS NOT NULL") + \
        count(conn, "SELECT COUNT(*) FROM ca_judgments WHERE triage_score IS NOT NULL")
    score_note = ("Scores [0-3] and why-lines on petitions and Supreme Court judgments come from "
                  "the judge (tools/ca_triage.py, Canadian frame); everything else is unscored."
                  if scored else
                  "**No item is scored yet**: the Canadian judge has not been run, so petitions "
                  "and judgments are shown on tier-1 matches only and nothing is ranked by score.")

    week = divisions_on_our_ground(conn, since, today)
    divided = divided_bills(week)
    this = "parliament=? AND session=?"
    moved = bills_where(conn, this + " AND ((last_stage_at > ? AND last_stage_at <= ? AND "
                                     "(introduced_at IS NULL OR introduced_at <= ?)) "
                                     "OR (royal_assent_at IS NOT NULL AND substr(royal_assent_at, 1, 10) > ? "
                                     "AND substr(royal_assent_at, 1, 10) <= ?))",
                        (parl, sess, since, today, since, since, today))
    keys = {r["bill_key"] for r in moved}
    moved += [r for r in bills_where(conn, this, (parl, sess))
              if (r["parliament"], r["session"], r["number"]) in divided and r["bill_key"] not in keys]
    new = bills_where(conn, this + " AND introduced_at > ? AND introduced_at <= ?",
                      (parl, sess, since, today))
    live = bills_where(conn, this + " AND royal_assent_at IS NULL AND "
                                    "COALESCE(status, '') != 'Bill defeated'", (parl, sess))
    assented = bills_where(conn, this + " AND royal_assent_at IS NOT NULL", (parl, sess))
    defeated = bills_where(conn, this + " AND status = 'Bill defeated'", (parl, sess))
    began = session_began(conn, parl, sess)
    fell = []
    if began and (day - datetime.date.fromisoformat(began)).days <= FALLEN_SECTION_DAYS:
        fell = [r for r in bills_where(conn, "royal_assent_at IS NULL AND "
                                             "(parliament < ? OR (parliament = ? AND session < ?))",
                                       (parl, parl, sess))
                if (r["parliament"], r["session"]) == max(
                    ((b[0], b[1]) for b in conn.execute(
                        "SELECT parliament, session FROM ca_bills WHERE parliament < ? OR "
                        "(parliament = ? AND session < ?)", (parl, parl, sess))), default=None)]

    petition_lines, pet_groups, pet_best = petition_section(conn, since, today, names)
    gazette_lines, comment = gazette_section(conn, since, today, names)
    court_lines, judgments, leave = courts_section(conn, since, today, names)
    debate_lines = debate_section(conn, since, today, names)
    committee_lines, _ = committee_section(conn, since, today, names)

    out = ["# Canada Federal Monitor",
           "### Week ending {0} | Edition {1} | {2} Parliament, {3} session".format(
               today, edition_number(today), ordinal(parl), ordinal(sess)), "",
           HONESTY.format(taxonomy_version(), score_note), ""]

    # Top lines
    out += ["## Top lines", ""]
    tops = []
    for g in fold_divisions(week)[:3]:
        r = g[0]
        tops.append("- **{0} division{1}** on {2}: {3} {4}-{5}.".format(
            CHAMBER.get(r["chamber"], r["chamber"]), "s" if len(g) > 1 else "",
            clip(r["subject"], 90), (r["result"] or "?").lower(), r["yeas"] or 0, r["nays"] or 0))
    if not week:
        tops.append("- **Parliament recorded no division on our ground this week.** The House "
                    "last divided on our ground on {0}, the Senate on {1}.".format(
                        last_division(conn, "commons") or "?", last_division(conn, "senate") or "?"))
    for r in [b for b in rank_bills(moved) if (b["parliament"], b["session"], b["number"])
              not in divided][:3]:
        tops.append("- [{0}]({1}) {2}: {3}.".format(
            r["number"], bill_url(r["parliament"], r["session"], r["number"]),
            clip(r["short_title"] or r["long_title"], 70),
            "Royal Assent" if r["royal_assent_at"] else lower_first(r["last_stage"] or r["status"])))
    if new:
        tops.append("- {0} new bill(s) on our ground: {1}.".format(
            len(new), ", ".join(r["number"] for r in new)))
    drives = [g for g in pet_groups if shown(pet_best(g), min(p["tier"] or 2 for p in g))]
    if drives:
        g = drives[0]
        top = max(drives, key=lambda g: len(g))
        tops.append("- **Petitions:** {0} text(s) at the bar this week. The most presented, "
                    "[{1}]({2}), came {3} time(s) from {4} member(s), {5} signature(s) in all.".format(
                        len(drives), top[0]["petition_id"], petition_url(top[0]["petition_id"]),
                        len(top), len({p["mp_person_id"] or p["mp_name"] for p in top}),
                        sum(p["signatures"] or 0 for p in top)))
    unsigned = [g for g in fold_divisions(week)
                if any(stance_status(stance.get(x["division_key"])) != "confirmed" for x in g)]
    if unsigned:
        tops.append("- **5CA:** {0} of this week's division line(s) have no signed reading, so "
                    "they place nobody yet: {1}.".format(
                        len(unsigned), ", ".join("{0} division {1}".format(
                            CHAMBER.get(g[0]["chamber"]), g[0]["number"]) for g in unsigned)))
    if judgments:
        tops.append("- **Supreme Court:** {0} judgment(s) on our ground this week.".format(len(judgments)))
    out += tops or ["*Nothing moved on our ground this week.*"]
    out.append("")

    # Dates that matter
    out += ["## Dates that matter", ""]
    for date, what in DATES:
        days = (datetime.date.fromisoformat(date) - day).days
        if days < -RECENT_DAYS:
            continue
        when = "{0} days".format(days) if days >= 0 else "{0} days ago".format(-days)
        extra = ""
        if date.startswith("2029"):
            extra = " **{0} live bill(s) on our ground today.**".format(len(live))
        out.append("- **{0}** ({1}): {2}.{3}".format(date, when, what, extra))
    for r in comment:
        out.append("- **{0}**: comment period closes on [{1}]({2}) (Canada Gazette, Part I, {3}).".format(
            r["comment_until"], clip(r["title"], 80), r["url"] or r["item_key"], r["date"]))
    last_house = count(conn, "SELECT MAX(date) FROM ca_sittings")
    last_senate = count(conn, "SELECT MAX(date) FROM ca_senate_sittings")
    out += ["- *Sittings:* the sitting calendar is not collected. The last House sitting read is "
            "{0}, the last Senate sitting {1}.".format(last_house or "none", last_senate or "none"),
            "- *Prorogation and dissolution:* {0}".format(PROROGATION_NOTE), ""]

    # Divisions
    if week:
        out += ["## Divisions this week ({0})".format(len(week)), ""]
        out += division_lines(conn, fold_divisions(week), names, stance)
    else:
        recent = divisions_on_our_ground(conn, month, today)
        out += ["## Divisions (none this week; last 30 days: {0})".format(len(recent)), ""]
        if recent:
            out += division_lines(conn, fold_divisions(recent), names, stance)
        else:
            latest = fold_divisions(divisions_on_our_ground(conn, "0000", today))[:LATEST_GROUPS]
            out += ["*None in the last 30 days. The latest on our ground:*", ""]
            out += division_lines(conn, latest, names, stance) or ["*None held.*"]
    out.append("")

    # Bills
    out += ["## Bills that moved this week ({0})".format(len(moved)), "",
            "*A stage completed, Royal Assent, or a division on the bill this week. Unscored: "
            "bills are matched on their titles.*", ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in rank_bills(moved)]) if moved \
        else ["*No bill on our ground completed a stage this week.*"]
    out += ["", "## New bills this week ({0})".format(len(new)), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in rank_bills(new)]) if new \
        else ["*None introduced on our ground this week.*"]
    out += ["", "## Live bills ({0})".format(len(live)), "",
            "*Bills of the {0} Parliament, {1} session, on our ground, without Royal Assent and "
            "not defeated. Ordered by how far through, then by date. 'Outside the Order of "
            "Precedence' is a private member's bill not yet drawn for debate.*".format(
                ordinal(parl), ordinal(sess)), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in rank_bills(live)]) if live \
        else ["*None.*"]
    out += ["", "## Royal Assent this session ({0})".format(len(assented)), ""]
    out += ["- [{0}]({1}) {2}: Royal Assent {3}.".format(
        r["number"], bill_url(r["parliament"], r["session"], r["number"]),
        clip(r["short_title"] or r["long_title"], 90), day_of(r["royal_assent_at"]))
        for r in sorted(assented, key=lambda r: r["royal_assent_at"], reverse=True)] or ["*None.*"]
    out += ["", "## Fallen ({0})".format(len(defeated) + len(fell)), ""]
    out += ["- [{0}]({1}) {2}: defeated{3}.".format(
        r["number"], bill_url(r["parliament"], r["session"], r["number"]),
        clip(r["short_title"] or r["long_title"], 90),
        " at a division on {0}".format(last_bill_division(conn, r)) if last_bill_division(conn, r)
        else "") for r in defeated]
    out += ["- [{0}]({1}) {2}: fell at the end of the {3} Parliament, {4} session.".format(
        r["number"], bill_url(r["parliament"], r["session"], r["number"]),
        clip(r["short_title"] or r["long_title"], 90), ordinal(r["parliament"]),
        ordinal(r["session"])) for r in fell]
    if not (defeated or fell):
        out.append("*None.*")
    out.append("")

    out += debate_lines + committee_lines + petition_lines + gazette_lines + court_lines
    out += five_ca_section(conn, today, parl, sess, stance, bill_stance, names)

    # Coverage
    out += ["## Coverage", "",
            "- **Collected:** {0} House and {1} Senate divisions ({2} on our ground, members' "
            "votes with their caucus at the vote), {3} bills ({4} this session), {5} House and "
            "{6} Senate sittings read, {7} committee meetings read ({8} witness testimonies on "
            "our ground), {9} petitions ({10} judged), {11} Gazette issues, {12} Supreme Court "
            "judgments and {13} leave decisions. Last pull: {14}.".format(
                count(conn, "SELECT COUNT(*) FROM ca_divisions WHERE chamber='commons'"),
                count(conn, "SELECT COUNT(*) FROM ca_divisions WHERE chamber='senate'"),
                len(divisions_on_our_ground(conn, "0000", "9999")),
                count(conn, "SELECT COUNT(*) FROM ca_bills"),
                count(conn, "SELECT COUNT(*) FROM ca_bills WHERE parliament=? AND session=?",
                      (parl, sess)),
                count(conn, "SELECT COUNT(*) FROM ca_sittings"),
                count(conn, "SELECT COUNT(*) FROM ca_senate_sittings"),
                count(conn, "SELECT COUNT(*) FROM ca_committee_meetings WHERE status='read'"),
                count(conn, "SELECT COUNT(*) FROM ca_testimony"),
                count(conn, "SELECT COUNT(*) FROM ca_petitions"),
                count(conn, "SELECT COUNT(*) FROM ca_petitions WHERE triage_score IS NOT NULL"),
                count(conn, "SELECT COUNT(*) FROM ca_gazette_issues"),
                count(conn, "SELECT COUNT(*) FROM ca_judgments WHERE court='SCC'"),
                count(conn, "SELECT COUNT(*) FROM ca_leave"), last_pull(conn) or "unknown"),
            "- **Read with a lag:** Hansard is read when the House publishes it, so the last "
            "sitting or two of a week can arrive next week; the Supreme Court's pages stop at "
            "Lexum's bot check and resume next run.",
            "- **Not collected:** the sitting calendar, the Order Paper and written questions, "
            "committee reports, Senate committees, bill texts (PDF), provincial legislatures and "
            "courts (CanLII needs a key).",
            "- **Unscored:** divisions, bills, speeches, testimony and the Gazette; the judge "
            "scores petitions and Supreme Court judgments only.",
            "- **Migration** is matched and stored but not shown, as in every edition here.",
            "- Specification and decisions: [docs/canada-scope.md]({0}docs/canada-scope.md).".format(REPO),
            ""]
    return "\n".join(out)


def last_division(conn, chamber):
    found = [r for r in rows(conn, "SELECT areas, date FROM ca_divisions WHERE chamber=? "
                                   "ORDER BY date DESC LIMIT 400", (chamber,)) if visible(r["areas"])]
    return day_of(found[0]["date"]) if found else None


def last_bill_division(conn, r):
    row = conn.execute("SELECT MAX(date) FROM ca_divisions WHERE parliament=? AND session=? "
                       "AND bill_number=?", (r["parliament"], r["session"], r["number"])).fetchone()
    return day_of(row[0]) if row and row[0] else None


def dm_summary(conn, today, path=None):
    """The week in one Slack message, to Christopher alone."""
    conn.row_factory = sqlite3.Row
    ca_store.ensure_schema(conn)
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=WEEK_DAYS)).isoformat()
    parl, sess = current_session(conn)
    week = divisions_on_our_ground(conn, since, today)
    new = bills_where(conn, "parliament=? AND session=? AND introduced_at > ? AND introduced_at <= ?",
                      (parl, sess, since, today))
    live = bills_where(conn, "parliament=? AND session=? AND royal_assent_at IS NULL AND "
                             "COALESCE(status, '') != 'Bill defeated'", (parl, sess))
    lines = [":flag-ca: *Canada Federal Monitor - week ending {0}*".format(today), ""]
    if week:
        lines.append("*{0} division(s) on our ground* (House {1}, Senate {2}):".format(
            len(week), sum(r["chamber"] == "commons" for r in week),
            sum(r["chamber"] == "senate" for r in week)))
        for g in fold_divisions(week)[:4]:
            r = g[0]
            lines.append("• {0}: {1}, {2} {3}".format(
                CHAMBER.get(r["chamber"]), clip(r["subject"], 90), r["result"] or "?", tally(r)))
    else:
        lines.append("*No division on our ground this week.* House last {0}, Senate {1}.".format(
            last_division(conn, "commons") or "?", last_division(conn, "senate") or "?"))
    groups, best = fold_petitions(petitions_week(conn, since, today))
    drives = [g for g in groups if shown(best(g), min(p["tier"] or 2 for p in g))]
    lines.append("{0} new bill(s), {1} live on our ground; {2} petition text(s) at the bar, "
                 "{3} speech(es) on our ground.".format(
                     len(new), len(live), len(drives), len(speeches_week(conn, since, today))))
    for g in drives[:3]:
        why = next((x["why_it_matters"] for x in g if x["why_it_matters"]), None)
        lines.append("• {0}{1} x{2}, {3} sig.{4}".format(
            "*[{0}]* ".format(best(g)) if best(g) is not None else "", g[0]["petition_id"],
            len(g), sum(p["signatures"] or 0 for p in g),
            "\n   _{0}_".format(clip(why, 160)) if why else ""))
    lines.append("_Areas from taxonomy v{0}; Canadian terms not yet reviewed by a Canadian "
                 "campaigner. No verdicts: results and splits only._".format(taxonomy_version()))
    if path:
        lines.append("Full edition: {0}{1}".format(REPO, os.path.relpath(path, ROOT)))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--edition", action="store_true", help="write editions/ca-monitor-<date>.md")
    ap.add_argument("--dm", action="store_true", help="DM the summary to Christopher")
    ap.add_argument("--print", action="store_true", help="render to stdout, write nothing")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    conn.row_factory = sqlite3.Row
    text = render_edition(conn, args.date)
    path = os.path.join(ROOT, "editions", "ca-monitor-{0}.md".format(args.date))
    if args.print:
        print(text)
        return 0
    if args.edition:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("edition: wrote {0} ({1} lines)".format(os.path.relpath(path, ROOT),
                                                     text.count("\n") + 1))
    if args.dm:
        from src import publish
        print("dm: {0}".format(publish.slack_dm(publish.load_secrets(),
                                                dm_summary(conn, args.date,
                                                           path if args.edition else None))))
    if not (args.edition or args.dm):
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
