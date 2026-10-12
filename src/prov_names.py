"""Provincial member names: one dated resolver for every legislature.

No province publishes member ids on its divisions (docs/canada-provinces-
scope.md, "Names, not ids"). Every recorded vote arrives as a printed label
and has to be joined to a member through the roster TERMS VALID ON THE DAY
of the division -- so a 2025 by-election winner who shares a surname with a
2024 member (Alberta's two Brars) cannot absorb the earlier member's votes.

The forms that occur, all handled by `parse_label` and `Resolver.resolve`:

    surname only                         Notley, Calahoo Stonehouse, de Jonge
    surname plus riding                  Sigurdson (Highwood), Wright (Cypress-Medicine Hat)
    riding wrapped onto the next line    Sigurdson / (Edmonton-Riverview)     -- split_name_run
    initial plus surname                 L. Neufeld, Sigurdson, R.J., Mr. J. LeBlanc
    honorifics                           Hon. Mr. Higgs, Mme, M., Member, KC, ECA
    full name                            Scott Moe, Betty Nippi -Albright
    French accents                       Rattée, Lagimodière -- folded to ASCII on both sides
    a footnote mark                      Amery*, Hanson * -- Alberta's "* Member voted remotely"
    an earlier surname (reviewed)        Glasgo (Michaela Frey) -- Resolver.with_record
    an abbreviated riding (reviewed)     Nixon (Rimbey-Rocky Mtn. House-Sundre)

AN UNRESOLVED LABEL RESOLVES TO None, NEVER TO A GUESS. Unique-or-nothing:
if two members valid on the day fit a label, the answer is None with the
reason ("ambiguous: ...") -- the caller stores the label with a NULL member
and the tally check turns the division into a gap.

PARTY-ONLY TERMS. A term whose `source` starts with "party" (New Brunswick's
Hansard member list, Newfoundland's election results) dates a PARTY and
nothing else: it never makes anyone a member on a day. `resolve`,
`valid_terms` and `term_for` ignore it; only `party_at` reads it.

REVIEWED LABEL ALIASES (config/prov_record.yaml, `label_aliases:`). A
printed label that is a typo in the source ("Mr. Russel", "Lloyd Parrot")
is cleared by `Aliased` only AFTER the normal resolver has found nobody,
only on the day and in the document the entry was checked against, and
only when its member holds a term that day. It is a list of single
reviewed facts, never a fuzzy matcher: an entry names the document, the
date, the printed form, the member and the evidence.
"""

from __future__ import annotations

import os
import re
import unicodedata

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(ROOT, "config", "prov_record.yaml")

HONORIFICS = {
    "hon", "honourable", "honorable", "the", "mr", "mrs", "ms", "miss", "mx",
    "dr", "m", "mme", "mlle", "l'hon", "lhon", "member", "mla", "kc", "qc",
    "eca", "premier", "minister", "min", "hon'ble",
}
_DASHES = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-",
                         "—": "-", "−": "-", "­": None,
                         "’": "'", "‘": "'", " ": " "})
_PAREN = re.compile(r"\(([^()]*)\)\s*$")
_INITIALS = re.compile(r"^(?:[A-Za-z]\.){1,3}$|^[A-Z]$")


def fold(text):
    """Lower-case ASCII: accents stripped, dashes unified, ' -' closed up
    (Saskatchewan's Word export prints 'Nippi -Albright')."""
    s = (text or "").translate(_DASHES)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def squash(text):
    """fold() with every non-alphanumeric removed: for comparing ridings,
    whose dashes and spaces vary by source ('Kelowna–Lake Country' vs
    'Kelowna-Lake Country')."""
    return re.sub(r"[^a-z0-9]", "", fold(text))


def initials_of(given):
    """'R.J.' -> 'rj', 'Lori' -> 'l', 'Mary-Anne Jo' -> 'mj'."""
    return "".join(p[0] for p in re.split(r"[\s.]+", fold(given)) if p)


class Label:
    __slots__ = ("raw", "tokens", "initials", "riding", "comma")

    def __init__(self, raw, tokens, initials, riding, comma):
        self.raw, self.tokens, self.initials, self.riding, self.comma = (
            raw, tokens, initials, riding, comma)

    def __repr__(self):
        return "Label({0!r}, tokens={1}, initials={2!r}, riding={3!r})".format(
            self.raw, self.tokens, self.initials, self.riding)


def _strip_honorifics(tokens):
    out = list(tokens)
    stripped = 0
    while out and fold(out[0]).rstrip(".,") in HONORIFICS:
        # 'M.' is the French 'Monsieur' only in FIRST place: after another
        # honorific it is an initial ('Mr. M. LeBlanc', New Brunswick).
        if stripped and fold(out[0]).rstrip(".,") == "m" and len(out) > 1:
            break
        out.pop(0)
        stripped += 1
    while out and fold(out[-1]).rstrip(".,") in {"kc", "qc", "eca", "mla"}:
        out.pop()
    return out


def parse_label(raw):
    s = (raw or "").translate(_DASHES).strip()
    s = re.sub(r"\s*-\s*", "-", s)
    # A trailing '*' is a FOOTNOTE MARK, not part of the name: Alberta's V&P
    # of the COVID sittings marks each member who voted remotely ("Amery*",
    # "Sigurdson (Highwood)*") and explains it under the list ("* Member
    # voted remotely"). The raw label keeps the mark; the name is read without it.
    s = re.sub(r"\s*\*+$", "", s)
    riding = None
    m = _PAREN.search(s)
    if m:
        riding = m.group(1).strip() or None
        s = s[:m.start()].strip()
    comma = "," in s
    initials = ""
    if comma:
        head, _, tail = s.partition(",")
        tail_tokens = _strip_honorifics(tail.split())
        if tail_tokens and all(_INITIALS.match(t) for t in tail_tokens):
            initials = "".join(t.replace(".", "").lower() for t in tail_tokens)
            tokens = _strip_honorifics(head.split())
        else:
            # 'Smith, Danielle' -- the roster form, given names after the comma
            tokens = tail_tokens + _strip_honorifics(head.split())
            comma = False
    else:
        tokens = _strip_honorifics(s.split())
        while tokens and _INITIALS.match(tokens[0]) and len(tokens) > 1:
            initials += tokens.pop(0).replace(".", "").lower()
    return Label(raw, [fold(t) for t in tokens if t], initials, riding, comma)


class Resolver:
    """Resolve printed labels against dated roster terms.

    members: {member_key: {'surname', 'given', 'name'}}
    terms:   [{'member_key', 'legislature', 'party', 'riding', 'start', 'end',
               'party_dated'}]

    Two kinds of REVIEWED fact may widen what a label can match, both read
    from config/prov_record.yaml by `with_record` and never inferred:

      other_surnames  {member_key: [surname, ...]}: a surname the member also
                      sat under, as the member's own official page says
                      ("Michaela Frey (Also served under Glasgo)"). The label
                      is still matched against every member valid on the
                      day, so a second Glasgo would make it ambiguous.
      riding_aliases  {printed riding: riding}: the record's own abbreviation
                      of a constituency ("Rimbey-Rocky Mtn. House-Sundre").
    """

    def __init__(self, members, terms, other_surnames=None, riding_aliases=None):
        self.members = members
        self.terms = list(terms)
        self.other_surnames = {k: [fold(s) for s in v] for k, v in (other_surnames or {}).items()}
        self.riding_aliases = {squash(k): squash(v) for k, v in (riding_aliases or {}).items()}

    def with_record(self, prov, path=None):
        """This resolver with the province's reviewed other_surnames and
        riding_aliases (config/prov_record.yaml) loaded."""
        for a in load_other_surnames(prov, path):
            self.other_surnames.setdefault(str(a["member"]), []).append(fold(a["surname"]))
        for a in load_riding_aliases(prov, path):
            self.riding_aliases[squash(a["printed"])] = squash(a["riding"])
        return self

    def _riding_is(self, printed, riding):
        p = squash(printed)
        return squash(riding) in (p, self.riding_aliases.get(p))

    @classmethod
    def from_conn(cls, conn, prov):
        members = {}
        for key, name, surname, given in conn.execute(
                "SELECT member_key, name, surname, given FROM prov_members WHERE prov=?", (prov,)):
            members[key] = {"name": name, "surname": surname, "given": given}
        terms = [dict(zip(("member_key", "legislature", "party", "riding", "start",
                           "end", "party_dated", "source"), r)) for r in conn.execute(
            "SELECT member_key, legislature, party, riding, start, end, party_dated, source "
            "FROM prov_member_terms WHERE prov=?", (prov,))]
        return cls(members, terms)

    def valid_terms(self, date, legislature=None, party_only=False):
        """Terms valid on `date`. Party-only terms (source 'party...') are
        left out unless party_only=True asks for them as well."""
        out = []
        for t in self.terms:
            if not party_only and is_party_only(t):
                continue
            if legislature is not None and t.get("legislature") is not None \
                    and int(t["legislature"]) != int(legislature):
                continue
            if date and t.get("start") and t["start"] > date:
                continue
            if date and t.get("end") and t["end"] < date:
                continue
            out.append(t)
        return out

    def surname_vocab(self):
        """Folded surname token tuples of every member: what split_name_run
        uses to keep 'Calahoo Stonehouse' together."""
        out = set()
        for m in self.members.values():
            if m.get("surname"):
                out.add(tuple(fold(m["surname"]).split()))
        for names in self.other_surnames.values():
            out.update(tuple(s.split()) for s in names)
        return out

    def term_for(self, member_key, date, legislature=None):
        for t in self.valid_terms(date, legislature):
            if t["member_key"] == member_key:
                return t
        return None

    def party_at(self, member_key, date, legislature=None):
        """The party on the day, ONLY from a term whose source dates it."""
        hits = {t.get("party") for t in self.valid_terms(date, legislature, party_only=True)
                if t["member_key"] == member_key and t.get("party_dated")}
        return hits.pop() if len(hits) == 1 else None

    def resolve(self, raw, date, legislature=None, document=None):
        """(member_key, how) or (None, why). `document` is accepted for the
        Aliased wrapper's sake and not used here."""
        lab = parse_label(raw)
        if not lab.tokens:
            return None, "empty label"
        valid = self.valid_terms(date, legislature)
        by_key = {}
        for t in valid:
            by_key.setdefault(t["member_key"], []).append(t)
        hits = {}
        n = len(lab.tokens)
        for key, ts in by_key.items():
            m = self.members.get(key) or {}
            given = fold(m.get("given"))
            surnames = [fold(m.get("surname"))] if m.get("surname") else []
            surnames += self.other_surnames.get(key, [])
            how = None
            for k_sur, sur in enumerate(surnames):
                for i in range(n):
                    if " ".join(lab.tokens[i:]) != sur:
                        continue
                    giv = lab.tokens[:i]
                    if giv:
                        gtoks = given.replace("-", " ").split()
                        if not gtoks or not all(
                                any(g == x or (len(g) == 1 and x.startswith(g)) for x in gtoks)
                                for g in giv):
                            continue
                        how = "full-name"
                    else:
                        how = "surname"
                    break
                if how is not None:
                    if k_sur:
                        how = "other-" + how      # a reviewed other surname
                    break
            if how is None:
                continue
            if lab.initials:
                if not initials_of(m.get("given")).startswith(lab.initials):
                    continue
                how = "initial"
            if lab.riding:
                if not any(self._riding_is(lab.riding, t.get("riding")) for t in ts):
                    continue
                how = "surname+riding" if how == "surname" else how + "+riding"
            hits[key] = how
        if len(hits) == 1:
            return next(iter(hits.items()))
        if not hits:
            return None, "unknown on {0}".format(date)
        return None, "ambiguous: {0}".format(", ".join(sorted(hits)))


def is_party_only(term):
    return str(term.get("source") or "").startswith("party")


# -- reviewed label aliases ---------------------------------------------------

_ALIAS_FIELDS = ("printed", "member", "date", "document", "verified_against", "why")


def load_record(prov, path=None):
    """The province's section of config/prov_record.yaml ({} when none)."""
    path = path or RECORD
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return (raw.get("provinces") or {}).get(prov) or {}


def load_aliases(prov, path=None):
    """The province's reviewed label aliases. An entry missing any of
    printed, member, date, document, verified_against or why is refused:
    an alias nobody can check is not a reviewed one."""
    out = []
    for a in load_record(prov, path).get("label_aliases") or []:
        missing = [f for f in _ALIAS_FIELDS if not a.get(f)]
        if missing:
            raise ValueError("{0} label alias {1!r} lacks {2}".format(prov, a.get("printed"), ", ".join(missing)))
        out.append(dict(a, date=str(a["date"])))
    return out


def _reviewed(prov, section, fields, path=None):
    """Entries of one reviewed-fact section; an entry missing a field is refused."""
    out = []
    for a in load_record(prov, path).get(section) or []:
        missing = [f for f in fields if not a.get(f)]
        if missing:
            raise ValueError("{0} {1} entry {2!r} lacks {3}".format(
                prov, section, a.get(fields[0]), ", ".join(missing)))
        out.append(a)
    return out


def load_other_surnames(prov, path=None):
    """`other_surnames:` -- a surname a member also sat under, read on the
    member's own official page. Needs member, surname, document,
    verified_against and why."""
    return _reviewed(prov, "other_surnames",
                     ("surname", "member", "document", "verified_against", "why"), path)


def load_riding_aliases(prov, path=None):
    """`riding_aliases:` -- a constituency as a record abbreviates it, with
    the constituency's own name. Needs printed, riding, document,
    verified_against and why."""
    return _reviewed(prov, "riding_aliases",
                     ("printed", "riding", "document", "verified_against", "why"), path)


def load_misprints(prov, path=None):
    """`misprints:` -- ONE misspelling of one member's name that a record
    repeats over a span of sittings (Ontario's V&P printed "Cuzzeto" for Rudy
    Cuzzetto in every division list of 19 July 2018 - 21 July 2020 but a few
    weeks of 2019). A label_alias per day would be some seventy entries of
    the same fact. Needs printed, member, from, to, document_prefix (every
    document it applies in starts with it), documents (where it was read),
    verified_against and why. Read by Aliased exactly as a label alias:
    only after the normal resolver found nobody, only on a day inside the
    span and in a document under the prefix, only to a member holding a
    term that day. The fact type was approved by Christopher on 2 October
    2026."""
    out = []
    for a in _reviewed(prov, "misprints", ("printed", "member", "from", "to", "document_prefix",
                                           "documents", "verified_against", "why"), path):
        out.append(dict(a, **{"from": str(a["from"]), "to": str(a["to"])}))
    return out


def load_same_person(prov, path=None):
    """`same_person:` -- reviewed sets of member keys that are ONE member
    whose keys the seat rule cannot join (two legislatures: Manitoba's "Cliff"
    GRAYDON of the 39th-40th and "Clifford" GRAYDON of the 41st, Emerson,
    one entry on the Assembly's former-members page). Needs keys (two or
    more), document, verified_against and why. Read by
    prov_store.merge_split_members as `same_person`."""
    out = []
    for a in _reviewed(prov, "same_person", ("keys", "document", "verified_against", "why"), path):
        keys = [str(k) for k in a["keys"]]
        if len(set(keys)) < 2:
            raise ValueError("{0} same_person entry {1!r} names fewer than two keys".format(prov, keys))
        out.append(keys)
    return out


def load_same_person_keep(prov, path=None):
    """The key each reviewed same_person entry says to KEEP (`keep:`,
    optional; Newfoundland, 7 October 2026), as a set. It must be one of the
    entry's keys. An entry without it keeps the key most votes already name."""
    out = set()
    for a in _reviewed(prov, "same_person", ("keys", "document", "verified_against", "why"), path):
        if a.get("keep") is None:
            continue
        if str(a["keep"]) not in [str(k) for k in a["keys"]]:
            raise ValueError("{0} same_person keep {1!r} is not one of {2!r}".format(prov, a["keep"], a["keys"]))
        out.add(str(a["keep"]))
    return out


def load_vp_not_served(prov, path=None):
    """`vp_not_served:` -- sitting days whose Votes and Proceedings the
    legislature does not serve (the listed file is an error page, or a copy
    of another day's record), with the Hansard PDFs whose own division
    lists are read INSTEAD, for that day only. Needs date, record (the
    listed V&P URL, which must still fail), hansard (the day's PDFs, which
    must be in the day's Hansard listing), divisions (how many recorded
    votes Hansard prints that day), verified_against and why."""
    out = []
    for a in _reviewed(prov, "vp_not_served", ("date", "record", "hansard", "divisions",
                                               "verified_against", "why"), path):
        out.append(dict(a, date=str(a["date"]), hansard=[str(u) for u in a["hansard"]],
                        divisions=int(a["divisions"])))
    return out


# -- reviewed facts about ONE division ---------------------------------------
#
# Christopher, 2 October 2026: where Hansard is explicit for the SAME division,
# a reviewed entry may settle a bare ambiguous name or supply a total the V&P
# omits; and a reviewed entry may correct a bill number the record misprints.
# Every entry is keyed to ONE division_key (and, for a name, one printed
# label in one list): it never becomes a general alias. The tally check runs
# exactly as before on the result.

_DIVISION_FACT_FIELDS = {
    "hansard_labels": ("division", "position", "printed", "member", "document", "hansard",
                       "quoted", "why"),
    "hansard_totals": ("division", "position", "total", "document", "hansard", "quoted", "why"),
    "bill_corrections": ("division", "printed_bill", "bill", "document", "verified_against", "why"),
    # Christopher, 7 October 2026: a member the Clerk's count includes and the
    # printed list omits, where a SECOND official record states the vote.
    "added_members": ("division", "position", "member", "document", "record", "quoted", "why"),
    # Christopher, 7 October 2026: a printed list under the wrong heading,
    # moved to the position the proclaimed result and the Journal show.
    "list_positions": ("division", "printed_position", "position", "count", "document", "hansard",
                       "quoted", "why"),
}
REVIEWED = "reviewed, config/prov_record.yaml"


class ReviewedDivisions:
    """The province's division-scoped reviewed facts, by division_key."""

    def __init__(self, entries=None):
        self.by = {}
        for section, items in (entries or {}).items():
            for a in items:
                self.by.setdefault(str(a["division"]), {}).setdefault(section, []).append(a)

    @classmethod
    def load(cls, prov, path=None):
        entries = {}
        for section, fields in _DIVISION_FACT_FIELDS.items():
            entries[section] = _reviewed(prov, section, fields, path)
        return cls(entries)

    def facts(self, division_key):
        return self.by.get(str(division_key), {})

    def total(self, division_key, position, printed):
        """(total, note): a reviewed total for a list the record printed
        WITHOUT one; or, in the REPLACE form, for a list whose printed total
        is a misprint. The replace form must state `replaces:`, the figure
        the record prints, and applies only while the record still prints
        exactly that figure (as a bill correction does); the printed figure
        stays in the note. Without `replaces:` a printed total is never
        replaced (Christopher, 2 October 2026: Manitoba's 5 Dec 2013 "18"
        over 17 names, Hansard "Nays 17")."""
        for a in self.facts(division_key).get("hansard_totals", []):
            if a["position"] != position:
                continue
            quoted = " ".join(str(a["quoted"]).split())
            if a.get("replaces") is not None:
                if printed is not None and int(printed) == int(a["replaces"]):
                    return int(a["total"]), "{0} total {1} from Hansard replaces the record's printed {2} " \
                                            "({3!r}; {4})".format(position, a["total"], printed, quoted, REVIEWED)
                return printed, "reviewed {0} total {1} not used: the record prints {2}, not {3}".format(
                    position, a["total"], printed, a["replaces"])
            if printed is not None:
                return printed, "reviewed {0} total {1} not used: the record prints {2}".format(
                    position, a["total"], printed)
            return int(a["total"]), "{0} total {1} from Hansard ({2!r}; {3})".format(
                position, a["total"], quoted, REVIEWED)
        return printed, None

    def list_position(self, division_key, printed_position, count):
        """(position, note): where a list the record prints under
        `printed_position` belongs, for ONE division whose Hansard reads the
        same members under another position (Quebec, 7 December 2017: the
        annex heads the 20 CAQ members "CONTRE - 20", the Journal reads them
        after "Y a-t-il des abstentions?" and the Secretary proclaims
        "Abstentions : 20"). Applied only while the record still prints
        exactly `count` names under `printed_position`; the printed heading
        stays in the note (Christopher, 7 October 2026)."""
        for a in self.facts(division_key).get("list_positions", []):
            if a["printed_position"] != printed_position:
                continue
            quoted = " ".join(str(a["quoted"]).split())
            if int(a["count"]) != int(count):
                return printed_position, "reviewed list position not used: the record prints {0} name(s) " \
                                         "under {1}, not {2}".format(count, printed_position, a["count"])
            return a["position"], "the record prints these {0} under {1}; Hansard reads them as {2} " \
                                  "({3!r}; {4})".format(count, printed_position, a["position"], quoted, REVIEWED)
        return printed_position, None

    def bill(self, division_key, printed):
        """(number, note): the reviewed bill for a division whose record
        prints the wrong one. Applied only when the record still prints the
        number the entry was checked against."""
        for a in self.facts(division_key).get("bill_corrections", []):
            if str(a["printed_bill"]) == str(printed):
                return str(a["bill"]), "bill: the record names Bill {0}; stored as Bill {1} ({2})".format(
                    printed, a["bill"], REVIEWED)
            return printed, "reviewed bill correction not used: the record now names Bill {0}, " \
                            "not Bill {1}".format(printed, a["printed_bill"])
        return printed, None

    def add(self, division_key, votes, printed, resolver, date, legislature=None):
        """Add a member the printed list omits, named by a reviewed
        `added_members` entry for THIS division (Christopher, 7 October 2026).
        Only while the list prints fewer names than the record's own count
        for that side (`printed`: {'Yea': n, ...}), only for a member placed
        nowhere in the division who holds a term on the day, and only from
        an entry citing a second official record that states the vote
        (`record`, `quoted`). The tally check then runs as normal. Returns
        the notes."""
        notes = []
        for a in self.facts(division_key).get("added_members", []):
            position, member = a["position"], str(a["member"])
            total = printed.get(position)
            have = [v for v in votes if v["position"] == position]
            if total is None or len(have) >= int(total):
                notes.append("reviewed addition of {0} not used: the {1} list already prints {2} name(s) for "
                             "a count of {3}".format(member, position, len(have), total))
                continue
            if any(v.get("member_key") == member for v in votes):
                notes.append("reviewed addition of {0} not used: already placed in the division".format(member))
                continue
            if resolver.term_for(member, date, legislature) is None:
                notes.append("reviewed addition of {0} not used: no term on {1}".format(member, date))
                continue
            votes.append({"position": position, "ordinal": max([v["ordinal"] for v in have] + [0]) + 1,
                          "raw_label": "[not printed]", "member_key": member,
                          "how": "added from {0} ({1})".format(a["record"], REVIEWED),
                          "party_at_vote": resolver.party_at(member, date, legislature)})
            notes.append("{0} {1} added: counted, not printed; {2} says {3!r} ({4})".format(
                position, member, a["record"], " ".join(str(a["quoted"]).split()), REVIEWED))
        return notes

    def settle(self, division_key, votes, resolver, date, legislature=None):
        """Settle bare AMBIGUOUS labels named by a reviewed entry, in place.
        The entry's member must be one of the candidates the resolver found
        and hold a term on the day, and the printed label must occur exactly
        once in that list. Returns the notes."""
        notes = []
        for a in self.facts(division_key).get("hansard_labels", []):
            hits = [v for v in votes if v["position"] == a["position"]
                    and _norm_label(v["raw_label"]) == _norm_label(a["printed"])]
            if len(hits) != 1:
                notes.append("reviewed label {0!r} not used: {1} such label(s) in the {2} list".format(
                    a["printed"], len(hits), a["position"]))
                continue
            v = hits[0]
            how = str(v.get("how") or "")
            candidates = [k.strip() for k in how.partition(":")[2].split(",")] \
                if how.startswith("ambiguous") else []
            member = str(a["member"])
            # `office: true` -- the list prints an OFFICE, not a name (Ontario,
            # 21 Sep 2017: "Deputy Speaker" among the Ayes, the chair's casting
            # vote). No member can match it, so there are no candidates; the
            # label must have resolved to nobody, and Hansard for the same
            # division names who held the office (Christopher, 2 October 2026:
            # casting votes are placed).
            if a.get("office") and not v.get("member_key") and how.startswith("unknown"):
                candidates = [member]
            # `by_exclusion: [keys]` -- the label prints a surname whose
            # distinguishing riding is lost or blank, and the record names
            # nobody (Quebec, 9 February 2022, vote 225: "Tardif (CAQ) ( )"
            # in a group vote). Every OTHER member it could be is named in
            # this same division (here Marie-Louise Tardif, printed with her
            # riding), so it is the entry's member, provided he is named
            # nowhere else in it (Christopher, 8 October 2026: placed by
            # exclusion). Scoped to this division and label like every entry.
            if a.get("by_exclusion") and not v.get("member_key") and \
                    (how.startswith("unknown") or how.startswith("unparsed")):
                placed = {str(x.get("member_key")) for x in votes if x.get("member_key")}
                others = [str(k) for k in a["by_exclusion"]]
                if all(k in placed for k in others) and member not in placed:
                    candidates = [member]
                else:
                    notes.append("reviewed label {0!r} not used: by exclusion needs {1} placed and {2} "
                                 "absent in this division".format(a["printed"], ", ".join(others), member))
                    continue
            if v.get("member_key") or member not in candidates:
                notes.append("reviewed label {0!r} not used: {1}".format(
                    a["printed"], "already resolved" if v.get("member_key")
                    else "{0} is not among the members it could be ({1})".format(member, how)))
                continue
            if resolver.term_for(member, date, legislature) is None:
                notes.append("reviewed label {0!r} not used: {1} holds no term on {2}".format(
                    a["printed"], member, date))
                continue
            v["member_key"] = member
            v["how"] = "{0} ({1})".format("by exclusion" if a.get("by_exclusion") else "hansard", REVIEWED)
            v["party_at_vote"] = resolver.party_at(member, date, legislature)
            notes.append("{0} {1!r} settled {2} ({3!r}; {4})".format(
                a["position"], a["printed"],
                "by exclusion of {0}".format(", ".join(str(k) for k in a["by_exclusion"]))
                if a.get("by_exclusion") else "from Hansard", " ".join(str(a["quoted"]).split()), REVIEWED))
        return notes


class Aliased:
    """Wrap a resolver: the reviewed aliases are consulted ONLY when the
    normal resolver found nobody ('unknown ...'), never over an ambiguous or
    a resolved label. A match must be exact (the label as printed, whitespace
    aside), on the entry's own date and, when the caller says which, in the
    entry's own document; its member must hold a term that day. Still
    unique-or-nothing, and the tally check still runs on the result.

    `misprints` (load_misprints) are read the same way over a span of days,
    and only when the caller names the document and it lies under the
    entry's document_prefix."""

    def __init__(self, inner, aliases, base=None, misprints=None):
        self.inner = inner
        self.base = base or getattr(inner, "r", inner)
        self.by = {}
        for a in aliases or []:
            self.by.setdefault((_norm_label(a["printed"]), a["date"]), []).append(a)
        self.misprints = {}
        for a in misprints or []:
            self.misprints.setdefault(_norm_label(a["printed"]), []).append(a)

    def party_at(self, member_key, date, legislature=None):
        return self.inner.party_at(member_key, date, legislature)

    def resolve(self, raw, date, legislature=None, document=None):
        key, how = self.inner.resolve(raw, date, legislature)
        if key or not str(how).startswith("unknown"):
            return key, how
        hits = [a for a in self.by.get((_norm_label(raw), date), [])
                if document is None or a["document"] == document]
        hits += [a for a in self.misprints.get(_norm_label(raw), [])
                 if document and a["from"] <= date <= a["to"]
                 and document.startswith(a["document_prefix"])]
        targets = sorted({a["member"] for a in hits})
        if not targets:
            return key, how
        if len(targets) > 1:
            return None, "ambiguous alias: {0}".format(", ".join(targets))
        if self.base.term_for(targets[0], date, legislature) is None:
            return None, "alias {0!r} -> {1}, who holds no term on {2}".format(raw, targets[0], date)
        return targets[0], "alias (reviewed, config/prov_record.yaml)"


def _norm_label(s):
    return re.sub(r"\s+", " ", (s or "").translate(_DASHES)).strip()


# -- column-run splitting (Alberta V&P, Saskatchewan 29L minutes) ------------

_PAGE_FURNITURE = re.compile(
    r"^\s*(?:=+PAGE|\d+|\d*\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),"
    r"\s+\w+\s+\d{1,2},\s+\d{4}\s*\d*)\s*$")
STOP_WORDS = {"reading", "readings", "committee", "bill", "bills", "motion", "motions",
              "orders", "order", "government", "assembly", "speaker", "chair", "page",
              "royal", "assent", "adjournment", "debate", "amendment", "yeas", "nays",
              "for", "against", "totals", "pour", "contre", "the", "and", "of"}


def is_furniture(line):
    """A page number, a running date header or a page marker: skipped inside
    a name list, never a reason to end it."""
    return bool(_PAGE_FURNITURE.match(line or "")) or not (line or "").strip()


_SPACED = re.compile(r"(?<!\S)(?:\S ){2,}\S(?!\S)")


def close_letter_spacing(line):
    """'G a n l e y  P a y n e' -> 'Ganley  Payne'. pypdf reads some of
    Alberta's V&P names one glyph at a time (24 June 2015: "(Leduc-Beaumont)
    G a n l e y  P a y n e"; 29 May 2019: "v a n  D i j k e n"), with ONE
    space between letters and two between words. A run of three or more
    single characters each separated by one space is closed up; two (an
    initial pair, 'R J') is left alone."""
    return _SPACED.sub(lambda m: m.group(0).replace(" ", ""), line or "")


def close_split_names(line, vocab_tokens):
    """'Cortes-Vargas La rivee Shepherd' -> 'Cortes-Vargas Larivee Shepherd'.
    pypdf sometimes breaks one surname in two with a space (Alberta V&P,
    December 2017 to November 2018). A lower-case fragment is joined to the
    word before it ONLY when the fragment is not itself a surname token
    ('van', 'de') and the joined word IS one; anything else is left to fail
    honestly."""
    parts = re.split(r"(\s+)", line or "")
    out = []
    for p in parts:
        if (p and p[0].islower() and fold(p).strip(".,") not in vocab_tokens
                and len(out) >= 2 and out[-1] == " " and out[-2][:1].isupper()
                and fold(out[-2] + p) in vocab_tokens):
            out.pop()
            out[-1] = out[-1] + p
            continue
        out.append(p)
    return "".join(out)


def is_name_line(line, vocab_tokens):
    """True when every word on the line could be part of a member's name:
    capitalised (or a known surname token such as 'de', 'van'), no digits,
    no sentence punctuation, and not a heading word. A wrapped riding line
    '(Edmonton-Riverview)' or 'Jaw North)' counts, and so does a line holding
    only the remote-vote footnote mark '*' wrapped from the name before it."""
    s = close_split_names(close_letter_spacing((line or "").strip()), vocab_tokens)
    if not s:
        return False
    if re.search(r"[0-9:;!?“”\"]", s):
        return False
    body = re.sub(r"\([^()]*\)?|^[^()]*\)", " ", s)     # ridings, open or closed
    body = body.replace("*", " ")                       # footnote marks ('Amery*')
    for w in body.split():
        f = fold(w).strip(".,")
        if not f:
            continue
        if f in STOP_WORDS:
            return False
        if f in vocab_tokens:
            continue
        if not w[0].isupper():
            return False
        if w.endswith(".") and len(w) > 3:              # a sentence end, not an initial
            return False
    return True


def split_name_run(lines, vocab):
    """Labels from lines of column-run surnames.

    vocab: set of folded surname tuples (Resolver.surname_vocab()). Tokens are
    matched GREEDILY against it, longest first, so 'Calahoo Stonehouse Haji
    Sabir' is three members, not four; a token matching nothing becomes a
    one-word label of its own and fails resolution honestly. A parenthesised
    riding -- on the same line or wrapped onto the next, open or split across
    two lines -- attaches to the label just before it, and so does a
    footnote mark '*' standing on its own ('Hanson *', or 'Gotfried' with
    its '*' wrapped to the start of the next line): it always FOLLOWS the
    name it marks, and the label becomes 'Hanson*'."""
    tokens = vocab_tokens(vocab)
    text = " ".join(close_split_names(close_letter_spacing(l.strip()), tokens)
                    for l in lines if l and not is_furniture(l))
    text = (text or "").translate(_DASHES)
    parts = re.findall(r"\([^()]*\)|[^\s()]+", text)
    # A riding split as '(Moose' ... 'Jaw North)' over two lines is joined by
    # the join above, so '(...)' arrives whole; a stray ')' never does.
    longest = max((len(v) for v in vocab), default=1)
    labels = []
    i = 0
    while i < len(parts):
        p = parts[i]
        if p.startswith("("):
            if labels:
                labels[-1] = labels[-1] + " " + p
            i += 1
            continue
        if set(p) == {"*"}:
            if labels:
                labels[-1] = labels[-1] + p
            i += 1
            continue
        take = 1
        for k in range(min(longest, len(parts) - i), 1, -1):
            chunk = parts[i:i + k]
            if any(c.startswith("(") or c.endswith("*") for c in chunk[:-1]) or chunk[-1].startswith("("):
                continue
            if tuple(fold(c).rstrip("*") for c in chunk) in vocab:
                take = k
                break
        labels.append(" ".join(parts[i:i + take]))
        i += take
    return labels


def vocab_tokens(vocab):
    return {tok for tup in vocab for tok in tup}
