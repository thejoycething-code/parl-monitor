"""NI Assembly Hansard: what a division was actually about.

A DivisionSubject names an amendment NUMBER and never its content -- "Amendment
97 - Consideration Stage: Justice Bill (NIA Bill 7/22-27) (Day 4) [Mr Timothy
Gaston]" -- and is truncated at 100 characters. Nothing can classify that, which
is why ni_divisions.areas sat empty on all 139 rows. Hansard carries the
amendment's own wording, and that can be classified: amendment 97 is
"Accommodation of women prisoners", which is area 5, while amendments 79-86 on
the same day are "Minimum age of criminal responsibility" and are correctly
nothing to do with us.

TWO EXACT KEYS, both verified against the live store on 2026-08-18. Neither is
a string match, and using either instead of a string match is the whole reason
this module is reliable:

  * A component of type "Division" carries RelatedItemId == the division's
    DocumentID. Verified 7 of 7 on 2026-06-30 and 139 of 139 across every
    division date. This IDENTIFIES the division; no amendment-number regex is
    needed for that job.
  * That same component's ParentComponentId is the ComponentId of its enclosing
    "Header". This SCOPES the window.

DO NOT SCAN BACKWARDS FOR THE NEAREST HEADER. It looks equivalent and is not:
a division can sit hundreds of components after its own header, and the nearest
preceding one then belongs to different business entirely. Measured: on
2026-04-20 division 477724 ("Final Stage: Hospital Parking Charges Bill") was
attributed to a Marriage and Civil Partnership Bill motion and classified area 9
on "civil partnership". The parent pointer resolves it correctly.

DO NOT GATE ON A NAME COMPARISON EITHER. Hansard inverts word order -- header
"Hate: Executive Approach" against subject "The Executive's Approach to Hate" --
so bill_matches(bill_of(subject), header) rejected 23 of 139 CORRECT windows.
The parent pointer is authoritative; a name mismatch is worth reporting, never
worth acting on.

ComponentHeader is NOT a scope key. It is header DEPTH: its values across one
sitting are "level 1", "level 2", "level 3" and a time. The scope is the
component whose ComponentType is "Header", which is a different field.

THE CUE-LINE GRAMMAR, as measured:

  BILL AMENDMENT
    Procedure Line     "Amendment No 97 proposed:"   (or "... proposed on 15 June 2026:")
    Bill Text          "After clause 30 insert-- Accommodation of women prisoners ..."
    Procedure Line     "Question put, That amendment No 97 be made."
    Division           RelatedItemId=493329

  MOTION, PLURAL AMENDMENTS
    Procedure Line     "Which amendments were:"
    Plenary Item Text  "No 1: Leave out all after "Assembly" and insert: ..."
    Plenary Item Text  "No 2: ..."
    Division

  MOTION, SINGLE AMENDMENT
    Procedure Line     "Which amendment was:"        (singular, and UNNUMBERED)
    Plenary Item Text  the amendment

  WHOLE QUESTION (Second/Final Stage, or a motion with no amendment)
    Plenary Item Text  "That the Hospital Parking Charges Bill ... do now pass."
    Procedure Line     "Question put."

The "Question put..." line is the authoritative statement of WHAT WAS VOTED ON
-- whether it was an amendment at all, and which number. It disagrees with the
subject line (80 amendment votes by Hansard against 83 by the subject regex),
and Hansard wins: the subject is a rendered label.
"""

from __future__ import annotations

import datetime
import html
import json
import os
import re
from dataclasses import dataclass, field

from src.ingest import niassembly

HANSARD_BY_DATE = (niassembly.BASE + "/hansard.asmx/"
                   "GetHansardComponentsByPlenaryDate_JSON?plenaryDate={date}")

# ComponentType values we depend on. ComponentTypeId is the stable numeric code
# and ComponentType is a display string with variants -- "Speaker (MlaName)",
# "(DeputySpeaker)" and "(PrincipalDeputySpeaker)" are all typeId 2 -- so both
# are read and the pairing is asserted in tests. The DivisonType misspelling in
# niassembly.parse_divisions is the same lesson: an upstream rename must not
# silently empty every window.
HEADER = "Header"
DIVISION = "Division"
PROCEDURE = "Procedure Line"
BILL_TEXT = "Bill Text"
ITEM_TEXT = "Plenary Item Text"

TYPE_IDS = {HEADER: "0", DIVISION: "7", PROCEDURE: "8", BILL_TEXT: "12"}

# Evidence provenance, explicit and never optional -- the same discipline as
# ni_store.party_at returning a source. An unmarked fallback is indistinguishable
# from the real thing, and that is the bug that filed Doug Beattie's UUP
# questions under Independent.
AMENDMENT_TEXT = "amendment-text"   # the amendment's own operative wording
ITEM_ONLY = "item-text"             # only the motion or bill question was found
NO_TEXT = "no-text"                 # nothing recovered; areas MUST stay unset

_TAGS = re.compile(r"<[^>]+>")
# "Question put, That amendment No 97 be made." / "Question put."
_QUESTION = re.compile(r"^Question\s+put", re.I)
_Q_NUMBER = re.compile(r"amendment\s+No\s*(\d+)", re.I)
# "Amendment No 97 proposed:" / "Amendment No 79 proposed on 15 June 2026:"
_PROPOSED = re.compile(
    r"^Amendment\s+No\s*(\d+)\s+(?:proposed|made)"
    r"(?:\s+on\s+(\d{1,2}\s+\w+\s+\d{4}))?", re.I)
# "Which amendments were:" / "Which amendment was:"
_WHICH = re.compile(r"^Which\s+amendments?\s+(?:was|were)\s*:", re.I)
# "I beg to move amendment No 1:" -- a THIRD opener, and the one that matters
# most for motion amendments moved during the debate rather than listed up
# front. It arrives as Spoken Text, not a Procedure Line, and its wording
# follows as Plenary Item Text. Omitting it left the two "Hate: Executive
# Approach" divisions of 2025-09-22 unexplained.
# The number is OPTIONAL: a motion that drew exactly one amendment reads "I beg
# to move the following amendment:" with no number at all, and its question line
# is likewise "Question put, That the amendment be made." Requiring a number
# left most of the 24 unresolved divisions unexplained.
_BEG_TO_MOVE = re.compile(
    r"beg\s+to\s+move\s+(?:the\s+following\s+)?amendment(?:\s+No\s*(\d+))?\s*:",
    re.I)
# "No 1: Leave out all after ..." -- the numbered form inside a motion block
_NUMBERED = re.compile(r"^No\s+(\d+)\s*:\s*", re.I)

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def clean(text):
    """Tags out, entities decoded, whitespace collapsed.

    Entities matter: every Bill Text opens with &quot;, and src/filter.py's
    _TAG_RE strips tags only. scotland.strip_html does the same job; this is
    kept local so the Hansard parser has no cross-ingester import.
    """
    return re.sub(r"\s+", " ", html.unescape(_TAGS.sub(" ", text or ""))).strip()


def _spoken_date(value):
    """'15 June 2026' -> date. Returns None rather than guessing."""
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", (value or "").strip())
    if not m:
        return None
    month = MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return datetime.date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


@dataclass
class Component:
    component_id: str
    parent_id: str
    kind: str                   # ComponentType, verbatim
    type_id: str                # ComponentTypeId, the stable code
    text: str
    related_id: str             # POLYMORPHIC -- see below
    level: str                  # ComponentHeader: header DEPTH, not a scope

    # related_id is a division DocumentID on a Division, a plenary item id on a
    # Header, and a PersonId on a Speaker row. Never read it without checking
    # `kind` first, or a PersonId gets attributed to a division.


@dataclass
class Sitting:
    when: datetime.date
    components: list = field(default_factory=list)

    def index_of(self, component_id):
        for i, c in enumerate(self.components):
            if c.component_id and c.component_id == component_id:
                return i
        return None

    def anchors(self):
        """{division doc_id: index} -- the exact identification key."""
        return {c.related_id: i for i, c in enumerate(self.components)
                if c.kind == DIVISION and c.related_id}

    def ordered(self):
        """Is ComponentId monotonically increasing?

        Document order is load-bearing for every window and nothing in the
        payload guarantees it, so a caller checks rather than assumes.
        """
        seen = [int(c.component_id) for c in self.components
                if (c.component_id or "").isdigit()]
        return seen == sorted(seen)


@dataclass
class Evidence:
    doc_id: str                 # division DocumentID: the exact join key
    when: datetime.date
    item_id: str = ""           # Header.RelatedItemId -- an ID, not a title
    item_name: str = ""         # Header text, UNTRUNCATED, with stage
    question: str = ""          # the 'Question put...' line, verbatim
    amendment_no: int = None    # from the question line; None when unnumbered
    on_amendment: bool = False  # the vote was on an amendment, not the whole item
    amendment_text: str = ""    # '' when not recovered -- NEVER the item text
    item_text: str = ""         # the motion, or 'That the Bill do now pass'
    source: str = NO_TEXT

    @property
    def classify_fields(self):
        """(title, body) for filter_item, in that order.

        A MOTION amendment is a DIFF -- "Leave out all after 'environment;' and
        insert:" means nothing on its own -- so the motion travels with it as
        context. A BILL amendment is self-contained and gets NO context, so a
        broad motion cannot lend it areas. Same reasoning as the title/body
        split in filter_item.
        """
        if self.source == AMENDMENT_TEXT:
            if self.item_text and not self.amendment_text.lower().startswith(
                    ("after clause", "before clause", "in clause", "in page",
                     "leave out clause", "clause")):
                return self.item_name, "{0}\n{1}".format(
                    self.amendment_text, self.item_text)
            return self.item_name, self.amendment_text
        if self.source == ITEM_ONLY:
            return self.item_name, self.item_text
        return self.item_name, ""


def parse_sitting(payload, when):
    out = []
    for row in niassembly.rows(payload, "AllHansardComponentsList",
                               "HansardComponent"):
        out.append(Component(
            component_id=str(row.get("ComponentId") or ""),
            # Absent on many components, so JSON omits the key entirely.
            parent_id=str(row.get("ParentComponentId") or ""),
            kind=(row.get("ComponentType") or "").strip(),
            type_id=str(row.get("ComponentTypeId") or ""),
            text=clean(row.get("ComponentText")),
            related_id=str(row.get("RelatedItemId") or ""),
            level=(row.get("ComponentHeader") or "").strip()))
    return Sitting(when=when, components=out)


def _question_for(sitting, division_index, look_back=6):
    """The 'Question put...' line immediately preceding a division."""
    for i in range(division_index - 1, max(-1, division_index - look_back - 1), -1):
        c = sitting.components[i]
        if c.kind == PROCEDURE and _QUESTION.search(c.text):
            return c.text
    return ""


def _candidates(sitting, start, end):
    """Amendment texts and the item text inside one window.

    Returns ({number_or_None: text}, item_text). Numbers restart per motion --
    "No 1..No 3" can appear twice in one afternoon under different motions --
    which is exactly why the window bounds the search: within one window a
    number is unique.
    """
    amendments, unnumbered, item_text = {}, [], ""
    i = start
    while i < end:
        c = sitting.components[i]
        if c.kind == PROCEDURE:
            m = _PROPOSED.match(c.text)
            if m:
                # Adjacency is not guaranteed to be +1, so look ahead a little
                # rather than assuming the very next component.
                for j in range(i + 1, min(end, i + 4)):
                    if sitting.components[j].kind == BILL_TEXT:
                        amendments[int(m.group(1))] = sitting.components[j].text
                        break
                i += 1
                continue
            if _WHICH.match(c.text):
                for j in range(i + 1, end):
                    nxt = sitting.components[j]
                    if nxt.kind != ITEM_TEXT:
                        break
                    num = _NUMBERED.match(nxt.text)
                    if num:
                        amendments[int(num.group(1))] = _NUMBERED.sub("", nxt.text)
                    else:
                        unnumbered.append(nxt.text)
                    i = j
                i += 1
                continue
        else:
            beg = _BEG_TO_MOVE.search(c.text)
            if beg:
                for j in range(i + 1, min(end, i + 4)):
                    if sitting.components[j].kind == ITEM_TEXT:
                        body = _NUMBERED.sub("", sitting.components[j].text)
                        if not body:
                            break
                        if beg.group(1):
                            amendments[int(beg.group(1))] = body
                        else:
                            unnumbered.append(body)
                        break
            elif c.kind == ITEM_TEXT and not _NUMBERED.match(c.text):
                # The FIRST such component is the item as moved, pre-amendment.
                if not item_text:
                    item_text = c.text
        i += 1
    return amendments, unnumbered, item_text


def _windows_for_item(sitting, item_id):
    """(start, end) for every window whose Header names `item_id`.

    One debate can span several Header instances -- on 2025-09-22 the A5 motion
    appears under two -- so the amendments may have been moved under an earlier
    instance than the one the division sits in. Keyed on the item ID, never on
    the header NAME: Hansard inverts word order ("Hate: Executive Approach"),
    and name matching rejected 23 of 139 correct windows.
    """
    out, starts = [], []
    for i, c in enumerate(sitting.components):
        if c.kind == HEADER:
            starts.append((i, c.related_id))
    for n, (i, related) in enumerate(starts):
        if related and related == item_id:
            end = starts[n + 1][0] if n + 1 < len(starts) else len(sitting.components)
            out.append((i + 1, end))
    return out


def evidence_for(sitting, doc_ids, hints=None):
    """Evidence per division. Returns (list[Evidence], gaps).

    `hints` is {doc_id: amendment_number} taken from the division SUBJECT. The
    Hansard question line is authoritative when it carries a number, but it
    often reads "Question put, That the amendment be made." with no number even
    where several amendments were moved -- 4 of 7 divisions on 2026-06-30. The
    subject's number resolves those, so it is used only as a fallback.

    Every division is returned, including those with no recoverable text, so a
    caller can count what it could not explain rather than quietly showing
    fewer rows.
    """
    hints = hints or {}
    gaps = []
    if not sitting.ordered():
        return [], ["{0}: components are not in ComponentId order; refusing to "
                    "window this sitting".format(sitting.when)]
    anchors = sitting.anchors()
    out = []
    for doc_id in doc_ids:
        index = anchors.get(doc_id)
        if index is None:
            gaps.append("division {0} ({1}): no Division component in Hansard"
                        .format(doc_id, sitting.when))
            continue
        ev = Evidence(doc_id=doc_id, when=sitting.when)
        parent = sitting.components[index].parent_id
        header_at = sitting.index_of(parent) if parent else None
        if header_at is None or sitting.components[header_at].kind != HEADER:
            gaps.append("division {0} ({1}): ParentComponentId {2!r} is not a "
                        "Header; not scoped".format(doc_id, sitting.when, parent))
            out.append(ev)
            continue
        header = sitting.components[header_at]
        ev.item_id, ev.item_name = header.related_id, header.text
        ev.question = _question_for(sitting, index)
        ev.on_amendment = "amendment" in (ev.question or "").lower()
        num = _Q_NUMBER.search(ev.question or "")
        ev.amendment_no = int(num.group(1)) if num else None

        amendments, unnumbered, item_text = _candidates(
            sitting, header_at + 1, index)
        ev.item_text = item_text
        # The question line wins when numbered; the subject is the fallback.
        wanted = ev.amendment_no
        if wanted is None and ev.on_amendment:
            wanted = hints.get(doc_id)
        # WIDEN, same day only: the amendments may have been moved under an
        # earlier Header instance of the same item. Keyed on item_id.
        if ev.on_amendment and wanted is not None and wanted not in amendments:
            for start, end in _windows_for_item(sitting, ev.item_id):
                if start > index:
                    continue
                more, more_un, more_item = _candidates(sitting, start, end)
                amendments.update(more)
                if not item_text and more_item:
                    ev.item_text = item_text = more_item
                if wanted in amendments:
                    break
        # AMENDMENT_TEXT is only ever set with text actually in hand. An empty
        # string here would leave classify_fields returning the MOTION under an
        # amendment label -- which is the unmarked-fallback bug this module
        # exists to prevent, and it did happen: division 476834 classified area
        # 5 off its motion while claiming source=amendment-text.
        amendments = {k: v for k, v in amendments.items() if v}
        unnumbered = [u for u in unnumbered if u]
        if not ev.on_amendment:
            ev.source = ITEM_ONLY if item_text else NO_TEXT
        elif wanted is not None and wanted in amendments:
            ev.amendment_no = wanted
            ev.amendment_text = amendments[wanted]
            ev.source = AMENDMENT_TEXT
        elif len(unnumbered) == 1 and not amendments:
            # A motion that drew exactly one amendment: Hansard numbers neither
            # the proposal ("I beg to move the following amendment:") nor the
            # question ("That the amendment be made."), while the SUBJECT still
            # says "Amendment 1". Requiring wanted to be None here meant the
            # subject hint disqualified the very case it was meant to help, so
            # the sole unnumbered candidate wins whenever no numbered one exists.
            ev.amendment_text = unnumbered[0]
            ev.source = AMENDMENT_TEXT
        else:
            # NEVER substitute the item text for a missing amendment. A motion's
            # areas standing in for an amendment that guts it is precisely the
            # unmarked-fallback bug this codebase keeps designing out.
            ev.source = NO_TEXT
            gaps.append(
                "division {0} ({1}): {2!r} but no amendment text under item "
                "{3} on this date".format(
                    doc_id, sitting.when,
                    (ev.question or "no question line")[:56], ev.item_id or "?"))
        out.append(ev)
    return out, gaps


def fetch_sitting(client, when, timeout=120):
    """One sitting day. Returns (Sitting_or_None, error_or_None).

    Errors are returned because this is called once per date over dozens of
    dates and one 500 must not lose the rest -- the convention for every
    looped fetch in niassembly.py.
    """
    day = when.isoformat() if hasattr(when, "isoformat") else str(when)
    try:
        payload = client.get_json(HANSARD_BY_DATE.format(date=day),
                                  "niassembly", "hansard-{0}".format(day),
                                  timeout=timeout)
    except Exception as exc:                      # noqa: BLE001 - reported up
        return None, "{0}: {1}".format(type(exc).__name__, exc)
    return parse_sitting(payload, _as_date(day)), None


def load_sitting(raw_dir, day):
    """A sitting from the archive, without touching the network.

    HttpClient is write-only -- it archives every response but never reads one
    back -- so re-classification would re-fetch all fifty-odd sittings on every
    run without this. Same offline-recovery route as stance.build_text_map: the
    fetch already wrote the payload, so use it.

    The archive is laid out data/raw/<fetch date>/<feed>_<slug>.json.gz, and the
    fetch date is NOT the sitting date, so the file is found by glob across
    every archive date and the newest copy wins.
    """
    import glob
    import gzip

    slug = "niassembly_hansard-{0}.json.gz".format(
        day.isoformat() if hasattr(day, "isoformat") else str(day))
    paths = sorted(glob.glob(os.path.join(raw_dir, "*", slug)))
    if not paths:
        return None
    try:
        with gzip.open(paths[-1], "rb") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return parse_sitting(payload, _as_date(day))


def sitting(client, raw_dir, day):
    """The archived sitting if there is one, else fetch and archive it.

    Returns (Sitting_or_None, error_or_None). This is what makes the classifier
    free to re-run: the first pass pays for the network, every later pass reads
    the archive.
    """
    held = load_sitting(raw_dir, day)
    if held is not None:
        return held, None
    return fetch_sitting(client, day)


def _as_date(day):
    try:
        return datetime.date.fromisoformat(str(day)[:10])
    except ValueError:
        return None
