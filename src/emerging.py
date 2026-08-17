"""Catch language we did not think to list.

The taxonomies match vocabulary somebody wrote down. That is a real blind
spot: a new framing arrives in words nobody predicted, and sometimes inside a
word we already exclude. "Self-determination" at the UN means decolonisation,
so a claim that gender should rest on self-determination hides behind a term
the monitor must otherwise ignore. Guarded terms handle the cases we can
imagine; this module is for the ones we cannot.

Two mechanisms, deliberately separate:

NOVEL PHRASES. The store now holds thousands of UPR recommendations and
hundreds of drafts. That is a baseline of how the UN normally talks about our
issues, and it was accumulated as a side effect rather than designed -- which
makes it the cheapest asset here. A phrase that appears in a document which
ALREADY matches one of our areas, and which the rest of the corpus has barely
seen, is emerging language by definition. No list to maintain.

RIGHTS-CLAIM ESCALATION. The event in "the UN wants to treat self-ID as a
human right" is not a new noun, it is a change of status: "States should
consider" becoming "the right to". That is structural, so it is matched as a
pattern and works whatever noun follows.

Both produce a REVIEW QUEUE, not alerts. Most novel phrasing is drafting
variation, and a monitor that cries wolf gets ignored -- so callers are
expected to print the counts they discarded, as the parliamentary side does.
"""

from __future__ import annotations

import re
from collections import Counter

# Words that carry no signal on their own. Kept small on purpose: an
# aggressive stop list would remove the very connectives that make a framing
# recognisable ("the right to", "on the basis of").
_NOISE = frozenset("""
the a an of to and in for on with its it their that this by as be are is at
from all such which who or not no its his her they them we our
including accordance held whether within
january february march april may june july august september october november
december
""".split())

# UN drafting boilerplate. These phrases are everywhere and mean nothing about
# subject matter, so they would otherwise dominate any novelty measure.
_BOILERPLATE = (
    "recalling", "reaffirming", "recognizing", "welcoming", "noting",
    "emphasizing", "stressing", "bearing in mind", "taking note",
    "requests the secretary-general", "decides to remain seized",
)

# Amendment and drafting MECHANICS. A phrase made only of these says how a
# text is being changed, not what about. Dropping any gram whose every word is
# procedural keeps "delete sexual and reproductive" -- which is the finding --
# while losing "in operative paragraph delete", which is furniture.
_PROCEDURAL = frozenset("""
preambular operative paragraph paragraphs subparagraph amendment amendments
amend revised revise draft resolution decision replace replacing insert
inserting delete deleting after before following reading new item items agenda
session committee annex add text word words line lines chapter part
first second third fourth fifth sixth seventh eighth ninth tenth eleventh
twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth
nineteenth twentieth
""".split())


def _is_furniture(gram):
    return all(w in _NOISE or w in _PROCEDURAL for w in gram.split())


_RIGHTS_CLAIM = re.compile(
    r"\b(?:the\s+)?right\s+to\b"
    r"|\brights?\s+of\s+(?:every|all|each)\b"
    r"|\brecogniz\w+\s+the\s+right\b|\brecognis\w+\s+the\s+right\b"
    r"|\bhuman\s+right\s+to\b"
    r"|\bentitled\s+to\b", re.I)


def phrases(text, sizes=(2, 3, 4)):
    """Word n-grams, lowercased, boilerplate and all-noise runs dropped."""
    words = re.findall(r"[a-z][a-z'-]+", (text or "").lower())
    out = []
    for n in sizes:
        for i in range(len(words) - n + 1):
            gram = words[i:i + n]
            if all(w in _NOISE for w in gram):
                continue
            if gram[0] in _NOISE and gram[-1] in _NOISE:
                continue
            joined = " ".join(gram)
            if any(b in joined for b in _BOILERPLATE):
                continue
            if _is_furniture(joined):
                continue
            out.append(joined)
    return out


def build_baseline(texts, sizes=(2, 3, 4)):
    """{phrase: number of DOCUMENTS it appears in}.

    Document frequency, not raw count: a phrase repeated forty times in one
    resolution is still one document's worth of evidence that it is normal.
    """
    df = Counter()
    for text in texts:
        for gram in set(phrases(text, sizes)):
            df[gram] += 1
    return df


def novel_phrases(text, baseline, max_df=1, sizes=(2, 3, 4)):
    """Phrases in `text` that the corpus has barely seen.

    max_df=1 means "appears in at most one other document". Raising it makes
    the queue quieter and blinder; the right value depends on corpus size and
    should be tuned against real output rather than guessed.
    """
    seen = set()
    out = []
    for gram in phrases(text, sizes):
        if gram in seen:
            continue
        seen.add(gram)
        if baseline.get(gram, 0) <= max_df:
            out.append(gram)
    return out


def _content_words(gram):
    return [w for w in gram.split() if w not in _NOISE and w not in _PROCEDURAL]


def longest_novel(text, baseline, max_df=1, limit=6):
    """The novel phrases worth showing a human.

    Ranked by SUBJECT CONTENT, not length: "delete sexual and reproductive"
    and "operative paragraph delete sexual" are the same window over the same
    text, but only the first reads as a finding. Ranking by content words puts
    it first, and deduplicating on word overlap stops the same discovery being
    reported eight times in slightly different framings -- which is what the
    first version did, burying "eradication of child labour" in variants.
    """
    found = sorted(novel_phrases(text, baseline, max_df),
                   key=lambda g: (len(_content_words(g)), len(g)), reverse=True)
    kept, claimed = [], []
    for gram in found:
        words = set(_content_words(gram))
        if not words:
            continue
        # ANY shared content word collapses the pair. Within one short
        # document that is right: four windows over "delete sexual and
        # reproductive health" are one finding, and a reader who wants the
        # detail opens the link. Across documents this function is never
        # called, so there is no risk of merging separate discoveries.
        if any(words & seen for seen in claimed):
            continue
        kept.append(gram)
        claimed.append(words)
        if len(kept) >= limit:
            break
    return kept


def rights_claims(text, area_terms):
    """Sentences that make a rights claim AND mention one of our terms.

    Both conditions in the SAME sentence: a resolution can assert a right in
    one paragraph and mention gender in another without the two being related,
    and treating that as escalation would flag almost every UN text.
    """
    hits = []
    for sentence in re.split(r"(?<=[.;])\s+", text or ""):
        if not _RIGHTS_CLAIM.search(sentence):
            continue
        low = sentence.lower()
        matched = [t for t in area_terms if t and t.lower() in low]
        if matched:
            hits.append((re.sub(r"\s+", " ", sentence).strip()[:240], matched[:3]))
    return hits
