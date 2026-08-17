"""Voting records from Human Rights Council session reports.

The last gap, and it closed from a direction I had already dismissed. HRC
session reports (`A/HRC/{session}/2`) record every recorded vote in a fixed
form, they are reachable by symbol through docs.un.org with `?direct=true`,
and pypdf reads them. Session 58's report is 219 pages and carries 17 votes.

    In favour: Albania, Belgium, Bulgaria, Chile, ...
    Against: Bolivia (Plurinational State of), Burundi, China, Cuba, ...
    Abstaining: Algeria, Bangladesh, Benin, Brazil, ...

This is the UN analogue of a division list: named states, named positions, on
a specific text. Unlike the UPR tracker it is CURRENT -- a session's report is
published within weeks of it closing, not nine months later.

Two things the implementation turns on:

  * each vote is anchored to the NEAREST PRECEDING draft symbol
    (`A/HRC/58/L.30/Rev.1`), because the prose immediately around a vote block
    says only "a recorded vote was taken on the draft resolution". The symbol
    is what lets the vote be joined to the draft whose subject we already
    know from un_docs.
  * tallies are COUNTED from the name lists rather than read from the prose.
    The prose form varies ("by a recorded vote of 24 to 6, with 17
    abstentions" appears in some sections and not others), while the lists are
    always there and are the actual evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

REPORT_SYMBOL = "A/HRC/{session}/2"

_BLOCK = re.compile(
    r"In favour:(?P<favour>.*?)"
    r"Against:(?P<against>.*?)"
    r"Abstaining:(?P<abstaining>.*?)(?=\n\s*\d+\.\s|\Z)", re.S)
# Symbols look like A/HRC/58/L.30/Rev.1 or A/HRC/58/L.6; a trailing full stop
# is sentence punctuation, not part of the symbol.
_SYMBOL = re.compile(r"A/HRC/\d+/L\.\d+(?:/Rev\.\d+)?")


@dataclass
class Vote:
    draft: str                        # 'A/HRC/58/L.30/Rev.1' or None
    favour: list = field(default_factory=list)
    against: list = field(default_factory=list)
    abstaining: list = field(default_factory=list)

    @property
    def tally(self):
        return (len(self.favour), len(self.against), len(self.abstaining))

    def position(self, state):
        """How one state voted, or None if it did not (absent, or not a member)."""
        for name, group in (("for", self.favour), ("against", self.against),
                            ("abstain", self.abstaining)):
            if state in group:
                return name
        return None


# Lowercase words that legitimately appear INSIDE a state name. Anything else
# in lower case means the PDF has glued the following sentence onto the last
# name in the list, which is where a naive split goes wrong: an early version
# truncated "Bolivia (Plurinational State of)" to "Bolivia (Plurinational".
_CONNECTORS = frozenset(
    "of the and de del la republic people's d'ivoire".split())


def _states(blob):
    """Split a UN country list on commas.

    Names carry parentheses -- "Bolivia (Plurinational State of)", "Netherlands
    (Kingdom of the)" -- but never internal commas, so the split itself is
    safe. The work is deciding where the LAST name ends, because the PDF runs
    it into the next sentence with no punctuation. Tokens are kept while they
    are capitalised or a known connector, and the first other lower-case word
    ends the name.
    """
    out = []
    for part in (blob or "").split(","):
        text = re.sub(r"\s+", " ", part).strip(" .;")
        if not text or not re.match(r"^[A-ZÀ-Þ(]", text):
            continue
        # A digit in the FIRST token means the whole entry is page furniture.
        # A digit later means the footer has been glued onto a real name, so
        # the name is kept and the furniture trimmed -- rejecting the whole
        # entry silently lost "Kenya" from a list, which a test caught.
        if re.search(r"\d", text.split(" ")[0]):
            continue
        kept = []
        for token in text.split(" "):
            bare = token.strip("().,").lower()
            if any(c.isdigit() for c in token):
                break                      # page footer starts here
            if token[:1].isupper() or token[:1] in "(" or bare in _CONNECTORS:
                kept.append(token)
                continue
            break
        name = " ".join(kept).strip(" .;")
        if name and len(name) <= 60:
            out.append(name)
    return out


def parse_votes(text, symbol_pattern=_SYMBOL):
    """Every recorded vote in a session report, anchored to its draft."""
    votes = []
    for m in _BLOCK.finditer(text or ""):
        before = text[:m.start()]
        symbols = symbol_pattern.findall(before)
        votes.append(Vote(
            draft=symbols[-1] if symbols else None,
            favour=_states(m.group("favour")),
            against=_states(m.group("against")),
            abstaining=_states(m.group("abstaining"))))
    return votes


def fetch_session_votes(client, session, un_docs):
    """Votes from one HRC session report. un_docs is passed in to avoid a
    circular import and to keep the fetch/parse split testable."""
    symbol = REPORT_SYMBOL.format(session=session)
    text = un_docs.document_text(client, symbol)
    return parse_votes(text), symbol
