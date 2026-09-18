"""One bar for what the EU surfaces show: the judge's digest score.

Body matching (17 Sept 2026) and text-to-division inheritance (18 Sept) widened
recall on purpose: admit generously, let the judge sort. The judge's score is
therefore the only thing that makes a list readable. 3 = campaign trigger,
2 = digest, 1 = background, 0 = noise; a row the judge has not reached is
shown, not hidden. The edition, the MEP tracker and the meaning-line queue
all read this so they cannot drift apart.
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
