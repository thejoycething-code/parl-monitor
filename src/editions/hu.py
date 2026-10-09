"""Hungary: what became law, from the Magyar Közlöny (src/hu_store.py,
tools/hu_gazette.py). Phase 0 (HU6, 10 October 2026).

A "became law" edition. The Országgyűlés's bills and recorded votes are not
collected: parlament.hu answers us with a CAPTCHA (never solved or worked
around), and its W-API needs a personal token (HU1), so every edition
carries a standing line saying so. What the gazette gives is the end of the
process: each Act, amendment to the Fundamental Law, resolution of the
Országgyűlés, government resolution and decree, ministerial decree and
Constitutional Court (AB) decision, as its contents page lists them, a week
or more after the vote and without positions.

Items: Acts and amendments to the Fundamental Law under "Laws", everything
else under "Gazette notices", each with the Hungarian title verbatim and an
English takeaway built from the designation (what it is, its number, where
it was published) and the title's own legal formula ("... módosításáról":
it amends). No model reads anything (X16). Presidential (KE) and Prime
Minister's (ME) decisions, which are appointments, and the Kúria's
local-government rulings are stored but left out; a watched one is shown.

HU4: an amendment to the Fundamental Law is shown whatever its words, as a
watched item under the rule's own watchlist key, "HU4".
"""

from __future__ import annotations

import json

from src import country_edition as ce
from src import hu_store

LAW_TYPES = ("act", "fundamental_law")
GAZETTE_TYPES = ("ogy_resolution", "gov_resolution", "gov_decree", "ministerial_decree",
                 "ab_decision")
HU4 = "HU4"
HU4_ENTRY = {"areas": [], "why": "HU4: every amendment to the Fundamental Law is triaged "
                                 "and read in full, whatever its words (Chris, 10 October 2026)."}
MONTHS = ce.MONTHS

# The title's closing legal formula, folded, and what it says in English.
# First match wins; the more specific formulas come first.
FORMULAS = (
    ("alaptorveny-ellenessegenek megallapitasarol es megsemmisiteserol",
     "It finds a provision or ruling contrary to the Fundamental Law and annuls it"),
    ("alaptorveny-ellenessegenek megallapitasarol",
     "It finds a provision or ruling contrary to the Fundamental Law"),
    ("alkotmanyjogi panasz elutasitasarol", "It rejects a constitutional complaint"),
    ("elutasitasarol", "It rejects a petition"),
    ("visszautasitasarol", "It turns a petition away"),
    ("hatalyon kivul helyezeserol", "It repeals earlier law"),
    ("kihirdeteserol", "It promulgates an international agreement"),
    ("modositasarol", "It amends existing law"),
    ("modositasaval osszefuggo", "It makes the changes that follow from another amendment"),
    ("letrehozasarol", "It establishes a body or scheme"),
    ("megszuneserol", "It ends a body or scheme"),
    ("tamogatasarol", "It provides funding or support"),
    ("vegrehajtasarol", "It implements an Act"),
)


STANDING = ("Bills and recorded votes await the Országgyűlés's API token (HU1): parlament.hu "
            "answers this project with a CAPTCHA, which is never solved or worked around. Until "
            "then this edition reports what became law, from the official gazette, a week or "
            "more after the vote and without positions.")


def notice(conn, today, dm):
    """The standing line, in every edition and DM (quiet weeks included)."""
    if dm:
        return "_Bills and votes await the parliament's API token (HU1); this is what became law._"
    return "> " + STANDING


def watchlist(config_dir=None):
    wl = dict(hu_store.watchlist())
    wl.setdefault(HU4, HU4_ENTRY)
    return wl


def long_date(iso):
    try:
        return ce.long_date(iso)
    except (TypeError, ValueError):
        return iso or "an unknown date"


def designation_english(kind, number, issuer, key):
    """'Act LVI of 2026', 'Government decree 225/2026', ..."""
    if kind == "fundamental_law":
        return "An amendment to the Fundamental Law"
    if kind == "act" and number:
        numeral, _, year = number.partition("/")
        return "Act {0} of {1} (Act {2})".format(numeral, year, hu_store.roman(numeral))
    names = {"ogy_resolution": "Resolution {0} of the Országgyűlés",
             "gov_resolution": "Government resolution {0}",
             "gov_decree": "Government decree {0}",
             "ab_decision": "Constitutional Court decision {0}",
             "ministerial_decree": "Decree {0} of " + (issuer or "a minister")}
    if kind in names and number:
        return names[kind].format(number)
    return key


def formula(title):
    folded = ce.noise_mod.fold(title)
    for pattern, english in FORMULAS:
        if pattern in folded:
            return english
    return None


def takeaway(r):
    issue = r["issue_key"].partition("/")[2]
    bits = ["{0}, published in Magyar Közlöny No. {1} of {2}{3}".format(
        designation_english(r["type"], r["number"], r["issuer"], r["entry_key"]), issue,
        long_date(r["date"]), ", page {0}".format(r["page"]) if r["page"] else "")]
    f = formula(r["title"])
    if f:
        bits.append("By its title: " + f[0].lower() + f[1:])
    if r["rule"] == HU4:
        bits.append("Shown under HU4 whatever its words; its subject is in the text, not "
                    "the title")
    return ". ".join(bits)


def items(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT e.*, i.url AS issue_url FROM hu_gazette_entries e "
                           "LEFT JOIN hu_gazette_issues i USING (issue_key) WHERE "
                           + ce.window_sql("e.date"), (since, until)):
        key = r["entry_key"]
        own_watch = key in wl
        hu4 = r["rule"] == HU4
        watched = own_watch or hu4
        if r["type"] not in LAW_TYPES + GAZETTE_TYPES and not own_watch:
            continue
        if not ce.on_ground(r["areas"], watched):
            continue
        terms = json.loads(r["matched_terms"] or "[]")
        lines = ["Matched: {0}.".format(", ".join(terms[:8]))] if terms else []
        out.append(ce.item("hu", "law" if r["type"] in LAW_TYPES else "gazette", key,
                           r["date"], r["title"] or key, ce.areas_of(r["areas"]), r["tier"],
                           watched, url=r["issue_url"], terms=r["matched_terms"],
                           takeaway=takeaway(r), lines=lines,
                           watch_key=None if own_watch or not hu4 else HU4))
    return out


COUNTRY = ce.Country(
    cc="hu", name="Hungary", chamber="Országgyűlés, through the Magyar Közlöny",
    language="Hungarian",
    taxonomies=(("taxonomy-hu.yaml", "hu"),),
    items=items, watchlist=watchlist, flag=":flag-hu:",
    kinds=("law", "gazette"),
    members_note="No member positions: this edition reads the official gazette, which "
                 "records what became law, not who voted",
    notice=notice,
    coverage=("The Magyar Közlöny is read in full, every issue; each contents entry is "
              "classified by its Hungarian title.",
              "Presidential (KE) and Prime Minister's (ME) decisions, mostly appointments, "
              "and the Kúria's local-government rulings are stored but not shown unless "
              "watched.",
              "The Hivatalos Értesítő and the Indokolások Tára (the explanatory memoranda) "
              "are not read."),
)
