"""Score unscored ledger refs onto the 5CA stance gradient.

    python3 tools/score_stance.py [--dry-run]

Full evidence text (the member's question, the motion text) is recovered
OFFLINE from the data/raw archive that every fetch already wrote -- no
re-fetching. Refs whose text is not recoverable are classified from the
ledger line alone, which the rubric treats conservatively (unclear -> 0).

Live Claude pass (claude-sonnet-5, batches of 20) using anthropic_api_key
from config/secrets.yaml. Idempotent: only refs with no stance row are sent;
re-running after a partial failure fills the gaps. Pennies per full run.
"""

from __future__ import annotations

import datetime
import glob
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, publish, stance


def _read_payload(path):
    with gzip.open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def build_text_map(raw_root):
    """{ref: full text} from every archived PQ/EDM payload, newest last so
    the freshest capture of a ref wins."""
    texts = {}
    for path in sorted(glob.glob(os.path.join(raw_root, "*", "pq_*.json.gz"))):
        try:
            payload = _read_payload(path)
        except Exception:
            continue
        for row in (payload.get("results") or payload.get("Response") or []):
            value = row.get("value") or row
            qid = value.get("id")
            if qid:
                texts["pq:{0}".format(qid)] = "{0}\n{1}".format(
                    value.get("heading") or "", value.get("questionText") or "")
    for path in sorted(glob.glob(os.path.join(raw_root, "*", "hansard_*.json.gz"))):
        try:
            payload = _read_payload(path)
        except Exception:
            continue
        for row in (payload.get("Results") or []):
            ext = row.get("ContributionExtId")
            if ext:
                texts["hansard:{0}".format(ext)] = "{0}\n{1}".format(
                    row.get("DebateSection") or "",
                    row.get("ContributionTextFull") or row.get("ContributionText") or "")
    for path in sorted(glob.glob(os.path.join(raw_root, "*", "edm_*.json.gz"))):
        try:
            payload = _read_payload(path)
        except Exception:
            continue
        rows = payload.get("Response")
        rows = rows if isinstance(rows, list) else ([rows] if rows else [])
        for row in rows:
            eid = row.get("Id")
            if eid:
                texts["edm:{0}".format(eid)] = "{0}\n{1}".format(
                    row.get("Title") or "", row.get("MotionText") or "")
    return texts


def main():
    dry = "--dry-run" in sys.argv
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    pending = stance.unscored_refs(conn)
    if not pending:
        print("nothing to score")
        return

    texts = build_text_map(os.path.join(ROOT, "data", "raw"))
    evidence, missing = [], 0
    for r in pending:
        text = texts.get(r["ref"], "")
        if not text:
            missing += 1
        evidence.append(stance.Evidence(
            ref=r["ref"], kind=r["kind"], line=r["line"] or "",
            areas=json.loads(r["areas"]) if r["areas"] else [], text=text))
    print("{0} refs to score ({1} without recovered text)".format(len(evidence), missing))
    if dry:
        return

    api_key = publish.load_secrets().get("anthropic_api_key")
    today = datetime.date.today().isoformat()
    results, failed = [], 0
    for batch in stance._batches(evidence):
        try:
            scored = stance.classify_batch(batch, api_key=api_key)
        except Exception as exc:
            failed += 1
            print("  [gap] batch of {0} failed: {1}".format(len(batch), exc))
            continue
        stance.store_scores(conn, scored, today)  # per batch: crash loses nothing
        results.extend(scored)
        print("  scored {0}/{1}".format(len(results), len(evidence)))
    if failed:
        print("{0} batch(es) failed; re-run to fill the gaps (idempotent)".format(failed))

    dist = {}
    for r in results:
        col = stance.stance_to_column(r.stance if r.stance is not None else 0)
        dist[col] = dist.get(col, 0) + 1
    print("scored {0}: ".format(len(results)) +
          "  ".join("{0} x{1}".format(c, dist[c]) for c in stance.COLUMNS if c in dist))

    # Editorial rules outrank the classifier wherever they match, and re-apply
    # on every run so newly scored refs pick them up too.
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    n_over = stance.apply_overrides(conn, cfg, today)
    print("editorial overrides applied to {0} vote refs".format(n_over))
    conn.close()


if __name__ == "__main__":
    main()
