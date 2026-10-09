#!/usr/bin/env python3
"""The free session judge for the fifteen country editions and the Latam monitor.

    python3 tools/edition_judge.py                          # what is pending, by country
    python3 tools/edition_judge.py --queue-out /tmp/q.md --limit 25   # for a session
    python3 tools/edition_judge.py --queue-in /tmp/q.md              # apply its scores
    python3 tools/edition_judge.py --rerender --dm          # rewrite this week's scored editions

Chris, 10 October 2026: the paid AI judge stays off (X16), and the free
session judge built for the provinces (9 October, "option 3") is adopted for
the weekly country editions (src/country_edition.py, src/editions/<cc>.py)
and the Latam monitor (src/latam.py, tools/latam_monitor.py,
tools/latam_alerts.py): Claude Code on the Mac Mini, signed in to Chris's
claude.ai account, scores on the plan allowance. No API key, no spend.

ONE TOOL FOR EVERY EDITION, keyed by country code, not sixteen copies.
--queue-out writes the pending items of all of them to one file in
src/session_queue.py's format, in priority order across countries: watched
items first, then tier 1, then tier 2, newest first within each. An item is
pending when it is on our ground in its edition's current window (the latest
edition's window and anything since, for a weekly or fortnightly edition;
the last 31 days for Latam), not muted or filtered by the noise rules (the
edition would not show it), and not scored. A vote group (one bill's
amendments and its final vote) is offered once. Each item carries its frame:
the country and chamber, the kind, the title in the source's language
verbatim, the English takeaway and status, the areas and tier, the matched
terms, and whether and why it is watched.

--queue-in reads the file back STRICTLY, item by item (one digit 0-3 and a
why-line, or refused with its reason; an id that is not a pending edition
item is refused), and stores each score once, ever, in edition_scores with
model 'claude-code-session' (src/edition_judge.py). Neither flag needs
ANTHROPIC_API_KEY or spends anything.

--rerender rewrites, in place, the latest edition (of the last cadence) of
each country with an item scored today, and the Latam edition when it is
under a week old. With --dm, ONE short DM to Chris alone, and only when the
scores changed what leads an edition already sent ("Leading:"); otherwise
nothing is sent. jobs/editions-session-judge.sh runs the three steps weekly.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce  # noqa: E402
from src import db, edition_judge as ej, latam, session_queue, triage  # noqa: E402

QUEUE_MARKER = "<!-- edition-session-queue v1 -->"
SESSION_MODEL = ej.SESSION_MODEL
LATAM_DAYS = 31
LATAM_FRESH_DAYS = 7          # a Latam edition younger than this is rewritten
MAX_TEXT = 1200

SYSTEM_PROMPT_EDITIONS = triage.SYSTEM_PROMPT.replace(
    "You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns",
    "You are the triage layer of CitizenGO's country monitors outside the UK: fifteen weekly "
    "editions (Spain, Italy, France, the Netherlands, Belgium, Austria, Switzerland, Poland, "
    "Portugal, Croatia, Slovakia, Hungary, Brazil, Argentina and Mexico) and the monthly Latam "
    "monitor (Colombia, Chile, Peru, Ecuador, Bolivia, Uruguay, Guatemala, Panama, Honduras, "
    "El Salvador, the Dominican Republic, Venezuela's Assembly news feed and Nicaragua's "
    "official gazette). Each item names its country and chamber. Its title is the source's "
    "own words, verbatim, in the source's language; the English takeaway, status and lines "
    "around it are ours. Never mark an item down for not being British or for not being in "
    "English: judge it in its own country's terms. Every item was put on our ground by a "
    "keyword taxonomy, which is loose: judge what the item does, not the term it matched. A "
    "matched word in a long omnibus title, a procedural vote, a tribute, a commemorative day "
    "or a routine funding line is background at most. A RECORDED VOTE is given by its "
    "question, tally and result; a BILL or initiative by its title and status; a QUESTION, "
    "answer or request for information by its subject; a PRESS, NEWS or GAZETTE item by its "
    "headline and an excerpt. Migration is matched and stored but never shown in these "
    "editions. CitizenGO campaigns", 1)
assert SYSTEM_PROMPT_EDITIONS != triage.SYSTEM_PROMPT

TIER_RANK = {1: 0, 2: 1}


# --- what is pending ---------------------------------------------------------------

def edition_since(country, today, directory=None):
    """The start (exclusive) of what the judge reads for a country edition:
    the latest edition's window when it is within one cadence of today, so
    the edition just sent and the next one are both covered; else one cadence."""
    days = country.cadence_days
    eds = [d for d in ce.editions(country.cc, directory) if d <= today]
    t = datetime.date.fromisoformat(today)
    if eds and (t - datetime.date.fromisoformat(eds[-1])).days <= days:
        return ce.window(country.cc, eds[-1], directory=directory, days=days)[0]
    return (t - datetime.timedelta(days=days)).isoformat()


def _frame(cc):
    if cc in ej.EDITION_CCS:
        c = ce.adapter(cc)
        return {"name": c.name, "chamber": c.chamber, "language": c.language}
    chamber = next((ch for code, _, ch in latam.COUNTRIES if code == cc), "")
    return {"name": latam.NAMES.get(cc, cc), "chamber": chamber, "language": "Spanish"}


def country_items(conn, cc, today, config_dir=None, directory=None):
    """The items an edition would show for cc, annotated with any scores."""
    if cc in ej.EDITION_CCS:
        country = ce.adapter(cc)
        since = edition_since(country, today, directory)
        wl = ce.watchlist_of(country, config_dir)
        got = country.items(conn, since, today, wl) or []
        if country.kinds:
            got = [it for it in got if it["kind"] in country.kinds]
        kept, _ = ce.noise_for(country).split(got, config_dir)
        items = ej.annotate(conn, ce.collapse_titles(kept))
        return [it for it in items if not (it.get("judge") == 0 and not it["watched"])]
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=LATAM_DAYS)).isoformat()
    # ledger=None: the alert ledger's moves are watched items, scored as they come.
    return latam.country_items(conn, cc, since, today, None, config_dir)


def priority(it):
    return (not it["watched"], TIER_RANK.get(it["tier"], 2), latam._neg(it["date"]),
            ej.item_id(it))


def pending(conn, today, config_dir=None, directory=None, ccs=None):
    """Unscored items across every edition, in the judge's order; a vote
    group once (its first item), an id once."""
    out, seen, groups = [], set(), set()
    for cc in ccs or (ej.EDITION_CCS + ej.LATAM_CCS):
        conn.row_factory = sqlite3.Row
        for it in country_items(conn, cc, today, config_dir, directory):
            if it.get("judge") is not None:
                continue
            out.append(it)
    out.sort(key=priority)
    kept = []
    for it in out:
        iid = ej.item_id(it)
        g = (it["cc"], it.get("group")) if it.get("group") else None
        if iid in seen or (g and g in groups):
            continue
        seen.add(iid)
        if g:
            groups.add(g)
        kept.append(it)
    return kept


def _kind(kind):
    return (ce.KIND_NAMES.get(kind) or (latam.KINDS.get(kind, kind),))[0]


def item_text(it, wl=None):
    """The frame the session judge reads for one item, one line, English
    around the source's own words."""
    f = _frame(it["cc"])
    bits = ["Country: {0}, {1} (titles in {2}).".format(f["name"], f["chamber"], f["language"]),
            "Kind: {0}; date {1}; key {2}.".format(_kind(it["kind"]), it["date"] or "?", it["key"]),
            "Areas matched: {0}.".format(ce.area_text(it["areas"]) or "none (watchlist only)"),
            "Tier {0}.".format(it["tier"]) if it["tier"] else "No tier (watchlist only)."]
    if it["watched"]:
        why = ce.why_watched(it, wl or {}) if wl is not None else None
        bits.append("Watched by CitizenGO{0}".format(": " + why if why else "."))
    else:
        bits.append("Not on the watchlist.")
    if it.get("terms"):
        bits.append("Matched terms: {0}.".format(", ".join(it["terms"][:8])))
    if it.get("own") is False:
        bits.append("Matched only through the bill or dossier it belongs to, not its own words.")
    if it.get("group_title") and it["group_title"] != it["title"]:
        bits.append("On: {0}.".format(ce.clip(it["group_title"], 200)))
    if it.get("takeaway"):
        bits.append("Takeaway: {0}".format(ce.sentence(ce.clean(it["takeaway"]))))
    if it.get("status"):
        bits.append("Status: {0}.".format(ce.clip(it["status"], 200).rstrip(".")))
    for line in (it.get("lines") or [])[:3]:
        bits.append(ce.sentence(ce.clean(line)))
    if it.get("body"):
        bits.append("Excerpt: {0}".format(ce.clip(it["body"], 300)))
    return ce.clip(" ".join(bits), MAX_TEXT)


def queue_items(conn, items, config_dir=None):
    wls = {}
    out = []
    for it in items:
        cc = it["cc"]
        if cc not in wls:
            wls[cc] = (ce.watchlist_of(ce.adapter(cc), config_dir) if cc in ej.EDITION_CCS
                       else latam.watchlist(cc, config_dir))
        out.append(triage.TriageItem(
            id=ej.item_id(it), title=it["title"] or "(no title published)",
            text=item_text(it, wls[cc]), tier=it["tier"],
            issue_areas=[latam.AREA_LABELS.get(a, str(a)) for a in it["areas"]],
            watchlist_hit=it["watched"]))
    return out


# --- the queue ------------------------------------------------------------------

def queue_out(conn, path, today, limit, config_dir=None, directory=None, log=print):
    """Write the first `limit` pending items for a Claude Code session.
    Returns (written, still pending after)."""
    queued = pending(conn, today, config_dir, directory)
    items = queued[:max(0, limit)]
    n = session_queue.write_queue(
        path, queue_items(conn, items, config_dir),
        "Country editions and Latam judge queue, {0}".format(today), QUEUE_MARKER,
        SYSTEM_PROMPT_EDITIONS)
    by = {}
    for it in items:
        by[it["cc"]] = by.get(it["cc"], 0) + 1
    log("edition-judge: session queue: {0} item(s) written to {1} ({2}); {3} pending in all, "
        "{4} watched; noise-filtered and muted items left out.".format(
            n, path, ", ".join("{0} {1}".format(k, v) for k, v in sorted(by.items())) or "none",
            len(queued), sum(it["watched"] for it in queued)))
    return n, len(queued) - n


def queue_in(conn, path, today, config_dir=None, directory=None, log=print):
    """Apply a filled-in queue, item by item. Returns (scored, refused, blank),
    or None when the file is not this judge's queue."""
    results, refused, blank = session_queue.read_queue(path, QUEUE_MARKER)
    if refused and refused[0][0] == "(file)":
        log("  [gap] session queue {0} refused: {1}".format(path, refused[0][1]))
        return None
    done = ej.load(conn)
    open_items = {ej.item_id(it): it for it in pending(conn, today, config_dir, directory)}
    scored = 0
    for res in results:
        if res.id in done:
            refused.append((res.id, "already scored; scores are written once ever"))
        elif res.id not in open_items:
            refused.append((res.id, "not a pending edition item"))
        elif ej.write(conn, open_items[res.id]["cc"], res.id, res.score, res.why, today):
            scored += 1
    conn.commit()
    for iid, why in refused:
        log("  [gap] queue item refused: {0}: {1}".format(iid, why))
    log("edition-judge: session queue: {0} item(s) scored, {1} refused, {2} left blank "
        "(they stay pending for the next run).".format(scored, len(refused), len(blank)))
    return scored, len(refused), len(blank)


# --- rewriting the week's editions -----------------------------------------------

def scored_on(conn, today):
    """Country codes with a session score written on `today`."""
    return {r[0] for r in latam.rows(conn, "SELECT DISTINCT cc FROM {0} WHERE model=? AND "
                                           "substr(scored_at,1,10)=?".format(ej.TABLE),
                                     (SESSION_MODEL, today))}


def leading(text):
    """The edition's "Leading:" lines, or []."""
    lines = (text or "").splitlines()
    if "Leading:" not in lines:
        return []
    out = []
    for line in lines[lines.index("Leading:") + 1:]:
        if not line.strip():
            break
        out.append(line)
    return out


def rerender(conn, today, ccs=None, directory=None, config_dir=None, log=print):
    """Rewrite the latest edition of each country in `ccs` (default: those
    scored today) in place. Returns [(name, path, new leading lines)] for the
    editions whose lead changed."""
    ccs = scored_on(conn, today) if ccs is None else set(ccs)
    changed = []
    t = datetime.date.fromisoformat(today)
    for cc in ej.EDITION_CCS:
        if cc not in ccs:
            continue
        country = ce.adapter(cc)
        eds = [d for d in ce.editions(cc, directory) if d <= today]
        if not eds or (t - datetime.date.fromisoformat(eds[-1])).days > country.cadence_days:
            log("edition-judge: {0}: no edition in the last {1} days to rewrite".format(
                cc, country.cadence_days))
            continue
        path = ce.edition_path(cc, eds[-1], directory)
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
        conn.row_factory = sqlite3.Row
        new = ce.render(conn, country, eds[-1], config_dir=config_dir, directory=directory)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new + "\n")
        log("edition-judge: rewrote {0}".format(os.path.relpath(path, ROOT)))
        if leading(old) != leading(new):
            changed.append((country.name, path, leading(new)))
    if directory is None and ccs & set(ej.LATAM_CCS):
        rerender_latam(conn, today, log)
    return changed


def rerender_latam(conn, today, log=print):
    """The Latam edition, rewritten when it is under a week old (no DM: the
    held alerts carry what is new; tools/latam_alerts.py)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import latam_monitor
    eds = [d for d in latam_monitor.editions() if d <= today]
    if not eds or (datetime.date.fromisoformat(today)
                   - datetime.date.fromisoformat(eds[-1])).days > LATAM_FRESH_DAYS:
        log("edition-judge: Latam: no edition in the last {0} days to rewrite".format(
            LATAM_FRESH_DAYS))
        return
    path = os.path.join(ROOT, "editions", "latam-monitor-{0}.md".format(eds[-1]))
    conn.row_factory = sqlite3.Row
    text = latam_monitor.render_edition(conn, eds[-1])
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    log("edition-judge: rewrote {0}".format(os.path.relpath(path, ROOT)))


def slack(line):
    """A Markdown edition line as Slack mrkdwn."""
    line = re.sub(r"^- ", "• ", line)
    return re.sub(r"\*([^*]+)\*", r"_\1_", line)


def update_dm(changed):
    """One DM for every edition whose lead the scores changed; None for none."""
    if not changed:
        return None
    lines = [":scales: *Country editions, re-scored*",
             "The free session judge read this week's items, and what leads changed in {0} "
             "edition(s) already sent. Each is rewritten in place; no other DM.".format(
                 len(changed))]
    for name, path, lead in changed:
        lines.append("*{0}*: {1}{2}".format(name, ce.REPO, os.path.relpath(path, ROOT)))
        lines += [slack(x) for x in lead[:3]] or ["• nothing leads now"]
    return "\n".join(lines)


# --- the command ----------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--limit", type=int, default=25)
    q = ap.add_mutually_exclusive_group()
    q.add_argument("--queue-out", metavar="PATH",
                   help="write the first --limit pending items for a Claude Code session; no spend")
    q.add_argument("--queue-in", metavar="PATH",
                   help="apply a session's SCORE/WHY lines from PATH; no spend")
    q.add_argument("--rerender", action="store_true",
                   help="rewrite this week's editions of the countries scored today")
    ap.add_argument("--dm", action="store_true",
                    help="with --rerender: one DM to Chris when the lead of an edition changed")
    args = ap.parse_args(argv)
    conn = db.init_db(db.connect(args.db))
    conn.row_factory = sqlite3.Row
    today = args.date
    if args.queue_out:
        queue_out(conn, args.queue_out, today, args.limit)
        return 0
    if args.queue_in:
        got = queue_in(conn, args.queue_in, today)
        dist = dict(conn.execute("SELECT score, COUNT(*) FROM {0} GROUP BY 1".format(
            ej.TABLE)).fetchall())
        print("  edition_scores so far: {0}".format(
            ", ".join("{0}: {1}".format(k, dist[k]) for k in sorted(dist)) or "none"))
        conn.close()
        return 1 if got is None else 0
    if args.rerender:
        changed = rerender(conn, today)
        text = update_dm(changed)
        if text and args.dm:
            print("dm: {0}".format(ce.send_dm(text)))
        elif text:
            print(text)
        else:
            print("edition-judge: no edition's lead changed; no DM")
        return 0
    queued = pending(conn, today)
    by = {}
    for it in queued:
        by[it["cc"]] = by.get(it["cc"], 0) + 1
    print("edition-judge: {0} item(s) pending ({1} watched, {2} tier 1): {3}".format(
        len(queued), sum(it["watched"] for it in queued),
        sum(it["tier"] == 1 and not it["watched"] for it in queued),
        ", ".join("{0} {1}".format(k, v) for k, v in sorted(by.items())) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
