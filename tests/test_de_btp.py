"""The keyless protocol route, and the Bundestag's own member register.

Both were measured against live data on 26 September 2026 before being
built; the numbers in these tests are those measurements, not guesses.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import de_btp  # noqa: E402


LISTING = (
    '<div class="meta-slider" data-hits="4656" data-limit="10">'
    '<div class="bt-slide"><div class="bt-documents-description">'
    '<strong>21/96</strong><p>96. Sitzung, 21. Wahlperiode, 24.09.2026</p>'
    '<p>Protokoll | PDF | 1 MB</p></div>'
    '<a href="https://dserver.bundestag.de/btp/21/21096.pdf">PDF</a></div>'
    '<div class="bt-slide"><div class="bt-documents-description">'
    '<strong>21/7</strong><p>7. Sitzung, 21. Wahlperiode, 11.03.2026</p>'
    '</div></div>'
)


class DocumentUrlTests(unittest.TestCase):
    def test_the_sitting_number_pads_to_three(self):
        """21/96 is 21096.pdf. Not 2196.pdf, which 404s."""
        self.assertEqual(de_btp.pdf_url(21, 96),
                         "https://dserver.bundestag.de/btp/21/21096.pdf")
        self.assertEqual(de_btp.pdf_url(21, 7),
                         "https://dserver.bundestag.de/btp/21/21007.pdf")
        self.assertEqual(de_btp.pdf_url("21", "123"),
                         "https://dserver.bundestag.de/btp/21/21123.pdf")


class ListingTests(unittest.TestCase):
    def test_rows_carry_their_own_identity(self):
        rows = de_btp.parse_list(LISTING)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["protocol"], "21/96")
        self.assertEqual(rows[0]["datum"], "2026-09-24")
        self.assertEqual(rows[0]["wahlperiode"], 21)
        self.assertEqual(rows[0]["sitzung"], 96)

    def test_the_url_is_rebuilt_not_scraped(self):
        """Read from the row's own description, so a change to the document
        host cannot silently yield rows with no identity."""
        rows = de_btp.parse_list(LISTING)
        self.assertEqual(rows[0]["url"],
                         "https://dserver.bundestag.de/btp/21/21096.pdf")
        # the second row has no href at all and still resolves
        self.assertEqual(rows[1]["url"],
                         "https://dserver.bundestag.de/btp/21/21007.pdf")

    def test_the_total_is_read_from_the_page(self):
        self.assertEqual(de_btp.hits(LISTING), 4656)

    def test_a_repeated_sitting_is_listed_once(self):
        self.assertEqual(len(de_btp.parse_list(LISTING + LISTING)), 2)


class HyphenTests(unittest.TestCase):
    """The Bericht is justified and hyphenates freely: 3,467 splits in
    protocol 21/96, where DIP's text has none. Left alone, a term list that
    works on DIP under-matches on the PDF -- the first live run found 11
    speeches on our ground where DIP found 14, and 13 after this."""

    def test_a_split_word_is_rejoined(self):
        self.assertEqual(de_btp.dehyphenate("Bundesregie-\nrung"),
                         "Bundesregierung")
        self.assertEqual(
            de_btp.dehyphenate("Schwangerschafts-\nabbruch"),
            "Schwangerschaftsabbruch")

    def test_a_real_compound_keeps_its_hyphen(self):
        """A capital after the break is a compound, not a split word.
        Welding it would invent a word nobody wrote."""
        self.assertEqual(de_btp.dehyphenate("Mediendienste-\nInvestitions"),
                         "Mediendienste-\nInvestitions")

    def test_an_ordinary_line_break_is_untouched(self):
        self.assertEqual(de_btp.dehyphenate("erste Zeile\nzweite Zeile"),
                         "erste Zeile\nzweite Zeile")


class ExtractTests(unittest.TestCase):
    def test_an_unreadable_pdf_costs_its_own_sitting_and_no_more(self):
        """Returns empty rather than raising, the same rule the PQ archive
        reader follows."""
        self.assertEqual(de_btp.extract_text(b"not a pdf at all"), "")
        self.assertEqual(de_btp.extract_text(b""), "")


class FallbackShapeTests(unittest.TestCase):
    """The point of the route is that tools/de_speeches.py cannot tell which
    source it was handed."""

    def test_it_returns_what_the_dip_reader_returns(self):
        class Client:
            def get_text(self, url, feed, slug, **kw):
                return LISTING

            def get_bytes(self, url, feed, slug, **kw):
                return b"%PDF-1.4 not really"

        got = de_btp.protocols(Client(), "2026-01-01", limit=5, log=lambda *a: None)
        # both rows fail extraction, so none is yielded -- and nothing raises
        self.assertEqual(got, [])

    def test_it_stops_at_the_window_rather_than_paging_all_4656(self):
        seen = []

        class Client:
            def get_text(self, url, feed, slug, **kw):
                seen.append(url)
                return LISTING

            def get_bytes(self, url, feed, slug, **kw):
                raise AssertionError("must not download an out-of-window PDF")

        de_btp.protocols(Client(), "2027-01-01", limit=5, log=lambda *a: None)
        self.assertEqual(len(seen), 1, "one page, then the window ended it")


class StammdatenTests(unittest.TestCase):
    """MdB-Stammdaten.zip: 4,614 members, Wahlperioden 1-21, 532 with a
    constituency suffix (measured 2026-09-26)."""

    def _module(self):
        import importlib.util as iu
        spec = iu.spec_from_file_location(
            "de_stammdaten", os.path.join(ROOT, "tools", "de_stammdaten.py"))
        mod = iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    XML = (
        '<DOCUMENT><MDB><ID>11005627</ID><NAMEN>'
        '<NAME><NACHNAME>Alt</NACHNAME><VORNAME>Erika</VORNAME>'
        '<ORTSZUSATZ></ORTSZUSATZ><HISTORIE_VON>01.01.1990</HISTORIE_VON>'
        '<HISTORIE_BIS>31.12.2000</HISTORIE_BIS></NAME>'
        '<NAME><NACHNAME>Brand</NACHNAME><VORNAME>Michael</VORNAME>'
        '<ORTSZUSATZ>(Fulda)</ORTSZUSATZ><AKAD_TITEL>Dr.</AKAD_TITEL>'
        '<HISTORIE_VON>01.01.2001</HISTORIE_VON><HISTORIE_BIS></HISTORIE_BIS>'
        '</NAME></NAMEN>'
        '<BIOGRAFISCHE_ANGABEN><PARTEI_KURZ>CDU</PARTEI_KURZ>'
        '<RELIGION>evangelisch</RELIGION><BERUF>Jurist</BERUF>'
        '</BIOGRAFISCHE_ANGABEN>'
        '<WAHLPERIODEN>'
        '<WAHLPERIODE><WP>16</WP><MANDATSART>Direktwahl</MANDATSART>'
        '<WKR_NAME>Fulda</WKR_NAME></WAHLPERIODE>'
        '<WAHLPERIODE><WP>21</WP><MANDATSART>Direktwahl</MANDATSART>'
        '</WAHLPERIODE></WAHLPERIODEN></MDB></DOCUMENT>'
    )

    def test_the_current_name_wins_not_the_first(self):
        """A member can have several names, recorded with HISTORIE_BIS.
        Taking the first would give some of them the name they were elected
        under decades ago."""
        member, terms = self._module().parse(self.XML)[0]
        self.assertEqual(member["nachname"], "Brand")
        self.assertEqual(member["vorname"], "Michael")
        self.assertEqual(len(terms), 2)

    def test_the_constituency_suffix_is_stored_without_its_brackets(self):
        """It arrives as "(Fulda)". Stored bare, so it compares with what a
        parser pulled out of a heading."""
        member, _terms = self._module().parse(self.XML)[0]
        self.assertEqual(member["ortszusatz"], "Fulda")

    def test_service_is_summarised_across_terms(self):
        member, _terms = self._module().parse(self.XML)[0]
        self.assertEqual((member["first_wp"], member["last_wp"]), (16, 21))

    def test_religion_is_never_collected(self):
        """The file carries it. It is special category data and holding it
        is not necessary for anything this monitor does."""
        mod = self._module()
        member, _terms = mod.parse(self.XML)[0]
        self.assertNotIn("religion", member)
        self.assertNotIn("evangelisch", str(member))
        self.assertIn("RELIGION", mod.NOT_COLLECTED)

    def test_the_store_is_idempotent(self):
        from src import db
        mod = self._module()
        conn = db.init_db(db.connect(":memory:"))
        records = mod.parse(self.XML)
        mod.store(conn, records, today="2026-09-26")
        mod.store(conn, records, today="2026-09-27")
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM de_mdb").fetchone()[0], 1)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM de_mdb_terms").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
