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
QUESTION = re.compile(
    r"Question\s+put(?:\s+(?:forthwith|accordingly))?(?:\s*\([^)]*\))?\s*,\s*"
    r"(That\b.*?\.)(?=\s+[A-Z]|\s*$)", re.S)
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


# "Amendment proposed: 1176, ..." / "New Clause 1 ... proposed" / "Motion made".
# NOT "Amendment made: 402": that is an amendment already AGREED without a
# division, which is exactly the one the vote is not about.
PROPOSED = re.compile(r"^(?:(?:Amendment|New Clause)\b[^:]{0,40}proposed|Motion made)", re.I)
# The clerk closes an amendment's text with its mover: "...—(Nadine Dorries.)"
CLERK_MOVER = re.compile(r"[\u2014\u2013-]\s*\(([^()]{3,80}?)\.?\)\s*$")
MOVE = re.compile(r"\bI beg to move\b", re.I)


def context_in(debate, division_external_id):
    """{question, proposed, mover} for one division, from its debate's items.

    question -- the LAST "Question put ..., That ..." before the division
        item: a closure ("That the Question be now put") is agreed first and
        the substantive question put after it, often in the same paragraph.
    proposed, mover -- WHAT was put and BY WHOM, looked for only in the
        stretch of debate since the previous division, so a debate with four
        amendment votes cannot lend one amendment's text to another. The
        clerk's "Amendment proposed: 1176, page 2, line 7 ..." when it is
        there, with the mover taken ONLY from the clerk's closing "—(Name.)";
        otherwise the opening "I beg to move amendment ..." and the member
        it is attributed to. "That the amendment be made" alone says
        nothing a reviewer can sign off, and the direction rule needs the
        mover's own vote.
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
    # The question, too, only from this division's own stretch: scanning
    # further back gave the Health and Social Care Bill's Third Reading
    # (7 Sept 2011, 316-251) the previous amendment's "That the amendment be
    # made". Where the clerk wrote no "Question put, That ...", the motion is
    # the one the mover opened with: "I beg to move, That the Bill be now
    # read the Third time."
    for it in reversed(segment):
        found = QUESTION.findall(_text(it))
        if found:
            out["question"] = found[-1]
            break
    if out["question"] is None:
        for it in segment:
            got = re.search(r"\bI beg to move,\s*(That\b.*?\.)(?=\s+[A-Z]|\s*$)", _text(it))
            if got:
                out["question"] = got.group(1)
                break
    clerk = [i for i, it in enumerate(segment) if PROPOSED.search(_text(it))]
    if clerk:
        # The clerk's own line, and the mover only from the clerk's own
        # attribution at the end of the amendment's text. Never a nearby
        # "I beg to move": in a debate on a group of amendments that is
        # usually someone else's (7 Sept 2011: a minister's, for an
        # Opposition amendment). No attribution found means no mover given.
        out["proposed"] = _text(segment[clerk[-1]])[:240]
        for it in segment[clerk[-1]:]:
            got = CLERK_MOVER.search(_text(it))
            if got:
                out["mover"] = got.group(1).strip()
        return out
    moved = next((it for it in segment if MOVE.search(_text(it))), None)
    if moved is not None:
        # No clerk line: the question is the one opened by this speech, and
        # its speaker moved it (Nadine Dorries, amendment 1, 7 Sept 2011).
        out["mover"] = " ".join((moved.get("AttributedTo") or "").split()) or None
        text = _text(moved)
        out["proposed"] = text[MOVE.search(text).start():][:240]
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
    division = Division(
        id=int(payload["Id"]), house="Commons", number=payload.get("Number"),
        title=" ".join((payload.get("DebateSection") or "").split()),
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
