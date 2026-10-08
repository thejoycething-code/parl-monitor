"""Court watch: Strasbourg judgments as upstream drivers.

    python3 tools/eu_courts.py

Courts create the consultations the monitors later catch -- JR87 created
the NI RE consultation, and ECtHR rulings set the frame member states
legislate under. This watches the EUROPEAN COURT OF HUMAN RIGHTS via
HUDOC's open JSON API (probed 2026-09-02: bare-term query grammar,
kpdate-sorted, 95k+ documents; the fulltext: field syntax silently
returns zero and is NOT used).

A curated term net nominates recent judgments; the taxonomy judges the
case NAME + conclusion text before anything is stored -- same
net-vs-judge split as the speeches collector.

LUXEMBOURG ADDED 2026-09-03. The earlier note said the CJEU was out of
reach: curia retired its RSS routes and InfoCuria is POST-driven, both
still true. What was not tried then is EUR-Lex's own public search,
which answers on a plain GET and parses cleanly -- CELEX id, court,
date and link. So Luxembourg is a BOUNDED read: the judgment's
existence, court and date, never its reasoning, which a human reads on
the page. If the page shape moves, the parse yields ids without titles
and the run records a gap rather than storing blanks.

THE MAC MINI RELAY (8 October 2026). HUDOC began answering 403 to GitHub
Actions with the EU weekly catch-up of that day, while the same query from
the Mac Mini's home connection answers 200 (docs/api-notes.md). Christopher:
"Run the HUDOC search from the Mini". So the Mini runs

    python3 tools/eu_courts.py --relay

each morning (tools/hudoc_relay.sh, launchd), which fetches the same HUDOC
searches and commits their replies to data/hudoc-relay/<term>.json -- it
never touches the store, so ONE WRITER AT A TIME holds. When the live
search is refused here, pull() reads the relay instead if it is at most
RELAY_MAX_AGE_DAYS old, and says so in the log; an older or missing relay
is a gap, as before. Live always comes first: if HUDOC lifts the block,
the relay simply stops being read.

Separation guarantee: writes eu_judgments only (and, with --relay,
data/hudoc-relay/ only).
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import FetchError, HttpClient

QUERY = ("https://hudoc.echr.coe.int/app/query/results?query={0}"
         "&select=itemid,docname,doctype,appno,conclusion,kpdate,"
         "respondent&sort=kpdate%20Descending&start=0&length=50")
CASE = "https://hudoc.echr.coe.int/eng?i={0}"
LOOKBACK_DAYS = 90

SEARCH_TERMS = [
    "abortion", "surrogacy", "euthanasia", "assisted suicide",
    "conversion therapy", "religious freedom", "freedom of religion",
    "gender reassignment", "same-sex parenthood", "home education",
    "freedom of expression religion",
]


EURLEX = ("https://eur-lex.europa.eu/search.html?scope=EURLEX&text={0}"
          "&type=quick&lang=en&DTS_SUBDOM=EU_CASE_LAW"
          "&date0=ALL%3A{1}%7C{2}&sortOne=DD&sortOneOrder=desc")
EURLEX_DOC = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{0}"
# CELEX sector-6 document codes: 62021CJ0621 -> CJ = Court judgment.
CJEU_DOCTYPE = {"CJ": "CJEU judgment", "TJ": "General Court judgment",
                "TB": "General Court order", "CC": "AG opinion",
                "CO": "CJEU order"}


def eurlex_cases(client, term, start, end, log=print):
    """(rows, ok). Bounded parse of EUR-Lex's public case-law search."""
    import re
    url = EURLEX.format(term.replace(" ", "+"),
                        start.strftime("%d%m%Y"), end.strftime("%d%m%Y"))
    try:
        html = client.get_text(url, "eu-courts",
                               "eurlex-" + term.replace(" ", "-"),
                               archive=False)
    except FetchError as exc:
        log("  [gap] eur-lex '{0}': {1}".format(term, exc.cause))
        return [], False
    celex = []
    for cid in re.findall(r"CELEX[%:]3?A?(6\d{4}[A-Z]{2}\d+)", html):
        if cid not in celex:
            celex.append(cid)
    titles = re.findall(r'class="title"[^>]*>([^<]{10,200})', html)
    if celex and not titles:
        log("  [gap] eur-lex '{0}': {1} case id(s) but no titles -- the "
            "page shape moved; storing nothing".format(term, len(celex)))
        return [], False
    rows = []
    for i, cid in enumerate(celex):
        title = " ".join(titles[i].split()) if i < len(titles) else None
        if not title:
            continue
        date = None
        m = re.search(r"of (\d{1,2} \w+ \d{4})", title)
        if m:
            try:
                date = datetime.datetime.strptime(
                    m.group(1), "%d %B %Y").date().isoformat()
            except ValueError:
                date = None
        rows.append({"item_id": "CJEU:" + cid, "case_name": title,
                     "doc_type": CJEU_DOCTYPE.get(cid[5:7], "CJEU"),
                     "app_no": cid, "conclusion": None, "date": date,
                     "respondent": None, "url": EURLEX_DOC.format(cid)})
    return rows, True


RELAY_DIR = os.path.join(ROOT, "data", "hudoc-relay")
RELAY_MAX_AGE_DAYS = 8


def relay_path(term, relay_dir=RELAY_DIR):
    return os.path.join(relay_dir, term.replace(" ", "-") + ".json")


def read_relay(term, today, relay_dir=RELAY_DIR):
    """(reply, fetched_on) from the Mini's relay; reply is None when the
    file is missing, unreadable or older than RELAY_MAX_AGE_DAYS."""
    try:
        with open(relay_path(term, relay_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        fetched = rec["fetched_on"]
        age = (datetime.date.fromisoformat(today)
               - datetime.date.fromisoformat(fetched)).days
    except (OSError, ValueError, KeyError, TypeError):
        return None, None
    if age > RELAY_MAX_AGE_DAYS or not isinstance(rec.get("reply"), dict):
        return None, fetched
    return rec["reply"], fetched


def write_relay(client, today, relay_dir=RELAY_DIR, log=print):
    """The Mini's half: fetch every HUDOC search live and write its reply.
    -> (written, failed). A failed term leaves its previous file alone, so
    the age check, not a blank file, decides whether CI may use it."""
    start = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    os.makedirs(relay_dir, exist_ok=True)
    written = failed = 0
    for term in SEARCH_TERMS:
        try:
            reply = client.get_json(build_query('"{0}"'.format(term), start),
                                    "eu-courts",
                                    term.replace(" ", "-"), archive=False)
        except (FetchError, ValueError) as exc:
            log("  [relay gap] hudoc '{0}': {1}".format(term, exc))
            failed += 1
            continue
        with open(relay_path(term, relay_dir), "w", encoding="utf-8") as fh:
            json.dump({"term": term, "fetched_on": today, "start": start,
                       "reply": reply}, fh, indent=1, sort_keys=True)
            fh.write("\n")
        written += 1
    return written, failed


def hudoc_search(client, term, start, today, log=print, relay_dir=RELAY_DIR):
    """Live first; on refusal, the Mini's relay if fresh; else raise."""
    try:
        return client.get_json(build_query('"{0}"'.format(term), start),
                               "eu-courts",
                               term.replace(" ", "-"), archive=False)
    except (FetchError, ValueError) as exc:
        reply, fetched = read_relay(term, today, relay_dir)
        if reply is None:
            raise
        cause = getattr(exc, "cause", exc)
        log("  hudoc '{0}': refused here ({1}); read the Mac Mini relay "
            "of {2}".format(term, cause, fetched))
        return reply


def build_query(term, start):
    q = ('contentsitename:ECHR AND {0} AND ((languageisocode="ENG")) '
         'AND (kpdate>="{1}")').format(term, start)
    return QUERY.format(urllib.parse.quote(q, safe=""))


def pull(conn, client, today, log=print, relay_dir=RELAY_DIR):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    start = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    known = {r[0] for r in conn.execute("SELECT item_id FROM eu_judgments")}
    seen = stored = gaps = 0
    for term in SEARCH_TERMS:
        try:
            reply = hudoc_search(client, term, start, today, log, relay_dir)
        except (FetchError, ValueError) as exc:
            log("  [gap] hudoc '{0}': {1}".format(term, exc))
            gaps += 1
            continue
        for r in reply.get("results") or []:
            c = r.get("columns") or {}
            item = c.get("itemid")
            if not item or item in known:
                continue
            seen += 1
            name = c.get("docname") or ""
            conclusion = c.get("conclusion") or ""
            res = filt.filter_item(tax, wl, "{0} {1} {2}".format(
                name, conclusion, term))
            areas = res.issue_areas or []
            if not areas:
                continue
            known.add(item)
            stored += 1
            conn.execute(
                "INSERT OR REPLACE INTO eu_judgments (item_id, case_name, "
                "doc_type, app_no, conclusion, date, respondent, url, "
                "areas, matched_terms, tier, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item, name, c.get("doctype"), c.get("appno"),
                 conclusion[:500], str(c.get("kpdate", ""))[:10],
                 c.get("respondent"), CASE.format(item),
                 json.dumps(areas), json.dumps(res.matched_terms or []),
                 res.tier, today, today))
        # Luxembourg, same term, same judge, same table.
        rows, ok = eurlex_cases(client, term,
                                datetime.date.fromisoformat(start),
                                datetime.date.fromisoformat(today), log)
        if not ok:
            gaps += 1
        for row in rows:
            if row["item_id"] in known:
                continue
            seen += 1
            # NOTE on what is actually being judged here. A CJEU
            # search-result title is boilerplate -- "Judgment of the Court
            # (Grand Chamber) of 16 July 2026" -- so the taxonomy has
            # nothing of the case to read, and the SEARCH TERM is passed
            # in with it. That means the term, not the title, supplies the
            # area: the row exists because EUR-Lex matched that phrase in
            # the judgment's full text, which is real evidence the court
            # engaged our vocabulary, but it is NOT an independent
            # judgement of the case. The stored conclusion says which term
            # found it so a reader can weigh that, and the same is true of
            # the HUDOC rows above, whose docname is equally terse.
            res = filt.filter_item(tax, wl, "{0} {1}".format(
                row["case_name"], term))
            areas = res.issue_areas or []
            known.add(row["item_id"])
            stored += 1
            conn.execute(
                "INSERT OR REPLACE INTO eu_judgments (item_id, case_name, "
                "doc_type, app_no, conclusion, date, respondent, url, "
                "areas, matched_terms, tier, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["item_id"], row["case_name"], row["doc_type"],
                 row["app_no"], "found by search term: " + term,
                 row["date"], None, row["url"], json.dumps(areas),
                 json.dumps(res.matched_terms or []), res.tier,
                 today, today))
    conn.commit()
    return seen, stored, gaps


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    if "--relay" in sys.argv[1:]:
        today = datetime.date.today().isoformat()
        written, failed = write_relay(client, today)
        print("hudoc relay: {0} search(es) written to data/hudoc-relay, "
              "{1} failed.".format(written, failed))
        return 1 if failed and not written else 0
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    seen, stored, gaps = pull(conn, client, today)
    total = conn.execute("SELECT COUNT(*) FROM eu_judgments").fetchone()[0]
    print("eu-courts: {0} new candidate(s) inside {1} days, {2} stored on "
          "our ground ({3} held); {4} gap(s).".format(
              seen, LOOKBACK_DAYS, stored, total, gaps))
    for r in conn.execute("SELECT * FROM eu_judgments ORDER BY date DESC "
                          "LIMIT 8").fetchall():
        print("  [{0}] {1} - {2}".format(
            ",".join(str(a) for a in json.loads(r["areas"])),
            r["date"], (r["case_name"] or "")[:70]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
