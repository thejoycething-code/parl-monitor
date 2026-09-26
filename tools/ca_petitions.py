#!/usr/bin/env python3
"""House of Commons of Canada petitions, paper and electronic.

    python3 tools/ca_petitions.py                    # new, open, and owed a refresh
    python3 tools/ca_petitions.py --limit 200        # a bigger bite
    python3 tools/ca_petitions.py --db /tmp/ca.db
    python3 tools/ca_petitions.py --only e-7000      # one page, for debugging

GROUNDWORK, phase 2 (26 September 2026). Nothing schedules this.

THE ROUTE, AND THE ONE NOT TAKEN. The petitions search posts to
/petitions/en/Petition/SearchAsync, and that form carries a reCAPTCHA token;
the XML export behind it is triggered from the same form. The endpoint
answers without a token, but a collector built on a form guarded by bot
detection is not one this project runs. Everything here reads the public
Details page for ONE petition by GET -- the page anyone following a link
from Hansard or an MP's newsletter lands on.

TWO NUMBER SPACES, BOTH WALKED.
  * PRESENTED petitions are numbered 451-00001 upwards with no holes (1,218
    by 26 September 2026), paper and electronic alike: an e-petition gets a
    451- number when an MP presents it, and 451-01121 serves the e-7000 page.
    So walking 451- upwards finds every petition the House has received.
    The walk stops at three consecutive empty pages.
  * OPEN e-petitions are not presented yet, so they have only an e- number,
    and those are SPARSE: e-7810 was live while e-7800..e-7815 around it
    were empty (drafts not yet published). They are found by probing a
    window around the highest e- number seen. An unpublished number answers
    200 with an EMPTY body, so a probe costs almost nothing. This is the
    early-warning layer: a petition on our ground while it is still
    gathering signatures, as at Westminster.

REFRESH. A petition on our ground is refetched while it can still change --
open for signature, or presented and awaiting the government's response --
because signatures and the response are the facts that matter.

Every petition read is stored, on our ground or not; the prayer text is
short, and a list that stores only matches cannot show it looked. The
government's RESPONSE text is stored on our ground only.

ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmlmod
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ca-petitions"
DETAILS = "https://www.ourcommons.ca/petitions/en/Petition/Details?Petition={0}"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")
PRESENTED_PREFIX = "451"      # 45th Parliament, 1st session
EMPTY_RUN = 3                 # consecutive empty 451- pages that end the walk
# The highest e- number seen live on 26 September 2026. Only a seed for an
# empty store: once any e-petition is stored, the window follows the data.
E_SEED = 7810
E_BACK, E_AHEAD = 150, 40
DEFAULT_LIMIT = 60
HIDDEN_AREAS = (11,)

MONTH_DATE = re.compile(r"([A-Z][a-z]+ \d{1,2}, \d{4})")
TAG = re.compile(r"<[^>]+>")


def _clean(fragment):
    return " ".join(htmlmod.unescape(TAG.sub(" ", fragment or "")).split())


def iso_date(text):
    """'February 12, 2026, at 10:57 a.m. (EDT)' -> '2026-02-12', else None."""
    hit = MONTH_DATE.search(text or "")
    if not hit:
        return None
    try:
        return datetime.datetime.strptime(hit.group(1), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def _section(page, cls):
    """Inner HTML of the first <div class="cls ..."> up to its balanced end."""
    hit = re.search(r'<div[^>]+class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*>', page)
    if not hit:
        return ""
    depth, i = 1, hit.end()
    for m in re.finditer(r"<(/?)div\b[^>]*>", page[i:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return page[i:i + m.start()]
    return page[i:]


def parse_details(page):
    """One petition's fields, or None for an unpublished number (empty body)."""
    if not page or not page.strip():
        return None
    h1 = re.search(r"<h1[^>]*>\s*([^<]+?)\s*</h1>", page)
    if not h1:
        return None
    head = _clean(h1.group(1))
    hit = re.match(r"^(e-\d+|\d{3}-\d{5})\s*(?:\((.*)\))?$", head)
    if not hit:
        return None
    pid, category = hit.group(1), hit.group(2)
    keywords = [_clean(k) for k in re.findall(
        r'<li class="indexDetails">\s*<a[^>]*>(.*?)</a>', page, re.S)]
    intro = _section(page, "introDetails")
    kind = ("Paper petition" if "Paper petition" in intro
            else "E-petition" if "E-petition" in intro else None)
    prayer_html = _section(page, "pet-prayer")
    addressee = re.search(r"<h3[^>]*>(.*?)</h3>", prayer_html, re.S)
    prayer = _clean(re.sub(r"<h3[^>]*>.*?</h3>", " ", prayer_html, count=1, flags=re.S))
    history = {}
    hist_html = _section(page, "history-section")
    for dt, dd in re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", hist_html, re.S):
        history[_clean(dt)] = dd
    presented = history.get("Presented to the House of Commons", "")
    number = re.search(r"Petition No\.\s*(\d{3}-\d{5})", _clean(presented))
    mp = re.search(r"members/[^\"'()]*\((\d+)\)\"?[^>]*>(.*?)</a>", presented, re.S) \
        or re.search(r"members/[^\"'()]*\((\d+)\)\"?[^>]*>(.*?)</a>", page, re.S)
    sigs = re.search(r"([\d,]+)\s+signatures?\s*</h2>", page)
    resp = _section(page, "pet-reponse")
    resp_by = re.search(r'<h3 class="title">(.*?)</h3>', resp, re.S)
    resp_text = " ".join(_clean(p) for p in re.findall(
        r'<p class="rep-para">(.*?)</p>', resp, re.S))
    return {
        "petition_id": pid,
        "presented_number": number.group(1) if number else (pid if not pid.startswith("e-") else None),
        "kind": kind,
        "category": category,
        "keywords": keywords,
        "addressee": _clean(addressee.group(1)) if addressee else None,
        "prayer": prayer or None,
        "opened": iso_date(_clean(history.get("Open for signature", ""))),
        "closed": iso_date(_clean(history.get("Closed for signature", ""))),
        "presented": iso_date(_clean(presented)),
        "mp_person_id": mp.group(1) if mp else None,
        "mp_name": _clean(mp.group(2)) if mp else None,
        "response_tabled": iso_date(_clean(history.get("Government response tabled", ""))),
        "response_by": _clean(resp_by.group(1)) if resp_by else None,
        "response_text": resp_text or None,
        "signatures": int(sigs.group(1).replace(",", "")) if sigs else None,
    }


def classify(tax, wl, p):
    return filt.filter_item(tax, wl, " ".join([p["category"] or ""] + p["keywords"]),
                            p["prayer"] or "")


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def store(conn, p, res, today):
    ours = on_our_ground(res.issue_areas)
    conn.execute(
        "INSERT INTO ca_petitions (petition_id, presented_number, kind, category, "
        "keywords, addressee, prayer, opened, closed, presented, mp_person_id, "
        "mp_name, response_tabled, response_by, response_text, signatures, areas, "
        "matched_terms, tier, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(petition_id) DO UPDATE SET "
        "presented_number=COALESCE(excluded.presented_number, ca_petitions.presented_number), "
        "kind=excluded.kind, category=excluded.category, keywords=excluded.keywords, "
        "addressee=excluded.addressee, prayer=excluded.prayer, opened=excluded.opened, "
        "closed=excluded.closed, presented=excluded.presented, "
        "mp_person_id=excluded.mp_person_id, mp_name=excluded.mp_name, "
        "response_tabled=excluded.response_tabled, response_by=excluded.response_by, "
        "response_text=excluded.response_text, signatures=excluded.signatures, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (p["petition_id"], p["presented_number"], p["kind"], p["category"],
         json.dumps(p["keywords"], ensure_ascii=False), p["addressee"], p["prayer"],
         p["opened"], p["closed"], p["presented"], p["mp_person_id"], p["mp_name"],
         p["response_tabled"], p["response_by"] if ours else None,
         p["response_text"] if ours else None, p["signatures"],
         json.dumps(res.issue_areas or []),
         json.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today))
    return ours


class Run:
    """One run's fetch budget, counters and gap log."""

    def __init__(self, conn, client, today, tax, wl, limit, budget, log):
        self.conn, self.client, self.today = conn, client, today
        self.tax, self.wl, self.limit, self.budget, self.log = tax, wl, limit, budget, log
        self.fetched = self.stored = self.ours = self.gaps = self.empty = 0
        self.stopped = None

    def spent(self):
        if self.limit is not None and self.fetched >= self.limit:
            self.stopped = self.stopped or ("fetch cap ({0}) reached; the rest lands on "
                                            "the next run -- disclosed, not silent".format(self.limit))
            return True
        if self.budget is not None and self.budget.exhausted():
            self.stopped = self.stopped or self.budget.disclose("petition pages", self.fetched)
            return True
        return False

    def read(self, number):
        """Fetch and store one number. True = a petition, False = empty, None = gap."""
        self.fetched += 1
        try:
            page = self.client.get_text(DETAILS.format(number), FEED,
                                        "petition-" + number, archive=False)
        except FetchError as exc:
            self.conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                              (self.today, FEED, "{0}: {1}".format(number, exc)))
            self.log("  [gap] {0}: {1}".format(number, str(exc)[:70]))
            self.gaps += 1
            return None
        p = parse_details(page)
        if p is None:
            self.empty += 1
            return False
        if store(self.conn, p, classify(self.tax, self.wl, p), self.today):
            self.ours += 1
        self.stored += 1
        self.conn.commit()
        return True


def highest_presented(conn, prefix=PRESENTED_PREFIX):
    best = 0
    for (num,) in conn.execute("SELECT presented_number FROM ca_petitions "
                               "WHERE presented_number LIKE ?", (prefix + "-%",)):
        best = max(best, int(num.split("-")[1]))
    return best


def highest_e(conn):
    best = 0
    for (pid,) in conn.execute("SELECT petition_id FROM ca_petitions WHERE petition_id LIKE 'e-%'"):
        best = max(best, int(pid[2:]))
    return best


def walk_presented(run, prefix=PRESENTED_PREFIX, start=None):
    n, misses = start or highest_presented(run.conn, prefix) + 1, 0
    while misses < EMPTY_RUN and not run.spent():
        got = run.read("{0}-{1:05d}".format(prefix, n))
        if got is None:
            break           # a failed page is a gap; do not walk past it
        misses = 0 if got else misses + 1
        n += 1


def probe_open(run, back=E_BACK, ahead=E_AHEAD):
    # The seed is a FLOOR, not a default. The 451- walk stores PRESENTED
    # e-petitions, which are older, so on 26 September the highest stored was
    # e-7719 and a window centred there skipped every open petition from
    # e-7760 up -- including e-7810, live that morning.
    top = max(highest_e(run.conn), E_SEED)
    have = {r[0] for r in run.conn.execute("SELECT petition_id FROM ca_petitions "
                                           "WHERE petition_id LIKE 'e-%'")}
    # Newest first: the early-warning value is at the frontier.
    for n in range(top + ahead, max(top - back, 0), -1):
        if run.spent():
            return
        pid = "e-{0}".format(n)
        if pid not in have:
            run.read(pid)


def refresh_owed(run):
    """Our petitions that can still change: open, or awaiting a response."""
    rows = run.conn.execute(
        "SELECT petition_id FROM ca_petitions WHERE areas NOT IN ('[]','[11]') "
        "AND response_tabled IS NULL AND last_seen < ? ORDER BY last_seen",
        (run.today,)).fetchall()
    for (pid,) in rows:
        if run.spent():
            return
        run.read(pid)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="page fetches per run")
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--only", help="fetch and print one petition number, store nothing")
    ap.add_argument("--skip-open", action="store_true", help="do not probe open e-petitions")
    ap.add_argument("--from-presented", type=int,
                    help="start the 451- walk here instead of after the highest stored")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    if args.only:
        p = parse_details(client.get_text(DETAILS.format(args.only), FEED,
                                          "petition-" + args.only, archive=False))
        print(json.dumps(p, indent=2, ensure_ascii=False) if p else "{0}: not published".format(args.only))
        return 0
    conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    run = Run(conn, client, today, filt.load_taxonomy(TAXONOMY),
              filt.load_watchlist(WATCHLIST), args.limit,
              drain.Budget(args.budget_seconds), print)
    # Order is the priority: what can change on our ground, then what is new.
    refresh_owed(run)
    walk_presented(run, start=args.from_presented)
    if not args.skip_open:
        probe_open(run)
    if run.stopped:
        print("  " + run.stopped)
    print("ca-petitions: {0} page(s) fetched, {1} petition(s) stored, {2} on our "
          "ground, {3} unpublished number(s), {4} gap(s).".format(
              run.fetched, run.stored, run.ours, run.empty, run.gaps))
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    print("  store: {0} petition(s), {1} on our ground, highest presented {2}-{3:05d}, "
          "highest e-{4}".format(
              n("SELECT COUNT(*) FROM ca_petitions"),
              n("SELECT COUNT(*) FROM ca_petitions WHERE areas NOT IN ('[]','[11]')"),
              PRESENTED_PREFIX, highest_presented(conn), highest_e(conn)))
    conn.close()
    return 1 if run.gaps else 0


if __name__ == "__main__":
    sys.exit(main())
