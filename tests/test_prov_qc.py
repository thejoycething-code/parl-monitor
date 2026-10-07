"""Quebec (src/ingest/prov_qc.py). No network: fixtures in tests/fixtures/prov/.

THE PROOFS (docs/canada-provinces-scope.md, Quebec):
  * Bill 21, Loi sur la laïcité de l'État, adopted on 16 June 2019, 73-35
    (procès-verbal vote no. 165): Legault and Jolin-Barrette for,
    Nadeau-Dubois against, tally matched.
  * Bill 1, Loi constitutionnelle de 2025 sur le Québec, principle adopted
    68-31-1 on 1 April 2026 (vote no. 139), electronic voting: names and
    parties read from the procès-verbal annex, from a real PDF page.
  * The annex is four columns read top to bottom, and a riding wraps under
    ITS OWN column: in the text stream "(Soulanges)" sits beside Lamontagne,
    but it is Picard's.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.ingest import prov_qc as qc  # noqa: E402
from src.prov_fetch import Context, rule_allows, star_rules  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")


def fx(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def annex(day):
    data = json.loads(fx("qc_pv_{0}_annex.json".format(day)))
    pages = [[tuple(f) for f in page] for page in data["pages"]]
    return qc.parse_annex(pages, data["plain"])


def resolver():
    """The dated roster, as read live from the depcir pages on 2 October
    2026, cut to the members sitting on the fixture days."""
    data = json.loads(fx("qc_terms.json"))
    return pn.Resolver(data["members"], data["terms"])


def resolved(day, number, date):
    body = {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_{0}_body.txt".format(day)))}
    return qc.resolve_division(body[number], annex(day)[number], resolver(), date)


def by_surname(votes, surname, riding=None):
    r = resolver()
    out = []
    for v in votes:
        m = r.members.get(v["member_key"]) or {}
        if m.get("surname") == surname and (riding is None or riding in v["raw_label"]):
            out.append(v)
    return out


class _Client:
    """A stub HttpClient: GETs from a dict, POSTs from a list, both logged."""

    def __init__(self, gets=None, posts=None, robots=""):
        self.gets, self.posts, self.robots = dict(gets or {}), list(posts or []), robots
        self.user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
        self.throttle = 1.1
        self.log = []

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        self.log.append(("GET", url))
        if url.endswith("/robots.txt"):
            return self.robots
        if url in self.gets:
            return self.gets[url]
        raise FetchError(url, feed, slug, 1, "404")

    def get_bytes(self, url, feed, slug, archive=True):
        self.log.append(("GET", url))
        if url in self.gets:
            return self.gets[url]
        raise FetchError(url, feed, slug, 1, "404")

    def post_form(self, url, fields, feed, slug):
        self.log.append(("POST", url, dict(fields).get(qc.MONTH_FIELD)))
        if not self.posts:
            raise FetchError(url, feed, slug, 1, "no more")
        return self.posts.pop(0)


def _ctx(client, since=None, until=None, conn=None):
    conn = conn or db.init_db(db.connect(":memory:"))
    return Context(conn, client, "qc", since=since, until=until, log=lambda *_: None)


# -- the sitting index ---------------------------------------------------------

class SittingIndexTests(unittest.TestCase):
    def test_the_listing_gives_the_pv_urls_ids_and_all(self):
        page = fx("qc_sittings_43-2.html")
        months, shown = qc.month_options(page)
        self.assertEqual(shown, "202604")
        self.assertIn("202510", months)
        rows = qc.parse_sittings(page)
        self.assertEqual([r["date"] for r in rows], ["2026-04-02", "2026-04-01"])
        apr1 = rows[1]
        # The id is taken from the listing; it cannot be guessed.
        self.assertIn("DocumentGenerique_220051", apr1["pv_url"])
        self.assertTrue(apr1["jd_url"].endswith("/43-2/journal-debats/20260401/431619.html"))

    def test_the_month_form_is_the_pages_own(self):
        fields = dict(qc.form_fields(fx("qc_sittings_43-2.html"), "202510"))
        self.assertEqual(fields[qc.MONTH_FIELD], "202510")
        self.assertEqual(fields[qc.MONTH_BUTTON], "Rechercher")
        self.assertTrue(fields["__VIEWSTATE"].startswith("/wEP"))
        self.assertIn("__EVENTVALIDATION", fields)
        # The session select keeps the page's own selected value.
        self.assertTrue(fields["ctl00$ColCentre$ContenuColonneGauche$ddlChoixSession"].endswith("/43-2/index.html"))

    def test_an_extraordinary_sitting_is_a_sitting(self):
        rows = qc.parse_sittings(fx("qc_sittings_42-1_201906.html"))
        june16 = [r for r in rows if r["date"] == "2019-06-16"][0]
        self.assertTrue(june16["extraordinary"])
        self.assertIn("DocumentGenerique_146807", june16["pv_url"])
        self.assertEqual(len(rows), 11)

    def test_only_months_in_the_window_are_asked_for(self):
        url = qc.SITTINGS.format(43, 2)
        client = _Client(gets={url: fx("qc_sittings_43-2.html")})
        ctx = _ctx(client, since="2026-04-01", until="2026-04-30")
        records, pages = qc.list_records(ctx, 43, 2)
        self.assertEqual(pages, 1)
        self.assertFalse([e for e in client.log if e[0] == "POST"])
        self.assertEqual([r["date"] for r in records], ["2026-04-01", "2026-04-02"])

    def test_a_reply_for_the_wrong_month_is_a_gap_never_a_listing(self):
        url = qc.SITTINGS.format(43, 2)
        # The server answers the October 2025 request with the June 2019 page.
        client = _Client(gets={url: fx("qc_sittings_43-2.html")},
                         posts=[fx("qc_sittings_42-1_201906.html")])
        ctx = _ctx(client, since="2025-10-01", until="2025-10-31")
        records, _ = qc.list_records(ctx, 43, 2)
        self.assertEqual(records, [])
        self.assertTrue(any("asked for month 202510" in g for g in ctx.gaps))


# -- robots.txt ------------------------------------------------------------------

class RobotsTests(unittest.TestCase):
    """assnat.qc.ca writes one 'User-agent: *' group per rule. The standard
    library parser keeps only the first, and reported /json/ ALLOWED."""

    def setUp(self):
        self.rules = star_rules(fx("qc_robots.txt"), "CitizenGO-ParlMonitor/1.0 (contact: x)")

    def test_the_vote_register_feed_is_disallowed(self):
        self.assertFalse(rule_allows(self.rules, "https://www.assnat.qc.ca/json/RegistreVotes.json"))
        self.assertFalse(rule_allows(self.rules, "https://www.assnat.qc.ca/media/x.pdf"))
        self.assertFalse(rule_allows(self.rules, "https://www.assnat.qc.ca/fr/recherche/x.html"))

    def test_the_six_named_documents_are_disallowed_literally(self):
        url = ("https://www.assnat.qc.ca/Media/Process.aspx?MediaId=ANQ.Vigie.Bll.DocumentGenerique_103903"
               "&process=Default&token=ZyMoxNwUn8ikQ+TRKYwPCjWrKwg+vIv9rjij7p3xLGTZDmLVSmJLoqe/vG7/YWzz")
        self.assertFalse(rule_allows(self.rules, url))

    def test_the_proces_verbaux_and_listings_are_allowed(self):
        self.assertTrue(rule_allows(self.rules, "https://www.assnat.qc.ca/Media/Process.aspx?MediaId=ANQ.Vigie."
                                                "Bll.DocumentGenerique_220051&process=Default&token=Z"))
        self.assertTrue(rule_allows(self.rules, qc.SITTINGS.format(43, 2)))
        self.assertTrue(rule_allows(self.rules, qc.DEPCIR))

    def test_the_context_refuses_json_and_records_the_gap(self):
        ctx = _ctx(_Client(robots=fx("qc_robots.txt")))
        self.assertIsNone(ctx.text("https://www.assnat.qc.ca/json/x.json", "x"))
        self.assertTrue(any("robots.txt disallows" in g for g in ctx.gaps))

    def test_a_group_for_another_robot_is_not_ours(self):
        rules = star_rules("User-agent: PetalBot\nDisallow: /\n", "CitizenGO-ParlMonitor/1.0")
        self.assertTrue(rule_allows(rules, "https://www.assnat.qc.ca/fr/index.html"))


# -- the roster ------------------------------------------------------------------

class RosterTests(unittest.TestCase):
    def setUp(self):
        a, self.links = qc.parse_depcir(fx("qc_depcir_a.html"))
        s, self.links_s = qc.parse_depcir(fx("qc_depcir_s.html"))
        self.ridings = dict(a, **s)
        self.elections, self.numbers = qc.parse_elections(fx("qc_elections.html"))
        self.by = qc.parse_byelections(fx("qc_partielles.html"))
        self.gaps = []
        self.rows = qc.build_terms(self.ridings, self.elections, self.by, self.gaps, self.numbers)

    def terms(self, member_key):
        return sorted((t for k, m, t in self.rows if k == member_key), key=lambda t: t["start"])

    def test_the_letter_pages_link_each_other(self):
        self.assertEqual(self.links, ["b.html"])
        self.assertEqual(self.links_s, ["tz.html"])

    def test_a_compound_ridings_dash_is_kept(self):
        """depcir prints the en dash as '<sup>__</sup>'; a heading regex that
        stopped at the first tag filed Saint-Henri–Sainte-Anne's members
        under the riding before it."""
        self.assertIn("SAINT-HENRI–SAINTE-ANNE", self.ridings)
        self.assertEqual([r["surname"] for r in self.ridings["SAINT-HENRI–SAINTE-ANNE"]][-4:],
                         ["ANGLADE", "ANGLADE", "ANGLADE", "CLICHE-RIVARD"])

    def test_legislatures_are_counted_from_1867(self):
        """1867's poll is 'Août-septembre 1867' -- no date, still the 1st."""
        self.assertEqual(self.numbers[self.elections[2018]], 42)
        self.assertEqual(self.numbers[self.elections[2022]], 43)

    def test_a_resignation_ends_a_term_and_a_by_election_starts_one(self):
        blais = self.terms("1263")
        self.assertEqual(blais[-1]["end"], "2015-09-15")             # démissionne le 15-09-2015
        anglade = self.terms("16499")
        self.assertEqual(anglade[0]["start"], "2015-11-09")           # partielles.html
        self.assertEqual(anglade[0]["end"], "2018-09-30")             # the day before the 2018 poll
        # Her 2022 term ends the day before her successor's by-election.
        self.assertEqual(anglade[-1]["end"], "2023-03-12")
        cliche = [t for k, m, t in self.rows if m["surname"] == "Cliche-Rivard"]
        self.assertEqual((cliche[0]["start"], cliche[0]["end"]), ("2023-03-13", None))  # no later poll listed

    def test_party_is_the_party_elected_under_and_never_dated(self):
        dufour = self.terms("17823")
        self.assertEqual({t["party"] for t in dufour}, {"CAQ"})
        self.assertTrue(all(t["party_dated"] == 0 for k, m, t in self.rows))
        r = pn.Resolver({k: m for k, m, t in self.rows}, [dict(t, member_key=k) for k, m, t in self.rows])
        self.assertIsNone(r.party_at("17823", "2026-04-01"))

    def test_the_current_roster_keeps_real_case(self):
        cur = qc.parse_current_roster(fx("qc_roster.html"))
        self.assertEqual(cur["17847"][0], "LeBel")
        self.assertEqual(cur["4131"][:4], ("Legault", "François", "L'Assomption", "Coalition avenir Québec"))
        self.assertTrue(cur["4131"][4].endswith("/fr/deputes/legault-francois-4131/index.html"))

    def test_a_link_with_markup_inside_is_still_a_member(self):
        """Marie-Victorin's 2016 and 2018 rows wrap the name in a span. The
        first pattern dropped them silently and 'Fournier (IND)' failed the
        tally in 24 divisions of June 2019."""
        page = ('<h3 class="textAligneCentre"><a class="ancreNommee" name="mvic"></a>MARIE-VICTORIN</h3>'
                '<table><tr><td>2016</td><td><a href="https://www.assnat.qc.ca/fr/deputes/fournier-catherine-16775/'
                'index.html"><span class="nomDepute">FOURNIER, Catherine</span></a><a href="https://www.assnat.qc.ca/'
                'fr/deputes/fournier-catherine-16775/index.html"><span class="nomDepute"><br /></span></a></td>'
                '<td>Parti québécois</td><td>&nbsp;</td></tr>'
                '<tr><td>2025&nbsp;(élection partielle)</td><td>BOISSONNEAULT, Alex</td><td>Parti québécois</td>'
                '<td>&nbsp;</td></tr>'
                '<tr><td>1989</td><td>(Voir Salaberry-Soulanges)</td><td>&nbsp;</td><td>&nbsp;</td></tr>'
                '<tr><td>2026</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr></table>')
        rows = qc.parse_depcir(page)[0]["MARIE-VICTORIN"]
        self.assertEqual((rows[0]["member_id"], rows[0]["surname"], rows[0]["given"]), ("16775", "FOURNIER", "Catherine"))
        # printed without a link: kept, keyed later by name; a cross-reference is not a member
        self.assertEqual((rows[1]["member_id"], rows[1]["surname"], rows[1]["by_election"]), (None, "BOISSONNEAULT", True))
        self.assertEqual(rows[2]["unparsed"], "")                      # an empty row is said, not skipped
        self.assertEqual(len(rows), 3)
        gaps = []
        qc.build_terms({"MARIE-VICTORIN": rows}, self.elections, self.by, gaps, self.numbers)
        self.assertTrue(any("no member link" in g for g in gaps))

    def test_a_heading_with_the_letters_anchor_is_still_a_riding(self):
        """FABRE's heading carries '<a name="f"></a>' first; read as part of
        the previous riding, Gilles Ouimet sat for Duplessis."""
        page = ('<h3 class="textAligneCentre"><a class="ancreNommee" name="dupl"></a>DUPLESSIS</h3><table>'
                '<tr><td>2012</td><td><a href="https://www.assnat.qc.ca/fr/deputes/richard-lorraine-1335/index.html">'
                'RICHARD, Lorraine</a></td><td>Parti québécois</td><td>&nbsp;</td></tr></table>'
                '<h3 class="textAligneCentre"><a name="f"></a><a class="ancreNommee" name="fabr"></a>FABRE</h3><table>'
                '<tr><td>2012</td><td><a href="https://www.assnat.qc.ca/fr/deputes/ouimet-gilles-12245/index.html">'
                'OUIMET, Gilles</a></td><td>Libéral</td><td>démissionne le 24-08-2015</td></tr></table>')
        ridings = qc.parse_depcir(page)[0]
        self.assertEqual([r["surname"] for r in ridings["FABRE"]], ["OUIMET"])
        self.assertEqual([r["surname"] for r in ridings["DUPLESSIS"]], ["RICHARD"])

    def test_years_running_backwards_are_a_gap_never_terms(self):
        rows = [{"year": y, "by_election": False, "member_id": k, "surname": s, "given": "X", "party": "Libéral",
                 "remark": ""} for y, k, s in ((2012, "1", "RICHARD"), (2014, "1", "RICHARD"), (2012, "2", "OUIMET"))]
        gaps = []
        self.assertEqual(qc.build_terms({"DUPLESSIS": rows}, self.elections, self.by, gaps, self.numbers), [])
        self.assertIn("years run backwards", gaps[0])

    def test_a_former_members_prose_biography(self):
        page = ("<p>Élu député libéral dans Fabre en 2012. Réélu en 2014. Président de la Commission des "
                "institutions du 2 juin 2014 au 24 août 2015, date de sa démission.</p>"
                "<p>Élu député de Terrebonne pour la Coalition avenir Québec en 2018. Réélu en 2022.</p>")
        mandates, left = qc.parse_bio_mandates(page, self.elections)
        self.assertEqual(mandates[:2], [("Fabre", "2012-09-04", False), ("Fabre", "2014-04-07", False)])
        self.assertEqual(mandates[-1], ("Terrebonne", "2022-10-03", False))
        self.assertEqual(left, "2015-08-24")
        one, left = qc.parse_bio_mandates(page.split("</p>")[0], self.elections)
        terms = qc.mandate_terms(one, self.elections, "PLQ", self.numbers, left=left)
        self.assertEqual(terms[-1]["end"], "2015-08-24")

    def test_a_name_without_a_link_takes_the_current_rosters_id(self):
        ridings = {"ARTHABASKA": [{"year": 2025, "by_election": True, "member_id": None, "surname": "BOISSONNEAULT",
                                   "given": "Alex", "party": "Parti québécois", "remark": ""}]}
        qc.link_ids(ridings, {"19999": ("Boissonneault", "Alex", "Arthabaska", "Parti québécois", "u")})
        self.assertEqual(ridings["ARTHABASKA"][0]["member_id"], "19999")
        ridings["ARTHABASKA"][0]["member_id"] = None
        qc.link_ids(ridings, {})
        self.assertEqual(ridings["ARTHABASKA"][0]["member_id"], "x-boissonneault-alex")

    def test_a_sitting_member_missing_from_depcir_is_dated_from_their_page(self):
        """depcir has no 2022 row for Vanier-Les Rivières and nothing for the
        2025 Terrebonne by-election; the member page prints both."""
        page = ("<p>Fonctions politiques, parlementaires et ministérielles</p><p>Élue députée de la "
                "circonscription de Terrebonne aux élections partielles du 17 mars 2025</p>"
                "<p>Réélu député de la circonscription de Vanier-Les Rivières aux élections générales du "
                "3 octobre 2022</p><p>Élu député de la circonscription de Vanier-Les Rivières aux élections "
                "générales du 1 octobre 2018</p>")
        mandates = qc.parse_mandates(page)
        self.assertEqual(mandates[0], ("Vanier-Les Rivières", "2018-10-01", False))
        self.assertEqual(mandates[-1], ("Terrebonne", "2025-03-17", True))
        terms = qc.mandate_terms(mandates[:2], self.elections, "CAQ", self.numbers)
        self.assertEqual([(t["start"], t["end"], t["legislature"]) for t in terms],
                         [("2018-10-01", "2022-10-02", 42), ("2022-10-03", None, 43)])

    def test_display_case_never_matters_for_matching(self):
        self.assertEqual(qc.display_case("SAINT-HENRI–SAINTE-ANNE"), "Saint-Henri–Sainte-Anne")
        self.assertEqual(qc.display_case("D'AMOURS"), "D'Amours")


# -- the procès-verbal ---------------------------------------------------------

class BodyTests(unittest.TestCase):
    def test_each_named_vote_with_its_printed_totals(self):
        votes = {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_20190616_body.txt"))}
        self.assertEqual(sorted(votes), [163, 164, 165])
        v = votes[165]
        self.assertEqual(v["totals"], {"Yea": 73, "Nay": 35, "Abstain": 0})
        self.assertEqual(v["result"], "La motion est adoptée")
        self.assertEqual(votes[164]["result"], "Le rapport amendé est adopté")
        self.assertEqual(votes[164]["bill_number"], "21")
        self.assertEqual(votes[163]["stage"], "Procédure législative d'exception")

    def test_the_stage_comes_from_the_annex_heading_first(self):
        a = annex("20190616")
        votes = {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_20190616_body.txt"))}
        self.assertEqual(qc.stage_of(votes[165]["question"], a[165]["heading"]), "Adoption")
        self.assertEqual(qc.stage_of(votes[164]["question"], a[164]["heading"]), "Prise en considération du rapport")
        b13 = {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_20131029_body.txt"))}
        self.assertEqual(qc.stage_of(b13[64]["question"], annex("20131029")[64]["heading"]), "Adoption du principe")
        self.assertEqual(b13[64]["bill_number"], "52")


class AnnexTests(unittest.TestCase):
    def test_counts_and_lists(self):
        a = annex("20190616")
        self.assertEqual({n: {p: len(l) for p, l in v["labels"].items()} for n, v in a.items()},
                         {163: {"Yea": 63, "Nay": 42}, 164: {"Yea": 73, "Nay": 35},
                          165: {"Yea": 73, "Nay": 35}})
        self.assertEqual(a[165]["counts"], {"Yea": 73, "Nay": 35})

    def test_a_riding_wraps_under_its_own_column(self):
        """Text stream: 'Lamontagne (CAQ) (Soulanges)'. Column: Picard's."""
        labels = annex("20190616")[165]["labels"]["Yea"]
        self.assertIn("Picard (CAQ) (Soulanges)", labels)
        self.assertIn("Lamontagne (CAQ)", labels)
        self.assertIn("Blais (CAQ) (Prévost)", labels)
        self.assertIn("Blais (CAQ) (Abitibi-Ouest)", labels)
        self.assertIn("Tardif (CAQ) (Rivière-du-Loup–Témiscouata)", labels)

    def test_layout_spacing_is_repaired_from_the_plain_text(self):
        """29 October 2013: layout mode reads "D 'A mour", the text "D'Amour"."""
        nays = annex("20131029")[64]["labels"]["Nay"]
        self.assertIn("D'Amour (PLQ)", nays)
        self.assertEqual(len(nays), 26)

    def test_a_long_name_wrapped_inside_its_cell(self):
        """30 October 2025: "Lakhoyan Olivier" on one line, "(PLQ)" under
        it. Read as prose, it ended the list at 31 names of 98."""
        v = annex("20251030")[52]
        self.assertEqual((v["counts"]["Yea"], len(v["labels"]["Yea"])), (98, 98))
        for label in ("Lakhoyan Olivier (PLQ)", "St-Pierre Plamondon (PQ)", "Champagne Jourdain (CAQ)",
                      "Bélanger (CAQ) (Prévost)", "Dufour (PLQ) (Mille-Îles)"):
            self.assertIn(label, v["labels"]["Yea"])

    def test_a_cell_that_swallows_its_neighbour_is_cut_at_the_column(self):
        """6 April 2023: a fragment's recorded end ran on, and the gap rule
        read "Champagne Jourdain Guillemette (CAQ)" as one cell. Name rows
        are re-cut where the grid's columns start."""
        v = annex("20230406")[65]
        self.assertEqual({p: len(l) for p, l in v["labels"].items()}, {"Yea": 28, "Nay": 74, "Abstain": 1})
        self.assertIn("Champagne Jourdain (CAQ)", v["labels"]["Nay"])
        self.assertIn("Guillemette (CAQ)", v["labels"]["Nay"])

    def test_a_stray_start_is_not_a_column(self):
        xs = [0.0] * 20 + [110.5] * 20 + [221.2] * 19 + [331.7] * 18 + [169.8]
        self.assertEqual(qc._edges(xs), [0.0, 110.5, 221.2, 331.7])

    def test_an_annex_without_its_heading(self):
        """14 June 2019 prints no "ANNEXE": the named votes start on a fresh
        page at "Sur la motion de M. Bonnardel ... (Vote n° 153)"."""
        v = annex("20190614")[153]
        self.assertEqual((v["counts"]["Yea"], len(v["labels"]["Yea"])), (110, 110))
        self.assertIn("Bonnardel", v["heading"])

    def test_identical_to_an_earlier_vote(self):
        """2 June 2023: vote 110 is printed as '(Identique au vote n° 109)'."""
        def frag(x, y, text):
            return (x, y, x + 5.0 * len(text), text)
        page = [frag(170, 700, "ANNEXE"), frag(100, 680, "Sur l’amendement de Mme Maccarone :"),
                frag(160, 660, "(Vote n° 109)"), frag(170, 640, "POUR - 2"),
                frag(0, 620, "Arseneau (PQ)"), frag(110.5, 620, "Ghazal (QS)"),
                frag(170, 600, "CONTRE - 1"), frag(0, 580, "Legault (CAQ)"),
                frag(100, 560, "Sur l’amendement de M. Arseneau :"),
                frag(160, 540, "(Vote n° 110)"), frag(150, 520, "(Identique au vote n° 109)")]
        a = qc.parse_annex([page])
        self.assertEqual(a[110]["same_as"], 109)
        self.assertEqual(a[110]["labels"], {"Yea": ["Arseneau (PQ)", "Ghazal (QS)"], "Nay": ["Legault (CAQ)"]})
        self.assertEqual(a[110]["counts"], {"Yea": 2, "Nay": 1})
        self.assertIn("Arseneau", a[110]["heading"])

    def test_split_label(self):
        self.assertEqual(qc.split_label("Blais (CAQ) (Prévost)"), ("Blais (Prévost)", "CAQ"))
        self.assertEqual(qc.split_label("Perry Mélançon (PQ)"), ("Perry Mélançon", "PQ"))
        self.assertEqual(qc.split_label("no party here"), ("no party here", None))

    def test_the_real_pdf_page_electronic_vote(self):
        """The 1 April 2026 annex page, fonts stripped (14 KB): the pypdf
        layout interface is exercised for real, not only on fragments."""
        with open(os.path.join(FIX, "qc_pv_20260401_annex.pdf"), "rb") as fh:
            body, frags, plain = qc.split_pv(fh.read())
        a = qc.parse_annex(frags, plain)
        v = a[139]
        self.assertEqual({p: len(l) for p, l in v["labels"].items()}, {"Yea": 68, "Nay": 31, "Abstain": 1})
        self.assertEqual(v["counts"], {"Yea": 68, "Nay": 31, "Abstain": 1})
        self.assertEqual(v["labels"]["Abstain"], ["Dufour (IND) (Abitibi-Est)"])
        self.assertIn("Dufour (PLQ) (Mille-Îles)", v["labels"]["Nay"])
        self.assertIn("Dubé (IND)", v["labels"]["Yea"])
        self.assertIn("Bélanger (CAQ) (Prévost)", v["labels"]["Yea"])
        # The superscript "o" of "no" is set apart by the layout engine
        # ("... o proposant ... projet de loi n 1"): the bill number is
        # still read.
        self.assertEqual(qc._BILL_NO.findall(v["heading"]), ["1"])
        # No body vote line on an annex-only page: the totals are owed.
        self.assertEqual(qc.parse_pv_body(body), [])


class ProofTests(unittest.TestCase):
    def test_bill_21_adoption_73_35(self):
        votes, ok, note, printed = resolved("20190616", 165, "2019-06-16")
        self.assertTrue(ok, note)
        self.assertEqual(printed, {"Yea": 73, "Nay": 35, "Abstain": 0})
        legault = by_surname(votes, "Legault")[0]
        self.assertEqual((legault["position"], legault["party_at_vote"]), ("Yea", "CAQ"))
        self.assertEqual(by_surname(votes, "Jolin-Barrette")[0]["position"], "Yea")
        gnd = by_surname(votes, "Nadeau-Dubois")[0]
        self.assertEqual((gnd["position"], gnd["party_at_vote"]), ("Nay", "QS"))
        self.assertEqual(by_surname(votes, "Hivon")[0]["position"], "Yea")    # the PQ voted for
        self.assertEqual(by_surname(votes, "Arcand")[0]["position"], "Nay")

    def test_shared_surnames_are_told_apart_by_riding(self):
        votes, ok, _, _ = resolved("20190616", 165, "2019-06-16")
        blais = {v["raw_label"]: v["member_key"] for v in votes if v["raw_label"].startswith("Blais")}
        self.assertEqual(len(set(blais.values())), 2)
        self.assertTrue(all(blais.values()))

    def test_the_other_two_bill_21_votes(self):
        for number, want in ((163, (63, 42)), (164, (73, 35))):
            votes, ok, note, printed = resolved("20190616", number, "2019-06-16")
            self.assertTrue(ok, note)
            self.assertEqual((printed["Yea"], printed["Nay"]), want)

    def test_bill_52_principle_2013(self):
        votes, ok, note, printed = resolved("20131029", 64, "2013-10-29")
        self.assertTrue(ok, note)
        self.assertEqual((printed["Yea"], printed["Nay"]), (84, 26))
        self.assertEqual(by_surname(votes, "Hivon")[0]["position"], "Yea")
        self.assertEqual(by_surname(votes, "Couillard"), [])           # not a member yet

    def test_bill_11_adoption_2023(self):
        votes, ok, note, printed = resolved("20230607", 113, "2023-06-07")
        self.assertTrue(ok, note)
        self.assertEqual(printed, {"Yea": 103, "Nay": 2, "Abstain": 1})

    def test_a_missing_name_is_a_gap(self):
        body = {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_20190616_body.txt"))}
        a = annex("20190616")[165]
        a = dict(a, labels=dict(a["labels"], Yea=a["labels"]["Yea"][:-1]))
        _votes, ok, note, _ = qc.resolve_division(body[165], a, resolver(), "2019-06-16")
        self.assertFalse(ok)
        self.assertIn("Yea: 72 name(s) read, 73 printed", note)

    def test_an_unknown_name_is_null_never_guessed(self):
        body = {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_20190616_body.txt"))}
        a = annex("20190616")[165]
        yeas = list(a["labels"]["Yea"])
        yeas[0] = "Inconnu (CAQ)"
        votes, ok, note, _ = qc.resolve_division(body[165], dict(a, labels=dict(a["labels"], Yea=yeas)),
                                                 resolver(), "2019-06-16")
        self.assertFalse(ok)
        row = [v for v in votes if v["raw_label"] == "Inconnu (CAQ)"][0]
        self.assertIsNone(row["member_key"])
        self.assertEqual(row["party_at_vote"], "CAQ")             # as printed, even unresolved

    def test_the_annex_count_must_agree_with_the_body(self):
        body = {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_20190616_body.txt"))}
        a = annex("20190616")[165]
        _v, ok, note, _ = qc.resolve_division(body[165], dict(a, counts={"Yea": 74, "Nay": 35}),
                                              resolver(), "2019-06-16")
        self.assertFalse(ok)
        self.assertIn("annex says Yea - 74", note)

    def test_a_vote_with_no_annex_list_is_a_gap(self):
        body = {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_20190616_body.txt"))}
        _v, ok, note, _ = qc.resolve_division(body[165], None, resolver(), "2019-06-16")
        self.assertFalse(ok)
        self.assertIn("no annex list", note)

    def test_a_member_is_unknown_before_their_term(self):
        r = resolver()
        self.assertEqual(r.resolve("Legault", "2019-06-16")[0], "4131")
        # Dominique Anglade: by-election of 9 November 2015.
        self.assertIsNone(r.resolve("Anglade", "2015-06-01")[0])


# -- bills -------------------------------------------------------------------------

class BillTests(unittest.TestCase):
    def test_a_reinstated_bill_keeps_its_first_sessions_key(self):
        items = {i["number"]: i for i in qc.parse_bill_list(fx("qc_bills_43-2.html"))}
        self.assertEqual(items["94"]["key"], "qc-43-1/94")             # adopted in 43-2
        self.assertEqual(items["1"]["key"], "qc-43-2/1")
        self.assertIn("laïcité", items["9"]["title"])

    def test_stage_outcomes_from_the_bill_page(self):
        b = qc.parse_bill_page(fx("qc_bill_21-42-1.html"))
        self.assertEqual(b["author"], "Simon Jolin-Barrette")
        self.assertEqual(b["author_key"], "15359")
        self.assertIn("DocumentGenerique_143925", b["text_url"])
        stages = {s["stage"]: s["sittings"] for s in b["stages"]}
        self.assertEqual(stages["Adoption"][-1]["tally"], [73, 35, 0])
        self.assertEqual(stages["Adoption du principe"][-1]["tally"], [77, 38, 0])
        self.assertEqual(qc.voice_stages(b), [])
        self.assertEqual(qc.parse_en_title(fx("qc_bill_21-42-1_en.html")),
                         "An Act respecting the laicity of the State")

    def test_a_stage_without_a_named_vote_is_a_voice_decision(self):
        """Bill 11's principle (4 April 2023) has no 'Vote :' line."""
        b = qc.parse_bill_page(fx("qc_bill_11-43-1.html"))
        self.assertEqual([(s, x["date"]) for s, x in qc.voice_stages(b)],
                         [("Adoption du principe", "2023-04-04")])
        b94 = qc.parse_bill_page(fx("qc_bill_94-43-1.html"))
        self.assertEqual([(s, x["date"], x["note"]) for s, x in qc.voice_stages(b94)],
                         [("Prise en considération du rapport de commission", "2025-10-28",
                           "à la majorité des voix")])
        adoption = [s for s in b94["stages"] if s["stage"] == "Adoption"][0]["sittings"][-1]
        self.assertEqual((adoption["date"], adoption["session"], adoption["tally"]), ("2025-10-30", 2, [70, 27, 0]))

    def _division(self, conn, key, yeas, nays, bill=None):
        ps.store_division(conn, {"division_key": key, "prov": "qc", "legislature": 43, "session": 1,
                                 "date": "2023-06-02", "seq": key[-3:], "kind": "recorded", "bill_key": bill,
                                 "yeas": yeas, "nays": nays, "abstentions": 0, "positions_ok": 1,
                                 "areas": [], "votes": []})

    def _bill(self, conn):
        ps.store_bill(conn, {"bill_key": "qc-43-1/11", "prov": "qc", "legislature": 43, "session": 1,
                             "number": "11", "stages": [{"stage": "Prise en considération du rapport de commission",
                                                         "date": "2023-06-02", "tally": [107, 0, 0]}],
                             "areas": [2], "matched_terms": ["qc-43-1/11"], "tier": 1, "text_read": 1})

    def test_the_bill_pages_tally_joins_a_vote_the_pv_did_not_name(self):
        """'Sur le rapport de la Commission des relations avec les citoyens'
        names no bill; Bill 11's page says its report stage was 107-0 that
        day, and only one vote of that day was 107-0."""
        conn = db.init_db(db.connect(":memory:"))
        self._bill(conn)
        self._division(conn, "qc-43-1-2023-06-02-111", 107, 0)
        self._division(conn, "qc-43-1-2023-06-02-108", 93, 12)
        ctx = _ctx(_Client(), conn=conn)
        self.assertEqual(qc.check_bill_tallies(ctx, {"2023-06-02"}), 0)
        row = conn.execute("SELECT bill_key, stage, areas FROM prov_divisions WHERE division_key LIKE '%111'").fetchone()
        self.assertEqual(row[:2], ("qc-43-1/11", "Prise en considération du rapport de commission"))
        self.assertIn(2, json.loads(row[2]))
        self.assertIsNone(conn.execute("SELECT bill_key FROM prov_divisions WHERE division_key LIKE '%108'").fetchone()[0])

    def test_two_votes_with_the_same_totals_are_never_joined(self):
        conn = db.init_db(db.connect(":memory:"))
        self._bill(conn)
        self._division(conn, "qc-43-1-2023-06-02-111", 107, 0)
        self._division(conn, "qc-43-1-2023-06-02-112", 107, 0)
        ctx = _ctx(_Client(), conn=conn)
        self.assertEqual(qc.check_bill_tallies(ctx, {"2023-06-02"}), 1)
        self.assertTrue(any("named vote 107-0" in g for g in ctx.gaps))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_divisions WHERE bill_key IS NOT NULL").fetchone()[0], 0)

    def test_a_voice_decision_is_stored_as_such(self):
        conn = db.init_db(db.connect(":memory:"))
        ctx = _ctx(_Client(), conn=conn)
        qc.store_voice(ctx, "qc-43-1/11", qc.parse_bill_page(fx("qc_bill_11-43-1.html")),
                       "https://www.assnat.qc.ca/fr/travaux-parlementaires/projets-loi/projet-loi-11-43-1.html")
        row = conn.execute("SELECT kind, yeas, positions_ok, stage, result FROM prov_divisions").fetchone()
        self.assertEqual(row[:4], ("voice", None, None, "Adoption du principe"))
        self.assertIn("aucun vote par appel nominal", row[4])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_votes").fetchone()[0], 0)


# -- classification in French ----------------------------------------------------------

class FrenchClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.en = pc.load_taxonomy()
        cls.fr = pc.load_french_taxonomy("qc")
        cls.wl = pc.load_watchlist("qc")

    def areas(self, title=None, text=None):
        return pc.classify(self.en, self.wl, "qc", fr_tax=self.fr, fr_title=title,
                           fr_texts=[text] if text else []).areas

    def test_the_english_taxonomy_cannot_read_bill_21(self):
        self.assertEqual(pc.classify(self.en, self.wl, "qc", title="Loi sur la laïcité de l’État").areas, [])
        self.assertEqual(self.areas(title="Loi sur la laïcité de l’État"), [8])

    def test_the_measured_titles(self):
        for title, area in (
                ("Loi modifiant la Loi concernant les soins de fin de vie et d’autres dispositions législatives", 2),
                ("Loi visant à protéger les personnes contre les thérapies de conversion dispensées pour changer "
                 "leur orientation sexuelle, leur identité de genre ou leur expression de genre", 4),
                ("Loi visant à protéger l'accès aux établissements où se pratiquent des interruptions volontaires "
                 "de grossesse", 1),
                ("Loi instaurant une présomption de consentement au don d’organes ou de tissus après le décès", 13),
                ("Loi instituant l'union civile et établissant de nouvelles règles de filiation", 9),
                ("Loi modifiant diverses dispositions en matière de procréation assistée", 10),
                ("Loi sur la liberté académique dans le milieu universitaire", 7),
                ("Loi modifiant la Loi sur l'indemnisation des victimes d'actes criminels afin d'inclure les "
                 "notions d'exploitation sexuelle et de traite des personnes", 12),
                ("Loi visant à renforcer la lutte contre la transphobie et à améliorer notamment la situation des "
                 "mineurs transgenres", 3),
                ("Loi modifiant le Code civil dans le but de permettre à toute personne domiciliée au Québec "
                 "d’obtenir une modification de la mention du sexe figurant sur son acte de naissance", 5)):
            self.assertIn(area, self.areas(title=title), title)

    def test_the_traps(self):
        for title in (
                # 'conversion' of two mutual insurers (Bill 222, 2016)
                "Loi permettant la conversion de L'Assurance Mutuelle de l'Inter-Ouest et de l'Assurance "
                "mutuelle des fabriques de Montréal et leur fusion",
                # age checks for energy drinks are not online age verification (Bill 9, 2026)
                # (its text also says "en ligne": the first guard let it through)
                "Le projet de loi interdit de vendre une boisson énergisante à une personne de moins de 16 ans, "
                "y compris en ligne, et prévoit la vérification de l'âge de l'acheteur.",
                "Loi sur les services de garde éducatifs à l'enfance",
                "des mesures de tout genre pour le transport collectif"):
            self.assertEqual(self.areas(text=title), [], title)

    def test_a_cited_statute_is_masked_in_the_text(self):
        """An Act named with its chapter number is a citation, not a subject."""
        text = ("L’article 12 de la Loi concernant les soins de fin de vie (chapitre S-32.0001) est modifié "
                "par le remplacement de « 2024 » par « 2025 ».")
        self.assertEqual(self.areas(text=text), [])
        self.assertEqual(self.areas(title="Loi modifiant la Loi concernant les soins de fin de vie"), [2])

    def test_an_omnibus_bills_act_heading_is_masked(self):
        """Bill 37 (2020, government procurement) amends the neutrality Act
        under a capitalised heading with no chapter number."""
        text = ("LOI FAVORISANT LE RESPECT DE LA NEUTRALITÉ RELIGIEUSE DE L’ÉTAT ET VISANT\n"
                "NOTAMMENT À ENCADRER LES DEMANDES D’ACCOMMODEMENTS POUR UN MOTIF RELIGIEUX\n"
                "DANS CERTAINS ORGANISMES\n"
                "59. L’article 2 de cette loi est modifié par la suppression de « Infrastructures ».")
        self.assertEqual(self.areas(text=text), [])
        cited = "La Loi sur la laïcité de l’État (2019, chapitre 12) est modifiée par l’ajout de l’article 3."
        self.assertEqual(self.areas(text=cited), [])
        # pypdf's split capital in the "LOIS MODIFIÉES PAR CE PROJET DE LOI" list (Bills 23, 37 of 42-1)
        listed = ("LOIS MODIFIÉES PAR CE PROJET DE LOI : – L oi favorisant le respect de la neutralité religieuse "
                  "de l’État et visant notamment à encadrer les demandes d’accommodements pour un motif religieux "
                  "dans certains organismes (chapitre R-26.2.01);")
        self.assertEqual(self.areas(text=listed), [])
        # The same words as the subject of the bill's own prose still count.
        self.assertEqual(self.areas(text="Le projet de loi interdit le port d’un signe religieux."), [8])

    def test_a_pregnancy_benefit_and_a_spouse_definition_are_not_ours(self):
        """Tier 2 since the 42-1 sweep: Bill 51 (2020) parental insurance,
        Bill 84 (2021) victims of crime."""
        self.assertEqual(self.areas(text="si la grossesse se termine par une interruption de grossesse après "
                                         "la vingtième semaine, la prestation est versée"), [])
        self.assertEqual(self.areas(text="« conjoint » : la personne liée par un mariage ou par une union "
                                         "civile à une personne victime"), [])

    def test_decomposed_accents_still_match(self):
        import unicodedata
        nfd = unicodedata.normalize("NFD", "Loi sur la laïcité de l’État")
        self.assertEqual(self.areas(title=nfd), [8])

    def test_french_text_without_a_french_layer_is_refused(self):
        with self.assertRaises(ValueError):
            pc.classify(self.en, self.wl, "qc", fr_texts=["laïcité"])

    def test_a_watched_key_gives_tier_1(self):
        res = pc.classify(self.en, self.wl, "qc", bill_key="qc-43-1/11", fr_tax=self.fr)
        self.assertEqual((res.areas, res.tier), ([2], 1))


# -- one sitting end to end --------------------------------------------------------------

class SittingTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        data = json.loads(fx("qc_terms.json"))
        for key, m in data["members"].items():
            ps.upsert_member(self.conn, "qc", key, name=m["name"], surname=m["surname"], given=m["given"])
            ps.replace_terms(self.conn, "qc", key, [t for t in data["terms"] if t["member_key"] == key], "depcir")
        self.conn.commit()
        self.url = "https://www.assnat.qc.ca/Media/Process.aspx?MediaId=ANQ.Vigie.Bll.DocumentGenerique_146807"
        self.rec = {"date": "2019-06-16", "pv_url": self.url, "part": None}

    def _read(self, monkey=True):
        ctx = _ctx(_Client(gets={self.url: b"%PDF-stub"}), conn=self.conn)
        ctx.tax = pc.load_taxonomy()
        ctx.bill_map = {"21": "qc-42-1/21"}
        data = json.loads(fx("qc_pv_20190616_annex.json"))
        real = qc.split_pv
        if monkey:
            qc.split_pv = lambda raw: (fx("qc_pv_20190616_body.txt"),
                                       [[tuple(f) for f in p] for p in data["pages"]], data["plain"])
        try:
            got = qc.read_sitting(ctx, self.rec, 42, 1, pn.Resolver.from_conn(self.conn, "qc"),
                                  pc.load_french_taxonomy("qc"), pc.load_watchlist("qc"))
        finally:
            qc.split_pv = real
        return ctx, got

    def test_the_sitting_is_stored_with_three_trusted_divisions(self):
        ctx, (n, gaps) = self._read()
        self.assertEqual((n, gaps), (3, 0), ctx.gaps)
        rows = self.conn.execute("SELECT division_key, bill_key, stage, yeas, nays, positions_ok, areas "
                                 "FROM prov_divisions ORDER BY seq").fetchall()
        self.assertEqual(rows[2][:6], ("qc-42-1-2019-06-16-165", "qc-42-1/21", "Adoption", 73, 35, 1))
        self.assertIn(8, json.loads(rows[2][6]))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM prov_votes WHERE member_key IS NULL").fetchone()[0], 0)
        self.assertTrue(ps.sitting_done(self.conn, self.url))

    def test_a_truncated_pv_is_unreadable_and_owed(self):
        ctx, (n, gaps) = self._read(monkey=False)
        self.assertEqual((n, gaps), (0, 1))
        self.assertFalse(ps.sitting_done(self.conn, self.url))
        self.assertTrue(any("not a PDF" in g or "truncated" in g for g in ctx.gaps))


class MemberPagesTests(unittest.TestCase):
    """The two roster holes a procès-verbal exposes, closed from members' own
    pages and nothing else."""

    ROY_N = "https://www.assnat.qc.ca/fr/deputes/roy-nathalie-12187/index.html"
    ROY_S = "https://www.assnat.qc.ca/fr/deputes/roy-suzanne-19265/index.html"
    FITZ = "https://www.assnat.qc.ca/fr/deputes/fitzgibbon-pierre-17837/index.html"

    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))
        for key, given, riding, url in (("12187", "Nathalie", "Montarville", self.ROY_N),
                                        ("19265", "Suzanne", "Verchères", self.ROY_S)):
            ps.upsert_member(self.conn, "qc", key, name=given + " Roy", surname="Roy", given=given,
                             party="CAQ", page_url=url)
            ps.replace_terms(self.conn, "qc", key, [{"legislature": 43, "party": "CAQ", "riding": riding,
                                                     "start": "2022-10-03", "end": None}], "depcir")
        ps.upsert_member(self.conn, "qc", "17837", name="Pierre Fitzgibbon", surname="Fitzgibbon",
                         given="Pierre", party="CAQ", page_url=self.FITZ)
        ps.replace_terms(self.conn, "qc", "17837", [{"legislature": 42, "party": "CAQ", "riding": "Terrebonne",
                                                     "start": "2018-10-01", "end": "2022-10-02"}], "depcir")
        self.conn.commit()
        self.client = _Client(gets={
            self.ROY_N: "<p>Présidente de l’Assemblée nationale depuis le 29 novembre 2022</p>",
            self.ROY_S: "<p>Élue députée de la circonscription de Verchères aux élections générales du "
                        "3 octobre 2022</p>",
            self.FITZ: "<p>Réélu député de la circonscription de Terrebonne aux élections générales du "
                       "3 octobre 2022</p><p>Élu député de la circonscription de Terrebonne aux élections "
                       "générales du 1 octobre 2018</p>",
            qc.ELECTIONS: fx("qc_elections.html")})
        self.pages = qc.MemberPages(_ctx(self.client, conn=self.conn), pn.Resolver.from_conn(self.conn, "qc"))

    def test_the_president_does_not_vote(self):
        """'Roy (CAQ)' in 2025-2026 is Suzanne Roy: Nathalie Roy presides."""
        self.assertTrue(self.pages.resolver.resolve("Roy", "2026-04-01")[1].startswith("ambiguous"))
        key, how = self.pages.resolve("Roy", "2026-04-01")
        self.assertEqual(key, "19265")
        self.assertIn("President", how)
        # Before her presidency the same label stays ambiguous: never a guess.
        self.assertIsNone(self.pages.resolve("Roy", "2022-11-01")[0])

    def test_a_missing_mandate_is_read_from_the_members_page(self):
        self.assertEqual(self.pages.resolver.resolve("Fitzgibbon", "2023-06-07")[0], None)
        key, how = self.pages.resolve("Fitzgibbon", "2023-06-07")
        self.assertEqual((key, how), ("17837", "surname (member page)"))
        sources = {r[0] for r in self.conn.execute(
            "SELECT source FROM prov_member_terms WHERE member_key='17837'")}
        self.assertEqual(sources, {"depcir", "member-page"})

    def test_an_initial_printed_as_part_of_the_name(self):
        """'H. Plante' (2014) is Marc H. Plante; his given-name initial is M."""
        ps.upsert_member(self.conn, "qc", "15405", name="Marc H. Plante", surname="Plante", given="Marc H.")
        ps.replace_terms(self.conn, "qc", "15405", [{"legislature": 41, "party": "PLQ", "riding": "Maskinongé",
                                                     "start": "2014-04-07", "end": "2018-09-30"}], "depcir")
        pages = qc.MemberPages(_ctx(self.client, conn=self.conn), pn.Resolver.from_conn(self.conn, "qc"))
        self.assertIsNone(pages.resolver.resolve("H. Plante", "2014-06-05")[0])
        self.assertEqual(pages.resolve("H. Plante", "2014-06-05")[0], "15405")
        self.assertIsNone(pages.resolve("H. Plante", "2019-06-05")[0])          # not sitting then

    def test_an_unknown_surname_fetches_nothing(self):
        self.assertIsNone(self.pages.resolve("Inconnu", "2023-06-07")[0])
        self.assertFalse([e for e in self.client.log if "deputes" in e[1]])

    def test_presidencies(self):
        self.assertEqual(qc.parse_presidencies("Président de l'Assemblée nationale du 27 novembre 2018 "
                                               "au 28 août 2022. Vice-président de l'Assemblée nationale"),
                         [("2018-11-27", "2022-08-28")])


# -- the 2010 backfill (CI run 37048289773, 2 October 2026) --------------------------------
#
# 294 tally gaps, 157 bill-page misses, 1,147 unresolved votes. Every fixture
# below is a real procès-verbal page, cut to the votes it proves.

def backfill_resolver():
    data = json.loads(fx("qc_terms_backfill.json"))
    return pn.Resolver(data["members"], data["terms"])


def body_votes(day):
    return {v["number"]: v for v in qc.parse_pv_body(fx("qc_pv_{0}_body.txt".format(day)))}


class BareAnnexTests(unittest.TestCase):
    """2008-2012: the annex prints surnames only, no party."""

    def test_2010_prints_whole_rows_as_one_fragment(self):
        """16 February 2010: "Arcand Charette Huot  Pelletier " is ONE
        fragment and ridings are in [brackets]; the old reader took the row
        for one name and stopped at the first bracket (1 name of 111)."""
        v = annex("20100216")[62]
        self.assertTrue(v["bare"])
        self.assertEqual((v["counts"], len(v["labels"]["Yea"])), ({"Yea": 111}, 111))
        for label in ("Arcand", "Pelletier (Rimouski)", "Bachand (Arthabaska)", "Bachand (Outremont)",
                      "Richard (Marguerite-D'Youville)", "Richard (Duplessis)", "Simard (Richelieu)"):
            self.assertIn(label, v["labels"]["Yea"])
        votes, ok, note, _ = qc.resolve_division(body_votes("20100216")[62], v, backfill_resolver(), "2010-02-16")
        self.assertTrue(ok, note)
        self.assertEqual({x["party_at_vote"] for x in votes}, {None})    # never printed, never invented

    def test_2011_glyph_runs_are_joined_from_the_plain_text(self):
        """9 June 2011: one fragment per name, but the layout engine splits
        "Dia mond" and "Si mard"; the plain text spells them whole."""
        v = annex("20110609")[36]
        self.assertEqual(len(v["labels"]["Yea"]), 112)
        self.assertIn("Diamond", v["labels"]["Yea"])
        self.assertEqual(sum(1 for x in v["labels"]["Yea"] if x.startswith("Simard (")), 3)
        votes, ok, note, _ = qc.resolve_division(body_votes("20110609")[36], v, backfill_resolver(), "2011-06-09")
        self.assertTrue(ok, note)

    def test_a_lone_riding_line_is_placed_by_its_seat(self):
        """11 February 2010: "  [Marguerite-D'Youville]" alone on its line,
        no x-position, read under Deltell; it is Monique Richard's seat, and
        "Richard" is the one bare Richard in the list."""
        votes, ok, note, _ = qc.resolve_division(body_votes("20100211")[61], annex("20100211")[61],
                                                 backfill_resolver(), "2010-02-11")
        self.assertTrue(ok, note)
        labels = {v["raw_label"] for v in votes}
        self.assertIn("Richard (Marguerite-D'Youville)", labels)
        self.assertIn("Deltell", labels)
        self.assertIn("placed under", note)

    def test_a_riding_in_the_wrong_column_finds_nobody(self):
        """A bare riding that lands under another surname resolves to nobody:
        the resolver requires the riding to be the member's own."""
        self.assertIsNone(backfill_resolver().resolve("Lessard (Duplessis)", "2010-02-16")[0])

    def test_a_label_without_party_is_read_only_in_a_bare_annex(self):
        v = {"counts": {"Yea": 1}, "labels": {"Yea": ["Arcand"]}}
        votes, ok, _, _ = qc.resolve_division({"totals": {"Yea": 1, "Nay": 0, "Abstain": 0}}, v,
                                              backfill_resolver(), "2010-02-16")
        self.assertEqual((votes[0]["how"], ok), ("unparsed label", False))

    def test_tokens(self):
        words = qc.plain_words("Dupuis Diamond Courcy")
        self.assertEqual(qc.bare_tokens("[Mirabel]   Dia mond De Courcy  [Marguerite-", words),
                         ["(Mirabel)", "Diamond", "De Courcy", "(Marguerite-"])


class AnnexLayoutTests(unittest.TestCase):
    def test_vote_no_with_a_full_stop(self):
        """23 March 2010: "(Vote No. 70)"."""
        self.assertEqual(len(annex("20100323")[70]["labels"]["Yea"]), 113)

    def test_every_party_closed_twice(self):
        """22 November 2012: "Arcand (PLQ))"."""
        v = annex("20121122")[10]
        self.assertEqual({p: len(l) for p, l in v["labels"].items()}, {"Yea": 62, "Nay": 47})
        self.assertIn("Arcand (PLQ)", v["labels"]["Yea"])

    def test_a_split_glyph_run_repeated_down_a_column_is_not_a_column(self):
        """4 December 2012: "St" / "-Amand (PLQ)" and "Po" / "ëti (PLQ)" on
        several rows cleared the 15 % floor as columns of their own."""
        v = annex("20121204")[13]
        self.assertEqual(len(v["labels"]["Nay"]), 65)
        for label in ("St-Amand (PLQ)", "St-Laurent (CAQ)", "St-Pierre (PLQ)", "Poëti (PLQ)"):
            self.assertIn(label, v["labels"]["Nay"])

    def test_every_party_doubled(self):
        """12 November 2014: "Arcand ((PLQ))"."""
        v = annex("20141112")[47]
        self.assertEqual({p: len(l) for p, l in v["labels"].items()}, {"Yea": 82, "Nay": 25})
        self.assertIn("Arcand (PLQ)", v["labels"]["Yea"])

    def test_a_missing_opening_bracket_on_a_list_with_no_heading(self):
        """7 October 2015, vote 136: no "POUR - 106" and "Arcand PLQ)"."""
        v = annex("20151007")[136]
        self.assertEqual(len(v["labels"][qc.UNHEADED]), 106)
        self.assertEqual(v["labels"][qc.UNHEADED][0], "Arcand (PLQ)")

    def test_a_scrambled_reference_is_read_from_the_plain_text(self):
        """21 April 2015: the layout reads vote 100's "(Identique au vote n°
        98)" as 89 -- a real, earlier vote of the session. The plain text's
        references replace the layout's; without the plain text a reference
        is not followed at all."""
        data = json.loads(fx("qc_pv_20150421_annex.json"))
        pages = [[tuple(f) for f in p] for p in data["pages"]]
        self.assertEqual(qc.parse_annex(pages, data["plain"])[100]["same_as"], 98)
        blind = qc.parse_annex(pages, "")
        self.assertEqual(blind[100]["same_as"], 89)
        conn = db.init_db(db.connect(":memory:"))
        ps.store_division(conn, {"division_key": "qc-41-1-2015-04-16-89", "prov": "qc", "legislature": 41,
                                 "session": 1, "date": "2015-04-16", "seq": 89, "kind": "recorded",
                                 "positions_ok": 1, "votes": [{"position": "Yea", "ordinal": 1,
                                                               "raw_label": "Arcand (PLQ)", "member_key": "1"}]})
        qc.earlier_lists(conn, blind, 41, 1)
        self.assertEqual(blind[100]["labels"], {})
        self.assertIn("not followed", blind[100]["earlier_note"])

    def test_identique_auvote(self):
        """13 June 2014: "(Identique auvote n° 16)"."""
        a = annex("20140613")
        self.assertEqual(a[19]["same_as"], 16)
        self.assertEqual(a[19]["labels"], a[16]["labels"])

    def test_a_vote_number_is_read_in_content_order(self):
        """14 February 2018: the layout engine put vote 421's "4" and "2" at
        one x-position and read 241; the plain text says 421."""
        a = annex("20180214")
        self.assertEqual(list(a), [421])

    def test_a_split_number_is_closed_up(self):
        """7 April 2022: "(Identique au vote n° 2 78)"."""
        self.assertEqual(annex("20220407")[294]["same_as"], 278)

    def test_a_list_with_no_position_heading(self):
        """13 May 2020: "Vote n° 310" (no brackets) and the 120 names under no
        "POUR - 120". Placed only because the body leaves no choice."""
        a, body = annex("20200513"), body_votes("20200513")
        self.assertEqual(a[309]["counts"], {"Yea": 120})
        self.assertEqual((a[310]["counts"], len(a[310]["labels"][qc.UNHEADED])), ({}, 120))
        votes, ok, note, _ = qc.resolve_division(body[310], a[310], resolver(), "2020-05-13")
        self.assertEqual(sum(1 for v in votes if v["position"] == "Yea"), 120)
        self.assertIn("no position heading", note)
        split = {"totals": {"Yea": 100, "Nay": 20, "Abstain": 0}}
        votes, ok, note, _ = qc.resolve_division(split, a[310], resolver(), "2020-05-13")
        self.assertFalse(ok)
        self.assertEqual(votes, [])

    def test_a_heading_printed_twice(self):
        """20 April 2021 heads two lists "(Vote n° 938)" before 940: the
        second is 939. Never merged into one list."""
        a = annex("20210420")
        self.assertEqual(sorted(a), [937, 938, 939, 940])
        self.assertEqual((a[938]["same_as"], a[939]["same_as"]), (936, 936))
        self.assertIn("read as vote 939", a[939]["renumbered"])

    def test_a_misnumbered_heading_takes_its_place_in_the_sequence(self):
        """9 June 2021 prints "(Vote n° 1002)" between 1101 and 1103."""
        a = annex("20210609")
        self.assertEqual(list(a), [1100, 1101, 1002])
        got, notes = qc.renumber_annex({**a, 1103: {"labels": {}}},set(range(1099, 1106)))
        self.assertIn(1102, got)
        self.assertNotIn(1002, got)
        self.assertIn("1002", notes[1102])
        # Not flanked by n-1 and n+1: left alone.
        got, notes = qc.renumber_annex(a, set(range(1099, 1106)))
        self.assertIn(1002, got)


class BodyNumberTests(unittest.TestCase):
    def test_a_number_printed_twice_in_the_body(self):
        """10 December 2021: "(Vote n° 180 en annexe)" for Bill 11 and again
        for Bill 9; the annex numbers Bill 9's vote 181."""
        votes, notes = qc.renumber_body(qc.parse_pv_body(fx("qc_pv_20211210_body.txt")), {179, 180, 181, 182})
        self.assertEqual([(v["number"], v["bill_number"]) for v in votes],
                         [(179, None), (180, "11"), (181, "9"), (182, "7")])
        self.assertIn(181, notes)
        # Without 181 in the annex nothing is renumbered.
        votes, notes = qc.renumber_body(qc.parse_pv_body(fx("qc_pv_20211210_body.txt")), {179, 180, 182})
        self.assertEqual([v["number"] for v in votes], [179, 180, 180, 182])


class RidingPlacementTests(unittest.TestCase):
    """12 February 2020, vote 289: the annex reads "Zanetti (QS) (Berthier)"
    and a bare "Proulx (CAQ)"; Berthier is Caroline Proulx's seat."""

    def setUp(self):
        members = {"17837": {"surname": "Proulx", "given": "Caroline", "name": "Caroline Proulx"},
                   "17915": {"surname": "Proulx", "given": "Marie-Eve", "name": "Marie-Eve Proulx"},
                   "19000": {"surname": "Zanetti", "given": "Sol", "name": "Sol Zanetti"}}
        terms = [{"member_key": k, "legislature": 42, "party": p, "riding": r, "start": "2018-10-01",
                  "end": "2022-10-02"} for k, p, r in (("17837", "CAQ", "Berthier"), ("17915", "CAQ", "Côte-du-Sud"),
                                                      ("19000", "QS", "Jean-Lesage"))]
        self.r = pn.Resolver(members, terms)

    def test_the_riding_goes_to_the_one_name_it_can_belong_to(self):
        annex_v = {"counts": {"Yea": 3}, "labels": {"Yea": ["Proulx (CAQ)", "Proulx (CAQ) (Côte-du-Sud)",
                                                             "Zanetti (QS) (Berthier)"]}}
        votes, ok, note, _ = qc.resolve_division({"totals": {"Yea": 3, "Nay": 0, "Abstain": 0}}, annex_v,
                                                 self.r, "2020-02-12")
        self.assertTrue(ok, note)
        got = {v["raw_label"]: (v["member_key"], v["party_at_vote"]) for v in votes}
        self.assertEqual(got["Proulx (CAQ) (Berthier)"], ("17837", "CAQ"))
        self.assertEqual(got["Zanetti (QS)"], ("19000", "QS"))

    def test_two_possible_takers_move_nothing(self):
        annex_v = {"counts": {"Yea": 3}, "labels": {"Yea": ["Proulx (CAQ)", "Proulx (CAQ)", "Zanetti (QS) (Berthier)"]}}
        _, ok, _, _ = qc.resolve_division({"totals": {"Yea": 3, "Nay": 0, "Abstain": 0}}, annex_v, self.r,
                                          "2020-02-12")
        self.assertFalse(ok)


class EarlierListTests(unittest.TestCase):
    """7 April 2022: "(Identique au vote n° 278)" names a vote of an earlier
    sitting."""

    def setUp(self):
        self.conn = db.init_db(db.connect(":memory:"))

    def _store(self, ok):
        ps.store_division(self.conn, {
            "division_key": "qc-42-2-2022-04-06-278", "prov": "qc", "legislature": 42, "session": 2,
            "date": "2022-04-06", "seq": 278, "kind": "recorded", "yeas": 1, "nays": 1,
            "positions_ok": 1 if ok else 0,
            "votes": [{"position": "Yea", "ordinal": 1, "raw_label": "Arcand (PLQ)", "member_key": "1"},
                      {"position": "Nay", "ordinal": 1, "raw_label": "Allaire (CAQ)", "member_key": "2"}]})

    def test_a_trusted_earlier_division_lends_its_list(self):
        self._store(True)
        a = annex("20220407")
        qc.earlier_lists(self.conn, a, 42, 2)
        self.assertEqual(a[294]["labels"], {"Yea": ["Arcand (PLQ)"], "Nay": ["Allaire (CAQ)"]})
        self.assertIn("2022-04-06", a[294]["earlier_note"])

    def test_an_untrusted_one_does_not(self):
        self._store(False)
        a = annex("20220407")
        qc.earlier_lists(self.conn, a, 42, 2)
        self.assertEqual(a[294]["labels"], {})
        self.assertIn("not a trusted division", a[294]["earlier_note"])


class BillNumberTests(unittest.TestCase):
    def test_presentation_and_private_bills(self):
        """The PV's own words (30 May 2019, vote 126; 26 May 2020, vote 315)."""
        q126 = ("M. Bonnardel, ministre des Transports, propose que l’Assemblée soit saisie du projet de loi "
                "suivant : n° 26 Loi concernant le Réseau structurant de transport en commun de la Ville de "
                "Québec La motion est adoptée. En conséquence, l’Assemblée est saisie du projet de loi n° 26. "
                "M. Gaudreault (Jonquière) propose que l’Assemblée soit saisie du projet de loi suivant : "
                "n° 391 Loi modif iant la Loi sur la qualité de l ’environnement")
        self.assertEqual(qc._BILL_NO.findall(q126)[-1], "391")
        q315 = ("propose que l’Assemblée soit saisie du projet de loi d’intérêt privé n° 211, L oi "
                "concernant SSQ mutuelle.")
        self.assertEqual(qc._BILL_NO.findall(q315), ["211"])


class PageTermTests(unittest.TestCase):
    """France Dionne (member 1985-1997): "Élue en 2019 vice-présidente de
    l'Amicale des anciens parlementaires ..., puis présidente en 2022" gave
    her a 43rd-legislature term, and every "Dionne (CAQ)" of 2022-2026
    became ambiguous with Amélie Dionne."""

    URL = "https://www.assnat.qc.ca/fr/deputes/dionne-france-2911/index.html"

    def test_an_association_is_not_a_mandate(self):
        elections, _ = qc.parse_elections(fx("qc_elections.html"))
        mandates, _ = qc.parse_bio_mandates(fx("qc_member_dionne_2911.html"), elections)
        self.assertEqual([m[1][:4] for m in mandates], ["1985", "1989", "1994"])

    def test_a_stale_page_term_is_re_read_with_the_roster(self):
        conn = db.init_db(db.connect(":memory:"))
        ps.upsert_member(conn, "qc", "2911", name="France Dionne", surname="Dionne", given="France",
                         party="PLQ", page_url=self.URL)
        ps.replace_terms(conn, "qc", "2911", [{"legislature": 35, "party": "PLQ", "riding": "Kamouraska-Témiscouata",
                                               "start": "1994-09-12", "end": "1997-05-02"}], "depcir")
        ps.replace_terms(conn, "qc", "2911", [{"legislature": 43, "party": "PLQ", "riding": "Kamouraska-Témiscouata",
                                               "start": "2022-10-03", "end": None}], "member-page")
        ctx = _ctx(_Client(gets={self.URL: fx("qc_member_dionne_2911.html")}), conn=conn)
        elections, legislatures = qc.parse_elections(fx("qc_elections.html"))
        self.assertEqual(qc.recheck_page_terms(ctx, elections, legislatures), 1)
        self.assertIsNone(pn.Resolver.from_conn(conn, "qc").term_for("2911", "2024-01-01"))


class OwedTests(unittest.TestCase):
    def test_a_day_with_a_missed_bill_vote_is_read_again_once(self):
        conn = db.init_db(db.connect(":memory:"))
        ps.store_bill(conn, {"bill_key": "qc-42-1/391", "prov": "qc", "legislature": 42, "session": 1,
                             "number": "391", "stages": [{"stage": "Présentation", "date": "2019-05-30",
                                                          "tally": [110, 0, 0]}]})
        old = "https://x/pv-old"
        ps.store_sitting(conn, "qc", "qc-42-1-2019-05-30", "2019-05-30", old, status="ok", when="2026-10-02")
        ps.store_sitting(conn, "qc", "qc-42-1-2019-05-31", "2019-05-31", "https://x/b", status="ok",
                         when="2026-10-02")
        recs = [{"date": "2019-05-30", "pv_url": old}, {"date": "2019-05-31", "pv_url": "https://x/b"}]
        ctx = _ctx(_Client(), conn=conn)
        self.assertEqual(qc.owe_missed(ctx, 42, 1, recs), 1)
        self.assertFalse(ps.sitting_done(conn, old))
        # Read again today and still missed: not owed a second time.
        ps.store_sitting(conn, "qc", "qc-42-1-2019-05-30", "2019-05-30", old, status="ok")
        self.assertEqual(qc.owe_missed(ctx, 42, 1, recs), 0)


class ReviewedQuebecTests(unittest.TestCase):
    """Facts from the Journal des débats, scoped to one division."""

    def setUp(self):
        members = {"655": {"surname": "Picard", "given": "Marc", "name": "Marc Picard"},
                   "17891": {"surname": "Picard", "given": "Marilyne", "name": "Marilyne Picard"}}
        terms = [{"member_key": "655", "legislature": 42, "party": "CAQ", "riding": "Chutes-de-la-Chaudière",
                  "start": "2018-10-01", "end": "2022-10-02"},
                 {"member_key": "17891", "legislature": 42, "party": "CAQ", "riding": "Soulanges",
                  "start": "2018-10-01", "end": "2022-10-02"}]
        self.r = pn.Resolver(members, terms)
        self.annex = {"counts": {"Nay": 1}, "labels": {"Nay": ["Picard (CAQ)"]}}

    def test_a_bare_surname_settled_by_the_roll_call(self):
        rev = pn.ReviewedDivisions({"hansard_labels": [{
            "division": "qc-42-1-2020-12-08-650", "position": "Nay", "printed": "Picard (CAQ)",
            "member": "17891", "quoted": "Mme Picard (Soulanges)"}]})
        body = {"totals": {"Yea": 0, "Nay": 1, "Abstain": 0}}
        votes, ok, _, _ = qc.resolve_division(body, self.annex, self.r, "2020-12-08")
        self.assertFalse(ok)
        votes, ok, note, _ = qc.resolve_division(body, self.annex, self.r, "2020-12-08", reviewed=rev,
                                                 division_key="qc-42-1-2020-12-08-650")
        self.assertTrue(ok, note)
        self.assertEqual((votes[0]["member_key"], votes[0]["party_at_vote"]), ("17891", "CAQ"))
        # Another division of the same day is not touched.
        votes, ok, _, _ = qc.resolve_division(body, self.annex, self.r, "2020-12-08", reviewed=rev,
                                              division_key="qc-42-1-2020-12-08-651")
        self.assertFalse(ok)

    def test_a_body_total_replaced_only_while_it_prints_the_misprint(self):
        annex_v = {"counts": {"Yea": 2}, "labels": {"Yea": ["Picard (CAQ) (Soulanges)",
                                                             "Picard (CAQ) (Chutes-de-la-Chaudière)"]}}
        rev = pn.ReviewedDivisions({"hansard_totals": [{
            "division": "d", "position": "Yea", "total": 2, "replaces": 1, "quoted": "Pour : 2"}]})
        votes, ok, note, printed = qc.resolve_division({"totals": {"Yea": 1, "Nay": 0, "Abstain": 0}}, annex_v,
                                                       self.r, "2020-12-08", reviewed=rev, division_key="d")
        self.assertTrue(ok, note)
        self.assertEqual(printed["Yea"], 2)
        self.assertIn("replaces the record's printed 1", note)
        _, ok, _, _ = qc.resolve_division({"totals": {"Yea": 3, "Nay": 0, "Abstain": 0}}, annex_v,
                                          self.r, "2020-12-08", reviewed=rev, division_key="d")
        self.assertFalse(ok)


class MisprintTests(unittest.TestCase):
    """"Charrette" for Benoit Charette (config/prov_record.yaml, misprints):
    only in a procès-verbal, only inside the reviewed span."""

    PV = "https://www.assnat.qc.ca/Media/Process.aspx?MediaId=ANQ.Vigie.Bll.DocumentGenerique_34721&process=Default"

    def setUp(self):
        conn = db.init_db(db.connect(":memory:"))
        ps.upsert_member(conn, "qc", "195", name="Benoit Charette", surname="Charette", given="Benoit")
        ps.replace_terms(conn, "qc", "195", [{"legislature": 39, "party": "PQ", "riding": "Deux-Montagnes",
                                              "start": "2008-12-08", "end": "2012-09-03"}], "depcir")
        self.pages = qc.MemberPages(_ctx(_Client(), conn=conn), pn.Resolver.from_conn(conn, "qc"))

    def test_inside_the_span_in_a_pv(self):
        self.assertEqual(self.pages.resolve("Charrette", "2010-05-18", document=self.PV)[0], "195")

    def test_outside_the_span_or_without_the_document(self):
        self.assertIsNone(self.pages.resolve("Charrette", "2011-05-18", document=self.PV)[0])
        self.assertIsNone(self.pages.resolve("Charrette", "2010-05-18")[0])


class RunnerTests(unittest.TestCase):
    def test_quebec_is_built(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import prov_collect
        self.assertEqual(prov_collect.module_for("qc").PROV, "qc")


if __name__ == "__main__":
    unittest.main()
