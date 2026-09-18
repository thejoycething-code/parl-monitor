"""EU dossier tracker: the bills-board analog for watched EP procedures.

    python3 tools/eu_dossiers.py

Phase 2a of the EU monitor (Christopher, 2026-09-01: build phase 2 in the
spec's order). Each dossier in config/eu_watchlist.yaml is fetched from the
EP Open Data procedures endpoint weekly; a change of current_stage is
MOVEMENT and is recorded and marked in the EU edition, exactly as the
Westminster board marks "▲ moved".

Why a watchlist and not enumeration: the procedures listing returns ids
without titles, so taxonomy-matching every EU procedure would cost one
detail fetch each against a 500-requests-per-5-minutes limit. The board is
curated -- verified ids with a why: line -- and matched adopted texts will
auto-PROPOSE additions later (phase 2c); a human confirms, as with the
Westminster watchlist.

Separation guarantee: writes eu_dossiers only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, eulabel
from src.http import FetchError, HttpClient

PROC = ("https://data.europarl.europa.eu/api/v2/procedures/{0}"
        "?format=application%2Fld%2Bjson")

# The procedure-phase authority codes seen so far, spelled out for the
# edition. An UNKNOWN code renders as itself -- never guessed.
STAGE_LABEL = {
    "RDG1": "First reading",
    "RDG2": "Second reading",
    "RDG3": "Third reading",
    "CONCIL": "Conciliation",
    "PREPAR": "Preparatory phase",
    "AWAITING_DECISION": "Awaiting decision",
}


def stage_code(uri):
    """'.../procedure-phase/RDG1' -> 'RDG1'; None stays None."""
    return uri.rstrip("/").rsplit("/", 1)[-1] if uri else None


def load_watchlist():
    import yaml
    with open(os.path.join(ROOT, "config", "eu_watchlist.yaml"),
              encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("dossiers") or []


def track(conn, client, watchlist, today, log=print):
    moved = gaps = 0
    for d in watchlist:
        pid = d["process_id"]
        try:
            reply = client.get_json(PROC.format(pid), "eu-dossiers", pid,
                                    archive=False)
        except FetchError as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (today, "eu-dossiers", "{0}: {1}".format(pid,
                                                                  exc.cause)))
            log("  [gap] {0}: {1}".format(pid, exc.cause))
            gaps += 1
            continue
        data = (reply.get("data") or [{}])[0]
        stage = stage_code(data.get("current_stage"))
        title = eulabel.english(data.get("process_title")) or d.get("title")
        prev = conn.execute("SELECT stage FROM eu_dossiers WHERE "
                            "process_id = ?", (pid,)).fetchone()
        prev_stage = prev["stage"] if prev else None
        if prev and prev_stage != stage:
            moved += 1
            log("  MOVED: {0} {1} -> {2}".format(d.get("title") or pid,
                                                 prev_stage, stage))
        conn.execute(
            "INSERT INTO eu_dossiers (process_id, label, title, stage, "
            "prev_stage, moved_date, areas, why, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(process_id) DO UPDATE SET title=excluded.title, "
            "prev_stage=CASE WHEN eu_dossiers.stage != excluded.stage "
            "THEN eu_dossiers.stage ELSE eu_dossiers.prev_stage END, "
            "moved_date=CASE WHEN eu_dossiers.stage != excluded.stage "
            "THEN excluded.last_seen ELSE eu_dossiers.moved_date END, "
            "stage=excluded.stage, areas=excluded.areas, why=excluded.why, "
            "last_seen=excluded.last_seen",
            (pid, d.get("label"), title, stage, None, None,
             ",".join(str(a) for a in d.get("areas") or []),
             (d.get("why") or "").strip(), today, today))
    conn.commit()
    return moved, gaps


def board_rows(conn, today):
    """The edition's dossier board, movement first."""
    rows = conn.execute("SELECT * FROM eu_dossiers ORDER BY label").fetchall()
    out = []
    for r in rows:
        if r["first_seen"] == today:
            movement = "NEW"
        elif r["moved_date"] == today:
            movement = "▲ moved ({0} → {1})".format(
                STAGE_LABEL.get(r["prev_stage"], r["prev_stage"]),
                STAGE_LABEL.get(r["stage"], r["stage"]))
        else:
            movement = "no change"
        out.append({
            "label": r["label"], "title": r["title"],
            "stage": STAGE_LABEL.get(r["stage"], r["stage"] or "?"),
            "movement": movement, "why": r["why"],
            "url": "https://oeil.europarl.europa.eu/oeil/en/procedure-file"
                   "?reference={0}".format(r["label"]),
        })
    return out


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    wl = load_watchlist()
    moved, gaps = track(conn, client, wl, today)
    print("eu-dossiers: {0} tracked, {1} moved, {2} gap(s).".format(
        len(wl), moved, gaps))
    for r in board_rows(conn, today):
        print("  {0} | {1} | {2} | {3}".format(
            r["label"], (r["title"] or "?")[:60], r["stage"], r["movement"]))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
