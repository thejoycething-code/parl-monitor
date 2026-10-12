"""robots.txt checked at RUN time, for collectors that do not run inside
src/prov_fetch.Context.

The regional collectors added on 12 October 2026 (tools/es_regions.py,
tools/pe_regions.py, tools/it_regions.py) read each site's robots.txt when
they were built, and then fetched on every run without asking again: a site
that later disallowed us would have gone on being crawled. This wraps their
HttpClient so every request asks robots.txt first, read once per host per
run, with the provinces' reader and rules (src/prov_fetch.Context):

  * both readers must allow the URL: Robots (the RFC 9309 matcher) and
    star_rules (every '*' group, literal paths);
  * a robots.txt answering 4xx means no rules; a 5xx or no answer at all
    means "unreachable", read as Disallow: / for the whole host (RFC 9309
    2.3.1; #142);
  * a Crawl-delay larger than the client's throttle raises THAT host's
    interval (HttpClient.set_host_throttle never lowers one already set, so a
    collector's own per-host delay stands).

A refused request raises RobotsRefused, a FetchError, so the collectors'
existing `except FetchError` paths turn it into a [gap] line and a gaps row
and move on: never fatal, never a silent skip. `host_skipped` is True when
the whole host is refused (robots.txt unreachable), so a collector looping
over one host's pages can stop asking it.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from src.http import FetchError
from src.prov_fetch import Context


class RobotsRefused(FetchError):
    """A request robots.txt does not allow; it was never sent."""

    def __init__(self, url, feed, slug, reason, host_skipped=False):
        super().__init__(url, feed, slug, 0, reason)
        self.reason = reason
        self.host_skipped = host_skipped

    def __str__(self):
        return self.reason


class RobotsGuard(Context):
    """Context's robots.txt reader without the rest of Context: no store, no
    budget. Gaps are the caller's to record (refusal() returns the reason)."""

    def __init__(self, client, feed, log=print):
        keep = getattr(client, "throttle", None)
        super().__init__(None, client, feed, feed=feed, log=log)
        if keep is not None:
            # Context raises a client's throttle to 1.1 s for the provinces;
            # here the collector's own throttle stands.
            client.throttle = keep

    def gap(self, detail):
        # The caller records the gap (it owns the store and the feed); the
        # unreachable reason comes back through refusal().
        self.gaps.append(detail)

    def refusal(self, url):
        """None when robots.txt allows `url`, else (reason, host_skipped)."""
        rp = self._parser(url)
        unreachable = getattr(rp, "unreachable", None)
        if unreachable:
            return unreachable, True
        if self.allowed(url):
            return None
        return "robots.txt disallows {0}; not fetched".format(url), False

    def crawl_delay(self, host, scheme="https"):
        """The Crawl-delay robots.txt asks of us on `host` (None if none)."""
        rp = self._parser("{0}://{1}/".format(scheme, host))
        return rp.crawl_delay(self.client.user_agent)


class GuardedClient:
    """An HttpClient whose every request asks robots.txt first. Everything
    else (throttles, user_agent, raw_dir) passes through to the client."""

    def __init__(self, client, feed, log=print):
        self._client = client
        self.robots = RobotsGuard(client, feed, log=log)

    def __getattr__(self, name):
        return getattr(self._client, name)

    def check(self, url, feed=None, slug=""):
        refused = self.robots.refusal(url)
        if refused:
            reason, host_skipped = refused
            raise RobotsRefused(url, feed or self.robots.feed, slug, reason, host_skipped)

    def allowed(self, url):
        return self.robots.refusal(url) is None

    def crawl_delay(self, host):
        return self.robots.crawl_delay(host)

    def get_text(self, url, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.get_text(url, feed, slug, *args, **kwargs)

    def get_bytes(self, url, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.get_bytes(url, feed, slug, *args, **kwargs)

    def get_json(self, url, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.get_json(url, feed, slug, *args, **kwargs)

    def post_form(self, url, fields, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.post_form(url, fields, feed, slug, *args, **kwargs)

    def post_json(self, url, body, feed, slug, *args, **kwargs):
        self.check(url, feed, slug)
        return self._client.post_json(url, body, feed, slug, *args, **kwargs)


