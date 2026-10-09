"""Australian debates (tools/au_debates.py), their Debate section
(tools/au_monitor.py) and their judging (tools/au_triage.py). No network:
OpenAustralia's Senate day file of 10 September 2026, trimmed to the social
media minimum age enforcement bill's committee stage, two notices, a
senator's statement and another bill's second reading."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIX = os.path.join(ROOT, "tests", "fixtures", "au")

from src import db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aud = _load("au_debates")
aum = _load("au_monitor")
aut = _load("au_triage")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = aud.empty_watchlist()
DATE = "2026-09-10"
TODAY = "2026-09-11"
SENATORS = {"lord/100971": "Slade Brockman", "lord/100256": "Sarah Hanson-Young",
            "lord/100908": "Nita Green", "lord/100849": "James Paterson",
            "lord/100312": "Deborah O'Neill", "lord/100907": "Katy Gallagher",
            "lord/100961": "Michelle Ananda-Rajah", "lord/100252": "Michaelia Cash"}


def raw():
    with open(os.path.join(FIX, "senate_debates_2026-09-10.xml"), "rb") as fh:
        return fh.read()


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    for n, (office, name) in enumerate(sorted(SENATORS.items())):
        pid = str(20000 + n)
        conn.execute("INSERT INTO au_offices (office_id, person_id, house, party) VALUES (?,?,?,?)",
                     (office, pid, "senate", "Australian Labor Party"))
        conn.execute("INSERT INTO au_members (person_id, name, phid) VALUES (?,?,?)",
                     (pid, name, "PH" + str(n)))
    conn.execute("INSERT INTO au_bills (bill_id, parliament, title, areas) VALUES "
                 "('r7500', 48, 'Statute Update Bill 2026', '[]')")
    conn.commit()
    return conn


def read(conn, watch=None):
    return aud.read_day(conn, raw(), "senate", DATE, TODAY, TAX, WL, aud._people(conn),
                        aud.BillTitles(conn, TAX, WL), watch)


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.speeches, self.unresolved = aud.parse_speeches(raw(), "senate", DATE)
        self.by = {s["segment"]: s for s in self.speeches}

    def test_everything_one_senator_said_in_one_section_is_one_speech(self):
        # Paterson spoke, was interrupted, and continued across divisions.
        paterson = [s for s in self.speeches if s["name"] == "James Paterson"]
        self.assertEqual(len(paterson), 1)
        self.assertGreater(paterson[0]["words"], 1000)

    def test_interjections_are_nobodys_speech(self):
        self.assertFalse(any(s["segment"] in ("2026-09-10.11.3",) for s in self.speeches))
        self.assertEqual(self.unresolved, 0)

    def test_a_debate_carries_its_bills_and_headings(self):
        s = self.by["2026-09-10.14.1"]
        self.assertEqual(s["bills"], ["r7512"])
        self.assertTrue(s["minor"].startswith("Online Safety Amendment"))
        self.assertEqual(self.by["2026-09-10.202.3"]["bills"], ["r7500"])

    def test_kinds(self):
        self.assertEqual(self.by["2026-09-10.20.1"]["kind"], "motion")     # Paterson moves amendments
        self.assertEqual(self.by["2026-09-10.33.3"]["kind"], "notice")     # under NOTICES
        self.assertEqual(self.by["2026-09-10.141.2"]["kind"], "speech")    # a statement
        self.assertEqual(aud.speech_kind("BILLS", ["I move: That this bill be now read a second time."]),
                         "speech")
        self.assertEqual(aud.speech_kind("BILLS", ["by leave—I move:", "That the Senate ..."]),
                         "motion")

    def test_an_unknown_speaker_is_counted_never_given_to_anyone(self):
        xml = (b"<debates><major-heading>MOTIONS</major-heading>"
               b"<speech id='uk.org.publicwhip/lords/2026-09-10.1.1' speakerid='unknown' "
               b"speakername='Opposition Senators' talktype='speech'><p>Abortion!</p></speech>"
               b"</debates>")
        speeches, unresolved = aud.parse_speeches(xml, "senate", DATE)
        self.assertEqual((speeches, unresolved), ([], 1))


class RuleTests(unittest.TestCase):
    def test_own_words_need_no_bill(self):
        own, areas, source, _t, tier, excerpt = aud.classify_speech(
            TAX, WL, "Statements", "We must protect children from online harms and nudification apps.",
            12, [], lambda b: [], watch={})
        self.assertTrue(areas)
        self.assertEqual(source, "own")
        self.assertLessEqual(len(excerpt), aud.EXCERPT)

    def test_a_watched_bill_lends_only_to_more_than_procedure(self):
        text = "I move that the question be now put."
        self.assertEqual(aud.classify_speech(TAX, WL, "X Bill; In Committee", text, 8, ["r7512"],
                                             lambda b: [], watch={"r7512": ([6], "")})[1], [])
        long = " ".join(["The committee will now consider the clauses in turn."] * 6)
        res = aud.classify_speech(TAX, WL, "X Bill; In Committee", long, 54, ["r7512"],
                                  lambda b: [], watch={"r7512": ([6], "")})
        self.assertEqual((res[1], res[2]), ([6], "watch"))

    def test_a_bill_lends_its_title_only_to_a_full_speech_that_matched_nothing(self):
        long = " ".join(["The amendments improve the administration of the scheme."] * 20)
        lent = aud.classify_speech(TAX, WL, "Y Bill; Second Reading", long, 160, ["r1"],
                                   lambda b: [1], watch={})
        self.assertEqual((lent[1], lent[2]), ([1], "bill"))
        short = aud.classify_speech(TAX, WL, "Y Bill; Second Reading", long[:300], 45, ["r1"],
                                    lambda b: [1], watch={})
        self.assertEqual(short[1], [])
        hidden = aud.classify_speech(TAX, WL, "Y Bill; Second Reading", long, 160, ["r1"],
                                     lambda b: [11], watch={})
        self.assertEqual(hidden[1], [])

    def test_the_heading_counts_only_for_a_full_speech(self):
        heading = "Sex Discrimination Amendment (Restoring Common Sense and Recognising Biological Sex) Bill 2026"
        short = aud.classify_speech(TAX, WL, heading, "I thank senators for their contributions.",
                                    6, [], lambda b: [], watch={})
        self.assertEqual(short[1], [])


class StoreTests(unittest.TestCase):
    def test_a_day_stores_only_speeches_on_our_ground_with_speaker_and_party(self):
        conn = store()
        read_n, ours, unresolved = read(conn)
        self.assertEqual((read_n, unresolved), (9, 0))
        rows = conn.execute("SELECT speech_key, name, party, phid, kind, bill_ids, areas_from, "
                            "excerpt, url FROM au_speeches ORDER BY speech_key").fetchall()
        self.assertEqual(ours, len(rows))
        keys = [r[0] for r in rows]
        self.assertIn("senate/2026-09-10.20.1", keys)
        self.assertNotIn("senate/2026-09-10.202.3", keys)          # Statute Update: not ours
        self.assertNotIn("senate/2026-09-10.27.2", keys)           # an 11-word closure
        pat = [r for r in rows if r[0] == "senate/2026-09-10.20.1"][0]
        self.assertEqual((pat[1], pat[2], pat[4], json.loads(pat[5])),
                         ("James Paterson", "Australian Labor Party", "motion", ["r7512"]))
        self.assertTrue(pat[3].startswith("PH"))
        self.assertTrue(all(len(r[7] or "") <= aud.EXCERPT for r in rows))
        self.assertEqual(pat[8], "https://www.openaustralia.org.au/senate/?id=2026-09-10.20.1")

    def test_a_reparsed_day_replaces_its_unscored_speeches(self):
        conn = store()
        read(conn)
        conn.execute("INSERT INTO au_speeches (speech_key, chamber, date, areas) VALUES "
                     "('senate/2026-09-10.999.1', 'senate', ?, '[7]')", (DATE,))
        read(conn)
        self.assertIsNone(conn.execute("SELECT 1 FROM au_speeches WHERE speech_key="
                                       "'senate/2026-09-10.999.1'").fetchone())

    def test_pull_reads_newest_first_and_stops_on_its_limit(self):
        conn = store()
        aur = aud.aur
        listing = ('<a href="2026-09-09.xml">2026-09-09.xml</a> 2026-09-10 09:05 '
                   '<a href="2026-09-10.xml">2026-09-10.xml</a> 2026-09-11 09:05')

        class Client:
            asked = []

            def get_text(self, url, feed, slug, archive=True, **kw):
                if "senate" in url:
                    return listing
                raise FetchError(url, feed, slug, 1, "404")

            def get_bytes(self, url, feed, slug, archive=True, **kw):
                self.asked.append(url)
                assert archive is False
                return raw()

        client = Client()
        s = aud.pull(conn, client, TODAY, tax=TAX, wl=WL, log=lambda *_: None, limit=1)
        self.assertEqual(client.asked, [aur.DAY.format("senate", "2026-09-10")])
        self.assertEqual((s["days"], s["left"], s["gaps"]), (1, 1, 1))   # the House listing 404
        self.assertEqual(conn.execute("SELECT listed_modified FROM au_debate_days").fetchone()[0],
                         "2026-09-11 09:05")


class EditionTests(unittest.TestCase):
    def test_the_debate_section_is_one_line_per_speech(self):
        conn = store()
        read(conn)
        conn.row_factory = sqlite3.Row
        text = aum.render_edition(conn, TODAY)
        section = text.split("## Debate")[1].split("\n## ")[0]
        lines = [l for l in section.splitlines() if l.startswith("- ")]
        self.assertTrue(lines)
        self.assertTrue(any("James Paterson (ALP) (moving a motion)" in l for l in lines))
        self.assertTrue(all(len(l) < 900 for l in lines))
        self.assertIn("speech(es) or motion(s) on our ground", aum.dm_summary(conn, TODAY))

    def test_no_speech_says_so(self):
        conn = store()
        conn.row_factory = sqlite3.Row
        self.assertIn("## Debate (none this week; last 30 days: 0)", aum.render_edition(conn, TODAY))


class JudgeTests(unittest.TestCase):
    def test_speeches_whose_own_words_matched_are_judged(self):
        conn = store()
        read(conn)
        conn.row_factory = sqlite3.Row
        ids = [i.id for i in aut.pending(conn)]
        self.assertIn("au_speeches:senate/2026-09-10.20.1", ids)
        own = conn.execute("SELECT COUNT(*) FROM au_speeches WHERE own_areas NOT IN ('[]','[11]')"
                           ).fetchone()[0]
        self.assertEqual(sum(i.startswith("au_speeches:") for i in ids), own)


if __name__ == "__main__":
    unittest.main()
