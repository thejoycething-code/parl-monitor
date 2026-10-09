"""The Oireachtas vote tracker and member profiles (src/ie_profiles.py,
tools/make_ie_votes.py, templates/ie-votes.html). Small in-memory stores and
temporary stance files; no network.

The rule under test: a vote's direction is a SIGNED human judgement. With a
reading unsigned the page shows the record and labels nobody; a signed
reading shows its direction. Migration is never shown."""

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

from src import db, ie_profiles, ie_store  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mk = _load("make_ie_votes")

MEMBERS = [  # code, name, last, house, party, represents, start, end
    ("Ally.D.2024", "Ally Pro", "Pro", "dail", "Aontú", "Meath West", "2024-11-29", None),
    ("Opp.D.2024", "Opp Osite", "Osite", "dail", "Labour Party", "Dublin Bay South",
     "2024-11-29", None),
    ("Gone.D.2024", "Gone Away", "Away", "dail", "Fine Gael", "Kerry", "2024-11-29", "2026-01-01"),
    ("Sen.S.2025", "Sen Ator", "Ator", "seanad", "Independent", "Labour Panel", "2025-02-01", None),
]
DIVS = [  # key, chamber, house_key, committee, date, subject, bill, own, areas, amendment
    ("dail/34/2026-06-17/vote_149", "dail", "dail/34", None, "2026-06-17", "Question put:",
     "2026/47", "[1]", "[1]", None),
    # An amendment that only borrows its bill's area: not on our ground.
    ("dail/34/2026-06-18/vote_150", "dail", "dail/34", None, "2026-06-18", "Amendment put:",
     "2026/47", "[]", "[1]", None),
    # An amendment whose own text matched: on our ground, with its text.
    ("dail/34/2026-06-19/vote_151", "dail", "dail/34", None, "2026-06-19", "Amendment put:",
     "2026/47", "[1]", "[1]", "I move amendment No. 3: AMENDTEXT </script>"),
    ("committee/health/2026-05-05/vote_1", "committee", "dail/34", "Committee on Health",
     "2026-05-05", "Amendment put:", "2026/47", "[1]", "[1]", None),
    # Migration is matched and stored but never shown (HIDDEN_AREAS).
    ("dail/34/2026-03-01/vote_20", "dail", "dail/34", None, "2026-03-01", "Question put:",
     None, "[11]", "[11]", None),
    ("dail/34/2026-03-02/vote_21", "dail", "dail/34", None, "2026-03-02", "Question put:",
     None, "[1, 11]", "[1, 11]", None),
    ("seanad/27/2026-04-01/vote_9", "seanad", "seanad/27", None, "2026-04-01", "Question put:",
     None, "[7]", "[7]", None),
    # Own text matched, but the judge scored it 0 and nobody reads it: off the page.
    ("dail/34/2026-02-01/vote_5", "dail", "dail/34", None, "2026-02-01", "Question put:",
     None, "[1]", "[1]", None),
]
JUDGED_ZERO = ("dail/34/2026-02-01/vote_5", "dail/34/2026-06-17/vote_149")  # the second is read
VOTES = {
    "dail/34/2026-06-17/vote_149": {"Ally.D.2024": "No", "Opp.D.2024": "Yes"},
    "dail/34/2026-06-18/vote_150": {"Ally.D.2024": "No", "Opp.D.2024": "Yes"},
    "dail/34/2026-06-19/vote_151": {"Ally.D.2024": "Yes", "Opp.D.2024": "Abstain"},
    "committee/health/2026-05-05/vote_1": {"Ally.D.2024": "Yes"},
    "dail/34/2026-03-01/vote_20": {"Ally.D.2024": "Yes", "Opp.D.2024": "No"},
    "dail/34/2026-03-02/vote_21": {"Ally.D.2024": "Yes", "Gone.D.2024": "No"},
    "seanad/27/2026-04-01/vote_9": {"Sen.S.2025": "Yes"},
    "dail/34/2026-02-01/vote_5": {"Ally.D.2024": "Yes"},
}
STANCE = {
    "divisions": [
        {"key": "dail/34/2026-06-17/vote_149", "yea": -2, "nay": 2, "why_yea": "WHYTA-wider",
         "why_nay": "WHYNIL-against", "aye_means": "AYEMEANS-three-day", "draft": True},
        {"key": "seanad/27/2026-04-01/vote_9", "placeable": False, "reason": "REASON-x",
         "draft": True},
    ],
    "bills": [
        {"key": "2026/10", "sponsored": -2, "why_sponsored": "WHYSPONSOR", "draft": True},
    ],
}


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    ie_store.ensure_schema(conn)
    for code, name, last, house, party, rep, start, end in MEMBERS:
        conn.execute("INSERT INTO ie_members (member_code, name, last_name, house, party, "
                     "represents, start_date, end_date) VALUES (?,?,?,?,?,?,?,?)",
                     (code, name, last, house, party, rep, start, end))
    party = {m[0]: m[4] for m in MEMBERS}
    for key, ch, hk, com, date, subj, bill, own, areas, amend in DIVS:
        conn.execute("INSERT INTO ie_divisions (division_key, chamber, house_key, committee, date, "
                     "vote_id, debate_title, subject, outcome, ta, nil, staon, bill_key, own_areas, "
                     "areas, amendment_ref, amendment_text) VALUES (?,?,?,?,?,?,?,?, 'Carried', "
                     "1, 1, 0, ?,?,?,?,?)",
                     (key, ch, hk, com, date, key.split("/")[-1], "Debate " + key, subj, bill, own,
                      areas, "amendment No. 3" if amend else None, amend))
        for code, pos in VOTES[key].items():
            conn.execute("INSERT INTO ie_votes VALUES (?,?,?,?)", (key, code, pos, party[code]))
    for key in JUDGED_ZERO:
        conn.execute("UPDATE ie_divisions SET triage_score=0 WHERE division_key=?", (key,))
    for key, title, source, areas, score in (
            ("2026/10", "Abortion Bill", "Private Member", "[1]", None),
            ("2026/11", "Migration Bill", "Private Member", "[11]", None),
            ("2026/12", "Judged not ours", "Private Member", "[1]", 0),
            ("2026/13", "Government Bill", "Government", "[1]", None)):
        year, num = key.split("/")
        conn.execute("INSERT INTO ie_bills (bill_key, year, number, title, source, areas, "
                     "introduced, triage_score) VALUES (?,?,?,?,?,?, '2026-01-29', ?)",
                     (key, int(year), int(num), title, source, areas, score))
        conn.execute("INSERT INTO ie_sponsors (bill_key, sponsor, member_code, is_primary) "
                     "VALUES (?, 'Opp.D.2024', 'Opp.D.2024', 1)", (key,))
    for i in range(7):
        conn.execute("INSERT INTO ie_questions (question_key, ref, date, qtype, member_code, "
                     "minister, heading, question, answer_takeaway, areas, url) VALUES "
                     "(?,?,?, 'written', 'Ally.D.2024', 'Minister for Health', ?, "
                     "'QUESTION-TEXT', ?, '[1]', ?)",
                     ("2026-0{0}-01/pq_1".format(i + 1), "[{0}/26]".format(i), "2026-0{0}-01".format(i + 1),
                      "Heading {0}".format(i), "Takeaway {0}".format(i),
                      "https://www.oireachtas.ie/q{0}".format(i)))
    conn.execute("INSERT INTO ie_questions (question_key, date, member_code, heading, areas) "
                 "VALUES ('x/pq', '2026-09-01', 'Ally.D.2024', 'Migration question', '[11]')")
    for i in range(4):
        conn.execute("INSERT INTO ie_speeches (speech_key, date, chamber, section_title, "
                     "member_code, areas, excerpt, url) VALUES (?,?, 'dail', ?, 'Opp.D.2024', "
                     "'[1]', 'LONG-EXCERPT', ?)",
                     ("s{0}".format(i), "2026-0{0}-02".format(i + 1), "Section {0}".format(i),
                      "https://www.oireachtas.ie/s{0}".format(i)))
    conn.execute("INSERT INTO ie_speeches (speech_key, date, chamber, section_title, member_code, "
                 "areas, triage_score) VALUES ('s9', '2026-09-09', 'dail', 'Judged 0', "
                 "'Opp.D.2024', '[1]', 0)")
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
        self.assertEqual(set(by_key(build())), {
            "dail/34/2026-06-17/vote_149", "dail/34/2026-06-19/vote_151",
            "committee/health/2026-05-05/vote_1", "dail/34/2026-03-02/vote_21",
            "seanad/27/2026-04-01/vote_9"})

    def test_judged_zero_division_is_off_unless_the_stance_file_reads_it(self):
        divs = by_key(build())
        self.assertNotIn("dail/34/2026-02-01/vote_5", divs)      # scored 0, unread
        self.assertIn("dail/34/2026-06-17/vote_149", divs)        # scored 0, draft reading
        self.assertIn("dail/34/2026-03-02/vote_21", divs)         # unscored stays
        signed = by_key(build(signed_keys=("dail/34/2026-06-17/vote_149",)))
        self.assertIn("dail/34/2026-06-17/vote_149", signed)      # scored 0, signed reading

    def test_migration_hidden(self):
        data = build()
        divs = by_key(data)
        self.assertNotIn("dail/34/2026-03-01/vote_20", divs)
        self.assertEqual(divs["dail/34/2026-03-02/vote_21"]["areas"], [1])
        self.assertNotIn("11", data["areas"])
        self.assertNotIn("2026/11", {b["key"] for b in data["bills"]})
        self.assertNotIn("Migration question", json.dumps(data["questions"]))
        self.assertNotIn(11, data["five_ca_areas"])

    def test_committee_divisions_are_flagged(self):
        divs = by_key(build())
        self.assertEqual(divs["committee/health/2026-05-05/vote_1"]["committee"], "Committee on Health")
        self.assertEqual(divs["committee/health/2026-05-05/vote_1"]["house"], "dail")
        self.assertIsNone(divs["dail/34/2026-06-17/vote_149"]["committee"])

    def test_positions_parties_and_members(self):
        data = build()
        ids = [m["id"] for m in data["members"]]
        d = by_key(data)["dail/34/2026-06-19/vote_151"]
        self.assertEqual(d["pos"][ids.index("Ally.D.2024")], "Y")
        self.assertEqual(d["pos"][ids.index("Opp.D.2024")], "A")
        self.assertEqual(d["pos"][ids.index("Sen.S.2025")], ".")
        self.assertIn("AMENDTEXT", d["amendment"])
        self.assertFalse(d["amendment"].startswith("amendment No. 3: I move"))
        self.assertEqual(d["parties"]["Labour Party"]["A"], 1)
        m = {x["id"]: x for x in data["members"]}
        self.assertFalse(m["Gone.D.2024"]["in_office"])      # left, but voted here
        self.assertEqual(m["Sen.S.2025"]["house"], "seanad")
        self.assertEqual(m["Ally.D.2024"]["where"], "Meath West")

    def test_bills_questions_and_speeches(self):
        data = build()
        bills = data["bills"]
        self.assertEqual([bills[i]["key"] for i, _k, _d in data["member_bills"]["Opp.D.2024"]],
                         ["2026/10"])        # not Government, not judged 0, not migration
        q = data["questions"]["Ally.D.2024"]
        self.assertEqual(q["count"], 7)
        self.assertEqual(len(q["latest"]), ie_profiles.QUESTIONS_SHOWN)
        self.assertEqual(q["latest"][0]["takeaway"], "Takeaway 6")
        sp = data["speeches"]["Opp.D.2024"]
        self.assertEqual((sp["count"], len(sp["latest"])), (4, 3))
        blob = json.dumps(data)
        self.assertNotIn("QUESTION-TEXT", blob)              # never the question or answer
        self.assertNotIn("LONG-EXCERPT", blob)


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
        for token in ("WHYTA", "WHYNIL", "AYEMEANS", "WHYSPONSOR", "REASON-x"):
            self.assertNotIn(token, page)
        self.assertNotIn('"direction":', page)
        self.assertIn("Nobody on this page is labelled", page)


class SignedShowsDirectionTests(unittest.TestCase):
    def test_a_signed_reading_carries_its_direction(self):
        data = build(signed_keys=("dail/34/2026-06-17/vote_149",))
        d = by_key(data)["dail/34/2026-06-17/vote_149"]
        self.assertEqual(d["reading"], "signed")
        self.assertEqual(d["direction"]["ours"], "Nay")
        self.assertEqual(d["direction"]["why_nay"], "WHYNIL-against")
        self.assertNotIn("direction", by_key(data)["dail/34/2026-06-19/vote_151"])
        self.assertIn("WHYNIL-against", mk.render(data))

    def test_signed_reading_places_members_in_5ca(self):
        data = build(signed_keys=("dail/34/2026-06-17/vote_149",))
        self.assertEqual(data["placements"]["Ally.D.2024"]["1"]["column"], "++")
        self.assertEqual(data["placements"]["Opp.D.2024"]["1"]["column"], "--")
        self.assertNotIn("Sen.S.2025", data["placements"])

    def test_signed_evidence_only_has_no_direction(self):
        data = build(signed_keys=("seanad/27/2026-04-01/vote_9",))
        d = by_key(data)["seanad/27/2026-04-01/vote_9"]
        self.assertEqual(d["reading"], "signed: evidence only")
        self.assertNotIn("direction", d)

    def test_signed_bill_reading(self):
        data = build(signed_keys=("2026/10",))
        b = next(b for b in data["bills"] if b["key"] == "2026/10")
        self.assertEqual(b["direction"]["sponsored"], -2)
        self.assertEqual(data["placements"]["Opp.D.2024"]["1"]["column"], "--")


class PageTests(unittest.TestCase):
    def test_render_embeds_data_and_escapes_script_close(self):
        page = mk.render(build())
        self.assertNotIn("/*__DATA__*/", page)
        blob = re.search(r"const DATA = (\{.*?\});\n", page, re.S).group(1)
        self.assertEqual(len(json.loads(blob)["divisions"]), 5)
        self.assertEqual(page.lower().count("</script>"), 1)

    def test_main_writes_the_page_from_a_store_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dbp = os.path.join(tmp, "s.db")
            src = store()
            dst = sqlite3.connect(dbp)
            src.backup(dst)
            dst.close()
            out = os.path.join(tmp, "ie-votes.html")
            stance = stance_file()
            try:
                self.assertEqual(mk.main(["--db", dbp, "--out", out, "--stance", stance]), 0)
            finally:
                os.unlink(stance)
            with open(out, encoding="utf-8") as fh:
                self.assertIn("How did your TD or senator vote?", fh.read())

    def test_links(self):
        self.assertEqual(ie_profiles.bill_url("2026/10"),
                         "https://www.oireachtas.ie/en/bills/bill/2026/10/")
        self.assertEqual(ie_profiles.division_url(
            {"chamber": "dail", "house_key": "dail/34", "date": "2026-06-17", "vote_id": "vote_149"}),
            "https://www.oireachtas.ie/en/debates/vote/dail/34/2026-06-17/149/")


class WiringTests(unittest.TestCase):
    def test_weekly_builds_the_page_after_the_5ca_and_commits_it(self):
        with open(os.path.join(ROOT, "jobs", "ie-weekly.sh"), encoding="utf-8") as fh:
            script = fh.read()
        self.assertLess(script.index("tools/ie_5ca.py --all"), script.index("tools/make_ie_votes.py"))
        self.assertLess(script.index("tools/make_ie_votes.py"), script.rindex("tools/db_state.py --push"))
        self.assertRegex(script, r"make_ie_votes\.py[^\n]*\\\n\s*\|\| echo \"  \[gap\]")
        commit = re.search(r"^# mini_run: commit (.+)$", script, re.M).group(1).split()
        self.assertIn("partner_site", commit)
        self.assertIn("docs", commit)
        with open(os.path.join(ROOT, ".github", "workflows", "ie-weekly.yml"), encoding="utf-8") as fh:
            add = next(ln for ln in fh.read().splitlines() if ln.strip().startswith("git add "))
        self.assertEqual({p.rstrip("/") for p in add.split()[2:]} - {"data"}, set(commit))


if __name__ == "__main__":
    unittest.main()
