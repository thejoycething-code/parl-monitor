"""legislation.gov.uk Act verification (handoff 4.8).

Contents come from /ukpga/{year}/{chapter}/contents/data.xml as
<ContentsNumber>/<ContentsTitle> pairs; grep them for taxonomy terms to locate
the relevant section (locate by title, not a hardcoded number, per handoff 4.8).
For ukpga/2026/20 this correctly finds s.241 "Removal of women from the criminal
law related to abortion" (and s.242), both in force at Royal Assent.
In-force status comes from the section HTML annotations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LEG_BASE = "https://www.legislation.gov.uk"


@dataclass
class ContentsEntry:
    number: str
    title: str


_PAIR = re.compile(
    r"<ContentsNumber[^>]*>(.*?)</ContentsNumber>\s*<ContentsTitle[^>]*>(.*?)</ContentsTitle>",
    re.S,
)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def parse_contents(xml_text):
    """Parse contents data.xml into ordered ContentsEntry list.

    A section's number and title are adjacent (ContentsNumber immediately
    followed by ContentsTitle within a contents item); pairing on that adjacency
    is robust to the Part/Chapter nesting, where container numbers have no
    directly following title. Inner markup in a title is stripped.
    """
    entries = []
    for number, title in _PAIR.findall(xml_text):
        title = _WS.sub(" ", _TAG.sub("", title)).strip()
        entries.append(ContentsEntry(number=number.strip(), title=title))
    return entries


def locate_sections(entries, term):
    """Contents entries whose title contains term (case-insensitive)."""
    low = term.lower()
    return [e for e in entries if e.title and low in e.title.lower()]


# In-force annotation phrases, most specific first.
_INFORCE_PATTERNS = [
    ("in_force_at_royal_assent", "in force at royal assent"),
    ("not_yet_in_force", "not yet in force"),
    ("comes_into_force", "comes into force"),
]


@dataclass
class InForceStatus:
    section: str
    in_force: bool          # True/False, or None if unknown
    note: str               # the matched annotation phrase


def section_in_force(section_html, section_number):
    low = section_html.lower()
    for key, phrase in _INFORCE_PATTERNS:
        if phrase in low:
            in_force = key == "in_force_at_royal_assent" or key == "comes_into_force"
            if key == "not_yet_in_force":
                in_force = False
            return InForceStatus(section=section_number, in_force=in_force, note=phrase)
    return InForceStatus(section=section_number, in_force=None, note="unknown")


# -- fetch helpers ----------------------------------------------------------

def fetch_contents(client, chapter):
    """chapter like 'ukpga/2026/20'. Returns list[ContentsEntry]."""
    url = "{0}/{1}/contents/data.xml".format(LEG_BASE, chapter)
    slug = chapter.replace("/", "-")
    return parse_contents(client.get_text(url, "legislation", "{0}-contents".format(slug)))


def fetch_section_status(client, chapter, section_number):
    url = "{0}/{1}/section/{2}".format(LEG_BASE, chapter, section_number)
    slug = chapter.replace("/", "-")
    html = client.get_text(url, "legislation", "{0}-section-{1}".format(slug, section_number))
    return section_in_force(html, section_number)


def browse_year_chapters(client, year, kind="ukpga"):
    """Extract chapter numbers from the year browse page."""
    url = "{0}/{1}/{2}".format(LEG_BASE, kind, year)
    html = client.get_text(url, "legislation", "{0}-{1}-browse".format(kind, year))
    return sorted(set(int(m) for m in re.findall(r"/%s/%s/(\d+)/contents" % (kind, year), html)))
