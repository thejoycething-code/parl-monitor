"""Plain-English vote meanings for the new countries (src/vote_meanings.py,
tools/vote_meanings.py). Small temporary stores; no network, no Slack, no AI."""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import country5ca as c5  # noqa: E402
from src import vote_meanings as vm  # noqa: E402
from test_country_5ca import PL_STANCE, PL_WL, pl_store_at  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tool = _load("vote_meanings")
QUIET = lambda *a, **k: None  # noqa: E731


def read(path):
    with open(path, encoding="utf-8") as h:
        return h.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as h:
        h.write(text)


def row(question, subject=None, key="k1", **kw):
    r = {"key": key, "question": question, "subject": subject, "watch_key": None,
         "process_keys": None, "date": "2026-05-29"}
    r.update(kw)
    return r


class RuleTests(unittest.TestCase):
    BILLS = {"10/2110": {"key": "10/2110", "direction": "against",
                         "why": "O statusie osoby najbliższej (government): registered cohabitation "
                                "contracts. Passed 29 May 2026."}}

    def rule(self, question, subject=None, procs=("10/2110",), cc="pl", **kw):
        import json
        r = row(question, subject, process_keys=json.dumps(list(procs)), **kw)
        return vm.rule_meaning(cc, r, {}, self.BILLS)

    def test_whole_text_names_the_bill_in_english(self):
        m = self.rule("głosowanie nad całością projektu.")
        self.assertEqual(m["yes"], "To pass 10/2110 (registered cohabitation contracts) as a whole.")
        self.assertEqual(m["no"], "Against passing it.")
        self.assertEqual(m["quality"], "full")

    def test_motion_to_reject_and_veto_override(self):
        m = self.rule("wniosek o odrzucenie w całości projektu.")
        self.assertTrue(m["yes"].startswith("To reject 10/2110"))
        self.assertIn("goes on", m["no"])
        v = self.rule("głosowanie nad ponownym uchwaleniem ustawy")
        self.assertIn("overriding the President's veto", v["yes"])
        self.assertIn("veto stands", v["no"])

    def test_amendment_number_and_procedure(self):
        m = self.rule("poprawka 12")
        self.assertEqual(m["yes"], "To adopt amendment 12 to 10/2110 (registered cohabitation "
                                   "contracts).")
        self.assertIn("leaving the text as it stood", m["no"])
        p = self.rule("wniosek o uzupełnienie porządku dziennego.")
        self.assertIn("order of business", p["yes"])

    def test_no_english_description_quotes_the_source(self):
        m = self.rule("głosowanie nad całością projektu.", "Pkt. 5 Sprawozdanie Komisji",
                      procs=("10/999",))
        self.assertEqual(m["quality"], "title")
        self.assertIn("“Pkt. 5 Sprawozdanie Komisji”", m["yes"])

    def test_unreadable_kind_has_no_rule(self):
        self.assertIsNone(self.rule("coś zupełnie innego"))

    def test_latin_american_forms(self):
        m = vm.rule_meaning("cl", row("Votación en general del proyecto", boletin=None), {}, {})
        self.assertIn("in general", m["yes"])
        p = vm.rule_meaning("cl", row("Votación en particular, artículo 3", boletin=None), {}, {})
        self.assertIn("in its articles", p["yes"])

    def test_swiss_meaning_lines_are_translated(self):
        r = row("Gesamtabstimmung", short_number=None, business_id=None,
                meaning_yes="Antrag der Mehrheit", meaning_no="Antrag der Minderheit (Glarner)")
        m = vm.rule_meaning("ch", r, {}, {})
        self.assertEqual(m["yes"], "For the committee majority's proposal.")
        self.assertEqual(m["no"], "For the committee minority's proposal (Glarner).")
        r2 = row("x", meaning_yes="Etwas Unbekanntes", meaning_no="Anderes", short_number=None,
                 business_id=None)
        self.assertIn("“Etwas Unbekanntes”", vm.rule_meaning("ch", r2, {}, {})["yes"])

    def test_gloss_keeps_english_after_a_source_title(self):
        self.assertEqual(vm.gloss("Kodeks karny: decriminalises abortion up to 12 weeks. More."),
                         "decriminalises abortion up to 12 weeks")
        self.assertEqual(vm.gloss("Euthanasia, the matrix bill: 'asistencia médica'"),
                         "Euthanasia, the matrix bill: 'asistencia médica'")

    def test_line_and_member_position(self):
        m = {"yes": "To pass it.", "no": "Against passing it.", "source": "rule"}
        text = vm.line(m, "pl")
        self.assertEqual(text, "Meaning: **Za** = to pass it; **Przeciw** = against passing it. "
                               "_(by rule, from the vote's wording and the bill)_")
        self.assertEqual(vm.for_position(m, "pl", "YES"), "To pass it.")
        self.assertEqual(vm.for_position(m, "pl", "NO"), "Against passing it.")
        self.assertIsNone(vm.for_position(m, "pl", "ABSENT"))


class StoreBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.tmp.name, "config")
        os.makedirs(self.cfg)
        with open(os.path.join(self.cfg, "pl_stance.yaml"), "w", encoding="utf-8") as h:
            h.write(PL_STANCE)
        path = os.path.join(self.tmp.name, "store.db")
        pl_store_at(path).close()
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        vm.ensure_table(self.conn)
        vm._OVERRIDES.clear()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def write_override(self, text):
        with open(os.path.join(self.cfg, "vote-meanings-pl.yaml"), "w", encoding="utf-8") as h:
            h.write(text)


class StoreTests(StoreBase):
    def test_rules_are_stored_for_watched_and_tier1_only(self):
        got = vm.write_rules(self.conn, "pl", "2026-10-11", self.cfg, QUIET, wl=PL_WL)
        self.assertEqual(got["divisions"], 5)          # pl-10-1-5 is tier 2, unwatched
        rows = vm.stored(self.conn, "pl")
        self.assertNotIn("pl-10-1-5", rows)
        self.assertEqual(rows["pl-10-1-1"]["source"], "rule")
        self.assertIn("Registered cohabitation contracts", rows["pl-10-1-1"]["meaning_yes"])
        again = vm.write_rules(self.conn, "pl", "2026-10-12", self.cfg, QUIET, wl=PL_WL)
        self.assertEqual(again["written"], 0)          # unchanged lines are not rewritten

    def test_person_then_judge_then_rule(self):
        vm.write_rules(self.conn, "pl", "2026-10-11", self.cfg, QUIET, wl=PL_WL)
        vm.write_judged(self.conn, "pl", "pl-10-1-4", "To kill it.", "To keep it.", "2026-10-11")
        vm.write_rules(self.conn, "pl", "2026-10-12", self.cfg, QUIET, wl=PL_WL)
        self.assertEqual(vm.stored(self.conn, "pl")["pl-10-1-4"]["source"], "judge")
        self.write_override('meanings:\n  "pl-10-1-1":\n    meaning_yes: "To pass the bill."\n'
                            '    meaning_no: "To stop it."\n    by: "Christopher"\n'
                            '  "pl-10-1-2":\n    meaning_yes: "Only one side."\n')
        got = vm.lookup_many(self.conn, "pl", ["pl-10-1-1", "pl-10-1-2", "pl-10-1-4"], self.cfg,
                             wl=PL_WL)
        self.assertEqual((got["pl-10-1-1"]["source"], got["pl-10-1-1"]["by"]), ("person", "Christopher"))
        self.assertEqual(got["pl-10-1-4"]["yes"], "To kill it.")
        self.assertEqual(got["pl-10-1-2"]["source"], "rule")      # the half entry is ignored
        _, problems = vm.overrides("pl", self.cfg)
        self.assertEqual(problems, ["pl-10-1-2: needs both meaning_yes and meaning_no"])
        self.assertIn("written by Christopher", vm.line(got["pl-10-1-1"], "pl"))

    def test_a_line_naming_citizengo_is_refused(self):
        self.write_override('meanings:\n  "pl-10-1-1":\n    meaning_yes: "With CitizenGO."\n'
                            '    meaning_no: "x"\n')
        good, problems = vm.overrides("pl", self.cfg)
        self.assertEqual(good, {})
        self.assertIn("stance file", problems[0])

    def test_annotate_puts_meaning_on_watched_and_tier1_votes_only(self):
        items = [{"cc": "pl", "kind": "vote", "key": "pl-10-1-1", "watched": True, "tier": 1},
                 {"cc": "pl", "kind": "vote", "key": "pl-10-1-5", "watched": False, "tier": 2},
                 {"cc": "pl", "kind": "new", "key": "10/2110", "watched": True, "tier": 1}]
        vm.annotate(self.conn, items, self.cfg)
        self.assertIn("meaning", items[0])
        self.assertNotIn("meaning", items[1])
        self.assertNotIn("meaning", items[2])


class QueueTests(StoreBase):
    WLS = {"pl": PL_WL}

    def path(self):
        return os.path.join(self.tmp.name, "q.md")

    def test_only_what_the_rules_could_not_do_is_offered(self):
        todo = vm.pending(self.conn, ["pl"], self.cfg, self.WLS)
        keys = [p["row"]["key"] for p in todo]
        # 10/999 has no English description (quality 'title'); the rest are full.
        self.assertEqual(keys, ["pl-10-1-6"])

    def test_round_trip_with_refusals(self):
        n, _ = tool.queue_out(self.conn, self.path(), "2026-10-11", 10, ["pl"], QUIET, self.cfg,
                              self.WLS)
        self.assertEqual(n, 1)
        text = read(self.path())
        self.assertIn(tool.QUEUE_MARKER, text)
        self.assertIn("### item: pl:pl-10-1-6", text)
        self.assertIn("rules' draft", text)
        text = text.replace("YES: \nNO: ", "YES: To pass the abortion bill as a whole.\n"
                                           "NO: Against passing it.")
        text += ("\n### item: pl:pl-10-1-1\nYES: To pass it.\nNO: no.\n"
                 "\n### item: pl:nope\nYES: x\n")
        write(self.path(), text)
        logs = []
        done, refused, blank = tool.queue_in(self.conn, self.path(), "2026-10-11", ["pl"],
                                             logs.append, self.cfg, self.WLS)
        self.assertEqual((done, refused, blank), (1, 2, 0))
        self.assertEqual(vm.stored(self.conn, "pl")["pl-10-1-6"]["source"], "judge")
        self.assertEqual(vm.judged_on(self.conn, "2026-10-11"), {"pl"})
        self.assertEqual(vm.pending(self.conn, ["pl"], self.cfg, self.WLS), [])
        self.assertTrue(any("session queue: 1 item(s) scored" in x for x in logs))

    def test_unclear_is_kept_and_not_offered_again(self):
        tool.queue_out(self.conn, self.path(), "2026-10-11", 10, ["pl"], QUIET, self.cfg, self.WLS)
        text = read(self.path()).replace("YES: \n", "YES: UNCLEAR\n")
        write(self.path(), text)
        tool.queue_in(self.conn, self.path(), "2026-10-11", ["pl"], QUIET, self.cfg, self.WLS)
        self.assertEqual(vm.stored(self.conn, "pl")["pl-10-1-6"]["source"], "judge-unclear")
        self.assertEqual(vm.pending(self.conn, ["pl"], self.cfg, self.WLS), [])
        got = vm.lookup(self.conn, "pl", "pl-10-1-6", self.cfg, wl=PL_WL)
        self.assertEqual(got["source"], "rule")            # the rule line still shows

    def test_a_foreign_file_and_blank_lines(self):
        write(self.path(), "# x\n### item: pl:pl-10-1-6\nYES: a\nNO: b\n")
        self.assertIsNone(tool.queue_in(self.conn, self.path(), "2026-10-11", ["pl"], QUIET,
                                        self.cfg, self.WLS))
        tool.queue_out(self.conn, self.path(), "2026-10-11", 10, ["pl"], QUIET, self.cfg, self.WLS)
        self.assertEqual(tool.queue_in(self.conn, self.path(), "2026-10-11", ["pl"], QUIET,
                                       self.cfg, self.WLS), (0, 0, 1))


class ShownTests(StoreBase):
    def item(self):
        return {"cc": "pl", "kind": "vote", "key": "pl-10-1-1", "date": "2026-05-29",
                "title": "głosowanie nad całością projektu.", "status": None, "areas": [9],
                "tier": 1, "watched": True, "url": None, "lines": ["Tally: Za 230, Przeciw 198."],
                "terms": [], "body": None, "refs": [], "takeaway": None, "group": None,
                "group_title": None, "final": True, "own": None, "watch_key": "10/2110"}

    def test_edition_brief_profile_and_guide_show_it(self):
        from src import country_edition as ce
        from src import country_vote_brief as vb
        from src import member_profiles as mp
        it = vm.annotate(self.conn, [self.item()], self.cfg)[0]
        lines = ce.item_lines(it, PL_WL)
        self.assertTrue(any(x.strip().startswith("Meaning: **Za** = to pass") for x in lines))
        brief = vb.brief_markdown("pl", [it], ["watched"], generated="2026-10-11")
        self.assertIn("Meaning: **Za** = to pass", brief)
        dm = vb.dm_entry("pl", [it], ["watched"], "https://example.org/brief")
        self.assertIn("Meaning: *Za* = to pass", dm)
        v = {"meaning": it["meaning"], "position": "NO"}
        self.assertEqual(mp.meaning_of(mp.SPECS["pl"], v),
                         "their vote meant: against passing it (by rule, from the vote's wording "
                         "and the bill)")
        c5.draft(c5.connect_ro(os.path.join(self.tmp.name, "store.db")), "pl", self.cfg,
                 "2026-10-10", QUIET, wl=PL_WL)
        guide = c5.signoff_markdown("pl", self.cfg)
        self.assertIn("Meaning: **Za** = to pass 10/2110", guide)
        self.assertIn("Meaning: **Za** = to reject 10/2110", guide)

    def test_debate_pack_label_is_translated(self):
        from src import debatepack_i18n as i18n
        m = {"yes": "To pass it.", "no": "Against it.", "source": "judge"}
        self.assertTrue(vm.line(m, "pl", prefix=i18n.text("pl", "meaning")).startswith(
            "Znaczenie (po angielsku): **Za** = to pass it;"))
        for lang, table in i18n.TEXT.items():
            self.assertIn("meaning", table, lang)


class JobTests(unittest.TestCase):
    def test_meanings_follow_the_scores_within_one_budget(self):
        text = read(os.path.join(ROOT, "jobs", "editions-session-judge.sh"))
        rules = text.index("tools/vote_meanings.py --rules")
        scores = text.index("tools/session_judge.sh tools/edition_judge.py")
        meanings = text.index("tools/session_judge.sh tools/vote_meanings.py")
        self.assertLess(rules, scores)
        self.assertLess(scores, meanings)
        self.assertIn('left=$((MAX - ${offered:-$MAX}))', text)
        self.assertIn("SESSION_JUDGE_PROMPT", text)
        judge = read(os.path.join(ROOT, "tools", "session_judge.sh"))
        self.assertIn('PROMPT="$SESSION_JUDGE_PROMPT"', judge)
        self.assertIn("unset ANTHROPIC_API_KEY", judge)

    def test_the_table_is_declared(self):
        from src import db
        self.assertIn("vote_meanings", db.TABLES)
        self.assertIn("CREATE TABLE IF NOT EXISTS vote_meanings", db.SCHEMA)


if __name__ == "__main__":
    unittest.main()
