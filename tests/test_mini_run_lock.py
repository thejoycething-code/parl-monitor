"""tools/mini_run.sh, step 1 (the lock), run for real: several waiters in a
temp dir with short sleeps, under /bin/bash (3.2 on macOS). No network, no
store, no git: the block is cut out of the wrapper and run with a stub `fail`.

10 October 2026: at-weekly arrived at 02:00 UTC and waited 7,200 s while
hr-weekly, latam-courts-backfill, be-weekly and us-division-watch took the
lock ahead of it; the failure named whoever held the lock at the end. Now the
lock is first in, first out, and the failure names the queue.
"""

import os
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASH = "/bin/bash" if os.path.exists("/bin/bash") else shutil.which("bash")


def lock_block():
    with open(os.path.join(ROOT, "tools", "mini_run.sh"), encoding="utf-8") as h:
        src = h.read()
    start = src.index("# 1. The lock")
    end = src.index("# 1b. Say so on GitHub")
    return src[start:end]


# The harness: the wrapper's lock block, then a "job" that notes it got the
# lock, holds it for HOLD seconds and lets it go, as cleanup() does.
HARNESS = """set -u
JOB="$1"
RUNNER="$T"
LOCK="$RUNNER/locks/state"
LOCK_WAIT="${LOCK_WAIT:-30}"
TICKET=
fail() { echo "  FAILED at $STAGE: $*"; [ -n "$TICKET" ] && rm -f "$TICKET"; exit 1; }
%s
echo "$JOB" >> "$RUNNER/order"
sleep "${HOLD:-0.3}"
[ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ] && rm -rf "$LOCK"
echo "DONE $JOB"
"""


class LockQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        # Named mini_run.sh: a ticket counts as live only while its PID runs mini_run.
        self.script = os.path.join(self.bin, "mini_run.sh")
        with open(self.script, "w", encoding="utf-8") as h:
            h.write(HARNESS % lock_block())
        self.queue = os.path.join(self.tmp, "locks", "queue")
        self.lock = os.path.join(self.tmp, "locks", "state")
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
            p.stdout.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start(self, job, hold=0.3, wait=30, argv=None, poll=0.1):
        env = {**os.environ, "T": self.tmp, "HOLD": str(hold), "LOCK_WAIT": str(wait),
               "LOCK_POLL": str(poll)}
        p = subprocess.Popen(argv or [BASH, self.script, job], env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
        self.procs.append(p)
        return p

    def until(self, cond, what, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return
            time.sleep(0.02)
        self.fail("timed out waiting for " + what)

    def tickets(self):
        return sorted(os.listdir(self.queue)) if os.path.isdir(self.queue) else []

    def holder(self):
        try:
            with open(os.path.join(self.lock, "job")) as h:
                return h.read().strip()
        except OSError:
            return ""

    def order(self):
        try:
            with open(os.path.join(self.tmp, "order")) as h:
                return h.read().split()
        except OSError:
            return []

    def finish(self, p):
        out, _ = p.communicate(timeout=60)
        return p.returncode, out

    def test_arrival_order_is_honoured(self):
        first = self.start("hr-weekly", hold=1.0)
        self.until(lambda: self.holder() == "hr-weekly", "the first job to take the lock")
        jobs = ["at-weekly", "latam-courts-backfill", "be-weekly", "us-division-watch"]
        procs = []
        for n, job in enumerate(jobs, 1):
            # The first waiter looks slowly and the later ones quickly, as on
            # 10 October: a bare mkdir poll lets the quick ones in first.
            procs.append(self.start(job, hold=0.2, poll=1.5 if n == 1 else 0.05))
            self.until(lambda n=n: len(self.tickets()) == n, job + "'s ticket")
        for p in [first] + procs:
            rc, out = self.finish(p)
            self.assertEqual(rc, 0, out)
        self.assertEqual(self.order(), ["hr-weekly"] + jobs)
        self.assertEqual(self.tickets(), [])  # every holder removed its ticket
        self.assertFalse(os.path.exists(self.lock))

    def test_a_dead_waiters_ticket_is_skipped(self):
        os.makedirs(self.queue)
        dead = subprocess.Popen(["true"])
        dead.wait()
        # Older than anything real: a waiter that died, and one whose PID now
        # belongs to something that is not mini_run (a reused PID).
        with open(os.path.join(self.queue, "%017d-%d" % (1, dead.pid)), "w") as h:
            h.write("crashed-weekly\n")
        other = subprocess.Popen(["sleep", "30"])
        try:
            with open(os.path.join(self.queue, "%017d-%d" % (2, other.pid)), "w") as h:
                h.write("reused-pid\n")
            rc, out = self.finish(self.start("at-weekly", hold=0.1, wait=5))
        finally:
            other.kill()
            other.wait()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.order(), ["at-weekly"])
        self.assertIn("dropped the ticket of pid %d (crashed-weekly)" % dead.pid, out)
        self.assertIn("dropped the ticket of pid %d (reused-pid)" % other.pid, out)
        self.assertEqual(self.tickets(), [])

    def test_a_stale_lock_is_taken_over(self):
        dead = subprocess.Popen(["true"])
        dead.wait()
        os.makedirs(self.lock)
        with open(os.path.join(self.lock, "pid"), "w") as h:
            h.write("%d\n" % dead.pid)
        with open(os.path.join(self.lock, "job"), "w") as h:
            h.write("crashed-weekly\n")
        rc, out = self.finish(self.start("be-weekly", hold=0.1, wait=5))
        self.assertEqual(rc, 0, out)
        self.assertIn("stale lock from pid %d (crashed-weekly); taking it" % dead.pid, out)
        self.assertEqual(self.order(), ["be-weekly"])

    def test_the_failure_names_the_queue_and_the_holder(self):
        holder = self.start("hr-weekly", hold=4)
        self.until(lambda: self.holder() == "hr-weekly", "the holder")
        ahead = []
        for n, job in enumerate(["latam-courts-backfill", "be-weekly"], 1):
            ahead.append(self.start(job, hold=0.1))
            self.until(lambda n=n: len(self.tickets()) == n, job + "'s ticket")
        late = self.start("at-weekly", wait=1)
        rc, out = self.finish(late)
        self.assertEqual(rc, 1, out)
        self.assertIn("queued for the lock; ahead of us: latam-courts-backfill, be-weekly; "
                      "holder: hr-weekly", out)
        self.assertRegex(out, r"FAILED at lock: waited [12]s; ahead of us when we gave up: "
                              r"latam-courts-backfill, be-weekly; holder: hr-weekly\n")
        self.assertEqual(len(self.tickets()), 2)  # its own ticket went with it
        for p in [holder] + ahead:
            self.assertEqual(self.finish(p)[0], 0)
        self.assertEqual(self.order(), ["hr-weekly", "latam-courts-backfill", "be-weekly"])

    def test_a_re_exec_keeps_its_place_and_never_queues(self):
        # Step 2's re-exec: the same PID already holds the lock when the new
        # wrapper starts. A later waiter queues meanwhile; the re-exec must go
        # first, without a ticket of its own.
        reexec = ('mkdir -p "$T/locks"; mkdir "$T/locks/state"; echo $$ > "$T/locks/state/pid"; '
                  'echo us-weekly > "$T/locks/state/job"; '
                  'while [ ! -f "$T/go" ]; do sleep 0.05; done; exec "$0" "$1" us-weekly')
        first = self.start("us-weekly", hold=0.1, argv=[BASH, "-c", reexec, BASH, self.script])
        self.until(lambda: self.holder() == "us-weekly", "the re-exec's lock")
        later = self.start("ie-weekly", hold=0.1)
        self.until(lambda: len(self.tickets()) == 1, "the later job's ticket")
        open(os.path.join(self.tmp, "go"), "w").close()
        rc, out = self.finish(first)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("queued", out)
        self.assertEqual(self.finish(later)[0], 0)
        self.assertEqual(self.order(), ["us-weekly", "ie-weekly"])

    def test_the_wrapper_keeps_its_contract(self):
        with open(os.path.join(ROOT, "tools", "mini_run.sh"), encoding="utf-8") as h:
            src = h.read()
        self.assertIn('LOCK_WAIT="${LOCK_WAIT:-7200}"', src)
        self.assertIn("export JOB_TIMEOUT", src)
        self.assertIn('MINI_RUN_FRESH=1 exec bash "$CLONE/tools/mini_run.sh" "$JOB"', src)
        self.assertNotIn("EPOCHREALTIME", src)  # bash 5 only; macOS ships 3.2
        out = subprocess.run([BASH, "-n", os.path.join(ROOT, "tools", "mini_run.sh")],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
