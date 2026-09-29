#!/usr/bin/env python3
"""Who put their name to a Bundestag paper on our ground: de_authorship.

    python3 tools/de_authorship.py --area 1              # abortion, WP 20 and 21
    python3 tools/de_authorship.py --area 1 --since-wp 19
    python3 tools/de_authorship.py --area 1 --dry-run
    python3 tools/de_authorship.py --area 1 --db /tmp/scratch.db
    python3 tools/de_authorship.py --all            # every area with listed papers
    python3 tools/de_authorship.py --area 7 --discover   # also sweep descriptors

Built 29 September 2026 for the German 5CA (tools/de_5ca.py). A German
member's own acts beyond a speech are co-sponsoring a group bill, co-authoring
a motion and asking a question, and DIP holds all three -- but not where you
would look, and not whole.

FINDING THE PAPERS. By the Bundestag's own subject descriptors
(`f.deskriptor`), not our taxonomy: for area 1 that found 119 Vorgänge in WP
20-21 where the taxonomy-tagged de_vorgaenge held 32, and it found the § 218
group bill (20/13775, 329 co-sponsors) that the store had missed entirely.

THREE TRAPS, each paid for once:
  * /drucksache and /aktivitaet silently IGNORE `f.vorgang` and return the
    global feed: 43,078 "Kleine Anfragen" for 119 Vorgänge, which put 38
    Linke members at ++ on a first draft. /vorgangsposition honours it -- and
    every reply is still checked against the Vorgang asked for.
  * vorgangsposition's authors are TRUNCATED: 2-4 names shown for a
    312-author motion (`aktivitaet_anzahl` says how many there are). The full
    list is in the paper's text, from /drucksache-text.
  * A FRAKTION paper's signature block is its two leaders ("Dr. Alice Weidel,
    Tino Chrupalla und Fraktion"), who sign everything. Its authors are on
    the cover: "der Abgeordneten ... und der Fraktion". A GROUP paper has no
    cover list; its signers ARE the block after the last "Berlin, den".

A two-column signer block ("Corinna Rüffer Dr. Hendrik Hoppenstedt") cannot
be split line by line, so for source 'signers' the stored author is each
known member name found in the block (src/de_names.found_in). Cover and
activity names are stored as printed.

Direction is NOT decided here. Which way a paper points is a signed human
reading in config/de_stance.yaml; this only records who put their name to it.

Separation guarantee: writes de_authorship only. ONE WRITER AT A TIME on
data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, de_names, dip  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "de-authorship"
# The Bundestag's own Sachbegriffe per area live in config/de_stance.yaml
# (`descriptors:`), next to the readings they feed: adding an area is a
# config change, not a code change. Each list was measured against DIP
# before it was kept (counts and reasons are in the file).
STANCE_PATH = os.path.join(ROOT, "config", "de_stance.yaml")


def listed_papers(path=STANCE_PATH):
    """{area: {vorgang_id, ...}} of the papers config/de_stance.yaml reads.

    A reviewer may pick a paper by hand from a descriptor too noisy to keep
    (the chat-control motions sit under Datenschutz, 700-odd Vorgänge of
    mostly other things). The descriptor search would never find it, so
    every listed paper is collected by id as well.
    """
    import yaml
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    out = {}
    for p in cfg.get("papers") or []:
        if p.get("area") is not None and p.get("key"):
            out.setdefault(int(p["area"]), set()).add(str(p["key"]))
    return out


def load_descriptors(path=STANCE_PATH):
    """{area: [Sachbegriff, ...]} from the stance file."""
    import yaml
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    return {int(a): [d["term"] if isinstance(d, dict) else d for d in terms
                     if not isinstance(d, dict) or d.get("kept", True)]
            for a, terms in (cfg.get("descriptors") or {}).items()}
# Positions a member AUTHORS. Replies, reports and debates are not authorship.
AUTHORED = {"Antrag", "Gesetzentwurf", "Entschließungsantrag", "Kleine Anfrage",
            "Große Anfrage", "Schriftliche Frage", "Mündliche Frage"}
AUTHOR_ACTS = {"Antrag", "Gesetzentwurf", "Entschließungsantrag", "Kleine Anfrage",
               "Große Anfrage", "Frage"}
# "Dr. Alice Weidel, Tino Chrupalla und Fraktion" -- leaders, not authors.
LEADERS_ONLY = re.compile(r"^[^\n]{0,120}\bund\s+(der\s+)?(Fraktion|Gruppe)\b", re.S)
COVER = re.compile(r"der Abgeordneten\s(.*?)\s(?:und der (?:Fraktion|Gruppe)|und weiterer)", re.S)
STOP = re.compile(r"Begründung|Gesamtherstellung|Vorbemerkung|Vertrieb:")


def authored_type(position):
    """The authored part of a position's type, or None.

    DIP names a question and its answer as ONE position: "Schriftliche
    Frage/Schriftliche Antwort". Matching the whole name found 9 author rows
    for 71 questions on the first live run.
    """
    head = (position.get("vorgangsposition") or "").split("/")[0].strip()
    return head if head in AUTHORED else None


def vorgaenge(client, key, area, since_wp, log=print, descriptors=None):
    """{vorgang_id: document} for the area's descriptors, WP >= since_wp."""
    found = {}
    for desk in (descriptors if descriptors is not None else load_descriptors()).get(area, ()):
        for wp in range(since_wp, 22):
            for reply in dip.pages(client, "/vorgang", key, feed=FEED,
                                   slug="vg-{0}-{1}".format(desk[:12], wp), log=log,
                                   **{"f.deskriptor": desk, "f.wahlperiode": wp}):
                for d in reply.get("documents") or []:
                    found[str(d["id"])] = d
    return found


def vorgang(client, key, vorgang_id, log=print):
    """One Vorgang by id, or None. /vorgang/{id} is a path, not a filter, so
    it cannot be the ignored-f.vorgang trap."""
    try:
        doc = client.get_json(dip.url("/vorgang/" + str(vorgang_id), key), FEED,
                              "vg-id-" + str(vorgang_id), archive=False)
    except (FetchError, ValueError) as exc:
        log("  [gap] Vorgang {0}: {1}".format(vorgang_id, str(exc)[:60]))
        return None
    if str((doc or {}).get("id")) != str(vorgang_id):
        log("  [gap] Vorgang {0}: DIP answered for another id".format(vorgang_id))
        return None
    return doc


def positions(client, key, vorgang_id, log=print):
    """The Vorgang's positions, or None when DIP answered for another one."""
    docs = []
    for reply in dip.pages(client, "/vorgangsposition", key, feed=FEED,
                           slug="vp-" + vorgang_id, log=log,
                           **{"f.vorgang": vorgang_id}):
        docs.extend(reply.get("documents") or [])
    if any(str(d.get("vorgang_id")) != str(vorgang_id) for d in docs):
        log("  [gap] Vorgang {0}: DIP answered for another Vorgang -- the filter "
            "was ignored, nothing recorded".format(vorgang_id))
        return None
    return docs


def cover_authors(text):
    """Names from a Fraktion paper's cover line, as printed; [] if none."""
    hit = COVER.search((text or "")[:8000])
    if not hit:
        return []
    names = re.split(r",\s*", re.sub(r"\s+", " ", hit.group(1)))
    return [n.strip() for n in names if n.strip()]


def signer_block(text):
    """The block after the LAST 'Berlin, den', up to the reasons or the
    printer's imprint; '' when there is none, or when it is only the two
    leaders of a Fraktion."""
    text = text or ""
    at = text.rfind("Berlin, den")
    if at < 0:
        return ""
    block = STOP.split(text[at:])[0]
    body = block.split("\n", 1)[1] if "\n" in block else ""
    if LEADERS_ONLY.match(body.strip()):
        return ""
    return body


def names_in_block(block, known):
    """Known member names found in a signer block (folded match)."""
    folded = de_names.fold(block)
    return sorted({n for n in known if de_names.found_in(n, folded)})


def full_text(client, key, nummer, log=print):
    """A Drucksache's text by number, or None."""
    wp = nummer.split("/")[0]
    try:
        reply = client.get_json(dip.url("/drucksache", key, **{"f.dokumentnummer": nummer,
                                                               "f.wahlperiode": wp}),
                                FEED, "ds-" + nummer.replace("/", "-"), archive=False)
    except (FetchError, ValueError) as exc:
        log("  [gap] Drucksache {0}: {1}".format(nummer, str(exc)[:60]))
        return None
    docs = [d for d in (reply or {}).get("documents") or [] if d.get("dokumentnummer") == nummer]
    if not docs:
        log("  [gap] Drucksache {0}: not found by number".format(nummer))
        return None
    try:
        doc = client.get_json(dip.url("/drucksache-text/" + str(docs[0]["id"]), key),
                              FEED, "dt-" + nummer.replace("/", "-"), archive=False)
    except (FetchError, ValueError) as exc:
        log("  [gap] text of {0}: {1}".format(nummer, str(exc)[:60]))
        return None
    return (doc or {}).get("text")


def authors_of(client, key, position, known, log=print):
    """[(author, source)] for one authored position."""
    shown = [a for a in position.get("aktivitaet_anzeige") or []
             if a.get("aktivitaetsart") in AUTHOR_ACTS]
    printed = [(a["titel"].split(",")[0].strip(), "activity") for a in shown]
    if (position.get("aktivitaet_anzahl") or 0) <= len(position.get("aktivitaet_anzeige") or []):
        return printed
    nummer = (position.get("fundstelle") or {}).get("dokumentnummer")
    if not nummer:
        return printed
    text = full_text(client, key, nummer, log=log)
    if not text:
        log("  [gap] {0}: {1} authors, {2} shown, text unreadable -- the shown "
            "ones only".format(nummer, position.get("aktivitaet_anzahl"), len(shown)))
        return printed
    cover = cover_authors(text)
    if cover:
        return [(n, "cover") for n in cover]
    block = signer_block(text)
    if block:
        return [(n, "signers") for n in names_in_block(block, known)]
    log("  [gap] {0}: {1} authors, neither a cover list nor a signer block -- the "
        "shown ones only".format(nummer, position.get("aktivitaet_anzahl")))
    return printed


def collect(conn, client, key, area, since_wp, today, log=print, dry_run=False,
            discover=False):
    """Authors of the area's LISTED papers; with discover, also every paper
    the area's descriptors find.

    Listed-only by default (29 September 2026): the sheet reads only papers
    config/de_stance.yaml gives a reading, and several kept descriptors are
    broad on purpose and were filtered by hand (Suizid, Vorratsdatenspeicherung,
    Kirche), so sweeping them fetched authors for a thousand-odd Vorgänge
    that place nobody. --discover is the step for finding NEW papers to read.
    """
    known = sorted({r[0] for r in conn.execute("SELECT name FROM de_members")})
    found = vorgaenge(client, key, area, since_wp, log=log) if discover else {}
    for vid in sorted(listed_papers().get(area, set()) - set(found)):
        doc = vorgang(client, key, vid, log=log)
        if doc:
            found[vid] = doc
    rows = []
    for vid, v in sorted(found.items()):
        docs = positions(client, key, vid, log=log)
        for p in docs or []:
            if authored_type(p) is None:
                continue
            nummer = (p.get("fundstelle") or {}).get("dokumentnummer") or "vp-" + str(p["id"])
            for author, source in authors_of(client, key, p, known, log=log):
                rows.append((nummer, author, str(v.get("wahlperiode") or ""), vid,
                             authored_type(p), p.get("datum"),
                             (v.get("titel") or "")[:300], source, today, today))
    if not dry_run:
        conn.executemany(
            "INSERT INTO de_authorship (nummer, author, wahlperiode, vorgang_id, art, "
            "datum, titel, source, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(nummer, vorgang_id, author) DO UPDATE SET last_seen = excluded.last_seen, "
            "source = excluded.source", rows)
        conn.commit()
    return len(found), rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", type=int)
    ap.add_argument("--all", action="store_true", help="every area with descriptors")
    ap.add_argument("--since-wp", type=int, default=20)
    ap.add_argument("--discover", action="store_true",
                    help="also sweep the area's descriptors for papers not yet listed")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.all and args.area is None:
        ap.error("--area N or --all")
    if not args.all and args.area not in listed_papers() and args.area not in load_descriptors():
        ap.error("area {0} has no listed papers or descriptors in "
                 "config/de_stance.yaml".format(args.area))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    key = dip.api_key(client=client)
    if not key:
        return 1
    conn = db.init_db(db.connect(args.db))
    areas = sorted(set(load_descriptors()) | set(listed_papers())) if args.all else [args.area]
    for area in areas:
        n_vg, rows = collect(conn, client, key, area, args.since_wp,
                             datetime.date.today().isoformat(), dry_run=args.dry_run,
                             discover=args.discover)
        by_source = {}
        for r in rows:
            by_source[r[7]] = by_source.get(r[7], 0) + 1
        print("de-authorship area {0}: {1} Vorgänge, {2} author rows ({3}){4}.".format(
            area, n_vg, len(rows),
            ", ".join("{0} {1}".format(v, k) for k, v in sorted(by_source.items())) or "none",
            " [dry run]" if args.dry_run else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
