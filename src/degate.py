"""One bar for what the German surfaces show: the judge's digest score.

A mirror of src/eugate.py, kept separate rather than shared so the two
jurisdictions can diverge without one silently moving the other. 3 = campaign
trigger, 2 = digest, 1 = background, 0 = noise; a row the judge has not
reached is shown, not hidden.

Germany carries one extra caveat the EU does not. Its areas come from
config/taxonomy-de.yaml, an AI draft Christopher signed off on 29 September
2026 and the German team may still correct, read by a matcher built for
English. The bar is the same; the edition says on its face who signed the
taxonomy off.
"""

FLOOR = 2
SHOWN_SQL = "(triage_score IS NULL OR triage_score >= {0})".format(FLOOR)


def shown(row):
    """For rows already in hand."""
    try:
        score = row["triage_score"]
    except (IndexError, KeyError):
        return True
    return score is None or score >= FLOOR
