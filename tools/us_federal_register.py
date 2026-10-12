#!/usr/bin/env python3
"""The US executive: presidential documents, final rules and proposed rules
from the Federal Register, with their comment-period close dates.

    python3 tools/us_federal_register.py                    # since the last stored date
    python3 tools/us_federal_register.py --since 2025-01-20 # the first backfill
    python3 tools/us_federal_register.py --reclassify       # re-derive areas, offline
    python3 tools/us_federal_register.py --db /tmp/us.db    # anywhere but the store

Christopher, 9 October 2026: yes to an executive-actions section in the US
edition. In the US much of our ground moves by executive order and agency
rule, not statute: the January 2025 orders on gender ideology, the Hyde
Amendment and the Mexico City Policy were each a single document here.

THE SOURCE is federalregister.gov/api/v1/documents.json: open, keyless,
official, JSON. Three document types are read, PRESDOCU (executive orders,
proclamations, memoranda, determinations, notices), RULE and PRORULE.
Agency NOTICES are not: about 10,000 since January 2025, nearly all permits,
meetings and information collections. One query per window, 1,000 documents
a page; every page is archived to data/raw before it is parsed.

INCREMENTAL BY PUBLICATION DATE. A run asks for everything published since
the latest date stored, less OVERLAP_DAYS, so a correction or a reopened
comment period published a few days late is re-seen and the table's
last_seen moves every week (tools/coverage.py watches it). The first run
starts at FIRST_DATE, 20 January 2025, the inauguration. The API stops
paging at 10,000 results, so a window that reports more is split in two.

WHAT IS MATCHED: title, abstract, action line and the CFR index terms,
title first (src/filter.py's convention), through the shared taxonomy.
Not the body: a rule's full text cites everything around it, as a
judgment's does. Presidential documents have no abstract, so they match on
the title alone; an executive order's title is usually its subject
("Enforcing the Hyde Amendment"), but some on our ground are missed
(docs/us-scope.md lists the ones seen).

NOISE, MEASURED on the 7,972 documents of 20 January 2025 to 9 October 2026:
  * "euthanasia" never reaches the matched text. The phrase is in 13 FR
    documents, all animal welfare and all in the body, which is not read.
  * pollutant "surrogates", wildlife contraceptives and "unborn" livestock
    were vetoed in the taxonomy itself (v1.18).
  * the CFR index term "Adoption and foster care" is printed on every
    8 CFR immigration rule; it is dropped where the same document carries
    "Aliens" or "Immigration" (CFR_BOILERPLATE below), and nowhere else.
Area 11 (migration) is stored and never shown, as everywhere.

Separation guarantee: writes us_fr_documents, the shared gaps table and its
own source_runs heartbeat only. ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, us_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "us-federal-register"
HEARTBEAT = "US Federal Register"
API = "https://www.federalregister.gov/api/v1/documents.json"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
TYPES = ("PRESDOCU", "RULE", "PRORULE")
FIRST_DATE = "2025-01-20"
OVERLAP_DAYS = 14
PER_PAGE = 1000
API_CAP = 10000
HIDDEN_AREAS = (11,)
FIELDS = ("document_number", "title", "type", "subtype", "abstract", "action",
          "publication_date", "agencies", "html_url", "comments_close_on", "effective_on",
          "executive_order_number", "signing_date", "topics", "docket_ids",
          "regulations_dot_gov_url", "significant", "citation")
# The CFR index printed on every Title 8 (immigration) rule includes
# "Adoption and foster care", because 8 CFR also governs adoptee visas.
# Matched as-is it filed three USCIS rules (biometrics, EB-5, a visa grace
# period) under parental rights. Dropped only in that company.
CFR_BOILERPLATE = {"Adoption and foster care": ("Aliens", "Immigration")}


def query_url(since, until, page=1):
    params = [("per_page", PER_PAGE), ("page", page), ("order", "oldest"),
              ("conditions[publication_date][gte]", since),
              ("conditions[publication_date][lte]", until)]
    params += [("conditions[type][]", t) for t in TYPES]
    params += [("fields[]", f) for f in FIELDS]
    return API + "?" + urllib.parse.urlencode(params)


def parse_document(r):
    """One API result -> the row's fields, or None without a document number."""
    if not r.get("document_number") or not r.get("publication_date"):
        return None
    return {
        "document_number": r["document_number"],
        "doc_type": r.get("type") or "?",
        "subtype": r.get("subtype"),
        "title": " ".join((r.get("title") or "").split()) or None,
        "abstract": " ".join((r.get("abstract") or "").split()) or None,
        "action": " ".join((r.get("action") or "").split()) or None,
        "agencies": [a.get("name") or a.get("raw_name") for a in (r.get("agencies") or [])
                     if a.get("name") or a.get("raw_name")],
        "topics": list(r.get("topics") or []),
        "publication_date": r["publication_date"],
        "signing_date": r.get("signing_date"),
        "effective_on": r.get("effective_on"),
        "comments_close_on": r.get("comments_close_on"),
        "eo_number": (str(r["executive_order_number"])
                      if r.get("executive_order_number") else None),
        "citation": r.get("citation"),
        "docket_ids": list(r.get("docket_ids") or []),
        "comment_url": r.get("regulations_dot_gov_url"),
        "html_url": r.get("html_url"),
        "significant": None if r.get("significant") is None else int(bool(r["significant"])),
    }


def classified_topics(topics):
    """The CFR index terms that are matched: all of them, less boilerplate."""
    have = set(topics or [])
    return [t for t in topics or []
            if not (t in CFR_BOILERPLATE and have & set(CFR_BOILERPLATE[t]))]


def classify(tax, wl, d):
    return filt.filter_item(tax, wl, d["title"] or "", d["abstract"] or "", d["action"] or "",
                            "; ".join(classified_topics(d["topics"])), title=d["title"] or "")


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def store_document(conn, d, res, today):
    conn.execute(
        "INSERT INTO us_fr_documents (document_number, doc_type, subtype, title, abstract, "
        "action, agencies, topics, publication_date, signing_date, effective_on, "
        "comments_close_on, eo_number, citation, docket_ids, comment_url, html_url, "
        "significant, areas, matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(document_number) DO UPDATE SET doc_type=excluded.doc_type, "
        "subtype=excluded.subtype, title=excluded.title, abstract=excluded.abstract, "
        "action=excluded.action, agencies=excluded.agencies, topics=excluded.topics, "
        "publication_date=excluded.publication_date, signing_date=excluded.signing_date, "
        "effective_on=excluded.effective_on, comments_close_on=excluded.comments_close_on, "
        "eo_number=excluded.eo_number, citation=excluded.citation, "
        "docket_ids=excluded.docket_ids, comment_url=excluded.comment_url, "
        "html_url=excluded.html_url, significant=excluded.significant, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen",
        (d["document_number"], d["doc_type"], d["subtype"], d["title"], d["abstract"],
         d["action"], us_store.dumps(d["agencies"]), us_store.dumps(d["topics"]),
         d["publication_date"], d["signing_date"], d["effective_on"], d["comments_close_on"],
         d["eo_number"], d["citation"], us_store.dumps(d["docket_ids"]), d["comment_url"],
         d["html_url"], d["significant"], us_store.dumps(res.issue_areas),
         us_store.dumps(res.matched_terms), res.tier, today, today))


def fetch_window(client, since, until, log=print):
    """Every document published in [since, until], split while the API's
    10,000 cap would truncate it. Raises FetchError on a failed page."""
    first = client.get_json(query_url(since, until), FEED,
                            "documents-{0}-{1}-p1".format(since, until))
    count = int(first.get("count") or 0)
    if count > API_CAP and since < until:
        a, b = datetime.date.fromisoformat(since), datetime.date.fromisoformat(until)
        mid = a + (b - a) // 2
        log("  {0} documents {1} to {2}: over the API's cap, split".format(count, since, until))
        return (fetch_window(client, since, mid.isoformat(), log)
                + fetch_window(client, (mid + datetime.timedelta(days=1)).isoformat(), until, log))
    results, page, data = list(first.get("results") or []), 1, first
    pages = int(first.get("total_pages") or 1)
    while page < pages:
        page += 1
        data = client.get_json(query_url(since, until, page), FEED,
                               "documents-{0}-{1}-p{2}".format(since, until, page))
        results += list(data.get("results") or [])
    return results


def start_date(conn):
    (latest,) = conn.execute("SELECT MAX(publication_date) FROM us_fr_documents").fetchone()
    if not latest:
        return FIRST_DATE
    since = datetime.date.fromisoformat(latest) - datetime.timedelta(days=OVERLAP_DAYS)
    return max(since.isoformat(), FIRST_DATE)


def stamp(conn, today):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/us_federal_register.py"))
    conn.commit()


def pull(conn, client, today, since=None, until=None, tax=None, log=print):
    """Returns (read, ours, gaps)."""
    us_store.ensure_schema(conn)
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    since = since or start_date(conn)
    until = until or today
    try:
        results = fetch_window(client, since, until, log)
    except (FetchError, ValueError) as exc:
        db.record_gap(conn, FEED, "documents {0} to {1}: {2}".format(since, until, exc), today)
        return 0, 0, 1
    read = ours = 0
    by_type = {}
    for r in results:
        d = parse_document(r)
        if d is None:
            continue
        res = classify(tax, wl, d)
        store_document(conn, d, res, today)
        read += 1
        if on_our_ground(res.issue_areas):
            ours += 1
            by_type[d["doc_type"]] = by_type.get(d["doc_type"], 0) + 1
    conn.commit()
    log("us-federal-register: {0} to {1}: {2} document(s) read, {3} on our ground ({4})".format(
        since, until, read, ours, ", ".join("{0} {1}".format(n, t) for t, n in sorted(by_type.items()))
        or "none"))
    return read, ours, 0


def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def reclassify(conn, tax=None, log=print):
    """Re-derive every stored document's areas, offline, after a taxonomy change."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    changed = 0
    for row in conn.execute("SELECT document_number, title, abstract, action, topics, areas "
                            "FROM us_fr_documents").fetchall():
        d = {"title": row[1], "abstract": row[2], "action": row[3],
             "topics": json.loads(row[4] or "[]")}
        res = classify(tax, wl, d)
        new = us_store.dumps(res.issue_areas)
        changed += new != (row[5] or "[]")
        conn.execute("UPDATE us_fr_documents SET areas=?, matched_terms=?, tier=? "
                     "WHERE document_number=?",
                     (new, us_store.dumps(res.matched_terms), res.tier, row[0]))
    conn.commit()
    log("us-federal-register: reclassified; {0} document(s) changed area".format(changed))
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--since", help="ISO date; default: the latest stored, less {0} days".format(
        OVERLAP_DAYS))
    ap.add_argument("--until", help="ISO date; default: today")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored documents, offline")
    args = ap.parse_args()
    conn = db.init_db(db.connect(args.db))
    today = datetime.date.today().isoformat()
    if args.reclassify:
        reclassify(conn)
        conn.close()
        return 0
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    _read, _ours, gaps = pull(conn, client, today, since=args.since, until=args.until)
    if not gaps:
        stamp(conn, today)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
