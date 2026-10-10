"""Slovakia: the weekly edition's adapter (src/country_edition.py).

Reads the sk_* tables tools/sk_rollcalls.py fills (src/sk_store.py): the
Národná rada's prints (tlače), its recorded votes with every member's
position and the club the vote page grouped them under, and
interpellations.

TOTALS COME FROM THE MEMBER POSITIONS. The open data's absent count
(`countNotPresent`, stored as sk_divisions.absent) is wrong on 568 of the
term's 4,570 open votes, about 12% (docs/slovakia-scope.md). So a vote whose
positions have been read shows a tally counted from them, absences
included; a vote whose positions are not read yet shows the open data's
for, against, abstaining and not voting, which agree with the pages, and
leaves absences out rather than print a wrong number. The absent field is
never read here.

A vote's label is the print's title, its reading, then the question put
("Hlasovanie o návrhu zákona ako o celku."). The question leads the item's
title here, both verbatim, so each line of a group says which vote it was;
the print's own title heads the group. Votes on one print in one week fold
into one entry; the vote on the bill as a whole is the decisive one.
"""

from __future__ import annotations

import re

from src import country_edition as ce

CC = "sk"
VOTE_URL = "https://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID={id}"
PRINT_URL = ("https://www.nrsr.sk/web/Default.aspx?sid=zakony/cpt&ZakZborID=13"
             "&CisObdobia={term}&ID={tlac}")
YES, NO, ABSTAIN = ("z",), ("p",), ("?",)

# The question put, in English, by a folded fragment of the label's last
# sentence; the first match wins.
QUESTIONS = (
    ("ako o celku", "Final vote on the bill as a whole"),
    ("ustavnom zakone ako", "Final vote on the constitutional law as a whole"),
    ("aby bol navrh zakona prerokovany v druhom citani",
     "First reading: whether the bill goes on to a second reading"),
    ("pozmenujuc", "Vote on amendments"),
    ("nepokracovat v rokovani", "Motion to stop debating the bill"),
    ("vratit navrh zakona na dopracovanie", "Motion to send the bill back for redrafting"),
    ("navrhu uznesenia", "Vote on the draft resolution"),
    ("informacie", "Vote on a point of the committee's report"),
    ("namietk", "Vote on an objection"),
    ("skratene legislativne konanie", "Vote on the government's request for fast-track procedure"),
)
READINGS = (("prve citanie", "first reading"), ("druhe citanie", "second reading"),
            ("tretie citanie", "third reading"))
RESULTS = {"navrh presiel": "the motion passed", "navrh nepresiel": "the motion did not pass"}
BILL_TYPES = {"navrh zakona": "Bill", "informacia": "Information to the House",
              "sprava": "Report", "medzinarodna zmluva": "International treaty",
              "iny typ": "Other print"}


def _fold(text):
    from src.noise import fold
    return fold(text)


def sentence(text):
    """A takeaway ends with a full stop: a group's decisive vote prints it as is."""
    text = (text or "").strip()
    return text if not text or text.endswith((".", "…", "?", "!")) else text + "."


def split_label(name):
    """(head, question): the print-and-reading part and the question put,
    both verbatim. A label without a question is all head."""
    parts = [p.strip() for p in (name or "").split("\n") if p.strip()]
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    m = re.search(r"(Hlasovanie o .*)$", name or "")
    if m:
        return (name[:m.start()].strip(), m.group(1).strip())
    return ce.clean(name), None


def vote_title(name):
    head, question = split_label(name)
    return ce.clean("{0} {1}".format(question, head) if question else head)


def question_english(name):
    _, q = split_label(name)
    q = _fold(q or "")
    return next((en for frag, en in QUESTIONS if frag in q), None)


def reading_english(name):
    head, _ = split_label(name)
    h = _fold(head)
    return next((en for frag, en in READINGS if frag in h), None)


def tally(conn, voting_id):
    """{code: count} from the stored positions; {} when none are stored."""
    out = {}
    for r in ce.rows(conn, "SELECT position, COUNT(*) AS n FROM sk_votes WHERE voting_id = ? "
                     "GROUP BY position", (voting_id,)):
        out[r["position"]] = r["n"]
    return out


def positions(conn, r):
    """(name, club at the vote, position) for every member, [] for a secret
    ballot or before the positions are read."""
    if r["is_secret"]:
        return []
    return [(m["name"] or "member {0}".format(m["mp_id"]), m["club"] or "no club",
             (m["position"] or "").lower())
            for m in ce.rows(conn, "SELECT v.mp_id, v.club, v.position, m.name FROM sk_votes v "
                             "LEFT JOIN sk_members m ON m.mp_id = v.mp_id WHERE v.voting_id = ?",
                             (r["voting_id"],))]


def vote_lines(conn, r):
    result = ce.clean(r["result"]) or None
    if r["is_secret"]:
        return [ce.tally_line(r["agreed"], r["disagreed"], r["abstained"], result=result,
                              how="secret ballot: totals only"),
                "A secret ballot: no member positions exist."]
    t = tally(conn, r["voting_id"])
    if t:
        n = sum(t.values())
        how = "counted from the {0} member positions: {1} not voting, {2} absent".format(
            n, t.get("N", 0), t.get("0", 0))
        lines = [ce.tally_line(t.get("Z", 0), t.get("P", 0), t.get("?", 0), result=result,
                               how=how)]
        pos = positions(conn, r)
        lines.append(ce.split_line(ce.group_counts([(c, p) for _, c, p in pos], YES, NO, ABSTAIN),
                                   label="By club at the vote"))
        lines.append(ce.members_line(len(pos), ce.rebels(pos, YES, NO)))
        return lines
    how = ("open-data totals, {0} not voting; absences left out until the member positions "
           "are read, the open data's absent count being wrong on about 12% of votes".format(
               r["not_voting"] if r["not_voting"] is not None else "?"))
    return [ce.tally_line(r["agreed"], r["disagreed"], r["abstained"], result=result, how=how)]


def bill_title(conn, bill_key):
    if not bill_key:
        return None
    got = ce.rows(conn, "SELECT title FROM sk_bills WHERE bill_key = ?", (bill_key,))
    return got[0]["title"] if got else None


def votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM sk_divisions WHERE " + ce.window_sql("date")
                     + " ORDER BY date, number", (since, until)):
        key = r["bill_key"] or "vote:{0}".format(r["voting_id"])
        watched = bool(r["bill_key"]) and r["bill_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        bits = [x for x in (question_english(r["name"]), reading_english(r["name"])) if x]
        takeaway = ", ".join(bits)
        res = RESULTS.get(_fold(r["result"]).strip(" ."))
        if res:
            takeaway = (takeaway + ". " if takeaway else "") + "The record says {0}".format(res)
        own = bool(ce.areas_of(r["own_areas"])) if r["own_areas"] is not None else None
        head, _ = split_label(r["name"])
        pos = positions(conn, r)
        out.append(ce.vote(
            CC, key, r["date"], vote_title(r["name"]), ce.areas_of(r["areas"]), r["tier"],
            watched, vote_lines(conn, r), terms=r["matched_terms"], body=ce.clean(r["name"]),
            url=VOTE_URL.format(id=r["voting_id"]), takeaway=sentence(takeaway) or None,
            group=("sk", key), group_title=bill_title(conn, r["bill_key"]) or head,
            final="ako o celku" in _fold(r["name"]),
            own=False if own is False else None,
            positions=pos or None, rebels=ce.rebels(pos, YES, NO) if pos else None))
    return out


def new_prints(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM sk_bills WHERE " + ce.window_sql("delivered")
                     + " ORDER BY delivered, CAST(tlac AS INTEGER)", (since, until)):
        watched = r["bill_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        kind = BILL_TYPES.get(_fold(r["type_name"]).strip(), ce.clean(r["type_name"]))
        out.append(ce.item(
            CC, "new", r["bill_key"], r["delivered"], r["title"], ce.areas_of(r["areas"]),
            r["tier"], watched, url=PRINT_URL.format(term=r["term"], tlac=r["tlac"]),
            terms=r["matched_terms"],
            takeaway="{0}, print (tlač) {1}, delivered to the House".format(kind, r["tlac"])))
    return out


def interpellations(conn, since, until, wl):
    out = []
    for kind, col in (("question", "submitted"), ("answer", "answered")):
        for r in ce.rows(conn, "SELECT * FROM sk_interpellations WHERE " + ce.window_sql(col)
                         + " ORDER BY " + col, (since, until)):
            if not ce.on_ground(r["areas"], False):
                continue
            who = ce.clean(r["questioner"])
            to = ce.clean(r["addressee"])
            when = ce.long_date(ce.day(r["submitted"])) if r["submitted"] else None
            if kind == "question":
                take = "Interpellation by {0}, addressed to: {1}".format(
                    who or "a member", to or "the government")
            else:
                take = "Answered: the interpellation by {0}{1}, addressed to: {2}".format(
                    who or "a member", " of " + when if when else "", to or "the government")
            out.append(ce.item(
                CC, kind, "int:{0}".format(r["int_id"]), r[col], r["subject"],
                ce.areas_of(r["areas"]), r["tier"], False, status=r["state"],
                terms=r["matched_terms"], takeaway=sentence(take)))
    return out


def items(conn, since, until, wl):
    return (votes(conn, since, until, wl) + new_prints(conn, since, until, wl)
            + interpellations(conn, since, until, wl))


COUNTRY = ce.Country(
    cc=CC, name="Slovakia", chamber="Národná rada Slovenskej republiky", language="Slovak",
    taxonomies=(("taxonomy-sk.yaml", "sk"),),
    items=items,
    members_note=("Tallies are counted from the member positions where they have been read "
                  "(the open data's absent count is wrong on about 12% of votes and is never "
                  "used); clubs are as the vote page grouped members on the day, so a member "
                  "against their club's majority is named"),
    coverage=(
        "Member positions are read only for votes on our ground, newest first, within the "
        "weekly job's budget; a vote without them shows the open data's totals with "
        "absences left out.",
        "Print titles name the act they amend, so a print whose title says only that "
        "(tlač 733, the 2025 constitutional amendment) is watched by key; the bill "
        "documents are phase 2 (SK6).",
        "The legislative stage of each print is not collected yet (phase 2), so there is "
        "no stage-moves section.",
    ),
)
