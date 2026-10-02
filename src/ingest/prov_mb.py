"""Legislative Assembly of Manitoba: dated roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov mb. Scope: docs/canada-provinces-scope.md
(Manitoba: value 4, difficulty 2).

ROBOTS AND POLICY. gov.mb.ca's robots.txt gives `Disallow: /` to a list of
named AI crawlers (GPTBot, ClaudeBot, anthropic-ai, CCBot and others) and,
for `*`, disallows a few paths that do not include /legislature/.
Christopher decided on 2 October 2026 to collect Manitoba (scope,
"Decisions"): this collector is not a training crawler, it identifies itself
honestly (src/http.py), reads public parliamentary records at about one
request a second, and obeys every path disallowed for `*`. The robots file
is read on every run (src/prov_fetch.Robots); if Manitoba ever names our
agent there, every fetch becomes a gap and nothing is read. If Manitoba asks
us to stop, we stop. web2.gov.mb.ca (the bills site) answers robots.txt with
an error page: no rules.

  * LISTINGS, never constructed: business/votes_proceedings.html names each
    session's V&P calendar page (43rd/43rd_3rd.html); each calendar links a
    day's Votes and Proceedings PDF under its day number. A stray link with
    no day (42-3 prints votes_029 a second time in the 6 October cell) is
    dropped when the same file is listed under a real day. The PDF's own
    printed date ("Thursday, October 14, 2021") is the record's date.
    hansard/hansard_archive.html names each session's Hansard calendar, and
    web2.gov.mb.ca/bills/sess/index.php each session's bills page.
  * ROSTER, DATED TO THE DAY. The Assembly's member pages list only current
    MLAs. Every Hansard PDF instead prints, on its second page, the whole
    House AS AT THAT SITTING: "COX, Cathy, Hon. Kildonan-River East PC",
    "WASYLIW, Mark Fort Garry Ind.", "Vacant Fort Whyte". For every day with
    a recorded division, that day's Hansard cover is read and each member's
    term is widened to cover exactly that day (prov_store.extend_term), as
    for Saskatchewan. Party at the vote is a fact of the day: Mark Wasyliw
    is NDP in 2021 and Independent in June 2025.
  * DIVISIONS. Votes and Proceedings: "And the Question being put. It was
    negatived, on the following division:" then "YEA" (42nd Legislature) or
    "AYE" (43rd), one name per line in capitals, a riding where two members
    share a surname ("SMITH (Lagimodière)"), the printed total on the last
    name's line ("WIEBE ......... 20"), then "NAY". The totals are the tally
    check, and the count of "on the following division" phrases in the text
    is a second one: a division the parser missed is a gap.
  * VOICE. "It was agreed to." with "The Bill was accordingly read a Second
    Time ...", "... concurred in, read a Third Time and passed", "It was
    negatived, on division" (dissent noted, no names), and the day's list of
    bills "read a First Time" are decisions without a recorded division:
    stored as kind='voice'.
  * BILLS. The session's bills page (number, sponsor, title, the HTML text
    of the bill as distributed after first reading). Each text is classified
    per passage with statute names masked (src/prov_classify.py).

Hansard speeches and the session's billstatus.pdf (stage dates) are not
read: stage dates come from the V&P themselves (scope "Built" notes).
"""

from __future__ import annotations

import datetime
import html as _html
import re
from urllib.parse import urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text, pdf_text, sessions_sorted, slug, year_span

PROV = "mb"
CURRENT_SESSION = "43-3"
BASE = "https://www.gov.mb.ca/legislature/"
VP_SESSIONS = BASE + "business/votes_proceedings.html"
HANSARD_SESSIONS = BASE + "hansard/hansard_archive.html"
BILL_SESSIONS = "https://web2.gov.mb.ca/bills/sess/index.php"

_ORD = r"(?:st|nd|rd|th)"
_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"), 1)}
_DAY_HEAD = re.compile(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
                       r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})")


def parse_session(code):
    m = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("Manitoba session must look like 43-3, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def printed_date(text):
    """The first 'Thursday, October 14, 2021' in a record, as ISO."""
    m = _DAY_HEAD.search(text or "")
    if not m or m.group(1).lower() not in _MONTHS:
        return None
    return datetime.date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()


# -- listings ---------------------------------------------------------------

def session_pages(html, base, kind):
    """{(legislature, session): url} from a listing page. kind 'vp' reads
    '43rd/43rd_3rd.html', 'hansard' '../hansard/42nd_3rd/42nd_3rd.html#top',
    'bills' '../42-3/index.php'."""
    out = {}
    if kind == "vp":
        rx = re.compile(r'href="((\d+){0}/\2{0}_(\d){0}\.html)"'.format(_ORD))
        for href, leg, sess in rx.findall(html or ""):
            out.setdefault((int(leg), int(sess)), urljoin(base, href))
    elif kind == "hansard":
        rx = re.compile(r'href="([^"#]*?/((\d+){0}_(\d){0})/\2\.html)(?:#[^"]*)?"'.format(_ORD))
        for href, _code, leg, sess in rx.findall(html or ""):
            out.setdefault((int(leg), int(sess)), urljoin(base, href))
    elif kind == "bills":
        for href, leg, sess in re.findall(r'href="((?:\.\./)?(\d+)-(\d)/index\.php)"', html or ""):
            out.setdefault((int(leg), int(sess)), urljoin(base, href))
    return out


_VP_SESSION_HREF = re.compile(r'href="((\d+){0}/\2{0}_(\d){0}\.html)"'.format(_ORD))
_YEARS = re.compile(r"(?<!\d)(\d{4})(?:\s*-\s*(\d{4}))?(?!\d)")


def parse_sessions(html):
    """Every session on the V&P sessions page, one table row each: the
    years cell ("2010 - 2011", "&nbsp;2016&nbsp;") and the session's link.
    A row without years still names its session, with no span (it is read
    by any window)."""
    out = []
    for row in re.findall(r"<tr\b(.*?)</tr>", html or "", re.S | re.I):
        link = _VP_SESSION_HREF.search(row)
        if not link:
            continue
        code = "{0}-{1}".format(int(link.group(2)), int(link.group(3)))
        years = _YEARS.search(_html.unescape(re.sub(r"<[^>]+>", " ", row[:link.start()])))
        out.append(year_span(code, years.group(1), years.group(2)) if years
                   else {"code": code, "start": None, "end": None})
    return sessions_sorted(out)


def list_sessions(ctx):
    listing = ctx.text(VP_SESSIONS, "vp-sessions")
    out = parse_sessions(listing)
    if listing and not out:
        ctx.gap("mb: no sessions parsed from {0}".format(VP_SESSIONS))
    return out


_CAL = re.compile(r'<table class="calendar">(.*?)</table>', re.S)
_CAL_TITLE = re.compile(r'thead_title">(?:<a[^>]*></a>)?\s*([A-Za-z]+)\s+(\d{4})')


def parse_calendar(html, base, href_rx):
    """[(date or None, url, link_text)] for every link matching href_rx in a
    session calendar page, with the date of the day cell it sits in."""
    out = []
    for table in _CAL.findall(html or ""):
        t = _CAL_TITLE.search(table)
        if not t or t.group(1).lower() not in _MONTHS:
            continue
        month, year = _MONTHS[t.group(1).lower()], int(t.group(2))
        for cell in re.findall(r"<td[^>]*>(.*?)</td>", table, re.S):
            text = html_text(cell)
            day = re.match(r"(\d{1,2})\b", text)
            for href, label in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', cell, re.S):
                if not re.search(href_rx, href):
                    continue
                label = html_text(label)
                date = None
                if day:
                    try:
                        date = datetime.date(year, month, int(day.group(1))).isoformat()
                    except ValueError:
                        date = None
                out.append((date, urljoin(base, _html.unescape(href)), label))
    return out


def list_records(html, base):
    """[(date, url)] of V&P PDFs. A link whose text is not the day number is
    a stray (42-3 links votes_029 again, blank, in the 6 October cell): it
    is dropped when the same file is listed under its day, and kept with
    date None (the PDF's printed date decides) when it is not."""
    dated, undated = {}, []
    for date, url, label in parse_calendar(html, base, r"votes_\d+\w*\.pdf$"):
        if label.isdigit() and date:
            dated.setdefault(url, date)
        else:
            undated.append(url)
    out = sorted((d, u) for u, d in dated.items())
    out += [(None, u) for u in dict.fromkeys(undated) if u not in dated]
    return out


def list_hansard(html, base):
    """{date: [pdf url, ...]} in the order printed (82A before 82B)."""
    out = {}
    for date, url, _label in parse_calendar(html, base, r"hansardpdf/\w+\.pdf$"):
        if date:
            out.setdefault(date, [])
            if url not in out[date]:
                out[date].append(url)
    return out


# -- the Hansard cover roster -----------------------------------------------

_COVER_LINE = re.compile(r"^\s*(?P<sur>[A-ZÀ-Ý][A-ZÀ-Ý'’ .\-]+?),\s*(?P<rest>.+?)\s+"
                         r"(?P<party>NDP|PC|Lib\.|Liberal|Ind\.|IND|Ind|Green|[A-Z][A-Za-z]{0,4}\.?)\s*$")


def _title(surname):
    return "-".join(" ".join(w[:1] + w[1:].lower() for w in part.split(" "))
                    for part in surname.split("-"))


def parse_cover(text):
    """(members, vacancies) from a Hansard PDF's member page.
    members: [{surname, given, riding, party, key, hon}]"""
    t = text or ""
    start = t.find("Political Affiliation")
    if start < 0:
        return [], 0
    members, vacant = [], 0
    for line in t[start + len("Political Affiliation"):].splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("LEGISLATIVE ASSEMBLY OF MANITOBA") or _DAY_HEAD.search(s):
            break
        if s.startswith("Vacant"):
            vacant += 1
            continue
        m = _COVER_LINE.match(s)
        if not m:
            continue
        rest = m.group("rest").strip()
        hon = False
        h = re.match(r"^(.*?),\s*Hon\.\s+(.+)$", rest)
        if h:
            given, riding, hon = h.group(1).strip(), h.group(2).strip(), True
        else:
            # One given name, then the constituency: true of every member
            # listed in the 42nd and 43rd Legislatures. A two-word given name
            # would put a word into the riding, which then fails to match a
            # "SMITH (Riding)" label -- a gap, never a wrong member.
            given, _, riding = rest.partition(" ")
        surname = _title(m.group("sur").strip())
        members.append({"surname": surname, "given": given, "riding": riding.strip() or None,
                        "party": m.group("party"), "hon": hon,
                        "key": slug(given + " " + surname)})
    return members, vacant


def roster_for_day(ctx, legislature, date, hansard):
    """Read the day's Hansard cover and widen every member's term to it."""
    have = ctx.conn.execute(
        "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source='hansard-cover' "
        "AND start<=? AND end>=?", (PROV, date, date)).fetchone()[0]
    if have and not ctx.refresh:
        return have
    urls = (hansard or {}).get(date) or []
    if not urls:
        ctx.gap("mb {0}: no Hansard listed for the day, so no roster as at the day "
                "(Hansard lags the V&P; the day stays owed)".format(date))
        return 0
    raw = ctx.bytes(urls[0], "hansard-{0}".format(date))
    if not raw:
        return 0
    try:
        text = pdf_text(raw, pages=[0, 1, 2])
    except Unreadable as exc:
        ctx.gap("mb {0}: Hansard cover {1}: {2}".format(date, urls[0], exc))
        return 0
    members, _vacant = parse_cover(text)
    if len(members) < 40:
        ctx.gap("mb {0}: only {1} member(s) parsed from the Hansard cover {2}".format(
            date, len(members), urls[0]))
        if not members:
            return 0
    newest = ctx.conn.execute("SELECT MAX(end) FROM prov_member_terms WHERE prov=? AND "
                              "source='hansard-cover'", (PROV,)).fetchone()[0]
    is_newest = newest is None or date >= newest
    if is_newest:
        ctx.conn.execute("UPDATE prov_members SET sitting=0 WHERE prov=?", (PROV,))
    for m in members:
        ps.upsert_member(ctx.conn, PROV, m["key"], name=m["given"] + " " + m["surname"],
                         surname=m["surname"], given=m["given"],
                         riding=m["riding"] if is_newest else None,
                         party=m["party"] if is_newest else None,
                         sitting=1 if is_newest else None)
        ps.extend_term(ctx.conn, PROV, m["key"], legislature, m["party"], m["riding"],
                       date, "hansard-cover")
    ctx.conn.commit()
    return len(members)


# -- Votes and Proceedings ----------------------------------------------------

HEADER = re.compile(r"^\s*(YEAS?|AYES?|NAYS?)\s*:?\s*$")
_LEADER = re.compile(r"^(.*?)\s*\.{4,}\s*(\d+)\s*$")
_SEPARATOR = re.compile(r"^\s*_{6,}\s*$")
_BILL_NO = re.compile(r"Bill\s*\(No\.\s*(\d+)\)")
_TITLE = re.compile(r"\(No\.\s*(\d+)\)\s*[–—-]\s*(.+?)\s*/\s*(?:Loi|Code)\b")
_PUT = re.compile(r"And the Question being put(?: on the (amendment|sub-?amendment|main motion|motion))?\."
                  r"\s*It was (agreed to|negatived)(,\s*unanimously|,\s*on division|,\s*on the following division)?",
                  re.I)
_VOICE_BILL = re.compile(r"The Bill was accordingly (read a Second Time|concurred in, read a Third Time)", re.I)
_FIRST_LIST = re.compile(r"The following Bills? (?:was|were) read a First Time", re.I)


def _stage(text):
    """The stage named last in a block's text."""
    found = None
    for m in re.finditer(r"(be now read a Second Time|read for a Third Time|concurred in and be now read"
                         r"|Report Stage|read a First Time|be now received and read a First Time)", text, re.I):
        w = m.group(1).lower()
        found = ("Second Reading" if "second" in w else "Third Reading" if ("third" in w or "concurred" in w)
                 else "Report Stage" if "report" in w else "First Reading")
    return found


def _blocks(text):
    """The V&P split at its own '______' item rules, furniture removed."""
    blocks, cur = [], []
    for line in (text or "").splitlines():
        if _SEPARATOR.match(line):
            blocks.append(cur)
            cur = []
            continue
        if pn.is_furniture(line):
            continue
        cur.append(line.rstrip())
    blocks.append(cur)
    return [b for b in blocks if any(l.strip() for l in b)]


def _take_list(lines, i):
    """(labels, total, i, problem) for one AYE/NAY list starting after its
    header at lines[i]. The total is printed on the last name's line."""
    labels, n = [], len(lines)
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        lead = _LEADER.match(s)
        if lead:
            if lead.group(1).strip():
                labels.append(lead.group(1).strip())
            return labels, int(lead.group(2)), i + 1, None
        if HEADER.match(s):
            return labels, None, i, "a list ended without its printed total"
        if s.startswith("(") and labels and not labels[-1].endswith(")"):
            labels[-1] += " " + s        # a riding wrapped onto its own line
        elif labels and labels[-1].count("(") > labels[-1].count(")"):
            labels[-1] += " " + s        # a riding split across lines
        elif re.match(r"^[A-ZÀ-Ý][A-ZÀ-Ý'’ .\-]*(?:\s*\([^()]*\)?)?$", s):
            labels.append(s)
        else:
            return labels, None, i, "unexpected line in a name list: {0!r}".format(s[:60])
        i += 1
    return labels, None, i, "the record ended inside a name list"


def parse_vp(text):
    """(divisions, voices, titles, expected) from one day's V&P text.

    divisions: [{seq, vote_on, yeas, nays, yea_labels, nay_labels, question,
                 result, stage, bill_number, problem}]
    voices:    [{bill_number, stage, result}]
    titles:    {number: English title}
    expected:  how many times the text says "on the following division"."""
    divisions, voices, titles = [], [], {}
    flat = re.sub(r"\s+", " ", text or "")
    expected = len(re.findall(r"on the following division", flat, re.I))
    for num, title in _TITLE.findall(flat):
        titles.setdefault(num, title.strip(" ,"))
    for block in _blocks(text):
        joined = re.sub(r"\s+", " ", " ".join(block)).strip()
        bill = (_BILL_NO.findall(joined) or [None])[-1]
        context, i, n = [], 0, len(block)
        block_divs = []
        while i < n:
            line = block[i]
            h = HEADER.match(line)
            if not h or not h.group(1).upper().startswith(("YEA", "AYE")):
                context.append(line)
                i += 1
                continue
            yea_labels, yeas, i, problem = _take_list(block, i + 1)
            while i < n and not block[i].strip():
                i += 1
            nay_labels, nays = [], None
            if i < n and HEADER.match(block[i]) and HEADER.match(block[i]).group(1).upper().startswith("NAY"):
                nay_labels, nays, i, p2 = _take_list(block, i + 1)
                problem = problem or p2
            else:
                problem = problem or "no NAY list after the YEA list"
            ctx_text = re.sub(r"\s+", " ", " ".join(context)).strip()
            upto = re.sub(r"\s+", " ", " ".join(block[:i])).strip()
            puts = _PUT.findall(ctx_text)
            on = (puts[-1][0] or "motion").lower() if puts else "motion"
            d = {"seq": len(divisions) + 1,
                 "vote_on": "amendment" if on == "amendment" else
                            "subamendment" if on.startswith("sub") else "motion",
                 "yeas": yeas, "nays": nays, "yea_labels": yea_labels, "nay_labels": nay_labels,
                 "question": ctx_text[-700:] or None,
                 "result": "It was {0}, on the following division".format(puts[-1][1].lower()) if puts else None,
                 "stage": _stage(upto) or "Motion",
                 "bill_number": (_BILL_NO.findall(upto) or [bill])[-1],
                 "problem": problem}
            divisions.append(d)
            block_divs.append(d)
            context = []
        # Voice decisions in this block: a question put without a recorded
        # division, on a bill stage, where no recorded division in the block
        # was on the main question.
        main_recorded = any(d["vote_on"] == "motion" for d in block_divs)
        stage = _stage(joined)
        if bill and stage in ("Second Reading", "Third Reading") and not main_recorded:
            for on, result, how in _PUT.findall(joined):
                if (on or "motion").lower() not in ("motion", "main motion"):
                    continue
                if "following division" in (how or "").lower():
                    continue
                voices.append({"bill_number": bill, "stage": stage,
                               "result": "It was {0}{1}".format(result.lower(), how or "")})
                break
            else:
                v = _VOICE_BILL.search(joined)
                if v:
                    voices.append({"bill_number": bill, "stage": stage, "result": v.group(0)})
        if _FIRST_LIST.search(joined):
            tail = joined[_FIRST_LIST.search(joined).end():]
            for num in re.findall(r"\(No\.\s*(\d+)\)", tail):
                voices.append({"bill_number": num, "stage": "First Reading",
                               "result": "read a First Time"})
    seen, unique = set(), []
    for v in voices:
        k = (v["bill_number"], v["stage"])
        if k not in seen:
            seen.add(k)
            unique.append(v)
    return divisions, unique, titles, expected


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


def read_sitting(ctx, legislature, session, listed_date, url, hansard, wl):
    """Read one V&P. Returns (divisions, gaps_in_it)."""
    data = ctx.bytes(url, "vp-{0}".format(listed_date or "undated"))
    if data is None:
        return 0, 1
    try:
        text = pdf_text(data)
    except Unreadable as exc:
        ctx.gap("mb {0}: {1}: {2}".format(listed_date, url, exc))
        if listed_date:
            ps.store_sitting(ctx.conn, PROV, ps.sitting_key(PROV, legislature, session, listed_date),
                             listed_date, url, status="unreadable")
        return 0, 1
    date = printed_date(text) or listed_date
    if listed_date and date != listed_date:
        ctx.log("  mb: {0} is listed under {1} but prints {2}; the record's own date is used".format(
            url, listed_date, date))
    if not date:
        ctx.gap("mb: {0} has no listed or printed date".format(url))
        return 0, 1
    if not ctx.in_window(date):
        return 0, 0
    skey = ps.sitting_key(PROV, legislature, session, date)
    divisions, voices, titles, expected = parse_vp(text)
    gaps = 0
    if divisions:
        roster_for_day(ctx, legislature, date, hansard)
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    for number, title in titles.items():
        key = ps.bill_key(PROV, legislature, session, number)
        res = pc.classify(ctx.tax, wl, PROV, title=title, bill_key=key)
        ps.store_bill(ctx.conn, {"bill_key": key, "prov": PROV, "legislature": legislature,
                                 "session": session, "number": number, "title_en": title,
                                 "areas": res.areas, "matched_terms": res.terms, "tier": res.tier,
                                 "excerpt": res.excerpt})
    if expected != len(divisions):
        gaps += 1
        ctx.gap("{0}: the record says 'on the following division' {1} time(s) but {2} "
                "division(s) were parsed".format(skey, expected, len(divisions)))
    for d in divisions:
        votes, ok, note = resolve_division(d, resolver, date, legislature)
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["question"]], bill_key=bkey,
                          inherit=pc.Result(b_areas, b_terms, b_tier) if b_areas else None)
        dkey = ps.division_key(PROV, legislature, session, date, d["seq"])
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": date, "seq": d["seq"], "kind": "recorded", "question": d["question"],
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "source_url": url, "areas": res.areas,
            "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": note, "votes": votes})
    for v in voices:
        bkey = ps.bill_key(PROV, legislature, session, v["bill_number"])
        areas, terms, tier = ps.bill_areas(ctx.conn, bkey)
        ps.store_division(ctx.conn, {
            "division_key": ps.division_key(PROV, legislature, session, date, "v{0}-{1}".format(
                v["bill_number"], {"First Reading": "1r", "Second Reading": "2r",
                                   "Third Reading": "3r"}[v["stage"]])),
            "prov": PROV, "legislature": legislature, "session": session, "date": date, "seq": "v",
            "kind": "voice", "bill_key": bkey, "stage": v["stage"], "result": v["result"],
            "source_url": url, "areas": areas, "matched_terms": terms, "tier": tier})
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions), voice=len(voices),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return len(divisions), gaps


# -- bills ------------------------------------------------------------------

_BILL_ROW = re.compile(r'<tr>\s*<td class="right sm">\s*(\d+)\s*</td>\s*<td class="left sm8">(.*?)</td>(.*?)</tr>',
                       re.S)


def parse_bill_list(html, base):
    """[{number, sponsor, title, text_url, pdf_url, is_government}]"""
    out = []
    kind = None
    for m in re.finditer(r'<td class="centerbig"[^>]*>(.*?)</td>|' + _BILL_ROW.pattern, html or "", re.S):
        if m.group(1) is not None:
            kind = html_text(m.group(1))
            continue
        number, sponsor, rest = m.group(2), m.group(3), m.group(4)
        sponsor = html_text(re.split(r"<br\s*/?>", sponsor)[0]) or None
        link = re.search(r'<a href="(b\d+\w*\.php)">(.*?)</a>', rest, re.S)
        pdf = re.search(r'<a class="sm" href="(pdf/[^"]+\.pdf)"', rest)
        title = html_text(link.group(2)) if link else html_text(re.split(r"&mdash;|—", rest)[0])
        out.append({"number": number, "sponsor": sponsor, "title": title or None,
                    "text_url": urljoin(base, link.group(1)) if link else None,
                    "pdf_url": urljoin(base, pdf.group(1)) if pdf else None,
                    "is_government": 1 if (kind or "").lower().startswith("government") else 0,
                    "bill_type": kind})
    return out


def bill_text(html):
    """The bill's own text from its HTML page (from the 'chapter' heading to
    the end of the content), site chrome removed."""
    s = html or ""
    i = s.find('<p class="chapter">')
    j = s.find("<!--end content-->")
    body = s[i if i >= 0 else 0:j if j > i else len(s)]
    body = re.sub(r"</(p|tr|h\d|li|div)>", "\n\n", body, flags=re.I)
    return "\n".join(html_text(p) for p in body.split("\n\n") if html_text(p))


def fetch_bills(ctx, legislature, session, wl):
    sessions = ctx.text(BILL_SESSIONS, "bill-sessions")
    url = session_pages(sessions, BILL_SESSIONS, "bills").get((legislature, session)) if sessions else None
    if sessions and not url:
        ctx.gap("mb bills: session {0}-{1} not on the bills sessions page".format(legislature, session))
    html = ctx.text(url, "bills-{0}-{1}".format(legislature, session)) if url else None
    items = parse_bill_list(html, url) if html else []
    if html and not items:
        ctx.gap("mb bills {0}-{1}: no bills parsed from the listing".format(legislature, session))
    if ctx.dry_run:
        return {"bills": len(items)}
    texts = 0
    for it in items:
        key = ps.bill_key(PROV, legislature, session, it["number"])
        record = {"bill_key": key, "prov": PROV, "legislature": legislature, "session": session,
                  "number": it["number"], "title_en": it["title"], "sponsor": it["sponsor"],
                  "is_government": it["is_government"], "bill_type": it["bill_type"],
                  "page_url": it["text_url"], "text_url": it["text_url"] or it["pdf_url"]}
        have = ctx.conn.execute("SELECT text_read FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
        if have and have[0] and not ctx.refresh:
            ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
            continue
        body = None
        if it["text_url"]:
            if ctx.budget is not None and ctx.budget.exhausted():
                ctx.log(ctx.budget.disclose("bill texts", texts))
                break
            page = ctx.text(it["text_url"], "bill-{0}-{1}".format(session, it["number"]))
            body = bill_text(page) if page else None
            if page and not body:
                ctx.gap("{0}: bill text page {1} had no text".format(key, it["text_url"]))
        res = pc.classify(ctx.tax, wl, PROV, title=it["title"], texts=[body] if body else [], bill_key=key)
        ps.store_bill(ctx.conn, dict(record, text_read=1 if body else 0, areas=res.areas,
                                     matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
        texts += 1 if body else 0
    ctx.conn.commit()
    ctx.log("  mb bills {0}-{1}: {2} listed, {3} text(s) read".format(legislature, session, len(items), texts))
    return {"bills": len(items), "bill_texts": texts}


# -- the run ----------------------------------------------------------------

def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    """--session picks the session; --since/--until the window. The roster
    is read per division day from that day's Hansard (so --no-roster leaves
    every division without its names resolved: a gap, said out loud)."""
    legislature, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    stats = {}
    if bills:
        stats.update(fetch_bills(ctx, legislature, sess, wl))
    listing = ctx.text(VP_SESSIONS, "vp-sessions")
    vp_url = session_pages(listing, VP_SESSIONS, "vp").get((legislature, sess)) if listing else None
    if listing and not vp_url:
        ctx.gap("mb V&P: session {0} is not on {1}".format(session, VP_SESSIONS))
    page = ctx.text(vp_url, "vp-list-{0}".format(session)) if vp_url else None
    records = [r for r in list_records(page, vp_url) if r[0] is None or ctx.in_window(r[0])] if page else []
    if page and not list_records(page, vp_url):
        ctx.gap("mb V&P {0}: no records parsed from {1}".format(session, vp_url))
    stats["records_listed"] = len(records)
    if ctx.dry_run:
        return stats
    hansard = None
    read = divs = gaps = 0
    for date, url in records:
        if not ctx.refresh and ps.sitting_done(ctx.conn, url):
            continue
        if ctx.stop():
            break
        if hansard is None and roster:
            hl = ctx.text(HANSARD_SESSIONS, "hansard-sessions")
            h_url = session_pages(hl, HANSARD_SESSIONS, "hansard").get((legislature, sess)) if hl else None
            if hl and not h_url:
                ctx.gap("mb Hansard: session {0} is not on {1}".format(session, HANSARD_SESSIONS))
            hp = ctx.text(h_url, "hansard-list-{0}".format(session)) if h_url else None
            hansard = list_hansard(hp, h_url) if hp else {}
        ctx.records_read += 1
        n, g = read_sitting(ctx, legislature, sess, date, url, hansard or {}, wl)
        read += 1
        divs += n
        gaps += g
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps})
    ctx.conn.commit()
    return stats
