"""The weekly country editions (src/country_edition.py), the shared noise
filters (src/noise.py) and the Austrian, Dutch, Belgian and Polish adapters
(src/editions/), on small stores built here."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country_edition as ce  # noqa: E402
from src import noise  # noqa: E402

TODAY = "2026-10-09"
SINCE = "2026-10-02"


def conn_with(*stores):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for store in stores:
        store.ensure_schema(conn)
    return conn


def fake(items, **kw):
    base = dict(cc="xx", name="Testland", chamber="Diet", language="Testish",
                taxonomies=(("taxonomy-nl.yaml", "nl"),), items=lambda *a: list(items))
    base.update(kw)
    return ce.Country(**base)


class Base(unittest.TestCase):
    def setUp(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        self.eds = os.path.join(self.tmp, "editions")
        os.makedirs(self.cfg)
        os.makedirs(self.eds)

    def tearDown(self):
        noise.load_yaml.__globals__["_FILES"].clear()
        shutil.rmtree(self.tmp)

    def copy(self, name):
        shutil.copy(os.path.join(ROOT, "config", name), self.cfg)

    def write(self, name, text):
        with open(os.path.join(self.cfg, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def render(self, country, conn=None, **kw):
        return ce.render(conn or sqlite3.connect(":memory:"), country, TODAY, SINCE,
                         config_dir=self.cfg, directory=self.eds, **kw)


class FrameworkTests(Base):
    def items(self):
        return [
            ce.vote("xx", "v1", "2026-10-08", "Vote on the whole", [1], 1, False,
                    [ce.tally_line(80, 60, 2, "Adopted.", "roll call")],
                    group="bill-1", group_title="Abortion bill", final=True),
            ce.vote("xx", "v2", "2026-10-08", "Amendment 3", [1], 1, False,
                    [ce.tally_line(50, 90)], group="bill-1", group_title="Abortion bill"),
            ce.item("xx", "new", "b9", "2026-10-05", "Wetsvoorstel abortus", [1], 1,
                    takeaway="A members' bill"),
            ce.item("xx", "answer", "a1", "2026-10-06", "Pride Month costs", [5], 2),
            ce.item("xx", "answer", "a2", "2026-10-06", "Pride Month costs", [5], 2),
        ]

    def test_full_edition_sections_and_rules(self):
        text = self.render(fake(self.items()))
        for heading in ("## In brief", "## Recorded votes", "## New on our ground",
                        "## Answers", "## Watchlist", "## Coverage"):
            self.assertIn(heading, text)
        self.assertIn("2 recorded votes on one item", text)
        self.assertIn("**Decisive vote**", text)
        self.assertIn("1 more with the same title: a2.", text)
        self.assertIn("*Wetsvoorstel abortus*", text)        # verbatim, italic
        self.assertNotIn("—", text)
        self.assertIn("Edition 1, covering 3 October 2026 to 9 October 2026", text)

    def test_quiet_week(self):
        text = self.render(fake([]))
        self.assertIn("**A quiet week.**", text)
        self.assertNotIn("## Recorded votes", text)

    def test_act_without_owner_is_refused(self):
        bad = ce.item("xx", "new", "b1", "2026-10-05", "[ACT] do something", [1], 1)
        with self.assertRaises(ValueError):
            self.render(fake([bad]))

    def test_window_runs_from_the_last_real_edition_and_skips_samples(self):
        with open(os.path.join(self.eds, "xx-monitor-2026-10-01.md"), "w") as fh:
            fh.write("# real\n")
        with open(os.path.join(self.eds, "xx-monitor-2026-10-05.md"), "w") as fh:
            fh.write("# x\n> **SAMPLE EDITION.**\n")
        self.assertEqual(ce.window("xx", TODAY, directory=self.eds), ("2026-10-01", TODAY))
        self.assertEqual(ce.edition_number("xx", TODAY, self.eds), 2)
        self.assertEqual(ce.window("yy", TODAY, directory=self.eds), (SINCE, TODAY))

    def test_noise_rules_mutes_and_watched_items(self):
        self.write("edition-noise-xx.yaml",
                   "procedural_votes: ['^amendment 3$']\nexclude_titles: ['pride month']\n")
        self.write("edition-mute-xx.yaml",
                   "mute_in_edition: true\nitems: ['xx|new|b9']\npatterns: []\n")
        items = self.items() + [ce.item("xx", "answer", "w1", "2026-10-06", "Pride Month watch",
                                        [5], 2, watched=True)]
        dropped = []
        got = ce.gather(sqlite3.connect(":memory:"), fake(items), SINCE, TODAY, self.cfg, dropped)
        keys = {it["key"] for it in got}
        self.assertEqual(keys, {"v1", "w1"})
        self.assertEqual(sorted(d["dropped"] for d in dropped),
                         ["excluded title", "excluded title", "muted", "procedural vote"])
        text = self.render(fake(items))
        self.assertIn("2 excluded titles", text)

    def test_edition_evidence_own_words(self):
        self.write("edition-noise-xx.yaml", "edition_evidence:\n  vote: {own_words: true}\n")
        inherited = ce.vote("xx", "v3", "2026-10-08", "Motion", [12], 2, False, [], own=False)
        own = ce.vote("xx", "v4", "2026-10-08", "Motion", [12], 2, False, [], own=True)
        got = ce.gather(sqlite3.connect(":memory:"), fake([inherited, own]), SINCE, TODAY,
                        self.cfg)
        self.assertEqual([it["key"] for it in got], ["v4"])

    def test_kinds_restrict_the_edition(self):
        text = self.render(fake(self.items(), kinds=("vote",)))
        self.assertNotIn("## New on our ground", text)
        self.assertIn("## Recorded votes", text)

    def test_dm_goes_to_chris_alone(self):
        sent = {}

        def slack_dm(secrets, text):
            sent.update(secrets)
            return {"ok": True}
        with mock.patch("src.publish.load_secrets",
                        return_value={"slack_bot_token": "x", "slack_dm_user_id": "USOMEONE"}), \
                mock.patch("src.publish.slack_dm", side_effect=slack_dm):
            ce.send_dm("hello")
        self.assertEqual(sent["slack_dm_user_id"], ce.CHRIS)

    def test_dm_summary_counts_and_leads(self):
        text = ce.dm_summary(sqlite3.connect(":memory:"), fake(self.items(), flag=":flag-xx:"),
                             TODAY, SINCE, config_dir=self.cfg, directory=self.eds)
        self.assertIn(":flag-xx: *Testland Monitor", text)
        self.assertIn("2 recorded votes", text)
        self.assertEqual(text.count("Abortion bill"), 1)      # one line per vote group

    def test_rebels_and_splits(self):
        rows = [("A", "P", "yes"), ("B", "P", "yes"), ("C", "P", "no"), ("D", "Q", "no"),
                ("E", "niez.", "yes")]
        self.assertEqual(ce.rebels(rows, skip=("niez.",)), ["C (P)"])
        self.assertIn("P 2-1", ce.split_line(ce.group_counts([(g, p) for _, g, p in rows])))
        self.assertIn("DERIVED", ce.derived_line(5, "basis"))


class PolishTests(Base):
    """why_watched's first sentence, grouped vote lines, and the notice,
    post_render and cadence hooks."""

    def test_why_is_not_cut_inside_brackets_or_after_an_abbreviation(self):
        wl = {"PEC 5/2023": {"why": "Extends tax immunity for religious organisations "
                                    "(art. 150 of the Constitution). Eight nominal votes."}}
        it = ce.item("br", "vote", "PEC 5/2023", "2026-05-28", "PEC", [8], 1, True)
        self.assertEqual(ce.why_watched(it, wl), "Extends tax immunity for religious "
                         "organisations (art. 150 of the Constitution).")
        self.assertEqual(ce.first_sentence("Under art. 5 of the code. More."),
                         "Under art. 5 of the code.")
        self.assertEqual(ce.first_sentence("Filed by J. Smith today. More."),
                         "Filed by J. Smith today.")
        self.assertEqual(ce.first_sentence("Is it? Yes."), "Is it?")
        self.assertEqual(ce.first_sentence("No full stop"), "No full stop")

    def group(self, other_takeaway, other_title="Amendment 3"):
        return [ce.vote("xx", "v1", "2026-10-08", "Vote on the whole", [1], 1, False,
                        [ce.tally_line(80, 60)], group="g", group_title="Bill", final=True,
                        takeaway="The bill's final vote"),
                ce.vote("xx", "v2", "2026-10-07", other_title, [1], 1, False,
                        [ce.tally_line(50, 90)], group="g", group_title="Bill",
                        takeaway=other_takeaway)]

    def test_group_sub_line_has_one_full_stop(self):
        out = "\n".join(ce.vote_lines(self.group(None, "Sim: 467; Total: 472."), {}))
        self.assertIn("  - 7 Oct: *Sim: 467; Total: 472.* 50 for, 90 against", out)
        self.assertNotIn("*.", out)
        out = "\n".join(ce.vote_lines(self.group(None), {}))
        self.assertIn("  - 7 Oct: *Amendment 3*. 50 for, 90 against", out)

    def test_group_shows_a_takeaway_that_differs_from_the_headline(self):
        out = ce.vote_lines(self.group("Amendment on article 2"), {})
        self.assertIn("    Amendment on article 2.", out)
        same = ce.vote_lines(self.group("The bill's final vote"), {})
        self.assertEqual(sum("The bill's final vote" in ln for ln in same), 1)

    def test_notice_string_and_callable(self):
        text = self.render(fake([], notice="> **Parliament is dissolved.**"))
        lines = text.split("\n")
        sub = next(i for i, ln in enumerate(lines) if ln.startswith("_Diet."))
        self.assertEqual(lines[sub + 2], "> **Parliament is dissolved.**")
        self.assertEqual(lines[sub + 3], "")
        self.assertIn("**A quiet week.**", lines[sub + 4])
        calls = []

        def notice(conn, today, dm):
            calls.append(dm)
            return "_DM notice._" if dm else None
        country = fake([], notice=notice)
        self.assertNotIn("notice", self.render(country))
        dm = ce.dm_summary(sqlite3.connect(":memory:"), country, TODAY, SINCE,
                           config_dir=self.cfg, directory=self.eds)
        self.assertEqual(dm.split("\n")[1], "_DM notice._")
        self.assertEqual(calls, [False, True])
        plain = ce.dm_summary(sqlite3.connect(":memory:"), fake([]), TODAY, SINCE,
                              config_dir=self.cfg, directory=self.eds)
        self.assertEqual(plain.split("\n")[1], "")

    def test_post_render_and_cadence(self):
        country = fake([], post_render=lambda conn, c, today, text, wl: text + "\nEXTRA",
                       cadence_days=14, frequency="Fortnightly")
        text = ce.render(sqlite3.connect(":memory:"), country, TODAY, config_dir=self.cfg,
                         directory=self.eds)
        self.assertTrue(text.endswith("\nEXTRA"))
        self.assertIn("covering 26 September 2026 to 9 October 2026. Fortnightly, to Chris", text)
        self.assertIn("**A quiet fortnight.**", text)
        self.assertEqual(ce.window("xx", TODAY, directory=self.eds, days=14)[0], "2026-09-25")


class PolishTaxonomyTests(unittest.TestCase):
    def test_age_verification_needs_an_online_context(self):
        from src import filter as filt
        tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-pl.yaml"), "pl")
        wl = filt.Watchlist([], [], [])
        alcohol = ("Poselski projekt ustawy o zmianie ustawy o wychowaniu w trzeźwości i "
                   "przeciwdziałaniu alkoholizmowi oraz ustawy o radiofonii i telewizji",
                   "wprowadzenie obowiązku weryfikacji wieku przy zakupie; uregulowanie "
                   "sprzedaży internetowej wyłącznie z odbiorem osobistym")
        self.assertNotIn(7, filt.filter_item(tax, wl, *alcohol).issue_areas or [])
        online = ("Obywatelski projekt ustawy o ochronie małoletnich przed treściami "
                  "pornograficznymi w Internecie",
                  "zobowiązanie administratorów stron do wprowadzenia skutecznej weryfikacji wieku")
        res = filt.filter_item(tax, wl, *online)
        self.assertIn(7, res.issue_areas)
        self.assertIn("weryfikacj* wieku", res.matched_terms)
        broadcast = ("Sprawozdanie Krajowej Rady Radiofonii i Telewizji",
                     "o zmianie ustawy o radiofonii i telewizji")
        self.assertIn(7, filt.filter_item(tax, wl, *broadcast).issue_areas)


class LatamUnchangedTests(unittest.TestCase):
    def test_latam_noise_is_the_shared_class(self):
        from src import latam_noise
        self.assertIsInstance(latam_noise.NOISE, noise.Noise)
        latam_noise.clear()
        it = {"cc": "pe", "kind": "vote", "key": "k", "title": "Aprobación del orden del día",
              "watched": False, "tier": 1}
        self.assertEqual(latam_noise.drop_reason(it), "procedural vote")


# --- adapters --------------------------------------------------------------------

class AustriaTests(Base):
    def setUp(self):
        super().setUp()
        from src import at_store
        self.conn = conn_with(at_store)
        self.copy("watchlist-at.yaml")
        c = self.conn
        c.execute("INSERT INTO at_items (item_key, gp, chamber, art, title, citation, status, "
                  "introduced, last_date, areas, matched_terms, tier) VALUES "
                  "('XXVIII/I/525','XXVIII','NR','RV','Sterbeverfügungsgesetz-Novelle 2026',"
                  "'525 d.B.',5,'2026-06-01','2026-10-07','[2]','[]',1)")
        c.execute("INSERT INTO at_items (item_key, gp, chamber, art, title, status, introduced, "
                  "last_date, areas, matched_terms, tier) VALUES ('XXVIII/AA/78','XXVIII','NR',"
                  "'AA','Sterbeverfügungsgesetz-Novelle 2026',5,'2026-10-07','2026-10-07','[2]',"
                  "'[]',2)")
        c.execute("INSERT INTO at_items (item_key, gp, chamber, art, title, status, introduced, "
                  "last_date, areas, tier) VALUES ('XXVIII/J/1','XXVIII','NR','J',"
                  "'Anfrage zum Schwangerschaftsabbruch',3,'2026-10-05','2026-10-05','[1]',1)")
        for key in ("XXVIII/I/525@XXVIII/NRSITZ/87#210+2", "XXVIII/AA/78@XXVIII/NRSITZ/87#210+2"):
            c.execute("INSERT INTO at_divisions (division_key, item_key, date, body, question, "
                      "outcome, areas) VALUES (?,?,?,?,?,?,?)",
                      (key, key.split("@")[0], "2026-10-07", "NR",
                       "Gesetzesvorschlag in dritter Lesung", "angenommen", "[2]"))
            for klub, pos in (("ÖVP", "Dafür"), ("GRÜNE", "Dagegen")):
                c.execute("INSERT INTO at_votes VALUES (?,?,?)", (key, klub, pos))
        for pad, klub in (("1", "ÖVP"), ("2", "ÖVP"), ("3", "GRÜNE")):
            c.execute("INSERT INTO at_members (pad, name, chamber, klub) VALUES (?,?,?,?)",
                      (pad, "M" + pad, "NR", klub))

    def test_one_floor_vote_once_with_derived_members(self):
        country = ce.adapter("at")
        got = ce.gather(self.conn, country, SINCE, TODAY, self.cfg)
        votes = [it for it in got if it["kind"] == "vote"]
        self.assertEqual(len(votes), 1)
        self.assertTrue(votes[0]["watched"])                  # on the watched RV
        text = self.render(country, self.conn)
        self.assertIn("By Klub: for ÖVP; against GRÜNE.", text)
        self.assertIn("3 DERIVED from the group vote", text)
        self.assertIn("## Questions", text)
        self.assertIn("*Sterbeverfügungsgesetz-Novelle 2026*", text)


class NetherlandsTests(Base):
    def setUp(self):
        super().setUp()
        from src import nl_store
        self.conn = conn_with(nl_store)
        c = self.conn
        c.execute("INSERT INTO nl_zaken (zaak_nummer, soort, onderwerp, dossiers, dossier_titels, "
                  "own_areas, areas, tier) VALUES ('2026Z1','Motie','Motie over abortuszorg',"
                  "'[\"36180\"]','[\"Strategie\"]','[1]','[1]',1)")
        c.execute("INSERT INTO nl_zaken (zaak_nummer, soort, onderwerp, dossiers, own_areas, "
                  "areas, tier) VALUES ('2026Z2','Motie','Motie over asiel','[]','[11]','[11]',1)")
        c.execute("INSERT INTO nl_zaken (zaak_nummer, soort, onderwerp, dossiers, own_areas, "
                  "areas, tier) VALUES ('2026Z3','Motie','Motie over regenboogvlag','[]','[5]',"
                  "'[5]',2)")
        c.execute("INSERT INTO nl_divisions (besluit_id, zaak_nummer, date, stemmingssoort, "
                  "besluit_tekst, voor, tegen, positions_pending, areas) VALUES "
                  "('b1','2026Z1','2026-10-06','Met handopsteken','Aangenomen.',101,49,0,'[1]')")
        c.execute("INSERT INTO nl_divisions (besluit_id, zaak_nummer, date, stemmingssoort, "
                  "besluit_tekst, voor, tegen, positions_pending, areas) VALUES "
                  "('b2','2026Z2','2026-10-06','Met handopsteken','Verworpen.',40,110,0,'[11]')")
        c.execute("INSERT INTO nl_divisions (besluit_id, zaak_nummer, date, stemmingssoort, "
                  "besluit_tekst, voor, tegen, positions_pending, areas) VALUES "
                  "('b3','2026Z3','2026-10-08','Hoofdelijk','Aangenomen (2-1).',2,1,0,'[5]')")
        c.execute("INSERT INTO nl_votes (stemming_id, besluit_id, kind, fractie, position, zetels) "
                  "VALUES ('s1','b1','fractie','D66','Voor',26),('s2','b1','fractie','PVV',"
                  "'Tegen',19)")
        c.execute("INSERT INTO nl_votes (stemming_id, besluit_id, kind, fractie, persoon_id, actor, "
                  "position) VALUES ('s3','b3','lid','CDA','p1','Jansen','Voor'),"
                  "('s4','b3','lid','CDA','p2','Pietersen','Voor'),"
                  "('s5','b3','lid','CDA','p3','Klaassen','Tegen')")
        c.execute("INSERT INTO nl_members (persoon_id, name, fractie) VALUES "
                  "('m1','A','D66'),('m2','B','PVV')")

    def test_votes_only_migration_hidden_derived_and_roll_call(self):
        text = self.render(ce.adapter("nl"), self.conn)
        self.assertIn("Motie over abortuszorg", text)
        self.assertNotIn("Motie over asiel", text)           # migration is never shown
        self.assertIn("By fractie (seats): for D66 (26); against PVV (19).", text)
        self.assertIn("2 DERIVED from the group vote", text)
        self.assertIn("Against their group's majority: Klaassen (CDA)", text)


class BelgiumTests(Base):
    def setUp(self):
        super().setUp()
        from src import be_store
        self.conn = conn_with(be_store)
        self.copy("watchlist-be.yaml")
        c = self.conn
        c.execute("INSERT INTO be_dossiers (dossier_key, legislature, number, title_nl, title_fr, "
                  "areas, first_seen) VALUES ('56/1338',56,1338,'Rouwverlof euthanasie',"
                  "'Congé de deuil euthanasie','[2]','2026-01-01')")
        for n, heading, final in ((4, "Aangehouden amendement", 0), (5, "Geheel van het wetsvoorstel", 1)):
            c.execute("INSERT INTO be_divisions (division_key, legislature, sitting, vote_no, date, "
                      "dossier_key, heading_nl, heading_fr, subjects, kind, yes, no, abstain, "
                      "outcome, result_fr, areas) VALUES (?,56,143,?,'2026-10-08','56/1338',?,?,"
                      "'[]','nominal',?,?,0,'adopted','La Chambre adopte','[2]')",
                      ("56/143/{0}".format(n), n, heading, "Ensemble" if final else "Amendement",
                       2 if final else 1, 1 if final else 2))
            for name, grp, pos in (("Aerts Staf", "N-VA", "yes"), ("Peeters Jan", "N-VA", "yes"),
                                   ("Smet An", "N-VA", "no")):
                c.execute("INSERT INTO be_votes VALUES (?,?,?,?,?)",
                          ("56/143/{0}".format(n), name, None, pos, grp))

    def test_full_edition_with_groups_and_positions(self):
        text = self.render(ce.adapter("be"), self.conn)
        self.assertIn("2 recorded votes on one item", text)
        self.assertIn("**Decisive vote**", text)
        self.assertIn("Geheel van het wetsvoorstel", text)
        self.assertIn("Against their group's majority: Smet An (N-VA)", text)
        self.assertIn("not at the vote", text)
        self.assertIn("**watched**", text)                    # 56/1338 is on watchlist-be


class PolandTests(Base):
    def setUp(self):
        super().setUp()
        from src import pl_store
        self.conn = conn_with(pl_store)
        c = self.conn
        c.execute("INSERT INTO pl_processes (process_key, term, number, title, start_date, areas, "
                  "tier) VALUES ('10/5000',10,'5000','Projekt ustawy o ochronie życia',"
                  "'2026-10-05','[1]',1)")
        c.execute("INSERT INTO pl_members (mp_key, term, mp_id, name, club) VALUES "
                  "('10/1',10,1,'Jan Nowak','PiS'),('10/2',10,2,'Anna Kowal','PiS'),"
                  "('10/3',10,3,'Ewa Lis','PiS')")
        rows = (("pl-10-66-1", 1, "wniosek o skrócenie terminu", "Pkt. 1 Projekt o ochronie życia"),
                ("pl-10-66-2", 2, "głosowanie nad całością projektu.", "Pkt. 1 Projekt o ochronie życia"),
                ("pl-10-66-3", 3, "poprawka 1", "Pkt. 2 Projekt ustawy o wychowaniu w trzeźwości"))
        for key, n, topic, title in rows:
            c.execute("INSERT INTO pl_divisions (division_key, term, sitting, number, voted_at, "
                      "kind, title, topic, process_keys, yes, no, abstain, own_areas, areas, tier, "
                      "positions) VALUES (?,10,66,?,'2026-10-08T10:00:00','ELECTRONIC',?,?,"
                      "'[\"10/5000\"]',2,1,0,'[1]','[1]',1,3)", (key, n, title, topic))
        c.execute("UPDATE pl_divisions SET process_keys='[\"10/6000\"]', areas='[7]' "
                  "WHERE division_key='pl-10-66-3'")
        for mp, pos in (("10/1", "YES"), ("10/2", "YES"), ("10/3", "NO")):
            c.execute("INSERT INTO pl_votes (division_key, mp_key, position, club) VALUES "
                      "('pl-10-66-2',?,?,'PiS')", (mp, pos))

    def test_positions_procedure_and_alcohol_rules(self):
        country = ce.adapter("pl")
        dropped = []
        got = ce.gather(self.conn, country, SINCE, TODAY, dropped=dropped)
        self.assertEqual(sorted(d["dropped"] for d in dropped),
                         ["names only excluded bills", "procedural vote"])
        text = ce.render(self.conn, country, TODAY, SINCE, directory=self.eds)
        self.assertIn("By club (for-against, then abstaining where any): PiS 2-1", text)
        self.assertIn("Against their group's majority: Ewa Lis (PiS)", text)
        self.assertIn("## New on our ground", text)
        self.assertIn("głosowanie nad całością projektu.", text)
        self.assertEqual(len([it for it in got if it["kind"] == "vote"]), 1)


if __name__ == "__main__":
    unittest.main()
