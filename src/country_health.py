"""The new countries in the daily health summary (11 October 2026).

tools/health_summary.py lists every Mini run of the last day and every
overdue source. With some 30 country jobs, each with an edition, vote briefs,
an agenda, a chamber step, courts and the rest inside it, that list grew to
dozens of lines a morning. This folds the new countries into ONE compact
section per region (Europe, Latam) plus one line for the jobs they share,
problems first:

  * failed jobs (the last Mini run failed, with the stage) and unfinished ones;
  * stale jobs: no good Mini run within the job's cadence plus a grace (from
    its launchd plist, or tools/coverage.py PIPELINES where the job has a
    heartbeat there: Guatemala and Mexico are fortnightly);
  * jobs with no Mini run yet (installed later, or still on GitHub);
  * step gaps in each job's LAST run, by step: edition, vote briefs, judge,
    agenda, chamber, courts, backfill, profiles, briefs, drive, alerts. The
    collectors' own source gaps (recorded in each store's gaps table, often
    dozens a run, such as the Italian Senate's 403s) are one count per country;
  * editions older than their cadence (editions/<cc>-monitor-<date>.md);
  * the overdue sources tools/coverage.py finds for these countries (their
    pipelines and their tables), moved here out of the general list.

When a region is clean it is one line. Nothing here reads the network or
writes anything; it works on what health_summary already read.
"""

from __future__ import annotations

import datetime
import os
import plistlib
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EUROPE = ("at", "be", "ch", "es", "fr", "hr", "hu", "it", "nl", "pl", "pt", "sk")
LATAM = ("ar", "bo", "br", "cl", "co", "do", "ec", "gt", "hn", "mx", "pa", "pe", "sv", "uy")
# "latam" is the monthly Latam monitor (Venezuela and Nicaragua): its job is
# latam-monthly, its edition latam-monitor-<date>.md, its tables ve_ and nic_.
REGIONS = (
    ("Europe", EUROPE, ("sk-docs-backfill", "sk-positions-backfill", "hu-karzat-backfill")),
    ("Latam", LATAM + ("latam",), ("latam-courts-backfill",)),
)
SHARED = ("vote-briefs-daily", "editions-session-judge")
TABLE_PREFIX = {"ve": "latam", "nic": "latam"}
SHARED_TABLES = ("country_agenda",)
# Countries with their own edition file; the Latam monitor's countries have none.
EDITION_CCS = ("at", "be", "ch", "es", "fr", "hr", "hu", "it", "nl", "pl", "pt", "sk",
               "ar", "br", "mx", "latam")

# Step of a "[gap]" line, first match wins. Lowercased substrings of the lines
# the jobs print (jobs/*.sh, tools/chamber_step.sh) and the tools they call.
STEPS = (
    ("drive", ("drive",)),
    ("vote briefs", ("vote brief",)),
    ("judge", ("judge", "5ca", "stance digest", "rewrite failed", "rescore")),
    ("agenda", ("agenda", "week ahead", "week-ahead")),
    ("chamber", ("-chamber", "chamber step", "questions step", "debates step",
                 "questions skipped")),
    ("courts", ("courts",)),
    ("edition", ("edition", "-monitor:")),
    ("profiles", ("member-profiles", "party-history")),
    ("briefs", ("country-briefs",)),
    ("alerts", ("latam-alerts",)),
    ("backfill", ("backfill", "diario", "bo-questions", "bo members", "-ocr")),
)
SOURCE = "source"


def job_of(cc):
    return "latam-monthly" if cc == "latam" else "{0}-weekly".format(cc)


def step_of(line, job=""):
    if job.endswith("-backfill"):
        return "backfill"
    low = line.lower()
    if "fetch failed" in low:          # a collector's request: the source's gap
        return SOURCE
    for name, needles in STEPS:
        if any(n in low for n in needles):
            return name
    return SOURCE


# --- cadence -----------------------------------------------------------------

def plist_cadence(job, root=ROOT):
    """Days between the job's launchd slots: 1 daily, 7 weekly, 31 monthly, the
    longest gap between listed weekdays otherwise; None without a plist."""
    path = os.path.join(root, "ops", "launchd", "net.citizengo.parlmonitor.{0}.plist".format(job))
    try:
        with open(path, "rb") as handle:
            data = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    slots = data.get("StartCalendarInterval")
    if slots is None:
        return None
    slots = slots if isinstance(slots, list) else [slots]
    if any("Day" in s for s in slots):
        return 31
    days = sorted({int(s["Weekday"]) % 7 for s in slots if "Weekday" in s})
    if not days or any("Weekday" not in s for s in slots):
        return 1
    gaps = [(days[(i + 1) % len(days)] - d) % 7 or 7 for i, d in enumerate(days)]
    return max(gaps)


# Mexico's Mini job is only the clock: it dispatches the GitHub run, whose
# script (jobs/mx-collect.sh) names the heartbeat.
CLOCKS = {"mx-weekly": "mx-collect"}


def workflow_of(job, root=ROOT):
    """The GITHUB_WORKFLOW name the job stamps its heartbeat with, or None."""
    try:
        with open(os.path.join(root, "jobs", CLOCKS.get(job, job) + ".sh"), encoding="utf-8") as handle:
            m = re.search(r"GITHUB_WORKFLOW:-([^}\"]+)", handle.read())
    except OSError:
        return None
    return m.group(1).strip() if m else None


def grace(days):
    if days <= 1:
        return 1
    if days >= 28:
        return 7
    return max(2, days // 4)


def cadence(job, pipelines=None, root=ROOT):
    """(days, grace) for a job: tools/coverage.py PIPELINES when the job's
    workflow is there (it knows the fortnightly ones), else the plist."""
    pipelines = pipelines or {}
    days = None
    wf = workflow_of(job, root)
    if wf in pipelines:
        days = pipelines[wf][0]
    if days is None:
        days = plist_cadence(job, root)
    if days is None:
        return None
    return days, grace(days)


# --- what the logs say -------------------------------------------------------

def job_states(runs, jobs, now, running_job=None, pipelines=None, root=ROOT):
    """{job: state} for each job named. runs: health_summary.read_mini_full."""
    by_job = {}
    for job, started, outcome, gaps in runs or ():
        by_job.setdefault(job, []).append((started, outcome, gaps))
    out = {}
    for job in jobs:
        mine = sorted(by_job.get(job, []), key=lambda r: r[0])
        st = {"job": job, "last": None, "outcome": None, "gaps": [], "last_ok": None,
              "status": "none", "cadence": cadence(job, pipelines, root)}
        if mine:
            started, outcome, gaps = mine[-1]
            st.update(last=started, outcome=outcome, gaps=list(gaps))
            oks = [s for s, o, _g in mine if o == "ok"]
            st["last_ok"] = oks[-1] if oks else None
            if outcome.startswith("FAILED"):
                st["status"] = "failed"
            elif outcome == "running":
                st["status"] = "running" if job == running_job else "unfinished"
            else:
                st["status"] = "ok"
            cad = st["cadence"]
            if cad and st["status"] in ("ok", "failed", "unfinished") and not job.endswith("-backfill"):
                # Since the last good run, or, when none is in the log, since
                # the first run it holds: a job that failed on its first
                # night is failed, not yet stale.
                ref = st["last_ok"] or mine[0][0]
                if (now - ref).total_seconds() > (cad[0] + cad[1]) * 86400:
                    st["stale"] = True
        out[job] = st
    return out


def edition_ages(today, root=ROOT, ccs=EDITION_CCS):
    """{cc: (newest edition date, age in days)} from editions/; missing ones absent."""
    newest = {}
    folder = os.path.join(root, "editions")
    try:
        names = os.listdir(folder)
    except OSError:
        return {}
    pat = re.compile(r"^([a-z]+)-monitor-(\d{4}-\d\d-\d\d)\.md$")
    for name in names:
        m = pat.match(name)
        if not m or m.group(1) not in ccs:
            continue
        cc, day = m.group(1), m.group(2)
        if day > newest.get(cc, ""):
            newest[cc] = day
    return {cc: (d, (today - datetime.date.fromisoformat(d)).days) for cc, d in newest.items()}


# --- overdue sources from tools/coverage.py ------------------------------------

def workflow_ccs(root=ROOT):
    """{workflow name: cc} for the new countries' jobs."""
    out = {}
    for _region, ccs, _bf in REGIONS:
        for cc in ccs:
            wf = workflow_of(job_of(cc), root)
            if wf:
                out[wf] = cc
    return out


def cc_of_key(key, wf_ccs):
    """The new country (or "shared") a coverage problem key belongs to, else None.

    Keys: "pipeline:<workflow>", "feed:<table>", "empty:<table>",
    "lost:<workflow>:<table>" (tools/coverage.check)."""
    kind, _, rest = key.partition(":")
    if kind in ("pipeline", "lost"):
        name = rest.split(":")[0]
        if name in wf_ccs:
            return wf_ccs[name]
        if kind == "pipeline":
            return None
        rest = rest.split(":", 1)[1] if ":" in rest else ""
    table = rest
    if table in SHARED_TABLES:
        return "shared"
    prefix = table.split("_", 1)[0]
    if prefix in TABLE_PREFIX:
        return TABLE_PREFIX[prefix]
    if prefix in EUROPE or prefix in LATAM:
        return prefix
    return None


def split_overdue(found, wf_ccs):
    """(country items {cc: [(text, is_new)]}, the rest [(text, is_new)]).

    found: [(key, age, text, is_new)] from health_summary.overdue_found."""
    mine, rest = {}, []
    for key, _age, text, is_new in found or ():
        cc = cc_of_key(key, wf_ccs)
        if cc:
            mine.setdefault(cc, []).append((text, is_new))
        else:
            rest.append((text, is_new))
    return mine, rest


# --- the section ---------------------------------------------------------------

def _when(ts, fmt):
    return fmt(ts) if ts else "never"


def _ago(now, ts):
    if ts is None:
        return "never"
    days = (now - ts).total_seconds() / 86400
    return "{0:.0f} days ago".format(days) if days >= 2 else "{0:.0f}h ago".format(days * 24)


def _cc(job):
    return job.split("-")[0] if job.endswith("-weekly") else job


def _gap_counts(gaps, job):
    counts = {}
    for line in gaps:
        step = step_of(line, job)
        counts[step] = counts.get(step, 0) + 1
    return counts


def region_lines(name, ccs, backfills, states, editions, overdue, now, when):
    """One headline line, then problem lines (each starting "   ◦ ")."""
    jobs = [job_of(cc) for cc in ccs] + list(backfills)
    failed, unfinished, stale, never, stepgaps, srcgaps = [], [], [], [], [], []
    for job in (jobs if states is not None else ()):
        st = states.get(job) or {"status": "none", "gaps": []}
        backfill = job.endswith("-backfill")
        if st["status"] == "none":
            if not backfill:
                never.append(job)
            continue
        if st["status"] == "failed":
            failed.append("{0} at {1}: {2} (last ok {3}{4})".format(
                job, when(st["last"]), st["outcome"][10:][:110], _ago(now, st["last_ok"]),
                ", stale" if st.get("stale") else ""))
            st = dict(st, stale=False)
        elif st["status"] == "unfinished":
            unfinished.append("{0} at {1}".format(job, when(st["last"])))
        if st.get("stale"):
            stale.append("{0}: last ok {1} (every {2} days)".format(
                job, _ago(now, st["last_ok"]), st["cadence"][0]))
        counts = _gap_counts(st["gaps"], job)
        src = counts.pop(SOURCE, 0)
        if counts:
            stepgaps.append("{0} {1}".format(_cc(job), ", ".join(
                "{0} {1}".format(k, v) for k, v in sorted(counts.items()))))
        if src:
            srcgaps.append("{0} {1}".format(_cc(job), src))
    old_ed = []
    for cc in ccs:
        if cc not in EDITION_CCS:
            continue
        cad = ((states or {}).get(job_of(cc)) or {}).get("cadence") or (7, 2)
        got = editions.get(cc)
        if got is None:
            old_ed.append("{0} none yet".format(cc))
        elif got[1] > cad[0] + cad[1]:
            old_ed.append("{0} {1} days".format(cc, got[1]))
    n_ed = sum(1 for cc in ccs if cc in EDITION_CCS)
    late = [(cc, t, n) for cc in ccs for t, n in overdue.get(cc, ())]
    n_jobs = len([j for j in jobs if not j.endswith("-backfill")])
    bits = []
    if failed:
        bits.append("{0} failed".format(len(failed)))
    if unfinished:
        bits.append("{0} unfinished".format(len(unfinished)))
    if stale:
        bits.append("{0} stale".format(len(stale)))
    if never:
        bits.append("{0} not run on the Mini yet".format(len(never)))
    if stepgaps:
        bits.append("{0} with step gaps".format(len(stepgaps)))
    if late:
        bits.append("{0} overdue source(s)".format(len(late)))
    ed = "editions {0}/{1} current".format(n_ed - len(old_ed), n_ed) if n_ed else ""
    if states is None:
        bits.insert(0, "runs unknown")
    if not bits and not old_ed:
        head = "• *{0}*: all {1} jobs ok, {2}, no step gaps{3}".format(
            name, n_jobs, ed or "no editions",
            "; source gaps recorded: " + ", ".join(srcgaps) if srcgaps else "")
        return [head]
    lines = ["• *{0}*: {1} jobs: {2}{3}".format(
        name, n_jobs, ", ".join(bits) or "all ran", "; " + ed if ed else "")]
    sub = "   ◦ "
    lines += [sub + ":x: " + f for f in failed]
    lines += [sub + ":warning: never finished: " + u for u in unfinished]
    lines += [sub + ":warning: stale: " + s for s in stale]
    for cc, text, is_new in sorted(late, key=lambda x: not x[2]):
        lines.append(sub + "{0}overdue: {1}".format("*NEW* " if is_new else "", text))
    if stepgaps:
        lines.append(sub + "step gaps in the last run: " + "; ".join(stepgaps))
    if old_ed:
        lines.append(sub + "editions behind: " + ", ".join(old_ed))
    if never:
        lines.append(sub + "no Mini run yet: " + ", ".join(never))
    if srcgaps:
        lines.append(sub + "source gaps recorded (gaps table): " + ", ".join(srcgaps))
    return lines


def shared_line(states, overdue, now, when):
    parts, problems = [], []
    for job in (SHARED if states is not None else ()):
        st = states.get(job) or {"status": "none", "gaps": []}
        if st["status"] == "none":
            parts.append("{0} not run on the Mini yet".format(job))
            continue
        counts = _gap_counts(st["gaps"], job)
        gaps = ", ".join("{0} {1}".format(k, v) for k, v in sorted(counts.items()))
        word = {"ok": "ok", "failed": ":x: failed", "running": "running now",
                "unfinished": ":warning: never finished"}[st["status"]]
        if st.get("stale"):
            word += ", :warning: stale (last ok {0})".format(_ago(now, st["last_ok"]))
        parts.append("{0} {1} {2}{3}".format(job, word, when(st["last"]),
                                             " (gaps: {0})".format(gaps) if gaps else ""))
        if st["status"] == "failed":
            problems.append("   ◦ :x: {0}: {1}".format(job, st["outcome"][10:][:140]))
    for text, is_new in overdue.get("shared", ()):
        problems.append("   ◦ {0}overdue: {1}".format("*NEW* " if is_new else "", text))
    return (["• *Shared*: " + "; ".join(parts)] if parts else []) + problems


def all_jobs():
    """Every job this section reports on."""
    jobs = list(SHARED)
    for _name, ccs, backfills in REGIONS:
        jobs += [job_of(cc) for cc in ccs] + list(backfills)
    return jobs


def section(runs, found, now, when, running_job=None, pipelines=None, root=ROOT):
    """(lines of the "Country editions" section, the overdue items left for the
    general list). runs: read_mini_full (None when there are no logs); found:
    overdue_found (None when the store is unreadable)."""
    wf_ccs = workflow_ccs(root)
    mine, rest = split_overdue(found, wf_ccs)
    jobs = all_jobs()
    out = ["\n*Country editions (new countries)*"]
    if runs is None:
        out.append("• no Mini logs found, so the country jobs are unknown")
        states = None
    else:
        states = job_states(runs, jobs, now, running_job, pipelines, root)
    editions = edition_ages(now.date(), root)
    for name, ccs, backfills in REGIONS:
        out += region_lines(name, ccs, backfills, states, editions, mine, now, when)
    out += shared_line(states, mine, now, when)
    if found is None:
        out.append("• the store could not be read, so these countries' sources are unchecked")
    return out, (None if found is None else rest)
