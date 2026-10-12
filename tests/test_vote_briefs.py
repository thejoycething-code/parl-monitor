"""The same-day vote briefs for the US, Ireland and Australia (9 October 2026).

No network. The payloads are REAL, recorded on 9 October 2026:
tests/fixtures/us_division_brief (two Clerk roll calls, the Clerk's error page
for a roll that does not exist, two BILLSTATUS files), tests/fixtures/us_senate,
tests/fixtures/ie and tests/fixtures/au (the collectors' own fixtures).
"""

import datetime as dt
import glob
import gzip
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import vote_brief  # noqa: E402
from src.http import FetchError  # noqa: E402
import au_division_brief as aub  # noqa: E402
import ie_division_brief as ieb  # noqa: E402
import us_division_brief as usb  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def raw(*parts):
    path = os.path.join(FIX, *parts)
    with (gzip.open if path.endswith(".gz") else open)(path, "rb") as fh:
        return fh.read()


# --- the US ------------------------------------------------------------------

ROLL_266 = raw("us_division_brief", "roll-2026-266.xml.gz")
ROLL_286 = raw("us_division_brief", "roll-2026-286.xml.gz")
CLERK_ERROR = raw("us_division_brief", "roll-2026-315-error.xml.gz")
BILLS = {"hr/8800": raw("us_division_brief", "billstatus-119-hr-8800.xml.gz"),
         "hr/6500": raw("us_division_brief", "billstatus-119-hr-6500.xml.gz")}


def quorum_roll(n):
    """Roll 286's real file renumbered as an off-ground quorum call: 20 July
    before roll 266 (21 July), 1 August after it."""
    text = ROLL_286.decode("utf-8")
    text = re.sub(r"<rollcall-num>\d+", "<rollcall-num>{0}".format(n), text)
    text = re.sub(r"<legis-num>[^<]*", "<legis-num>QUORUM", text)
    text = re.sub(r"<action-date>[^<]*", "<action-date>{0}".format("20-Jul-2026" if n < 266 else "1-Aug-2026"), text)
    text = re.sub(r"<vote-question>[^<]*", "<vote-question>Call of the House", text)
    return text.encode("utf-8")


class FakeClerk:
    """The Clerk (rolls 1..top, holes answer with its error page) and GovInfo."""

    def __init__(self, top=286, holes=()):
        self.top, self.holes, self.fetched = top, set(holes), []

    def get_bytes(self, url, feed, slug, archive=True, **_kw):
        self.fetched.append(url)
        hit = re.search(r"evs/2026/roll(\d+)\.xml$", url)
        if hit:
            n = int(hit.group(1))
            if n > self.top or n in self.holes:
                return CLERK_ERROR
            return {266: ROLL_266, 286: ROLL_286}.get(n) or quorum_roll(n)
        hit = re.search(r"BILLSTATUS/119/(\w+)/BILLSTATUS-119\w+?(\d+)\.xml$", url)
        if hit and "{0}/{1}".format(hit.group(1), hit.group(2)) in BILLS:
            return BILLS["{0}/{1}".format(hit.group(1), hit.group(2))]
        raise FetchError(url, feed, slug, 1, "not in the fixtures")


class UsHouseTests(unittest.TestCase):
    def test_the_newest_roll_is_found_past_the_clerks_200_error_page(self):
        self.assertEqual(usb.newest_roll(FakeClerk(), 2026), 286)

    def test_a_hole_does_not_stop_the_search_short(self):
        self.assertEqual(usb.newest_roll(FakeClerk(holes={256, 284}), 2026), 286)

    def _votes(self, since="2026-07-21"):
        from src import filter as filt
        import us_rollcalls as usr
        return usb.house_votes(FakeClerk(), since, "2026-09-02",
                               filt.load_taxonomy(usr.TAXONOMY), usr.empty_watchlist(), key=None,
                               log=lambda *_: None)

    def test_the_walk_stops_at_the_window_and_classifies_as_the_collector_does(self):
        votes = {v["key"]: v for v in self._votes()}
        self.assertIn("house-119-2-266", votes)
        self.assertIn("house-119-2-286", votes)
        self.assertNotIn("house-119-2-265", votes)        # before 21 July: never read
        boebert = votes["house-119-2-266"]
        # BILLSTATUS gave the amendment its purpose, and the purpose alone
        # classifies it: not the NDAA's areas.
        self.assertEqual(boebert["matched"], "amendment")
        self.assertIn("biological sex", boebert["amendment"])
        self.assertEqual(boebert["areas"], [5])
        self.assertEqual(boebert["result"], "Failed")
        self.assertEqual(dict(boebert["parties"])["Republican"]["Yea"], 211)
        cr = votes["house-119-2-286"]
        self.assertEqual(cr["matched"], "bill only")
        self.assertTrue(cr["on_ground"])
        self.assertFalse(votes["house-119-2-285"]["on_ground"])   # the quorum call

    def test_the_stance_status_is_read_never_the_direction(self):
        self.assertEqual(vote_brief.stance_status("us", "house-119-2-266"),
                         "reading awaiting sign-off (a draft in config/us_stance.yaml).")
        self.assertIn("no 5CA reading", vote_brief.stance_status("us", "house-119-2-286"))


class UsSenateTests(unittest.TestCase):
    def test_the_menu_dates_each_vote(self):
        rows = usb.menu_dates(raw("us_senate", "menu_119_1.xml"), 2025)
        self.assertIn((659, "PN373", "2025-12-18"), rows)

    def test_a_senate_vote_briefs_with_its_own_purpose_and_its_bill(self):
        from src import filter as filt
        import us_rollcalls as usr
        d = usr.parse_senate_vote(raw("us_senate", "vote_119_1_00011.xml"))
        v = usb.to_vote(d, None, filt.load_taxonomy(usr.TAXONOMY), usr.empty_watchlist())
        self.assertEqual(v["key"], "senate-119-1-11")
        self.assertTrue(v["on_ground"])
        self.assertEqual(v["matched"], "own text")
        self.assertIn("senate.gov", v["url"])
        self.assertIn("awaiting sign-off", vote_brief.stance_status("us", v["key"]))


# --- Ireland -----------------------------------------------------------------

class FakeOireachtas:
    def __init__(self):
        self.votes = json.loads(raw("ie", "votes.json"))
        self.bills = json.loads(raw("ie", "legislation.json"))
        self.members = {"dail/34": json.loads(raw("ie", "members-dail-34.json.gz")),
                        "seanad/27": json.loads(raw("ie", "members-seanad-27.json.gz"))}

    def get_json(self, url, feed, slug, archive=True, **_kw):
        if "/votes?" in url:
            if "house%2Fdail%2F34" in url or "house/dail/34" in url:
                ds = re.search(r"date_start=([\d-]+)", url).group(1)
                de = re.search(r"date_end=([\d-]+)", url).group(1)
                rows = [r for r in self.votes["results"] if ds <= r["division"]["date"] <= de
                        and r["division"]["house"].get("houseCode") == "dail"]
                return {"head": {}, "results": rows}
            return {"head": {}, "results": []}
        if "/legislation?" in url:
            return self.bills
        if "/members?" in url:
            for k, v in self.members.items():
                if k.replace("/", "%2F") in url or k in url:
                    return v
        raise FetchError(url, feed, slug, 1, "not in the fixtures")

    def get_bytes(self, url, feed, slug, **_kw):
        raise FetchError(url, feed, slug, 1, "no transcript in the fixtures")


class IrelandTests(unittest.TestCase):
    def _votes(self):
        return {v["key"]: v for v in ieb.collect(FakeOireachtas(), "2026-06-15", "2026-06-18",
                                                 log=lambda *_: None)}

    def test_the_three_day_wait_division_joins_its_bill_and_counts_party_on_the_day(self):
        v = self._votes()["dail/34/2026-06-17/vote_149"]
        self.assertTrue(v["on_ground"])
        self.assertEqual(v["matched"], "bill only")     # the debate title names no term; the Bill does
        self.assertEqual(v["result"], "Carried")
        self.assertEqual(v["tally"], "Tá 86, Níl 70, Staon 0")
        parties = dict(v["parties"])
        # config/ie_stance.yaml's lobbies line, counted from the store: FF 12 Tá, 30 Níl.
        self.assertEqual((parties["Fianna Fáil"]["Tá (Yes)"], parties["Fianna Fáil"]["Níl (No)"]), (12, 30))
        self.assertTrue(any("joined by its debate section" in n for n in v["notes"]))
        self.assertIn("awaiting sign-off", vote_brief.stance_status("ie", v["key"]))
        self.assertEqual(v["file_key"], "dail-34-2026-06-17-vote_149")

    def test_the_window_is_kept(self):
        self.assertEqual(list(self._votes()), ["dail/34/2026-06-17/vote_149"])


# --- Australia ----------------------------------------------------------------

LISTING = ('<pre><a href="2026-06-30.xml">2026-06-30.xml</a>          2026-07-01 09:05  1.1M\n'
           '<a href="2026-07-01.xml">2026-07-01.xml</a>          2026-07-02 09:05  0.9M\n</pre>')


class FakeOpenAustralia:
    def __init__(self):
        self.days = []

    def get_text(self, url, feed, slug, archive=True, **_kw):
        if "senate_debates" in url:
            return LISTING
        return '<pre><a href="2026-06-30.xml">2026-06-30.xml</a>          2026-07-01 09:05  1.1M\n</pre>'

    def get_bytes(self, url, feed, slug, archive=True, **_kw):
        if url.endswith("senate_debates/2026-07-01.xml"):
            self.days.append(url)
            return raw("au", "senate_2026-07-01.xml")
        for name in ("people", "representatives", "senators"):
            if url.endswith("/members/{0}.xml".format(name)):
                return raw("au", name + ".xml")
        raise FetchError(url, feed, slug, 1, "not in the fixtures")


class AustraliaTests(unittest.TestCase):
    def test_a_file_posted_in_the_window_is_read_and_one_before_it_is_not(self):
        fake = FakeOpenAustralia()
        votes = aub.collect(fake, "2026-07-02", "2026-07-02", log=lambda *_: None)
        self.assertEqual(len(fake.days), 1)               # 30 June was posted on 1 July: not read
        v = {x["key"]: x for x in votes}["senate-2026-07-01-16"]
        self.assertTrue(v["on_ground"])
        self.assertEqual((v["result"], v["tally"]), ("Negatived", "Ayes 21, Noes 30, pairs 11"))
        # config/au_stance.yaml's lobbies line: Aye Liberal 14, No Labor 19.
        parties = dict(v["parties"])
        self.assertEqual(parties["Liberal Party"]["Aye"], 14)
        self.assertEqual(parties["Australian Labor Party"]["No"], 19)
        self.assertIn("awaiting sign-off", vote_brief.stance_status("au", v["key"]))

    def test_nothing_posted_reads_nothing(self):
        fake = FakeOpenAustralia()
        self.assertEqual(aub.collect(fake, "2026-08-01", "2026-08-02", log=lambda *_: None), [])
        self.assertEqual(fake.days, [])


# --- the shared rules ---------------------------------------------------------

def au_votes():
    return aub.collect(FakeOpenAustralia(), "2026-07-02", "2026-07-02", log=lambda *_: None)


class SpeakOnceTests(unittest.TestCase):
    def test_a_division_is_briefed_and_sent_once(self):
        out, sent, logs = tempfile.mkdtemp(), [], []
        send = lambda secrets, text: sent.append((secrets, text)) or {"ok": True, "message_ts": "1"}  # noqa: E731
        votes = au_votes()
        ours = [v for v in votes if v["on_ground"]]
        self.assertTrue(ours)
        vote_brief.run("au", votes, out_dir=out, secrets={}, log=logs.append, sender=send)
        self.assertEqual(len(sent), 1)                    # one DM for the run, however many
        self.assertEqual(sorted(os.listdir(out)),
                         sorted("au-division-{0}.md".format(v["file_key"]) for v in ours))
        before = {f: _read(os.path.join(out, f)) for f in os.listdir(out)}
        # the next slot: nothing rewritten, nothing resent
        vote_brief.run("au", au_votes(), out_dir=out, secrets={}, log=logs.append, sender=send,
                       generated="later")
        self.assertEqual(len(sent), 1)
        self.assertEqual(before, {f: _read(os.path.join(out, f)) for f in os.listdir(out)})
        self.assertTrue(any("already briefed" in line for line in logs))

    def test_force_rewrites_and_resends(self):
        out, sent = tempfile.mkdtemp(), []
        send = lambda secrets, text: sent.append(text) or {"ok": True}  # noqa: E731
        vote_brief.run("au", au_votes(), out_dir=out, secrets={}, log=lambda *_: None, sender=send)
        vote_brief.run("au", au_votes(), out_dir=out, secrets={}, log=lambda *_: None, sender=send,
                       force=True)
        self.assertEqual(len(sent), 2)

    def test_no_dm_prints_and_sends_nothing(self):
        out, logs = tempfile.mkdtemp(), []
        boom = mock.Mock(side_effect=AssertionError("sent"))
        vote_brief.run("au", au_votes(), out_dir=out, dm=False, log=logs.append, sender=boom)
        self.assertTrue(any("It would read" in line for line in logs))

    def test_the_dm_goes_to_christopher_alone(self):
        got = []
        vote_brief.run("au", au_votes(), out_dir=tempfile.mkdtemp(), log=lambda *_: None,
                       secrets={"slack_bot_token": "x", "slack_dm_user_id": "U_SOMEONE_ELSE"},
                       sender=lambda secrets, text: got.append(secrets) or {"ok": True})
        self.assertEqual(got[0]["slack_dm_user_id"], "U05LJP0BT61")


class NoVerdictTests(unittest.TestCase):
    def _all(self):
        names = vote_brief.area_names()
        from src import filter as filt
        import us_rollcalls as usr
        us = usb.house_votes(FakeClerk(), "2026-07-21", "2026-09-02", filt.load_taxonomy(usr.TAXONOMY),
                             usr.empty_watchlist(), log=lambda *_: None)
        ie = ieb.collect(FakeOireachtas(), "2026-06-15", "2026-06-18", log=lambda *_: None)
        for v in [x for x in us + ie + au_votes() if x["on_ground"]]:
            stance = vote_brief.stance_status(v["cc"], v["key"])
            yield v, (vote_brief.brief_markdown(v, names, stance, generated="now"),
                      vote_brief.dm_text(v, names, stance, "https://example/brief.md"))

    def test_no_brief_or_dm_names_a_winner(self):
        n = 0
        for v, texts in self._all():
            for text in texts:
                self.assertIsNone(vote_brief.VERDICT_WORDS.search(text), (v["key"], text[:200]))
                self.assertNotIn("\u2014", text)          # house style: no em dashes, even quoted
            n += 1
        self.assertGreaterEqual(n, 4)

    def test_a_draft_reading_is_never_rendered_only_its_status(self):
        """The three drafts in the fixtures carry why_yea/why_nay lines and
        +/- values; none of it may reach a brief before a human signs."""
        from src import readings5ca as r5
        for v, texts in self._all():
            entry = r5.load_stance(os.path.join(ROOT, "config", "{0}_stance.yaml".format(v["cc"]))).get(v["key"])
            if not entry:
                continue
            for text in texts:
                self.assertIn("reading awaiting sign-off", text)
                for field in ("why_yea", "why_nay", "aye_means", "flag"):
                    if entry.get(field):
                        self.assertNotIn(entry[field][:60], text, (v["key"], field))


# --- wiring ---------------------------------------------------------------------

WATCHES = {"us": ("US_DIVISION_WATCH", "US division watch"),
           "ie": ("IE_DIVISION_WATCH", "Ireland division watch"),
           "au": ("AU_DIVISION_WATCH", "Australia division watch")}


def _crons(text):
    return re.findall(r'^\s*-\s*cron:\s*"([^"]+)"', text, re.M)


def _expand(cron):
    """{(weekday 0-6 Sun=0, hour, minute)} a five-field cron names (lists and ranges)."""
    minute, hour, _dom, _mon, dow = cron.split()

    def field(f, lo, hi):
        if f == "*":
            return set(range(lo, hi + 1))
        out = set()
        for part in f.split(","):
            a, _, b = part.partition("-")
            out |= set(range(int(a), int(b or a) + 1))
        return out
    return {(d % 7, h, m) for d in field(dow, 0, 6) for h in field(hour, 0, 23) for m in field(minute, 0, 59)}


class WiringTests(unittest.TestCase):
    def _flow(self, cc):
        with open(os.path.join(ROOT, ".github", "workflows", "{0}-division-watch.yml".format(cc)),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_each_job_is_store_free_and_publishes_the_archive(self):
        for cc in WATCHES:
            job = _read(os.path.join(ROOT, "jobs", "{0}-division-watch.sh".format(cc)))
            self.assertIn("# mini_run: no-store", job)
            self.assertIn("tools/{0}_division_brief.py".format(cc), job)
            self.assertIn("python3 tools/raw_state.py --push", job)
            self.assertNotIn("db_state.py", job)
            self.assertIn("U05LJP0BT61", job)

    def test_each_workflow_is_gated_named_and_alerted_on(self):
        alert = _read(os.path.join(ROOT, ".github", "workflows", "alert.yml"))
        for cc, (gate, name) in WATCHES.items():
            flow = self._flow(cc)
            self.assertTrue(flow.startswith("name: {0}\n".format(name)), cc)
            self.assertIn("uses: ./.github/workflows/mini-check.yml", flow)
            self.assertIn("job: {0}".format(gate), flow)
            self.assertIn("needs.mini-check.outputs.run == 'true'", flow)
            self.assertIn("bash jobs/{0}-division-watch.sh".format(cc), flow)
            self.assertIn("group: parl-monitor-state", flow)
            self.assertNotIn("db_state.py", flow)
            self.assertIn('"{0}"'.format(name), alert)

    def test_the_senate_half_runs_on_github_only_and_ungated(self):
        import yaml
        doc = yaml.safe_load(self._flow("us"))
        senate = doc["jobs"]["senate"]
        self.assertNotIn("needs", senate)
        self.assertIn("50 0,3 * * 2-6", senate["if"])
        self.assertIn("50 0,3 * * 2-6", doc["jobs"]["mini-check"]["if"])     # no gate minute spent
        self.assertIn("US_DIVISION_CHAMBER: senate", self._flow("us"))

    def test_the_mini_runs_the_london_hours_the_crons_name_in_summer(self):
        """launchd keeps London time; the crons are UTC, written for BST
        (London = UTC+1), as for the UK division watch. The Senate cron has no
        Mini half."""
        import plistlib
        for cc in WATCHES:
            with open(os.path.join(ROOT, "ops", "launchd",
                                   "net.citizengo.parlmonitor.{0}-division-watch.plist".format(cc)), "rb") as fh:
                plist = plistlib.load(fh)
            self.assertEqual(plist["ProgramArguments"][-1], "{0}-division-watch".format(cc))
            self.assertTrue(plist["ProgramArguments"][1].startswith("/Users/christopherjoyce/runner/"))
            london = {(s["Weekday"] % 7, s["Hour"], s["Minute"]) for s in plist["StartCalendarInterval"]}
            utc = set()
            for cron in _crons(self._flow(cc)):
                if cron.startswith("50 0,3"):
                    continue
                utc |= _expand(cron)
            as_london = {((d + (h + 1) // 24) % 7, (h + 1) % 24, m) for d, h, m in utc}
            self.assertEqual(as_london, london, cc)

    def test_no_slot_collides_with_another_workflow(self):
        mine, others = {}, {}
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            name = os.path.basename(path)
            with open(path, encoding="utf-8") as fh:
                slots = set().union(*[_expand(c) for c in _crons(fh.read())] or [set()])
            (mine if name in {"{0}-division-watch.yml".format(c) for c in WATCHES} else others)[name] = slots
        taken = set().union(*others.values())
        for name, slots in mine.items():
            self.assertFalse(slots & taken, name)
            for other, theirs in mine.items():
                if other != name:
                    self.assertFalse(slots & theirs, (name, other))

    def test_the_gate_keeps_each_slot_apart(self):
        """mini_check counts a Mini run up to 75 minutes before a slot: the
        slots of one watch must be further apart than that."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("mini_check", os.path.join(ROOT, "tools", "mini_check.py"))
        mc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mc)
        utc = dt.timezone.utc
        # US: the Mini's 01:40 London (00:40 UTC in BST) run does not cover 04:40.
        now = dt.datetime(2026, 7, 22, 3, 45, tzinfo=utc)
        self.assertTrue(mc.decide("schedule", "40 0,3 * * 2-6", "2026-07-22T00:40:05Z", now, 75)[0])
        self.assertFalse(mc.decide("schedule", "40 0,3 * * 2-6", "2026-07-22T03:40:05Z", now, 75)[0])


if __name__ == "__main__":
    unittest.main()
