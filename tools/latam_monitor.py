#!/usr/bin/env python3
"""The Latam edition: one monthly document for CitizenGO Latam, and a DM.

    python3 tools/latam_monitor.py --edition              # editions/latam-monitor-<date>.md
    python3 tools/latam_monitor.py --edition --dm         # and DM the summary to Chris
    python3 tools/latam_monitor.py --print                # render to stdout, write nothing
    python3 tools/latam_monitor.py --print --date 2026-10-09 --since 2026-09-08
    python3 tools/latam_monitor.py --edition --sample --db <scoping store>

Chris, 10 October 2026 (docs/country-decisions-2026-10-10.md, "Edition
structure"): one Latam monitor for every Latin American country where
CitizenGO works through CitizenGO Latam, replacing the Central America
digest (X10) and the per-country cadences (EC5, SV1, HN1). Monthly, to him
alone by Slack DM, as the US, German and Irish editions went to him first;
nothing posts to a channel. Modelled on tools/us_monitor.py.

WHAT LEADS. A section only for a country with something on our ground this
month: new bills, stage moves, recorded votes (with the party split where
the country publishes per-member positions), Honduras's press items and
gazette, Uruguay's pedidos de informes and laws, El Salvador's committee
reports and votes. Every quiet country goes into one "nothing new" line;
Costa Rica and Paraguay into one "access pending" line. Venezuela gets its
small note (the news feed and the hand-watched Ley contra el Odio reform),
Nicaragua its gazette check. Between editions, tools/latam_alerts.py sends
the watched and tier-1 items as they land.

LANGUAGE. English takeaways; the source's Spanish title is kept verbatim, in
italics, as the German edition keeps German. British spelling, no em dashes.

NO VERDICTS. A vote carries its tally, the source's own words for the
result and its party split, never "a win" or "a defeat". Which way a vote
cut is a signed human judgement, as everywhere in this repo.

SCORES. The paid AI judge is deferred (X16): items are ordered by the stub
triage (tier 1 or watched before tier 2) and the edition says so. Where the
free session judge (src/edition_judge.py, Claude Code on the Mac Mini, plan
allowance) has read an item, its score 0-3 orders it and its why-line is
shown, and an unwatched item it scored 0 is left out (counted). Nothing
here is an [ACT] item, and the render refuses one without an owner
(CLAUDE.md hard rule) should a later change ever add one.

Read-only on the store.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, edition_judge, latam  # noqa: E402

REPO = "https://github.com/thejoycething-code/parl-monitor/blob/main/"
CHRIS = "U05LJP0BT61"          # the DM goes to Chris alone
DEFAULT_DAYS = 31
MAX_PER_COUNTRY = 12
SAMPLE_MARK = "SAMPLE EDITION"

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")

HONESTY = (
    "> **How to read this edition.** Each country's items come from its own store, "
    "classified by the shared Spanish taxonomy (taxonomy-es v{0}, country-tagged terms, "
    "approved without a native read, X4) and the country's watchlist. The AI judge is off "
    "(X16), so nothing has been read for relevance by a model: items are ordered by tier "
    "(watched and tier 1 first) and a tier-2 match can still be noise. Titles are the "
    "source's own Spanish, verbatim; the English around them is ours. Tallies, results "
    "and party splits are the record; whether a vote helped or hurt is a human call and "
    "is never made here. Migration is matched and stored but not shown. Procedural votes, "
    "the patterns in config/latam-noise.yaml and Chris's mutes are left out (counted under "
    "Coverage); a watched item never is."
)


JUDGED = (
    "**The session judge.** {0} item(s) here were read for relevance by the free session "
    "judge (Claude Code on the Mac Mini, on the plan allowance; the paid API judge stays off, "
    "X16): each shows its score [0-3] and why-line, an unwatched item it scored 0 is left out "
    "(counted under Coverage), and the scores order the items. Items without a score are "
    "ordered by tier as above."
)


# --- dates ----------------------------------------------------------------------

def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return "{0} {1} {2}".format(d.day, MONTHS[d.month - 1], d.year)


def short_date(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or "?"
    return "{0} {1}".format(d.day, MONTHS[d.month - 1][:3])


def editions(exclude_samples=True):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "editions", "latam-monitor-*.md"))):
        if exclude_samples:
            with open(f, encoding="utf-8") as fh:
                if SAMPLE_MARK in fh.read(2000):
                    continue
        out.append(os.path.basename(f)[len("latam-monitor-"):-3])
    return out


def window(today, since=None):
    """(since, until): from the last real edition (exclusive) to today, or a
    month when there is none."""
    if since:
        return since, today
    prior = [d for d in editions() if d < today]
    if prior:
        return prior[-1], today
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=DEFAULT_DAYS)).isoformat(), today


def edition_number(today):
    return len([d for d in editions() if d < today]) + 1


# --- text pieces ------------------------------------------------------------------

def taxonomy_version():
    import yaml
    with open(os.path.join(ROOT, "config", "taxonomy-es.yaml"), encoding="utf-8") as fh:
        return str(yaml.safe_load(fh).get("version"))


def why_watched(it, config_dir=None):
    key = it["key"]
    for prefix in ("Ficha ", "Iniciativa ", "Dictamen "):
        if key.startswith(prefix):
            key = key[len(prefix):]
    entry = latam.watchlist(it["cc"], config_dir).get(key) or latam.watchlist(
        it["cc"], config_dir).get(it["status"] or "")
    why = (entry or {}).get("why")
    if not why:
        return None
    first = re.split(r"(?<=[.!?])\s", latam.clean(why), maxsplit=1)[0]
    return latam.clip(first, 220)


def takeaway(it, config_dir=None):
    """The English line under an item: what happened, where it stands."""
    bits = []
    if it["status"] and it["kind"] != "news":   # a news item's status is only its watch key
        label = {"moved": "Moved", "updated": "Status", "report": "Committee",
                 "pedido": "Answer", "agenda": "Listed by", "gazette": "In",
                 "news": "Watched item"}.get(it["kind"], "Status")
        status = it["status"]
        if it["kind"] == "news":
            status = status.replace("-", " ")
        bits.append("{0}: \u201c{1}\u201d.".format(label, latam.clip(status, 200).rstrip(".")))
    if it["watched"]:
        why = why_watched(it, config_dir)
        bits.append("Watched{0}".format(": " + why if why else "."))
    return " ".join(bits)


def item_lines(it, config_dir=None):
    head = "- **{0}** · {1} · {2} · {3}{4}{5}".format(
        latam.KINDS.get(it["kind"], it["kind"]), latam.clip(it["key"], 60), short_date(it["date"]),
        latam.area_text(it["areas"]) or "watched", " · tier {0}".format(it["tier"])
        if it["tier"] else "", " · **watched**" if it["watched"] else "")
    out = [head, "  *{0}*".format(latam.clip(it["title"], 400) or "(no title published)")]
    t = takeaway(it, config_dir)
    if t:
        out.append("  " + t)
    judge = edition_judge.why_line(it)
    if judge:
        out.append("  " + judge)
    for line in it["lines"]:
        out.append("  " + latam.clean(line))
    if it["url"]:
        out.append("  [Source]({0})".format(it["url"]))
    return out


def counts(items):
    c = {}
    for it in items:
        c[it["kind"]] = c.get(it["kind"], 0) + 1
    return c


def count_text(items):
    c = counts(items)
    order = ("new", "moved", "updated", "vote", "report", "agenda", "pedido", "law", "press",
             "gazette", "news")
    names = {"new": ("new bill", "new bills"), "moved": ("stage move", "stage moves"),
             "updated": ("register update", "register updates"),
             "vote": ("recorded vote", "recorded votes"),
             "report": ("committee report", "committee reports"),
             "agenda": ("agenda item", "agenda items"), "pedido": ("pedido", "pedidos"),
             "law": ("law", "laws"), "press": ("press item", "press items"),
             "gazette": ("gazette notice", "gazette notices"), "news": ("news item", "news items")}
    return ", ".join("{0} {1}".format(c[k], names[k][c[k] != 1]) for k in order if c.get(k))


def last_seen(conn, cc):
    best = None
    for r in latam.rows(conn, "SELECT name FROM sqlite_master WHERE type='table'"):
        name = r[0]
        if not name.startswith(cc + "_"):
            continue
        cols = [c[1] for c in latam.rows(conn, "PRAGMA table_info({0})".format(name))]
        col = "last_seen" if "last_seen" in cols else ("read_at" if "read_at" in cols else None)
        if not col:
            continue
        got = latam.rows(conn, "SELECT MAX({0}) FROM {1}".format(col, name))
        v = got[0][0] if got else None
        if v and (best is None or v > best):
            best = v
    return latam.day(best) or None


# --- the edition ------------------------------------------------------------------

def gather(conn, since, until, ledger=None, config_dir=None, dropped=None):
    """{cc: [scored items]} for every country, quiet ones included as [].
    `dropped`, when a dict, gets {cc: [items the noise filters left out]}."""
    out = {}
    for cc, _, _ in latam.COUNTRIES:
        gone = []
        out[cc] = latam.score(latam.country_items(conn, cc, since, until, ledger, config_dir,
                                                  gone))
        if dropped is not None and gone:
            dropped[cc] = gone
    return out


# src/latam_noise.drop_reason's reasons, singular and plural.
DROPPED = {"procedural vote": ("procedural vote", "procedural votes"),
           "excluded title": ("excluded title", "excluded titles"),
           "names only excluded bills": ("vote on excluded bills only", "votes on excluded bills only"),
           "missing required context": ("item without the required context",
                                        "items without the required context"),
           "muted": ("muted item", "muted items"),
           edition_judge.DROP_REASON: ("item the judge scored 0", "items the judge scored 0")}


def dropped_line(dropped):
    """'Dominican Republic 10 (9 procedural votes, 1 excluded title); ...'"""
    parts = []
    for cc, _, _ in latam.COUNTRIES:
        gone = dropped.get(cc)
        if not gone:
            continue
        why = {}
        for it in gone:
            why[it["dropped"]] = why.get(it["dropped"], 0) + 1
        parts.append("{0} {1} ({2})".format(latam.NAMES[cc], len(gone), ", ".join(
            "{0} {1}".format(n, DROPPED.get(w, (w, w))[n != 1])
            for w, n in sorted(why.items(), key=lambda kv: (-kv[1], kv[0])))))
    return "; ".join(parts)


def venezuela_section(conn, since, until, items, config_dir=None):
    wl = latam.watchlist("ve", config_dir)
    read = latam.rows(conn, "SELECT COUNT(*) FROM ve_news WHERE substr(date,1,10) > ? AND "
                            "substr(date,1,10) <= ?", (since, until))
    n_read = read[0][0] if read else 0
    out = ["## Venezuela (monthly note)", "",
           "_Asamblea Nacional. No recorded votes are published and the bill register stopped "
           "in 2022, so this is a keyword note on the Assembly's Legislativa news feed "
           "(tools/ve_news.py), not a parliamentary section (VE1-VE3)._", ""]
    for key, entry in wl.items():
        mentions = [it for it in items if it["status"] == key]
        out.append("- **Watched by hand: {0}.** Status as of {1}, by hand: “{2}”. {3}".format(
            latam.clip(entry.get("why", key).split(",")[0], 120).rstrip("."),
            long_date(str(entry["as_of"])) if entry.get("as_of") else "unknown",
            latam.clean(entry.get("status") or "unknown"),
            "{0} news item(s) this month mention it.".format(len(mentions))
            if mentions else "No news item this month mentions it."))
    if n_read == 0:
        out.append("- The news feed was not read for this period (no items stored); see Coverage.")
    elif not items:
        out.append("- {0} news item(s) read this month; none on our ground.".format(n_read))
    else:
        out.append("- {0} news item(s) read this month; {1} on our ground:".format(n_read, len(items)))
        out.append("")
        for it in items[:6]:
            out += item_lines(it, config_dir)
    return out + [""]


def nicaragua_section(conn, since, until, items):
    issues = latam.rows(conn, "SELECT COUNT(*), MIN(date), MAX(date), SUM(pages = 0) FROM "
                              "nic_gazette_issues WHERE substr(date,1,10) > ? AND substr(date,1,10) <= ?",
                        (since, until))
    n, first, last, blind = issues[0] if issues else (0, None, None, 0)
    relig = items
    got = latam.rows(conn, "SELECT COUNT(*) FROM nic_gazette_items WHERE substr(date,1,10) > ? AND "
                           "substr(date,1,10) <= ?", (since, until))
    matched8 = len(latam.nic_items(conn, since, until))   # before the noise filters
    other = (got[0][0] if got else 0) - matched8
    filtered = matched8 - len(relig)
    out = ["## Nicaragua (La Gaceta)", "",
           "_No parliamentary section (NI1). La Gaceta, the official gazette, is read for "
           "religious-freedom items: cancellations of the legal status of churches, religious "
           "associations and NGOs (NI2; tools/nic_gaceta.py)._", ""]
    if not n:
        out.append("- La Gaceta was not read for this period (no issues stored); see Coverage.")
    else:
        out.append("- {0} issue(s) read, {1} to {2}{3}; {4} religious-freedom notice(s){5}{6}.".format(
            n, short_date(first), short_date(last),
            " ({0} without a text layer)".format(blind) if blind else "",
            len(relig), "; {0} other notice(s) matched other areas and are not shown".format(other)
            if other else "",
            "; {0} matched notice(s) with no cancellation or religious body in them were left out "
            "(config/latam-noise.yaml)".format(filtered) if filtered else ""))
        if relig:
            out.append("")
            for it in relig[:10]:
                out += item_lines(it)
    return out + [""]


def render_edition(conn, today, since=None, sample=False, ledger=None, config_dir=None):
    conn.row_factory = sqlite3.Row
    since, until = window(today, since)
    if ledger is None:
        ledger = latam.load_ledger()
    dropped = {}
    got = gather(conn, since, until, ledger, config_dir, dropped)
    d = datetime.date.fromisoformat(today)
    title = "# Latam Monitor - {0} {1}".format(MONTHS[d.month - 1], d.year)
    out = [title, ""]
    if sample:
        out += ["> **{0}.** Rendered on {1} from the scoping stores (the scratch stores each "
                "country branch built on 9 October 2026, reclassified under taxonomy-es, plus a "
                "live read of Colombia, Chile and Peru). Not a real edition: the stores are "
                "partial and the period is illustrative.".format(SAMPLE_MARK, long_date(today)), ""]
    collected = [cc for cc in latam.COLLECTED]
    active = [cc for cc in collected if got[cc]]
    quiet = [cc for cc in collected if not got[cc]]
    n_items = sum(len(got[cc]) for cc in active)
    n_watch = sum(it["watched"] for cc in active for it in got[cc])
    out += ["_Edition {0}, covering {1} to {2}. Monthly, to Chris by DM; watched and tier-1 items "
            "also arrive as instant alerts between editions._".format(
                edition_number(today) if not sample else "sample",
                long_date((datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()),
                long_date(until)), "",
            HONESTY.format(taxonomy_version())]
    n_judged = sum(edition_judge.judged(got[cc]) for cc in got)
    if n_judged:
        out += [">", "> " + JUDGED.format(n_judged)]
    out.append("")

    out += ["## This month", ""]
    if active:
        out.append("**{0} item(s) on our ground in {1} countr{2}**, {3} of them watched.".format(
            n_items, len(active), "y" if len(active) == 1 else "ies", n_watch))
        out += ["", "| Country | On our ground | Watched |", "|---|---|---|"]
        for cc in sorted(active, key=lambda c: (-len(got[c]), c)):
            out.append("| [{0}](#{1}) | {2} | {3} |".format(
                latam.NAMES[cc], latam.NAMES[cc].lower().replace(" ", "-"), count_text(got[cc]),
                sum(it["watched"] for it in got[cc]) or "-"))
    else:
        out.append("**Nothing on our ground in any collected country this month.**")
    out.append("")
    if quiet:
        out.append("**Nothing new on our ground:** {0}.".format(
            ", ".join(latam.NAMES[c] for c in sorted(quiet, key=lambda c: latam.NAMES[c]))))
    out.append("**Access pending:** {0}.".format("; ".join(
        "{0} ({1})".format(latam.NAMES[c], latam.PENDING[c]) for c in ("cr", "py"))))
    out.append("")

    for cc in sorted(active, key=lambda c: (-max(it.get("score", 0) for it in got[c]),
                                            -len(got[c]), c)):
        name = next(n for c, n, _ in latam.COUNTRIES if c == cc)
        chamber = next(ch for c, _, ch in latam.COUNTRIES if c == cc)
        items = got[cc]
        out += ["## {0}".format(name), "",
                "_{0}. {1}. Store last read {2}._".format(
                    chamber, count_text(items).capitalize(),
                    long_date(last_seen(conn, cc)) if last_seen(conn, cc) else "unknown"), ""]
        shown = items[:MAX_PER_COUNTRY]
        for it in shown:
            out += item_lines(it, config_dir)
        rest = items[MAX_PER_COUNTRY:]
        if rest:
            out.append("- _And {0} more on our ground ({1}), lower in the order; in the store._".format(
                len(rest), count_text(rest)))
        out.append("")

    out += venezuela_section(conn, since, until, got["ve"], config_dir)
    out += nicaragua_section(conn, since, until, got["nic"])

    out += ["## Coverage", ""]
    for cc in collected:
        seen = last_seen(conn, cc)
        out.append("- **{0}:** {1}.".format(
            latam.NAMES[cc], "store last read {0}".format(long_date(seen)) if seen
            else "no rows in this store yet"))
    out += ["- **Costa Rica, Paraguay:** no collector (CR1, PY1).",
            "- **Venezuela:** the Legislativa news feed, monthly; votes, bills and agendas are not "
            "published in a readable form (docs/venezuela-scope.md).",
            "- **Nicaragua:** La Gaceta only, monthly; the Assembly's votes are not followed (NI1).",
            "- **Guatemala** is collected fortnightly on GitHub (X9), so a month holds two pulls.",
            "- Stage moves for Colombia, Chile, Peru, Ecuador, Guatemala, Uruguay and El Salvador "
            "come from the alert pass, which sees a watched bill's status change between "
            "collections; their stores keep no change dates.",
            "- **Left out by the noise filters** (config/latam-noise.yaml, config/latam-mute.yaml; "
            "never a watched item): {0}.".format(dropped_line(dropped) or "nothing this month"),
            "- Specification and decisions: [docs/country-decisions-2026-10-10.md]({0}docs/"
            "country-decisions-2026-10-10.md).".format(REPO), ""]
    text = "\n".join(out)
    refuse_ownerless_act(text)
    return text


def refuse_ownerless_act(text):
    """CLAUDE.md: never render an [ACT] item without a non-null owner. This
    edition renders no [ACT] items; if one ever appears, it must name its owner."""
    for line in text.splitlines():
        if "[ACT]" in line and not re.search(r"owner:\s*\S", line, re.I):
            raise ValueError("refusing to render an [ACT] item without an owner: " + line[:120])


def dm_summary(conn, today, since=None, path=None, ledger=None, config_dir=None):
    """The month in one Slack message, to Chris alone."""
    conn.row_factory = sqlite3.Row
    since, until = window(today, since)
    if ledger is None:
        ledger = latam.load_ledger()
    got = gather(conn, since, until, ledger, config_dir)
    d = datetime.date.fromisoformat(today)
    active = [cc for cc in latam.COLLECTED if got[cc]]
    quiet = [cc for cc in latam.COLLECTED if not got[cc]]
    lines = [":earth_americas: *Latam Monitor - {0} {1}*".format(MONTHS[d.month - 1], d.year), ""]
    if active:
        lines.append("*{0} item(s) on our ground in {1} countr{2}*, {3} watched.".format(
            sum(len(got[c]) for c in active), len(active), "y" if len(active) == 1 else "ies",
            sum(it["watched"] for c in active for it in got[c])))
        for cc in sorted(active, key=lambda c: (-len(got[c]), c)):
            lines.append("• *{0}*: {1}".format(latam.NAMES[cc], count_text(got[cc])))
        top = latam.score([it for c in active for it in got[c]])[:5]
        lines.append("")
        for it in top:
            lines.append("• [{0}] {1}: _{2}_ ({3}{4})".format(
                it["cc"].upper(), latam.KINDS.get(it["kind"], it["kind"]).lower(),
                latam.clip(it["title"], 90), latam.area_text(it["areas"]) or "watched",
                ", watched" if it["watched"] else ""))
    else:
        lines.append("*Nothing on our ground in any collected country this month.*")
    if quiet:
        lines.append("Nothing new: {0}.".format(", ".join(latam.NAMES[c] for c in sorted(
            quiet, key=lambda c: latam.NAMES[c]))))
    lines.append("Access pending: Costa Rica, Paraguay.")
    lines.append("Venezuela: {0} news item(s) on our ground. Nicaragua: {1} religious-freedom "
                 "notice(s) in La Gaceta.".format(len(got["ve"]),
                                                   sum(8 in it["areas"] for it in got["nic"])))
    lines.append("_Ordered by the session judge's scores where it has read an item, by tier "
                 "elsewhere; the paid judge stays off (X16)._"
                 if any(edition_judge.judged(got[c]) for c in got) else
                 "_Ordered by tier; the AI judge is off (X16)._")
    if path:
        lines.append("Full edition: {0}{1}".format(REPO, os.path.relpath(path, ROOT)))
    return "\n".join(lines)


def send_dm(text):
    from src import publish
    secrets = publish.load_secrets()
    secrets["slack_dm_user_id"] = CHRIS       # Chris alone, whatever secrets.yaml says
    return publish.slack_dm(secrets, text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--since", help="ISO date, exclusive; default: the last edition, or a month")
    ap.add_argument("--edition", action="store_true", help="write editions/latam-monitor-<date>.md")
    ap.add_argument("--dm", action="store_true", help="DM the summary to Chris")
    ap.add_argument("--print", action="store_true", help="render to stdout, write nothing")
    ap.add_argument("--sample", action="store_true", help="mark the edition as a sample")
    args = ap.parse_args()
    conn = db.connect(args.db)
    conn.row_factory = sqlite3.Row
    text = render_edition(conn, args.date, args.since, args.sample)
    path = os.path.join(ROOT, "editions", "latam-monitor-{0}.md".format(args.date))
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
            print("dm: {0}".format(send_dm(dm_summary(conn, args.date, args.since,
                                                      path if args.edition else None))))
    if not (args.edition or args.dm):
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
