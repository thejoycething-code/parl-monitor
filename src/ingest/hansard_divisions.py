"""Commons divisions from before 9 March 2016, read from Hansard.

The Commons Votes API -- the source of every other Commons division here --
starts on 9 March 2016 (its division 2, an immigration SI). Everything the
2010 and 2015 Parliaments decided on our ground is therefore absent from the
ledger: the 2013 same-sex marriage Bill, the 2015 Assisted Dying (No. 2)
Bill, the 2011 abortion-counselling amendment. Christopher, 28 September
2026: "Build the pre-2016 votes collector."

Hansard holds those divisions with FULL voter lists, keyed on the same
member ids the ledger uses (MemberId 8 is Theresa May in both), measured the
same day:

  search/divisions.json   honours its date window only alongside a search
                          term; the term matches the debate title
  debates/division/<ExternalId>.json
                          AyeMembers / NoeMembers, IsTeller on each
  debates/debate/<DebateSectionExtId>.json
                          the debate, with the division as an item in it --
                          which is where the QUESTION is. The division's own
                          TextBeforeVote says only "The House having divided".

WHY THE QUESTION MATTERS. A division title names the Bill, not the question
(the Lords inversion of August 2026: an amendment vote read as a verdict on
the Bill). "Assisted Dying (No. 2) Bill" was the Second Reading;
"Health and Social Care (Re-committed) Bill" on 7 September 2011 was four
different questions, one of them Nadine Dorries's counselling amendment. The
question put -- "That the Bill be now read a Second time" -- is stored as the
division's notes, which record_votes makes the ledger excerpt, so the stance
model is shown what was actually decided.

OWN ID SPACE. Hansard numbers its divisions itself: its 1591 is the 2015
Assisted Dying vote, and Commons Votes 1591 is a different division years
later. So these ledger under their own prefix, div:h<Hansard Id>:<lobby>, and
can never be mistaken for, or merged with, a Votes API division.

Tellers are not ledgered, as everywhere else: a teller's lobby is the side
they count for, not a vote.
"""

from __future__ import annotations

import datetime
import re
from urllib.parse import quote

from src.ingest.divisions import Division, Voter

HANSARD = "https://hansard-api.parliament.uk"
# The first date the Commons Votes API holds. Hansard is the source BEFORE
# it and never on or after it, so no division can be counted twice.
FIRST_VOTES_API_DATE = "2016-03-09"
PREFIX = "h"
FEED = "hansard-division"

# "Question put accordingly, That the Bill be now read a Second time." The
# question runs to the first full stop followed by a capital or the end, so
# "(No. 2)" inside a Bill's name does not cut it short.
# The clerk ends a question with a full stop, or with ":—" where the
# division list follows (20 May 2013: "Question put, That the clause be read a
# Second time:—"). Captured without its terminator; _q() adds the stop.
_END = r"(?:\.|:\s*[\u2014\u2013-]*)(?=\s+[A-Z]|\s*$)"
QUESTION = re.compile(
    # "p ut" is Hansard's own typo (5 Feb 2013); the bracket may nest one
    # level: "(Standing Order No. 52(1)( a ))".
    r"Question\s+p\s?ut(?:\s+(?:forthwith|accordingly))?"
    r"(?:\s*\((?:[^()]|\([^()]*\))*\))?\s*,\s*"
    r"(That\b.*?)" + _END, re.S)
# "Hopkins, Kelvin" / "May, rh Mrs Theresa" / "Walker, Mr Charles"
HONORIFIC = re.compile(r"^(?:rh\s+)?(?:(?:Mr|Mrs|Ms|Miss|Dr|Sir|Dame|Lady|Lord|Rev|Prof)\.?\s+)*",
                       re.I)


def _slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-")[:60]


def search(client, term, start, end, house="Commons", page=100):
    """Hansard's division search: [row dicts], every page.

    `end` is clamped to the day before the Votes API begins -- after that,
    the Votes API is the record.
    """
    last = (datetime.date.fromisoformat(FIRST_VOTES_API_DATE)
            - datetime.timedelta(days=1)).isoformat()
    end = min(end, last)
    if start > end:
        return []
    out, skip = [], 0
    while True:
        url = ("{0}/search/divisions.json?queryParameters.searchTerm={1}"
               "&queryParameters.startDate={2}&queryParameters.endDate={3}"
               "&queryParameters.house={4}&queryParameters.skip={5}"
               "&queryParameters.take={6}").format(
                   HANSARD, quote(term), start, end, house, skip, page)
        payload = client.get_json(url, FEED, "hsearch-{0}-{1}-{2}-{3}".format(
            _slug(term), start, end, skip)) or {}
        rows = payload.get("Results") or []
        out.extend(rows)
        skip += len(rows)
        if not rows or skip >= int(payload.get("TotalResultCount") or 0):
            return out


def fetch(client, external_id):
    """The division with its voter lists."""
    return client.get_json("{0}/debates/division/{1}.json".format(HANSARD, external_id),
                           FEED, "hdetail-{0}".format(external_id))


def _text(item):
    return " ".join(re.sub(r"<[^>]+>", " ", item.get("Value") or "").split())


# What the clerk writes when a question is proposed:
#   "Amendment proposed: 1176, page 2, line 7 ..."   "Motion made, and Question put ..."
#   "New Clause 2" (a bare heading, the clause's title and text follow)
# NOT "Amendment made: 402": an amendment already AGREED without a division.
PROPOSED = re.compile(r"^(?:(?:Amendment|New Clause)\b[^:]{0,40}proposed|Motion made|New Clause\s+\d+\s*$)",
                      re.I)
# The clerk closes an amendment's or clause's text with its mover:
# "...—(Nadine Dorries.)", "”— (John Mann.)"
CLERK_MOVER = re.compile(r"[\u2014\u2013-]\s*\(([^()]{3,80}?)\.?\)\s*$")
MOVE = re.compile(r"\bI beg to move\b", re.I)
# A question interrupted at the programme deadline: "The Deputy Speaker put
# forthwith the Question already proposed from the Chair (Standing Order
# No. 83E), That the clause be read a Second time."
CHAIR_QUESTION = re.compile(r"Question already proposed from the Chair(?:\s*\([^)]*\))?\s*,\s*"
                            r"(That\b.*?)" + _END, re.S)
SPLIT_QUESTION = re.compile(r"\bQuestion\s+p\s?ut\b(?!.*\bThat\b)", re.S)
BEG_QUESTION = re.compile(r"\bI beg to move,\s*(That\b.*?)" + _END)


def _q(text):
    return text.strip() + "."


def context_in(debate, division_external_id):
    """{question, proposed, mover} for one division, from its debate's items.

    Everything comes from the division's OWN stretch of debate -- since the
    previous division -- so a debate with several votes cannot lend one
    vote's question or mover to another.

    question -- the last "Question put ..., That ..." (or a question "already
        proposed from the Chair", put forthwith at a programme deadline) in
        that stretch. After a closure the substantive question comes second,
        often in the same paragraph. Failing both, the motion the mover
        opened with: "I beg to move, That the Bill be now read the Third time."

    proposed, mover -- the proposal NEAREST BEFORE the question. A report
        stage debates several groups before its first division, and the
        division is on the latest: on 23 February 2015 the Solicitor-General
        moved the first group, but the 201-292 vote was on Fiona Bruce's new
        clause, moved last. Either the clerk's line ("Amendment proposed:
        1176 ...", "New Clause 2"), whose mover is ONLY the clerk's closing
        "—(Name.)", or a member's "I beg to move", whose mover is its
        speaker. "That the amendment be made" alone says nothing a reviewer
        can sign off, and the direction rule needs the mover's own vote.
    """
    items = sorted((debate or {}).get("Items") or [],
                   key=lambda it: it.get("OrderInSection") or 0)
    at = next((i for i, it in enumerate(items)
               if it.get("ItemType") == "Division"
               and str(it.get("ExternalId")) == str(division_external_id)), None)
    out = {"question": None, "proposed": None, "mover": None}
    if at is None:
        return out
    since = 0
    for i in range(at - 1, -1, -1):
        if items[i].get("ItemType") == "Division":
            since = i + 1
            break
    segment = items[since:at]
    texts = [_text(it) for it in segment]

    q_at = None
    for i in range(len(segment) - 1, -1, -1):
        found = QUESTION.findall(texts[i]) or CHAIR_QUESTION.findall(texts[i])
        if found:
            out["question"], q_at = _q(found[-1]), i
            break
        # The clerk sometimes splits it: "Motion made, and Question put
        # forthwith (Standing Order No. 52(1)(a))" as one item, the motion --
        # "That, for the purposes of any Act ..." -- as the NEXT (5 February
        # 2013, the money and carry-over motions).
        if SPLIT_QUESTION.search(texts[i]) and i + 1 < len(segment) \
                and texts[i + 1].startswith("That"):
            motion = re.split(r"[\u2014\u2013]|\.(?=\s|$)", texts[i + 1])[0]
            out["question"], q_at = _q(motion[:200]), i
            break
    if out["question"] is None:
        for t in texts:
            got = BEG_QUESTION.search(t)
            if got:
                out["question"] = _q(got.group(1))
                break
    limit = q_at if q_at is not None else len(segment)

    nearest = None
    for i in range(limit - 1, -1, -1):
        if PROPOSED.search(texts[i]):
            nearest = ("clerk", i)
            break
        if MOVE.search(texts[i]):
            nearest = ("move", i)
            break
    if nearest is None:
        return out
    kind, i = nearest
    if kind == "clerk":
        head = texts[i]
        if re.match(r"New Clause\s+\d+\s*$", head, re.I) and i + 1 < limit:
            head = "{0}: {1}".format(head, texts[i + 1])      # the clause's title
        out["proposed"] = head[:240]
        for t in texts[i:limit]:
            got = CLERK_MOVER.search(t)
            if got:
                out["mover"] = got.group(1).strip()
                break
    else:
        out["mover"] = " ".join((segment[i].get("AttributedTo") or "").split()) or None
        out["proposed"] = texts[i][MOVE.search(texts[i]).start():][:240]
    return out


def question_in(debate, division_external_id):
    return context_in(debate, division_external_id)["question"]


def context(client, section_external_id, division_external_id):
    """context_in() for a division, fetching (and archiving) its debate."""
    if not section_external_id:
        return {"question": None, "proposed": None, "mover": None}
    try:
        debate = client.get_json("{0}/debates/debate/{1}.json".format(
            HANSARD, section_external_id), FEED, "hdebate-{0}".format(section_external_id))
    except Exception:                                       # noqa: BLE001
        return {"question": None, "proposed": None, "mover": None}
    return context_in(debate, division_external_id)


def question_put(client, section_external_id, division_external_id):
    return context(client, section_external_id, division_external_id)["question"]


def display_name(list_as):
    """"May, rh Mrs Theresa" -> "Theresa May". A name with no comma is
    already in display order ("Heidi Alexander", the tellers)."""
    text = " ".join((list_as or "").split())
    if "," not in text:
        return text or None
    surname, rest = text.split(",", 1)
    rest = HONORIFIC.sub("", rest.strip())
    return " ".join(p for p in (rest, surname.strip()) if p) or None


def parse(payload, question=None):
    """(Division, [Voter]) in the shapes intel.record_votes takes. Tellers out."""
    date = datetime.date.fromisoformat((payload.get("Date") or "")[:10])
    section = " ".join((payload.get("DebateSection") or "").split())
    # THE QUESTION GOES IN THE TITLE, which record_votes makes the ledger line
    # the stance model reads. Hansard titles every division of a debate by
    # its Bill: all ten 2013 same-sex marriage divisions read "Marriage (Same
    # Sex Couples) Bill" -- the Second Reading, the report-stage clauses and
    # the programme motions alike. Read bare, "Voted Aye" on a clause looks
    # like a vote FOR THE BILL, which is the Lords inversion again. Where no
    # question was found, the line says so rather than letting the title
    # stand for it.
    title = "{0}: {1}".format(section, question) if question else \
        "{0} (question not recorded: may be an amendment or procedural motion, " \
        "not the Bill itself)".format(section)
    division = Division(
        id=int(payload["Id"]), house="Commons", number=payload.get("Number"),
        title=title,
        date=date, aye_count=payload.get("AyesCount"), no_count=payload.get("NoesCount"),
        notes=("Question put: " + question) if question else None)
    voters = []
    for key, vote in (("AyeMembers", "aye"), ("NoeMembers", "no")):
        for m in payload.get(key) or []:
            if m.get("IsTeller") or not m.get("MemberId"):
                continue
            voters.append(Voter(member_id=m["MemberId"], name=display_name(m.get("ListAs")),
                                party=m.get("Party"), seat=m.get("MemberFrom"), vote=vote))
    return division, voters


def to_votes_api_shape(payload):
    """A Hansard division rewritten in the Commons Votes API vocabulary, so the
    tracker page renders it like any other (make_vote_tracker)."""
    def side(key, tellers):
        return [{"MemberId": m.get("MemberId"), "Name": display_name(m.get("ListAs")),
                 "Party": m.get("Party"), "MemberFrom": m.get("MemberFrom")}
                for m in payload.get(key) or [] if bool(m.get("IsTeller")) == tellers]
    return {
        "DivisionId": payload.get("Id"),
        "Source": "hansard",
        "ExternalId": payload.get("ExternalId"),
        "SectionExtId": payload.get("DebateSectionExtId"),
        "House": "Commons",
        "Title": " ".join((payload.get("DebateSection") or "").split()),
        "Date": (payload.get("Date") or "")[:10],
        "Ayes": side("AyeMembers", False),
        "Noes": side("NoeMembers", False),
        "AyeTellers": side("AyeMembers", True),
        "NoTellers": side("NoeMembers", True),
        "NoVoteRecorded": [],
        "AyeCount": payload.get("AyesCount"),
        "NoCount": payload.get("NoesCount"),
    }
