"""What a Minister actually said, and the shape of the saying.

A stored answer is the one thing in the NI monitor that carries a GOVERNMENT
position rather than a member's activity. 203 of 217 stored questions hold one,
already fetched, so reading them costs nothing.

WHY THIS IS NOT ABOUT AREAS. Classifying the answer text finds almost nothing
the question did not already say -- measured 2026-08-19, 7 of 203 answers add
an area the question lacked, one per area, which is noise. The value is in the
SHAPE of the answer, and the shapes that matter are the ones where a Minister
declines: 28 of 203 (14%) say the data is not held, no guidance was issued, the
matter is not Northern Ireland's, or no position has settled. Measured against
the store, one answer never matches two shapes, so 28 patterns means 28
answers. Those are the quotable ones:

  "the HSC Business Services Organisation does not hold information on the
   indication for which drugs have been prescribed"          (puberty blockers)

  "a body which does not have functions in Northern Ireland about legislation
   which does not extend to Northern Ireland"    (EHRC guidance, area 5)

  "the draft ... do not represent the Department's settled position"

So this is structural matching, like emerging.rights_claims: a pattern over how
government answers, not a list of subjects. The remaining 175 answers are
substantive and carry no shape, which is the correct result for them.

ANSWER AREAS ARE STORED SEPARATELY from the question's, and must stay that way.
`ni_items.areas` is the MLA's evidence and feeds the 5CA; a Minister's words are
not the asker's position, and merging the two would credit a member with ground
they never took. A test asserts tools/ni_5ca.py never reads answer_areas.
"""

from __future__ import annotations

import re

# Ordered most-specific first: an answer that both declines a remit AND says no
# data is held reads better as the remit refusal, which is the harder wall.
SHAPES = (
    ("not our remit",
     r"does not extend to Northern Ireland"
     r"|do(?:es)? not have functions in Northern Ireland"
     r"|is (?:a )?(?:reserved|excepted) matter"
     r"|not (?:a )?(?:devolved|transferred) matter"
     # "This is not a policy or legislative responsibility of my Department."
     # Dropped by accident when these patterns were rewritten from the probe,
     # which cost 8 of 28 answers. Restored with its own measurement.
     r"|responsibility (?:of|rests with|lies with)"),
    ("data not held",
     r"does not (?:hold|collect|record)"
     r"|is not (?:held|collected|recorded)"
     r"|not (?:centrally )?(?:held|available)"
     r"|no (?:such )?(?:information|data) (?:is )?(?:held|available)"),
    ("no policy issued",
     r"has not (?:issued|published|developed|introduced|commissioned)"
     r"|no (?:such )?guidance (?:has been )?issued"
     r"|there (?:is|are) no (?:current )?plans"),
    ("no settled position",
     r"settled position"
     r"|under (?:active )?consideration"
     r"|developing (?:analysis|policy)"
     # "...will be brought forward in due course" -- the classic
     # non-commitment. Also dropped by accident in the rewrite: 6 answers.
     r"|in due course"
     r"|no decision has (?:yet )?been (?:taken|made)"),
    ("passed to another body",
     r"transferred (?:from|to)"
     r"|should be (?:directed|addressed) to"
     r"|(?:is a )?matter for (?:the )?(?:council|Trust|Department)"),
)

_COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in SHAPES]

# The sentence carrying the shape, for quoting. A whole answer averages 980
# characters and is far too long to show; the sentence that declines is the
# part a campaigner would actually cite.
_SENTENCE = re.compile(r"(?<=[.;])\s+")


def shape(answer):
    """The name of the first matching shape, or '' for a substantive answer.

    '' is a real result, not a failure: 175 of 203 answers decline nothing and
    should read as substantive rather than as unclassified.
    """
    text = answer or ""
    for name, pattern in _COMPILED:
        if pattern.search(text):
            return name
    return ""


def quote(answer, name=None, limit=200):
    """The sentence that carries the shape, trimmed for display.

    Falls back to the opening sentence when no shape matched, so a caller
    showing a substantive answer still gets its most load-bearing line rather
    than an arbitrary 200-character slice.
    """
    text = " ".join((answer or "").split())
    if not text:
        return ""
    name = name if name is not None else shape(text)
    sentences = [s for s in _SENTENCE.split(text) if s.strip()]
    chosen = sentences[0] if sentences else text
    if name:
        pattern = dict(_COMPILED)[name]
        for sentence in sentences:
            if pattern.search(sentence):
                chosen = sentence
                break
    chosen = chosen.strip()
    if len(chosen) > limit:
        chosen = chosen[:limit].rsplit(" ", 1)[0] + "..."
    return chosen


def classify(taxonomy, watchlist, answer, filter_item):
    """(areas, terms, shape) for one answer.

    `filter_item` is injected rather than imported so this module stays free of
    the filter's config loading and can be tested on its own.
    """
    text = answer or ""
    if not text:
        return [], [], ""
    result = filter_item(taxonomy, watchlist, text)
    return result.issue_areas, result.matched_terms, shape(text)
