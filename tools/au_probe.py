#!/usr/bin/env python3
"""Does aph.gov.au answer this machine? A one-off, read-only probe.

    python3 tools/au_probe.py --out /tmp/au-probe            # from the Mini, by hand
    python3 tools/au_probe.py --out probe-out --summary "$GITHUB_STEP_SUMMARY"

Run by .github/workflows/au-probe.yml (workflow_dispatch only) from GitHub's
runners, or by hand from the Mac Mini. NOT RUN YET: Christopher decides.

Why. On 9 October 2026 www.aph.gov.au and parlinfo.aph.gov.au answered the
laptop with an Azure WAF block page (403) on every request, robots.txt
included, and www.hcourt.gov.au failed at the TLS layer (docs/australia-scope.md).
The US Senate did the same and answered GitHub's runners. If any of these
answer the runners or the Mini, phase 1b (bill texts, amendment sheets,
Votes and Proceedings, the sitting calendar) becomes buildable.

HOW. Every request goes through tools/probe_hosts.Prober, so the rules are
that tool's, unchanged: the repo's honest User-Agent; robots.txt read first
and honoured, with its Crawl-delay; at least --delay seconds between requests
to a host; GET only; redirects followed only within the same site. A BOT
CHALLENGE OR A 403/429 STOPS THE HOST for the run: it is recorded, never
solved, retried with another User-Agent or worked around, and the targets
left on that host are reported as not asked.

What comes back is saved under --out (the workflow uploads it as an
artifact), and a table, one row per target with a short text sample, goes to
stdout and to --summary when given. No store, no commit, no secrets.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import probe_hosts  # noqa: E402

# (what, URL). One page per source the scope doc says is blocked; a bill and
# a sitting day from the 48th Parliament that the store already holds, so a
# sample can be checked against what OpenAustralia gave us.
TARGETS = (
    ("Bills Search (results)",
     "https://www.aph.gov.au/Parliamentary_Business/Bills_Legislation/Bills_Search_Results"
     "?st=1&sr=1&q=&ito=1&expand=False&drvH=7&drt=2&pnu=48&pnuH=48&ps=10&pageNumber=1"),
    ("Bill homepage (r7512)",
     "https://www.aph.gov.au/Parliamentary_Business/Bills_Legislation/Bills_Search_Results/"
     "Result?bId=r7512"),
    ("ParlInfo bill homepage (r7512)",
     "https://parlinfo.aph.gov.au/parlInfo/search/display/display.w3p;query=Id%3A%22legislation"
     "%2Fbillhome%2Fr7512%22"),
    ("ParlInfo Senate Hansard (17 Sep 2026)",
     "https://parlinfo.aph.gov.au/parlInfo/search/display/display.w3p;adv=yes;orderBy="
     "_fragment_number,doc_date-rev;page=0;query=Dataset%3Ahansards,hansards80%20Date%3A17%2F9"
     "%2F2026;rec=0;resCount=Default"),
    ("Votes and Proceedings",
     "https://www.aph.gov.au/Parliamentary_Business/Chamber_documents/HoR/Votes_and_Proceedings"),
    ("Journals of the Senate",
     "https://www.aph.gov.au/Parliamentary_Business/Chamber_documents/Senate_chamber_documents/"
     "Journals_of_the_Senate"),
    ("Sitting calendar",
     "https://www.aph.gov.au/Parliamentary_Business/Sitting_Calendar"),
    ("Committees",
     "https://www.aph.gov.au/Parliamentary_Business/Committees"),
    ("Senate estimates",
     "https://www.aph.gov.au/Parliamentary_Business/Senate_estimates"),
    ("High Court (www)", "https://www.hcourt.gov.au/"),
    ("High Court (eresources)", "https://eresources.hcourt.gov.au/"),
)


def sample(body, n=300):
    """A short plain-text sample of a reply, for the summary table."""
    text = (body or b"")[:200000].decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = " ".join(text.split()).replace("|", "/")
    return text[:n] + ("..." if len(text) > n else "")


def probe(prober, targets=TARGETS, log=print):
    """[(what, url, outcome, status, bytes, sample)], one per target."""
    rows = []
    for what, url in targets:
        host = urlsplit(url).netloc
        if host in prober.blocked:
            rows.append((what, url, "not asked: host stopped ({0})".format(prober.blocked[host]),
                         "-", 0, ""))
            continue
        got = prober.get(url)
        if got is None:
            why = prober.blocked.get(host, "robots.txt disallows it, or an off-site redirect")
            rows.append((what, url, "refused: " + why, "-", 0, ""))
            continue
        final, status, ctype, body = got
        rows.append((what, final, "answered" if status == 200 else "status {0}".format(status),
                     status, len(body or b""), sample(body)))
    return rows


def table(rows):
    out = ["| Source | Outcome | Status | Bytes | Sample |", "|---|---|---|---|---|"]
    for what, url, outcome, status, size, text in rows:
        out.append("| [{0}]({1}) | {2} | {3} | {4} | {5} |".format(
            what, url, outcome, status, size, text or ""))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="/tmp/au-probe")
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--summary", help="append the table here (e.g. $GITHUB_STEP_SUMMARY)")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    prober = probe_hosts.Prober(a.out, max(a.delay, 2.0))
    print("UA: " + probe_hosts.UA)
    rows = probe(prober)
    text = "## Australia probe\n\n" + table(rows) + "\n"
    print(text)
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
