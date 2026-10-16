#!/usr/bin/env python3
"""Where a German parliamentarian stands, from their own words.

    python3 tools/de_stance.py --dry-run     # what would be scored, and the cost
    python3 tools/de_stance.py --limit 40

Christopher, 23 September 2026: build stance scoring. It was impossible in
Germany until the speeches layer existed a day earlier -- the Bundestag takes
68 recorded votes in sixteen months and six of the matched ones are migration,
so votes carry almost no signal here. What a member SAYS is the German
evidence stream.

Same gradient as Westminster (+2 strong ally .. -2 strong opponent), the same
src/stance.py machinery, the same `stance` table. Refs are namespaced
"de-speech:..." so German and Westminster evidence cannot collide in a table
keyed on ref alone.

THE WHOLE SPEECH IS SENT, NOT THE MATCHED PASSAGE. This is the one design
point that matters and it is not a preference. src/stance._evidence_text
centres its window on the excerpt INSIDE the full text because excerpt-only
scoring is a failure this repo has already paid for by name: Lord Farmer's
excerpt read as support for the assisted dying Bill when the surrounding
speech was plainly against it, and that misread flipped his placement
(2026-08-11). de_speeches therefore stores the full body of every matched
speech, and a German pass reading 400 characters would have repeated a known
bug in a second language.

MIGRATION IS NOT SCORED. Area 11 is collated, never campaigned, and renders
nowhere, so paying a judge to place members on it would be spend for a
surface that does not exist.

NO VERDICT ON A DIVISION. This scores speech. Which way a German division ran
for us stays a signed human judgement.

THE FREE SESSION JUDGE IS THE DEFAULT (Chris, 16 October 2026: "ALL model
scoring moves off the paid Claude API"). --queue-out writes the newest
--limit unscored speeches, with the German stance frame and the very window
of text the API judge would read (stance._evidence_text), for a Claude Code
session on the Mac Mini (jobs/europe-session-judge.sh through
tools/session_judge.sh with uk_stance_judge.STANCE_PROMPT); --queue-in reads
STANCE (-2..2) and WHY back strictly (tools/uk_stance_judge.read_queue) and
stores them as the API pass does, model 'claude-code-session'. The paid path
runs only with DE_STANCE_PAID=1 (src/paid_ai.py); a key alone does nothing.

    python3 tools/de_stance.py --queue-out /tmp/q.md --limit 25
    python3 tools/de_stance.py --queue-in /tmp/q.md

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, paid_ai, publish, spend, stance  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
import uk_stance_judge  # noqa: E402  (the stance queue's reader and prompt)

QUEUE_MARKER = "<!-- de-stance-session-queue v1 -->"
SESSION_MODEL = "claude-code-session"

PASS_NAME = "de-stance"
REF = "de-speech:{0}"


def evidence(conn, limit=None):
    """Unscored German speeches, as stance.Evidence.

    A speech whose only areas are hidden ones is left out entirely rather
    than scored and then suppressed downstream.
    """
    stance.ensure_table(conn)
    rows = conn.execute(
        "SELECT s.* FROM de_speeches s LEFT JOIN stance st "
        "ON st.ref = 'de-speech:' || s.speech_id "
        "WHERE st.ref IS NULL AND s.areas IS NOT NULL AND s.areas != '[]' "
        "AND s.role != 'chair' "
        "ORDER BY s.date DESC").fetchall()
    out = []
    hidden = set(stance.HIDDEN_AREAS)
    for r in rows:
        try:
            areas = json.loads(r["areas"] or "[]")
        except ValueError:
            areas = []
        # Hidden areas, and areas with no stated position (stance.positioned),
        # leave nothing to score against. The 24 September organ-donation
        # debate would otherwise have been placed on assisted dying.
        areas = [a for a in stance.positioned(areas) if a not in hidden]
        if not areas:
            continue
        line = "{0}{1} in the Bundestag, {2}".format(
            r["speaker"] or "?",
            " ({0})".format(r["party"]) if r["party"] else "",
            r["date"] or "?")
        out.append(stance.Evidence(
            ref=REF.format(r["speech_id"]), kind="speech", line=line,
            areas=areas,
            text=r["text"] or "", excerpt=r["excerpt"] or ""))
        if limit and len(out) >= limit:
            break
    return out


def report(conn, log=print, top=8):
    """Where members sit, once scored. Read-only."""
    rows = conn.execute(
        "SELECT s.speaker, s.party, AVG(st.stance) AS avg, COUNT(*) AS n "
        "FROM de_speeches s JOIN stance st "
        "ON st.ref = 'de-speech:' || s.speech_id "
        "WHERE s.person_id IS NOT NULL "
        "GROUP BY s.person_id ORDER BY avg DESC").fetchall()
    if not rows:
        log("de-stance: nothing scored yet.")
        return []
    log("de-stance: {0} member(s) placed.".format(len(rows)))
    for r in list(rows)[:top]:
        log("  {0:+.1f}  {1} ({2})  from {3} speech(es)".format(
            r["avg"], (r["speaker"] or "?")[:34], r["party"] or "-", r["n"]))
    if len(rows) > top:
        log("  ...")
        for r in list(rows)[-min(top, len(rows) - top):]:
            log("  {0:+.1f}  {1} ({2})  from {3} speech(es)".format(
                r["avg"], (r["speaker"] or "?")[:34], r["party"] or "-",
                r["n"]))
    return rows


def queue_out(conn, path, today, limit, log=print):
    """The newest `limit` unscored speeches, for a Claude Code session."""
    allev = evidence(conn)
    chosen = allev[:max(0, limit)]
    head = uk_stance_judge.HEADER.replace("# UK stance queue", "# German stance queue")
    blocks = [head.format(today=today, marker=QUEUE_MARKER,
                          system_prompt=stance.SYSTEM_PROMPT_DE.strip())]
    for ev in chosen:
        blocks += ["### item: {0}".format(ev.ref),
                   "- kind: {0} | areas: {1}".format(ev.kind, ", ".join(str(a) for a in ev.areas) or "-"),
                   "- line: {0}".format(" ".join((ev.line or "").split())),
                   "- text: {0}".format(" ".join(stance._evidence_text(ev).split())),
                   "STANCE: ", "WHY: ", ""]
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(blocks))
    log("de-stance: session queue: {0} item(s) written to {1}; {2} unscored in all.".format(
        len(chosen), path, len(allev)))
    return len(chosen)


def queue_in(conn, path, today, log=print):
    """Store a filled-in queue's stances strictly. None if not our file."""
    results, refused, blank = uk_stance_judge.read_queue(path, QUEUE_MARKER)
    if refused and refused[0][0] == "(file)":
        log("  [gap] session queue {0} refused: {1}".format(path, refused[0][1]))
        return None
    open_refs = {ev.ref for ev in evidence(conn)}
    good = []
    for res in results:
        if res.ref in open_refs:
            good.append(res)
        else:
            refused.append((res.ref, "not an unscored German speech"))
    stance.store_scores(conn, good, today, model=SESSION_MODEL)
    conn.commit()
    for ref, why in refused:
        log("  [gap] queue item refused: {0}: {1}".format(ref, why))
    log("de-stance: session queue: {0} item(s) scored, {1} refused, {2} left blank.".format(
        len(good), len(refused), len(blank)))
    return len(good)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--queue-out", metavar="PATH")
    ap.add_argument("--queue-in", metavar="PATH")
    ap.add_argument("--limit", type=int, help="score at most this many")
    ap.add_argument("--dry-run", action="store_true",
                    help="what would be scored, and roughly what it costs")
    ap.add_argument("--report", action="store_true",
                    help="print the placements already scored, offline")
    args = ap.parse_args()

    conn = db.init_db(db.connect(args.db))
    today = args.date
    if args.queue_out:
        queue_out(conn, args.queue_out, today, args.limit or 25)
        conn.close()
        return 0
    if args.queue_in:
        got = queue_in(conn, args.queue_in, today)
        conn.close()
        return 1 if got is None else 0
    if args.report:
        report(conn)
        conn.close()
        return 0

    items = evidence(conn, limit=args.limit)
    if args.dry_run:
        calls = (len(items) + stance.BATCH_SIZE - 1) // stance.BATCH_SIZE
        print("de-stance: {0} speech(es) unscored -> about {1} call(s). "
              "Nothing sent.".format(len(items), calls))
        for ev in items[:5]:
            print("  {0}  [{1}]  {2} chars".format(
                ev.line[:58], ",".join(str(a) for a in ev.areas),
                len(ev.text or "")))
        conn.close()
        return 0
    if not items:
        print("de-stance: nothing unscored.")
        conn.close()
        return 0

    if not paid_ai.allowed(PASS_NAME):
        # PAID AI OFF (16 October 2026): left for the free session judge.
        print(paid_ai.off_line(PASS_NAME, len(items), "speech(es)"))
        conn.close()
        return 0
    secrets = publish.load_secrets()

    def _spend(usage, model):
        # usage_sink is a CALLABLE (usage, model), not a list to append to.
        # Passing a list raised only when the FIRST reply came back, after
        # the call had been paid for -- so the shape of this argument is
        # worth being exact about.
        spend.record(conn, PASS_NAME, model or stance.STANCE_MODEL, usage,
                     dated=today)

    # Batched, so one bad reply costs one batch rather than the whole run --
    # the same guard src/stance.score_pending uses.
    results, failed = [], 0
    for batch in stance._batches(items):
        try:
            results.extend(stance.classify_batch(
                batch, api_key=secrets.get("anthropic_api_key"),
                usage_sink=_spend, system=stance.SYSTEM_PROMPT_DE))
        except Exception as exc:                            # noqa: BLE001
            failed += 1
            print("  batch of {0} failed: {1}".format(len(batch),
                                                      str(exc)[:110]))
    stance.store_scores(conn, results, today)
    conn.commit()
    print("de-stance: {0} speech(es) scored{1}.".format(
        len(results),
        "" if not failed else ", {0} batch(es) failed".format(failed)))
    report(conn)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
