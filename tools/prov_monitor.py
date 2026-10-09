#!/usr/bin/env python3
"""The Canadian provinces edition: one weekly document, and a DM to Christopher.

    python3 tools/prov_monitor.py --edition              # editions/prov-monitor-<date>.md
    python3 tools/prov_monitor.py --edition --dm         # and DM the summary
    python3 tools/prov_monitor.py --print                # render to stdout, write nothing
    python3 tools/prov_monitor.py --print --date 2026-10-14 --since 2026-10-01

Christopher, 9 October 2026: the provinces had collection (tools/prov_collect.py,
tools/prov_speeches.py) and a signed 5CA (config/prov_stance.yaml) but no
edition and no judge. This is the edition; tools/prov_triage.py is the judge.
To him alone by Slack DM (U05LJP0BT61), as the US, Irish and Latam editions
went to him first; nothing posts to a channel. Modelled on tools/latam_monitor.py
(a section per jurisdiction) and tools/us_monitor.py (votes with party splits).

ONE SECTION PER PROVINCE THAT HAD ACTIVITY on our ground in the window
(Alberta, Saskatchewan, British Columbia, Manitoba, Ontario, Quebec, New
Brunswick, Newfoundland and Labrador, Nova Scotia; Prince Edward Island is out
of reach, docs/canada-provinces-scope.md). Each holds the divisions on our
ground with their party splits, the bills that were new, moved, received
royal assent or fell, the Hansard speeches on our ground (one line and the
link, never the speech), and the province's 5CA headline. Quiet provinces
share one line. Top lines across provinces lead; Coverage closes.

THE WINDOW. From the last edition (exclusive) to today, or a week when there
is none. A record dated up to LATE_DAYS before the window that the store
first saw inside it is shown too, marked "collected late": votes and
proceedings are printed days after the sitting.

NO VERDICTS. A division carries its result in the legislature's own words,
its printed tally and its party split, never "a win" or "a defeat". Which way
a vote cut is a signed human judgement here as everywhere in this repo: a
direction is printed ONLY where config/prov_stance.yaml holds a confirmed
reading for that division, and the 5CA headline counts members placed by
confirmed readings alone (tools/prov_5ca.py's rule, applied in memory).

NOISE IS MUTED, FREE (9 October 2026, Christopher's "option 2").
config/prov-noise.yaml (src/prov_noise.py) takes measured false positives off
an item's areas for the edition only: "Down syndrome" on a day act is not
abortion, "surrogate" in an estates bill is not surrogacy. An item left with
no shown area is muted, and Coverage says how many, province by province.
Never a watched item, never anything a signed reading covers. The store is
untouched.

SCORES ARE OPTIONAL. The judge (tools/prov_triage.py) runs only when the
repository variable PROV_JUDGE is 'on'. Without scores everything still
renders (CLAUDE.md: TRIAGE=stub), ordered by tier and date, and says so.

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
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, intel, prov_noise  # noqa: E402
import prov_5ca as p5  # noqa: E402

TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
REPO = "https://github.com/thejoycething-code/parl-monitor/blob/main/"
CHRIS = "U05LJP0BT61"          # the DM goes to Christopher alone
HIDDEN_AREAS = (11,)
WEEK_DAYS = 7
LATE_DAYS = 30
MAX_DIVISIONS = 12              # per province; the rest are counted
MAX_BILLS = 12
MAX_SPEECHES = 10
TOP_DIVISIONS = 5

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")

# The provinces collected, in the order Christopher named them.
PROVINCES = (("ab", "Alberta", "Legislative Assembly of Alberta"),
             ("sk", "Saskatchewan", "Legislative Assembly of Saskatchewan"),
             ("bc", "British Columbia", "Legislative Assembly of British Columbia"),
             ("mb", "Manitoba", "Legislative Assembly of Manitoba"),
             ("on", "Ontario", "Legislative Assembly of Ontario"),
             ("qc", "Quebec", "Assemblée nationale du Québec"),
             ("nb", "New Brunswick", "Legislative Assembly of New Brunswick"),
             ("nl", "Newfoundland and Labrador", "House of Assembly of Newfoundland and Labrador"),
             ("ns", "Nova Scotia", "Nova Scotia House of Assembly"))
NAMES = {p: n for p, n, _ in PROVINCES}
CHAMBER = {p: c for p, _, c in PROVINCES}

# Party labels as the sources print them, shortened for a split line. Anything
# not here is printed as stored.
PARTY_SHORT = {
    "United Conservative": "UCP", "Alberta New Democratic Party": "NDP",
    "Alberta Party": "AP", "Progressive Tory Party": "PC", "Wildrose": "WRP",
    "British Columbia New Democratic Party": "NDP", "Conservative Party of British Columbia": "Con",
    "British Columbia Green Party": "Green", "BC United": "BCU",
    "Progressive Conservative Party of New Brunswick": "PC", "Liberal Party of New Brunswick": "Lib",
    "Green Party of New Brunswick": "Green", "People's Alliance of New Brunswick": "PANB",
    "Progressive Conservative": "PC", "New Democrat": "NDP", "New Democratic": "NDP",
    "Liberal": "Lib", "Independent/Non-Affiliated": "Ind", "Independent": "Ind",
    "Lib.": "Lib", "Ind.": "Ind", "LIB": "Lib", "IND": "Ind", "GRN": "Green",
}

HONESTY = (
    "> **How to read this edition.** Areas come from the shared taxonomy (v{0}) and the "
    "provincial watchlist, matched on each bill's TEXT passage by passage (provincial titles "
    "name a statute, not a subject), on each division's question and debate, and on each "
    "speech's own words; Quebec is read in French (taxonomy-qc). A division takes its bill's "
    "areas, so a procedural vote on a bill on our ground is listed under it. Results and "
    "tallies are the legislature's own; party splits are the party at the vote where the "
    "source dates it. **Whether a vote helped or hurt is a human call**: a direction is "
    "printed only where a signed reading in config/prov_stance.yaml covers that division, and "
    "the 5CA lines count members placed by signed readings alone. {1} Migration is matched "
    "and stored but not shown."
)


# --- small helpers -------------------------------------------------------------

def oneline(text):
    """One line, and no em dashes (CLAUDE.md: rendered editions carry none)."""
    return " ".join((text or "").replace("—", " - ").replace("–", "-").split())


def clip(text, n):
    text = oneline(text)
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def visible(areas_json):
    try:
        return [a for a in json.loads(areas_json or "[]") if a not in HIDDEN_AREAS]
    except (TypeError, ValueError):
        return []


def long_date(iso):
    d = datetime.date.fromisoformat(iso[:10])
    return "{0} {1} {2}".format(d.day, MONTHS[d.month - 1], d.year)


def short_date(iso):
    try:
        d = datetime.date.fromisoformat((iso or "")[:10])
    except ValueError:
        return iso or "?"
    return "{0} {1}".format(d.day, MONTHS[d.month - 1][:3])


def party(name):
    return PARTY_SHORT.get(name, name) if name else "?"


def area_names():
    return intel.area_names(TAXONOMY)


def area_text(areas, names):
    return ", ".join(names.get(a, str(a)) for a in areas)


def taxonomy_version():
    import yaml
    with open(TAXONOMY, encoding="utf-8") as fh:
        return str(yaml.safe_load(fh).get("version"))


def _has_table(conn, name):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                             (name,)).fetchone())


def editions():
    return sorted(os.path.basename(f)[len("prov-monitor-"):-3]
                  for f in glob.glob(os.path.join(ROOT, "editions", "prov-monitor-*.md")))


def window(today, since=None):
    """(since, until): from the last edition before today (exclusive), or a week."""
    if since:
        return since, today
    prior = [d for d in editions() if d < today]
    if prior:
        return prior[-1], today
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=WEEK_DAYS)).isoformat(), today


def edition_number(today):
    return len([d for d in editions() if d < today]) + 1


def late_floor(since):
    return (datetime.date.fromisoformat(since) - datetime.timedelta(days=LATE_DAYS)).isoformat()


def in_window(date, first_seen, since, until):
    """'' (not shown), 'in' (dated in the window) or 'late' (dated up to
    LATE_DAYS before it, first seen inside it)."""
    date = (date or "")[:10]
    if since < date <= until:
        return "in"
    seen = (first_seen or "")[:10]
    if late_floor(since) < date <= since and since < seen <= until:
        return "late"
    return ""


# --- the noise filter -----------------------------------------------------------------

class Mutes:
    """The noise filter's verdicts for one edition, and what it muted.

    areas(conn, kind, row) gives the areas the edition shows for an item;
    callers ask only for items inside the window, so what is recorded here
    is what this edition muted. enabled=False shows every stored area."""

    KIND_WORDS = {"bill": ("bill", "bills"), "division": ("division", "divisions"),
                  "speech": ("Hansard speech", "Hansard speeches")}

    def __init__(self, conn, stance_path=None, config_dir=None, enabled=True):
        self.nz = prov_noise.ProvNoise(config_dir, signed=prov_noise.signed_keys(
            conn, stance_path)) if enabled else None
        self.titles = {}
        if enabled:
            self.titles = {r[0]: " ".join(x for x in (r[1], r[2]) if x) for r in conn.execute(
                "SELECT bill_key, title_en, title_fr FROM prov_bills")}
        self.shown = {}
        self.muted = {}                  # prov -> {kind: {key}}
        self.trimmed = {}                # prov -> {(kind, key)}: shown, an area muted

    def _heading(self, conn, kind, r):
        if kind == "bill":
            return self.titles.get(r["bill_key"], ""), [r["bill_key"]]
        if kind == "division":
            bills = _linked(conn, r)
            return " ".join([self.titles.get(b, "") for b in bills]
                            + [r["stage"] or "", r["vote_on"] or "", r["question"] or ""]), bills
        return " ".join(x for x in (r["subject"], r["rubric"]) if x), (
            [r["bill_key"]] if r["bill_key"] else [])

    def areas(self, conn, kind, r):
        key = r[{"bill": "bill_key", "division": "division_key", "speech": "speech_id"}[kind]]
        if (kind, key) in self.shown:
            return self.shown[(kind, key)]
        stored = visible(r["areas"])
        if self.nz is None or not stored:
            self.shown[(kind, key)] = stored
            return stored
        heading, bills = self._heading(conn, kind, r)
        try:
            terms = json.loads(r["matched_terms"] or "[]")
        except (TypeError, ValueError, IndexError):
            terms = []
        shown, muted = self.nz.judge(kind, key, heading, stored, terms, bills)
        if muted and not shown:
            self.muted.setdefault(r["prov"], {}).setdefault(kind, set()).add(key)
        elif muted:
            self.trimmed.setdefault(r["prov"], set()).add((kind, key))
        self.shown[(kind, key)] = shown
        return shown

    def of(self, kind, key, areas_json):
        """The areas shown for an item already judged (stored areas otherwise)."""
        return self.shown.get((kind, key), visible(areas_json))

    def count(self, prov=None):
        provs = [prov] if prov else list(self.muted)
        return sum(len(v) for p in provs for v in self.muted.get(p, {}).values())

    def coverage_line(self):
        if self.nz is None:
            return "- **Noise filter:** off for this render; every stored area is shown."
        total = self.count()
        trimmed = sum(len(v) for v in self.trimmed.values())
        if not total and not trimmed:
            return ("- **Noise filter** (config/prov-noise.yaml): nothing muted this week. It takes "
                    "measured false positives off an item's areas, never a watched item or one a "
                    "signed reading covers.")
        parts = []
        for p, _n, _c in PROVINCES:
            got = self.muted.get(p) or {}
            if got:
                parts.append("{0} {1}".format(NAMES[p], ", ".join(
                    "{0} {1}".format(len(got[k]), self.KIND_WORDS[k][len(got[k]) != 1])
                    for k in ("bill", "division", "speech") if got.get(k))))
        return ("- **Noise filter** (config/prov-noise.yaml): {0} item(s) on our ground muted "
                "from this edition{1}; {2} item(s) shown with a noise area taken off. Muted items "
                "stay in the store; a watched item, or one a signed reading covers, is never "
                "muted.".format(total, " ({0})".format("; ".join(parts)) if parts else "", trimmed))


def _mutes(mutes):
    return mutes if mutes is not None else _NoMutes()


class _NoMutes:
    def areas(self, conn, kind, r):
        return visible(r["areas"])

    def of(self, kind, key, areas_json):
        return visible(areas_json)


# --- scores ------------------------------------------------------------------------

def load_scores(conn):
    if not _has_table(conn, "prov_scores"):
        return {}
    return {r[0]: (r[1], r[2]) for r in conn.execute("SELECT item, score, why FROM prov_scores")}


def score_mark(score):
    return "**[{0}]** ".format(score) if score is not None else ""


# --- stance (signed readings only) ---------------------------------------------------

def load_signed(stance_path=None):
    """(division entries, bill entries) from config/prov_stance.yaml."""
    path = stance_path or p5.STANCE_PATH
    return p5.load_stance(path, "divisions"), p5.load_stance(path, "bills")


def signed_line(entry):
    """The signed reading of one division, or None. Directions only where signed."""
    st = p5.status(entry)
    if st == "confirmed":
        sides = []
        for side, key in (("Yea", "yea"), ("Nay", "nay")):
            if entry.get(key) is not None:
                sides.append("{0} {1:+d}".format(side, entry[key]))
        return "Signed reading (config/prov_stance.yaml): {0}.".format(", ".join(sides)) if sides else None
    if st == "unplaceable":
        return "Signed reading: evidence only, places nobody ({0}).".format(
            clip((entry or {}).get("reason") or "", 120).rstrip("."))
    return None


def _slug(name):
    """tools/prov_5ca.py's sheet slug for an area name."""
    return name.lower().replace(" ", "-").replace(",", "")


def sheet_totals(path):
    """(sitting, {column: n}) from a 5CA sheet's Totals row, or None."""
    import csv
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            for row in csv.reader(fh):
                m = re.match(r"Totals - (\d+) sitting", row[0] if row else "")
                if m:
                    cols = p5.stance.COLUMNS
                    return int(m.group(1)), {c: int(row[1 + i] or 0) for i, c in enumerate(cols)}
    except OSError:
        return None
    return None


def fiveca_headline(prov, entries, bill_entries, names, sheet_dir=None):
    """The province's 5CA in a few lines, from the sheets tools/prov_5ca.py
    has just written (the weekly runs it before this edition): for each area,
    how many sitting members its rule places in each column. Only CONFIRMED
    readings place anyone there, so every count here is a signed reading's.
    Reading the sheets, not rebuilding them, keeps the edition to seconds."""
    sheet_dir = sheet_dir or p5.OUT_DIR
    mine = [e for k, e in entries.items() if k.startswith(prov + "-")]
    mine_bills = [e for k, e in bill_entries.items() if k.startswith(prov + "-")]
    confirmed = sum(p5.status(e) == "confirmed" for e in mine)
    confirmed_bills = sum(p5.status(e) == "confirmed" for e in mine_bills)
    if not confirmed and not confirmed_bills:
        return ["**5CA:** no signed reading for {0} yet, so nobody is placed; the sheets "
                "(data/5ca/prov-5ca-{1}-*.csv) are evidence lists.".format(NAMES[prov], prov)]
    parts = []
    for area in sorted(names):
        got = sheet_totals(os.path.join(sheet_dir, "prov-5ca-{0}-{1}.csv".format(
            prov, _slug(names[area]))))
        if not got:
            continue
        sitting, tally = got
        if not sum(n for c, n in tally.items() if c != "0"):
            continue
        parts.append("{0}: {1} (of {2} sitting)".format(names[area], " · ".join(
            "{0} {1}".format("0 (not placed)" if c == "0" else c, tally[c])
            for c in p5.stance.COLUMNS), sitting))
    head = "**5CA, signed readings only:** {0} confirmed division reading(s){1}.".format(
        confirmed, ", {0} bill reading(s)".format(confirmed_bills) if confirmed_bills else "")
    if not parts:
        return [head + " No sitting member is placed by them yet."]
    return [head] + ["- " + p for p in parts]


# --- gathering ---------------------------------------------------------------------

def party_split(conn, division_key):
    """'UCP 47-0, NDP 0-35' (Yea-Nay by party at the vote), largest first."""
    counts = {}
    for p, position, n in conn.execute(
            "SELECT party_at_vote, position, COUNT(*) FROM prov_votes WHERE division_key=? "
            "GROUP BY party_at_vote, position", (division_key,)):
        counts.setdefault(party(p), {})[position] = n
    order = sorted(counts, key=lambda p: (p == "?", -sum(counts[p].values()), p))
    out = []
    for p in order:
        c = counts[p]
        s = "{0} {1}-{2}".format(p, c.get("Yea", 0), c.get("Nay", 0))
        if c.get("Abstain"):
            s += " ({0} abst.)".format(c["Abstain"])
        out.append(s)
    return ", ".join(out)


def bill_titles(conn):
    return {r[0]: (r[1] or r[2] or "", r[3], visible(r[4]))
            for r in conn.execute("SELECT bill_key, title_en, title_fr, page_url, areas FROM prov_bills")}


def bill_label(key):
    """'ab-31-2/26' -> 'Bill 26 (31-2)'; an unnumbered '/x-<slug>' -> 'unnumbered bill'."""
    head, _, num = (key or "").partition("/")
    sess = "-".join(head.split("-")[1:3])
    if num.startswith("x-"):
        return "Unnumbered bill ({0})".format(sess)
    return "Bill {0} ({1})".format(num, sess)


def divisions(conn, prov, since, until, mutes=None):
    mz = _mutes(mutes)
    rows = conn.execute(
        "SELECT * FROM prov_divisions WHERE prov=? AND date > ? AND date <= ? "
        "ORDER BY date DESC, division_key DESC", (prov, late_floor(since), until)).fetchall()
    out = []
    for r in rows:
        when = in_window(r["date"], r["first_seen"], since, until)
        if when and visible(r["areas"]) and mz.areas(conn, "division", r):
            out.append((when, r))
    return out


def _stages(row):
    try:
        st = json.loads(row["stages"] or "[]")
    except (TypeError, ValueError):
        return []
    return [s for s in st if isinstance(s, dict) and s.get("date")]


ASSENT = re.compile(r"royal assent|^sanction|^RA$", re.I)
FIRST = re.compile(r"first reading|^pr[ée]sentation|^1$|introduc", re.I)


def bill_events(conn, prov, since, until, div_bills, mutes=None):
    """{bill_key: (row, kind, [event lines], when)} for bills on our ground
    that were new, moved or assented in the window. `div_bills` are the bills
    a division in the window decided: they moved, whatever the stages say."""
    out = {}
    for r in conn.execute("SELECT * FROM prov_bills WHERE prov=?", (prov,)):
        if not visible(r["areas"]):
            continue
        events, kinds, when = [], set(), "in"
        for s in _stages(r):
            w = in_window(s["date"], r["first_seen"], since, until)
            if not w:
                continue
            when = "late" if w == "late" and when == "in" and not events else when
            label = oneline(s.get("stage") or "?")
            status = oneline(s.get("status") or "")
            events.append("{0} {1}{2}".format(short_date(s["date"]), label,
                                              " ({0})".format(clip(status, 80)) if status else ""))
            kinds.add("assent" if ASSENT.search(label) else "new" if FIRST.search(label) else "moved")
        ra = r["royal_assent"]
        if ra and re.match(r"\d{4}-\d{2}-\d{2}", ra) and in_window(ra, r["first_seen"], since, until) \
                and "assent" not in kinds:
            events.append("{0} Royal Assent".format(short_date(ra)))
            kinds.add("assent")
        if r["bill_key"] in div_bills and not events:
            events.append("decided on a division this week (below)")
            kinds.add("moved")
        if not events:
            continue
        if not _mutes(mutes).areas(conn, "bill", r):
            continue
        kind = "assent" if "assent" in kinds else "new" if kinds == {"new"} else "moved"
        out[r["bill_key"]] = (r, kind, events, when)
    return out


def sessions(conn, prov):
    """[(legislature, session, first date)] for the province, oldest first,
    from every dated thing the store holds."""
    got = {}
    for sql in ("SELECT legislature, session, MIN(date) FROM prov_divisions WHERE prov=? "
                "GROUP BY 1, 2",
                "SELECT legislature, session, MIN(date) FROM prov_speech_sittings WHERE prov=? "
                "GROUP BY 1, 2"):
        for leg, sess, first in conn.execute(sql, (prov,)):
            if leg is None or sess is None or not first:
                continue
            k = (int(leg), int(sess))
            got[k] = min(got.get(k, first), first)
    return sorted((k[0], k[1], v) for k, v in got.items())


def fallen(conn, prov, since, until, mutes=None):
    """(old session label, new session label, [bill rows]) when a new session
    first appears in the store inside the window: the old session's bills on
    our ground without royal assent died with it (prorogation or dissolution)."""
    ss = sessions(conn, prov)
    for i in range(1, len(ss)):
        leg, sess, first = ss[i]
        if since < first[:10] <= until:
            old = ss[i - 1]
            rows = [r for r in conn.execute(
                "SELECT * FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
                (prov, old[0], old[1]))
                if visible(r["areas"]) and not r["royal_assent"]
                and not any(ASSENT.search(s.get("stage") or "") for s in _stages(r))
                and not ASSENT.search(r["latest_stage"] or "")
                and _mutes(mutes).areas(conn, "bill", r)]
            return ("{0}-{1}".format(old[0], old[1]), "{0}-{1}".format(leg, sess), rows)
    return None


def speeches(conn, prov, since, until, mutes=None):
    mz = _mutes(mutes)
    rows = conn.execute(
        "SELECT s.*, m.name AS member_name, m.party AS member_party FROM prov_speeches s "
        "LEFT JOIN prov_members m ON m.prov = s.prov AND m.member_key = s.member_key "
        "WHERE s.prov=? AND s.date > ? AND s.date <= ? ORDER BY s.date DESC, s.seq",
        (prov, late_floor(since), until)).fetchall()
    return [(w, r) for w, r in ((in_window(r["date"], r["first_seen"], since, until), r)
                                for r in rows) if w and visible(r["areas"])
            and mz.areas(conn, "speech", r)]


def fold_speeches(rows):
    """One line per (member, day, debate), as on the 5CA sheets: a long
    debate is one item, not twenty."""
    groups, order = {}, []
    for w, r in rows:
        k = (r["member_key"] or r["speaker_label"], r["date"], r["subject"] or r["rubric"] or "")
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append((w, r))
    return [groups[k] for k in order]


def gather(conn, prov, since, until, scores, mutes=None):
    divs = divisions(conn, prov, since, until, mutes)
    div_bills = set()
    for _, d in divs:
        div_bills.update(b for b in _linked(conn, d))
    bills = bill_events(conn, prov, since, until, div_bills, mutes)
    fell = fallen(conn, prov, since, until, mutes)
    sp = fold_speeches(speeches(conn, prov, since, until, mutes))
    return {"divisions": divs, "bills": bills, "fallen": fell, "speeches": sp}


def _linked(conn, d):
    rows = conn.execute("SELECT bill_key FROM prov_division_bills WHERE division_key=? "
                        "ORDER BY is_primary DESC, bill_key", (d["division_key"],)).fetchall()
    keys = [r[0] for r in rows]
    if not keys and d["bill_key"]:
        keys = [d["bill_key"]]
    return keys


def active(got):
    return bool(got["divisions"] or got["bills"] or got["speeches"]
                or (got["fallen"] and got["fallen"][2]))


def div_score(d, scores, titles):
    """A division on a bill on our ground takes the bill's score; one whose
    areas are its own has its own (tools/prov_triage.py)."""
    if d["bill_key"] and d["bill_key"] in titles and titles[d["bill_key"]][2]:
        return scores.get("prov_bills:" + d["bill_key"], (None, None))
    return scores.get("prov_divisions:" + d["division_key"], (None, None))


def _rank(score, tier, date):
    return (-(score if score is not None else 1.5), tier or 2, "".join(
        chr(255 - ord(c)) for c in (date or "")))


# --- rendering -----------------------------------------------------------------------

def division_lines(conn, prov, divs, scores, titles, entries, names, mutes=None):
    ranked = sorted(divs, key=lambda wd: _rank(div_score(wd[1], scores, titles)[0],
                                              wd[1]["tier"], wd[1]["date"]))
    out = []
    for when, d in ranked[:MAX_DIVISIONS]:
        score, why = div_score(d, scores, titles)
        bills = _linked(conn, d)
        on = "; ".join("{0} *{1}*".format(bill_label(b), clip(titles.get(b, ("",))[0], 90))
                       for b in bills) or "no bill"
        if d["kind"] == "recorded":
            tally = "{0} {1}-{2}{3}".format(oneline(d["result"]) or "result not printed",
                                            d["yeas"] if d["yeas"] is not None else "?",
                                            d["nays"] if d["nays"] is not None else "?",
                                            ", {0} abstaining".format(d["abstentions"])
                                            if d["abstentions"] else "")
        else:
            tally = "{0}; on voice, no member record".format(oneline(d["result"]) or "decided")
        out.append("- {0}**{1}** · {2} · {3}: {4}.{5}".format(
            score_mark(score), short_date(d["date"]), oneline(d["stage"] or d["vote_on"] or "Division"),
            on, tally, " _(collected late)_" if when == "late" else ""))
        if d["kind"] == "recorded":
            split = party_split(conn, d["division_key"])
            if split:
                out.append("  Party split (Yea-Nay): {0}.{1}".format(
                    split, "" if d["positions_ok"] == 1 else
                    " _Names did not account for the printed totals: not trusted, places nobody._"))
        if d["question"] and not bills:
            out.append("  Question: “{0}”".format(clip(d["question"], 220)))
        sl = signed_line(entries.get(d["division_key"]))
        if sl:
            out.append("  " + sl)
        if why:
            out.append("  _{0}_".format(oneline(why)))
        out.append("  Areas: {0}.{1}".format(
            area_text(_mutes(mutes).of("division", d["division_key"], d["areas"]), names),
            " [Record]({0})".format(d["source_url"]) if d["source_url"] else ""))
    rest = ranked[MAX_DIVISIONS:]
    if rest:
        out.append("- _And {0} more division(s) on our ground, lower in the order; in the "
                   "store._".format(len(rest)))
    return out


KIND_LABEL = {"assent": "Royal assent", "new": "New", "moved": "Moved"}


def bill_lines(bills, scores, names, mutes=None):
    order = {"assent": 0, "moved": 1, "new": 2}
    ranked = sorted(bills.values(), key=lambda b: (
        order[b[1]], _rank(scores.get("prov_bills:" + b[0]["bill_key"], (None,))[0],
                           b[0]["tier"], max((s["date"] for s in _stages(b[0])), default=""))))
    out = []
    for r, kind, events, when in ranked[:MAX_BILLS]:
        score, why = scores.get("prov_bills:" + r["bill_key"], (None, None))
        title = r["title_en"] or r["title_fr"] or "(no title stored)"
        link = r["page_url"]
        out.append("- {0}**{1}** · {2} *{3}*{4}: {5}.{6}".format(
            score_mark(score), KIND_LABEL[kind], "[{0}]({1})".format(bill_label(r["bill_key"]), link)
            if link else bill_label(r["bill_key"]), clip(title, 110),
            " ({0})".format("government" if r["is_government"] == 1 else "private member")
            if r["is_government"] in (0, 1) else "",
            "; ".join(events), " _(collected late)_" if when == "late" else ""))
        if why:
            out.append("  _{0}_".format(oneline(why)))
        out.append("  Areas: {0}.".format(area_text(_mutes(mutes).of("bill", r["bill_key"], r["areas"]),
                                                    names)))
    rest = ranked[MAX_BILLS:]
    if rest:
        out.append("- _And {0} more bill(s); in the store._".format(len(rest)))
    return out


def speech_lines(groups, scores, names, mutes=None):
    def best(g):
        return max((scores.get("prov_speeches:" + r["speech_id"], (None,))[0] for _, r in g
                    if scores.get("prov_speeches:" + r["speech_id"])), default=None)
    ranked = sorted(groups, key=lambda g: _rank(best(g), min(r["tier"] or 2 for _, r in g), g[0][1]["date"]))
    out = []
    for g in ranked[:MAX_SPEECHES]:
        w, r = g[0]
        first = next((x for _, x in g if x["excerpt"]), r)
        who = r["member_name"] or r["speaker_label"] or "Unresolved speaker"
        areas = sorted({a for _, x in g for a in _mutes(mutes).of("speech", x["speech_id"], x["areas"])})
        why = next((scores["prov_speeches:" + x["speech_id"]][1] for _, x in g
                    if scores.get("prov_speeches:" + x["speech_id"])
                    and scores["prov_speeches:" + x["speech_id"]][1]), None)
        out.append("- {0}**{1}** ({2}) · {3} · {4}{5}: “{6}” ({7}){8}{9}".format(
            score_mark(best(g)), oneline(who), party(r["member_party"]), short_date(r["date"]),
            clip(r["subject"] or r["rubric"] or "debate", 70),
            " ({0} turns)".format(len(g)) if len(g) > 1 else "",
            clip(first["excerpt"], 160), area_text(areas, names),
            " [Hansard]({0})".format(r["source_url"]) if r["source_url"] else "",
            " _(collected late)_" if w == "late" else ""))
        if why:
            out.append("  _{0}_".format(oneline(why)))
    rest = ranked[MAX_SPEECHES:]
    if rest:
        out.append("- _And {0} more speaker-debate(s) on our ground; in the store._".format(len(rest)))
    return out


def count_text(got):
    bits = []
    rec = sum(d["kind"] == "recorded" for _, d in got["divisions"])
    voice = len(got["divisions"]) - rec
    if rec:
        bits.append("{0} recorded division{1}".format(rec, "" if rec == 1 else "s"))
    if voice:
        bits.append("{0} voice decision{1}".format(voice, "" if voice == 1 else "s"))
    kinds = [b[1] for b in got["bills"].values()]
    for k, (one, many) in (("assent", ("bill assented", "bills assented")),
                           ("moved", ("bill moved", "bills moved")),
                           ("new", ("new bill", "new bills"))):
        n = kinds.count(k)
        if n:
            bits.append("{0} {1}".format(n, one if n == 1 else many))
    if got["fallen"] and got["fallen"][2]:
        bits.append("{0} fallen with {1}".format(len(got["fallen"][2]), got["fallen"][0]))
    sp = len(got["speeches"])
    if sp:
        bits.append("{0} speaker-debate{1} in Hansard".format(sp, "" if sp == 1 else "s"))
    return ", ".join(bits)


def last_read(conn, prov):
    vals = []
    for sql in ("SELECT MAX(last_seen) FROM prov_bills WHERE prov=?",
                "SELECT MAX(last_seen) FROM prov_divisions WHERE prov=?",
                "SELECT MAX(read_at) FROM prov_sittings WHERE prov=?",
                "SELECT MAX(read_at) FROM prov_speech_sittings WHERE prov=?"):
        v = conn.execute(sql, (prov,)).fetchone()[0]
        if v:
            vals.append(v[:10])
    return max(vals) if vals else None


def latest(conn, prov):
    div = conn.execute("SELECT MAX(date) FROM prov_divisions WHERE prov=?", (prov,)).fetchone()[0]
    day = conn.execute("SELECT MAX(date) FROM prov_speech_sittings WHERE prov=?", (prov,)).fetchone()[0]
    return div, day


def render_edition(conn, today, since=None, stance_path=None, sheet_dir=None, noise_dir=None,
                   mute=True):
    conn.row_factory = sqlite3.Row
    since, until = window(today, since)
    names = area_names()
    scores = load_scores(conn)
    titles = bill_titles(conn)
    entries, bill_entries = load_signed(stance_path)
    mutes = Mutes(conn, stance_path, noise_dir, enabled=mute)
    got = {p: gather(conn, p, since, until, scores, mutes) for p, _, _ in PROVINCES}
    act = [p for p, _, _ in PROVINCES if active(got[p])]
    quiet = [p for p, _, _ in PROVINCES if not active(got[p])]
    score_note = ("Scores [0-3] and the italic why-lines come from the judge (src/triage.py, "
                  "provincial frame; tools/prov_triage.py)." if scores else
                  "**No item is scored**: the provincial judge is off (repository variable "
                  "PROV_JUDGE), so items are ordered by tier and date and nothing has been read "
                  "for relevance by a model; a tier-2 match can still be noise.")
    out = ["# Canadian Provinces Monitor",
           "### Week ending {0} | Edition {1} | {2} to {3}".format(
               today, edition_number(today),
               long_date((datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()),
               long_date(until)), "",
           "_Weekly, after the Provinces weekly collection; to Christopher by DM._", "",
           HONESTY.format(taxonomy_version(), score_note), ""]

    # Top lines
    out += ["## Top lines", ""]
    tops = []
    if act:
        tops.append("- **Activity on our ground in {0} of {1} provinces**: {2}.".format(
            len(act), len(PROVINCES), "; ".join("{0} ({1})".format(NAMES[p], count_text(got[p]))
                                                 for p in act)))
    else:
        tops.append("- **Nothing on our ground in any province this week.** Most legislatures "
                    "sit again from mid-October.")
    alldivs = [(p, w, d) for p in act for w, d in got[p]["divisions"] if d["kind"] == "recorded"]
    alldivs.sort(key=lambda x: _rank(div_score(x[2], scores, titles)[0], x[2]["tier"], x[2]["date"]))
    for p, w, d in alldivs[:TOP_DIVISIONS]:
        bills = _linked(conn, d)
        what = ("{0} on {1} *{2}*".format(oneline(d["stage"] or d["vote_on"] or "Division"),
                                          bill_label(bills[0]),
                                          clip(titles.get(bills[0], ("",))[0], 70))
                if bills else "{0} (no bill): \u201c{1}\u201d".format(
                    oneline(d["stage"] or d["vote_on"] or "Division").capitalize(),
                    clip(d["question"] or "question not printed", 70)))
        tops.append("- {0}**{1}**, {2}: {3}, {4} {5}-{6} ({7}).".format(
            score_mark(div_score(d, scores, titles)[0]), NAMES[p], short_date(d["date"]), what,
            oneline(d["result"]) or "result not printed", d["yeas"], d["nays"],
            party_split(conn, d["division_key"]) or "no split"))
    for p in act:
        for r, kind, events, _w in got[p]["bills"].values():
            if kind == "assent":
                tops.append("- **{0}**: {1} *{2}* received royal assent.".format(
                    NAMES[p], bill_label(r["bill_key"]), clip(r["title_en"] or r["title_fr"], 80)))
        f = got[p]["fallen"]
        if f and f[2]:
            tops.append("- **{0}**: session {1} has ended ({2} opened); {3} bill(s) on our ground "
                        "without royal assent fell with it.".format(NAMES[p], f[0], f[1], len(f[2])))
    out += tops + [""]
    if quiet:
        out += ["**Quiet this week** (nothing on our ground): {0}.".format(
            ", ".join(NAMES[p] for p in quiet)), ""]
    out += ["**Out of reach:** Prince Edward Island (every page behind a CAPTCHA, from CI too); "
            "the territories are not collected.", ""]

    for p in act:
        g = got[p]
        div, day = latest(conn, p)
        out += ["## {0}".format(NAMES[p]), "",
                "_{0}. {1}. Latest division in the store {2}; latest Hansard day read {3}._".format(
                    CHAMBER[p], count_text(g)[:1].upper() + count_text(g)[1:], short_date(div) if div else "none",
                    short_date(day) if day else "none"), ""]
        if g["divisions"]:
            out += ["**Divisions on our ground ({0})**".format(len(g["divisions"])), ""]
            out += division_lines(conn, p, g["divisions"], scores, titles, entries, names,
                                  mutes) + [""]
        if g["bills"]:
            out += ["**Bills ({0})**".format(len(g["bills"])), ""]
            out += bill_lines(g["bills"], scores, names, mutes) + [""]
        f = g["fallen"]
        if f and f[2]:
            out += ["**Fell with session {0}** ({1} opened; {2} bill(s) on our ground without "
                    "royal assent; a bill that returns is a new bill)".format(f[0], f[1], len(f[2])), ""]
            for r in f[2][:MAX_BILLS]:
                out.append("- {0} *{1}*, last stage: {2}.".format(
                    bill_label(r["bill_key"]), clip(r["title_en"] or r["title_fr"], 100),
                    oneline(r["latest_stage"]) or "not stored"))
            if len(f[2]) > MAX_BILLS:
                out.append("- _And {0} more._".format(len(f[2]) - MAX_BILLS))
            out.append("")
        if g["speeches"]:
            out += ["**Hansard on our ground ({0} speaker-debate(s); one line each, never the "
                    "speech)**".format(len(g["speeches"])), ""]
            out += speech_lines(g["speeches"], scores, names, mutes) + [""]
        out += fiveca_headline(p, entries, bill_entries, names, sheet_dir) + [""]

    # Coverage
    out += ["## Coverage", ""]
    for p, _, _ in PROVINCES:
        seen = last_read(conn, p)
        div, day = latest(conn, p)
        out.append("- **{0}:** store last read {1}; latest division {2}, latest Hansard day {3}.".format(
            NAMES[p], long_date(seen) if seen else "never", long_date(div) if div else "none",
            long_date(day) if day else "none (no Hansard reader)" if p == "ns" else
            long_date(day) if day else "none"))
    n_scored = len(scores)
    out += ["- **Prince Edward Island:** not collected (Radware CAPTCHA on every inner page, from "
            "CI too). Yukon, the Northwest Territories and Nunavut are not collected.",
            "- **Bill stages:** Manitoba, Ontario and Saskatchewan bill pages give the store no "
            "dated stages, so their bills show here only through a division; Nova Scotia's are "
            "dated for the bills read since its build.",
            "- **Nova Scotia** has divisions and bills but no Hansard speeches reader.",
            "- **Fallen bills** are shown the week a province's next session first appears in "
            "the store; a dissolution with no new session yet (Quebec's, for the 5 October 2026 "
            "election) shows when the new legislature's first session is collected.",
            "- **Judge:** {0}.".format(
                "{0} item(s) scored so far (tools/prov_triage.py)".format(n_scored) if n_scored
                else "off (PROV_JUDGE); nothing scored"),
            mutes.coverage_line(),
            "- **5CA sheets** are rebuilt every week (data/5ca/prov-5ca-*.csv); only confirmed "
            "readings in config/prov_stance.yaml place anyone.",
            "- **Migration** is matched and stored but not shown, as in every edition here.",
            "- Specification and decisions: [docs/canada-provinces-scope.md]({0}docs/"
            "canada-provinces-scope.md).".format(REPO), ""]
    text = "\n".join(out)
    refuse_ownerless_act(text)
    return text


def refuse_ownerless_act(text):
    """CLAUDE.md: never render an [ACT] item without a non-null owner. This
    edition renders no [ACT] items; if one ever appears, it must name its owner."""
    for line in text.splitlines():
        if "[ACT]" in line and not re.search(r"owner:\s*\S", line, re.I):
            raise ValueError("refusing to render an [ACT] item without an owner: " + line[:120])


def dm_summary(conn, today, since=None, path=None, stance_path=None, noise_dir=None):
    """The week in one Slack message, to Christopher alone."""
    conn.row_factory = sqlite3.Row
    since, until = window(today, since)
    scores = load_scores(conn)
    titles = bill_titles(conn)
    mutes = Mutes(conn, stance_path, noise_dir)
    got = {p: gather(conn, p, since, until, scores, mutes) for p, _, _ in PROVINCES}
    act = [p for p, _, _ in PROVINCES if active(got[p])]
    quiet = [p for p, _, _ in PROVINCES if not active(got[p])]
    lines = [":flag-ca: *Canadian Provinces Monitor - week ending {0}*".format(today), ""]
    if act:
        for p in act:
            lines.append("• *{0}*: {1}".format(NAMES[p], count_text(got[p])))
        alldivs = sorted(((p, d) for p in act for _, d in got[p]["divisions"] if d["kind"] == "recorded"),
                         key=lambda x: _rank(div_score(x[1], scores, titles)[0], x[1]["tier"], x[1]["date"]))
        for p, d in alldivs[:3]:
            bills = _linked(conn, d)
            lines.append("• [{0}] {1} on {2}: {3} {4}-{5}".format(
                p.upper(), oneline(d["stage"] or "division"),
                clip(titles.get(bills[0], ("",))[0], 60) if bills else "a motion",
                oneline(d["result"]), d["yeas"], d["nays"]))
    else:
        lines.append("*Nothing on our ground in any province this week.*")
    if quiet:
        lines.append("Quiet: {0}.".format(", ".join(NAMES[p] for p in quiet)))
    if mutes.count():
        lines.append("Muted as noise (config/prov-noise.yaml): {0} item(s).".format(mutes.count()))
    lines.append("_{0}_".format("Scored by the provincial judge." if scores else
                                "Ordered by tier; the provincial judge is off (PROV_JUDGE)."))
    if path:
        lines.append("Full edition: {0}{1}".format(REPO, os.path.relpath(path, ROOT)))
    return "\n".join(lines)


def send_dm(text):
    from src import publish
    secrets = publish.load_secrets()
    secrets["slack_dm_user_id"] = CHRIS       # Christopher alone, whatever secrets.yaml says
    return publish.slack_dm(secrets, text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--since", help="ISO date, exclusive; default: the last edition, or a week")
    ap.add_argument("--edition", action="store_true", help="write editions/prov-monitor-<date>.md")
    ap.add_argument("--dm", action="store_true", help="DM the summary to Christopher")
    ap.add_argument("--print", action="store_true", help="render to stdout, write nothing")
    args = ap.parse_args()
    conn = db.connect(args.db)
    conn.row_factory = sqlite3.Row
    text = render_edition(conn, args.date, args.since)
    path = os.path.join(ROOT, "editions", "prov-monitor-{0}.md".format(args.date))
    if args.print:
        print(text)
        return 0
    if args.edition:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("edition: wrote {0} ({1} lines)".format(os.path.relpath(path, ROOT),
                                                     text.count("\n") + 1))
    if args.dm:
        print("dm: {0}".format(send_dm(dm_summary(conn, args.date, args.since,
                                                  path if args.edition else None))))
    if not (args.edition or args.dm):
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
