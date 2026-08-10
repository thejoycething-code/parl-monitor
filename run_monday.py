"""Monday publish run (unattended): render the edition, post to Slack, create
the Asana reading task. Companion to the Sunday pull; handoff section 8 cron
design, extended with publishing.

  python3 run_monday.py               # this week's Monday
  python3 run_monday.py 2026-08-10    # explicit week

Human review remains available, not blocking: decisions saved into
reviews/review-<week>.md before this runs are applied (merge-preserved). If
nobody reviewed, the edition ships WATCH/NOTE-only; the ACT-owner validation
makes ownerless urgency structurally impossible in an unattended run.
"""

from __future__ import annotations

import datetime
import os
import re
import sys

import run_weekly
from src import digest, partner, publish

ROOT = os.path.dirname(os.path.abspath(__file__))


def summarise_edition(markdown, week):
    """Build the Slack mrkdwn summary + supporting lists from the edition."""
    top = re.findall(r"^- \*\*\[(ACT|WATCH|NOTE)\]\*\* (.+)$", markdown, re.M)
    acts = [text for tag, text in top if tag == "ACT"]
    # ACT lines can appear in any section; collect all, deduped, tag stripped.
    all_acts = []
    for line in re.findall(r"^- \*\*\[ACT\]\*\* (.+)$", markdown, re.M):
        clean = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", line)  # unlink
        if clean not in all_acts:
            all_acts.append(clean)

    deadlines = []  # populated from the store by deadlines_from_store()

    bullet_lines = []
    for tag, text in top[:4]:
        clean = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
        bullet_lines.append("• *[{0}]* {1}".format(tag, clean))
    for act in all_acts:
        line = "• *[ACT]* {0}".format(act)
        if line not in bullet_lines:
            bullet_lines.append(line)

    summary = ("*Parliamentary Monitor - week commencing {0}*\n\n"
               "The weekly briefing on everything moving in Westminster that touches "
               "our campaigns.\n\n{1}").format(week, "\n".join(bullet_lines))
    return summary, all_acts, deadlines


def edition_number(conn):
    return conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0]


def deadlines_from_store(conn, week, days=21):
    """Reviewed items whose deadline falls within the horizon, for the task."""
    import datetime as _dt
    horizon = (_dt.date.fromisoformat(week) + _dt.timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT title, deadline FROM items WHERE priority_tag IS NOT NULL "
        "AND deadline IS NOT NULL AND deadline >= ? AND deadline <= ? ORDER BY deadline",
        (week, horizon)).fetchall()
    return ["{0} (closes {1})".format(r["title"], r["deadline"]) for r in rows]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    # --no-publish renders, redacts and builds the partner site but posts
    # nothing to Slack and creates no Asana task: the way to exercise the
    # pipeline (and the Vercel deploy) without anything team-visible.
    no_publish = "--no-publish" in sys.argv or os.environ.get("NO_PUBLISH") == "1"
    week = args[0] if args else (
        datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    ).isoformat()

    path = run_weekly.render_edition(week, run_weekly._db_name(week))
    with open(path, "r", encoding="utf-8") as handle:
        markdown = handle.read()

    from src import db
    conn = db.connect(os.path.join(ROOT, "data", run_weekly._db_name(week)))
    number = edition_number(conn)
    store_deadlines = deadlines_from_store(conn, week)
    scrub_names = partner.owners_from_store(conn)

    # Publishing is idempotent per week. The 2026-08-10 edition went out twice:
    # a local run after the scheduled slot failed to start, then the delayed
    # cron arrived four hours late and posted again - the delay-proof guard
    # correctly identified it as the legitimate slot, because it was. Whether
    # a run is a duplicate is a fact about what has already been published,
    # not about clocks or cron identities, so it is recorded here in the store
    # (committed by every publish, so a later runner sees an earlier one).
    conn.execute("CREATE TABLE IF NOT EXISTS publish_log ("
                 "week TEXT PRIMARY KEY, message_ts TEXT, canvas_id TEXT, "
                 "asana_gid TEXT, published_at TEXT)")
    already = conn.execute("SELECT published_at, canvas_id FROM publish_log "
                           "WHERE week = ?", (week,)).fetchone()
    force = "--force" in sys.argv
    if already and not no_publish and not force:
        print("already published for w/c {0} at {1} (canvas {2}); skipping the "
              "Slack post and Asana task. Site artefacts still regenerate. "
              "Use --force to publish again.".format(
                  week, already["published_at"], already["canvas_id"]))
        no_publish = True

    secrets = publish.load_secrets()
    summary, acts, deadlines = summarise_edition(markdown, week)

    # Canvas carries the edition body (strip the file's H1; canvas has a title).
    canvas_md = re.sub(r"^# Parliamentary Monitor\n", "", markdown, count=1)

    if no_publish:
        slack = {"skipped": "dry run (--no-publish): nothing posted to Slack"}
        asana = {"skipped": "dry run (--no-publish): no reading task created"}
        print("slack: {0}\nasana: {1}".format(slack["skipped"], asana["skipped"]))
        canvas_url = "(dry run)"
    else:
        slack = publish.slack_publish_edition(secrets, week, number, canvas_md, summary)
        print("slack: {0}".format(slack))
        canvas_url = slack.get("canvas_url", "(not posted to Slack)")
        asana = publish.asana_create_reading_task(secrets, week, canvas_url, acts, store_deadlines)
        print("asana: {0}".format(asana))
        if "error" not in slack:
            conn.execute("INSERT OR REPLACE INTO publish_log "
                         "(week, message_ts, canvas_id, asana_gid, published_at) "
                         "VALUES (?, ?, ?, ?, ?)",
                         (week, slack.get("message_ts"), slack.get("canvas_id"),
                          asana.get("task_gid"),
                          datetime.datetime.now().isoformat(timespec="seconds")))
            conn.commit()
    conn.close()

    # Partner edition: redacted static site, committed alongside the edition.
    import glob
    weeks = sorted(os.path.basename(f)[len("parliamentary-monitor-"):-3]
                   for f in glob.glob(os.path.join(ROOT, "editions", "parliamentary-monitor-*.md")))
    partner_md = partner.redact(markdown, extra_names=scrub_names)
    # The question tables link to a companion page carrying the full text.
    pq_conn = db.connect(os.path.join(ROOT, "data", run_weekly._db_name(week)))
    pq_edition = run_weekly.sections_from_store(
        pq_conn, digest.Edition(week_commencing=week, number=number, mode="normal"))
    pq_conn.close()
    site = partner.build_site(os.path.join(ROOT, "partner_site"), week, partner_md, weeks,
                              pq_rows=pq_edition.pq_rows,
                              pq_background=pq_edition.pq_background)
    print("partner site: {0}".format(site))

    # Internal 5CA tracker: regenerated weekly so the placements the team works
    # from are never staler than an edition. Written to docs/, never to
    # partner_site/ -- stance placements are our analysis, not public record.
    import subprocess
    # Refresh the Commons roster before anything that depends on it: a
    # by-election MP is otherwise absent from the vote tracker, and a departed
    # one still counted, until somebody remembers to run the tool by hand.
    for label, argv in (("roster", ["tools/pull_commons_roster.py"]),
                        ("vote tracker", ["tools/make_vote_tracker.py"]),
                        ("5ca sheets", ["tools/make_5ca_web.py"]),
                        ("5ca matrix", ["tools/make_5ca_matrix.py"])):
        # Each tool prints its own one-line summary; relay it rather than
        # discarding it. A log that is silent on success cannot be used to
        # tell "ran and rebuilt" from "never ran" -- and an unattended run is
        # read only through its log.
        try:
            done = subprocess.run([sys.executable, os.path.join(ROOT, *argv[0].split("/"))],
                                  check=True, cwd=ROOT, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
            out = (done.stdout or b"").decode("utf-8", "replace").strip().splitlines()
            head = out[0].strip() if out else "ok (no output)"
            if head.lower().startswith(label.lower() + ":"):
                head = head[len(label) + 1:].strip()
            print("{0}: {1}".format(label, head))
            # Detail lines are mostly tallies and output paths, but the ones
            # naming a caveat (unsigned divisions, missing data) are the whole
            # reason to read the log at all.
            for line in out[1:]:
                if re.search(r"\bNOT\b|missing|no recorded|gap|stale|gaps", line):
                    print("  {0}".format(line.strip()))
        except Exception as exc:
            print("{0}: failed ({1}); edition unaffected".format(label, exc))
    try:
        done = subprocess.run([sys.executable,
                               os.path.join(ROOT, "tools", "make_5ca_tracker.py"), week],
                              check=True, cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        tracker_out = (done.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        print("5ca tracker: {0}".format(tracker_out[0].strip() if tracker_out else "ok"))
    except Exception as exc:
        print("5ca tracker: failed ({0}); edition unaffected".format(exc))

    # The per-area CSVs are what a campaigner pastes into a Campaigns Brief, so
    # they are refreshed with the tracker rather than left at whatever date they
    # were last generated by hand.
    from src import stance as _stance
    cfg = _stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    excluded = set(cfg.get("excluded_from_5ca") or [])
    made = 0
    for area in sorted(set(range(1, 12)) - excluded):
        try:
            subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_5ca.py"),
                            str(area)], check=True, cwd=ROOT,
                           stdout=subprocess.DEVNULL)
            made += 1
        except Exception as exc:
            print("5ca sheet area {0}: failed ({1})".format(area, exc))
    print("5ca sheets refreshed: {0}".format(made))

    print("edition: {0}".format(path))
    failures = [s for s in (slack, asana) if "error" in s]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
