"""UK court judgments from Find Case Law (Christopher, 2026-09-07).

For Women Scotland shaped more of area 5 than any Bill, and the monitor
did not see it. The National Archives' Find Case Law publishes an Atom
feed per court, newest first, each entry carrying the neutral citation,
the public URL and a link to the judgment's Akoma Ntoso XML. Titles are
party names, so matching needs the text: the XML is fetched (never
archived -- canonical and re-fetchable) and passage-matched.

Courts watched: the Supreme Court, the Court of Appeal (Civil and
Criminal), the Administrative Court, the Family Division and the King's
Bench Division.
"""

from __future__ import annotations

import datetime
import html
import re
from dataclasses import dataclass

FEED = "https://caselaw.nationalarchives.gov.uk/atom.xml?court={court}&order=-date&per_page={n}"
COURTS = {
    "uksc": "Supreme Court", "ewca/civ": "Court of Appeal (Civil)", "ewca/crim": "Court of Appeal (Criminal)",
    "ewhc/admin": "High Court (Administrative Court)", "ewhc/fam": "High Court (Family Division)",
    "ewhc/kb": "High Court (King's Bench)",
}
_ENTRY = re.compile(r"<entry>(.*?)</entry>", re.S)
_TAG = re.compile(r"<[^>]+>")


@dataclass
class Judgment:
    title: str
    url: str
    court: str
    court_name: str
    published: datetime.date
    ncn: str = None            # [2026] UKSC 31
    xml_url: str = None
    summary: str = ""

    @property
    def key(self):
        return (self.ncn or self.url or "").replace(" ", "")


def _first(pattern, text, flags=re.S):
    m = re.search(pattern, text, flags)
    return html.unescape(m.group(1)).strip() if m else None


def parse_feed(xml_text, court):
    out = []
    for body in _ENTRY.findall(xml_text or ""):
        title = _first(r"<title[^>]*>(.*?)</title>", body)
        url = _first(r'<link href="([^"]+)" rel="alternate"/>', body)
        xml_url = _first(r'<link href="([^"]+)" rel="alternate" type="application/akn\+xml"/>', body)
        pub = _first(r"<published>(.*?)</published>", body) or ""
        ncn = _first(r'<tna:identifier[^>]*type="ukncn">(.*?)</tna:identifier>', body)
        summary = _first(r"<summary[^>]*>(.*?)</summary>", body) or ""
        try:
            published = datetime.date.fromisoformat(pub[:10]) if pub else None
        except ValueError:
            published = None
        if title and url:
            out.append(Judgment(title=title, url=url, court=court, court_name=COURTS.get(court, court),
                                published=published, ncn=ncn, xml_url=xml_url,
                                summary=" ".join(_TAG.sub(" ", summary).split())))
    return out


def fetch_recent(client, court, n=50):
    raw = client.get_text(FEED.format(court=court, n=n), "caselaw", "feed-{0}".format(court.replace("/", "-")),
                          archive=False)
    return parse_feed(raw, court)


def fetch_text(client, judgment, cap=400000):
    """The judgment's words, markup stripped, for passage matching."""
    if not judgment.xml_url:
        return ""
    raw = client.get_text(judgment.xml_url, "caselaw", "judgment", archive=False)
    return " ".join(_TAG.sub(" ", html.unescape(raw[:cap])).split())
