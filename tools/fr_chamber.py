#!/usr/bin/env python3
"""France: what was said in the Assemblée nationale, and the questions put.

    python3 tools/fr_chamber.py                      # the last three weeks
    python3 tools/fr_chamber.py --since 2026-09-01 --budget-seconds 600
    python3 tools/fr_chamber.py --only questions
    python3 tools/fr_chamber.py --dry-run
    python3 tools/fr_chamber.py --reclassify

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. From the
Assemblée's open data (Licence Ouverte, robots.txt allows everything; the
host tools/fr_rollcalls.py reads); the rest is src/chamber_store.py.

SPEECHES: the compte rendu intégral, one XML document per sitting, fetched by
its uid from /dyn/opendata/<uid>.xml (0.5 to 0.9 MB): CRSANR5L17S2027O1N012
is the 12th sitting of the ordinary session 2026-2027 (O1, October to June;
E1, E2 the extraordinary sessions of July and September). Numbers run on
without gaps, so each run walks a session from the last sitting read until
the next number is not there (404). A session never read is entered by a
binary search on the sitting date, so the first run does not read July to
reach September. Inside, each `paragraphe` carries its speaker (`orateur`:
name, quality, `id_acteur`); consecutive paragraphs by one speaker are one
speech, the presiding officer's are never stored, and the debate is the
title of the enclosing top-level `point`. The speaker's group comes from
fr_members / fr_groups (the French weekly's roster) when it holds them.
The whole-legislature Syceron dump (57 MB) is not used.

QUESTIONS: questions écrites (QE, Questions_ecrites.json.zip, 49 MB, about
800 a month) and questions au gouvernement (QG, 5.4 MB), the nightly dumps
of the whole legislature, read whole once a week. A question is classified
on the Assemblée's own index of it (rubrique, tête d'analyse, analyse),
never its full text: the index is the subject, the text cites much else.
The minister asked is `minInt`; the asker's name is the text's own opening
("Mme Mathilde Hignet appelle l'attention de ..."), the group `auteur.groupe`.
A published answer is recorded by its date in the Journal officiel; its text
is never read.

RAW ARCHIVE. The sitting documents are archived. The two question dumps are
NOT (55 MB a week of a file rebuilt nightly and re-fetchable at the same
URL; the store keeps every question on our ground), as tools/ie_questions.py
does not archive its weeks.
"""

from __future__ import annotations

import datetime
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402

CC = "fr"
FEED = "fr-chamber"
LEG = 17
OPENDATA = "https://www.assemblee-nationale.fr/dyn/opendata/{0}.xml"
DUMPS = "https://data.assemblee-nationale.fr/static/openData/repository/{0}/questions/".format(LEG)
QUESTION_DUMPS = (("written", DUMPS + "questions_ecrites/Questions_ecrites.json.zip"),
                  ("government", DUMPS + "questions_gouvernement/Questions_gouvernement.json.zip"))
QUESTION_PAGE = "https://questions.assemblee-nationale.fr/q{0}/{0}-{1}{2}.htm"
CHAIR = re.compile(r"^(?:M\. le président|Mme la présidente)\b", re.I)
MAX_WALK = 60


# --- sessions and sittings -----------------------------------------------------------

def sessions_for(since, today):
    """Session codes that can hold sittings between since and today:
    'S2027O1' (October 2026 to June 2027), 'S2026E1', 'S2026E2'."""
    out = []
    d = datetime.date.fromisoformat(since)
    end = datetime.date.fromisoformat(today)
    while d <= end:
        if d.month >= 10:
            codes = ["S{0}O1".format(d.year + 1)]
        elif d.month <= 6:
            codes = ["S{0}O1".format(d.year)]
        else:
            codes = ["S{0}E1".format(d.year), "S{0}E2".format(d.year)]
        for c in codes:
            if c not in out:
                out.append(c)
        d = (d.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    return out


def uid(session, n):
    return "CRSANR5L{0}{1}N{2:03d}".format(LEG, session, n)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _first(el, name):
    for e in el.iter():
        if _local(e.tag) == name:
            return e
    return None


def sitting_date(root):
    d = _first(root, "dateSeance")
    t = (d.text or "") if d is not None else ""
    return "{0}-{1}-{2}".format(t[:4], t[4:6], t[6:8]) if len(t) >= 8 else None


def _text(el):
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def parse_sitting(xml_bytes):
    """(date, [(debate, actor, name, quality, text)]): one entry per speech,
    consecutive paragraphs by one speaker joined; the chair's left out.

    The points of the agenda are SIBLINGS, not nested (measured on the
    2026-2027 session): a level-1 point opens a debate ("Questions au
    gouvernement", a bill's title) and the level-2 points after it are its
    parts ("Discussion générale", "Article 3"), or, under questions, each
    question ("Mobilisation lycéenne"), which is then the debate's own title."""
    root = ET.fromstring(xml_bytes)
    date = sitting_date(root)
    contenu = _first(root, "contenu")
    out, current = [], None
    level1 = level2 = None

    def title_of(point):
        return _text(next((c for c in point if _local(c.tag) == "texte"), None)) or None

    def debate_now():
        if level1 and level2 and level1.lower().startswith("questions"):
            return "{0}: {1}".format(level1, level2)
        return level1

    for block in (contenu if contenu is not None else []):
        if _local(block.tag) == "point":
            if block.get("nivpoint") == "1":
                level1, level2 = title_of(block) or level1, None
            else:
                level2 = title_of(block) or level2
        debate = debate_now()
        for child in block.iter():
            if _local(child.tag) != "paragraphe":
                continue
            orateur = _first(child, "orateur")
            name = _text(_first(orateur, "nom")) if orateur is not None else ""
            quality = _text(_first(orateur, "qualite")) if orateur is not None else ""
            actor = child.get("id_acteur") or ""
            texte = next((c for c in child if _local(c.tag) == "texte"), None)
            words = _text(texte)
            if not words:
                continue
            if current and current[1] == actor and current[0] == debate and actor:
                current[4].append(words)
                continue
            current = [debate, actor, name, quality, [words]]
            out.append(current)
    speeches = [(d, a, n, q, "\n".join(ws)) for d, a, n, q, ws in out
                if n and not CHAIR.match(n)]
    return date, speeches


SUFFIX = re.compile(r"\s*\(([^)]{1,20})\)$")


def split_name(name):
    """'Mme Sandrine Josso (Dem)' -> ('Mme Sandrine Josso', 'Dem'): the
    compte rendu prints a speaker's group after the name on first mention."""
    m = SUFFIX.search(name or "")
    return (name[:m.start()], m.group(1)) if m else (name, None)


def groups(conn):
    """{acteur_ref: group abbreviation} from the French weekly's roster."""
    try:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT m.acteur_ref, COALESCE(g.abbr, m.group_ref) FROM fr_members m "
            "LEFT JOIN fr_groups g ON g.organe_ref = m.group_ref")}
    except Exception:                               # noqa: BLE001
        try:
            return {r[0]: r[1] for r in conn.execute("SELECT acteur_ref, group_ref FROM fr_members")}
        except Exception:                           # noqa: BLE001
            return {}


def fetch(run, session, n):
    """The sitting's XML, or None when it is not (yet) there."""
    try:
        return run.client.get_bytes(OPENDATA.format(uid(session, n)), FEED,
                                    "cr-{0}".format(uid(session, n)))
    except FetchError as exc:
        if cs.not_found(exc):
            return None
        raise


def first_after(run, session):
    """The first sitting number dated after --since in a session never read:
    a binary search on the sitting date, so a first run does not read the
    whole session to reach its window. 1 when the session starts after."""
    lo, hi, top = 1, 1, None
    while hi < 512:
        blob = fetch(run, session, hi)
        if blob is None:
            top = hi
            break
        if (sitting_date(ET.fromstring(blob)) or "") > run.since:
            top = hi
            break
        lo, hi = hi, hi * 2
    if top is None:
        return hi
    while lo < top:
        mid = (lo + top) // 2
        blob = fetch(run, session, mid)
        if blob is not None and (sitting_date(ET.fromstring(blob)) or "") <= run.since:
            lo = mid + 1
        else:
            top = mid
    return lo


def speeches(run):
    roster = groups(run.conn)
    for session in sessions_for(run.since, run.today):
        prefix = "CRSANR5L{0}{1}N".format(LEG, session)
        row = run.conn.execute("SELECT MAX(doc_id) FROM fr_record_reads WHERE doc_id LIKE ? "
                               "AND status='read'", (prefix + "%",)).fetchone()
        n = int(row[0][len(prefix):]) + 1 if row and row[0] else first_after(run, session)
        misses = 0
        for _ in range(MAX_WALK):
            if run.out_of_time("sittings", run.docs):
                return
            try:
                blob = fetch(run, session, n)
            except FetchError as exc:
                run.gap("compte rendu {0}: {1}".format(uid(session, n), str(exc)[:100]))
                break
            if blob is None:
                misses += 1
                if misses >= 2:
                    break
                n += 1
                continue
            misses = 0
            doc_id = uid(session, n)
            try:
                date, items = parse_sitting(blob)
            except ET.ParseError as exc:
                run.gap("compte rendu {0} unreadable: {1}".format(doc_id, exc))
                n += 1
                continue
            titles, kept, matched = {}, [], 0
            for i, (debate, actor, name, quality, text) in enumerate(items):
                if debate not in titles:
                    titles[debate] = cs.classify_title(run.taxes, debate)
                m = cs.classify_speech(run.taxes, text, titles[debate])
                if not m:
                    continue
                sid = "{0}#{1}".format(doc_id, i)
                kept.append(sid)
                matched += 1
                run.speech({"speech_id": sid, "doc_id": doc_id, "date": date,
                            "debate_id": cs.short_id(debate or doc_id), "debate": debate,
                            "speaker": split_name(name)[0],
                            "party": roster.get(actor) or split_name(name)[1],
                            "role": quality or "member", "person_id": actor or None,
                            "text": text, "url": OPENDATA.format(doc_id),
                            "title_areas": titles[debate].areas}, m)
            if not run.dry_run:
                cs.forget_speeches(run.conn, CC, doc_id, kept)
            run.read(doc_id, "speeches", date, None, len(items), matched, len(blob))
            run.log("  [compte rendu] {0} {1}: {2} speech(es), {3} on our ground".format(
                doc_id, date, len(items), matched))
            n += 1


# --- questions -----------------------------------------------------------------------

ASKER = re.compile(r"^\s*((?:M\.|Mme)\s+[^,]{2,60}?)\s+(?:appelle|attire|interroge|demande|"
                   r"alerte|souhaite|sollicite|rappelle|signale|expose|questionne|porte)\b")


def _one(x):
    return x[0] if isinstance(x, list) and x else x


def parse_question(q, kind):
    num = (q.get("identifiant") or {}).get("numero")
    idx = q.get("indexationAN") or {}
    analyses = (idx.get("analyses") or {}).get("analyse")
    analyse = "; ".join(analyses) if isinstance(analyses, list) else (analyses or "")
    tq = _one((q.get("textesQuestion") or {}).get("texteQuestion")) or {}
    date = ((tq.get("infoJO") or {}).get("dateJO")
            or ((_one((q.get("minAttribs") or {}).get("minAttrib")) or {}).get("infoJO") or {})
            .get("dateJO") or "")[:10]
    text = re.sub(r"<[^>]+>", " ", tq.get("texte") or "")
    m = ASKER.match(text)
    rep = _one((q.get("textesReponse") or {}).get("texteReponse")) or {}
    answered = ((rep.get("infoJO") or {}).get("dateJO") or "")[:10] or None
    group = ((q.get("auteur") or {}).get("groupe") or {}).get("abrege")
    code = q.get("type") or ("QE" if kind == "written" else "QG")
    return {"question_id": "{0} {1}".format(code, num), "kind": kind, "date": date,
            "title": analyse or idx.get("rubrique") or "",
            "text": "; ".join(t for t in (idx.get("rubrique"), idx.get("teteAnalyse")) if t),
            "asker": " ".join(m.group(1).split()) if m else None, "party": group,
            "addressee": (q.get("minInt") or {}).get("developpe"),
            "answered": answered if kind == "written" else "untracked",
            "url": QUESTION_PAGE.format(LEG, num, code)}


def questions(run):
    for kind, url in QUESTION_DUMPS:
        if run.out_of_time("question dumps", run.questions):
            return
        try:
            blob = run.client.get_bytes(url, FEED, "questions-" + kind, archive=False,
                                        timeout=180)
            zf = zipfile.ZipFile(io.BytesIO(blob))
        except (FetchError, zipfile.BadZipFile) as exc:
            run.gap("{0} questions dump unreadable: {1}".format(kind, str(exc)[:100]))
            continue
        listed = matched = 0
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            try:
                q = parse_question(json.loads(zf.read(name))["question"], kind)
            except (KeyError, ValueError, TypeError):
                continue
            if not q["date"] or q["date"] <= run.since:
                continue
            listed += 1
            m = cs.classify_question(run.taxes, q["title"], q["text"])
            if not m:
                continue
            matched += 1
            run.question(q, m)
        run.read("{0}:{1}:{2}".format(kind, run.since, run.today), "questions", run.today,
                 None, listed, matched, len(blob))
        run.log("  [questions {0}] {1} published since {2}, {3} on our ground".format(
            kind, listed, run.since, matched))


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"speeches": speeches, "questions": questions}, doc=__doc__))
