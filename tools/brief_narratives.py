#!/usr/bin/env python3
"""Campaigns Brief narratives, drafted by the free session judge (src/brief_narratives.py).

    python3 tools/brief_narratives.py                        # what is pending, and the placeholder count
    python3 tools/brief_narratives.py --queue-out q.md --limit 3   # for a session
    python3 tools/brief_narratives.py --queue-in q.md               # store what it drafted
    python3 tools/brief_narratives.py --show SLUG            # a stored narrative
    python3 tools/brief_narratives.py --redraft SLUG         # forget one, so it is queued again

On the Mac Mini, tools/session_judge.sh drives the queue flags with
SESSION_JUDGE_PROMPT set to src/brief_narratives.NARRATIVE_PROMPT
(jobs/brief-narratives.sh, Sundays 18:15 London: after the UK session judge
has scored the week's items and before the German weekly at 20:00 and the
Monday publish at 04:00, which build the briefs). No API key, no spend.

WHAT IS PENDING, in this order:
  1. new Westminster subjects (tools/make_briefs.py subjects with no brief yet):
     the Monday publish builds their briefs with the narrative already drafted;
  2. new German subjects (tools/de_briefs.py), likewise for Sunday's de-weekly;
  3. BACKFILL: live briefs already written with placeholders (a UK brief still
     pending review, a German draft) whose subject is still current. When their
     narrative arrives the brief files are re-rendered in place (no new review
     task, status kept) and a UK brief already on Drive is marked for the Drive
     publisher to refill (tools/publish_briefs_to_drive.py, only when no person
     has edited the sheet).
A narrative is written once per slug; --redraft clears one. A placeholder stays
until a narrative passes every check (src/brief_narratives.check_fields).
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import brief_narratives as bn  # noqa: E402
from src import db  # noqa: E402

LABEL = "brief narratives"
PLACEHOLDER_SIGNS = ("NARRATIVE NOT DRAFTED", "NARRATIVE DRAFT FAILED")
UK_FIELD_PLACEHOLDER = "[CAMPAIGNER: draft needed]"
# A UK brief with this many prose fields left as placeholders had no
# narrative at all (one missing field is a draft that skipped a field).
UK_PLACEHOLDER_MIN = 6
LIVE = {"uk": ("pending",), "de": ("draft",)}


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Builders:
    """make_briefs and de_briefs, loaded once, pointed at one briefs folder."""

    def __init__(self, briefs_dir=None):
        self.mb = _load("make_briefs")
        self.de = _load("de_briefs")
        if briefs_dir:
            self.mb.BRIEFS_DIR = self.de.BRIEFS_DIR = os.path.abspath(briefs_dir)
        self.briefs_dir = self.mb.BRIEFS_DIR

    def subjects(self, conn, builder):
        try:
            return self.mb.subjects(conn) if builder == "uk" else self.de.subjects(conn)
        except Exception as exc:                            # noqa: BLE001
            print("  [gap] {0} subjects unreadable: {1}".format(builder, exc))
            return []

    def payload(self, conn, builder, s):
        facts = self.mb.uk_facts(conn, s) if builder == "uk" else self.de.facts(conn, s)
        return self.mb.narrative_payload(s, facts)


def has_placeholders(path):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return False
    return (any(sign in text for sign in PLACEHOLDER_SIGNS)
            or text.count(UK_FIELD_PLACEHOLDER) >= UK_PLACEHOLDER_MIN)


def survey(conn, b):
    """{'pending': [items in queue order], 'stuck': [(builder, slug)]}.

    stuck: live briefs showing placeholders whose subject is no longer
    current (the bill concluded, the petition closed), so there is no record
    left to draft from; they are counted, never queued."""
    try:
        logged = {r[0]: r[1] for r in conn.execute("SELECT slug, status FROM brief_log")}
    except Exception:                                       # noqa: BLE001
        logged = {}                                         # no brief yet, anywhere
    try:
        drafted = {r[0] for r in conn.execute("SELECT slug FROM brief_narratives")}
    except Exception:                                       # noqa: BLE001
        drafted = set()                                     # read-only: no table yet
    new, backfill, current = [], [], set()
    for builder in ("uk", "de"):
        for s in b.subjects(conn, builder):
            current.add(s["slug"])
            if s["slug"] in drafted:
                continue
            item = {"builder": builder, "slug": s["slug"], "title": s["title"],
                    "kind": s["kind"], "subject": s}
            if s["slug"] not in logged:
                new.append(dict(item, why="new"))
            elif (logged[s["slug"]] in LIVE[builder]
                  and has_placeholders(os.path.join(b.briefs_dir, s["slug"] + ".md"))):
                backfill.append(dict(item, why="backfill"))
    stuck = []
    for slug, status in logged.items():
        builder = "de" if slug.startswith("de-") else "uk"
        if (status in LIVE[builder] and slug not in current and slug not in drafted
                and has_placeholders(os.path.join(b.briefs_dir, slug + ".md"))):
            stuck.append((builder, slug))
    # Stable sort: within each refusal count, new before backfill, record order.
    tried = bn.refusals(conn)
    pending = sorted(new + backfill, key=lambda it: tried.get(it["slug"], 0))
    return {"pending": pending, "stuck": stuck}


def queue_out(conn, b, path, limit, log=print):
    found = survey(conn, b)
    todo = found["pending"][:limit]
    for it in todo:
        it["payload"] = b.payload(conn, it["builder"], it["subject"])
    n = bn.write_queue(path, todo, b.mb.DRAFT_SYSTEM)
    counts = {}
    for it in todo:
        k = "{0} {1}".format(it["builder"], it["why"])
        counts[k] = counts.get(k, 0) + 1
    log("{0}: session queue: {1} item(s) written to {2} ({3}); {4} pending in all.".format(
        LABEL, n, path, ", ".join("{0} {1}".format(v, k) for k, v in counts.items()) or "none",
        len(found["pending"])))
    return n


def queue_in(conn, b, path, today=None, log=print):
    """Store every narrative that keeps the rules; re-render backfilled briefs.
    Returns (stored, refused, blank), or None for a file that is not ours."""
    today = today or datetime.date.today()
    answers, refused, blank = bn.read_queue(path)
    if refused and refused[0][0] == "(file)":
        log("  [gap] session queue {0} refused: {1}".format(path, refused[0][1]))
        return None
    b.mb.ensure_log(conn)
    bn.ensure(conn)
    pending = {bn.item_id(it["builder"], it["slug"]): it for it in survey(conn, b)["pending"]}
    wanted = [fid for fid, _ in b.mb.NARRATIVE_FIELDS]
    cfg = None
    stored = 0
    for iid, text in answers.items():
        it = pending.get(iid)
        if it is None:
            refused.append((iid, "not pending: drafted already (--redraft clears one), or no "
                                 "longer a brief subject"))
            continue
        fields, problem = bn.parse_answer(text, wanted)
        payload = b.payload(conn, it["builder"], it["subject"])
        if not problem:
            tim_ids = [c.get("id") for c in (payload.get("facts") or {}).get("tim_candidates") or []]
            problem = bn.check_fields(fields, bn.payload_text(payload), wanted, tim_ids)
        if problem:
            refused.append((iid, problem))
            continue
        bn.save(conn, it["slug"], it["builder"], fields, payload, today.isoformat())
        conn.commit()
        stored += 1
        if it["why"] != "backfill":
            log("  stored {0} (the brief is built with it)".format(iid))
            continue
        # The brief is live with placeholders: re-render it in place now.
        try:
            if it["builder"] == "uk":
                if cfg is None:
                    from src import stance
                    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
                b.mb.write_one(conn, it["subject"], cfg, today, None, rerender=True)
            else:
                b.de.write_brief(conn, it["subject"], b.mb, None, today.isoformat())
            log("  stored {0} and re-rendered its brief".format(iid))
        except Exception as exc:                            # noqa: BLE001
            log("  [gap] stored {0}, but the re-render failed ({1}); the next builder run "
                "uses it".format(iid, exc))
    for iid, why in refused:
        log("  [gap] queue item refused: {0}: {1}".format(iid, why))
        if iid in pending:
            bn.note_refusal(conn, pending[iid]["slug"], why, today.isoformat())
    conn.commit()
    log("{0}: session queue: {1} item(s) scored, {2} refused, {3} left blank "
        "(they stay pending for the next run).".format(LABEL, stored, len(refused), len(blank)))
    return stored, len(refused), len(blank)


def report(conn, b):
    found = survey(conn, b)
    try:
        conn.execute("SELECT 1 FROM brief_log LIMIT 1")
    except Exception:                                       # noqa: BLE001
        print("{0}: no brief_log in this store".format(LABEL))
        return
    live = 0
    for builder, statuses in LIVE.items():
        for (slug,) in conn.execute("SELECT slug FROM brief_log WHERE status IN ({0})".format(
                ",".join("?" * len(statuses))), statuses):
            if (slug.startswith("de-")) == (builder == "de"):
                live += 1
    showing = [it for it in found["pending"] if it["why"] == "backfill"]
    print("{0}: {1} live brief(s) (UK pending review, German drafts); {2} show the "
          "narrative placeholder: {3} to backfill, {4} no longer a subject (nothing to "
          "draft from).".format(LABEL, live, len(showing) + len(found["stuck"]), len(showing),
                                len(found["stuck"])))
    print("{0}: {1} pending in all ({2} new subject(s), {3} backfill).".format(
        LABEL, len(found["pending"]), len(found["pending"]) - len(showing), len(showing)))
    for it in found["pending"]:
        print("  {0:8} {1}".format(it["why"], bn.item_id(it["builder"], it["slug"])))
    for builder, slug in found["stuck"]:
        print("  stuck    {0}".format(bn.item_id(builder, slug)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--briefs-dir", help="the briefs folder (default briefs/)")
    ap.add_argument("--queue-out")
    ap.add_argument("--queue-in")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--show")
    ap.add_argument("--redraft")
    args = ap.parse_args(argv)

    conn = db.connect(args.db)
    b = Builders(args.briefs_dir)
    try:
        if args.queue_out:
            queue_out(conn, b, args.queue_out, max(0, args.limit))
        elif args.queue_in:
            if queue_in(conn, b, args.queue_in) is None:
                return 1
        elif args.show:
            got = bn.stored(conn, args.show)
            if not got:
                print("{0}: no stored narrative for {1}".format(LABEL, args.show))
                return 1
            for fid, prose in got.items():
                print("@@{0}@@\n{1}\n".format(fid, prose))
        elif args.redraft:
            bn.forget(conn, args.redraft)
            conn.commit()
            print("{0}: {1} cleared; it is queued again while its brief needs one".format(
                LABEL, args.redraft))
        else:
            report(conn, b)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
