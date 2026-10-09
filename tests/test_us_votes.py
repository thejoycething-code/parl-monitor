"""The US vote tracker and member profiles (src/us_profiles.py,
tools/make_us_votes.py, templates/us-votes.html). Small in-memory stores and
temporary stance files; no network.

The rule under test: a vote's direction is a SIGNED human judgement. With a
reading unsigned the page shows the record and labels nobody; a signed
reading shows its direction."""

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

from src import db, us_profiles, us_store  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mk = _load("make_us_votes")

MEMBERS = [  # bioguide, name, party, state, district, chamber, as_of
    ("A1", "Ally", "R", "TX", "1", "house", "2026-09-16"),
    ("O1", "Opp", "D", "CA", "2", "house", "2026-09-16"),
    ("G1", "Gone", "R", "FL", "4", "house", "2025-06-01"),
    ("S1", "Senator", "R", "OK", None, "senate", "2026-09-16"),
    ("DL", "Delegate", "D", "XX", "AL", "house", "2026-08-01"),
]
DIVS = [  # key, date, bill, question, own_areas, areas, text
    ("house-119-1-26", "2025-01-23", "119/hr/21", "On Motion to Recommit", "[1]", "[1]", None),
    ("house-119-1-27", "2025-01-23", "119/hr/21", "On Passage", "[1]", "[1]", None),
    # Borrows its area from an omnibus and nobody reads it: not on our ground.
    ("house-119-1-90", "2025-03-11", "119/hr/1968", "On Agreeing to the Amendment", "[]", "[1]",
     "A </script> amendment"),
    ("house-119-2-1", "2026-09-16", None, "Quorum", "[]", "[]", None),
    # Migration is matched and stored but never shown (HIDDEN_AREAS).
    ("house-119-1-170", "2025-06-12", "119/hr/2056", "On Passage", "[11]", "[11]", None),
    ("house-119-1-171", "2025-06-12", "119/hr/2057", "On Passage", "[1, 11]", "[1, 11]", None),
    ("senate-119-1-11", "2025-01-22", "119/s/6", "On Cloture on the Motion to Proceed", "[1]",
     "[1]", "Motion to Proceed to S. 6"),
]
VOTES = {
    "house-119-1-26": {"A1": "Nay", "O1": "Yea", "G1": "Nay"},
    "house-119-1-27": {"A1": "Yea", "O1": "Nay", "G1": "Not Voting", "DL": "Present"},
    "house-119-1-90": {"A1": "Yea", "O1": "Nay"},
    "house-119-2-1": {"A1": "Yea", "O1": "Yea"},
    "house-119-1-170": {"A1": "Yea", "O1": "Nay"},
    "house-119-1-171": {"A1": "Yea", "O1": "Nay"},          # Gone has left; latest House roll
    "senate-119-1-11": {"S1": "Yea"},
}
STANCE = {
    "divisions": [
        {"key": "house-119-1-26", "placeable": False, "reason": "MTR", "draft": True},
        {"key": "house-119-1-27", "yea": 2, "nay": -2, "why_yea": "WHYYEA-born-alive",
         "why_nay": "WHYNAY-against", "aye_means": "AYEMEANS-passing", "draft": True},
        {"key": "senate-119-1-11", "yea": 2, "nay": -2, "why_yea": "cloture yes",
         "why_nay": "cloture no", "draft": True},
    ],
    "bills": [
        {"key": "119/hr/21", "sponsored": 2, "cosponsored": 1, "why_sponsored": "WHYSPONSOR",
         "why_cosponsored": "WHYCOSPONSOR", "draft": True},
    ],
}


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    us_store.ensure_schema(conn)
    for bio, name, party, state, district, chamber, as_of in MEMBERS:
        conn.execute("INSERT INTO us_members (bioguide, name, party, state, district, chamber, as_of) "
                     "VALUES (?,?,?,?,?,?,?)", (bio, name, party, state, district, chamber, as_of))
    for key, date, bill, q, own, areas, text in DIVS:
        chamber, cong, sess, roll = key.split("-")
        conn.execute("INSERT INTO us_divisions (division_key, chamber, congress, session, roll, date, "
                     "bill_key, question, result, yeas, nays, own_areas, areas, amendment_text) "
                     "VALUES (?,?,?,?,?,?,?,?, 'Passed', 1, 1, ?, ?, ?)",
                     (key, chamber, int(cong), int(sess), int(roll), date, bill, q, own, areas, text))
        for bio, pos in VOTES[key].items():
            party = dict((m[0], m[2]) for m in MEMBERS)[bio]
            conn.execute("INSERT INTO us_votes VALUES (?,?,?,?,?)", (key, bio, pos, party, "TX"))
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, sponsor, "
                 "introduced, areas) VALUES ('119/hr/21', 119, 'hr', 21, 'Born-Alive', 'A1', "
                 "'2025-01-03', '[1]')")
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, sponsor, "
                 "introduced, areas) VALUES ('119/hr/99', 119, 'hr', 99, 'Post Office naming', "
                 "'A1', '2025-01-03', '[]')")
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, sponsor, "
                 "introduced, areas, triage_score) VALUES ('119/hr/98', 119, 'hr', 98, "
                 "'Judged not ours', 'A1', '2025-01-03', '[7]', 0)")
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, sponsor, "
                 "introduced, areas) VALUES ('119/hr/2056', 119, 'hr', 2056, 'Migration only', "
                 "'O1', '2025-01-03', '[11]')")
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, sponsor, "
                 "introduced, areas) VALUES ('119/hr/2057', 119, 'hr', 2057, 'Mixed', "
                 "'O1', '2025-01-03', '[7, 11]')")
    conn.execute("INSERT INTO us_cosponsors VALUES ('119/hr/21', 'O1', '2025-01-05', '2025-02-01', 0)")
    conn.execute("INSERT INTO us_cosponsors VALUES ('119/hr/21', 'S1', '2025-01-05', NULL, 1)")
    for i in range(5):
        conn.execute("INSERT INTO us_record_speeches (speech_key, granule_id, package_id, date, "
                     "chamber, title, bioguide, areas, excerpt, url) VALUES (?,?,?,?, 'house', ?, "
                     "'A1', '[1]', 'LONG-EXCERPT-TEXT', ?)",
                     ("g{0}/A1".format(i), "g{0}".format(i), "p", "2026-0{0}-01".format(i + 1),
                      "Speech {0}".format(i), "https://www.govinfo.gov/g{0}".format(i)))
    conn.execute("INSERT INTO us_record_speeches (speech_key, granule_id, package_id, date, chamber, "
                 "title, bioguide, areas) VALUES ('x/A1', 'x', 'p', '2026-09-01', 'house', "
                 "'Off our ground', 'A1', '[]')")
    conn.commit()
    return conn


def stance_file(signed_keys=()):
    """A temporary stance file; entries whose key is in signed_keys lose draft."""
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
        keys = set(by_key(build()))
        self.assertEqual(keys, {"house-119-1-26", "house-119-1-27", "senate-119-1-11",
                                "house-119-1-171"})

    def test_hidden_areas_never_shown(self):
        data = build()
        divs = by_key(data)
        self.assertNotIn("house-119-1-170", divs)            # migration only: drops out
        self.assertEqual(divs["house-119-1-171"]["areas"], [1])
        bills = {b["key"]: b for b in data["bills"]}
        self.assertNotIn("119/hr/2056", bills)
        self.assertEqual(bills["119/hr/2057"]["areas"], [7])
        self.assertNotIn("11", data["areas"])

    def test_positions_party_splits_and_members(self):
        data = build()
        ids = [m["id"] for m in data["members"]]
        d = by_key(data)["house-119-1-27"]
        self.assertEqual(d["pos"][ids.index("A1")], "Y")
        self.assertEqual(d["pos"][ids.index("O1")], "N")
        self.assertEqual(d["pos"][ids.index("G1")], "V")
        self.assertEqual(d["pos"][ids.index("DL")], "P")
        self.assertEqual(d["pos"][ids.index("S1")], ".")
        self.assertEqual(d["parties"]["R"], {"Y": 1, "N": 0, "P": 0, "V": 1, "O": 0})
        self.assertEqual(d["parties"]["D"]["N"], 1)
        m = {x["id"]: x for x in data["members"]}
        self.assertTrue(m["A1"]["in_office"])
        self.assertFalse(m["G1"]["in_office"])            # voted here, then left
        self.assertTrue(m["DL"]["in_office"])             # delegate seen within 120 days
        self.assertEqual(m["S1"]["chamber"], "senate")

    def test_bills_withdrawals_and_speeches(self):
        data = build()
        bills = data["bills"]
        a1 = [(bills[i]["key"], kind) for i, kind, _d, _w in data["member_bills"]["A1"]]
        self.assertEqual(a1, [("119/hr/21", "S")])   # off-ground and judged-0 bills are not listed
        o1 = data["member_bills"]["O1"]
        self.assertEqual((o1[0][1], o1[0][3]), ("C", "2025-02-01"))
        sp = data["speeches"]["A1"]
        self.assertEqual(sp["count"], 5)                  # off-ground speech not counted
        self.assertEqual(len(sp["latest"]), 3)
        self.assertEqual(sp["latest"][0]["date"], "2026-05-01")
        self.assertNotIn("excerpt", json.dumps(sp))
        self.assertNotIn("LONG-EXCERPT-TEXT", json.dumps(data))


class UnsignedShowsNoDirectionTests(unittest.TestCase):
    def test_no_direction_fields_and_awaiting_sign_off(self):
        data = build()
        for d in data["divisions"]:
            self.assertNotIn("direction", d)
            self.assertEqual(d["reading"], "awaiting sign-off")
        for b in data["bills"]:
            self.assertNotIn("direction", b)
        self.assertEqual(data["placements"], {})
        self.assertEqual(data["readings"]["divisions_signed"], 0)

    def test_drafted_wording_never_reaches_the_page(self):
        page = mk.render(build())
        for token in ("WHYYEA", "WHYNAY", "AYEMEANS", "WHYSPONSOR", "WHYCOSPONSOR",
                      "cloture yes"):
            self.assertNotIn(token, page)
        self.assertIn("awaiting sign-off", page)
        self.assertNotIn('"direction":', page)


class SignedShowsDirectionTests(unittest.TestCase):
    def test_a_signed_reading_carries_its_direction(self):
        data = build(signed_keys=("house-119-1-27",))
        d = by_key(data)["house-119-1-27"]
        self.assertEqual(d["reading"], "signed")
        self.assertEqual(d["direction"]["ours"], "Yea")
        self.assertEqual((d["direction"]["yea"], d["direction"]["nay"]), (2, -2))
        self.assertEqual(d["direction"]["why_yea"], "WHYYEA-born-alive")
        # The others stay unsigned and carry nothing.
        self.assertNotIn("direction", by_key(data)["senate-119-1-11"])
        self.assertEqual(data["readings"]["divisions_signed"], 1)
        page = mk.render(data)
        self.assertIn("WHYYEA-born-alive", page)
        self.assertNotIn("cloture yes", page)

    def test_signed_reading_places_members_in_5ca(self):
        data = build(signed_keys=("house-119-1-27",))
        self.assertEqual(data["placements"]["A1"]["1"]["column"], "++")
        self.assertEqual(data["placements"]["O1"]["1"]["column"], "--")
        self.assertNotIn("S1", data["placements"])        # his only reading is a draft

    def test_signed_evidence_only_has_no_direction(self):
        data = build(signed_keys=("house-119-1-26",))
        d = by_key(data)["house-119-1-26"]
        self.assertEqual(d["reading"], "signed: evidence only")
        self.assertNotIn("direction", d)

    def test_signed_bill_reading(self):
        data = build(signed_keys=("119/hr/21",))
        b = next(b for b in data["bills"] if b["key"] == "119/hr/21")
        self.assertEqual(b["direction"]["sponsored"], 2)
        self.assertEqual(data["placements"]["A1"]["1"]["column"], "++")


class PageTests(unittest.TestCase):
    def test_render_embeds_data_and_escapes_script_close(self):
        page = mk.render(build())
        self.assertNotIn("/*__DATA__*/", page)
        blob = re.search(r"const DATA = (\{.*?\});\n", page, re.S).group(1)
        self.assertEqual(len(json.loads(blob)["divisions"]), 4)
        self.assertEqual(page.lower().count("</script>"), 1)

    def test_main_writes_the_page_from_a_store_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dbp = os.path.join(tmp, "s.db")
            src = store()
            dst = sqlite3.connect(dbp)
            src.backup(dst)
            dst.close()
            out = os.path.join(tmp, "us-votes.html")
            stance = stance_file()
            try:
                self.assertEqual(mk.main(["--db", dbp, "--out", out, "--stance", stance]), 0)
            finally:
                os.unlink(stance)
            with open(out, encoding="utf-8") as fh:
                self.assertIn("How did your member of Congress vote?", fh.read())

    def test_bill_and_division_links(self):
        self.assertEqual(us_profiles.bill_label("119/hjres/7"), "H.J.Res. 7")
        self.assertEqual(us_profiles.bill_url("119/hr/21"),
                         "https://www.congress.gov/bill/119th-congress/house-bill/21")
        self.assertEqual(us_profiles.division_url(
            {"chamber": "senate", "congress": 119, "session": 1, "roll": 11, "date": "2025-01-22"}),
            "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1191/vote_119_1_00011.htm")
        self.assertEqual(us_profiles.division_url(
            {"chamber": "house", "congress": 119, "session": 1, "roll": 27, "date": "2025-01-23"}),
            "https://clerk.house.gov/Votes/202527")


class WiringTests(unittest.TestCase):
    def test_weekly_builds_the_page_after_the_5ca_and_commits_it(self):
        with open(os.path.join(ROOT, "jobs", "us-weekly.sh"), encoding="utf-8") as fh:
            script = fh.read()
        self.assertLess(script.index("tools/us_5ca.py --all"), script.index("tools/make_us_votes.py"))
        self.assertLess(script.index("tools/make_us_votes.py"), script.rindex("tools/db_state.py --push"))
        commit = re.search(r"^# mini_run: commit (.+)$", script, re.M).group(1).split()
        self.assertIn("partner_site", commit)
        with open(os.path.join(ROOT, ".github", "workflows", "us-weekly.yml"), encoding="utf-8") as fh:
            add = next(ln for ln in fh.read().splitlines() if ln.strip().startswith("git add "))
        self.assertEqual({p.rstrip("/") for p in add.split()[2:]} - {"data"}, set(commit))


if __name__ == "__main__":
    unittest.main()
