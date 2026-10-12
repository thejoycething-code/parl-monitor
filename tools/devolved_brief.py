"""Same-day vote briefs for Holyrood, the Senedd and the Assembly.

    python3 tools/devolved_brief.py                       # all three, last 7 days
    python3 tools/devolved_brief.py --nation scotland     # one nation
    python3 tools/devolved_brief.py --since 2026-09-28 --no-dm --out /tmp/x
    python3 tools/devolved_brief.py --force               # rewrite and resend

Christopher, 9 October 2026: parity with the Westminster division watch
(tools/division_brief.py). For each NEW division on our ground it writes
data/briefs/<nation>-division-<id>.md and sends ONE DM per run, to
Christopher alone: the question, the result, the tally, how each party
split, what matched, the link, and the 5CA reading status -- the signed
direction of each lobby where a human has signed it in
config/{sp,sd,ni}_stance.yaml, otherwise "awaiting sign-off".

NO VERDICTS. A lobby is reported as a fact. A direction appears only as a
human signed it, and is labelled as the signed 5CA reading.

SPEAKS ONCE. A brief that exists is neither rewritten nor resent (--force
overrides), so overlapping slots, a late GitHub backup after the Mini, or a
division the source publishes days late are all harmless. Every run looks
back --days (default 7): Holyrood has published a sitting's divisions up to
six days late (measured: 10 September 2026, published the 16th).

WHEN THE SOURCES PUBLISH (measured 9 October 2026; docs/api-notes.md):
  * Holyrood's votesmotion rows carry their own publication stamp
    (UpdatedElasticDate). Over the 27 sitting days of the new Parliament,
    17 were published the same evening between 17:08 and 19:00 London,
    after Decision Time at about 17:00; 7 the next morning between 09:10
    and 12:22; 3 two to six days late.
  * The Senedd's XMLExport and the Assembly's division list carry no
    publication stamp. Both hold the week's divisions by the Friday. The
    Assembly stamps each division with its time (the latest of the session
    so far: 21:40 on 28 September). The brief records when the watch first
    saw each division, so the lag measures itself from here on.

TOUCHES NO STORE. Everything is fetched live, through src/http.py, and the
small payloads are archived under data/raw like every other fetch. The
weeklies ledger the same divisions in the store as before.
"""

from __future__ import annotations

import argparse
import datetime
import html as _html
import json
import os
import re
import sys
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import devolved, devolved_intel, filter as filt, publish  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.ingest import holyrood, ni_hansard, niassembly, senedd  # noqa: E402

BRIEFS = os.path.join(ROOT, "data", "briefs")
REPO = "thejoycething-code/parl-monitor"
CHRISTOPHER = "U05LJP0BT61"          # the DM goes to him alone, whatever the env says
LOOKBACK_DAYS = 7
NATIONS = ("scotland", "wales", "ni")
LABEL = {"scotland": "Holyrood", "wales": "Senedd", "ni": "Assembly"}
CHAMBER = {"scotland": "Scottish Parliament", "wales": "Senedd Cymru",
           "ni": "Northern Ireland Assembly"}
PAGE = {"scotland": "msp-votes.html", "wales": "ms-votes.html", "ni": "mla-votes.html"}
SITE = "https://parl-monitor-partner.vercel.app/"
STANCE_FILE = {"scotland": "config/sp_stance.yaml", "wales": "config/sd_stance.yaml",
               "ni": "config/ni_stance.yaml"}
# The chamber's own words for the two lobbies, and the stance-file keys.
LOBBIES = {"scotland": (("Yes", "aye", "why_aye"), ("No", "no", "why_no")),
           "wales": (("For", "for", "why_for"), ("Against", "against", "why_against")),
           "ni": (("Aye", "aye", "why_aye"), ("No", "no", "why_no"))}
BOT_CHECK = "Verifying your browser"


@dataclass
class Voter:
    name: str
    party: str
    seat: str
    lobby: str          # for | against | abstain | absent


@dataclass
class Found:
    nation: str
    key: str                        # the chamber's own division id
    dated: str
    title: str
    result: str
    counts: dict                    # for, against, abstain, absent
    link: str
    voters: list = field(default_factory=list)
    question: str = ""              # the words voted on, where published
    question_source: str = ""
    areas: list = field(default_factory=list)
    terms: list = field(default_factory=list)
    matched_on: str = ""            # what text the areas came from
    watched: str = ""               # NI: the ni_watch.yaml bill it belongs to
    entry: dict = None              # the stance file's entry, if any
    reference: str = ""             # Holyrood motion reference
    published: str = ""             # the source's own publication stamp
    kind: str = ""                  # NI: Simple Majority | Cross-Community
    designation: dict = None        # NI: {designation: (ayes, noes, abst)}
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------- ground

def load_filter():
    return (filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml")),
            filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml")))


def classify(tax, wl, title, body="", any_tier=False):
    """(areas, terms) on our ground, or ([], terms) when it is not.

    Holyrood: tier 1 or a watchlist entity, the sp_items.tier rule (its
    motion culture is congratulatory, and tier 2 filed a dental fundraiser
    under assisted dying). The Senedd and the Assembly: any tier, as their
    stores classify (short debate titles; Hansard amendment wording).
    Area 11 is collated only.
    """
    res = filt.filter_item(tax, wl, title or "", body or "", title=title or "")
    if not res.matched():
        return [], []
    if not any_tier and res.tier != 1 and not res.watchlist_hits:
        return [], list(res.matched_terms or [])
    areas = [a for a in (res.issue_areas or []) if a not in devolved_intel.NOT_OUR_GROUND]
    return areas, list(res.matched_terms or []) + list(res.watchlist_hits or [])


def struck(nation):
    """Divisions a human struck as not ours in the votes config."""
    import yaml
    path = os.path.join(ROOT, "config", {"wales": "senedd_votes.yaml",
                                         "ni": "nia_votes.yaml"}.get(nation, "holyrood_votes.yaml"))
    if not os.path.exists(path):
        return set()
    divs = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("divisions") or []
    return {str(d.get("key")) for d in divs if d.get("not_ours")}


def stance_entries(nation):
    if nation == "scotland":
        return devolved_intel._tool("sp_5ca").load_stance(section="divisions")
    if nation == "wales":
        return devolved_intel._tool("sd_5ca").load_stance()
    return devolved_intel._tool("ni_5ca").load_stance(section="divisions")


# ----------------------------------------------------------------- Holyrood

def motion_page_text(client, base):
    """The base motion's text from its public page, or "" when refused.

    The open data carries no motion text short of the 110MB dump, and an
    AMENDMENT's own page answers with a bot check; the base motion's page
    answers and carries the motion as lodged (and as amended)."""
    try:
        page = client.get_text(devolved_intel.SP_MOTION.format(base), "holyrood",
                               "motion-page-{0}".format(base), timeout=60)
    except FetchError:
        return ""
    if BOT_CHECK in page:
        return ""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    text = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", text)).split())
    start = text.find("That the Parliament")
    if start < 0:
        return ""
    stop = len(text)
    for marker in (" Supported by:", " Result ", ": Amendment 1 Submitted by", " Copyright "):
        at = text.find(marker, start)
        if 0 <= at < stop:
            stop = at
    return text[start:min(stop, start + 4000)].strip()


def motion_texts(client, log=print):
    """{reference: text} from the motions dump, or {} when it fails."""
    try:
        raw = client.get_json(holyrood.MOTIONS_URL, "holyrood", "motions",
                              timeout=300, archive=False)
    except FetchError as exc:
        log("  holyrood motions dump unavailable ({0}); falling back to motion "
            "pages".format(exc.cause))
        return {}
    out = {}
    for r in raw or []:
        ref = str(r.get("EventID") or "")
        if ref:
            # Entities arrive double-escaped ("&amp;rsquo;"): unescape twice.
            out[ref] = holyrood.clean(holyrood.clean(r.get("ItemText")))
    return out


def published_stamps(raw):
    """{division key: earliest UpdatedElasticDate} from votesmotion rows."""
    out = {}
    for r in raw or []:
        d = r.get("Detail") or {}
        key = ("m{0}".format(d["MotionAgendaItemID"]) if d.get("MotionAgendaItemID") else
               "b{0}".format(d["BackupAgendaItemID"]) if d.get("BackupAgendaItemID") else "")
        stamp = r.get("UpdatedElasticDate") or ""
        if key and stamp and (key not in out or stamp < out[key]):
            out[key] = stamp
    return out


SP_LOBBY = {"Yes": "for", "No": "against", "Abstain": "abstain", "Not Voted": "absent"}


def scotland(client, since, until, skip, tax, wl, log=print):
    entries = stance_entries("scotland")
    out, raw_all = [], []
    for year in range(since.year, until.year + 1):
        try:
            raw_all.extend(client.get_json(holyrood.VOTES_URL.format(year), "holyrood",
                                           "votes-{0}".format(year), timeout=180,
                                           archive=False) or [])
        except FetchError as exc:
            log("  holyrood votes {0} unavailable: {1}".format(year, exc.cause))
    stamps = published_stamps(raw_all)
    texts, wording = {}, None
    for d in holyrood.parse_votes(raw_all):
        if not d.date or not (since.isoformat() <= d.date <= until.isoformat()):
            continue
        if d.key in skip:
            continue
        entry = entries.get(d.reference)
        base = holyrood.base_reference(d.reference)
        # THE WORDS VOTED ON, as the store classifies them: the reference
        # ('S7M-01517.3') is itself a row of the motions dump with its own
        # text. The dump is current to the hour (measured 9 October: the
        # 7 October amendments were in it) and takes ~40s, so it is fetched
        # once per run, and only when there is a division to classify.
        if wording is None:
            wording = motion_texts(client, log)
        text = wording.get(d.reference or "", "")
        source = "the {0}'s own wording".format("amendment" if "." in (d.reference or "")
                                                 else "motion")
        if not text and base:
            # Fallback: the base motion's public page (an amendment's own page
            # answers with a bot check). Marked as such: a motion's text
            # standing in for an amendment is never passed off as its own.
            if base not in texts:
                texts[base] = motion_page_text(client, base)
            text = texts[base]
            source = ("the base motion's text ({0}); the amendment's own wording was "
                      "not available".format(base) if "." in (d.reference or "")
                      else "the motion's text")
        areas, terms = classify(tax, wl, d.title, text)
        matched_on = source if areas else ""
        if not areas and not entry:
            if terms:
                log("  {0} {1}: tier-2 only ({2}); not briefed".format(
                    d.reference, d.title[:50], ", ".join(terms[:3])))
            continue
        voters = [Voter(name=devolved_intel_name(v.person_name), party=v.party or "?",
                        seat=v.constituency or "", lobby=SP_LOBBY.get(v.vote, "absent"))
                  for v in d.votes]
        counts = tally(voters)
        counts["for"], counts["against"] = d.vote_for, d.vote_against
        f = Found(nation="scotland", key=d.key, dated=d.date, title=d.title,
                  result=d.result or "?", counts=counts,
                  link=devolved_intel.SP_MOTION.format(base) if base else "",
                  voters=voters, areas=areas, terms=terms,
                  matched_on=matched_on or "a reading in config/sp_stance.yaml",
                  entry=entry, reference=d.reference or "",
                  published=stamps.get(d.key, ""))
        if text:
            f.question = text
            f.question_source = source
        out.append(f)
    return out


def devolved_intel_name(sortable):
    """'Adam, George' -> 'George Adam'."""
    name = " ".join((sortable or "").split())
    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
        return "{0} {1}".format(first, last)
    return name


# ------------------------------------------------------------------ Senedd

SD_LOBBY = {"For": "for", "Against": "against", "Abstain": "abstain"}


def wales_parties(client, log=print):
    """(name index, {person_id: (party, seat, start, end)}) from parlparse.

    The Senedd's records carry no party and its own member pages refuse our
    honest User-Agent (tools/sd_members.py), so the roster comes from
    mySociety's parlparse -- fetched only when there is a division to brief.
    """
    sdm = devolved_intel._tool("sd_members")
    data = client.get_json(sdm.URL, "senedd", "parlparse-people", timeout=180,
                           archive=False)
    posts = {p["id"]: (p.get("area") or {}).get("name") or p.get("label")
             for p in data["posts"] if p.get("organization_id") == "welsh-parliament"}
    persons = {p["id"]: p for p in data["persons"]}
    spells, index = {}, {}
    for m in data["memberships"]:
        if m.get("post_id") not in posts:
            continue
        pid = m.get("person_id")
        spells.setdefault(pid, []).append(
            (sdm.PARTY_NAMES.get(m.get("on_behalf_of_id"), m.get("on_behalf_of_id")),
             posts.get(m.get("post_id")), m.get("start_date") or "", m.get("end_date") or "9999"))
        person = persons.get(pid) or {}
        for name in [sdm.person_name(person)] + [a for a, _k in sdm.person_aliases(person)]:
            key = " ".join(devolved.norm(name).split())
            if key and key not in index:
                index[key] = pid
    return index, spells


def wales(client, since, until, skip, tax, wl, log=print):
    entries = stance_entries("wales")
    not_ours = struck("wales")
    candidates = []
    page = 1
    while page <= 3:
        try:
            sittings, more = senedd.fetch_vote_index(client, senedd.SEVENTH_SENEDD, page)
        except FetchError as exc:
            log("  senedd index page {0} unavailable: {1}".format(page, exc.cause))
            break
        recent = [s for s in sittings if s.dated >= since.isoformat()]
        for s in recent:
            if s.dated > until.isoformat() or not s.has_votes:
                continue
            try:
                divs = senedd.fetch_votes(client, s.meeting_id)
            except FetchError as exc:
                log("  senedd votes {0} unavailable: {1}".format(s.meeting_id, exc.cause))
                continue
            for d in divs:
                key = str(d.key)
                if key in skip or key in not_ours:
                    continue
                entry = entries.get(key)
                # Any tier, as the Senedd store does: a debate title is short
                # and specific, unlike Holyrood's congratulatory motions.
                areas, terms = classify(tax, wl, d.title, any_tier=True)
                if not areas and not entry:
                    if terms:
                        log("  senedd {0} {1}: tier-2 only ({2}); not briefed".format(
                            key, d.title[:50], ", ".join(terms[:3])))
                    continue
                candidates.append((d, entry, areas, terms))
        if not more or len(recent) < len(sittings):
            break
        page += 1
    if not candidates:
        return []
    try:
        index, spells = wales_parties(client, log)
    except FetchError as exc:
        log("  parlparse unavailable ({0}); parties not shown".format(exc.cause))
        index, spells = {}, {}
    out = []
    for d, entry, areas, terms in candidates:
        voters, unresolved = [], []
        got, missing = devolved.resolve([v.member_name for v in d.votes], index)
        for v in d.votes:
            pid = got.get(v.member_name)
            party, seat = "Unknown", ""
            for p, s, start, end in spells.get(pid, []):
                if start <= d.dated <= end:
                    party, seat = p or "Unknown", s or ""
            voters.append(Voter(name=v.member_name, party=party, seat=seat,
                                lobby=SD_LOBBY.get(v.result, "absent")))
        counts = tally(voters)
        counts.update({"for": d.total_for, "against": d.total_against,
                       "abstain": d.total_abstain})
        f = Found(nation="wales", key=str(d.key), dated=d.dated, title=d.title,
                  result=d.result or "?", counts=counts,
                  link=devolved_intel.SD_PLENARY.format(d.meeting_id),
                  voters=voters, areas=areas, terms=terms,
                  matched_on="the division title" if areas else
                  "a reading in config/sd_stance.yaml", entry=entry)
        if missing:
            f.notes.append("Not in the roster, so shown without a party: {0}.".format(
                ", ".join(missing)))
        out.append(f)
    return out


# ---------------------------------------------------------------- Assembly

NI_LOBBY = {"aye": "for", "no": "against", "abstain": "abstain"}


def ni(client, since, until, skip, tax, wl, log=print):
    entries = stance_entries("ni")
    not_ours = struck("ni")
    nic = devolved_intel._tool("ni_classify")
    watch = nic.watched_names()
    try:
        divisions = niassembly.fetch_divisions(client, since, until)
    except Exception as exc:                          # noqa: BLE001
        log("  assembly division list unavailable: {0}".format(exc))
        return []
    fresh = [d for d in divisions if str(d.doc_id) not in skip
             and str(d.doc_id) not in not_ours]
    by_day = {}
    for d in fresh:
        by_day.setdefault(d.when.isoformat() if d.when else "", []).append(d)
    out = []
    for day, ds in sorted(by_day.items()):
        evidence = {}
        sitting, err = (ni_hansard.fetch_sitting(client, datetime.date.fromisoformat(day))
                        if day else (None, "undated"))
        if sitting is not None and sitting.components:
            hints = {}
            for d in ds:
                m = nic._SUBJECT_AMD.search(d.subject or "")
                if m:
                    hints[d.doc_id] = int(m.group(1))
            evs, _gaps = ni_hansard.evidence_for(sitting, [d.doc_id for d in ds], hints=hints)
            evidence = {e.doc_id: e for e in evs}
        roster = {}
        for d in ds:
            doc = str(d.doc_id)
            entry = entries.get(doc)
            watched = niassembly.canonical_bill(d.bill, watch) or ""
            result, rerr = niassembly.fetch_division_result(client, doc)
            title = (result.title if result and result.title else d.subject)
            areas, terms, matched_on = [], [], ""
            ev = evidence.get(doc)
            if ev is not None and ev.source != ni_hansard.NO_TEXT:
                areas, terms, _excerpt = nic.classify(tax, wl, ev)
                areas = [a for a in areas if a not in devolved_intel.NOT_OUR_GROUND]
                matched_on = ("the amendment's own wording in Hansard"
                              if ev.source == ni_hansard.AMENDMENT_TEXT else
                              "the item's wording in Hansard")
            if not areas:
                areas, terms = classify(tax, wl, title, any_tier=True)
                matched_on = "the division title" if areas else matched_on
            if not areas and not watched and not entry:
                if ev is None:
                    log("  assembly {0} {1}: Hansard not published yet; next run".format(
                        doc, title[:50]))
                continue
            votes, verr = niassembly.fetch_member_voting(client, doc)
            if verr or not votes:
                log("  assembly {0}: member votes not published yet ({1}); next run".format(
                    doc, verr or "no rows"))
                continue
            if not roster:
                members, merr = niassembly.fetch_members_at(client, d.when)
                roster = {m.person_id: m for m in members}
            voters = []
            for v in votes:
                m = roster.get(v.person_id)
                voters.append(Voter(name=(m.display_name if m else v.member),
                                    party=(m.party if m else "{0} (designation)".format(
                                        v.designation or "?")),
                                    seat=(m.constituency if m else ""),
                                    lobby=NI_LOBBY.get(v.vote, "absent")))
            counts = tally(voters)
            if result:
                counts.update({"for": result.ayes, "against": result.noes,
                               "abstain": result.abstentions})
            f = Found(nation="ni", key=doc, dated=day, title=title,
                      result=(result.outcome if result else "?"), counts=counts,
                      link=niassembly.DIVISION_PAGE.format(doc=doc), voters=voters,
                      areas=areas, terms=terms,
                      matched_on=matched_on or ("the watched bill" if watched else
                                                "a reading in config/ni_stance.yaml"),
                      watched=watched, entry=entry,
                      published=(result.when if result else ""),
                      kind=(result.decision_type if result else d.kind),
                      designation=(result.by_designation if result else None))
            if ev is not None and (ev.amendment_text or ev.item_text):
                f.question = " ".join((ev.amendment_text or ev.item_text).split())[:1500]
                f.question_source = ("the amendment as printed in Hansard"
                                     if ev.amendment_text else "the item in Hansard")
            elif ev is None:
                f.notes.append("Hansard for the day was not yet published when this was "
                               "written; what matched is the division's title or bill.")
            if rerr:
                f.notes.append("The declared result was not available ({0}); the tally "
                               "is counted from the member votes.".format(rerr))
            out.append(f)
    return out


# ------------------------------------------------------------------- output

def tally(voters):
    c = {"for": 0, "against": 0, "abstain": 0, "absent": 0}
    for v in voters:
        c[v.lobby] = c.get(v.lobby, 0) + 1
    return c


def party_splits(voters):
    """[(party, for, against, abstain, absent)] largest voting party first."""
    t = {}
    for v in voters:
        row = t.setdefault(v.party or "Unknown", {"for": 0, "against": 0, "abstain": 0, "absent": 0})
        row[v.lobby] = row.get(v.lobby, 0) + 1
    rows = [(p, r["for"], r["against"], r["abstain"], r["absent"]) for p, r in t.items()]
    return sorted(rows, key=lambda r: (-(r[1] + r[2] + r[3]), r[0]))


def area_label(areas):
    names = devolved_intel.area_labels()
    return ", ".join(names.get(str(a), "area {0}".format(a)) for a in areas)


def reading_lines(f):
    """The 5CA reading status, as a human signed it or did not."""
    status = devolved_intel.division_status(f.entry)
    path = STANCE_FILE[f.nation]
    if status == "awaiting":
        what = "a draft reading" if f.entry else "no reading"
        return "awaiting sign-off", ["Awaiting sign-off: {0} in {1}. Until a human signs "
                                     "what this division decided, it places nobody.".format(what, path)]
    if status == "not-placeable":
        return "read: places nobody", ["Read and settled in {0}: this division cannot say who "
                                       "is with us, so it places nobody.".format(path)]
    lines = []
    for word, key, why in LOBBIES[f.nation]:
        value = f.entry.get(key)
        if value is None:
            lines.append("{0}: no signed direction.".format(word))
        else:
            lines.append("{0}: signed 5CA reading {1:+d}. {2}".format(
                word, int(value), " ".join((f.entry.get(why) or "").split())))
    signed = "; ".join("{0} {1:+d}".format(w, int(f.entry[k]))
                       for w, k, _y in LOBBIES[f.nation] if f.entry.get(k) is not None)
    return "signed ({0})".format(signed), lines


def _date_words(iso):
    try:
        d = datetime.date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    return "{0} {1} {2}".format(d.strftime("%A"), d.day, d.strftime("%B %Y"))


def _stamp_words(stamp):
    """An ISO stamp in London time, as 'Thursday 8 October 2026 17:56'."""
    if not stamp:
        return ""
    # Python's parser wants three or six fractional digits; the Assembly
    # gives two ("21:40:14.33+01:00") and Holyrood seven. Seconds suffice.
    clean = re.sub(r"\.\d+", "", stamp.replace("Z", "+00:00"))
    try:
        when = datetime.datetime.fromisoformat(clean)
    except ValueError:
        return stamp
    if when.tzinfo is not None:
        try:
            from zoneinfo import ZoneInfo
            when = when.astimezone(ZoneInfo("Europe/London"))
        except Exception:                             # noqa: BLE001
            pass
    return "{0} {1:%H:%M}".format(_date_words(when.date().isoformat()), when)


def lobby_words(nation):
    a, b = LOBBIES[nation][0][0], LOBBIES[nation][1][0]
    return {"for": a, "against": b, "abstain": "Abstained", "absent": "No vote"}


def house(text):
    """No em dashes in anything we render (CLAUDE.md), quotes included."""
    return (text or "").replace("\u2014", "-").replace("\u2013", "-")


def brief_markdown(f, seen=None):
    words = lobby_words(f.nation)
    c = f.counts
    out = ["# {0} division brief: {1}".format(LABEL[f.nation], " ".join((f.title or "").split())), ""]
    meta = "{0} division {1}{2}, {3}.".format(
        CHAMBER[f.nation], f.key, " ({0})".format(f.reference) if f.reference else "",
        _date_words(f.dated))
    if f.published:
        meta += " {0} {1}.".format("Divided at" if f.nation == "ni" else "Published by the Parliament",
                                   _stamp_words(f.published))
    meta += " First seen by the devolved watch {0}.".format(seen or datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    out += ["*{0} Facts of the record only: no verdict is given.*".format(meta), ""]
    tally_line = "{0} {1}, {2} {3}".format(words["for"], c.get("for"), words["against"], c.get("against"))
    if c.get("abstain"):
        tally_line += ", abstained {0}".format(c["abstain"])
    if c.get("absent"):
        tally_line += " ({0} recorded no vote)".format(c["absent"])
    out += ["**Result: {0}. {1}.**".format(f.result.rstrip("."), tally_line), ""]
    if f.kind:
        out += ["*Decision type: {0}.{1}*".format(
            f.kind, " A cross-community vote needs majorities in both designations; "
            "the designation table below is the arithmetic." if "cross" in f.kind.lower() else ""), ""]
    out += ["Sources: [the record]({0}) · [our {1} vote page]({2}{3})".format(
        f.link, {"scotland": "MSP", "wales": "MS", "ni": "MLA"}[f.nation], SITE, PAGE[f.nation]), ""]
    if f.question:
        q = f.question if len(f.question) <= 1200 else f.question[:1199].rstrip() + "…"
        out += ["## The question", "", "From {0}:".format(f.question_source), "", "> " + q, ""]
    out += ["## What matched", ""]
    if f.areas:
        out.append("- {0}, from {1} (terms: {2}).".format(
            area_label(f.areas), f.matched_on, ", ".join(f.terms[:6]) or "?"))
    if f.watched:
        out.append("- The bill is on the watch list: {0} (config/ni_watch.yaml).".format(f.watched))
    if f.entry:
        out.append("- A reading of this division exists in {0}.".format(STANCE_FILE[f.nation]))
    out.append("")
    status, lines = reading_lines(f)
    out += ["## 5CA reading", ""] + ["- " + ln for ln in lines] + [""]
    out += ["## By party", "", "| Party | {0} | {1} | Abstained | No vote |".format(
        words["for"], words["against"]), "|---|---|---|---|---|"]
    for p, a, n, ab, ns in party_splits(f.voters):
        out.append("| {0} | {1} | {2} | {3} | {4} |".format(p, a, n, ab, ns))
    out.append("")
    if f.designation:
        out += ["## By designation", "", "| Designation | Ayes | Noes | Abstained |", "|---|---|---|---|"]
        for des, (a, n, ab) in f.designation.items():
            out.append("| {0} | {1} | {2} | {3} |".format(des, a, n, ab))
        out.append("")
    for lobby in ("for", "against", "abstain"):
        side = [v for v in f.voters if v.lobby == lobby]
        if not side:
            continue
        out += ["## {0} ({1})".format(words[lobby], len(side)), ""]
        by_party = {}
        for v in side:
            by_party.setdefault(v.party or "Unknown", []).append(v)
        for party in sorted(by_party, key=lambda p: (-len(by_party[p]), p)):
            names = sorted(by_party[party], key=lambda v: v.name.split()[-1] if v.name else "")
            out += ["**{0}** ({1}): {2}".format(party, len(names), "; ".join(
                "{0} ({1})".format(v.name, v.seat) if v.seat else v.name for v in names)), ""]
    for note in f.notes:
        out += ["*{0}*".format(note), ""]
    out += ["---", "", "Next: read the question in the record, then sign what each lobby means in "
            "{0} (a draft places nobody). The weekly then places members and the vote page "
            "shows the signed reading.".format(STANCE_FILE[f.nation])]
    return house("\n".join(out)) + "\n"


def dm_text(f, brief_url):
    words = lobby_words(f.nation)
    c = f.counts
    lines = [":ballot_box_with_ballot: *{0} division: {1}*".format(
        LABEL[f.nation], " ".join((f.title or "").split())[:200])]
    lines.append("{0}: {1} {2}, {3} {4}{5}.".format(
        f.result.rstrip("."), words["for"], c.get("for"), words["against"], c.get("against"),
        ", abstained {0}".format(c["abstain"]) if c.get("abstain") else ""))
    splits = party_splits(f.voters)[:5]
    lines.append("By party ({0}/{1}): ".format(words["for"], words["against"]) + "; ".join(
        "{0} {1}-{2}".format(p, a, n) for p, a, n, _ab, _ns in splits) + ".")
    matched = []
    if f.areas:
        matched.append("{0} ({1})".format(area_label(f.areas), f.matched_on))
    if f.watched:
        matched.append("watched bill: {0}".format(f.watched))
    if matched:
        lines.append("Matched: " + "; ".join(matched) + ".")
    status, _lines = reading_lines(f)
    lines.append("5CA reading: {0}.".format(status))
    lines.append("Brief: {0}".format(brief_url))
    lines.append("Record: {0}".format(f.link))
    return house("\n".join(lines))


# ---------------------------------------------------------------------- run

COLLECT = {"scotland": scotland, "wales": wales, "ni": ni}


def brief_path(out_dir, nation, key):
    return os.path.join(out_dir, "{0}-division-{1}.md".format(nation, key))


def run(nations=NATIONS, since=None, until=None, out_dir=BRIEFS, force=False, dm=True,
        client=None, secrets=None, transport=None, log=print, now=None):
    now = now or datetime.datetime.now()
    until = until or now.date()
    since = since or (until - datetime.timedelta(days=LOOKBACK_DAYS))
    client = client or HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax, wl = load_filter()
    os.makedirs(out_dir, exist_ok=True)
    messages, written = [], 0
    for nation in nations:
        skip = set()
        if not force:
            prefix = "{0}-division-".format(nation)
            skip = {n[len(prefix):-3] for n in os.listdir(out_dir)
                    if n.startswith(prefix) and n.endswith(".md")}
        try:
            found = COLLECT[nation](client, since, until, skip, tax, wl, log=log)
        except Exception as exc:                      # noqa: BLE001 - one nation never sinks the rest
            log("{0}: failed ({1}: {2}); the other nations go on".format(
                LABEL[nation], type(exc).__name__, exc))
            continue
        log("{0}: {1} new division(s) on our ground since {2}.".format(
            LABEL[nation], len(found), since.isoformat()))
        for f in found:
            path = brief_path(out_dir, nation, f.key)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(brief_markdown(f, seen=now.strftime("%Y-%m-%d %H:%M")))
            written += 1
            rel = os.path.relpath(path, ROOT)
            log("  {0} {1}: brief written -> {2}".format(f.key, f.title[:60], rel))
            messages.append(dm_text(f, "https://github.com/{0}/blob/main/{1}".format(REPO, rel)))
    # ONE message per run, however many divisions and nations (the
    # Westminster lesson: six divisions once sent six DMs in a row).
    if dm and messages:
        secrets = dict(secrets if secrets is not None else publish.load_secrets())
        secrets["slack_dm_user_id"] = CHRISTOPHER
        text = "\n\n".join(messages)
        if len(messages) > 1:
            text = "*{0} devolved divisions on our ground.*\n\n".format(len(messages)) + text
        result = publish.slack_dm(secrets, text, transport=transport)
        log("DM: {0} ({1} division(s) in one message)".format(
            "sent" if result.get("message_ts") or result.get("ok") else
            result.get("skipped") or result.get("error") or "sent", len(messages)))
    elif messages:
        log("DM: not sent (--no-dm); {0} division(s) would have gone in one message.".format(
            len(messages)))
    log("{0} brief(s) written.".format(written))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nation", default="all", choices=("all",) + NATIONS)
    ap.add_argument("--since", default="", help="YYYY-MM-DD (default: {0} days back)".format(LOOKBACK_DAYS))
    ap.add_argument("--until", default="", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--force", action="store_true", help="rewrite and resend briefs that exist")
    ap.add_argument("--no-dm", action="store_true")
    ap.add_argument("--out", default=BRIEFS)
    args = ap.parse_args()
    nations = NATIONS if args.nation == "all" else (args.nation,)
    since = datetime.date.fromisoformat(args.since) if args.since else None
    until = datetime.date.fromisoformat(args.until) if args.until else None
    return run(nations, since=since, until=until, out_dir=args.out, force=args.force,
               dm=not args.no_dm)


if __name__ == "__main__":
    sys.exit(main())
