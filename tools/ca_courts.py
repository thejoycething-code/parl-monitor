#!/usr/bin/env python3
"""Supreme Court of Canada: judgments, and applications for leave to appeal.

    python3 tools/ca_courts.py                          # both weekly feeds
    python3 tools/ca_courts.py --backfill --since 2010  # the year indexes, hand-dispatched
    python3 tools/ca_courts.py --backfill --since 2015 --until 2015 --limit 70
    python3 tools/ca_courts.py --federal-court          # also the Federal Court feed (low yield)
    python3 tools/ca_courts.py --dry-run --db /tmp/ca.db

Built 2 October 2026 on Christopher's approval of the federal-sources scope,
section (5). Carter (2015 SCC 5) struck down the assisted-suicide ban two
years before Parliament legislated, and Bedford (2013 SCC 72) the
prostitution laws: on several of our issues the Court moved first and the
monitor watched only the chamber that followed.

THE SOURCES (Lexum's decisions.scc-csc.ca, probed 1-2 October 2026):
  * the judgments JSON Feed, scc-csc/scc-csc/en/json/rss.do, 100 items.
    It lists PUBLISHED AND UPDATED documents -- Ford v. Quebec (1988) beside
    2026 SCC 31 -- so it is keyed on the Lexum item id and each item is READ
    ONCE: an id already in ca_judgments is not fetched again, only re-seen;
  * the leave JSON Feed, scc-csc/scc-l-csc-a/en/json/rss.do, 100 items,
    "Granted" or "Dismissed". The leave text names only the parties and the
    lower court, so for a GRANTED leave the docket page on scc-csc.ca
    (cases-dossiers/search-recherche/<docket>/) is read for the Registrar's
    case summary and its keywords, and that is what is classified. This is
    the early-warning layer: a granted leave is a judgment a year or so out;
  * --backfill: the year index, scc-csc/scc-csc/en/<YYYY>/nav_date.do, 25 a
    page (about 60 judgments a year), from 2010 by default.

WHAT IS MATCHED: THE HEADNOTE, NOT THE JUDGMENT. Each judgment's page
(item/<id>/index.do?iframe=true) gives the metadata table (date, neutral and
SCR citations, docket, judges, on appeal from, subjects) and the full text.
The text matched is the HEADNOTE: from "Indexed as" to "Cases Cited". The
full text drags in every precedent it cites -- Carter picked up area 1 from
an abortion case it cites -- and the style of cause above "Indexed as" holds
the interveners' names, which are not what the Court decided ("Euthanasia
Prevention Coalition" intervening in a sentencing appeal is not a judgment
on euthanasia). Titles are party names and match nothing, as the UK found
(src/ingest/caselaw.py). Matching is per passage with the subjects and the
case name as title passages, as every Canadian collector does.

THE INTERVENERS ARE THE PRIZE. Carter had 25, among them the Evangelical
Fellowship, the Catholic Civil Rights League, ARPA, the Euthanasia Prevention
Coalition and Dying With Dignity: an ally and opponent map per case. They are
stored as a JSON list of names, read from the headnote's own style of cause
(one party per line in the Court's Word styles). NULL means the list could
not be read; [] means the case had none.

CONTEXT ONLY. A judgment never places anyone and never enters a 5CA sheet.
At most a stance file cites one in a reading's `why` (C-7 cites Truchon,
C-14 cites Carter). Taxonomy hits go to tools/ca_triage.py for a 0-3 score
and a why-line; nothing here calls the model.

THE FEDERAL COURT (--federal-court, off by default). Its RSS
(decisions.fct-cf.gc.ca/fc-cf/decisions/en/rss.do) is 100 items, nearly all
immigration (area 11, collated, never campaigned), so immigration titles are
counted and skipped unread. The rest are matched on their reasons -- an FC
decision has no headnote -- and, as the UK rule for a judgment's full text,
two qualifying passages are needed. Rows are 'fc-<id>': a different Lexum
instance, a different id space. The Federal Court of Appeal's feed was not
found.

NOT HERE: PROVINCIAL COURTS. Much of our ground is provincial (the
Saskatchewan pronoun case, Alberta's gender laws, conscience rules), and the
only uniform route is the CanLII API, which answers 401 without a key. A key
is free on request for non-commercial use; applying is Christopher's call.

ROBOTS. Both hosts were read on 1 October 2026. decisions.scc-csc.ca
disallows four icm documents, none of ours; www.scc-csc.ca disallows
/cso-dce/ and any path containing 22551. ROBOTS_DISALLOW below holds them, a
disallowed URL is skipped and said, and the client sends the honest CitizenGO
User-Agent at one request every THROTTLE_S seconds per host.

NORMA. Lexum's platform asks a client "accessing a large number of files" to
solve a CAPTCHA; it did so (a 403) after about 200 pages at one a second on
2 October 2026. It is never answered or worked around: the run stops at the
first challenge, records ONE gap, and the next run carries on, since nothing
unread is marked read. Hence the pacing and the DEFAULT_LIMIT page cap.

Every failed fetch is a gap (db.record_gaps), never an empty week. ONE WRITER
AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ca-courts"
BASE = "https://decisions.scc-csc.ca"
JUDGMENTS_FEED = BASE + "/scc-csc/scc-csc/en/json/rss.do"
LEAVE_FEED = BASE + "/scc-csc/scc-l-csc-a/en/json/rss.do"
YEAR_INDEX = BASE + "/scc-csc/scc-csc/en/{year}/nav_date.do?iframe=true&page={page}"
ITEM = BASE + "/scc-csc/scc-csc/en/item/{id}/index.do?iframe=true"
LEAVE_ITEM = BASE + "/scc-csc/scc-l-csc-a/en/item/{id}/index.do?iframe=true"
DOCKET = "https://www.scc-csc.ca/cases-dossiers/search-recherche/{docket}/"
FC_FEED = "https://decisions.fct-cf.gc.ca/fc-cf/decisions/en/rss.do"
FC_ITEM = "https://decisions.fct-cf.gc.ca/fc-cf/decisions/en/item/{id}/index.do?iframe=true"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")
BACKFILL_FROM = 2010
PER_PAGE = 25
# PACING. Lexum's Norma served its CAPTCHA after about 200 pages at one a
# second on 2 October 2026 (the first smoke run: 100 judgments, then the
# leave pages). So: one request every THROTTLE_S seconds per host, and at
# most DEFAULT_LIMIT item pages a run unless --limit says otherwise. A weekly
# feed brings 5-25 new items; the first run and the backfill drain over
# several runs, which the cap discloses.
THROTTLE_S = 3.0
DEFAULT_LIMIT = 60
HIDDEN_AREAS = (11,)
HEADNOTE_CAP = 50000     # TWU (2018 SCC 32) runs to 34,000 characters before Cases Cited
# The Federal Court: titles naming an immigration respondent are area 11,
# hidden, and are not read at all.
FC_IMMIGRATION = re.compile(r"\((?:Citizenship and Immigration|Public Safety and Emergency "
                            r"Preparedness|Immigration, Refugees and Citizenship|Minister of "
                            r"Citizenship and Immigration|Citoyennet\u00e9 et Immigration|"
                            r"S\u00e9curit\u00e9 publique et Protection civile)\)", re.I)
# robots.txt as read on 1 October 2026: (host, path pattern).
ROBOTS_DISALLOW = (
    ("decisions.scc-csc.ca", re.compile(r"^/icm/icm/en/(?:item/)?(?:120620|111322)/")),
    ("decisions.fct-cf.gc.ca", re.compile(r"^/icm/icm/en/(?:item/)?(?:120620|111322)/")),
    ("www.scc-csc.ca", re.compile(r"^/cso-dce/|22551")),
)

# Lexum's Norma bot check: a 403 (or, defensively, any page) carrying this.
LEXUM_HOSTS = ("decisions.scc-csc.ca", "decisions.fct-cf.gc.ca", "norma.lexum.com")
NORMA_CHALLENGE = re.compile(r"Lexum's Norma technology|captcha test", re.I)

TAG = re.compile(r"<[^>]+>")
BLOCK_END = re.compile(r"(?i)</p>|<br\s*/?>|</div>|</tr>|</h\d>|</li>|</td>")
META_ROW = re.compile(r'<td class="label">(.*?)</td>\s*<td class="metadata">(.*?)</tr>', re.S)
PARA = re.compile(r"<p\b([^>]*)>(.*?)</p>", re.S)
ROLE_SPAN = re.compile(r'<span class="SCCLsocPartyRole">(.*)', re.S)
ROLE = re.compile(r"^(?:Interveners?|Appellants?|Respondents?|Applicants?|Defendants?|"
                  r"Plaintiffs?|Mis en cause|Respondents?/Appellants? on cross-appeal|"
                  r"Appellants?/Respondents? on cross-appeal)\b", re.I)
SEPARATOR = re.compile(r"SCCLsoc(?:Versus|SubfileSeparator|OtherPartySeparator|Prefix)")
HEADNOTE_END = re.compile(r"^(?:Cases Cited|Statutes and Regulations Cited|Authors Cited|"
                          r"APPEALS? from|APPEAL and CROSS-APPEAL|MOTION|REFERENCE)\b")
STATUS = re.compile(r"^(.*?)\s*-\s*(?:New document|Document updated)")
FC_TITLE = re.compile(r"^(.*?)\s*-\s*(\d{4} (?:FC|CF) \d+)\s*-\s*(\d{4}-\d{2}-\d{2})\s*$", re.S)


def _lines(fragment):
    """Block-structured text: one line per paragraph, markup and entities gone."""
    text = htmlmod.unescape(TAG.sub(" ", BLOCK_END.sub("\n", fragment or "")))
    return [" ".join(l.split()) for l in text.split("\n") if l.split()]


def _clean(fragment):
    return " ".join(htmlmod.unescape(TAG.sub(" ", fragment or "")).split())


def _lexum(url):
    return any(h in url for h in LEXUM_HOSTS)


def allowed(url):
    m = re.match(r"https?://([^/]+)(/[^?#]*)?", url)
    host, path = (m.group(1), m.group(2) or "/") if m else ("", "/")
    return not any(h == host and pat.search(path) for h, pat in ROBOTS_DISALLOW)


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


# -- parsing ------------------------------------------------------------------

def parse_feed(data):
    """[{id, title, url, published, modified, note}] from a Lexum JSON Feed."""
    out = []
    for it in (data or {}).get("items") or []:
        if not it.get("id"):
            continue
        out.append({"id": str(it["id"]), "title": (it.get("title") or "").strip(),
                    "url": it.get("url"), "published": it.get("date_published"),
                    "modified": it.get("date_modified"),
                    "note": (it.get("content_text") or "").strip()})
    return out


def leave_status(note):
    """'Granted' from 'Granted - New document published on 2026-10-01'."""
    m = STATUS.match(note or "")
    return (m.group(1).strip() or None) if m else None


def parse_meta(page):
    """{label: value} from the item page's metadata table, plus 'title'.
    Subjects come back as a list (one per <br/>)."""
    out = {}
    start = page.find('<div class="metadata">')
    end = page.find("</table>", start)
    block = page[start:end] if start >= 0 else ""
    t = re.search(r'<h3 class="title">(.*?)</h3>', block, re.S)
    if t:
        out["title"] = _clean(t.group(1))
    for label, value in META_ROW.findall(block):
        label = _clean(label)
        out[label] = _lines(value) if label == "Subjects" else _clean(value)
    return out


def _content(page):
    i = page.find('class="documentcontent"')
    return page[page.find(">", i) + 1:] if i >= 0 else ""


def headnote(lines):
    """(text, matched_on): the lines from 'Indexed as' to 'Cases Cited'.

    Falls back to 'Present:' for the start; with no end marker the opening
    HEADNOTE_CAP characters are taken and matched_on says 'opening'."""
    start = next((i for i, l in enumerate(lines) if l.startswith("Indexed as")), None)
    if start is None:
        start = next((i for i, l in enumerate(lines) if l.startswith("Present:")), 0)
    end = next((i for i in range(start + 1, len(lines)) if HEADNOTE_END.match(lines[i])), None)
    if end is None:
        text = "\n".join(lines[start:])[:HEADNOTE_CAP]
        return text, "opening"
    return "\n".join(lines[start:end])[:HEADNOTE_CAP], "headnote"


def _split_names(lines):
    """Party lines -> names. A name ends at a line ending ',' or ' and'; a
    line ending otherwise was wrapped ("...Who are Supportive of" / "Legal
    Assisted Dying Society,") and joins the next."""
    names, buf = [], ""
    for line in lines:
        buf = (buf + " " + line).strip()
        if buf.endswith(","):
            names.append(buf[:-1].strip())
            buf = ""
        elif re.search(r"\s(?:and|et)$", buf):
            names.append(re.sub(r"\s(?:and|et)$", "", buf).strip())
            buf = ""
    if buf:
        names.append(buf)
    out = []
    for n in names:
        # Two names can share a line (Bedford: "Christian Legal Fellowship,
        # Catholic Civil Rights League,"). A comma splits only where the
        # left side is at least two words and the right starts a capitalised
        # name, so "Faith, Fealty & Creed Society" and "AWCEP Asian Women
        # for Equality Society, operating as ..." stay whole.
        parts = [n]
        while True:
            m = next((m for m in re.finditer(r",\s+(?=[A-Z0-9])", parts[-1])
                      if len(parts[-1][:m.start()].split()) >= 2), None)
            if not m:
                break
            parts[-1:] = [parts[-1][:m.start()], parts[-1][m.end():]]
        out += parts
    return [re.sub(r"^(?:the|and)\s+", "", n).strip(" ,;") for n in out if n.strip(" ,;")]


def interveners(content_html):
    """The interveners as a list of names; [] if the case had none; None if
    the style of cause names interveners and none could be read.

    Read from the LAST style of cause before 'Indexed as' -- the headnote's
    own, one party per <p class="SCCLsocParty">. The cover page above it
    packs several names a line, and its role sits in a plain paragraph."""
    stop = content_html.find("Indexed as")
    region = content_html[:stop] if stop > 0 else content_html[:60000]
    group, found = [], None
    for attrs, inner in PARA.findall(region):
        cls = re.search(r'class="([^"]+)"', attrs)
        cls = cls.group(1) if cls else ""
        if SEPARATOR.search(cls):
            group = []
            continue
        role_m = ROLE_SPAN.search(inner)
        name_part = inner[:role_m.start()] if role_m else inner
        text = _clean(name_part)
        if cls.startswith("SCCLsocParty") or cls.startswith("SCCLsocLastPartyInRole"):
            if text:
                group.append(text)
            if role_m:
                if re.match(r"Interveners?\b", _clean(role_m.group(1)), re.I):
                    found = list(group)
                group = []
            continue
        if text and ROLE.match(text):
            if re.match(r"Interveners?\b", text, re.I):
                found = list(group)
            group = []
    if found:
        return _split_names(found)
    lines = _lines(region)
    if any(re.match(r"Interveners?\b", l) for l in lines):
        # The list exists and the Word styles did not carry it: the plain
        # text between the last '- and -' and 'Interveners'.
        flat = " ".join(lines)
        m = list(re.finditer(r"Interveners?\b", flat))
        seg = flat[:m[-1].start()] if m else ""
        cut = max(seg.rfind("- and -"), seg.rfind("‑ and ‑"))
        if cut >= 0:
            seg = seg[cut + 7:]
            parts = [p.strip() for p in re.split(r",\s+|\s+and\s+", seg) if p.strip()]
            return parts or None
        return None
    return []


def parse_item(page):
    """One judgment page -> the fields stored, plus the text matched."""
    meta = parse_meta(page)
    content = _content(page)
    lines = _lines(content)
    text, matched_on = headnote(lines)
    judges = [j.strip() for j in (meta.get("Judges") or "").split(";") if j.strip()]
    return {
        "title": meta.get("title"),
        "date": meta.get("Date"),
        "citation": meta.get("Neutral citation"),
        "scr": meta.get("Report"),
        "docket": meta.get("Case number"),
        "judges": judges,
        "on_appeal_from": meta.get("On appeal from"),
        "subjects": meta.get("Subjects") or [],
        "interveners": interveners(content),
        "headnote": text,
        "matched_on": matched_on,
        "has_content": bool(lines),
    }


def parse_leave(page):
    meta = parse_meta(page)
    return {"title": meta.get("title"), "decided": meta.get("Date"),
            "docket": meta.get("Case number"), "status": meta.get("Status"),
            "on_appeal_from": meta.get("On appeal from")}


def parse_docket_summary(page):
    """The Registrar's keywords and case summary from a docket page, the
    boilerplate paragraph ("Case summaries are prepared by...") left out.
    '' when the page carries none."""
    i = page.find('id="summary-content"')
    if i < 0:
        return ""
    j = page.find('id="filed-documents-content"', i)
    block = page[i:j if j > i else len(page)]
    out = []
    parts = re.split(r"<h4[^>]*>(.*?)</h4>", block, flags=re.S)
    # parts: [before, heading1, body1, heading2, body2, ...]
    for k in range(1, len(parts) - 1, 2):
        heading = _clean(parts[k])
        if heading not in ("Keywords", "Summary"):
            continue
        body = re.sub(r'<p class="fw-500">.*?</p>', " ", parts[k + 1], flags=re.S)
        for line in _lines(body):
            if line not in ("None.", "None"):
                out.append(line)
    return "\n".join(out)


def parse_year_index(page):
    """(total, [{id, title, citation, scr, date, subjects}]) for one page."""
    total = re.search(r"<h2>\s*(\d+)(?:&nbsp;|\s)result", page)
    rows = []
    for li in re.findall(r'<li class="(?:odd|even)[^"]*">(.*?)</li>', page, re.S):
        m = re.search(r'href="[^"]*/item/(\d+)/index\.do">(.*?)</a>', li, re.S)
        if not m:
            continue
        span = lambda c: (lambda x: _clean(x.group(1)) if x else None)(
            re.search(r'<span class="{0}">(.*?)</span>'.format(c), li, re.S))
        subj = re.search(r'<div class="subject">(.*?)</div>', li, re.S)
        rows.append({"id": m.group(1), "title": _clean(m.group(2)),
                     "citation": span("citation"), "scr": span("report-citation"),
                     "date": span("publicationDate"),
                     "subjects": _lines(subj.group(1)) if subj else []})
    return (int(total.group(1)) if total else None), rows


def parse_fc_feed(xml_text):
    """[{id, title, citation, date, url}] from the Federal Court RSS."""
    out = []
    for item in ET.fromstring(xml_text).iter("item"):
        link = (item.findtext("link") or "").strip()
        m = re.search(r"/item/(\d+)/", link)
        if not m:
            continue
        raw = " ".join((item.findtext("title") or "").split())
        t = FC_TITLE.match(raw)
        out.append({"id": m.group(1), "title": t.group(1) if t else raw,
                    "citation": t.group(2) if t else None,
                    "date": t.group(3) if t else None,
                    "url": FC_ITEM.format(id=m.group(1)).replace("?iframe=true", "")})
    return out


# -- classification -----------------------------------------------------------

def _passages(tax, wl, text, title):
    matches = filt.match_passages(tax, wl, text or "", title=title or None)
    areas, terms, excerpt = filt.aggregate_passages(matches)
    tier = 1 if any(m.result.tier == 1 for m in matches) else 2 if matches else None
    return list(areas or []), list(terms or []), tier, excerpt, matches


def judgment_text(subjects, headnote_text):
    """What a judgment is matched on: its subjects, one a line, then the
    headnote. tools/ca_retag.py rebuilds the same string from the store."""
    return "\n".join(list(subjects or []) + [headnote_text or ""])


def classify_judgment(tax, wl, title, subjects, headnote_text):
    """(areas, terms, tier, excerpt). The case name is a title passage --
    it is party names and almost never matches, but when a party IS the
    subject ("Euthanasia Prevention Coalition v. ...") that is real."""
    areas, terms, tier, excerpt, _ = _passages(tax, wl, judgment_text(subjects, headnote_text), title)
    return areas, terms, tier, excerpt


def classify_leave(tax, wl, title, summary):
    areas, terms, tier, excerpt, _ = _passages(tax, wl, summary or "", title)
    return areas, terms, tier, excerpt


# -- storing ------------------------------------------------------------------

def held_judgments(conn):
    return {r[0] for r in conn.execute("SELECT judgment_id FROM ca_judgments")}


def store_judgment(conn, jid, court, j, areas, terms, tier, excerpt, url, today):
    conn.execute(
        "INSERT INTO ca_judgments (judgment_id, court, citation, scr, docket, date, title, "
        "subjects, judges, on_appeal_from, interveners, headnote, excerpt, matched_on, areas, "
        "matched_terms, tier, url, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(judgment_id) DO UPDATE SET citation=excluded.citation, scr=excluded.scr, "
        "docket=excluded.docket, date=excluded.date, title=excluded.title, "
        "subjects=excluded.subjects, judges=excluded.judges, "
        "on_appeal_from=excluded.on_appeal_from, interveners=excluded.interveners, "
        "headnote=excluded.headnote, excerpt=excluded.excerpt, matched_on=excluded.matched_on, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "url=excluded.url, last_seen=excluded.last_seen",
        (jid, court, j.get("citation"), j.get("scr"), j.get("docket"), j.get("date"),
         j.get("title"), json.dumps(j.get("subjects") or [], ensure_ascii=False),
         json.dumps(j.get("judges") or [], ensure_ascii=False), j.get("on_appeal_from"),
         None if j.get("interveners") is None else json.dumps(j["interveners"], ensure_ascii=False),
         j.get("headnote"), excerpt, j.get("matched_on"), json.dumps(sorted(areas)),
         json.dumps(terms, ensure_ascii=False), tier, url, today, today))


def seen_again(conn, jids, today):
    for jid in jids:
        conn.execute("UPDATE ca_judgments SET last_seen = ? WHERE judgment_id = ?", (today, jid))


def _say(log, kind, j, areas):
    n = j.get("interveners")
    log("  [{0}] {1} {2}: {3}{4}".format(
        kind, j.get("citation") or j.get("scr") or j.get("docket") or "?", areas, (j.get("title") or "")[:70],
        "" if not n else " ({0} interveners)".format(len(n))))


# -- the collector ------------------------------------------------------------

class Run:
    """Counts, gaps and the two caps (item pages, wall clock) for one run."""

    def __init__(self, conn, client, today, tax, wl, limit=None, budget=None, dry_run=False,
                 log=print):
        self.conn, self.client, self.today = conn, client, today
        self.tax, self.wl = tax, wl
        self.limit, self.budget, self.dry_run, self.log = limit, budget, dry_run, log
        self.pages = 0           # item/leave/docket pages fetched (the --limit unit)
        self.gaps = []
        self.read = self.ours = self.again = self.leaves = self.leaves_ours = 0
        self.stopped = False
        self.blocked = False     # Lexum's Norma served its CAPTCHA: the run stops
        self.landed = []         # (citation, title, areas, interveners) on our ground

    def gap(self, detail):
        if self.blocked:
            return               # one gap says it all; every page after it is unread, not lost
        self.gaps.append(detail)
        self.log("  [gap] {0}".format(detail))

    def room(self, what):
        """False once a cap is reached; says so once."""
        if self.stopped:
            return False
        if self.limit is not None and self.pages >= self.limit:
            self.log("  page cap ({0}) reached during {1}; the rest is read on the next run "
                     "-- disclosed, not silent".format(self.limit, what))
            self.stopped = True
        elif self.budget is not None and self.budget.exhausted():
            self.log(self.budget.disclose("pages ({0})".format(what), self.pages))
            self.stopped = True
        return not self.stopped

    def get(self, url, slug, json_=False, archive=False):
        if not allowed(url):
            raise FetchError(url, FEED, slug, 0, OSError("disallowed by robots.txt"))
        if self.blocked:
            raise FetchError(url, FEED, slug, 0, OSError("not asked: Norma challenge in force"))
        try:
            if json_:
                return self.client.get_json(url, FEED, slug, archive=archive)
            body = self.client.get_text(url, FEED, slug, archive=archive)
        except FetchError as exc:
            if getattr(exc.cause, "code", None) == 403 and _lexum(url):
                self._block(url)
            raise
        if _lexum(url) and NORMA_CHALLENGE.search(body[:20000]):
            self._block(url)
            raise FetchError(url, FEED, slug, 1, OSError("Norma challenge page"))
        return body

    def _block(self, url):
        """Lexum's Norma asks a client "accessing a large number of files" to
        prove it is a person (2 October 2026: a 403 CAPTCHA page after about
        200 pages at one a second). It is never answered or worked around:
        the run stops at once, says so in ONE gap, and the next run carries on
        from where this one stopped, since nothing unread was marked read."""
        self.gap("Lexum Norma challenge (403 CAPTCHA) after {0} page(s) at {1}; stopped, the "
                 "rest is read on a later run -- never answered, never evaded".format(
                     self.pages, url.split("?")[0]))
        self.blocked = self.stopped = True

    # judgments ---------------------------------------------------------------

    def read_judgment(self, jid, hint=None):
        """Fetch, parse, classify and store one SCC judgment. True if stored."""
        url = ITEM.format(id=jid)
        self.pages += 1
        try:
            page = self.get(url, "item-" + jid)
        except FetchError as exc:
            self.gap("judgment {0}: {1}".format(jid, str(exc)[:120]))
            return False
        j = parse_item(page)
        if not j["has_content"] or not j["title"]:
            self.gap("judgment {0}: the page carried no metadata or text (markup changed?)".format(jid))
            return False
        for k, v in (hint or {}).items():       # the index row fills what the page lacks
            if v and not j.get(k):
                j[k] = v
        areas, terms, tier, excerpt = classify_judgment(self.tax, self.wl, j["title"],
                                                        j["subjects"], j["headnote"])
        if j["interveners"] is None:
            self.log("  note: {0} names interveners the parser could not read".format(
                j.get("citation") or jid))
        store_judgment(self.conn, jid, "SCC", j, areas, terms, tier, excerpt,
                       url.replace("?iframe=true", ""), self.today)
        self.conn.commit()
        self.read += 1
        if on_our_ground(areas):
            self.ours += 1
            self.landed.append((j.get("citation"), j.get("title"), areas, j["interveners"]))
            _say(self.log, "scc", j, areas)
        return True

    def judgments_feed(self):
        try:
            items = parse_feed(self.get(JUDGMENTS_FEED, "scc-feed", json_=True, archive=True))
        except (FetchError, ValueError) as exc:
            self.gap("judgments feed: {0}".format(str(exc)[:120]))
            return
        held = held_judgments(self.conn)
        known = [i["id"] for i in items if i["id"] in held]
        new = [i for i in items if i["id"] not in held]
        self.log("  judgments feed: {0} item(s), {1} new, {2} already read (an updated "
                 "document re-listed is not read again)".format(len(items), len(new), len(known)))
        if self.dry_run:
            return
        seen_again(self.conn, known, self.today)
        self.again += len(known)
        for it in new:
            if not self.room("the judgments feed"):
                break
            self.read_judgment(it["id"])
        self.conn.commit()

    def backfill(self, since, until):
        """The year indexes, oldest year first; ids already held are skipped."""
        for year in range(since, until + 1):
            held = held_judgments(self.conn)
            page_no, pages = 1, None
            while pages is None or page_no <= pages:
                if self.stopped:
                    return
                try:
                    total, rows = parse_year_index(self.get(
                        YEAR_INDEX.format(year=year, page=page_no),
                        "index-{0}-{1}".format(year, page_no)))
                except FetchError as exc:
                    self.gap("{0} index page {1}: {2}".format(year, page_no, str(exc)[:100]))
                    break
                if pages is None:
                    if not total:
                        self.gap("{0} index: no result count (markup changed?)".format(year))
                        break
                    pages = int(math.ceil(total / float(PER_PAGE)))
                    have = self.conn.execute(
                        "SELECT COUNT(*) FROM ca_judgments WHERE court='SCC' AND date LIKE ?",
                        ("{0}-%".format(year),)).fetchone()[0]
                    self.log("  {0}: {1} judgment(s) in the index, {2} held".format(year, total, have))
                    if have >= total and all(r["id"] in held for r in rows):
                        break       # the year is complete; its other pages are not read
                if not rows:
                    self.gap("{0} index page {1}: no rows parsed".format(year, page_no))
                    break
                todo = [r for r in rows if r["id"] not in held]
                if self.dry_run:
                    self.log("    page {0}: {1} unread".format(page_no, len(todo)))
                for r in todo:
                    if self.dry_run or not self.room("the {0} backfill".format(year)):
                        break
                    self.read_judgment(r["id"], hint={k: r[k] for k in
                                                      ("title", "citation", "scr", "date", "subjects")})
                page_no += 1

    # leave ---------------------------------------------------------------------

    def leave_feed(self):
        try:
            items = parse_feed(self.get(LEAVE_FEED, "leave-feed", json_=True, archive=True))
        except (FetchError, ValueError) as exc:
            self.gap("leave feed: {0}".format(str(exc)[:120]))
            return
        held = {r[0] for r in self.conn.execute("SELECT lexum_id FROM ca_leave WHERE lexum_id IS NOT NULL")}
        new = [i for i in items if i["id"] not in held]
        granted = sum(1 for i in new if (leave_status(i["note"]) or "").startswith("Granted"))
        self.log("  leave feed: {0} item(s), {1} new ({2} granted)".format(len(items), len(new), granted))
        if self.dry_run:
            return
        for it in new:
            if not self.room("the leave feed"):
                break
            self.read_leave(it)
        self.conn.commit()

    def read_leave(self, it):
        url = LEAVE_ITEM.format(id=it["id"])
        self.pages += 1
        try:
            lv = parse_leave(self.get(url, "leave-" + it["id"]))
        except FetchError as exc:
            self.gap("leave {0}: {1}".format(it["id"], str(exc)[:120]))
            return
        if not lv["docket"]:
            self.gap("leave {0}: no case number on the page (markup changed?)".format(it["id"]))
            return
        status = lv["status"] or leave_status(it["note"])
        title = lv["title"] or re.sub(r"\s*-\s*\d{4}-\d{2}-\d{2}$", "", it["title"])
        summary = None
        docket_url = DOCKET.format(docket=lv["docket"])
        if (status or "").startswith("Granted"):
            self.pages += 1
            try:
                summary = parse_docket_summary(self.get(docket_url, "docket-" + lv["docket"])) or None
            except FetchError as exc:
                # Stored without its summary would look like a leave with
                # nothing on our ground; leave it unread instead.
                self.gap("docket {0}: {1}".format(lv["docket"], str(exc)[:120]))
                return
            if not summary:
                self.log("  note: docket {0} (granted) carries no case summary yet".format(lv["docket"]))
        if summary is None:
            # A second decision on a docket already held (a reconsideration)
            # keeps the summary it was classified on.
            prior = self.conn.execute("SELECT summary FROM ca_leave WHERE docket = ?",
                                      (lv["docket"],)).fetchone()
            summary = prior[0] if prior else None
        areas, terms, tier, excerpt = classify_leave(self.tax, self.wl, title, summary)
        self.conn.execute(
            "INSERT INTO ca_leave (docket, lexum_id, status, decided, title, on_appeal_from, "
            "summary, excerpt, areas, matched_terms, tier, url, first_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(docket) DO UPDATE SET "
            "lexum_id=excluded.lexum_id, status=excluded.status, decided=excluded.decided, "
            "title=excluded.title, on_appeal_from=excluded.on_appeal_from, "
            "summary=excluded.summary, excerpt=excluded.excerpt, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
            "url=excluded.url",
            (lv["docket"], it["id"], status, lv["decided"] or it["published"], title,
             lv["on_appeal_from"], summary, excerpt, json.dumps(sorted(areas)),
             json.dumps(terms, ensure_ascii=False), tier, docket_url, self.today))
        self.leaves += 1
        if on_our_ground(areas):
            self.leaves_ours += 1
            self.log("  [leave {0}] {1} {2}: {3}".format(status, lv["docket"], areas, title[:70]))

    # federal court ---------------------------------------------------------------

    def federal_court(self):
        try:
            items = parse_fc_feed(self.get(FC_FEED, "fc-feed", archive=True))
        except (FetchError, ET.ParseError) as exc:
            self.gap("Federal Court feed: {0}".format(str(exc)[:120]))
            return
        held = held_judgments(self.conn)
        imm = [i for i in items if FC_IMMIGRATION.search(i["title"])]
        todo = [i for i in items if not FC_IMMIGRATION.search(i["title"])
                and "fc-" + i["id"] not in held]
        self.log("  Federal Court feed: {0} item(s); {1} immigration (area 11, hidden) skipped "
                 "unread; {2} new to read".format(len(items), len(imm), len(todo)))
        if self.dry_run:
            return
        for it in todo:
            if not self.room("the Federal Court feed"):
                break
            self.pages += 1
            try:
                page = self.get(FC_ITEM.format(id=it["id"]), "fc-item-" + it["id"])
            except FetchError as exc:
                self.gap("FC {0}: {1}".format(it["id"], str(exc)[:120]))
                continue
            reasons = "\n".join(_lines(_content(page)))
            areas, terms, tier, excerpt, matches = _passages(self.tax, self.wl, reasons, it["title"])
            # No headnote: the full reasons, so two qualifying passages, as
            # the UK rule for a judgment's text (run_weekly.sweep_judgments).
            if len(matches) < 2:
                areas, terms, tier = [], [], None
            j = {"title": it["title"], "citation": it["citation"], "date": it["date"],
                 "matched_on": "reasons", "interveners": None}
            store_judgment(self.conn, "fc-" + it["id"], "FC", j, areas, terms, tier,
                           excerpt if areas else None, it["url"], self.today)
            self.conn.commit()
            self.read += 1
            if on_our_ground(areas):
                self.ours += 1
                self.landed.append((it["citation"], it["title"], areas, None))
                _say(self.log, "fc", j, areas)


def run(conn, client, today, backfill=False, since=BACKFILL_FROM, until=None, federal=False,
        limit=None, budget=None, dry_run=False, tax=None, wl=None, log=print):
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    r = Run(conn, client, today, tax, wl, limit=limit, budget=budget, dry_run=dry_run, log=log)
    if backfill:
        r.backfill(since, until or int(today[:4]))
    else:
        r.judgments_feed()
        r.leave_feed()
        if federal:
            r.federal_court()
    if r.gaps and not dry_run:
        db.record_gaps(conn, FEED, r.gaps, edition=today)
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--backfill", action="store_true",
                    help="read the year indexes instead of the feeds (hand-dispatched)")
    ap.add_argument("--since", type=int, default=BACKFILL_FROM, help="first year of a backfill")
    ap.add_argument("--until", type=int, help="last year of a backfill (default: this year)")
    ap.add_argument("--federal-court", action="store_true",
                    help="also read the Federal Court feed (low yield: mostly immigration)")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="item pages per run (default {0}: Lexum's Norma challenges a client "
                         "reading many pages)".format(DEFAULT_LIMIT))
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true", help="read the feeds/indexes, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=THROTTLE_S)
    today = datetime.date.today().isoformat()
    conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    r = run(conn, client, today, backfill=args.backfill, since=args.since, until=args.until,
            federal=args.federal_court, limit=args.limit,
            budget=drain.Budget(args.budget_seconds), dry_run=args.dry_run)
    if args.dry_run:
        print("ca-courts: dry run, nothing stored.")
        conn.close()
        return 0
    print("ca-courts: {0} judgment(s) read, {1} on our ground, {2} re-listed and not re-read; "
          "{3} leave decision(s) read, {4} on our ground; {5} page(s) fetched, {6} gap(s).".format(
              r.read, r.ours, r.again, r.leaves, r.leaves_ours, r.pages, len(r.gaps)))
    pending = conn.execute(
        "SELECT COUNT(*) FROM ca_judgments WHERE areas NOT IN ('[]','[11]') "
        "AND triage_score IS NULL").fetchone()[0]
    print("  {0} judgment(s) on our ground await the judge (tools/ca_triage.py). Context only: "
          "a judgment never places anyone.".format(pending))
    conn.close()
    return 1 if r.gaps else 0


if __name__ == "__main__":
    sys.exit(main())
