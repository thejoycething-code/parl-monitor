"""Senate of Canada votes and the Canada Gazette (tools/ca_senate.py, tools/ca_gazette.py). No network."""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sen = _load("ca_senate")
gaz = _load("ca_gazette")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-ca.yaml"))


def quiet(*a):
    return None


def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    return ca_store.ensure_schema(conn)


# --- Senate -----------------------------------------------------------------

def list_row(vote_id, date, title, yeas, nays, abst, bill, result):
    bill_cell = ('<a href="http://www.parl.ca/LEGISInfo/BillDetails.aspx?billId=1" '
                 'title="View bill information">{0}</a>'.format(bill)) if bill else ""
    return ('<tr><td class="vote-centered" data-order="{d} 09:00:00 5"><a href="/j">{d}</a></td>'
            '<td data-order="x"><a class="vote-web-title-link" href="/en/in-the-chamber/votes/'
            'details/{id}/45-1">{t}</a><br />Yeas: {y} <text>|</text> Nays: {n} <text>|</text> '
            'Abstentions: {a} <text>|</text> Total: {tot}</td>'
            '<td class="vote-centered" data-order="1">{b}</td>'
            '<td class="vote-centered">{r}</td></tr>').format(
                d=date, id=vote_id, t=title, y=yeas, n=nays, a=abst, tot=yeas + nays + abst,
                b=bill_cell, r=result)


LIST = ("<table><tr><th>Date</th><th>Title</th><th>Related Bill</th><th>Result</th></tr>"
        + list_row(700344, "2026-06-04", "Combatting Hate Act &#x2013; C-9 &#x2013; Third Reading "
                   "&#x2013; Amendment (Sen. Martin)", 2, 1, 1, "C-9", "Defeated")
        + list_row(668042, "2025-06-26", "One Canadian Economy Act &#x2013; C-5 &#x2013; Third "
                   "Reading", 2, 1, 1, "C-5", "Adopted")
        + "</table>")


def senator(sid, name, aff, prov, mark):
    cells = "".join('<td data-order="{0}" class="c">{1}</td>'.format(
        "aaa" if i == mark else "zzz",
        '<i class="fa-solid fa-times"></i>' if i == mark else "") for i in range(3))
    return ('<tr><td data-order="{n}"><a href="/en/in-the-chamber/votes/senator/{s}/45-1">{n}'
            '</a></td><td class="c">{a}</td><td data-order="{p}" class="c">{p}</td>{c}</tr>').format(
                n=name, s=sid, a=aff, p=prov, c=cells)


DETAIL = ('<table class="table sc-table" id="sc-vote-details-table"><thead><tr><th>Senator</th>'
          '</tr></thead><tbody>'
          + senator(1, "Martin, Yonah", "C", "British Columbia", 0)
          + senator(2, "Housakos, Leo", "C", "Quebec", 0)
          + senator(3, "Pate, Kim", "ISG", "Ontario", 1)
          + senator(4, "Gold, Marc", "Non-affiliated", "Quebec", 2)
          + senator(5, "Absent, Anne", "PSG", "Ontario", None)
          + "</tbody></table>")


class SenateClient:
    def __init__(self, detail=DETAIL):
        self.detail, self.calls = detail, []

    def get_text(self, url, feed, slug, archive=True):
        if "/details/" in url:
            self.calls.append(url)
            return self.detail
        return LIST


class SenateTests(unittest.TestCase):
    def pull(self, conn, client, **kw):
        return sen.pull(conn, client, "2026-09-26", tax=TAX, wl=WL, log=quiet, **kw)

    def test_the_list_parses_title_bill_tallies_and_result(self):
        votes = sen.parse_list(LIST)
        self.assertEqual(len(votes), 2, "the header row is not a vote")
        v = votes[0]
        self.assertEqual((v["vote_id"], v["date"], v["bill_number"], v["result"]),
                         (700344, "2026-06-04", "C-9", "Defeated"))
        self.assertEqual((v["yeas"], v["nays"], v["abstentions"]), (2, 1, 1))
        self.assertIn("Combatting Hate Act – C-9", v["title"])

    def test_every_vote_is_stored_positions_only_on_our_ground(self):
        conn = store()
        client = SenateClient()
        listed, ours, fetched, gaps = self.pull(conn, client)
        self.assertEqual((listed, ours, fetched, gaps), (2, 1, 1, 0))
        self.assertTrue(client.calls[0].endswith("/details/700344/45-1"))
        row = conn.execute("SELECT * FROM ca_divisions WHERE number=700344").fetchone()
        self.assertEqual((row["chamber"], row["abstentions"]), ("senate", 1))

    def test_senators_who_did_not_vote_are_stored_as_such(self):
        """The Senate lists every seated senator; an unmarked row is an absence."""
        conn = store()
        self.pull(conn, SenateClient())
        pos = {r["person_id"]: (r["position"], r["party"]) for r in conn.execute("SELECT * FROM ca_votes")}
        self.assertEqual(pos["senator-1"], ("Yea", "C"))
        self.assertEqual(pos["senator-3"], ("Nay", "ISG"))
        self.assertEqual(pos["senator-4"], ("Abstention", "Non-affiliated"))
        self.assertEqual(pos["senator-5"][0], sen.DID_NOT_VOTE)

    def test_senator_ids_cannot_collide_with_house_person_ids(self):
        conn = store()
        self.pull(conn, SenateClient())
        self.assertTrue(all(r[0].startswith("senator-") for r in
                            conn.execute("SELECT person_id FROM ca_senators")))

    def test_positions_that_disagree_with_the_tally_are_a_gap(self):
        """The list's tally is the independent check on the details markup."""
        conn = store()
        wrong = DETAIL.replace(senator(2, "Housakos, Leo", "C", "Quebec", 0),
                               senator(2, "Housakos, Leo", "C", "Quebec", 1))
        _, _, fetched, gaps = self.pull(conn, SenateClient(detail=wrong))
        self.assertEqual((fetched, gaps), (0, 1))
        self.assertEqual(conn.execute("SELECT positions_fetched FROM ca_divisions "
                                      "WHERE number=700344").fetchone()[0], 0)
        self.assertIn("against the tally", conn.execute(
            "SELECT detail FROM gaps WHERE feed='ca-senate'").fetchone()[0])

    def test_a_list_that_parses_to_nothing_is_a_gap(self):
        conn = store()

        class Empty(SenateClient):
            def get_text(self, url, feed, slug, archive=True):
                return "<html>redesigned</html>"

        self.assertEqual(self.pull(conn, Empty()), (0, 0, 0, 1))

    def test_the_bills_long_title_is_joined_in(self):
        """A Senate title uses the short title only; C-16's long title is what
        the taxonomy reads."""
        conn = store()
        conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title) "
                     "VALUES ('45-1/C-5', 45, 1, 'C-5', 'An Act respecting gender-based violence')")
        _, ours, _, _ = self.pull(conn, SenateClient())
        self.assertEqual(ours, 2)


# --- Gazette ----------------------------------------------------------------

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Canada Gazette - Part I</title>
<item><title>Canada Gazette - Part I, September 26, 2026</title>
<link>https://gazette.gc.ca/rp-pr/p1/2026/2026-09-26/html/index-eng.html</link>
<pubDate>Sat, 26 Sep 2026 14:00:00 -0500</pubDate></item>
<item><title>Canada Gazette - Part I, Extra, July 31, 2026</title>
<link>https://gazette.gc.ca/rp-pr/p1/2026/2026-07-31-x6/html/extra6-eng.html</link>
<pubDate>Fri, 31 Jul 2026 14:00:00 -0500</pubDate></item>
<item><title>Quarterly index</title><link>https://gazette.gc.ca/rp-pr/p1/205/indexq1-eng.html</link>
<pubDate>Sat, 03 Jan 2026 14:00:00 -0500</pubDate></item>
</channel></rss>"""

BASE = "https://gazette.gc.ca/rp-pr/p1/2026/2026-09-26/html/"
INDEX = """<html><nav><a href="/other">Site chrome</a></nav><main>
<h2><a href="./commis-eng.html">Commissions</a></h2>
<a href="./commis-eng.html">Commissions</a>
<h3>Canada Revenue Agency</h3>
<a href="./commis-eng.html#cs9">Revocation of registration of charities</a>
<h3>Canadian International Trade Tribunal</h3>
<a href="./commis-eng.html#cs1">Photovoltaic modules and laminates</a><a href="#fn1">footnote *</a>
<h2>Proposed Regulations</h2><h3>Health, Dept. of</h3>
<a href="./reg1-eng.html">Regulations Amending the Medical Assistance in Dying Monitoring Regulations</a>
<h2>Supplements</h2>
<a href="./sup1-eng.html">Television Retransmission Tariff</a>
</main></html>"""
COMMIS = """<html><main>
<div id="cs1">CANADIAN INTERNATIONAL TRADE TRIBUNAL Photovoltaic modules. Solar panel dumping inquiry.</div>
<div id="cs9">CANADA REVENUE AGENCY Revocation of registration of charities. 1234RR0001
CAMPAIGN LIFE EDUCATION FUND, TORONTO, ONT. Notice of revocation for failure to meet the
requirements; the organisation's advocacy against abortion was not a charitable purpose.</div>
</main></html>"""
REG1 = """<html><main>Statutory authority Criminal Code. Sponsoring department Department of Health.
REGULATORY IMPACT ANALYSIS STATEMENT. The amendments extend reporting on MAID provided to
persons whose sole underlying condition is a mental illness.
Interested persons may make representations within 30 days after the date of publication of this notice.
</main></html>"""
SUP1 = "<html><main>A copyright tariff for television retransmission.</main></html>"
EXTRA = "<html><main>OFFICE OF THE CHIEF ELECTORAL OFFICER Determination of number of electors.</main></html>"


class GazetteClient:
    def __init__(self, fail=()):
        self.fail, self.calls = set(fail), []

    def get_text(self, url, feed, slug, archive=True):
        self.calls.append(url)
        if any(f in url for f in self.fail):
            raise FetchError(url, feed, slug, 4, OSError("503"))
        if url.endswith("-eng.xml"):
            return RSS
        name = url.rsplit("/", 1)[1]
        return {"index-eng.html": INDEX, "commis-eng.html": COMMIS, "reg1-eng.html": REG1,
                "sup1-eng.html": SUP1, "extra6-eng.html": EXTRA}[name]


class GazetteTests(unittest.TestCase):
    def pull(self, conn, client, **kw):
        return gaz.pull(conn, client, "2026-09-26", parts=(1,), since="2026-07-01",
                        tax=TAX, wl=WL, log=quiet, **kw)

    def item(self, conn, suffix):
        return conn.execute("SELECT * FROM ca_gazette_items WHERE item_key LIKE ?",
                            ("%" + suffix,)).fetchone()

    def test_the_feed_lists_issues_and_keys_extras_apart(self):
        issues = gaz.parse_rss(RSS, 1)
        self.assertEqual([i["issue_key"] for i in issues], ["p1-2026-09-26", "p1-2026-07-31-x6"],
                         "the quarterly index is not an issue")
        self.assertEqual(issues[0]["date"], "2026-09-26")

    def test_the_index_yields_items_not_section_links_or_footnotes(self):
        items = gaz.parse_index(INDEX, BASE + "index-eng.html")
        self.assertEqual([i["title"] for i in items],
                         ["Revocation of registration of charities", "Photovoltaic modules and laminates",
                          "Regulations Amending the Medical Assistance in Dying Monitoring Regulations",
                          "Television Retransmission Tariff"])
        kinds = {i["title"][:10]: (i["kind"], i["section"], i["department"]) for i in items}
        self.assertEqual(kinds["Revocation"], ("notice", "Commissions", "Canada Revenue Agency"))
        self.assertEqual(kinds["Regulation"], ("regulation", "Proposed Regulations", "Health, Dept. of"))
        self.assertEqual(kinds["Television"][0], "document")

    def test_a_proposed_regulation_carries_its_comment_deadline(self):
        conn = store()
        self.pull(conn, GazetteClient())
        r = self.item(conn, "reg1-eng.html")
        self.assertEqual((r["comment_days"], r["comment_until"]), (30, "2026-10-26"))
        self.assertIn(2, json.loads(r["areas"]))

    def test_a_notice_is_read_from_its_own_text_not_its_title(self):
        """'Revocation of registration of charities' names nobody; the text does."""
        conn = store()
        self.pull(conn, GazetteClient())
        r = self.item(conn, "#cs9")
        self.assertEqual(r["matched_on"], "body")
        self.assertIn("CAMPAIGN LIFE", r["text"])
        self.assertIn(1, json.loads(r["areas"]))
        other = self.item(conn, "#cs1")
        self.assertNotIn("CAMPAIGN LIFE", other["text"], "each notice is cut at the next anchor")

    def test_a_shared_notice_page_is_fetched_once(self):
        conn = store()
        client = GazetteClient()
        self.pull(conn, client)
        self.assertEqual(sum(1 for c in client.calls if c.endswith("commis-eng.html")), 1)

    def test_an_extra_edition_is_one_item_read_whole(self):
        conn = store()
        self.pull(conn, GazetteClient())
        r = self.item(conn, "extra6-eng.html")
        self.assertEqual((r["kind"], r["section"]), ("extra", "Extra edition"))

    def test_every_issue_read_gets_a_row_and_is_not_read_again(self):
        conn = store()
        self.pull(conn, GazetteClient())
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ca_gazette_issues").fetchone()[0], 2)
        client = GazetteClient()
        issues, *_ = self.pull(conn, client)
        self.assertEqual(issues, 0)
        self.assertEqual(len(client.calls), 1, "only the feed")

    def test_an_issue_with_a_failed_item_is_not_marked_read(self):
        conn = store()
        _, _, _, gaps = self.pull(conn, GazetteClient(fail=("reg1-eng.html",)))
        self.assertEqual(gaps, 1)
        keys = {r[0] for r in conn.execute("SELECT issue_key FROM ca_gazette_issues")}
        self.assertNotIn("p1-2026-09-26", keys, "retried whole next run")
        self.assertIn("p1-2026-07-31-x6", keys)

    def test_a_feed_that_fails_is_a_gap_not_an_empty_week(self):
        conn = store()
        self.assertEqual(self.pull(conn, GazetteClient(fail=("-eng.xml",))), (0, 0, 0, 1))


if __name__ == "__main__":
    unittest.main()
