#!/usr/bin/env python3
"""Belgium's federal Chamber: members, dossiers, plenary sittings, recorded votes.

    python3 tools/be_rollcalls.py                     # the current (56th) legislature
    python3 tools/be_rollcalls.py --dry-run           # parse the latest sitting, store nothing
    python3 tools/be_rollcalls.py --reclassify        # re-apply watchlist-be, offline
    python3 tools/be_rollcalls.py --db /tmp/be.db --raw-dir /tmp/be-raw   # a scratch run

PHASE 1 (9 October 2026). See docs/belgium-scope.md. No edition reads these
tables yet. Every source is the Chamber's own website, open and keyless:

  * /doc/PCRI/html/56/ip<NNN>x.html -- the Integraal Verslag / Compte rendu
    intégral of each plenary sitting as HTML (Word export, windows-1252).
    Its annex "DETAIL VAN DE NAAMSTEMMINGEN / DETAIL DES VOTES NOMINATIFS"
    lists every member's position on every recorded vote by name; the body
    gives each vote's agenda heading, the question put and the Chamber's
    own sentence on the result. The index of sittings is the CRIV listing.
  * ListFromTo.cfm -- the dossier index, a hundred dossiers a page, in French
    and in Dutch: number, title, main Eurovoc descriptor.
  * flwbn.cfm -- one dossier page: status, type, deposit date, authors with
    their member keys, and every Eurovoc descriptor (the Chamber's own
    thesaurus: EUTHANASIE, AVORTEMENT). One request each, so it is DRAINED
    under the time budget: voted and watched dossiers first, then the
    week's recent documents, then the backlog, newest first.
  * cvlist54.cfm -- the member lists (sitting members, and every member of
    the legislature), with each member's key and group.

ROBOTS.TXT ASKS FOR "Crawl-delay: 5" on www.lachambre.be, so that host is
spaced five seconds apart (make_client). A first run is therefore long
(about 140 sittings and 38 index pages before any dossier page); later weeks
read only new sittings, the last few again, and the index.

THE RESULT OF THE PREVIOUS VOTE. The Chamber often applies one electronic
vote to several questions ("Mag de uitslag van de vorige stemming ook gelden
voor deze stemming? (Ja)"). The record then repeats "(Stemming/vote 2)". One
division row is stored per electronic vote, and `subjects` lists every
question its result decided.

CLASSIFICATION. None on text until a Belgian term list is approved (the
Germany precedent). Areas come only from config/watchlist-be.yaml, by
dossier key; a division takes its dossier's.

Separation guarantee: writes be_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import be_store, db, drain  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "be-rollcalls"
HOST = "https://www.lachambre.be"
CRAWL_DELAY_S = 5.0                 # robots.txt, measured 9 October 2026
CURRENT_LEGISLATURE = 56            # elected 9 June 2024
CRI_LIST = (HOST + "/kvvcr/showpage.cfm?section=/cricra&language=fr&cfm=dcricra.cfm"
            "?type=plen&cricra=cri&count=all")
CRIV = HOST + "/doc/PCRI/html/{0}/ip{1:03d}x.html"
MEMBERS_CURRENT = HOST + "/kvvcr/showpage.cfm?section=/depute&language=fr&cfm=/site/wwwcfm/depute/cvlist54.cfm"
MEMBERS_LEGISLATURE = (HOST + "/kvvcr/showpage.cfm?section=/depute&language=fr&cfm=cvlist54.cfm"
                       "?legis={0}&today=n")
LISTDOC = HOST + "/kvvcr/showpage.cfm?section=/flwb&language=fr&cfm=ListDocument.cfm?legislat={0}"
RANGE = (HOST + "/kvvcr/showpage.cfm?section=/flwb&language={lang}&cfm=ListFromTo.cfm"
         "?legislat={leg}&from={a}&to={b}")
DOSSIER = (HOST + "/kvvcr/showpage.cfm?section=/flwb&language=fr&cfm=/site/wwwcfm/flwb/flwbn.cfm"
           "?lang=F&legislat={0}&dossierID={1}")
RECENT = (HOST + "/kvvcr/showpage.cfm?section=/flwb/recent&language=fr&cfm=/site/wwwcfm/flwb/"
          "LastDocument.cfm")
BUDGET_S = 2700.0
REREAD_LAST = 3        # the newest sittings are read again each run: the record is corrected
# Dossier pages per run, at five seconds each: about nine minutes. MEASURED
# 9 October 2026: after about 520 requests in 46 minutes (143 sittings, the
# index and 272 dossier pages) the server began resetting connections. A
# weekly run stays far below that; the first run reads the 143 sittings,
# the index and this many pages, about 285 requests.
DOSSIER_CAP = 100
# Consecutive refused dossier pages that end the drain for this run: a
# server that has started resetting connections is asking us to stop.
DOSSIER_BREAKER = 3
GAPS_EXIT = 3          # stored what it could, recorded gaps: jobs/be-weekly.sh publishes

MONTHS_FR = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
             "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
             "novembre": 11, "décembre": 12, "decembre": 12}

# Markers in the plenary record, MEASURED across legislature 56 (sittings
# 1-15, 60, 140-143): "(Stemming/vote 4)" and, in 2025, "(Stemming/ vote 4)".
# The annex heads each list "Naamstemming - Vote nominatif: 1" (spaced
# "nominatif : 1" in 2025) and, in the first sittings of 2024, the other way
# round, "Vote nominatif - Naamstemming: 1", with the French label first in
# every count too ("Oui 80 Ja", "Non 0 Nee", "Abstentions 0 Onthoudingen").
# A counted vote shares the numbering: "(Elektronische telling/comptage
# électronique 1)" (sitting 56/96).
VOTE_MARK = re.compile(r"\(\s*(?:Stemming\s*/\s*vote|Elektronische telling\s*/\s*comptage "
                       r"électronique)\s*(\d+)\s*\)", re.I)
# The annex starts at its heading; a sitting whose only recorded vote was a
# count heads it "ELEKTRONISCHE TELLING COMPTAGE ELECTRONIQUE" (56/48).
DETAIL_SPLIT = re.compile(r"(?i:DETAIL VAN DE NAAMSTEMMINGEN)|ELEKTRONISCHE TELLING\W+COMPTAGE ELECTRONIQUE")
# "Ce compte rendu n'a pas d'annexe." (56/81, 10 December 2025): the record
# itself says the votes it took have no name list.
NO_ANNEX = re.compile(r"Ce compte rendu n'a pas d'annexe")
# Some votes are counted, not named: "Comptage électronique - Elektronische
# telling: 2 Oui 128 Ja" (sitting 56/12), "Elektronische telling - comptage
# électronique: 1" (56/80). Their annex entry has counts only.
DETAIL_HEAD = re.compile(r"(Naamstemming\s*-\s*Vote nominatif|Vote nominatif\s*-\s*Naamstemming|"
                         r"Comptage électronique\s*[-\u2013]\s*Elektronische telling|"
                         r"Elektronische telling\s*[-\u2013]\s*Comptage électronique)\s*:\s*(\d+)", re.I)
COUNTS = re.compile(r"^\s*Ja\s+(\d+)\s+Oui\s+Nee\s+(\d+)\s+Non\s+Onthoudingen\s+(\d+)\s+Abstentions")
SECTIONS = (("yes", re.compile(r"\b(?:Ja\s+(\d+)\s+Oui|Oui\s+(\d+)\s+Ja)\b")),
            ("no", re.compile(r"\b(?:Nee\s+(\d+)\s+Non|Non\s+(\d+)\s+Nee)\b")),
            ("abstain", re.compile(r"\b(?:Onthoudingen\s+(\d+)\s+Abstentions|"
                                   r"Abstentions\s+(\d+)\s+Onthoudingen)\b")))
# "(Le vote n° 43 est annulé.)": the Chamber cancelled the electronic vote
# (sitting 56/60) and took it again under the next number; the annex still
# lists the cancelled one.
ANNULLED = re.compile(r"Le vote n°\s*(\d+) est annulé")
# "Pour des raisons techniques, le détail du vote n'est pas disponible."
# (sitting 56/140, vote 4): the counts are printed, the names are not.
NO_DETAIL = re.compile(r"détail du vote n'est pas disponible")
HEADING = re.compile(r"\x01(.*?)\x02", re.S)
DOC_REF = re.compile(r"\((\d{1,4})/([0-9][0-9 ,\-]*)\)")
NL_WORDS = {"van", "het", "tot", "een", "over", "betreffende", "wetsontwerp", "wetsvoorstel",
            "voorstel", "geheel", "aangehouden", "moties", "ingediend", "aan", "vraag", "vragen",
            "houdende", "wijziging", "en", "op", "der", "inzake", "teneinde", "met"}
FR_WORDS = {"du", "la", "le", "les", "des", "et", "projet", "proposition", "loi", "ensemble",
            "réservés", "réservé", "motions", "déposées", "relative", "visant", "question",
            "questions", "portant", "modifiant", "sur", "à", "au", "aux", "en", "concernant"}


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def _squash(text):
    return re.sub(r"\s+", " ", text or "").strip()


def fold(text):
    """Accent- and case-free, single-spaced: the key a printed name is matched on."""
    text = unicodedata.normalize("NFKD", text or "")
    return _squash("".join(c for c in text if not unicodedata.combining(c))).lower()


def decode(raw):
    """The Chamber's Word exports declare windows-1252; its pages vary."""
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def plain(markup, keep_headings=False):
    """Text of an HTML page on one line. With keep_headings, every h1-h4 is
    wrapped in \\x01 ... \\x02 so the vote parser can see the agenda."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", markup)
    if keep_headings:
        text = re.sub(r"(?is)<h[1-4]\b[^>]*>(.*?)</h[1-4]>",
                      lambda m: " \x01" + re.sub(r"<[^>]+>", " ", m.group(1)) + "\x02 ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return _squash(html.unescape(text).replace("\xa0", " "))


def iso_date_fr(day, month, year):
    month = MONTHS_FR.get(fold(month)) or MONTHS_FR.get((month or "").lower())
    if not month:
        return None
    try:
        return datetime.date(int(year), month, int(day)).isoformat()
    except ValueError:
        return None


def heading_lang(text):
    words = re.findall(r"[a-zà-ÿ]+", (text or "").lower())
    nl = sum(w in NL_WORDS for w in words)
    fr = sum(w in FR_WORDS for w in words)
    return "nl" if nl > fr else "fr"


# --- the plenary record --------------------------------------------------------

def parse_sitting_list(markup, legislature):
    """Sitting numbers that have an HTML record, ascending."""
    return sorted({int(n) for n in re.findall(
        r"/doc/PCRI/html/{0}/ip(\d+)x\.html".format(legislature), markup)})


def _names(chunk):
    out = []
    for name in chunk.split(","):
        name = _squash(name)
        if name:
            out.append(name)
    return out


def parse_detail(text):
    """{vote_no: {'yes': [...], 'no': [...], 'abstain': [...], 'counts': {...}}}."""
    out = {}
    heads = list(DETAIL_HEAD.finditer(text))
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[head.end():end]
        found = []
        for pos, pattern in SECTIONS:
            m = pattern.search(block)
            if m:
                found.append((m.start(), m.end(), pos, int(m.group(1) or m.group(2))))
        found.sort()
        counted = "telling" in head.group(1).lower()
        entry = {"yes": [], "no": [], "abstain": [], "counts": {},
                 "kind": "count" if counted else "nominal",
                 "no_detail": counted or bool(NO_DETAIL.search(block))}
        for j, (_s, e, pos, count) in enumerate(found):
            stop = found[j + 1][0] if j + 1 < len(found) else len(block)
            entry[pos] = _names(block[e:stop]) if count and not entry["no_detail"] else []
            entry["counts"][pos] = count
        out[int(head.group(2))] = entry
    return out


def _subject(segment):
    """The last question put in a stretch of the record: (nl, fr) or None."""
    nl = list(re.finditer(r"Stemming over (.+?)(?= Vote sur | Begin van de stemming| Mag de uitslag|"
                          r" Vraagt iemand|$)", segment))
    fr = list(re.finditer(r"Vote sur (.+?)(?= Begin van de stemming| Mag de uitslag| Vraagt iemand|"
                          r" Stemming over |$)", segment))
    if not nl and not fr:
        return None
    return (_squash("Stemming over " + nl[-1].group(1)) if nl else None,
            _squash("Vote sur " + fr[-1].group(1)) if fr else None)


def _result_sentence(after):
    """The Chamber's French sentence on the result: the first sentence after
    the vote that says adopted or rejected ("En conséquence, la Chambre adopte
    la proposition de loi.", "La motion pure et simple est adoptée.")."""
    stretch = re.split(r"\x01|\(\s*Stemming\s*/", after, maxsplit=1)[0][:900]
    for sentence in re.split(r"(?<=\.)\s+", stretch):
        if re.search(r"\badopt|\brejet", sentence, re.I):
            return _squash(sentence)
    return None


def _outcome(sentence):
    words = re.findall(r"adopt\w*|rejet\w*|rejeté\w*", (sentence or "").lower())
    if not words:
        return None
    return "adopted" if words[0].startswith("adopt") else "rejected"


def _doc_refs(*texts):
    refs = []
    for text in texts:
        for number, docs in DOC_REF.findall(text or ""):
            ref = "{0}/{1}".format(int(number), _squash(docs).replace(" ", ""))
            if ref not in refs:
                refs.append(ref)
    return refs


def parse_sitting(raw, legislature, number):
    """One plenary record -> {'date', 'divisions': [...], 'problems': [...]}.

    A division whose printed counts disagree with the names listed, or whose
    number appears in only one half of the record, is still returned and
    named in `problems`, which the caller records as a gap."""
    text = plain(decode(raw), keep_headings=True)
    date = None
    m = re.search(r"du (?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche) (\d{1,2})(?:er)? "
                  r"(\w+) (\d{4})", text, re.I)
    if m:
        date = iso_date_fr(*m.groups())
    parts = DETAIL_SPLIT.split(text, maxsplit=1)
    body = parts[0]
    detail = parse_detail(parts[1]) if len(parts) > 1 else {}
    problems = []

    # Walk the body in order: headings set the agenda item, vote marks close a question.
    events = sorted([(h.start(), "h", h) for h in HEADING.finditer(body)]
                    + [(v.start(), "v", v) for v in VOTE_MARK.finditer(body)], key=lambda e: e[0])
    headings = []            # recent headings, newest last: (number, text)
    votes = {}
    last_cut = 0
    for pos, kind, m in events:
        if kind == "h":
            htext = _squash(m.group(1))
            num = re.match(r"(\d{1,3})\s+(.*)", htext)
            if num:
                headings.append((int(num.group(1)), num.group(2)))
                headings = headings[-4:]
            last_cut = m.end()
            continue
        vote_no = int(m.group(1))
        segment = body[last_cut:pos]
        last_cut = m.end()
        after = body[m.end():m.end() + 1200]
        subject = _subject(segment)
        entry = votes.get(vote_no)
        if entry is None:
            item = headings[-1][0] if headings else None
            pair = [t for n, t in headings if n == item]
            nl = next((t for t in pair if heading_lang(t) == "nl"), None)
            fr = next((t for t in pair if heading_lang(t) == "fr"), None)
            entry = votes[vote_no] = {"vote_no": vote_no, "heading_nl": nl, "heading_fr": fr,
                                      "subjects": [], "counts": None, "result_fr": None}
        if subject:
            entry["subjects"].append(list(subject))
        counts = COUNTS.match(after)
        if counts and entry["counts"] is None:
            entry["counts"] = tuple(int(c) for c in counts.groups())
        if entry["result_fr"] is None:
            entry["result_fr"] = _result_sentence(after)

    annulled = {int(n) for n in ANNULLED.findall(body)}
    divisions = []
    for vote_no in sorted(set(votes) | set(detail)):
        v = votes.get(vote_no) or {"vote_no": vote_no, "heading_nl": None, "heading_fr": None,
                                   "subjects": [], "counts": None, "result_fr": None}
        d = detail.get(vote_no) or {"yes": [], "no": [], "abstain": [], "counts": {}}
        if vote_no not in votes and vote_no not in annulled:
            problems.append("sitting {0}/{1}: vote {2} is in the annex but not the body".format(
                legislature, number, vote_no))
        if vote_no not in detail:
            problems.append("sitting {0}/{1}: vote {2} has no name list {3}".format(
                legislature, number, vote_no,
                "(the record says it has no annex)" if NO_ANNEX.search(text) and not detail
                else "in the annex"))
        if d.get("no_detail") and d.get("kind") != "count":
            problems.append("sitting {0}/{1}: vote {2}: the record says its name list is not "
                            "available for technical reasons".format(legislature, number, vote_no))
        for pos in ("yes", "no", "abstain"):
            if d.get("no_detail"):
                break
            printed = d["counts"].get(pos)
            if printed is not None and printed != len(d[pos]):
                problems.append("sitting {0}/{1}: vote {2}: {3} printed {4}, {5} names".format(
                    legislature, number, vote_no, pos, printed, len(d[pos])))
        counts = v["counts"] or (d["counts"].get("yes"), d["counts"].get("no"),
                                 d["counts"].get("abstain"))
        subj_text = " ".join(s for pair in v["subjects"] for s in pair if s)
        refs = _doc_refs(v["heading_nl"], v["heading_fr"], subj_text)
        dossier = None
        for h in (v["heading_nl"], v["heading_fr"]):
            hit = DOC_REF.search(h or "")
            if hit:
                dossier = "{0}/{1}".format(legislature, int(hit.group(1)))
                break
        divisions.append({
            "division_key": "{0}/{1}/{2}".format(legislature, number, vote_no),
            "vote_no": vote_no, "date": date, "dossier_key": dossier, "doc_refs": refs,
            "heading_nl": v["heading_nl"], "heading_fr": v["heading_fr"],
            "subjects": v["subjects"], "yes": counts[0], "no": counts[1], "abstain": counts[2],
            "kind": d.get("kind") or "nominal",
            "outcome": "annulled" if vote_no in annulled else _outcome(v["result_fr"]),
            "result_fr": v["result_fr"],
            "positions": [(name, pos) for pos in ("yes", "no", "abstain") for name in d[pos]],
        })
    return {"date": date, "divisions": divisions, "problems": problems}


# --- members -------------------------------------------------------------------

def parse_members(markup):
    """[(member_key, 'Surname Forename', group)] from a cvlist page."""
    out = []
    for row in re.findall(r"(?is)<tr>(.*?)</tr>", markup):
        # The key as printed. MEASURED 9 October 2026: three sitting members'
        # keys begin with a capital O, not a zero ("key=O1330", Dominiek
        # Sneppe): kept as the site prints it, since that is what its links use.
        key = re.search(r"cvview54\.cfm\?key=(\w+)", row)
        name = re.search(r"(?is)cvview54\.cfm\?key=\w+[^>]*>\s*<b>(.*?)</b>", row)
        if not key or not name:
            continue
        group = re.search(r"(?is)namegroup=[^>]*>(.*?)</a>", row)
        group = _squash(html.unescape(group.group(1))) if group else ""
        out.append((key.group(1), _squash(html.unescape(re.sub(r"<[^>]+>", " ", name.group(1)))),
                    group or None))
    return out


def pull_members(conn, client, today, legislature=CURRENT_LEGISLATURE):
    current = parse_members(decode(client.get_bytes(MEMBERS_CURRENT, FEED, "members-current")))
    everyone = parse_members(decode(client.get_bytes(
        MEMBERS_LEGISLATURE.format(legislature), FEED, "members-{0}".format(legislature))))
    if not current:
        raise ValueError("the sitting-member list parsed to nothing")
    now = {k for k, _n, _g in current}
    seen = {}
    for key, name, group in everyone + current:      # the sitting list wins for the group
        seen[key] = (name, group or (seen.get(key) or (None, None))[1])
    for key, (name, group) in seen.items():
        conn.execute(
            "INSERT INTO be_members (member_key, name, party_group, legislature, current, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(member_key) DO UPDATE SET "
            "name=excluded.name, party_group=COALESCE(excluded.party_group, be_members.party_group), "
            "legislature=MAX(COALESCE(be_members.legislature, 0), excluded.legislature), "
            "current=excluded.current, last_seen=excluded.last_seen",
            (key, name, group, legislature, int(key in now), today, today))
    # A member who left is no longer current, whether or not this legislature's list has them.
    if now:
        conn.execute("UPDATE be_members SET current=0 WHERE member_key NOT IN ({0})".format(
            ",".join("?" * len(now))), sorted(now))
    conn.commit()
    return len(seen), len(now)


def _rotations(folded):
    """Every word order that keeps the name's sequence: 'van der donckt wim'
    also as 'wim van der donckt'. One record (sitting 56/72, vote 13) prints
    "Forename Surname" for the whole list, and a multi-word surname cannot be
    split, so every rotation is indexed and only a unique one is trusted."""
    words = folded.split()
    return {" ".join(words[i:] + words[:i]) for i in range(1, len(words))}


def member_index(conn):
    """{folded name: (member_key, group)}; a name two members share maps to None.
    Rotated forms are added under ('rot', name) keys, never over a real name."""
    index = {}
    rotated = {}
    for key, name, group, leg in conn.execute(
            "SELECT member_key, name, party_group, legislature FROM be_members "
            "ORDER BY legislature"):
        k = fold(name)
        if k in index and index[k] and index[k][0] != key:
            index[k] = None
        else:
            index[k] = (key, group)
        for r in _rotations(k):
            rotated[r] = None if (r in rotated and rotated[r] and rotated[r][0] != key) else (key, group)
    for r, v in rotated.items():
        index[("rot", r)] = v
    return index


def resolve(index, name):
    """(member_key, group) for a printed name, or None.

    Exact (accent- and case-free) first. Failing that, the one member whose
    name EXTENDS the printed one: the 2024 records print "Mutyebele Ngoi"
    for Lydia Mutyebele Ngoi (sittings 56/11 onwards). Two candidates, or
    none, is None: never a guess between members."""
    key = fold(name)
    if key in index:
        return index[key]
    if ("rot", key) in index:
        return index[("rot", key)]
    hits = [v for k, v in index.items() if v and isinstance(k, str) and k.startswith(key + " ")]
    return hits[0] if len(hits) == 1 else None


# --- dossiers ------------------------------------------------------------------

def parse_ranges(markup):
    return [(int(a), int(b)) for a, b in re.findall(
        r"ListFromTo\.cfm\?legislat=\d+&(?:amp;)?from=(\d+)&(?:amp;)?to=(\d+)", markup)]


def parse_range(markup):
    """[(number, title, main descriptor)] from one ListFromTo page."""
    out = []
    for num, cell in re.findall(
            r"(?is)dossierID=(\d+)\">\s*\d+\s*</A>\s*</div>\s*</td>\s*<td>\s*<div[^>]*>(.*?)</div>",
            markup):
        parts = re.split(r"(?i)<br\s*/?>", cell, maxsplit=1)
        title = _squash(html.unescape(re.sub(r"<[^>]+>", " ", parts[0])))
        desc = _squash(html.unescape(re.sub(r"<[^>]+>", " ", parts[1]))) if len(parts) > 1 else None
        out.append((int(num), title or None, desc or None))
    return out


def _field(markup, label):
    m = re.search(r"(?is)<td class=\"td1x\"[^>]*>(?:(?!</td>).)*?" + re.escape(label) +
                  r"(?:(?!</td>).)*</td>\s*<td class=\"td0x\"[^>]*>(.*?)</td>", markup)
    return m.group(1) if m else None


def _text(fragment):
    return _squash(html.unescape(re.sub(r"<[^>]+>", " ", fragment or ""))) or None


def parse_dossier(markup):
    """The fields of one dossier page that the index does not carry."""
    status = re.search(r"(?is)<td class=\"td1x\">\s*</td>\s*<td class=\"td0x\">(.*?)</td>", markup)
    title = re.search(r"(?is)<h4>\s*<center>(.*?)</center>", markup)
    deposited = _text(_field(markup, "Date de dépôt"))
    iso = None
    if deposited and re.match(r"\d{2}/\d{2}/\d{4}$", deposited):
        d, mth, y = deposited.split("/")
        iso = "{0}-{1}-{2}".format(y, mth, d)
    authors = []
    block = _field(markup, "Auteur(s)") or ""
    for key, name, group in re.findall(
            r"(?is)key=(\w+)[^>]*>\s*([^<]+?)\s*</a>\s*([^<]*?)\s*<small>", block):
        authors.append([key, _squash(html.unescape(name)), _squash(group) or None])
    eurovoc = _text(_field(markup, "Descripteurs Eurovoc"))
    return {
        "title_fr": _text(title.group(1)) if title else None,
        "status": _text(status.group(1)) if status else None,
        "deposited": iso,
        "procedure": _text(_field(markup, "Article Constitution")),
        "doc_type": _text(_field(markup, "Type de document")),
        "authors": authors,
        "eurovoc": [e.strip() for e in eurovoc.split("|") if e.strip()] if eurovoc else [],
        "descriptor_fr": _text(_field(markup, "Descripteur Eurovoc principal")),
    }


def parse_recent(markup):
    """Dossier numbers with a new document in the Chamber's recent-documents listing."""
    return sorted({int(n) for n in re.findall(r"flwbn\.cfm\?[^\"']*dossierID=(\d+)", markup)})


def _upsert_dossier(conn, legislature, number, today, **fields):
    key = "{0}/{1}".format(legislature, number)
    areas, terms = be_store.watch_areas(key)
    conn.execute(
        "INSERT INTO be_dossiers (dossier_key, legislature, number, areas, matched_terms, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(dossier_key) DO UPDATE SET "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, last_seen=excluded.last_seen",
        (key, legislature, number, be_store.dumps(areas), be_store.dumps(terms), today, today))
    cols = {k: v for k, v in fields.items() if v is not None}
    if cols:
        conn.execute("UPDATE be_dossiers SET {0} WHERE dossier_key=?".format(
            ", ".join("{0}=?".format(c) for c in cols)), list(cols.values()) + [key])
    return key


def pull_index(conn, client, today, legislature=CURRENT_LEGISLATURE, log=print):
    """Every dossier's number, titles and main descriptor. Returns (dossiers, gaps)."""
    ranges = parse_ranges(decode(client.get_bytes(LISTDOC.format(legislature), FEED,
                                                  "listdoc-{0}".format(legislature))))
    if not ranges:
        raise ValueError("the dossier index lists no ranges")
    seen, gaps = set(), 0
    for a, b in ranges:
        for lang in ("fr", "nl"):
            try:
                rows = parse_range(decode(client.get_bytes(
                    RANGE.format(lang=lang, leg=legislature, a=a, b=b), FEED,
                    "range-{0}-{1}-{2}".format(legislature, a, lang))))
            except FetchError as exc:
                gaps += 1
                _gap(conn, today, "dossier index {0}-{1} ({2}): {3}".format(a, b, lang, exc))
                log("  [gap] dossier index {0}-{1} ({2})".format(a, b, lang))
                continue
            for number, title, desc in rows:
                seen.add(number)
                if lang == "fr":
                    _upsert_dossier(conn, legislature, number, today, title_fr=title,
                                    descriptor_fr=desc)
                else:
                    _upsert_dossier(conn, legislature, number, today, title_nl=title,
                                    descriptor_nl=desc)
    conn.commit()
    return len(seen), gaps


def dossier_queue(conn, legislature, recent=()):
    """Dossier numbers to read pages for, in order: watched and voted dossiers
    never read, then the week's recent documents, then the backlog newest first."""
    watched = {int(k.split("/")[1]) for k in be_store.watchlist() if k.startswith(
        "{0}/".format(legislature))}
    voted = {int(k.split("/")[1]) for (k,) in conn.execute(
        "SELECT DISTINCT dossier_key FROM be_divisions WHERE legislature=? AND dossier_key "
        "IS NOT NULL", (legislature,))}
    unread = {n for (n,) in conn.execute(
        "SELECT number FROM be_dossiers WHERE legislature=? AND detail_read IS NULL", (legislature,))}
    stored = {n for (n,) in conn.execute(
        "SELECT number FROM be_dossiers WHERE legislature=?", (legislature,))}
    # A watched dossier the index has not reached yet is still read first.
    first = sorted((watched | voted) & (unread | (watched - stored)), reverse=True)
    then = [n for n in sorted(set(recent), reverse=True) if n not in first]
    rest = [n for n in sorted(unread, reverse=True) if n not in first and n not in then]
    return first + then + rest


def pull_dossiers(conn, client, today, legislature=CURRENT_LEGISLATURE, budget=None,
                  cap=DOSSIER_CAP, log=print):
    """Read dossier pages, drained. Returns (read, gaps, left)."""
    try:
        recent = parse_recent(decode(client.get_bytes(RECENT, FEED, "recent")))
    except FetchError as exc:
        _gap(conn, today, "recent documents: {0}".format(exc))
        log("  [gap] recent documents listing")
        recent = []
    queue = dossier_queue(conn, legislature, recent)
    read = gaps = refused = 0
    for number in queue:
        if refused >= DOSSIER_BREAKER:
            log("  {0} dossier pages refused in a row; the drain stops for this run".format(refused))
            break
        if read >= cap or (budget and budget.exhausted()):
            if budget and budget.exhausted():
                log(budget.disclose("dossier page(s)", read))
            break
        try:
            raw = client.get_bytes(DOSSIER.format(legislature, number), FEED,
                                   "dossier-{0}-{1}".format(legislature, number))
        except FetchError as exc:
            gaps += 1
            refused += 1
            _gap(conn, today, "dossier {0}/{1}: {2}".format(legislature, number, exc))
            log("  [gap] dossier {0}/{1}".format(legislature, number))
            continue
        refused = 0
        d = parse_dossier(decode(raw))
        read += 1
        if not d["title_fr"]:
            gaps += 1
            _gap(conn, today, "dossier {0}/{1}: page carried no title".format(legislature, number))
            continue
        _upsert_dossier(conn, legislature, number, today, title_fr=d["title_fr"],
                        status=d["status"], deposited=d["deposited"], procedure=d["procedure"],
                        doc_type=d["doc_type"], authors=be_store.dumps(d["authors"]),
                        eurovoc=be_store.dumps(d["eurovoc"]), descriptor_fr=d["descriptor_fr"],
                        detail_read=today)
        conn.commit()
    return read, gaps, max(0, len(queue) - read)


# --- sittings and divisions ----------------------------------------------------

def store_sitting(conn, legislature, number, raw, parsed, today, index=None):
    """Upsert one sitting's divisions and positions. Returns (divisions, unresolved names)."""
    index = index if index is not None else member_index(conn)
    unresolved = set()
    for d in parsed["divisions"]:
        areas, terms = be_store.watch_areas(d["dossier_key"])
        conn.execute(
            "INSERT INTO be_divisions (division_key, legislature, sitting, vote_no, date, "
            "dossier_key, doc_refs, heading_nl, heading_fr, subjects, kind, yes, no, abstain, outcome, "
            "result_fr, areas, matched_terms, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(division_key) DO UPDATE SET "
            "date=excluded.date, dossier_key=excluded.dossier_key, doc_refs=excluded.doc_refs, "
            "heading_nl=excluded.heading_nl, heading_fr=excluded.heading_fr, "
            "subjects=excluded.subjects, kind=excluded.kind, yes=excluded.yes, no=excluded.no, "
            "abstain=excluded.abstain, outcome=excluded.outcome, result_fr=excluded.result_fr, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "last_seen=excluded.last_seen",
            (d["division_key"], legislature, number, d["vote_no"], d["date"], d["dossier_key"],
             be_store.dumps(d["doc_refs"]), d["heading_nl"], d["heading_fr"],
             be_store.dumps(d["subjects"]), d["kind"], d["yes"], d["no"], d["abstain"], d["outcome"],
             d["result_fr"], be_store.dumps(areas), be_store.dumps(terms), today, today))
        conn.execute("DELETE FROM be_votes WHERE division_key=?", (d["division_key"],))
        for name, pos in d["positions"]:
            hit = resolve(index, name)
            if not hit:
                unresolved.add(name)
            conn.execute("INSERT OR REPLACE INTO be_votes (division_key, member_name, member_key, "
                         "position, group_seen) VALUES (?,?,?,?,?)",
                         (d["division_key"], name, hit[0] if hit else None, pos,
                          hit[1] if hit else None))
        if d["dossier_key"]:
            _upsert_dossier(conn, legislature, int(d["dossier_key"].split("/")[1]), today)
    conn.execute(
        "INSERT INTO be_sittings (sitting_key, legislature, number, date, url, divisions, sha1, "
        "read_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(sitting_key) DO UPDATE SET "
        "date=excluded.date, divisions=excluded.divisions, sha1=excluded.sha1, "
        "read_at=excluded.read_at",
        ("{0}/{1}".format(legislature, number), legislature, number, parsed["date"],
         CRIV.format(legislature, number), len(parsed["divisions"]),
         hashlib.sha1(raw).hexdigest(), today))
    conn.commit()
    return len(parsed["divisions"]), unresolved


def pull_sittings(conn, client, today, legislature=CURRENT_LEGISLATURE, budget=None,
                  limit=None, log=print):
    """Read every sitting not yet stored, and the newest REREAD_LAST again."""
    listed = parse_sitting_list(decode(client.get_bytes(CRI_LIST, FEED, "cri-list")), legislature)
    if not listed:
        raise ValueError("the plenary listing names no sitting of legislature {0}".format(legislature))
    stored = {n for (n,) in conn.execute("SELECT number FROM be_sittings WHERE legislature=?",
                                         (legislature,))}
    todo = [n for n in listed if n not in stored] + [n for n in listed[-REREAD_LAST:] if n in stored]
    stats = {"listed": len(listed), "read": 0, "divisions": 0, "ours": 0, "gaps": 0,
             "unresolved": set()}
    index = member_index(conn)
    for number in todo:
        if limit is not None and stats["read"] >= limit:
            break
        if budget and budget.exhausted():
            log(budget.disclose("sitting(s)", stats["read"]))
            break
        try:
            raw = client.get_bytes(CRIV.format(legislature, number), FEED,
                                   "criv-{0}-{1}".format(legislature, number))
        except FetchError as exc:
            stats["gaps"] += 1
            _gap(conn, today, "sitting {0}/{1}: {2}".format(legislature, number, exc))
            log("  [gap] sitting {0}/{1}".format(legislature, number))
            continue
        parsed = parse_sitting(raw, legislature, number)
        for problem in parsed["problems"]:
            stats["gaps"] += 1
            _gap(conn, today, problem)
            log("  [gap] " + problem)
        n, unresolved = store_sitting(conn, legislature, number, raw, parsed, today, index)
        stats["read"] += 1
        stats["divisions"] += n
        stats["ours"] += sum(1 for d in parsed["divisions"]
                             if be_store.watch_areas(d["dossier_key"])[0])
        stats["unresolved"] |= unresolved
    for name in sorted(stats["unresolved"]):
        stats["gaps"] += 1
        _gap(conn, today, "vote list name matched no member: {0}".format(name))
        log("  [gap] vote list name matched no member: {0}".format(name))
    conn.commit()
    return stats


# --- offline -------------------------------------------------------------------

def reclassify(conn, log=print, wl_path=None):
    """Re-apply config/watchlist-be.yaml to every stored dossier and division."""
    changed_d = changed_v = 0
    for key, areas in conn.execute("SELECT dossier_key, areas FROM be_dossiers").fetchall():
        new, terms = be_store.watch_areas(key, wl_path)
        changed_d += be_store.dumps(new) != (areas or "[]")
        conn.execute("UPDATE be_dossiers SET areas=?, matched_terms=? WHERE dossier_key=?",
                     (be_store.dumps(new), be_store.dumps(terms), key))
    for key, dossier, areas in conn.execute(
            "SELECT division_key, dossier_key, areas FROM be_divisions").fetchall():
        new, terms = be_store.watch_areas(dossier, wl_path)
        changed_v += be_store.dumps(new) != (areas or "[]")
        conn.execute("UPDATE be_divisions SET areas=?, matched_terms=? WHERE division_key=?",
                     (be_store.dumps(new), be_store.dumps(terms), key))
    conn.commit()
    log("be-rollcalls: reclassified; {0} dossier(s) and {1} division(s) changed area".format(
        changed_d, changed_v))
    return changed_d, changed_v


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    log("  store: {0} dossier(s) ({1} with their page read, {2} watched); {3} sitting(s), "
        "{4} division(s) ({5} on a watched dossier); {6} position(s), {7} unresolved; "
        "{8} member(s), {9} sitting".format(
            n("SELECT COUNT(*) FROM be_dossiers"),
            n("SELECT COUNT(*) FROM be_dossiers WHERE detail_read IS NOT NULL"),
            n("SELECT COUNT(*) FROM be_dossiers WHERE areas != '[]'"),
            n("SELECT COUNT(*) FROM be_sittings"), n("SELECT COUNT(*) FROM be_divisions"),
            n("SELECT COUNT(*) FROM be_divisions WHERE areas != '[]'"),
            n("SELECT COUNT(*) FROM be_votes"),
            n("SELECT COUNT(*) FROM be_votes WHERE member_key IS NULL"),
            n("SELECT COUNT(*) FROM be_members"),
            n("SELECT COUNT(*) FROM be_members WHERE current=1")))


def make_client(raw_dir=None):
    client = HttpClient(raw_dir=raw_dir or os.path.join(ROOT, "data", "raw"))
    client.set_host_throttle("www.lachambre.be", CRAWL_DELAY_S)
    return client


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legislature", type=int, default=CURRENT_LEGISLATURE)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", help="archive raw payloads here instead of data/raw "
                    "(for a scratch run beside --db)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-sittings", action="store_true")
    ap.add_argument("--no-index", action="store_true", help="skip the dossier index pages")
    ap.add_argument("--no-dossiers", action="store_true", help="skip the dossier pages")
    ap.add_argument("--dossier-cap", type=int, default=DOSSIER_CAP)
    ap.add_argument("--reclassify", action="store_true",
                    help="re-apply config/watchlist-be.yaml to stored rows, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many sittings")
    ap.add_argument("--dry-run", action="store_true",
                    help="read the listing and the latest sitting, store nothing")
    args = ap.parse_args()
    client = make_client(args.raw_dir)
    today = datetime.date.today().isoformat()
    leg = args.legislature
    if args.dry_run:
        listed = parse_sitting_list(decode(client.get_text(CRI_LIST, FEED, "dry-cri-list",
                                                           archive=False)), leg)
        if not listed:
            print("be-rollcalls: NO SITTINGS LISTED for legislature {0}".format(leg))
            return 1
        raw = client.get_bytes(CRIV.format(leg, listed[-1]), FEED, "dry", archive=False)
        parsed = parse_sitting(raw, leg, listed[-1])
        print("be-rollcalls: {0} sitting(s) listed; sitting {1} ({2}): {3} division(s), "
              "{4} position(s), {5} problem(s)".format(
                  len(listed), listed[-1], parsed["date"], len(parsed["divisions"]),
                  sum(len(d["positions"]) for d in parsed["divisions"]), len(parsed["problems"])))
        for d in parsed["divisions"]:
            print("  {0} {1} {2}-{3}-{4} {5}".format(d["division_key"], d["dossier_key"] or "-",
                                                     d["yes"], d["no"], d["abstain"],
                                                     (d["heading_fr"] or "")[:70]))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        try:
            total, sitting = pull_members(conn, client, today, leg)
            print("be-rollcalls: {0} member(s) of legislature {1}, {2} sitting".format(
                total, leg, sitting))
        except (FetchError, ValueError) as exc:
            gaps += 1
            _gap(conn, today, "members: {0}".format(exc))
            conn.commit()
            print("  [gap] members: {0}".format(str(exc)[:70]))
    if not args.no_sittings:
        try:
            s = pull_sittings(conn, client, today, leg, budget=budget, limit=args.limit)
            gaps += s["gaps"]
            print("be-rollcalls: {0} sitting(s) listed, {1} read; {2} division(s), {3} on a "
                  "watched dossier; {4} unresolved name(s); {5} gap(s)".format(
                      s["listed"], s["read"], s["divisions"], s["ours"], len(s["unresolved"]),
                      s["gaps"]))
        except (FetchError, ValueError) as exc:
            gaps += 1
            _gap(conn, today, "sittings: {0}".format(exc))
            conn.commit()
            print("  [gap] sittings: {0}".format(str(exc)[:70]))
    if not args.no_index:
        try:
            n, g = pull_index(conn, client, today, leg)
            gaps += g
            print("be-rollcalls: {0} dossier(s) in the index, {1} gap(s)".format(n, g))
        except (FetchError, ValueError) as exc:
            gaps += 1
            _gap(conn, today, "dossier index: {0}".format(exc))
            conn.commit()
            print("  [gap] dossier index: {0}".format(str(exc)[:70]))
    if not args.no_dossiers:
        read, g, left = pull_dossiers(conn, client, today, leg, budget=budget,
                                      cap=args.dossier_cap)
        gaps += g
        print("be-rollcalls: {0} dossier page(s) read, {1} left for later runs, {2} gap(s)".format(
            read, left, g))
    summary(conn)
    conn.close()
    return GAPS_EXIT if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
