"""tools/store_sizes.py: per-table sizes, read-only, on a throwaway store."""

import contextlib
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import store_sizes


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class StoreSizesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "store.db")
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE fr_votes (division_key TEXT, member TEXT, position TEXT, "
                     "PRIMARY KEY (division_key, member))")
        conn.execute("CREATE INDEX fr_votes_member ON fr_votes (member)")
        conn.execute("CREATE TABLE fr_members (key TEXT PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, title TEXT)")
        conn.executemany("INSERT INTO fr_votes VALUES (?,?,?)",
                         [("d{0}".format(d), "m{0}".format(m), "pour")
                          for d in range(200) for m in range(50)])
        conn.executemany("INSERT INTO fr_members VALUES (?,?)",
                         [("m{0}".format(m), "Member {0}".format(m)) for m in range(50)])
        conn.execute("INSERT INTO items VALUES ('a', 'one item')")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_largest_first_with_indexes_counted_and_rows(self):
        stats = store_sizes.measure(self.path)
        names = [t["name"] for t in stats["tables"]]
        self.assertEqual(names[0], "fr_votes")
        votes = stats["tables"][0]
        self.assertEqual(votes["rows"], 10000)
        self.assertGreater(votes["index_bytes"], 0)          # the PK and member indexes
        self.assertEqual(votes["bytes"], votes["table_bytes"] + votes["index_bytes"])
        self.assertEqual(stats["page_size"] * stats["pages"], stats["file_bytes"])
        self.assertEqual(sum(t["bytes"] for t in stats["tables"]), stats["file_bytes"])

    def test_groups_sum_by_prefix(self):
        stats = store_sizes.measure(self.path)
        got = {g["group"]: g for g in store_sizes.groups(stats["tables"])}
        self.assertEqual(got["fr"]["tables"], 2)
        self.assertEqual(got["items"]["tables"], 1)
        self.assertEqual(store_sizes.groups(stats["tables"])[0]["group"], "fr")

    def test_never_changes_the_store(self):
        before = sha(self.path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(store_sizes.main(["--db", self.path, "--top", "1"]), 0)
            self.assertEqual(store_sizes.main(["--db", self.path, "--groups", "--json"]), 0)
        self.assertEqual(sha(self.path), before)
        self.assertFalse(os.path.exists(self.path + "-journal"))
        text = out.getvalue()
        self.assertIn("fr_votes", text)
        self.assertIn("(3 more)", text)          # fr_members, items, the schema
        self.assertIn('"groups"', text)

    def test_missing_store_is_a_plain_failure(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(store_sizes.main(["--db", os.path.join(self.tmp.name, "nope.db")]), 1)
        self.assertIn("no store at", out.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "nope.db")))

    def test_json_is_parseable(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            store_sizes.main(["--db", self.path, "--json"])
        data = json.loads(out.getvalue())
        self.assertEqual(data["tables"][0]["name"], "fr_votes")


if __name__ == "__main__":
    unittest.main()
