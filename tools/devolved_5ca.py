"""Five Columns Analysis sheets for Holyrood, the Senedd and the Assembly.

    python3 tools/devolved_5ca.py                  # every nation
    python3 tools/devolved_5ca.py --nation wales   # one

Christopher, 2026-09-04: "Wire them." tools/sp_5ca.py, sd_5ca.py and
ni_5ca.py were finished and correct and ran NOWHERE -- no workflow, no
run_monday. Scotland's assisted-dying sheet places all 129 MSPs (30 in
++, 33 in --, 66 neutral) from recorded votes with human-confirmed
meaning lines, and it was only ever as fresh as the last time somebody
remembered to type the command. That is the lesson sp-weekly already
learned about scoring: a placement that exists only where a human ran a
tool is not published state.

WHICH AREAS. Every non-excluded area is attempted, and a sheet is KEPT
only where at least one member is actually placed at ++, +, - or --.
A sheet on which nobody is placed carries no campaign information -- it
is a member list with an empty grid -- so it is deleted and the run says
why. Today that yields Scotland 5 (abortion, assisted dying, gender
medicine, sex-based rights, parental rights), Wales 1 (assisted dying,
19 Members placed) and NI 2 (abortion 74, sex-based rights 80).

TWO DIFFERENT SIGN-OFF SURFACES, and they are easy to confuse. The
TRACKER pages are gated by `signed_off` in config/senedd_votes.yaml and
nia_votes.yaml, and neither Welsh nor NI division is signed -- which is
why ms-votes.html and mla-votes.html still say nothing about what a vote
MEANT. These sheets are placed by config/{sp,sd,ni}_stance.yaml instead,
where a human has already confirmed 27, 5 and 4 acts respectively. A
nation can therefore have 5CA placements while its tracker stays silent,
and that is not an inconsistency: the stance file says what an aye meant
on one named act, the votes file publishes a verdict to every member
page.

STABLE FILENAMES, deliberately unlike Westminster's. make_5ca.py writes
a DATED sheet per area per run, and data/5ca has reached 109 files and
47MB in git as a result -- the shape of the problem that forced the
store out of the repo at 88MB. These overwrite one file per nation per
area, so wiring three more legislatures into a weekly job adds a fixed
33 files rather than 33 a week.

NEVER POSTED. Same contract as the tools it drives: the CSVs land in
data/5ca and go nowhere near Slack, the digest or the ledger.
"""

from __future__ import annotations

import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import intel

SHEETS = os.path.join(ROOT, "data", "5ca")

NATIONS = {
    "scotland": ("sp_5ca.py", "sp", "config/sp_stance.yaml", "Holyrood"),
    "wales": ("sd_5ca.py", "sd", "config/sd_stance.yaml", "the Senedd"),
    "ni": ("ni_5ca.py", "ni", "config/ni_stance.yaml", "the Assembly"),
}

# The columns that constitute a PLACEMENT. "0" is not one: a member sitting
# at zero has been looked at and not placed, which is the state every
# member is in before any verdict is signed.
PLACED = {"++", "+", "-", "--"}


def excluded_areas():
    import yaml
    path = os.path.join(ROOT, "config", "stance_overrides.yaml")
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    return {int(a) for a in (cfg.get("excluded_from_5ca") or [])}


def places_anyone(path):
    """Does this sheet place a single MEMBER either way?

    Two traps, both paid for on 2026-09-04. The sheet ends with a
    "Totals - 90 decision-makers" row whose empty columns hold the
    STRING "0", so a naive truthiness test read every empty sheet as
    full and kept ten NI sheets on which nobody was placed at all. And
    the neutral column is a placement column in the CSV but not a
    placement: a member sitting at 0 has been looked at and not placed,
    which is the state every member is in before a verdict is signed.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
    except OSError:
        return False
    if not rows:
        return False
    header = [c.strip() for c in rows[0]]
    cols = [i for i, name in enumerate(header) if name in PLACED]
    for row in rows[1:]:
        if not row or row[0].strip().lower().startswith("totals"):
            continue
        for i in cols:
            if i < len(row) and row[i].strip() not in ("", "0"):
                return True
    return False


def build(nation, areas, names, log=print):
    """-> (kept, [(area, reason)]) for one nation."""
    tool, prefix, stance_path, _label = NATIONS[nation]
    kept, skipped = [], []
    for area in areas:
        label = names.get(area, "area-{0}".format(area))
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        out = os.path.join(SHEETS, "{0}-5ca-{1}.csv".format(prefix, slug))
        done = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", tool),
             "--area", str(area), out],
            cwd=ROOT, capture_output=True, text=True)
        if done.returncode:
            # A tool that refuses (an excluded area, a missing stance file)
            # is not a crash, and must not take the other areas down.
            first = (done.stdout or done.stderr or "").strip().splitlines()
            skipped.append((area, (first[0] if first else "no output")[:90]))
            continue
        if places_anyone(out):
            kept.append((area, label))
        else:
            os.path.exists(out) and os.remove(out)
            skipped.append((area, "no confirmed act places anyone"))
    return kept, skipped


def main():
    nations = list(NATIONS)
    if "--nation" in sys.argv:
        nations = [sys.argv[sys.argv.index("--nation") + 1]]
    for nation in nations:
        if nation not in NATIONS:
            print("unknown nation: {0} ({1})".format(
                nation, "|".join(NATIONS)))
            return 1
    os.makedirs(SHEETS, exist_ok=True)
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    areas = sorted(set(names) - excluded_areas())

    summary, detail = [], []
    for nation in nations:
        kept, skipped = build(nation, areas, names)
        summary.append("{0} {1} sheet(s)".format(nation, len(kept)))
        for area, label in kept:
            detail.append("   {0}: area {1} {2} -> data/5ca/{3}-5ca-*.csv"
                          .format(nation, area, label, NATIONS[nation][1]))
        if not kept:
            # NEVER SILENT: a nation with no sheets is the normal state
            # before its verdicts are signed, and the run must say so
            # rather than look like it did nothing.
            detail.append(
                "{0}: no sheet published -- no confirmed act places anyone "
                "in any area yet. Sign a division off in config/{1}_stance"
                ".yaml and this fills itself.".format(
                    nation, NATIONS[nation][1]))
    print("devolved 5CA: " + "; ".join(summary))
    for line in detail:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
