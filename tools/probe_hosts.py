#!/usr/bin/env python3
"""Read-only probe of a legislature's public pages, from a GitHub runner.

    python3 tools/probe_hosts.py --out /tmp/probe --max 40 \\
        --follow 'journals|hansard' https://nslegislature.ca/legislative-business/journals

Run by .github/workflows/probe-hosts.yml (workflow_dispatch only). Built 2
October 2026 for Nova Scotia and PEI, which refuse the laptop's VPN exit:
their fixtures and live probes have to come from the IP the collectors use.

WHAT IT DOES, AND WHAT IT NEVER DOES
  * the repo's honest User-Agent (src/http.USER_AGENT_TEMPLATE, with contact);
  * robots.txt read first for each host and HONOURED with both of the repo's
    readers (src/prov_fetch.Robots and star_rules), a Crawl-delay raising the
    interval; never less than --delay seconds between requests to a host;
  * redirects are followed only within the same site (assembly.pe.ca and
    docs.assembly.pe.ca are one site). A redirect elsewhere is recorded and
    not followed;
  * A BOT CHALLENGE STOPS THE HOST. A reply that is a CAPTCHA or challenge
    page (Radware/perfdrive, Cloudflare, "Attention Required") is recorded
    and no further request is made to that host in this run. It is never
    solved, retried with another User-Agent, or worked around;
  * GET only. Nothing is written but the --out directory, which the workflow
    uploads as an artifact. No store, no commit.

Every reply is saved under --out/<host>/ with an index.tsv line (status,
bytes, content type, url, title, flag), and the links of each HTML page
that match --follow are queued, up to --max pages in all.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit, urldefrag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.http import DEFAULT_CONTACT, USER_AGENT_TEMPLATE  # noqa: E402
from src.prov_fetch import Robots, rule_allows, star_rules  # noqa: E402

UA = USER_AGENT_TEMPLATE.format(contact=DEFAULT_CONTACT)
CHALLENGE = re.compile(r"perfdrive|radware|cf-chl|challenge-platform|Attention Required|"
                       r"Just a moment\.\.\.|bot manager|shieldsquare", re.I)
# "captcha" alone appears in ordinary pages (a contact form's reCAPTCHA), so
# it flags only in a title or in a short page that is nothing else.
CAPTCHA = re.compile(r"captcha", re.I)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def site(host):
    parts = host.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def safe_name(url):
    p = urlsplit(url)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", (p.path.strip("/") or "index") + ("_" + p.query if p.query else ""))
    if len(name) > 150:
        name = name[:120] + "_" + hashlib.sha1(name.encode()).hexdigest()[:10]
    return name


class Prober:
    def __init__(self, out, delay):
        self.out, self.delay = out, delay
        self.last = {}
        self.robots = {}
        self.blocked = {}
        self.host_delay = {}

    def wait(self, host):
        gap = max(self.delay, self.host_delay.get(host, 0))
        since = time.monotonic() - self.last.get(host, 0)
        if since < gap:
            time.sleep(gap - since)
        self.last[host] = time.monotonic()

    def raw_get(self, url):
        host = urlsplit(url).netloc
        self.wait(host)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            r = OPENER.open(req, timeout=60)
            return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers or {}), e.read() if hasattr(e, "read") else b""
        except Exception as e:  # noqa: BLE001 -- a probe reports every failure
            return None, {}, repr(e).encode()

    def allowed(self, url):
        p = urlsplit(url)
        host = p.netloc
        if host not in self.robots:
            status, _h, body = self.raw_get("{0}://{1}/robots.txt".format(p.scheme, host))
            text = body.decode("utf-8", "replace") if status == 200 else ""
            if status == 200 and CHALLENGE.search(text[:5000]):
                self.blocked[host] = "robots.txt is a challenge page"
                text = ""
            elif status is None or status >= 500 or status in (403, 429):
                # No answer (a timeout, a reset) is not "no rules": the
                # Crawl-delay is unknown, so nothing more is asked of the host.
                self.blocked[host] = "robots.txt did not answer ({0})".format(
                    status if status is not None else body.decode("utf-8", "replace")[:80])
                text = ""
            self.save(host, "robots.txt", body or b"")
            rp = Robots(text)
            rp.star_rules = star_rules(text, UA)
            d = rp.crawl_delay(UA)
            if d:
                self.host_delay[host] = float(d)
            self.robots[host] = rp
            print("robots {0}: status {1}, {2} bytes, crawl-delay {3}".format(host, status, len(body or b""), d))
            print("  " + "\n  ".join(text.splitlines()[:60]))
        rp = self.robots[host]
        return rp.can_fetch(UA, url) and rp.can_fetch("*", url) and rule_allows(rp.star_rules, url)

    def save(self, host, name, body):
        d = os.path.join(self.out, host)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "wb") as fh:
            fh.write(body)

    def index(self, host, line):
        d = os.path.join(self.out, host)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.tsv"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        print(line)

    def get(self, url):
        """(final_url, status, ctype, body) or None when not fetched."""
        for _hop in range(4):
            host = urlsplit(url).netloc
            if host in self.blocked:
                print("SKIP {0}: host stopped ({1})".format(url, self.blocked[host]))
                return None
            if not self.allowed(url):
                self.index(host, "ROBOTS-DISALLOWED\t-\t-\t{0}".format(url))
                return None
            if host in self.blocked:          # robots.txt itself did not answer
                print("SKIP {0}: host stopped ({1})".format(url, self.blocked[host]))
                return None
            status, headers, body = self.raw_get(url)
            ctype = headers.get("Content-Type") or headers.get("content-type") or ""
            loc = headers.get("Location") or headers.get("location")
            head = body[:20000].decode("utf-8", "replace")
            title = re.search(r"<title[^>]*>([^<]*)", head, re.I)
            flag = ""
            ttl = title.group(1) if title else ""
            # A real page may CARRY a bot manager's script (assembly.pe.ca's
            # pages load Radware's stormcaster.js and name validate.perfdrive.com
            # in its config) and still be the page. The challenge is the
            # redirect to it, a challenge title, or a short page that is
            # nothing but the challenge.
            if (loc and (CHALLENGE.search(loc) or CAPTCHA.search(loc))) \
                    or CHALLENGE.search(ttl) or CAPTCHA.search(ttl) \
                    or (len(body) < 15000 and (CHALLENGE.search(head) or CAPTCHA.search(head))):
                flag = "BOT-CHALLENGE"
            elif CHALLENGE.search(head):
                flag = "bot-manager-script"
            name = safe_name(url)
            self.save(host, name, body)
            self.index(host, "\t".join(str(x) for x in (
                status, len(body), ctype.split(";")[0], url, (title.group(1).strip()[:80] if title else ""),
                flag + (" -> " + loc if loc else ""), name)))
            if status in (403, 429) and not flag:
                flag = "REFUSED"
            if flag in ("BOT-CHALLENGE", "REFUSED"):
                self.blocked[host] = "challenge at {0}".format(url)
                print("STOP {0}: bot challenge; no further requests to this host".format(host))
                return None
            if status in (301, 302, 303, 307, 308) and loc:
                nxt = urljoin(url, loc)
                if site(urlsplit(nxt).netloc) != site(host):
                    print("  redirect off-site to {0}; not followed".format(nxt))
                    return None
                url = nxt
                continue
            return url, status, ctype, body
        return None


def links(base, body):
    html = body.decode("utf-8", "replace")
    out = []
    for href in re.findall(r'href\s*=\s*["\']([^"\'#][^"\']*)["\']', html, re.I):
        u = urldefrag(urljoin(base, href.strip()))[0]
        if u.startswith("http") and u not in out:
            out.append(u)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("seeds", nargs="+")
    ap.add_argument("--follow", default="", help="regex: queue links matching it")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--out", default="/tmp/probe")
    ap.add_argument("--show-links", type=int, default=150, help="links printed per seed page")
    a = ap.parse_args(argv)
    a.delay = max(a.delay, 2.0)
    os.makedirs(a.out, exist_ok=True)
    pr = Prober(a.out, a.delay)
    follow = re.compile(a.follow) if a.follow else None
    queue, seen, n = list(a.seeds), set(), 0
    seeds = set(a.seeds)
    print("UA: " + UA)
    while queue and n < a.max:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        got = pr.get(url)
        n += 1
        if not got:
            continue
        final, status, ctype, body = got
        if status == 200 and "html" in ctype.lower():
            ls = links(final, body)
            if url in seeds:
                print("  links on {0} ({1}):".format(url, len(ls)))
                for l in ls[:a.show_links]:
                    print("    " + l)
            if follow:
                for l in ls:
                    if follow.search(l) and l not in seen and l not in queue:
                        queue.append(l)
    print("\n{0} page(s) fetched; {1} still queued; hosts stopped: {2}".format(
        n, len(queue), pr.blocked or "none"))
    for q in queue[:200]:
        print("  queued, not fetched: " + q)


if __name__ == "__main__":
    main()
