#!/usr/bin/env python3
"""Hungary, HU7: the 43rd term's papers, recorded votes and member positions,
loaded once from karzat's open data (CC BY 4.0), until the W-API token (HU1).

    python3 tools/hu_karzat_backfill.py               # karzat's newest data commit
    python3 tools/hu_karzat_backfill.py --commit SHA  # a pinned commit
    python3 tools/hu_karzat_backfill.py --force       # reload a commit already loaded
    python3 tools/hu_karzat_backfill.py --reclassify  # offline, after a taxonomy-hu or
                                                      # watchlist-hu change
    python3 tools/hu_karzat_backfill.py --summary [--out FILE]
                                                      # the one-off "since 9 May" read

Chris, 10 October 2026 (HU7: "use karzat's CC BY data with attribution";
docs/hungary-scope.md, "HU7"). A manual job, not a feed: karzat stopped
updating around 28 August 2026, so this is a one-off historical backfill,
run by hand on the Mac Mini (jobs/hu-karzat-backfill.sh, docs/mac-mini.md).
Safe to rerun if karzat ever updates: every write is an upsert on the
parliament's own keys.

THE SOURCE. ONLY karzat's derived files, from its GitHub repository
(github.com/abognar-git/karzat, `data/derived/`; data CC BY 4.0, code MIT),
read at one commit through the GitHub API and raw.githubusercontent.com with
src/http.py. Never parlament.hu (it answers us with a CAPTCHA, which is never
solved or worked around) and never karzat's own site. Four files:

  votes_index.json      every recorded vote of the term: timestamp, mode
                        (the majority rule), tally, result, the motion put
                        and its paper, the tally by group
  votes_positions.json  each member's position on each vote, with the
                        member's group at the vote
  iromany_records.json  every paper (iromány) of the term: number, type,
                        title, status, submitters, promulgation
  mps.json              the term's members, keyed on the parliament's p_azon

Measured on 9 and 10 October 2026, commit 4f932a3a (3 September 2026): 272
votes from 9 May to 28 August 2026, 586 papers, 201 members. Every file is
archived to data/raw/<date>/hu-karzat_* before it is parsed.

KEYS (src/hu_store.py): members on p_azon, papers on their number in the
term ('T/324'), votes on their timestamp ('2026.07.13.18:19:08'), positions
on (vote, member). karzat's positions file names each member by p_azon
('g053', '000P'; MEASURED: 201 of 201 are mps.json keys with the same name);
a code mps.json lacks is joined by name, and one that neither places keeps
'karzat:<code>' and is reported. A motion such
as '324/14' (paper 324's consolidated text) is joined to its paper by the
paper's number in the term, never by title.

PROVENANCE. Every row: source 'karzat@<commit, 12 characters>' and as_of
(the votes: the data's last day; papers and members: karzat's derivation
date). One hu_sources row per load carries the licence and the attribution
the edition shows wherever such a row appears. A row whose source is not
karzat's (the W-API's, once the token arrives) is never overwritten: the
House's own record wins.

CLASSIFICATION. taxonomy-hu on the paper's Hungarian TITLE only (accents
fold, X3); a vote takes its paper's. HU4: a paper titled "Magyarország
Alaptörvényének ... módosítása", and every vote on it, carries rule 'HU4'
and is triaged whatever its words. HU5: a vote on accepting a minister's
answer to an interpellation carries rule 'HU5' and counts as a division, on
our ground when the interpellation is. The watchlist (config/watchlist-hu.yaml,
`papers:`) is applied by paper number.

Separation guarantee: writes hu_members, hu_papers, hu_divisions, hu_votes
and hu_sources only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, hu_store  # noqa: E402

REPO = "abognar-git/karzat"
API = "https://api.github.com/repos/" + REPO
RAW = "https://raw.githubusercontent.com/" + REPO + "/{sha}/data/derived/{name}"
FILES = ("votes_index.json", "votes_positions.json", "iromany_records.json", "mps.json")
FEED = "hu-karzat"
TERM_START = "2026-05-09"        # the 43rd Országgyűlés's inaugural sitting
THROTTLE_S = 1.0
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-hu.yaml")
INTERPELLATION_ANSWER = "interpellációs választ"   # "... az interpellációs választ elfogadta"

_NO_WATCH = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


# --- fetching -------------------------------------------------------------------

def latest_commit(client):
    """The newest commit that touched karzat's data/derived/."""
    got = client.get_json(API + "/commits?path=data/derived&per_page=1", FEED, "commits")
    if not got:
        raise RuntimeError("karzat: no commit touches data/derived")
    return got[0]["sha"]


def fetch(client, sha):
    """{file name: parsed JSON} for FILES at one commit."""
    return {name: client.get_json(RAW.format(sha=sha, name=name), FEED,
                                  "{0}-{1}".format(name.split(".")[0], sha[:12]))
            for name in FILES}


def read_dir(path):
    """{file name: parsed JSON} from a local copy (tests, offline reloads)."""
    out = {}
    for name in FILES:
        with open(os.path.join(path, name), encoding="utf-8") as fh:
            out[name] = json.load(fh)
    return out


# --- classifying ------------------------------------------------------------------

def load_taxonomy(path=TAXONOMY):
    return filt.load_taxonomy(path, country="hu")


def is_amendment(title):
    return bool(hu_store.AMENDMENT.search(hu_store.norm(title)))


def classify_title(tax, title):
    """(areas, terms, tier) from a Hungarian title alone."""
    res = filt.filter_item(tax, _NO_WATCH, title or "")
    return sorted(set(res.issue_areas or [])), list(res.matched_terms or []), res.tier


def classify_paper(tax, wl, key, title):
    """(areas, terms, tier, rule, watched): the title, HU4, the watchlist by key."""
    areas, terms, tier = classify_title(tax, title)
    rule = "HU4" if is_amendment(title) else None
    entry = wl.get(key)
    watched = entry is not None
    if watched:
        areas = sorted(set(areas) | {int(a) for a in (entry.get("areas") or [])})
        tier = tier or 2
    return areas, terms, tier, rule, watched


def classify_division(tax, wl, paper_key, title, motion_kind, outcome):
    """A vote takes its paper's classification; HU4 for an amendment to the
    Fundamental Law, HU5 for a vote on an interpellation answer."""
    areas, terms, tier, rule, watched = classify_paper(tax, wl, paper_key, title)
    if rule is None and (motion_kind == "I" or INTERPELLATION_ANSWER in (outcome or "")):
        rule = "HU5"
    return areas, terms, tier, rule, watched


# --- parsing --------------------------------------------------------------------

def paper_of(motion, by_izon):
    """The paper key a motion names: 'T/324' as it is, '324/14' by izon."""
    m = hu_store.MOTION.match(hu_store.norm(motion))
    if not m:
        return None
    letter, izon, _ = m.groups()
    if letter:
        return "{0}/{1}".format(letter, izon)
    return by_izon.get(izon)


def gazette_issue(promulgation):
    """'2026/92' from karzat's promulgation {mk_issue, date}, or None."""
    if not promulgation or not promulgation.get("mk_issue") or not promulgation.get("date"):
        return None
    return hu_store.issue_key(promulgation["date"][:4], promulgation["mk_issue"])


def _day(stamp):
    return (stamp or "")[:10] or None


# --- storing ----------------------------------------------------------------------

def _upsert(conn, table, key_cols, row):
    """INSERT, or UPDATE every column but first_seen, only over a karzat row:
    the House's own record (any other source) wins."""
    cols = list(row)
    keep = set(key_cols) | {"first_seen"}
    sql = ("INSERT INTO {0} ({1}) VALUES ({2}) ON CONFLICT({3}) DO UPDATE SET {4} "
           "WHERE {0}.source LIKE '{5}@%'").format(
        table, ", ".join(cols), ",".join("?" * len(cols)), ", ".join(key_cols),
        ", ".join("{0}=excluded.{0}".format(c) for c in cols if c not in keep), hu_store.KARZAT)
    conn.execute(sql, [row[c] for c in cols])


def _ours(conn, table, key_col, key):
    got = conn.execute("SELECT source FROM {0} WHERE {1} = ?".format(table, key_col),
                       (key,)).fetchone()
    return got is None or hu_store.is_karzat(got[0])


def load(conn, data, commit, today, tax, wl, since=TERM_START):
    """Write karzat's files into the hu_* tables. Returns a summary dict."""
    source = "{0}@{1}".format(hu_store.KARZAT, commit[:12])
    vi, vp = data["votes_index.json"], data["votes_positions.json"]
    ir, mps = data["iromany_records.json"], data["mps.json"]
    votes_as_of = (vi.get("window") or {}).get("to") or max(
        (v["on_date"] for v in vi["votes"]), default=None)
    papers_as_of = _day(ir.get("derived_at"))
    members_as_of = _day(mps.get("derived_at"))
    s = {"source": source, "members": 0, "papers": 0, "divisions": 0, "positions": 0,
         "unplaced_members": [], "unjoined_motions": [], "kept_house_rows": 0,
         "from": None, "to": None, "as_of": votes_as_of}

    # Members, on p_azon.
    by_name = {}
    for pid, m in (mps.get("mps") or {}).items():
        by_name.setdefault(hu_store.norm(m.get("name")), pid)
        _upsert(conn, "hu_members", ["member_id"], {
            "member_id": pid, "name": m.get("name"), "faction": m.get("faction"),
            "current": int(bool(m.get("current"))), "mandate_kind": m.get("mandate_kind"),
            "county": m.get("county"), "constituency_no": m.get("constituency_no"),
            "mandate_from": m.get("mandate_from"), "mandate_to": m.get("mandate_to"),
            "source": source, "as_of": members_as_of, "first_seen": today, "last_seen": today})
        s["members"] += 1

    # Papers, on their number in the term.
    by_izon, papers = {}, {}
    for key, r in (ir.get("records") or {}).items():
        key = hu_store.norm(r.get("szam") or key)
        by_izon[str(r.get("izon"))] = key
        papers[key] = r
        areas, terms, tier, rule, watched = classify_paper(tax, wl, key, r.get("title"))
        prom = r.get("promulgation") or {}
        _upsert(conn, "hu_papers", ["paper_key"], {
            "paper_key": key, "izon": str(r.get("izon")), "kind": key.split("/")[0],
            "type": r.get("type"), "main_type": r.get("main_type"), "title": r.get("title"),
            "status": r.get("status"), "submitted_on": r.get("submitted_on"),
            "submitters": hu_store.dumps(r.get("submitters")), "addressee": r.get("addressee"),
            "procedure": r.get("procedure_kind"), "promulgated_issue": gazette_issue(prom),
            "promulgated_on": prom.get("date"), "law_ref": prom.get("law_ref"),
            "final_vote_ts": r.get("final_vote_ts"), "url": r.get("text_pdf_url"),
            "areas": hu_store.dumps(areas), "matched_terms": hu_store.dumps(terms),
            "tier": tier, "rule": rule, "watched": int(watched), "source": source,
            "as_of": papers_as_of, "first_seen": today, "last_seen": today})
        s["papers"] += 1

    # Votes, on their timestamp; the term only.
    members = vp.get("members") or {}
    factions = vp.get("factions") or []
    positions = vp.get("positions") or {}
    for v in vi.get("votes") or []:
        if (v.get("on_date") or "") < since:
            continue
        ts = v["ts"]
        motion = (v.get("motions") or [None])[0] or {}
        paper_key = paper_of(motion.get("iromany") or "", by_izon) if motion else None
        if motion and not paper_key:
            s["unjoined_motions"].append(motion.get("iromany"))
        title = (papers.get(paper_key) or {}).get("title") or motion.get("title")
        areas, terms, tier, rule, watched = classify_division(
            tax, wl, paper_key, title, motion.get("kind"), motion.get("outcome"))
        maj = v.get("majority") or {}
        if not _ours(conn, "hu_divisions", "vote_ts", ts):
            s["kept_house_rows"] += 1
            continue
        _upsert(conn, "hu_divisions", ["vote_ts"], {
            "vote_ts": ts, "date": v.get("on_date"), "time": v.get("time"),
            "mode": v.get("mode"), "secret": int(bool(v.get("secret"))), "kind": v.get("kind"),
            "majority": maj.get("rule"), "yes": v.get("igen"), "no": v.get("nem"),
            "abstain": v.get("tartozkodott"), "total": v.get("osszes_szavazat"),
            "passed": None if v.get("passed") is None else int(bool(v["passed"])),
            "result": v.get("result_raw"), "motion": motion.get("iromany"),
            "motion_kind": motion.get("kind"), "outcome": motion.get("outcome"),
            "paper_key": paper_key, "title": title,
            "group_tallies": json.dumps(v.get("faction_tallies") or [], ensure_ascii=False),
            "areas": hu_store.dumps(areas), "matched_terms": hu_store.dumps(terms),
            "tier": tier, "rule": rule, "watched": int(watched), "source": source,
            "as_of": votes_as_of, "first_seen": today, "last_seen": today})
        s["divisions"] += 1
        s["from"] = min(s["from"] or v["on_date"], v["on_date"])
        s["to"] = max(s["to"] or v["on_date"], v["on_date"])
        conn.execute("DELETE FROM hu_votes WHERE vote_ts = ? AND source LIKE ?",
                     (ts, hu_store.KARZAT + "@%"))
        for code, fidx, pos in positions.get(ts) or []:
            who = members.get(code) or {}
            pid = code if code in (mps.get("mps") or {}) else \
                by_name.get(hu_store.norm(who.get("name")))
            if not pid:
                pid = "karzat:" + code
                if pid not in s["unplaced_members"]:
                    s["unplaced_members"].append(pid)
            faction = factions[fidx] if isinstance(fidx, int) and fidx < len(factions) \
                else who.get("faction")
            conn.execute("INSERT OR IGNORE INTO hu_votes (vote_ts, member_id, name, faction, "
                         "position, source, as_of) VALUES (?,?,?,?,?,?,?)",
                         (ts, pid, who.get("name"), faction, hu_store.POSITIONS.get(pos, pos),
                          source, votes_as_of))
            s["positions"] += 1

    conn.execute(
        "INSERT INTO hu_sources (source, name, url, licence, attribution, commit_sha, "
        "derived_at, data_from, data_to, loaded_at, counts) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(source) DO UPDATE SET derived_at=excluded.derived_at, "
        "data_from=excluded.data_from, data_to=excluded.data_to, "
        "loaded_at=excluded.loaded_at, counts=excluded.counts, "
        "attribution=excluded.attribution",
        (source, hu_store.KARZAT, hu_store.KARZAT_URL, hu_store.KARZAT_LICENCE,
         hu_store.KARZAT_ATTRIBUTION, commit, vi.get("derived_at"), s["from"], votes_as_of,
         today, json.dumps({k: s[k] for k in ("members", "papers", "divisions", "positions")})))
    conn.commit()
    return s


def reclassify(conn, tax, wl):
    """Re-derive every karzat paper's and vote's areas, rule and watch flag."""
    n = 0
    for key, title in conn.execute("SELECT paper_key, title FROM hu_papers").fetchall():
        areas, terms, tier, rule, watched = classify_paper(tax, wl, key, title)
        conn.execute("UPDATE hu_papers SET areas=?, matched_terms=?, tier=?, rule=?, watched=? "
                     "WHERE paper_key=?", (hu_store.dumps(areas), hu_store.dumps(terms), tier,
                                           rule, int(watched), key))
        n += 1
    for ts, key, title, kind, outcome in conn.execute(
            "SELECT vote_ts, paper_key, title, motion_kind, outcome FROM hu_divisions").fetchall():
        areas, terms, tier, rule, watched = classify_division(tax, wl, key, title, kind, outcome)
        conn.execute("UPDATE hu_divisions SET areas=?, matched_terms=?, tier=?, rule=?, "
                     "watched=? WHERE vote_ts=?", (hu_store.dumps(areas), hu_store.dumps(terms),
                                                   tier, rule, int(watched), ts))
        n += 1
    conn.commit()
    return n


# --- measuring ----------------------------------------------------------------------

def on_ground_sql(alias=""):
    a = alias + "." if alias else ""
    return "({0}areas != '[]' OR {0}rule = 'HU4' OR {0}watched = 1)".format(a)


def measure(conn):
    """Counts for the report: what is stored and what is on our ground."""
    one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "papers": one("SELECT COUNT(*) FROM hu_papers"),
        "bills": one("SELECT COUNT(*) FROM hu_papers WHERE kind = 'T'"),
        "papers_ours": one("SELECT COUNT(*) FROM hu_papers WHERE " + on_ground_sql()),
        "divisions": one("SELECT COUNT(*) FROM hu_divisions"),
        "divisions_ours": one("SELECT COUNT(*) FROM hu_divisions WHERE " + on_ground_sql()),
        "hu5_ours": one("SELECT COUNT(*) FROM hu_divisions WHERE rule = 'HU5' AND "
                        + on_ground_sql()),
        "positions": one("SELECT COUNT(*) FROM hu_votes"),
        "members": one("SELECT COUNT(*) FROM hu_members"),
        "from": one("SELECT MIN(date) FROM hu_divisions"),
        "to": one("SELECT MAX(date) FROM hu_divisions"),
    }


def cross_check(conn):
    """Each promulgated paper against the gazette collector's store: the issue
    karzat names, its date, and the Act (or amendment) in its contents.
    Returns [(paper, issue, verdict)]; [] when the gazette is not loaded."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='hu_gazette_issues'").fetchone() \
            or not conn.execute("SELECT 1 FROM hu_gazette_issues LIMIT 1").fetchone():
        return []
    out = []
    for key, title, issue, on, law in conn.execute(
            "SELECT paper_key, title, promulgated_issue, promulgated_on, law_ref FROM hu_papers "
            "WHERE promulgated_issue IS NOT NULL AND kind IN ('T', 'H') ORDER BY paper_key"):
        got = conn.execute("SELECT date FROM hu_gazette_issues WHERE issue_key = ?",
                           (issue,)).fetchone()
        if not got:
            out.append((key, issue, "issue not in the gazette store"))
            continue
        if got[0] != on:
            out.append((key, issue, "dates differ: karzat {0}, gazette {1}".format(on, got[0])))
            continue
        if law:
            hit = conn.execute("SELECT 1 FROM hu_gazette_entries WHERE entry_key = ? AND "
                               "issue_key = ?", (law, issue)).fetchone()
        elif is_amendment(title):
            hit = conn.execute("SELECT 1 FROM hu_gazette_entries WHERE type = 'fundamental_law' "
                               "AND issue_key = ? AND entry_key LIKE ?",
                               (issue, hu_store.norm(title) + "%")).fetchone()
        else:
            hit = True        # a resolution: karzat gives no number to look for
        out.append((key, issue, "agrees" if hit else "issue agrees, entry not found"))
    return out


# --- the command ----------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--commit", help="karzat commit to read (default: its newest data commit)")
    ap.add_argument("--from-dir", help="read the four files from this directory, not GitHub "
                                       "(needs --commit)")
    ap.add_argument("--force", action="store_true", help="reload a commit already loaded")
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--summary", action="store_true",
                    help="render the one-off read of the backfill, from 9 May 2026")
    ap.add_argument("--out", help="with --summary: write it here instead of stdout")
    args = ap.parse_args(argv)
    conn = db.connect(args.db)
    hu_store.ensure_schema(conn)
    if args.summary:
        from src.editions import hu
        text = hu.backfill_summary(conn)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            print("hu-karzat: wrote the summary to {0}".format(args.out))
        else:
            print(text)
        return 0
    tax = load_taxonomy()
    wl = hu_store.watchlist()
    if args.reclassify:
        print("hu-karzat: reclassified {0} row(s)".format(reclassify(conn, tax, wl)))
        return 0
    today = datetime.date.today().isoformat()
    if args.from_dir:
        if not args.commit:
            ap.error("--from-dir needs --commit (the karzat commit the files came from)")
        data, commit = read_dir(args.from_dir), args.commit
    else:
        from src.http import HttpClient
        client = HttpClient(raw_dir=args.raw_dir, throttle=THROTTLE_S)
        commit = args.commit or latest_commit(client)
        source = "{0}@{1}".format(hu_store.KARZAT, commit[:12])
        if not args.force and conn.execute("SELECT 1 FROM hu_sources WHERE source = ?",
                                           (source,)).fetchone():
            print("hu-karzat: {0} is already loaded; nothing to do (--force reloads it)"
                  .format(source))
            return 0
        data = fetch(client, commit)
    s = load(conn, data, commit, today, tax, wl)
    m = measure(conn)
    print("hu-karzat: loaded {0}: {1} member(s), {2} paper(s), {3} vote(s) from {4} to {5}, "
          "{6} position(s); data as of {7}".format(s["source"], s["members"], s["papers"],
                                                   s["divisions"], s["from"], s["to"],
                                                   s["positions"], s["as_of"]))
    print("hu-karzat: store: {0} paper(s) ({1} bills), {2} on our ground; {3} vote(s), {4} on "
          "our ground ({5} interpellation answers, HU5); {6} position(s)".format(
              m["papers"], m["bills"], m["papers_ours"], m["divisions"], m["divisions_ours"],
              m["hu5_ours"], m["positions"]))
    if s["unplaced_members"]:
        print("  [gap] {0} member code(s) not joined to a p_azon: {1}".format(
            len(s["unplaced_members"]), ", ".join(s["unplaced_members"][:10])))
    if s["unjoined_motions"]:
        print("  [gap] {0} motion(s) not joined to a paper: {1}".format(
            len(s["unjoined_motions"]), ", ".join(s["unjoined_motions"][:10])))
    if s["kept_house_rows"]:
        print("  {0} vote(s) already held from the House's own record were left as they are"
              .format(s["kept_house_rows"]))
    checks = cross_check(conn)
    if checks:
        agree = sum(1 for *_, v in checks if v == "agrees")
        print("hu-karzat: gazette cross-check: {0} of {1} promulgated bills and resolutions "
              "agree".format(agree, len(checks)))
        for key, issue, verdict in checks:
            if verdict != "agrees":
                print("  {0} (Magyar Közlöny {1}): {2}".format(key, issue, verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main())
