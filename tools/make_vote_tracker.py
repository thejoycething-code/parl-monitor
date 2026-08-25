"""Build the MP vote tracker: how every sitting MP voted on our issues.

    python3 tools/make_vote_tracker.py            # build both audiences
    python3 tools/make_vote_tracker.py --candidates   # divisions we could add

Reads config/vote_tracker.yaml (issues, divisions, plain-English meaning
lines) and the archived division payloads in data/raw, and renders the
prototype's view layer from templates/vote-tracker.html.

Vote data comes from the archive, not a refetch: the payloads carry Ayes,
Noes, both sets of tellers AND NoVoteRecorded, which is what lets the tool
keep the distinction that matters most -- no vote recorded is NOT an
abstention, because the Commons does not record abstentions.

Written to partner_site/mp-votes.html (allies) and docs/mp-votes.html
(internal). Same page: it states what members did and what each vote meant,
which is public record either way.
"""

from __future__ import annotations

import datetime
import glob
import gzip
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel
from src.http import HttpClient
from src.ingest import divisions as div_ingest

TEMPLATE = os.path.join(ROOT, "templates", "vote-tracker.html")
CONFIG = os.path.join(ROOT, "config", "vote_tracker.yaml")
OUTPUTS = (os.path.join(ROOT, "partner_site", "mp-votes.html"),
           os.path.join(ROOT, "docs", "mp-votes.html"))

CODES = (("Ayes", "A"), ("Noes", "N"), ("AyeTellers", "TA"),
         ("NoTellers", "TN"), ("NoVoteRecorded", "X"))


def load_config():
    import yaml
    with open(CONFIG, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def archived_divisions():
    """{division_id: payload} from data/raw, newest file per id winning."""
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*",
                                              "division_cdetail-*.json.gz"))):
        try:
            with gzip.open(path, "rb") as handle:
                payload = json.loads(handle.read().decode("utf-8"))
        except Exception:
            continue
        if payload.get("DivisionId"):
            out[payload["DivisionId"]] = payload
    return out


def candidates(conn):
    """Divisions in the ledger that could join the tracker, by area."""
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    have = {d["id"] for d in (load_config().get("divisions") or [])}
    rows = conn.execute(
        "SELECT ref, MIN(line) AS line, MIN(date) AS date, MIN(areas) AS areas "
        "FROM mp_events WHERE kind = 'vote' AND ref LIKE 'div:c%' GROUP BY ref "
        "ORDER BY date DESC").fetchall()
    seen = set()
    for r in rows:
        base = r["ref"].rsplit(":", 1)[0]
        div_id = int(base.split("c")[1])
        if base in seen or div_id in have:
            continue
        seen.add(base)
        title = re.sub(r"^Voted (Aye|No): ", "", r["line"] or "")
        if not re.search(r"Reading|New Clause|Amendment \d|Regulations", title):
            continue
        areas = [names.get(a, a) for a in json.loads(r["areas"] or "[]")]
        print("  id {0:5}  {1}  {2:66} {3}".format(
            div_id, r["date"], title[:66], ", ".join(str(a) for a in areas)))
    print("\nAdd the ones worth showing to config/vote_tracker.yaml with meaning "
          "lines a human has written.")


def fetch_missing(payloads, cfg):
    """Fetch any configured division the archive lacks.

    The sweep only archives divisions whose TITLE matched a sweep term, so the
    abortion decriminalisation vote was absent: it sits inside "Crime and
    Policing Bill Report Stage: New Clause 1", which matches nothing in the
    division term list. A division named in the config is wanted by definition,
    so fetch it (and it archives for next time).
    """
    wanted = [d["id"] for d in (cfg.get("divisions") or []) if d["id"] not in payloads]
    if not wanted:
        return 0
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    got = 0
    for div_id in wanted:
        try:
            client.get_json(
                "{0}/division/{1}.json".format(div_ingest.COMMONS_API, div_id),
                "division", "cdetail-{0}".format(div_id))
            got += 1
        except Exception as exc:
            print("  could not fetch division {0}: {1}".format(div_id, exc))
    return got


MERGE_PARTY = {"Labour (Co-op)": "Labour"}  # whips together, reads together


def party_splits(payload, top=4):
    """[[party, ayes, noes], ...] for the largest parties in a division."""
    tally = {}
    for key, side in (("Ayes", 0), ("Noes", 1)):
        for m in (payload.get(key) or []):
            party = MERGE_PARTY.get(m.get("Party") or "?", m.get("Party") or "?")
            tally.setdefault(party, [0, 0])[side] += 1
    ranked = sorted(tally.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
    return [[p, a, n] for p, (a, n) in ranked[:top]]


def whip_label(d, issue_note, splits):
    """'free' | 'whipped' | None, editorial text first, arithmetic second.

    The signed-off wording is authoritative where it speaks (the config
    review checked every claim against the record). Where it is silent,
    the bloc test decides: the two largest parties each voting >=98% one
    way, on opposite sides, is a party-line vote whatever anyone says.
    """
    text = " ".join([d.get("context") or "", issue_note or ""]).lower()
    # Negations first: the signed-off NI contexts say "this was NOT a whipped
    # vote", and a bare substring test read that as whipped (caught on the
    # first build, 2026-08-12).
    if ("not a whipped vote" in text or "not whipped" in text
            or "free vote" in text or "free-vote" in text or "free votes" in text):
        return "free"
    if "whipped" in text:
        return "whipped"
    two = [x for x in splits[:2] if x[1] + x[2] >= 20]
    if len(two) == 2:
        sides = []
        for _, a, n in two:
            if a >= (a + n) * 0.98:
                sides.append("aye")
            elif n >= (a + n) * 0.98:
                sides.append("no")
        if len(sides) == 2 and sides[0] != sides[1]:
            return "whipped"
    return None


def build(conn, cfg, payloads):
    issues = cfg.get("issues") or []
    issue_notes = {i["id"]: i.get("note", "") for i in issues}
    used_issues, divisions, votes = set(), [], {}
    missing = []
    for d in cfg.get("divisions") or []:
        payload = payloads.get(d["id"])
        if payload is None:
            missing.append(d["id"])
            continue
        used_issues.add(d["issue"])
        for key, code in CODES:
            for m in (payload.get(key) or []):
                votes.setdefault(m["MemberId"], {})[d["id"]] = code
        splits = party_splits(payload)
        our = str(d.get("our_side") or "").lower()
        divisions.append({
            "splits": splits,
            "whip": whip_label(d, issue_notes.get(d["issue"]), splits),
            # 'good' drives the internal build's GOOD/BAD VOTE chips. The
            # partner build strips it before writing (facts only in public),
            # so flipping the public page later is a one-line decision, not
            # a rebuild of anything.
            "good": our if our in ("aye", "no") else None,
            "id": d["id"], "issue": d["issue"], "date": (payload.get("Date") or "")[:10],
            "stage": d["stage"], "stage_group": d.get("stage_group", d["stage"]),
            "landmark": bool(d.get("landmark")), "context": d.get("context", ""),
            "title": payload.get("Title"), "short": d["short"],
            "ayes": payload.get("AyeCount"), "noes": payload.get("NoCount"),
            "passed": (payload.get("AyeCount") or 0) > (payload.get("NoCount") or 0),
            "meaning_aye": d["meaning_aye"], "meaning_no": d["meaning_no"],
            "signed_off": bool(d.get("signed_off")),
            "url": "https://votes.parliament.uk/Votes/Commons/Division/{0}".format(d["id"]),
        })

    # Deputy Speakers identify themselves in the payloads: their listed party
    # is "Deputy Speaker". They do not vote, so their blank record is a role,
    # not a choice.
    deputies = {m["MemberId"] for p in payloads.values() for key, _ in CODES
                for m in (p.get(key) or []) if m.get("Party") == "Deputy Speaker"}

    members = []
    for r in conn.execute(
            "SELECT id, name, list_as, party, seat, since FROM members "
            "WHERE current_mp = 1 ORDER BY COALESCE(list_as, name)"):
        party = "Labour" if r["party"] == "Labour (Co-op)" else r["party"]
        role = None
        if party == "Speaker":
            role = "speaker"
        elif r["id"] in deputies:
            role = "deputy"
        elif party and party.startswith("Sinn F"):
            role = "sf"
        members.append({
            "id": r["id"], "name": r["name"], "listAs": r["list_as"] or r["name"],
            "party": party, "constituency": r["seat"], "since": r["since"],
            "role": role, "votes": votes.get(r["id"], {}),
        })

    dataset = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + " local",
        "issues": [i for i in issues if i["id"] in used_issues],
        "divisions": sorted(divisions, key=lambda d: (d["issue"], d["date"])),
        "members": members,
    }
    return dataset, missing


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    if "--candidates" in sys.argv:
        candidates(conn)
        return 0

    cfg = load_config()
    payloads = archived_divisions()
    if fetch_missing(payloads, cfg):
        payloads = archived_divisions()   # re-read: the fetch archived them
    dataset, missing = build(conn, cfg, payloads)
    conn.close()

    if not dataset["members"]:
        print("no sitting MPs in the cache - run tools/pull_commons_roster.py first")
        return 1
    if missing:
        print("no archived payload for division(s) {0}: they are omitted. Capture "
              "them by running the divisions backfill, then rebuild.".format(missing))

    with open(TEMPLATE, encoding="utf-8") as handle:
        template = handle.read()
    # The sign-off line is derived, never hardcoded: a fixed "pending sign-off"
    # sentence stayed on the page after every division had been signed off,
    # telling readers the summaries were unchecked when they had been.
    pending = [d["id"] for d in dataset["divisions"] if not d["signed_off"]]
    if pending:
        signoff = ("{0} of {1} summaries are still pending editorial sign-off."
                   .format(len(pending), len(dataset["divisions"])))
    else:
        signoff = ("Every summary on this page has been checked against Hansard "
                   "and the official division record, and signed off editorially.")
    # Verdicts are PUBLIC (Christopher, 2026-08-24, reversing his 2026-08-12
    # decision to keep them internal while the site was passwordless). Both
    # builds now carry `good`, so the public page names a vote good or bad
    # rather than reporting the lobby and leaving the reader to judge. That
    # makes this a campaigning page, not only a transparency one -- a
    # deliberate change of what the page IS, asked for twice.
    #
    # A division with no `our_side` in config/vote_tracker.yaml still shows
    # no verdict, so the honest gap stays visible rather than defaulting to
    # a judgement nobody made.
    for path, ds in ((OUTPUTS[0], dataset), (OUTPUTS[1], dataset)):
        page = (template.replace("__DATASET__", json.dumps(ds, separators=(",", ":")))
                        .replace("__SIGNOFF__", signoff))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)

    unsigned = [d["id"] for d in dataset["divisions"] if not d["signed_off"]]
    no_since = sum(1 for m in dataset["members"] if not m["since"])
    print("{0} divisions across {1} issues, {2} sitting MPs".format(
        len(dataset["divisions"]), len(dataset["issues"]), len(dataset["members"])))
    print("  roles: {0} speaker, {1} deputy, {2} Sinn Fein".format(
        *[sum(1 for m in dataset["members"] if m["role"] == r)
          for r in ("speaker", "deputy", "sf")]))
    if no_since:
        print("  {0} MPs without a start date: 'Not yet an MP' cannot be shown "
              "for them until the roster is re-pulled".format(no_since))
    if unsigned:
        print("  {0} of {1} divisions are NOT editorially signed off; the page "
              "carries the pending notice".format(len(unsigned), len(dataset["divisions"])))
    print("  -> " + "\n  -> ".join(OUTPUTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
