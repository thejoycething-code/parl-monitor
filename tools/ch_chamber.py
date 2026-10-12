#!/usr/bin/env python3
"""Switzerland: what was said in the Nationalrat and the Ständerat.

    python3 tools/ch_chamber.py                     # the last three weeks
    python3 tools/ch_chamber.py --since 2026-09-07  # the Herbstsession
    python3 tools/ch_chamber.py --dry-run
    python3 tools/ch_chamber.py --reclassify

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. The
Amtliches Bulletin, speech by speech, from the Federal Assembly's OData
service (ws.parlament.ch, keyless; tools/ch_rollcalls.py reads the same
service): entity `Transcript`, one row per speech, 4,336 in the Herbstsession
2026 (docs/switzerland-scope.md). The rest is src/chamber_store.py.

QUESTIONS are not collected here: the Swiss edition already carries the
Vorstösse (interpellations, Fragestunde questions, Anfragen) from
ch_businesses (src/editions/ch.py), so a second copy would double them.

THE SHAPE. Each speech is stored once per language (DE, FR, IT) with the
SAME original text; only Language='DE' is read, so each speech is read once,
in the language it was given (LanguageOfText; French and Italian speeches
are classified with taxonomy-fr and taxonomy-atch together, as the edition's
taxonomies say). Type 1 is a speech, Type 2 a vote record (the tallies are
ch_divisions'); only Type 1 is read. SpeakerFunction says who spoke: 'Mit-M'
and 'Mit-F' members, 'BR-M' / 'BR-F' a Federal Councillor, 'P-*' and
'*VP-*' the chair, which is never stored. IdSubject is the debate: its
business number and title come from SubjectBusiness, asked for in batches.

INCREMENTAL. A cheap listing (no Text) of every speech since --since gives
each sitting day's and council's newest `Modified`; a day is read whole,
with its texts, only when it was never read or has changed since. The
Federal Assembly sits in four three-week sessions a year (and a special
session), so most weeks this reads nothing and says so.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402

CC = "ch"
FEED = "ch-chamber"
ODATA = "https://ws.parlament.ch/odata.svc/"
COUNCILS = {"N": "Nationalrat", "S": "Ständerat", "V": "Vereinigte Bundesversammlung"}
PAGE = 1000
SUBJECT_BATCH = 20
BULLETIN = ("https://www.parlament.ch/de/ratsbetrieb/amtliches-bulletin/"
            "amtliches-bulletin-die-verhandlungen?SubjectId={0}")
LIST_FIELDS = "ID,IdSubject,MeetingDate,MeetingCouncilAbbreviation,Type,Modified"
TEXT_FIELDS = ("ID,IdSubject,MeetingDate,MeetingCouncilAbbreviation,Type,SpeakerFullName,"
               "SpeakerFunction,ParlGroupAbbreviation,CantonAbbreviation,PersonNumber,"
               "LanguageOfText,SortOrder,Text")


def url(entity, flt, select, top=PAGE, orderby="ID"):
    return "{0}{1}?$filter={2}&$select={3}&$orderby={4}&$top={5}&$format=json".format(
        ODATA, entity, quote(flt, safe="'()"), select, orderby, top)


def rows(run, first, slug):
    """Every row behind a query: $top pages walked with $skip (the service
    gives no __next link once $top is set), and any __next it does give."""
    out, i = [], 0
    while i < 50:
        page = first + "&$skip={0}".format(i * PAGE) if i else first
        d = run.client.get_json(page, FEED, "{0}-p{1}".format(slug, i)).get("d") or {}
        got = d.get("results") if isinstance(d, dict) else d
        out += got or []
        i += 1
        if not got or len(got) < PAGE:
            break
    return out


def ms(value):
    """'/Date(1790929011388)/' -> 1790929011388 (for comparing versions)."""
    m = re.search(r"\d+", value or "")
    return int(m.group(0)) if m else 0


def iso(yyyymmdd):
    s = str(yyyymmdd or "")
    return "{0}-{1}-{2}".format(s[:4], s[4:6], s[6:8]) if len(s) == 8 else s


LABEL = re.compile(r"^\s*(?:<pd_text>)?\s*<p>\s*<b>[^<]*</b>\s*(?:\([^)]*\))?\s*:?\s*", re.S)
MARKERS = re.compile(r"\[(?:GZ|VS|NAM|NB)\]")


def speech_text(html):
    """The speech without its speaker label and the Bulletin's layout marks."""
    return cs.html_text(MARKERS.sub("", LABEL.sub("<p>", html or "", count=1)))


FR_WORDS = re.compile(r"\b(?:le|la|les|des|est|nous|vous|une|pour)\b")
DE_WORDS = re.compile(r"\b(?:der|die|das|und|ist|wir|Sie|nicht|eine)\b")
IT_WORDS = re.compile(r"\b(?:il|che|della|sono|non|per|gli)\b")


def language(declared, text):
    """The speech's language, read off its commonest function words.
    LanguageOfText is empty for about a third of speeches (measured on 22
    September 2026: 80 of 258) and sometimes names the speaker's language
    rather than the text's (a Federal Councillor from Jura reading German),
    so it only breaks a tie."""
    counts = sorted([(len(DE_WORDS.findall(text)), "DE"), (len(FR_WORDS.findall(text)), "FR"),
                     (len(IT_WORDS.findall(text)), "IT")], reverse=True)
    if counts[0][0] and counts[0][0] > counts[1][0]:
        return counts[0][1]
    return declared if declared in ("DE", "FR", "IT") else "DE"


def taxes_for(by_file, lang):
    """Each speech is read with the list of its own language: 'IVG' is an
    abortion term in French and the disability-insurance law in German
    (measured: ten speeches on the 26.029 inclusion bill, 21 September 2026,
    filed under abortion when both lists read every speech). Italian
    speeches get both lists until Swiss Italian terms exist (CH6)."""
    de, fr = by_file.get("taxonomy-atch.yaml"), by_file.get("taxonomy-fr.yaml")
    if lang == "DE" and de:
        return [de]
    if lang == "FR" and fr:
        return [fr]
    return list(by_file.values())


# 'IVG' in a Swiss speech is the disability-insurance law (Bundesgesetz über
# die Invalidenversicherung) far more often than an abortion: "Artikel
# 42quinquies IVG", "im BehiG, im IVG", in German and in French (measured on
# the 26.029 inclusion bill, 21 September 2026). In a paragraph that does not
# also speak of pregnancy or abortion it is masked before matching, as
# tools/fr_rollcalls.py masks its false friends; the list itself is untouched.
IVG = re.compile(r"\bIVG\b")
ABORTION_CONTEXT = re.compile(r"(?i)avort|grossesse|schwanger|abtreib|abbruch|interruzione")


def mask(text):
    return "\n".join(p if ABORTION_CONTEXT.search(p) else IVG.sub("Invalidenversicherungsgesetz", p)
                     for p in (text or "").split("\n"))


def is_chair(function):
    f = (function or "").upper()
    return f.startswith("P-") or "VP-" in f


def role_of(function):
    f = (function or "").upper()
    if f.startswith("BR-"):
        return "Federal Councillor"
    if f.startswith("MIT-") or not f:
        return "member"
    return function


def subject_titles(run, ids):
    """{IdSubject: 'business number: title'}, asked for in batches."""
    out, ids = {}, sorted(set(i for i in ids if i))
    for n in range(0, len(ids), SUBJECT_BATCH):
        chunk = ids[n:n + SUBJECT_BATCH]
        flt = "Language eq 'DE' and ({0})".format(
            " or ".join("IdSubject eq {0}L".format(i) for i in chunk))
        try:
            got = rows(run, url("SubjectBusiness", flt, "IdSubject,BusinessShortNumber,Title,"
                                "SortOrder", orderby="IdSubject"),
                       "subjects-{0}-{1}".format(chunk[0], len(chunk)))
        except FetchError as exc:
            run.gap("subject titles unreadable: {0}".format(str(exc)[:100]))
            continue
        for r in sorted(got, key=lambda r: r.get("SortOrder") or 0):
            sid = str(r.get("IdSubject"))
            if sid not in out:
                out[sid] = "{0}: {1}".format(r.get("BusinessShortNumber"),
                                             " ".join((r.get("Title") or "").split()))
    return out


def speeches(run):
    by_file = cs.load_taxonomies(CC, by_file=True)
    since = run.since.replace("-", "")
    listing = rows(run, url("Transcript", "Language eq 'DE' and Type eq 1 and MeetingDate gt "
                            "'{0}'".format(since), LIST_FIELDS),
                   "transcripts-{0}".format(since))
    days = {}
    for r in listing:
        k = (r["MeetingDate"], r["MeetingCouncilAbbreviation"] or "")
        days[k] = max(days.get(k, 0), ms(r.get("Modified")))
    run.log("  [bulletin] {0} speech(es) listed since {1}, {2} sitting day(s)".format(
        len(listing), run.since, len(days)))
    for n, ((day, council), modified) in enumerate(sorted(days.items(), reverse=True)):
        doc_id = "{0}-{1}".format(council, day)
        version = str(modified)
        old, status = cs.read_state(run.conn, CC, doc_id)
        if old == version and status == "read":
            if not run.dry_run:
                cs.seen(run.conn, CC, doc_id, run.today)
            continue
        if run.out_of_time("sitting days", n):
            return
        try:
            got = rows(run, url("Transcript", "Language eq 'DE' and Type eq 1 and MeetingDate eq "
                                "'{0}' and MeetingCouncilAbbreviation eq '{1}'".format(
                                    day, council), TEXT_FIELDS),
                       "day-{0}".format(doc_id))
        except FetchError as exc:
            run.gap("Bulletin {0} unreadable: {1}".format(doc_id, str(exc)[:100]))
            continue
        titles = subject_titles(run, [str(r.get("IdSubject")) for r in got])
        title_match, kept, matched, chars, turns = {}, [], 0, 0, 0
        for r in sorted(got, key=lambda r: (int(r.get("SortOrder") or 0), int(r["ID"]))):
            text = speech_text(r.get("Text"))
            chars += len(text)
            if is_chair(r.get("SpeakerFunction")) or not text:
                continue
            turns += 1
            subj = str(r.get("IdSubject"))
            debate = titles.get(subj)
            if subj not in title_match:
                # Titles are the German ones (SubjectBusiness, Language 'DE').
                title_match[subj] = cs.classify_title(taxes_for(by_file, "DE"), debate)
            lang = language(r.get("LanguageOfText"), text)
            m = cs.classify_speech(taxes_for(by_file, lang), mask(text), title_match[subj])
            if not m:
                continue
            sid = "transcript:{0}".format(r["ID"])
            kept.append(sid)
            matched += 1
            run.speech({"speech_id": sid, "doc_id": doc_id, "date": iso(day),
                        "chamber": COUNCILS.get(council, council),
                        "debate_id": cs.short_id(debate or subj),
                        "debate": debate, "speaker": r.get("SpeakerFullName"),
                        "party": "/".join(p for p in (r.get("ParlGroupAbbreviation"),
                                                      r.get("CantonAbbreviation")) if p) or None,
                        "role": role_of(r.get("SpeakerFunction")),
                        "person_id": str(r["PersonNumber"]) if r.get("PersonNumber") else None,
                        "text": text, "url": BULLETIN.format(subj),
                        "title_areas": title_match[subj].areas}, m)
        if not run.dry_run:
            cs.forget_speeches(run.conn, CC, doc_id, kept)
        run.read(doc_id, "speeches", iso(day), version, turns, matched, chars)
        run.log("  [bulletin] {0} {1}: {2} speech(es), {3} on our ground".format(
            COUNCILS.get(council, council), iso(day), turns, matched))


_BY_FILE = {}


def route(text):
    """How --reclassify reads a stored speech: as speeches() does."""
    if not _BY_FILE:
        _BY_FILE.update(cs.load_taxonomies(CC, by_file=True))
    return taxes_for(_BY_FILE, language(None, text)), mask(text)


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"speeches": speeches}, doc=__doc__, route=route))
