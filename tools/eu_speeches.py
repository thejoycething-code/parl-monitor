"""MEPs' own words: plenary speeches on our ground, quoted on their cards.

    python3 tools/eu_speeches.py

The Hansard analog for the EP, via the Open Data speeches endpoint --
which turns out to be a full text-search API (probed 2026-09-02):
`?text=<phrase>&sitting-date=...` returns matching speech events, and the
speech detail's `api:xmlFragment` carries the verbatim text in every
language.

Recall comes from a curated set of high-signal search phrases (one API
call each per window); PRECISION stays with the taxonomy, which judges
the fetched English text before anything is stored -- the search terms
cast the net, the filter decides what is ours. One detail fetch per NEW
matched speech.

Separation guarantee: writes eu_speeches only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import FetchError, HttpClient

SEARCH = ("https://data.europarl.europa.eu/api/v2/speeches"
          "?text={0}&search-language=en&sitting-date={1}"
          "&sitting-date-end={2}&limit=50&format=application%2Fld%2Bjson")
DETAIL = ("https://data.europarl.europa.eu/api/v2/speeches/{0}"
          "?include-output=xml_fragment&format=application%2Fld%2Bjson")
LOOKBACK_DAYS = 60

# Recall net: high-signal phrases in the EP's own English. The taxonomy is
# the judge; a phrase here only nominates.
SEARCH_TERMS = [
    "abortion", "assisted dying", "euthanasia", "surrogacy",
    "sexual and reproductive health", "conversion therapy", "chat control",
    "child sexual abuse regulation", "persecution of Christians",
    "religious freedom", "gender ideology", "Istanbul Convention",
    "parenthood certificate", "freedom of expression online",
    # Added 2026-09-03 from the FIRST recall audit (--audit), which
    # measured what the hand-picked net could not reach: "Christian
    # persecution" surfaced the Nigeria debate the curated terms missed
    # outright. The DSA and age-verification phrases came from the same
    # run; their hits were generic debates, kept because the taxonomy
    # still judges every fetched text and a wider net costs one call.
    "Christian persecution", "Digital Services Act", "age verification",
]


def excerpt_en(detail_data):
    """Speaker id and a clean EN excerpt from the speech detail."""
    rec = detail_data.get("recorded_in_a_realization_of") or []
    frag = None
    for r in rec:
        if isinstance(r, dict) and r.get("api:xmlFragment"):
            frag = r["api:xmlFragment"]
            break
    text = ""
    if isinstance(frag, dict):
        text = frag.get("en") or ""
    text = re.sub(r"<[^>]+>", " ", str(text))
    text = " ".join(text.split())
    # Drop the leading "Name , on behalf of the X Group . " prefix the
    # verbatim carries; keep the words themselves.
    text = re.sub(r"^[^.]{0,120}?\.\s*[–-]?\s*", "", text, count=1)
    part = detail_data.get("had_participation") or {}
    if isinstance(part, list):
        part = part[0] if part else {}
    persons = part.get("had_participant_person") or []
    pid = str(persons[0]).rsplit("/", 1)[-1] if persons else None
    return pid, text[:700]


def pull(conn, client, today, log=print, days=None):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    start = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=days or LOOKBACK_DAYS)).isoformat()
    known = {r[0] for r in conn.execute("SELECT speech_id FROM eu_speeches")}
    candidates = {}
    gaps = 0
    for term in SEARCH_TERMS:
        try:
            reply = client.get_json(
                SEARCH.format(term.replace(" ", "%20"), start, today),
                "eu-speeches", term.replace(" ", "-"), archive=False)
        except ValueError:
            continue          # 204: no matches for this phrase
        except FetchError as exc:
            log("  [gap] search '{0}': {1}".format(term, exc.cause))
            gaps += 1
            continue
        for s in reply.get("data") or []:
            sid = s.get("activity_id")
            if sid and sid not in known:
                label = (s.get("activity_label") or {})
                candidates[sid] = (s.get("activity_date"),
                                   label.get("en") if isinstance(label, dict)
                                   else str(label))
    stored = 0
    for sid, (date, debate) in candidates.items():
        try:
            det = client.get_json(DETAIL.format(sid), "eu-speeches", sid,
                                  archive=False)
            d = (det.get("data") or [{}])[0]
        except (FetchError, ValueError) as exc:
            log("  [gap] speech {0}: {1}".format(sid, exc))
            gaps += 1
            continue
        pid, text = excerpt_en(d)
        if not pid or not text:
            continue
        if re.match(r"(The next (vote|item)|The sitting|I declare|"
                    r"The debate is closed|Voting time)", text):
            # The verbatim includes the CHAIR's procedural announcements
            # ("The next vote is on..."), attributed to whoever presides.
            # Found live: the presiding Vice-President "quoted" announcing
            # the Nigeria vote. Not their words on the issue; skipped.
            continue
        res = filt.filter_item(tax, wl, "{0} {1}".format(debate or "", text))
        areas = res.issue_areas or []
        if not areas:
            continue          # the taxonomy is the judge, not the net
        conn.execute(
            "INSERT INTO eu_speeches (speech_id, person_id, date, debate, "
            "excerpt, areas, matched_terms, tier, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(speech_id) DO UPDATE "
            "SET excerpt=excluded.excerpt, last_seen=excluded.last_seen",
            (sid, pid, date, debate, text, json.dumps(areas),
             json.dumps(res.matched_terms or []), res.tier, today, today))
        stored += 1
    conn.commit()
    return len(candidates), stored, gaps


def audit(conn, client, today, log=print):
    """Measure the curated net's RECALL, storing nothing.

    SEARCH_TERMS is a hand-picked net and nothing has ever told us what
    it misses. This runs the taxonomy's OWN tier-1 phrases (the ones long
    enough to be worth a query) as extra searches over the same window,
    and reports speeches they surface that the curated net did not. It
    writes nothing: the answer is a number for a human to act on by
    editing SEARCH_TERMS.
    """
    import yaml
    tax_path = os.path.join(ROOT, "config", "taxonomy.yaml")
    tax = yaml.safe_load(open(tax_path, encoding="utf-8")) or {}
    phrases = []
    for area in (tax.get("areas") or {}).values():
        for term in (area.get("tier1") or []):
            term = str(term).strip('"')
            # multi-word, no wildcards or guards: a phrase a search can use
            if " " in term and "*" not in term and "[" not in term:
                phrases.append(term)
    phrases = sorted(set(phrases) - set(SEARCH_TERMS))
    start = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    known = {r[0] for r in conn.execute("SELECT speech_id FROM eu_speeches")}
    missed = {}
    for phrase in phrases:
        try:
            reply = client.get_json(
                SEARCH.format(phrase.replace(" ", "%20"), start, today),
                "eu-speeches", "audit-" + phrase.replace(" ", "-"),
                archive=False)
        except ValueError:
            continue
        except FetchError as exc:
            log("  [gap] audit '{0}': {1}".format(phrase, exc.cause))
            continue
        for s in reply.get("data") or []:
            sid = s.get("activity_id")
            if sid and sid not in known:
                label = s.get("activity_label") or {}
                missed.setdefault(sid, (
                    label.get("en") if isinstance(label, dict) else "",
                    phrase))
    log("recall audit: {0} extra taxonomy phrase(s) searched over {1} "
        "days; {2} speech(es) the curated net did not reach.".format(
            len(phrases), LOOKBACK_DAYS, len(missed)))
    for sid, (debate, phrase) in list(missed.items())[:12]:
        log("  MISSED via '{0}': {1}".format(phrase, (debate or sid)[:70]))
    if missed:
        log("Add the phrases above to SEARCH_TERMS if the debates are "
            "ours; nothing has been stored.")
    return len(phrases), len(missed)


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    if "--audit" in sys.argv:
        audit(conn, client, today)
        conn.close()
        return 0
    # --days widens the window (17 Sept 2026). These collectors had a fixed
    # 60-day lookback, so when the 9 Sept store rebuild emptied their tables
    # the July plenary was already out of reach and a plain re-run could not
    # recover it. A gap needs a wider window, the way the Westminster
    # backfills do.
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else LOOKBACK_DAYS
    cands, stored, gaps = pull(conn, client, today, days=days)
    total = conn.execute("SELECT COUNT(*) FROM eu_speeches").fetchone()[0]
    print("eu-speeches: {0} candidate(s) in {1} days, {2} stored on our "
          "ground ({3} held in total); {4} gap(s).".format(
              cands, LOOKBACK_DAYS, stored, total, gaps))
    for r in conn.execute("SELECT s.date, s.debate, m.name FROM eu_speeches "
                          "s LEFT JOIN eu_meps m ON m.person_id = "
                          "s.person_id ORDER BY s.date DESC LIMIT 6"):
        print("  {0} {1} - {2}".format(r[0], (r[2] or "?")[:30],
                                       (r[1] or "?")[:60]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
