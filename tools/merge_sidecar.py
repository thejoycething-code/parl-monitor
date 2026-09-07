"""Git merge driver for data/parl-monitor.db.json: the release decides.

    git config merge.db-sidecar.driver "python3 tools/merge_sidecar.py %O %A %B"
    (installed idempotently by tools/db_state.py --pull; bound by .gitattributes)

THE FRICTION. Every store publish rewrites the sidecar, so whenever a CI
run commits between a laptop's store push and its git push, the rebase
stops on this one file and a human resolves it -- three times on 6-7
September 2026 alone, each time by hand, each time correctly, each time
one wrong keystroke from pointing the repo at a store that is not there.

THE RULE. The right side is whichever one names the asset that is
ACTUALLY published. GitHub exposes the release asset's sha256 digest
without a download, so this asks, and takes the side that matches.
"Ours" and "theirs" are irrelevant: the newest pointer is not the true
pointer if someone published after it.

FALLBACKS, in order. No digest reachable (offline, no gh, no token): the
side with the later `published_utc`, because a later publish is by
construction the current asset -- the lineage guard in db_state.py
refuses any push that is not. No timestamps either (a sidecar from
before 2026-09-07): exit 1 and leave the conflict for a human, saying
why. A merge driver that guesses is worse than one that stops.

Contract (git): argv = BASE OURS THEIRS; write the result into OURS;
exit 0 resolved, non-zero conflict.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "thejoycething-code/parl-monitor"
TAG = "db-state"
ASSET = "parl-monitor.db"


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def published_digest():
    """sha256 of the asset the release currently holds, or None.

    SIDECAR_DIGEST in the environment overrides the lookup -- for tests,
    and for a human who has just read it from the GitHub page.
    """
    forced = os.environ.get("SIDECAR_DIGEST")
    if forced is not None:
        return forced.replace("sha256:", "").strip() or None
    try:
        out = subprocess.run(
            ["gh", "api", "repos/{0}/releases/tags/{1}".format(REPO, TAG),
             "--jq", '.assets[] | select(.name=="{0}") | .digest'.format(ASSET)],
            capture_output=True, text=True, timeout=60)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().replace("sha256:", "")
    except Exception:
        pass
    return None


def choose(ours, theirs, digest):
    """-> ('ours'|'theirs'|None, reason)."""
    o, t = ours.get("sha256"), theirs.get("sha256")
    if digest:
        if o == digest and t != digest:
            return "ours", "ours names the published asset {0}".format(digest[:12])
        if t == digest and o != digest:
            return "theirs", "theirs names the published asset {0}".format(digest[:12])
        if o == digest and t == digest:
            return "ours", "both sides name the published asset"
        return None, ("NEITHER side names the published asset {0} (ours {1}, "
                      "theirs {2}); the release and the repo have diverged -- "
                      "resolve by hand after reading tools/db_state.py".format(
                          digest[:12], (o or "?")[:12], (t or "?")[:12]))
    ou, tu = ours.get("published_utc"), theirs.get("published_utc")
    if ou and tu:
        if ou > tu:
            return "ours", "no digest reachable; ours published later ({0})".format(ou)
        if tu > ou:
            return "theirs", "no digest reachable; theirs published later ({0})".format(tu)
        return "ours", "no digest reachable; same publish time"
    return None, ("no digest reachable and no published_utc on both sides; "
                  "refusing to guess")


def main(argv):
    if len(argv) != 4:
        print("usage: merge_sidecar.py BASE OURS THEIRS", file=sys.stderr)
        return 2
    _base, ours_path, theirs_path = argv[1], argv[2], argv[3]
    ours, theirs = load(ours_path), load(theirs_path)
    side, reason = choose(ours, theirs, published_digest())
    if side is None:
        print("merge-sidecar: CONFLICT -- {0}".format(reason), file=sys.stderr)
        return 1
    winner = ours if side == "ours" else theirs
    with open(ours_path, "w", encoding="utf-8") as fh:
        json.dump(winner, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("merge-sidecar: took {0} -- {1}".format(side, reason), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
