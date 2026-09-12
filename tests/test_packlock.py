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

    def test_another_live_process_is_refused_unless_forced(self):
        d = tempfile.mkdtemp()
        json.dump({"pid": os.getppid(), "tool": "other", "since": "now"}, open(os.path.join(d, ".lock"), "w"))
        with self.assertRaises(SystemExit) as caught:
            packlock.acquire(d, "me")
        self.assertIn("held by other", str(caught.exception))
        packlock.acquire(d, "me", force=True)
        self.assertEqual(json.load(open(os.path.join(d, ".lock")))["tool"], "me")


if __name__ == "__main__":
    unittest.main()
