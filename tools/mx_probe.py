#!/usr/bin/env python3
"""Read-only scoping probe for Mexico's Congress (docs/mexico-scope.md).

    python3 tools/mx_probe.py --max 40 --follow 'votaci|iniciativ' URL [URL ...]

Built 9 October 2026 because every Mexican federal host refuses the laptop
(diputados.gob.mx: TCP timeout from a BT address in London; senado.gob.mx:
an Imperva/Incapsula challenge), while GitHub's runners reach the Chamber
of Deputies. It runs from .github/workflows/mx-probe.yml and writes nothing
but data/raw/<date>/mx-probe_*.json.gz, which the workflow uploads.

Rules, the same as tools/probe_hosts.py:
  * every request goes through src/http.py (honest UA, retries, archive);
  * robots.txt is read first per host with the stdlib parser, which treats
    '#' as a comment, and honoured; at least --delay seconds between
    requests to one host;
  * a bot challenge (Incapsula, Cloudflare, Radware) STOPS the host for the
    run. It is recorded, never solved or worked around;
  * GET only; same-site links only.
"""

from __future__ import annotations

import argparse
import os
import re
import ssl
import sys
import urllib.request
import urllib.robotparser
from urllib.parse import parse_qsl, urldefrag, urljoin, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.http import FetchError, HttpClient  # noqa: E402

FEED = "mx-probe"
CHALLENGE = re.compile(r"_Incapsula_Resource|Incapsula incident|cf-chl|challenge-platform|"
                       r"Just a moment\.\.\.|perfdrive|radware|shieldsquare", re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
LINK = re.compile(r"""(?:href|src)\s*=\s*["']([^"'#]+)""", re.I)


def site(host):
    """'sitl.diputados.gob.mx:443' -> 'diputados.gob.mx'."""
    host = host.split(":")[0].lower()
    parts = host.split(".")
    return ".".join(parts[-3:]) if host.endswith(".gob.mx") else ".".join(parts[-2:])


def decode(raw):
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--follow", default="")
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--show-links", type=int, default=80)
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--extra-ca", default=os.path.join(ROOT, "config", "mx-ca-intermediates.pem"))
    args = ap.parse_args(argv)

    ctx = ssl.create_default_context()
    if args.extra_ca:
        ctx.load_verify_locations(cafile=args.extra_ca)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    client = HttpClient(args.raw_dir, max_retries=1, backoff=(5.0,), default_timeout=45,
                        opener=opener)
    follow = re.compile(args.follow, re.I) if args.follow else None
    robots, stopped, seen = {}, {}, set()
    queue = list(args.urls)
    fetched = 0
    while queue and fetched < args.max:
        url = urldefrag(queue.pop(0))[0]
        post = url.startswith("POST:")
        if post:
            url = url[5:]
        if url in seen:
            continue
        seen.add(url)
        parts = urlsplit(url)
        host = parts.hostname or ""
        if host in stopped:
            print("SKIP\t{0}\t(host stopped: {1})".format(url, stopped[host]))
            continue
        client.set_host_throttle(parts.netloc, args.delay)
        if host not in robots:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = "{0}://{1}/robots.txt".format(parts.scheme, parts.netloc)
            try:
                body = decode(client.get_bytes(robots_url, FEED, host + "-robots"))
                print("ROBOTS\t{0}\t{1!r}".format(host, body[:300]))
                rp.parse(body.splitlines())
            except FetchError as exc:
                print("ROBOTS\t{0}\tunreadable ({1}); treated as allow-all".format(host, exc.cause))
                rp.parse([])
            robots[host] = rp
        if not robots[host].can_fetch(client.user_agent, url):
            print("ROBOTS-DISALLOWED\t{0}".format(url))
            continue
        try:
            slug = parts.netloc + parts.path + "-" + (parts.query or "")
            if post:
                # A form the site's own pages submit to look up a list (the
                # Gaceta's per-vote member lists). Read-only; archived.
                target = url.split("?", 1)[0]
                raw = client.post_form(target, parse_qsl(parts.query), FEED, "post-" + slug,
                                       archive=True)
                raw = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            else:
                raw = client.get_bytes(url, FEED, slug)
        except FetchError as exc:
            print("ERR\t{0}\t{1}".format(url, exc.cause))
            if not isinstance(getattr(exc.cause, "code", None), int):
                stopped[host] = str(exc.cause)
            continue
        fetched += 1
        text = decode(raw)
        title = TITLE.search(text)
        title = re.sub(r"\s+", " ", title.group(1)).strip()[:90] if title else ""
        flag = "CHALLENGE" if CHALLENGE.search(text[:5000]) else ""
        print("OK\t{0}\t{1}\t{2}\t{3}".format(len(raw), url, title, flag))
        if flag:
            stopped[host] = "bot challenge"
            continue
        links = []
        for href in LINK.findall(text):
            link = urldefrag(urljoin(url, href.strip()))[0]
            if urlsplit(link).scheme in ("http", "https") and site(urlsplit(link).netloc) == site(parts.netloc):
                if link not in links:
                    links.append(link)
        for link in links[:args.show_links]:
            print("    link\t{0}".format(link))
        if follow:
            queue.extend(l for l in links if follow.search(l) and l not in seen)
    print("fetched {0}; queued {1}; stopped {2}".format(fetched, len(queue), stopped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
