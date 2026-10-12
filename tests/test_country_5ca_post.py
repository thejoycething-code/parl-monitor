"""The new countries' 5CA posted to Chris alone (src/country5ca_post.py,
tools/country_5ca_post.py). Temporary stores and stance files, scratch
confirmations, a fake Slack transport; no network."""

import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country5ca as c5  # noqa: E402
from src import country5ca_post as cp  # noqa: E402
import country_5ca_post as tool  # noqa: E402
from test_country_5ca import PL_STANCE, PL_WL, QUIET, pl_store_at  # noqa: E402
from test_country_5ca_web import AT_STANCE, at_store_at  # noqa: E402

SECRETS = {"slack_bot_token": "xoxb-test", "slack_dm_user_id": "USOMEONEELSE",
           "slack_channel_id": "CPUBLIC"}


class FakeSlack:
    def __init__(self):
        self.calls = []
        self.n = 0

    def __call__(self, url, payload, headers):
        self.calls.append((url.rsplit("/", 1)[-1], payload))
        if url.endswith("canvases.create"):
            self.n += 1
            return {"ok": True, "canvas_id": "F{0:03d}".format(self.n)}
        return {"ok": True, "ts": "1.{0}".format(len(self.calls))}

    def names(self):
        return [c[0] for c in self.calls]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.cfg = os.path.join(t, "config")
        os.makedirs(self.cfg)
        with open(c5.stance_path("pl", self.cfg), "w", encoding="utf-8") as h:
            h.write(PL_STANCE)
        with open(c5.stance_path("at", self.cfg), "w", encoding="utf-8") as h:
            h.write(AT_STANCE)
        self.pl_db = os.path.join(t, "pl.db")
        pl_store_at(self.pl_db).close()
        self.at_db = os.path.join(t, "at.db")
        at_store_at(self.at_db)
        for cc, path, wl in (("pl", self.pl_db, PL_WL), ("at", self.at_db, {"XXVIII/UEA/26": {}})):
            ro = c5.connect_ro(path)
            c5.draft(ro, cc, self.cfg, "2026-10-10", QUIET, wl=wl)
            ro.close()
        self.state = os.path.join(t, "5ca", "country-post-state.json")
        self.slack = FakeSlack()

    def tearDown(self):
        self.tmp.cleanup()

    def run_(self, ccs=("pl", "at"), **kw):
        kw.setdefault("today", "2026-10-11")
        return cp.run(list(ccs), {"pl": self.pl_db, "at": self.at_db}, "/no/such.db", self.cfg,
                      self.state, secrets=dict(SECRETS), transport=self.slack, log=QUIET, **kw)

    def saved(self):
        with open(self.state, encoding="utf-8") as h:
            return json.load(h)

    def assert_chris_alone(self):
        for name, payload in self.slack.calls:
            self.assertNotIn("channel_ids", payload)
            if name == "canvases.access.set":
                self.assertEqual(payload["user_ids"], [cp.CHRIS])
            if name == "chat.postMessage":
                self.assertEqual(payload["channel"], cp.CHRIS)


class NothingConfirmedTests(Base):
    def test_no_call_no_message_no_state(self):
        done, gaps = self.run_()
        self.assertEqual((done, gaps), ([], []))
        self.assertEqual(self.slack.calls, [])
        self.assertFalse(os.path.exists(self.state))
        done, gaps = self.run_(refresh=True)
        self.assertEqual(self.slack.calls, [])

    def test_needs_no_store(self):
        done, gaps = cp.run(["pl", "at"], {}, "/no/such.db", self.cfg, self.state, refresh=True,
                            transport=self.slack, secrets=dict(SECRETS), log=QUIET)
        self.assertEqual((done, gaps, self.slack.calls), ([], [], []))


class ConfirmedTests(Base):
    def setUp(self):
        super().setUp()
        c5.confirm("pl", ["pl-10-1-1"], "Christopher", "2026-10-10", self.cfg, log=QUIET)

    def test_creates_canvas_for_chris_alone_and_one_dm(self):
        done, gaps = self.run_()
        self.assertEqual(gaps, [])
        self.assertEqual(len(done), 1)
        self.assertEqual(self.slack.names(),
                         ["canvases.create", "canvases.access.set", "chat.postMessage"])
        self.assert_chris_alone()
        body = self.slack.calls[0][1]["document_content"]["markdown"]
        self.assertIn("Anna Adamska", body)
        self.assertIn("Bartosz Bielski", body)
        self.assertIn("signed by Christopher on 2026-10-10", body)
        self.assertIn("Shared with Chris alone", body)
        self.assertNotIn("Frau F", body)                  # Austria: nothing confirmed
        st = self.saved()
        (key, rec), = st.items()
        self.assertTrue(key.startswith("pl|"))
        self.assertEqual(rec["canvas_id"], "F001")
        self.assertIn("F001", self.slack.calls[2][1]["text"])

    def test_drafts_place_no_one(self):
        self.run_()
        body = self.slack.calls[0][1]["document_content"]["markdown"]
        nobody = body.split("*No placement from the confirmed readings")[1]
        self.assertIn("Celina Czarnecka", nobody)          # only a draft says otherwise

    def test_rerun_rewrites_the_same_canvas(self):
        self.run_()
        self.slack.calls = []
        self.run_()
        self.assertEqual(self.slack.names(), ["canvases.edit", "chat.postMessage"])
        self.assertEqual(self.slack.calls[0][1]["canvas_id"], "F001")
        self.assertEqual(list(self.saved().values())[0]["canvas_id"], "F001")

    def test_refresh_is_silent_when_nothing_changed(self):
        self.run_()
        self.slack.calls = []
        done, gaps = self.run_(refresh=True)
        self.assertEqual((done, self.slack.calls), ([], []))

    def test_refresh_rewrites_when_confirmed_readings_change(self):
        self.run_()
        self.slack.calls = []
        c5.confirm("pl", ["pl-10-1-4"], "Christopher", "2026-10-12", self.cfg, log=QUIET)
        done, _ = self.run_(refresh=True)
        self.assertEqual(self.slack.names(), ["canvases.edit", "chat.postMessage"])
        self.assertEqual(self.slack.calls[0][1]["canvas_id"], "F001")
        self.assert_chris_alone()

    def test_withdrawn_reading_rewrites_with_no_placement(self):
        self.run_()
        self.slack.calls = []
        path = c5.stance_path("pl", self.cfg)
        with open(path, encoding="utf-8") as h:
            text = h.read().replace("status: confirmed", "status: draft")
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        self.run_(refresh=True)
        self.assertEqual(self.slack.names(), ["canvases.edit", "chat.postMessage"])
        body = self.slack.calls[0][1]["changes"][0]["document_content"]["markdown"]
        self.assertIn("No confirmed reading places anyone", body)
        self.assertNotIn("Anna Adamska", body)
        self.slack.calls = []
        self.run_(refresh=True)                            # withdrawn once, then quiet
        self.assertEqual(self.slack.calls, [])

    def test_dry_run_sends_nothing_and_writes_no_state(self):
        out = io.StringIO()
        with redirect_stdout(out):
            done, _ = cp.run(["pl"], {"pl": self.pl_db}, "/no", self.cfg, self.state,
                             dry_run=True, transport=self.slack, today="2026-10-11")
        self.assertEqual(len(done), 1)
        self.assertEqual(self.slack.calls, [])
        self.assertFalse(os.path.exists(self.state))
        self.assertIn("[dry run]", out.getvalue())
        self.assertIn("Anna Adamska", out.getvalue())

    def test_dm_only(self):
        self.run_(to="dm")
        self.assertEqual(self.slack.names(), ["chat.postMessage"])
        self.assertIn("Anna Adamska", self.slack.calls[0][1]["text"])
        self.assert_chris_alone()
        self.slack.calls = []
        self.run_(to="dm", refresh=True)
        self.assertEqual(self.slack.calls, [])

    def test_both_and_no_summary_dm(self):
        self.run_(to="both", announce=False)
        self.assertEqual(self.slack.names(),
                         ["canvases.create", "canvases.access.set", "chat.postMessage"])
        self.assert_chris_alone()

    def test_area_filter(self):
        done, _ = self.run_(area=5)
        self.assertEqual(done, [])
        done, _ = self.run_(area=9)
        self.assertEqual(len(done), 1)

    def test_missing_store_is_a_gap(self):
        done, gaps = cp.run(["pl"], {}, "/no/such.db", self.cfg, self.state,
                            transport=self.slack, secrets=dict(SECRETS), log=QUIET)
        self.assertEqual(done, [])
        self.assertTrue(gaps)
        self.assertEqual(self.slack.calls, [])

    def test_cli(self):
        rc = tool.main(["--cc", "pl", "--db-map", self.map(), "--config-dir", self.cfg,
                        "--state", self.state, "--today", "2026-10-11"],
                       transport=self.slack, secrets=dict(SECRETS))
        self.assertEqual(rc, 0)
        self.assert_chris_alone()
        self.assertIn("canvases.create", self.slack.names())

    def map(self):
        path = os.path.join(self.tmp.name, "stores.txt")
        with open(path, "w") as h:
            h.write("pl {0}\nat {1}\n".format(self.pl_db, self.at_db))
        return path


class DerivedTests(Base):
    def setUp(self):
        super().setUp()
        conn = sqlite3.connect(self.at_db)
        conn.execute("INSERT INTO at_votes (division_key, klub, position) VALUES "
                     "('k1', 'Fraktionslos', 'Dafür')")
        conn.execute("INSERT INTO at_members (pad, name, chamber, klub) VALUES "
                     "('9', 'Herr Wild', 'NR', 'Fraktionslos')")
        conn.commit()
        conn.close()
        c5.confirm("at", ["k1"], "Christopher", "2026-10-10", self.cfg, log=QUIET)

    def test_derived_labelled_and_non_attached_excluded(self):
        self.run_(ccs=("at",))
        body = self.slack.calls[0][1]["document_content"]["markdown"]
        self.assertIn("Frau F (FPÖ) [DERIVED]", body)
        self.assertIn("carry the group's vote", body)
        allies = body.split("*Allies")[1].split("*Opponents")[0]
        self.assertNotIn("Herr Wild", allies)
        excluded = body.split("*Excluded: non-attached or independent (1)*")[1]
        self.assertIn("Herr Wild", excluded)


class SecretsTests(unittest.TestCase):
    def test_forced_to_chris_and_no_channel(self):
        got = cp.secrets_for_chris(dict(SECRETS))
        self.assertEqual(got["slack_dm_user_id"], cp.CHRIS)
        self.assertNotIn("slack_channel_id", got)


if __name__ == "__main__":
    unittest.main()
