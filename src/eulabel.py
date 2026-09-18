"""English out of the European Parliament's multilingual label fields.

The night a sitting ends, EP Open Data often carries a voted item's label in
French and in "mul" (French - English - German joined by " - ") but not yet
under "en". The first live EU day sweep (18 Sept 2026) required "en", skipped
all ten of 17 Sept's voted items, and told the DM "0 divisions". Every EU
collector that reads a label or a title goes through here now.
"""

import re

EN_WORDS = frozenset("the and of on to for in a with its".split())


def english_label(labels, any_language=False):
    """Return (label, provisional).

    "en" when present (provisional False). Otherwise the segment of "mul"
    that reads most like English, scored on common English words. With
    any_language, a French/German/Spanish/Italian label is the last resort;
    without it, no English means "" and the caller skips as before -- a
    weekly collector has no heal pass and must not store a French title
    for ever. Provisional is True whenever "en" was absent.
    """
    labels = labels or {}
    if not isinstance(labels, dict):
        text = str(labels).strip()
        return text, False
    en = (labels.get("en") or "").strip()
    if en:
        return en, False
    best, score = "", 0
    for seg in (labels.get("mul") or "").split(" - "):
        words = {w.strip(",.:;'’()\"").lower() for w in seg.split()}
        hits = len(words & EN_WORDS)
        if hits > score:
            best, score = seg.strip(), hits
    if best:
        return best, True
    if any_language:
        for lang in ("fr", "de", "es", "it"):
            if (labels.get(lang) or "").strip():
                return labels[lang].strip(), True
    return "", True


def english(labels):
    """The label alone, for collectors that only want a string."""
    return english_label(labels)[0]


_PROC = re.compile(r"\(\d{4}/\d{4}\([A-Za-z]+\)\)")
_READING = re.compile(r"\*+\s*I*(?=\s|$)")     # "***I", "**" reading markers
_JUNK = re.compile(r"[^a-z0-9 ]+")


def normalise_title(title):
    """A key that matches a vote item's subject to its adopted text: case,
    punctuation, procedure references and the ***I reading markers
    stripped."""
    t = _PROC.sub(" ", title or "")
    t = _READING.sub(" ", t)
    t = _JUNK.sub(" ", t.lower())
    return " ".join(t.split())
