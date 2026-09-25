"""Parsing the Bundestag's Stenografischer Bericht.

Lifted out of tools/de_speeches.py on 25 September 2026, unchanged, when the
debate packs needed the same parser. src never imports from tools, and the
alternative was a second copy of a regex that took three measured attempts
to get right -- 98% of protocol 21/94's characters accounted for is the
number that says it is not quietly missing half the day.

The collector stores only speeches on our ground; a debate pack needs EVERY
speaker in one debate, including the ones no term matched, so it parses the
protocol itself rather than reading the filtered table.
"""

from __future__ import annotations

import re

NOT_A_PERSON = ("tagesordnungspunkt", "zusatzpunkt", "anlage", "inhalt",
                "einzelplan", "punkt", "drucksache", "anhang")

# The Bericht hyphenates across lines ("Nordrhein-\nWestfalen"), so anywhere a
# heading can run long it must tolerate a line break AFTER A HYPHEN and
# nowhere else. A plain [^\n:] stopped at the break and lost the heading; a
# permissive [^:] would have run on into the speech.
_BRK = r"(?:[^\n:]|-\n)"
SPEAKER = re.compile(
    r"^(?P<who>"
    r"(?:Präsident(?:in)?|Vizepräsident(?:in)?)\s+[^\n:()]{3,60}"
    # A member, optionally with the CONSTITUENCY the Bericht prints to tell
    # two members of the same name apart: "Michael Brand (Fulda) (CDU/CSU):".
    # Without the optional group the whole heading failed to match and the
    # speech was dropped -- four of them in protocol 21/96, all of them the
    # lead signatory of the motion being debated (measured 2026-09-25).
    r"|[A-ZÄÖÜ][^\n:()]{2,60}?(?:\s*\([^)\n]{2,30}\))?\s*\((?P<party>[^)\n]{2,40})\)"
    # A federal minister, and a LAND minister speaking for the Bundesrat:
    # "Karl-Josef Laumann, Minister (Nordrhein-\nWestfalen):".
    r"|[A-ZÄÖÜ][^\n:()]{2,60}?,\s*(?:Bundes)?[Mm]inister(?:in)?" + _BRK + r"{0,60}"
    r"|[A-ZÄÖÜ][^\n:()]{2,60}?,\s*(?:Staatsminister(?:in)?|Senator(?:in)?)" + _BRK + r"{0,60}"
    r"|[A-ZÄÖÜ][^\n:()]{2,60}?,\s*Parl\.?\s*Staatssekretär(?:in)?" + _BRK + r"{0,60}"
    r"):\s*\n", re.M)


def role_of(who, party):
    low = who.lower()
    if low.startswith(("präsident", "vizepräsident")):
        return "chair"
    if party:
        return "member"
    return "minister"


# Question time prints "Frage der Abgeordneten Clara Bünger (Die Linke):" --
# the heading is a LABEL meaning "question from MP X", not a name. Stored
# whole it produced a speaker called "Frage der Abgeordneten Clara Bünger",
# who attributes to nobody. Removing the label is not renaming anyone: the
# member's own name is what is left.
QUESTION_LABEL = re.compile(
    r"^Frage\s+(?:der|des)\s+Abgeordneten\s+", re.I)


def clean_name(who, role):
    """The name as the protocol prints it, minus the office.

    Never reconstructed or tidied beyond stripping a title or a procedural
    label: these are real parliamentarians and the house rule is that we do
    not invent their names or their words.
    """
    name = QUESTION_LABEL.sub("", who.strip())
    if role == "chair":
        name = re.sub(r"^(?:Vize)?[Pp]räsident(?:in)?\s+", "", name)
    elif role == "minister":
        name = name.split(",", 1)[0]
    else:
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    return name.strip()


def parse_speeches(text):
    """[(speaker, party, role, body)] in the order they were given.

    Procedural headings are dropped here and the caller is told how many, so
    the count in de_protocols reflects real speech headings.
    """
    out, skipped = [], 0
    hits = list(SPEAKER.finditer(text))
    for i, m in enumerate(hits):
        who = m.group("who").strip()
        if who.lower().startswith(NOT_A_PERSON):
            skipped += 1
            continue
        party = (m.group("party") or "").strip() or None
        role = role_of(who, party)
        if role == "member" and party and party.lower() in NOT_A_PERSON:
            skipped += 1
            continue
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        out.append((clean_name(who, role), party, role,
                    text[m.end():end].strip()))
    return out, skipped


# The Stenografischer Bericht prints academic titles; abgeordnetenwatch does
# not. "Dr. Dietmar Bartsch" against "Dietmar Bartsch" was 32 of 125 speeches
# unattributed on the first run, and every one of them a member we hold.
TITLES = re.compile(
    r"^(?:Dr\.|Prof\.|Dr\.\s*h\.\s*c\.|Dipl\.-[A-Za-zä-ü]+\.?|"
    r"Freiherr|Freifrau|Graf|Gräfin)\s+", re.I)


def match_key(name):
    """The form a name is COMPARED on. Never the form it is stored in.

    The speaker column keeps the protocol's own wording, because these are
    real parliamentarians and the standing rule is that we do not reword
    them. This is only a join key.
    """
    out = (name or "").strip()
    while True:
        stripped = TITLES.sub("", out)
        if stripped == out:
            break
        out = stripped
    return out.strip().lower()
