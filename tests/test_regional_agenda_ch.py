"""Swiss cantonal parliaments' forward agendas (src/regional_agendas/ch.py) on
trimmed live captures of 16 October 2026 (tests/fixtures/regional_agenda/ch/).
No network."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import regional_agenda as ra  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.regional_agendas import ch  # noqa: E402
from tests.test_regional_agenda import FakeClient, load_fixture, store  # noqa: E402

TODAY, UNTIL = "2026-10-16", "2026-12-11"


def fx(name):
    return load_fixture("ch", name)


def ctx():
    return ra.Ctx(TODAY, UNTIL, log=lambda *a: None)


def opd_rows():
    meetings = json.loads(fx("opd_meetings.json.gz"))["data"]
    agendas = json.loads(fx("opd_agendas.json.gz"))["data"]
    groups = {g["id"]: g for g in json.loads(fx("opd_groups.json"))["data"]}
    c = ctx()
    return [m for m in meetings if c.in_window(m["begin_date"][:10])], agendas, groups


def opd_pages():
    """The three OpenParlData requests a run makes, as the fixtures answer them."""
    meetings, agendas, groups = opd_rows()
    keys = ",".join(c.upper() for c in ch.OPD_CANTONS)
    ids = [str(m["id"]) for m in meetings]
    gids = sorted({str(m["group_id"]) for m in meetings if m.get("group_id")})
    wanted = set(int(i) for i in ids)
    pages = {ch.OPD_MEETINGS.format(keys=keys, limit=ch.OPD_PAGE, offset=0):
             json.loads(fx("opd_meetings.json.gz"))}
    for i in range(0, len(ids), 80):
        chunk = set(int(x) for x in ids[i:i + 80])
        pages[ch.OPD_AGENDAS.format(ids=",".join(ids[i:i + 80]), offset=0)] = {
            "meta": {"has_more": False},
            "data": [a for a in agendas if a["meeting_id"] in chunk and a["meeting_id"] in wanted]}
    pages[ch.OPD_GROUPS.format(ids=",".join(gids))] = json.loads(fx("opd_groups.json"))
    return pages


class OpenParlDataTest(unittest.TestCase):
    def test_items_tba_and_languages(self):
        meetings, agendas, groups = opd_rows()
        be = ch.opd_items("be", meetings, agendas, groups, ctx())
        # 116 business in German and French = 116 items (+1 TBA training day),
        # the French title as detail, both taxonomies applied (lang None).
        self.assertEqual(len(be), 117)
        self.assertEqual(sum(1 for i in be if not i["business"]), 1)
        paired = [i for i in be if i["reference"] == "2024.STA.1285"][0]
        self.assertEqual(paired["business"], "Verfassung des Kantons Bern (KV). Änderung")
        self.assertIn("Constitution du canton de Berne", paired["detail"])
        self.assertIsNone(paired["lang"])
        # Half-day sittings of the session carry no rows of their own.
        self.assertTrue(all(i["meeting_id"] in ("opd-33648", "opd-33824") for i in be))
        bs = ch.opd_items("bs", meetings, agendas, groups, ctx())
        self.assertEqual(len(bs), 108)
        self.assertTrue(all(i["body"] == "Grosser Rat" and i["dated"] == "2026-10-21" for i in bs))
        ag = ch.opd_items("ag", meetings, agendas, groups, ctx())
        self.assertEqual([(i["dated"], i["item_time"], i["business"]) for i in ag],
                         [("2026-10-20", "10:00", ""), ("2026-10-20", "14:00", "")])
        gr = ch.opd_items("gr", meetings, agendas, groups, ctx())
        violence = [i for i in gr if i["reference"] == "2026-81"][0]
        self.assertTrue(violence["business"].startswith("Gesetz gegen häusliche Gewalt"))
        self.assertIn("Legge contro la violenza domestica", violence["detail"])

    def test_collect_shares_one_read(self):
        conn = store()
        client = FakeClient(opd_pages())
        s = ra.collect(conn, "ch", client, TODAY, days=56, regions=["be", "bs", "bl", "ag", "fr"],
                       log=lambda *a: None)
        self.assertEqual(sorted(s["read"]), ["be", "bl", "bs"])
        # Aargau's own host refuses us: not read through the republisher either.
        self.assertEqual(sorted(s["blocked"]), ["ag", "fr"])
        self.assertEqual(len(client.asked), 3)          # meetings, agendas, groups: once
        n = dict(conn.execute("SELECT region, COUNT(*) FROM regional_agenda GROUP BY region")
                 .fetchall())
        self.assertEqual((n["be"], n["bs"], n["bl"]), (117, 108, 72))
        self.assertNotIn("ag", n)
        langs = dict(conn.execute("SELECT region, lang FROM regional_agenda WHERE region='bs' "
                                  "LIMIT 1").fetchall())
        self.assertEqual(langs["bs"], "taxonomy-atch.yaml")

    def test_dead_api_keeps_rows(self):
        conn = store()
        ra.collect(conn, "ch", FakeClient(opd_pages()), TODAY, days=56, regions=["bs", "bl"],
                   log=lambda *a: None)
        client = FakeClient({})
        s = ra.collect(conn, "ch", client, "2026-10-17", days=55, regions=["bs", "bl"],
                       log=lambda *a: None)
        self.assertEqual(sorted(s["gap"]), ["bl", "bs"])
        self.assertEqual(len(client.asked), 1)          # the failure is shared, not retried
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM regional_agenda").fetchone()[0], 180)


class OwnRoutesTest(unittest.TestCase):
    def test_zh(self):
        items = ch.parse_zh(fx("zh_sitzungen.xml.gz"), ctx())
        kr = [i for i in items if i["body"] == "Kantonsrat" and i["business"]]
        self.assertEqual(len(kr), 144)
        self.assertEqual([i["item_order"] for i in kr[:3]], [1, 2, 3])
        self.assertEqual(kr[1]["reference"], "KR-Nr. 333/2026")
        konv = [i for i in kr if "Konversionsmassnahmen" in i["business"]][0]
        self.assertEqual(konv["reference"], "KR-Nr. 376/2026")
        kssg = [i for i in items if i["body"].startswith("Kommission für soziale")]
        self.assertTrue(any(i["reference"] == "6115" and "Sozialhilfegesetz" in i["business"]
                            for i in kssg))
        tba = [i for i in items if not i["business"]]
        self.assertTrue(tba)
        self.assertTrue(all(i["meeting_id"].startswith("zh-") for i in items))

    def test_ge(self):
        sessions = ch.parse_ge_sessions(fx("ge_seances_2026.html.gz"), "2026")
        octo = [s for s in sessions if s[0] == "030406"][0]
        self.assertEqual(octo[2][0], ("2026-10-29", "17:00"))
        self.assertIn("seances-odj-lion", octo[3])
        nov = [s for s in sessions if s[0] == "030407"][0]
        self.assertIsNone(nov[3])
        items = ch.parse_ge_odj(fx("ge_odj_030406.html.gz"), "2026-10-29", "030406")
        self.assertEqual(len(items), 146)
        pl = [i for i in items if i["reference"] == "PL 13694-A"][0]
        self.assertIn("mixité sociale", pl["business"])
        self.assertIn("Catégorie II", pl["detail"])

    def test_vd_ti_vs_zg(self):
        self.assertEqual(ch.parse_vd_list(fx("vd_list.html.gz"))[0][0], "2026-10-06")
        vd = ch.parse_vd_sitting(fx("vd_seance_1033712.html"), "2026-10-06")
        self.assertEqual(vd[2]["reference"], "26_INI_10")
        dated, time, ti = ch.parse_ti_odg(fx("ti_odg.html"))
        self.assertEqual((dated, time, len(ti)), ("2026-10-26", "14:00", 19))
        self.assertEqual(ti[4]["reference"], "134859")
        cal = ch.parse_ti_calendar(fx("ti_calendario.html"))
        self.assertEqual(cal[1], ("2026-11-23", "2026-11-25", "Oggetti vari"))
        empty = json.loads(fx("vs_session_280737.json"))
        empty["dates"] = ["2026-11-09", "2026-11-10"]
        vs = ch.parse_vs_session(empty, ctx())
        self.assertEqual([(i["dated"], i["business"]) for i in vs],
                         [("2026-11-09", ""), ("2026-11-10", "")])
        sept = ch.parse_vs_session(json.loads(fx("vs_session_278796.json.gz")),
                                   ra.Ctx("2026-09-01", "2026-09-30"))
        self.assertGreater(len(sept), 100)
        self.assertTrue(any("Halten von Hunden" in i["business"] for i in sept))
        zg = ch.parse_zg_agenda(fx("zg_169.html"), "2026-09-24")
        self.assertEqual(zg[3]["reference"], "4187")
        self.assertEqual(zg[3]["item_time"], "08:00")
        self.assertTrue(any("Kopftücher" in i["business"] for i in zg))

    def test_ti_reader_skips_session_with_agenda(self):
        client = FakeClient({ch.TI_ODG: fx("ti_odg.html"), ch.TI_CAL: fx("ti_calendario.html")})
        read = ch.read_ti(client, ctx())
        tba = [i for i in read.items if not i["business"]]
        self.assertEqual([i["dated"] for i in tba], ["2026-11-23"])   # 14 December is past until
        self.assertEqual(read.units, [ra.window(TODAY, UNTIL)])

    def test_ge_reader_failure_is_partial(self):
        year = ch.GE_SESSIONS.format("2026")
        client = FakeClient({year: fx("ge_seances_2026.html.gz")})     # the ODJ page is down
        read = ch.read_ge(client, ctx())
        self.assertTrue(read.gaps)
        self.assertEqual(read.units, [])
        self.assertTrue(all(i["dated"] >= "2026-11-26" for i in read.items))


if __name__ == "__main__":
    unittest.main()
