#!/usr/bin/env python3
"""Austria: what was said in the Nationalrat and the Bundesrat.

    python3 tools/at_chamber.py                      # the last three weeks
    python3 tools/at_chamber.py --since 2026-09-01 --budget-seconds 600
    python3 tools/at_chamber.py --dry-run
    python3 tools/at_chamber.py --reclassify

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. From the
Parliament's own site (www.parlament.gv.at, keyless, the host
tools/at_rollcalls.py reads); the rest is src/chamber_store.py.

QUESTIONS are not collected here: the Austrian edition already carries the
written questions (J) and answers (AB) from at_items (src/editions/at.py).

THE SOURCE, measured 10 October 2026. The full Stenographisches Protokoll of
a sitting is published months later (none since July 2025 had one), but each
sitting's history page (/gegenstand/<GP>/NRSITZ/<n>?json=TRUE, 75 KB) lists
every debate contribution ("Wortmeldungen in der Debatte": name, club,
Pro/Contra/tatsächliche Berichtigung/Regierungsbank) with a link to that
speech alone in the provisional protocol (/dokument/.../A_-_12_05_21_....html,
about 26 KB, "noch nicht autorisiert"). The sittings come from the protocol
list (/Filter/api/filter/data/211), Nationalrat and Bundesrat together. So a
sitting costs one page plus one request per speech: 100 to 200 for a full
Nationalrat day. The chair is not in the list.

BUDGET. Speeches are read newest sitting first and the run stops at its time
budget; a sitting left part-read is marked 'partial' and its remaining
speeches are read next run (each speech file read is remembered in
at_record_reads, feed 'speech-file', so nothing is fetched twice). The
first run, from 1 September 2026, takes two or three runs to drain.

THE TEXT. The file holds the speech with its opening label ("Abgeordneter
Herbert Kickl (FPÖ):"), the minutes it began and ended, the chair's
interventions and the House's interjections in brackets ("(Beifall bei der
FPÖ. - Ruf bei der ÖVP: Ja, ja!)"). The label and the times are cut; the
interjections are cut too, before matching, because they are other members'
words: a "Ruf: Abtreibung!" from the benches is not the speaker's ground.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402

CC = "at"
FEED = "at-chamber"
BASE = "https://www.parlament.gv.at"
PROTOCOLS = BASE + "/Filter/api/filter/data/211?js=eval&showAll=true"
CHAMBERS = {"NRSITZ": "Nationalrat", "BRSITZ": "Bundesrat"}
GP = "XXVIII"


def sittings(run):
    """[(chamber, path, date, title)] of plenary sittings after --since, newest first."""
    body = json.dumps({"GP_CODE": [GP]})
    reply = run.client.post_json(PROTOCOLS, body, FEED, "protokolle-" + GP)
    out = []
    for r in reply.get("rows") or []:
        kind, path, date = r[3], r[1], (r[9] or "")[:10]
        if kind in CHAMBERS and date > run.since:
            out.append((CHAMBERS[kind], path, date, r[5]))
    return sorted(out, key=lambda s: (s[2], s[1]), reverse=True)


TITLE = re.compile(r"^\d{1,2}:\d{2}:\d{2} - (?P<who>.+?) \((?P<party>[^)]*)\) - (?P<what>.+?)"
                   r"(?: \((?P<rn>RN/\d+)\))?$")
LINKED = re.compile(r">([^<]+)<")


def contributions(page):
    """[(debate_id, debate, speaker, party, kind, url)] from a history page."""
    content = (page.get("content") or [{}])[0]
    out = []
    for stage in content.get("stages") or []:
        table = (stage.get("reden") or {}).get("data") or {}
        for row in table.get("rows") or []:
            links = row[2] if len(row) > 2 and isinstance(row[2], list) else []
            if not links:
                continue
            link = links[0]
            m = TITLE.match(link.get("title") or "")
            name = LINKED.search(row[0] or "")
            who = m.group("who") if m else (name.group(1) if name else None)
            party = m.group("party") if m else None
            what = m.group("what") if m else stage.get("date")
            top = re.match(r"(TOP [\d\-, ]+\d)", what or "")
            out.append((top.group(1) if top else (what or stage.get("date")), what, who, party,
                        row[1], BASE + (link.get("url") or "").split("#")[0]))
    return out


# The page opens "Name (Club), 96. Sitzung, XXVIII. GP des NR, 19:13 RN/149
# 19.13 Abgeordnete Mag. Name (Club): ..."; the speech starts after that label.
LABEL = re.compile(r"RN/\d+\s+\d{1,2}\.\d{2}\s+[A-ZÄÖÜ][^:]{2,160}?:\s")
LABEL_LOOSE = re.compile(r"^.{0,200}?\d{1,2}\.\d{2}\s+(?:[A-ZÄÖÜ][^:]{2,160}?):\s", re.S)
# The page closes with the minute the speech ended, the chair calling the next
# speaker ("Präsidentin Doris Bures: Zu Wort gelangt ...") and the note that
# the text is not yet authorised. None of it is the speech.
UNAUTHORISED = re.compile(r"\s*Die angezeigte Rede ist noch nicht.*$", re.S)
END = re.compile(r"\s\d{1,2}\.\d{2}(?:\s+(?:(?:Vize)?[Pp]räsident(?:in)?|Präsident)\b.*)?\s*$", re.S)
INTERJECTION = re.compile(r"\(\s*(?:Beifall|Ruf|Rufe|Zwischenruf|Heiterkeit|Abg\.|Abgeordnete|"
                          r"Präsident|Bundesrät|Anhaltende|Lebhafte|Allgemeine|Weitere|Neuerliche)"
                          r"[^()]*(?:\([^()]*\)[^()]*)*\)")
MAIN = re.compile(r"(?is)<main\b.*?</main>")


def speech_text(html):
    """The speech alone, from one speech's page of the provisional protocol."""
    m = MAIN.search(html or "")
    text = cs.html_text(m.group(0) if m else html)
    one = " ".join(text.split())
    lab = LABEL.search(one[:400]) or LABEL_LOOSE.search(one)
    if lab:
        one = one[lab.end():]
    one = END.sub("", UNAUTHORISED.sub("", one))
    return INTERJECTION.sub(" ", one).strip()


def role_of(kind, party):
    """'Stellungnahme Regierungsbank' is a minister or state secretary speaking
    from the government bench; everyone else on the list is a member."""
    if "regierungsbank" in (kind or "").lower() or not party:
        return "Federal Government"
    return "member"


def speeches(run):
    try:
        listed = sittings(run)
    except FetchError as exc:
        run.gap("protocol list unreadable: {0}".format(str(exc)[:100]))
        return
    run.log("  [protokolle] {0} sitting(s) since {1}".format(len(listed), run.since))
    fetched = 0
    for chamber, path, date, title in listed:
        doc_id = path.strip("/").replace("gegenstand/", "")
        old, status = cs.read_state(run.conn, CC, doc_id)
        if status == "read":
            if not run.dry_run:
                cs.seen(run.conn, CC, doc_id, run.today)
            continue
        if run.out_of_time("speeches", fetched):
            return
        try:
            page = run.client.get_json(BASE + path + "?json=TRUE", FEED,
                                       "sitzung-" + doc_id.replace("/", "-"))
        except (FetchError, ValueError) as exc:
            run.gap("sitting {0} unreadable: {1}".format(doc_id, str(exc)[:100]))
            continue
        items = contributions(page)
        titles, matched, done, chars, pending = {}, 0, 0, 0, 0
        for i, (debate_id, debate, who, party, kind, url) in enumerate(items):
            file_id = url[len(BASE):]
            if cs.read_state(run.conn, CC, file_id)[1] == "read":
                done += 1
                continue
            if run.out_of_time("speeches", fetched):
                break
            try:
                html = run.client.get_text(url, FEED, "rede-" + os.path.basename(file_id)[:60])
            except FetchError as exc:
                if cs.not_found(exc):
                    # Listed before it is published (the newest sitting, measured
                    # 10 October 2026): read when it appears, not a gap.
                    pending += 1
                    continue
                run.gap("speech {0} unreadable: {1}".format(file_id, str(exc)[:80]))
                continue
            fetched += 1
            done += 1
            text = speech_text(html)
            chars += len(text)
            if debate not in titles:
                titles[debate] = cs.classify_title(run.taxes, debate)
            m = cs.classify_speech(run.taxes, text, titles[debate])
            hit = 0
            if m:
                hit = matched = matched + 1
                run.speech({"speech_id": "{0}#{1}".format(doc_id, os.path.basename(file_id)),
                            "doc_id": doc_id, "date": date, "chamber": chamber,
                            "debate_id": cs.short_id(debate or debate_id), "debate": debate,
                            "speaker": who,
                            "party": party, "role": role_of(kind, party), "person_id": None,
                            "text": text, "url": url, "title_areas": titles[debate].areas}, m)
            if not run.dry_run:
                cs.mark_read(run.conn, CC, file_id, "speech-file", date, None, 1,
                             1 if hit else 0, len(text), run.today)
        complete = done >= len(items)
        prior = run.conn.execute("SELECT matched FROM at_record_reads WHERE doc_id=?",
                                 (doc_id,)).fetchone()
        run.read(doc_id, "speeches", date, None, len(items),
                 matched + (prior[0] or 0 if prior else 0), chars,
                 "read" if complete else "partial")
        run.log("  [sitzung] {0} {1} ({2}): {3} speech(es) listed, {4} on our ground{5}{6}".format(
            chamber, date, title, len(items), matched, "" if complete else
            "; part-read, the rest next run", "; {0} not yet published".format(pending)
            if pending else ""))
        if not complete and run.stopped:
            return


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"speeches": speeches}, doc=__doc__))
