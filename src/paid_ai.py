"""The paid Claude API is OFF unless one pass's own flag says otherwise.

Chris, 16 October 2026: "ALL model scoring moves off the paid Claude API onto
the free session judge" (tools/session_judge.sh: Claude Code on the Mac Mini,
signed in to the work account, on the plan allowance). The UK weekly went
first (#207, UK_PAID_JUDGE); this module carries the same rule to every other
pass that ever spent: a key in config/secrets.yaml or the environment is NOT
consent to spend. Each pass runs its paid path only when its own flag is set
to exactly "1", and no workflow or job sets one (tests/test_no_paid_api.py).

Two fences:
  1. each call site asks allowed(<pass>) before it reads a key, and leaves
     its items unscored for the free session judge when the answer is no;
  2. the two network transports to the Messages API (src/triage.py and
     src/stance.py, the only ones in the repo) call check_transport(), which
     refuses outright unless at least one paid flag is set in this process.
     A call site that forgot fence 1 fails closed, never spends.
"""

from __future__ import annotations

import os

# pass name (as recorded in api_spend) -> the env var that opts it in.
FLAGS = {
    # The UK weekly (#207): one flag for its three passes, as shipped.
    "triage": "UK_PAID_JUDGE",
    "stance": "UK_PAID_JUDGE",
    "devolved-triage": "UK_PAID_JUDGE",
    # The editions' judges (16 October 2026).
    "de-triage": "DE_TRIAGE_PAID",
    "de-stance": "DE_STANCE_PAID",
    "ca-triage": "CA_TRIAGE_PAID",
    "eu-triage": "EU_TRIAGE_PAID",
    "us-triage": "US_TRIAGE_PAID",
    "ie-triage": "IE_TRIAGE_PAID",
    "au-triage": "AU_TRIAGE_PAID",
    "prov-triage": "PROV_TRIAGE_PAID",
    # Hand-run tools and drafting passes.
    "brief-narrative": "BRIEF_NARRATIVE_PAID",   # tools/make_briefs.py, tools/de_briefs.py
    "speech-pick": "SPEECH_PICK_PAID",           # tools/pick_speeches.py
    "debate-report": "DEBATE_REPORT_PAID",       # tools/debate_report.py
    "debate-pack": "DEBATE_PACK_PAID",           # tools/debate_pack.py direction reads
    "judge-rescore": "JUDGE_RESCORE_PAID",       # tools/judge_eval.py rescore --spend
    "stance-rescore": "STANCE_RESCORE_PAID",     # tools/score_stance.py, rescore_blind_speeches.py
}


class PaidAIOff(RuntimeError):
    """Raised when a paid call is attempted with no pass opted in."""


def flag(pass_name):
    return FLAGS[pass_name]


def allowed(pass_name, env=None):
    """True only when this pass's flag is exactly "1"."""
    env = os.environ if env is None else env
    return (env.get(FLAGS[pass_name]) or "").strip() == "1"


def off_line(pass_name, n=None, what="item(s)"):
    """The log line a pass prints when it leaves work for the session judge."""
    lead = "{0}: ".format(pass_name)
    if n is not None:
        lead += "{0} {1} left for the free session judge; ".format(n, what)
    return lead + "the paid API is off ({0}=1 opts in; a key alone never does).".format(
        FLAGS[pass_name])


def check_transport(env=None):
    """Refuse a request to the Messages API unless some pass opted in."""
    env = os.environ if env is None else env
    if not any((env.get(v) or "").strip() == "1" for v in set(FLAGS.values())):
        raise PaidAIOff("paid Claude API refused: no pass is opted in ({0}); the free "
                        "session judge scores instead".format(", ".join(sorted(set(FLAGS.values())))))
