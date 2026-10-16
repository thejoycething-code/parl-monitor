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

    def test_a_robots_txt_that_redirects_to_a_page_does_not_recurse(self):
        """Found by the live scan: a robots.txt redirecting to a login page
        made the guard read robots.txt about the hop, which redirected
        again, until the host's semaphore was exhausted (a hang)."""
        routes = {
            "https://a.test/robots.txt": redirect("https://a.test/login?next=/robots.txt"),
            "https://a.test/login?next=/robots.txt": text("<html>log in</html>"),
            "https://a.test/page": redirect("https://a.test/other"),
            "https://a.test/other": text("fine"),
        }
        for injected in (False, True):
            with self.subTest(injected=injected):
                c, web = self.client(routes, injected=injected)
                self.assertEqual(self.guarded(c).get_text("https://a.test/page", "t", "s"), "fine")
                self.assertEqual(web.asked.count("https://a.test/robots.txt"), 1)

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


class RobotsTxtRedirectToPageTests(Base):
    """A robots.txt request that ends on a web page means no rules (16
    October 2026, Chris; RFC 9309 2.2, 2.3.1.2). dokumente.landtag.rlp.de
    answers 302 to www.landtag.rlp.de/de/startseitex/, which answers 302 to
    landtag-rlp.de/: the Landtag's home page. Before this the laptop's curl
    fallback did not follow the 302 and the host was read as unreachable."""

    HOME = (200, {"Content-Type": "text/html; charset=utf-8"},
            "\ufeff\n<!DOCTYPE html>\n<html lang=\"de\"><head><meta name=\"robots\" "
            "content=\"index, follow\"></head><body>Landtag</body></html>".encode())

    def test_a_cross_host_chain_ending_on_an_html_page_is_no_rules(self):
        routes = {
            "https://dok.test/robots.txt": redirect("https://www.home.test/de/startseitex/"),
            "https://www.home.test/de/startseitex/": redirect("https://home.test/"),
            "https://home.test/": self.HOME,
            "https://dok.test/einladung.pdf": ok(),
        }
        c, web = self.client(routes)
        g = self.guarded(c)
        self.assertTrue(g.get_bytes("https://dok.test/einladung.pdf", "t", "s").startswith(b"%PDF"))
        self.assertEqual(web.asked.count("https://dok.test/robots.txt"), 1)
        # the hops of the robots.txt read are not themselves asked about
        self.assertNotIn("https://home.test/robots.txt", web.asked)

    def test_a_genuine_robots_file_after_a_cross_host_chain_is_honoured(self):
        routes = {
            "https://dok.test/robots.txt": redirect("https://cdn.test/a/robots.txt"),
            "https://cdn.test/a/robots.txt": redirect("https://cdn.test/robots.txt"),
            "https://cdn.test/robots.txt": (200, {"Content-Type": "text/html"},
                                            b"User-agent: *\nDisallow: /intern/\n"),
            "https://dok.test/intern/x.pdf": ok(),
            "https://dok.test/offen/x.pdf": ok(),
        }
        c, web = self.client(routes)
        g = self.guarded(c)
        self.assertTrue(g.get_bytes("https://dok.test/offen/x.pdf", "t", "s"))
        with self.assertRaises(RobotsRefused):
            g.get_bytes("https://dok.test/intern/x.pdf", "t", "s")
        self.assertNotIn("https://dok.test/intern/x.pdf", web.asked)

    def test_five_redirects_are_followed_and_a_sixth_is_unavailable(self):
        def chain(n, last):
            routes = {"https://r.test/robots.txt": redirect("https://r.test/h1/robots.txt")}
            for i in range(1, n):
                routes["https://r.test/h{0}/robots.txt".format(i)] = redirect(
                    "https://r.test/h{0}/robots.txt".format(i + 1))
            routes["https://r.test/h{0}/robots.txt".format(n)] = last
            routes["https://r.test/private/x"] = text("secret")
            return routes

        rules = text("User-agent: *\nDisallow: /private\n")
        # five hops: the file at the end is read and honoured
        c, web = self.client(chain(5, rules))
        with self.assertRaises(RobotsRefused):
            self.guarded(c).get_text("https://r.test/private/x", "t", "s")
        # six hops: never followed to the end; unavailable, so no rules
        c, web = self.client(chain(6, rules))
        self.assertEqual(self.guarded(c).get_text("https://r.test/private/x", "t", "s"), "secret")
        self.assertNotIn("https://r.test/h6/robots.txt", web.asked)

    def test_a_server_error_after_a_redirect_still_skips_the_host(self):
        routes = {
            "https://dok.test/robots.txt": redirect("https://home.test/robots.txt"),
            "https://home.test/robots.txt": (503, {}, b"busy"),
            "https://dok.test/x.pdf": ok(),
        }
        c, web = self.client(routes)
        with self.assertRaises(RobotsRefused):
            self.guarded(c).get_bytes("https://dok.test/x.pdf", "t", "s")
        self.assertNotIn("https://dok.test/x.pdf", web.asked)

    def test_a_fetched_url_redirecting_off_host_is_still_asked(self):
        """The change is to robots.txt reads only: a document's own hops are
        asked as before, even on a host whose robots.txt was a web page."""
        routes = {
            "https://dok.test/robots.txt": self.HOME,
            "https://dok.test/doc": redirect("https://other.test/api/doc"),
            "https://other.test/robots.txt": text("User-agent: *\nDisallow: /api\n"),
            "https://other.test/api/doc": ok(),
        }
        c, web = self.client(routes)
        with self.assertRaises(RobotsRefused):
            self.guarded(c).get_bytes("https://dok.test/doc", "t", "s")
        self.assertNotIn("https://other.test/api/doc", web.asked)


class LooksLikeHtmlTests(unittest.TestCase):
    def test_pages_and_robots_files(self):
        from src.prov_fetch import looks_like_html
        self.assertTrue(looks_like_html("\ufeff\n<!DOCTYPE html><html><body>x</body></html>"))
        self.assertTrue(looks_like_html("<!-- portal -->\n<html><head></head></html>"))
        self.assertTrue(looks_like_html("<HTML><BODY>Disallow: / is a word here</BODY></HTML>"))
        self.assertFalse(looks_like_html("User-agent: *\nDisallow: /api\n"))
        self.assertFalse(looks_like_html(""))
        # a robots file wrapped in markup by a misconfigured server keeps its rules
        self.assertFalse(looks_like_html("<html>\nUser-agent: *\nDisallow: /\n</html>"))


class CurlFallbackRedirectTests(unittest.TestCase):
    """The laptop's LibreSSL cannot negotiate some hosts; _fetch_via_curl
    stands in. For robots.txt only it follows redirects (-L, at most 5) and
    raises the final HTTP status, so read_robots can classify it."""

    def run_with(self, url, stdout, returncode=0):
        import subprocess
        from unittest import mock
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"] = argv
            return subprocess.CompletedProcess(argv, returncode, stdout, b"")

        c = HttpClient(raw_dir=tempfile.mkdtemp(), sleep=lambda s: None, max_retries=0)
        with mock.patch("subprocess.run", fake_run), mock.patch("shutil.which", lambda n: "/usr/bin/curl"):
            try:
                return c._fetch_via_curl(url, 10, OSError("tls")), seen["argv"], None
            except Exception as exc:          # noqa: BLE001 - the test inspects it
                return None, seen["argv"], exc

    def test_robots_txt_follows_at_most_five(self):
        body, argv, exc = self.run_with("https://dok.test/robots.txt", b"<html></html>\n200")
        self.assertIsNone(exc)
        self.assertEqual(body, b"<html></html>")
        self.assertIn("-L", argv)
        self.assertEqual(argv[argv.index("--max-redirs") + 1], "5")

    def test_a_document_is_not_followed(self):
        _body, argv, exc = self.run_with("https://dok.test/x.pdf", b"\n302")
        self.assertNotIn("-L", argv)
        self.assertIsNotNone(exc)

    def test_robots_status_is_raised_as_an_http_error(self):
        import urllib.error
        for code in (404, 503, 302):
            with self.subTest(code=code):
                _b, _a, exc = self.run_with("https://dok.test/robots.txt",
                                            "x\n{0}".format(code).encode(),
                                            returncode=47 if code == 302 else 0)
                self.assertIsInstance(exc, urllib.error.HTTPError)
                self.assertEqual(exc.code, code)

    def test_read_robots_classifies_the_curl_statuses(self):
        from src.prov_fetch import DISALLOW_ALL, read_robots

        class Client:
            def __init__(self, code):
                self.code = code

            def get_text(self, url, feed, slug, archive=False):
                import urllib.error
                raise FetchError(url, feed, slug, 1, urllib.error.HTTPError(
                    url, self.code, "via curl", None, None))

        quiet = lambda *a, **k: None  # noqa: E731
        for code, want in ((404, ""), (302, ""), (503, DISALLOW_ALL)):
            with self.subTest(code=code):
                got, _why = read_robots(Client(code), "https", "dok.test", "t", log=quiet,
                                        cache_dir=None, sleep=lambda s: None)
                self.assertEqual(got, want)


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
