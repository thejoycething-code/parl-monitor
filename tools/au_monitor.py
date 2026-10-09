#!/usr/bin/env python3
"""The Australian edition: its own document, and a DM to Christopher.

    python3 tools/au_monitor.py --edition              # write editions/au-monitor-<date>.md
    python3 tools/au_monitor.py --edition --dm         # and DM the summary
    python3 tools/au_monitor.py --print                # render to stdout, write nothing
    python3 tools/au_monitor.py --print --date 2026-10-09 --db /tmp/au.db

Decided 9 October 2026 (Christopher, confirming the US pattern): Australia
gets its own edition, and it goes to him alone, as a DM, until it is good.
Nothing posts to a channel. Modelled on tools/us_monitor.py.

WHAT LEADS. The Federal Parliament moves our ground through divisions (House
and Senate, with the Senate's pairs), bills reaching a new stage in the
Hansard, new bills, and Acts; speeches in debate (tools/au_debates.py) and
what is coming up (tools/au_schedule.py). The edition leads with the week and says
plainly when Parliament did not sit, rather than padding the top.

NO VERDICTS. A division carries its question, its tally, its pairs and its
party split, and never "a win" or "a defeat". "Agreed to" and "negatived"
are the arithmetic of ayes against noes, nothing more: a negatived motion to
refer gender dysphoria guidelines to a committee is not by itself good or bad
news, and which way a question cuts is a signed human judgement here as
everywhere in this repo.

INHERITED AREAS ARE MARKED. A division takes every tagged bill's areas
(tools/au_rollcalls.py), so each line says whether its own words matched or
only a bill did. Committee-stage amendments are moved by sheet number and
their text is on aph.gov.au, which refuses our collectors, so they always
read "bill only" until phase 1b.

SCORES ARE OPTIONAL. Everything renders with no judge run at all (CLAUDE.md:
everything must run with TRIAGE=stub). The judge (tools/au_triage.py) runs
only when the repository variable AU_JUDGE is 'on'.

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
PARLIAMENT = 48
FIRST_MEETING = "2025-07-22"
EXPIRY = "2028-07-21"

DATES = (
    (EXPIRY, "The House of Representatives expires three years from its first meeting "
             "(22 July 2025), unless it is dissolved sooner; at the dissolution every bill "
             "not yet an Act lapses, and returns, if at all, under a new ID"),
)

HONESTY = (
    "> **How to read this edition.** Areas come from the shared taxonomy (v{0}) and "
    "config/watchlist-au.yaml, applied by bill ID. Bills are matched on their **titles "
    "only**: the explanatory memoranda and bills digests are on aph.gov.au, which refuses "
    "our collectors. A division takes its bills' areas, so every division line says "
    "whether its **own** words (the headings, the question and the motion) matched or "
    "only its **bill** did. Senate pairs are shown as pairs: the record does not say which "
    "side each paired senator was on. \"Agreed to\" and \"negatived\" are ayes against "
    "noes; whether a division helped or hurt is a human call and is never made here. {1}"
)

PARTY = {"Australian Labor Party": "ALP", "Liberal Party": "LIB",
         "Liberal National Party": "LNP", "National Party": "NAT",
         "Australian Greens": "GRN", "Pauline Hanson's One Nation Party": "ONP",
         "Independent": "IND", "Jacqui Lambie Network": "JLN",
         "United Australia Party": "UAP", "Centre Alliance": "CA",
         "Katter's Australian Party": "KAP", "Country Liberal Party": "CLP",
         "Australia's Voice": "AV"}
PARTY_ORDER = ("ALP", "LIB", "LNP", "NAT", "CLP", "GRN", "ONP")


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


def sentence(text, n):
    """Clipped to n and closed with one full stop, never '….'."""
    text = clip((text or "").rstrip(". "), n)
    return text if text.endswith("\u2026") else text + "."


def lead_rank(group):
    """Top-line order with no verdict in it: a judge's score first; then a
    division whose own words hit a tier-1 term; then one on a bill on our
    ground; a tier-2 own-text hit (where most of the noise is) last."""
    r = group[0]
    score = r["triage_score"] if r["triage_score"] is not None else 1.5
    own = visible(r["own_areas"])
    kind = 0 if (own and r["tier"] == 1) else (1 if not own or r["bill_ids"] != "[]" else 2)
    return (-score, kind, -len(group))


def score_mark(score):
    return "**[{0}]**".format(score) if score is not None else "·"


def bill_url(bill_id):
    return ("https://www.aph.gov.au/Parliamentary_Business/Bills_Legislation/"
            "Bills_Search_Results/Result?bId={0}".format(bill_id))


def act_url(act_id):
    return "https://www.legislation.gov.au/{0}/asmade".format(act_id)


def outcome(ayes, noes):
    """Arithmetic, not a verdict."""
    if ayes is None or noes is None:
        return "count not recorded"
    if ayes > noes:
        return "Agreed to"
    if noes > ayes:
        return "Negatived"
    return "Tied"


def stage(row):
    """(rank, label): an Act first, then the last stage the Hansard named."""
    if row["act_id"]:
        return 0, "Act, assent {0}".format(row["assent_date"] or "?")
    if row["last_stage"]:
        return 1, "{0} ({1}, {2})".format(row["last_stage"], (row["last_stage_chamber"] or "?").title(),
                                          row["last_stage_date"] or "?")
    return 2, "Named in the Hansard {0}".format(row["first_date"] or "?")


def party_split(conn, division_key):
    """'ALP 0-60, LIB 20-0 ...; paired ALP 5, LIB 5' (Aye-No by party at the vote)."""
    counts = {}
    for party, position, n in conn.execute(
            "SELECT party, position, COUNT(*) FROM au_votes WHERE division_key=? "
            "GROUP BY party, position", (division_key,)):
        counts.setdefault(PARTY.get(party, party or "?"), {})[position] = n
    order = sorted(counts, key=lambda p: (PARTY_ORDER.index(p) if p in PARTY_ORDER else 99, p))
    votes = ["{0} {1}-{2}".format(p, counts[p].get("Aye", 0), counts[p].get("No", 0))
             for p in order if counts[p].get("Aye") or counts[p].get("No")]
    paired = ["{0} {1}".format(p, counts[p]["Paired"]) for p in order if counts[p].get("Paired")]
    return ", ".join(votes) + ("; paired " + ", ".join(paired) if paired else "")


def edition_number(today):
    dates = {os.path.basename(f)[len("au-monitor-"):-len(".md")]
             for f in glob.glob(os.path.join(ROOT, "editions", "au-monitor-*.md"))}
    dates.add(today)
    return sorted(dates).index(today) + 1


# --- queries -----------------------------------------------------------------

def divisions_on_our_ground(conn, since, until):
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM au_divisions WHERE date > ? AND date <= ? "
                        "ORDER BY date DESC, chamber, number DESC", (since, until)).fetchall()
    return [r for r in rows if visible(r["areas"])]


def fold_divisions(rows):
    """One line per (chamber, bills or heading, question, outcome): a closure
    or a second reading amendment put again and again is one story."""
    groups, order = {}, []
    for r in rows:
        key = (r["chamber"], r["bill_ids"] if r["bill_ids"] != "[]" else r["minor_heading"],
               (r["question"] or "")[:60], outcome(r["ayes"], r["noes"]))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    return [groups[k] for k in order]


def bills_where(conn, where, params=()):
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM au_bills WHERE parliament = ? AND " + where,
                        (PARLIAMENT,) + tuple(params)).fetchall()
    return [r for r in rows if visible(r["areas"])]


def by_recency(rows):
    """Scored first by score, then the most recent stage first."""
    return sorted(rows, key=lambda r: (r["triage_score"] if r["triage_score"] is not None else 1.5,
                                       r["last_stage_date"] or r["first_date"] or ""), reverse=True)


def bill_titles(conn, bill_ids):
    out = []
    for bid in bill_ids:
        row = conn.execute("SELECT title FROM au_bills WHERE bill_id=?", (bid,)).fetchone()
        out.append((bid, row[0] if row else None))
    return out


def last_division(conn, chamber):
    row = conn.execute("SELECT MAX(date) FROM au_divisions WHERE chamber=?", (chamber,)).fetchone()
    return row[0] if row else None


def last_sitting(conn):
    row = conn.execute("SELECT MAX(date) FROM au_hansard_files").fetchone()
    return row[0] if row else None


def last_pull(conn):
    try:
        row = conn.execute("SELECT last_run FROM source_runs WHERE source='Australia weekly'").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None


# --- coming up (tools/au_schedule.py) -------------------------------------------
#
# The APH sitting calendar, the Notice Papers and the Daily Programs are on
# aph.gov.au, which refuses our collectors, so which bill comes up on which
# day cannot be known here. What can: the sitting days the Federal Register
# of Legislation counts disallowance to (each last day for disallowance still
# ahead is a day that House is due to sit), the instruments on our ground
# whose disallowance window is open, any notice of a disallowance motion on
# them, and whether the Parliamentary Handbook records a dissolution.

AHEAD_DAYS = 60
SCHEDULE_HEARTBEAT = "AU week ahead"


def long_date(iso, weekday=True):
    """'2026-10-12' -> 'Monday 12 October' (British order, no comma)."""
    d = datetime.date.fromisoformat(iso)
    return "{0}{1} {2}".format(d.strftime("%A ") if weekday else "", d.day, d.strftime("%B"))


def day_runs(dates):
    """['2026-10-12', '2026-10-13', '2026-10-15'] -> '12 to 13 October, 15 October':
    consecutive days (weekends bridged) folded into one run."""
    runs = []
    for iso in sorted(dates):
        d = datetime.date.fromisoformat(iso)
        if runs and 0 < (d - runs[-1][1]).days <= (3 if runs[-1][1].weekday() == 4 else 1):
            runs[-1][1] = d
        else:
            runs.append([d, d])
    out = []
    for a, b in runs:
        if a == b:
            out.append("{0} {1}".format(a.day, a.strftime("%B")))
        elif a.month == b.month:
            out.append("{0} to {1} {2}".format(a.day, b.day, b.strftime("%B")))
        else:
            out.append("{0} {1} to {2} {3}".format(a.day, a.strftime("%B"), b.day, b.strftime("%B")))
    return ", ".join(out)


def instrument_url(title_id):
    return "https://www.legislation.gov.au/{0}/asmade".format(title_id)


def coming_up(conn, today):
    """Everything the section and the DM need, or None when the week ahead
    was never collected into this store."""
    conn.row_factory = sqlite3.Row
    try:
        read = conn.execute("SELECT last_run, note FROM source_runs WHERE source=?",
                            (SCHEDULE_HEARTBEAT,)).fetchone()
    except sqlite3.Error:
        return None
    if not read:
        return None
    until = (datetime.date.fromisoformat(today) + datetime.timedelta(days=AHEAD_DAYS)).isoformat()
    days = {ch: [r[0] for r in conn.execute(
        "SELECT date FROM au_sitting_days WHERE chamber=? AND date >= ? AND date <= ? ORDER BY date",
        (ch, today, until))] for ch in ("house", "senate")}
    open_all = conn.execute("SELECT COUNT(*) FROM au_instruments WHERE open=1").fetchone()[0]
    ours = [r for r in conn.execute("SELECT * FROM au_instruments WHERE open=1 ORDER BY "
                                    "COALESCE(MIN(last_day_house, last_day_senate), "
                                    "last_day_house, last_day_senate, '9999'), title_id")
            if visible(r["areas"])]
    parl = conn.execute("SELECT * FROM au_parliaments WHERE parliament=?", (PARLIAMENT,)).fetchone()
    return {"read": read["last_run"], "days": days, "open": open_all, "ours": ours, "parl": parl}


def _motions(r):
    try:
        events = json.loads(r["scrutiny"] or "[]")
    except (TypeError, ValueError):
        events = []
    return [e for e in events if e.get("type") == "DisallowanceMotion"]


def instrument_line(r, names, today):
    def last(day):
        if not day:
            return "no clock running"
        return "{0}{1}".format(long_date(day, weekday=False), " (passed)" if day < today else "")
    source = {"own": "its own name", "act": "the Act it is made under",
              "bill": "the bill its Act came from"}.get(r["areas_from"], "?")
    out = ["- [{0}]({1}) {2}: last day to disallow, House {3}, Senate {4}. *Areas: {5} "
           "(matched on {6}).*".format(r["title_id"], instrument_url(r["title_id"]),
                                       clip(r["name"], 110), last(r["last_day_house"]),
                                       last(r["last_day_senate"]),
                                       names_of(visible(r["areas"]), names), source)]
    if r["bill_id"]:
        out.append("  - Made under the Act of [{0}]({1}).".format(r["bill_id"], bill_url(r["bill_id"])))
    for m in _motions(r):
        out.append("  - **Notice of a disallowance motion**: {0}, {1}, {2}{3}.".format(
            m.get("sponsor") or "sponsor not recorded", (m.get("house") or "?").title(),
            long_date(m["date"], weekday=False) if m.get("date") else "date not recorded",
            ", outcome: {0}".format(m["outcome"]) if m.get("outcome") else ""))
    return out


def render_coming_up(conn, today, names):
    c = coming_up(conn, today)
    head = "## Coming up"
    if c is None:
        return [head, "", "*The week ahead was not collected for this edition "
                          "(tools/au_schedule.py has not run on this store).*", ""]
    out = [head, "",
           "*The sitting calendar, the Notice Papers and the Daily Programs are on aph.gov.au, "
           "which refuses our collectors, so this cannot say which bill comes up or when. What "
           "it can see, from the Federal Register of Legislation and the Parliamentary Handbook "
           "(read {0}):*".format(c["read"]), ""]
    parl = c["parl"]
    if parl is not None and parl["dissolution"]:
        out += ["**The {0}th Parliament was dissolved on {1}** (Parliamentary Handbook): every "
                "bill before it has lapsed.".format(PARLIAMENT, parl["dissolution"]), ""]
    for ch in ("house", "senate"):
        days = c["days"][ch]
        label = "House" if ch == "house" else "Senate"
        if days:
            out.append("- **{0}**: next sitting {1}; days due to sit in the next {2} days: "
                       "{3}.".format(label, long_date(days[0]), AHEAD_DAYS, day_runs(days)))
        else:
            out.append("- **{0}**: no sitting day ahead is visible.".format(label))
    out += ["", "*These are the days the Register counts disallowance to: every one is a sitting "
                "day, but a sitting day on which no instrument's clock ends is missing, and "
                "Senate estimates are not shown.*", ""]
    out.append("**Instruments open for disallowance on our ground: {0} of {1}.**".format(
        len(c["ours"]), c["open"]))
    if c["ours"]:
        out.append("")
        for r in c["ours"]:
            out += instrument_line(r, names, today)
    else:
        out.append("*None of the instruments the Register lists as open for disallowance is "
                   "on our ground (by name, by the Act it is made under, or by the bill that "
                   "Act came from).*")
    out.append("")
    return out


def coming_up_dm(conn, today):
    c = coming_up(conn, today)
    if c is None:
        return None
    parts = []
    for ch, label in (("house", "House"), ("senate", "Senate")):
        days = c["days"][ch]
        parts.append("{0} next sits {1}".format(label, long_date(days[0], weekday=False))
                     if days else "{0}: no sitting day visible".format(label))
    parts.append("{0} instrument(s) on our ground open for disallowance".format(len(c["ours"])))
    motions = sum(len(_motions(r)) for r in c["ours"])
    if motions:
        parts.append("{0} disallowance motion(s) on them".format(motions))
    return "*Coming up:* " + "; ".join(parts) + " (from the Register; the APH calendar is blocked)."


# --- debate (tools/au_debates.py) -----------------------------------------------
#
# Speeches on our ground: the speaker, the day, the debate, one line of the
# speaker's own words and the link, NEVER the speech itself.

DEBATE_LINES = 20
FROM_LABEL = {"own": "own words", "watch": "the watchlist bill debated",
              "bill": "the bill debated"}
KIND_LABEL = {"motion": " (moving a motion)", "notice": " (notice of motion)", "speech": ""}


def _speeches(conn, where, params=()):
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM au_speeches WHERE " + where +
                            " ORDER BY COALESCE(triage_score, 1.5) DESC, date DESC, speech_key",
                            params).fetchall()
    except sqlite3.Error:
        return None
    return [r for r in rows if visible(r["areas"])]


def speech_line(r, names):
    bills = json.loads(r["bill_ids"] or "[]")
    on = clip(r["minor_heading"] or r["major_heading"] or "?", 80)
    if bills:
        on += " ({0})".format(", ".join("[{0}]({1})".format(b, bill_url(b)) for b in bills[:2]))
    return ("- {0} **{1}**, {2}, {3} ({4}){5}, on {6}: \"{7}\" [Hansard]({8}). "
            "*Areas: {9} (matched on {10}).*".format(
                score_mark(r["triage_score"]), r["chamber"].title(), r["date"],
                r["name"] or "?", PARTY.get(r["party"], r["party"] or "?"),
                KIND_LABEL.get(r["kind"], ""), on, clip(r["excerpt"], 200), r["url"],
                names_of(visible(r["areas"]), names), FROM_LABEL.get(r["areas_from"], "?")))


def render_debate(conn, today, since, month, names):
    week = _speeches(conn, "date > ? AND date <= ?", (since, today))
    head = "## Debate"
    if week is None:
        return [head, "", "*Debates were not collected for this edition.*", ""]
    note = ("*Speeches and motions on our ground in the House and the Senate, from the "
            "OpenAustralia Foundation's parse of the Hansard: matched on the speaker's own "
            "words, or on the bill being debated for a full speech (150 words or more) that "
            "matched nothing itself. One line each and the link, never the speech.*")
    if week:
        out = ["{0} this week ({1})".format(head, len(week)), "", note, ""]
        out += [speech_line(r, names) for r in week[:DEBATE_LINES]]
        if len(week) > DEBATE_LINES:
            out.append("\n_...and {0} more._".format(len(week) - DEBATE_LINES))
        return out + [""]
    recent = _speeches(conn, "date > ? AND date <= ?", (month, today)) or []
    out = ["{0} (none this week; last 30 days: {1})".format(head, len(recent)), "", note, ""]
    out += [speech_line(r, names) for r in recent[:DEBATE_LINES]] or [
        "*No speech on our ground in the last 30 days, or the debates backfill has not reached "
        "them yet (it reads newest days first).*"]
    if len(recent) > DEBATE_LINES:
        out.append("\n_...and {0} more._".format(len(recent) - DEBATE_LINES))
    return out + [""]


# --- rendering ---------------------------------------------------------------

BILL_HEAD = ("| Bill | Areas | Stage | Why it matters, or where it stands |\n"
             "|---|---|---|---|")


def bill_row(r, names):
    link = "[{0}]({1})".format(r["bill_id"], bill_url(r["bill_id"]))
    where = r["why_it_matters"] or (
        "[{0}]({1})".format(oneline(r["act_name"]), act_url(r["act_id"])) if r["act_id"] else
        "{0} bill, first named {1}".format((r["origin"] or "?").title(), r["first_date"] or "?"))
    return "| {0} {1} {2} | {3} | {4} | {5} |".format(
        score_mark(r["triage_score"]), link, clip(r["title"], 100),
        names_of(visible(r["areas"]), names), stage(r)[1], clip(where, 160))


def division_lines(conn, groups, names):
    out = []
    for g in groups:
        r = g[0]
        own = visible(r["own_areas"])
        times = (" (x{0}, {1} to {2})".format(len(g), g[-1]["date"], r["date"]) if len(g) > 1 else "")
        pairs = ", {0} pairs".format(r["pairs"]) if r["pairs"] else ""
        out.append("- {0} **{1}**, [division {2}]({3}), {4}{5}: {6} **{7}** {8}-{9}{10}; {11}. "
                   "*Areas: {12} (matched on {13}).*".format(
                       score_mark(r["triage_score"]), r["chamber"].title(), r["number"],
                       r["source_url"] or "", r["date"], times,
                       sentence(r["question"] or r["minor_heading"], 110),
                       outcome(r["ayes"], r["noes"]), r["ayes"], r["noes"], pairs,
                       party_split(conn, r["division_key"]) or "no split recorded",
                       names_of(visible(r["areas"]), names),
                       "own text" if own else "bill only"))
        bills = json.loads(r["bill_ids"] or "[]")
        if bills:
            out.append("  - On: " + "; ".join("[{0}]({1}) {2}".format(b, bill_url(b), clip(t, 80))
                                              for b, t in bill_titles(conn, bills)[:3])
                       + (" and {0} more".format(len(bills) - 3) if len(bills) > 3 else ""))
        else:
            out.append("  - Business: {0}".format(clip(r["minor_heading"] or r["major_heading"], 120)))
        if r["motion"] and own:
            out.append("  - Motion: {0}".format(clip(r["motion"], 240)))
        if r["why_it_matters"]:
            out.append("  - *{0}*".format(oneline(r["why_it_matters"])))
    return out


def render_edition(conn, today):
    conn.row_factory = sqlite3.Row
    names = area_names()
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=WEEK_DAYS)).isoformat()
    month = (datetime.date.fromisoformat(today) - datetime.timedelta(days=30)).isoformat()
    scored = (conn.execute("SELECT COUNT(*) FROM au_bills WHERE triage_score IS NOT NULL").fetchone()[0]
              + conn.execute("SELECT COUNT(*) FROM au_divisions WHERE triage_score IS NOT NULL")
              .fetchone()[0])
    score_note = ("Scores [0-3] and why-lines come from the judge (tools/au_triage.py, "
                  "Australian frame)." if scored else
                  "**No item is scored yet**: the Australian judge has not been run, so items "
                  "are ranked by stage and date and carry where they stand in place of a "
                  "why-line.")
    week = divisions_on_our_ground(conn, since, today)
    moved = bills_where(conn, "((last_stage_date > ? AND last_stage_date <= ?) OR "
                              "(assent_date > ? AND assent_date <= ?)) AND first_date <= ?",
                        (since, today, since, today, since))
    new = bills_where(conn, "first_date > ? AND first_date <= ?", (since, today))
    enacted = bills_where(conn, "act_id IS NOT NULL")
    live = bills_where(conn, "act_id IS NULL")

    out = ["# Australian Parliament Monitor",
           "### Week ending {0} | Edition {1} | {2}th Parliament".format(
               today, edition_number(today), PARLIAMENT), "",
           HONESTY.format(taxonomy_version(), score_note), ""]

    out += ["## Top lines", ""]
    tops = []
    if not week:
        tops.append("- **Parliament recorded no division on our ground this week.** The House "
                    "last divided on {0}, the Senate on {1}; the last sitting day in the store "
                    "is {2}.".format(last_division(conn, "house") or "?",
                                     last_division(conn, "senate") or "?",
                                     last_sitting(conn) or "?"))
    for g in sorted(fold_divisions(week), key=lead_rank)[:3]:
        r = g[0]
        tops.append("- **{0} division{1}** on {2}: {3}, {4} {5}-{6}.".format(
            r["chamber"].title(), "s" if len(g) > 1 else "", clip(r["minor_heading"], 80),
            clip((r["question"] or "").rstrip(". "), 70), outcome(r["ayes"], r["noes"]).lower(),
            r["ayes"], r["noes"]))
    for r in by_recency(moved)[:max(0, 6 - len(tops))]:
        tops.append("- {0} [{1}]({2}) {3}: {4}.".format(
            score_mark(r["triage_score"]), r["bill_id"], bill_url(r["bill_id"]),
            clip(r["title"], 80), stage(r)[1]))
    if new:
        tops.append("- {0} new bill(s) on our ground were named in the Hansard.".format(len(new)))
    out += tops + [""]

    out += ["## Dates that matter", ""]
    for date, what in DATES:
        days = (datetime.date.fromisoformat(date) - datetime.date.fromisoformat(today)).days
        if days >= 0:
            out.append("- **{0} at the latest** ({1} days): {2}. **{3} bill(s) on our ground are "
                       "before Parliament now.**".format(date, days, what, len(live)))
    ahead = coming_up(conn, today)
    nxt = [d[0] for d in (ahead["days"].values() if ahead else []) if d]
    if nxt:
        out.append("- **{0}**: Parliament next sits (the House or the Senate; see Coming up). "
                   "The last sitting day in the store is {1}.".format(
                       long_date(min(nxt)), last_sitting(conn) or "?"))
    out += ["- **The sitting calendar and Senate estimates** are published on aph.gov.au, which "
            "refuses our collectors; the sitting days in Coming up are read from the Federal "
            "Register of Legislation's disallowance clock, not the calendar. The last sitting "
            "day in the store is {0}.".format(last_sitting(conn) or "?"), ""]
    out += render_coming_up(conn, today, names)

    if week:
        out += ["## Divisions this week ({0})".format(len(week)), ""]
        out += division_lines(conn, fold_divisions(week), names)
    else:
        recent = divisions_on_our_ground(conn, month, today)
        out += ["## Divisions (none this week; last 30 days: {0})".format(len(recent)), ""]
        out += division_lines(conn, fold_divisions(recent), names) or ["*None in the last 30 days.*"]
    out.append("")
    out += render_debate(conn, today, since, month, names)

    out += ["## Bills that moved this week ({0})".format(len(moved)), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in by_recency(moved)]) if moved else \
        ["*No bill on our ground reached a new stage in the Hansard this week.*"]
    out += ["", "## New bills this week ({0})".format(len(new)), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in by_recency(new)]) if new else \
        ["*None named in the Hansard this week.*"]
    out += ["", "## Before Parliament ({0})".format(len(live)), "",
            "*Bills of the {0}th Parliament on our ground that are not yet Acts. Ordered by score, "
            "then the latest stage the Hansard named.*".format(PARLIAMENT), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in by_recency(live)[:30]]) if live else ["*None.*"]
    if len(live) > 30:
        out.append("\n_...and {0} more._".format(len(live) - 30))
    out += ["", "## Enacted this Parliament ({0})".format(len(enacted)), ""]
    out += ([BILL_HEAD] + [bill_row(r, names) for r in sorted(
        enacted, key=lambda r: r["assent_date"] or "", reverse=True)]) if enacted else ["*None.*"]

    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    out += ["", "## Coverage", "",
            "- **Collected:** {0} bills of the {1}th Parliament ({2} on our ground, {3} became "
            "Acts), {4} House and {5} Senate divisions with every member's vote and the Senate's "
            "pairs, from {6} Hansard sitting-day files. Last pull: {7}.".format(
                n("SELECT COUNT(*) FROM au_bills WHERE parliament={0}".format(PARLIAMENT)),
                PARLIAMENT, len(bills_where(conn, "1=1")),
                n("SELECT COUNT(*) FROM au_bills WHERE parliament={0} AND act_id IS NOT NULL"
                  .format(PARLIAMENT)),
                n("SELECT COUNT(*) FROM au_divisions WHERE chamber='house'"),
                n("SELECT COUNT(*) FROM au_divisions WHERE chamber='senate'"),
                n("SELECT COUNT(*) FROM au_hansard_files"), last_pull(conn) or "unknown"),
            "- **Blocked:** aph.gov.au and ParlInfo refuse our collectors (an Azure WAF block "
            "page on every request). So this edition has no bill texts, explanatory memoranda, "
            "bills digests or sponsors, no amendment sheets (committee-stage amendments read "
            "\"bill only\"), no Votes and Proceedings or Journals of the Senate, no sitting "
            "calendar (the sitting days in Coming up are the Federal Register of Legislation's "
            "disallowance clock), no Notice Papers or Daily Programs, no Senate estimates, no "
            "committee inquiries or submissions, and no e-petitions. Divisions and bill stages come from the OpenAustralia Foundation's "
            "parse of the official Hansard; Acts from the Federal Register of Legislation.",
            "- **Debates:** {0} speech(es) and motion(s) on our ground from {1} Hansard day "
            "file(s) read for debates (the speeches themselves are never stored).".format(
                _count(conn, "SELECT COUNT(*) FROM au_speeches"),
                _count(conn, "SELECT COUNT(*) FROM au_debate_days")),
            "- **Not yet collected:** the High Court, and the states and territories.",
            "- **Migration** is matched and stored but not shown, as in every edition here.",
            "- Specification and decisions: [docs/australia-scope.md]({0}docs/australia-scope.md)."
            .format(REPO), ""]
    return "\n".join(out)


def _count(conn, sql):
    try:
        return conn.execute(sql).fetchone()[0]
    except sqlite3.Error:
        return 0


def dm_summary(conn, today, path=None):
    """The week in one Slack message, to Christopher alone."""
    conn.row_factory = sqlite3.Row
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=WEEK_DAYS)).isoformat()
    week = divisions_on_our_ground(conn, since, today)
    moved = bills_where(conn, "((last_stage_date > ? AND last_stage_date <= ?) OR "
                              "(assent_date > ? AND assent_date <= ?)) AND first_date <= ?",
                        (since, today, since, today, since))
    new = bills_where(conn, "first_date > ? AND first_date <= ?", (since, today))
    lines = [":flag-au: *Australian Parliament Monitor - week ending {0}*".format(today), ""]
    if week:
        lines.append("*{0} division(s) on our ground* (House {1}, Senate {2}).".format(
            len(week), sum(r["chamber"] == "house" for r in week),
            sum(r["chamber"] == "senate" for r in week)))
    else:
        lines.append("*No division on our ground this week.* Last sitting day in the store: "
                     "{0}.".format(last_sitting(conn) or "?"))
    lines.append("{0} bill(s) moved, {1} new.".format(len(moved), len(new)))
    speeches = _speeches(conn, "date > ? AND date <= ?", (since, today))
    if speeches:
        lines.append("{0} speech(es) or motion(s) on our ground in the debates.".format(len(speeches)))
    for r in by_recency(moved + new)[:5]:
        why = r["why_it_matters"]
        lines.append("• {0}{1}: {2} ({3}){4}".format(
            "*[{0}]* ".format(r["triage_score"]) if r["triage_score"] is not None else "",
            r["bill_id"], clip(r["title"], 80), stage(r)[1],
            "\n   _{0}_".format(oneline(why)) if why else ""))
    ahead = coming_up_dm(conn, today)
    if ahead:
        lines.append(ahead)
    lines.append("_Areas from taxonomy v{0} plus watchlist-au; bills matched on titles only "
                 "(aph.gov.au refuses our collectors)._".format(taxonomy_version()))
    if path:
        lines.append("Full edition: {0}{1}".format(REPO, os.path.relpath(path, ROOT)))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--edition", action="store_true", help="write editions/au-monitor-<date>.md")
    ap.add_argument("--dm", action="store_true", help="DM the summary to Christopher")
    ap.add_argument("--print", action="store_true", help="render to stdout, write nothing")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    conn.row_factory = sqlite3.Row
    text = render_edition(conn, args.date)
    path = os.path.join(ROOT, "editions", "au-monitor-{0}.md".format(args.date))
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
