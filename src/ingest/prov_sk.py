"""Legislative Assembly of Saskatchewan: dated roster and recorded divisions.

Driven by tools/prov_collect.py --prov sk. Scope: docs/canada-provinces-scope.md
(Saskatchewan: value 5, difficulty 2, 3 for the PDF backfill). www returns
404 for robots.txt and docs.legassembly.sk.ca is an Azure blob with none:
no rules. No WAF.

  * LISTING. The Legislative Meeting Archive, filtered to the Assembly and a
    date range (?Start=&End=&Committee=280140000), lists each sitting day's
    Minutes, Debates and Orders with their real file names. The names are
    taken from it, never constructed: two path roots, YYMMDD in the 29th
    Legislature and YYYYMMDD in the 30th, "Revised" and "-HTML" suffixes,
    and a prorogation day (25 Oct 2023) that carries Minutes for TWO sessions.
  * ROSTER, DATED TO THE DAY. The Assembly's MLA page lists only current
    members, by caucus ("Government Caucus"), not party. Every Hansard PDF
    instead prints, on its second page, the full member list AS AT THAT
    SITTING with constituency and party ("Wilson, Nadine -- Saskatchewan
    Rivers (Ind.)") and the standings. So for every day that has a recorded
    division, that day's Hansard cover is read and each member's term is
    widened to cover exactly that day (prov_store.extend_term). Party at the
    vote is then a fact of the day. The standings are the roster's own
    tally check.
  * DIVISIONS. Minutes ("Votes and Proceedings"). From the 30th Legislature
    an HTML edition (Word export, windows-1252) prints each recorded division
    as a table with one full name per paragraph ("Scott Moe"). Before it, the
    PDF is bilingual and two-column in its prose, but the name lists run
    across the page as surnames, with ridings that wrap ("Ross (Regina /
    Rochdale)"): the shared column-run splitter handles them.
  * VOICE. "it was agreed to and the said bill was accordingly read a second
    time" is a decision without a recorded division; stored as kind='voice'.

Bills: no per-bill page exists (progress-of-bills is a session PDF), so a
bill row is made from the Minutes' own "Bill No. 137 -- <title>" lines and
classified on its title, the watchlist key and the division's text. Bill
text and the progress PDF are not read yet (scope "Built" notes).
"""

from __future__ import annotations

import datetime
import html as _html
import re
from urllib.parse import urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text, pdf_text, slug

PROV = "sk"
CURRENT_SESSION = "30-2"
BASE = "https://www.legassembly.sk.ca"
ARCHIVE = BASE + "/legislative-business/archive/?Start={0}&End={1}&Committee=280140000"
DEFAULT_WINDOW_DAYS = 60
LISTING_PAGE_CAP = 60          # per calendar-year window of the archive listing
# The archive lists records by DATE across every session, so a window needs
# no session list: tools/prov_collect.py --all-sessions passes the window on.
DATE_DRIVEN = True


def year_windows(since, until):
    """[(since, until)] cut at each 31 December: '2010-03-01'..'2011-06-30'
    is two windows."""
    out, lo = [], since
    while lo <= until:
        hi = min(until, "{0}-12-31".format(lo[:4]))
        out.append((lo, hi))
        lo = "{0}-01-01".format(int(lo[:4]) + 1)
    return out

_SESSION_IN_PATH = re.compile(r"/(\d{2})L(\d)S/")


def parse_session(code):
    m = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("Saskatchewan session must look like 30-2, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


# -- listing ----------------------------------------------------------------

_CARD = re.compile(r'<a data-bs-toggle="collapse" href="#(\d{8})">')
_DOC = re.compile(r'<span>([^(<]+?)\s*\((.*?)</span>', re.S)


def list_records(html):
    """[{date, legislature, session, kind, minutes_pdf, minutes_html, debates}]
    one per Minutes entry; `debates` is that day's Hansard PDF in the SAME
    session, for the cover roster."""
    out = []
    marks = [(m.start(), m.group(1)) for m in _CARD.finditer(html or "")]
    for idx, (pos, ymd) in enumerate(marks):
        body = html[pos:marks[idx + 1][0] if idx + 1 < len(marks) else len(html)]
        date = "{0}-{1}-{2}".format(ymd[:4], ymd[4:6], ymd[6:])
        docs = []
        for label, links in _DOC.findall(body):
            hrefs = [_html.unescape(h) for h in re.findall(r'href="([^"]+)"', links)]
            docs.append((label.strip(), hrefs))
        # THE PRE-2023 LAYOUT (measured 2 October 2026 on a November 2015
        # page): a bare <a href=".../Minutes/27L4S/151126Minutes.pdf">Minutes</a>
        # with no "<span>Minutes (" wrapper, which _DOC never matched -- so a
        # backfill read NOTHING before 2023 and logged no gap. Such links are
        # taken by their path, as prov_sk_hansard.list_debates does.
        if not any(label.startswith("Minutes") for label, _ in docs):
            bare = [_html.unescape(h) for h in re.findall(r'href="([^"]+)"', body)]
            for label, part in (("Minutes", "/Minutes/"), ("Debates", "/Debates/")):
                hs = [h for h in bare if part in h and _SESSION_IN_PATH.search(h)]
                if hs:
                    docs.append((label, hs))
        debates = [h for label, hs in docs if label.startswith("Debates") for h in hs
                   if h.lower().endswith(".pdf")]
        for label, hrefs in docs:
            if not label.startswith("Minutes"):
                continue
            pdf = next((h for h in hrefs if h.lower().endswith(".pdf")), None)
            htm = next((h for h in hrefs if h.lower().endswith(".htm")), None)
            m = _SESSION_IN_PATH.search(pdf or htm or "")
            if not m:
                continue
            leg, sess = int(m.group(1)), int(m.group(2))
            same = [d for d in debates if "/{0}L{1}S/".format(leg, sess) in d]
            out.append({"date": date, "legislature": leg, "session": sess, "label": label,
                        "minutes_pdf": pdf, "minutes_html": htm,
                        "debates": same[0] if same else None})
    return out


def next_page(html):
    m = re.search(r'<a class="[^"]*page-link[^"]*" href="([^"]+)" rel="next">', html or "")
    return urljoin(BASE, _html.unescape(m.group(1))) if m else None


# -- the Hansard cover roster ----------------------------------------------

_COVER = re.compile(r"^\s*(?P<sur>[^,—]+?),\s*(?P<given>[^—]+?)\s+[—–]\s+"
                    r"(?P<riding>.+?)\s+\((?P<party>[^()]+)\)\s*$")


def parse_cover(text):
    """(members, standings_total) from a Hansard PDF's second page.
    members: [{surname, given, riding, party, key}]"""
    lines = (text or "").splitlines()
    joined, buf = [], ""
    for l in lines:
        s = l.strip()
        if buf:
            s = buf + " " + s
            buf = ""
        if "—" in s and "," in s.split("—")[0] and not s.endswith(")"):
            buf = s          # wrapped riding: join the next line
            continue
        joined.append(s)
    members = []
    for s in joined:
        m = _COVER.match(s)
        if not m or s.startswith(("Speaker", "Premier", "Leader", "Lieutenant", "Clerk")):
            continue
        given = " ".join(t for t in m.group("given").split() if pn.fold(t).rstrip(".") not in pn.HONORIFICS)
        surname = m.group("sur").strip()
        members.append({"surname": surname, "given": given, "riding": m.group("riding").strip(),
                        "party": m.group("party").strip(), "key": slug(given + " " + surname)})
    stand = re.search(r"Standings(.*?)(?:Clerks|$)", text or "", re.S)
    total = sum(int(n) for n in re.findall(r"\)\s*[—–-]\s*(\d+)", stand.group(1))) if stand else None
    return members, total


def roster_for_day(ctx, rec):
    """Read the day's Hansard cover and widen every member's term to it."""
    url = rec["debates"]
    if not url:
        ctx.gap("sk {0}: no Hansard PDF listed for the day, so no roster as at the day".format(rec["date"]))
        return 0
    have = ctx.conn.execute(
        "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source='hansard-cover' "
        "AND start<=? AND end>=?", (PROV, rec["date"], rec["date"])).fetchone()[0]
    if have and not ctx.refresh:
        return have
    raw = ctx.bytes(url, "debates-{0}".format(rec["date"]))
    if not raw:
        return 0
    try:
        text = pdf_text(raw, pages=[1, 2])
    except Unreadable as exc:
        ctx.gap("sk {0}: Hansard cover {1}: {2}".format(rec["date"], url, exc))
        return 0
    members, total = parse_cover(text)
    if not members:
        ctx.gap("sk {0}: no members parsed from the Hansard cover {1}".format(rec["date"], url))
        return 0
    if total is not None and total != len(members):
        ctx.gap("sk {0}: Hansard cover lists {1} member(s), standings say {2}".format(
            rec["date"], len(members), total))
    # The newest cover read is the sitting list: members on it are sitting,
    # everyone else held only on older covers is former. An older cover
    # (a backfill) never changes that.
    newest = ctx.conn.execute("SELECT MAX(end) FROM prov_member_terms WHERE prov=? AND "
                              "source='hansard-cover'", (PROV,)).fetchone()[0]
    is_newest = newest is None or rec["date"] >= newest
    if is_newest:
        ctx.conn.execute("UPDATE prov_members SET sitting=0 WHERE prov=?", (PROV,))
    for m in members:
        ps.upsert_member(ctx.conn, PROV, m["key"], name=m["given"] + " " + m["surname"],
                         surname=m["surname"], given=m["given"],
                         riding=m["riding"] if is_newest else None,
                         party=m["party"] if is_newest else None,
                         sitting=1 if is_newest else None)
        ps.extend_term(ctx.conn, PROV, m["key"], rec["legislature"], m["party"], m["riding"],
                       rec["date"], "hansard-cover")
    ctx.conn.commit()
    return len(members)


# -- Minutes ------------------------------------------------------------------

HEADER = re.compile(r"^\s*(YEAS|NAYS)(?:\s*/\s*(?:POUR|CONTRE))?\s*[—–-]+\s*(\d+|Nil)\s*$", re.I)
_BILL = re.compile(r"Bill No\.\s*(\d+)\s*[—–-]\s*(.+?)"
                   r"(?=\s+(?:be now read|Projet de loi|/|Moved|The Hon|The Assembly|\[)|\s*$)")
_STAGE = re.compile(r"read (?:a|the)\s+(first|second|third)\s+time", re.I)
_RESULT = re.compile(r"it was (agreed to|negatived)", re.I)
_VOICE = re.compile(r"it was (agreed to|negatived) and the said bill was accordingly read (?:a|the)\s+"
                    r"(first|second|third)\s+time", re.I)
_PUT_ON = re.compile(r"question being put on the (motion as amended|motion|amendment|subamendment|sub-amendment)",
                     re.I)


def _n(v):
    return 0 if v.lower() == "nil" else int(v)


def blocks_from_html(text):
    """[('h'|'p', text) | ('div', [(header, [names])])] in document order."""
    out = []
    pos = 0
    for m in re.finditer(r"<table.*?</table>", text, re.S | re.I):
        out.extend(_paras(text[pos:m.start()]))
        cols = []
        for td in re.findall(r"<td.*?</td>", m.group(0), re.S | re.I):
            ps_ = [html_text(p) for p in re.findall(r"<p.*?</p>", td, re.S | re.I)]
            ps_ = [p for p in ps_ if p]
            if ps_ and HEADER.match(ps_[0]):
                cols.append((ps_[0], ps_[1:]))
        if cols:
            out.append(("div", cols))
        else:
            out.extend(_paras(m.group(0)))
        pos = m.end()
    out.extend(_paras(text[pos:]))
    return out


def _paras(fragment):
    out = []
    for tag, body in re.findall(r"<(h\d|p)\b[^>]*>(.*?)</\1>", fragment, re.S | re.I):
        t = html_text(body)
        if t:
            out.append(("h" if tag.lower().startswith("h") else "p", t))
    return out


def blocks_from_pdf(text, vocab):
    """The 29th-Legislature PDF as blocks: an all-caps line is a heading, a
    YEAS/NAYS header opens a name run, everything else is prose."""
    lines = (text or "").splitlines()
    tokens = pn.vocab_tokens(vocab)
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i].strip()
        h = HEADER.match(line)
        if h:
            cols = []
            while i < n and HEADER.match(lines[i].strip()):
                head = lines[i].strip()
                i += 1
                got = []
                while i < n:
                    l = lines[i]
                    if pn.is_furniture(l):
                        i += 1
                        continue
                    if HEADER.match(l.strip()) or not pn.is_name_line(l, tokens):
                        break
                    got.append(l)
                    i += 1
                cols.append((head, pn.split_name_run(got, vocab)))
                while i < n and pn.is_furniture(lines[i]):
                    i += 1
            out.append(("div", cols))
            continue
        if pn.is_furniture(line):
            pass
        elif len(line) > 3 and re.sub(r"[^A-Za-z]", "", line).isupper():
            out.append(("h", line))
        else:
            out.append(("p", line))
        i += 1
    return out


def parse_minutes(blocks):
    """(divisions, voices) from blocks. Names unresolved."""
    divisions, voices = [], []
    stage = bill = None
    bill_titles = {}
    context = []
    previous = None
    seen_voice = set()
    for kind, item in blocks:
        if kind == "h":
            low = item.lower()
            b = _BILL.search(item)
            if b:
                # a bill's own heading inside a stage section: keep the stage
                bill = b.group(1)
                bill_titles.setdefault(bill, b.group(2).strip(" .—"))
            else:
                found = ("First Reading" if "first reading" in low else
                         "Second Reading" if "second reading" in low else
                         "Third Reading" if "third reading" in low else
                         "Committee of the Whole" if "committee of the whole" in low else
                         "Motion" if "motion" in low else None)
                # The 29L PDF prints the French heading on the next line
                # ("COMITÉ PLÉNIER SUR LES PROJETS DE LOI"): a heading that
                # follows a heading and names no stage continues it.
                if found or previous != "h":
                    stage, bill = found, None
            context = [item] if previous != "h" else context + [item]
            previous = kind
            continue
        previous = kind
        if kind == "p":
            for b in _BILL.finditer(item):
                bill = b.group(1)
                bill_titles.setdefault(bill, b.group(2).strip(" .—"))
            # PDF lines wrap mid-phrase ("be now read a / second time"), so
            # the stage and voice patterns are read over the last few lines.
            tail = " ".join(context[-3:] + [item])
            st = _STAGE.findall(tail)
            if st:
                stage = st[-1].title() + " Reading"
            v = _VOICE.search(tail)
            if v and bill and (bill, v.group(2)) not in seen_voice:
                seen_voice.add((bill, v.group(2)))
                voices.append({"bill_number": bill, "stage": v.group(2).title() + " Reading",
                               "result": re.sub(r"\s+", " ", v.group(0))})
            context.append(item)
            continue
        # a division
        printed, labels = {}, {}
        for head, names in item:
            h = HEADER.match(head)
            pos = "Yea" if h.group(1).upper() == "YEAS" else "Nay"
            printed[pos] = _n(h.group(2))
            labels[pos] = names
        text = re.sub(r"\s+", " ", " ".join(context)).strip()
        res = _RESULT.findall(text)
        put = _PUT_ON.findall(text)
        divisions.append({
            "seq": len(divisions) + 1, "yeas": printed.get("Yea"), "nays": printed.get("Nay"),
            "yea_labels": labels.get("Yea", []), "nay_labels": labels.get("Nay", []),
            "question": text[-700:] or None,
            "result": ("it was " + res[-1]) if res else None,
            "vote_on": ("amendment" if put and "amend" in put[-1].lower() and "as amended" not in put[-1].lower()
                        else "motion"),
            "stage": stage, "bill_number": bill,
            "problem": None if ("Yea" in printed and "Nay" in printed) else "a YEAS or NAYS list is missing"})
        context = []
    return divisions, voices, bill_titles


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


def _vocab(resolver):
    """Surnames for the 29L column runs, and full names ("Scott Moe") so a
    run of full names splits on members too."""
    vocab = resolver.surname_vocab()
    for m in resolver.members.values():
        if m.get("given") and m.get("surname"):
            vocab.add(tuple(pn.fold(m["given"] + " " + m["surname"]).split()))
    return vocab


def read_sitting(ctx, rec, wl):
    url = rec["minutes_html"] or rec["minutes_pdf"]
    leg, sess, date = rec["legislature"], rec["session"], rec["date"]
    part = None if rec["label"] == "Minutes" else slug(rec["label"].replace("Minutes", ""))
    skey = ps.sitting_key(PROV, leg, sess, date, part)
    if rec["minutes_html"]:
        raw = ctx.text(url, "minutes-{0}".format(date), encoding="cp1252")
        if raw is None:
            return 0, 1
        quick = html_text(raw)
    else:
        data = ctx.bytes(url, "minutes-{0}".format(date))
        if data is None:
            return 0, 1
        try:
            raw = pdf_text(data)
        except Unreadable as exc:
            ctx.gap("{0}: {1}: {2}".format(skey, url, exc))
            ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
            return 0, 1
        quick = raw
    if "recorded division" in quick.lower():
        roster_for_day(ctx, rec)
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    vocab = _vocab(resolver)
    blocks = blocks_from_html(raw) if rec["minutes_html"] else blocks_from_pdf(raw, vocab)
    divisions, voices, titles = parse_minutes(blocks)
    for number, title in titles.items():
        key = ps.bill_key(PROV, leg, sess, number)
        res = pc.classify(ctx.tax, wl, PROV, title=title, bill_key=key)
        ps.store_bill(ctx.conn, {"bill_key": key, "prov": PROV, "legislature": leg, "session": sess,
                                 "number": number, "title_en": title, "areas": res.areas,
                                 "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt})
    gaps = 0
    for d in divisions:
        votes, ok, note = resolve_division(d, resolver, date, leg)
        bkey = ps.bill_key(PROV, leg, sess, d["bill_number"]) if d["bill_number"] else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        res = pc.classify(ctx.tax, wl, PROV, texts=[d["question"]], bill_key=bkey,
                          inherit=pc.Result(b_areas, b_terms, b_tier) if b_areas else None)
        seq = "{0}.{1}".format(part, d["seq"]) if part else d["seq"]
        dkey = ps.division_key(PROV, leg, sess, date, seq)
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": leg, "session": sess, "date": date,
            "seq": seq, "kind": "recorded", "question": d["question"], "vote_on": d["vote_on"],
            "bill_key": bkey, "stage": d["stage"], "result": d["result"], "yeas": d["yeas"],
            "nays": d["nays"], "source_url": url, "areas": res.areas, "matched_terms": res.terms,
            "tier": res.tier, "excerpt": res.excerpt, "positions_ok": 1 if ok else 0,
            "tally_note": note, "votes": votes})
    for k, v in enumerate(voices, 1):
        bkey = ps.bill_key(PROV, leg, sess, v["bill_number"])
        areas, terms, tier = ps.bill_areas(ctx.conn, bkey)
        ps.store_division(ctx.conn, {
            "division_key": ps.division_key(PROV, leg, sess, date, "v{0}-{1}".format(
                v["bill_number"], v["stage"].split()[0].lower())),
            "prov": PROV, "legislature": leg, "session": sess, "date": date, "seq": "v",
            "kind": "voice", "bill_key": bkey, "stage": v["stage"], "result": v["result"],
            "source_url": url, "areas": areas, "matched_terms": terms, "tier": tier})
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions), voice=len(voices),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return len(divisions), gaps


def collect(ctx, session=None, roster=True, bills=True):
    """--session narrows the records to one legislature-session; the window
    is --since/--until (default: the last 60 days, said out loud)."""
    want = parse_session(session) if session and session != CURRENT_SESSION else None
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    until = ctx.until or datetime.date.today().isoformat()
    since = ctx.since or (datetime.date.fromisoformat(until)
                          - datetime.timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()
    if not ctx.since:
        ctx.log("  sk: no --since; reading the {0} days to {1}".format(DEFAULT_WINDOW_DAYS, until))
    records, pages = [], 0
    # The archive is asked one calendar year at a time, each with its own
    # page cap, so a backfill to 2010 (some 115 listing pages) is never cut
    # off in silence by a cap sized for a week; a year that still has a next
    # page at the cap is a gap.
    for lo, hi in year_windows(since, until):
        url, n = ARCHIVE.format(lo, hi), 0
        while url and n < LISTING_PAGE_CAP:
            page = ctx.text(url, "archive-{0}-{1}-{2}".format(lo, hi, n))
            if page is None:
                break
            records.extend(list_records(page))
            n += 1
            url = next_page(page)
        if url and n >= LISTING_PAGE_CAP:
            ctx.gap("sk archive {0}..{1}: still a next page after {2} listing pages; the rest of "
                    "that window was not listed".format(lo, hi, LISTING_PAGE_CAP))
        pages += n
    records = [r for r in records if since <= r["date"] <= until]
    if want:
        records = [r for r in records if (r["legislature"], r["session"]) == want]
    records.sort(key=lambda r: (r["date"], r["label"]))
    stats = {"records_listed": len(records), "listing_pages": pages}
    if ctx.dry_run:
        return stats
    read = divs = gaps = 0
    for rec in records:
        url = rec["minutes_html"] or rec["minutes_pdf"]
        if not ctx.refresh and ps.sitting_done(ctx.conn, url):
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        n, g = read_sitting(ctx, rec, wl)
        read += 1
        divs += n
        gaps += g
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps})
    return stats
