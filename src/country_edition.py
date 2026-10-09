"""Weekly country editions: one framework, one small adapter per country.

Chris, 10 October 2026 (docs/country-decisions-2026-10-10.md, "Edition
structure"): Spain, Italy, France, the Netherlands, Belgium, Austria,
Switzerland, Poland, Portugal, Croatia, Slovakia, Hungary, Brazil, Argentina
and Mexico each get their own edition, to Chris alone by Slack DM, archived
to editions/<cc>-monitor-<date>.md. This module renders all of them; a
country supplies only an adapter that reads its own store.

WHAT AN EDITION HOLDS, in this order (a section only when it has items):
the week in brief (counts, and the lead items: watched, or tier 1 with the
minimum evidence), recorded votes (tally, the source's own words for the
result, party split, member positions where the country has them, DERIVED
records labelled as such for party-group countries, X5), new items on our
ground, stage moves, questions and answers, other items, watchlist
movements, the week ahead (when the store has agenda data), and coverage
(store last read, what the noise filters left out). A week with nothing on
our ground gets the short "quiet week" form. Titles are the source's own,
verbatim, in the original language, in italics; the English around them is
ours. British spelling, no em dashes. No verdicts: which way a vote cut is a
signed human judgement and is never made here.

CLASSIFICATION. Items come only from the store's own classification, which
each collector made through src/filter.py with the country's taxonomy and
watchlist; raw keyword hits are never read here. The stub triage
(src/triage.py, mode "stub" whatever TRIAGE says; X16, the judge stays off)
orders items. No [ACT] items are rendered, and render() refuses one without
an owner (CLAUDE.md hard rule) should an adapter ever add one.

======================================================================
THE ADAPTER INTERFACE (stable; additive changes only, noted below)
======================================================================

1. A module src/editions/<cc>.py defining COUNTRY, a `Country`:

       COUNTRY = Country(
           cc="at", name="Austria", chamber="Nationalrat and Bundesrat",
           language="German",
           taxonomies=(("taxonomy-atch.yaml", "at"),),   # config files + code
           items=items,              # required, see 2
           week_ahead=None,          # optional: fn(conn, today, wl) -> [item]
           kinds=None,               # None = every kind; ("vote",) = votes only
           dm_kinds=None,            # kinds the DM counts and leads with
           watchlist=None,           # optional: fn(config_dir) -> {key: entry};
                                     # default: every mapping section of
                                     # config/watchlist-<cc>.yaml merged
           members_note="...",       # one line for the honesty note
           coverage=("...",),        # extra Coverage lines, English
       )

2. `items(conn, since, until, wl)` returns the store's items on our ground
   dated in the window (since exclusive, until inclusive, ISO dates), built
   with `item()` or `vote()` below. `conn` is a read-only sqlite3
   connection with row_factory sqlite3.Row; use `rows(conn, sql, params)`,
   which returns [] when a table is missing; `window_sql(col)` gives the
   date test. `wl` is the watchlist mapping. An item is on our ground when
   `areas_of(row["areas"])` is non-empty or its key is watched
   (`on_ground(areas_raw, watched)`); never add an item on a keyword alone.

3. AN ITEM is a dict (src/latam.py's shape, plus five optional fields):

       cc, kind, key, date, title, status, areas, tier, watched, url,
       lines, terms, body, refs,
       takeaway   English line under the title (what it is, where it stands)
       watch_key  the watchlist key, when it is not `key` (a vote on a
                  watched bill); the Watchlist section and "why" use it
       group      votes sharing a group (one bill's amendments and final
                  vote, one floor vote recorded on several items) render
                  as one entry; the group's heading is `group_title`
       final      True for the group's decisive vote (passage, the whole)
       own        False when the areas are only the parent bill's or
                  dossier's, not the item's own words (rendered as a note,
                  and usable by `edition_evidence: own_words` in the noise
                  rules)

   KINDS (section): new, moved, vote, question, answer, report, agenda,
   law, updated, press, gazette, news, pedido. A vote's `lines` carry the
   tally, the party split and the member-position line: build them with
   tally_line(), split_line(), members_line(), derived_line().

4. NOISE: config/edition-noise-<cc>.yaml (rules) and
   config/edition-mute-<cc>.yaml (Chris's mutes), both optional, read by
   src/noise.py (the Latam filters generalised; the format is documented
   there): procedural votes, excluded titles, required context, minimum
   evidence for the edition (`edition_evidence`) and for the lead
   (`alert`). A watched item is never filtered except by its own key.
   What the filters drop is counted under Coverage.

5. tools/<cc>_monitor.py is three lines:

       from src import country_edition
       sys.exit(country_edition.main("at"))

   with the flags --edition (write editions/<cc>-monitor-<date>.md),
   --dm (to Chris alone: publish.slack_dm with his id forced), --print,
   --sample (marked SAMPLE, never DMed), --date, --since, --db.

6. SCHEDULE: the last step of jobs/<cc>-weekly.sh, before the publish,
   once a day (an edition already committed for today is rewritten, not
   resent), with "# mini_run: commit editions" in the job and editions/
   added in the workflow's commit step (see jobs/at-weekly.sh).

Change log of the interface (additive only):
  10 October 2026  first version.
  10 October 2026  item(..., watch_key=) added; one_per_group() helper;
                   rebels(..., skip=) for independents; an item's
                   group_title is shown under its title ("On: ...");
                   items of one kind with one title collapse into one.

Read-only on the store.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import glob
import importlib
import json
import os
import re
import sqlite3
import sys
from typing import Callable, Optional

import yaml

from src import latam
from src import noise as noise_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
EDITIONS = os.path.join(ROOT, "editions")
REPO = "https://github.com/thejoycething-code/parl-monitor/blob/main/"
CHRIS = "U05LJP0BT61"          # the DM goes to Chris alone
DEFAULT_DAYS = 7
MAX_PER_SECTION = 15
MAX_GROUP_VOTES = 6
SAMPLE_MARK = "SAMPLE EDITION"
HIDDEN_AREAS = latam.HIDDEN_AREAS
AREA_LABELS = latam.AREA_LABELS

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")

# kind -> (section heading, singular, plural); the order is the edition's.
SECTIONS = (
    ("vote", "Recorded votes", "recorded vote", "recorded votes"),
    ("new", "New on our ground", "new item", "new items"),
    ("moved", "Stage moves", "stage move", "stage moves"),
    ("report", "Committee reports", "committee report", "committee reports"),
    ("law", "Laws", "law", "laws"),
    ("question", "Questions", "question", "questions"),
    ("answer", "Answers", "answer", "answers"),
    ("pedido", "Requests for information", "request for information",
     "requests for information"),
    ("updated", "Updated on the register", "register update", "register updates"),
    ("press", "Press items", "press item", "press items"),
    ("gazette", "Gazette notices", "gazette notice", "gazette notices"),
    ("news", "News items", "news item", "news items"),
)
AHEAD = ("agenda", "Week ahead", "agenda item", "agenda items")
KIND_NAMES = {k: (one, many) for k, _, one, many in SECTIONS + (AHEAD,)}

DROPPED = {"procedural vote": ("procedural vote", "procedural votes"),
           "excluded title": ("excluded title", "excluded titles"),
           "names only excluded bills": ("vote on excluded bills only",
                                         "votes on excluded bills only"),
           "missing required context": ("item without the required context",
                                        "items without the required context"),
           "too little evidence": ("item with too little evidence",
                                   "items with too little evidence"),
           "muted": ("muted item", "muted items")}


# --- the adapter ------------------------------------------------------------------

@dataclasses.dataclass
class Country:
    cc: str
    name: str
    chamber: str
    language: str
    taxonomies: tuple
    items: Callable
    week_ahead: Optional[Callable] = None
    kinds: Optional[tuple] = None
    dm_kinds: Optional[tuple] = None
    watchlist: Optional[Callable] = None
    members_note: str = ""
    coverage: tuple = ()
    flag: str = ""


def adapter(cc):
    """The Country for a code, from src/editions/<cc>.py."""
    return importlib.import_module("src.editions.{0}".format(cc)).COUNTRY


def noise_for(country):
    return noise_mod.Noise(
        lambda cc: "edition-noise-{0}.yaml".format(cc),
        lambda cc: "edition-mute-{0}.yaml".format(cc),
        lambda cc: [(os.path.join(CONFIG, f), code) for f, code in country.taxonomies])


# --- helpers for adapters ----------------------------------------------------------

clean = latam.clean
clip = latam.clip
areas_of = latam.areas_of
area_text = latam.area_text
terms_of = latam.terms_of
on_ground = latam.on_ground
day = latam.day


def rows(conn, sql, params=()):
    """Rows as sqlite3.Row; [] when a table is missing."""
    return latam.rows(conn, sql, params)


def window_sql(col):
    """The window test on a date column: two parameters, (since, until)."""
    return "substr({0},1,10) > ? AND substr({0},1,10) <= ?".format(col)


def watchlist_file(cc, config_dir=None):
    """{key: entry} from config/watchlist-<cc>.yaml, every mapping section
    merged; {} when the country has no file."""
    return latam.watchlist(cc, config_dir)


def item(cc, kind, key, date, title, areas, tier, watched=False, status=None, url=None,
         lines=None, terms=None, body=None, refs=None, takeaway=None, group=None,
         group_title=None, final=False, own=None, watch_key=None):
    it = latam.item(cc, kind, key, date, title, areas, tier, watched, status, url, lines,
                    terms, body, refs)
    it.update(takeaway=clean(takeaway) or None, group=group, group_title=clean(group_title)
              or None, final=bool(final), own=own, watch_key=watch_key)
    return it


def vote(cc, key, date, title, areas, tier, watched, lines, **kw):
    """A recorded vote; `lines` from tally_line, split_line, members_line."""
    return item(cc, "vote", key, date, title, areas, tier, watched,
                lines=[ln for ln in lines if ln], **kw)


def tally_line(yes, no, abstain=None, result=None, how=None):
    bits = ["{0} for, {1} against".format(yes if yes is not None else "?",
                                          no if no is not None else "?")]
    if abstain:
        bits.append("{0} abstaining".format(abstain))
    line = "Tally: " + ", ".join(bits)
    if how:
        line += " ({0})".format(how)
    if result:
        line += "; result as recorded: “{0}”".format(clean(result).rstrip("."))
    return line


def split_line(groups, label="By party"):
    """'By party (for-against-abstaining): A 54-0-1, ...' from {party: [y, n, a]}."""
    parts = []
    for p, v in sorted(groups.items(), key=lambda kv: (-sum(kv[1][:3]), kv[0] or "")):
        v = list(v) + [0] * (3 - len(v))
        if not any(v[:3]):
            continue
        parts.append("{0} {1}-{2}{3}".format(p or "unknown", v[0], v[1],
                                             "-{0}".format(v[2]) if v[2] else ""))
    return "{0} (for-against, then abstaining where any): {1}".format(
        label, ", ".join(parts)) if parts else None


def side_line(for_groups, against_groups, label="By party"):
    """For a party-group vote that names sides only: 'For: A, B; against: C'."""
    if not for_groups and not against_groups:
        return None
    return "{0}: for {1}; against {2}.".format(
        label, ", ".join(for_groups) or "none", ", ".join(against_groups) or "none")


def members_line(n, rebels=None, caveat=None):
    """Stored member positions, and who voted against their group's majority."""
    if not n:
        return None
    line = "{0} member positions stored.".format(n)
    if rebels:
        shown = ", ".join(rebels[:8])
        more = len(rebels) - 8
        line += " Against their group's majority: {0}{1}.".format(
            shown, " and {0} more".format(more) if more > 0 else "")
    if caveat:
        line += " " + caveat
    return line


def derived_line(n, basis):
    """X5: member records derived from the group, labelled as derived."""
    if not n:
        return None
    return ("Member positions: {0} DERIVED from the group vote ({1}; X5), "
            "not recorded per member.".format(n, basis))


def group_counts(pairs, yes=("yes",), no=("no",), abstain=("abstain",)):
    """{group: [yes, no, abstain]} from (group, position) pairs."""
    out = {}
    for g, pos in pairs:
        p = (pos or "").strip().lower()
        idx = 0 if p in yes else 1 if p in no else 2 if p in abstain else None
        if idx is None:
            continue
        out.setdefault(g, [0, 0, 0])[idx] += 1
    return out


def rebels(rows_, yes=("yes",), no=("no",), skip=()):
    """'Name (Group)' for members who voted yes/no against their group's
    yes/no majority, from (name, group, position) rows. Groups in `skip`
    (independents, who have no group line to break) are left out."""
    counts = group_counts([(g, p) for _, g, p in rows_], yes, no)
    out = []
    for name, g, p in rows_:
        if not g or g in skip:
            continue
        c = counts.get(g)
        if not c or c[0] == c[1]:
            continue
        majority = "yes" if c[0] > c[1] else "no"
        pos = (p or "").strip().lower()
        side = "yes" if pos in yes else "no" if pos in no else None
        if side and side != majority:
            out.append("{0} ({1})".format(clean(name), g or "no group"))
    return sorted(out)


# --- dates and windows ------------------------------------------------------------

def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return "{0} {1} {2}".format(d.day, MONTHS[d.month - 1], d.year)


def short_date(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or "?"
    return "{0} {1}".format(d.day, MONTHS[d.month - 1][:3])


def edition_path(cc, today, directory=None):
    return os.path.join(directory or EDITIONS, "{0}-monitor-{1}.md".format(cc, today))


def editions(cc, directory=None, exclude_samples=True):
    """Dates of the country's archived editions, samples left out."""
    out = []
    prefix = "{0}-monitor-".format(cc)
    for f in sorted(glob.glob(os.path.join(directory or EDITIONS, prefix + "*.md"))):
        if exclude_samples:
            with open(f, encoding="utf-8") as fh:
                if SAMPLE_MARK in fh.read(3000):
                    continue
        out.append(os.path.basename(f)[len(prefix):-3])
    return out


def window(cc, today, since=None, directory=None):
    """(since, until): from the last real edition (exclusive) to today, or a
    week when there is none."""
    if since:
        return since, today
    prior = [d for d in editions(cc, directory) if d < today]
    if prior:
        return prior[-1], today
    return (datetime.date.fromisoformat(today)
            - datetime.timedelta(days=DEFAULT_DAYS)).isoformat(), today


def edition_number(cc, today, directory=None):
    return len([d for d in editions(cc, directory) if d < today]) + 1


# --- gathering --------------------------------------------------------------------

def score(items):
    """Stub triage score on each item (X16: the judge stays off, whatever
    TRIAGE says), ordered: watched, score, votes first, newest."""
    from src import triage
    tis = [triage.TriageItem(id=str(i), title=it["title"], text=it["title"], tier=it["tier"],
                             issue_areas=it["areas"], watchlist_hit=it["watched"])
           for i, it in enumerate(items)]
    for res in triage.triage(tis, mode="stub"):
        items[int(res.id)]["score"] = res.score
    return sorted(items, key=lambda it: (not it["watched"], -it.get("score", 0),
                                         it["kind"] != "vote", latam._neg(it["date"]),
                                         it["key"]))


def watchlist_of(country, config_dir=None):
    if country.watchlist:
        return country.watchlist(config_dir)
    return watchlist_file(country.cc, config_dir)


def gather(conn, country, since, until, config_dir=None, dropped=None):
    """The country's items in the window after the noise filters, scored.
    Items the filters leave out go to `dropped` (a list), with their reason."""
    conn.row_factory = sqlite3.Row
    wl = watchlist_of(country, config_dir)
    got = country.items(conn, since, until, wl) or []
    if country.kinds:
        got = [it for it in got if it["kind"] in country.kinds]
    kept, out = noise_for(country).split(got, config_dir)
    if dropped is not None:
        dropped.extend(out)
    return score(collapse_titles(kept))


def collapse_titles(items):
    """One entry for items of one kind (not votes) with the same title: the
    same written question put to every ministry, its fourteen answers. The
    entry keeps the first key and lists the others in a line."""
    out, seen = [], {}
    for it in sorted(items, key=lambda i: (i["date"], i["key"])):
        if it["kind"] == "vote" or not it["title"]:
            out.append(it)
            continue
        k = (it["kind"], noise_mod.fold(it["title"]))
        if k not in seen:
            seen[k] = dict(it, lines=list(it["lines"]), same=[])
            out.append(seen[k])
            continue
        first = seen[k]
        first["same"].append(it["key"])
        first["watched"] = first["watched"] or it["watched"]
        first["areas"] = sorted(set(first["areas"]) | set(it["areas"]))
        if it["tier"] and (not first["tier"] or it["tier"] < first["tier"]):
            first["tier"] = it["tier"]
    for it in out:
        same = it.pop("same", None)
        if same:
            it["lines"].append("{0} more with the same title: {1}.".format(
                len(same), ", ".join(same[:10]) + (", ..." if len(same) > 10 else "")))
    return out


def one_per_group(items):
    """The first item of each vote group, every other item as it is."""
    out, seen = [], set()
    for it in items:
        g = it.get("group")
        if g:
            if g in seen:
                continue
            seen.add(g)
        out.append(it)
    return out


def lead(country, items, config_dir=None):
    """Items that lead: watched, or tier 1 with the minimum evidence."""
    nz = noise_for(country)
    return [it for it in items if nz.alert_reason(it, config_dir)]


# --- rendering --------------------------------------------------------------------

def count_text(items):
    c = {}
    for it in items:
        c[it["kind"]] = c.get(it["kind"], 0) + 1
    order = [k for k, *_ in SECTIONS] + ["agenda"]
    return ", ".join("{0} {1}".format(c[k], KIND_NAMES[k][c[k] != 1])
                     for k in order if c.get(k))


def watch_key(it):
    return it.get("watch_key") or it["key"]


def why_watched(it, wl):
    entry = wl.get(watch_key(it)) or {}
    why = entry.get("why") if isinstance(entry, dict) else None
    if not why:
        return None
    first = re.split(r"(?<=[.!?])\s", clean(why), maxsplit=1)[0]
    return clip(first, 220)


def head_line(it):
    return "- **{0}** · {1} · {2} · {3}{4}{5}".format(
        KIND_NAMES.get(it["kind"], (it["kind"],))[0].capitalize(), clip(it["key"], 60),
        short_date(it["date"]), area_text(it["areas"]) or "watched",
        " · tier {0}".format(it["tier"]) if it["tier"] else "",
        " · **watched**" if it["watched"] else "")


def item_lines(it, wl, indent=""):
    out = [indent + head_line(it),
           indent + "  *{0}*".format(clip(it["title"], 400) or "(no title published)")]
    if it.get("group_title") and it["group_title"] != it["title"]:
        out.append(indent + "  On: *{0}*".format(clip(it["group_title"], 300)))
    bits = []
    if it.get("takeaway"):
        t = it["takeaway"]
        bits.append(t if t.endswith(("…", ".", "?", "!")) else t + ".")
    if it["status"]:
        bits.append("Status: “{0}”.".format(clip(it["status"], 200).rstrip(".")))
    if it.get("own") is False:
        bits.append("Its areas come from the bill or dossier it belongs to, not its own words.")
    if it["watched"]:
        why = why_watched(it, wl)
        bits.append("Watched{0}".format(": " + why if why else "."))
    if bits:
        out.append(indent + "  " + " ".join(bits))
    for line in it["lines"]:
        out.append(indent + "  " + clean(line))
    if it["url"]:
        out.append(indent + "  [Source]({0})".format(it["url"]))
    return out


def vote_groups(votes):
    """[(group key, [votes])] in the order of each group's best vote."""
    order, groups = [], {}
    for it in votes:
        g = it.get("group") or ("key", it["key"])
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(it)
    return [(g, groups[g]) for g in order]


def vote_lines(group, wl):
    if len(group) == 1:
        return item_lines(group[0], wl)
    chrono = sorted(group, key=lambda v: (v["date"], v["key"]))
    finals = [v for v in chrono if v.get("final")]
    headline = finals[-1] if finals else chrono[-1]
    first = group[0]
    areas = sorted({a for v in group for a in v["areas"]})
    title = first.get("group_title") or first["title"]
    watched = any(v["watched"] for v in group)
    out = ["- **{0} recorded votes on one item** · {1} to {2} · {3}{4}".format(
        len(group), short_date(chrono[0]["date"]), short_date(chrono[-1]["date"]),
        area_text(areas) or "watched", " · **watched**" if watched else ""),
        "  *{0}*".format(clip(title, 400))]
    if watched:
        why = next((why_watched(v, wl) for v in group if why_watched(v, wl)), None)
        if why:
            out.append("  Watched: " + why)
    others = [v for v in chrono if v is not headline]
    out.append("  - **{0}** ({1}): *{2}*".format(
        "Decisive vote" if headline.get("final") else "Latest vote",
        short_date(headline["date"]), clip(headline["title"], 300)))
    if headline.get("takeaway"):
        out.append("    " + headline["takeaway"])
    for line in headline["lines"]:
        out.append("    " + clean(line))
    if headline["url"]:
        out.append("    [Source]({0})".format(headline["url"]))
    for v in others[:MAX_GROUP_VOTES]:
        tally = next((ln for ln in v["lines"] if ln.startswith("Tally:")),
                     next(iter(v["lines"]), "")).replace("Tally: ", "").strip()
        out.append("  - {0}: *{1}*. {2}".format(short_date(v["date"]), clip(v["title"], 200),
                                                tally).rstrip())
    if len(others) > MAX_GROUP_VOTES:
        out.append("  - _And {0} more votes on the same item, in the store._".format(
            len(others) - MAX_GROUP_VOTES))
    return out


def honesty(country):
    tax = ", ".join("{0} v{1}".format(f.replace(".yaml", ""), taxonomy_version(f))
                    for f, _ in country.taxonomies)
    return (
        "> **How to read this edition.** Items come from the {0} store, classified by "
        "{1} (approved without a native read, X4) and config/watchlist-{2}.yaml. The AI judge "
        "is off (X16): nothing has been read for relevance by a model, items are ordered by "
        "tier (watched and tier 1 first), and a tier-2 match can still be noise. Titles are "
        "the source's own {3}, verbatim; the English around them is ours. Tallies, results "
        "and splits are the record; whether a vote helped or hurt is a human call and is "
        "never made here. {4}Migration is matched and stored but not shown. Procedural "
        "votes, the patterns in config/edition-noise-{2}.yaml and Chris's mutes are left "
        "out (counted under Coverage); a watched item never is.".format(
            country.name, tax, country.cc, country.language,
            (country.members_note.rstrip(".") + ". ") if country.members_note else ""))


def taxonomy_version(filename):
    try:
        with open(os.path.join(CONFIG, filename), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("version:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "?"


def last_read(conn, cc):
    best = None
    for r in rows(conn, "SELECT name FROM sqlite_master WHERE type='table'"):
        name = r[0]
        if not name.startswith(cc + "_"):
            continue
        cols = [c[1] for c in rows(conn, "PRAGMA table_info({0})".format(name))]
        col = "last_seen" if "last_seen" in cols else ("read_at" if "read_at" in cols else None)
        if not col:
            continue
        got = rows(conn, "SELECT MAX({0}) FROM {1}".format(col, name))
        v = got[0][0] if got else None
        if v and (best is None or v > best):
            best = v
    return day(best) or None


def dropped_text(dropped):
    why = {}
    for it in dropped:
        why[it["dropped"]] = why.get(it["dropped"], 0) + 1
    return ", ".join("{0} {1}".format(n, DROPPED.get(w, (w, w))[n != 1])
                     for w, n in sorted(why.items(), key=lambda kv: (-kv[1], kv[0])))


def title_line(country, today, since=None):
    """'# Austria Monitor - week to 9 October 2026'; a window that is not a
    week (the first edition after a gap, a sample) names both ends."""
    d = datetime.date.fromisoformat(today)
    if since:
        first = datetime.date.fromisoformat(since) + datetime.timedelta(days=1)
        if (d - first).days != DEFAULT_DAYS - 1:
            return "# {0} Monitor - {1} to {2}".format(
                country.name, long_date(first.isoformat()), long_date(today))
    return "# {0} Monitor - week to {1} {2} {3}".format(
        country.name, d.day, MONTHS[d.month - 1], d.year)


def render(conn, country, today, since=None, sample=False, config_dir=None,
           directory=None):
    """The edition's Markdown."""
    conn.row_factory = sqlite3.Row
    since, until = window(country.cc, today, since, directory)
    dropped = []
    got = gather(conn, country, since, until, config_dir, dropped)
    ahead = []
    if country.week_ahead:
        ahead, _ = noise_for(country).split(
            country.week_ahead(conn, today, watchlist_of(country, config_dir)) or [],
            config_dir)
    wl = watchlist_of(country, config_dir)
    seen = last_read(conn, country.cc)
    out = [title_line(country, today, since), ""]
    if sample:
        out += ["> **{0}.** Rendered on {1} from the scoping store built on 9 October 2026, "
                "reclassified under the current taxonomy and watchlist. Not a real edition: "
                "the store is partial and the period is illustrative.".format(
                    SAMPLE_MARK, long_date(today)), ""]
    first = (datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()
    out += ["_{0}. Edition {1}, covering {2} to {3}. Weekly, to Chris by DM._".format(
        country.chamber, "sample" if sample else edition_number(country.cc, today, directory),
        long_date(first), long_date(until)), ""]

    if not got and not ahead:
        out += ["**A quiet week.** Nothing on our ground in the {0} between {1} and {2}.".format(
            country.chamber, long_date(first), long_date(until)), ""]
        out += ["- Watchlist: {0} item(s), none moved.".format(len(wl)),
                "- Store last read {0}.".format(long_date(seen) if seen else "never"),
                "- Left out by the noise filters: {0}.".format(dropped_text(dropped) or "nothing"),
                ""]
        text = "\n".join(out)
        refuse_ownerless_act(text)
        return text

    out.append(honesty(country))
    out += ["", "## In brief", ""]
    n_watch = sum(it["watched"] for it in got)
    out.append("**{0} item(s) on our ground**: {1}; {2} watched.".format(
        len(got), count_text(got) or "none", n_watch or "none"))
    top = one_per_group(lead(country, got, config_dir))[:5]
    if top:
        out += ["", "Leading:"]
        for it in top:
            out.append("- {0}: *{1}* ({2}{3})".format(
                KIND_NAMES.get(it["kind"], (it["kind"],))[0].capitalize(),
                clip(it.get("group_title") or it["title"], 120),
                area_text(it["areas"]) or "watched", ", watched" if it["watched"] else ""))
    out.append("")

    for kind, heading, _, _ in SECTIONS:
        these = [it for it in got if it["kind"] == kind]
        if not these:
            continue
        out += ["## " + heading, ""]
        if kind == "vote":
            groups = vote_groups(these)
            for _, g in groups[:MAX_PER_SECTION]:
                out += vote_lines(g, wl)
            rest = groups[MAX_PER_SECTION:]
            if rest:
                out.append("- _And {0} more vote group(s), lower in the order; in the store._"
                           .format(len(rest)))
        else:
            for it in these[:MAX_PER_SECTION]:
                out += item_lines(it, wl)
            if len(these) > MAX_PER_SECTION:
                out.append("- _And {0} more, lower in the order; in the store._".format(
                    len(these) - MAX_PER_SECTION))
        out.append("")

    moved = [it for it in got if it["watched"]]
    out += ["## Watchlist", ""]
    if moved:
        keys = sorted({watch_key(it) for it in moved})
        out.append("{0} watched item(s) with activity in this edition: {1}. {2} other "
                   "watched item(s) had none.".format(len(keys), ", ".join(keys[:12]),
                                             max(len(wl) - len(keys), 0)))
    else:
        out.append("None of the {0} watched item(s) moved in this edition's period.".format(len(wl)))
    out.append("")

    if ahead:
        out += ["## Week ahead", ""]
        for it in score(ahead)[:MAX_PER_SECTION]:
            out += item_lines(it, wl)
        out.append("")

    out += ["## Coverage", "",
            "- Store last read {0}.".format(long_date(seen) if seen else "never")]
    out += ["- " + clean(c) for c in country.coverage]
    if not country.week_ahead:
        out.append("- No agenda is collected yet, so there is no week-ahead section.")
    out += ["- **Left out by the noise filters** (config/edition-noise-{0}.yaml, "
            "config/edition-mute-{0}.yaml; never a watched item): {1}.".format(
                country.cc, dropped_text(dropped) or "nothing"),
            "- Decisions: [docs/country-decisions-2026-10-10.md]({0}docs/"
            "country-decisions-2026-10-10.md).".format(REPO), ""]
    text = "\n".join(out)
    refuse_ownerless_act(text)
    return text


def refuse_ownerless_act(text):
    """CLAUDE.md: never render an [ACT] item without a non-null owner."""
    for line in text.splitlines():
        if "[ACT]" in line and not re.search(r"owner:\s*\S", line, re.I):
            raise ValueError("refusing to render an [ACT] item without an owner: " + line[:120])


def dm_summary(conn, country, today, since=None, path=None, config_dir=None, directory=None):
    """The week in one Slack message, to Chris alone."""
    since, until = window(country.cc, today, since, directory)
    got = gather(conn, country, since, until, config_dir)
    if country.dm_kinds:
        got = [it for it in got if it["kind"] in country.dm_kinds]
    d = datetime.date.fromisoformat(today)
    lines = ["{0}*{1} Monitor - week to {2} {3} {4}*".format(
        country.flag + " " if country.flag else "", country.name, d.day,
        MONTHS[d.month - 1], d.year), ""]
    if got:
        lines.append("*{0} item(s) on our ground*: {1}; {2} watched.".format(
            len(got), count_text(got), sum(it["watched"] for it in got) or "none"))
        for it in one_per_group(lead(country, got, config_dir) or got)[:5]:
            lines.append("• {0}: _{1}_ ({2}{3})".format(
                KIND_NAMES.get(it["kind"], (it["kind"],))[0].capitalize(),
                clip(it.get("group_title") or it["title"], 90),
                area_text(it["areas"]) or "watched", ", watched" if it["watched"] else ""))
    else:
        lines.append("*A quiet week*: nothing on our ground{0}.".format(
            " in recorded votes" if country.dm_kinds == ("vote",) else ""))
    lines.append("_Ordered by tier; the AI judge is off (X16)._")
    if path:
        lines.append("Full edition: {0}{1}".format(REPO, os.path.relpath(path, ROOT)))
    return "\n".join(lines)


def send_dm(text):
    from src import publish
    secrets = publish.load_secrets()
    secrets["slack_dm_user_id"] = CHRIS       # Chris alone, whatever secrets.yaml says
    return publish.slack_dm(secrets, text)


def main(cc, argv=None):
    """The entry point every tools/<cc>_monitor.py calls."""
    country = adapter(cc)
    ap = argparse.ArgumentParser(description="The {0} weekly edition (src/country_edition.py)."
                                 .format(country.name))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--since", help="ISO date, exclusive; default: the last edition, or a week")
    ap.add_argument("--edition", action="store_true",
                    help="write editions/{0}-monitor-<date>.md".format(cc))
    ap.add_argument("--dm", action="store_true", help="DM the summary to Chris")
    ap.add_argument("--print", action="store_true", help="render to stdout, write nothing")
    ap.add_argument("--sample", action="store_true", help="mark the edition as a sample")
    args = ap.parse_args(argv)
    from src import db
    conn = db.connect(args.db)
    conn.row_factory = sqlite3.Row
    text = render(conn, country, args.date, args.since, args.sample)
    path = edition_path(cc, args.date)
    if args.print:
        print(text)
        return 0
    if args.edition:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("edition: wrote {0} ({1} lines)".format(os.path.relpath(path, ROOT),
                                                     text.count("\n") + 1))
    if args.dm:
        if args.sample:
            print("dm: not sent (a sample edition is never sent)")
        else:
            print("dm: {0}".format(send_dm(dm_summary(conn, country, args.date, args.since,
                                                      path if args.edition else None))))
    if not (args.edition or args.dm):
        ap.print_help()
    return 0
