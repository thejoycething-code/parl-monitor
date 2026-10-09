#!/usr/bin/env python3
"""The US edition: its own document, and a DM to Christopher.

    python3 tools/us_monitor.py --edition              # write editions/us-monitor-<date>.md
    python3 tools/us_monitor.py --edition --dm         # and DM the summary
    python3 tools/us_monitor.py --print                # render to stdout, write nothing
    python3 tools/us_monitor.py --print --date 2026-10-09

Christopher, 9 October 2026: "own edition", and "US edition will just be me
for now until I get it good". So the edition goes to him alone, as a DM, as
the German one went to him first; nothing posts to a channel.

WHAT LEADS. Congress moves our ground through three things this store holds:
recorded votes (House and Senate), bills changing stage, and new bills. The
edition leads with what happened in the week and says so plainly when
Congress did not sit -- the first edition fell in the election recess, with
no House vote since 16 September -- rather than padding the top with old news.

NO VERDICTS. A vote carries its result, its tally and its party split, and
never "a win" or "a defeat". The direction of a division is a signed human
judgement here as everywhere in this repo (the Lords inversion): a question's
meaning comes from the motion, and a motion to table an amendment that would
have defunded abortion is a vote FOR the status quo.

INHERITED AREAS ARE MARKED. A vote takes its bill's areas (tools/us_rollcalls.py),
so an amendment vote on a spending bill shows "abortion" because the bill's
summary mentions the Hyde Amendment. Every vote line says whether its own
text matched or only its bill did, so a reader can discount the second kind
until amendment purposes (phase 1b, the Congress.gov key) arrive.

SCORES ARE OPTIONAL. Everything renders with no judge run at all
(CLAUDE.md: everything must run with TRIAGE=stub). Unscored items are
ranked by stage and cosponsors and say they are unscored.

Read-only on the store.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402

TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
REPO = "https://github.com/thejoycething-code/parl-monitor/blob/main/"
HIDDEN_AREAS = (11,)
WEEK_DAYS = 7
CONGRESS = 119

# Fixed dates, each with what it means for the store. Kept here, not in prose,
# so the edition can count down to them.
DATES = (
    ("2026-11-03", "Midterm elections: every House seat and a third of the Senate"),
    ("2027-01-03", "The 119th Congress ends; every bill not enacted falls, and must be "
                   "re-introduced in the 120th under a new number"),
)

HONESTY = (
    "> **How to read this edition.** Areas come from the shared taxonomy (v{0}), "
    "whose American terms were added on 9 October 2026 and have not yet been "
    "reviewed by anyone who campaigns in the US. Bills are matched on their "
    "titles, their Congressional Research Service subject terms and summary. A "
    "vote takes its bill's areas, so every vote line says whether its **own** "
    "text matched or only its **bill** did: on spending and defence bills the "
    "second kind is often noise until amendment purposes are collected. "
    "Results, tallies and party splits are the record; whether a vote helped "
    "or hurt is a human call and is never made here. {1}"
)

TYPE_LABEL = {"hr": "H.R.", "s": "S.", "hres": "H.Res.", "sres": "S.Res.",
              "hjres": "H.J.Res.", "sjres": "S.J.Res.", "hconres": "H.Con.Res.",
              "sconres": "S.Con.Res."}
TYPE_URL = {"hr": "house-bill", "s": "senate-bill", "hres": "house-resolution",
            "sres": "senate-resolution", "hjres": "house-joint-resolution",
            "sjres": "senate-joint-resolution", "hconres": "house-concurrent-resolution",
            "sconres": "senate-concurrent-resolution"}

# Stage from the latest action's own words. Rank orders "how close to law".
STAGES = (
    (0, "Law", ("became public law", "signed by president")),
    (1, "To the President", ("presented to president", "cleared for white house")),
    (2, "Agreed", ("resolution agreed to", "agreed to in senate", "agreed to in house",
                   "agreed to without amendment", "agreed to by voice vote",
                   "agreed to by unanimous consent", "concurrent resolution agreed")),
    (2, "Passed one chamber", ("received in the senate", "received in the house",
                               "passed senate", "passed house", "held at the desk",
                               "message on senate action")),
    (3, "Failed on the floor", ("not invoked", "failed of passage", "failed by")),
    (4, "Reported or on the calendar", ("placed on", "reported by", "ordered to be reported",
                                        "reported (amended)", "reported with",
                                        "discharged")),
    (5, "In committee", ("referred to", "subcommittee", "hearings held",
                         "committee consideration")),
)


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


def stage(row):
    """(rank, label) from the bill's law field and latest action."""
    if row["law"]:
        return 0, "Law ({0})".format(row["law"])
    text = (row["latest_action"] or "").lower()
    # The second chamber's passage reads "Passed Senate" on a HOUSE bill: that
    # is both chambers, not one (H.R. 1744, 29 September 2026).
    house_origin = (row["bill_type"] or "").startswith("h")
    if ("passed senate" in text and house_origin) or ("passed house" in text and not house_origin):
        return 1, "Passed both chambers"
    for rank, label, needles in STAGES:
        if any(n in text for n in needles):
            return rank, label
    return 6, "Introduced"


def bill_label(key):
    _c, btype, number = key.split("/")
    return "{0} {1}".format(TYPE_LABEL.get(btype, btype.upper()), number)


def bill_url(key):
    congress, btype, number = key.split("/")
    return "https://www.congress.gov/bill/{0}th-congress/{1}/{2}".format(
        congress, TYPE_URL.get(btype, btype), number)


def vote_url(row):
    if row["chamber"] == "senate":
        return ("https://www.senate.gov/legislative/LIS/roll_call_votes/vote{0}{1}/"
                "vote_{0}_{1}_{2:05d}.htm").format(row["congress"], row["session"], row["roll"])
    return "https://clerk.house.gov/Votes/{0}{1}".format((row["date"] or "????")[:4], row["roll"])


def sponsor(row):
    """'Rep. Steube, W. Gregory [R-FL-17]' -> 'Rep. Steube (R-FL-17)'."""
    m = re.match(r"^(\S+\.?)\s+([^,\[]+)[^\[]*\[([^\]]+)\]", row["sponsor_name"] or "")
    return "{0} {1} ({2})".format(m.group(1), m.group(2).strip(), m.group(3)) if m else (
        row["sponsor_name"] or "?")


def score_mark(score):
    return "**[{0}]**".format(score) if score is not None else "·"


def party_split(conn, division_key):
    """'R 210-3, D 2-205' (Yea-Nay by party at the vote), majors first."""
    counts = {}
    for party, position, n in conn.execute(
            "SELECT party, position, COUNT(*) FROM us_votes WHERE division_key=? "
            "GROUP BY party, position", (division_key,)):
        counts.setdefault(party or "?", {})[position] = n
    parts = []
    for party in sorted(counts, key=lambda p: ({"R": 0, "D": 1}.get(p, 2), p)):
        c = counts[party]
        parts.append("{0} {1}-{2}".format(party, c.get("Yea", 0), c.get("Nay", 0)))
    return ", ".join(parts)


def edition_number(today):
    dates = {os.path.basename(f)[len("us-monitor-"):-len(".md")]
             for f in glob.glob(os.path.join(ROOT, "editions", "us-monitor-*.md"))}
    dates.add(today)
    return sorted(dates).index(today) + 1


# --- queries -----------------------------------------------------------------

def votes_on_our_ground(conn, since, until):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT d.*, b.title AS bill_title, b.triage_score AS bill_score, "
        "b.why_it_matters AS bill_why FROM us_divisions d "
        "LEFT JOIN us_bills b ON b.bill_key = d.bill_key "
        "WHERE d.date > ? AND d.date <= ? ORDER BY d.date DESC, d.roll DESC",
        (since, until)).fetchall()
    return [r for r in rows if visible(r["areas"])]


def fold_votes(rows):
    """One line per (chamber, measure, question, result): the Senate took the
    same cloture vote on the shutdown CR some twenty times, and twenty lines
    for one story read as twenty findings."""
    groups, order = {}, []
    for r in rows:
        key = (r["chamber"], r["bill_key"] or r["legis_num"], (r["question"] or "")[:60],
               r["result"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    return [groups[k] for k in order]


def bills_where(conn, where, params=()):
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM us_bills WHERE " + where, params).fetchall()
    return [r for r in rows if visible(r["areas"])]


def rank_bills(rows):
    """Scored first by score; then by stage, cosponsors and recency."""
    return sorted(rows, key=lambda r: (-(r["triage_score"] if r["triage_score"] is not None else 1.5),
                                       stage(r)[0], -(r["cosponsors"] or 0),
                                       r["latest_action_at"] or ""), reverse=False)


def last_vote(conn, chamber):
    row = conn.execute("SELECT MAX(date) FROM us_divisions WHERE chamber=?", (chamber,)).fetchone()
    return row[0] if row else None


def last_pull(conn):
    try:
        row = conn.execute("SELECT last_run FROM source_runs WHERE source='US weekly'").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None


# --- rendering ---------------------------------------------------------------

def bill_row(r, names):
    return "| {0} [{1}]({2}) {3} | {4} | {5} | {6} | {7} |".format(
        score_mark(r["triage_score"]), bill_label(r["bill_key"]), bill_url(r["bill_key"]),
        clip(r["title"], 90), names_of(visible(r["areas"]), names), stage(r)[1],
        "{0}, {1} cosponsor(s)".format(sponsor(r), r["cosponsors"] or 0),
        clip(r["why_it_matters"] or ("{0} ({1})".format(r["latest_action"], r["latest_action_at"])
                                     if r["latest_action"] else ""), 160))


BILL_HEAD = ("| Bill | Areas | Stage | Sponsor | Why it matters, or the latest action |\n"
             "|---|---|---|---|---|")


def vote_lines(conn, groups, names):
    out = []
    for g in groups:
        r = g[0]
        own = visible(r["own_areas"])
        matched = "own text" if own else "bill only"
        measure = ("[{0}]({1}) {2}".format(r["legis_num"], bill_url(r["bill_key"]),
                                           clip(r["bill_title"], 70))
                   if r["bill_key"] else (r["legis_num"] or "no measure"))
        times = (" (x{0}, {1} to {2})".format(len(g), g[-1]["date"], r["date"])
                 if len(g) > 1 else "")
        score = r["triage_score"] if r["triage_score"] is not None else r["bill_score"]
        out.append("- {0} **{1}**, [{2} vote {3}]({4}), {5}{6}: {7}. **{8}** {9}-{10}; {11}. "
                   "*Areas: {12} (matched on {13}).*".format(
                       score_mark(score), r["chamber"].title(), r["chamber"].title(), r["roll"],
                       vote_url(r), r["date"], times, clip(r["question"], 80), r["result"],
                       r["yeas"], r["nays"], party_split(conn, r["division_key"]) or "no split",
                       names_of(visible(r["areas"]), names), matched))
        if r["amendment_author"] or (r["chamber"] == "senate" and "Amdt" in (r["description"] or "")):
            out.append("  - {0}".format(clip(r["amendment_author"] or r["description"], 200)))
        why = r["why_it_matters"] or r["bill_why"]
        if why:
            out.append("  - *{0}*".format(oneline(why)))
    return out


# --- executive actions and the Supreme Court (9 October 2026) ---------------
#
# Christopher said yes to both sections on 9 October 2026. Each is a view of
# its own table (tools/us_federal_register.py, tools/us_courts.py), and each
# renders on an empty or missing table: a store that has not run those
# collectors yet says so rather than failing the edition.

CLOSING_SOON_DAYS = 14


def _rows(conn, sql, params=()):
    conn.row_factory = sqlite3.Row
    try:
        return [r for r in conn.execute(sql, params).fetchall() if visible(r["areas"])]
    except sqlite3.OperationalError:
        return []


def safe_count(conn, sql):
    try:
        return conn.execute(sql).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def fr_label(r):
    """'Executive Order 14187', 'Proclamation', 'Final rule', 'Proposed rule'."""
    if r["doc_type"] == "Presidential Document":
        return "{0}{1}".format(r["subtype"] or "Presidential document",
                               " " + r["eo_number"] if r["eo_number"] else "")
    return {"Rule": "Final rule", "Proposed Rule": "Proposed rule"}.get(r["doc_type"],
                                                                         r["doc_type"])


def fr_agency(r):
    names = json.loads(r["agencies"] or "[]")
    return names[-1] if names else "?"


def executive_section(conn, since, today, names):
    new = _rows(conn, "SELECT * FROM us_fr_documents WHERE publication_date > ? AND "
                      "publication_date <= ? ORDER BY publication_date DESC", (since, today))
    open_ = _rows(conn, "SELECT * FROM us_fr_documents WHERE doc_type='Proposed Rule' AND "
                        "comments_close_on >= ? ORDER BY comments_close_on, document_number",
                  (today,))
    out = ["## Executive actions", "",
           "*The Federal Register: executive orders, proclamations and memoranda, final rules "
           "and proposed rules, matched on their titles and the agency's abstract "
           "(presidential documents have no abstract and match on the title alone).*", "",
           "### New on our ground this week ({0})".format(len(new)), ""]
    for r in new:
        out.append("- {0} **{1}**, {2}: [{3}]({4}). *{5}; areas: {6}.*{7}".format(
            score_mark(r["triage_score"]), fr_label(r), r["publication_date"],
            clip(r["title"], 120), r["html_url"], fr_agency(r),
            names_of(visible(r["areas"]), names),
            " Comments close {0}.".format(r["comments_close_on"]) if r["comments_close_on"] else ""))
        if r["why_it_matters"]:
            out.append("  - *{0}*".format(oneline(r["why_it_matters"])))
    if not new:
        out.append("*Nothing new on our ground in the Federal Register this week.*")
    out += ["", "### Open for comment ({0})".format(len(open_)), "",
            "*Proposed rules on our ground whose comment period has not closed: the one "
            "executive-branch step where anyone can put a view on the record.*", ""]
    for r in open_:
        days = (datetime.date.fromisoformat(r["comments_close_on"])
                - datetime.date.fromisoformat(today)).days
        when = "closes {0} ({1} day{2})".format(r["comments_close_on"], days,
                                               "" if days == 1 else "s")
        out.append("- {0} {1}: [{2}]({3}), {4}.{5} *Areas: {6}.*".format(
            score_mark(r["triage_score"]),
            "**" + when + "**" if days <= CLOSING_SOON_DAYS else when,
            clip(r["title"], 110), r["html_url"], fr_agency(r),
            " [Comment]({0}).".format(r["comment_url"]) if r["comment_url"] else "",
            names_of(visible(r["areas"]), names)))
    if not open_:
        out.append("*No proposed rule on our ground is open for comment.*")
    out.append("")
    return out


def court_section(conn, since, today, names):
    week = _rows(conn, "SELECT * FROM us_court_cases WHERE decided > ? AND decided <= ? "
                       "ORDER BY decided DESC, case_key", (since, today))
    opinions = _rows(conn, "SELECT * FROM us_court_cases WHERE kind='opinion'")
    try:
        all_dockets = {d.strip() for (x,) in conn.execute(
            "SELECT docket FROM us_court_cases WHERE kind='opinion'") for d in (x or "").split(",")}
    except sqlite3.OperationalError:
        all_dockets = set()
    pending = [r for r in _rows(conn, "SELECT * FROM us_court_cases WHERE kind='grant' "
                                      "ORDER BY decided DESC")
               if r["docket"] not in all_dockets]
    term = max((r["term"] for r in opinions if r["term"]), default=None)
    this_term = sorted((r for r in opinions if r["term"] == term),
                       key=lambda r: r["decided"] or "", reverse=True)

    def line(r):
        what = ("opinion, {0}".format(r["citation"]) if r["kind"] == "opinion" and r["citation"]
                else "opinion" if r["kind"] == "opinion" else "certiorari granted")
        return "- {0} [{1}]({2}) (No. {3}), {4}, {5}: {6} *Areas: {7}.*".format(
            score_mark(r["triage_score"]), r["case_name"] or "?", r["url"], r["docket"] or "?",
            what, r["decided"] or "?", clip(r["summary"] or "question presented not read", 260),
            names_of(visible(r["areas"]), names))

    out = ["## Supreme Court", "",
           "*Opinions are matched on the Court's one-line holding, grants on the question "
           "presented; the case name alone is party names and matches nothing.*", "",
           "### This week ({0})".format(len(week)), ""]
    out += [line(r) for r in week] or ["*No opinion or grant on our ground this week.*"]
    out += ["", "### Granted, awaiting decision ({0})".format(len(pending)), ""]
    out += [line(r) for r in pending] or ["*None on our ground.*"]
    if term:
        out += ["", "### Decided on our ground, October Term 20{0} ({1})".format(
            term, len(this_term)), ""]
        out += [line(r) for r in this_term] or ["*None.*"]
    out.append("")
    return out


def executive_court_tops(conn, since, today):
    """Top lines from the two sections: what is new, and what closes soon."""
    out = []
    fr = _rows(conn, "SELECT * FROM us_fr_documents WHERE publication_date > ? AND "
                     "publication_date <= ?", (since, today))
    if fr:
        out.append("- {0} executive action(s) on our ground in the Federal Register, "
                   "among them {1}: {2}.".format(len(fr), fr_label(fr[0]).lower()
                                                 if fr[0]["doc_type"] != "Presidential Document"
                                                 else fr_label(fr[0]), clip(fr[0]["title"], 80)))
    soon = (datetime.date.fromisoformat(today)
            + datetime.timedelta(days=CLOSING_SOON_DAYS)).isoformat()
    closing = _rows(conn, "SELECT * FROM us_fr_documents WHERE doc_type='Proposed Rule' AND "
                          "comments_close_on >= ? AND comments_close_on <= ? "
                          "ORDER BY comments_close_on", (today, soon))
    if closing:
        out.append("- **{0} comment period(s) on our ground close within {1} days**, the first "
                   "on {2}: {3}.".format(len(closing), CLOSING_SOON_DAYS,
                                         closing[0]["comments_close_on"],
                                         clip(closing[0]["title"], 80)))
    court = _rows(conn, "SELECT * FROM us_court_cases WHERE decided > ? AND decided <= ?",
                  (since, today))
    if court:
        out.append("- **Supreme Court**: {0}.".format("; ".join(
            "{0} ({1})".format(r["case_name"], "opinion" if r["kind"] == "opinion"
                               else "certiorari granted") for r in court[:3])))
    return out


def render_edition(conn, today):
    conn.row_factory = sqlite3.Row
    names = area_names()
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=WEEK_DAYS)).isoformat()
    month = (datetime.date.fromisoformat(today) - datetime.timedelta(days=30)).isoformat()
    scored = conn.execute("SELECT COUNT(*) FROM us_bills WHERE triage_score IS NOT NULL").fetchone()[0]
    score_note = ("Scores [0-3] and why-lines come from the judge (src/triage.py, US frame)."
                  if scored else
                  "**No item is scored yet**: the US judge has not been run, so items are "
                  "ranked by stage and cosponsors and carry the latest action in place of a "
                  "why-line.")
    week_votes = votes_on_our_ground(conn, since, today)
    moved = bills_where(conn, "latest_action_at > ? AND latest_action_at <= ? "
                              "AND (introduced IS NULL OR introduced <= ?)", (since, today, since))
    new = bills_where(conn, "introduced > ? AND introduced <= ?", (since, today))
    # A simple resolution (H.Res./S.Res.) agreed to is finished business, and
    # is mostly commemorative: National Adoption Day is not a live bill.
    agreed_simple = [r for r in bills_where(conn, "law IS NULL AND bill_type IN ('hres', 'sres')")
                     if stage(r)[1] == "Agreed"]
    live = [r for r in bills_where(conn, "law IS NULL") if 1 <= stage(r)[0] <= 4
            and r not in agreed_simple]
    laws = bills_where(conn, "law IS NOT NULL")
    committee = [r for r in bills_where(conn, "law IS NULL") if stage(r)[0] >= 5]
    pending_all = bills_where(conn, "law IS NULL")

    out = ["# US Congress Monitor",
           "### Week ending {0} | Edition {1} | {2}th Congress".format(
               today, edition_number(today), CONGRESS), "",
           HONESTY.format(taxonomy_version(), score_note), ""]

    # Top lines
    out += ["## Top lines", ""]
    tops = []
    for g in fold_votes(week_votes)[:3]:
        r = g[0]
        tops.append("- **{0} vote{1}** on {2}: {3}, {4} {5}-{6}.".format(
            r["chamber"].title(), "s" if len(g) > 1 else "", r["legis_num"] or "a nomination",
            clip(r["question"], 70), r["result"], r["yeas"], r["nays"]))
    for r in rank_bills([b for b in moved if stage(b)[0] <= 4])[:6 - len(tops)]:
        tops.append("- {0} [{1}]({2}) {3}: {4}.".format(
            score_mark(r["triage_score"]), bill_label(r["bill_key"]), bill_url(r["bill_key"]),
            clip(r["title"], 80), stage(r)[1].lower()))
    if not week_votes:
        tops.insert(0, "- **Congress recorded no vote on our ground this week.** The House last "
                       "voted on {0}, the Senate on {1}.".format(
                           last_vote(conn, "house") or "?", last_vote(conn, "senate") or "?"))
    if new:
        tops.append("- {0} new bill(s) on our ground were introduced.".format(len(new)))
    tops += executive_court_tops(conn, since, today)
    out += tops or ["*Nothing moved on our ground this week.*"]
    out.append("")

    # Dates that matter
    out += ["## Dates that matter", ""]
    for date, what in DATES:
        days = (datetime.date.fromisoformat(date) - datetime.date.fromisoformat(today)).days
        if days < 0:
            continue
        extra = ""
        if date == "2027-01-03":
            extra = " **{0} bill(s) on our ground are pending and fall then unless enacted.**".format(
                len(pending_all))
        out.append("- **{0}** ({1} days): {2}.{3}".format(date, days, what, extra))
    out.append("")

    # Votes
    if week_votes:
        out += ["## Recorded votes this week ({0})".format(len(week_votes)), ""]
        out += vote_lines(conn, fold_votes(week_votes), names)
    else:
        recent = votes_on_our_ground(conn, month, today)
        out += ["## Recorded votes (none this week; last 30 days: {0})".format(len(recent)), ""]
        out += vote_lines(conn, fold_votes(recent), names) or ["*None in the last 30 days.*"]
    out.append("")

    # Bills
    out += ["## Bills that moved this week ({0})".format(len(moved)), ""]
    if moved:
        out += [BILL_HEAD] + [bill_row(r, names) for r in rank_bills(moved)[:25]]
        if len(moved) > 25:
            out.append("\n_...and {0} more; the store holds them all._".format(len(moved) - 25))
    else:
        out.append("*No bill on our ground changed stage this week.*")
    out += ["", "## New bills this week ({0})".format(len(new)), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in rank_bills(new)]) if new else \
        ["*None introduced on our ground this week.*"]
    out += ["", "## Live beyond committee ({0})".format(len(live)), "",
            "*Bills on our ground that have passed a chamber, been reported, reached a calendar "
            "or failed on the floor, and are not yet law. Ordered by score, then how close to "
            "law, then cosponsors. {0} simple resolution(s) agreed to in one chamber "
            "(commemorations and sense-of-the-chamber statements, never law) are left "
            "out.*".format(len(agreed_simple)), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in rank_bills(live)[:30]]) if live else \
        ["*None.*"]
    if len(live) > 30:
        out.append("\n_...and {0} more._".format(len(live) - 30))
    out += ["", "## Most-backed in committee (top 15 of {0})".format(len(committee)), "",
            "*A cosponsor is a public, recorded position: these are where members have put "
            "their names, even where nothing has moved.*", ""]
    out += [BILL_HEAD] + [bill_row(r, names) for r in sorted(
        committee, key=lambda r: -(r["cosponsors"] or 0))[:15]]
    out += ["", "## Enacted this Congress ({0})".format(len(laws)), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in sorted(
        laws, key=lambda r: r["latest_action_at"] or "", reverse=True)]) if laws else ["*None.*"]

    out += [""] + executive_section(conn, since, today, names)
    out += court_section(conn, since, today, names)

    # Coverage
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    out += ["", "## Coverage", "",
            "- **Collected:** {0} bills and resolutions ({1} on our ground), {2} House and "
            "{3} Senate roll calls, every member's position on each, every cosponsorship. "
            "Last pull: {4}.".format(
                n("SELECT COUNT(*) FROM us_bills"),
                len(bills_where(conn, "1=1")),
                n("SELECT COUNT(*) FROM us_divisions WHERE chamber='house'"),
                n("SELECT COUNT(*) FROM us_divisions WHERE chamber='senate'"),
                last_pull(conn) or "unknown"),
            "- **Executive and Court:** {0} Federal Register documents since 20 January 2025 "
            "({1} on our ground); {2} Supreme Court opinions and {3} certiorari grants "
            "({4} on our ground).".format(
                safe_count(conn, "SELECT COUNT(*) FROM us_fr_documents"),
                len(_rows(conn, "SELECT areas FROM us_fr_documents")),
                safe_count(conn, "SELECT COUNT(*) FROM us_court_cases WHERE kind='opinion'"),
                safe_count(conn, "SELECT COUNT(*) FROM us_court_cases WHERE kind='grant'"),
                len(_rows(conn, "SELECT areas FROM us_court_cases"))),
            "- **Not yet collected:** amendment purposes for House votes (needs the "
            "Congress.gov key), the Congressional Record (floor debates), committee hearings, "
            "the weekly floor schedule, Federal Register notices (only presidential "
            "documents and rules are read), Supreme Court dockets beyond the granted cases, "
            "and the fifty state legislatures (needs the Open States key).",
            "- **Migration** is matched and stored but not shown, as in every edition here.",
            "- Specification and decisions: [docs/us-scope.md]({0}docs/us-scope.md).".format(REPO),
            ""]
    return "\n".join(out)


def dm_summary(conn, today, path=None):
    """The week in one Slack message, to Christopher alone."""
    conn.row_factory = sqlite3.Row
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=WEEK_DAYS)).isoformat()
    votes = votes_on_our_ground(conn, since, today)
    moved = bills_where(conn, "latest_action_at > ? AND latest_action_at <= ? "
                              "AND (introduced IS NULL OR introduced <= ?)", (since, today, since))
    new = bills_where(conn, "introduced > ? AND introduced <= ?", (since, today))
    pending_all = bills_where(conn, "law IS NULL")
    lines = [":us: *US Congress Monitor - week ending {0}*".format(today), ""]
    if votes:
        lines.append("*{0} recorded vote(s) on our ground* (House {1}, Senate {2}).".format(
            len(votes), sum(r["chamber"] == "house" for r in votes),
            sum(r["chamber"] == "senate" for r in votes)))
    else:
        lines.append("*No recorded vote on our ground this week.* House last voted {0}, "
                     "Senate {1}.".format(last_vote(conn, "house") or "?",
                                          last_vote(conn, "senate") or "?"))
    lines.append("{0} bill(s) moved, {1} new.".format(len(moved), len(new)))
    lines += [t.replace("**", "*") for t in executive_court_tops(conn, since, today)]
    top = rank_bills([b for b in moved + new if stage(b)[0] <= 4 or b in new])[:5]
    for r in top:
        why = r["why_it_matters"]
        lines.append("• {0}{1}: {2} ({3}){4}".format(
            "*[{0}]* ".format(r["triage_score"]) if r["triage_score"] is not None else "",
            bill_label(r["bill_key"]), clip(r["title"], 80), stage(r)[1].lower(),
            "\n   _{0}_".format(oneline(why)) if why else ""))
    days = (datetime.date(2027, 1, 3) - datetime.date.fromisoformat(today)).days
    if days >= 0:
        lines.append("_{0} pending bill(s) on our ground fall when the Congress ends in {1} "
                     "days (3 January 2027)._".format(len(pending_all), days))
    lines.append("_Areas from taxonomy v{0}; American terms not yet reviewed by a US "
                 "campaigner._".format(taxonomy_version()))
    if path:
        lines.append("Full edition: {0}{1}".format(REPO, os.path.relpath(path, ROOT)))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--edition", action="store_true", help="write editions/us-monitor-<date>.md")
    ap.add_argument("--dm", action="store_true", help="DM the summary to Christopher")
    ap.add_argument("--print", action="store_true", help="render to stdout, write nothing")
    args = ap.parse_args()
    conn = db.connect(args.db)
    conn.row_factory = sqlite3.Row
    text = render_edition(conn, args.date)
    path = os.path.join(ROOT, "editions", "us-monitor-{0}.md".format(args.date))
    if args.print:
        print(text)
        return 0
    if args.edition:
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
