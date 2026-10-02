"""Legislative Assembly of Ontario: dated roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov on. Scope: docs/canada-provinces-scope.md
(Ontario: value 3, difficulty 2).

ACCESS. ola.org sits behind Akamai, which refuses a bot User-Agent without a
contact; the repo's standard UA (src/http.py, with its contact) passes, and
nothing else is used. robots.txt ends with a second `User-agent: *` group,
`Disallow: /*?`: NO QUERY-STRING URL IS EVER REQUESTED. The standard
library's robotparser cannot read that rule, which is why src/prov_fetch has
its own (prov_fetch.Robots); every URL this module builds or reads is a path.

  * SITTINGS. house-documents lists every session; a session's page lists
    each sitting day's document hub (".../2022-11-03/hansard"). The hub
    names the day's Votes and Proceedings (".../votes-proceedings", a
    suffix where a day has more than one) and the Hansard PDF. Both are
    taken from the hub, never constructed.
  * ROSTER, DATED TO THE DAY. Every Hansard PDF ends with the whole House AS
    AT THAT SITTING: "Lecce, Hon. / L'hon. Stephen (PC) King--Vaughan ...",
    in three columns (member and party, constituency, other
    responsibilities), with ridings that wrap and carry a French name after
    " / ". The columns are read by position (prov_fetch.pdf_fragments). For
    every day with a recorded division, that day's list is read and each
    member's term widened to exactly that day (prov_store.extend_term), as
    for Saskatchewan and Manitoba. Party at the vote is a fact of the day.
  * DIVISIONS. Votes and Proceedings, in two layouts:
      - since about 2022: bilingual two-column event tables, each division
        "<h5 class="divisionHeader">Ayes/pour (74)</h5>" over a votesList
        table, one surname per cell, a riding where two members share a
        surname ("Ford (Etobicoke North)"); since late 2025 the table's class
        is "table votesList" and each cell holds the name in an English and
        a hidden French div, of which only the English is read;
      - before: one table, English cell then French cell per row, the
        division as "AYES / POUR - 95" then name columns, and "AYES / POUR -
        Continued" where a list runs over a page.
    The printed totals are the tally check.
  * TOTALS ONLY. A dilatory motion's division is printed as "Carried on the
    following division -- Ayes 74, Nays 30" with no names (they are in
    Hansard, which is not read). Stored as recorded, positions_ok=0 and a
    tally_note that says why, so it places nobody; it is not a gap, because
    no re-read of the V&P can ever resolve it.
  * VOICE. "Carried." / "Lost." after a reading of a bill, and the day's
    lists of bills "introduced and read the first time", "read the second
    time" or "read the third time and were passed", are decisions without a
    recorded division: stored as kind='voice'. Bill 77 (2015, conversion
    practices) passed third reading this way: no member record exists.
  * BILLS. A session's bills page lists every bill. A bill's own page (about
    750 KB: it carries the text) is read only when the window's records name
    the bill, or the watchlist does -- not all three hundred. Its text is
    classified per passage, statute names masked.

THE ONE CONSTRUCTED URL is the session's bills listing
(/en/legislative-business/bills/parliament-N/session-M): no index page links
past sessions' listings except from inside a bill. It is a listing, not a
record; a wrong guess is a 404 and a gap, never a wrong record.

Hansard speeches are not read (scope "Built" notes).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text, pdf_fragments, slug

PROV = "on"
CURRENT_SESSION = "44-1"
BASE = "https://www.ola.org"
HOUSE_DOCS = BASE + "/en/legislative-business/house-documents"
BILLS = BASE + "/en/legislative-business/bills/parliament-{0}/session-{1}"


def parse_session(code):
    m = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("Ontario session must look like 44-1, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def bill_number(token):
    """'28' -> '28'; 'Pr14', 'pr14' -> 'Pr14'."""
    t = (token or "").strip()
    return "Pr" + t[2:] if t.lower().startswith("pr") else t


# -- listings ---------------------------------------------------------------

def session_page(index_html, legislature, session):
    m = re.search(r'href="(/en/legislative-business/house-documents/parliament-{0}/session-{1}/?)"'.format(
        legislature, session), index_html or "")
    return urljoin(BASE, m.group(1)) if m else None


def list_sittings(html, legislature, session):
    """[(date, hub_url)] in date order."""
    rx = re.compile(r'href="(/en/legislative-business/house-documents/parliament-{0}/session-{1}/'
                    r'(\d{{4}}-\d{{2}}-\d{{2}})/hansard)"'.format(legislature, session))
    out = {}
    for href, date in rx.findall(html or ""):
        out.setdefault(date, urljoin(BASE, href))
    return sorted(out.items())


def hub_documents(html, date):
    """(V&P urls, Hansard PDF url) named on a day's hub page."""
    vp = []
    for href in re.findall(r'href="([^"]*/{0}/votes-proceedings(?:-\d+)?)"'.format(re.escape(date)), html or ""):
        url = urljoin(BASE, href)
        if url not in vp and "/en/" in url:
            vp.append(url)
    pdf = re.search(r'href="(/sites/default/files/node-files/hansard/document/pdf/[^"]+\.pdf)"', html or "")
    return vp, (urljoin(BASE, pdf.group(1)) if pdf else None)


# -- the Hansard member list --------------------------------------------------

_PARTY = re.compile(r"\(([A-Z]{2,5})\)\s*$")


def _lines(frags):
    """[(y, [(x, text)])] top to bottom, fragments grouped by baseline."""
    rows = {}
    for _p, x, y, t in frags:
        rows.setdefault(y, []).append((x, t))
    return [(y, sorted(rows[y])) for y in sorted(rows, reverse=True)]


def parse_member_pages(frags):
    """members [{surname, given, party, riding, key}] from the positioned
    text of the Hansard's member-list pages (pdf_fragments)."""
    members = []
    by_page = {}
    for f in frags:
        by_page.setdefault(f[0], []).append(f)
    for page in sorted(by_page):
        fr = by_page[page]
        head = [f for f in fr if f[3].strip().startswith("Member and Party")]
        if not head:
            continue
        top = min(f[2] for f in head) - 12          # below 'Député(e) et parti'
        body = [f for f in fr if f[2] < top]
        starts = Counter(round(f[1]) for f in body)
        cols = sorted(x for x, _n in starts.most_common(3))
        if len(cols) < 2:
            continue
        c_riding = cols[1] - 2
        c_other = cols[2] - 2 if len(cols) > 2 else 10 ** 6
        cur = None
        for _y, parts in _lines(body):
            mem = "".join(t for x, t in parts if x < c_riding).strip()
            rid = "".join(t for x, t in parts if c_riding <= x < c_other).strip()
            if mem and ("," in mem.split("(")[0] or mem.startswith("Vacant")):
                cur = {"member": mem, "riding": [rid] if rid else []}
                members.append(cur)
            elif cur is not None:
                if mem:
                    cur["member"] += " " + mem
                if rid:
                    cur["riding"].append(rid)
    out = []
    for m in members:
        text = re.sub(r"\s+", " ", m["member"]).strip()
        party = _PARTY.search(text)
        if text.startswith("Vacant") or not party:
            continue
        sur, _, rest = text[:party.start()].partition(",")
        rest = re.sub(r"Hon\.\s*/\s*L[’']hon\.|\bHon\.", " ", rest)
        given = re.sub(r"\([^()]*\)", " ", rest)          # 'Jennifer (Jennie)'
        given = re.sub(r"\s+", " ", given).strip()
        riding = " ".join(m["riding"]).split("/")[0]
        riding = re.sub(r"\s+", " ", riding).strip(" -—–") or None
        surname = sur.strip()
        out.append({"surname": surname, "given": given, "party": party.group(1),
                    "riding": riding, "key": slug(given + " " + surname)})
    return out


def roster_for_day(ctx, legislature, date, pdf_url):
    have = ctx.conn.execute(
        "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source='hansard-cover' "
        "AND start<=? AND end>=?", (PROV, date, date)).fetchone()[0]
    if have and not ctx.refresh:
        return have
    if not pdf_url:
        ctx.gap("on {0}: no Hansard PDF on the day's hub, so no roster as at the day".format(date))
        return 0
    raw = ctx.bytes(pdf_url, "hansard-{0}".format(date))
    if not raw:
        return 0
    try:
        frags = pdf_fragments(raw, pages=range(-16, 0), want="Member and Party")
    except Unreadable as exc:
        ctx.gap("on {0}: Hansard {1}: {2}".format(date, pdf_url, exc))
        return 0
    members = parse_member_pages(frags)
    if len(members) < 90:
        ctx.gap("on {0}: only {1} member(s) parsed from the Hansard member list {2}".format(
            date, len(members), pdf_url))
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

_NEW_HEAD = re.compile(r"^(Ayes|Nays)\s*/\s*(?:pour|contre)\s*\((\d+)\)\s*$", re.I)
_OLD_HEAD = re.compile(r"^(AYES|NAYS)\s*/\s*(?:POUR|CONTRE)\s*[-–—]\s*(\d+|Continued)\s*$", re.I)
_PARA = re.compile(r"<(p|h\d)\b[^>]*>(.*?)</\1>", re.S | re.I)


def _paras(fragment):
    out = []
    for tag, body in _PARA.findall(fragment or ""):
        t = html_text(body)
        if t:
            out.append(("h" if tag.lower().startswith("h") else "p", t))
    return out


def _cell_name(cell):
    """One member's label from a votesList cell. Since late 2025 each cell
    carries the name twice, '<div lang="en">Bell</div><div class="docHide"
    lang="fr">Bell</div>': only the English div is read, or every name
    would be read as 'Bell Bell' (measured live on 24 November 2025)."""
    en = re.search(r'<div[^>]*\blang="en"[^>]*>(.*?)</div>', cell, re.S)
    return html_text(en.group(1) if en else cell)


def vp_events(html):
    """[('h'|'p', text) | ('list', 'Yea'|'Nay', total, [labels])] in order."""
    html = html or ""
    events = []
    if "votesProceedingsDoc2col" in html or "divisionHeader" in html:
        rx = re.compile(r'<td class="votesProceedingsDoc2col" lang="en">(.*?)</td>|'
                        r'<h5 class="divisionHeader">(.*?)</h5>'
                        r'(?:\s*<table class="[^"]*\bvotesList\b[^"]*">(.*?)</table>)?',
                        re.S)
        for m in rx.finditer(html):
            if m.group(1) is not None:
                events.extend(_paras(m.group(1)))
                continue
            h = _NEW_HEAD.match(html_text(m.group(2)))
            # A nil list ("Nays/contre (0)", late 2025) is a header with no table.
            names = [_cell_name(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(3) or "", re.S)]
            names = [n for n in names if n]
            if h:
                events.append(("list", "Yea" if h.group(1).lower() == "ayes" else "Nay",
                               int(h.group(2)), names))
            else:
                events.append(("p", html_text(m.group(2))))
        return events
    # The older single-table layout.
    start = html.find("PRAYERS")
    body = html[max(0, html.rfind("<table", 0, start)) if start > 0 else 0:]
    # Rows hold an English cell then its French twin; a division is a header
    # row ("AYES / POUR - 95", "... - Continued") then rows of name columns.
    # Cell widths vary (colspan 2, 4, 5, 6, empty <td/> spacers), so rows are
    # told apart by what they hold, not by their attributes.
    body = re.sub(r"<td\b[^>]*/>", "", body)
    current = None
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body, re.S | re.I):
        cells = [_paras(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)]
        cells = [c for c in cells if c]
        if not cells:
            continue                      # a spacer row; it never ends a list
        first = cells[0]
        if len(first) == 1 and _OLD_HEAD.match(first[0][1]):
            h = _OLD_HEAD.match(first[0][1])
            pos = "Yea" if h.group(1).upper() == "AYES" else "Nay"
            if h.group(2).lower() == "continued" and current is not None and current[1] == pos:
                continue
            current = ["list", pos, int(h.group(2)) if h.group(2).isdigit() else None, []]
            events.append(current)
            continue
        texts = [t for c in cells for _k, t in c]
        if current is not None and all(_NAME.match(t) for t in texts):
            current[3].extend(texts)
            continue
        current = None
        events.extend(first)
    return [tuple(e) for e in events]


_NAME = re.compile(r"^[A-ZÀ-Ý][\w'’\-]*(?: [A-ZÀ-Ý][\w'’\-]*)*(?: \([^()]+\))?$")


_READING = re.compile(r"^(First|Second|Third) Reading of Bill (Pr\d+|\d+)\b", re.I)
_TIME_ALLOC = re.compile(r"allocation of time on Bill (Pr\d+|\d+)", re.I)
_BILL_ITEM = re.compile(r"^Bill (Pr\d+|\d+), (.+)$")
_RESULT = re.compile(r"^(Carried|Lost|Negatived|Defeated) on the following division", re.I)
_TOTALS_ONLY = re.compile(r"^(Carried|Lost|Negatived|Defeated) on the following division\s*[–—-]+\s*"
                          r"Ayes\s*(\d+),\s*Nays\s*(\d+)", re.I)
_MASS = re.compile(r"^The following (?:bills|Bills) were (introduced and read the first time|"
                   r"read the second time|read the third time)", re.I)
_VOICE = re.compile(r"^(Carried|Lost|Negatived|Defeated)\.$", re.I)


def parse_vp(events):
    """(divisions, voices, titles) from vp_events. Names unresolved.

    divisions: [{seq, yeas, nays, yea_labels, nay_labels, question, result,
                 stage, bill_number, vote_on, totals_only, problem}]"""
    divisions, voices, titles = [], [], {}
    stage = bill = None
    context = []
    mass = None
    i, n = 0, len(events)
    while i < n:
        e = events[i]
        if e[0] == "list":
            lists = {}
            while i < n and events[i][0] == "list":
                lists.setdefault(events[i][1], events[i])
                i += 1
            ctx_text = " ".join(context)
            res = [m.group(0) for m in map(_RESULT.match, context) if m]
            yea, nay = lists.get("Yea"), lists.get("Nay")
            problem = None if (yea and nay) else "an Ayes or Nays list is missing"
            if (yea and yea[2] is None) or (nay and nay[2] is None):
                problem = "a list has no printed total"
            divisions.append({
                "seq": len(divisions) + 1, "yeas": yea[2] if yea else None,
                "nays": nay[2] if nay else None,
                "yea_labels": list(yea[3]) if yea else [], "nay_labels": list(nay[3]) if nay else [],
                "question": ctx_text[-700:] or None, "result": res[-1] if res else None,
                "stage": stage or "Motion", "bill_number": bill,
                "vote_on": "amendment" if re.search(r"\bbe amended\b|\bon the amendment\b|"
                                                    r"\bamendment to the motion\b", ctx_text, re.I)
                           else "motion",
                "totals_only": False, "problem": problem})
            context = []
            mass = None
            continue
        kind, text = e
        i += 1
        if kind == "h":
            stage = bill = None
            mass = None
            context = [text]
            continue
        m = _MASS.match(text)
        if m:
            w = m.group(1).lower()
            mass = "First Reading" if "first" in w else "Second Reading" if "second" in w else "Third Reading"
            continue
        b = _BILL_ITEM.match(text)
        if mass and b:
            num = bill_number(b.group(1))
            titles.setdefault(num, b.group(2).split(". ")[0].strip(" ."))
            voices.append({"bill_number": num, "stage": mass, "result": "read the {0} time".format(
                mass.split()[0].lower())})
            continue
        mass = None
        r = _READING.match(text)
        if r:
            stage, bill = r.group(1).title() + " Reading", bill_number(r.group(2))
            title = text[r.end():].lstrip(" ,").strip(" .")
            if title:
                titles.setdefault(bill, title)
            context = [text]
            continue
        t = _TIME_ALLOC.search(text)
        if t:
            stage, bill = "Time Allocation", bill_number(t.group(1))
            context = [text]
            continue
        if re.search(r"\bmoved,?$", text) or text.startswith("Private Members' Notice of Motion"):
            stage, bill = "Motion", None
            context = [text]
            continue
        tot = _TOTALS_ONLY.match(text)
        if tot:
            divisions.append({
                "seq": len(divisions) + 1, "yeas": int(tot.group(2)), "nays": int(tot.group(3)),
                "yea_labels": [], "nay_labels": [], "question": " ".join(context)[-700:] or None,
                "result": tot.group(0), "stage": stage or "Motion", "bill_number": bill,
                "vote_on": "motion", "totals_only": True, "problem": None})
            context = []
            continue
        v = _VOICE.match(text)
        if v and bill and stage in ("Second Reading", "Third Reading"):
            voices.append({"bill_number": bill, "stage": stage, "result": text})
            stage = None
            context = []
            continue
        context.append(text)
    seen, unique = set(), []
    for v in voices:
        k = (v["bill_number"], v["stage"])
        if k not in seen:
            seen.add(k)
            unique.append(v)
    return divisions, unique, titles


def resolve_division(raw, resolver, date, legislature):
    votes = []
    for position, labels in (("Yea", raw["yea_labels"]), ("Nay", raw["nay_labels"])):
        for k, label in enumerate(labels, 1):
            key, how = resolver.resolve(label, date, legislature)
            votes.append({"position": position, "ordinal": k, "raw_label": label, "member_key": key,
                          "how": how,
                          "party_at_vote": resolver.party_at(key, date, legislature) if key else None})
    if raw.get("totals_only"):
        return votes, False, ("totals only: the V&P prints no names for this division (a dilatory "
                              "motion); the names are in Hansard, which is not read")
    ok, note = ps.tally({"Yea": raw["yeas"], "Nay": raw["nays"]}, votes)
    if raw.get("problem"):
        ok, note = False, "; ".join(x for x in (raw["problem"], note) if x)
    return votes, ok, note


def read_vp(ctx, legislature, session, date, part, url, pdf_url, wl, named):
    """Read one V&P page. Returns (divisions, gaps_in_it)."""
    html = ctx.text(url, "vp-{0}".format(date))
    skey = ps.sitting_key(PROV, legislature, session, date, part)
    if html is None:
        return 0, 1
    events = vp_events(html)
    if not events:
        ctx.gap("{0}: {1}: no proceedings parsed".format(skey, url))
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
        return 0, 1
    divisions, voices, titles = parse_vp(events)
    expected = len(re.findall(r"on the following division", " ".join(e[1] for e in events if e[0] == "p"),
                              re.I))
    gaps = 0
    if any(not d["totals_only"] for d in divisions):
        roster_for_day(ctx, legislature, date, pdf_url)
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    for number, title in titles.items():
        key = ps.bill_key(PROV, legislature, session, number)
        named.add(number)
        if ctx.conn.execute("SELECT 1 FROM prov_bills WHERE bill_key=?", (key,)).fetchone():
            continue                 # the bill page's title is better than the V&P's
        res = pc.classify(ctx.tax, wl, PROV, title=title, bill_key=key)
        ps.store_bill(ctx.conn, {"bill_key": key, "prov": PROV, "legislature": legislature,
                                 "session": session, "number": number, "title_en": title,
                                 "areas": res.areas, "matched_terms": res.terms, "tier": res.tier,
                                 "excerpt": res.excerpt})
    if expected != len(divisions):
        gaps += 1
        ctx.gap("{0}: the record says 'on the following division' {1} time(s) but {2} division(s) "
                "were parsed".format(skey, expected, len(divisions)))
    for d in divisions:
        if d["bill_number"]:
            named.add(d["bill_number"])
        votes, ok, note = resolve_division(d, resolver, date, legislature)
        bkey = ps.bill_key(PROV, legislature, session, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["question"]], bill_key=bkey,
                          inherit=pc.Result(b_areas, b_terms, b_tier) if b_areas else None)
        seq = "{0}.{1}".format(part, d["seq"]) if part else d["seq"]
        dkey = ps.division_key(PROV, legislature, session, date, seq)
        if not ok and not d["totals_only"]:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": date, "seq": seq, "kind": "recorded", "question": d["question"],
            "vote_on": d["vote_on"], "bill_key": bkey, "stage": d["stage"], "result": d["result"],
            "yeas": d["yeas"], "nays": d["nays"], "source_url": url, "areas": res.areas,
            "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": note, "votes": votes})
    for v in voices:
        named.add(v["bill_number"])
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

def parse_bill_list(html, legislature, session):
    """{number: (url, title)} from a session's bills page."""
    rx = re.compile(r'href="(/en/legislative-business/bills/parliament-{0}/session-{1}/bill-(pr\d+|\d+))"'
                    r'[^>]*>([^<]*)<'.format(legislature, session), re.I)
    out = {}
    for href, num, title in rx.findall(html or ""):
        out.setdefault(bill_number(num), (urljoin(BASE, href), html_text(title) or None))
    return out


def parse_bill_page(html):
    """{title, sponsor, sponsor_slug, status, text, pdf}"""
    s = html or ""
    title = re.search(r'<h1 class="bill-title">(.*?)</h1>', s, re.S)
    sponsor = re.search(r'<div class="bill-sponsors">.*?<a href="/en/members/all/([^"]+)">(.*?)</a>', s, re.S)
    status = re.search(r'views-field-field-current-status-1"><span class="field-content">(.*?)</span>', s, re.S)
    body = re.search(r'<div class="views-field views-field-body[^"]*bill-body"><div class="field-content">'
                     r'(.*?)(?=<div class="views-field views-field-body|<div class="lao-tab-content|$)', s, re.S)
    pdf = re.search(r'href="(/sites/default/files/node-files/bill/document/pdf/[^"]+\.pdf)"', s)
    text = None
    if body:
        chunk = re.sub(r"</(p|tr|h\d|li|div)>", "\n\n", body.group(1), flags=re.I)
        text = "\n".join(html_text(p) for p in chunk.split("\n\n") if html_text(p)) or None
    return {"title": html_text(title.group(1)) if title else None,
            "sponsor": html_text(sponsor.group(2)) if sponsor else None,
            "sponsor_slug": sponsor.group(1) if sponsor else None,
            "status": html_text(status.group(1)) if status else None,
            "text": text, "pdf": urljoin(BASE, pdf.group(1)) if pdf else None}


def fetch_bills(ctx, legislature, session, wl, wanted):
    """Read the bill pages of `wanted` numbers (named by this run's records
    or watched). Returns (listed, read)."""
    watched = [k.rsplit("/", 1)[1] for k in ((pc._raw().get("provinces") or {}).get(PROV, {}).get("bills") or {})
               if k.startswith("{0}-{1}-{2}/".format(PROV, legislature, session))]
    wanted = set(wanted) | set(watched)
    if not wanted:
        return 0, 0
    url = BILLS.format(legislature, session)
    html = ctx.text(url, "bills-{0}-{1}".format(legislature, session))
    listing = parse_bill_list(html, legislature, session) if html else {}
    if html and not listing:
        ctx.gap("on bills {0}-{1}: no bills parsed from {2}".format(legislature, session, url))
    read = 0
    for number in sorted(wanted, key=lambda x: (not x[0].isdigit(), int(re.sub(r"\D", "", x) or 0))):
        key = ps.bill_key(PROV, legislature, session, number)
        have = ctx.conn.execute("SELECT text_read FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
        if have and have[0] and not ctx.refresh:
            continue
        if number not in listing:
            if listing:
                ctx.gap("{0}: named in the record but not on the session's bills page".format(key))
            continue
        if ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("bill pages", read))
            break
        page_url, list_title = listing[number]
        page_html = ctx.text(page_url, "bill-{0}-{1}-{2}".format(legislature, session, number))
        if not page_html:
            continue
        page = parse_bill_page(page_html)
        read += 1
        title = page["title"] or list_title
        if title:
            title = re.sub(r"^Bill (?:Pr)?\d+,\s*", "", title)
        sponsor_key = None
        if page["sponsor_slug"] and ctx.conn.execute(
                "SELECT 1 FROM prov_members WHERE prov=? AND member_key=?", (PROV, page["sponsor_slug"])).fetchone():
            sponsor_key = page["sponsor_slug"]
        res = pc.classify(ctx.tax, wl, PROV, title=title, texts=[page["text"]] if page["text"] else [],
                          bill_key=key)
        ps.store_bill(ctx.conn, {
            "bill_key": key, "prov": PROV, "legislature": legislature, "session": session,
            "number": number, "title_en": title, "sponsor": page["sponsor"], "sponsor_key": sponsor_key,
            "is_government": 1 if (page["sponsor"] or "").startswith("Hon.") or ", Hon." in (page["sponsor"] or "")
            else 0, "latest_stage": page["status"], "page_url": page_url, "text_url": page["pdf"] or page_url,
            "text_read": 1 if page["text"] else 0, "areas": res.areas, "matched_terms": res.terms,
            "tier": res.tier, "excerpt": res.excerpt})
        if not page["text"]:
            ctx.gap("{0}: no bill text on {1}".format(key, page_url))
        # Divisions and voice decisions on the bill inherit its text areas.
        for dkey, kind, question in ctx.conn.execute(
                "SELECT division_key, kind, question FROM prov_divisions WHERE bill_key=?", (key,)).fetchall():
            d_res = pc.classify(ctx.tax, wl, PROV, texts=[question] if question else [], bill_key=key,
                                inherit=pc.Result(res.areas, res.terms, res.tier) if res.areas else None)
            ctx.conn.execute("UPDATE prov_divisions SET areas=?, matched_terms=?, tier=? WHERE division_key=?",
                             (json.dumps(d_res.areas), json.dumps(d_res.terms), d_res.tier, dkey))
    ctx.conn.commit()
    ctx.log("  on bills {0}-{1}: {2} listed, {3} page(s) read".format(legislature, session, len(listing), read))
    return len(listing), read


# -- the run ----------------------------------------------------------------

def _day_done(conn, legislature, session, date):
    key = ps.sitting_key(PROV, legislature, session, date)
    rows = conn.execute("SELECT status FROM prov_sittings WHERE sitting_key=? OR sitting_key LIKE ?",
                        (key, key + "-%")).fetchall()
    return bool(rows) and all(r[0] == "ok" for r in rows)


def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    legislature, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    stats = {}
    index = ctx.text(HOUSE_DOCS, "house-documents")
    s_url = session_page(index, legislature, sess) if index else None
    if index and not s_url:
        ctx.gap("on: session {0} is not on {1}".format(session, HOUSE_DOCS))
    page = ctx.text(s_url, "sittings-{0}".format(session)) if s_url else None
    sittings = [s for s in list_sittings(page, legislature, sess) if ctx.in_window(s[0])] if page else []
    if page and not list_sittings(page, legislature, sess):
        ctx.gap("on {0}: no sitting days parsed from {1}".format(session, s_url))
    stats["records_listed"] = len(sittings)
    if ctx.dry_run:
        return stats
    named = set()
    read = divs = gaps = 0
    for date, hub in sittings:
        if not ctx.refresh and _day_done(ctx.conn, legislature, sess, date):
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        hub_html = ctx.text(hub, "hub-{0}".format(date))
        if hub_html is None:
            gaps += 1
            continue
        vps, pdf_url = hub_documents(hub_html, date)
        if not vps:
            ctx.gap("on {0}: the day's hub {1} names no Votes and Proceedings".format(date, hub))
            gaps += 1
            continue
        for k, url in enumerate(vps):
            n, g = read_vp(ctx, legislature, sess, date, str(k + 1) if k else None, url,
                           pdf_url if roster else None, wl, named)
            read += 1
            divs += n
            gaps += g
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps})
    if bills:
        listed, pages = fetch_bills(ctx, legislature, sess, wl, named)
        stats.update({"bills_listed": listed, "bill_pages": pages})
    ctx.conn.commit()
    return stats
