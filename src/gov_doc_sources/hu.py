"""Hungary: the government's public consultation of draft legislation
(társadalmi egyeztetés, kormany.hu) and the Acts and decrees of the Magyar
Közlöny, mirrored from the gazette collector's tables.

Probed 16 October 2026 (docs/hungary-scope.md, "Government consultations and
publications"). The Országgyűlés's site answers every client with a CAPTCHA
and is never touched.

TÁRSADALMI EGYEZTETÉS ('te'). Under Act CXXXI of 2010 a ministry publishes
each draft law or decree for public comment, with an address for comments
and a deadline (usually eight days). kormany.hu's document library
(Dokumentumtár, category 'Jogszabálytervezetek') lists them. The site is an
Angular application whose browser code reads its data from
https://kormany.hu/application/ (environment apiUrl); robots.txt disallows
only /publicapi, so /application is allowed. One call a hundred drafts:

    GET /application/document-groups?filter={"categories":[2]}
        &pagination={"page":N,"itemsPerPage":100}

newest first (visibleDate), each with the title, the lead (a summary of the
draft), the ministry, the comment address, the publication date and the
deadline. Pages are read until one holds nothing published in the window:
four or five calls (388 drafts in the 92 days to 16 October 2026, 153 still
open). The page served for people is https://kormany.hu/dokumentumtar/<slug>.

Doc type: the instrument is read off the title, the last of 'törvény' (an
Act) and 'rendelet' (a decree) it names deciding ("a ... 2011. évi CXC.
törvény végrehajtásáról szóló ... rendelet módosításáról" is a decree),
then off the lead ("törvényjavaslat", "kormányrendelet"): a draft Act is a
'bill_draft', a draft decree a 'regulation_draft', anything else (a
programme, a strategy) a 'consultation'.

MAGYAR KÖZLÖNY ('mk', a mirror). tools/hu_gazette.py already reads the
gazette's RSS and every issue's contents page into hu_gazette_entries (keyed
on the official designation, '225/2026. (X. 6.) Korm. rendelet'). The
mirror re-files the government's instruments only: Acts ('act') and the
amendments to the Fundamental Law ('fundamental_law') as 'law', government
decrees ('gov_decree') and ministerial decrees ('ministerial_decree') as
'regulation'. Government resolutions (Korm. határozat), OGY resolutions,
presidential and Constitutional Court decisions stay in the gazette tables.
The designation is passed as a ref, so config/watchlist-hu.yaml's keys
('2026. évi XXIV. törvény') mark a row watched, and an amendment to the
Fundamental Law carries 'HU4' (Chris, 10 October 2026: every amendment goes
to triage whatever its words; its title names no subject). Run after
tools/hu_gazette.py in the Hungarian weekly so the mirror is this week's read.
"""

from __future__ import annotations

import re

from src import gov_docs as G

CC = "hu"

KORMANY = "https://kormany.hu"
DRAFTS = (KORMANY + '/application/document-groups?filter={"categories":[2]}'
          '&pagination={"page":%d,"itemsPerPage":100}')
PAGE = KORMANY + "/dokumentumtar/{0}"
MAX_PAGES = 12

GAZETTE_TYPES = {"act": "law", "fundamental_law": "law", "gov_decree": "regulation",
                 "ministerial_decree": "regulation"}

_INSTRUMENT = re.compile(r"törvény|rendelet", re.I)


def draft_kind(title, lead):
    t = title or ""
    words = _INSTRUMENT.findall(t)
    if words:
        return "bill_draft" if words[-1].lower() == "törvény" else "regulation_draft"
    lead = lead or ""
    if re.search(r"törvényjavaslat|törvénytervezet|törvény\s+tervezet|törvény\s+megalkotás", lead, re.I):
        return "bill_draft"
    if re.search(r"rendelet", lead, re.I):
        return "regulation_draft"
    return "consultation"


def _title(name):
    """The draft's own words: the house prefix 'Társadalmi egyeztetés' kept, as printed."""
    return G.one_line(name)


def parse_drafts(reply):
    """([entry], [visibleDate]) from one document-groups page."""
    out, dates = [], []
    for x in (reply or {}).get("data") or []:
        slug, name = x.get("slug"), x.get("name")
        if not slug or not name:
            continue
        dates.append(x.get("visibleDate") or "")
        cat = x.get("category") or {}
        if isinstance(cat, dict) and cat.get("id") not in (None, 2):
            continue
        lead = G.text(x.get("lead"))
        ministry = (x.get("ministry") or {}).get("name") if isinstance(x.get("ministry"), dict) else None
        status = "Társadalmi egyeztetés"
        if x.get("email"):
            status += "; észrevételek: {0}".format(x["email"])
        out.append(G.entry("te", slug, _title(name), draft_kind(name, lead), body=ministry,
                           published=x.get("visibleDate"), closing_date=x.get("deadline"),
                           url=PAGE.format(slug), summary=lead, status=status))
    return out, dates


def fetch_tarsadalmi_egyeztetes(client, today, log):
    start = G.window_start(today)
    entries, gaps, pages = [], [], 0
    for page in range(1, MAX_PAGES + 1):
        reply = client.get_json(DRAFTS % page, "hu-govdocs", "te-{0}".format(page))
        got, dates = parse_drafts(reply)
        pages += 1
        entries += got
        if not dates or max(dates) < start:
            break
    else:
        gaps.append("kormany.hu drafts: stopped after {0} pages".format(MAX_PAGES))
    note = "{0} draft(s) on {1} page(s) of kormany.hu Jogszabálytervezetek".format(len(entries), pages)
    return G.fetched(entries, note=note, gaps=gaps)


# --- the Magyar Közlöny mirror ---------------------------------------------------

def _gazette_body(kind, issuer):
    if kind in ("act", "fundamental_law"):
        return "Országgyűlés"
    if issuer == "Korm.":
        return "Kormány"
    return issuer or None


def mirror_gazette(conn, cc, today):
    start = G.window_start(today)
    marks = ",".join("?" * len(GAZETTE_TYPES))
    try:
        rows = conn.execute(
            "SELECT e.entry_key, e.issue_key, e.date, e.page, e.type, e.issuer, e.title, i.url "
            "FROM hu_gazette_entries e LEFT JOIN hu_gazette_issues i ON i.issue_key = e.issue_key "
            "WHERE e.date >= ? AND e.type IN ({0}) ORDER BY e.date".format(marks),
            (start,) + tuple(GAZETTE_TYPES)).fetchall()
        last = conn.execute("SELECT MAX(date) FROM hu_gazette_issues").fetchone()[0]
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["hu_gazette_entries unreadable: {0}".format(str(exc)[:160])])
    out = []
    for key, issue, date, page, kind, issuer, title, url in rows:
        refs = [key] + (["HU4"] if kind == "fundamental_law" else [])
        summary = "Magyar Közlöny {0}{1}".format(issue, ", {0}. oldal".format(page) if page else "")
        out.append(G.entry("mk", key, title or key, GAZETTE_TYPES[kind], body=_gazette_body(kind, issuer), published=date,
                           url=url, summary=summary, status=kind, refs=refs))
    gaps = []
    if not rows:
        gaps.append("hu_gazette_entries holds nothing in the window (has tools/hu_gazette.py run?)")
    return G.fetched(out, note="mirrored from hu_gazette_entries (latest issue {0})".format(last),
                     gaps=gaps)


SOURCES = (
    G.Source(code="te", name="kormany.hu társadalmi egyeztetés (draft laws and decrees)",
             fetch=fetch_tarsadalmi_egyeztetes, url=KORMANY + "/dokumentumtar"),
    G.Source(code="mk", name="Magyar Közlöny (Acts, government and ministerial decrees)",
             url="https://magyarkozlony.hu/", mirror=mirror_gazette),
)
