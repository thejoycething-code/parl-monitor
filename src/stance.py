"""Stance layer: classify ledger evidence onto the 5CA gradient.

The ledger measures ACTIVITY, not DIRECTION -- an asker pressing for tighter
borders and a peer pressing against them ledger identically (docs/5ca-notes.md).
This pass reads the evidence text (the member's question framing, the motion
text they signed) and scores the MEMBER'S OWN ACTION against CitizenGO's
position: +2 strong ally .. -2 strong opponent, 0 when neutral, procedural or
unclear. Scores are stored per ref in the stance table; an EDM's sponsor and
every co-signatory inherit the motion's direction (signing endorses the text).

Division votes and Hansard speeches (September) will outrank these
text-derived scores in the 5CA generator's evidence hierarchy.

Mirrors triage.py: stub-free live pass, injectable transport, batches of 20.
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field

STANCE_MODEL = "claude-sonnet-5"
BATCH_SIZE = 20

SYSTEM_PROMPT = """You are the stance-classification layer of CitizenGO UK's parliamentary monitor.
CitizenGO's positions: abortion (pro-life), assisted dying (opposed), youth gender
medicine (opposed to paediatric transition), conversion practices bans (concerned re
therapy/parental/religious freedom), single-sex spaces (defends sex-based rights),
parental rights in education (supports), free speech (defends; wary of online safety
overreach), freedom of religion or belief (defends), marriage and family (supports),
surrogacy (opposed to commercial surrogacy), migration (border control and integrity,
opposed to illegal migration).

Each input is a parliamentary action BY A MEMBER: a written question they asked
(text = the member's own question, never the government's answer), an Early Day
Motion they sponsored or signed (text = the motion they endorsed), a division
vote (the line states which way they voted on the division title; judge what a
vote that way means for the underlying question), or a spoken debate
contribution (text = the member's own words in the chamber -- usually the
clearest personal stance signal).

Score the member's action relative to CitizenGO's position on the areas given:
 +2 clearly advances/aligns with the position (strong ally signal)
 +1 leans toward it
  0 neutral, procedural, factual information-seeking, or direction unclear
 -1 leans against it
 -2 clearly opposes it (strong opponent signal)

Rules: judge only the text supplied; most written questions are neutral
information-seeking and score 0 -- only score direction the framing itself shows.
Never infer stance from the member's party or name. An EDM's text is an endorsed
position, so motions usually carry direction. Division votes on second/third
readings carry clear direction; procedural or amendment ping-pong motions whose
effect is unclear from the title alone score 0.

For each input return JSON: {"ref": ..., "stance": -2..2, "why": "..."}.
why: maximum 20 words, concrete, British spelling, no em dashes.
Return only the JSON array."""


@dataclass
class Evidence:
    ref: str             # 'pq:123' / 'edm:456' -- shared by sponsor + signatories
    kind: str
    line: str
    areas: list = field(default_factory=list)
    text: str = ""       # full question / motion text where recoverable


@dataclass
class StanceResult:
    ref: str
    stance: int
    why: str


# -- storage ------------------------------------------------------------------

def ensure_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS stance ("
                 "ref TEXT PRIMARY KEY, stance INTEGER, why TEXT, "
                 "model TEXT, scored_at TEXT)")
    conn.commit()


def unscored_refs(conn):
    """Distinct ledger refs with no stance row yet.

    One representative row per ref: sponsor/signatory events share their
    motion's ref and therefore its (single) stance classification, and vote
    refs encode direction (div:c123:aye vs :no) so each side classifies
    separately -- every Aye voter inherits the aye ref's score.
    """
    ensure_table(conn)
    # No issue area, no scoring: those rows render nowhere, so paying to be
    # told a dementia question is irrelevant is pure waste.
    return conn.execute(
        "SELECT e.ref, MIN(e.kind) AS kind, MIN(e.line) AS line, MIN(e.areas) AS areas "
        "FROM mp_events e LEFT JOIN stance s ON s.ref = e.ref "
        "WHERE s.ref IS NULL AND e.areas IS NOT NULL AND e.areas != '[]' "
        "GROUP BY e.ref").fetchall()


def store_scores(conn, results, scored_at, model=STANCE_MODEL):
    ensure_table(conn)
    for r in results:
        if r.ref is None or r.stance is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO stance (ref, stance, why, model, scored_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (r.ref, max(-2, min(2, int(r.stance))), r.why or "", model, scored_at))
    conn.commit()


# -- live classification ------------------------------------------------------

def _batches(items, size=BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _build_payload(batch):
    user = [{"ref": ev.ref, "kind": ev.kind, "areas": ev.areas,
             "line": ev.line, "text": (ev.text or "")[:1500]} for ev in batch]
    return {
        "model": STANCE_MODEL,
        "max_tokens": 4000,  # 20 whys at ~20 words never approaches this
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": json.dumps(user)}],
    }


def _default_transport(payload, api_key):  # pragma: no cover - real network
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The body carries the actual reason (credit exhausted, oversized
        # request, invalid field); a bare "HTTP Error 400" wasted a run.
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise RuntimeError("HTTP {0}: {1}".format(exc.code, detail)) from exc


def _parse_reply(reply):
    """Extract results, tolerating markdown fences and truncated arrays.

    A max_tokens cut mid-array (seen live 2026-08-04) loses at most the last
    entry; the salvage keeps every complete object so the idempotent re-run
    only has the remainder to score.
    """
    text = "".join(block.get("text", "") for block in (reply.get("content") or [])).strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    start = text.find("[")
    if start > 0:
        text = text[start:]  # tolerate preamble prose before the array
    try:
        data = json.loads(text)
    except ValueError:
        cut = text.rfind("}")
        if cut < 0:
            raise
        data = json.loads(text[:cut + 1] + "]")
    return [StanceResult(ref=row.get("ref"), stance=row.get("stance"),
                         why=row.get("why") or "")
            for row in data]


def classify_batch(batch, api_key=None, transport=None):
    """One live call over up to BATCH_SIZE Evidence items."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("anthropic_api_key required for stance classification")
    transport = transport or _default_transport
    return _parse_reply(transport(_build_payload(batch), api_key))


def classify_live(evidence, api_key=None, transport=None):
    results = []
    for batch in _batches(evidence):
        results.extend(classify_batch(batch, api_key=api_key, transport=transport))
    return results


# -- evidence text recovery ---------------------------------------------------

def build_text_map(raw_dir, since_days=None):
    """{ref: full evidence text} from the archived payloads in data/raw.

    Recovered OFFLINE: every fetch already wrote its response, so scoring
    never re-hits the source APIs. since_days limits the scan to recent
    archive dates, which keeps the weekly pass quick as the archive grows.
    """
    import glob
    import gzip

    dates = "*"
    if since_days:
        keep = {(datetime.date.today() - datetime.timedelta(days=n)).isoformat()
                for n in range(since_days + 1)}
        dates = None
    texts = {}

    def each(pattern):
        for path in sorted(glob.glob(os.path.join(raw_dir, "*", pattern))):
            if dates is None:
                if os.path.basename(os.path.dirname(path)) not in keep:
                    continue
            try:
                with gzip.open(path, "rb") as handle:
                    yield json.loads(handle.read().decode("utf-8"))
            except Exception:
                continue  # a truncated archive file must not stop scoring

    for payload in each("pq_*.json.gz"):
        for row in (payload.get("results") or []):
            value = row.get("value") or row
            if value.get("id"):
                texts["pq:{0}".format(value["id"])] = "{0}\n{1}".format(
                    value.get("heading") or "", value.get("questionText") or "")
    for payload in each("hansard_*.json.gz"):
        for row in (payload.get("Results") or []):
            if row.get("ContributionExtId"):
                texts["hansard:{0}".format(row["ContributionExtId"])] = "{0}\n{1}".format(
                    row.get("DebateSection") or "",
                    row.get("ContributionTextFull") or row.get("ContributionText") or "")
    for payload in each("edm_*.json.gz"):
        rows = payload.get("Response")
        rows = rows if isinstance(rows, list) else ([rows] if rows else [])
        for row in rows:
            if row.get("Id"):
                texts["edm:{0}".format(row["Id"])] = "{0}\n{1}".format(
                    row.get("Title") or "", row.get("MotionText") or "")
    return texts


def score_pending(conn, raw_dir, api_key, scored_at, max_refs=None,
                  overrides_cfg=None, since_days=None, log=None):
    """Score every unscored ref, then apply editorial overrides.

    Stores per batch, so a crash or credit exhaustion keeps what was scored
    and the next run resumes. max_refs caps one run's spend; the remainder
    is reported (never silently dropped) and picked up next time.
    """
    log = log or (lambda _msg: None)
    pending = unscored_refs(conn)
    deferred = 0
    if max_refs and len(pending) > max_refs:
        deferred = len(pending) - max_refs
        pending = pending[:max_refs]
    if not pending:
        return {"scored": 0, "failed_batches": 0, "deferred": 0, "overridden": 0}

    texts = build_text_map(raw_dir, since_days=since_days)
    evidence = [Evidence(ref=r["ref"], kind=r["kind"], line=r["line"] or "",
                         areas=json.loads(r["areas"]) if r["areas"] else [],
                         text=texts.get(r["ref"], ""))
                for r in pending]

    scored, failed = 0, 0
    for batch in _batches(evidence):
        try:
            results = classify_batch(batch, api_key=api_key)
        except Exception as exc:
            failed += 1
            log("stance batch of {0} failed: {1}".format(len(batch), exc))
            continue
        store_scores(conn, results, scored_at)
        scored += len(results)
    overridden = apply_overrides(conn, overrides_cfg or {"overrides": []}, scored_at)
    return {"scored": scored, "failed_batches": failed, "deferred": deferred,
            "overridden": overridden}


# -- editorial overrides ------------------------------------------------------

def load_overrides(path):
    """config/stance_overrides.yaml -> {'overrides': [...], 'free_vote_titles': [...]}"""
    import yaml
    if not os.path.exists(path):
        return {"overrides": [], "caps": [], "free_vote_titles": [],
                "excluded_from_5ca": []}
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    overrides = []
    for rule in (raw.get("overrides") or []):
        # YAML 1.1 parses a bare `no:` key as boolean False; normalise so
        # rules read naturally in the config file.
        if False in rule:
            rule["no"] = rule.pop(False)
        if True in rule:
            rule["aye"] = rule.pop(True)
        overrides.append(rule)
    return {"overrides": overrides,
            "caps": list(raw.get("caps") or []),
            "free_vote_titles": list(raw.get("free_vote_titles") or []),
            "excluded_from_5ca": [int(a) for a in (raw.get("excluded_from_5ca") or [])]}


def _rule_matches(rule, title):
    low = (title or "").lower()
    if (rule.get("match") or "").lower() not in low:
        return False
    when = rule.get("when_any")
    if when and not any(w.lower() in low for w in when):
        return False
    unless = rule.get("unless_any")
    if unless and any(u.lower() in low for u in unless):
        return False
    return True


def apply_overrides(conn, cfg, scored_at):
    """Stamp editorial stances onto matching vote refs. Idempotent; the
    organisation's settled judgement on named bills outranks the classifier
    (Christopher, 2026-08-04). Returns the number of refs overridden."""
    ensure_table(conn)
    rows = conn.execute(
        "SELECT s.ref, MIN(e.line) AS line FROM stance s "
        "JOIN mp_events e ON e.ref = s.ref WHERE e.kind = 'vote' "
        "GROUP BY s.ref").fetchall()
    n = 0
    for r in rows:
        direction = "aye" if r["ref"].endswith(":aye") else "no"
        title = (r["line"] or "").split(": ", 1)[-1]
        for rule in cfg["overrides"]:
            if direction not in rule or not _rule_matches(rule, title):
                continue  # a rule may score only one direction
            conn.execute(
                "UPDATE stance SET stance = ?, why = ?, model = 'override', "
                "scored_at = ? WHERE ref = ?",
                (max(-2, min(2, int(rule[direction]))),
                 rule.get("why_" + direction) or "", scored_at, r["ref"]))
            n += 1
            break
    conn.commit()
    return n


# -- whip status ---------------------------------------------------------------

def ensure_whip_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS division_whip ("
                 "ref_base TEXT PRIMARY KEY, whipped INTEGER)")
    conn.commit()


def whip_note(title, ref, whip_map, free_vote_titles):
    """'free vote' / 'whipped' / None for one vote evidence line.

    Conscience-convention titles are free votes in both Houses; Lords
    divisions additionally carry the API's explicit isWhipped flag.
    """
    low = (title or "").lower()
    if any(t.lower() in low for t in free_vote_titles):
        return "free vote"
    base = ref.rsplit(":", 1)[0] if ref else None
    flag = whip_map.get(base)
    if flag is None:
        return None
    return "whipped" if flag else "free vote"


# -- 5CA sheet generation -----------------------------------------------------

COLUMNS = ("++", "+", "0", "-", "--")

# Evidence hierarchy (docs/5ca-notes.md): a recorded vote is ground truth and
# outranks everything text-derived; a speech is a chosen personal act and
# outranks sponsoring a motion, which outranks signing one, which outranks
# question framing.
KIND_WEIGHT = {"vote": 5, "debate": 4, "edm": 3, "edm-signed": 2, "pq": 1}


def applicable_caps(evidence_rows, caps):
    """Cap rules triggered by a member's evidence -> [(ceiling, note)].

    A cap limits the upside only: a bad vote that must not read as strong
    support, without erasing the good record that sits alongside it.
    """
    hits = []
    for rule in caps or []:
        want = (rule.get("direction") or "").lower()
        for r in evidence_rows:
            ref = r["ref"] or ""
            if want and not ref.endswith(":" + want):
                continue
            title = (r["line"] or "").split(": ", 1)[-1]
            if (rule.get("match") or "").lower() in title.lower():
                hits.append((int(rule.get("ceiling", 2)), rule.get("note") or ""))
                break
    return hits


def stance_to_column(stance):
    return {2: "++", 1: "+", 0: "0", -1: "-", -2: "--"}[max(-2, min(2, stance or 0))]


def suggest_rows(conn, area, full_roster=False, overrides_cfg=None):
    """5CA Plan rows for `area`, strongest evidence first.

    full_roster=False: one row per member (either House) with ledger
    activity on the area. full_roster=True: one row per sitting MP from the
    Commons roster (members.current_mp=1, ~650) -- the actual voting body a
    Commons-division 5CA targets; MPs the ledger has never seen sit at 0
    with "No recorded activity", and active peers are excluded (they do not
    vote in the Commons).

    Placement rule: the most directional evidence wins, ties broken by kind
    weight then recency; members whose evidence is all-neutral sit at 0. A
    sign conflict (both + and - evidence) is flagged in the comments -- the
    campaigner decides, the tool never averages opposing signals away.
    """
    ensure_table(conn)
    ensure_whip_table(conn)
    free_titles = (overrides_cfg or {}).get("free_vote_titles") or []
    whip_map = {r["ref_base"]: r["whipped"]
                for r in conn.execute("SELECT ref_base, whipped FROM division_whip")}
    rows = conn.execute(
        "SELECT e.member_id, e.date, e.kind, e.ref, e.line, e.areas, e.excerpt, "
        "s.stance, s.why, m.name, m.party, m.seat, m.house "
        "FROM mp_events e LEFT JOIN stance s ON s.ref = e.ref "
        "LEFT JOIN members m ON m.id = e.member_id "
        "ORDER BY e.date DESC").fetchall()

    def _whip(r):
        if r["kind"] != "vote":
            return None
        return whip_note(r["line"], r["ref"], whip_map, free_titles)

    per_member = {}
    for r in rows:
        areas = json.loads(r["areas"]) if r["areas"] else []
        if area not in areas:
            continue
        per_member.setdefault(r["member_id"], []).append(r)

    roster = {}
    if full_roster:
        roster = {r["id"]: r for r in conn.execute(
            "SELECT id, name, party, seat FROM members WHERE current_mp = 1")}
        per_member = {mid: evs for mid, evs in per_member.items() if mid in roster}

    out = []
    for mid, evs in per_member.items():
        # A free vote is the member's own conviction; at equal strength and
        # kind it outranks whipped or unknown-whip evidence.
        best = max(evs, key=lambda r: (abs(r["stance"] or 0),
                                       KIND_WEIGHT.get(r["kind"], 0),
                                       1 if _whip(r) == "free vote" else 0,
                                       r["date"]))
        stance = best["stance"] or 0
        cap_notes = []
        for ceiling, note in applicable_caps(evs, (overrides_cfg or {}).get("caps")):
            if stance > ceiling:
                stance = ceiling
                if note:
                    cap_notes.append(note)
        signs = {(1 if (r["stance"] or 0) > 0 else -1)
                 for r in evs if (r["stance"] or 0) != 0}
        conflict = len(signs) > 1
        first = evs[0]
        name = first["name"] or "Member {0}".format(mid)
        detail = ", ".join(x for x in (first["party"], first["seat"]) if x)
        comments = []
        comments.extend(cap_notes)
        if conflict:
            comments.append("CONFLICTING SIGNALS - review all evidence")
        for r in sorted(evs, key=lambda r: r["date"], reverse=True):
            whip = _whip(r)
            why = (r["why"] or "").rstrip(".")
            note = " [{0}{1}{2}]".format(
                stance_to_column(r["stance"]) if r["stance"] is not None else "unscored",
                ": " + why if why else "",
                "; {0}".format(whip) if whip else "")
            # The excerpt is the passage that put this row here, which is what
            # a campaigner needs to see -- a debate title alone can be about
            # something else entirely.
            quote = ' "{0}"'.format(r["excerpt"]) if r["excerpt"] else ""
            comments.append("{0} {1}: {2}{3}{4}".format(
                r["date"], r["kind"].upper(), r["line"], quote, note))
        out.append({
            "member_id": mid,
            "decision_maker": name + (" ({0})".format(detail) if detail else ""),
            "house": first["house"] or "",
            "column": stance_to_column(stance),
            "conflict": conflict,
            "n_events": len(evs),
            "comments": " | ".join(comments),
        })

    for mid, m in roster.items():
        if mid in per_member:
            continue
        detail = ", ".join(x for x in (m["party"], m["seat"]) if x)
        out.append({
            "member_id": mid,
            "decision_maker": (m["name"] or "Member {0}".format(mid))
                              + (" ({0})".format(detail) if detail else ""),
            "house": "Commons",
            "column": "0",
            "conflict": False,
            "n_events": 0,
            "comments": "No recorded activity on this area (ledger from 2026-02-03)",
        })

    order = {c: i for i, c in enumerate(COLUMNS)}
    out.sort(key=lambda r: (order[r["column"]], -r["n_events"], r["decision_maker"]))
    return out
