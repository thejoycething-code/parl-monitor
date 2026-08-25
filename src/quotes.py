"""Shareable quotes: complete sentences, cut cleanly, from the member's own words.

Built 2026-08-25 (Christopher: "suggest ways of doing so where we can pull
shareable quotes. Amend to cut sentences / longer quotes cleanly").

WHY THIS EXISTS. The ledger's `excerpt` is a hard 260-character slice of the
strongest-matching passage, taken at ingest. Of 20,453 stored debate excerpts
the median length is 255 and 11,179 end in an ellipsis -- so the public page
was quoting members mid-word ("...design this thing: not as healthcare, but
as a com"). A truncated quote set in large type under a member's name is a
quotation published on OUR authority, and half a sentence can misrepresent an
argument as easily as a wrong word can.

The full text was on disk all along: the Hansard search payloads under
data/raw carry ContributionTextFull, and 20,883 of 20,909 ledgered debate
refs (100%) are recoverable from them. No API call, no cost.

WHAT A SHAREABLE QUOTE IS, HERE:
  * whole sentences only -- never a mid-sentence or mid-word cut;
  * on-topic -- it must contain a taxonomy term for the area it will be
    displayed under, which is also what stops the cross-area misattribution
    the single stored excerpt caused (a speech tagged [1, 2] rendered the
    SAME words under both headings);
  * long enough to carry an argument (~140 characters floor) and short
    enough to read (~520 cap);
  * free of procedural throat-clearing -- "I beg to move", "Q6. Will the
    Prime Minister join me in thanking...", courtesies to the Chair.

If no passage clears that bar, this returns None and the caller shows a
counted receipt instead of words. Showing nothing is correct: 666 of the
2,093 receipts on the first build carried no real quote, and a grey chip
above a procedural title tells a constituent nothing.
"""

from __future__ import annotations

import gzip
import json
import os
import re

# Abbreviations that end in a full stop and do NOT end a sentence. Hansard is
# dense with them -- "the hon. Member", "the right hon. Gentleman", "No. 10",
# "s. 4 of the 1967 Act" -- and splitting on them shreds every other quote.
_ABBREV = (
    "hon", "rt hon", "mr", "mrs", "ms", "dr", "prof", "st", "no", "nos",
    "e.g", "i.e", "etc", "vs", "cf", "para", "paras", "ch", "cl", "s", "ss",
    "art", "sched", "vol", "col", "cols", "jr", "sr", "bt", "kt", "rev",
    "lt", "col", "gen", "maj", "capt", "sgt", "fig", "pp", "ed", "approx",
)
_ABBREV_RE = re.compile(
    r"(?:^|\s)(?:" + "|".join(re.escape(a) for a in _ABBREV) + r")\.$",
    re.IGNORECASE)

# A sentence ends at . ! ? (optionally closed by a quote/bracket) followed by
# whitespace and something that starts a new sentence.
_BOUNDARY = re.compile(r'(?<=[.!?])(["”’\')\]]*)\s+(?=[“"‘\'(\[]?[A-Z0-9])')

# Procedural throat-clearing. Stripped from the FRONT of a contribution only:
# these are ways of starting to speak, not things a member is saying.
_OPENERS = [
    re.compile(r"^Q\d+\.\s*", re.I),                      # PMQs question number
    re.compile(r"^My Lords[,.]?\s*", re.I),
    re.compile(r"^(?:Mr|Madam|Mister)\s+(?:Deputy\s+)?Speaker[,.]?\s*", re.I),
    re.compile(r"^I beg to move[^.?!]*[.?!]\s*", re.I),
    re.compile(r"^It is a (?:great )?pleasure to (?:serve|speak|follow)[^.?!]*[.?!]\s*", re.I),
    re.compile(r"^I (?:congratulate|thank|pay tribute to)[^.?!]*[.?!]\s*", re.I),
    re.compile(r"^I am grateful to[^.?!]*[.?!]\s*", re.I),
    re.compile(r"^With permission[^.?!]*[.?!]\s*", re.I),
    re.compile(r"^Before I (?:begin|start)[^.?!]*[.?!]\s*", re.I),
]

# Whole contributions that are procedure, not argument. If what survives is
# only this, there is no quote to publish.
_PROCEDURAL = re.compile(
    r"^(?:i beg to move|question put|division|the house divided|"
    r"will the (?:hon|right hon)[^.?!]*give way|i give way|"
    r"order|that this house|amendment (?:proposed|agreed|withdrawn|negatived)|"
    r"clause \d+ (?:ordered|accordingly)|on a point of order)",
    re.IGNORECASE)

# Sentences opening with one of these depend on what came before, so the
# window grows backwards to pick up the antecedent.
_DEPENDENT = re.compile(
    r"^(?:that|this|these|those|it|he|she|they|but|and|so|however|"
    r"therefore|thus|yet|nor|moreover|furthermore|again|there)\b", re.I)

# A sentence may close with SEVERAL quote or bracket characters -- Hansard
# nests quotations inside quotations, so ...consent.'" is a complete sentence.
SENTENCE_END = re.compile(r"""[.!?]['"\u2019\u201d)\]]*$""")

# Hansard writes an em-dash where a member was interrupted or gave way. It is
# a true feature of the record and a bad end to a pulled quote: it reads as if
# WE cut them off.
_INTERRUPTED = re.compile(r"[\u2014\u2013-]$")

FLOOR = 140      # below this a quote carries no argument
TARGET = 380     # what we aim for
CAP = 520        # above this nobody reads it


# Hansard embeds column markers in the contribution text itself, e.g.
# <span id="730" class="column-number" data-column-number="730"></span>.
# They are invisible on their site and pure noise in a pulled quote.
_TAG = re.compile(r"<[^>]+>")


def clean(text):
    """Drop Hansard's inline markup and normalise whitespace."""
    return " ".join(_TAG.sub(" ", text or "").split())


def sentences(text):
    """Split into sentences without breaking on 'hon.', 'No. 10' or 's. 4'.

    Cut points are found first and then FILTERED, rather than split on and
    rejoined: the rejoining version silently lost its abbreviation guard
    whenever the boundary carried a closing quotation mark, which is how
    "the hon. Member for Spen Valley" became the start of a sentence.
    """
    text = clean(text)
    if not text:
        return []
    cuts = []
    for m in _BOUNDARY.finditer(text):
        head = text[:m.start()] + (m.group(1) or "")
        if _ABBREV_RE.search(head.rstrip()):
            continue                      # "hon." is not the end of a sentence
        cuts.append(m.end())
    out, prev = [], 0
    for cut in cuts:
        piece = text[prev:cut].strip()
        if piece:
            out.append(piece)
        prev = cut
    tail = text[prev:].strip()
    if tail:
        out.append(tail)
    return out


def strip_openers(text):
    """Remove ways of starting to speak from the front."""
    prev = None
    while prev != text:
        prev = text
        for rx in _OPENERS:
            text = rx.sub("", text, count=1)
    return text.strip()


def _matches(sentence, patterns):
    return sum(1 for p in patterns if p.search(sentence))


def shareable(text, patterns, floor=FLOOR, target=TARGET, cap=CAP):
    """Best whole-sentence passage of `text` that is on-topic for `patterns`.

    Returns the quote, or None when nothing clears the bar. `patterns` are
    compiled taxonomy regexes for the ONE area this quote will be shown
    under -- passing the area's patterns is what keeps a quote about
    assisted dying from being published beneath a heading that says
    Abortion.
    """
    body = strip_openers(text or "")
    if not body:
        return None
    sents = sentences(body)
    if not sents:
        return None

    scored = [(i, _matches(s, patterns)) for i, s in enumerate(sents)]
    # A "sentence" longer than the cap is nearly always a block quotation or
    # a semicolon list that Hansard never terminated -- one ran to 5,593
    # characters. It cannot be trimmed without cutting mid-sentence, which is
    # the whole thing this module exists to avoid, so it is not a candidate.
    hits = [i for i, n in scored if n and len(sents[i]) <= cap]
    if not hits:
        return None

    # Seed on the sentence with the most term matches; earliest wins ties,
    # because a member's first statement of a position is usually the
    # cleanest one.
    seed = max(hits, key=lambda i: (scored[i][1], -i))

    start = end = seed
    # grow backwards once if the seed leans on an antecedent
    if _DEPENDENT.match(sents[seed]) and seed > 0:
        cand = " ".join(sents[seed - 1:end + 1])
        if len(cand) <= cap:
            start = seed - 1

    def span():
        return " ".join(sents[start:end + 1])

    # grow forwards to the target, then stop; never cross the cap
    while len(span()) < target and end + 1 < len(sents):
        nxt = " ".join(sents[start:end + 2])
        if len(nxt) > cap:
            break
        end += 1
    # still thin? try backwards
    while len(span()) < floor and start > 0:
        nxt = " ".join(sents[start - 1:end + 1])
        if len(nxt) > cap:
            break
        start -= 1

    # The window can grow away from the very term that justified it, leaving
    # a passage displayed under a heading nothing in it mentions. If that has
    # happened, shrink back towards the seed until the term is visible again.
    while not _matches(span(), patterns) and (start < seed or end > seed):
        if end > seed:
            end -= 1
        else:
            start += 1

    # Drop a trailing interrupted sentence rather than publish a quote that
    # ends mid-word on an em-dash.
    while end > start and _INTERRUPTED.search(sents[end].rstrip()):
        end -= 1

    quote = span().strip()
    if _INTERRUPTED.search(quote) or not SENTENCE_END.search(quote):
        return None
    if len(quote) < floor or _PROCEDURAL.match(quote):
        return None
    if not _matches(quote, patterns):
        return None
    return quote


# A member asking the Minister to clarify a statutory instrument is on-topic
# and unquotable. A member saying what they believe is the thing worth
# putting on a public page, so candidates are ranked before they are cut.
_STANCE = re.compile(
    r"\b(?:I believe|I think|I am concerned|I do not believe|in my view|"
    r"we should|we must|we cannot|it is wrong|it is right|the truth is|"
    r"I fear|I am clear|let us be clear|the reality is|I will not|"
    r"I cannot support|I support|I oppose|my view is)\b", re.I)
_PROCEDURAL_ASK = re.compile(
    r"\b(?:will the (?:Minister|Secretary of State|hon|right hon)[^.?!]*"
    r"(?:confirm|clarify|tell|give way|agree)|"
    r"could (?:the Minister|he|she) (?:confirm|clarify|explain)|"
    r"I would be grateful if|to ask the Secretary of State|"
    r"what (?:assessment|estimate|steps) (?:has|have|he|she))\b", re.I)


def quotability(quote):
    """How well a passage stands alone on a public page. Higher is better.

    This ranks candidates; it never invents or edits them. It is a display
    judgement about readability, not a judgement about the member -- nothing
    here looks at which side of an argument the words are on, and it must
    stay that way, because ranking by direction would turn a receipt into an
    inference.
    """
    if not quote:
        return -99.0
    score = 0.0
    if _STANCE.search(quote):
        score += 3.0                       # they are stating a position
    if _PROCEDURAL_ASK.search(quote):
        score -= 2.5                       # asking the Minister to clarify
    questions = quote.count("?")
    if questions:
        score -= 1.2 * questions           # a question is rarely quotable
    if quote.rstrip().endswith("?"):
        score -= 1.0
    # quoting someone else at length is their words, not the member's
    if quote.count("“") + quote.count('"') >= 2:
        score -= 1.5
    # readable length: full enough to carry an argument, short enough to read
    length = len(quote)
    if TARGET - 120 <= length <= CAP:
        score += 1.0
    elif length < FLOOR + 60:
        score -= 0.8
    return score


class RawHansard:
    """Index of contribution id -> full text, built from data/raw.

    The weekly payloads are gzipped search responses; the same contribution
    can appear in several of them (one per matched term), so the longest
    text wins. Roughly 1,400 files and 42,000 contributions, which is a few
    seconds -- cheap enough to do at build time rather than caching, and a
    cache would only go stale against the next sweep.
    """

    def __init__(self, root):
        self.text = {}
        self.meta = {}
        pattern = os.path.join(root, "data", "raw", "*", "hansard_search-*.json.gz")
        import glob
        for path in glob.glob(pattern):
            try:
                with gzip.open(path, "rt", encoding="utf-8") as fh:
                    payload = json.load(fh)
            except (OSError, ValueError):
                continue          # a half-written sweep must not fail a build
            for row in (payload.get("Results") or []):
                ext = row.get("ContributionExtId")
                if not ext:
                    continue
                full = row.get("ContributionTextFull") or row.get("ContributionText") or ""
                if ext not in self.text or len(full) > len(self.text[ext]):
                    self.text[ext] = full
                    self.meta[ext] = {
                        "house": row.get("House") or "Commons",
                        "date": (row.get("SittingDate") or "")[:10],
                        "debate": row.get("DebateSection") or "",
                        "debate_id": row.get("DebateSectionExtId") or "",
                    }

    def __len__(self):
        return len(self.text)

    def get(self, ref):
        """ref is the ledger's 'hansard:GUID'."""
        ext = ref.split(":", 1)[1] if ":" in ref else ref
        return self.text.get(ext), self.meta.get(ext)

    def url(self, ref):
        """Public Hansard page anchored to the exact contribution.

        Same construction as src/ingest/hansard.py, which has been building
        the weekly monitor's links for weeks -- a day-level link makes a
        reader hunt for the words, which is fatal for something meant to be
        shared.
        """
        ext = ref.split(":", 1)[1] if ":" in ref else ref
        m = self.meta.get(ext)
        if not m or not m.get("debate_id") or not m.get("date"):
            return None
        return "https://hansard.parliament.uk/{0}/{1}/debates/{2}/#contribution-{3}".format(
            m["house"], m["date"], m["debate_id"], ext)

def trim_to_sentence(text, floor=FLOOR):
    """Cut stored text back to its last COMPLETE sentence.

    Written questions have no full-text source on disk the way speeches do,
    so their text is the ledger's own 260-character slice -- which ends in an
    ellipsis about half the time. Publishing that under a member's name has
    the same defect as a truncated speech, so it is cut back rather than
    shown mid-sentence. Returns None when nothing whole survives: no quote is
    better than half of one.
    """
    body = clean(text)
    if not body:
        return None
    body = re.sub(r"(?:\.\.\.|\u2026)\s*$", "", body).strip()
    sents = sentences(body)
    if not sents:
        return None
    # drop a trailing fragment: a real sentence ends in punctuation
    while sents and not SENTENCE_END.search(sents[-1]):
        sents.pop()
    out = " ".join(sents).strip()
    return out if len(out) >= floor else None
