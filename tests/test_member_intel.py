"""Member intelligence for the new countries (src/member_intel.py,
tools/member_intel.py) and its place in the member profiles
(src/member_profiles.py): committees, cross-party groups, interests, the
config's flags and Brazil's party line. Fixtures are trimmed copies of the
parliaments' own replies, archived 11 October 2026. No network."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import br_store, member_intel as mi, member_profiles as mp, noise, pl_store  # noqa: E402
from tests.test_member_profiles import Base, pl_store_with_votes  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "member_intel")
TODAY = "2026-10-11"


def fixture(name):
    path = os.path.join(FIX, name)
    if name.endswith(".zip"):
        with open(path, "rb") as fh:
            return fh.read()
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class FakeClient:
    """Answers by URL substring; records every request."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def _answer(self, url):
        self.asked.append(url)
        for part, reply in self.answers:
            if part in url:
                return reply
        raise AssertionError("unexpected request: " + url)

    def get_json(self, url, feed, slug, **_):
        return self._answer(url)

    def get_bytes(self, url, feed, slug, **_):
        return self._answer(url)

    def post_json(self, url, body, feed, slug, **_):
        return self._answer(url + " " + body)


class Parsers(unittest.TestCase):
    def test_poland_committees_keyed_by_term_and_id(self):
        rows = mi.parse_pl_committees(fixture("pl_committees.json"), 10)
        self.assertEqual(len(rows), 9)
        health = [r for r in rows if r["group_key"] == "ZDR"]
        self.assertTrue(all(r["member_key"].startswith("10/") for r in health))
        self.assertEqual(health[0]["kind"], "committee")
        self.assertEqual(health[0]["group_name"], "Komisja Zdrowia")
        self.assertTrue(all(r["role"] for r in rows))      # 'członek' where none printed

    def test_switzerland_committees_and_interests(self):
        coms = mi.parse_ch_committees(fixture("ch_committees.json")["d"])
        jost = [c for c in coms if c["member_key"] == "4331"]
        self.assertEqual(len(jost), 3)
        self.assertIn("Präsident/in", {c["role"] for c in jost})
        ints = mi.parse_ch_interests(fixture("ch_interests.json")["d"])
        self.assertTrue(ints)
        self.assertTrue(all(i["member_key"] == "4331" for i in ints))
        self.assertTrue({i["paid"] for i in ints} <= {"bezahlt", "ehrenamtlich"})
        self.assertTrue(all(i["category"] for i in ints))

    def test_netherlands_seats_and_nevenfuncties(self):
        seats = mi.parse_nl_seats(fixture("nl_vast.json")["value"])
        self.assertEqual(len(seats), 3)
        self.assertEqual(seats[1]["role"], "Voorzitter")
        subs = mi.parse_nl_seats(fixture("nl_vervanger.json")["value"], substitute=True)
        self.assertTrue(subs)
        keep = {seats[0]["member_key"]}
        self.assertEqual(len(mi.parse_nl_seats(fixture("nl_vast.json")["value"], keep=keep)), 1)
        neven = mi.parse_nl_nevenfuncties(fixture("nl_neven.json")["value"])
        self.assertEqual(len(neven), 3)
        self.assertEqual(neven[0]["category"], "Nevenfunctie")
        self.assertTrue(neven[0]["text"].startswith("Bestuurslid"))

    def test_austria_keeps_current_bundesrat_functions_only(self):
        nr = mi.parse_at_committees(fixture("at_xxviii.json"))
        self.assertEqual(len(nr), 3)
        br = mi.parse_at_committees(fixture("at_br.json"))
        self.assertEqual([r["member_key"] for r in br], ["3460", "31956"])
        self.assertEqual(br[0]["start"][:4], br[0]["start"][:4])
        self.assertEqual(mi.parse_at_committees(fixture("at_br.json"), keep={"31956"})[0]["role"],
                         "Vorsitzende")

    def test_italy_current_memberships_only_and_deduplicated(self):
        b = [{k: v["value"] for k, v in x.items()}
             for x in fixture("it_camera.json")["results"]["bindings"]]
        rows = mi.parse_it_camera(b)
        self.assertEqual(len(rows), 2)          # the ended one dropped, the repeats folded
        self.assertTrue(all(r["member_key"] is None and r["name"] == "ALBERTO PANDOLFO"
                            for r in rows))
        kinds = {r["group_name"]: r["kind"] for r in rows}
        self.assertEqual(kinds["X COMMISSIONE (ATTIVITA' PRODUTTIVE, COMMERCIO E TURISMO)"],
                         "committee")
        self.assertIn("inquiry", kinds.values())
        self.assertEqual(rows[0]["start"], "2026-07-14")

    def test_france_keeps_committees_and_study_groups_not_friendship_groups(self):
        rows = mi.parse_fr_amo(fixture("fr_amo10_small.zip"))
        types = sorted(r["group_type"] for r in rows)
        self.assertEqual(types, ["COMPER", "GE", "GE"])
        self.assertTrue(all(r["member_key"] == "PA842255" for r in rows))
        self.assertEqual({r["kind"] for r in rows}, {"committee", "cross_party"})
        self.assertTrue(all(r["group_name"] and not r["group_name"].startswith("PO")
                            for r in rows))

    def test_brazil_organs_fronts_and_members(self):
        organs = mi.parse_br_organs(fixture("br_orgaos.json"), TODAY)
        self.assertEqual(len(organs), 3)        # the ended Mesa seat dropped
        self.assertTrue(all(o["member_key"].startswith("camara-") for o in organs))
        fronts = mi.parse_br_fronts([fixture("br_frentes_page.json")])
        self.assertEqual(len(fronts), 4)
        ev = [f for f in fronts if f["id"] == "54477"][0]
        members = mi.parse_br_front_members(ev, fixture("br_frente_54477.json"))
        self.assertEqual(len(members), 3)
        self.assertEqual(members[0]["kind"], "cross_party")
        self.assertEqual(members[0]["group_name"], "Frente Parlamentar Evangélica do Congresso "
                                                   "Nacional")

    def test_dates(self):
        self.assertEqual(mi.iso("20250226"), "2025-02-26")
        self.assertEqual(mi.iso("2025-02-26T00:00:00+01:00"), "2025-02-26")
        self.assertEqual(mi.iso("26.02.2025"), "2025-02-26")
        self.assertEqual(mi.iso("2010"), "2010")
        self.assertIsNone(mi.iso(""))


class Flags(unittest.TestCase):
    def test_the_config_reads_names_folded(self):
        flags = mi.load_flags()
        self.assertTrue(mi.flag(flags, "br", "Frente Parlamentar Evangélica do Congresso Nacional"))
        self.assertTrue(mi.flag(flags, "br", "Frente Parlamentar Mista contra o Aborto e em "
                                             "Defesa da Vida"))
        self.assertIsNone(mi.flag(flags, "br", "Frente Parlamentar Mista da Agricultura Familiar"))
        self.assertTrue(mi.flag(flags, "pl", "Komisja Polityki Społecznej i Rodziny"))
        self.assertTrue(mi.flag(flags, "fr", "Chrétiens d'Orient"))
        self.assertIsNone(mi.flag(flags, "fr", "Cheval"))
        self.assertTrue(mi.flag(flags, "ch", "Pro Life, Bern"))
        self.assertIsNone(mi.flag(flags, "ch", "Swiss eMobility"))
        self.assertIsNone(mi.flag(flags, "xx", "anything"))

    def test_germany_committees_approved_16_october(self):
        flags = mi.load_flags()
        cases = {
            "Ausschuss für Gesundheit": (1, 2, 3, 10),
            "Ausschuss für Recht und Verbraucherschutz": (5, 7, 9, 10),
            "Ausschuss für Bildung, Familie, Senioren, Frauen und Jugend": (6, 9),
            "Kommission zur Wahrnehmung der Belange der Kinder (Kinderkommission)": (6, 9),
            "Ausschuss für Menschenrechte und humanitäre Hilfe": (8,),
        }
        for name, areas in cases.items():
            got = mi.flag(flags, "de", name)
            self.assertIsNotNone(got, name)
            self.assertEqual(got[0], areas, name)
        self.assertIsNone(mi.flag(flags, "de", "Verteidigungsausschuss"))
        self.assertIsNone(mi.flag(flags, "de", "Ausschuss für Verkehr"))

    def test_every_rule_compiles_and_names_its_areas(self):
        for cc, rules in mi.load_flags().items():
            for pat, areas, why in rules:
                self.assertTrue(why, cc)
                self.assertTrue(set(areas) <= set(range(1, 14)), (cc, why))


class Store(unittest.TestCase):
    def setUp(self):
        self.conn = mi.ensure(sqlite3.connect(":memory:"))

    def test_a_run_replaces_its_source_only(self):
        a = [mi.group(member_key="10/1", kind="committee", group_key="ZDR",
                      group_name="Komisja Zdrowia")]
        mi.replace(self.conn, "pl", "pl-committees", TODAY, a)
        mi.replace(self.conn, "ch", "ch-committees", TODAY, a)
        mi.replace(self.conn, "pl", "pl-committees", TODAY, a + a)
        n = dict(self.conn.execute("SELECT cc, COUNT(*) FROM mi_groups GROUP BY cc").fetchall())
        self.assertEqual(n, {"pl": 2, "ch": 1})
        self.assertEqual(self.conn.execute("SELECT groups FROM mi_runs WHERE cc='pl'").fetchone(),
                         (2,))

    def test_collect_poland_through_a_fake_client(self):
        client = FakeClient([("/term10/committees", fixture("pl_committees.json"))])
        done = mi.collect(self.conn, client, "pl", TODAY, log=lambda *_: None)
        self.assertEqual(done, {"pl-committees": (9, 0)})
        self.assertEqual(len(client.asked), 1)

    def test_brazil_reads_fronts_on_our_ground_and_keeps_the_rest(self):
        # Last run read a front this week's rotation skips: its rows stand.
        mi.replace(self.conn, "br", "br-frentes", "2026-10-04", [mi.group(
            member_key="camara-1", kind="cross_party", group_key="55703",
            group_name="Frente Parlamentar Mista do Serviço Exterior Brasileiro")])
        client = FakeClient([
            ("orgaosDeputados", fixture("br_orgaos.json")),
            ("/frentes?", fixture("br_frentes_page.json")),
            ("/frentes/54477/membros", fixture("br_frente_54477.json")),
            ("/membros", {"dados": []})])
        mi.collect(self.conn, client, "br", TODAY, log=lambda *_: None)
        asked = [u for u in client.asked if "/membros" in u]
        self.assertIn(mi.BR_API + "/frentes/54477/membros", asked)
        self.assertLess(len(asked), 4)          # not every front: a rotation share
        names = {r[0] for r in self.conn.execute(
            "SELECT group_name FROM mi_groups WHERE source='br-frentes'")}
        self.assertIn("Frente Parlamentar Evangélica do Congresso Nacional", names)
        self.assertIn("Frente Parlamentar Mista do Serviço Exterior Brasileiro", names)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM mi_groups WHERE "
                                           "source='br-orgaos'").fetchone()[0], 3)

    def test_rotation_covers_every_front_in_eight_weeks(self):
        fronts = [{"id": str(i), "titulo": "f"} for i in range(1, 41)]
        seen = set()
        for week in range(8):
            day = (mi.datetime.date(2026, 1, 5) + mi.datetime.timedelta(weeks=week)).isoformat()
            seen |= {f["id"] for f in mi.br_rotation(fronts, day)}
        self.assertEqual(len(seen), 40)


class Profiles(Base):
    def store(self):
        conn = pl_store_with_votes()
        conn.execute("INSERT INTO pl_members (mp_key, term, mp_id, name, club, district, active) "
                     "VALUES ('10/3', 10, 3, 'Ewa Zielińska', 'PSL', 'Lublin (6)', 1)")
        mi.ensure(conn)
        mi.replace(conn, "pl", "pl-committees", TODAY, [
            mi.group(member_key="10/1", kind="committee", group_key="ZDR",
                     group_name="Komisja Zdrowia", role="przewodnicząca"),
            mi.group(member_key="10/3", kind="committee", group_key="PSR",
                     group_name="Komisja Polityki Społecznej i Rodziny", role="członek"),
            mi.group(member_key="10/3", kind="committee", group_key="ASW",
                     group_name="Komisja Administracji i Spraw Wewnętrznych"),
            mi.group(member_key="10/99", kind="committee", group_key="ZDR",
                     group_name="Komisja Zdrowia")])
        conn.row_factory = sqlite3.Row
        return conn

    def setUp(self):
        super().setUp()
        shutil.copy(mi.CONFIG, os.path.join(self.cfg, mi.CONFIG_NAME))

    def test_groups_attach_with_flags(self):
        data = self.build(self.store(), "pl")
        anna, ewa = data["members"]["10/1"], data["members"]["10/3"]
        self.assertEqual([g["group_name"] for g in anna.groups], ["Komisja Zdrowia"])
        self.assertTrue(anna.groups[0]["flag"])
        self.assertEqual(len(ewa.groups), 2)
        self.assertTrue(ewa.groups[0]["flag"])          # flagged first
        self.assertIsNone(ewa.groups[1]["flag"])
        self.assertEqual(data["intel"]["unmatched"], 1)  # 10/99 is no listed member

    def test_a_flagged_membership_earns_a_profile(self):
        data = self.build(self.store(), "pl")
        ewa = data["members"]["10/3"]
        self.assertFalse(ewa.votes)
        self.assertTrue(mp.has_record(ewa))
        out = os.path.join(self.tmp, "out")
        mp.write(data, out)
        files = os.listdir(os.path.join(out, "pl"))
        self.assertIn(mp.filename(ewa), files)
        text = read(os.path.join(out, "pl", mp.filename(ewa)))
        self.assertIn("## Committees and groups (2)", text)
        self.assertIn("**Komisja Polityki Społecznej i Rodziny (członek)** (on our ground: "
                      "the social policy and family committee)", text)
        index = read(os.path.join(out, "pl", "index.md"))
        self.assertIn("## Groups on our ground", index)
        self.assertIn("**Komisja Zdrowia** (committee; the health committee; 1 member(s))",
                      index)
        self.assertIn("src/member_intel.py; pl-committees read 2026-10-11 (4 row(s))", index)

    def test_without_intel_rows_nothing_changes(self):
        data = self.build(pl_store_with_votes(), "pl")
        self.assertIsNone(data["intel"])
        out = os.path.join(self.tmp, "out")
        mp.write(data, out)
        index = read(os.path.join(out, "pl", "index.md"))
        self.assertNotIn("Groups on our ground", index)

    def test_interests_render_in_a_table(self):
        conn = self.store()
        mi.replace(conn, "pl", "pl-test", TODAY, interests=[mi.interest(
            member_key="10/1", category="Verein", text="Pro Life | Bern", paid="ehrenamtlich")])
        conn.row_factory = sqlite3.Row
        data = self.build(conn, "pl")
        text = "\n".join(mp.render_intel(data["members"]["10/1"]))
        self.assertIn("| Verein | Pro Life / Bern |  | ehrenamtlich |  |", text)


class BrazilPartyLine(Base):
    def test_party_and_federation_orientations_never_truncated_blocs(self):
        conn = sqlite3.connect(":memory:")
        br_store.ensure_schema(conn)
        conn.executemany("INSERT INTO br_orientations VALUES (?,?,?)", [
            ("camara-1", "PL", "Não"), ("camara-1", "Fdr PT-PCdoB-PV", "Sim"),
            ("camara-1", "Bl UniPpFdrPsdbCid...", "Sim")])
        line = mp._br_party_line(conn)
        self.assertEqual(line("camara-1", "PL"), ("PL", "Não"))
        self.assertEqual(line("camara-1", "PCdoB"), ("Fdr PT-PCdoB-PV", "Sim"))
        self.assertIsNone(line("camara-1", "UNIÃO"))
        self.assertIsNone(line("camara-2", "PL"))

    def test_counts_and_marks(self):
        votes = [{"position": "Não", "party": "PL", "party_line": ("PL", "Não")},
                 {"position": "Sim", "party": "PL", "party_line": ("PL", "Não")},
                 {"position": "Sim", "party": "PT", "party_line": ("Fdr PT-PCdoB-PV", "Liberado")},
                 {"position": "Artigo 17", "party": "PL", "party_line": ("PL", "Sim")},
                 {"position": "Sim", "party": "PL", "party_line": None}]
        self.assertEqual(mp.party_line_counts(votes),
                         {"followed": 1, "differed": 1, "free vote": 1, "other": 1})
        self.assertEqual(mp.party_line_mark(votes[0]), "party line: Não")
        self.assertEqual(mp.party_line_mark(votes[2]),
                         "party line (Fdr PT-PCdoB-PV): Liberado")


class Tool(unittest.TestCase):
    def test_a_failing_country_is_a_gap_and_the_rest_still_run(self):
        from tools import member_intel as tool
        tmp = tempfile.mkdtemp()
        try:
            db = os.path.join(tmp, "s.db")
            calls = []

            def boom(conn, client, today, log=print, **_):
                calls.append("nl")
                raise ValueError("bad reply")

            def ok(conn, client, today, log=print, **_):
                calls.append("pl")
                return {"pl-committees": ([], [], True, None)}
            saved = dict(mi.FETCHERS)
            mi.FETCHERS.update(nl=boom, pl=ok)
            try:
                rc = tool.main(["nl", "pl", "--db", db, "--raw", tmp, "--date", TODAY])
            finally:
                mi.FETCHERS.clear()
                mi.FETCHERS.update(saved)
            self.assertEqual(rc, 3)
            self.assertEqual(calls, ["nl", "pl"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
