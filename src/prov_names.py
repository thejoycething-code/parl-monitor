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
"""

from __future__ import annotations

import re
import unicodedata

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
    while out and fold(out[0]).rstrip(".,") in HONORIFICS:
        out.pop(0)
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
                           "end", "party_dated"), r)) for r in conn.execute(
            "SELECT member_key, legislature, party, riding, start, end, party_dated "
            "FROM prov_member_terms WHERE prov=?", (prov,))]
        return cls(members, terms)

    def valid_terms(self, date, legislature=None):
        out = []
        for t in self.terms:
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
        hits = {t.get("party") for t in self.valid_terms(date, legislature)
                if t["member_key"] == member_key and t.get("party_dated")}
        return hits.pop() if len(hits) == 1 else None

    def resolve(self, raw, date, legislature=None):
        """(member_key, how) or (None, why)."""
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
