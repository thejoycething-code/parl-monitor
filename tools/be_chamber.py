#!/usr/bin/env python3
"""Belgium: what was said in the Chamber's plenary.

    python3 tools/be_chamber.py                      # the last three weeks
    python3 tools/be_chamber.py --since 2026-09-01
    python3 tools/be_chamber.py --dry-run
    python3 tools/be_chamber.py --reclassify

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. From the
Integraal Verslag / Compte rendu intégral, the record tools/be_rollcalls.py
reads for its votes (www.lachambre.be, robots.txt's five-second crawl delay
kept); the rest is src/chamber_store.py.

THE RECORD. One HTML file per sitting (/doc/PCRI/html/56/ip143x.html, a Word
export in windows-1252, 0.5 to 3 MB), listed on the plenary page be_rollcalls
already reads. Each contribution opens a paragraph whose first spans are
class "oraspr": its number and the speaker ("02.03 Axel Ronse (N-VA): ...");
the paragraphs after it are the speech, until the next numbered speaker or
the chair. The presiding officer's interventions carry no number and are
never stored. The agenda items are the numbered headings ("02 Questions
jointes de", then the questions, "- Axel Ronse à Bart De Wever (premier
ministre) sur ..."), in both languages; the first language printed is kept
as the debate's title. Each speech is read with both the Dutch and the
French lists, as the Belgian edition's taxonomies say: a speech can change
language mid-sentence.

QUESTIONS ARE NOT COLLECTED (yet): data.lachambre.be pages the written
questions ten at a time with no date and no order (610 requests to find a
week's), and its bulk archive (45 MB) held deposits only to 7 September on
9 October 2026 (docs/belgium-scope.md). The oral questions are in this
record, as the agenda items above.
"""

from __future__ import annotations

import html as htmlmod
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402
import be_rollcalls as be  # noqa: E402

CC = "be"
FEED = "be-chamber"
LEG = be.CURRENT_LEGISLATURE
MAX_SITTINGS = 12

BLOCK = re.compile(r"(?is)<(p|h[1-4])\b[^>]*>(.*?)</\1>")
NUMBERED = re.compile(r"^(\d{2})\.(\d{2})\s+(.+?)\s*(?:\(([^()]{1,40})\))?\s*:\s*(.*)$", re.S)
ITEM = re.compile(r"^(\d{2})\s+(.*)$")


def _text(markup):
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", markup)).replace("\xa0", " ").split())


def parse_record(raw):
    """(date, [(item_no, debate, speaker, party, text)]) from one sitting."""
    markup = be.decode(raw)
    date = None
    m = re.search(r"du (?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche) (\d{1,2})(?:er)? "
                  r"(\w+) (\d{4})", be.plain(markup[:200000]), re.I)
    if m:
        date = be.iso_date_fr(*m.groups())
    titles, item, out, current = {}, None, [], None
    for tag, body in BLOCK.findall(markup):
        text = _text(body)
        if not text:
            continue
        if tag.lower().startswith("h"):
            im = ITEM.match(text)
            if im:
                item = im.group(1)
                titles.setdefault(item, im.group(2))
            elif text.startswith("- ") and item and len(titles[item]) < 300:
                titles[item] = (titles[item] + " " + text).strip()
            current = None
            continue
        if "oraspr" in body:
            nm = NUMBERED.match(text)
            if nm:
                current = [item, nm.group(3).strip(), nm.group(4), [nm.group(5)]]
                out.append(current)
            else:
                current = None                  # the chair, or a procedural line
            continue
        if current is not None:
            current[3].append(text)
    speeches = [(i, titles.get(i), who, party, "\n".join(p for p in paras if p))
                for i, who, party, paras in out]
    return date, speeches


def speeches(run):
    try:
        listed = be.parse_sitting_list(be.decode(run.client.get_bytes(be.CRI_LIST, FEED,
                                                                      "cri-list")), LEG)
    except FetchError as exc:
        run.gap("plenary listing unreadable: {0}".format(str(exc)[:100]))
        return
    for number in sorted(listed, reverse=True)[:MAX_SITTINGS]:
        doc_id = "{0}/{1}".format(LEG, number)
        old, status = cs.read_state(run.conn, CC, doc_id)
        if status == "read":
            if not run.dry_run:
                cs.seen(run.conn, CC, doc_id, run.today)
            if old and old <= run.since:
                break
            continue
        if run.out_of_time("sittings", run.docs):
            return
        url = be.CRIV.format(LEG, number)
        try:
            raw = run.client.get_bytes(url, FEED, "cri-{0}".format(number))
        except FetchError as exc:
            run.gap("sitting {0} unreadable: {1}".format(doc_id, str(exc)[:100]))
            continue
        date, items = parse_record(raw)
        if not date:
            # "Site under maintenance!" answers 200 (measured 10 October 2026, sittings
            # 138 to 140): not a record, never marked read; the next run tries again.
            run.gap("sitting {0}: no record in the reply ({1} bytes; the site's maintenance "
                    "page?)".format(doc_id, len(raw)))
            break
        if date <= run.since:
            break
        titles, kept, matched = {}, [], 0
        for i, (item_no, debate, who, party, text) in enumerate(items):
            if debate not in titles:
                titles[debate] = cs.classify_title(run.taxes, debate)
            m = cs.classify_speech(run.taxes, text, titles[debate])
            if not m:
                continue
            sid = "{0}#{1}".format(doc_id, i)
            kept.append(sid)
            matched += 1
            run.speech({"speech_id": sid, "doc_id": doc_id, "date": date,
                        "debate_id": "{0}-{1}".format(doc_id, item_no), "debate": debate,
                        "speaker": who, "party": party,
                        "role": "member" if party else "government",
                        "person_id": None, "text": text, "url": url,
                        "title_areas": titles[debate].areas}, m)
        if not run.dry_run:
            cs.forget_speeches(run.conn, CC, doc_id, kept)
        # The version is the sitting's date, so a later run can stop at --since.
        run.read(doc_id, "speeches", date, date, len(items), matched, len(raw))
        run.log("  [verslag] {0} {1}: {2} speech(es), {3} on our ground".format(
            doc_id, date, len(items), matched))


def configure(client):
    client.set_host_throttle("www.lachambre.be", be.CRAWL_DELAY_S)


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"speeches": speeches}, doc=__doc__, configure=configure))
