"""Legislative Assembly of British Columbia: roster, bills and divisions.

Driven by tools/prov_collect.py --prov bc. Scope: docs/canada-provinces-scope.md
(BC: value 4, difficulty 2, "the best structured source of the thirteen").
www.leg.bc.ca's robots.txt is a standard Drupal file (/search/, /admin/);
lims.leg.bc.ca and api.lims.leg.bc.ca answer robots.txt with a 404 page: no
rules.

  * SESSIONS AND ROSTER: the LIMS GraphQL API (api.lims.leg.bc.ca/graphql,
    POST only). allSessions maps "43-2" to its id (206) and its dates;
    allMemberParliaments gives each member of a parliament with party and
    constituency, plus election and resignation dates. THE API'S PARTY IS
    ONE PER PARLIAMENT AND UNDATED: Tara Armstrong and Dallas Brodie left the
    Conservative caucus in 2025 and the API shows them Independent for the
    whole parliament; it shows Bruce Banman, elected a BC Liberal in 2020,
    Conservative for all of the 42nd. Those terms (source 'api') carry
    party_dated=0 and are never written on a vote: today's party joined to
    an earlier vote is the misattribution the NI roster taught us to refuse.
    (memberElections carries a party only for 2024, and no election dates.)
  * PARTY AT THE VOTE, DATED TO THE SITTING: every House issue's PDF
    (pdfLink in the debates JSON, 25 August 2009 on) prints the
    "ALPHABETICAL LIST OF MEMBERS" with each Member's party, and the party
    standings. It is the list for that sitting: the 6 February 2023 issue,
    produced in January 2024, still shows Banman "(BC Liberal Party)". The
    standings are a tally check; each entry resolves against the roster
    terms valid that day; the parties are stored as party-only terms
    (source 'party-hansard') spanning the sittings they were seen on.
    Read: every division day, each session's first and last sitting, and
    then the sittings between a member's last list in one party and first
    in another, by bisection, until the change lies between two sittings
    in a row. NOT EVERY ISSUE'S LIST IS ITS DAY'S: the 3 October 2022
    morning issue, regenerated in 2024, prints 2024's parties. So a party
    seen on one sitting alone is believed only when a sitting beside it
    agrees (lone_lists, refute_lone_lists). A vote in such a window, or on a day whose list cannot be
    read and whose neighbours disagree, carries NO party. party_at_vote is
    rewritten from these terms for every stored vote of the session
    (prov_store.refresh_party), so votes stored before the lists were read
    are repaired without fetching their transcripts again. Sources:
    lims.leg.bc.ca/hdms/debates/<session code> (pdfLink) and
    lims.leg.bc.ca/hdms/file/Debates/<code>/<issue>.pdf.
  * HANSARD LISTING: /hdms/debates/<43rd2nd> (JSON) lists every House
    transcript file of the session; names are taken from it: '...-Hansard-
    n119.html' from the 41st Parliament, '...-Hansard-v19n3.htm' in the 39th
    and 40th (read only from 2 October 2026: before, those sessions listed
    nothing, silently). A listed transcript name not taken, or a listing that
    yields none, is a gap.
  * DIVISIONS: each transcript prints a division as a table of "YEAS -- 38"
    / "NAYS -- 49" headers and one surname per cell, initials where two
    share one ("L. Neufeld"): <table class="DivisionTable"> with the headers
    in <th> (2025-), or in <td><p class="DivisionHeader"> (2009-2017), and
    <table class="division-table"> with <p class="division-header"> and
    hyphenated lower-case paragraph classes (2018-2024). Until 2 October
    2026 only the first was read: 2017's headers were read as names (19
    tally gaps) and 725 sittings of 2018-2024 were stored 'ok' with none.
    Also read: a page number printed inside a cell, a table continuing the
    one before it after a page break, unquoted upper-case markup (2015),
    and, throughout (2010-2026), a division the transcript records WITHOUT names
    ("approved unanimously on a division. [See Votes and Proceedings.]"),
    stored with no votes and a tally_note beginning "no names": untrusted,
    not owed.
    TWO GUARDS now: a transcript that prints "on the following division" (or
    a division table) more often than it parses divisions is a gap; and the
    session's Voting Records index (below), which links every standing vote
    to its transcript from the 41st Parliament on, makes a cited sitting
    stored with no division OWED, so the run reads it again, and a gap if it
    still holds none.
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
second, independent record of every standing vote. It is read for WHICH
transcripts hold one (the guard above); its per-member positions are not
compared with the transcript's yet.

MEMBERS THE API'S ROSTER LACKS. allMemberParliaments lists a parliament's
members at its end: the 39th omits Gordon Campbell, Iain Black and Barry
Penner, who resigned in 2011-12. A Hansard list entry no roster term fits is
matched against every member the API knows (allMembers) on surname, given
name AND riding, unique-or-nothing, and gets a MEMBERSHIP term (source
'hansard-list') spanning exactly the sittings it is listed on; the sittings
its votes left unresolved are read again in the same run.
"""

from __future__ import annotations

import json
import re

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text, pdf_text, sessions_sorted, slug

PROV = "bc"
CURRENT_SESSION = "43-2"
GRAPHQL = "https://api.lims.leg.bc.ca/graphql"
DEBATES = "https://lims.leg.bc.ca/hdms/debates/{0}"
FILE = "https://lims.leg.bc.ca/hdms/file{0}/{1}"
PDF_FILE = "https://lims.leg.bc.ca/hdms/file{0}"
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
        # One parliament's roster replaces that parliament's terms only: the
        # Alberta fault (ffd13b9e) was a re-read deleting every legislature's.
        ps.replace_terms(ctx.conn, PROV, key, [t], "api", legislature=t["legislature"])
    ctx.conn.commit()
    ctx.log("  bc roster parliament {0}: {1} member(s)".format(parl["number"], len(rows)))
    return len(rows)


# -- party at the vote: the Hansard's own list of members ----------------------
#
# Every House issue of the Official Report, as a PDF (pdfLink in the debates
# JSON), prints a few pages in an "ALPHABETICAL LIST OF MEMBERS" with each
# Member's party, and the party standings under it. It is the Assembly's
# list for THAT sitting: the 6 February 2023 issue, produced in January 2024,
# still shows Bruce Banman "(BC Liberal Party)" though he sat as a
# Conservative from September 2023. Three layouts, all read:
#   39th Parliament   'Dix, adrian (nDP) ....... Vancouver-kingsway' (small
#                     capitals come out lower-case; '(l)' is Liberal) and
#                     "Party Standings: liberal 49; new Democratic 35; independent 1"
#   40th-42nd         'Banman, Bruce (BC Liberal Party) ....... Abbotsford South'
#                     and "Party Standings: BC NDP 57; BC Liberal Party 28; ..."
#   43rd              'ALPHABETICAL LIST OF MEMBERS BY PARTY', one heading per
#                     party ('CONSERV ATIVE PARTY OF BC'), two entries on a line
#                     where the columns meet, and "BC NDP – 47 | ..."
# THE STANDINGS ARE THE TALLY CHECK: a list whose entries per party do not
# add up to the printed standings is refused whole, as a division whose
# names do not add up is. Each entry is resolved against the roster terms
# valid that day, unique-or-nothing, and stored as a PARTY-ONLY term
# (source 'party-hansard', prov_names: it never makes anyone a member)
# spanning the sittings it was seen on.

PARTY_SOURCE = "party-hansard"
BISECT_READS = 60          # per session: lists read to narrow a change to two sittings

# The printed party, squashed (prov_names.squash), to the members API's own
# party names, so a dated party reads like prov_members.party.
PARTY_NAMES = {
    "British Columbia Liberal Party": ("l", "liberal", "bcliberal", "bcliberals", "bcliberalparty",
                                       "britishcolumbialiberalparty"),
    "British Columbia New Democratic Party": ("ndp", "bcndp", "newdemocratic", "newdemocraticparty",
                                              "britishcolumbianewdemocraticparty"),
    "British Columbia United": ("bcunited", "britishcolumbiaunited"),
    "Conservative Party of British Columbia": ("c", "conservative", "bcconservative", "bcconservatives",
                                               "bcconservativeparty", "conservativeparty",
                                               "conservativepartyofbc", "conservativepartyofbritishcolumbia"),
    "British Columbia Green Party": ("g", "green", "greenparty", "bcgreen", "bcgreens", "bcgreenparty",
                                     "britishcolumbiagreenparty"),
    "Independent": ("i", "ind", "independent", "independents"),
    "OneBC": ("onebc",),
}
_PARTY = {code: name for name, codes in PARTY_NAMES.items() for code in codes}
_MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july",
                                        "august", "september", "october", "november", "december"), 1)}
_ENTRY = re.compile(r"^(?P<pre>.*?),\s*(?P<given>[^()]*?)\s*(?:\((?P<party>[^()]*)\))?\s*$")
_LIST_START = re.compile(r"list\s+of\s+members", re.I)
_LIST_END = re.compile(r"list\s+of\s+members\s+by\s+riding|list\s+of\s+ridings|party\s+standings|=====PAGE", re.I)
_GIVEN_HONORIFICS = {"hon", "dr", "kc", "qc", "rev", "mr", "mrs", "ms"}


def party_name(printed):
    """The API's name for a party as the list prints it, or None."""
    return _PARTY.get(pn.squash(printed))


def list_pdfs(listing):
    """{date: [(part, pdf url)]} for the House transcripts of a debates JSON
    that have a PDF. Every file name since 2009 begins 'YYYYMMDDam|pm-'."""
    out = {}
    for n in ((listing or {}).get("allHansardFileAttributes") or {}).get("nodes") or []:
        m = re.match(r"^(\d{4})(\d{2})(\d{2})(am|pm)-Hansard-", n.get("fileName") or "")
        if not m or not n.get("published", True):
            continue
        for a in (n.get("debateAttributes") or {}).get("nodes") or []:
            if a.get("pdfLink") and (a.get("debateType") or {}).get("name") in ("House", None):
                date = "{0}-{1}-{2}".format(*m.groups()[:3])
                out.setdefault(date, []).append((m.group(4), PDF_FILE.format(a["pdfLink"])))
    return {d: sorted(set(v)) for d, v in out.items()}


def parse_standings(text):
    """{party: seats} from the standings the list prints, Vacant left out;
    None when there are none, or a party in them is not one we know."""
    m = re.search(r"party\s+standings:?(.*)", text or "", re.I | re.S)
    if not m:
        return None
    pieces = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or re.match(r"total\s+seats", line, re.I):
            continue
        if not re.search(r"\d", line):
            if pieces:
                break
            continue
        pieces += re.split(r"[;|]", line)
        if not re.search(r"[;|]\s*$", line):
            break
    out = {}
    for p in pieces:
        pm = re.match(r"^\s*(.+?)\s*[–—-]?\s*(\d+)\s*$", p)
        if not pm:
            continue
        if pn.squash(pm.group(1)) == "vacant":
            continue
        name = party_name(pm.group(1))
        if not name:
            return None
        out[name] = out.get(name, 0) + int(pm.group(2))
    return out or None


def parse_member_list(text):
    """The Hansard's list of members, or None when it prints none:
    {'parliament', 'date', 'standings', 'entries': [{pre, given, party,
    riding, merged}], 'unknown': [printed parties not recognised]}.

    'pre' is the text before the comma: the surname, or, where two entries
    share a line (the 43rd's columns), the first entry's riding then the
    second's surname ('Saanich North and the Islands Valeriote'), which
    resolve_member_list cuts with the roster's surnames."""
    text = text or ""
    start = _LIST_START.search(text)
    if not start:
        return None
    out = {"parliament": None, "date": None, "standings": None, "entries": [], "unknown": [],
           "headings": []}
    p = re.search(r"(\d{2})(?:st|nd|rd|th)\s+Parliament", text[:start.start()] or text[:3000])
    if p:
        out["parliament"] = int(p.group(1))
    d = re.search(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
                  text[:start.start()] or text[:3000])
    if d and d.group(1).lower() in _MONTHS:
        out["date"] = "{0}-{1:02d}-{2:02d}".format(d.group(3), _MONTHS[d.group(1).lower()], int(d.group(2)))
    # The page holding the list carries the standings, before it (43rd) or after.
    page_start = text.rfind("=====PAGE", 0, start.start())
    page_end = text.find("=====PAGE", start.end())
    page = text[page_start + 1 if page_start >= 0 else 0:page_end if page_end >= 0 else None]
    out["standings"] = parse_standings(page)
    end = _LIST_END.search(text, start.end())
    block = text[start.end():end.start() if end else None]
    section = None
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        if not re.search(r"\.{2,}", line):
            # A party heading of the 43rd's layout ('CONSERV ATIVE PARTY OF BC').
            # Any other capitalised line that is not the list's own title
            # ends the section: entries under a heading we cannot name carry
            # no party, and the tally then refuses the list.
            if party_name(line):
                section = party_name(line)
            elif line.isupper() and not _LIST_START.search(line) and pn.squash(line) != "byparty":
                section = None
                out["headings"].append(line)
            continue
        segs = [s.strip() for s in re.split(r"\s*\.{2,}\s*", line)]
        names, ridings = [segs[0]], []
        for mid in segs[1:-1]:
            ridings.append(mid)          # riding of the entry before, then the next name
            names.append(mid)
        ridings.append(segs[-1])
        for k, name in enumerate(names):
            m = _ENTRY.match(name)
            if not m:
                continue
            party = section
            if m.group("party") is not None:
                party = party_name(m.group("party"))
                if party is None:
                    out["unknown"].append(m.group("party"))
                    continue
            out["entries"].append({"pre": m.group("pre").strip(), "given": m.group("given").strip(),
                                   "party": party, "riding": ridings[k] if k == len(names) - 1 else None,
                                   "merged": k > 0})
    return out


def tally_member_list(parsed):
    """None when the entries per party add up to the printed standings,
    else why not."""
    if not parsed or not parsed["entries"]:
        return "no members listed"
    if parsed["unknown"]:
        return "unknown party {0!r}".format(parsed["unknown"][0])
    if not parsed["standings"]:
        return "no party standings printed (or a party in them unknown)"
    counts = {}
    for e in parsed["entries"]:
        if not e["party"]:
            return "an entry with no party ({0}, {1})".format(e["pre"], e["given"])
        counts[e["party"]] = counts.get(e["party"], 0) + 1
    if counts != parsed["standings"]:
        return "entries {0} against standings {1}".format(
            ", ".join("{0} {1}".format(k, v) for k, v in sorted(counts.items())),
            ", ".join("{0} {1}".format(k, v) for k, v in sorted(parsed["standings"].items())))
    return None


def _given_tokens(given):
    # 'Dr.Andrew' (Weaver, 2017) has no space after the honorific
    toks = [pn.squash(t) for t in re.split(r"[\s/,.]+", given or "")]
    return [t for t in toks if t and t not in _GIVEN_HONORIFICS]


def resolve_member_list(parsed, resolver, date, legislature, known=None, found=None):
    """([(member_key, party)], problems): each entry's member among those
    holding a roster term that day, by surname (and, for two entries on one
    line, by the longest run of words ending the text that is a surname),
    then the given name, then the riding. Unique-or-nothing: a member two
    entries resolve to gets no party at all."""
    valid = {}
    for t in resolver.valid_terms(date, legislature):
        valid.setdefault(t["member_key"], []).append(t)
    people = []
    for key, ts in valid.items():
        m = resolver.members.get(key) or {}
        if m.get("surname"):
            people.append({"key": key, "surname": pn.squash(m["surname"]),
                           "given": [pn.squash(g) for g in re.split(r"[\s-]+", m.get("given") or "") if g],
                           "ridings": {pn.squash(t.get("riding")) for t in ts if t.get("riding")}})
    surnames = {p["surname"] for p in people}
    rows = []
    for e in parsed["entries"]:
        row = {"e": e, "surname": pn.squash(e["pre"]), "riding": e["riding"]}
        if e["merged"]:
            # 'Saanich North and the Islands Valeriote': the longest run of
            # words ending the text that is a surname; the rest is the riding
            # of the entry before it on the line.
            words, row["surname"] = e["pre"].split(), None
            for k in range(len(words)):
                if pn.squash(" ".join(words[k:])) in surnames:
                    row["surname"] = pn.squash(" ".join(words[k:]))
                    if rows and k:
                        rows[-1]["riding"] = " ".join(words[:k])
                    break
        rows.append(row)
    pairs, problems = [], []
    for row in rows:
        e, surname = row["e"], row["surname"]
        given = _given_tokens(e["given"])
        cands = [p for p in people if surname and p["surname"] == surname]
        if not cands and surname and len(surname) >= 4 and given:
            # A surname the member later lengthened (2009's 'Herbert' is the
            # roster's 'Chandra Herbert'): matched on its end, given name required.
            cands = [p for p in people if p["surname"].endswith(surname)]
        if given:
            cands = [p for p in cands if not p["given"] or any(
                g.startswith(given[0]) or given[0].startswith(g) for g in p["given"])]
        riding = pn.squash(row["riding"] or "")
        if len(cands) > 1 and riding:
            cands = [p for p in cands if riding in p["ridings"]] or cands
        if len(cands) == 1:
            pairs.append((cands[0]["key"], e["party"]))
        elif not cands and known and surname and given and riding:
            # Nobody holding a roster term fits: a member the API's roster of
            # the parliament leaves out (it lists the 39th's members at its
            # end, not Campbell, Black or Penner, who resigned in 2011-12). A
            # member the Assembly knows (allMembers) is taken only on surname,
            # given name AND riding together, unique-or-nothing.
            hits = [m for m in known if pn.squash(m["surname"]) == surname and pn.squash(m["riding"]) == riding
                    and m["key"] not in valid and any(g.startswith(given[0]) or given[0].startswith(g)
                                                      for g in m["given_tokens"])]
            if len(hits) == 1:
                pairs.append((hits[0]["key"], e["party"]))
                if found is not None:
                    found.append((hits[0], row["riding"]))
            else:
                problems.append("{0}, {1} ({2}): {3}".format(
                    e["pre"], e["given"], e["party"], "nobody holding a term that day fits, and "
                    "{0} member(s) of the Assembly with that name and riding".format(len(hits))))
        else:
            problems.append("{0}, {1} ({2}): {3}".format(
                e["pre"], e["given"], e["party"], "nobody holding a term that day fits" if not cands else
                "ambiguous: " + ", ".join(sorted(p["key"] for p in cands))))
    keys = [k for k, _ in pairs]
    for k in sorted({k for k in keys if keys.count(k) > 1}):
        problems.append("{0} matched more than one entry; no party stored for them".format(k))
        pairs = [(x, p) for x, p in pairs if x != k]
    return pairs, problems


def extend_party(conn, member_key, legislature, party, date):
    """Record that `member_key` sat for `party` on `date`. The term in force
    before the day widens to it when the party is the same, or the one after
    when that is; otherwise a one-day term starts. A day inside a run of
    another party, assumed between the run's two ends, SPLITS the run back to
    those ends ('split'); a day an end of another party's run already holds
    gets a term of its own, so two terms cover it and party_at gives NOTHING
    there ('conflict')."""
    rows = conn.execute(
        "SELECT rowid, party, start, end FROM prov_member_terms WHERE prov=? AND member_key=? "
        "AND legislature=? AND source=? ORDER BY start", (PROV, member_key, legislature, PARTY_SOURCE)).fetchall()
    inside = [r for r in rows if r[2] <= date <= r[3]]
    if any(r[1] == party for r in inside):
        return None

    def insert(p, start, end):
        conn.execute(
            "INSERT INTO prov_member_terms (prov, member_key, legislature, party, riding, start, end, "
            "party_dated, source) VALUES (?,?,?,?,?,?,?,1,?)",
            (PROV, member_key, legislature, p, None, start, end, PARTY_SOURCE))

    if inside:
        rowid, other, start, end = inside[0]
        if start < date < end:
            # The run was only ASSUMED between its two ends: keep the two
            # ends, which were seen, and let bisection read the sittings
            # between them again (an issue printing another day's list is
            # then refuted by its neighbours; a real change is found).
            conn.execute("UPDATE prov_member_terms SET end=? WHERE rowid=?", (start, rowid))
            insert(other, end, end)
            insert(party, date, date)
            return "split"
        insert(party, date, date)            # two parties seen on one day: none that day
        return "conflict"
    # The term that ENDS last before the day and the one that STARTS first
    # after it: no other term lies between them, so widening one never jumps
    # over a term in another party.
    before = sorted((r for r in rows if r[3] < date), key=lambda r: r[3])[-1:]
    after = sorted((r for r in rows if r[2] > date), key=lambda r: r[2])[:1]
    if before and before[0][1] == party:
        if after and after[0][1] == party:
            conn.execute("UPDATE prov_member_terms SET end=? WHERE rowid=?", (after[0][3], before[0][0]))
            conn.execute("DELETE FROM prov_member_terms WHERE rowid=?", (after[0][0],))
        else:
            conn.execute("UPDATE prov_member_terms SET end=? WHERE rowid=?", (date, before[0][0]))
    elif after and after[0][1] == party:
        conn.execute("UPDATE prov_member_terms SET start=? WHERE rowid=?", (date, after[0][0]))
    else:
        insert(party, date, date)
    return None


def change_windows(conn, legislature):
    """[(after, before)]: the open days between a member's last sighting in
    one party and first in another, in one parliament."""
    by = {}
    for key, party, start, end in conn.execute(
            "SELECT member_key, party, start, end FROM prov_member_terms WHERE prov=? AND source=? "
            "AND legislature=? ORDER BY member_key, start", (PROV, PARTY_SOURCE, legislature)):
        by.setdefault(key, []).append((party, start, end))
    out = set()
    for ts in by.values():
        for a, b in zip(ts, ts[1:]):
            if a[0] != b[0] and a[2] < b[1]:
                out.add((a[2], b[1]))
    return sorted(out)


def _terms_by_member(conn, legislature):
    by = {}
    for rowid, key, party, start, end in conn.execute(
            "SELECT rowid, member_key, party, start, end FROM prov_member_terms WHERE prov=? AND source=? "
            "AND legislature=? ORDER BY member_key, start, end", (PROV, PARTY_SOURCE, legislature)):
        by.setdefault(key, []).append((rowid, party, start, end))
    return by


def lone_lists(conn, legislature):
    """[(member_key, day)]: a member's party seen on ONE sitting only, with
    another party on a list before or after it. An issue's list can be a
    later one: the 3 October 2022 morning issue, regenerated in January
    2024, prints 2024's parties (Banman 'Conservative Party of BC', the
    Liberals 'BC United', Adam Walker 'Independent') where the afternoon
    issue of the same day prints 2022's. So such a list
    is believed only once a neighbouring sitting agrees; fetch_party_lists
    reads the listed sittings either side to see."""
    out = []
    for key, ts in _terms_by_member(conn, legislature).items():
        for i, t in enumerate(ts):
            if t[2] != t[3] or len(ts) < 2:
                continue
            if any(o is not t and o[2] <= t[2] <= o[3] for o in ts):
                continue                     # two parties on one day: none that day already
            out.append((key, t[2]))
    return out


def _party_on(ts, day):
    hits = {o[1] for o in ts if o[2] <= day <= o[3]}
    return hits.pop() if len(hits) == 1 else None


def refute_lone_lists(ctx, legislature, dates, seen, refuted=None):
    """Drop a lone list's party (see lone_lists) once the listed sittings
    either side of it have been READ this run (`seen`) and the one after
    shows the member in another party, as does the one before (or the
    member is not on it). Where the two sides agree, their terms are joined
    across the day, as for a day whose list cannot be read. Returns how many
    were dropped."""
    n = 0
    dropped = {}
    for key, day in lone_lists(ctx.conn, legislature):
        ts = _terms_by_member(ctx.conn, legislature).get(key) or []
        t = next((o for o in ts if o[2] == o[3] == day), None)
        if t is None:
            continue                         # joined into a term by an earlier refutation
        before = [d for d in dates if d < day][-1:]
        after = [d for d in dates if d > day][:1]
        # Judged only with BOTH sides read: a day opening the session's
        # listing has its other side in the session before, read there.
        if not after or not before or after[0] not in seen or before[0] not in seen:
            continue
        p_after = _party_on(ts, after[0])
        p_before = _party_on(ts, before[0]) if before else None
        if p_after is None or p_after == t[1] or p_before == t[1]:
            continue
        ctx.conn.execute("DELETE FROM prov_member_terms WHERE rowid=?", (t[0],))
        if p_before is not None and p_before == p_after:
            left = next(o for o in ts if o[2] <= before[0] <= o[3])
            right = next(o for o in ts if o[2] <= after[0] <= o[3])
            ctx.conn.execute("UPDATE prov_member_terms SET end=? WHERE rowid=?", (right[3], left[0]))
            ctx.conn.execute("DELETE FROM prov_member_terms WHERE rowid=?", (right[0],))
        dropped.setdefault(day, []).append("{0} ({1}; {2} after)".format(key, t[1], p_after))
        if refuted is not None:
            refuted.add((key, day))
        n += 1
    for day, who in sorted(dropped.items()):
        ctx.gap("bc {0}: that issue's list is not the day's -- {1} member(s) in a party no sitting either "
                "side shows them in; not used: {2}".format(day, len(who), ", ".join(who)))
    ctx.conn.commit()
    return n


def covered(conn, legislature, date):
    return bool(conn.execute(
        "SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND source=? AND legislature=? "
        "AND start<=? AND end>=?", (PROV, PARTY_SOURCE, legislature, date, date)).fetchone()[0])


LIST_SOURCE = "hansard-list"
Q_ALL_MEMBERS = ("{ allMembers { nodes { id firstName lastName middleName "
                 "constituencyByConstituencyId { name } } } }")


def known_members(ctx):
    """Every member the Assembly's API knows (allMembers), read once a run:
    [{key, name, surname, given, given_tokens, riding (latest)}]."""
    if getattr(ctx, "bc_known", None) is None:
        reply = ctx.post_json(GRAPHQL, json.dumps({"query": Q_ALL_MEMBERS}), "members-all")
        nodes = (((reply or {}).get("data") or {}).get("allMembers") or {}).get("nodes") or []
        ctx.bc_known = []
        for m in nodes:
            given = " ".join(x for x in (m.get("firstName"), m.get("middleName")) if x)
            riding = (m.get("constituencyByConstituencyId") or {}).get("name")
            if m.get("lastName") and riding:
                ctx.bc_known.append({
                    "key": str(m["id"]), "surname": m["lastName"], "given": given, "riding": riding,
                    "name": " ".join(x for x in (m.get("firstName"), m.get("lastName")) if x),
                    "given_tokens": [pn.squash(g) for g in re.split(r"[\s-]+", given) if g]})
    return ctx.bc_known


def read_party_list(ctx, legislature, date, url, resolver):
    """Read one issue's list of members and store its parties. None when it
    cannot be read or its tally fails; else {'pairs': [(member_key, party)],
    'split': [member_key whose assumed run it split]}."""
    raw = ctx.bytes(url, "hansard-pdf-{0}".format(url.rsplit("/", 1)[-1]))
    if raw is None:
        return None
    try:
        parsed = parse_member_list(pdf_text(raw, pages=range(8)))
    except Unreadable as exc:
        ctx.gap("bc {0}: Hansard {1}: {2}; no member list read".format(date, url, exc))
        return None
    if parsed is None:
        ctx.gap("bc {0}: Hansard {1} prints no list of members".format(date, url))
        return None
    if parsed["parliament"] not in (None, legislature) or parsed["date"] not in (None, date):
        ctx.gap("bc {0}: Hansard {1} is for {2} of the {3} Parliament; not used".format(
            date, url, parsed["date"], parsed["parliament"]))
        return None
    why = tally_member_list(parsed)
    if why:
        ctx.gap("bc {0}: the member list of {1} does not add up ({2}); no party taken from it".format(
            date, url, why))
        return None
    found = []
    pairs, problems = resolve_member_list(parsed, resolver, date, legislature, known=known_members(ctx),
                                          found=found)
    for p in problems:
        ctx.gap("bc {0}: Hansard member list: {1}".format(date, p))
    if found and not ctx.dry_run:
        for m, riding in found:
            ps.upsert_member(ctx.conn, PROV, m["key"], name=m["name"], surname=m["surname"], given=m["given"],
                             riding=m["riding"])
            # A MEMBERSHIP term (not party-only), exactly the sittings the
            # member is seen listed on, as Saskatchewan's cover lists are.
            ps.extend_term(ctx.conn, PROV, m["key"], legislature, None, m["riding"], date, LIST_SOURCE,
                           party_dated=False)
        ctx.bc_members_added = getattr(ctx, "bc_members_added", 0) + len(found)
        resolver.members.update({m["key"]: {"name": m["name"], "surname": m["surname"], "given": m["given"]}
                                 for m, _ in found})
        resolver.terms.extend({"member_key": m["key"], "legislature": legislature, "party": None,
                               "riding": m["riding"], "start": date, "end": date, "party_dated": 0,
                               "source": LIST_SOURCE} for m, _ in found)
    if not ctx.dry_run:
        odd = {"split": [], "conflict": []}
        for key, party in pairs:
            what = extend_party(ctx.conn, key, legislature, party, date)
            if what:
                odd[what].append(key)
        if odd["split"]:
            ctx.log("  bc {0}: {1} member(s) listed in another party inside a run assumed between two "
                    "lists; the run is read again: {2}".format(date, len(odd["split"]), " ".join(odd["split"])))
        if odd["conflict"]:
            ctx.gap("bc {0}: {1} listed in two parties on that day; no party for them that day".format(
                date, " ".join(odd["conflict"])))
        ctx.conn.commit()
        return {"pairs": pairs, "split": odd["split"]}
    return {"pairs": pairs, "split": []}


def fetch_party_lists(ctx, legislature, session, listing, days, parts=None):
    """Read the member lists the votes need, then narrow every change.

    Read: each division day in `days` (the issue of the part that held a
    division, from `parts`), and the session's first and last listed
    sittings. A division day with no PDF, or an unreadable one, is covered
    only by the nearest lists either side: the same party on both, and the
    term spans it; else that day has no party. Then each window between a
    member's last sighting in one party and first in another is BISECTED
    through the session's listed sittings, until the change lies between two
    sittings in a row: as exact as the Hansard allows. Returns lists read."""
    pdfs = list_pdfs(listing)
    if not pdfs:
        return 0
    dates = sorted(pdfs)
    resolver = pn.Resolver.from_conn(ctx.conn, PROV)
    parts = parts or {}
    tried, seen, read = set(), set(), 0
    sightings, refuted = {}, set()

    def replay(keys):
        # A split run loses the sightings inside it; those read THIS run are
        # put back from memory (earlier runs' are read again by bisection).
        for day in sorted(sightings):
            for key in keys:
                party = sightings[day].get(key)
                if party and (key, day) not in refuted:
                    extend_party(ctx.conn, key, legislature, party, day)
        ctx.conn.commit()

    def read_day(day):
        nonlocal read
        tried.add(day)
        if ctx.budget is not None and ctx.budget.exhausted():
            return False
        # The part that held the division first, then the day's other part:
        # the 28 November 2017 morning issue prints no list, the afternoon's does.
        options = sorted(pdfs.get(day) or [], key=lambda o: o[0] != parts.get(day))
        for _part, url in options:
            got = read_party_list(ctx, legislature, day, url, resolver)
            if got is not None:
                read += 1
                seen.add(day)
                sightings[day] = dict(got["pairs"])
                if got["split"]:
                    replay(got["split"])
                return True
        return False

    for day in sorted(set(days) | {dates[0], dates[-1]}):
        if not ctx.refresh and covered(ctx.conn, legislature, day):
            continue
        if day in pdfs and read_day(day):
            continue
        if day not in days:
            continue
        if day not in pdfs:
            ctx.gap("bc {0}: no Hansard PDF listed for the day".format(day))
        for side in ([d for d in dates if d < day][-1:] + [d for d in dates if d > day][:1]):
            if side not in tried and not covered(ctx.conn, legislature, side):
                read_day(side)
        if not covered(ctx.conn, legislature, day):
            ctx.gap("bc {0}: no party at the vote that day (its own list unread and none read either "
                    "side covers it)".format(day))
    spent = 0
    while spent < BISECT_READS:
        refute_lone_lists(ctx, legislature, dates, seen, refuted)
        targets = set()
        for after, before in change_windows(ctx.conn, legislature):
            between = [d for d in dates if after < d < before and d not in tried]
            if between:
                targets.add(between[len(between) // 2])
        # a party seen on one sitting is believed when a sitting beside it agrees
        for _key, day in lone_lists(ctx.conn, legislature):
            for side in [d for d in dates if d < day][-1:] + [d for d in dates if d > day][:1]:
                if side not in tried:
                    targets.add(side)
        if not targets:
            break
        for day in sorted(targets):
            read_day(day)
            spent += 1
        if ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("bc member lists", read))
            break
    refute_lone_lists(ctx, legislature, dates, seen, refuted)
    return read


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

_RECORD = re.compile(r"^(\d{4})(\d{2})(\d{2})(am|pm)-Hansard-(?:v\d+)?n(\d+)\.html?$")


def list_records(listing, code):
    """[(date, part, issue, url)] House transcripts from the debates JSON.
    File names: '20260219am-Hansard-n119.html' from the 41st Parliament on,
    '20100531am-Hansard-v19n3.htm' (volume and number) in the 39th and 40th."""
    out = []
    for n in _nodes(listing):
        name = n.get("fileName") or ""
        m = _RECORD.match(name)
        if not m or not n.get("published", True):
            continue
        path = n.get("filePath") or "/Debates/" + code
        out.append(("{0}-{1}-{2}".format(*m.groups()[:3]), m.group(4), m.group(5),
                    FILE.format(path, name)))
    return sorted(set(out))


def _nodes(listing):
    return ((listing or {}).get("allHansardFileAttributes") or {}).get("nodes") or []


def unread_transcripts(listing):
    """House transcript file names the listing holds that list_records does
    not take: each one is a sitting silently never read (the 39th and 40th
    Parliaments' 'v19n3' names went unread until 2 October 2026)."""
    out = []
    for n in _nodes(listing):
        name = n.get("fileName") or ""
        if re.match(r"^\d{8}(am|pm)-Hansard-", name) and n.get("published", True) and not _RECORD.match(name):
            out.append(name)
    return sorted(out)


# Five markups since 2009, read alike: 'DivisionTable' with its headers in
# <th> (2026) or in <td><p class="DivisionHeader"> (2009-2017), and
# 'division-table' with <p class="division-header"> and lower-case,
# hyphenated paragraph classes (2018-2024). Classes are compared folded:
# 'Subject-Heading', 'SubjectHeading' and 'subject-heading' are one class.
# Also: '<table border="0" ... class="DivisionTable">' (2011); upper-case
# tags with unquoted classes, '<TABLE class=DivisionTable>' (2015); and a
# StyleLine left open before its table, '<p class="StyleLine">Amendment
# negatived on the following division:<br> <table ...>' (20 November 2014),
# so a paragraph ends at '</p>' or where a table begins, never inside one.
_DIV_CLASS = r'(?:"(?:DivisionTable|division-table)[^"]*"|(?:DivisionTable|division-table)\b)'
_BLOCK = re.compile(r'<p\b[^>]*?\bclass=(?:"([^"]*)"|([^\s>"]+))[^>]*>((?:(?!<table\b).)*?)(?:</p>|(?=<table\b))'
                    r'|<table\b[^>]*\bclass=' + _DIV_CLASS + r'[^>]*>(.*?)</table>', re.S | re.I)
_DIVISION_TABLE = re.compile(r'<table\b[^>]*\bclass=' + _DIV_CLASS, re.I)
# The House's own words for a recorded division, in every markup.
_DIVISION_WORDS = re.compile(r"on the following division", re.I)
# A division the transcript records WITHOUT names (60 of them 2010-2026): "Second
# reading of Bill 2 approved unanimously on a division. [See Votes and
# Proceedings.]" The names are printed only in the Votes and Proceedings.
_NO_NAMES = re.compile(r"unanimously on (?:a )?division|on (?:a )?division\.?\s*\[See Votes and Proceedings", re.I)
# The question put: "the question is ...", "the motion before you ... is"
# (2014), or the mover's own "I move the bill be introduced and read a first
# time now" (2017, where nobody restates it before the division).
_QUESTION = re.compile(r"question (?:before the House )?is\b|the motion before you|"
                       r"\bI move (?:that )?the bill be (?:introduced and )?read (?:for )?a "
                       r"(?:first|second|third) time", re.I)
_PAGE_NUMBER = re.compile(r'<span\b[^>]*\bclass="?PageNumber"?[^>]*>.*?</span>', re.S | re.I)
_HEAD = re.compile(r"^(YEAS|NAYS|ABSTENTIONS)\s*[—–-]+\s*(\d+)\s*$", re.I)


def parse_division_table(table_html, out=None, current=None):
    """{'Yea': (printed, [labels]), 'Nay': ...}. With `out` and `current`, a
    table CONTINUING a division (a page break splits the names into a second
    table, 2010-2012) adds to that division's lists."""
    out = {} if out is None else out
    for _tag, body in re.findall(r"<(th|td)[^>]*>(.*?)</\1>", table_html, re.S | re.I):
        # The printed page number can fall inside a cell, before a name or a
        # header: '<span class="PageNumber">[ <a name="8656">Page 8656</a> ]</span>'
        # (2014-2017), read as a name '[ Page 8656 ] NAYS — 45' until 2 October 2026.
        body = _PAGE_NUMBER.sub(" ", body)
        text = re.sub(r"\[\s*Page\s+\d+\s*\]", " ", html_text(body)).strip()
        text = re.sub(r"\s+", " ", text)
        # A header is a header in a <th> or a <td>: before 2018 'YEAS — 42'
        # sat in a <td colspan="3"> and was read as a NAME (the 19 gaps of 2017).
        h = _HEAD.match(text)
        if h:
            current = {"YEAS": "Yea", "NAYS": "Nay", "ABSTENTIONS": "Abstain"}[h.group(1).upper()]
            out[current] = (int(h.group(2)), [])
            continue
        if text and current:
            out[current][1].append(text)
    return out


def _last_section(parsed):
    return list(parsed)[-1] if parsed else None


def _klass(cls):
    return re.sub(r"[^a-z]", "", (cls or "").lower())


def stage_of(question):
    q = (question or "").lower()
    for word, stage in (("first", "First Reading"), ("second", "Second Reading"), ("third", "Third Reading")):
        # 'first reading', or the mover's 'read for a first time now' (2017)
        if re.search(r"\b{0} reading|read (?:for )?a {0} time".format(word), q):
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
    announced = False
    for m in _BLOCK.finditer(html or ""):
        cls, body, table = m.group(1) or m.group(2), m.group(3), m.group(4)
        if table is not None:
            if out and not announced:
                # No "on the following division" since the last table: this
                # one continues it (the names run on after a page break).
                last = out[-1]
                parsed = {k: (last["printed"][k], last["labels"][k]) for k in last["printed"]}
                parse_division_table(table, parsed, _last_section(parsed))
                last["printed"] = {k: v[0] for k, v in parsed.items()}
                last["labels"] = {k: v[1] for k, v in parsed.items()}
                last["tables"] = last.get("tables", 1) + 1
                paras = []
                continue
            announced = False
            question = next((p for p in reversed(paras[-14:]) if _QUESTION.search(p)), None)
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
        k = _klass(cls)
        if k in ("timestamp", "timeline"):
            ident = re.search(r'id="([^"]+)"', m.group(0))
            anchor = ident.group(1) if ident else anchor
            continue
        if k in ("businessheading", "proceduralheading", "procedureheading"):
            business, heading, debate = text, None, []
        elif k == "subjectheading":
            heading, debate = text, []
        elif text:
            paras.append(text)
            if _DIVISION_WORDS.search(text):
                announced = True
            elif _NO_NAMES.search(text):
                sentence = re.search(r"[^.\]]*(?:unanimously )?on (?:a )?division\.?(?:\s*\[See Votes and Proceedings\.?\])?",
                                     text, re.I)
                question = next((p for p in reversed(paras[-14:]) if _QUESTION.search(p)), None)
                out.append({"seq": len(out) + 1, "anchor": anchor, "heading": heading, "business": business,
                            "question": question, "result": " ".join(sentence.group(0).split()) if sentence else text,
                            "debate": list(debate), "printed": {}, "labels": {}, "presented": dict(presented),
                            "no_names": True})
            if k.startswith("speaker"):
                debate.append(text)
            p = re.search(r"presented a bill intituled (.+?)\.?$", text)
            if p:
                presented[p.group(1).strip()] = text
    return out


def bill_for(d, titles, leg, sess):
    """(bill_key, unnumbered_title) for a division."""
    for text in (d["heading"], d["question"]):
        m = re.search(r"\bBill (M?\d+)\b", text or "", re.I)      # 'BILL 2', 'BIll 21' (2010)
        if m:
            return ps.bill_key(PROV, leg, sess, m.group(1)), None
    head = pn.fold(re.sub(r"\s*\(Bill [^)]*\)", "", d["heading"] or ""))
    if head and head in titles:
        return titles[head], None
    for title in d["presented"]:
        if pn.fold(title) == head:
            return ps.bill_key(PROV, leg, sess, "x-" + slug(title)), title
    return None, None


def settle_by_elimination(votes, resolver, date, leg):
    """A bare surname two members share, where the SAME division names the
    other one by initial: 'Black' beside 'D. Black' (2010-2011) is Iain
    Black, because Dawn Black cannot vote twice. Only when exactly one
    candidate is left; the tally check still runs on the result."""
    taken = {v["member_key"] for v in votes if v.get("member_key")}
    for v in votes:
        how = str(v.get("how") or "")
        if v.get("member_key") or not how.startswith("ambiguous: "):
            continue
        left = [k.strip() for k in how[len("ambiguous: "):].split(",") if k.strip() not in taken]
        if len(left) == 1:
            v["member_key"], v["how"] = left[0], "surname (the other one is named in the same division)"
            v["party_at_vote"] = resolver.party_at(left[0], date, leg)
            taken.add(left[0])


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
    # The House's words count the divisions; a division table without them
    # still means at least one (a table can continue the one before it).
    printed_divisions = len(_DIVISION_WORDS.findall(page)) or (1 if _DIVISION_TABLE.search(page) else 0)
    if len(divisions) < printed_divisions:
        # The House says a division happened and we read fewer: a markup we
        # do not know (2018-2024's 'division-table' was read as 0 divisions,
        # status 'ok', in 725 sittings). Never 'ok': the sitting stays owed.
        gaps += 1
        ctx.gap("{0}: the transcript prints {1} recorded division(s) ('on the following division'), "
                "{2} parsed; the sitting stays owed".format(skey, printed_divisions, len(divisions)))
    for d in divisions:
        votes = []
        for position in ("Yea", "Nay", "Abstain"):
            for k, label in enumerate(d["labels"].get(position, []), 1):
                key, how = resolver.resolve(label, date, leg)
                votes.append({"position": position, "ordinal": k, "raw_label": label,
                              "member_key": key, "how": how,
                              "party_at_vote": resolver.party_at(key, date, leg) if key else None})
        settle_by_elimination(votes, resolver, date, leg)
        printed = {p: d["printed"].get(p) for p in ("Yea", "Nay", "Abstain")}
        ok, note = ps.tally(printed, votes)
        if d.get("no_names"):
            # Known and untrusted, but not owed: no re-read of the
            # transcript can give names it does not print.
            ok, note = None, ("no names: the transcript records {0!r}; the names are printed only in the "
                              "Votes and Proceedings".format(d["result"]))
        elif "Yea" not in d["printed"] or "Nay" not in d["printed"]:
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
        if ok is False:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        question = " | ".join(x for x in (d["heading"] or d["business"], d["question"]) if x) or None
        # Before 2018 the question is often not restated before the division:
        # the business heading ('Committee of the Whole House', 'Introduction
        # and First Reading') then says the stage.
        stage = stage_of(d["question"] if d["question"] else d["business"])
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": leg, "session": sess, "date": date,
            "seq": seq, "kind": "recorded", "question": question,
            "vote_on": vote_on(d["question"]),
            "bill_key": bkey, "stage": stage, "result": d["result"],
            "yeas": printed["Yea"], "nays": printed["Nay"], "abstentions": printed["Abstain"],
            "source_url": url + ("#" + d["anchor"] if d["anchor"] else ""),
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier, "excerpt": res.excerpt,
            "positions_ok": 1 if ok else 0, "tally_note": note, "votes": votes})
        stored.append((bkey, stage))
    ps.store_sitting(ctx.conn, PROV, skey, date, url, divisions=len(divisions),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return stored, gaps


def store_voice(ctx, leg, sess, read_dates):
    """Reading dates in the bills JSON, on days read, with no recorded
    division on that bill and stage: voice decisions."""
    n = 0
    # A reading stored as voice while its division went unparsed (2018-2024)
    # is withdrawn once the recorded division is stored.
    retracted = ctx.conn.execute(
        "DELETE FROM prov_divisions WHERE prov=? AND legislature=? AND session=? AND kind='voice' "
        "AND EXISTS (SELECT 1 FROM prov_divisions r WHERE r.prov=prov_divisions.prov AND r.kind='recorded' "
        "AND r.bill_key=prov_divisions.bill_key AND r.date=prov_divisions.date AND r.stage=prov_divisions.stage)",
        (PROV, leg, sess)).rowcount
    if retracted:
        ctx.log("  bc {0}-{1}: {2} voice decision(s) withdrawn: a recorded division of that bill, stage "
                "and day is now stored".format(leg, sess, retracted))
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
    every = list_records(listing, code)
    unread = unread_transcripts(listing)
    if unread:
        ctx.gap("bc {0}: {1} House transcript(s) listed in a file name list_records does not read "
                "(e.g. {2}); those sittings are not read".format(code, len(unread), unread[0]))
    if listing is not None and _nodes(listing) and not every:
        ctx.gap("bc {0}: the debates listing holds {1} file(s) but no House transcript was taken "
                "from it".format(code, len(_nodes(listing))))
    records = [r for r in every if ctx.in_window(r[0])]
    stats["records_listed"] = len(records)
    if ctx.dry_run:
        return stats
    cited = owe_cited(ctx, leg, sess, code, records)
    resolver = pn.Resolver.from_conn(ctx.conn, PROV).with_record(PROV)
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
    stats["index_misses"] = check_cited(ctx, leg, sess, records, cited)
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps,
                  "voice": store_voice(ctx, leg, sess, read_dates) if bills else 0})
    added = getattr(ctx, "bc_members_added", 0)
    stats.update(party_at_votes(ctx, leg, sess, listing))
    if getattr(ctx, "bc_members_added", 0) > added:
        # A member the API's roster lacks was found on the day's list of
        # members: the sittings their names left unresolved are read again.
        again = 0
        resolver = pn.Resolver.from_conn(ctx.conn, PROV).with_record(PROV)
        for date, part, issue, url in records:
            if ps.sitting_done(ctx.conn, url) or ctx.stop():
                continue
            again += 1
            stored, g = read_sitting(ctx, leg, sess, date, part, issue, url, resolver, wl, titles)
            stats["divisions"] += len(stored)
        ctx.log("  bc {0}-{1}: {2} sitting(s) read again with the members found on the lists".format(
            leg, sess, again))
        stats.update(party_at_votes(ctx, leg, sess, listing))
        stats["tally_gaps"] = ctx.conn.execute(
            "SELECT COUNT(*) FROM prov_divisions WHERE prov=? AND legislature=? AND session=? "
            "AND kind='recorded' AND positions_ok=0", (PROV, leg, sess)).fetchone()[0]
    return stats


# -- the Voting Records index: an independent record of every standing vote ----
#
# Each session's Hansard index ("/hdms/index/<code>", title "Voting Records")
# lists every member's standing votes, one page per letter. From the 41st
# Parliament each vote links the transcript and time it happened in
# ("../../Debates/42nd2nd/20210602pm-Hansard-n82.html#82B:1845"); the 39th's
# and 40th's print the vote without a link. A transcript the index cites that
# is stored with no division is a silent loss: 725 sittings of 2018-2024 were
# stored 'ok' with 0 divisions, their 'division-table' markup unread. Such a
# sitting is made OWED before the session is read, so the run reads it
# again, and anything still short after the read is a gap.

INDEX = "https://lims.leg.bc.ca/hdms/index/{0}"


def index_vote_files(index_json):
    """[(filePath, fileName)] of the session's Voting Records pages."""
    return [(n.get("filePath"), n.get("fileName")) for n in _nodes(index_json)
            if "voting" in (n.get("title") or "").lower() and n.get("fileName")]


def letter_pages(main_html, main_name):
    """The per-letter pages a Voting Records page links ('2018-votesb.htm')."""
    stem = re.sub(r"(?:mhds)?\.html?$", "", main_name or "").lower()
    out = []
    # '2026-Votesa.htm#mh1' from '2026-votesmhds.htm': the case differs
    for href in re.findall(r'href="([^"#/]+\.html?)(?:#[^"]*)?"', main_html or ""):
        if href.lower().startswith(stem) and href != main_name and href not in out:
            out.append(href)
    return out


def cited_transcripts(letter_html):
    """{transcript file name: {anchors}} a letter page links votes to."""
    out = {}
    for name, anchor in re.findall(r'href="[^"]*/Debates/[^"/]+/([^"/#]+\.html?)#([^"]+)"', letter_html or ""):
        out.setdefault(name, set()).add(anchor)
    return out


def fetch_cited(ctx, code):
    """{file name: {anchors}}: every transcript the session's Voting Records
    cite a standing vote in; {} where the index prints no links (39th, 40th)
    or cannot be read (a gap)."""
    raw = ctx.text(INDEX.format(code), "index-{0}".format(code))
    try:
        files = index_vote_files(json.loads(raw)) if raw else []
    except ValueError:
        ctx.gap("bc {0}: the Hansard index listing is not JSON".format(code))
        return {}
    out = {}
    for path, name in files:
        main = ctx.text(FILE.format(path, name), "votes-{0}".format(name))
        letters = letter_pages(main, name)
        for k, letter in enumerate(letters):
            if ctx.budget is not None and ctx.budget.exhausted():
                ctx.gap("bc {0}: the Voting Records index was not read to the end (time budget)".format(code))
                return out
            page = ctx.text(FILE.format(path, letter), "votes-{0}".format(letter))
            got = cited_transcripts(page)
            if not got and k == 0:
                break                        # an index without links: nothing to check
            for f, anchors in got.items():
                out.setdefault(f, set()).update(anchors)
    return out


def owe_cited(ctx, leg, sess, code, records):
    """Make OWED every sitting in the window the Voting Records cite a vote
    in but that is stored 'ok' with no division. Returns the citations."""
    if not records:
        return {}
    cited = fetch_cited(ctx, code)
    owed = 0
    for date, part, issue, url in records:
        if url.rsplit("/", 1)[-1] not in cited:
            continue
        n = ctx.conn.execute(
            "UPDATE prov_sittings SET status='owed' WHERE record_url=? AND status='ok' AND COALESCE(divisions, 0)=0",
            (url,)).rowcount
        owed += n
    ctx.conn.commit()
    if owed:
        ctx.log("  bc {0}: {1} sitting(s) stored with no division but cited by the Voting Records index; "
                "read again".format(code, owed))
    return cited


def check_cited(ctx, leg, sess, records, cited):
    """After the read: a cited transcript still holding no division is a gap."""
    n = 0
    for date, part, issue, url in records:
        if url.rsplit("/", 1)[-1] not in cited:
            continue
        row = ctx.conn.execute("SELECT divisions, status FROM prov_sittings WHERE record_url=? "
                               "ORDER BY read_at DESC LIMIT 1", (url,)).fetchone()
        if row and not row[0]:
            n += 1
            ctx.gap("bc {0}: the Voting Records index cites {1} standing vote(s) in {2}, none parsed".format(
                date, len(cited[url.rsplit("/", 1)[-1]]), url))
            ctx.conn.execute("UPDATE prov_sittings SET status='gap' WHERE record_url=?", (url,))
    ctx.conn.commit()
    return n


def party_at_votes(ctx, leg, sess, listing):
    """Read the member lists of the session's division days in the window
    (fetch_party_lists), then write party_at_vote onto EVERY stored vote of
    the session from the dated terms (prov_store.refresh_party): so a vote
    stored before its day's list was read -- the 8,508 of the first backfill
    -- gets its party without its transcript being fetched again."""
    days = {r[0] for r in ctx.conn.execute(
        "SELECT DISTINCT date FROM prov_divisions WHERE prov=? AND legislature=? AND session=? "
        "AND kind='recorded'", (PROV, leg, sess)) if ctx.in_window(r[0])}
    parts = {}
    for key, n in ctx.conn.execute(
            "SELECT sitting_key, divisions FROM prov_sittings WHERE prov=? AND sitting_key LIKE ? "
            "ORDER BY sitting_key", (PROV, "{0}-{1}-{2}-%".format(PROV, leg, sess))):
        m = re.search(r"-(\d{4}-\d{2}-\d{2})-(am|pm)$", key)
        if m and n:
            parts.setdefault(m.group(1), m.group(2))
    lists = fetch_party_lists(ctx, leg, sess, listing, days, parts) if listing else 0
    n, with_party = ps.refresh_party(ctx.conn, PROV, pn.Resolver.from_conn(ctx.conn, PROV), leg, sess)
    ctx.conn.commit()
    if lists or n:
        ctx.log("  bc {0}-{1}: {2} member list(s) read; {3} of {4} vote(s) carry a dated party".format(
            leg, sess, lists, with_party, n))
    return {"party_lists": lists, "votes_with_party": "{0}/{1}".format(with_party, n)}
