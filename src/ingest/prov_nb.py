"""Legislative Assembly of New Brunswick: roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov nb. Scope: docs/canada-provinces-scope.md
(New Brunswick: value 4, difficulty 3). robots.txt disallows nothing but
sets `crawl-delay: 10`: prov_fetch reads it and the client waits 10 seconds
between requests to legnb.ca (HttpClient.set_host_throttle), so a session
of ~50 journals plus its bill pages takes the best part of half an hour.
No WAF.

BILINGUAL. Every record exists in English and French ("e" and "f" file
suffixes; bill texts "-e.htm"). Only the English files are read: English is
the text matched against the taxonomy, and reading both would count every
division twice.

  * LISTING. /en/house-business/journals/<leg>/<sess> lists each sitting's
    Journal with its date, and the session's "Journals (Compiled)". File
    names are taken from it, never constructed: they carry the sitting
    number, YYMMDD and sometimes a revision suffix ("47230615e2.pdf"), and
    the hrefs use Windows backslashes.
  * ROSTER, DATED BY SESSION. The site publishes only the CURRENT members
    (/en/members/current, with party). For a past session the dated roster
    is the compiled Journal's own "MEMBERS OF THE LEGISLATIVE ASSEMBLY"
    page: constituency and member for that session, with footnotes for
    by-elections ("By-election April 24, 2023, vice Denis Landry resigned
    November 30, 2022"). A term runs from the session's first sitting (or
    the by-election) to its last sitting (or the resignation). The page
    prints NO PARTY, and nothing on the site dates one, so party_at_vote
    stays NULL for New Brunswick (as for BC): today's party joined to a 2023
    vote would misattribute every floor-crosser (Dominic Cardy left the PC
    caucus in October 2022). The compiled Journal's header names its session
    and is checked: the 60-3 listing links a file named for 2022-2023.
  * BILLS. /en/legislation/bills/<leg>/<sess> gives every bill with its
    stage dates ("2nd Reading Passed: 5/11/2023"); each bill page gives the
    type, sponsor and the bill-text documents, the English HTML preferred.
    Bills are classified on that TEXT, per passage (src/prov_classify.py).
  * DIVISIONS. "on the following recorded division: YEAS - 26", then three
    columns of "Hon. Mr. Holder", "Ms. Holt", "Mr. J. LeBlanc" (pypdf reads
    them row by row), then "NAYS - 20". The printed totals are the tally
    check.
  * VOICE. "the question being put that Bill 52 be now read a third time,
    it was resolved in the affirmative." with no division, and "The
    following Bills were read a third time: Bill 42, ...". Stored as
    kind='voice': "passed on voice, no member record".
  * CROSS-CHECK. Every second or third reading the bills listing dates to a
    day whose Journal was read must be found in that Journal, as a division
    or as a voice decision. A miss is a gap, said out loud.

Hansard (the bilingual "b" PDFs, two interleaved columns) is not read; one of
them, 20 November 2025, is served truncated. Any record that is truncated or
not a PDF is a gap with status 'unreadable', never an empty day.
"""

from __future__ import annotations

import datetime
import html as _html
import json
import re
from urllib.parse import quote, urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import (Unreadable, html_text, join_fragments, pdf_rows, pdf_text, sessions_sorted, slug,
                            split_columns, year_span)

PROV = "nb"
CURRENT_SESSION = "61-2"
BASE = "https://www.legnb.ca"
JOURNALS = BASE + "/en/house-business/journals/{0}/{1}"
BILLS = BASE + "/en/legislation/bills/{0}/{1}"
MEMBERS = BASE + "/en/members/current"

STAGE_CODE = {"First Reading": "1r", "Second Reading": "2r", "Third Reading": "3r"}


def parse_session(code):
    m = re.match(r"^(\d{2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("New Brunswick session must look like 60-2, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def _current_legislature():
    return parse_session(CURRENT_SESSION)[0]


def _date(text, fmts=("%B %d, %Y", "%m/%d/%Y")):
    t = re.sub(r"\s+", " ", (text or "").strip())
    for f in fmts:
        try:
            return datetime.datetime.strptime(t, f).date().isoformat()
        except ValueError:
            continue
    return None


def _url(href):
    """A listing href as a URL: backslashes turned, spaces quoted, nothing
    else touched."""
    path = _html.unescape(href).replace("\\", "/")
    return urljoin(BASE, quote(path, safe="/:%?=&#"))


# -- the journals listing ---------------------------------------------------

_LINK = re.compile(r'<a[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', re.S | re.I)
_DAILY = re.compile(r"/(\d{1,3})(\d{6})e(\d*)\.pdf$", re.I)


def list_records(html):
    """{'daily': [{date, url, sitting, revision}], 'compiled': url|None}
    from one session's journals listing. English files only; where a date
    is listed twice the highest revision is kept."""
    daily, compiled = {}, None
    section = (html or "")
    start = section.find('class="file-list"')
    if start >= 0:
        section = section[start:]
    for href, inner in _LINK.findall(section):
        label = html_text(inner)
        url = _url(href)
        if label.lower().startswith("journals (compiled)"):
            compiled = url
            continue
        m = _DAILY.search(url)
        if not m:
            continue
        date = _date(label)
        if not date:
            ymd = m.group(2)
            date = "20{0}-{1}-{2}".format(ymd[:2], ymd[2:4], ymd[4:])
        rev = int(m.group(3) or 1)
        have = daily.get(date)
        if have is None or rev > have["revision"]:
            daily[date] = {"date": date, "url": url, "sitting": int(m.group(1)), "revision": rev}
    return {"daily": sorted(daily.values(), key=lambda r: r["date"]), "compiled": compiled}


# The journals page's own session selector: one block per legislature
# ('id="leg_60"'), each session a link ("journals/57/1" ... "(2010-2011)")
# except the page's own, printed as <span class="selected">.
_SEL_TOKEN = re.compile(
    r'id="leg_(?P<leg>\d+)"'
    r'|journals/(?P<lleg>\d+)/(?P<lsess>\d)"\s*>\s*<span>[^(<]*(?:<sup>[^<]*</sup>)?[^(<]*\((?P<lyears>[^)]*)\)'
    r'|class="selected">\s*(?P<ssess>\d)\s*(?:<sup>[^<]*</sup>)?[^(<]*\((?P<syears>[^)]*)\)')
_SPAN = re.compile(r"^\s*(\d{4})\s*(-)?\s*(\d{4})?\s*$")


def _years(code, text):
    """'2010-2011', '2018' (one year) or '2025-' (still open)."""
    m = _SPAN.match(text or "")
    if not m:
        return {"code": code, "start": None, "end": None}
    return year_span(code, m.group(1), m.group(3), open_ended=bool(m.group(2)) and not m.group(3))


def parse_sessions(html):
    """Every session in the journals page's selector, back to the 53rd
    Legislature (1995), oldest first."""
    out, leg = [], None
    for m in _SEL_TOKEN.finditer(html or ""):
        if m.group("leg"):
            leg = int(m.group("leg"))
        elif m.group("lleg"):
            out.append(_years("{0}-{1}".format(int(m.group("lleg")), int(m.group("lsess"))), m.group("lyears")))
        elif m.group("ssess") and leg:
            out.append(_years("{0}-{1}".format(leg, int(m.group("ssess"))), m.group("syears")))
    return sessions_sorted(out)


def list_sessions(ctx):
    legislature, session = parse_session(CURRENT_SESSION)
    url = JOURNALS.format(legislature, session)
    html = ctx.text(url, "journals-sessions-{0}-{1}".format(legislature, session))
    out = parse_sessions(html)
    if html and not out:
        ctx.gap("nb: no session selector parsed from {0}".format(url))
    return out


# -- rosters ----------------------------------------------------------------

_CARD = re.compile(
    r'<div class="member-card[^"]*"[^>]*>.*?<li class="member-card-description-name">\s*'
    r'(?:<a href="([^"]*)">)?\s*<h3>(.*?)</h3>.*?'
    r'<li class="member-card-description-party">(.*?)</li>.*?'
    r'<li class="member-card-description-riding">(.*?)</li>', re.S)


def clean_given(given):
    """'Jean-Claude (JC)' -> 'Jean-Claude'; 'William (Bill)' -> 'William'."""
    return re.sub(r"\s+", " ", re.sub(r"\([^()]*\)", " ", given or "")).strip()


def member_key(given, surname):
    """slug of the first given name that is not an initial, plus the surname:
    'K. Dorothy Shephard' -> 'dorothy-shephard', 'Mary E. Wilson' and
    'Wilson, Mary' -> 'mary-wilson', so the current page and a compiled
    roster agree on one person."""
    toks = [t for t in re.split(r"\s+", clean_given(given)) if t]
    first = next((t for t in toks if not pn._INITIALS.match(t)), toks[0] if toks else "")
    return slug(first + " " + surname)


def parse_current_members(html):
    """[{key, surname, given, name, party, riding, href}] from /en/members/current."""
    out = []
    for href, name, party, riding in _CARD.findall(html or ""):
        name = html_text(name)
        surname, _, given = name.partition(",")
        surname, given = surname.strip(), clean_given(given)
        out.append({"key": member_key(given, surname), "surname": surname, "given": given,
                    "name": (given + " " + surname).strip(), "party": html_text(party) or None,
                    "riding": html_text(riding) or None, "href": urljoin(BASE, href) if href else None})
    return out


_ORD_UNITS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
              "seventh": 7, "eighth": 8, "ninth": 9}
_ORD_TENS = {"fiftieth": 50, "sixtieth": 60, "seventieth": 70, "fortieth": 40}
_TENS = {"fifty": 50, "sixty": 60, "seventy": 70, "forty": 40}


def ordinal_value(word):
    """'Sixtieth' -> 60, 'Sixty-First' -> 61, 'Second' -> 2."""
    w = (word or "").lower().replace("–", "-").strip()
    if w in _ORD_UNITS:
        return _ORD_UNITS[w]
    if w in _ORD_TENS:
        return _ORD_TENS[w]
    head, _, tail = w.partition("-")
    if head in _TENS and tail in _ORD_UNITS:
        return _TENS[head] + _ORD_UNITS[tail]
    return None


_SESSION_HEAD = re.compile(r"\b([A-Za-z]+)\s+Session\s+of\s+the\s+([A-Za-z\-–]+)\s+Legislative\s+Assembly", re.I)
_FOOTNOTE = re.compile(
    r"^(\*+)\s*By-election\s+(\w+\s+\d{1,2},\s*\d{4}),\s*vice\s+(.+?),?\s+"
    r"(resigned|deceased|died|appointed[^,]*?)\s*(?:on\s+)?(\w+\s+\d{1,2},\s*\d{4})\.?\s*$", re.I)


def roster_rows(raw):
    """The rows of the compiled Journal's members page, or [] when there is
    none in its first five pages."""
    for page in pdf_rows(raw, pages=range(5)):
        if any("MEMBERS OF THE LEGISLATIVE ASSEMBLY" in join_fragments(fr) for _, fr in page):
            return [[list(f) for f in fr] for _, fr in page]
    return []


def parse_compiled_roster(rows):
    """{'session': (leg, sess)|None, 'members': [...], 'notes': [...], 'problems': [...]}

    rows: one page as [[(x0, x1, text), ...], ...] lines (roster_rows)."""
    out = {"session": None, "members": [], "notes": [], "problems": []}
    edges = None
    for frags in rows:
        frags = [tuple(f) for f in frags]
        line = join_fragments(frags)
        if out["session"] is None:
            m = _SESSION_HEAD.search(line)
            if m:
                sess, leg = ordinal_value(m.group(1)), ordinal_value(m.group(2))
                if sess and leg:
                    out["session"] = (leg, sess)
        if edges is None:
            heads = [f for f in frags if f[2].strip() in ("Constituency", "Member", "Residence")]
            if len(heads) == 3:
                edges = [heads[0][0], heads[1][0], heads[2][0]]
            continue
        if line.startswith("OFFICERS OF THE ASSEMBLY"):
            edges = False
            continue
        if edges is False:
            if line.startswith("*"):
                fn = _FOOTNOTE.match(line)
                if fn:
                    out["notes"].append({"mark": fn.group(1), "elected": _date(fn.group(2)),
                                         "vice": fn.group(3).strip(), "why": fn.group(4).lower(),
                                         "left": _date(fn.group(5))})
                else:
                    out["problems"].append("footnote not understood: {0!r}".format(line))
            continue
        riding, member, _residence = split_columns(frags, edges)
        if not riding or not member:
            continue
        mark = re.search(r"(\*+)\s*$", riding)
        riding = re.sub(r"\s*\*+\s*$", "", riding)
        riding = re.sub(r"\s*-\s*", "-", riding)
        member = re.sub(r"\s*-\s*", "-", member)
        member = re.sub(r",?\s*(?:K\.C\.|Q\.C\.)\s*$", "", member).strip()
        member = re.sub(r"^(?:Hon\.|The Honourable)\s+", "", member).strip()
        given, surname = _split_name(member)
        out["members"].append({"riding": riding, "given": given, "surname": surname,
                               "name": clean_given(given) + " " + surname,
                               "key": member_key(given, surname),
                               "mark": mark.group(1) if mark else None})
    if not out["members"]:
        out["problems"].append("no members read from the compiled Journal's members page")
    return out


def _split_name(full):
    toks = clean_given(full).split()
    if len(toks) < 2:
        return "", full.strip()
    return " ".join(toks[:-1]), toks[-1]


def terms_from_compiled(parsed, legislature, first, last):
    """[(member dict, term dict)] for one session: first/last are its first
    and last sitting dates (last None while the session runs)."""
    notes = {n["mark"]: n for n in parsed["notes"]}
    out = []
    for m in parsed["members"]:
        start = first
        note = notes.get(m["mark"]) if m["mark"] else None
        if note and note["elected"] and (not first or note["elected"] > first):
            start = note["elected"]
        out.append((m, {"legislature": legislature, "party": None, "riding": m["riding"],
                        "start": start, "end": last, "party_dated": 0}))
        if note and note["vice"] and note["left"] and (not first or note["left"] >= first):
            given, surname = _split_name(note["vice"])
            out.append(({"given": given, "surname": surname, "name": note["vice"],
                         "key": member_key(given, surname), "riding": m["riding"]},
                        {"legislature": legislature, "party": None, "riding": m["riding"],
                         "start": first, "end": note["left"], "party_dated": 0}))
    return out


def fetch_roster(ctx, legislature, session, listing):
    """The dated roster for one session. Returns the number of members."""
    daily = listing["daily"]
    first = daily[0]["date"] if daily else None
    last = daily[-1]["date"] if daily and (legislature, session) != parse_session(CURRENT_SESSION) else None
    if listing["compiled"]:
        have = ctx.conn.execute(
            "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND legislature=? AND source=?",
            (PROV, legislature, "journal-{0}-{1}".format(legislature, session))).fetchone()[0]
        if have and not ctx.refresh:
            return have
        raw = ctx.bytes(listing["compiled"], "compiled-{0}-{1}".format(legislature, session))
        if raw:
            try:
                parsed = parse_compiled_roster(roster_rows(raw))
            except Unreadable as exc:
                ctx.gap("nb {0}-{1}: compiled Journal {2}: {3}".format(legislature, session, listing["compiled"], exc))
                parsed = None
            if parsed:
                for p in parsed["problems"]:
                    ctx.gap("nb {0}-{1}: compiled Journal: {2}".format(legislature, session, p))
                if parsed["session"] != (legislature, session):
                    ctx.gap("nb {0}-{1}: the compiled Journal {2} is for session {3}, not this one; "
                            "its members page is not used".format(legislature, session,
                                                                  listing["compiled"], parsed["session"]))
                elif parsed["members"]:
                    return _store_compiled(ctx, legislature, session, parsed, first, last)
    if legislature == _current_legislature():
        return fetch_current(ctx, legislature)
    ctx.gap("nb {0}-{1}: no roster for the session (no usable compiled Journal, and the site lists "
            "only current members); its divisions cannot be resolved".format(legislature, session))
    return 0


def _store_compiled(ctx, legislature, session, parsed, first, last):
    source = "journal-{0}-{1}".format(legislature, session)
    rows = terms_from_compiled(parsed, legislature, first, last)
    if ctx.dry_run:
        return len(rows)
    by_key = {}
    for m, t in rows:
        by_key.setdefault(m["key"], (m, []))[1].append(t)
    for key, (m, terms) in by_key.items():
        ps.upsert_member(ctx.conn, PROV, key, name=m["name"], surname=m["surname"],
                         given=clean_given(m["given"]))
        ps.replace_terms(ctx.conn, PROV, key, terms, source)
    ctx.conn.commit()
    ctx.log("  nb roster {0}-{1}: {2} member(s) from the compiled Journal".format(
        legislature, session, len(by_key)))
    return len(by_key)


def fetch_current(ctx, legislature):
    html = ctx.text(MEMBERS, "members-current")
    rows = parse_current_members(html) if html else []
    if html and not rows:
        ctx.gap("nb: no members parsed from {0}".format(MEMBERS))
    if ctx.dry_run or not rows:
        return len(rows)
    ctx.conn.execute("UPDATE prov_members SET sitting=0 WHERE prov=?", (PROV,))
    for r in rows:
        ps.upsert_member(ctx.conn, PROV, r["key"], name=r["name"], surname=r["surname"],
                         given=r["given"], riding=r["riding"], party=r["party"], sitting=1)
        # The page dates nothing: the party is today's, so party_dated=0 and
        # it is never written as party_at_vote.
        ps.replace_terms(ctx.conn, PROV, r["key"], [{
            "legislature": legislature, "party": r["party"], "riding": r["riding"],
            "start": None, "end": None, "party_dated": 0}], "roster")
    ctx.conn.commit()
    ctx.log("  nb roster: {0} current member(s) (legislature {1}; party undated)".format(
        len(rows), legislature))
    return len(rows)


# -- bills ------------------------------------------------------------------

_BILL_ITEM = re.compile(r'<li class="bill-item">(.*?)</li>\s*(?=<li class="bill-item">|</ul>)', re.S)
_STEP = re.compile(r'<div class="step[^"]*">\s*<span>(.*?)</span>\s*<span>(.*?)</span', re.S)
_STAGE_NAME = {"1st reading": "First Reading", "2nd reading": "Second Reading",
               "3rd reading": "Third Reading", "committee": "Committee", "royal assent": "Royal Assent"}


def parse_bill_list(html):
    """[{number, title, href, amended, stages: [{stage, status, date}]}]"""
    out = []
    for item in _BILL_ITEM.findall(html or ""):
        num = re.search(r'<div class="bill-item-number">\s*([^<]+?)\s*</div>', item)
        link = re.search(r'<div class="bill-item-title">\s*<a href="([^"]+)">(.*?)</a>', item, re.S)
        if not num or not link:
            continue
        stages = []
        for name, status in _STEP.findall(item):
            stage = _STAGE_NAME.get(html_text(name).lower())
            st = html_text(status)
            word, _, when = st.partition(":")
            if stage:
                stages.append({"stage": stage, "status": word.strip() or None,
                               "date": _date(when) if when.strip() else None})
        out.append({"number": num.group(1).strip(), "title": html_text(link.group(2)),
                    "href": urljoin(BASE, _html.unescape(link.group(1))),
                    "amended": "bill-amendment-count" in item, "stages": stages})
    return out


_DOC = re.compile(r'<a class="bill-document"[^>]*href="([^"]+)"[^>]*>\s*<span>(.*?)</span>', re.S)


def parse_bill_page(html):
    """{bill_type, sponsor, sponsor_party, docs: [(label, url)], text_url}"""
    def prop(label):
        m = re.search(r'<span class="property-label">{0}</span>(.*?)</div>'.format(label), html or "", re.S)
        return html_text(m.group(1)) if m else None
    spons = re.search(r'<span class="property-label">Sponsored by</span>(.*?)</section>', html or "", re.S)
    sponsor = party = None
    if spons:
        n = re.search(r"<h3>(.*?)</h3>", spons.group(1), re.S)
        p = re.search(r'member-card-description-party">(.*?)</li>', spons.group(1), re.S)
        sponsor = html_text(n.group(1)) if n else None
        party = html_text(p.group(1)) if p else None
    docs = [(html_text(label), _url(href)) for href, label in _DOC.findall(html or "")]
    reading = [d for d in docs if "reading" in d[0].lower()]
    # The latest reading's text, English HTML first and its PDF as the
    # fallback: Bill-57-e.htm (60-2) is served as an empty document.
    texts = [u for l, u in reversed(reading) if u.lower().endswith((".htm", ".html"))][:1] + \
        [u for l, u in reversed(reading) if u.lower().endswith(".pdf")][:1]
    return {"bill_type": prop("Bill Type"), "sponsor": sponsor, "sponsor_party": party,
            "docs": docs, "texts": texts, "text_url": texts[0] if texts else None}


def bill_text(ctx, url, slug_):
    """English text of one bill document, or None. An empty document is
    reported back as None so the caller can try the next one."""
    if url.lower().endswith(".pdf"):
        raw = ctx.bytes(url, slug_)
        if raw is None:
            return None
        try:
            return pdf_text(raw).strip() or None
        except Unreadable as exc:
            ctx.gap("nb bill text {0}: {1}".format(url, exc))
            return None
    raw = ctx.text(url, slug_, encoding="cp1252")
    if raw is None:
        return None
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    # paragraphs and headings to line breaks, so passages stay passages
    body = re.sub(r"(?i)</(p|h\d|div|tr|li)>|<br[^>]*>", "\n\n", body)
    return "\n".join(html_text(l) for l in body.split("\n\n") if html_text(l)) or None


def _stage_dates_in_window(ctx, stages):
    return any(s.get("date") and ctx.in_window(s["date"]) for s in stages)


def fetch_bills(ctx, legislature, session, tax, wl):
    html = ctx.text(BILLS.format(legislature, session), "bills-{0}-{1}".format(legislature, session))
    items = parse_bill_list(html) if html else []
    if html and not items:
        ctx.gap("nb bills {0}-{1}: no bills parsed from the listing".format(legislature, session))
    if ctx.dry_run:
        return {"bills": len(items)}
    pages = texts = 0
    windowed = bool(ctx.since or ctx.until)
    out_of_time = False
    for it in items:
        key = ps.bill_key(PROV, legislature, session, it["number"])
        latest = [s for s in it["stages"] if s["date"]]
        record = {"bill_key": key, "prov": PROV, "legislature": legislature, "session": session,
                  "number": it["number"], "title_en": it["title"], "stages": it["stages"],
                  "page_url": it["href"], "latest_stage": latest[-1]["stage"] if latest else None,
                  "royal_assent": next((s["date"] for s in it["stages"]
                                        if s["stage"] == "Royal Assent" and s["date"]), None)}
        have = ctx.conn.execute("SELECT text_read FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
        wanted = (not windowed or _stage_dates_in_window(ctx, it["stages"])
                  or pc.watched_bill(PROV, key) is not None)
        if not out_of_time and ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("bill pages", pages))
            out_of_time = True
        if (have and have[0] and not ctx.refresh) or not wanted or out_of_time:
            # Listed only: stages kept fresh, a text classification kept.
            if have and have[0]:
                ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
            else:
                res = pc.classify(tax, wl, PROV, title=it["title"], bill_key=key)
                ps.store_bill(ctx.conn, dict(record, text_read=0, areas=res.areas,
                                             matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
            continue
        page_html = ctx.text(it["href"], "bill-{0}-{1}-{2}".format(legislature, session, it["number"]))
        page = parse_bill_page(page_html) if page_html else {"docs": [], "text_url": None}
        pages += 1 if page_html else 0
        body = None
        text_url = None
        for k, url in enumerate(page.get("texts") or []):
            body = bill_text(ctx, url, "billtext-{0}-{1}-{2}-{3}".format(
                legislature, session, it["number"], k))
            if body:
                text_url = url
                texts += 1
                break
        if page_html and not page.get("texts"):
            ctx.gap("{0}: the bill page lists no bill-text document".format(key))
        elif page_html and not body:
            ctx.gap("{0}: no bill-text document gave any text ({1}); classified on its title".format(
                key, ", ".join(page["texts"])))
        res = pc.classify(tax, wl, PROV, title=it["title"], texts=[body] if body else [], bill_key=key)
        ps.store_bill(ctx.conn, dict(
            record, sponsor=page.get("sponsor"), bill_type=page.get("bill_type"),
            is_government=1 if (page.get("bill_type") or "").startswith("Government") else
            (0 if page.get("bill_type") else None),
            text_url=text_url or page.get("text_url"), text_read=1 if body else 0, areas=res.areas,
            matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
    ctx.conn.commit()
    ctx.log("  nb bills {0}-{1}: {2} listed, {3} page(s) read, {4} text(s) read".format(
        legislature, session, len(items), pages, texts))
    return {"bills": len(items), "bill_pages": pages, "bill_texts": texts}


# -- the Journal --------------------------------------------------------------

HEADER = re.compile(r"^\s*(YEAS|NAYS)\s*[-–—]+\s*(\d+|Nil)\s*$", re.I)
_FURNITURE = re.compile(
    r"^\s*(?:=====PAGE|\d+\s+[\d\-–]+\s+(?:Elizabeth|Charles)\s+(?:II|III)\b.*"
    r"|(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2}\s+Journal of Assembly\s+\d+)\s*$")
_LABEL = re.compile(
    r"(?:Hon\.\s*)?(?:Mr|Mrs|Ms|Miss|Dr|Mme)\.\s+(?:[A-Z]\.\s*)*[A-ZÀ-Þ][\w’'\-]*"
    r"(?:\s+(?!(?:Hon|Mr|Mrs|Ms|Miss|Dr|Mme)\.)[A-ZÀ-Þ][\w’'\-]*)*")


def normalise(line):
    """Undo pypdf's stray spaces: 'M s.' -> 'Ms.', 'sub -amendment' ->
    'sub-amendment', runs of spaces -> one."""
    s = (line or "").replace("\xa0", " ")
    s = re.sub(r"\bM\s+(s|rs|r)\.", r"M\1.", s)
    s = re.sub(r"(\w)\s+-(\w)", r"\1-\2", s)
    s = re.sub(r"\bHon\.\s+Mr\s*,", "Hon. Mr.", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def is_furniture(line):
    return not (line or "").strip() or bool(_FURNITURE.match(line))


def labels_in_line(line):
    """The member labels on one name-list line, or None if anything else is on it."""
    s = normalise(line)
    if not s:
        return None
    out, pos = [], 0
    for m in _LABEL.finditer(s):
        if s[pos:m.start()].strip():
            return None
        out.append(m.group(0).strip())
        pos = m.end()
    if s[pos:].strip():
        return None
    return out or None


_RESULT = re.compile(r"([^.;:]*?)\s+on the following\s+recorded\s+division", re.I)
_RESULT_HEAD = re.compile(
    r"((?:it|the (?:amendment|sub\s*-?\s*amendment|motion)|Motion \d+(?: as amended)?|Bill \d+)"
    r"\s+was\s+.+)$", re.I)
_READ_Q = re.compile(r"question being put that Bill (\d+) be now read a (first|second|third) time", re.I)
_READ_DEBATE = re.compile(r"the motion that Bill (\d+),[^.]*?be now read a (second|third) time", re.I)
_ORDER_READ = re.compile(r"The Order being read for (second|third) reading of Bill (\d+)", re.I)
_MOTION = re.compile(r"\bMotion (\d+)\b")
_ITEM_START = re.compile(
    r"(?:Pursuant to Notice of Motion \d+|Debate resumed|The Order being read|"
    r"(?:Mr\.|Madam) (?:Deputy )?Speaker put the question on Motion|The House resumed the adjourned debate)")
_VOICE_Q = re.compile(
    r"question being put that Bill (\d+) be now read a (first|second|third) time,\s*"
    r"it was (resolved in the affirmative|resolved in the negative|defeated|carried|negatived)\s*\.", re.I)
_VOICE_LIST = re.compile(r"^The following Bills? (?:was|were) (?:introduced and )?read a (first|second|third) time\s*:?\s*$",
                         re.I)


def parse_journal(text):
    """(divisions, voices) from one day's English Journal text, names unresolved.

    divisions: [{seq, yeas, nays, yea_labels, nay_labels, question, item,
                 result, vote_on, stage, bill_number, motion, problem}]
    voices:    [{bill_number, stage, result}]"""
    lines = [normalise(l) for l in (text or "").splitlines()]
    divisions, prose, context = [], [], []
    i, n = 0, len(lines)

    def take(i):
        got = []
        while i < n:
            l = lines[i]
            if is_furniture(l):
                i += 1
                continue
            if HEADER.match(l):
                break
            labs = labels_in_line(l)
            if labs is None:
                break
            got.extend(labs)
            i += 1
        return got, i

    while i < n:
        line = lines[i]
        h = HEADER.match(line)
        if h and h.group(1).upper() == "YEAS":
            yeas = 0 if h.group(2).lower() == "nil" else int(h.group(2))
            yea_labels, i = take(i + 1)
            while i < n and is_furniture(lines[i]):
                i += 1
            h2 = HEADER.match(lines[i]) if i < n else None
            nays, nay_labels, problem, note = None, [], None, None
            if h2 and h2.group(1).upper() == "NAYS":
                nays = 0 if h2.group(2).lower() == "nil" else int(h2.group(2))
                nay_labels, i = take(i + 1)
            elif i < n and lines[i].strip():
                # A unanimous recorded division prints YEAS only (Motion 36
                # as amended, 8 June 2023: YEAS - 44 and then the next
                # item). No NAYS total is printed, so none is checked; the
                # YEAS still must account for every name.
                note = "no NAYS list printed (unanimous)"
            else:
                problem = "no NAYS list after 'YEAS - {0}'".format(yeas)
            divisions.append(_division(context, len(divisions) + 1, yeas, nays,
                                       yea_labels, nay_labels, problem))
            divisions[-1]["note"] = note
            prose.append("")
            context = []
            continue
        if not is_furniture(line):
            context.append(line)
            prose.append(line)
        elif not line.strip():
            prose.append("")
            context.append("")
        i += 1
    return divisions, _voices(prose)


def _division(context, seq, yeas, nays, yea_labels, nay_labels, problem):
    text = re.sub(r"\s+", " ", " ".join(context)).strip()
    starts = list(_ITEM_START.finditer(text))
    item = text[starts[-1].start():] if starts else text
    tail = text[-700:]
    res = _RESULT.findall(tail)
    result = None
    if res:
        head = _RESULT_HEAD.search(res[-1])
        result = (head.group(1) if head else res[-1]).strip(" ,")
    low = tail.lower()
    vote_on = ("subamendment" if re.search(r"sub\s*-?\s*amendment", low[-400:]) else
               "amendment" if re.search(r"(?:on the (?:proposed )?amendment|the amendment was|amendment,? it was)", low[-400:])
               else "motion")
    bill = stage = motion = None
    # The bill and stage come from the ITEM the division closes, the last
    # mention there winning: on 16 June 2023 the context of Bill 37's
    # third-reading division also held Bill 32's third reading, carried on
    # voice just before it.
    reads = [(m.start(), m.group(1), m.group(2)) for m in _READ_Q.finditer(item)]
    reads += [(m.start(), m.group(2), m.group(1)) for m in _ORDER_READ.finditer(item)]
    reads += [(m.start(), m.group(1), m.group(2)) for m in _READ_DEBATE.finditer(item)]
    if reads:
        _, bill, word = max(reads)
        stage = word.title() + " Reading"
    else:
        ms = _MOTION.findall(tail) or _MOTION.findall(item)
        motion = ms[-1] if ms else None
        stage = "Motion"
    return {"seq": seq, "yeas": yeas, "nays": nays, "yea_labels": yea_labels,
            "nay_labels": nay_labels, "question": item[-1500:] or None, "item": item,
            "result": result, "vote_on": vote_on, "stage": stage, "bill_number": bill,
            "motion": motion, "problem": problem}


def _voices(prose):
    paras, buf = [], []
    for l in prose:
        if l.strip():
            buf.append(l)
        elif buf:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    out, seen = [], set()

    def add(number, stage, result):
        k = (number, stage)
        if k not in seen:
            seen.add(k)
            out.append({"bill_number": number, "stage": stage, "result": result})

    text = " ".join(paras)
    for m in _VOICE_Q.finditer(text):
        add(m.group(1), m.group(2).title() + " Reading", re.sub(r"\s+", " ", m.group(0)))
    for k, p in enumerate(paras):
        m = _VOICE_LIST.match(p.strip())
        if not m:
            continue
        stage = m.group(1).title() + " Reading"
        for q in paras[k + 1:]:
            if not re.match(r"^\s*(?:By [^,]+,\s*)?Bill \d+,", q):
                break
            for num in re.findall(r"\bBill (\d+),", q):
                add(num, stage, "read a {0} time (listed; no recorded division)".format(m.group(1).lower()))
    return out


def resolve_division(raw, resolver, date, legislature):
    votes = []
    for position, labels in (("Yea", raw["yea_labels"]), ("Nay", raw["nay_labels"])):
        for k, label in enumerate(labels, 1):
            key, how = resolver.resolve(label, date, legislature)
            votes.append({"position": position, "ordinal": k, "raw_label": label, "member_key": key,
                          "how": how,
                          "party_at_vote": resolver.party_at(key, date, legislature) if key else None})
    ok, note = ps.tally({"Yea": raw["yeas"], "Nay": raw["nays"]}, votes)
    if raw.get("problem"):
        ok, note = False, "; ".join(x for x in (raw["problem"], note) if x)
    return votes, ok, note


def read_sitting(ctx, legislature, session, rec, resolver, wl):
    """Read one day's Journal. Returns (divisions, gaps_in_it)."""
    date, url = rec["date"], rec["url"]
    skey = ps.sitting_key(PROV, legislature, session, date)
    raw = ctx.bytes(url, "journal-{0}".format(date))
    if raw is None:
        return 0, 1
    try:
        text = pdf_text(raw)
    except Unreadable as exc:
        ctx.gap("{0}: {1}: {2}".format(skey, url, exc))
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
        ctx.conn.commit()
        return 0, 1
    divisions, voices = parse_journal(text)
    gaps = 0
    for d in divisions:
        votes, ok, note = resolve_division(d, resolver, date, legislature)
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        inherit = pc.Result(b_areas, b_terms, b_tier) if b_areas else None
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["item"]], bill_key=bkey, inherit=inherit)
        dkey = ps.division_key(PROV, legislature, session, date, d["seq"])
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        question = d["question"]
        if d["motion"] and question and not question.startswith("Motion"):
            question = "[Motion {0}] {1}".format(d["motion"], question)
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": date, "seq": d["seq"], "kind": "recorded", "question": question,
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "abstentions": None, "source_url": url,
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": note or d.get("note"), "votes": votes})
    for v in voices:
        bkey = ps.bill_key(PROV, legislature, session, v["bill_number"])
        areas, terms, tier = ps.bill_areas(ctx.conn, bkey)
        ps.store_division(ctx.conn, {
            "division_key": ps.division_key(PROV, legislature, session, date, "v{0}-{1}".format(
                v["bill_number"], STAGE_CODE[v["stage"]])),
            "prov": PROV, "legislature": legislature, "session": session, "date": date,
            "seq": "v", "kind": "voice", "bill_key": bkey, "stage": v["stage"],
            "result": v["result"], "source_url": url, "areas": areas, "matched_terms": terms,
            "tier": tier})
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions), voice=len(voices),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return len(divisions), gaps


def check_listing_stages(ctx, legislature, session, read_dates):
    """Every second or third reading the bills listing dates to a day whose
    Journal was read must be in that Journal, divided or on voice."""
    misses = 0
    for key, stages in ctx.conn.execute(
            "SELECT bill_key, stages FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
            (PROV, legislature, session)).fetchall():
        for s in json.loads(stages or "[]"):
            if s.get("stage") not in ("Second Reading", "Third Reading") or s.get("date") not in read_dates \
                    or (s.get("status") or "").lower() not in ("passed", "defeated"):
                continue
            hit = ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? AND stage=?",
                (key, s["date"], s["stage"])).fetchone()[0]
            if not hit:
                misses += 1
                ctx.gap("{0}: the bills listing says {1} {2} on {3}; that day's Journal gave neither "
                        "a recorded division nor a voice decision for it".format(
                            key, s["stage"], s["status"].lower(), s["date"]))
    return misses


def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    legislature, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    html = ctx.text(JOURNALS.format(legislature, sess), "journals-{0}-{1}".format(legislature, sess))
    listing = list_records(html or "")
    if html and not listing["daily"]:
        ctx.gap("nb journals {0}: no daily Journals parsed from the listing".format(session))
    records = [r for r in listing["daily"] if ctx.in_window(r["date"])]
    stats = {"records_listed": len(records)}
    if roster:
        stats["members"] = fetch_roster(ctx, legislature, sess, listing)
    if bills:
        stats.update(fetch_bills(ctx, legislature, sess, ctx.tax, wl))
    if ctx.dry_run:
        return stats
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    read = divs = gaps = 0
    read_dates = set()
    for rec in records:
        if not ctx.refresh and ps.sitting_done(ctx.conn, rec["url"]):
            read_dates.add(rec["date"])
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        n, g = read_sitting(ctx, legislature, sess, rec, resolver, wl)
        read += 1
        divs += n
        gaps += g
        status = ctx.conn.execute("SELECT status FROM prov_sittings WHERE record_url=?",
                                  (rec["url"],)).fetchone()
        if status and status[0] != "unreadable":
            read_dates.add(rec["date"])
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps,
                  "listing_misses": check_listing_stages(ctx, legislature, sess, read_dates) if bills else 0})
    ctx.conn.commit()
    return stats
