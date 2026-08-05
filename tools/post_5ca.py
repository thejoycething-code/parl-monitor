"""Push a 5CA briefing for one issue area to Slack as a canvas.

    python3 tools/post_5ca.py <area-number> [--dry-run]

The CSV is 649 rows, which is a spreadsheet, not a Slack post. This posts
the decision-relevant cut instead: the shape of the House, the members whose
position is not on record (the target list a campaigner actually works), the
marginal placements, and the conflicts worth a human look. The full sheet
stays in data/5ca/ for the Campaigns Brief.

Non-voting members are separated out rather than presented as persuadable:
Sinn Fein members do not take their seats, the Speaker does not vote, and on
England-and-Wales bills Scottish and Northern Irish members frequently
abstain by convention. Calling them "no recorded position" without saying so
would send a campaigner after votes that were never available.

--dry-run prints the canvas instead of posting.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, publish, stance

ABSTENTIONIST = ("Sinn F", "Speaker")
DEVOLVED_PARTIES = ("Scottish National Party", "Social Democratic & Labour Party",
                    "Democratic Unionist Party", "Traditional Unionist Voice",
                    "Alliance", "Ulster Unionist Party", "Plaid Cymru")


def party_of(decision_maker):
    m = re.search(r"\(([^,]+),", decision_maker)
    return m.group(1) if m else ""


def bullets(rows, note=None):
    out = []
    for r in rows:
        line = "- {0}".format(r["decision_maker"])
        if note:
            line += " {0}".format(note(r))
        out.append(line)
    return "\n".join(out) if out else "- none"


def main():
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        print("usage: python3 tools/post_5ca.py <area-number> [--dry-run]")
        sys.exit(1)
    area = int(sys.argv[1])
    dry = "--dry-run" in sys.argv

    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    label = names.get(area, "area {0}".format(area))
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    if area in (cfg.get("excluded_from_5ca") or []):
        print("{0} is collated only, not a 5CA area".format(label))
        sys.exit(1)
    rows = stance.suggest_rows(conn, area, full_roster=True, overrides_cfg=cfg)
    conn.close()

    by = {}
    for r in rows:
        by.setdefault(r["column"], []).append(r)
    counts = {c: len(by.get(c, [])) for c in stance.COLUMNS}

    zeros = by.get("0", [])
    non_voting = [r for r in zeros if any(a in party_of(r["decision_maker"])
                                         for a in ABSTENTIONIST)]
    devolved = [r for r in zeros if r not in non_voting
                and party_of(r["decision_maker"]) in DEVOLVED_PARTIES]
    unknown = [r for r in zeros if r not in non_voting and r not in devolved]
    marginal = by.get("+", []) + by.get("-", [])
    conflicts = [r for r in rows if r["conflict"]]

    canvas = """*{label} — Five Column Analysis, working draft*

Generated from the parliamentary monitor's evidence ledger: {ev} of 649 sitting MPs have recorded evidence on this area, drawn from division votes, speeches, motions and questions since January 2020. Placements are *suggestions* from that evidence, strongest first (a recorded vote outranks a speech, which outranks a motion, which outranks a question). A campaigner confirms or overrides them; the Target column is deliberately left blank.

*The shape of the House*

| Column | Members |
|---|---|
| ++ strong ally | {pp} |
| + leans our way | {p} |
| 0 no position on record | {z} |
| - leans against | {m} |
| -- strong opponent | {mm} |

*Target list: no position on record ({n_unknown})*

These are the members worth working. Nothing in six years of votes, speeches, motions or questions places them either way on this issue.

{unknown}

*Not persuadable, excluded from the list above*

{non_voting_block}

{devolved_block}

*Marginal placements ({n_marginal})*

Evidence points one way but weakly. Worth a look before treating them as settled.

{marginal}

*Conflicting evidence ({n_conflicts})*

Members with directional evidence on both sides. The tool flags rather than averages: it will not quietly cancel out a vote against a speech.

*Caveats worth carrying into the room*

- Whipped votes measure the party line, not conviction. Free votes are the gold signal, and they are labelled as such in the full sheet's evidence column.
- Placements come from evidence, not from the member's own words about themselves. Read the Comments column before quoting anyone.
- The full 649-row sheet, with dated and linked evidence per member, is at `data/5ca/` in the monitor repo and pastes straight into the Campaigns Brief 5CA tab.
"""

    canvas = canvas.format(
        label=label, ev=sum(1 for r in rows if r["n_events"]),
        pp=counts.get("++", 0), p=counts.get("+", 0), z=counts.get("0", 0),
        m=counts.get("-", 0), mm=counts.get("--", 0),
        n_unknown=len(unknown), unknown=bullets(unknown),
        non_voting_block=("*Abstentionist or non-voting ({0}):* {1}".format(
            len(non_voting), ", ".join(r["decision_maker"].split(" (")[0] for r in non_voting))
            if non_voting else "*Abstentionist or non-voting:* none"),
        devolved_block=("*Devolved-seat members who commonly abstain on England-and-Wales "
                        "bills ({0}):* {1}".format(
                            len(devolved),
                            ", ".join(r["decision_maker"].split(" (")[0] for r in devolved))
                        if devolved else ""),
        n_marginal=len(marginal), marginal=bullets(marginal),
        n_conflicts=len(conflicts))

    summary = ("*5CA briefing: {0}* — {1} of 649 MPs placed from the evidence ledger. "
               "{2} strong allies, {3} strong opponents, {4} with no position on record "
               "({5} of them genuinely persuadable once abstentionist and devolved-seat "
               "members are set aside). Working draft: placements are evidence-based "
               "suggestions, not decisions.").format(
                   label, sum(1 for r in rows if r["n_events"]),
                   counts.get("++", 0), counts.get("--", 0), counts.get("0", 0), len(unknown))

    if dry:
        print(summary + "\n\n" + "-" * 60 + "\n" + canvas)
        return
    result = publish.slack_publish_canvas(
        publish.load_secrets(),
        "5CA working draft - {0}".format(label), canvas, summary)
    print(result)


if __name__ == "__main__":
    main()
