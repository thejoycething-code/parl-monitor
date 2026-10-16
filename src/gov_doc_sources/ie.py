"""Ireland: statutory instruments from the electronic Irish Statute Book.

Probed 16 October 2026.

WHAT IRELAND'S UK PARITY WOULD BE, AND WHY IT IS NOT HERE. Government
consultations and publications live on www.gov.ie, which answers our
user agent with a CloudFront 403 "Request blocked", robots.txt included
(the scope doc found the same for a browser UA and curl on 9 October).
That is an address block; it is never worked around. The legitimate routes
tried instead (docs/ireland-scope.md, "Government consultations and
publications"):
  * Iris Oifigiúil (the state gazette, where SIs, notices and some
    consultations are notified): robots.txt is Disallow: / for every agent;
  * data.gov.ie: robots.txt disallows /api/ (the CKAN API), so its
    datasets cannot be searched by program;
  * merrionstreet.ie (the Government news service) and ncca.ie (the
    curriculum council: SPHE and RSE consultations): 403 to robots.txt;
  * agencies with their own hosts answer (hiqa.ie, cnam.ie,
    electoralcommission.ie, lawreform.ie, citizensassembly.ie) but none
    publishes a machine-readable list of consultations with closing dates;
    each would be its own HTML scraper for a handful of items a year. Left
    as later options;
  * GitHub's runners: gov.ie from a hosted runner is still untested (a
    one-off probe workflow is the next step, as the scope doc says).

STATUTORY INSTRUMENTS (code 'isb'). www.irishstatutebook.ie (Office of the
Attorney General) lists every SI of a year on one page,
/eli/<year>/si/ (515 for 2026 on 16 October, eleven of them PDF-only and
not yet hyperlinked), number and title, no date.
robots.txt answers 404 (no rules). The newest TAIL numbers are the
candidates (about 55 SIs a month, so 250 covers the 92-day window with
room); a candidate whose TITLE already matches the taxonomy has its page
read (at most PAGE_CAP a run), which gives:
  * the date the making was notified in Iris Oifigiúil ("Notice of the
    making of this Statutory Instrument was published in 'Iris Oifigiúil'
    of 2nd October, 2026"): the published date, else the signing date;
  * the maker ("I, JAMES BROWNE, Minister for Housing, Local Government and
    Heritage"): the body;
  * the Explanatory Note: the summary.
A candidate whose title does not match is not read, carries no date and so
falls outside the window: it could not pass the precision gate (a made
regulation needs tier 1, on title and summary) without its note, and the
title is the strongest signal we have before reading. In January to April
the previous year's tail is read too.

CLASSIFICATION. The English shared taxonomy (config/taxonomy.yaml), with
its Irish vocabulary (v1.20), as tools/ie_monitor.py classifies.
"""

from __future__ import annotations

import datetime
import re

from src import gov_docs as G

CC = "ie"
TAXONOMIES = (("taxonomy.yaml", None),)

ISB = "https://www.irishstatutebook.ie"
YEAR_LIST = ISB + "/eli/{0}/si/"
SI_PAGE = ISB + "/eli/{0}/si/{1}/made/en/html"
TAIL = 250
PAGE_CAP = 40

ROW = re.compile(r'<td class="align-center">\s*(\d+)\s*</td>\s*<td>(.*?)</td>', re.S)
IRIS = re.compile(r"published in\W{0,3}Iris Oifigi[uú]il\W{0,3}of\s+(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
                  r"([A-Za-z]+),?\s+(\d{4})")
GIVEN = re.compile(r"(?:GIVEN under|Signed|Made)\b[^.]{0,80}?(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
                   r"([A-Za-z]+),?\s+(\d{4})")
MAKER = re.compile(r"\bI,\s+[A-Z][A-Z .'’-]+,\s+((?:Minister|Minister of State) (?:for|at) "
                   r".{3,160}?),?\s+in exercise")
MAKER_BODY = re.compile(r"^\s*(?:The\s+)?([A-Z][A-Za-z ,&'-]{3,80}?),? in exercise of the powers")


def parse_year_list(raw):
    """[(number, title, has_page)] from a year's SI list, in the page's order. An SI
    not yet hyperlinked (PDF only, the newest few) has no HTML page to read."""
    out = []
    for n, cell in ROW.findall(raw or ""):
        title = G.text(cell).rstrip(".")
        if title:
            out.append((int(n), title, "/si/" in cell and ".html" in cell))
    return out


def _date(m):
    if not m:
        return None
    return G.long_date("{0} {1} {2}".format(m.group(1), m.group(2), m.group(3)))


def parse_si_page(raw):
    """{published, body, summary} from an SI's page."""
    s = G.text(raw)
    out = {"published": _date(IRIS.search(s)) or _date(GIVEN.search(s)), "body": None,
           "summary": None}
    m = MAKER.search(s)
    if m:
        out["body"] = m.group(1).strip()
    else:
        i = s.find("Notice of the making")
        tail = s[i:] if i >= 0 else s
        tail = re.sub(r"^.*?\d{4}\.\s*", "", tail, count=1)
        m2 = MAKER_BODY.search(tail)
        if m2:
            out["body"] = m2.group(1).strip()
    i = s.find("EXPLANATORY NOTE")
    if i >= 0:
        note = s[i + len("EXPLANATORY NOTE"):]
        note = re.sub(r"^\s*\(\s*This note is not part of the Instrument.*?\)\s*", "", note)
        for stop in ("Privacy Statement", "Ráiteas Príobháideachais"):
            j = note.find(stop)
            if j >= 0:
                note = note[:j]
        out["summary"] = note.strip()[:G.SUMMARY_CAP] or None
    if not out["summary"]:
        # No Explanatory Note (common in a minister's regulations): the
        # enacting words and the first provisions stand in.
        i = s.find("in exercise of the powers")
        if i >= 0:
            out["summary"] = s[i:i + 600].strip()
    return out


def _looks_ours(title, taxes, wl):
    from src import latam
    e = G.classify({"doc_id": "isb:x", "title": title, "summary": None}, taxes, wl)
    return bool(latam.areas_of(e["areas"]) or e["watch_keys"])


def fetch_isb(client, today, log, taxes=None, wl=None):
    taxes = taxes if taxes is not None else G.taxonomies(CC)
    wl = wl if wl is not None else G.watchlist(CC)
    d = datetime.date.fromisoformat(today)
    years = [d.year] + ([d.year - 1] if d.month <= 4 else [])
    out, gaps, notes, read = [], [], [], 0
    for year in years:
        try:
            rows = parse_year_list(client.get_text(YEAR_LIST.format(year), "ie-govdocs",
                                                   "isb-{0}-{1}".format(year, today)))
        except Exception as exc:                            # noqa: BLE001
            gaps.append("ISB {0} list: {1}".format(year, str(exc)[:160]))
            continue
        if not rows:
            continue
        top = max(r[0] for r in rows)
        tail = sorted([r for r in rows if r[0] > top - TAIL], reverse=True)
        ours = [r for r in tail if _looks_ours(r[1], taxes, wl)]
        unlinked = [r for r in ours if not r[2]]
        notes.append("{0}: {1} SIs listed, {2} in the tail, {3} titles on our ground".format(
            year, len(rows), len(tail), len(ours)))
        if unlinked:
            notes.append("{0} on our ground not yet hyperlinked (PDF only): {1}".format(
                len(unlinked), ", ".join("S.I. {0}/{1}".format(r[0], year) for r in unlinked)))
        for n, title, has_page in ours:
            if not has_page:
                continue
            if read >= PAGE_CAP:
                gaps.append("ISB: page cap {0} reached; later titles not read".format(PAGE_CAP))
                break
            url = SI_PAGE.format(year, n)
            try:
                page = parse_si_page(client.get_text(url, "ie-govdocs", "isb-{0}-{1}".format(year, n),
                                                     archive=False))
            except Exception as exc:                        # noqa: BLE001
                gaps.append("ISB S.I. {0}/{1}: {2}".format(n, year, str(exc)[:120]))
                continue
            read += 1
            out.append(G.entry("isb", "{0}/si/{1}".format(year, n), title, "regulation",
                               body=page["body"], published=page["published"], url=url,
                               summary=page["summary"], status="S.I. No. {0} of {1}".format(n, year),
                               refs=["S.I. No. {0} of {1}".format(n, year)]))
    return G.fetched(out, note="; ".join(notes) + "; {0} pages read".format(read), gaps=gaps)


SOURCES = (
    G.Source(code="isb", name="Irish Statute Book (statutory instruments)",
             url="https://www.irishstatutebook.ie/eli/", fetch=fetch_isb),
)
