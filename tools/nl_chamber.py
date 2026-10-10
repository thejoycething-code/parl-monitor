#!/usr/bin/env python3
"""The Netherlands: what was said in the Tweede Kamer, and the questions put.

    python3 tools/nl_chamber.py                     # the last three weeks
    python3 tools/nl_chamber.py --since 2026-09-01 --budget-seconds 600
    python3 tools/nl_chamber.py --only questions    # one feed
    python3 tools/nl_chamber.py --dry-run           # fetch and count, store nothing
    python3 tools/nl_chamber.py --reclassify        # re-derive areas, offline

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. Both feeds
come from the Tweede Kamer's Open Data Portaal (gegevensmagazijn, OData v4,
keyless, the source tools/nl_rollcalls.py already reads); the rest is
src/chamber_store.py.

SPEECHES: the Handelingen. Every plenary sitting (Vergadering, Soort
'Plenair') has one or more Verslagen, each a VLOS XML document of 0.5 to
1.7 MB: provisional versions during and after the day (Tussenpublicatie,
'Ongecorrigeerd'), then the corrected Eindpublicatie. The best version is
read (Eindpublicatie first, else the newest), and read again whenever a
better or newer one appears, so a speech's words end as the corrected
record. Inside, each agenda item is an `activiteit` (its `onderwerp` is the
debate title) and each turn at the lectern a `woordvoerder` or an
`interrumpant` with its own `spreker` (name as printed, fractie, functie)
and `tekst`. The chair (`isvoorzitter` true) is never stored. Committee
debates (commissiedebatten) are not read: plenary only, to keep the weekly
budget to a few megabytes.

QUESTIONS: Kamervragen are zaken of Soort 'Schriftelijke vragen' and
'Mondelinge vragen', with the asker ('Indiener', co-signers 'Medeindiener')
and the minister asked ('Gericht aan') as ZaakActor. Classified on the
onderwerp alone; the answer is never read. A question is keyed on its
zaaknummer, so config/watchlist-nl.yaml can watch one.

Paging is by @odata.nextLink, never $skip; $top above 250 is a 400
(tools/nl_rollcalls.py).
"""

from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402

CC = "nl"
FEED = "nl-chamber"
BASE = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
QUESTION_SOORTEN = {"Schriftelijke vragen": "written", "Mondelinge vragen": "oral"}
VERSION_RANK = {"Eindpublicatie": 2, "Tussenpublicatie": 1}
MAX_PAGES = 40
# The speaker's label opening a turn, printed as its own alineaitem:
# "De heer Flach (SGP):", "Minister Heerma:". Not the speech.
LABEL = re.compile(r"^[^.!?]{1,120}:$")


def odata(path, **params):
    q = "&".join("{0}={1}".format(k, quote(str(v), safe="(),'$=/:")) for k, v in params.items())
    return BASE + path + ("?" + q if q else "")


def pages(run, url, slug):
    """Every record behind an OData query, following @odata.nextLink."""
    out, i = [], 0
    while url and i < MAX_PAGES:
        page = run.client.get_json(url, FEED, "{0}-p{1}".format(slug, i))
        out += page.get("value") or []
        url, i = page.get("@odata.nextLink"), i + 1
    return out


# --- speeches -----------------------------------------------------------------------

def best_versions(verslagen):
    """{vergadering_id: verslag}: per sitting the Eindpublicatie, else the newest."""
    best = {}
    for v in verslagen:
        vid = v.get("Vergadering_Id") or (v.get("Vergadering") or {}).get("Id")
        if not vid:
            continue
        rank = (VERSION_RANK.get(v.get("Soort"), 0), v.get("GewijzigdOp") or "")
        if vid not in best or rank > best[vid][0]:
            best[vid] = (rank, v)
    return {k: v for k, (_, v) in best.items()}


def version_of(v):
    return "{0}/{1}/{2}".format(v.get("Soort"), v.get("Status"), v.get("GewijzigdOp"))


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _child(el, name):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _text(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def parse_verslag(xml_bytes):
    """[(debate_id, debate, turn_id, speaker, fractie, functie, is_chair, text)]
    from a VLOS document, in order. Text keeps one line per alinea."""
    root = ET.fromstring(xml_bytes)
    out = []
    for act in root.iter():
        if _local(act.tag) != "activiteit":
            continue
        debate = _text(_child(act, "onderwerp")) or _text(_child(act, "titel"))
        debate_id = act.get("objectid")
        for turn in act.iter():
            if _local(turn.tag) not in ("woordvoerder", "interrumpant"):
                continue
            sp = _child(turn, "spreker")
            tekst = _child(turn, "tekst")
            if sp is None or tekst is None:
                continue
            chair = _text(_child(turn, "isvoorzitter")).lower() == "true"
            paras = []
            for al in tekst.iter():
                if _local(al.tag) != "alinea":
                    continue
                items = [_text(i) for i in al if _local(i.tag) == "alineaitem"] or [_text(al)]
                if not paras and items and LABEL.match(items[0]):
                    items = items[1:]           # "Mevrouw Van der Plas (BBB):", the label
                line = " ".join(i for i in items if i)
                if line:
                    paras.append(line)
            out.append((debate_id, debate, turn.get("objectid"),
                        _text(_child(sp, "verslagnaam")) or _text(_child(sp, "achternaam")),
                        _text(_child(sp, "fractie")) or None,
                        _text(_child(sp, "functie")) or None, chair, "\n".join(paras)))
    return out


def role_of(functie, kind="woordvoerder"):
    f = (functie or "").lower()
    if not f or "lid tweede kamer" in f or "kamerlid" in f:
        return "member"
    return functie


def speeches(run):
    url = odata("Verslag", **{
        "$filter": "Verwijderd eq false and Vergadering/Soort eq 'Plenair' and "
                   "Vergadering/Datum ge {0}T00:00:00Z".format(run.since),
        "$expand": "Vergadering($select=Id,Titel,Datum,VergaderingNummer)",
        "$select": "Id,Soort,Status,ContentLength,GewijzigdOp,Vergadering_Id",
        "$orderby": "GewijzigdOp desc", "$top": 250})
    best = best_versions(pages(run, url, "verslagen-" + run.since))
    order = sorted(best.values(), key=lambda v: (v.get("Vergadering") or {}).get("Datum") or "",
                   reverse=True)
    for n, v in enumerate(order):
        vg = v.get("Vergadering") or {}
        doc_id = "vergadering:" + vg.get("Id", v["Vergadering_Id"])
        date = (vg.get("Datum") or "")[:10]
        version = version_of(v)
        old, status = cs.read_state(run.conn, CC, doc_id)
        if old == version and status == "read":
            if not run.dry_run:
                cs.seen(run.conn, CC, doc_id, run.today)
            continue
        if run.out_of_time("plenary reports", n):
            return
        try:
            blob = run.client.get_bytes(BASE + "Verslag({0})/resource".format(v["Id"]), FEED,
                                        "verslag-{0}-{1}".format(date, v["Id"][:8]))
            turns = parse_verslag(blob)
        except (FetchError, ET.ParseError) as exc:
            run.gap("verslag {0} ({1}) unreadable: {2}".format(v["Id"], date, str(exc)[:100]))
            continue
        kept, matched, titles = [], 0, {}
        for i, (debate_id, debate, turn_id, name, fractie, functie, chair, text) in \
                enumerate(turns):
            if chair or not text:
                continue
            if debate not in titles:
                titles[debate] = cs.classify_title(run.taxes, debate)
            m = cs.classify_speech(run.taxes, text, titles[debate])
            if not m:
                continue
            sid = "{0}#{1}".format(doc_id, turn_id or i)
            kept.append(sid)
            matched += 1
            run.speech({"speech_id": sid, "doc_id": doc_id, "date": date, "chamber": None,
                        "debate_id": cs.short_id(debate or debate_id), "debate": debate, "speaker": name,
                        "party": fractie, "role": role_of(functie), "person_id": None,
                        "text": text, "url": BASE + "Verslag({0})/resource".format(v["Id"]),
                        "title_areas": titles[debate].areas}, m)
        if not run.dry_run:
            cs.forget_speeches(run.conn, CC, doc_id, kept)
        run.read(doc_id, "speeches", date, version,
                 sum(1 for t in turns if not t[6]), matched, len(blob))
        run.log("  [verslag] {0} {1} ({2}): {3} turn(s), {4} on our ground".format(
            date, vg.get("Titel") or "", v.get("Soort"), len(turns), matched))


# --- questions ----------------------------------------------------------------------

def actors(z, *relaties):
    return [a for a in z.get("ZaakActor") or [] if a.get("Relatie") in relaties]


def parse_question(z):
    askers = actors(z, "Indiener") + actors(z, "Medeindiener")
    asked = actors(z, "Gericht aan")
    lead = askers[0] if askers else {}
    asker = lead.get("ActorNaam")
    if len(askers) > 1:
        asker = "{0} and {1} other(s)".format(asker, len(askers) - 1)
    return {"question_id": z["Nummer"], "kind": QUESTION_SOORTEN.get(z.get("Soort"), "written"),
            "date": (z.get("GestartOp") or "")[:10],
            "title": z.get("Onderwerp") or z.get("Titel") or "", "text": z.get("Titel"),
            "asker": asker, "party": lead.get("ActorFractie"),
            "addressee": "; ".join(a.get("Functie") or a.get("ActorNaam") or "" for a in asked)
            or None,
            "answered": "yes" if z.get("Afgedaan") else None,
            "url": "https://www.tweedekamer.nl/kamerstukken/kamervragen/detail?id={0}".format(
                z["Nummer"])}


def questions(run):
    soorten = " or ".join("Soort eq '{0}'".format(s) for s in QUESTION_SOORTEN)
    url = odata("Zaak", **{
        "$filter": "Verwijderd eq false and ({0}) and GestartOp ge {1}T00:00:00Z".format(
            soorten, run.since),
        "$expand": "ZaakActor($select=ActorNaam,ActorFractie,Relatie,Functie)",
        "$select": "Id,Nummer,Soort,Onderwerp,Titel,GestartOp,Afgedaan",
        "$orderby": "GestartOp desc", "$top": 250})
    try:
        zaken = pages(run, url, "vragen-" + run.since)
    except FetchError as exc:
        run.gap("questions since {0} unreadable: {1}".format(run.since, str(exc)[:100]))
        return
    matched = 0
    for z in zaken:
        if not z.get("Nummer"):
            continue
        q = parse_question(z)
        m = cs.classify_question(run.taxes, q["title"], q["text"])
        if not m:
            continue
        matched += 1
        run.question(q, m)
    run.read("vragen:{0}:{1}".format(run.since, run.today), "questions", run.today, None,
             len(zaken), matched, 0)
    run.log("  [vragen] {0} question(s) tabled since {1}, {2} on our ground".format(
        len(zaken), run.since, matched))


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"speeches": speeches, "questions": questions}, doc=__doc__))
