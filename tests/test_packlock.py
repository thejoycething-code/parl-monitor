import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import packlock  # noqa: E402


class LockTests(unittest.TestCase):
    def test_a_live_holder_refuses_and_a_dead_one_is_taken_over(self):
        d = tempfile.mkdtemp()
        packlock.acquire(d, "a")
        self.assertEqual(packlock.held_by(d)["tool"], "a")
        # same process may re-enter
        packlock.acquire(d, "a")
        # a dead pid's lock is stale
        json.dump({"pid": 999999, "tool": "ghost", "since": "x"}, open(os.path.join(d, ".lock"), "w"))
        self.assertIsNone(packlock.held_by(d))
        packlock.acquire(d, "b")
        self.assertEqual(json.load(open(os.path.join(d, ".lock")))["tool"], "b")
        packlock.release(d)
        self.assertFalse(os.path.exists(os.path.join(d, ".lock")))

    def test_a_process_we_cannot_signal_counts_as_alive(self):
        """PID 1 exists and refuses our signal. Reading EPERM as "dead" let the
        lock be stolen from a live holder (17 September 2026)."""
        self.assertTrue(packlock._alive(1))
        self.assertFalse(packlock._alive(999999), "a pid that is really gone")

    def test_another_live_process_is_refused_unless_forced(self):
        d = tempfile.mkdtemp()
        # A REAL live child, not os.getppid(): under a detached parent that is
        # pid 1, which this user cannot signal, so the test passed alone and
        # failed in the suite.
        import subprocess
        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(lambda: (holder.kill(), holder.wait()))
        json.dump({"pid": holder.pid, "tool": "other", "since": "now"}, open(os.path.join(d, ".lock"), "w"))
        with self.assertRaises(SystemExit) as caught:
            packlock.acquire(d, "me")
        self.assertIn("held by other", str(caught.exception))
        packlock.acquire(d, "me", force=True)
        self.assertEqual(json.load(open(os.path.join(d, ".lock")))["tool"], "me")


if __name__ == "__main__":
    unittest.main()
