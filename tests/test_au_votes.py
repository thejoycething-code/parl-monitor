"""The Australian vote tracker and member profiles (src/au_profiles.py,
tools/make_au_votes.py, templates/au-votes.html). Small in-memory stores and
temporary stance files; no network.

The rule under test: a vote's direction is a SIGNED human judgement. With a
reading unsigned the page shows the record and labels nobody; a signed
reading shows its direction. A pair is a pair, with no side. Migration is
never shown."""

import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import au_profiles, au_store, db  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mk = _load("make_au_votes")

MEMBERS = [  # person, name, party, house, electorate, phid, current
    ("101", "Ann Ally", "Liberal Party", "senate", "Tasmania", "AB1", 1),
    ("102", "Oscar Opp", "Australian Greens", "senate", "Victoria", None, 1),
    ("103", "Gus Gone", "Australian Labor Party", "senate", "NSW", "GG1", 0),
    ("201", "Hal House", "Australian Labor Party", "house", "Grayndler", "R36", 1),
]
DIVS = [  # key, chamber, own, areas
    ("senate-2026-09-17-8", "senate", "[3]", "[3]"),
    ("senate-2026-09-16-2", "senate", "[]", "[3]"),        # borrows its bill's area, unread
    ("senate-2026-09-15-1", "senate", "[11]", "[11]"),      # migration only
    ("senate-2026-09-14-1", "senate", "[3, 11]", "[3, 11]"),
    ("house-2026-09-10-1", "house", "[1]", "[1]"),
    ("senate-2026-09-13-1", "senate", "[3]", "[3]"),      # judged 0, unread: off the page
]
JUDGED_ZERO = ("senate-2026-09-13-1", "senate-2026-09-17-8")  # the second is read
VOTES = {
    "senate-2026-09-17-8": {"101": "No", "102": "Aye", "103": "Paired"},
    "senate-2026-09-16-2": {"101": "No", "102": "Aye"},
    "senate-2026-09-15-1": {"101": "Aye", "102": "No"},
    "senate-2026-09-14-1": {"101": "Aye", "102": "Paired"},
    "house-2026-09-10-1": {"201": "Aye"},
    "senate-2026-09-13-1": {"101": "Aye"},
}
STANCE = {
    "divisions": [
        {"key": "senate-2026-09-17-8", "yea": -2, "nay": 2, "why_yea": "WHYAYE-restore",
         "why_nay": "WHYNO-against", "aye_means": "AYEMEANS-x", "draft": True},
        {"key": "house-2026-09-10-1", "placeable": False, "reason": "REASON-y", "draft": True},
    ],
}


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    au_store.ensure_schema(conn)
    for pid, name, party, house, elec, phid, cur in MEMBERS:
        conn.execute("INSERT INTO au_members (person_id, name, party, house, electorate, phid, "
                     "current) VALUES (?,?,?,?,?,?,?)", (pid, name, party, house, elec, phid, cur))
        conn.execute("INSERT INTO au_offices (office_id, person_id, house, party, from_date, "
                     "to_date) VALUES (?,?,?,?, '2022-07-01', ?)",
                     ("o" + pid, pid, house, party, "9999-12-31" if cur else "2026-09-17"))
    party = {m[0]: m[2] for m in MEMBERS}
    for key, ch, own, areas in DIVS:
        date = key.split("-", 1)[1].rsplit("-", 1)[0]
        conn.execute("INSERT INTO au_divisions (division_key, chamber, date, number, "
                     "minor_heading, bill_ids, question, motion, ayes, noes, pairs, own_areas, "
                     "areas, source_url) VALUES (?,?,?,?,?, '[\"s1518\"]', 'The question is', "
                     "'I move </script>', 1, 1, 1, ?, ?, 'https://parlinfo/x')",
                     (key, ch, date, int(key.rsplit("-", 1)[1]), "Heading " + key, own, areas))
        for pid, pos in VOTES[key].items():
            conn.execute("INSERT INTO au_votes (division_key, person_id, position, party) "
                         "VALUES (?,?,?,?)", (key, pid, pos, party[pid]))
    for key in JUDGED_ZERO:
        conn.execute("UPDATE au_divisions SET triage_score=0 WHERE division_key=?", (key,))
    conn.execute("INSERT INTO au_bills (bill_id, title, areas) VALUES ('s1518', 'Sex "
                 "Discrimination Amendment Bill', '[3]')")
    for i, kind in enumerate(("speech", "motion", "notice", "speech")):
        conn.execute("INSERT INTO au_speeches (speech_key, chamber, date, person_id, kind, "
                     "minor_heading, areas, excerpt, url) VALUES (?, 'senate', ?, '101', ?, ?, "
                     "'[3]', 'LONG-EXCERPT', ?)",
                     ("senate/{0}".format(i), "2026-09-0{0}".format(i + 1), kind,
                      "Heading {0}".format(i), "https://www.openaustralia.org.au/{0}".format(i)))
    conn.execute("INSERT INTO au_speeches (speech_key, chamber, date, person_id, kind, "
                 "minor_heading, areas) VALUES ('senate/m', 'senate', '2026-09-09', '101', "
                 "'speech', 'Migration speech', '[11]')")
    conn.commit()
    return conn


def stance_file(signed_keys=()):
    cfg = {sec: [{k: v for k, v in e.items() if not (k == "draft" and e["key"] in signed_keys)}
                 for e in entries] for sec, entries in STANCE.items()}
    fh = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    yaml.safe_dump(cfg, fh)
    fh.close()
    return fh.name


def build(signed_keys=()):
    path = stance_file(signed_keys)
    try:
        return mk.build_data(store(), stance_path=path, today="2026-10-09")
    finally:
        os.unlink(path)


def by_key(data):
    return {d["key"]: d for d in data["divisions"]}


class OurGroundTests(unittest.TestCase):
    def test_only_divisions_on_our_ground_are_listed(self):
        self.assertEqual(set(by_key(build())), {"senate-2026-09-17-8", "senate-2026-09-14-1",
                                                "house-2026-09-10-1"})

    def test_judged_zero_division_is_off_unless_the_stance_file_reads_it(self):
        divs = by_key(build())
        self.assertNotIn("senate-2026-09-13-1", divs)             # scored 0, unread
        self.assertIn("senate-2026-09-17-8", divs)                # scored 0, draft reading
        self.assertIn("senate-2026-09-14-1", divs)                # unscored stays
        self.assertIn("senate-2026-09-17-8", by_key(build(signed_keys=("senate-2026-09-17-8",))))

    def test_migration_hidden(self):
        data = build()
        divs = by_key(data)
        self.assertNotIn("senate-2026-09-15-1", divs)
        self.assertEqual(divs["senate-2026-09-14-1"]["areas"], [3])
        self.assertNotIn("11", data["areas"])
        self.assertNotIn(11, data["five_ca_areas"])
        self.assertNotIn("Migration speech", json.dumps(data["speeches"]))

    def test_pairs_are_pairs_with_no_side(self):
        data = build(signed_keys=("senate-2026-09-17-8",))
        ids = [m["id"] for m in data["members"]]
        d = by_key(data)["senate-2026-09-17-8"]
        self.assertEqual(d["pos"][ids.index("103")], "P")
        self.assertEqual(d["parties"]["Australian Labor Party"], {"Y": 0, "N": 0, "P": 1, "O": 0})
        self.assertNotIn("103", data["placements"])          # a pair places nobody

    def test_members_and_speeches(self):
        data = build()
        m = {x["id"]: x for x in data["members"]}
        self.assertEqual((m["201"]["chamber"], m["201"]["where"], m["201"]["phid"]),
                         ("house", "Grayndler", "R36"))
        self.assertFalse(m["103"]["in_office"])              # former, but voted here
        sp = data["speeches"]["101"]
        self.assertEqual(sp["count"], 4)
        self.assertEqual(sp["kinds"], {"speech": 2, "motion": 1, "notice": 1})
        self.assertEqual(len(sp["latest"]), 3)
        self.assertEqual(sp["latest"][0]["date"], "2026-09-04")
        self.assertNotIn("LONG-EXCERPT", json.dumps(data))
        d = by_key(data)["senate-2026-09-17-8"]
        self.assertEqual(d["bills"][0]["id"], "s1518")


class UnsignedShowsNoDirectionTests(unittest.TestCase):
    def test_no_direction_fields_and_awaiting_sign_off(self):
        data = build()
        for d in data["divisions"]:
            self.assertNotIn("direction", d)
            self.assertEqual(d["reading"], "awaiting sign-off")
        self.assertEqual(data["placements"], {})

    def test_drafted_wording_never_reaches_the_page(self):
        page = mk.render(build())
        for token in ("WHYAYE", "WHYNO", "AYEMEANS", "REASON-y"):
            self.assertNotIn(token, page)
        self.assertNotIn('"direction":', page)
        self.assertIn("Nobody on this page is labelled", page)


class SignedShowsDirectionTests(unittest.TestCase):
    def test_a_signed_reading_carries_its_direction(self):
        data = build(signed_keys=("senate-2026-09-17-8",))
        d = by_key(data)["senate-2026-09-17-8"]
        self.assertEqual(d["reading"], "signed")
        self.assertEqual(d["direction"]["ours"], "Nay")
        self.assertNotIn("direction", by_key(data)["senate-2026-09-14-1"])
        self.assertIn("WHYNO-against", mk.render(data))

    def test_signed_reading_places_members_in_5ca(self):
        data = build(signed_keys=("senate-2026-09-17-8",))
        self.assertEqual(data["placements"]["101"]["3"]["column"], "++")
        self.assertEqual(data["placements"]["102"]["3"]["column"], "--")

    def test_signed_evidence_only_has_no_direction(self):
        data = build(signed_keys=("house-2026-09-10-1",))
        d = by_key(data)["house-2026-09-10-1"]
        self.assertEqual(d["reading"], "signed: evidence only")
        self.assertNotIn("direction", d)


class PageTests(unittest.TestCase):
    def test_render_embeds_data_and_escapes_script_close(self):
        page = mk.render(build())
        self.assertNotIn("/*__DATA__*/", page)
        blob = re.search(r"const DATA = (\{.*?\});\n", page, re.S).group(1)
        self.assertEqual(len(json.loads(blob)["divisions"]), 3)
        self.assertEqual(page.lower().count("</script>"), 1)

    def test_main_writes_the_page_from_a_store_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dbp = os.path.join(tmp, "s.db")
            src = store()
            dst = sqlite3.connect(dbp)
            src.backup(dst)
            dst.close()
            out = os.path.join(tmp, "au-votes.html")
            stance = stance_file()
            try:
                self.assertEqual(mk.main(["--db", dbp, "--out", out, "--stance", stance]), 0)
            finally:
                os.unlink(stance)
            with open(out, encoding="utf-8") as fh:
                self.assertIn("How did your MP or senator vote?", fh.read())

    def test_links(self):
        self.assertIn("bId=s1518", au_profiles.bill_url("s1518"))
        self.assertTrue(au_profiles.phid_url("R36").endswith("MPID=R36"))


class WiringTests(unittest.TestCase):
    def test_weekly_builds_the_page_after_the_5ca_and_commits_it(self):
        with open(os.path.join(ROOT, "jobs", "au-weekly.sh"), encoding="utf-8") as fh:
            script = fh.read()
        self.assertLess(script.index("tools/au_5ca.py --all"), script.index("tools/make_au_votes.py"))
        self.assertLess(script.index("tools/make_au_votes.py"), script.rindex("tools/db_state.py --push"))
        self.assertRegex(script, r"make_au_votes\.py[^\n]*\\\n\s*\|\| echo \"  \[gap\]")
        commit = re.search(r"^# mini_run: commit (.+)$", script, re.M).group(1).split()
        self.assertIn("partner_site", commit)
        self.assertIn("docs", commit)
        with open(os.path.join(ROOT, ".github", "workflows", "au-weekly.yml"), encoding="utf-8") as fh:
            add = next(ln for ln in fh.read().splitlines() if ln.strip().startswith("git add "))
        self.assertEqual({p.rstrip("/") for p in add.split()[2:]} - {"data"}, set(commit))


if __name__ == "__main__":
    unittest.main()
