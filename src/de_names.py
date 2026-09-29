"""German member names: one folding rule for every place a name has to match.

abgeordnetenwatch keys a MANDATE, not a person, and fills politician_id only
for the current Bundestag; the Bundestag's own register (de_mdb) is a third id
space; a Drucksache prints names. So a member's 2019 vote, 2024 bill and 2026
speech meet only by name, and the name has to be folded the same way
everywhere or the same person fails to meet themselves.

Measured 29 September 2026 against the 630 sitting members, the forms that
differ between sources are all spelling, never identity:
    Jürgen Kögel / Jürgen Koegel          umlaut spelled out
    Rainer Gross / Rainer Groß            ß
    Cansın Köktürk / Cansin Köktürk       dotless ı
    Christian von Stetten / Christian Frhr. von Stetten
    Philip Hoffmann / Philip M. A. Hoffmann    middle initials
    Michael „Moses" Arndt / Michael Arndt      a nickname in quotes
    Dr.-Ing. Zoe Mayer / Zoe Mayer        a title the first version missed
    Reem Alabali Radovan / Reem Alabali-Radovan

key() is (first given name, last surname token). Two sitting members sharing a
key would be indistinguishable, so callers check clashes() and refuse to
attach evidence to either -- none exist in the 21st Bundestag.
"""

from __future__ import annotations

import re
import unicodedata

_SPELLED = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("ı", "i"))
_TITLES = re.compile(r"\b(dr|prof|ing|frhr|freiherr|freifrau)\.?\s")
_QUOTED = re.compile(r"„.*?“|\".*?\"|\(.*?\)")


def fold(text):
    """Lower-case ASCII with umlauts spelled out, titles, nicknames and
    bracketed suffixes ('(Fulda)', '(Bundestag 2025 - 2029)') removed."""
    s = (text or "").lower()
    for a, b in _SPELLED:
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = _QUOTED.sub(" ", s)
    s = re.sub(r"[-.,]", " ", s)
    s = _TITLES.sub(" ", s + " ")
    return re.sub(r"\s+", " ", s).strip()


def key(name):
    """(first given name, last surname token), or None for a single word."""
    t = fold(name).split()
    return (t[0], t[-1]) if len(t) >= 2 else None


def clashes(names):
    """Keys shared by two or more of the given names."""
    seen, out = {}, set()
    for n in names:
        k = key(n)
        if k in seen and seen[k] != n:
            out.add(k)
        seen.setdefault(k, n)
    return out


def found_in(name, text_folded):
    """Whether a name appears in already-folded text: first name, at most one
    middle token, surname. One token, not two: a two-column signer block reads
    "Peter Aumer Markus Kurth", and two would let a Peter Kurth match it."""
    k = key(name)
    if not k:
        return False
    return re.search(r"\b{0} (\w+ )?{1}\b".format(re.escape(k[0]), re.escape(k[1])),
                     text_folded) is not None


PARTY_FAMILY = (("afd", "afd"), ("esn", "afd"), ("csu", "union"), ("cdu", "union"),
                ("evp", "union"), ("spd", "spd"), ("s&d", "spd"), ("grün", "gruene"),
                ("efa", "gruene"), ("linke", "linke"), ("gue", "linke"), ("fdp", "fdp"),
                ("renew", "fdp"), ("freie wähler", "fw"), ("bsw", "bsw"))


def party_family(label):
    """'union', 'spd', 'gruene', 'linke', 'afd', 'fdp', 'fw', 'bsw' or None.

    A Land Fraktion and a Bundestag one are spelled differently (CSU in
    Bavaria, CDU/CSU in Berlin, EVP in Strasbourg); matching a name across
    parliaments also requires the same family, so a Bavarian namesake from
    another party cannot attach to a sitting member.
    """
    low = (label or "").lower()
    for needle, family in PARTY_FAMILY:
        if needle in low:
            return family
    return None
