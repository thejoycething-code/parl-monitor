"""Regulators' consultations that never reach gov.uk (Christopher, 2026-09-07).

Ofcom's age-assurance and online safety codes, NICE's guidance
consultations, NHS England's service specifications: the consultations
feed reads gov.uk only and misses all of them.

What answers a robot, measured 2026-09-07: NICE (a plain HTML table of
guidance in consultation with closing dates) and NHS England (whose
consultations live on engage.england.nhs.uk, a Citizen Space site with a
parseable listing). What does not: ofcom.org.uk, gmc-uk.org and
equalityhumanrights.com all answer 403 to every non-browser client,
browser user-agent included. Those are declared here as BLOCKED so the
edition's gaps footer says so every week rather than the feed quietly
covering less than its name suggests.
"""

from __future__ import annotations

import datetime
import html
import re
from dataclasses import dataclass

_TAG = re.compile(r"<[^>]+>")
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                       "august", "september", "october", "november", "december"], 1)}

BLOCKED = {
    "Ofcom": "ofcom.org.uk answers 403 to every non-browser client (measured 2026-09-07)",
    "GMC": "gmc-uk.org answers 403 to every non-browser client (measured 2026-09-07)",
    "EHRC": "equalityhumanrights.com answers 403 to every non-browser client (measured 2026-09-07)",
}


@dataclass
class RegConsultation:
    regulator: str
    title: str
    url: str
    closes: datetime.date = None
    kind: str = None

    @property
    def text(self):
        return " ".join(x for x in (self.title, self.kind) if x)


def _date(text):
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text or "")
    if not m or m.group(2).lower() not in MONTHS:
        return None
    try:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def _cells(row_html):
    return [html.unescape(" ".join(_TAG.sub(" ", c).split()))
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)]


def parse_nice(page_html):
    """NICE 'guidance in consultation': one table row per consultation --
    title [ID], consultation type, guidance type, closing date."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page_html or "", re.S):
        cells = _cells(row)
        link = re.search(r'href="([^"]+)"', row)
        if len(cells) < 3 or not link or "nice.org.uk" not in link.group(1) and not link.group(1).startswith("/"):
            continue
        url = link.group(1)
        if url.startswith("/"):
            url = "https://www.nice.org.uk" + url
        closes = next((_date(c) for c in cells if _date(c)), None)
        out.append(RegConsultation(regulator="NICE", title=cells[0], url=url, closes=closes,
                                   kind=" / ".join(c for c in cells[1:3] if c and not _date(c))))
    return out


def parse_citizen_space(page_html, base, regulator):
    """A Citizen Space listing (engage.england.nhs.uk): each consultation is
    an article/list item with a title link and a 'Closes DATE' line."""
    out = []
    blocks = re.findall(r"<(?:article|li)[^>]*>(.*?)</(?:article|li)>", page_html or "", re.S)
    for b in blocks:
        link = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not link:
            continue
        title = html.unescape(" ".join(_TAG.sub(" ", link.group(2)).split()))
        if len(title) < 8:
            continue
        url = link.group(1)
        if url.startswith("/"):
            url = base.rstrip("/") + url
        if base.split("//")[-1].split("/")[0] not in url:
            continue
        text = " ".join(_TAG.sub(" ", b).split())
        m = re.search(r"Clos(?:es|ing|ed)[^0-9]{0,20}(\d{1,2}\s+[A-Za-z]+\s+\d{4})", text)
        out.append(RegConsultation(regulator=regulator, title=title, url=url,
                                   closes=_date(m.group(1)) if m else None))
    return out


SOURCES = [
    ("NICE", "https://www.nice.org.uk/guidance/inconsultation", parse_nice),
    ("NHS England", "https://www.engage.england.nhs.uk/consultation_finder/?sort_on=iconsultable_enddate&sort_order=ascending&advanced=1&st=open",
     lambda page: parse_citizen_space(page, "https://www.engage.england.nhs.uk", "NHS England")),
]


def fetch_all(client, log=print):
    """-> ([RegConsultation], [(regulator, reason)]) -- the second list is
    every source that could not be read, blocked ones included, so the
    caller can record each as a gap."""
    out, gaps = [], [(name, why) for name, why in BLOCKED.items()]
    for name, url, parser in SOURCES:
        try:
            page = client.get_text(url, "regulators", name.lower().replace(" ", "-"), archive=False)
            found = parser(page)
            if not found:
                gaps.append((name, "listing answered but nothing parsed (layout changed?)"))
            out.extend(found)
        except Exception as exc:                            # noqa: BLE001
            gaps.append((name, "unreachable: {0}".format(str(exc)[:80])))
    return out, gaps
