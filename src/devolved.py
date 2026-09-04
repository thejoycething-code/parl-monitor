"""One identity for a devolved member, shared by the scorer and the page.

The Welsh record keys its votes by the Senedd's OWN member number
(sd_votes.member_id: 1, 143, 145) while the roster keys members by
publicwhip URI (sd_members.person_id) -- two id spaces that share
nothing. The only bridge between them is the member's NAME.

That bridge has to be built in exactly one place. It was not: the page
resolved names to URIs while tools/devolved_score.py wrote the Senedd's
integers into sd_scored.person_id, so every verdict lookup would have
missed. Nothing looked wrong because no Welsh division is signed off
yet -- the failure was scheduled for the day Christopher signs one and
the tracker quietly shows "not scored" for a division that has a
verdict.

Northern Ireland needs none of this: ni_votes.person_id is already the
roster's id.
"""

from __future__ import annotations

import re
import unicodedata


def norm(name):
    """A name in comparable form: no case, no accents, no punctuation."""
    s = unicodedata.normalize("NFD", (name or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Punctuation is DELETED, not spaced: the Welsh record writes
    # "Andrew R.T. Davies" and the roster "Andrew RT Davies", and
    # spacing the dots apart makes those two different people.
    return re.sub(r"[^a-z ]", "", s)


def _collapse(name):
    return " ".join(norm(name).split())


def roster(conn, sitting_only=False):
    """name -> person_id over the Welsh roster.

    The roster holds every Member the Senedd has ever had -- 227 people,
    one row each, of whom 96 sit today -- so two of them can share a
    name; the first id wins rather than the last.
    `sitting_only` is for the page, which must not invite a reader to
    write to a Member who left in 2016; the scorer wants every term,
    because a division from the last Senedd was cast by people who sit
    in it no longer.
    """
    where = ("WHERE end_date IS NULL OR end_date = ''") if sitting_only else ""
    out = {}
    for r in conn.execute(
            "SELECT person_id, name FROM sd_members {0}".format(where)):
        key = _collapse(r["name"])
        if key and key not in out:
            out[key] = r["person_id"]
    # Every OTHER name parlparse knows these people by. A member who
    # votes under a name the roster does not carry vanishes from the
    # page, and parlparse already answers this with its Alternate names
    # -- they are its own assertion that the names are one person.
    known = set(out.values())
    try:
        for r in conn.execute("SELECT person_id, name FROM member_aliases "
                              "WHERE chamber = 'wales'"):
            key = _collapse(r["name"])
            if key and key not in out and r["person_id"] in known:
                out[key] = r["person_id"]
    except Exception:
        pass                    # a store predating the aliases table
    return out


def resolve(names, index):
    """(resolved {raw: person_id}, unresolved [raw]) for a set of names.

    Never guesses. A name the roster does not carry comes back
    unresolved and is reported by the caller -- the Presiding Officer
    votes as "Y Llywydd / The Llywydd", the chair's casting vote as
    "Casting Vote", and the roster is simply missing some Members
    (measured 2026-09-04: 125 of 130 voter names resolve; the five that
    do not include the First Minister, who has no roster row at all).
    A near-match here would put words in a named politician's mouth.
    """
    got, missing = {}, []
    for raw in names:
        key = _collapse(raw)
        pid = index.get(key)
        if pid is None:
            pid = _by_name_shape(key, index)
        if pid:
            got[raw] = pid
        else:
            missing.append(raw)
    return got, sorted(set(missing))


def _by_name_shape(key, index):
    """One name inside another, same surname, and ONLY one candidate.

    The chamber and the roster disagree about middle names: the Welsh
    record has "Benjamin Hodge Mckenna" where the roster has "Benjamin
    McKenna", and "Eluned Morgan" where it has "Mair Eluned Morgan".
    Both are the same person under a longer or shorter form of one name.

    The rule is deliberately narrow, because the cost of a wrong match
    here is a vote attributed to a politician who did not cast it:
    the SURNAME must be identical, one name's words must all appear in
    the other's, and the roster must offer exactly ONE such person. Two
    candidates means we do not know, and not knowing is reported rather
    than resolved. No edit distance, no nicknames, no initials.
    """
    words = key.split()
    if len(words) < 2:
        return None
    surname, wordset = words[-1], set(words)
    hits = set()
    for cand, pid in index.items():
        cwords = cand.split()
        if len(cwords) < 2 or cwords[-1] != surname:
            continue
        cset = set(cwords)
        if wordset <= cset or cset <= wordset:
            hits.add(pid)
    return hits.pop() if len(hits) == 1 else None
