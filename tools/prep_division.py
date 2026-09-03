"""Prepare a new division for Christopher's sign-off, ready to paste.

    python3 tools/prep_division.py --date 2026-09-11
    python3 tools/prep_division.py --date 2026-09-11 --our-side no
    python3 tools/prep_division.py --rehearse      # known-answer self-test

Built for the TIA Second Reading (11 September 2026) and every division
after it. The day's risk is not fetching data -- it is assigning a
MEANING to a question nobody read. Two measured facts shape this tool:

1. The Commons API does NOT carry the question. Checked across 40
   archived division payloads: FriendlyDescription and FriendlyTitle are
   null in every one, and there is no motionNotes field (the Lords API
   has one; that asymmetry is what let the Lords inversion happen and
   what lets it be caught there). So the question must be read by a
   human from Hansard or the Votes and Proceedings; this tool prints
   both links and refuses to guess.
2. Verdicts can be anchor-tested from the store BEFORE anything ships.
   Three members have measured, unambiguous records on assisted suicide
   (both 2024 and 2025 readings, from the archived name lists):

       Danny Kruger      voted No   both times  -> must render GOOD
       Kim Leadbeater    voted Aye  both times  -> must render BAD
       Lauren Edwards    voted Aye  both times  -> must render BAD
                                        (and sponsors the 2026 Bill)

   With a proposed our_side, the tool computes what each anchor WOULD
   render and refuses to print a sign-off message unless all three land
   as above. An inverted meaning cannot survive that test.

Nothing here writes config or the store: it reads, checks, and prints.
The signature stays Christopher's.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import FetchError, HttpClient
from src.ingest import divisions as div_ingest

# member_id -> (name, verdict that MUST render).
#
# The expectation is fixed to the PERSON, not derived from our_side --
# the first version of this tool computed the expected verdict from the
# same our_side as the actual one, which made the whole test a tautology
# that passed an inverted verdict without a murmur (caught by feeding it
# our_side=aye on the known Third Reading, 2026-09-03). These three are
# consistent partisans on assisted suicide across both 2024 and 2025
# readings, verified from the archived name lists, so whatever a given
# question's polarity, the tracker must place them like this:
ANCHORS = {
    4858: ("Danny Kruger", "GOOD"),      # votes our way, every time
    4923: ("Kim Leadbeater", "BAD"),     # the 2025 Bill's sponsor
    5298: ("Lauren Edwards", "BAD"),     # the 2026 Bill's sponsor
}
MIN_ANCHORS = 2   # fewer than two voting anchors = untestable, so refuse

HANSARD = "https://hansard.parliament.uk/commons/{0}"
VANDP = ("https://commonsbusiness.parliament.uk/document/"
         "search?date={0}&type=VotesAndProceedings")
DIVISION_PAGE = "https://votes.parliament.uk/Votes/Commons/Division/{0}"


def verdict_for(lobby, our_side):
    """What the tracker would render for this lobby under our_side."""
    if lobby not in ("aye", "no"):
        return "NO VOTE"
    return "GOOD" if lobby == our_side else "BAD"


def anchor_test(voters, our_side):
    """(passed, rows). Each anchor must render its FIXED expected colour.

    An anchor who did not vote cannot testify; if fewer than MIN_ANCHORS
    voted, the test is untestable and fails closed rather than passing
    on silence.
    """
    by_id = {v.member_id: v.vote for v in voters}
    rows, failures, voted = [], 0, 0
    for mid, (name, expected) in ANCHORS.items():
        lobby = by_id.get(mid)
        rendered = verdict_for(lobby, our_side)
        if rendered == "NO VOTE":
            ok = None
        else:
            voted += 1
            ok = rendered == expected
            if not ok:
                failures += 1
        rows.append({"name": name, "lobby": lobby or "-",
                     "rendered": rendered, "expected": expected, "ok": ok})
    passed = failures == 0 and voted >= MIN_ANCHORS
    return passed, rows


def yaml_block(div, issue, stage, our_side, meanings):
    return "\n".join([
        "  - id: {0}".format(div.id),
        "    issue: {0}".format(issue),
        "    stage: {0}".format(stage),
        "    stage_group: {0}".format(stage),
        "    landmark: true",
        "    signed_off: false          # flips only on Christopher's word",
        '    our_side: "{0}"'.format(our_side),
        "    short: {0}".format(stage),
        '    context: ""',
        "    meaning_aye: >-",
        "      {0}".format(meanings["aye"]),
        "    meaning_no: >-",
        "      {0}".format(meanings["no"]),
    ])


DEFAULT_MEANINGS = {
    "aye": ("Supported the Bill continuing to its next stage (in "
            "principle, in favour of legalising assisted suicide for "
            "terminally ill adults in England and Wales)."),
    "no": "Voted to stop the new Bill at its first Commons hurdle.",
}


def pick(divs, stage, division_id=None):
    """The division a verdict is being drafted FOR.

    The rehearsal (20 June 2025) proved why this exists: that day carried
    SIX divisions -- Third Reading plus five amendments -- and each
    amendment has its own our_side, so anchor-testing the whole day under
    one flag is meaningless. Choose by explicit id, else by the division
    whose title names the stage; if that is ambiguous, refuse to choose.
    """
    if division_id:
        return [d for d in divs if str(d.id) == str(division_id)]
    key = stage.lower().replace(" ", "")
    return [d for d in divs
            if key in (d.title or "").lower().replace(" ", "")]


def run(date, our_side=None, issue="assisted-suicide-2026",
        stage="Second Reading", division_id=None, client=None, out=print):
    client = client or HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    try:
        divs = div_ingest.fetch_commons_divisions(client, date)
    except FetchError as exc:
        out("FETCH FAILED: {0}".format(exc.cause))
        out("The list endpoint lags after a big vote. Retry; do NOT build "
            "from press reports.")
        return 1
    if not divs:
        out("No Commons divisions recorded on {0}.".format(date))
        out("If the Bill was talked out or passed on the nod, nothing is "
            "signed: update the issue status line and the board's next "
            "key date instead (see docs/runbook-2026-09-11.md).")
        return 0
    out("{0} Commons division(s) on {1}:".format(len(divs), date))
    out("")
    for d in divs:
        out("  id {0} (No. {1})  {2}".format(d.id, d.number, d.title))
        out("      Ayes {0} / Noes {1}   {2}".format(
            d.aye_count, d.no_count, DIVISION_PAGE.format(d.id)))
    out("")
    out("READ THE QUESTION, from Hansard or the Votes and Proceedings --")
    out("the Commons API carries no motion text (measured: null in every")
    out("archived payload), so nothing here can tell you what was put:")
    out("  " + HANSARD.format(date))
    out("  " + VANDP.format(date))
    out("A reasoned amendment INVERTS the polarity (its question is to")
    out("decline a second reading). A closure motion is a separate")
    out("division and a separate judgement.")
    if not our_side:
        out("")
        out("Re-run with --our-side aye|no once the question is read, to")
        out("anchor-test the verdict and print the sign-off message.")
        return 0
    out("")
    targets = pick(divs, stage, division_id)
    if not targets:
        out("No division on {0} matches stage \"{1}\" -- name the one you "
            "mean with --division <id>.".format(date, stage))
        return 1
    if len(targets) > 1:
        out("{0} divisions match \"{1}\": {2}. Name one with --division "
            "<id>; each question needs its own verdict.".format(
                len(targets), stage, ", ".join(str(d.id) for d in targets)))
        return 1
    for d in targets:
        try:
            _, voters = div_ingest.fetch_commons_breakdown(client, d.id)
        except FetchError as exc:
            out("  id {0}: name lists not published yet ({1}); retry."
                .format(d.id, exc.cause))
            continue
        passed, rows = anchor_test(voters, our_side)
        out("ANCHOR TEST -- id {0}, our_side={1}, {2} voters"
            .format(d.id, our_side, len(voters)))
        for r in rows:
            mark = "PASS" if r["ok"] else ("----" if r["ok"] is None
                                           else "FAIL")
            out("  {0} {1:16} voted {2:4} -> renders {3:8} (must be {4})"
                .format(mark, r["name"], r["lobby"], r["rendered"],
                        r["expected"]))
        voting = sum(1 for r in rows if r["ok"] is not None)
        if voting < MIN_ANCHORS:
            out("")
            out("Only {0} anchor(s) voted: the verdict cannot be tested, so "
                "nothing is drafted. Christopher signs on the question "
                "text alone, or waits for a division the anchors are in."
                .format(voting))
            continue
        if not passed:
            out("")
            out("REFUSING to draft a sign-off for id {0}: an anchor landed "
                "on the wrong colour.".format(d.id))
            out("Either our_side is inverted for THIS question, or this "
                "division is not the one you think it is. Re-read the "
                "question before anything ships.")
            continue
        out("")
        if stage != "Second Reading":
            out("NOTE: the drafted meaning lines below are SECOND READING "
                "wording. This is {0} -- rewrite them from this "
                "question before signing.".format(stage))
        out("--- config/vote_tracker.yaml, append under divisions: ---")
        out(yaml_block(d, issue, stage, our_side, DEFAULT_MEANINGS))
        out("--- and on issue {0}: drop `upcoming: true` ---".format(issue))
        out("")
        result = ("passed" if (d.aye_count or 0) > (d.no_count or 0)
                  else "rejected")
        out("--- sign-off message ---")
        out("The {0} division is in: {1}-{2} ({3} by {4}). Question as "
            "recorded: \"<paste from Hansard>\".".format(
                stage, d.aye_count, d.no_count, result,
                abs((d.aye_count or 0) - (d.no_count or 0))))
        out("Drafted verdict: our side {0}.".format(our_side.upper()))
        out("  Aye means: {0}".format(DEFAULT_MEANINGS["aye"]))
        out("  No means:  {0}".format(DEFAULT_MEANINGS["no"]))
        out("Anchors check out: " + "; ".join(
            "{0} {1}".format(r["name"].split()[-1], r["rendered"])
            for r in rows) + ".")
        out("Say \"sign off\" and it ships to all 650 pages.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-09-11")
    ap.add_argument("--our-side", choices=("aye", "no"))
    ap.add_argument("--issue", default="assisted-suicide-2026")
    ap.add_argument("--stage", default="Second Reading")
    ap.add_argument("--division", help="division id, when the stage title "
                                       "is ambiguous")
    ap.add_argument("--rehearse", action="store_true",
                    help="run against the known 20 June 2025 Third Reading")
    args = ap.parse_args()
    if args.rehearse:
        print("REHEARSAL against a known answer: 20 June 2025, Third "
              "Reading, our_side=no.")
        print("Expect division 2071, Kruger GOOD, Leadbeater BAD, "
              "Edwards BAD.")
        print("")
        return run("2025-06-20", our_side="no", stage="Third Reading",
                   issue="assisted-suicide")
    return run(args.date, our_side=args.our_side, issue=args.issue,
               stage=args.stage, division_id=args.division)


if __name__ == "__main__":
    sys.exit(main())
