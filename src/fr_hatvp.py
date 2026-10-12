"""France: the HATVP's declarations of interests and activities, the
declarant's OWN items only, for sitting députés and sénateurs.

    from src import fr_hatvp
    index = fr_hatvp.parse_index(csv_text)                 # liste.csv
    decls = fr_hatvp.parse_declarations(stream)            # declarations.xml, streamed
    rows, stats = fr_hatvp.interests(decls, index, fr_hatvp.sitting(conn))
    mi.replace(conn, "fr", fr_hatvp.SOURCE, today, interests=rows, full=True)

    python3 tools/fr_hatvp.py          # the monthly step of jobs/fr-weekly.sh

A layer the member-intelligence round (#86, src/member_intel.py) left out
because the open data carries spouses' activities. It fills mi_interests
(source 'fr-hatvp'), which the member profiles already show as "Declared
interests", with two columns of its own: `declared` (the declaration's
deposit date) and `url` (the HATVP's page for the member).

THE SOURCE (probed 11 October 2026). The Haute Autorité pour la transparence
de la vie publique publishes, on https://www.hatvp.fr/open-data/:
  * liste.csv (3.2 MB): every published declaration, one row each, with the
    declarant's name, mandate type ('depute', 'senateur', ...), deposit date,
    the HATVP page (url_dossier) and `id_origine`, the parliament's own id
    (the Assemblée's acteur number without its 'PA', the Sénat's matricule);
  * declarations.xml (79.5 MB): the content of every declaration published in
    open data, one <declaration> each, keyed by name and mandate (no
    parliament id; the CSV supplies it).
Reuse terms: the 11 October 2013 transparency laws make the published
declarations "librement réutilisables"; the files are published under the
Licence Ouverte (Etalab), reuse with attribution ("Source: HATVP"). robots.txt
(11 October 2026) disallows only /wordpress/wp-admin/. Both files answer a
conditional request (If-Modified-Since: 304 when unchanged); they were last
regenerated on 2 October 2026.

WHAT IS KEPT. Of each sitting member's LATEST declaration for the mandate
they hold (a modificative declaration repeats every item, so the latest is
the whole current picture), the declarant's own items in six sections:

  activProfCinqDerniereDto     professional activities, the last five years
  activConsultantDto           consultancy
  participationDirigeantDto    management roles (boards of companies,
                               associations, public bodies)
  participationFinanciereDto   shareholdings (the share of capital or the
                               number of shares; never the valuation)
  fonctionBenevoleDto          voluntary and association roles
  mandatElectifDto             elective mandates

Each item becomes one row: the organisation (or mandate) as `text`, the
activity as `role`, the period, and "rémunéré" / "non rémunéré" from the
declared amounts (the amounts themselves are not stored). Free-text comments
are not read.

WHAT IS NEVER READ. Spouses' and partners' activities (activProfConjointDto),
the parliamentary collaborators' activities (activCollaborateursDto), the
free-text observations (observationInteretDto, which can name third parties)
and every asset section (patrimoine: property, accounts, vehicles, debts).
They are cleared at parse time, as each section closes, before the
declaration is read; nothing of them is stored, shown, logged or archived.
For the same reason the XML itself is NEVER written to data/raw (the raw
archive is published): its provenance is its URL and Last-Modified, kept in
mi_downloads. Only the CSV's parliamentary rows are archived (declarants'
names, mandates, dates and links; no third party). tests/test_fr_hatvp.py
proves a spouse's data in the fixture never reaches the store or the log.

MATCHING. A declaration is matched to a stored member (fr_members, current
= 1) by the HATVP's own id for the parliament: the one CSV person of that
mandate whose surname and first name agree with the declaration's (narrowed
by department when two do) gives `id_origine`, 'PA' + id for a député and
the matricule for a sénateur; it is accepted only when that member sits in
the right chamber AND the store's name agrees on the surname. Without an
id, by name and mandate: exactly one sitting member of that chamber whose
surname and first name agree, else nothing. Names differ between the XML,
the CSV and the store ('Catherina' / 'Catherine', 'TACHE DE LA PAGERIE' /
'Taché', 'KBIDI' / 'K/Bidi', given names in the surname field), hence the
word-level comparison (surname_agrees, first_agrees). Measured 11 October
2026: every sitting member with a published declaration matched, each
name-only match checked by hand. Former members and other mandates are
dropped.

FLAGS. An interest whose organisation NAME matches config/member-intel-
groups.yaml (the 'fr' rules) is flagged "on our ground" in the profile, as
for every other country's interests; never a stance.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET

from src import member_intel as mi

SOURCE = "fr-hatvp"
FEED = "fr-hatvp"
XML_URL = "https://www.hatvp.fr/livraison/merge/declarations.xml"
CSV_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"
SITE = "https://www.hatvp.fr"
STALE_DAYS = 28            # checked at most every four weeks (a monthly step)
MANDATES = {"depute": "an", "senateur": "senat"}

# The register's own sections kept, with the category shown in the profile
# and the fields read: (text field, role field).
KEEP = {
    "activProfCinqDerniereDto": ("Activité professionnelle (cinq dernières années)",
                                 "employeur", "description"),
    "activConsultantDto": ("Activité de consultant", "nomEmployeur", "description"),
    "participationDirigeantDto": ("Participation à un organe dirigeant", "nomSociete",
                                  "activite"),
    "participationFinanciereDto": ("Participation financière", "nomSociete", None),
    "fonctionBenevoleDto": ("Fonction bénévole", "nomStructure", "descriptionActivite"),
    "mandatElectifDto": ("Mandat électif", "descriptionMandat", None),
}
# Sections about third parties, free text, or assets: cleared as soon as they
# close, never read. Anything not in KEEP is ignored anyway; these are named
# so the parser can drop them early and the test can check each one.
SKIP = frozenset({
    "activProfConjointDto",          # the spouse's or partner's activity
    "activCollaborateursDto",        # the parliamentary collaborators' activities
    "observationInteretDto",         # free-text observations
    "immeubleDto", "sciDto", "valeursNonEnBourseDto", "valeursEnBourseDto",
    "assuranceVieDto", "comptesBancaireDto", "bienDiverDto", "vehiculeDto", "fondDto",
    "autreBienDto", "bienEtrangerDto", "passifDto", "observationPatrimoineDto",
    "revenuMandatDto", "evenementMajeurDto",
})
REDACTED = re.compile(r"\[\s*Donn[ée]es non publi[ée]es\s*\]", re.I)
# An item that only says there is nothing to declare.
NOTHING = re.compile(r"^(neant|aucun|aucune|sans objet|non|rien|na|n a)$")


def fold(text):
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def clean(text):
    return mi.clean(REDACTED.sub(" ", str(text or "")))


# --- the CSV index -------------------------------------------------------------------

def parse_index(text):
    """{mandate: [person]} for the parliamentary rows of liste.csv, one person
    per HATVP `classement` (its own person key): {"surname", "first_name",
    "ids": {id_origine}, "url": the HATVP page, "depts": {department}}."""
    people = {}
    for r in csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"):
        mandate = (r.get("type_mandat") or "").strip()
        if mandate not in MANDATES:
            continue
        key = (mandate, (r.get("classement") or "").strip() or
               (fold(r.get("nom")), fold(r.get("prenom"))))
        e = people.setdefault(key, {"surname": clean(r.get("nom")),
                                    "first_name": clean(r.get("prenom")), "ids": set(),
                                    "url": None, "depts": set()})
        if (r.get("id_origine") or "").strip():
            e["ids"].add(r["id_origine"].strip())
        if (r.get("url_dossier") or "").strip():
            e["url"] = SITE + r["url_dossier"].strip()
        if (r.get("departement") or "").strip():
            e["depts"].add(dept(r["departement"]))
    out = {}
    for (mandate, _k), e in people.items():
        out.setdefault(mandate, []).append(e)
    return out


def dept(code):
    return (code or "").strip().lstrip("0").upper()


def parliamentary_rows(text):
    """liste.csv cut to the parliamentary rows, for the raw archive."""
    lines = text.lstrip("﻿").splitlines(True)
    keep = [ln for ln in lines[1:] if any(";{0};".format(m) in ln for m in MANDATES)]
    return "".join(lines[:1] + keep)


# --- the XML, streamed --------------------------------------------------------------

def _paid(item):
    amounts = []
    for m in item.iter("montant"):
        if len(m):                       # the <montant> wrapping year and amount
            continue
        digits = re.sub(r"[^\d]", "", m.text or "")
        if digits:
            amounts.append(int(digits))
    if not amounts:
        return None
    return "rémunéré" if any(amounts) else "non rémunéré"


def _items(section, tag):
    category, text_field, role_field = KEEP[tag]
    out = []
    for it in section.findall("items/items"):
        if ((it.findtext("motif/id") or "").strip().upper()) == "SUPPRESSION":
            continue
        text = clean(it.findtext(text_field))
        if not text or NOTHING.match(fold(text)):
            continue
        if tag == "participationFinanciereDto":
            cap, parts = clean(it.findtext("capitalDetenu")), clean(it.findtext("nombreParts"))
            role = ("{0} % du capital".format(cap) if cap and cap != "0" else
                    "{0} part(s)".format(parts) if parts and parts != "0" else None)
        else:
            role = clean(it.findtext(role_field)) if role_field else None
        out.append({"category": category, "text": text, "role": role or None,
                    "paid": _paid(it), "start": clean(it.findtext("dateDebut")) or None,
                    "end": clean(it.findtext("dateFin")) or None})
    return out


def parse_declarations(stream):
    """Yield one dict per declaration by a député or sénateur: {surname,
    first_name, mandate, deposited ('YYYY-MM-DD HH:MM:SS'), items}. Every
    SKIP section is cleared the moment it closes; other mandates are cleared
    unread."""
    for event, el in ET.iterparse(stream, events=("end",)):
        if el.tag in SKIP:
            el.clear()
            continue
        if el.tag != "declaration":
            continue
        g = el.find("general")
        mandate = (g.findtext("qualiteMandat/codTypeMandatFichier") or "").strip() \
            if g is not None else ""
        if mandate in MANDATES:
            dep = (el.findtext("dateDepot") or "").strip()
            m = re.match(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\S+))?", dep)
            items = []
            for tag in KEEP:
                sec = el.find(tag)
                if sec is not None:
                    items += _items(sec, tag)
            yield {"surname": clean(g.findtext("declarant/nom")),
                   "first_name": clean(g.findtext("declarant/prenom")),
                   "mandate": mandate,
                   "deposited": "{2}-{1}-{0} {3}".format(*m.groups()).strip() if m else "",
                   "dept": dept(g.findtext("organe/codeOrgane")),
                   "items": items}
        el.clear()


# --- matching ------------------------------------------------------------------------

def sitting(conn):
    """{acteur_ref: (chamber, name)} for the sitting members in fr_members."""
    try:
        return {r[0]: (r[1], r[2] or "") for r in conn.execute(
            "SELECT acteur_ref, chamber, name FROM fr_members WHERE current = 1")}
    except sqlite3.Error:
        return {}


PARTICLES = frozenset({"de", "du", "des", "la", "le", "d", "l", "y", "van", "von"})


def _tokens(text):
    return {t for t in fold(text).split() if len(t) > 1 and t not in PARTICLES}


def surname_agrees(surname, name):
    """The declared surname and a printed name share a surname word ('TACHE DE LA
    PAGERIE' and 'Emmanuel Taché', 'Charret-Godard' and 'Océane Godard'), or
    agree once spaces and slashes go ('KBIDI' and 'Émeline K/Bidi')."""
    s, n = _tokens(surname), _tokens(name)
    if s & n:
        return True
    joined = fold(surname).replace(" ", "")
    return bool(joined) and joined in fold(name).replace(" ", "")


def first_agrees(first, other):
    """First names agree on their first four letters ('Liliane' / 'Liliana',
    'Marie-Dominique' / 'Marie-Do'), or one first name is among the other's
    ('Amal Amélia' / 'Amélia', 'MAX FRANCOIS' / 'Max')."""
    a, b = fold(first).split(), fold(other).split()
    if not a or not b:
        return False
    if set(a) & set(b):
        return True
    a, b = "".join(a), "".join(b)
    n = min(4, len(a), len(b))
    return a[:n] == b[:n]


def _first_of(name, surname):
    """The first-name part of a printed name, once the surname's words go."""
    drop = _tokens(surname)
    return " ".join(t for t in fold(name).split() if t not in drop) or fold(name)


def _store_key(ref, chamber):
    return ref if chamber == "senat" else "PA" + (ref[2:] if ref.startswith("PA") else ref)


def match(decl, index, members):
    """(member key, 'id' | 'name', HATVP page or None), or None.

    By the HATVP's id: the one CSV person of this mandate whose surname and
    first name agree (narrowed by department when two do; or the only one
    with that surname, whatever the first name) gives `id_origine`;
    accepted only when that member sits in the right chamber and the store's
    name agrees on the surname. Else by name and mandate: exactly one sitting
    member of that chamber whose surname and first name agree."""
    chamber = MANDATES[decl["mandate"]]
    same = [p for p in index.get(decl["mandate"], ())
            if surname_agrees(decl["surname"], p["surname"])]
    people = [p for p in same if first_agrees(decl["first_name"], p["first_name"])]
    if not people and len(same) == 1:   # 'Jean-Michel PAHUN' is the CSV's 'Jimmy'
        people = same
    if len(people) > 1 and decl.get("dept"):
        people = [p for p in people if decl["dept"] in p["depts"]] or people
    url = people[0]["url"] if len(people) == 1 else None
    if len(people) == 1 and len(people[0]["ids"]) == 1:
        key = _store_key(next(iter(people[0]["ids"])), chamber)
        got = members.get(key)
        if got and got[0] == chamber and surname_agrees(decl["surname"], got[1]):
            return key, "id", url
    cands = [k for k, (ch, name) in members.items()
             if ch == chamber and surname_agrees(decl["surname"], name)
             and first_agrees(decl["first_name"], _first_of(name, decl["surname"]))]
    if len(cands) == 1:
        return cands[0], "name", url
    return None


def interests(decls, index, members):
    """(mi.interest rows, stats) from each sitting member's latest declaration."""
    latest, stats = {}, {"declarations": 0, "by_id": 0, "by_name": 0, "unmatched": 0}
    for d in decls:
        stats["declarations"] += 1
        got = match(d, index, members)
        if not got:
            stats["unmatched"] += 1
            continue
        key, how, url = got
        if key not in latest or d["deposited"] > latest[key][0]["deposited"]:
            latest[key] = (d, how, url)
    rows = []
    for key, (d, how, url) in sorted(latest.items()):
        stats["by_" + how] += 1
        name = "{0} {1}".format(d["first_name"], d["surname"])
        for it in d["items"]:
            rows.append(mi.interest(member_key=key, member_ref=key, name=name,
                                    category=it["category"], text=it["text"], role=it["role"],
                                    paid=it["paid"], start=it["start"], end=it["end"],
                                    declared=d["deposited"][:10], url=url))
    stats["members"] = len(latest)
    stats["interests"] = len(rows)
    return rows, stats


# --- the download, only when changed ---------------------------------------------------

def download_row(conn):
    return mi.download_row(conn, XML_URL)


def due(conn, today, stale_days=STALE_DAYS):
    """(True/False, why): due when never checked, or last checked `stale_days` ago."""
    import datetime
    row = download_row(conn)
    if not row or not row[3]:
        return True, "never checked"
    age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(row[3])).days
    if age < stale_days:
        return False, "checked {0} day(s) ago".format(age)
    return True, "last checked {0} day(s) ago".format(age)


def record(conn, today, headers=None, fetched=False):
    mi.record_download(conn, XML_URL, today, headers=headers, fetched=fetched)


def conditional_headers(conn):
    row = download_row(conn)
    out = {}
    if row and row[4]:                   # only once a download has been parsed
        if row[0]:
            out["If-Modified-Since"] = row[0]
        if row[1]:
            out["If-None-Match"] = row[1]
    return out
