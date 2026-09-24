"""The judge evaluation corpus (Christopher, 2026-09-07).

The judge -- triage.score_live, one Sonnet call per twenty items -- decides
what the edition shows and what it says about it, and until today nothing
recorded its verdicts beyond the current store row, nothing asked a human
whether they were right, and a change of prompt or model could not be
measured. The daily briefing project learned this the hard way and banks
its labels; this is the same idea for the monitor.

Three parts.
  BANK    every live verdict, every week: what the judge saw (the title,
          tier, candidate areas), what it said (score, why), which model
          and which prompt (by hash). Table judge_verdicts, exported to
          data/eval/<week>.jsonl so git holds the history.
  SAMPLE  ten of the week's verdicts, stratified by score, written to
          reviews/judge-sample-<week>.md in the review file's own style.
          Christopher writes VERDICT: 0-3 (and a NOTE if he likes); the
          next Monday publish ingests it. His PRIORITY edits in
          review-<week>.md are read too, as implicit verdicts.
  REPORT  agreement over the labelled bank: exact, within one, over and
          under, a confusion matrix, and precision/recall for "belongs in
          the digest" (score >= 2). By month, so drift shows. And a
          RESCORE that re-runs the current judge over labelled items and
          compares -- the only honest test of a new prompt or model, and
          it spends money, so it asks first.

Concordance measures agreement, not correctness: the human verdict is the
truth here, the judge is what is measured. Ten a week is a habit; a
hundred labels is a corpus.
"""

from __future__ import annotations

import datetime
import hashlib
import glob
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, "data", "eval")
SAMPLE_SIZE = 10
PRIORITY_SCORE = {"ACT": 3, "WATCH": 2, "NOTE": 1}


# Which judge produced a verdict. The feed comes from the item id's own
# prefix ("de_vorgaenge:337053" -> "de_vorgaenge"), so this needs no new
# column and works on every row already banked.
#
# POOLING JURISDICTIONS WOULD BE WORSE THAN NOT MEASURING. Westminster, the
# EU and Germany run DIFFERENT system prompts over different taxonomies, and
# Germany's is an AI draft no German speaker has verified, read by a matcher
# built for English. One agreement figure across all three would describe
# none of them -- and would flatter Germany, which has a fraction of the
# labelled rows.
JURISDICTIONS = (("de_", "Germany"), ("eu_", "the EU"))


def jurisdiction_of(feed):
    for prefix, label in JURISDICTIONS:
        if (feed or "").startswith(prefix):
            return label
    return "Westminster"


def prompt_sha(system_prompt):
    return hashlib.sha256((system_prompt or "").encode("utf-8")).hexdigest()[:12]


def ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS judge_verdicts (
        week TEXT NOT NULL, item_id TEXT NOT NULL,
        feed TEXT, title TEXT, tier INTEGER, candidate_areas TEXT, watchlist_hit INTEGER,
        score INTEGER, why TEXT, areas TEXT,
        model TEXT, prompt_sha TEXT, mode TEXT,
        human_score INTEGER, human_note TEXT, human_source TEXT, labelled_at TEXT,
        captured_at TEXT NOT NULL,
        PRIMARY KEY (week, item_id))""")
    conn.commit()


def bank(conn, week, items, results, model, mode, system_prompt, captured_at=None):
    """Record what the judge saw and said. Stub verdicts are banked too
    (mode='stub') so a stub week is visible, but they are never measured."""
    ensure_table(conn)
    captured_at = captured_at or datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    by_id = {i.id: i for i in items}
    n = 0
    for r in results:
        it = by_id.get(r.id)
        if it is None:
            continue
        conn.execute(
            "INSERT INTO judge_verdicts (week, item_id, feed, title, tier, candidate_areas, watchlist_hit, "
            "score, why, areas, model, prompt_sha, mode, captured_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(week, item_id) DO UPDATE SET score=excluded.score, why=excluded.why, areas=excluded.areas, "
            "model=excluded.model, prompt_sha=excluded.prompt_sha, mode=excluded.mode, captured_at=excluded.captured_at",
            (week, it.id, it.id.split(":", 1)[0], it.title, it.tier, json.dumps(it.issue_areas),
             int(bool(it.watchlist_hit)), r.score, r.why_it_matters or "", json.dumps(r.areas or []),
             model, prompt_sha(system_prompt), mode, captured_at))
        n += 1
    conn.commit()
    return n


def export(conn, week, path=None):
    """One JSON line per verdict of the week, committed so git holds the history."""
    ensure_table(conn)
    # A test that runs the triage pass on an in-memory store must not write
    # the repo's export files: it did, and a test item ("a:1", week
    # 2026-08-10) was committed twice before anyone saw it (2026-09-07).
    if path is None and not _on_disk(conn):
        return None, 0
    path = path or os.path.join(EVAL_DIR, "{0}.jsonl".format(week))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = conn.execute("SELECT * FROM judge_verdicts WHERE week = ? ORDER BY item_id", (week,)).fetchall()
    with open(path, "w", encoding="utf-8") as handle:
        for r in rows:
            handle.write(json.dumps(dict(r), sort_keys=True, ensure_ascii=False) + "\n")
    return path, len(rows)


def restore(conn, eval_dir=None):
    """Load every data/eval/<week>.jsonl back into judge_verdicts. Returns rows added.

    The export exists so git holds the history; this is the other direction, for a
    store that came back without the bank (the 2026-09-09 rebuild: 72 verdicts across
    five weeks, all on disk, none in the store). INSERT OR IGNORE: a row the store
    already has -- perhaps carrying a human label added since -- is left alone.
    """
    ensure_table(conn)
    eval_dir = eval_dir or EVAL_DIR
    added = 0
    for path in sorted(glob.glob(os.path.join(eval_dir, "*.jsonl"))):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                cols = sorted(row)
                cur = conn.execute("INSERT OR IGNORE INTO judge_verdicts ({0}) VALUES ({1})".format(
                    ", ".join(cols), ", ".join("?" * len(cols))), [row[c] for c in cols])
                added += cur.rowcount if cur.rowcount > 0 else 0
    conn.commit()
    return added


def _on_disk(conn):
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        return bool(row and row[2])
    except Exception:                                       # noqa: BLE001
        return False


# -- the sample -------------------------------------------------------------------

SAMPLE_HEADER = """# Judge sample for the edition of {week}

Ten of this week's {total} live verdicts, chosen across the scores. For each,
write the score YOU would give on the VERDICT line (0 = irrelevant to every
area, 1 = background only, 2 = belongs in the weekly digest, 3 = likely
campaign or lobbying trigger). A NOTE is optional: say what the judge got
wrong when it did. Leave VERDICT blank to skip an item. The next Monday
publish reads this file; agreement over time is in docs/judge-eval.md.

Do not edit the `### item:` id lines.

---
"""


def pick_sample(rows, n=SAMPLE_SIZE, seed=None):
    """Stratified by score: at least two from each score present, then fill
    proportionally. Deterministic for a given seed (the week)."""
    rng = random.Random(seed)
    by_score = {}
    for r in rows:
        by_score.setdefault(r["score"], []).append(r)
    for bucket in by_score.values():
        rng.shuffle(bucket)
    chosen = []
    for s in sorted(by_score):
        chosen.extend(by_score[s][:2])
    rest = [r for s in sorted(by_score) for r in by_score[s][2:]]
    rng.shuffle(rest)
    chosen.extend(rest[:max(0, n - len(chosen))])
    return chosen[:max(n, min(len(rows), len(chosen)))] if len(chosen) > n else chosen


def write_sample(conn, week, path, n=SAMPLE_SIZE, jurisdiction=None):
    """Ten of the week's verdicts for a human to check.

    jurisdiction scopes the sample ("Germany", "Westminster", "the EU"). A
    reviewer checking the German judge should not be handed Westminster
    written questions: the frames differ, the taxonomies differ, and the
    verdict they give would be measured against the wrong prompt.
    """
    ensure_table(conn)
    rows = conn.execute("SELECT * FROM judge_verdicts WHERE week = ? AND mode != 'stub' AND score IS NOT NULL "
                        "ORDER BY item_id", (week,)).fetchall()
    if jurisdiction:
        rows = [r for r in rows if jurisdiction_of(r["feed"]) == jurisdiction]
    if not rows:
        return None, 0
    chosen = pick_sample(rows, n, seed=week)
    blocks = [SAMPLE_HEADER.format(week=week, total=len(rows))]
    for r in chosen:
        blocks.append("### item: {0}".format(r["item_id"]))
        blocks.append("- feed: {0} | judge score: {1} | tier: {2} | candidate areas: {3}".format(
            r["feed"], r["score"], r["tier"], ", ".join(str(a) for a in json.loads(r["candidate_areas"] or "[]")) or "-"))
        blocks.append("- title: {0}".format(r["title"]))
        blocks.append("- judge why: {0}".format(r["why"] or "-"))
        blocks.append("VERDICT: ")
        blocks.append("NOTE: ")
        blocks.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(blocks))
    return path, len(chosen)


def parse_sample(path):
    """-> [(item_id, verdict, note)] for items with a VERDICT written."""
    out, cur, verdict, note = [], None, None, ""
    week = re.search(r"judge-sample-(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.startswith("### item:"):
                if cur and verdict is not None:
                    out.append((cur, verdict, note))
                cur, verdict, note = line.split("item:", 1)[1].strip(), None, ""
            elif line.upper().startswith("VERDICT:"):
                v = line.split(":", 1)[1].strip()
                verdict = int(v) if v.isdigit() and 0 <= int(v) <= 3 else None
            elif line.upper().startswith("NOTE:"):
                note = line.split(":", 1)[1].strip()
    if cur and verdict is not None:
        out.append((cur, verdict, note))
    return (week.group(1) if week else None), out


def ingest_samples(conn, reviews_dir, today=None):
    """Read every judge-sample-*.md and review-*.md; write human verdicts.
    A sample VERDICT is explicit truth; a review PRIORITY (ACT/WATCH/NOTE)
    is an implicit one and never overwrites an explicit verdict."""
    ensure_table(conn)
    today = today or datetime.date.today().isoformat()
    explicit = implicit = 0
    if not os.path.isdir(reviews_dir):
        return explicit, implicit
    for name in sorted(os.listdir(reviews_dir)):
        path = os.path.join(reviews_dir, name)
        if name.startswith("judge-sample-") and name.endswith(".md"):
            week, rows = parse_sample(path)
            for item_id, verdict, note in rows:
                cur = conn.execute("UPDATE judge_verdicts SET human_score = ?, human_note = ?, human_source = 'sample', "
                                   "labelled_at = COALESCE(labelled_at, ?) WHERE item_id = ? AND week = ?",
                                   (verdict, note or None, today, item_id, week))
                explicit += cur.rowcount
        elif name.startswith("review-") and name.endswith(".md"):
            m = re.search(r"review-(\d{4}-\d{2}-\d{2})", name)
            if not m:
                continue
            from src import review as _review
            for e in _review.parse_review_file(path):
                pr = (e.get("priority") or "").upper()
                if pr not in PRIORITY_SCORE:
                    continue
                cur = conn.execute("UPDATE judge_verdicts SET human_score = ?, human_source = 'review', "
                                   "labelled_at = COALESCE(labelled_at, ?) WHERE item_id = ? AND week = ? "
                                   "AND (human_source IS NULL OR human_source != 'sample')",
                                   (PRIORITY_SCORE[pr], today, e["id"], m.group(1)))
                implicit += cur.rowcount
    conn.commit()
    return explicit, implicit


# -- the report -------------------------------------------------------------------

def stats(rows):
    """Agreement figures over labelled (score, human_score) pairs."""
    pairs = [(r["score"], r["human_score"]) for r in rows if r["score"] is not None and r["human_score"] is not None]
    n = len(pairs)
    out = {"n": n}
    if not n:
        return out
    out["exact"] = sum(1 for s, h in pairs if s == h) / n
    out["within_one"] = sum(1 for s, h in pairs if abs(s - h) <= 1) / n
    out["over"] = sum(1 for s, h in pairs if s > h)
    out["under"] = sum(1 for s, h in pairs if s < h)
    tp = sum(1 for s, h in pairs if s >= 2 and h >= 2)
    fp = sum(1 for s, h in pairs if s >= 2 and h < 2)
    fn = sum(1 for s, h in pairs if s < 2 and h >= 2)
    out["digest_precision"] = tp / (tp + fp) if tp + fp else None
    out["digest_recall"] = tp / (tp + fn) if tp + fn else None
    matrix = [[0] * 4 for _ in range(4)]
    for s, h in pairs:
        matrix[min(max(h, 0), 3)][min(max(s, 0), 3)] += 1
    out["matrix"] = matrix          # rows = human, columns = judge
    return out


def _pct(x):
    return "-" if x is None else "{0:.0f}%".format(x * 100)


def report(conn, write_to=None, today=None):
    ensure_table(conn)
    today = today or datetime.date.today().isoformat()
    rows = conn.execute("SELECT * FROM judge_verdicts WHERE mode != 'stub'").fetchall()
    # SPLIT, never pooled: see JURISDICTIONS. Each judge is measured against
    # its own labels, and a jurisdiction with no labels says so rather than
    # borrowing another's score.
    by_j = {}
    for r in rows:
        by_j.setdefault(jurisdiction_of(r["feed"]), []).append(r)
    labelled = [r for r in rows if r["human_score"] is not None]
    out = ["# Judge evaluation", "",
           "*Agreement between the judge's score and a human verdict on the same item. The human verdict is the "
           "truth here; this measures the judge. Generated {0}.*".format(today), "",
           "Banked verdicts: {0} live. Labelled: {1} ({2} by explicit sample verdict, {3} by review priority).".format(
               len(rows), len(labelled), sum(1 for r in labelled if r["human_source"] == "sample"),
               sum(1 for r in labelled if r["human_source"] == "review")), ""]

    # PER JURISDICTION, BEFORE the pooled figures, so the first table anyone
    # reads is the honest one. Westminster, the EU and Germany run different
    # prompts over different taxonomies; a single agreement number describes
    # none of them, and with 202 Westminster rows against a couple of hundred
    # German ones it would be Westminster's figure wearing a German label.
    out += ["## By jurisdiction", "",
            "*Each judge measured against its own labels. A jurisdiction with "
            "no labelled verdicts shows a dash: it has not been checked, "
            "which is not the same as agreeing.*", "",
            "| Jurisdiction | Banked | Labelled | Exact | Within one | "
            "Digest precision |", "|---|---|---|---|---|---|"]
    for name in sorted(by_j):
        got = by_j[name]
        lab = [r for r in got if r["human_score"] is not None]
        js = stats(lab)
        out.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
            name, len(got), len(lab),
            _pct(js["exact"]) if js["n"] else "-",
            _pct(js["within_one"]) if js["n"] else "-",
            _pct(js["digest_precision"]) if js["n"] else "-"))
    out.append("")
    unchecked = [n for n in sorted(by_j)
                 if not any(r["human_score"] is not None for r in by_j[n])]
    if unchecked:
        out.append("**Never checked by a human: {0}.** Those judges are "
                   "unmeasured, and every surface built on them rests on an "
                   "assumption rather than evidence.".format(
                       ", ".join(unchecked)))
        out.append("")
    s = stats(labelled)
    if s["n"]:
        out += ["## Overall (all jurisdictions pooled)", "",
                "*Kept for the long run of Westminster history. Read the "
                "table above first: pooling judges with different prompts "
                "flatters whichever has fewest labels.*", "",
                "| Labelled | Exact agreement | Within one | Judge over | Judge under | Digest precision | Digest recall |",
                "|---|---|---|---|---|---|---|",
                "| {0} | {1} | {2} | {3} | {4} | {5} | {6} |".format(
                    s["n"], _pct(s["exact"]), _pct(s["within_one"]), s["over"], s["under"],
                    _pct(s["digest_precision"]), _pct(s["digest_recall"])), "",
                "*Digest precision: of what the judge put in the edition (score 2 or 3), the share a human agreed "
                "belonged. Digest recall: of what a human said belonged, the share the judge caught.*", "",
                "## Confusion matrix (rows = human verdict, columns = judge score)", "",
                "| Human \\\\ Judge | 0 | 1 | 2 | 3 |", "|---|---|---|---|---|"]
        for h in range(4):
            out.append("| **{0}** | {1} | {2} | {3} | {4} |".format(h, *s["matrix"][h]))
        out.append("")
        by_month = {}
        for r in labelled:
            by_month.setdefault((r["week"] or "")[:7], []).append(r)
        out += ["## By month", "", "| Month | Labelled | Exact | Within one | Digest precision | Digest recall | Models |",
                "|---|---|---|---|---|---|---|"]
        for month in sorted(by_month):
            m = stats(by_month[month])
            models = sorted({r["model"] or "?" for r in by_month[month]})
            out.append("| {0} | {1} | {2} | {3} | {4} | {5} | {6} |".format(
                month, m["n"], _pct(m.get("exact")), _pct(m.get("within_one")),
                _pct(m.get("digest_precision")), _pct(m.get("digest_recall")), ", ".join(models)))
        out.append("")
        by_feed = {}
        for r in labelled:
            by_feed.setdefault(r["feed"] or "?", []).append(r)
        out += ["## By feed", "", "| Feed | Labelled | Exact | Within one |", "|---|---|---|---|"]
        for feed in sorted(by_feed, key=lambda f: -len(by_feed[f])):
            m = stats(by_feed[feed])
            out.append("| {0} | {1} | {2} | {3} |".format(feed, m["n"], _pct(m.get("exact")), _pct(m.get("within_one"))))
        out.append("")
        notes = [r for r in labelled if r["human_note"]]
        if notes:
            out += ["## What the human said the judge got wrong", ""]
            for r in sorted(notes, key=lambda r: r["week"], reverse=True)[:30]:
                out.append("- {0} ({1}, judge {2} / human {3}): {4}".format(
                    (r["title"] or "")[:90], r["week"], r["score"], r["human_score"], r["human_note"]))
            out.append("")
    else:
        out += ["*No labelled verdicts yet. Fill in a reviews/judge-sample-<week>.md and the next Monday publish "
                "ingests it.*", ""]
    prompts = conn.execute("SELECT prompt_sha, model, MIN(week), MAX(week), COUNT(*) FROM judge_verdicts "
                           "WHERE mode != 'stub' GROUP BY prompt_sha, model ORDER BY MIN(week)").fetchall()
    if prompts:
        out += ["## Prompt and model versions seen", "", "| Prompt | Model | First week | Last week | Verdicts |",
                "|---|---|---|---|---|"]
        for p in prompts:
            out.append("| {0} | {1} | {2} | {3} | {4} |".format(p[0] or "?", p[1] or "?", p[2], p[3], p[4]))
        out.append("")
    text = "\n".join(out)
    if write_to:
        os.makedirs(os.path.dirname(write_to), exist_ok=True)
        with open(write_to, "w", encoding="utf-8") as handle:
            handle.write(text)
    return text


# -- rescore: the drift check -----------------------------------------------------

def rescore(conn, api_key, limit=40, transport=None, usage_sink=None):
    """Re-run the CURRENT judge over labelled items and compare with the
    banked verdict and the human one. Spends money: the caller gates it."""
    from src import triage
    ensure_table(conn)
    rows = conn.execute("SELECT * FROM judge_verdicts WHERE human_score IS NOT NULL AND mode != 'stub' "
                        "ORDER BY labelled_at DESC, item_id LIMIT ?", (limit,)).fetchall()
    if not rows:
        return {"n": 0}
    items = [triage.TriageItem(id=r["item_id"], title=r["title"], text="", tier=r["tier"],
                               issue_areas=json.loads(r["candidate_areas"] or "[]"),
                               watchlist_hit=bool(r["watchlist_hit"])) for r in rows]
    results = triage.score_live(items, api_key=api_key, transport=transport, usage_sink=usage_sink)
    now = {r.id: r.score for r in results}
    then = {r["item_id"]: (r["score"], r["human_score"]) for r in rows}
    same_as_banked = sum(1 for i, s in now.items() if i in then and then[i][0] == s)
    agree_human_now = sum(1 for i, s in now.items() if i in then and then[i][1] == s)
    agree_human_then = sum(1 for i, (s, h) in then.items() if i in now and s == h)
    return {"n": len(now), "same_as_banked": same_as_banked, "agree_human_then": agree_human_then,
            "agree_human_now": agree_human_now, "prompt_sha": prompt_sha(triage.SYSTEM_PROMPT),
            "model": triage.TRIAGE_MODEL}
