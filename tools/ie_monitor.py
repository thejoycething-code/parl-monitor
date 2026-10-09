#!/usr/bin/env python3
"""The Ireland edition: its own document, and a DM to Christopher.

    python3 tools/ie_monitor.py --edition              # write editions/ie-monitor-<date>.md
    python3 tools/ie_monitor.py --edition --dm         # and DM the summary
    python3 tools/ie_monitor.py --print                # render to stdout, write nothing
    python3 tools/ie_monitor.py --print --date 2026-10-09

Christopher, 9 October 2026, confirmed: Ireland gets its own edition, to him
alone, as a DM (U05LJP0BT61), as the US and German editions went to him
first; nothing posts to a channel. Modelled on tools/us_monitor.py.

WHAT LEADS. The Oireachtas moves our ground through divisions (Dáil, Seanad
and committee), bills changing stage, and new bills. The edition leads with
the week and says so plainly when nothing on our ground was divided on.

NO VERDICTS. A division carries its outcome, its Tá-Níl-Staon tally and its
party split, never "a win" or "a defeat". Which way a vote cut is a signed
human judgement here as everywhere in this repo: a Government "timed
amendment" that carries can be the death of a Private Members' bill.

INHERITED AREAS ARE MARKED. A division takes its bill's areas
(tools/ie_rollcalls.py), so every line says what matched: the division's own
text, the amendment moved (read from the transcript, phase 1b), or only its
bill. An amendment that was read and matched nothing of its own is folded
into a count line under its bill rather than listed as a finding: that is
the Mental Health Bill's 31 votes, which the bill's "parental consent" put
in area 6.

SCORES ARE OPTIONAL. Everything renders with no judge run at all (CLAUDE.md:
everything runs with TRIAGE=stub). Unscored items are ranked by stage and say
they are unscored.

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

from src import db  # noqa: E402

TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
REPO = "https://github.com/thejoycething-code/parl-monitor/blob/main/"
HIDDEN_AREAS = (11,)
WEEK_DAYS = 7
DAIL, SEANAD = 34, 27
RECENT_DAYS = 21          # a past date stays on the list this long
LATEST_GROUPS = 6         # a quiet month shows the latest divisions on our ground

# Fixed dates, each with what it means for the store. Measured where they are
# measured (docs/ireland-scope.md); the one statutory date says so.
DATES = (
    ("2026-10-06", "Budget 2027: the Dáil voted the Financial Resolutions; the Finance "
                   "Bill and Social Welfare Bill follow through the autumn"),
    ("2029-12-17", "The latest the 34th Dáil can be dissolved (five years from its first "
                   "sitting on 18 December 2024, by statute). Every bill lapses at the "
                   "dissolution and can come back only by a restoration motion"),
)
SITTING_NOTE = ("The Dáil sits Tuesday to Thursday and takes most divisions in its "
                "Wednesday-evening division time (339 of 429 in this Dáil). Last winter it "
                "last divided on 17 December and returned on 13 January.")

HONESTY = (
    "> **How to read this edition.** Areas come from the shared taxonomy (v{0}), with "
    "Irish bills it cannot read by title added by key (config/watchlist-ie.yaml); its "
    "Irish vocabulary has not yet been reviewed by anyone who campaigns in Ireland. Bills "
    "are matched on their short and long titles. A division takes its bill's areas, so "
    "every division says whether its **own** text, the **amendment** moved, or only its "
    "**bill** matched. Outcomes, tallies and party splits are the record; whether a vote "
    "helped or hurt is a human call and is never made here. {1}"
)

PARTY_SHORT = {"Fianna Fáil": "FF", "Fine Gael": "FG", "Sinn Féin": "SF", "Labour Party": "Lab",
               "Social Democrats": "SD", "Independent": "Ind", "Independent Ireland": "II",
               "People Before Profit-Solidarity": "PBP-S", "Aontú": "Aontú",
               "Green Party": "GP", "100% RDR": "RDR"}
PARTY_ORDER = ("FF", "FG", "SF", "Lab", "SD", "II", "PBP-S", "Aontú", "GP", "RDR", "Ind")

# How far through the Oireachtas a bill has come, from its last completed stage.
STAGE_RANK = {"First Stage": 1, "Second Stage": 2, "Committee Stage": 3, "Report Stage": 4,
              "Fifth Stage": 5, "Enacted": 9}


def area_names():
    from src import intel
    return intel.area_names(TAXONOMY)


def taxonomy_version():
    import yaml
    with open(TAXONOMY, encoding="utf-8") as fh:
        return str(yaml.safe_load(fh).get("version"))


def oneline(text):
    """One line, and no em dashes (CLAUDE.md: rendered editions carry none)."""
    return " ".join((text or "").replace("—", " - ").split())


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


def bill_url(key):
    year, number = key.split("/")
    return "https://www.oireachtas.ie/en/bills/bill/{0}/{1}/".format(year, number)


def bill_label(key):
    year, number = key.split("/")
    return "Bill {0} of {1}".format(number, year)


def division_url(row):
    """The Oireachtas page for a plenary division. Committee divisions have no
    page we could confirm, so they link the day's transcript."""
    if row["chamber"] in ("dail", "seanad"):
        return "https://www.oireachtas.ie/en/debates/vote/{0}/{1}/{2}/".format(
            row["house_key"], row["date"], (row["vote_id"] or "").replace("vote_", ""))
    from_uri = (row["debate_uri"] or "").replace("/debate/main", "/debate/mul@/main.xml")
    return from_uri or "#"


def chamber_label(row):
    if row["chamber"] == "committee":
        return row["committee"] or "Committee"
    return {"dail": "Dáil", "seanad": "Seanad"}.get(row["chamber"], row["chamber"])


def stage_label(row):
    if row["act"]:
        return "Enacted ({0})".format(row["act"])
    house = {"dail": "Dáil", "seanad": "Seanad"}.get((row["last_stage_house"] or "/").split("/")[0], "")
    return " ".join(x for x in (house, row["last_stage"] or "Introduced") if x)


def stage_rank(row):
    if row["act"]:
        return 9
    rank = STAGE_RANK.get(row["last_stage"] or "", 0)
    # The second House's stages come after all of the first's.
    if row["origin_house"] and row["last_stage_house"] and \
            not row["last_stage_house"].startswith(row["origin_house"]):
        rank += 5
    return rank


def sponsor_of(conn, key):
    rows = conn.execute("SELECT name, office FROM ie_sponsors WHERE bill_key=? "
                        "ORDER BY is_primary DESC, name", (key,)).fetchall()
    if not rows:
        return "?"
    first = rows[0][1] if rows[0][0] is None else rows[0][0]
    return first + (" and {0} other(s)".format(len(rows) - 1) if len(rows) > 1 else "")


def party_split(conn, division_key):
    """'FF 40-0, FG 30-0, SF 0-35' (Tá-Níl, and -Staon where any), by party AT THE VOTE."""
    counts = {}
    for party, position, n in conn.execute(
            "SELECT party, position, COUNT(*) FROM ie_votes WHERE division_key=? "
            "GROUP BY party, position", (division_key,)):
        counts.setdefault(PARTY_SHORT.get(party, party or "?"), {})[position] = n
    parts = []
    for p in sorted(counts, key=lambda p: (PARTY_ORDER.index(p) if p in PARTY_ORDER else 99, p)):
        c = counts[p]
        parts.append("{0} {1}-{2}{3}".format(p, c.get("Yes", 0), c.get("No", 0),
                                             "-{0}".format(c["Abstain"]) if c.get("Abstain") else ""))
    return ", ".join(parts)


def edition_number(today):
    dates = {os.path.basename(f)[len("ie-monitor-"):-len(".md")]
             for f in glob.glob(os.path.join(ROOT, "editions", "ie-monitor-*.md"))}
    dates.add(today)
    return sorted(dates).index(today) + 1


# --- queries -----------------------------------------------------------------

def divisions_on_our_ground(conn, since, until):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT d.*, b.title AS bill_title, b.triage_score AS bill_score, "
        "b.why_it_matters AS bill_why FROM ie_divisions d "
        "LEFT JOIN ie_bills b ON b.bill_key = d.bill_key "
        "WHERE d.date > ? AND d.date <= ? ORDER BY d.date DESC, d.division_key DESC",
        (since, until)).fetchall()
    return [r for r in rows if visible(r["areas"])]


def matched_on(r):
    """What a division's areas rest on: 'own text', 'amendment', or 'bill only'."""
    if visible(r["own_areas"]):
        return "amendment" if r["amendment_text"] else "own text"
    return "bill only"


def read_and_blank(r):
    """An amendment read from the transcript that matched nothing of its own."""
    return bool(r["amendment_text"]) and not visible(r["own_areas"])


def fold_divisions(rows):
    """One line per (chamber, measure, subject, outcome): a Report Stage can
    take a dozen amendment divisions on one bill, and a Private Members'
    motion an amendment and then the motion."""
    groups, order = {}, []
    for r in rows:
        key = (r["chamber"], r["committee"], r["bill_key"] or r["debate_title"],
               (r["subject"] or "")[:60], r["outcome"], r["amendment_ref"] or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    return [groups[k] for k in order]


def bills_where(conn, where, params=()):
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM ie_bills WHERE " + where, params).fetchall()
    return [r for r in rows if visible(r["areas"])]


def rank_bills(rows):
    """Scored first by score; then by how far through, then recency."""
    return sorted(rows, key=lambda r: (-(r["triage_score"] if r["triage_score"] is not None else 1.5),
                                       -stage_rank(r), r["last_stage_at"] or ""))


def last_division(conn, chamber):
    row = conn.execute("SELECT MAX(date) FROM ie_divisions WHERE chamber=?", (chamber,)).fetchone()
    return row[0] if row else None


def last_pull(conn):
    try:
        row = conn.execute("SELECT last_run FROM source_runs WHERE source='Ireland weekly'").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None


# --- rendering ---------------------------------------------------------------

BILL_HEAD = ("| Bill | Areas | Stage | Sponsor | Why it matters, or the last stage |\n"
             "|---|---|---|---|---|")


def bill_row(conn, r, names):
    return "| {0} [{1}]({2}) {3} | {4} | {5} | {6} | {7} |".format(
        score_mark(r["triage_score"]), bill_label(r["bill_key"]), bill_url(r["bill_key"]),
        clip(r["title"], 90), names_of(visible(r["areas"]), names), stage_label(r),
        "{0} ({1})".format(clip(sponsor_of(conn, r["bill_key"]), 50), r["source"] or "?"),
        clip(r["why_it_matters"] or ("{0}, {1}".format(stage_label(r), r["last_stage_at"])
                                     if r["last_stage_at"] else ""), 160))


def division_lines(conn, groups, names):
    out, quiet = [], {}
    for g in groups:
        r = g[0]
        if all(read_and_blank(x) for x in g):
            quiet.setdefault((r["bill_key"], r["bill_title"]), []).extend(g)
            continue
        measure = ("[{0}]({1})".format(clip(r["bill_title"], 70), bill_url(r["bill_key"]))
                   if r["bill_key"] else clip(r["debate_title"], 80))
        times = (" (x{0}, {1} to {2})".format(len(g), g[-1]["date"], r["date"])
                 if len(g) > 1 else "")
        score = r["triage_score"] if r["triage_score"] is not None else r["bill_score"]
        tally = "{0}-{1}{2}".format(r["ta"] or 0, r["nil"] or 0,
                                    "-{0}".format(r["staon"]) if r["staon"] else "")
        out.append("- {0} **{1}**, [division]({2}) {3}{4}: {5}, {6}. **{7}** {8} (Tá-Níl{9}); "
                   "{10}. *Areas: {11} (matched on {12}).*".format(
                       score_mark(score), chamber_label(r), division_url(r), r["date"], times,
                       measure, clip((r["subject"] or "question put").rstrip(": ").rstrip(":"), 60), r["outcome"], tally,
                       "-Staon" if r["staon"] else "",
                       party_split(conn, r["division_key"]) or "no split",
                       names_of(visible(r["areas"]), names), matched_on(r)))
        if r["amendment_text"]:
            out.append("  - {0}".format(clip(r["amendment_text"], 220)))
        elif (r["subject"] or "").startswith(("Amendment", "Seanad amendment", "Recommendation")):
            out.append("  - *The amendment moved was not found before this division in the "
                       "transcript (often moved on an earlier day).*")
        why = r["why_it_matters"] or r["bill_why"]
        if why:
            out.append("  - *{0}*".format(oneline(why)))
    for (bkey, title), rows in quiet.items():
        label = "[{0}]({1})".format(clip(title, 70), bill_url(bkey)) if bkey else "a motion"
        out.append("- · {0} amendment division(s) on {1}, {2} to {3}, whose amendments were "
                   "read and matched nothing of their own: listed for the bill's areas only.".format(
                       len(rows), label, min(x["date"] for x in rows), max(x["date"] for x in rows)))
    return out


# --- phase 2: questions, debate, the week ahead ------------------------------

QUESTION_LINES = 15       # the week's questions listed; the rest are counted by area
DEBATE_GROUPS = 10        # debate sections listed
DEBATE_QUOTES = 2         # excerpts per section
AHEAD_DAYS = 10           # 'Coming up' looks this far past the edition date
FROM_LABEL = {"own": "own words", "watch": "watchlist bill", "bill": "the bill's title",
              "heading": "the debate's title"}


def _table(conn, name):
    try:
        conn.execute("SELECT 1 FROM {0} LIMIT 1".format(name))
        return True
    except sqlite3.Error:
        return False


def questions_on_our_ground(conn, since, until):
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM ie_questions WHERE date > ? AND date <= ? "
                        "ORDER BY date DESC, question_key", (since, until)).fetchall()
    return [r for r in rows if visible(r["areas"])]


def questions_asked(conn, since, until):
    """Questions read in the weeks the window touches, from ie_windows: the
    volume behind the ones on our ground. None when no such week was read."""
    first = datetime.date.fromisoformat(since) + datetime.timedelta(days=1)
    lo = (first - datetime.timedelta(days=first.weekday())).isoformat()
    row = conn.execute("SELECT COUNT(*), SUM(records) FROM ie_windows WHERE feed='questions' "
                       "AND status='read' AND week_of >= ? AND week_of <= ?", (lo, until)).fetchone()
    return row[1] if row and row[0] else None


def speeches_on_our_ground(conn, since, until):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT s.*, b.title AS bill_title, b.triage_score AS bill_score FROM ie_speeches s "
        "LEFT JOIN ie_bills b ON b.bill_key = s.bill_key WHERE s.date > ? AND s.date <= ? "
        "ORDER BY s.date DESC, s.speech_key", (since, until)).fetchall()
    return [r for r in rows if visible(r["areas"])]


def debate_groups(rows):
    """One group per debate section, the sections with most members on our
    ground first."""
    groups, order = {}, []
    for r in rows:
        k = (r["debate_uri"], r["debate_section"])
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(r)
    return sorted((groups[k] for k in order),
                  key=lambda g: (-max((x["triage_score"] if x["triage_score"] is not None else -1)
                                      for x in g), -len(g), g[0]["date"]), reverse=False)


def _who(r):
    party = PARTY_SHORT.get(r["party"], r["party"]) if r["party"] else None
    return "{0}{1}".format(r["speaker"] or r["member_code"], " ({0})".format(party) if party else "")


def question_lines(rows, names):
    out = []
    ranked = sorted(rows, key=lambda r: (-(r["triage_score"] if r["triage_score"] is not None else -1),
                                         r["date"]), reverse=False)
    for r in ranked[:QUESTION_LINES]:
        asker = r["asker"] or r["member_code"]
        party = PARTY_SHORT.get(r["party"], r["party"]) if r["party"] else None
        # The takeaway line only, and the link: never the answer (CLAUDE.md).
        answer = ("*Answer ({0}): {1}*".format(
            "{0}, {1}".format(r["answer_by"], r["answer_shape"]) if r["answer_shape"] and r["answer_by"]
            else (r["answer_by"] or r["answer_shape"] or "the Minister"),
            clip(r["answer_takeaway"], 200)) if r["answer_takeaway"] else
            "*Not answered in the record yet.*" if not r["answered"] else "*Answered; see the link.*")
        out.append("- {0} **{1}**{2}, {3} to the {4}, [{5}]({6}): {7} {8} *Areas: {9}.*".format(
            score_mark(r["triage_score"]), asker, " ({0})".format(party) if party else "",
            r["date"], r["minister"] or r["department"] or "Government", clip(r["heading"], 60),
            r["url"] or "#", clip(r["question"], 170), answer,
            names_of(visible(r["areas"]), names)))
        if r["why_it_matters"]:
            out.append("  - *{0}*".format(oneline(r["why_it_matters"])))
    rest = ranked[QUESTION_LINES:]
    if rest:
        by_area = {}
        for r in rest:
            for a in visible(r["areas"]):
                by_area[a] = by_area.get(a, 0) + 1
        out.append("- · and {0} more on our ground: {1}.".format(len(rest), ", ".join(
            "{0} {1}".format(names.get(a, a), n) for a, n in
            sorted(by_area.items(), key=lambda x: -x[1]))))
    return out


def debate_lines(conn, groups, names):
    out = []
    for g in groups[:DEBATE_GROUPS]:
        r = g[0]
        where = chamber_label(r)
        title = ("[{0}]({1})".format(clip(r["bill_title"] or r["section_title"], 90),
                                     bill_url(r["bill_key"]))
                 if r["bill_key"] else clip(r["section_title"], 90))
        froms = sorted({x["areas_from"] for x in g if x["areas_from"]})
        areas = sorted({a for x in g for a in visible(x["areas"])})
        score = max((x["triage_score"] for x in g if x["triage_score"] is not None),
                    default=r["bill_score"])
        out.append("- {0} **{1}**, {2}, {3} ([debate]({4})): {5} member(s) on our ground: {6}. "
                   "*Areas: {7} (matched on {8}).*".format(
                       score_mark(score), where, r["date"], title, r["url"] or "#", len(g),
                       ", ".join(_who(x) for x in g[:8]) + (" and {0} more".format(len(g) - 8)
                                                           if len(g) > 8 else ""),
                       names_of(areas, names), ", ".join(FROM_LABEL.get(f, f) for f in froms)))
        for x in sorted(g, key=lambda x: (x["areas_from"] != "own", -(x["words"] or 0)))[:DEBATE_QUOTES]:
            if x["excerpt"]:
                out.append("  - {0}: \"{1}\"".format(_who(x), clip(x["excerpt"], 300)))
        why = next((x["why_it_matters"] for x in g if x["why_it_matters"]), None)
        if why:
            out.append("  - *{0}*".format(oneline(why)))
    if len(groups) > DEBATE_GROUPS:
        out.append("- · and {0} more debate(s) with a member on our ground.".format(
            len(groups) - DEBATE_GROUPS))
    return out


def coming_up(conn, today):
    """The week ahead from ie_schedule, or None when it was never collected."""
    if not _table(conn, "ie_schedule_days"):
        return None
    conn.row_factory = sqlite3.Row
    last = (datetime.date.fromisoformat(today) + datetime.timedelta(days=AHEAD_DAYS)).isoformat()
    days = conn.execute("SELECT * FROM ie_schedule_days WHERE date > ? AND date <= ? "
                        "ORDER BY date", (today, last)).fetchall()
    seen = conn.execute("SELECT MAX(last_seen) FROM ie_schedule_days").fetchone()[0]
    if not seen:
        return None
    rows = conn.execute(
        "SELECT s.*, b.title AS bill_title, b.areas AS bill_areas, b.triage_score AS bill_score "
        "FROM ie_schedule s LEFT JOIN ie_bills b ON b.bill_key = s.bill_key "
        "WHERE s.date > ? AND s.date <= ? ORDER BY s.date, s.time, s.item_key",
        (today, last)).fetchall()
    notes = {r["chamber"]: r["note"] for r in conn.execute(
        "SELECT chamber, note FROM ie_schedule_days WHERE note IS NOT NULL AND last_seen = ? "
        "ORDER BY date", (seen,)).fetchall()}
    out = {"first": today, "last": last, "read": seen, "chambers": {}}
    for chamber in ("dail", "seanad", "committee"):
        listed = [d for d in days if d["chamber"] == chamber and d["status"] == "listed"]
        items = [r for r in rows if r["chamber"] == chamber]
        ours = [r for r in items if visible(r["bill_areas"]) or visible(r["own_areas"])]
        out["chambers"][chamber] = {"days": [d["date"] for d in listed], "items": items,
                                    "ours": ours, "note": notes.get(chamber)}
    return out


def _resumes(note):
    """'Dáil Éireann resumes on Tuesday, 13 October 2026' -> '2026-10-13', or None."""
    import re
    hit = re.search(r"resumes on \w+,? (\d{1,2}) (\w+) (\d{4})", note or "")
    if not hit:
        return None
    try:
        return datetime.datetime.strptime(" ".join(hit.groups()), "%d %B %Y").date().isoformat()
    except ValueError:
        return None


def schedule_line(r, names):
    areas = sorted(set(visible(r["bill_areas"])) | set(visible(r["own_areas"])))
    if r["bill_key"] and r["bill_title"]:
        what = "[{0}]({1}): {2}".format(clip(r["bill_title"], 90), bill_url(r["bill_key"]),
                                        clip(r["text"], 120))
    else:
        what = clip(r["text"], 140)
    return "- {0} **{1}**{2}{3}: {4}. *Areas: {5} (matched on {6}).*".format(
        score_mark(r["bill_score"]), r["date"], " {0}".format(r["time"]) if r["time"] else "",
        ", {0}".format(r["committee"]) if r["committee"] else "", what.rstrip("."),
        names_of(areas, names), "the bill" if visible(r["bill_areas"]) else "the line's own text")


def render_coming_up(conn, today, names):
    c = coming_up(conn, today)
    head = "## Coming up"
    if c is None:
        return [head, "", "*The week ahead was not collected for this edition "
                          "(tools/ie_schedule.py has not run on this store).*", ""]
    first = (datetime.date.fromisoformat(c["first"]) + datetime.timedelta(days=1)).isoformat()
    out = ["{0}: {1} to {2}".format(head, first, c["last"]), "",
           "*From the Oireachtas's detailed schedule, read {0}. What is scheduled on our ground, "
           "by the bill's key where the schedule links it, else by the line's own words. A "
           "sitting can be rearranged after this was read.*".format(c["read"]), ""]
    for chamber, label in (("dail", "Dáil"), ("seanad", "Seanad"), ("committee", "Committees")):
        ch = c["chambers"][chamber]
        if ch["days"]:
            out.append("**{0}.** {1} item(s) on {2} day(s) posted, {3} on our ground.".format(
                label, len(ch["items"]), len(ch["days"]), len(ch["ours"])))
            out += [schedule_line(r, names) for r in ch["ours"]]
        else:
            back = _resumes(ch["note"])
            if back and back > c["last"]:
                out.append("**{0}.** In recess: it resumes on {1}.".format(label, back))
            elif back:
                out.append("**{0}.** No business posted yet for the coming days; it resumes "
                           "on {1}. The Dáil's week is usually posted after its Business "
                           "Committee meets.".format(label, back) if chamber == "dail" else
                           "**{0}.** No business posted yet; it resumes on {1}.".format(label, back))
            else:
                out.append("**{0}.** No business posted for these days.".format(label))
        out.append("")
    return out


def coming_up_dm(conn, today):
    c = coming_up(conn, today)
    if c is None:
        return None
    parts = []
    for chamber, label in (("dail", "Dáil"), ("seanad", "Seanad"), ("committee", "committees")):
        ch = c["chambers"][chamber]
        if ch["days"]:
            parts.append("{0}: {1} item(s) on our ground".format(label, len(ch["ours"])))
        else:
            back = _resumes(ch["note"])
            parts.append("{0}: {1}".format(label, "in recess to {0}".format(back)
                                           if back and back > c["last"] else
                                           "nothing posted yet"))
    named = [r["bill_title"] for ch in c["chambers"].values() for r in ch["ours"]
             if r["bill_key"] and r["bill_title"]]
    return "*Coming up:* " + "; ".join(parts) + "." + (
        " " + "; ".join(clip(t, 60) for t in list(dict.fromkeys(named))[:3]) + "." if named else "")


def render_edition(conn, today):
    conn.row_factory = sqlite3.Row
    names = area_names()
    day = datetime.date.fromisoformat(today)
    since = (day - datetime.timedelta(days=WEEK_DAYS)).isoformat()
    month = (day - datetime.timedelta(days=30)).isoformat()
    scored = conn.execute("SELECT COUNT(*) FROM ie_bills WHERE triage_score IS NOT NULL").fetchone()[0]
    score_note = ("Scores [0-3] and why-lines come from the judge (src/triage.py, Irish frame)."
                  if scored else
                  "**No item is scored yet**: the Irish judge has not been run, so items are "
                  "ranked by stage and carry their last stage in place of a why-line.")
    week = divisions_on_our_ground(conn, since, today)
    moved = bills_where(conn, "last_stage_at > ? AND last_stage_at <= ? "
                              "AND (introduced IS NULL OR introduced <= ?)", (since, today, since))
    new = bills_where(conn, "introduced > ? AND introduced <= ?", (since, today))
    live = bills_where(conn, "alive = 1")
    enacted = bills_where(conn, "act IS NOT NULL")
    lapsed = bills_where(conn, "alive = 0 AND act IS NULL AND status IN ('Current', 'Lapsed')")
    defeated = bills_where(conn, "status IN ('Defeated', 'Withdrawn') AND last_stage_house IN (?, ?)",
                           ("dail/{0}".format(DAIL), "seanad/{0}".format(SEANAD)))
    questions = questions_on_our_ground(conn, since, today) if _table(conn, "ie_questions") else []
    asked = questions_asked(conn, since, today) if _table(conn, "ie_windows") else None
    speeches = speeches_on_our_ground(conn, since, today) if _table(conn, "ie_speeches") else []
    debates = debate_groups(speeches)

    out = ["# Ireland Oireachtas Monitor",
           "### Week ending {0} | Edition {1} | {2}th Dáil, {3}th Seanad".format(
               today, edition_number(today), DAIL, SEANAD), "",
           HONESTY.format(taxonomy_version(), score_note), ""]

    # Top lines
    out += ["## Top lines", ""]
    tops = []
    for g in [g for g in fold_divisions(week) if not all(read_and_blank(x) for x in g)][:3]:
        r = g[0]
        tops.append("- **{0} division{1}** on {2}: {3}, {4} {5}-{6}.".format(
            chamber_label(r), "s" if len(g) > 1 else "",
            clip(r["bill_title"] or r["debate_title"], 70), clip((r["subject"] or "").rstrip(": "), 50),
            r["outcome"], r["ta"] or 0, r["nil"] or 0))
    for r in rank_bills(moved)[:6 - len(tops)]:
        tops.append("- {0} [{1}]({2}): {3}.".format(
            score_mark(r["triage_score"]), clip(r["title"], 80), bill_url(r["bill_key"]),
            stage_label(r).lower()))
    if not week:
        tops.insert(0, "- **The Oireachtas recorded no division on our ground this week.** The "
                       "Dáil last divided on {0}, the Seanad on {1}.".format(
                           last_division(conn, "dail") or "?", last_division(conn, "seanad") or "?"))
    if new:
        tops.append("- {0} new bill(s) on our ground were introduced.".format(len(new)))
    if debates:
        g = debates[0]
        tops.append("- **Debate:** {0} member(s) spoke on our ground in {1} debate(s); the most "
                    "in {2} ({3}, {4}).".format(len(speeches), len(debates), clip(
                        g[0]["bill_title"] or g[0]["section_title"], 70), chamber_label(g[0]),
                        g[0]["date"]))
    if questions:
        tops.append("- **Questions:** {0} parliamentary question(s) on our ground{1}.".format(
            len(questions), " of {0:,} asked".format(asked) if asked else ""))
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
    out += ["- *Sittings:* {0}".format(SITTING_NOTE), ""]

    # The week ahead
    out += render_coming_up(conn, today, names)

    # Divisions
    if week:
        out += ["## Divisions this week ({0})".format(len(week)), ""]
        out += division_lines(conn, fold_divisions(week), names)
    else:
        recent = divisions_on_our_ground(conn, month, today)
        out += ["## Divisions (none this week; last 30 days: {0})".format(len(recent)), ""]
        if recent:
            out += division_lines(conn, fold_divisions(recent), names)
        else:
            # A quiet month still says where the last fights were.
            latest = [g for g in fold_divisions(divisions_on_our_ground(conn, "0000", today))
                      if not all(read_and_blank(x) for x in g)][:LATEST_GROUPS]
            out += ["*None in the last 30 days. The latest on our ground:*", ""]
            out += division_lines(conn, latest, names) or ["*None this Dáil.*"]
    out.append("")

    # Debate
    out += ["## Debate this week ({0} member(s) in {1} debate(s))".format(len(speeches), len(debates)),
            "", "*Members whose own words in a debate matched our ground, or who spoke at length "
            "in a debate on a bill or motion whose own title is on our ground (docs/ireland-scope.md "
            "has the rule). An excerpt of what they said, never the speech; the debate is at "
            "the link.*", ""]
    out += debate_lines(conn, debates, names) or ["*No member spoke on our ground this week, "
                                                  "or the record is not yet published.*"]
    out.append("")

    # Questions
    out += ["## Questions this week ({0} on our ground{1})".format(
        len(questions), ", of {0:,} asked".format(asked) if asked else ""), "",
        "*Parliamentary questions whose own words are on our ground (the Minister's office is "
        "struck before matching). One line of the answer and the link; never the answer.*", ""]
    out += question_lines(questions, names) or ["*None on our ground this week.*"]
    out.append("")

    # Bills
    out += ["## Bills that moved this week ({0})".format(len(moved)), ""]
    out += ([BILL_HEAD] + [bill_row(conn, r, names) for r in rank_bills(moved)[:25]]) if moved \
        else ["*No bill on our ground completed a stage this week.*"]
    out += ["", "## New bills this week ({0})".format(len(new)), ""]
    out += ([BILL_HEAD] + [bill_row(conn, r, names) for r in rank_bills(new)]) if new else \
        ["*None introduced on our ground this week.*"]
    out += ["", "## Live bills ({0})".format(len(live)), "",
            "*Before the 34th Dáil or the 27th Seanad now: 'Current' in the Oireachtas data and "
            "either taken there or restored to the order paper. Ordered by score, then how far "
            "through, then recency. The stage is the last one completed.*", ""]
    out += ([BILL_HEAD] + [bill_row(conn, r, names) for r in rank_bills(live)[:30]]) if live \
        else ["*None.*"]
    out += ["", "## Enacted since the Dáil first met ({0})".format(len(enacted)), ""]
    out += ([BILL_HEAD] + [bill_row(conn, r, names) for r in sorted(
        enacted, key=lambda r: r["last_stage_at"] or r["last_updated"] or "", reverse=True)]) \
        if enacted else ["*None.*"]
    out += ["", "## Defeated or withdrawn in this Dáil and Seanad ({0})".format(len(defeated)), ""]
    out += ["- [{0}]({1}): {2} after its {3} ({4})".format(
        clip(r["title"], 90), bill_url(r["bill_key"]), r["status"].lower(), r["last_stage"] or "?",
        r["last_stage_at"] or "?") for r in defeated] or ["*None.*"]
    out += ["", "## Lapsed and not restored ({0})".format(len(lapsed)), "",
            "*On our ground, lapsed at the dissolution and never restored, though the "
            "Oireachtas data may still call them 'Current'. Only a restoration motion brings "
            "one back.*", ""]
    out += ["- [{0}]({1}), last stage {2} ({3})".format(
        clip(r["title"], 90), bill_url(r["bill_key"]), stage_label(r),
        (r["last_stage_house"] or "?").replace("/", " ")) for r in rank_bills(lapsed)] or ["*None.*"]

    # Coverage
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    out += ["", "## Coverage", "",
            "- **Collected:** {0} bills with any event since the Dáil first met ({1} alive, "
            "{2} on our ground), {3} Dáil, {4} Seanad and {5} committee divisions with every "
            "member's vote and party at the vote, {6} amendment divisions read against the "
            "transcript. Last pull: {7}.".format(
                n("SELECT COUNT(*) FROM ie_bills"), n("SELECT COUNT(*) FROM ie_bills WHERE alive=1"),
                len(bills_where(conn, "1=1")),
                n("SELECT COUNT(*) FROM ie_divisions WHERE chamber='dail'"),
                n("SELECT COUNT(*) FROM ie_divisions WHERE chamber='seanad'"),
                n("SELECT COUNT(*) FROM ie_divisions WHERE chamber='committee'"),
                n("SELECT COUNT(*) FROM ie_divisions WHERE amendment_text IS NOT NULL"),
                last_pull(conn) or "unknown"),
            "- **Questions and debate:** {0} and {1}. Weeks are read newest first; the "
            "backfill to the Dáil's first sitting drains over runs.".format(
                coverage_line(conn, "questions", "question(s)"),
                coverage_line(conn, "debates-", "member speech(es)")),
            "- **Not yet collected:** committee hearings' witnesses (members' words in committee "
            "are read), bill text (PDF only), gov.ie consultations (refused from the laptop), "
            "statutory instruments and Iris Oifigiúil (its robots.txt forbids collection).",
            "- **Migration** is matched and stored but not shown, as in every edition here.",
            "- Specification and decisions: [docs/ireland-scope.md]({0}docs/ireland-scope.md).".format(
                REPO), ""]
    return "\n".join(out)


def coverage_line(conn, feed, what):
    """'5,284 question(s) read in 4 week(s) back to 2026-09-14, 52 on our ground'."""
    if not _table(conn, "ie_windows"):
        return "{0}: not collected".format(what)
    row = conn.execute("SELECT COUNT(DISTINCT week_of), COALESCE(SUM(items),0), "
                       "COALESCE(SUM(ours),0), MIN(week_of) FROM ie_windows WHERE feed LIKE ? "
                       "AND status='read'", (feed + "%",)).fetchone()
    if not row[0]:
        return "{0}: not read yet".format(what)
    return "{0:,} {1} read in {2} week(s) back to {3}, {4:,} on our ground".format(
        row[1], what, row[0], row[3], row[2])


def dm_summary(conn, today, path=None):
    """The week in one Slack message, to Christopher alone."""
    conn.row_factory = sqlite3.Row
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=WEEK_DAYS)).isoformat()
    week = divisions_on_our_ground(conn, since, today)
    listed = [r for r in week if not read_and_blank(r)]
    moved = bills_where(conn, "last_stage_at > ? AND last_stage_at <= ? "
                              "AND (introduced IS NULL OR introduced <= ?)", (since, today, since))
    new = bills_where(conn, "introduced > ? AND introduced <= ?", (since, today))
    live = bills_where(conn, "alive = 1")
    lines = [":flag-ie: *Ireland Oireachtas Monitor - week ending {0}*".format(today), ""]
    if week:
        lines.append("*{0} division(s) on our ground* (Dáil {1}, Seanad {2}, committee {3}); "
                     "{4} on their own or their amendment's text.".format(
                         len(week), sum(r["chamber"] == "dail" for r in week),
                         sum(r["chamber"] == "seanad" for r in week),
                         sum(r["chamber"] == "committee" for r in week), len(listed)))
    else:
        lines.append("*No division on our ground this week.* Dáil last divided {0}, "
                     "Seanad {1}.".format(last_division(conn, "dail") or "?",
                                          last_division(conn, "seanad") or "?"))
    lines.append("{0} bill(s) moved, {1} new; {2} live on our ground.".format(
        len(moved), len(new), len(live)))
    if _table(conn, "ie_speeches"):
        speeches = speeches_on_our_ground(conn, since, today)
        questions = questions_on_our_ground(conn, since, today)
        lines.append("Debate: {0} member(s) on our ground in {1} debate(s). Questions: {2} on "
                     "our ground.".format(len(speeches), len(debate_groups(speeches)),
                                         len(questions)))
    ahead = coming_up_dm(conn, today)
    if ahead:
        lines.append(ahead)
    for r in rank_bills(moved + new)[:5]:
        why = r["why_it_matters"]
        lines.append("• {0}{1} ({2}){3}".format(
            "*[{0}]* ".format(r["triage_score"]) if r["triage_score"] is not None else "",
            clip(r["title"], 80), stage_label(r).lower(),
            "\n   _{0}_".format(oneline(why)) if why else ""))
    lines.append("_Areas from taxonomy v{0}; Irish vocabulary not yet reviewed by an Irish "
                 "campaigner._".format(taxonomy_version()))
    if path:
        lines.append("Full edition: {0}{1}".format(REPO, os.path.relpath(path, ROOT)))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--edition", action="store_true", help="write editions/ie-monitor-<date>.md")
    ap.add_argument("--dm", action="store_true", help="DM the summary to Christopher")
    ap.add_argument("--print", action="store_true", help="render to stdout, write nothing")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    conn.row_factory = sqlite3.Row
    text = render_edition(conn, args.date)
    path = os.path.join(ROOT, "editions", "ie-monitor-{0}.md".format(args.date))
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
