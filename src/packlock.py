"""One pack, one process (12 September 2026).

Two sessions rendered the same pack the evening of the Second Reading; each
deleted the other's windows and clips, and three hours went on re-cuts. A tool
that writes into a pack takes the pack's lock first and refuses if another live
process holds it. A lock left by a dead process is stale and taken over.
"""

import atexit
import datetime
import json
import os

LOCK = ".lock"


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def acquire(pack_dir, tool, force=False):
    """Take the pack's lock for this process or raise SystemExit naming the holder."""
    path = os.path.join(pack_dir, LOCK)
    if os.path.exists(path):
        try:
            held = json.load(open(path))
        except ValueError:
            held = {}
        if held.get("pid") != os.getpid() and _alive(held.get("pid")) and not force:
            raise SystemExit("%s is held by %s (pid %s) since %s; wait for it, or set PARL_FORCE_LOCK=1 if you are sure it is dead"
                             % (pack_dir, held.get("tool"), held.get("pid"), held.get("since")))
    json.dump({"pid": os.getpid(), "tool": tool, "since": datetime.datetime.now().isoformat(timespec="seconds")},
              open(path, "w"))
    atexit.register(release, pack_dir)
    return path


def release(pack_dir):
    path = os.path.join(pack_dir, LOCK)
    try:
        if json.load(open(path)).get("pid") == os.getpid():
            os.remove(path)
    except (OSError, ValueError):
        pass


def held_by(pack_dir):
    """The live holder's record, or None."""
    path = os.path.join(pack_dir, LOCK)
    try:
        held = json.load(open(path))
    except (OSError, ValueError):
        return None
    return held if _alive(held.get("pid")) else None
