"""Legislative Assembly of British Columbia: roster, bills and divisions.

Driven by tools/prov_collect.py --prov bc. Scope: docs/canada-provinces-scope.md
(BC: value 4, difficulty 2, "the best structured source of the thirteen").
www.leg.bc.ca's robots.txt is a standard Drupal file (/search/, /admin/);
lims.leg.bc.ca and api.lims.leg.bc.ca answer robots.txt with a 404 page: no
rules.

  * SESSIONS AND ROSTER: the LIMS GraphQL API (api.lims.leg.bc.ca/graphql,
    POST only). allSessions maps "43-2" to its id (206) and its dates;
    allMemberParliaments gives each member of a parliament with party and
    constituency, plus election and resignation dates. THE PARTY IS ONE PER
    PARLIAMENT AND UNDATED: Tara Armstrong and Dallas Brodie left the
    Conservative caucus in 2025 and the API now shows them Independent for
    the whole parliament. So BC terms carry party_dated=0 and
    prov_votes.party_at_vote stays NULL: today's party joined to an earlier
    vote is exactly the misattribution the NI roster taught us to refuse.
  * HANSARD LISTING: /hdms/debates/<43rd2nd> (JSON) lists every House
    transcript file of the session; names are taken from it.
  * DIVISIONS: each transcript prints a division as
    <table class="DivisionTable"> with "YEAS -- 38" / "NAYS -- 49" header rows
    and one surname per cell, initials where two share one ("L. Neufeld").
    The question is the Speaker's "the question is ..." paragraph and the
    result the StyleLine before the table ("Motion negatived on the
    following division:"). A division is classified on its question, its
    Subject-Heading and the debate passages under that heading.
  * BILLS: /pdms/bills/progress-of-bills/<session id> (JSON): numbers,
    titles, every reading date, sponsor memberId and the text files' paths
    (served under lims.leg.bc.ca/pdms). TRAP: an unknown key silently
    answers ANOTHER session, so the paths must name the session's code or
    the reply is refused as a gap. A bill REFUSED FIRST READING never gets a
    number and is absent from the JSON; it is stored from the transcript
    ("Tara Armstrong presented a bill intituled ...") as '<key>/x-<slug>'.
  * VOICE: a reading date in the JSON on a day whose transcripts were read,
    with no recorded division on that bill and stage, is a voice decision.

The per-member Voting Records index (Index/43rd2nd/2026-Votes?.htm) is a
second, independent record of every standing vote; it is not read yet and
would make a second tally check (scope "Built" notes).
"""

from __future__ import annotations

import json
import re

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import html_text, sessions_sorted, slug

PROV = "bc"
CURRENT_SESSION = "43-2"
GRAPHQL = "https://api.lims.leg.bc.ca/graphql"
DEBATES = "https://lims.leg.bc.ca/hdms/debates/{0}"
FILE = "https://lims.leg.bc.ca/hdms/file{0}/{1}"
BILLS = "https://lims.leg.bc.ca/pdms/bills/progress-of-bills/{0}"
BILL_TEXT = "https://lims.leg.bc.ca/pdms{0}"

Q_SESSIONS = ("{ allSessions { nodes { id number annotation startDate endDate "
              "parliamentByParliamentId { id number annotation startDate endDate } } } }")
Q_MEMBERS = ("{{ allMemberParliaments(condition: {{parliamentId: {0}}}) {{ nodes {{ memberId active "
             "partyByPartyId {{ name abbreviation }} constituencyByConstituencyId {{ name }} "
             "memberByMemberId {{ id firstName lastName middleName "
             "memberResignationsByMemberId {{ nodes {{ resignationDate }} }} "
             "memberElectionsByMemberId {{ nodes {{ electionDate }} }} }} }} }} }}")

READINGS = (("firstReading", "First Reading"), ("secondReading", "Second Reading"),
            ("committeeReading", "Committee of the Whole"), ("thirdReading", "Third Reading"))


def parse_session(code):
    m = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("BC session must look like 43-2, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def session_code(s):
    """'43rd2nd' from an allSessions node -- the path segment LIMS uses."""
    p = s["parliamentByParliamentId"]
    return "{0}{1}{2}{3}".format(p["number"], p["annotation"], s["number"], s["annotation"])


def parse_sessions(nodes):
    """Every session in LIMS's allSessions, with its own start and end dates,
    oldest first."""
    out = []
    for s in nodes or []:
        p = s.get("parliamentByParliamentId") or {}
        if p.get("number") is None or s.get("number") is None:
            continue
        out.append({"code": "{0}-{1}".format(p["number"], s["number"]),
                    "start": (s.get("startDate") or "")[:10] or None,
                    "end": (s.get("endDate") or "")[:10] or None})
    return sessions_sorted(out)


def list_sessions(ctx):
    reply = ctx.post_json(GRAPHQL, json.dumps({"query": Q_SESSIONS}), "sessions")
    nodes = (((reply or {}).get("data") or {}).get("allSessions") or {}).get("nodes")
    if reply is not None and not nodes:
        ctx.gap("bc: the LIMS sessions list came back empty")
    return parse_sessions(nodes)


def find_session(nodes, legislature, session):
    for s in nodes or []:
        if s["parliamentByParliamentId"]["number"] == legislature and s["number"] == session:
            return s
    return None


# -- roster -----------------------------------------------------------------

def terms_from_members(nodes, parliament):
    """[(member_key, member dict, term dict)] from allMemberParliaments nodes."""
    out = []
    p_start, p_end = parliament.get("startDate"), parliament.get("endDate")
    for n in nodes or []:
        m = n.get("memberByMemberId") or {}
        party = (n.get("partyByPartyId") or {}).get("name")
        if not m or party == "Vacant" or (m.get("firstName"), m.get("lastName")) == ("Vacant", "Seat"):
            continue
        elections = sorted(e["electionDate"][:10] for e in
                           (m.get("memberElectionsByMemberId") or {}).get("nodes") or [] if e.get("electionDate"))
        start = p_start
        later = [d for d in elections if p_start and d > p_start and (not p_end or d <= p_end)]
        if later:
            start = later[-1]              # a by-election inside the parliament
        resigned = sorted(r["resignationDate"][:10] for r in
                          (m.get("memberResignationsByMemberId") or {}).get("nodes") or []
                          if r.get("resignationDate") and (not p_start or r["resignationDate"][:10] >= p_start))
        end = resigned[0] if resigned else (None if n.get("active") else p_end)
        key = str(m["id"])
        given = " ".join(x for x in (m.get("firstName"), m.get("middleName")) if x)
        out.append((key, {"name": " ".join(x for x in (m.get("firstName"), m.get("lastName")) if x),
                          "surname": m.get("lastName"), "given": given,
                          "riding": (n.get("constituencyByConstituencyId") or {}).get("name"),
                          "party": party, "active": n.get("active")},
                    {"legislature": parliament["number"], "party": party,
                     "riding": (n.get("constituencyByConstituencyId") or {}).get("name"),
                     "start": start, "end": end, "party_dated": 0}))
    return out


def fetch_roster(ctx, s):
    parl = s["parliamentByParliamentId"]
    reply = ctx.post_json(GRAPHQL, json.dumps({"query": Q_MEMBERS.format(parl["id"])}),
                          "members-{0}".format(parl["number"]))
    nodes = (((reply or {}).get("data") or {}).get("allMemberParliaments") or {}).get("nodes")
    if reply is not None and not nodes:
        ctx.gap("bc members of parliament {0}: none returned".format(parl["number"]))
    rows = terms_from_members(nodes, parl)
    if ctx.dry_run:
        return len(rows)
    for key, m, t in rows:
        ps.upsert_member(ctx.conn, PROV, key, name=m["name"], surname=m["surname"], given=m["given"],
                         riding=m["riding"], party=m["party"], sitting=1 if m["active"] else 0)
        ctx.conn.execute("DELETE FROM prov_member_terms WHERE prov=? AND member_key=? AND "
                         "legislature=? AND source='api'", (PROV, key, t["legislature"]))
        ctx.conn.execute(
            "INSERT INTO prov_member_terms (prov, member_key, legislature, party, riding, start, "
            "end, party_dated, source) VALUES (?,?,?,?,?,?,?,?,?)",
            (PROV, key, t["legislature"], t["party"], t["riding"], t["start"], t["end"], 0, "api"))
    ctx.conn.commit()
    ctx.log("  bc roster parliament {0}: {1} member(s)".format(parl["number"], len(rows)))
    return len(rows)


# -- bills ------------------------------------------------------------------

def check_bills_session(bills, code):
    """The progress-of-bills trap: True only when the reply's own file paths
    name this session."""
    paths = [f.get("path") or "" for b in bills or [] for f in ((b.get("files") or {}).get("nodes") or [])]
    return bool(paths) and all("/{0}/".format(code) in p for p in paths)


def fetch_bills(ctx, s, wl):
    leg, sess, code = s["parliamentByParliamentId"]["number"], s["number"], session_code(s)
    url = BILLS.format(s["id"])
    raw = ctx.text(url, "bills-{0}".format(code))
    try:
        bills = json.loads(raw) if raw else []
    except ValueError:
        ctx.gap("bc bills {0}: reply is not JSON".format(url))
        bills = []
    if bills and not check_bills_session(bills, code):
        ctx.gap("bc bills {0}: the reply's files do not name {1} -- the endpoint answered another "
                "session; refused".format(url, code))
        bills = []
    if ctx.dry_run:
        return {"bills": len(bills)}
    texts = 0
    for b in bills:
        number = str(b.get("billNumber"))
        if b.get("billTypeId") == 2:
            number = "M" + number       # private members' bills print as 'Bill M241'
        key = ps.bill_key(PROV, leg, sess, number)
        files = (b.get("files") or {}).get("nodes") or []
        text_url = BILL_TEXT.format(files[0]["path"]) if files else None
        have = ctx.conn.execute("SELECT text_read FROM prov_bills WHERE bill_key=?", (key,)).fetchone()
        body, text_read = None, 0
        if text_url and (ctx.refresh or not (have and have[0])) and not (
                ctx.budget is not None and ctx.budget.exhausted()):
            page = ctx.text(text_url, "billtext-{0}".format(key))
            if page:
                body = html_text(page)
                text_read = 1
                texts += 1
        stages = [{"stage": label, "date": b.get(field)} for field, label in READINGS if b.get(field)]
        record = {"bill_key": key, "prov": PROV, "legislature": leg, "session": sess, "number": number,
                  "title_en": b.get("title"), "sponsor": b.get("memberAlias"),
                  "sponsor_key": str(b["memberId"]) if b.get("memberId") else None,
                  "is_government": 1 if b.get("billTypeId") == 1 else 0,
                  "bill_type": {1: "Government", 2: "Private Member", 3: "Private"}.get(b.get("billTypeId")),
                  "stages": stages, "latest_stage": stages[-1]["stage"] if stages else None,
                  "royal_assent": b.get("royalAssent"), "page_url": url, "text_url": text_url}
        if have and have[0] and not text_read:
            ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
        else:
            res = pc.classify(ctx.tax, wl, PROV, title=b.get("title"), texts=[body] if body else [],
                              bill_key=key)
            ps.store_bill(ctx.conn, dict(record, text_read=text_read, areas=res.areas,
                                         matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
    ctx.conn.commit()
    ctx.log("  bc bills {0}: {1} listed, {2} text(s) read".format(code, len(bills), texts))
    return {"bills": len(bills), "bill_texts": texts}


# -- Hansard ----------------------------------------------------------------

def list_records(listing, code):
    """[(date, part, issue, url)] House transcripts from the debates JSON."""
    out = []
    nodes = ((listing or {}).get("allHansardFileAttributes") or {}).get("nodes") or []
    for n in nodes:
        name = n.get("fileName") or ""
        m = re.match(r"^(\d{4})(\d{2})(\d{2})(am|pm)-Hansard-n(\d+)\.html?$", name)
        if not m or not n.get("published", True):
            continue
        path = n.get("filePath") or "/Debates/" + code
        out.append(("{0}-{1}-{2}".format(*m.groups()[:3]), m.group(4), m.group(5),
                    FILE.format(path, name)))
    return sorted(set(out))


_BLOCK = re.compile(r'<p class="([^"]*)"[^>]*>(.*?)</p>|<table class="DivisionTable[^"]*"[^>]*>(.*?)</table>',
                    re.S)
_HEAD = re.compile(r"^(YEAS|NAYS|ABSTENTIONS)\s*[—–-]+\s*(\d+)\s*$", re.I)


def parse_division_table(table_html):
    """{'Yea': (printed, [labels]), 'Nay': ...}"""
    out, current = {}, None
    for tag, body in re.findall(r"<(th|td)[^>]*>(.*?)</\1>", table_html, re.S):
        text = html_text(body)
        if tag == "th":
            h = _HEAD.match(text)
            if h:
                current = {"YEAS": "Yea", "NAYS": "Nay", "ABSTENTIONS": "Abstain"}[h.group(1).upper()]
                out[current] = (int(h.group(2)), [])
            continue
        if text and current:
            out[current][1].append(text)
    return out


def stage_of(question):
    q = (question or "").lower()
    for word, stage in (("first reading", "First Reading"), ("second reading", "Second Reading"),
                        ("third reading", "Third Reading")):
        if word in q:
            return stage
    if "committee of supply" in q:
        return "Motion"
    if "committee" in q or "clause" in q or "section" in q:
        return "Committee of the Whole"
    return "Motion"


def vote_on(question):
    """'amendment' only when the question is ON an amendment -- not when a
    bill's title says "Amendment Act" (Bill M226, 23 Feb 2026)."""
    q = re.sub(r"\bAmendment Act\b", "", question or "")
    return "amendment" if re.search(r"\bamendment\b", q, re.I) else "motion"


def parse_hansard(html):
    """Divisions in one transcript, in order, names unresolved.
    [{seq, anchor, heading, business, question, result, debate, printed, labels, presented}]"""
    out = []
    heading = business = anchor = None
    paras, debate = [], []
    presented = {}
    for m in _BLOCK.finditer(html or ""):
        cls, body, table = m.group(1), m.group(2), m.group(3)
        if table is not None:
            question = next((p for p in reversed(paras[-14:]) if re.search(
                r"question (?:before the House )?is\b", p, re.I)), None)
            result = next((p for p in reversed(paras[-3:]) if "division" in p.lower()), None)
            parsed = parse_division_table(table)
            out.append({"seq": len(out) + 1, "anchor": anchor, "heading": heading, "business": business,
                        "question": question, "result": (result or "").rstrip(":").strip() or None,
                        "debate": list(debate), "printed": {k: v[0] for k, v in parsed.items()},
                        "labels": {k: v[1] for k, v in parsed.items()},
                        "presented": dict(presented)})
            paras = []
            continue
        text = html_text(body)
        if cls == "Time-Stamp":
            ident = re.search(r'id="([^"]+)"', m.group(0))
            anchor = ident.group(1) if ident else anchor
            continue
        if cls == "Business-Heading":
            business, heading, debate = text, None, []
        elif cls == "Subject-Heading":
            heading, debate = text, []
        elif text:
            paras.append(text)
            if cls.startswith("Speaker"):
                debate.append(text)
            p = re.search(r"presented a bill intituled (.+?)\.?$", text)
            if p:
                presented[p.group(1).strip()] = text
    return out


def bill_for(d, titles, leg, sess):
    """(bill_key, unnumbered_title) for a division."""
    for text in (d["heading"], d["question"]):
        m = re.search(r"\bBill (M?\d+)\b", text or "")
        if m:
            return ps.bill_key(PROV, leg, sess, m.group(1)), None
    head = pn.fold(re.sub(r"\s*\(Bill [^)]*\)", "", d["heading"] or ""))
    if head and head in titles:
        return titles[head], None
    for title in d["presented"]:
        if pn.fold(title) == head:
            return ps.bill_key(PROV, leg, sess, "x-" + slug(title)), title
    return None, None


def read_sitting(ctx, leg, sess, date, part, issue, url, resolver, wl, titles):
    page = ctx.text(url, "hansard-{0}-{1}".format(date, part))
    skey = ps.sitting_key(PROV, leg, sess, date, part)
    if page is None:
        return [], 1
    if "DivisionTable" not in page and "Hansard" not in page[:5000]:
        ctx.gap("{0}: {1} does not look like a transcript".format(skey, url))
        ps.store_sitting(ctx.conn, PROV, skey, date, url, status="unreadable")
        return [], 1
    divisions = parse_hansard(page)
    gaps, stored = 0, []
    for d in divisions:
        votes = []
        for position in ("Yea", "Nay", "Abstain"):
            for k, label in enumerate(d["labels"].get(position, []), 1):
                key, how = resolver.resolve(label, date, leg)
                votes.append({"position": position, "ordinal": k, "raw_label": label,
                              "member_key": key, "how": how,
                              "party_at_vote": resolver.party_at(key, date, leg) if key else None})
        printed = {p: d["printed"].get(p) for p in ("Yea", "Nay", "Abstain")}
        ok, note = ps.tally(printed, votes)
        if "Yea" not in d["printed"] or "Nay" not in d["printed"]:
            ok, note = False, "; ".join(x for x in ("a YEAS or NAYS header is missing", note) if x)
        bkey, unnumbered = bill_for(d, titles, leg, sess)
        if unnumbered:
            res_b = pc.classify(ctx.tax, wl, PROV, title=unnumbered,
                                texts=[d["presented"].get(unnumbered)] + d["debate"], bill_key=bkey)
            ps.store_bill(ctx.conn, {"bill_key": bkey, "prov": PROV, "legislature": leg, "session": sess,
                                     "number": None, "title_en": unnumbered,
                                     "sponsor": d["presented"][unnumbered].split(" presented")[0],
                                     "latest_stage": "First Reading refused" if d["result"] and
                                     "negatived" in d["result"].lower() else None,
                                     "stages": [{"stage": "First Reading", "date": date,
                                                 "result": d["result"]}],
                                     "page_url": url, "text_read": 0, "areas": res_b.areas,
                                     "matched_terms": res_b.terms, "tier": res_b.tier,
                                     "excerpt": res_b.excerpt})
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        res = pc.classify(ctx.tax, wl, PROV, title=d["heading"], texts=[d["question"]] + d["debate"],
                          bill_key=bkey, inherit=pc.Result(b_areas, b_terms, b_tier) if b_areas else None)
        seq = "{0}.{1}".format(issue, d["seq"])
        dkey = ps.division_key(PROV, leg, sess, date, seq)
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        question = " | ".join(x for x in (d["heading"] or d["business"], d["question"]) if x) or None
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": leg, "session": sess, "date": date,
            "seq": seq, "kind": "recorded", "question": question,
            "vote_on": vote_on(d["question"]),
            "bill_key": bkey, "stage": stage_of(d["question"]), "result": d["result"],
            "yeas": printed["Yea"], "nays": printed["Nay"], "abstentions": printed["Abstain"],
            "source_url": url + ("#" + d["anchor"] if d["anchor"] else ""),
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": note, "votes": votes})
        stored.append((bkey, stage_of(d["question"])))
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return stored, gaps


def store_voice(ctx, leg, sess, read_dates):
    """Reading dates in the bills JSON, on days read, with no recorded
    division on that bill and stage: voice decisions."""
    n = 0
    for key, stages, page_url in ctx.conn.execute(
            "SELECT bill_key, stages, page_url FROM prov_bills WHERE prov=? AND legislature=? "
            "AND session=? AND number IS NOT NULL", (PROV, leg, sess)).fetchall():
        areas, terms, tier = ps.bill_areas(ctx.conn, key)
        for s in json.loads(stages or "[]"):
            if s.get("date") not in read_dates:
                continue
            hit = ctx.conn.execute("SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? "
                                   "AND kind='recorded' AND stage=?", (key, s["date"], s["stage"])).fetchone()[0]
            if hit:
                continue
            ps.store_division(ctx.conn, {
                "division_key": ps.division_key(PROV, leg, sess, s["date"], "v{0}-{1}".format(
                    key.rsplit("/", 1)[1], s["stage"].split()[0].lower())),
                "prov": PROV, "legislature": leg, "session": sess, "date": s["date"], "seq": "v",
                "kind": "voice", "bill_key": key, "stage": s["stage"],
                "result": "reading recorded in progress of bills; no division in that day's transcripts",
                "source_url": page_url, "areas": areas, "matched_terms": terms,
                "tier": tier})
            n += 1
    ctx.conn.commit()
    return n


def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    leg, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    wl = pc.load_watchlist(PROV)
    reply = ctx.post_json(GRAPHQL, json.dumps({"query": Q_SESSIONS}), "sessions")
    s = find_session((((reply or {}).get("data") or {}).get("allSessions") or {}).get("nodes"), leg, sess)
    if not s:
        ctx.gap("bc: session {0} not found in the LIMS sessions list".format(session))
        return {}
    code = session_code(s)
    stats = {}
    if roster:
        stats["members"] = fetch_roster(ctx, s)
    if bills:
        stats.update(fetch_bills(ctx, s, wl))
    listing = ctx.text(DEBATES.format(code), "debates-{0}".format(code))
    try:
        listing = json.loads(listing) if listing else None
    except ValueError:
        ctx.gap("bc debates list {0}: not JSON".format(code))
        listing = None
    records = [r for r in list_records(listing, code) if ctx.in_window(r[0])]
    stats["records_listed"] = len(records)
    if ctx.dry_run:
        return stats
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    titles = {pn.fold(t): k for k, t in ctx.conn.execute(
        "SELECT bill_key, title_en FROM prov_bills WHERE prov=? AND legislature=? AND session=? "
        "AND title_en IS NOT NULL", (PROV, leg, sess)).fetchall()}
    read = divs = gaps = 0
    done = {}
    for date, part, issue, url in records:
        if not ctx.refresh and ps.sitting_done(ctx.conn, url):
            done.setdefault(date, []).append(True)
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        stored, g = read_sitting(ctx, leg, sess, date, part, issue, url, resolver, wl, titles)
        read += 1
        divs += len(stored)
        gaps += g
        done.setdefault(date, []).append(True)
    # A day counts as read only when EVERY transcript of it was: otherwise a
    # division in the unread half would be stored as a voice decision.
    per_day = {}
    for date, _part, _issue, _url in records:
        per_day[date] = per_day.get(date, 0) + 1
    read_dates = {d for d, n in per_day.items() if len(done.get(d, [])) == n}
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps,
                  "voice": store_voice(ctx, leg, sess, read_dates) if bills else 0})
    return stats
