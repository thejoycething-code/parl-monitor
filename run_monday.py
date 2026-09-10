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
    # Editorial tags retired: the summary quotes the Top lines section as
    # written -- score-driven, no [ACT]/[WATCH]/[NOTE] and no owners.
    m = re.search(r"^## (?:\d+\. )?Top lines\n(.*?)(?=^## |\Z)",
                  markdown, re.M | re.S)
    top_block = m.group(1) if m else ""
    top = re.findall(r"^- (.+)$", top_block, re.M)
    all_acts = []
    deadlines = []

    bullet_lines = []
    for text in top[:6]:
        clean = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
        bullet_lines.append("• {0}".format(clean))

    summary = ("*Parliamentary Monitor - week commencing {0}*\n\n"
               "The weekly briefing on everything moving in Westminster that touches "
               "our campaigns.\n\n{1}").format(week, "\n".join(bullet_lines))
    return summary, all_acts, deadlines


def edition_number(conn, week):
    """1 + editions before this week: order-independent, so a re-render or a
    post-render call agree (bare COUNT(*) said 'Edition 1' forever in the
    file header and drifted by call order -- found 2026-08-23)."""
    return 1 + conn.execute("SELECT COUNT(*) FROM editions WHERE "
                            "week_commencing < ?", (week,)).fetchone()[0]


def deadlines_from_store(conn, week, days=21):
    """Reviewed items whose deadline falls within the horizon, for the task."""
    import datetime as _dt
    horizon = (_dt.date.fromisoformat(week) + _dt.timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT title, deadline FROM items WHERE triage_score >= 2 "
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

    # THE DEVOLVED JUDGE, wired here by Christopher's decision 2026-09-06
    # rather than into the three devolved weeklies, which carry no
    # secrets by design -- the separation rule that keeps Slack tokens
    # out of the watching briefs. It runs BEFORE the edition renders so
    # its why-lines are in the edition, isolated so it can never take
    # the publish down, and fenced twice: an 8-minute wall-clock budget
    # inside (rows left over are picked up next Monday; scores are
    # once-ever, so nothing is lost) and a subprocess timeout outside in
    # case a single HTTP call wedges. Without ANTHROPIC_API_KEY the tool
    # refuses to stub-score and says so; it never freezes empty scores.
    import subprocess as _sp
    try:
        judged = _sp.run([sys.executable,
                          os.path.join(ROOT, "tools", "devolved_triage.py"),
                          "--budget-seconds", "480"],
                         cwd=ROOT, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                         timeout=660)
        lines = [ln for ln in (judged.stdout or b"").decode("utf-8", "replace")
                 .splitlines() if ln.strip()]
        print("devolved judge: {0}".format(lines[0].strip() if lines else "no output"))
        for ln in lines[1:]:
            if re.search(r"\[budget\]|\[gap\]|left unscored|UNSCORED|refuses", ln):
                print("  {0}".format(ln.strip()))
    except _sp.TimeoutExpired:
        print("devolved judge: hit the hard timeout; rows stay unscored for "
              "next week; edition unaffected")
    except Exception as exc:
        print("devolved judge: failed ({0}); edition unaffected".format(exc))

    path = run_weekly.render_edition(week, run_weekly._db_name(week))
    with open(path, "r", encoding="utf-8") as handle:
        markdown = handle.read()

    from src import db
    conn = db.connect(os.path.join(ROOT, "data", run_weekly._db_name(week)))
    number = edition_number(conn, week)
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
        # The Asana reading task is retired with the editorial loop:
        # Christopher creates his own tasks from the monitor and the briefs.
        asana = {}
        print("asana: {0}".format(asana))
        if "error" not in slack:
            conn.execute("INSERT OR REPLACE INTO publish_log "
                         "(week, message_ts, canvas_id, asana_gid, published_at) "
                         "VALUES (?, ?, ?, ?, ?)",
                         (week, slack.get("message_ts"), slack.get("canvas_id"),
                          asana.get("task_gid"),
                          datetime.datetime.now().isoformat(timespec="seconds")))
            conn.commit()
    # What the paid passes actually cost since the last edition. Recorded
    # rather than remembered: Christopher's standing instruction is to be
    # told when API funds are used, and until 2026-08-24 the only source was
    # my recollection of historic rates.
    from src import spend
    try:
        print(spend.line(conn, since=str(week)))
    except Exception as exc:                                # noqa: BLE001
        print("api spend: not available ({0})".format(exc))
    conn.close()

    # The judge evaluation corpus (Christopher, 2026-09-07): read any sample
    # or review file a human has filled in, write this week's ten-item
    # sample, and refresh the agreement report. All three are committed.
    try:
        from src import evalbank
        ev_conn = db.connect(os.path.join(ROOT, "data", run_weekly._db_name(week)))
        explicit, implicit = evalbank.ingest_samples(ev_conn, os.path.join(ROOT, "reviews"))
        sample_path, n_sample = evalbank.write_sample(
            ev_conn, week, os.path.join(ROOT, "reviews", "judge-sample-{0}.md".format(week)))
        evalbank.report(ev_conn, write_to=os.path.join(ROOT, "docs", "judge-eval.md"))
        ev_conn.close()
        print("judge eval: {0} explicit and {1} implicit verdict(s) ingested; sample of {2} -> {3}; docs/judge-eval.md "
              "refreshed".format(explicit, implicit, n_sample,
                                 os.path.relpath(sample_path, ROOT) if sample_path else "none"))
    except Exception as exc:                                # noqa: BLE001
        print("judge eval: skipped ({0})".format(exc))

    # Partner edition: redacted static site, committed alongside the edition.
    import glob
    weeks = sorted(os.path.basename(f)[len("parliamentary-monitor-"):-3]
                   for f in glob.glob(os.path.join(ROOT, "editions", "parliamentary-monitor-*.md")))
    partner_md = partner.redact(markdown, extra_names=scrub_names)
    # The question tables link to a companion page carrying the full text.
    pq_conn = db.connect(os.path.join(ROOT, "data", run_weekly._db_name(week)))
    pq_edition = run_weekly.sections_from_store(
        pq_conn, digest.Edition(week_commencing=week, number=number, mode="normal"))
    # The petitions companion page: petitions are kept out of the report
    # (Christopher, 2026-09-07) and surface here instead.
    from src import intel as _intel
    pet_page = partner.build_petitions_page(
        os.path.join(ROOT, "partner_site"), pq_conn,
        _intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml")))
    # Issue pages (Christopher, 2026-09-07): one page per area, everything the
    # store holds on it, read only.
    from src import issuepages as _issuepages
    try:
        issue_paths = _issuepages.build(os.path.join(ROOT, "partner_site"), pq_conn,
                                        _intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml")))
        print("issue pages: {0} written".format(len(issue_paths)))
    except Exception as exc:                                # noqa: BLE001
        print("issue pages: skipped ({0})".format(exc))
    pq_conn.close()
    site = partner.build_site(os.path.join(ROOT, "partner_site"), week, partner_md, weeks,
                              pq_rows=pq_edition.pq_rows,
                              pq_background=pq_edition.pq_background)
    print("partner site: {0}".format(site))
    print("petitions page: {0}".format(pet_page or "none (no petitions on our ground yet)"))

    # Internal 5CA tracker: regenerated weekly so the placements the team works
    # from are never staler than an edition. Written to docs/, never to
    # partner_site/ -- stance placements are our analysis, not public record.
    import subprocess
    # Refresh the Commons roster before anything that depends on it: a
    # by-election MP is otherwise absent from the vote tracker, and a departed
    # one still counted, until somebody remembers to run the tool by hand.
    for label, argv in (("roster", ["tools/pull_commons_roster.py"]),
                        # Every tracker division must have its voters in the ledger
                        # BEFORE the tracker and the 5CA sheets build. The 5CA reads
                        # placements from mp_events, and a division the title sweep
                        # cannot see ("Health Bill: Report Stage: New Clause 142")
                        # otherwise contributes nothing to anyone's placement; a NEW
                        # one also has no raw payload yet for the page to render.
                        # First run, 2026-09-10: 13 of 23 signed-off divisions.
                        ("tracker ledger", ["tools/ledger_tracker_divisions.py"]),
                        ("vote tracker", ["tools/make_vote_tracker.py"]),
                        ("msp votes", ["tools/make_msp_votes.py"]),
                        # Wales and NI in one call: the tool builds every
                        # nation when it is given no arguments.
                        ("ms/mla votes", ["tools/make_devolved_votes.py"]),
                        ("5ca sheets", ["tools/make_5ca_web.py"]),
                        ("5ca matrix", ["tools/make_5ca_matrix.py"]),
                        ("briefs", ["tools/make_briefs.py"]),
                        ("brief sheets", ["tools/publish_briefs_to_drive.py"])):
        # Each tool prints its own one-line summary; relay it rather than
        # discarding it. A log that is silent on success cannot be used to
        # tell "ran and rebuilt" from "never ran" -- and an unattended run is
        # read only through its log.
        try:
            # argv[1:] IS PASSED. It was not: the loop ran only argv[0]
            # and dropped every flag, so a tool added here with an
            # argument would quietly do something other than what this
            # list says it does.
            done = subprocess.run([sys.executable,
                                   os.path.join(ROOT, *argv[0].split("/"))]
                                  + list(argv[1:]),
                                  check=True, cwd=ROOT, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
            out = (done.stdout or b"").decode("utf-8", "replace").strip().splitlines()
            # Skip library noise: a DeprecationWarning on stderr once masked
            # the Drive step's real result, which is the whole point of the
            # relay (2026-08-16).
            def _noise(line):
                low = line.lower()
                return ("warning:" in low or line.startswith((" ", "\t"))
                        or ".py:" in line.split(" ")[0])
            speaking = [l for l in out if l.strip() and not _noise(l)]
            head = speaking[0].strip() if speaking else "ok (no output)"
            if head.lower().startswith(label.lower() + ":"):
                head = head[len(label) + 1:].strip()
            print("{0}: {1}".format(label, head))
            # Detail lines are mostly tallies and output paths, but the ones
            # naming a caveat (unsigned divisions, missing data) are the whole
            # reason to read the log at all.
            for line in speaking[1:]:
                # The Drive publisher's per-brief lines are outcomes, not
                # tallies: six successful uploads once hid behind a single
                # failure head line (2026-08-31), and an unattended run is
                # read only through its log.
                if re.search(r"\bNOT\b|missing|no recorded|gap|stale|gaps"
                             r"|published|FAILED|adopted|no generated", line):
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
    # DERIVED from the taxonomy, never a literal range: `range(1, 12)`
    # silently stopped at area 11, so area 12 (prostitution and sexual
    # exploitation, added at v1.6) would have had no 5CA sheet and
    # nobody would have been told. The same hardcoded count broke two
    # tests the same day.
    from src import intel as _intel
    all_areas = set(_intel.area_names(
        os.path.join(ROOT, "config", "taxonomy.yaml")))
    made = 0
    for area in sorted(all_areas - excluded):
        try:
            subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_5ca.py"),
                            str(area)], check=True, cwd=ROOT,
                           stdout=subprocess.DEVNULL)
            made += 1
        except Exception as exc:
            print("5ca sheet area {0}: failed ({1})".format(area, exc))
    print("5ca sheets refreshed: {0}".format(made))

    # The devolved sheets, which ran nowhere until 2026-09-04. Their own
    # weeklies refresh them too; here they ride along so a Monday edition
    # never quotes a devolved sheet older than the Westminster ones.
    try:
        done = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "devolved_5ca.py")],
            check=True, cwd=ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        head = (done.stdout or b"").decode("utf-8", "replace").strip()
        print(head.splitlines()[0] if head else "devolved 5CA: no output")
    except Exception as exc:
        print("devolved 5CA: failed ({0}); edition unaffected".format(exc))

    # PRUNE. make_5ca.py writes a DATED sheet per area per run, so data/5ca
    # had reached 109 files and 47MB IN GIT -- the shape of the problem
    # that forced the store out of the repo at 88MB, growing ~11 files a
    # week. tools/prune_5ca.py was written for this and, like the devolved
    # 5CA tools, was wired nowhere. It keeps the newest set, the oldest
    # (the unregenerable baseline) and the last set of each earlier month,
    # and prints every file it removes.
    # A DRY RUN DOES NOT DELETE. NO_PUBLISH already means "this run is a
    # rehearsal": it holds back Slack and Asana. Removing 31MB of tracked
    # sheets is a larger and less obviously reversible act than deploying
    # a site, so a rehearsal reports what it WOULD free and touches
    # nothing -- the ni_classify contract, one directory over.
    rehearsal = os.environ.get("NO_PUBLISH") == "1"
    argv = [sys.executable, os.path.join(ROOT, "tools", "prune_5ca.py")]
    if not rehearsal:
        argv.append("--apply")
    try:
        done = subprocess.run(argv, check=True, cwd=ROOT,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        out = (done.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        freed = [ln for ln in out if "freed" in ln]
        print("5ca prune{0}: {1}".format(
            " (rehearsal, nothing deleted)" if rehearsal else "",
            freed[-1] if freed else "nothing to prune"))
    except Exception as exc:
        print("5ca prune: failed ({0}); edition unaffected".format(exc))

    print("edition: {0}".format(path))
    failures = [s for s in (slack, asana) if "error" in s]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
