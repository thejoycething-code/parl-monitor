"""The new countries' debate report (src/country_debatereport.py,
tools/country_debate_report.py). A small French store and speeches in memory;
no network, no Slack (a fake transport), no AI."""

import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src import country5ca as c5  # noqa: E402
from src import country_debatereport as cdr  # noqa: E402
from src import fr_store  # noqa: E402

DAY = "2026-10-14"
TITLE = "Proposition de loi relative au droit à l'aide à mourir (DLR1)"
MEMBERS = [("PA1", "Jean Dupont", "RN"), ("PA2", "Marie Martin", "LFI"),
           ("PA3", "Paul Petit", "DR")]
VOTES = {"PA1": "contre", "PA2": "pour", "PA3": "contre"}
TEXTS = {
    "PA1": "Monsieur le président, chers collègues. Nous devons protéger les plus fragiles de notre "
           "société, et ce texte sur l'aide à mourir les expose à une pression terrible. Les soins "
           "palliatifs manquent dans un département sur cinq. Nous voterons contre ce texte.",
    "PA2": "Chers collègues, ce texte est une avancée pour la liberté de chacun. L'aide à mourir est "
           "attendue par une grande majorité des Français. Nous voterons pour ce texte, avec fierté.",
    "PA3": "Je m'interroge sur les garde-fous de cette aide à mourir. Le délai de réflexion de deux "
           "jours est trop court. Nous avons déposé des amendements pour le porter à quinze jours.",
}
QUIET = lambda *a, **k: None  # noqa: E731


def _tool():
    spec = importlib.util.spec_from_file_location(
        "country_debate_report", os.path.join(ROOT, "tools", "country_debate_report.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_store(path):
    conn = sqlite3.connect(path)
    fr_store.ensure_schema(conn)
    cs.ensure_schema(conn, ["fr"])
    groups = {}
    for ref, name, grp in MEMBERS:
        org = groups.setdefault(grp, "PO{0}".format(len(groups) + 1))
        conn.execute("INSERT OR IGNORE INTO fr_groups (organe_ref, chamber, abbr) VALUES (?,?,?)",
                     (org, "an", grp))
        conn.execute("INSERT INTO fr_members (acteur_ref, chamber, name, group_ref, current) "
                     "VALUES (?,?,?,?,1)", (ref, "an", name, org))
    conn.execute("INSERT INTO fr_dossiers (dossier_ref, title) VALUES ('DLR1', ?)",
                 ("Proposition de loi relative au droit à l'aide à mourir",))
    conn.execute("INSERT INTO fr_divisions (division_key, chamber, legislature, number, date, "
                 "result, title, dossier_ref, pour, contre, abstentions, areas, own_areas, tier) "
                 "VALUES ('an-17-1','an',17,1,?,'adopté',"
                 "'l''ensemble de la proposition de loi relative au droit à l''aide à mourir "
                 "(première lecture).','DLR1',1,2,0,'[2]','[2]',1)", (DAY,))
    grp = {m[0]: groups[m[2]] for m in MEMBERS}
    for ref, pos in VOTES.items():
        conn.execute("INSERT INTO fr_votes (division_key, acteur_ref, position, group_ref) "
                     "VALUES ('an-17-1',?,?,?)", (ref, pos, grp[ref]))
    for i, (ref, name, party) in enumerate(MEMBERS):
        prefix = "M." if ref != "PA2" else "Mme"
        conn.execute("INSERT INTO fr_speeches (speech_id, doc_id, date, chamber, debate_id, debate, "
                     "speaker, party, role, person_id, excerpt, text, url, areas, matched_terms, tier) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     ("CRSANR#{0}".format(i), "CRSANR", DAY, None, "d1", TITLE,
                      "{0} {1}".format(prefix, name), party, "member", ref, TEXTS[ref][:80],
                      TEXTS[ref], "https://example.org/cr#{0}".format(i), "[2]",
                      json.dumps(["aide à mourir", "soins palliatifs"]), 1))
    conn.execute("INSERT INTO fr_speeches (speech_id, doc_id, date, chamber, debate_id, debate, "
                 "speaker, party, role, person_id, excerpt, text, url, areas, matched_terms, tier) "
                 "VALUES ('CRSANR#9','CRSANR',?,NULL,'d1',?,'Mme la ministre',NULL,'ministre',NULL,"
                 "'x','Le Gouvernement soutient ce texte sur l''aide à mourir.','u','[2]','[]',1)",
                 (DAY, TITLE))
    conn.commit()
    conn.close()


def write_stance(cfg, status="draft"):
    signed = ('    confirmed_by: "Christopher"\n    confirmed_on: "2026-10-15"\n'
              if status == "confirmed" else "")
    with open(c5.stance_path("fr", cfg), "w", encoding="utf-8") as h:
        h.write(c5.header("fr") + """
bill_directions:

divisions:
  - key: "an-17-1"
    status: {0}
{1}    areas: [2]
    yea: -2
    why_yea: "For assisted dying."
    nay: 2
    why_nay: "Against assisted dying."
""".format(status, signed))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "store.db")
        self.cfg = os.path.join(self.tmp.name, "config")
        self.out = os.path.join(self.tmp.name, "report")
        os.makedirs(self.cfg)
        make_store(self.db)
        write_stance(self.cfg)
        self.tool = _tool()

    def tearDown(self):
        self.tmp.cleanup()

    def generate(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch.object(c5.SPECS["fr"], "watchlist_fn", lambda: {}):
            rc = self.tool.main(["--country", "fr", "--date", DAY, "--debate", "d1", "--db", self.db,
                                 "--config-dir", self.cfg, "--out", self.out, "--no-dm"] + list(extra))
        return rc, out.getvalue()

    def read(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as fh:
            return fh.read()

    def translate_all(self, by="Chris"):
        import yaml
        path = os.path.join(self.out, "translations.yaml")
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        for k, v in raw["items"].items():
            v["english"] = "English for " + k
            v["by"] = by
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(raw, fh, allow_unicode=True)

    def render(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.tool.main(["--report", self.out, "--render", "--config-dir", self.cfg])
        return out.getvalue()


class GenerateTests(Base):
    def test_awaiting_sign_off_report(self):
        rc, out = self.generate()
        self.assertEqual(rc, 0)
        report = self.read("report.md")
        self.assertIn("AWAITING SIGN-OFF", report)
        self.assertIn("places nobody", report)
        for text in TEXTS.values():                         # quotations verbatim
            self.assertIn(text.split(".")[1].strip()[:40], report)
        self.assertNotIn("with us", report)
        self.assertNotIn("against us", report)
        self.assertIn("Voted **Contre** on", report)
        self.assertIn("on this bill", report)               # DLR1 printed in the title
        self.assertIn("Mme la ministre also spoke (ministre)", report)
        self.assertIn("[translation pending]", report)
        with open(os.path.join(self.out, "report.json")) as fh:
            state = json.load(fh)
        self.assertFalse(state["signed"])
        self.assertTrue(any("translation(s) pending" in p for p in state["problems"]))
        social = self.read("social.md")
        self.assertIn("DRAFT, AWAITING SIGN-OFF", social)
        self.assertIn("[ACTION LINK]", social)

    def test_store_is_never_written(self):
        before = os.path.getmtime(self.db), os.path.getsize(self.db)
        self.generate()
        self.assertEqual(before, (os.path.getmtime(self.db), os.path.getsize(self.db)))

    def test_list(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.tool.main(["--country", "fr", "--date", DAY, "--db", self.db, "--list"])
        self.assertEqual(rc, 0)
        self.assertIn("d1", out.getvalue())
        self.assertIn("4 speakers", out.getvalue())       # the minister listed too

    def test_signed_report_places_from_confirmed_readings_only(self):
        write_stance(self.cfg, "confirmed")
        self.generate()
        report = self.read("report.md")
        self.assertNotIn("AWAITING SIGN-OFF", report)
        self.assertIn("Voted with us: M. Jean Dupont, M. Paul Petit.", report)
        self.assertIn("Voted against us: Mme Marie Martin.", report)
        self.assertIn("confirmed by Christopher, 15 October 2026", report)

    def test_contradiction_needs_a_read_and_a_confirmed_reading(self):
        reads = os.path.join(self.tmp.name, "reads.yaml")
        with open(reads, "w", encoding="utf-8") as fh:
            fh.write('reads:\n  "Mme Marie Martin": "against"\n  "M. Jean Dupont": "with"\n')
        self.generate("--reads", reads)
        self.assertNotIn("sounded unlike", self.read("report.md"))     # draft: nothing named
        write_stance(self.cfg, "confirmed")
        self.generate("--reads", reads)
        report = self.read("report.md")
        self.assertNotIn("sounded unlike", report)        # both consistent with their votes
        with open(reads, "w", encoding="utf-8") as fh:
            fh.write('reads:\n  "Mme Marie Martin": "with"\n')
        self.generate("--reads", reads)
        self.assertIn("they sounded unlike their vote (WOBBLE)", self.read("report.md"))


class TranslationTests(Base):
    def test_session_judge_round_trip(self):
        self.generate()
        q = os.path.join(self.tmp.name, "queue.md")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.tool.main(["--report", self.out, "--queue-out", q, "--limit", "2"])
        self.assertIn("session queue: 2 item(s) written", out.getvalue())
        with open(q, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(cdr.QUEUE_MARKER, text)
        ids = [l.split(": ")[1] for l in text.splitlines() if l.startswith("### item: ")]
        text = text.replace("TRANSLATION: \n", "TRANSLATION: Some English — here\n", 1)
        text += "### item: x-unknown\nTRANSLATION: nope\n"
        with open(q, "w", encoding="utf-8") as fh:
            fh.write(text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.tool.main(["--report", self.out, "--queue-in", q])
        self.assertIn("session queue: 1 item(s) scored", out.getvalue())
        self.assertIn("refused: x-unknown", out.getvalue())
        tr = cdr.load_translations(self.out)
        self.assertEqual(tr[ids[0]]["english"], "Some English, here")    # no em dash
        self.assertEqual(tr[ids[0]]["by"], "the free session judge")
        # a regenerated report keeps the translation
        self.generate()
        self.assertEqual(cdr.load_translations(self.out)[ids[0]]["english"], "Some English, here")
        self.render()
        self.assertIn("**In English:** Some English, here", self.read("report.md"))   # the title first
        self.assertIn("Le Gouvernement soutient ce texte", self.read("report.md"))    # a short turn whole

    def test_prompt(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.tool.main(["--prompt"])
        self.assertIn("TRANSLATION:", out.getvalue())


class ApprovalTests(Base):
    def fake(self):
        calls = []

        def transport(url, payload, headers):
            calls.append((url, payload))
            if url.endswith("canvases.create"):
                return {"ok": True, "canvas_id": "F123"}
            return {"ok": True, "ts": "1.2"}
        return calls, transport

    def publish(self, transport, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                mock.patch("src.publish.load_secrets", lambda: {"slack_bot_token": "x",
                                                                "slack_dm_user_id": "USOMEONE",
                                                                "slack_channel_id": "CCHANNEL"}):
            rc = self.tool.main(["--report", self.out, "--publish"] + list(extra), transport=transport)
        return rc, out.getvalue()

    def test_publish_refuses_without_approval_then_shares_with_chris_alone(self):
        self.generate()
        self.translate_all()
        self.render()
        calls, transport = self.fake()
        rc, out = self.publish(transport)
        self.assertEqual(rc, 2)
        self.assertIn("not approved", out)
        self.assertEqual(calls, [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.tool.main(["--report", self.out, "--approve", "--by", "Chris"])
        rc, out = self.publish(transport)
        self.assertEqual(rc, 0, out)
        urls = [u for u, _ in calls]
        self.assertEqual(urls[0], "https://slack.com/api/canvases.create")
        access = calls[1][1]
        self.assertEqual(access["user_ids"], [cdr.CHRIS])               # Chris alone
        self.assertNotIn("channel_ids", access)
        self.assertEqual(calls[2][1]["channel"], cdr.CHRIS)              # the DM, not a channel
        for _, payload in calls:
            self.assertNotIn("CCHANNEL", json.dumps(payload))
        body = calls[0][1]["document_content"]["markdown"]
        self.assertIn("Approved by Chris", body)
        self.assertIn("AWAITING SIGN-OFF", body)
        # a re-publish rewrites the same canvas in place
        calls2, transport2 = self.fake()
        rc, out = self.publish(transport2)
        self.assertEqual([u for u, _ in calls2], ["https://slack.com/api/canvases.edit"])
        self.assertEqual(calls2[0][1]["canvas_id"], "F123")

    def test_edit_after_approval_lapses_it(self):
        self.generate()
        self.translate_all()
        self.render()
        with contextlib.redirect_stdout(io.StringIO()):
            self.tool.main(["--report", self.out, "--approve", "--by", "Chris"])
        with open(os.path.join(self.out, "report.md"), "a", encoding="utf-8") as fh:
            fh.write("\nAn edit.\n")
        calls, transport = self.fake()
        rc, out = self.publish(transport)
        self.assertEqual(rc, 2)
        self.assertIn("changed after the approval", out)

    def test_failed_checks_refuse_unless_forced_and_samples_never(self):
        self.generate()                                   # translations pending
        with contextlib.redirect_stdout(io.StringIO()):
            self.tool.main(["--report", self.out, "--approve", "--by", "Chris"])
        calls, transport = self.fake()
        rc, out = self.publish(transport)
        self.assertEqual(rc, 2)
        self.assertIn("check(s) failed", out)
        rc, out = self.publish(transport, "--force")
        self.assertEqual(rc, 0)
        self.generate("--sample")
        with contextlib.redirect_stdout(io.StringIO()):
            self.tool.main(["--report", self.out, "--approve", "--by", "Chris"])
        rc, out = self.publish(transport, "--force")
        self.assertEqual(rc, 2)
        self.assertIn("SAMPLE", out)

    def test_approval_dm_goes_to_chris_alone(self):
        self.generate()
        sent = []
        with mock.patch("src.publish.load_secrets", lambda: {"slack_bot_token": "x",
                                                             "slack_dm_user_id": "USOMEONE"}), \
                mock.patch("src.publish._post_json",
                           lambda url, payload, headers: sent.append(payload) or {"ok": True, "ts": "1"}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.tool.main(["--report", self.out, "--render", "--dm", "--config-dir", self.cfg])
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["channel"], cdr.CHRIS)
        self.assertIn("for approval", sent[0]["text"])
        self.assertIn("--approve --by", sent[0]["text"])
        self.assertNotIn("published", sent[0]["text"].split("---")[0].replace("Nothing is published", ""))


class CheckTests(unittest.TestCase):
    def test_verdict_words_refused_before_sign_off_but_not_in_quotes(self):
        inp = {"speakers": [], "cc": "fr", "title": "t", "divisions": []}
        problems = cdr.checks(inp, "# x\n\n> AWAITING SIGN-OFF\n\n> \"a win for us\"\n", "", {"signed": False}, {})
        self.assertFalse(any("verdict" in p for p in problems))
        problems = cdr.checks(inp, "# x\n\nAWAITING SIGN-OFF. A big win.\n", "", {"signed": False}, {})
        self.assertTrue(any("verdict" in p for p in problems))

    def test_verbatim(self):
        self.assertTrue(cdr.verbatim("Nous devons protéger les plus fragiles.",
                                     "Bonjour. Nous devons  protéger les plus fragiles. Merci."))
        self.assertFalse(cdr.verbatim("Nous devons protéger tout le monde.", "Nous devons protéger."))

    def test_countries_are_the_speech_collectors(self):
        # HR, SK, PL and BR since their speeches (11 October 2026, gaps-speeches).
        self.assertEqual(set(cdr.COUNTRIES), {"nl", "ch", "at", "fr", "be", "hr", "sk", "pl",
                                              "br"})


if __name__ == "__main__":
    unittest.main()
