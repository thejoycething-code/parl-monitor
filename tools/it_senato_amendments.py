#!/usr/bin/env python3
"""The Italian Senate's amendment texts, from the Senate's own repository
(12 October 2026, Chris: "Yes, build it").

    python3 tools/it_senato_amendments.py                       # the weekly step
    python3 tools/it_senato_amendments.py --act 19/S.1735 19/S.824 [--force]
    python3 tools/it_senato_amendments.py --link-only           # offline: re-link the stored texts
    python3 tools/it_senato_amendments.py --db /tmp/scratch.db --act 19/S.824

WHAT. For every Senate act named by a Senate vote on our ground (watched, or
tier 1 with an area: src/country5ca.qualifying, the 5CA's own ground) whose
wording names an amendment or order of the day, it reads the act's
amendment files from github.com/SenatoDellaRepubblica/AkomaNtosoBulkData
(updated daily by the Senate; no bot check), stores them in
it_senate_amendments and links each vote to its text in
it_senate_amendment_votes (src/it_amendments.py says how; a split vote,
"1a parte", is flagged, never guessed).

HOW, within GitHub's anonymous limits (60 API requests an hour):
  1. the act's idFase, from dati.senato.it SPARQL (osr:fase "S.1735" ->
     osr:idFase 59761): one query for every act not mapped yet, kept in
     it_senate_amend_acts;
  2. ONE git trees API request per act (Leg19/Atto<idFase>, recursive): the
     emend (Assembly) and emendc (committee) files with their blob shas;
     an act whose tree sha is unchanged since the last read is done;
  3. each NEW or CHANGED file from raw.githubusercontent.com (not the API),
     its git blob sha checked against the tree's; a file whose sha is
     stored already is never fetched again.
An act is re-read when it was never read, when it has a vote on our ground
in the last 90 days, or when its last read is 28 days old (--force reads
every act named). At most --max-api API requests a run (default 30), never
below 5 left on GitHub's counter (X-RateLimit-Remaining), and at most
--max-files raw files (default 2500); what is left over is a [gap] line and
read on the next run. GITHUB_TOKEN is used for api.github.com only if it is
already in the runner's environment; it is never written anywhere, sent in
a header and never in a URL.

ROBOTS. dati.senato.it/sparql, api.github.com and raw.githubusercontent.com
are documented machine endpoints (src/robots_guard.DOCUMENTED_APIS): the
first two serve programs by design, and github.com's robots.txt points
crawlers to its API; raw.githubusercontent.com and api.github.com answer
404 for robots.txt (no rules; checked 12 October 2026). The client is
src/robots_guard.guard(), so anything else would ask robots.txt first.
Identified UA (src/http.py). Downloaded content is data: parsed with
ElementTree into strings, never executed or followed.

Exit 0, or 3 when it stored what it could and recorded gaps (the gaps table
and [gap] lines): jobs/it-weekly.sh treats any failure as a [gap] line,
never the run's.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, it_amendments as ia, it_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import guard  # noqa: E402

FEED = "it-senato-amendments"
SENATO_SPARQL = "https://dati.senato.it/sparql"
BUDGET_S = 600
MAX_API = 30
MIN_REMAINING = 5
MAX_FILES = 2500
RECENT_DAYS = 90
STALE_DAYS = 28


def _gap(conn, today, detail, log=print):
    log("  [gap] " + detail)
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    conn.commit()


# --- which acts --------------------------------------------------------------------

def ground_divisions(conn):
    """The Senate divisions on our ground (country5ca's qualifying: watched,
    or tier 1 with an area) whose wording names an amendment number."""
    from src import country5ca as c5
    keys = [r["key"] for r in c5.qualifying(conn, "it") if r.get("chamber") == "senato"]
    out = []
    for i in range(0, len(keys), 400):
        part = keys[i:i + 400]
        out += ia._rows(conn, "SELECT division_key, title, bill_key, bill_keys, date FROM it_divisions "
                              "WHERE division_key IN ({0})".format(",".join("?" * len(part))), part)
    return [r for r in out if ia.vote_numbers(r.get("title"))[0]]


def acts_named(divisions):
    """{act: newest vote date} over the divisions."""
    acts = {}
    for r in divisions:
        for a in ia.senate_acts(r):
            acts[a] = max(acts.get(a) or "", str(r.get("date") or "")[:10])
    return acts


def due(state, newest, today, force=False):
    """Whether an act's folder is read on this run."""
    if force or not state or not state.get("checked"):
        return True
    t = datetime.date.fromisoformat(today)
    try:
        if newest and (t - datetime.date.fromisoformat(newest)).days <= RECENT_DAYS:
            return True
        return (t - datetime.date.fromisoformat(state["checked"])).days >= STALE_DAYS
    except ValueError:
        return True


# --- the source -------------------------------------------------------------------

def q_id_fase(acts):
    fasi = ", ".join('"{0}"'.format(a.split("/", 1)[1].replace('"', "")) for a in acts)
    legs = sorted({int(a.split("/", 1)[0]) for a in acts})
    return ("PREFIX osr: <http://dati.senato.it/osr/>\n"
            "SELECT ?leg ?fase ?f WHERE {{ ?d a osr:Ddl ; osr:legislatura ?leg ; osr:fase ?fase ; "
            "osr:idFase ?f . FILTER(?leg IN ({0})) FILTER(STR(?fase) IN ({1})) }}").format(
                ", ".join(str(x) for x in legs), fasi)


def parse_id_fase(data):
    """{'19/S.1735': 59761} from a SPARQL JSON answer."""
    out = {}
    for b in (data.get("results") or {}).get("bindings") or []:
        try:
            out["{0}/{1}".format(int(b["leg"]["value"]), b["fase"]["value"].strip())] = int(b["f"]["value"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def fetch_id_fase(client, acts):
    url = SENATO_SPARQL + "?" + urllib.parse.urlencode(
        {"query": q_id_fase(acts), "format": "application/sparql-results+json"})
    raw = client.get_bytes(url, FEED, "idfase")
    return parse_id_fase(json.loads(raw.decode("utf-8"), strict=False))


def parse_tree(data, folder):
    """(tree sha, [(path in repo, sede, blob sha)]) for an act's tree answer."""
    files = []
    for t in data.get("tree") or []:
        if t.get("type") != "blob" or not str(t.get("path", "")).endswith(".xml"):
            continue
        top = t["path"].split("/", 1)[0]
        if top in ia.FOLDERS:
            files.append(("{0}/{1}".format(folder, t["path"]), ia.FOLDERS[top], t.get("sha")))
    return data.get("sha"), files


class Api:
    """GitHub API requests within a per-run cap and GitHub's own counter."""

    def __init__(self, client, cap=MAX_API, token=None):
        self.client, self.cap, self.used, self.remaining = client, cap, 0, None
        self.token = token

    def spent(self):
        return self.used >= self.cap or (self.remaining is not None and self.remaining < MIN_REMAINING)

    def get_json(self, url, slug):
        self.used += 1
        if self.token:   # a header only, never the URL; the reply is not archived (keyed)
            raw = self.client.get_bytes(url, FEED, slug, headers={
                "Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json"})
        else:
            raw = self.client.get_bytes(url, FEED, slug)
        try:
            self.remaining = int((getattr(self.client, "last_headers", None) or {}).get(
                "X-RateLimit-Remaining", self.remaining))
        except (TypeError, ValueError):
            pass
        return json.loads(raw.decode("utf-8"))


def _not_found(exc):
    return getattr(getattr(exc, "cause", None), "code", None) == 404


# --- storing ----------------------------------------------------------------------

def store_file(conn, path, sede, sha, parsed, id_fase, today):
    act = parsed.get("act")
    conn.execute(
        "INSERT INTO it_senate_amendments (file_path, legislature, act, id_fase, sede, number, number_norm, "
        "kind, proposers, text, presented, frbr_uri, file_sha, url, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(file_path) DO UPDATE SET "
        "legislature=excluded.legislature, act=excluded.act, id_fase=excluded.id_fase, sede=excluded.sede, "
        "number=excluded.number, number_norm=excluded.number_norm, kind=excluded.kind, "
        "proposers=excluded.proposers, text=excluded.text, presented=excluded.presented, "
        "frbr_uri=excluded.frbr_uri, file_sha=excluded.file_sha, url=excluded.url, "
        "last_seen=excluded.last_seen",
        (path, parsed.get("legislature"), act, id_fase, parsed.get("sede") or sede, parsed["number"],
         ia.norm(parsed["number"]) if parsed["number"] else None, parsed.get("kind"), json.dumps(parsed.get("proposers") or [],
                                                                    ensure_ascii=False),
         parsed.get("text"), parsed.get("presented"), parsed.get("frbr_uri"), sha,
         ia.BLOB_URL.format(path=path), today, today))


def read_act(conn, client, api, act, id_fase, state, today, files_left, log=print):
    """Read one act's folder. Returns (new or changed files stored, files
    fetched, gaps, done): done is False when a cap stopped it part-way."""
    leg = int(act.split("/", 1)[0])
    folder = ia.act_folder(leg, id_fase)
    try:
        data = api.get_json(ia.TREE_URL.format(folder=folder), "tree-" + folder.replace("/", "-"))
    except FetchError as e:
        if _not_found(e):        # the Senate has published no folder for this reading
            conn.execute("UPDATE it_senate_amend_acts SET files=0, checked=?, last_seen=? WHERE act=?",
                         (today, today, act))
            conn.commit()
            log("it-senato-amendments: {0} ({1}): no folder in the repository".format(act, folder))
            return 0, 0, 0, True
        _gap(conn, today, "{0}: the folder listing was not read ({1})".format(act, str(e)[:160]), log)
        return 0, 0, 1, False
    tree_sha, files = parse_tree(data, folder)
    if data.get("truncated"):
        _gap(conn, today, "{0}: GitHub truncated the folder listing; some files may be missing".format(act), log)
    if state and state.get("tree_sha") == tree_sha and state.get("checked"):
        conn.execute("UPDATE it_senate_amend_acts SET checked=?, last_seen=? WHERE act=?", (today, today, act))
        conn.execute("UPDATE it_senate_amendments SET last_seen=? WHERE file_path LIKE ?", (today, folder + "/%"))
        conn.commit()
        log("it-senato-amendments: {0}: unchanged since {1} ({2} files)".format(act, state["checked"], len(files)))
        return 0, 0, 0, True
    have = {r["file_path"]: r["file_sha"] for r in ia._rows(
        conn, "SELECT file_path, file_sha FROM it_senate_amendments WHERE file_path LIKE ?", (folder + "/%",))}
    stored = fetched = gaps = 0
    done = True
    for path, sede, sha in files:
        if have.get(path) == sha:
            conn.execute("UPDATE it_senate_amendments SET last_seen=? WHERE file_path=?", (today, path))
            continue
        if fetched >= files_left:
            done = False
            break
        try:
            raw = client.get_bytes(ia.RAW_URL.format(path=path), FEED, path.replace("/", "-"), archive=False)
        except FetchError as e:
            gaps += 1
            _gap(conn, today, "{0}: {1} not read ({2})".format(act, path, str(e)[:120]), log)
            continue
        fetched += 1
        if sha and ia.git_blob_sha(raw) != sha:
            gaps += 1
            _gap(conn, today, "{0}: {1} does not match the listed sha (a newer copy is on its way); "
                              "read next run".format(act, path), log)
            continue
        parsed = ia.parse_akn(raw)
        if not parsed and ia.is_empty_akn(raw):
            # The Senate publishes the odd empty document (Leg19/Atto00059761/emend/
            # 01503340-em.akn.xml, 12 October 2026): kept as a row with no number,
            # so its sha is known and it is not fetched again, and noted, not a gap.
            parsed = {"number": None, "act": act, "legislature": leg, "sede": sede}
            log("  note: {0} is an empty document; kept with no number".format(path))
        elif not parsed:
            gaps += 1
            _gap(conn, today, "{0}: {1} is not an Akoma Ntoso amendment".format(act, path), log)
            continue
        if not parsed.get("act"):
            parsed["act"], parsed["legislature"] = act, leg
        store_file(conn, path, sede, sha, parsed, id_fase, today)
        stored += 1
        if stored % 200 == 0:
            conn.commit()
    if done and not gaps:
        conn.execute("UPDATE it_senate_amend_acts SET tree_sha=?, files=?, checked=?, last_seen=? WHERE act=?",
                     (tree_sha, len(files), today, today, act))
    else:   # read again in full next run (the tree sha is not recorded)
        conn.execute("UPDATE it_senate_amend_acts SET files=?, checked=?, last_seen=? WHERE act=?",
                     (len(files), today, today, act))
    conn.commit()
    return stored, fetched, gaps, done


def summary(conn, acts=None):
    where, params = "", ()
    if acts:
        where = " WHERE act IN ({0})".format(",".join("?" * len(acts)))
        params = tuple(acts)
    for r in ia._rows(conn, "SELECT act, sede, COUNT(*) AS n, SUM(kind LIKE 'Ordine%') AS odg FROM "
                            "it_senate_amendments WHERE number IS NOT NULL{0} GROUP BY act, sede ORDER BY act, sede".format(
                                where.replace(" WHERE", " AND")), params):
        print("  {0:<20} {1}  {2:>5} file(s), {3} order(s) of the day".format(
            r["act"], "Assembly " if r["sede"] == "A" else "committee", r["n"], r["odg"] or 0))
    for r in ia._rows(conn, "SELECT status, COUNT(*) AS n FROM it_senate_amendment_votes GROUP BY status "
                            "ORDER BY status"):
        print("  votes -> texts: {0:<10} {1}".format(r["status"], r["n"]))


def main(argv=None, client=None, today=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--act", nargs="*", help="read these acts ('19/S.1735') instead of the ground's")
    ap.add_argument("--force", action="store_true", help="read every act named, due or not")
    ap.add_argument("--link-only", action="store_true", help="offline: re-link the stored texts")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--max-api", type=int, default=MAX_API)
    ap.add_argument("--max-files", type=int, default=MAX_FILES)
    args = ap.parse_args(argv)
    conn = db.init_db(db.connect(args.db))
    it_store.ensure_schema(conn)
    today = today or datetime.date.today().isoformat()
    divisions = ground_divisions(conn)
    named = acts_named(divisions)
    if args.link_only:
        print("it-senato-amendments: links {0}".format(ia.link(conn, divisions, today)))
        summary(conn)
        conn.close()
        return 0
    wanted = {a: named.get(a, "") for a in (args.act or named)}
    client = client or guard(HttpClient(raw_dir=os.path.join(ROOT, "data", "raw")), FEED)
    api = Api(client, args.max_api, os.environ.get("GITHUB_TOKEN") or None)
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    states = {r["act"]: r for r in ia._rows(conn, "SELECT * FROM it_senate_amend_acts")}
    for a in wanted:
        if a not in states:
            conn.execute("INSERT OR IGNORE INTO it_senate_amend_acts (act, first_seen, last_seen) VALUES (?,?,?)",
                         (a, today, today))
            states[a] = {"act": a}
    conn.commit()
    todo = [a for a in sorted(wanted, key=lambda a: wanted[a] or "", reverse=True)
            if due(states.get(a), wanted[a], today, args.force or bool(args.act))]
    unmapped = [a for a in todo if not states[a].get("id_fase")]
    if unmapped:
        try:
            got = fetch_id_fase(client, unmapped)
        except (FetchError, ValueError) as e:
            got = {}
            gaps += 1
            _gap(conn, today, "dati.senato.it: the idFase of {0} act(s) was not read ({1})".format(
                len(unmapped), str(e)[:160]))
        for a, f in got.items():
            conn.execute("UPDATE it_senate_amend_acts SET id_fase=? WHERE act=?", (f, a))
            if a in states:
                states[a]["id_fase"] = f
        conn.commit()
        for a in unmapped:
            if not states[a].get("id_fase") and got:
                # The query answered but not for this act: checked, so it is asked
                # again only when it falls due (28 days), not every run.
                conn.execute("UPDATE it_senate_amend_acts SET files=0, checked=?, last_seen=? WHERE act=?",
                             (today, today, a))
                print("it-senato-amendments: {0}: no idFase on dati.senato.it; skipped".format(a))
        conn.commit()
    print("it-senato-amendments: {0} act(s) named by votes on our ground, {1} due{2}".format(
        len(named), len(todo), " (acts given: {0})".format(", ".join(args.act)) if args.act else ""))
    files_left = args.max_files
    left_over = []
    for a in todo:
        st = states.get(a) or {}
        if not st.get("id_fase"):
            continue
        if budget.exhausted() or api.spent() or files_left <= 0:
            left_over.append(a)
            continue
        stored, fetched, g, done = read_act(conn, client, api, a, st["id_fase"], st, today, files_left)
        files_left -= fetched
        gaps += g
        if not done:
            left_over.append(a)
        if stored or fetched:
            print("it-senato-amendments: {0}: {1} file(s) fetched, {2} stored".format(a, fetched, stored))
    if left_over:
        gaps += 1
        _gap(conn, today, "{0} act(s) left for the next run (API cap {1}, GitHub remaining {2}, files {3}, "
                          "time {4:.0f}s): {5}".format(len(left_over), args.max_api, api.remaining,
                                                       args.max_files, args.budget_seconds,
                                                       ", ".join(left_over[:10])))
    print("it-senato-amendments: {0} GitHub API request(s) used (remaining {1})".format(api.used, api.remaining))
    print("it-senato-amendments: links {0}".format(ia.link(conn, divisions, today)))
    summary(conn, list(wanted))
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
