"""OHCHR calls for input: the UN's open consultations, with deadlines.

    Special Procedures, treaty bodies and the High Commissioner's office
    publish "calls for input" inviting written submissions on a theme, each
    with a closing date. They are the UN analogue of a Commons committee
    inquiry -- a dated, named opportunity to put evidence in front of a body
    that will report on it.

This is the EARLY WARNING half of the UN monitor. The UPR tracker records
positions already taken and trails the calendar by nine months; a call for
input is a door that is open now and closes on a known date.

Two things learned building this (2026-08-17):

  * www.ohchr.org requires a TLS version the macOS system Python's LibreSSL
    2.8.3 will not negotiate. src/http.py falls back to curl for exactly that
    error, so this works both on a laptop and in CI.
  * the listing is HTML with no RSS or JSON alternative, so it is parsed with
    regexes against a captured fixture. Layout changes WILL break it, which is
    why parse_calls returning nothing is treated by callers as a gap rather
    than as "no calls are open".
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

LISTING = "https://www.ohchr.org/en/calls-for-input-listing"
BASE = "https://www.ohchr.org"

MONTHS = ("January February March April May June July August September "
          "October November December").split()
_DATE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d\d)")
# Each listing row carries an issuing body, a deadline and a link whose slug
# is the topic. The slug is the most reliable title source: the visible title
# markup has changed shape before, the URL has not.
_ROW = re.compile(
    r'<div class="[^"]*(?:views-row|card)[^"]*">(.*?)</div>\s*</div>', re.S)
_LINK = re.compile(r'href="(/en/calls-for-input/[^"#?]+)"')
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class Call:
    title: str
    body: str                      # Special Procedures | OHCHR | a committee
    deadline: datetime.date
    url: str

    @property
    def days_left(self):
        return (self.deadline - datetime.date.today()).days

    @property
    def closed(self):
        return self.days_left < 0


def _text(html):
    return re.sub(r"\s+", " ", _TAGS.sub("", html)).strip()


def _title_from_slug(path):
    """'call-inputs-child-rights-and-safety-digital-environment' ->
    'Child rights and safety digital environment'."""
    slug = path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"^call[s]?-(?:for-)?input[s]?-", "", slug)
    slug = re.sub(r"^(?:report-|on-)", "", slug)
    words = slug.replace("-", " ").strip()
    return words[:1].upper() + words[1:] if words else "(untitled call)"


def parse_calls(html):
    """Every call on the listing page, newest deadline last.

    Rows without a parseable deadline are skipped: a call whose closing date
    we cannot read is worse than useless in a deadline feed, because it would
    sit in the list forever.
    """
    calls, seen = [], set()
    for block in _ROW.findall(html or ""):
        link = _LINK.search(block)
        if not link:
            continue
        found = _DATE.search(_text(block))
        if not found:
            continue
        day, month, year = found.groups()
        try:
            deadline = datetime.date(int(year), MONTHS.index(month) + 1, int(day))
        except ValueError:
            continue
        path = link.group(1)
        if path in seen:
            continue
        seen.add(path)
        text = _text(block)
        body = text.split(found.group(0))[0].strip() or "OHCHR"
        calls.append(Call(title=_title_from_slug(path), body=body[:80],
                          deadline=deadline, url=BASE + path))
    return sorted(calls, key=lambda c: c.deadline)


def match_text(call):
    """The text to run the taxonomy over.

    Includes the URL slug BOTH with and without hyphens, which is not
    decoration: the listing gives no description, titles are derived from the
    slug, and detail pages return 403 to non-browser clients (measured
    2026-08-17) so there is no prose to match on. The hyphenated form is what
    lets "faith-based" match; the spaced form catches terms written as
    separate words. Losing the hyphens dropped the faith-based organisations
    call from the results entirely.
    """
    slug = call.url.rstrip("/").rsplit("/", 1)[-1]
    return " ".join((call.title, call.body, slug, slug.replace("-", " ")))


def fetch_calls(client):
    html = client.get_text(LISTING, "ohchr", "calls-for-input")
    return parse_calls(html)


def open_calls(calls, today=None, horizon_days=None):
    """Calls still open, optionally only those closing within a horizon."""
    today = today or datetime.date.today()
    live = [c for c in calls if c.deadline >= today]
    if horizon_days is not None:
        cutoff = today + datetime.timedelta(days=horizon_days)
        live = [c for c in live if c.deadline <= cutoff]
    return live
