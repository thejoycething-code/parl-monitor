"""Devolved government consultations: Scotland, Wales, Northern Ireland.

Three EXECUTIVE sources (governments, not parliaments), probed 2026-08-22:

  * consult.gov.scot -- Citizen Space; its JSON API is DISABLED on this
    instance (every /api/* version 404s), so the finder page is the source.
  * consultations.nidirect.gov.uk -- Citizen Space, same markup as Scotland.
  * www.gov.wales/consultations -- Drupal listing. CloudFront blocks every
    non-browser UA; the browser UA for this one host was authorised by
    Christopher on 2026-08-22 (see src/http.py).

Listings carry no closing date on any of the three; the detail page does
("Closes 29 Oct 2026" on Citizen Space, "Consultation ends: 16 October
2026" on gov.wales), so each NEW consultation costs one detail fetch and
known keys are never refetched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

SOURCES = {
    "scotland": "https://consult.gov.scot/consultation_finder/?st=open",
    "ni": "https://consultations.nidirect.gov.uk/consultation_finder/?st=open",
    # field_consultation_status=1 is the form's real 'Open' radio value; a
    # made-up ?status=open is SILENTLY IGNORED and serves the mixed listing.
    "wales": ("https://www.gov.wales/consultations"
              "?field_consultation_status=1&page={0}"),
}
WALES_BASE = "https://www.gov.wales"

MONTHS = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"))}


@dataclass
class Consultation:
    key: str            # '<nation>:<url path>'
    nation: str
    title: str
    url: str
    summary: str = ""
    opened: str = None
    closes: str = None


def clean(text):
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def parse_date(text):
    """'6 Aug 2026' / '29 October 2026' -> ISO, else None -- never guessed."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text or "")
    if not m:
        return None
    month = next((v for k, v in MONTHS.items()
                  if k.startswith(m.group(2).lower())), None)
    if not month:
        return None
    return "{0}-{1:02d}-{2:02d}".format(m.group(3), month, int(m.group(1)))


def _key(nation, url):
    return "{0}:{1}".format(nation, re.sub(r"^https?://[^/]+", "", url))


def parse_citizen_space_finder(html, nation, host):
    """One <li class="... consultation-state-open"> per open consultation:
    an <h2><a> title, a summary <span>, and an 'Opened <date>' stamp."""
    out = []
    for block in re.findall(
            r'<li[^>]*consultation-state-open.*?</li>', html or "", re.S):
        link = re.search(r'<h2>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                         block, re.S)
        if not link:
            continue
        url = link.group(1)
        if url.startswith("/"):
            url = host + url
        summary = re.search(r'<span>\s*([^<]{20,})</span>', block)
        opened = re.search(r'Opened</span>\s*([^<]+)', block)
        out.append(Consultation(
            key=_key(nation, url), nation=nation,
            title=clean(link.group(2)), url=url,
            summary=clean(summary.group(1))[:500] if summary else "",
            opened=parse_date(opened.group(1) if opened else "")))
    return out


def parse_citizen_space_detail(html):
    """(opened, closes) from the sidebar's 'Opened'/'Closes' date pair."""
    closes = re.search(r'Closes</span>\s*([^<]+)', html or "")
    opened = re.search(r'Opened</span>\s*([^<]+)', html or "")
    return (parse_date(opened.group(1) if opened else ""),
            parse_date(closes.group(1) if closes else ""))


def parse_govwales_index(html):
    """gov.wales index-list items typed 'Open consultation' or 'Open call
    for evidence'. The listing's <time> is the last-updated stamp, NOT the
    open date -- dates come from the detail page."""
    out = []
    for block in re.findall(
            r'<li class="index-list__item">.*?</li>', html or "", re.S):
        if not re.search(r'index-list__type">\s*Open\b', block):
            continue
        link = re.search(r'index-list__title">\s*<a href="([^"]+)"[^>]*>'
                         r'\s*(?:<span[^>]*>)*([^<]+)', block, re.S)
        if not link:
            continue
        url = link.group(1)
        if url.startswith("/"):
            url = WALES_BASE + url
        topics = clean(" / ".join(re.findall(
            r'class="from-area"[^>]*>([^<]+)', block)))
        out.append(Consultation(
            key=_key("wales", url), nation="wales",
            title=clean(link.group(2)), url=url, summary=topics))
    return out


def parse_govwales_detail(html):
    """(launched, ends) from the header-meta label rows.

    ANCHOR ON THE LABEL ROW, NOT THE WORD "Consultation" (21 September 2026).
    gov.wales words the same two rows after the exercise: a call for evidence
    says "Call for evidence ends:", and matching "Consultation ends:" left
    those rows with no dates at all. Two were sitting in the store that way,
    the National Cancer Strategy and the culture and sport vision, so the
    actionability gate could not judge them and they could never reach a
    brief. The listing already accepted calls for evidence; only the detail
    parser did not. The markup is identical either side, so the wording
    before "ends:" is what varies and is what this ignores.
    """
    text = re.sub(r"\s+", " ", html or "")
    ends = re.search(r'<div class="label">[^<]*ends:</div>\s*<div[^>]*>\s*([^<]+)',
                     text)
    launched = re.search(r'<div class="label">[^<]*launched:</div>.*?<time[^>]*>([^<]+)',
                         text)
    return (parse_date(launched.group(1) if launched else ""),
            parse_date(ends.group(1) if ends else ""))


def render_consultations(conn, nation, shown, today, n=10, out=print):
    """The monitor section for one nation's open government consultations.

    `shown` is the calling monitor's own area filter, so hidden areas stay
    hidden here too. OURS items render with closing dates and day counts;
    the rest are a single honest total, never listed and never suppressed
    silently.
    """
    import json as _json
    rows = conn.execute(
        "SELECT title, url, closes, opened, areas FROM dg_consultations "
        "WHERE nation = ? AND (closes IS NULL OR closes >= ?) "
        "ORDER BY COALESCE(closes, '9999') ASC", (nation, today)).fetchall()
    ours = [r for r in rows
            if r["areas"] and shown(_json.loads(r["areas"]))]
    out("  {0} open government consultation(s); {1} on our ground by "
        "title+summary.".format(len(rows), len(ours)))
    out("  EXECUTIVE, not parliament: responding is a campaign decision, "
        "never automatic.\n")
    for r in ours[:n]:
        a = shown(_json.loads(r["areas"]))
        if r["closes"]:
            try:
                days = (_date(r["closes"]) - _date(today)).days
                closes = "closes {0} ({1} days)".format(r["closes"], days)
            except ValueError:
                closes = "closes " + r["closes"]
        else:
            closes = "no closing date parsed"
        out("  OURS  {0}   areas {1}".format(
            (r["title"] or "")[:62], ",".join(map(str, a))))
        out("        {0}".format(closes))
        out("        {0}".format(r["url"]))
    if len(ours) > n:
        out("  ...and {0} more.".format(len(ours) - n))


def _date(iso):
    import datetime as _dt
    return _dt.date(*[int(x) for x in iso.split("-")])
