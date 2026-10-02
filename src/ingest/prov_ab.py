"""Legislative Assembly of Alberta: roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov ab. Scope: docs/canada-provinces-scope.md
(Alberta: value 5, difficulty 3). Every source is official, open and keyless;
robots.txt carries only a sitemap line.

  * ROSTER. members-of-the-legislative-assembly?legl=L lists every member of
    legislature L (name, caucus, constituency; "Former Member" for those who
    left). Each member-information page carries DATED party affiliations
    (Pete Guthrie: United Conservative to 16 Apr 2025, Independent, Alberta
    Party, Progressive Tory), dates of service and the constituency won at
    each election. A term is one affiliation intersected with one spell of
    service, so party_at_vote is a fact of the day, not a join to today.
  * BILLS. bills-by-legislature?legl=L&session=S, then one page per bill:
    sponsor (by mid), type, the bill-text PDF, and every stage with its date
    and status -- "passed", or "passed on division". The flag is a free index
    of which stages were divided; a stage that "passed" without it is stored
    as a VOICE decision. Bills are classified on the TEXT of the PDF, per
    passage, with statute names masked (src/prov_classify.py).
  * DIVISIONS. Votes and Proceedings, one PDF per sitting day. File names
    are taken from the session's listing page, never constructed: the time
    token is always _1200_ for V&P while Hansard uses the real sitting time,
    and the listing's hrefs use Windows backslashes. Each division prints
    "For the motion: 47" then three columns of surnames, a riding where two
    members share one ("Sigurdson (Highwood)", sometimes wrapped onto the
    next line), then "Against the motion: 35". The printed totals are the
    tally check.

Hansard (PDF, speeches) is not read yet: see the scope's "Built" notes.
"""

from __future__ import annotations

import datetime
import html as _html
import json
import re
from urllib.parse import urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text, pdf_text

PROV = "ab"
CURRENT_SESSION = "31-2"
BASE = "https://www.assembly.ab.ca"
VP_LIST = BASE + "/assembly-business/assembly-records/votes-and-proceedings?legl={0}&session={1}"
ROSTER = BASE + "/members/members-of-the-legislative-assembly?legl={0}"
BILLS = BASE + "/assembly-business/bills/bills-by-legislature?legl={0}&session={1}"

STAGES = ("First Reading", "Second Reading", "Committee of the Whole", "Third Reading")
STAGE_CODE = {"First Reading": "1r", "Second Reading": "2r",
              "Committee of the Whole": "cw", "Third Reading": "3r"}


def parse_session(code):
    m = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("Alberta session must look like 31-1, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def _date(text, fmts):
    t = re.sub(r"\bSept\b", "Sep", (text or "").strip())
    for f in fmts:
        try:
            return datetime.datetime.strptime(t, f).date().isoformat()
        except ValueError:
            continue
    return None


# -- listing ----------------------------------------------------------------

_VP_ITEM = re.compile(
    r'<span class="rwd-hide">([^<]+)</span></div>\s*<div class="div2"><a[^>]*href="([^"]+_vp\.pdf)"')


def list_records(html):
    """[(date, url)] from a V&P listing page. The href's backslashes become
    forward slashes; nothing else about the name is touched."""
    out = []
    for when, href in _VP_ITEM.findall(html or ""):
        date = _date(when, ("%A, %B %d, %Y",))
        url = _html.unescape(href).replace("\\", "/")
        if not date:
            m = re.search(r"/(\d{8})_\d{4}_\d{2}_vp\.pdf$", url)
            date = m and "{0}-{1}-{2}".format(m.group(1)[:4], m.group(1)[4:6], m.group(1)[6:])
        out.append((date, url))
    return out


# -- roster -----------------------------------------------------------------

_ROSTER_ROW = re.compile(
    r'<img class="MemPhoto"[^>]*alt="([^"]*)"></td>\s*<td>\s*<a href="([^"]*member-information\?mid=(\d+)[^"]*)">'
    r'([^<]*)</a></td>\s*<td>\s*([^<]*)</td>\s*<td>\s*(.*?)</td>', re.S)


def parse_roster(html):
    """[{mid, name, surname, given, caucus, riding, former, href}]"""
    out = []
    for alt, href, mid, listed, caucus, riding in _ROSTER_ROW.findall(html or ""):
        name = _html.unescape(alt).strip()
        surname = _html.unescape(listed).split(",")[0].strip()
        given = name[:-len(surname)].strip() if name.endswith(surname) else None
        riding = html_text(riding)
        former = "Former Member" in riding
        caucus = _html.unescape(caucus).strip().replace("\xa0", "")
        out.append({"mid": mid, "name": name, "surname": surname, "given": given,
                    "caucus": caucus or None, "riding": None if former else riding,
                    "former": former, "href": urljoin(BASE, _html.unescape(href))})
    return out


def _rows(html, table):
    """Rows of one member-page table ('mla_pa', 'mla_dos', 'mla_cec') as
    {label: data} dicts, header row excluded."""
    start = html.find('<div id="{0}">'.format(table))
    if start < 0:
        return []
    block = html[start:start + 30000]
    head = re.search(r'<div class="{0} th mla_table">(.*?)</div>\s*<div class="{0} mla_table">'.format(table),
                     block, re.S)
    width = len(re.findall(r'class="col\d+"', head.group(1))) if head else 3
    out = []
    # Each row is cut to the table's own width: the next table on the page
    # (Offices and Roles) has Start/End cells too, and without the cut the
    # LAST row of one table swallowed the next table's dates (measured on the
    # live pages, 2 October 2026: role dates stored as party dates).
    for row in re.split(r'<div class="{0} mla_table">'.format(table), block)[1:]:
        cells = re.findall(r'<span class="label">([^<]*)</span><span class="data">(.*?)</span>',
                           row, re.S)[:width]
        out.append({k: html_text(v) for k, v in cells})
        if re.search(r'<div id="(?!{0})'.format(table), row):
            break
    return out


def parse_member_page(html):
    """{'affiliations': [(start, end, party)], 'service': [(start, end)],
    'elected': {legislature: constituency}}. 'Current' is an open end."""
    d = lambda s: None if (s or "").strip() in ("", "Current") else _date(s, ("%Y-%b-%d",))  # noqa: E731
    aff = [(d(r.get("Start")), d(r.get("End")), r.get("Party")) for r in _rows(html, "mla_pa")
           if r.get("Party")]
    service = [(d(r.get("Start")), d(r.get("End"))) for r in _rows(html, "mla_dos")
               if r.get("Start")]
    elected = {}
    for r in _rows(html, "mla_cec"):
        if (r.get("Result") or "").startswith("Elected") and (r.get("Legislature") or "").isdigit():
            elected.setdefault(int(r["Legislature"]), r.get("Constituency"))
    return {"affiliations": aff, "service": service, "elected": elected}


def terms_from_page(page, legislature, fallback_riding=None):
    """One term per party affiliation intersected with each spell of service."""
    riding = page["elected"].get(legislature) or fallback_riding
    out = []
    for a_start, a_end, party in page["affiliations"]:
        for s_start, s_end in page["service"] or [(None, None)]:
            start = max([x for x in (a_start, s_start) if x] or [None])
            end = min([x for x in (a_end, s_end) if x] or [None])
            if start and end and start > end:
                continue
            out.append({"legislature": legislature, "party": party, "riding": riding,
                        "start": start, "end": end, "party_dated": 1})
    return out


def fetch_roster(ctx, legislature):
    html = ctx.text(ROSTER.format(legislature), "roster-{0}".format(legislature))
    if not html:
        return 0
    rows = parse_roster(html)
    if not rows:
        ctx.gap("ab roster legl={0}: no members parsed".format(legislature))
        return 0
    if ctx.dry_run:
        return len(rows)
    pages = 0
    for r in rows:
        ps.upsert_member(ctx.conn, PROV, r["mid"], name=r["name"], surname=r["surname"],
                         given=r["given"], riding=r["riding"], party=r["caucus"],
                         sitting=(0 if r["former"] else 1)
                         if legislature == _current_legislature() else None)
        have = ctx.conn.execute(
            "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND member_key=? AND "
            "legislature=? AND source='member-page'", (PROV, r["mid"], legislature)).fetchone()[0]
        if have and not ctx.refresh:
            continue
        page_html = None if ctx.stop() else ctx.text(r["href"], "member-{0}".format(r["mid"]))
        page = parse_member_page(page_html) if page_html else None
        if page and page["affiliations"]:
            ps.replace_terms(ctx.conn, PROV, r["mid"], terms_from_page(page, legislature, r["riding"]),
                             "member-page")
            ps.replace_terms(ctx.conn, PROV, r["mid"], [], "roster")
            pages += 1
        else:
            # The listing alone: party and riding as listed, NOT dated.
            ps.replace_terms(ctx.conn, PROV, r["mid"], [{
                "legislature": legislature, "party": r["caucus"], "riding": r["riding"],
                "start": None, "end": None, "party_dated": 0}], "roster")
    ctx.conn.commit()
    ctx.log("  ab roster legl={0}: {1} member(s), {2} member page(s) read".format(
        legislature, len(rows), pages))
    return len(rows)


def _current_legislature():
    return parse_session(CURRENT_SESSION)[0]


# -- bills ------------------------------------------------------------------

_BILL_ITEM = re.compile(
    r'<a href="([^"]*bill\?billinfoid=(\d+)[^"]*)">Bill&nbsp;([^<]+)</a></div><div>([^<]*)</div>')


def parse_bill_list(html):
    """[{billinfoid, number, title, bill_type, href}]"""
    out = []
    parts = re.split(r'<div class="header">', html or "")
    for part in parts[1:]:
        kind = html_text(part[:part.find("</div>")])
        for href, bid, number, title in _BILL_ITEM.findall(part):
            out.append({"billinfoid": bid, "number": number.strip(),
                        "title": _html.unescape(title).strip().rstrip("*").strip(),
                        "bill_type": kind, "href": urljoin(BASE, _html.unescape(href))})
    return out


def parse_bill_page(html):
    """{title, sponsor, sponsor_mid, bill_type, text_url, stages: [{stage, date, status, hansard}]}"""
    def detail(label):
        m = re.search(r"<div>{0}</div>\s*<div>(.*?)</div></div>".format(label), html, re.S)
        return m.group(1) if m else None
    sponsor_html = detail("Sponsor") or ""
    mid = re.search(r"mid=(\d+)", sponsor_html)
    text = re.search(r'<div class="doc_item"><a[^>]*href="([^"]+\.pdf)"', html)
    stages = []
    for chunk in html.split('<div class="b_header">')[1:]:
        title = re.search(r'<div class="b_readingtitle">([^<]*)</div>', chunk)
        title = html_text(title.group(1)) if title else None
        # Entries only: the header row carries a 'rwd-show' span of its own
        # ("Transcript pages") that once stood in for the first date.
        for entry in chunk.split('<div class="b_entry">')[1:]:
            got = re.search(r'<div class="b_date"><span class="rwd-show">([^<]*)</span>.*?'
                            r'<div class="b_status">([^<]*)</div>\s*</div>\s*'
                            r'<div class="b_hansard">(.*?)</div>', entry, re.S)
            if not got:
                continue
            when, status, hansard = got.groups()
            date = _date(re.sub(r"\s+(am|pm|eve|morning|afternoon|evening)$", "", when.strip()),
                         ("%b %d, %Y", "%B %d, %Y"))
            link = re.search(r"href='([^']+)'", hansard) or re.search(r'href="([^"]+)"', hansard)
            stages.append({"stage": title, "date": date, "when": when.strip(),
                           "status": html_text(status), "hansard": link.group(1) if link else None})
    return {"title": html_text(detail("Title") or "").rstrip("*").strip() or None,
            "sponsor": html_text(sponsor_html) or None,
            "sponsor_mid": mid.group(1) if mid else None,
            "bill_type": html_text(detail("Type") or "") or None,
            "text_url": _html.unescape(text.group(1)) if text else None,
            "stages": stages}


def fetch_bills(ctx, legislature, session, tax, wl):
    html = ctx.text(BILLS.format(legislature, session), "bills-{0}-{1}".format(legislature, session))
    items = parse_bill_list(html) if html else []
    if html and not items:
        ctx.gap("ab bills {0}-{1}: no bills parsed from the listing".format(legislature, session))
    if ctx.dry_run:
        return {"bills": len(items)}
    read = texts = 0
    for it in items:
        key = ps.bill_key(PROV, legislature, session, it["number"])
        if ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("bill pages", read))
            break
        page_html = ctx.text(it["href"], "bill-{0}".format(it["billinfoid"]))
        if not page_html:
            continue
        page = parse_bill_page(page_html)
        read += 1
        text_read, body = 0, None
        have = ctx.conn.execute("SELECT text_read FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
        if page["text_url"] and (ctx.refresh or not (have and have[0])):
            raw = ctx.bytes(page["text_url"], "billtext-{0}".format(it["billinfoid"]))
            if raw:
                try:
                    body = pdf_text(raw)
                    text_read = 1
                    texts += 1
                except Unreadable as exc:
                    ctx.gap("{0}: bill text {1}: {2}".format(key, page["text_url"], exc))
        elif have and have[0]:
            text_read = None      # already classified on its text; keep that
        title = page["title"] or it["title"]
        record = {"bill_key": key, "prov": PROV, "legislature": legislature, "session": session,
                  "number": it["number"], "title_en": title, "sponsor": page["sponsor"],
                  "sponsor_key": page["sponsor_mid"], "bill_type": page["bill_type"] or it["bill_type"],
                  "is_government": 1 if (page["bill_type"] or it["bill_type"] or "").startswith("Government") else 0,
                  "stages": page["stages"], "page_url": it["href"], "text_url": page["text_url"]}
        latest = [s for s in page["stages"] if s["date"]]
        record["latest_stage"] = latest[-1]["stage"] if latest else None
        record["royal_assent"] = next((s["date"] for s in page["stages"] if s["stage"] == "Royal Assent"), None)
        if text_read is None:
            # text_read=0 never overwrites areas classified on the text
            ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
        else:
            res = pc.classify(tax, wl, PROV, title=title, texts=[body] if body else [], bill_key=key)
            ps.store_bill(ctx.conn, dict(record, text_read=text_read, areas=res.areas,
                                         matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
        store_voice_stages(ctx, key, legislature, session, page["stages"], it["href"])
    ctx.conn.commit()
    ctx.log("  ab bills {0}-{1}: {2} listed, {3} page(s) read, {4} text(s) read".format(
        legislature, session, len(items), read, texts))
    return {"bills": len(items), "bill_texts": texts}


def store_voice_stages(ctx, key, legislature, session, stages, page_url):
    """A stage the bill page marks plain "passed" was decided without a
    recorded division: stored as kind='voice', never as an empty roll-call."""
    areas, terms, tier = ps.bill_areas(ctx.conn, key)
    n = 0
    for s in stages:
        if s["stage"] not in STAGES or s["status"].lower() != "passed" or not s["date"] \
                or not ctx.in_window(s["date"]):
            continue
        ps.store_division(ctx.conn, {
            "division_key": ps.division_key(PROV, legislature, session, s["date"],
                                            "v{0}-{1}".format(key.rsplit("/", 1)[1], STAGE_CODE[s["stage"]])),
            "prov": PROV, "legislature": legislature, "session": session, "date": s["date"],
            "seq": "v", "kind": "voice", "bill_key": key, "stage": s["stage"],
            "result": "passed (bill page; no recorded division)", "source_url": page_url,
            "areas": areas, "matched_terms": terms, "tier": tier})
        n += 1
    return n


# -- Votes and Proceedings ----------------------------------------------------

HEADER = re.compile(r"^\s*(For|Against) the (motion|amendment|subamendment|sub-amendment)\s*:\s*(\d+)\s*$",
                    re.I)
_READ_A = re.compile(r"On the motion that the following Bills? be now read a (First|Second|Third) time", re.I)
_BILL_LINE = re.compile(r"^\s*Bill (\d+)\s+(.+?)\s+[—–-]\s+(?:Hon\.|Mr\.|Ms|Mrs\.|Dr\.|Member|MLA)")
_RESULT = re.compile(r"((?:the|which)\s[^.]{0,140}?\s(?:was|were)\s(?:agreed to|defeated|carried|negatived|lost))",
                     re.I)
def division_result(voice_text, yeas, nays, voice=False):
    """The outcome a RECORDED division decided (3 October 2026).

    Alberta's Votes and Proceedings prints the Speaker's VOICE-VOTE call first
    ("the amendment was agreed to on the voice vote") and then, when members
    demand a division, the names. The division decides the question, so the
    outcome comes from the printed totals; the voice-vote line is kept beside
    it. Storing the voice line alone recorded the government's 45-34 win on
    Bill 26's first reading as "defeated", and a 32-44 loss as "agreed to"."""
    subject = "question"
    if voice_text:
        m = re.search(r"\b(motion|amendment|subamendment|bill|clauses?)\b", voice_text, re.I)
        if m:
            subject = m.group(1).lower()
    if yeas is None or nays is None:
        return voice_text
    if yeas > nays:
        outcome = "carried"
    elif nays > yeas:
        outcome = "defeated"
    else:
        outcome = "tied (decided by the Chair)"
    out = "the {0} was {1} on division, {2}-{3}".format(subject, outcome, yeas, nays)
    if voice_text and (voice or "voice vote" in voice_text.lower()):
        out += " (voice vote before the division: {0})".format(voice_text)
    return out


_RESETS = {
    "introduction of bills": "First Reading", "second reading": "Second Reading",
    "third reading": "Third Reading", "committee of the whole": "Committee of the Whole",
    "government motions": "Motion", "motions other than government motions": "Motion",
    "written questions": None, "motions for returns": None, "private bills": None,
    "orders of the day": None, "ministerial statements": None, "members' statements": None,
    "presenting petitions": None, "tabling returns and reports": None, "adjournment": None,
    "emergency debate": "Motion",
}


def parse_vp(text, vocab):
    """Divisions in one day's V&P text, in order, names unresolved.

    [{seq, vote_on, yeas, nays, yea_labels, nay_labels, question, result,
      stage, bill_number, problem}]"""
    lines = (text or "").splitlines()
    tokens = pn.vocab_tokens(vocab)
    out, context = [], []
    stage = bill = None
    expect_bill = False
    i, n = 0, len(lines)

    def take(i):
        got = []
        while i < n:
            l = lines[i]
            if pn.is_furniture(l):
                i += 1
                continue
            if HEADER.match(l) or not pn.is_name_line(l, tokens):
                break
            got.append(l)
            i += 1
        return got, i

    while i < n:
        line = lines[i]
        m = HEADER.match(line)
        if m and m.group(1).lower() == "for":
            vote_on, yeas = m.group(2).lower(), int(m.group(3))
            yea_lines, i = take(i + 1)
            while i < n and pn.is_furniture(lines[i]):
                i += 1
            m2 = HEADER.match(lines[i]) if i < n else None
            problem, nays, nay_lines = None, None, []
            if m2 and m2.group(1).lower() == "against":
                nays = int(m2.group(3))
                nay_lines, i = take(i + 1)
            else:
                problem = "no 'Against the {0}' list after 'For the {0}: {1}'".format(vote_on, yeas)
            ctx_text = re.sub(r"\s+", " ", " ".join(context)).strip()
            results = _RESULT.findall(ctx_text)
            result = division_result(results[-1].strip() if results else None, yeas, nays,
                                     voice="on the voice vote" in ctx_text.lower())
            named = re.findall(r"\bBill (\d+)\b", ctx_text)
            out.append({
                "seq": len(out) + 1, "vote_on": vote_on, "yeas": yeas, "nays": nays,
                "yea_labels": pn.split_name_run(yea_lines, vocab),
                "nay_labels": pn.split_name_run(nay_lines, vocab),
                "question": ctx_text[-600:] or None,
                "result": result,
                "stage": stage, "bill_number": named[-1] if named else bill,
                "problem": problem})
            context = []
            continue
        stripped = line.strip()
        low = stripped.lower().rstrip(":")
        if low in _RESETS:
            stage, bill, expect_bill = _RESETS[low], None, low in ("introduction of bills", "committee of the whole")
        r = _READ_A.search(stripped)
        if r:
            stage, bill, expect_bill = r.group(1).title() + " Reading", None, True
        if "taken under consideration" in low or "requested leave to introduce" in low:
            expect_bill = True
        b = _BILL_LINE.match(stripped)
        if b and expect_bill:
            bill = b.group(1)
        if not pn.is_furniture(line):
            context.append(line)
        i += 1
    return out


def resolve_division(raw, resolver, date, legislature):
    """Votes with members resolved, and the tally verdict."""
    votes = []
    for position, labels in (("Yea", raw["yea_labels"]), ("Nay", raw["nay_labels"])):
        for k, label in enumerate(labels, 1):
            key, how = resolver.resolve(label, date, legislature)
            votes.append({"position": position, "ordinal": k, "raw_label": label,
                          "member_key": key, "how": how,
                          "party_at_vote": resolver.party_at(key, date, legislature) if key else None})
    ok, note = ps.tally({"Yea": raw["yeas"], "Nay": raw["nays"]}, votes)
    if raw.get("problem"):
        ok, note = False, "; ".join(x for x in (raw["problem"], note) if x)
    return votes, ok, note


def read_sitting(ctx, legislature, session, date, url, resolver, wl, vocab):
    """Read one V&P. Returns (divisions, gaps_in_it)."""
    raw = ctx.bytes(url, "vp-{0}".format(date))
    part = re.search(r"_(\d{2})_vp\.pdf$", url)
    part = part.group(1) if part and part.group(1) != "01" else None
    skey = ps.sitting_key(PROV, legislature, session, date, part)
    if raw is None:
        return 0, 1
    try:
        text = pdf_text(raw)
    except Unreadable as exc:
        ctx.gap("{0}: {1}: {2}".format(skey, url, exc))
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
        return 0, 1
    divisions = parse_vp(text, vocab)
    gaps = 0
    for d in divisions:
        votes, ok, note = resolve_division(d, resolver, date, legislature)
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        inherit = pc.Result(b_areas, b_terms, b_tier) if b_areas else None
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["question"]], bill_key=bkey, inherit=inherit)
        dkey = ps.division_key(PROV, legislature, session, date,
                               "{0}.{1}".format(part, d["seq"]) if part else d["seq"])
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": date, "seq": d["seq"], "kind": "recorded", "question": d["question"],
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "abstentions": None, "source_url": url,
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": note, "votes": votes})
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return len(divisions), gaps


def check_division_flags(ctx, legislature, session, read_dates):
    """The bill page's "passed on division" is a free index: every flagged
    stage on a day whose V&P was read must have a recorded division on that
    bill. A miss is a parse gap, said out loud."""
    misses = 0
    for key, stages in ctx.conn.execute(
            "SELECT bill_key, stages FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
            (PROV, legislature, session)).fetchall():
        for s in json.loads(stages or "[]"):
            if s.get("status", "").lower() != "passed on division" or s.get("date") not in read_dates:
                continue
            hit = ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? AND kind='recorded'",
                (key, s["date"])).fetchone()[0]
            if not hit:
                misses += 1
                ctx.gap("{0}: bill page says {1} on {2} passed on division; no recorded division "
                        "on that bill was parsed from that day's V&P".format(key, s["stage"], s["date"]))
    return misses


def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    legislature, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    stats = {}
    if roster:
        stats["members"] = fetch_roster(ctx, legislature)
    if bills:
        stats.update(fetch_bills(ctx, legislature, sess, ctx.tax, wl))
    listing = ctx.text(VP_LIST.format(legislature, sess), "vp-list-{0}-{1}".format(legislature, sess))
    records = sorted(r for r in list_records(listing or "") if ctx.in_window(r[0]))
    if listing and not list_records(listing):
        ctx.gap("ab V&P {0}: no records parsed from the listing".format(session))
    stats["records_listed"] = len(records)
    if ctx.dry_run:
        return stats
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    vocab = resolver.surname_vocab()
    read = divs = gaps = 0
    read_dates = set()
    for date, url in records:
        if not ctx.refresh and ps.sitting_done(ctx.conn, url):
            read_dates.add(date)
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        n, g = read_sitting(ctx, legislature, sess, date, url, resolver, wl, vocab)
        read += 1
        divs += n
        gaps += g
        if g == 0 or n:
            read_dates.add(date)
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps,
                  "flag_misses": check_division_flags(ctx, legislature, sess, read_dates) if bills else 0})
    ctx.conn.commit()
    return stats
