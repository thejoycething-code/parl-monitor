"""Saskatchewan Hansard speeches (tools/prov_speeches.py --prov sk).

THE SOURCE: the Legislative Meeting Archive the vote collector lists
(src/ingest/prov_sk, one calendar year at a time, each year on its own page
cap). Each day's "Debates" entry names the Hansard:
  * from the 30th Legislature, a Word-HTML file AND the PDF
    ("20251023DebatesHTML.htm", about 300 KB) -- the HTML is read;
  * before it, the PDF only ("29L3S/20231020Debates.pdf", about 700 KB):
    no HTML is listed, so none is requested (a URL is never built). The PDF
    text is clean in reading order; its paragraphs are separated by blank
    lines and every label ends ": —".
Both measured 2 October 2026. The prorogation day lists two sessions'
Debates ("30L1S/20251022Debates-AM.pdf" and "30L2S/20251022Debates.pdf"):
two records, keyed by session.

  HTML:  <h1>GOVERNMENT ORDERS</h1> <h1>THIRD READINGS</h1>       rubrics
         <h2>Bill No. 137 — The Education (...) Act, 2023/Loi ...</h2>
         <p><b>Hon. Mr. Cockrill</b>: — Thank you, Mr. Speaker. ...</p>
  PDF:   the same, with the headings in capitals or as "Bill No." blocks.

WHO SPOKE: surnames ("Ms. Beck", "Mr. Harrison (Meadow Lake)"), against the
member list on the second page of THAT DAY's Hansard PDF -- read through
prov_sk.roster_for_day, as the vote collector reads it on a division day,
when no term covers the day yet. The archive is date-driven, so this reads
a window across sessions as the vote collector does.
"""

from __future__ import annotations

import datetime
import html as _html
import re

from src import prov_names as pn, prov_speeches as sp
from src.ingest import prov_sk as base
from src.prov_fetch import pdf_text

PROV = "sk"
LANGUAGE = "en"
CURRENT_SESSION = base.CURRENT_SESSION
DATE_DRIVEN = True

_SESSION_PATH = re.compile(r"/(\d{2})L(\d)S/")
_PART = re.compile(r"Debates-?(AM|PM|EV)\b", re.I)


def english(heading):
    return re.split(r"\s*/\s*(?=Loi\b|Code\b|Projet\b)", heading or "")[0].strip()


def parse_html(html):
    return sp.word_html_turns(html, ("h1",), ("h2", "h3", "h4", "h5", "h6"), subject_text=english)


# -- the PDF (29th Legislature and before) ---------------------------------------

_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
# Running heads: "LEGISLATIVE ASSEMBLY OF SASKATCHEWAN 4351", "October 18, 2023
# Saskatchewan Hansard 4209", "4210 Saskatchewan Hansard October 18, 2023".
_FURNITURE = re.compile(
    r"^(?:=====PAGE|LEGISLATIVE ASSEMBLY OF SASKATCHEWAN\s+\d+|"
    r"(?:\d+\s+)?(?:" + _MONTH + r"\s+\d{1,2},\s+\d{4}\s+)?Saskatchewan Hansard(?:\s+\d+)?(?:\s+" + _MONTH +
    r"\s+\d{1,2},\s+\d{4})?|" + _MONTH + r"\s+\d{1,2},\s+\d{4}|\[\d{1,2}:\d{2}\]|\d{1,4})$")
_LABEL = re.compile(r"^(?P<l>[A-Z][^:]{1,90}?)\s*:\s*[—–]\s*(?P<r>.*)$", re.S)
_CAPS = re.compile(r"^[A-Z0-9 ,.'’()\-—–&/]+$")
_SPACED_STOP = re.compile(r"\b(Hon|Mr|Mrs|Ms|Dr)\s+\.")


def parse_pdf(text):
    lines = (text or "").splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip().startswith("[The Assembly met")), 0)
    paras, cur = [], []
    for raw in lines[start:]:
        line = raw.strip()
        if _FURNITURE.match(line):
            continue
        if not line:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(line)
    if cur:
        paras.append(" ".join(cur))
    blocks = []
    for p in paras:
        p = re.sub(r"\s+", " ", p).strip()
        m = _LABEL.match(p)
        prev = blocks[-1][0] if blocks else None
        if m and len(m.group("l").split()) <= 8:
            # The 27th Legislature's PDF text sometimes spaces an honorific's
            # full stop ("Hon. Mr . Duncan", 25 November 2015).
            label = _SPACED_STOP.sub(r"\1.", m.group("l").strip())
            blocks.append(("label", label, m.group("r").strip()))
        elif p.startswith("[") and p.endswith("]"):
            blocks.append(("proc", p))
        elif p.startswith("Bill No."):
            blocks.append(("subject", english(p), sp.bill_number(p)))
        elif _CAPS.match(p) and re.search(r"[A-Z]{3}", p):
            blocks.append(("rubric", p))
        elif prev in ("rubric", "subject") and len(p) <= 160 and not re.search(r"[.?!:;,”\"]$", p):
            # A heading follows a rubric (QUESTION PERIOD, then 'Parental
            # Engagement in Education') or another heading. Anywhere else a
            # short line is a speech's own (a quoted letter's signature).
            if prev == "subject" and blocks[-1][1] and not blocks[-1][1].startswith("Bill No."):
                blocks.append(("subject", blocks.pop()[1] + " " + p, None))
            else:
                blocks.append(("subject", english(p), sp.bill_number(p)))
        else:
            blocks.append(("para", p))
    return sp.turns_from_blocks(blocks)


# -- listing ------------------------------------------------------------------------

def list_debates(html):
    """[{date, legislature, session, part, pdf, html}] from one archive page:
    every Debates link of every day's card. Two layouts, both measured on 2
    October 2026: "<span>Debates (<a>PDF</a>, <a>HTML</a>)</span>" (2023 on)
    and a bare "<a href=...Debates.pdf>Debates</a>" (2015). The links are
    taken by their path ("/Debates/<nn>L<n>S/"), so either layout -- and a
    day carrying two sessions' Debates -- is read whole."""
    out = []
    marks = [(m.start(), m.group(1)) for m in base._CARD.finditer(html or "")]
    for idx, (pos, ymd) in enumerate(marks):
        body = html[pos:marks[idx + 1][0] if idx + 1 < len(marks) else len(html)]
        date = "{0}-{1}-{2}".format(ymd[:4], ymd[4:6], ymd[6:])
        by = {}
        for href in re.findall(r'href="([^"]+)"', body):
            href = _html.unescape(href)
            m = _SESSION_PATH.search(href)
            if "/Debates/" not in href or not m or not href.lower().endswith((".pdf", ".htm", ".html")):
                continue
            part = _PART.search(href)
            key = (int(m.group(1)), int(m.group(2)), part.group(1).lower() if part else None)
            slot = "pdf" if href.lower().endswith(".pdf") else "html"
            by.setdefault(key, {}).setdefault(slot, href)
        for (leg, sess, part), links in sorted(by.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")):
            out.append({"date": date, "legislature": leg, "session": sess, "part": part,
                        "pdf": links.get("pdf"), "html": links.get("html")})
    return out


def list_days(ctx, session=None):
    want = base.parse_session(session) if session and session != CURRENT_SESSION else None
    until = ctx.until or datetime.date.today().isoformat()
    since = ctx.since or (datetime.date.fromisoformat(until)
                          - datetime.timedelta(days=base.DEFAULT_WINDOW_DAYS)).isoformat()
    found = []
    for lo, hi in base.year_windows(since, until):
        url, n = base.ARCHIVE.format(lo, hi), 0
        while url and n < base.LISTING_PAGE_CAP:
            page = ctx.text(url, "archive-{0}-{1}-{2}".format(lo, hi, n))
            if page is None:
                break
            found.extend(list_debates(page))
            n += 1
            url = base.next_page(page)
        if url and n >= base.LISTING_PAGE_CAP:
            ctx.gap("sk archive {0}..{1}: still a next page after {2} listing pages; the rest of "
                    "that window was not listed".format(lo, hi, base.LISTING_PAGE_CAP))
    out, seen = [], set()
    for d in sorted(found, key=lambda d: (d["date"], d["legislature"], d["session"], d["part"] or "")):
        if not (since <= d["date"] <= until):
            continue
        if want and (d["legislature"], d["session"]) != want:
            continue
        key = "sk-{0}-{1}-{2}".format(d["legislature"], d["session"], d["date"]) + (
            "-" + d["part"] if d["part"] else "")
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(d, key=key, url=d["html"] or d["pdf"]))
    return out


def read_day(ctx, day):
    slug = "hansard-{0}".format(day["key"])
    raw = None
    if day.get("html"):
        html = ctx.text(day["html"], slug, encoding="cp1252", archive=True)
        if html is None:
            return None, ["the Debates HTML was not fetched"]
        turns = parse_html(html)
    else:
        raw = ctx.bytes(day["pdf"], slug, archive=True)
        if raw is None:
            return None, ["the Debates PDF was not fetched"]
        turns = parse_pdf(pdf_text(raw))
    problems = []
    rec = {"date": day["date"], "legislature": day["legislature"], "debates": day["pdf"]}
    if not base.roster_for_day(sp.Primed(ctx, day["pdf"], raw), rec):
        problems.append("no member list read for the day")
    return turns, problems


def resolver(ctx):
    return pn.Resolver.from_conn(ctx.conn, PROV)
