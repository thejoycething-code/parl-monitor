"""HTTP layer for the Parliamentary Monitor.

Everything else in the pipeline depends on this module (handoff section 3).
It encodes the observed behaviour of Parliament's feeds:

  * a fixed User-Agent identifying CitizenGO on every request;
  * a long default timeout (the Written Questions/Statements API is slow and
    flaky: 7 to 30+ seconds, intermittent multi-minute timeouts);
  * up to 3 retries with exponential backoff and jitter (2s, 8s, 20s);
  * a per-host concurrency cap of 4;
  * a 0.2s throttle between sequential calls to the same host;
  * every raw response archived to data/raw/<date>/<feed>_<slug>.json.gz
    *before* parsing, so provenance is never lost.

A term that still fails after all retries raises FetchError. The caller (an
ingester) is responsible for logging that to the `gaps` table and disclosing
it in the edition footer; the HTTP layer stays decoupled from the database.

stdlib only (urllib), so it runs without third-party packages. The clock,
sleeper, jitter source and URL opener are all injectable, which is what makes
the retry/backoff/throttle behaviour deterministically testable (Checkpoint 1
requires demonstrating retry under a simulated timeout).
"""

from __future__ import annotations

import gzip
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

DEFAULT_CONTACT = "cjoyce@citizengo.net"
USER_AGENT_TEMPLATE = "CitizenGO-ParlMonitor/1.0 (contact: {contact})"

# 60s per-request timeout for the slow WQ/statements API (Christopher,
# 2026-08-17). Measured, not guessed: multi-word PQ search terms routinely
# exceed 35s, so five of them failed after four attempts each in the 17 August
# pull. In a timed test "age assurance" succeeded only after 115s of attempts
# and backoff, while single-word terms returned in 14-18s. 35s was cutting off
# queries that were going to answer.
DEFAULT_TIMEOUT = 60.0
# handoff section 3: exponential backoff with jitter, 2s/8s/20s between tries.
DEFAULT_BACKOFF = (2.0, 8.0, 20.0)
DEFAULT_MAX_RETRIES = 3
DEFAULT_THROTTLE = 0.2
DEFAULT_HOST_CONCURRENCY = 4
# Never actually contended today: every sweep in run_weekly.py is a sequential
# `for term in terms` loop and the phases run one after another, so the
# semaphore below always has a free slot. Worth knowing before blaming it for
# anything -- a commit message on 2026-08-17 wrongly attributed the Written
# Questions 500s to our own parallelism. Tuning this number changes nothing
# until a caller genuinely fetches in parallel.

# 4xx errors are the caller's fault (e.g. What's On returns 400 on ranges over
# four weeks); never retry those. 5xx and 429 are transient; retry them.
# 500 gets TWO attempts. It was briefly raised to three on 2026-08-17 and the
# measurement did not support it: across twelve terms, ten answered first
# time and the two that did not failed every attempt, so the third rescued
# nothing while costing ~45s each time it was spent. The second attempt does
# earn its place ("Cass-Review": 500, then 177).
# Retrying harder is the wrong shape of fix anyway. Written Questions
# failures cluster on a term for a WINDOW rather than for good --
# "border-security" failed 4/4 in ten minutes and succeeded 3/3 in the next
# ten -- so what rescues a term is distance in time, not another try ten
# seconds later. That is run_weekly.resweep_pq_gaps, at the end of the pull.
# 429 and the gateway errors stay fully retryable; those were never in doubt.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_LIMITED_RETRY_STATUS = frozenset({500})
_LIMITED_RETRY_ATTEMPTS = 2


class FetchError(Exception):
    """Raised when a request still fails after all retries are exhausted.

    Carries enough context for the caller to record a `gaps` row: the URL,
    the feed/slug it was archiving under, how many attempts were made, and the
    underlying error.
    """

    def __init__(self, url, feed, slug, attempts, cause):
        self.url = url
        self.feed = feed
        self.slug = slug
        self.attempts = attempts
        self.cause = cause
        super().__init__(
            "fetch failed after {n} attempt(s) for {feed}/{slug}: {url} ({cause})".format(
                n=attempts, feed=feed, slug=slug, url=url, cause=cause
            )
        )


def slugify(value, max_length=80):
    """Filesystem-safe slug for raw-archive filenames."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if len(value) > max_length:
        value = value[:max_length].rstrip("-")
    return value or "response"


class _HostState:
    """Per-host throttle lock + concurrency semaphore."""

    def __init__(self, concurrency):
        self.lock = threading.Lock()          # serialises throttle bookkeeping
        self.semaphore = threading.Semaphore(concurrency)
        self.last_request_at = None           # monotonic timestamp of last call


class HttpClient:
    """Archiving, throttled, retrying JSON/text fetcher.

    Parameters injected for testability:
      sleep:  callable(seconds) -> None       (default time.sleep)
      clock:  callable() -> float seconds     (default time.monotonic)
      rng:    callable() -> float in [0, 1)   (jitter source; default random)
      opener: object with .open(request, timeout) (default urllib global opener)
    """

    def __init__(
        self,
        raw_dir,
        contact=DEFAULT_CONTACT,
        archive_date=None,
        default_timeout=DEFAULT_TIMEOUT,
        throttle=DEFAULT_THROTTLE,
        max_retries=DEFAULT_MAX_RETRIES,
        backoff=DEFAULT_BACKOFF,
        host_concurrency=DEFAULT_HOST_CONCURRENCY,
        sleep=None,
        clock=None,
        rng=None,
        opener=None,
    ):
        self.raw_dir = str(raw_dir)
        self.contact = contact
        self.user_agent = USER_AGENT_TEMPLATE.format(contact=contact)
        self.archive_date = archive_date  # e.g. "2026-08-01"; None -> today at write time
        self.default_timeout = default_timeout
        self.throttle = throttle
        self.max_retries = max_retries
        self.backoff = tuple(backoff)
        self.host_concurrency = host_concurrency

        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic
        if rng is None:
            import random

            self._rng = random.random
        else:
            self._rng = rng
        self._opener = opener or urllib.request.build_opener()

        self._hosts = {}
        self._hosts_guard = threading.Lock()

    # -- public API ---------------------------------------------------------

    def get_json(self, url, feed, slug, timeout=None):
        """Fetch, archive, and parse a JSON response."""
        raw = self._fetch(url, feed, slug, timeout)
        return json.loads(raw.decode("utf-8"))

    def get_text(self, url, feed, slug, timeout=None):
        """Fetch and archive a response, returning decoded text.

        Used for the HTML/XML feeds (legislation.gov.uk, Holyrood scrape).
        The archive filename still ends .json.gz for a uniform raw tree; the
        bytes stored are whatever the server returned.
        """
        raw = self._fetch(url, feed, slug, timeout)
        return raw.decode("utf-8", errors="replace")

    # -- internals ----------------------------------------------------------

    def _host_state(self, host):
        with self._hosts_guard:
            state = self._hosts.get(host)
            if state is None:
                state = _HostState(self.host_concurrency)
                self._hosts[host] = state
            return state

    def _fetch(self, url, feed, slug, timeout):
        timeout = self.default_timeout if timeout is None else timeout
        host = urlsplit(url).netloc
        state = self._host_state(host)

        # Per-host concurrency cap (handoff section 3). Sequential Phase 1
        # callers never contend; the cap is enforced here for when they don't.
        with state.semaphore:
            self._throttle(state)
            raw = self._request_with_retries(url, feed, slug, timeout)

        self._archive(raw, feed, slug)
        return raw

    def _throttle(self, state):
        """Ensure at least `throttle` seconds since this host's last request."""
        with state.lock:
            now = self._clock()
            if state.last_request_at is not None:
                elapsed = now - state.last_request_at
                wait = self.throttle - elapsed
                if wait > 0:
                    self._sleep(wait)
                    now = self._clock()
            state.last_request_at = now

    def _request_with_retries(self, url, feed, slug, timeout):
        attempts = 0
        last_error = None
        # 1 initial attempt + up to max_retries further attempts.
        for attempt in range(self.max_retries + 1):
            attempts = attempt + 1
            try:
                return self._request_once(url, timeout)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in _RETRYABLE_STATUS:
                    raise FetchError(url, feed, slug, attempts, exc)
                if (exc.code in _LIMITED_RETRY_STATUS
                        and attempts >= _LIMITED_RETRY_ATTEMPTS):
                    raise FetchError(url, feed, slug, attempts, exc)
            except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
                last_error = exc

            if attempt < self.max_retries:
                self._sleep(self._backoff_delay(attempt))

        raise FetchError(url, feed, slug, attempts, last_error)

    def _backoff_delay(self, attempt):
        """Backoff for the wait *after* a given attempt index (0-based).

        Base delays are 2/8/20s; jitter adds up to 25% of the base so retries
        from parallel workers don't thunder. rng() is injectable, so tests can
        pin the jitter (rng()==0 -> exactly the base delay).
        """
        base = self.backoff[min(attempt, len(self.backoff) - 1)]
        return base + self._rng() * (base * 0.25)

    def _request_once(self, url, timeout):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/xml, text/html;q=0.9, */*;q=0.8",
            },
        )
        response = self._opener.open(request, timeout=timeout)
        try:
            return response.read()
        finally:
            close = getattr(response, "close", None)
            if close:
                close()

    def _archive(self, raw, feed, slug):
        """Write raw bytes to data/raw/<date>/<feed>_<slug>.json.gz."""
        date = self.archive_date or time.strftime("%Y-%m-%d")
        directory = os.path.join(self.raw_dir, date)
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "{feed}_{slug}.json.gz".format(feed=feed, slug=slugify(slug)))
        with gzip.open(path, "wb") as handle:
            handle.write(raw)
        return path
