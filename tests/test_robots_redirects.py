"""robots.txt asked about EVERY hop of a redirect chain (13 October 2026).

docs.un.org/<symbol>?direct=true began answering 302 to
documents.un.org/api/symbol/access, a path documents.un.org/robots.txt
disallows, and the HTTP client followed it: robots.txt had been asked about
the first URL only. These run a real HttpClient over an in-memory web (a
urllib handler serving canned replies), so the redirect handling is urllib's
own, with no network.
"""

import email.message
import io
import os
import shutil
import sys
import tempfile
import unittest
import urllib.request
import urllib.response

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import http as http_mod  # noqa: E402
from src.http import FetchError, HttpClient, RobotsRefused  # noqa: E402
from src.prov_fetch import Context  # noqa: E402
from src.robots_guard import (GuardedClient, RobotsRefused as GuardRefused,  # noqa: E402
                              check_redirects, guard)

DISALLOW_API = "User-agent: *\nDisallow: /api\nDisallow: /doc\nDisallow: /access\n"


class FakeWeb(urllib.request.BaseHandler):
    """Serves `routes` {url: (status, headers, body)}; anything else 404."""

    handler_order = 100      # ahead of the real HTTPS handler

    def __init__(self, routes):
        self.routes = routes
        self.asked = []

    def https_open(self, req):
        url = req.full_url
        self.asked.append(url)
        status, headers, body = self.routes.get(url, (404, {}, b"not found"))
        msg = email.message.Message()
        for k, v in headers.items():
            msg[k] = v
        resp = urllib.response.addinfourl(io.BytesIO(body), msg, url, status)
        resp.msg = "OK" if status < 300 else "Redirect" if status < 400 else "Error"
        return resp


def redirect(to):
    return (302, {"Location": to}, b"")


def ok(body=b"%PDF-1.7 body"):
    return (200, {"Content-Type": "application/pdf"}, body)


def text(body):
    return (200, {"Content-Type": "text/plain"}, body.encode())


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client(self, routes, injected=False):
        """A real HttpClient over FakeWeb. injected=False: the client's own
        opener (its _RedirectHandler); True: an opener a collector built and
        passed in (urllib's plain redirect handler, wrapped)."""
        web = FakeWeb(routes)
        if injected:
            c = HttpClient(raw_dir=self.tmp, opener=urllib.request.build_opener(web),
                           sleep=lambda s: None, max_retries=0)
        else:
            c = HttpClient(raw_dir=self.tmp, sleep=lambda s: None, max_retries=0)
            c._opener = urllib.request.build_opener(web, http_mod._RedirectHandler(c))
        return c, web

    def guarded(self, client, **kw):
        return GuardedClient(client, "test", log=lambda *a, **k: None,
                             robots_cache_dir=None, robots_sleep=lambda s: None, **kw)


UN_ROUTES = {
    "https://docs.un.org/robots.txt": text("<!doctype html>language picker"),
    "https://docs.un.org/en/A/81/L.6?direct=true":
        redirect("https://documents.un.org/api/symbol/access?s=A/81/L.6&l=en&t=pdf"),
    "https://documents.un.org/robots.txt": text(DISALLOW_API),
    "https://documents.un.org/api/symbol/access?s=A/81/L.6&l=en&t=pdf": ok(),
}


class RedirectHopTests(Base):
    def test_a_disallowed_hop_is_refused_and_never_requested(self):
        for injected in (False, True):
            with self.subTest(injected=injected):
                c, web = self.client(UN_ROUTES, injected=injected)
                g = self.guarded(c)
                with self.assertRaises(RobotsRefused) as cm:
                    g.get_bytes("https://docs.un.org/en/A/81/L.6?direct=true", "undocs", "A-81-L.6")
                self.assertEqual(
                    str(cm.exception),
                    "robots.txt disallows https://documents.un.org/api/symbol/access?s=A/81/L.6"
                    "&l=en&t=pdf (redirected from https://docs.un.org/en/A/81/L.6?direct=true);"
                    " not fetched")
                self.assertNotIn("https://documents.un.org/api/symbol/access?s=A/81/L.6&l=en&t=pdf",
                                 web.asked)
                self.assertIn("https://documents.un.org/robots.txt", web.asked)
                # Still the collectors' FetchError, carrying the caller's feed.
                self.assertIsInstance(cm.exception, FetchError)
                self.assertIs(RobotsRefused, GuardRefused)
                self.assertEqual(cm.exception.feed, "undocs")

    def test_a_ranged_request_is_refused_too(self):
        c, web = self.client(UN_ROUTES)
        with self.assertRaises(RobotsRefused):
            self.guarded(c).get_bytes("https://docs.un.org/en/A/81/L.6?direct=true",
                                      "undocs", "A-81-L.6", first_bytes=64)

    def test_every_hop_of_a_chain_is_asked(self):
        routes = {
            "https://a.test/start": redirect("https://b.test/ok"),
            "https://b.test/ok": redirect("https://c.test/api/doc"),
            "https://c.test/robots.txt": text(DISALLOW_API),
        }
        c, web = self.client(routes)
        with self.assertRaises(RobotsRefused) as cm:
            self.guarded(c).get_text("https://a.test/start", "t", "s")
        self.assertIn("disallows https://c.test/api/doc (redirected from https://a.test/start)",
                      str(cm.exception))
        self.assertIn("https://b.test/ok", web.asked)
        self.assertNotIn("https://c.test/api/doc", web.asked)

    def test_an_allowed_redirect_is_followed(self):
        routes = {
            "https://a.test/start": redirect("https://b.test/page"),
            "https://b.test/robots.txt": text(DISALLOW_API),
            "https://b.test/page": text("hello"),
        }
        c, _web = self.client(routes)
        self.assertEqual(self.guarded(c).get_text("https://a.test/start", "t", "s"), "hello")

    def test_a_hop_to_an_unreachable_robots_host_is_refused(self):
        routes = {
            "https://a.test/start": redirect("https://down.test/page"),
            "https://down.test/robots.txt": (503, {}, b"down"),
            "https://down.test/page": text("never"),
        }
        c, web = self.client(routes)
        with self.assertRaises(RobotsRefused) as cm:
            self.guarded(c).get_text("https://a.test/start", "t", "s")
        self.assertIn("(redirected from https://a.test/start)", str(cm.exception))
        self.assertNotIn("https://down.test/page", web.asked)

    def test_a_hop_into_a_documented_api_passes_unasked(self):
        routes = {
            "https://a.test/start": redirect("https://api.test/v1/x"),
            "https://api.test/robots.txt": text("User-agent: *\nDisallow: /\n"),
            "https://api.test/v1/x": text("data"),
        }
        c, web = self.client(routes)
        g = self.guarded(c, exempt=("https://api.test/v1/",))
        self.assertEqual(g.get_text("https://a.test/start", "t", "s"), "data")
        self.assertNotIn("https://api.test/robots.txt", web.asked)

    def test_a_robots_txt_redirect_is_followed(self):
        routes = {
            "https://a.test/robots.txt": redirect("https://www.a.test/robots.txt"),
            "https://www.a.test/robots.txt": text("User-agent: *\nDisallow: /private\n"),
            "https://a.test/private/x": text("secret"),
            "https://a.test/public": text("open"),
        }
        c, _web = self.client(routes)
        g = self.guarded(c)
        self.assertEqual(g.get_text("https://a.test/public", "t", "s"), "open")
        with self.assertRaises(RobotsRefused):
            g.get_text("https://a.test/private/x", "t", "s")

    def test_a_refused_hop_is_never_served_from_todays_archive(self):
        c, _web = self.client(UN_ROUTES)
        c._archive(b"%PDF-1.7 old copy", "undocs", "A-81-L.6")
        with self.assertRaises(RobotsRefused):
            self.guarded(c).get_bytes("https://docs.un.org/en/A/81/L.6?direct=true",
                                      "undocs", "A-81-L.6")

    def test_guard_wraps_register_too(self):
        c, web = self.client(UN_ROUTES)
        g = guard(c, "undocs", log=lambda *a, **k: None)
        with self.assertRaises(RobotsRefused):
            g.get_bytes("https://docs.un.org/en/A/81/L.6?direct=true", "undocs", "A-81-L.6")

    def test_an_unguarded_client_follows_as_before(self):
        """A client no robots-checked wrapper has registered on (a documented
        API client) follows redirects exactly as it always did."""
        c, _web = self.client(UN_ROUTES)
        self.assertEqual(c.get_bytes("https://docs.un.org/en/A/81/L.6?direct=true",
                                     "undocs", "A-81-L.6"), b"%PDF-1.7 body")

    def test_a_dropped_wrapper_stops_being_asked(self):
        c, _web = self.client(UN_ROUTES)
        g = self.guarded(c)
        del g
        import gc
        gc.collect()
        self.assertEqual(c.get_bytes("https://docs.un.org/en/A/81/L.6?direct=true",
                                     "undocs", "A-81-L.6"), b"%PDF-1.7 body")


class ContextTests(Base):
    def test_a_province_context_records_the_refused_hop_as_a_gap(self):
        c, web = self.client(UN_ROUTES)
        ctx = Context(None, c, "zz", log=lambda *a, **k: None, robots_cache_dir=None,
                      robots_sleep=lambda s: None)
        self.assertIsNone(ctx.bytes("https://docs.un.org/en/A/81/L.6?direct=true", "x"))
        self.assertTrue(any("robots.txt disallows https://documents.un.org/api/" in g
                            and "redirected from https://docs.un.org/" in g for g in ctx.gaps))

    def test_robots_false_registers_nothing(self):
        c, _web = self.client(UN_ROUTES)
        ctx = Context(None, c, "zz", log=lambda *a, **k: None, robots=False)
        self.assertIsNotNone(ctx.bytes("https://docs.un.org/en/A/81/L.6?direct=true", "x"))


class RobotparserCollectorTests(Base):
    def test_check_redirects_covers_a_plain_client(self):
        """Collectors with their own urllib.robotparser first-URL check
        (src/member_service, src/agendas/at, tools/at_rollcalls ...)."""
        c, web = self.client(UN_ROUTES)
        rg = check_redirects(c, "at", log=lambda *a, **k: None)
        rg.robots_cache_dir = None
        with self.assertRaises(RobotsRefused):
            c.get_bytes("https://docs.un.org/en/A/81/L.6?direct=true", "undocs", "A-81-L.6")


if __name__ == "__main__":
    unittest.main()
