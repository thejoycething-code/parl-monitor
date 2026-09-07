"""Git merge driver for data/raw.json: per folder, the later publish wins.

    git config merge.raw-sidecar.driver "python3 tools/merge_raw_sidecar.py %O %A %B"
    (installed idempotently by tools/raw_state.py --pull; bound by .gitattributes)

Each folder's entry names the asset that was published for it, and every
publish of a folder is the UNION of what was there before (raw_state.py
merges before it uploads), so for any one folder the later published_utc
is by construction the current asset. The merge is therefore mechanical:
take the union of folder keys, and for a key on both sides the later
entry. No network, no guessing, no human.

Contract (git): argv = BASE OURS THEIRS; write the result into OURS;
exit 0 resolved, non-zero conflict.
"""

from __future__ import annotations

import json
import sys


def load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle) or {}
    except (OSError, ValueError):
        return {}


def merge(ours, theirs):
    out = dict(theirs)
    out.update(ours)
    folders = {}
    for side in (theirs.get("folders") or {}, ours.get("folders") or {}):
        for k, v in side.items():
            cur = folders.get(k)
            if cur is None or (v.get("published_utc") or "") > (cur.get("published_utc") or ""):
                folders[k] = v
    out["folders"] = folders
    return out


def main(argv):
    if len(argv) != 4:
        print("usage: merge_raw_sidecar.py BASE OURS THEIRS", file=sys.stderr)
        return 2
    _base, ours_path, theirs_path = argv[1:]
    result = merge(load(ours_path), load(theirs_path))
    with open(ours_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
