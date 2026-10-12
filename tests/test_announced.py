"""Announced business: the What's on block that does not depend on keywords.

The 5 Oct 2026 edition missed the Commons general debate on Baby Loss
Awareness Week and the Westminster Hall petition debate on rejoining the
EU (both 12 Oct), because neither title matched the taxonomy.
"""

import datetime
import unittest

import run_weekly
from src import digest
from src.ingest import whatson


def ev(id, day, house, category, venue, desc, start="", members=None):
    return whatson.Event(start_date=datetime.date(2026, 10, day), start_time=start,
                         house=house, category=category, type=venue,
                         description=desc, bill_id=None, bill_name=None,
                         committee=None, location=None, id=id, members=members or [])


EVENTS = [
    ev(1, 12, "Commons", "Oral questions", "Main Chamber", "Work and Pensions"),
    ev(2, 12, "Commons", "General debate", "Main Chamber",
       "General debate on Baby Loss Awareness Week", members=["Andy MacNae"]),
    ev(3, 12, "Commons", "Westminster Hall debate", "Westminster Hall",
       "e-petition 749128 relating to the UK applying to rejoin the EU", "16:30", ["Tony Vaughan"]),
    ev(4, 12, "Commons", "Adjournment", "Main Chamber", "High streets in Amber Valley"),
    ev(5, 13, "Lords", "Legislation", "Main Chamber", "Health Bill - second reading"),
    ev(6, 13, "Commons", "Oral evidence", "Select & Joint Committees", "Evidence session"),
    ev(7, 15, "Lords", "Debate", "Grand Committee", "UK-EU competition agreement"),
] + [ev(100 + i, 16, "Commons", "Private Members' Bills", "Main Chamber",
        "PMB {0}: Second Reading".format(i)) for i in range(6)]


class AnnouncedTest(unittest.TestCase):
    def test_selects_headline_business_only(self):
        rows, held = whatson.announced(EVENTS)
        ids = [e.id for e in rows]
        self.assertIn(2, ids)        # baby loss general debate
        self.assertIn(3, ids)        # EU petition debate
        self.assertIn(5, ids)
        self.assertIn(7, ids)
        for routine in (1, 4, 6):    # questions, adjournment, committee
            self.assertNotIn(routine, ids)

    def test_pmbs_capped_in_order_paper_order(self):
        rows, held = whatson.announced(EVENTS)
        pmbs = [e.id for e in rows if e.category == "Private Members' Bills"]
        self.assertEqual(pmbs, [100, 101, 102])
        self.assertEqual(held, {"2026-10-16": 3})

    def test_excludes_events_already_in_the_table(self):
        rows, _ = whatson.announced(EVENTS, exclude_ids={2})
        self.assertNotIn(2, [e.id for e in rows])

    def test_first_sitting_week(self):
        self.assertEqual(whatson.first_sitting_week(EVENTS), datetime.date(2026, 10, 12))
        self.assertIsNone(whatson.first_sitting_week([]))

    def test_recess_edition_shows_the_return_week(self):
        rows, held = whatson.announced(EVENTS)
        ed = digest.Edition(week_commencing="2026-10-05", number=1, mode="recess",
                            announced=[run_weekly.announced_row(e) for e in rows],
                            announced_week="2026-10-12", announced_held=held)
        out = digest.render_whats_on(ed, recess=True)
        self.assertIn("Announced for the return** (week of 12 Oct)", out)
        self.assertIn("General debate on Baby Loss Awareness Week", out)
        self.assertIn("Westminster Hall 4.30pm: [e-petition 749128", out)
        self.assertIn("Lords Grand Committee: [UK-EU competition agreement]", out)
        self.assertIn("and 3 more Private Members' Bills", out)
        self.assertNotIn("—", out)   # editions carry no em dashes

    def test_sitting_week_heading_and_venue_order(self):
        rows, held = whatson.announced(EVENTS)
        ed = digest.Edition(week_commencing="2026-10-12", number=1, mode="normal",
                            announced=[run_weekly.announced_row(e) for e in rows],
                            announced_held=held)
        out = digest.render_announced(ed)
        self.assertIn("Also announced this week", out)
        monday = [l for l in out.splitlines() if l.startswith("- **Mon 12 Oct")][0]
        self.assertLess(monday.index("Baby Loss"), monday.index("e-petition"))

    def test_nothing_announced_renders_nothing(self):
        ed = digest.Edition(week_commencing="2026-10-12", number=1, mode="normal")
        self.assertIsNone(digest.render_announced(ed))


if __name__ == "__main__":
    unittest.main()
