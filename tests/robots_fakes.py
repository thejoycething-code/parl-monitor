"""A test double for src/robots_guard: wraps a collector test's FakeClient
and answers robots.txt per host, from a fixture text or an HTTP status, so
the run-time robots check can be tested with no network."""

import urllib.error
from urllib.parse import urlsplit

from src.http import FetchError
from src.robots_guard import GuardedClient, guard

UA = "citizengo-parlmonitor/1.0 (+test)"


class RobotsServing:
    """robots: {host: text | int status}; a host not listed answers 404."""

    def __init__(self, inner, robots):
        self.inner = inner
        self.robots = robots
        self.user_agent = UA
        self.throttle = 1.0
        self.host_throttles = {}
        self.robots_asked = []

    def set_host_throttle(self, host, seconds):
        self.host_throttles[host] = max(seconds, self.host_throttles.get(host, 0))
        if hasattr(self.inner, "set_host_throttle"):
            self.inner.set_host_throttle(host, seconds)

    def get_text(self, url, feed, slug, *a, **kw):
        parts = urlsplit(url)
        if parts.path == "/robots.txt":
            self.robots_asked.append(parts.netloc)
            got = self.robots.get(parts.netloc, 404)
            if isinstance(got, int):
                raise FetchError(url, feed, slug, 1,
                                 urllib.error.HTTPError(url, got, "status", {}, None))
            return got
        return self.inner.get_text(url, feed, slug, *a, **kw)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def guarded(inner, robots, feed):
    """A GuardedClient over `inner`, with robots.txt served from `robots`."""
    serving = RobotsServing(inner, robots)
    return GuardedClient(serving, feed, log=lambda *a, **k: None), serving


def guarded_api(inner, robots, feed):
    """src/robots_guard.guard() over `inner` (documented APIs exempt), with
    robots.txt served from `robots`: how the #144 collectors are wrapped."""
    serving = RobotsServing(inner, robots)
    return guard(serving, feed, log=lambda *a, **k: None), serving
