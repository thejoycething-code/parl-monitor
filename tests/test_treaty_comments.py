"""Treaty body general comments: how a treaty gets reinterpreted."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.http import FetchError
from src.ingest import treaty_comments as tc
from src.robots_guard import GuardedClient, RobotsRefused
from tests.robots_fakes import guarded

sys.path.insert(0, os.path.join(ROOT, "tools"))
import un_comments  # noqa: E402

LISTING = """
<table>
<tr><th>Title</th><th>Document type</th><th>Treaty</th><th>COUNTRY</th></tr>
<tr><td>General recommendation No. 40 on equal and inclusive rep</td>
    <td>General Comment/recommendation</td><td>CEDAW</td><td>&nbsp;</td></tr>
<tr><td>Joint general recommendation No. 38 (2025) of the Co</td>
    <td>General Comment/recommendation</td><td>CERD</td><td>&nbsp;</td></tr>
<tr><td>Concluding observations on the report of Chad</td>
    <td>Concluding Observations</td><td>CRC</td><td>Chad</td></tr>
</table>
"""


class TreatyCommentTests(unittest.TestCase):
    def setUp(self):
        self.rows = tc.parse_general_comments(LISTING)

    def test_only_general_comments_are_kept(self):
        """Filtering on the document-type column means a reordered table
        yields nothing rather than nonsense."""
        self.assertEqual(len(self.rows), 2)
        self.assertNotIn("Chad", " ".join(r.title for r in self.rows))

    def test_number_and_year_are_read_from_the_title(self):
        cedaw = next(r for r in self.rows if r.treaty == "CEDAW")
        self.assertEqual(cedaw.symbol, "CEDAW/GC/40")
        cerd = next(r for r in self.rows if r.treaty == "CERD")
        self.assertEqual(cerd.year, "2025")

    def test_ours_is_decided_by_committee_not_by_being_a_comment(self):
        """The listing truncates titles, so keyword matching missed all ten
        real rows. CEDAW, CRC and CCPR are our ground by definition -- but
        CERD and CMW are not, and an earlier display marked every comment as
        ours."""
        self.assertTrue(next(r for r in self.rows if r.treaty == "CEDAW").ours)
        self.assertFalse(next(r for r in self.rows if r.treaty == "CERD").ours)

    def test_empty_parse_is_distinguishable_from_no_comments(self):
        self.assertEqual(tc.parse_general_comments("<table></table>"), [])


DISALLOW_ALL = "User-agent: *\nDisallow: /\n"


class Search:
    """The treaty body search: serves LISTING and records every request sent."""

    def __init__(self):
        self.asked = []

    def get_text(self, url, feed, slug, *a, **k):
        self.asked.append(url)
        if url == tc.TB_SEARCH:
            return LISTING
        raise FetchError(url, feed, slug, 1, "HTTP Error 404")


class RobotsGuardTests(unittest.TestCase):
    """tbinternet's robots.txt reads Disallow: / since 13 October 2026: the
    search must be refused before it is sent, and say so."""

    def test_disallowed_search_is_refused_and_never_sent(self):
        search = Search()
        client, serving = guarded(search, {"tbinternet.ohchr.org": DISALLOW_ALL}, "tb")
        with self.assertRaises(RobotsRefused) as ctx:
            tc.fetch_general_comments(client)
        self.assertEqual(search.asked, [])
        self.assertEqual(serving.robots_asked, ["tbinternet.ohchr.org"])
        self.assertIn("robots.txt disallows", str(ctx.exception))
        self.assertIn(tc.TB_SEARCH, str(ctx.exception))

    def test_refusal_is_a_fetch_error(self):
        """Callers that catch FetchError still catch a refusal."""
        client, _ = guarded(Search(), {"tbinternet.ohchr.org": DISALLOW_ALL}, "tb")
        with self.assertRaises(FetchError):
            tc.fetch_general_comments(client)

    def test_allowed_search_is_fetched_and_parsed(self):
        search = Search()
        client, _ = guarded(search, {"tbinternet.ohchr.org": "User-agent: *\nDisallow: /admin/\n"},
                            "tb")
        rows = tc.fetch_general_comments(client)
        self.assertEqual(search.asked, [tc.TB_SEARCH])
        self.assertEqual(len(rows), 2)

    def test_a_plain_client_is_wrapped_in_the_guard(self):
        self.assertIsInstance(tc.guarded(Search(), log=lambda *a, **k: None), GuardedClient)
        client, _ = guarded(Search(), {}, "tb")
        self.assertIs(tc.guarded(client), client)

    def test_the_tool_reports_could_not_read_and_stores_nothing(self):
        import contextlib
        import io
        search = Search()
        client, _ = guarded(search, {"tbinternet.ohchr.org": DISALLOW_ALL}, "tb")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = un_comments.main(client)
        self.assertEqual(code, 2)
        self.assertIn("could not read: robots.txt disallows", out.getvalue())
        self.assertEqual(search.asked, [])


if __name__ == "__main__":
    unittest.main()
