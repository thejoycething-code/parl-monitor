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
    """

    def __init__(self, members, terms):
        self.members = members
        self.terms = list(terms)

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
            sur = fold(m.get("surname"))
            given = fold(m.get("given"))
            if not sur:
                continue
            how = None
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
            if how is None:
                continue
            if lab.initials:
                if not initials_of(m.get("given")).startswith(lab.initials):
                    continue
                how = "initial"
            if lab.riding:
                if not any(squash(t.get("riding")) == squash(lab.riding) for t in ts):
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


class Aliased:
    """Wrap a resolver: the reviewed aliases are consulted ONLY when the
    normal resolver found nobody ('unknown ...'), never over an ambiguous or
    a resolved label. A match must be exact (the label as printed, whitespace
    aside), on the entry's own date and, when the caller says which, in the
    entry's own document; its member must hold a term that day. Still
    unique-or-nothing, and the tally check still runs on the result."""

    def __init__(self, inner, aliases, base=None):
        self.inner = inner
        self.base = base or getattr(inner, "r", inner)
        self.by = {}
        for a in aliases or []:
            self.by.setdefault((_norm_label(a["printed"]), a["date"]), []).append(a)

    def party_at(self, member_key, date, legislature=None):
        return self.inner.party_at(member_key, date, legislature)

    def resolve(self, raw, date, legislature=None, document=None):
        key, how = self.inner.resolve(raw, date, legislature)
        if key or not str(how).startswith("unknown"):
            return key, how
        hits = [a for a in self.by.get((_norm_label(raw), date), [])
                if document is None or a["document"] == document]
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


def is_name_line(line, vocab_tokens):
    """True when every word on the line could be part of a member's name:
    capitalised (or a known surname token such as 'de', 'van'), no digits,
    no sentence punctuation, and not a heading word. A wrapped riding line
    '(Edmonton-Riverview)' or 'Jaw North)' counts."""
    s = (line or "").strip()
    if not s:
        return False
    if re.search(r"[0-9:;!?“”\"]", s):
        return False
    body = re.sub(r"\([^()]*\)?|^[^()]*\)", " ", s)     # ridings, open or closed
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
    two lines -- attaches to the label just before it."""
    text = " ".join(l.strip() for l in lines if l and not is_furniture(l))
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
        take = 1
        for k in range(min(longest, len(parts) - i), 1, -1):
            chunk = parts[i:i + k]
            if any(c.startswith("(") for c in chunk):
                continue
            if tuple(fold(c) for c in chunk) in vocab:
                take = k
                break
        labels.append(" ".join(parts[i:i + take]))
        i += take
    return labels


def vocab_tokens(vocab):
    return {tok for tup in vocab for tok in tup}
