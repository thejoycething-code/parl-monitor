"""HTTP layer tests (handoff section 3).

Covers the observed-behaviour contract: User-Agent, raw archiving, retry with
backoff+jitter under a simulated timeout, throttle spacing, non-retryable 4xx,
and the per-host concurrency cap. The sleeper/clock/rng/opener are injected so
none of this touches the network or wall-clock time.
"""

import gzip
import os
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import http


class FakeResponse:
    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.closed = False

    def read(self):
        return self._body

    def close(self):
        self.closed = True


class ScriptedOpener:
    """Opener that replays a queue of outcomes: FakeResponse or an exception."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Recorder:
    """Deterministic sleeper + monotonic clock; sleeping advances the clock."""

    def __init__(self, start=0.0):
        self.t = start
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds

    def clock(self):
        return self.t


def make_client(tmp, opener, throttle=http.DEFAULT_THROTTLE, rng=lambda: 0.0):
    rec = Recorder()
    client = http.HttpClient(
        raw_dir=tmp,
        archive_date="2026-08-01",
        throttle=throttle,
        sleep=rec.sleep,
        clock=rec.clock,
        rng=rng,
        opener=opener,
    )
    return client, rec


class SuccessPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_sends_user_agent_and_parses_json(self):
        opener = ScriptedOpener([FakeResponse('{"ok": true, "n": 3}')])
        client, _ = make_client(self.tmp, opener)
        result = client.get_json("https://bills-api.parliament.uk/api/v1/Bills", "bills", "bills-search")
        self.assertEqual(result, {"ok": True, "n": 3})
        ua = opener.requests[0].get_header("User-agent")
        self.assertEqual(ua, "CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)")

    def test_archives_raw_gzip_before_parsing(self):
        opener = ScriptedOpener([FakeResponse('{"a": 1}')])
        client, _ = make_client(self.tmp, opener)
        client.get_json("https://x.parliament.uk/y", "edm", "Foetal Viability!")
        path = os.path.join(self.tmp, "2026-08-01", "edm_foetal-viability.json.gz")
        self.assertTrue(os.path.exists(path), path)
        with gzip.open(path, "rb") as handle:
            self.assertEqual(handle.read(), b'{"a": 1}')

    def test_get_text_returns_decoded_body(self):
        opener = ScriptedOpener([FakeResponse("<xml>hi</xml>")])
        client, _ = make_client(self.tmp, opener)
        self.assertEqual(client.get_text("https://www.legislation.gov.uk/z", "legislation", "z"), "<xml>hi</xml>")


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_succeeds_after_two_timeouts(self):
        opener = ScriptedOpener([
            socket.timeout("slow"),
            socket.timeout("slow"),
            FakeResponse('{"recovered": true}'),
        ])
        client, rec = make_client(self.tmp, opener)
        result = client.get_json("https://questions-statements-api.parliament.uk/q", "pq", "home-education")
        self.assertEqual(result, {"recovered": True})
        # Two backoff sleeps at the base delays (rng==0 -> no jitter).
        self.assertEqual(rec.sleeps, [2.0, 8.0])

    def test_raises_fetcherror_after_exhausting_retries(self):
        opener = ScriptedOpener([socket.timeout("slow")] * 4)
        client, rec = make_client(self.tmp, opener)
        with self.assertRaises(http.FetchError) as ctx:
            client.get_json("https://questions-statements-api.parliament.uk/q", "pq", "cass-review")
        err = ctx.exception
        self.assertEqual(err.attempts, 4)        # 1 initial + 3 retries
        self.assertEqual(err.feed, "pq")
        self.assertEqual(err.slug, "cass-review")
        self.assertEqual(rec.sleeps, [2.0, 8.0, 20.0])

    def test_jitter_adds_up_to_a_quarter_of_base(self):
        opener = ScriptedOpener([socket.timeout("x"), FakeResponse('{"ok": 1}')])
        client, rec = make_client(self.tmp, opener, rng=lambda: 0.5)
        client.get_json("https://h.parliament.uk/q", "pq", "silent-prayer")
        self.assertEqual(rec.sleeps, [2.0 + 0.5 * 0.5])  # base 2 + 0.5*(2*0.25)

    def test_retries_on_5xx_then_succeeds(self):
        err = urllib.error.HTTPError("u", 503, "unavailable", {}, None)
        opener = ScriptedOpener([err, FakeResponse('{"ok": 1}')])
        client, rec = make_client(self.tmp, opener)
        self.assertEqual(client.get_json("https://h.parliament.uk/q", "si", "cwsa"), {"ok": 1})
        self.assertEqual(rec.sleeps, [2.0])

    def test_does_not_retry_on_4xx(self):
        # What's On returns HTTP 400 on ranges over four weeks: a caller bug,
        # not a transient fault. Must fail fast with no backoff sleeps.
        err = urllib.error.HTTPError("u", 400, "bad range", {}, None)
        opener = ScriptedOpener([err])
        client, rec = make_client(self.tmp, opener)
        with self.assertRaises(http.FetchError) as ctx:
            client.get_json("https://whatson-api.parliament.uk/x", "whatson", "range")
        self.assertEqual(ctx.exception.attempts, 1)
        self.assertEqual(rec.sleeps, [])


class ThrottleTests(unittest.TestCase):
    def test_enforces_min_spacing_per_host(self):
        opener = ScriptedOpener([FakeResponse("{}"), FakeResponse("{}")])
        tmp = tempfile.mkdtemp()
        client, rec = make_client(tmp, opener, throttle=0.2)
        client.get_json("https://same-host.parliament.uk/a", "bills", "a")
        client.get_json("https://same-host.parliament.uk/b", "bills", "b")
        # Second call to the same host had to wait out the 0.2s throttle.
        self.assertIn(0.2, rec.sleeps)


class ConcurrencyCapTests(unittest.TestCase):
    def test_no_more_than_host_concurrency_in_flight(self):
        cap = http.DEFAULT_HOST_CONCURRENCY  # 4
        n_threads = 8
        state = {"active": 0, "max": 0}
        lock = threading.Lock()
        barrier = threading.Barrier(cap, timeout=5)

        class ConcurrentOpener:
            def open(self, request, timeout=None):
                with lock:
                    state["active"] += 1
                    state["max"] = max(state["max"], state["active"])
                try:
                    # Hold until `cap` requests are simultaneously in flight.
                    barrier.wait()
                finally:
                    with lock:
                        state["active"] -= 1
                return FakeResponse("{}")

        tmp = tempfile.mkdtemp()
        # throttle=0 so timing is governed purely by the semaphore.
        client = http.HttpClient(raw_dir=tmp, archive_date="2026-08-01", throttle=0.0,
                                 opener=ConcurrentOpener(), sleep=lambda s: None)

        def worker(i):
            client.get_json("https://cap-host.parliament.uk/%d" % i, "bills", "b%d" % i)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertFalse(any(t.is_alive() for t in threads), "threads deadlocked")
        self.assertLessEqual(state["max"], cap)
        self.assertEqual(state["max"], cap)  # the cap actually bit


if __name__ == "__main__":
    unittest.main()


class LimitedRetryTests(unittest.TestCase):
    """A 500 is retried once, not to exhaustion (revised 2026-08-17).

    Measured: of twelve Written Questions terms, ten answered on the first
    call and the two that did not failed every attempt. A third attempt
    rescued nothing and cost ~45s each time, so the cap stays at two. What
    rescues a windowed failure is resweep_pq_gaps, minutes later, not another
    try ten seconds later. Gateway errors keep the full budget.
    """

    def _run(self, status):
        opener = ScriptedOpener([
            urllib.error.HTTPError("https://example.test/x", status, "boom", {}, None)
            for _ in range(6)])
        client, _rec = make_client(tempfile.mkdtemp(), opener, throttle=0.0)
        with self.assertRaises(http.FetchError) as caught:
            client.get_json("https://example.test/x", "pq", "slug")
        return len(opener.requests), caught.exception.attempts

    def test_500_gives_up_after_two_attempts(self):
        calls, attempts = self._run(500)
        self.assertEqual(calls, 2, "a 500 should cost two attempts, not four")
        self.assertEqual(attempts, 2)

    def test_503_still_retries_fully(self):
        calls, _ = self._run(503)
        self.assertGreater(calls, 2, "gateway errors are transient; keep retrying")
