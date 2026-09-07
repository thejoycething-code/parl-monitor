"""Who spoke, and which way; closed deadlines; Across removed; Hansard window.

Christopher, 2026-09-07: "fix the closed consultations still appearing.
Remove the 'Across the parliaments' section from the edition. Build the
'Who spoke, and which way' feature."
"""

import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import digest, spoke  # noqa: E402


def _edition(**kw):
    e = digest.Edition(week_commencing="2026-09-07", number=6, mode="normal")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


class ClosedDeadlinesTests(unittest.TestCase):
    """Edition 6 printed two consultations at "-6 days" and "-3 days"."""

    def _rows(self):
        return [{"type": "Evidence", "title": "Closed last week", "url": "u1",
                 "why": "", "deadline": "2026-09-01"},
                {"type": "Consultation", "title": "Still open", "url": "u2",
                 "why": "", "deadline": "2026-09-18"}]

    def test_a_deadline_before_the_week_is_not_shown(self):
        out = digest.render_deadlines(_edition(deadlines=self._rows()))
        self.assertIn("Still open", out)
        self.assertNotIn("Closed last week", out)
        self.assertNotIn("-6 days", out)

    def test_nothing_open_means_no_section(self):
        rows = [self._rows()[0]]
        self.assertIsNone(digest.render_deadlines(_edition(deadlines=rows)))

    def test_a_rolling_call_stays(self):
        rows = [{"type": "Evidence", "title": "Rolling call", "url": "u",
                 "why": "", "deadline": None}]
        self.assertIn("Rolling call", digest.render_deadlines(_edition(deadlines=rows)))

    def test_a_past_deadline_is_not_a_top_line_either(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        self.assertIn('r["triage_score"] == 3 and not (r["deadline"] and '
                      'r["deadline"] < edition.week_commencing)', src)


class AcrossRemovedTests(unittest.TestCase):
    def test_the_edition_never_renders_across_the_parliaments(self):
        e = _edition(across="## Across the parliaments\n\n* something")
        e.board_rows = []
        md = digest.render(e)
        self.assertNotIn("Across the parliaments", md)

    def test_run_weekly_no_longer_builds_it(self):
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        self.assertNotIn("edition.across", src)
        self.assertNotIn("src import across", src)


class HansardWindowTests(unittest.TestCase):
    def test_the_sweep_reads_the_week_just_ended(self):
        """The newest speech in the ledger was dated 23 July on 7 September:
        the sweep searched the edition week, which had not happened."""
        src = open(os.path.join(ROOT, "run_weekly.py"), encoding="utf-8").read()
        block = src[src.index("def _hansard():"):src.index("def _wms():")]
        self.assertIn("report_start = week_start - datetime.timedelta(days=7)", block)
        self.assertIn("report_start.isoformat(), report_end.isoformat()", block)
        self.assertNotIn("week_start.isoformat(), week_end.isoformat()", block)


def _speaker(name, stance, why="because", **kw):
    d = {"member_id": hash(name) % 10000, "name": name, "party": "Labour",
         "seat": "Somewhere", "stance": stance, "why": why, "url": None, "count": 1}
    d.update(kw)
    return d


class RenderSpokeTests(unittest.TestCase):
    def _block(self, speakers, **kw):
        b = {"title": "Terminally Ill Adults (End of Life) Bill", "house": "Commons",
             "date": "2025-06-20",
             "url": "https://hansard.parliament.uk/Commons/2025-06-20/debates/X/",
             "speakers": speakers}
        b.update(kw)
        return b

    def test_one_table_per_debate_with_direction_and_reason(self):
        out = digest.render_spoke([self._block([
            _speaker("Danny Kruger", -2, "Argued the safeguards cannot hold.",
                     party="Conservative", seat="East Wiltshire",
                     url="https://hansard.parliament.uk/c/1"),
            _speaker("Kim Leadbeater", 2, "Moved the Bill.")])])
        self.assertIn("**Who spoke, and which way**", out)
        self.assertIn("**Terminally Ill Adults (End of Life) Bill** \u00b7 Commons \u00b7 Fri 20 Jun \u00b7 "
                      "[Hansard](https://hansard.parliament.uk/Commons/2025-06-20/debates/X/) \u00b7 "
                      "2 speakers on our ground", out)
        self.assertIn("| [Danny Kruger](https://hansard.parliament.uk/c/1) (Conservative, East Wiltshire) "
                      "| Against us, strongly | Argued the safeguards cannot hold. |", out)
        self.assertIn("| Kim Leadbeater (Labour, Somewhere) | With us, strongly | Moved the Bill. |", out)

    def test_direction_words_cover_every_score_and_the_unscored(self):
        out = digest.render_spoke([self._block([
            _speaker("A", 1), _speaker("B", 0), _speaker("C", -1), _speaker("D", None)])])
        for word in ("With us |", "Neutral or unclear", "Against us |", "Not yet scored"):
            self.assertIn(word, out)

    def test_committed_speakers_survive_the_cap(self):
        speakers = [_speaker("Neutral {0}".format(i), 0) for i in range(20)]
        speakers.append(_speaker("Zed Strong", 2))
        out = digest.render_spoke([self._block(speakers)], speakers_cap=5)
        self.assertIn("Zed Strong", out)
        self.assertIn("...and 16 more; every contribution is recorded on the member profiles.", out)

    def test_a_repeat_speaker_is_one_row_with_a_count(self):
        out = digest.render_spoke([self._block([_speaker("A", 1, count=3)])])
        self.assertIn("A (Labour, Somewhere) (x3)", out)

    def test_debates_are_capped_and_the_rest_counted(self):
        blocks = [self._block([_speaker("A", 1)], title="Debate {0}".format(i)) for i in range(10)]
        out = digest.render_spoke(blocks, debates_cap=8)
        self.assertEqual(out.count("| Member | Direction |"), 8)
        self.assertIn("...and 2 more debates on our ground this week", out)

    def test_nothing_spoken_renders_nothing(self):
        self.assertIsNone(digest.render_spoke([]))

    def test_it_leads_the_parliamentarians_section_and_debates_leave_the_list(self):
        events = [{"member_id": 1, "kind": "debate", "line": "Spoke: X", "name": "N",
                   "party": "P", "seat": "S", "areas": "[2]"},
                  {"member_id": 2, "kind": "edm", "line": "Sponsored EDM: Y", "name": "M",
                   "party": "P", "seat": "S", "areas": "[2]"}]
        lines = digest.mp_lines_from_events(events, skip_kinds={"debate"})
        self.assertEqual(len(lines), 1)
        self.assertIn("EDM", lines[0])
        md = digest.render_mp_section(lines, [self._block([_speaker("N", 1)])])
        self.assertLess(md.index("## Parliamentarians on our issues"), md.index("**Who spoke"))
        self.assertLess(md.index("**Who spoke"), md.index("Sponsored EDM"))

    def test_debates_still_list_when_there_is_no_spoke_block(self):
        """The old behaviour stays the fallback: skip_kinds defaults to none."""
        events = [{"member_id": 1, "kind": "debate", "line": "Spoke: X", "name": "N",
                   "party": "P", "seat": "S", "areas": "[2]"}]
        self.assertEqual(len(digest.mp_lines_from_events(events)), 1)


class CollectTests(unittest.TestCase):
    def _conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE mp_events (member_id INTEGER, date TEXT, kind TEXT, ref TEXT, "
                     "line TEXT, areas TEXT, excerpt TEXT)")
        conn.execute("CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT, party TEXT, "
                     "seat TEXT, house TEXT)")
        conn.execute("CREATE TABLE stance (ref TEXT PRIMARY KEY, stance INTEGER, why TEXT, "
                     "model TEXT, scored_at TEXT)")
        conn.executemany("INSERT INTO members VALUES (?,?,?,?,?)", [
            (1, "Danny Kruger", "Conservative", "East Wiltshire", "Commons"),
            (2, "Kim Leadbeater", "Labour", "Spen Valley", "Commons"),
            (3, "Quiet Member", "Labour", "Nowhere", "Commons")])
        conn.executemany("INSERT INTO mp_events VALUES (?,?,?,?,?,?,?)", [
            (1, "2025-06-20", "debate", "hansard:a1", "Spoke: Terminally Ill Adults (End of Life) Bill", "[2]", "x"),
            (1, "2025-06-20", "debate", "hansard:a2", "Spoke: Terminally Ill Adults (End of Life) Bill (re: assisted dying)", "[2]", "x"),
            (2, "2025-06-20", "debate", "hansard:b1", "Spoke: Terminally Ill Adults (End of Life) Bill", "[2]", "x"),
            (3, "2025-06-18", "debate", "hansard:c1", "Spoke: Extreme Heat", "[]", "x"),
            (2, "2025-06-20", "vote", "div:c2071:aye", "Voted Aye: Third Reading", "[2]", None)])
        conn.executemany("INSERT INTO stance VALUES (?,?,?,?,?)", [
            ("hansard:a1", -1, "Doubted the safeguards.", "m", "t"),
            ("hansard:a2", -2, "Called the Bill unsafe.", "m", "t")])
        return conn

    def test_one_block_per_debate_one_row_per_member_strongest_wins(self):
        blocks = spoke.collect(self._conn(), "2025-06-16", "2025-06-22", root=None)
        self.assertEqual(len(blocks), 1)
        b = blocks[0]
        self.assertEqual(b["title"], "Terminally Ill Adults (End of Life) Bill")
        names = {s["name"]: s for s in b["speakers"]}
        self.assertEqual(set(names), {"Danny Kruger", "Kim Leadbeater"})
        self.assertEqual(names["Danny Kruger"]["count"], 2)
        self.assertEqual(names["Danny Kruger"]["stance"], -2)
        self.assertEqual(names["Danny Kruger"]["why"], "Called the Bill unsafe.")
        self.assertIsNone(names["Kim Leadbeater"]["stance"])   # unscored, still listed

    def test_area_less_speeches_and_votes_never_enter(self):
        blocks = spoke.collect(self._conn(), "2025-06-16", "2025-06-22", root=None)
        titles = [b["title"] for b in blocks]
        self.assertNotIn("Extreme Heat", titles)

    def test_the_annotation_is_stripped_from_the_title(self):
        self.assertEqual(spoke._title_from_line("Spoke: Hospices (re: assisted dying)"), "Hospices")
        self.assertEqual(spoke._title_from_line("Spoke: Hospices"), "Hospices")

    def test_no_stance_table_is_no_crash(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE mp_events (member_id INTEGER, date TEXT, kind TEXT, ref TEXT, line TEXT, areas TEXT, excerpt TEXT)")
        self.assertEqual(spoke.collect(conn, "2025-06-16", "2025-06-22"), [])


if __name__ == "__main__":
    unittest.main()
