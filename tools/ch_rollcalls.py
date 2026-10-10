#!/usr/bin/env python3
"""Swiss Federal Assembly: members, sessions, businesses and the recorded
votes of both councils, with every member's position on our ground.

    python3 tools/ch_rollcalls.py                    # the current legislature
    python3 tools/ch_rollcalls.py --period 51        # an earlier one
    python3 tools/ch_rollcalls.py --dry-run          # count, store nothing
    python3 tools/ch_rollcalls.py --reclassify       # re-read businesses, re-derive areas
    python3 tools/ch_rollcalls.py --db /tmp/ch.db    # anywhere but the store

PHASE 1 (9 October 2026); see docs/switzerland-scope.md. Every source is
open, keyless and official:

  * ws.parlament.ch/odata.svc -- the Parliament Services' OData v2 service.
    MemberCouncil (members), Session, Business (Geschaefte, in DE and FR),
    Vote and Voting (the Nationalrat's recorded votes and positions).
  * parlament.ch/centers/documents/de/Abstimmungen_SR_<session>_DE.xlsx --
    the Staenderat's votes, one spreadsheet per session, since spring 2022.

THE STAENDERAT IS NOT IN THE ODATA SERVICE. Vote and Voting are the
Nationalrat only (200 positions per vote; a sitting Staenderat member has
no Voting row after the day they left the Nationalrat). The Staenderat
publishes its votes as a spreadsheet per session, whose file names are not
regular ('2026HS', but '2024Frühjahr'), so each spelling is tried in turn
and a session that never appears is a gap.

THE ODATA SERVICE ANSWERS IN TWO SHAPES. A short answer is {"d": [...]}; a
paged one is {"d": {"results": [...], "__next": url}}, 1,000 rows a page
for Business, while Voting returns a whole session (65,600 rows) unpaged.
rows() reads both; fetch_all follows __next.

A VOTE IS CLASSIFIED WITH ITS BUSINESS, and its own text is matched in
BOTH languages: the Nationalrat's Subject and Meaning lines are not
translated (on 9 October 2026 the German record of every Herbstsession
vote read 'Proposition de la majorité'), so the language of a vote's own
text is whatever the secretariat wrote. Businesses are matched German text
against config/taxonomy-de.yaml and French text against
config/taxonomy-qc.yaml, and the two are unioned: on the titles of the
current legislature the German list found 163 on our ground, the French
109, and they agreed on only 57.

ITALIAN TOO (CH6, Chris, 10 October 2026). Every business is also published
in Italian, and config/taxonomy-it.yaml (Italy's list; its Italy-only terms
are tagged [only: it] and dropped for `ch`) is matched on the Italian title
and submitted text, unioned like the other two (`areas_it`). A third
language pass reads the Italian records alongside the German and French
ones; businesses read by ID (refetch_businesses, two languages, unchanged)
get theirs from fill_italian, ID_BATCH to a request, on the same run. The
Italian list is NOT run on a vote's own text: the secretariat writes those in
German or French, where Italian terms are false friends (the Italian tier-1
"IVG" is the German abbreviation of the Invalidity Insurance Act). A
business refreshed in German and French only keeps its stored Italian
result (areas_it, terms_it), so the Italian areas never drop out between
passes.

POSITIONS FOR EVERY DIVISION (X15, Chris, 10 October 2026), our ground
first. Until then they were stored for divisions on our ground only (the
Canada rule), which is what the next lines measured.
The Nationalrat cast 4,201 votes in this legislature, which is 840,000
positions; a division that gains an area on --reclassify has its positions
fetched on the next run (Voting by IdVote, or the session spreadsheet).
The Nationalrat publishes no totals and no result: a stored division's
counts are tallied from its positions (counts_from='tallied'), and the
others carry none. The Staenderat's spreadsheet gives both.

Separation guarantee: writes ch_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

Exit codes: 0 clean, 3 stored what it could and recorded gaps (the weekly
job still publishes), anything else a failure.
"""

from __future__ import annotations

import argparse
import datetime
import html
import io
import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ch_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ch-rollcalls"
CURRENT_PERIOD = 52
# 10 October 2026: the addenda. taxonomy-atch is taxonomy-de plus the Swiss
# and Austrian German additions; taxonomy-fr is Quebec's French plus France's,
# Belgium's and Switzerland's (CH2-CH4). taxonomy-de and taxonomy-qc are
# unchanged for the Bundestag and Quebec.
TAXONOMY_DE = os.path.join(ROOT, "config", "taxonomy-atch.yaml")
TAXONOMY_FR = os.path.join(ROOT, "config", "taxonomy-fr.yaml")
# CH6: Italy's list on the Italian texts, for `ch` ([only: it] terms dropped).
TAXONOMY_IT = os.path.join(ROOT, "config", "taxonomy-it.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "ch"
ODATA = "https://ws.parlament.ch/odata.svc/"
SR_XLSX = "https://www.parlament.ch/centers/documents/de/Abstimmungen_SR_{0}_DE.xlsx"
BUDGET_S = drain.DEFAULT_S
# A session's votes are re-read until this many days after it ends; then it
# is marked complete and never fetched again. The Staenderat's Herbstsession
# 2026 spreadsheet was up a week after the session closed.
SESSION_GRACE_DAYS = 21
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)

BUSINESS_FIELDS = ("ID,BusinessShortNumber,BusinessTypeAbbreviation,Title,Description,"
                   "SubmittedText,SubmittedBy,BusinessStatusText,BusinessStatusDate,"
                   "SubmissionDate,SubmissionCouncilAbbreviation,SubmissionLegislativePeriod,"
                   "ResponsibleDepartmentAbbreviation,TagNames,Modified")
MEMBER_FIELDS = ("ID,PersonNumber,FirstName,LastName,CouncilAbbreviation,CantonAbbreviation,"
                 "CantonName,ParlGroupAbbreviation,PartyAbbreviation,Active,DateJoining,"
                 "DateLeaving")
VOTE_FIELDS = ("ID,IdSession,BusinessNumber,BusinessShortNumber,BillTitle,Subject,"
               "MeaningYes,MeaningNo,VoteEnd,VoteEndWithTimezone")
VOTING_FIELDS = ("IdVote,PersonNumber,FirstName,LastName,CantonName,ParlGroupCode,Decision")
SESSION_FIELDS = "ID,SessionName,StartDate,EndDate,Type,LegislativePeriodNumber"

# Voting.Decision, measured 9 October 2026 against DecisionText.
DECISIONS = {1: "Ja", 2: "Nein", 3: "Enthaltung", 4: "Anwesend",
             5: "Nicht teilgenommen", 6: "Entschuldigt", 7: "Präsident"}
# The session name's season -> the spreadsheet spellings seen, regular first.
SEASONS = (("Frühjahr", ("FS", "Frühjahr")), ("Sommer", ("SS", "Sommer")),
           ("Herbst", ("HS", "Herbst")), ("Winter", ("WS", "Winter")))


# --- small readers -------------------------------------------------------------

def odata_url(entity, flt, select=None, orderby=None, top=None):
    params = [("$filter", flt)]
    if select:
        params.append(("$select", select))
    if orderby:
        params.append(("$orderby", orderby))
    if top:
        params.append(("$top", str(top)))
    params.append(("$format", "json"))
    return ODATA + entity + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote,
                                                          safe="$',():")


def rows(payload):
    """The rows of an OData v2 answer, in either of its two shapes."""
    d = (payload or {}).get("d")
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        return d.get("results") or []
    return []


def next_link(payload):
    d = (payload or {}).get("d")
    return d.get("__next") if isinstance(d, dict) else None


def fetch_all(client, url, slug):
    """Every row behind a URL, following __next. Each page is archived."""
    out, page = [], 0
    while url:
        payload = client.get_json(url, FEED, "{0}-p{1}".format(slug, page))
        out.extend(rows(payload))
        url = next_link(payload)
        if url and "$format=" not in url:
            url += "&$format=json"
        page += 1
    return out


_DATE = re.compile(r"/Date\((-?\d+)([+-]\d{4})?\)/")


def odata_date(value, with_time=False):
    """'/Date(1790933659740+0120)/' -> '2026-10-02'. The offset is in MINUTES
    (+0120 is CEST), applied before the date is taken, so a vote at 00:30
    Swiss time is not filed under the day before."""
    hit = _DATE.match(value or "")
    if not hit:
        return None
    secs = int(hit.group(1)) / 1000.0
    if hit.group(2):
        sign = 1 if hit.group(2)[0] == "+" else -1
        secs += sign * int(hit.group(2)[1:]) * 60
    stamp = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=secs)
    return stamp.isoformat(timespec="seconds") if with_time else stamp.date().isoformat()


def strip_tags(markup):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))).strip() or None


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def empty_watchlist():
    """watchlist-ch is applied by Geschaeftsnummer (ch_store.watch_areas), so
    the filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


class Taxonomies:
    def __init__(self, de=None, fr=None, it=None):
        self.de = de if de is not None else filt.load_taxonomy(TAXONOMY_DE, country=TAXONOMY_COUNTRY)
        self.fr = fr if fr is not None else filt.load_taxonomy(TAXONOMY_FR, country=TAXONOMY_COUNTRY)
        # CH6. None when the file is absent: the Italian pass then stores
        # titles and matches nothing.
        if it is None and os.path.exists(TAXONOMY_IT):
            it = filt.load_taxonomy(TAXONOMY_IT, country=TAXONOMY_COUNTRY)
        self.it = it
        self.wl = empty_watchlist()


# --- businesses ------------------------------------------------------------------

def parse_business(rec):
    """One OData Business row -> the fields we keep, language-neutral."""
    return {
        "id": rec.get("ID"),
        "short_number": rec.get("BusinessShortNumber"),
        "type": rec.get("BusinessTypeAbbreviation"),
        "title": rec.get("Title"),
        "text": " ".join(x for x in (strip_tags(rec.get("Description")),
                                      strip_tags(rec.get("SubmittedText"))) if x),
        "submitted_by": rec.get("SubmittedBy"),
        "status": rec.get("BusinessStatusText"),
        "status_date": odata_date(rec.get("BusinessStatusDate")),
        "submission_date": odata_date(rec.get("SubmissionDate")),
        "council": rec.get("SubmissionCouncilAbbreviation") or None,
        "period": rec.get("SubmissionLegislativePeriod"),
        "department": rec.get("ResponsibleDepartmentAbbreviation") or None,
        "tags": rec.get("TagNames"),
        "modified": odata_date(rec.get("Modified"), with_time=True),
    }


def classify_business(tax, de, fr):
    """(areas_de, areas_fr, areas, matched_terms, tier). Title first, then the
    submitted text (the motion's wording, the question asked): the reasons
    and the Federal Council's background are left out, being where the
    loose matches live."""
    res_de = filt.filter_item(tax.de, tax.wl, de.get("title") or "", de.get("text") or "",
                              title=de.get("title") or "") if de else None
    res_fr = filt.filter_item(tax.fr, tax.wl, fr.get("title") or "", fr.get("text") or "",
                              title=fr.get("title") or "") if fr else None
    a_de = list(res_de.issue_areas) if res_de else []
    a_fr = list(res_fr.issue_areas) if res_fr else []
    terms = []
    for res in (res_de, res_fr):
        for t in (res.matched_terms if res else []):
            if t not in terms:
                terms.append(t)
    bid = (de or fr or {}).get("id")
    w_areas, w_hit = ch_store.watch_areas(bid)
    if w_hit:
        terms.append(w_hit)
    tiers = [r.tier for r in (res_de, res_fr) if r and r.tier]
    tier = min(tiers) if tiers else (2 if w_hit else None)
    return a_de, a_fr, sorted(set(a_de) | set(a_fr) | set(w_areas)), terms, tier


def classify_italian(tax, it):
    """(areas_it, terms_it, tier) for the Italian record (CH6), title first,
    then the submitted text, as classify_business does for the other two."""
    if not it or getattr(tax, "it", None) is None:
        return [], [], None
    res = filt.filter_item(tax.it, tax.wl, it.get("title") or "", it.get("text") or "",
                           title=it.get("title") or "")
    return list(res.issue_areas), list(res.matched_terms), res.tier


def _stored_italian(conn, bid):
    """The Italian result already stored, for a refresh without the Italian
    record: (title_it, areas_it, terms_it, tier_it) or (None, [], [], None)."""
    row = conn.execute("SELECT title_it, areas_it, terms_it, tier_it FROM ch_businesses "
                       "WHERE business_id=?", (bid,)).fetchone() if bid is not None else None
    if not row:
        return None, [], [], None
    return row[0], json.loads(row[1] or "[]"), json.loads(row[2] or "[]"), row[3]


def store_business(conn, tax, de, fr, today, it=None):
    base = de or fr or it
    a_de, a_fr, areas, terms, tier = classify_business(tax, de, fr)
    if it is not None:
        title_it = it.get("title")
        a_it, t_it, tier_it = classify_italian(tax, it)
    else:
        title_it, a_it, t_it, tier_it = _stored_italian(conn, base["id"])
    if a_it:
        areas = sorted(set(areas) | set(a_it))
        terms = terms + [t for t in t_it if t not in terms]
        tier = min(t for t in (tier, tier_it) if t) if (tier or tier_it) else None
    conn.execute(
        "INSERT INTO ch_businesses (business_id, short_number, business_type, title_de, "
        "title_fr, submitted_by, submission_date, submission_council, legislative_period, "
        "status, status_date, department, tags, modified, areas_de, areas_fr, areas, "
        "matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(business_id) DO UPDATE SET short_number=excluded.short_number, "
        "business_type=excluded.business_type, "
        "title_de=COALESCE(excluded.title_de, ch_businesses.title_de), "
        "title_fr=COALESCE(excluded.title_fr, ch_businesses.title_fr), "
        "submitted_by=excluded.submitted_by, status=excluded.status, "
        "status_date=excluded.status_date, department=excluded.department, "
        "tags=excluded.tags, modified=excluded.modified, areas_de=excluded.areas_de, "
        "areas_fr=excluded.areas_fr, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (base["id"], base["short_number"], base["type"], (de or {}).get("title"),
         (fr or {}).get("title"), base["submitted_by"], base["submission_date"],
         base["council"], base["period"], (de or base)["status"], base["status_date"],
         base["department"], (de or base)["tags"], base["modified"],
         ch_store.dumps(a_de), ch_store.dumps(a_fr), ch_store.dumps(areas),
         ch_store.dumps(terms), tier, today, today))
    if title_it is not None or it is not None:
        conn.execute("UPDATE ch_businesses SET title_it=COALESCE(?, title_it), areas_it=?, "
                     "terms_it=?, tier_it=? WHERE business_id=?",
                     (title_it, ch_store.dumps(a_it), ch_store.dumps(t_it), tier_it, base["id"]))
    return areas


def _pair(de_rows, fr_rows):
    fr = {r["ID"]: parse_business(r) for r in fr_rows}
    out = []
    seen = set()
    for r in de_rows:
        b = parse_business(r)
        out.append((b, fr.get(b["id"])))
        seen.add(b["id"])
    out.extend((None, b) for bid, b in fr.items() if bid not in seen)
    return out


def _italian_by_id(it_rows):
    return {r["ID"]: parse_business(r) for r in it_rows or []}


def pull_businesses(conn, client, tax, today, period=CURRENT_PERIOD, log=print, full=False):
    """First run: every business of the legislature, in German and French.
    Later runs: every business the service has modified since the newest
    Modified stamp stored, less a day. Returns (read, ours)."""
    (since,) = conn.execute("SELECT MAX(modified) FROM ch_businesses").fetchone()
    if full:
        since = None
    if since:
        stamp = (datetime.datetime.fromisoformat(since) - datetime.timedelta(days=1))
        cond = "Modified ge datetime'{0}'".format(stamp.strftime("%Y-%m-%dT%H:%M:%S"))
        slug = "business-since-{0}".format(stamp.date().isoformat())
    else:
        cond = "SubmissionLegislativePeriod eq {0}".format(int(period))
        slug = "business-lp{0}".format(int(period))
    pairs = _pair(
        fetch_all(client, odata_url("Business", "Language eq 'DE' and " + cond,
                                    BUSINESS_FIELDS), slug + "-de"),
        fetch_all(client, odata_url("Business", "Language eq 'FR' and " + cond,
                                    BUSINESS_FIELDS), slug + "-fr"))
    # CH6: the Italian records of the same businesses. A refused Italian
    # pass is not fatal: the German and French results are stored, the
    # Italian ones kept from before, and fill_italian retries the missing.
    try:
        italian = _italian_by_id(fetch_all(
            client, odata_url("Business", "Language eq 'IT' and " + cond, BUSINESS_FIELDS),
            slug + "-it"))
    except (FetchError, ValueError) as exc:
        log("ch-rollcalls: Italian pass refused ({0}); kept the stored Italian results".format(
            str(exc)[:80]))
        italian = None
    ours = 0
    for de, fr in pairs:
        bid = (de or fr)["id"]
        ours += on_our_ground(store_business(conn, tax, de, fr, today,
                                             it=(italian or {}).get(bid)))
    if italian is not None:
        _no_italian(conn, [(de or fr)["id"] for de, fr in pairs if (de or fr)["id"] not in italian])
    conn.commit()
    log("ch-rollcalls: {0} business(es) read ({1}), {2} on our ground".format(
        len(pairs), "since " + since[:10] if since else "legislature {0}".format(period), ours))
    return len(pairs), ours


# Businesses read by ID, this many to a request ('ID eq a or ID eq b ...').
# The first run of 9 October 2026 read the 774 older businesses its votes
# named one by one, German and French: 1,548 requests. In batches of 40 it
# is 40.
ID_BATCH = 40


def refetch_businesses(conn, client, tax, today, ids, log=print, budget=None):
    """Read named businesses, German and French, ID_BATCH to a request.
    Returns (got, gaps). An ID the service does not know is a gap."""
    ids = sorted({int(i) for i in ids})
    got = gaps = 0
    for start in range(0, len(ids), ID_BATCH):
        if budget is not None and budget.exhausted():
            log(budget.disclose("businesses", got))
            break
        chunk = ids[start:start + ID_BATCH]
        ors = " or ".join("ID eq {0}".format(i) for i in chunk)
        found, failed = {"DE": {}, "FR": {}}, False
        for lang in ("DE", "FR"):
            try:
                for r in fetch_all(client, odata_url(
                        "Business", "Language eq '{0}' and ({1})".format(lang, ors),
                        BUSINESS_FIELDS),
                        "business-{0}-{1}-{2}".format(chunk[0], len(chunk), lang.lower())):
                    found[lang][r["ID"]] = parse_business(r)
            except (FetchError, ValueError) as exc:
                _gap(conn, today, "businesses {0}..{1} {2}: {3}".format(
                    chunk[0], chunk[-1], lang, exc))
                gaps += 1
                failed = True
        for bid in chunk:
            de, fr = found["DE"].get(bid), found["FR"].get(bid)
            if de or fr:
                store_business(conn, tax, de, fr, today)
                got += 1
            elif not failed:
                _gap(conn, today, "business {0}: the service has no record".format(bid))
                gaps += 1
        conn.commit()
    return got, gaps


def _no_italian(conn, ids):
    """Mark businesses the service has no Italian record for (title_it = '',
    not NULL), so fill_italian does not ask again every week. Measured on
    10 October 2026: 3,416 of the legislature's 3,564 Fragestunde questions
    are published only in the language they were asked in."""
    for bid in ids:
        conn.execute("UPDATE ch_businesses SET title_it='' WHERE business_id=? "
                     "AND title_it IS NULL", (bid,))


def fill_italian(conn, client, tax, today, ids=None, log=print, budget=None):
    """CH6: read the Italian record of every business that has none yet
    (title_it NULL), ID_BATCH to a request, and re-derive its areas with the
    Italian result added. Returns (got, gaps). A business the service has no
    Italian record for is marked title_it = '' (no gap: Fragestunde
    questions are published in one language) and not asked again; a refused
    request is a gap."""
    if ids is None:
        ids = [b for (b,) in conn.execute(
            "SELECT business_id FROM ch_businesses WHERE title_it IS NULL ORDER BY business_id")]
    ids = sorted({int(i) for i in ids})
    got = gaps = 0
    for start in range(0, len(ids), ID_BATCH):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Italian businesses", got))
            break
        chunk = ids[start:start + ID_BATCH]
        ors = " or ".join("ID eq {0}".format(i) for i in chunk)
        try:
            italian = _italian_by_id(fetch_all(client, odata_url(
                "Business", "Language eq 'IT' and ({0})".format(ors), BUSINESS_FIELDS),
                "business-{0}-{1}-it".format(chunk[0], len(chunk))))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "businesses {0}..{1} IT: {2}".format(chunk[0], chunk[-1], exc))
            gaps += 1
            continue
        _no_italian(conn, [b for b in chunk if b not in italian])
        for bid, it in italian.items():
            row = conn.execute("SELECT areas_de, areas_fr, areas, matched_terms, tier "
                               "FROM ch_businesses WHERE business_id=?", (bid,)).fetchone()
            if not row:
                continue
            a_it, t_it, tier_it = classify_italian(tax, it)
            w_areas, _hit = ch_store.watch_areas(bid)
            base = (set(json.loads(row[0] or "[]")) | set(json.loads(row[1] or "[]"))
                    | set(w_areas))
            terms = json.loads(row[3] or "[]")
            terms += [t for t in t_it if t not in terms]
            tiers = [t for t in (row[4], tier_it) if t]
            conn.execute("UPDATE ch_businesses SET title_it=?, areas_it=?, terms_it=?, tier_it=?, "
                         "areas=?, matched_terms=?, tier=? WHERE business_id=?",
                         (it.get("title") or "", ch_store.dumps(a_it), ch_store.dumps(t_it), tier_it,
                          ch_store.dumps(sorted(base | set(a_it))), ch_store.dumps(terms),
                          min(tiers) if tiers else None, bid))
            got += 1
        conn.commit()
    if ids:
        log("ch-rollcalls: Italian records read for {0} of {1} business(es)".format(got, len(ids)))
    return got, gaps


def pull_missing_businesses(conn, client, tax, today, log=print, budget=None):
    """Businesses a stored division names but the store lacks: a vote in this
    legislature on a parliamentary initiative of 2017 is common."""
    missing = [b for (b,) in conn.execute(
        "SELECT DISTINCT d.business_id FROM ch_divisions d LEFT JOIN ch_businesses b "
        "ON b.business_id = d.business_id WHERE d.business_id >= 1000000 "
        "AND b.business_id IS NULL ORDER BY d.business_id")]
    got, gaps = refetch_businesses(conn, client, tax, today, missing, log=log, budget=budget)
    if missing:
        log("ch-rollcalls: {0} of {1} business(es) named by a vote fetched".format(
            got, len(missing)))
    return got, gaps


# --- members and sessions ------------------------------------------------------------

def store_member(conn, m, today):
    conn.execute(
        "INSERT INTO ch_members (person_number, first_name, last_name, council, canton, "
        "canton_name, parl_group, party, active, date_joining, date_leaving, first_seen, "
        "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(person_number) DO UPDATE SET "
        "first_name=COALESCE(excluded.first_name, ch_members.first_name), "
        "last_name=COALESCE(excluded.last_name, ch_members.last_name), "
        "council=COALESCE(excluded.council, ch_members.council), "
        "canton=COALESCE(excluded.canton, ch_members.canton), "
        "canton_name=COALESCE(excluded.canton_name, ch_members.canton_name), "
        "parl_group=COALESCE(excluded.parl_group, ch_members.parl_group), "
        "party=COALESCE(excluded.party, ch_members.party), "
        "active=COALESCE(excluded.active, ch_members.active), "
        "date_joining=COALESCE(excluded.date_joining, ch_members.date_joining), "
        "date_leaving=COALESCE(excluded.date_leaving, ch_members.date_leaving), "
        "last_seen=excluded.last_seen",
        (m["person_number"], m.get("first_name"), m.get("last_name"), m.get("council"),
         m.get("canton"), m.get("canton_name"), m.get("parl_group"), m.get("party"),
         m.get("active"), m.get("date_joining"), m.get("date_leaving"), today, today))


def parse_member(rec):
    return {"person_number": rec.get("PersonNumber") or rec.get("ID"),
            "first_name": rec.get("FirstName"), "last_name": rec.get("LastName"),
            "council": rec.get("CouncilAbbreviation") or None,
            "canton": rec.get("CantonAbbreviation") or None,
            "canton_name": rec.get("CantonName") or None,
            "parl_group": rec.get("ParlGroupAbbreviation") or None,
            "party": rec.get("PartyAbbreviation") or None,
            "active": None if rec.get("Active") is None else int(bool(rec.get("Active"))),
            "date_joining": odata_date(rec.get("DateJoining")),
            "date_leaving": odata_date(rec.get("DateLeaving"))}


def pull_members(conn, client, today, since):
    """Every member sitting now or at any time since `since` (the first day of
    the legislature): 332 for the 52nd, in one call."""
    flt = ("Language eq 'DE' and (Active eq true or DateLeaving ge datetime'{0}T00:00:00')"
           .format(since))
    recs = fetch_all(client, odata_url("MemberCouncil", flt, MEMBER_FIELDS), "members")
    for r in recs:
        store_member(conn, parse_member(r), today)
    conn.commit()
    return len(recs)


def parse_session(rec):
    return {"id": rec["ID"], "name": rec.get("SessionName"),
            "start": odata_date(rec.get("StartDate")), "end": odata_date(rec.get("EndDate")),
            "type": rec.get("Type"), "period": rec.get("LegislativePeriodNumber")}


def pull_sessions(conn, client, today, period=CURRENT_PERIOD):
    recs = fetch_all(client, odata_url(
        "Session", "Language eq 'DE' and LegislativePeriodNumber eq {0}".format(int(period)),
        SESSION_FIELDS), "sessions-lp{0}".format(int(period)))
    out = []
    for r in recs:
        s = parse_session(r)
        conn.execute(
            "INSERT INTO ch_sessions (session_id, name, start_date, end_date, session_type, "
            "legislative_period, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET name=excluded.name, "
            "start_date=excluded.start_date, end_date=excluded.end_date, "
            "session_type=excluded.session_type, last_seen=excluded.last_seen",
            (s["id"], s["name"], s["start"], s["end"], s["type"], s["period"], today, today))
        out.append(s)
    conn.commit()
    return sorted(out, key=lambda s: s["id"])


def sr_spellings(session_name):
    """'Herbstsession 2026' -> ['2026HS', '2026Herbst']; a special session -> []."""
    year = re.search(r"(\d{4})", session_name or "")
    if not year:
        return []
    for word, spellings in SEASONS:
        if (session_name or "").startswith(word):
            return [year.group(1) + s for s in spellings]
    return []


# --- divisions ---------------------------------------------------------------------

def classify_own(tax, d):
    """The vote's OWN text, in both languages (see the module docstring)."""
    fields = [d.get("subject") or "", d.get("meaning_yes") or "", d.get("meaning_no") or "",
              d.get("draft_title") or ""]
    res = [filt.filter_item(t, tax.wl, *fields, title="") for t in (tax.de, tax.fr)]
    areas = sorted(set(res[0].issue_areas) | set(res[1].issue_areas))
    terms = []
    for r in res:
        for t in r.matched_terms:
            if t not in terms:
                terms.append(t)
    tiers = [r.tier for r in res if r.tier]
    return areas, terms, (min(tiers) if tiers else None)


def _business_areas(conn, bid):
    if bid is None:
        return []
    row = conn.execute("SELECT areas FROM ch_businesses WHERE business_id=?", (bid,)).fetchone()
    return json.loads(row[0] or "[]") if row else []


def store_division(conn, tax, d, today):
    """Upsert one division (no positions). Returns its combined areas."""
    own, terms, tier = classify_own(tax, d)
    areas = sorted(set(own) | set(_business_areas(conn, d.get("business_id"))))
    conn.execute(
        "INSERT INTO ch_divisions (division_key, council, vote_id, session_id, date, "
        "business_id, short_number, draft_title, subject, meaning_yes, meaning_no, yes, no, "
        "abstain, absent, result, counts_from, positions, own_areas, areas, matched_terms, "
        "tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET session_id=excluded.session_id, "
        "date=excluded.date, business_id=excluded.business_id, "
        "short_number=excluded.short_number, draft_title=excluded.draft_title, "
        "subject=excluded.subject, meaning_yes=excluded.meaning_yes, "
        "meaning_no=excluded.meaning_no, "
        "yes=COALESCE(excluded.yes, ch_divisions.yes), no=COALESCE(excluded.no, ch_divisions.no), "
        "abstain=COALESCE(excluded.abstain, ch_divisions.abstain), "
        "absent=COALESCE(excluded.absent, ch_divisions.absent), "
        "result=COALESCE(excluded.result, ch_divisions.result), "
        "counts_from=COALESCE(excluded.counts_from, ch_divisions.counts_from), "
        "own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (d["key"], d["council"], d["vote_id"], d.get("session_id"), d.get("date"),
         d.get("business_id"), d.get("short_number"), d.get("draft_title"), d.get("subject"),
         d.get("meaning_yes"), d.get("meaning_no"), d.get("yes"), d.get("no"),
         d.get("abstain"), d.get("absent"), d.get("result"), d.get("counts_from"), 0,
         ch_store.dumps(own), ch_store.dumps(areas), ch_store.dumps(terms), tier,
         today, today))
    return areas


def store_positions(conn, key, positions, tally=False):
    """Replace a division's positions. tally=True also writes counts tallied
    from them (the Nationalrat publishes none)."""
    conn.execute("DELETE FROM ch_votes WHERE division_key=?", (key,))
    for p in positions:
        conn.execute("INSERT OR REPLACE INTO ch_votes (division_key, person_number, position, "
                     "parl_group, canton) VALUES (?,?,?,?,?)",
                     (key, p["person_number"], p["position"], p.get("parl_group"),
                      p.get("canton")))
    if tally:
        count = lambda *names: sum(1 for p in positions if p["position"] in names)  # noqa: E731
        conn.execute("UPDATE ch_divisions SET yes=?, no=?, abstain=?, absent=?, "
                     "counts_from='tallied', positions=? WHERE division_key=?",
                     (count("Ja"), count("Nein"), count("Enthaltung"),
                      count("Nicht teilgenommen", "Entschuldigt"), len(positions), key))
    else:
        conn.execute("UPDATE ch_divisions SET positions=? WHERE division_key=?",
                     (len(positions), key))


# Nationalrat ------------------------------------------------------------------

def parse_nr_vote(rec):
    """One OData Vote row. A procedural vote with no business (an
    Ordnungsantrag) carries BusinessNumber 1 and the short number '00.000':
    23 of the 52nd legislature's 4,201. It is stored with no business, never
    looked up as business 1."""
    when = rec.get("VoteEndWithTimezone") or rec.get("VoteEnd")
    bid = rec.get("BusinessNumber")
    bid = int(bid) if bid and int(bid) >= 1000000 else None
    return {"key": "nr-{0}".format(rec["ID"]), "council": "NR", "vote_id": rec["ID"],
            "session_id": int(rec["IdSession"]) if rec.get("IdSession") else None,
            "date": odata_date(when), "business_id": bid,
            "short_number": rec.get("BusinessShortNumber") if bid else None,
            "draft_title": rec.get("BillTitle"), "subject": rec.get("Subject"),
            "meaning_yes": rec.get("MeaningYes"), "meaning_no": rec.get("MeaningNo")}


def parse_nr_voting(rec):
    return {"person_number": rec.get("PersonNumber"),
            "first_name": rec.get("FirstName"), "last_name": rec.get("LastName"),
            "canton_name": rec.get("CantonName"),
            "parl_group": rec.get("ParlGroupCode") or None,
            "position": DECISIONS.get(rec.get("Decision"), str(rec.get("Decision")))}


def pull_nr_session(conn, client, tax, session_id, today, log=print):
    """Every Nationalrat vote of a session not yet stored. Returns (new, gaps)."""
    try:
        recs = fetch_all(client, odata_url(
            "Vote", "Language eq 'DE' and IdSession eq {0}".format(int(session_id)),
            VOTE_FIELDS), "nr-votes-{0}".format(session_id))
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "nr votes session {0}: {1}".format(session_id, exc))
        log("  [gap] NR votes, session {0}: {1}".format(session_id, str(exc)[:70]))
        return 0, 1
    have = {k for (k,) in conn.execute(
        "SELECT division_key FROM ch_divisions WHERE council='NR' AND session_id=?",
        (session_id,))}
    new = 0
    for r in recs:
        d = parse_nr_vote(r)
        if d["key"] in have:
            continue
        store_division(conn, tax, d, today)
        new += 1
    conn.commit()
    return new, 0


def fetch_nr_positions(conn, client, vote_id, today):
    recs = rows(client.get_json(odata_url(
        "Voting", "Language eq 'DE' and IdVote eq {0}".format(int(vote_id)), VOTING_FIELDS),
        FEED, "nr-voting-{0}".format(vote_id)))
    out = []
    for r in recs:
        p = parse_nr_voting(r)
        if not p["person_number"]:
            continue
        store_member(conn, {"person_number": p["person_number"],
                            "first_name": p["first_name"], "last_name": p["last_name"],
                            "canton_name": p["canton_name"], "parl_group": p["parl_group"]},
                     today)
        out.append(p)
    return out


# Staenderat -------------------------------------------------------------------

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def xlsx_rows(blob):
    """The first worksheet of an .xlsx as a list of {column letter: text}.
    Stdlib only: shared strings, inline strings and plain values."""
    zf = zipfile.ZipFile(io.BytesIO(blob))
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).iter(_NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(_NS + "t")))
    sheets = sorted(n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
    out = []
    for row in ET.fromstring(zf.read(sheets[0])).iter(_NS + "row"):
        vals = {}
        for c in row.findall(_NS + "c"):
            col = re.match(r"[A-Z]+", c.get("r") or "")
            if not col:
                continue
            v = c.find(_NS + "v")
            kind = c.get("t")
            if kind == "s" and v is not None:
                text = shared[int(v.text)]
            elif kind == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(_NS + "t"))
            else:
                text = v.text if v is not None else None
            vals[col.group(0)] = (text or "").strip()
        out.append(vals)
    return out


def _col_index(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


SR_POSITIONS = {"ja": "Ja", "nein": "Nein", "enthaltung": "Enthaltung",
                "hat nicht teilgenommen": "Nicht teilgenommen", "anwesend": "Anwesend",
                "die präsidentin/der präsident stimmt nicht": "Präsident"}
# Header labels, lower-cased, with the older layout's spelling second.
SR_FIELDS = {
    "business": ("geschäftsnummer",), "business_title": ("geschäftstitel",),
    "business_type": ("geschäftstyp",), "draft_title": ("entwurftitel", "vorlagetitel"),
    "ref": ("referenznummer",), "date": ("datum der abstimmung", "abstimmungsdatum"),
    "subject": ("abstimmungsgegenstand",), "meaning_yes": ("bedeutung ja",),
    "meaning_no": ("bedeutung nein",), "result": ("entscheid des rates",),
    "yes": ("anzahl 'ja'",), "no": ("anzahl 'nein'",), "abstain": ("anzahl enthaltungen",),
    "excused": ("anzahl 'entschuldigt'",), "absent": ("anzahl 'nicht teilgenommen'",),
}


def sr_position(cell):
    """Every spelling seen in the 13 sheets of 2022-2026: 'Ja' and 'ja',
    'Entschuldigt gem. Art. 57 Abs. 4' and plain 'entschuldigt', ..."""
    low = (cell or "").strip().lower()
    if not low:
        return None
    if low.startswith("entschuldigt"):
        return "Entschuldigt"
    return SR_POSITIONS.get(low, cell.strip())


def sr_meaning(text):
    """'Antrag der Kommission | * | *' -> 'Antrag der Kommission'. The older
    sheets pad each meaning with one '*' per extra proposal."""
    parts = [p.strip() for p in (text or "").split("|")]
    return " | ".join(p for p in parts if p and p != "*") or None


def _int(text):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def iso_ch_date(text):
    """'15.09.2026' -> '2026-09-15'; an Excel serial number is read too."""
    text = (text or "").strip()
    try:
        return datetime.datetime.strptime(text, "%d.%m.%Y").date().isoformat()
    except ValueError:
        pass
    if re.match(r"^\d+(\.\d+)?$", text):
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(text)))).isoformat()
    return text or None


def parse_sr_sheet(blob):
    """One Staenderat session spreadsheet -> {'declared', 'members', 'votes'}.

    Two layouts, measured over all 13 sheets of 2022-2026 (9 October 2026).
    To the Sommersession 2024 the member block carries a 'Ratsmitglied (Nr)'
    row of PersonNumbers above 'Name des Ratsmitgliedes' (label in column
    L), cantons as 'AG', and the vote header starts 'Abstimmungsdatum'. From
    the Herbstsession 2024 the number row is gone, the label reads 'Name des
    Ratsmitglieds' (column K), cantons are German names and the header
    starts 'Geschäftsnummer'. Column positions also move between sessions
    of one layout. So everything is found by its label, never by position,
    and a vote row is any row below the header with a Referenznummer: the
    Wintersession 2025 has a procedural vote with no Geschaeftsnummer."""
    sheet = xlsx_rows(blob)
    declared = None
    label_col = numbers = names = cantons = groups = header = None
    header_at = None
    for i, row in enumerate(sheet):
        if row.get("A", "").startswith("Anzahl Abstimmungen"):
            declared = _int(row.get("B"))
        lowered = {v.lower(): c for c, v in row.items() if v}
        if header is None and "referenznummer" in lowered:
            header, header_at = row, i
            continue
        if header is not None:
            continue
        for col, val in row.items():
            if val.startswith("Name des Ratsmitglied"):
                label_col, names = col, row
            elif val == "Ratsmitglied (Nr)":
                numbers = row
            elif val == "Kanton":
                cantons = row
            elif val == "Fraktion":
                groups = row
    if names is None or header is None:
        raise ValueError("not a Staenderat vote sheet: no member or header row")
    lowered = {v.lower(): c for c, v in header.items() if v}
    field = {}
    for key, labels in SR_FIELDS.items():
        for label in labels:
            if label in lowered:
                field[key] = lowered[label]
                break
    if "ref" not in field:
        raise ValueError("Staenderat sheet without a Referenznummer column")
    member_cols = [c for c, v in names.items()
                   if v and _col_index(c) > _col_index(label_col)]
    members = {}
    for c in member_cols:
        last, _, first = names[c].partition(",")
        members[c] = {"person_number": _int((numbers or {}).get(c)),
                      "last_name": last.strip(), "first_name": first.strip(),
                      "canton_name": (cantons or {}).get(c) or None,
                      "parl_group": re.sub(r"^Fraktion\s+", "", (groups or {}).get(c) or "") or None}

    def get(row, key):
        return row.get(field.get(key, "?")) or None

    votes = []
    for row in sheet[header_at + 1:]:
        ref = _int(get(row, "ref"))
        if ref is None:
            continue
        excused, absent = _int(get(row, "excused")), _int(get(row, "absent"))
        votes.append({
            "key": "sr-{0}".format(ref), "council": "SR", "vote_id": ref,
            "business_id": _int(get(row, "business")),
            "business_title": get(row, "business_title"),
            "business_type": get(row, "business_type"),
            "draft_title": get(row, "draft_title"),
            "date": iso_ch_date(get(row, "date")),
            "subject": sr_meaning(get(row, "subject")),
            "meaning_yes": sr_meaning(get(row, "meaning_yes")),
            "meaning_no": sr_meaning(get(row, "meaning_no")),
            "result": get(row, "result"),
            "yes": _int(get(row, "yes")), "no": _int(get(row, "no")),
            "abstain": _int(get(row, "abstain")),
            "absent": (None if excused is None and absent is None
                       else (excused or 0) + (absent or 0)),
            "counts_from": "published",
            "cells": {c: sr_position(row.get(c)) for c in member_cols},
        })
    return {"declared": declared, "members": members, "votes": votes}


class SrNames:
    """Staenderat spreadsheet member -> PersonNumber. The number row wins when
    the file has one; otherwise last and first name, then canton to split a
    tie. Nothing is guessed: no single match is no match."""

    def __init__(self, conn):
        self.index = {}
        for pn, first, last, canton_name in conn.execute(
                "SELECT person_number, first_name, last_name, canton_name FROM ch_members"):
            key = ((last or "").strip().lower(), (first or "").strip().lower())
            self.index.setdefault(key, []).append((pn, canton_name))

    def resolve(self, m):
        if m.get("person_number"):
            return m["person_number"]
        hits = self.index.get((m["last_name"].lower(), m["first_name"].lower()), [])
        if len(hits) > 1 and m.get("canton_name"):
            hits = [h for h in hits if h[1] == m["canton_name"]]
        return hits[0][0] if len(hits) == 1 else None


def fetch_sr_sheet(client, session_name):
    """(spelling, blob) for a session's spreadsheet, or (None, None) when no
    spelling answers. Each spelling is a real request; a 404 is the answer."""
    for spelling in sr_spellings(session_name):
        url = SR_XLSX.format(urllib.parse.quote(spelling))
        try:
            return spelling, client.get_bytes(url, FEED, "sr-{0}".format(spelling))
        except FetchError:
            continue
    return None, None


def sr_positions(conn, sheet, vote, names, today):
    """(positions, unresolved names) for one Staenderat vote of a parsed sheet."""
    out, unknown = [], []
    for col, m in sheet["members"].items():
        pos = vote["cells"].get(col)
        if not pos:
            continue
        pn = names.resolve(m)
        if pn is None:
            unknown.append("{0}, {1}".format(m["last_name"], m["first_name"]))
            continue
        if m.get("person_number"):
            store_member(conn, {"person_number": pn, "first_name": m["first_name"],
                                "last_name": m["last_name"], "canton_name": m["canton_name"]},
                         today)
        out.append({"person_number": pn, "position": pos, "parl_group": m["parl_group"],
                    "canton": m.get("canton_name")})
    return out, unknown


def pull_sr_session(conn, client, tax, session, today, cache, log=print):
    """Every Staenderat vote of a session. Returns (new, gaps, found)."""
    spelling, blob = fetch_sr_sheet(client, session["name"])
    if blob is None:
        return 0, 0, False
    try:
        sheet = parse_sr_sheet(blob)
    except (ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        _gap(conn, today, "sr sheet {0}: {1}".format(spelling, exc))
        log("  [gap] SR sheet {0}: {1}".format(spelling, exc))
        return 0, 1, True
    cache[session["id"]] = sheet
    gaps = 0
    if sheet["declared"] is not None and sheet["declared"] != len(sheet["votes"]):
        _gap(conn, today, "sr sheet {0}: declares {1} votes, {2} read".format(
            spelling, sheet["declared"], len(sheet["votes"])))
        log("  [gap] SR sheet {0}: declares {1} votes, {2} read".format(
            spelling, sheet["declared"], len(sheet["votes"])))
        gaps += 1
    have = {k for (k,) in conn.execute("SELECT division_key FROM ch_divisions WHERE council='SR'")}
    new = 0
    for v in sheet["votes"]:
        v["session_id"] = session["id"]
        v["short_number"] = ch_store.short_number(v["business_id"]) if v["business_id"] else None
        new += v["key"] not in have
        store_division(conn, tax, v, today)
    conn.commit()
    return new, gaps, True


# --- the run -----------------------------------------------------------------------

def derive_division_areas(conn, tax):
    """Re-derive every division's areas from its own text and its business.
    Cheap and offline; run after businesses arrive and on --reclassify."""
    changed = 0
    for (key, subject, yes_, no_, draft, bid, areas) in conn.execute(
            "SELECT division_key, subject, meaning_yes, meaning_no, draft_title, business_id, "
            "areas FROM ch_divisions").fetchall():
        own, terms, tier = classify_own(tax, {"subject": subject, "meaning_yes": yes_,
                                              "meaning_no": no_, "draft_title": draft})
        new = ch_store.dumps(sorted(set(own) | set(_business_areas(conn, bid))))
        changed += new != (areas or "[]")
        conn.execute("UPDATE ch_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?", (ch_store.dumps(own), new, ch_store.dumps(terms),
                                              tier, key))
    conn.commit()
    return changed


def backfill_positions(conn, client, today, sessions, cache, log=print, budget=None,
                       limit=None):
    """Positions for every division that has none yet: our ground first,
    then the rest (X15, Chris, 10 October 2026: store every member position;
    until then only our ground was read). Returns (filled, gaps)."""
    rows = conn.execute(
        "SELECT division_key, council, vote_id, session_id, areas FROM ch_divisions "
        "WHERE COALESCE(positions, 0) = 0 ORDER BY division_key").fetchall()
    todo = ([r for r in rows if on_our_ground(json.loads(r[4] or "[]"))]
            + [r for r in rows if not on_our_ground(json.loads(r[4] or "[]"))])
    names = SrNames(conn)
    by_id = {s["id"]: s for s in sessions}
    filled = gaps = 0
    for key, council, vote_id, session_id, _areas in todo:
        if limit is not None and filled >= limit:
            log("  position cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("positions", filled))
            break
        if council == "NR":
            try:
                positions = fetch_nr_positions(conn, client, vote_id, today)
            except (FetchError, ValueError) as exc:
                _gap(conn, today, "nr voting {0}: {1}".format(vote_id, exc))
                gaps += 1
                continue
            if not positions:
                _gap(conn, today, "nr voting {0}: no positions published".format(vote_id))
                gaps += 1
                continue
            store_positions(conn, key, positions, tally=True)
        else:
            sheet = cache.get(session_id)
            if sheet is None and session_id in by_id:
                _spelling, blob = fetch_sr_sheet(client, by_id[session_id]["name"])
                sheet = parse_sr_sheet(blob) if blob else None
                cache[session_id] = sheet
            vote = next((v for v in (sheet or {}).get("votes", []) if v["key"] == key), None)
            if vote is None:
                _gap(conn, today, "sr {0}: not in its session sheet".format(key))
                gaps += 1
                continue
            positions, unknown = sr_positions(conn, sheet, vote, names, today)
            if unknown:
                _gap(conn, today, "sr {0}: no PersonNumber for {1}".format(key, "; ".join(unknown)))
                gaps += 1
            store_positions(conn, key, positions)
        conn.commit()
        filled += 1
    return filled, gaps


def session_counts(conn, today, sessions, sr_found, nr_gaps):
    for s in sessions:
        (nr,) = conn.execute("SELECT COUNT(*) FROM ch_divisions WHERE council='NR' AND "
                             "session_id=?", (s["id"],)).fetchone()
        (sr,) = conn.execute("SELECT COUNT(*) FROM ch_divisions WHERE council='SR' AND "
                             "session_id=?", (s["id"],)).fetchone()
        done = None
        ended = s["end"] and (datetime.date.fromisoformat(today) -
                              datetime.date.fromisoformat(s["end"])).days > SESSION_GRACE_DAYS
        sr_needed = bool(sr_spellings(s["name"]))
        if ended and s["id"] not in nr_gaps and (sr_found.get(s["id"]) or not sr_needed):
            done = today
        conn.execute("UPDATE ch_sessions SET nr_votes=?, sr_votes=?, "
                     "complete_at=COALESCE(complete_at, ?) WHERE session_id=?",
                     (nr, sr, done, s["id"]))
    conn.commit()


def pull_divisions(conn, client, tax, today, sessions, log=print, budget=None):
    """Both councils, every session of the legislature that has started and is
    not yet complete. Returns (nr_new, sr_new, gaps, cache, sr_found, nr_gaps)."""
    nr_new = sr_new = gaps = 0
    cache, sr_found, nr_gap_ids = {}, {}, set()
    complete = {i for (i,) in conn.execute(
        "SELECT session_id FROM ch_sessions WHERE complete_at IS NOT NULL")}
    for s in sessions:
        if s["id"] in complete or not s["start"] or s["start"] > today:
            continue
        if budget is not None and budget.exhausted():
            log(budget.disclose("sessions", nr_new + sr_new))
            break
        n_nr, g = pull_nr_session(conn, client, tax, s["id"], today, log=log)
        nr_new += n_nr
        gaps += g
        if g:
            nr_gap_ids.add(s["id"])
        sr_note = "no Staenderat sitting"
        if sr_spellings(s["name"]):
            n_sr, g, found = pull_sr_session(conn, client, tax, s, today, cache, log=log)
            sr_new += n_sr
            gaps += g
            sr_found[s["id"]] = found
            late = s["end"] and (datetime.date.fromisoformat(today) -
                                 datetime.date.fromisoformat(s["end"])).days > SESSION_GRACE_DAYS
            if found:
                sr_note = "{0} new SR".format(n_sr)
            elif late:
                _gap(conn, today, "sr sheet for {0} not published (tried {1})".format(
                    s["name"], ", ".join(sr_spellings(s["name"]))))
                log("  [gap] SR sheet for {0} not found under {1}".format(
                    s["name"], ", ".join(sr_spellings(s["name"]))))
                gaps += 1
                sr_note = "SR sheet missing"
            else:
                sr_note = "SR sheet not out yet (within {0} days of the end)".format(
                    SESSION_GRACE_DAYS)
        log("  {0}: {1} new NR, {2}".format(s["name"], n_nr, sr_note))
    return nr_new, sr_new, gaps, cache, sr_found, nr_gap_ids


def reclassify(conn, client, tax=None, period=CURRENT_PERIOD, log=print):
    """Re-derive every area after a taxonomy or watchlist change.

    NOT OFFLINE, unlike the US: a business's areas come from its submitted
    text as well as its title, and the store keeps titles only (the text of
    10,000 businesses in two languages is tens of megabytes). So the
    legislature's businesses are read again whole (22 pages, about two
    minutes), older businesses a vote names are read one by one, and the
    divisions are then re-derived offline from their own text and their
    business."""
    tax = tax or Taxonomies()
    before = dict(conn.execute("SELECT business_id, areas FROM ch_businesses"))
    today = datetime.date.today().isoformat()
    pull_businesses(conn, client, tax, today, period, log=log, full=True)
    older = [b for (b,) in conn.execute(
        "SELECT business_id FROM ch_businesses WHERE COALESCE(legislative_period, 0) != ?",
        (int(period),))]
    refetch_businesses(conn, client, tax, today, older, log=log)
    fill_italian(conn, client, tax, today, older, log=log)
    after = dict(conn.execute("SELECT business_id, areas FROM ch_businesses"))
    changed_b = sum(1 for k, v in after.items() if before.get(k, "[]") != v)
    changed_d = derive_division_areas(conn, tax)
    log("ch-rollcalls: reclassified; {0} business(es) and {1} division(s) changed area".format(
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t, where="1=1": sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                                      for (a,) in conn.execute(
                                          "SELECT areas FROM {0} WHERE {1}".format(t, where)))
    log("  store: {0} business(es), {1} on our ground; {2} NR and {3} SR division(s), "
        "{4} and {5} on our ground; {6} member(s), {7} position(s)".format(
            n("SELECT COUNT(*) FROM ch_businesses"), ours("ch_businesses"),
            n("SELECT COUNT(*) FROM ch_divisions WHERE council='NR'"),
            n("SELECT COUNT(*) FROM ch_divisions WHERE council='SR'"),
            ours("ch_divisions", "council='NR'"), ours("ch_divisions", "council='SR'"),
            n("SELECT COUNT(*) FROM ch_members"), n("SELECT COUNT(*) FROM ch_votes")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", type=int, default=CURRENT_PERIOD,
                    help="legislative period (default: the 52nd, 2023-2027)")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--no-businesses", action="store_true")
    ap.add_argument("--no-divisions", action="store_true")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-read the legislature's businesses and re-derive every area "
                         "(network: about two minutes)")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many division position fetches")
    ap.add_argument("--dry-run", action="store_true",
                    help="read the latest session's votes and the SR sheet, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    if args.dry_run:
        recs = rows(client.get_json(odata_url("Session", "Language eq 'DE' and "
                                              "LegislativePeriodNumber eq {0}".format(args.period),
                                              SESSION_FIELDS), FEED, "dry-sessions"))
        s = max((parse_session(r) for r in recs), key=lambda x: x["id"])
        votes = rows(client.get_json(odata_url("Vote", "Language eq 'DE' and IdSession eq {0}"
                                               .format(s["id"]), "ID"), FEED, "dry-votes"))
        spelling, blob = fetch_sr_sheet(client, s["name"])
        sr = len(parse_sr_sheet(blob)["votes"]) if blob else "no sheet"
        print("ch-rollcalls: {0}: {1} NR vote(s); SR sheet {2}: {3}".format(
            s["name"], len(votes), spelling, sr))
        return 0
    conn = db.init_db(db.connect(args.db))
    tax = Taxonomies()
    if args.reclassify:
        reclassify(conn, client, tax, args.period)
        summary(conn)
        conn.close()
        return 0
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    sessions = pull_sessions(conn, client, today, args.period)
    since = min(s["start"] for s in sessions if s["start"])
    if not args.no_members:
        print("ch-rollcalls: {0} member(s) sitting since {1}".format(
            pull_members(conn, client, today, since), since))
    if not args.no_businesses:
        pull_businesses(conn, client, tax, today, args.period)
    if not args.no_divisions:
        nr, sr, g, cache, sr_found, nr_gaps = pull_divisions(conn, client, tax, today, sessions,
                                                             budget=budget)
        gaps += g
        print("ch-rollcalls: {0} new NR and {1} new SR division(s), {2} gap(s)".format(nr, sr, g))
        _got, g = pull_missing_businesses(conn, client, tax, today, budget=budget)
        gaps += g
        # CH6: the Italian record of any business still without one (the
        # older ones a vote named, read above in German and French).
        _got, g = fill_italian(conn, client, tax, today, budget=budget)
        gaps += g
        derive_division_areas(conn, tax)
        filled, g = backfill_positions(conn, client, today, sessions, cache, budget=budget,
                                       limit=args.limit)
        gaps += g
        print("ch-rollcalls: positions stored for {0} division(s) on our ground, {1} gap(s)"
              .format(filled, g))
        session_counts(conn, today, sessions, sr_found, nr_gaps)
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
