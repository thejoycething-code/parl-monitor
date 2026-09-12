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
import re
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
    excerpt: str = ""    # the matching passage: what actually earned the capture


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


HIDDEN_AREAS = (11,)   # migration: collated, never campaigned, shown nowhere (partner.HIDDEN_AREAS)


def unscored_refs(conn, skip_hidden=False):
    """Distinct ledger refs with no stance row yet.

    One representative row per ref: sponsor/signatory events share their
    motion's ref and therefore its (single) stance classification, and vote
    refs encode direction (div:c123:aye vs :no) so each side classifies
    separately -- every Aye voter inherits the aye ref's score.

    skip_hidden leaves out refs whose ONLY areas are hidden ones (migration):
    they render on no surface, so a backfill can score the displayable ground
    first and put the hidden rows to the campaigner as a separate spend.
    """
    ensure_table(conn)
    # No issue area, no scoring: those rows render nowhere, so paying to be
    # told a dementia question is irrelevant is pure waste.
    rows = conn.execute(
        "SELECT e.ref, MIN(e.kind) AS kind, MIN(e.line) AS line, MIN(e.areas) AS areas, "
        "MAX(e.excerpt) AS excerpt "
        "FROM mp_events e LEFT JOIN stance s ON s.ref = e.ref "
        "WHERE s.ref IS NULL AND e.areas IS NOT NULL AND e.areas != '[]' "
        "GROUP BY e.ref").fetchall()
    if not skip_hidden:
        return rows
    hidden = set(HIDDEN_AREAS)

    def only_hidden(areas):
        try:
            got = set(json.loads(areas or "[]"))
        except ValueError:
            return False
        return bool(got) and got <= hidden
    return [r for r in rows if not only_hidden(r["areas"])]


def store_scores(conn, results, scored_at, model=STANCE_MODEL):
    ensure_table(conn)
    for r in results:
        if r.ref is None or r.stance is None:
            continue
        try:
            value = max(-2, min(2, int(r.stance)))
        except (TypeError, ValueError):
            # A malformed row (stance as a list, a word, ...) must not kill
            # the run: skip it and the idempotent re-run scores it properly.
            continue
        conn.execute(
            "INSERT OR REPLACE INTO stance (ref, stance, why, model, scored_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (r.ref, value, r.why or "", model, scored_at))
    conn.commit()


# -- live classification ------------------------------------------------------

def _batches(items, size=BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _evidence_text(ev, cap=1500):
    """The matched passage IN its surroundings, not instead of them.

    Two failure modes bracketed this design. A bare 1,500-character prefix
    often ended before the passage that caused the capture (~2,300 speeches
    scored blind, fixed 2026-08-05). Then excerpt-ONLY stripped the context
    that gave the passage its direction: Lord Farmer's excerpt read as
    support for the assisted dying Bill when the surrounding speech was
    plainly against it, and one such misread flipped his placement
    (found in the peers spot-check, 2026-08-11). So: centre the window on
    the excerpt when it sits inside the full text; otherwise send excerpt
    then text within the same budget.
    """
    excerpt = ev.excerpt or ""
    text = ev.text or ""
    if excerpt and text:
        i = text.find(excerpt)
        if i >= 0:
            start = max(0, i - (cap - len(excerpt)) // 2)
            return text[start:start + cap]
        return (excerpt + " ... " + text)[:cap]
    return (excerpt or text)[:cap]


def _build_payload(batch):
    user = [{"ref": ev.ref, "kind": ev.kind, "areas": ev.areas, "line": ev.line,
             "text": _evidence_text(ev)} for ev in batch]
    return {
        "model": STANCE_MODEL,
        # Long speech batches were truncating at 4000 and losing whole
        # batches to unparseable replies (34% of the tail, 2026-08-05).
        "max_tokens": 8000,
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
    # A stance read answers in seconds; a 16,000-token report with thinking does not,
    # and 120s timed out on 11 Sept 2026. Scale with what was asked for.
    timeout = max(120, 60 + int(payload.get("max_tokens") or 0) // 20)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
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


def _salvage_objects(text):
    """Every complete JSON object at the start of a broken array.

    A max_tokens cut can land inside a string, so scanning for the last '}'
    is not enough (it may sit inside the unterminated value). Decoding
    object by object keeps everything intact and stops at the first break;
    the rest is picked up by the idempotent re-run.
    """
    decoder = json.JSONDecoder()
    out, i = [], 0
    if text.startswith("["):
        i = 1
    while i < len(text):
        while i < len(text) and text[i] in " \t\r\n,":
            i += 1
        if i >= len(text) or text[i] != "{":
            break
        try:
            obj, i = decoder.raw_decode(text, i)
        except ValueError:
            break
        out.append(obj)
    return out


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
        data = _salvage_objects(text)
        if not data:
            raise
    return [StanceResult(ref=row.get("ref"), stance=row.get("stance"),
                         why=row.get("why") or "")
            for row in data]


def classify_batch(batch, api_key=None, transport=None, usage_sink=None):
    """One live call over up to BATCH_SIZE Evidence items."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("anthropic_api_key required for stance classification")
    transport = transport or _default_transport
    reply = transport(_build_payload(batch), api_key)
    if usage_sink is not None:
        usage_sink(reply.get('usage') or {}, reply.get('model'))
    return _parse_reply(reply)


def classify_live(evidence, api_key=None, transport=None, usage_sink=None):
    results = []
    for batch in _batches(evidence):
        results.extend(classify_batch(batch, api_key=api_key,
                                      transport=transport,
                                      usage_sink=usage_sink))
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
        # Two payload shapes share this glob: the search list
        # ({results: [{value}]}, questionText cut at ~255 characters) and
        # the detail file ({value}, the whole question plus answerText),
        # written by pqs.fetch_question since 2026-09-06. When both exist
        # for an id the LONGER text wins, and the answer rides along
        # because the ingest filter matched on it too -- a retag that
        # reads less than the ingest read clears rows it should not.
        rows = payload.get("results")
        if rows is None and payload.get("value"):
            rows = [payload]
        for row in (rows or []):
            value = row.get("value") or row
            if not value.get("id"):
                continue
            key = "pq:{0}".format(value["id"])
            text = "{0}\n{1}".format(value.get("heading") or "",
                                     value.get("questionText") or "")
            if value.get("answerText"):
                text += "\n\nAnswer: {0}".format(value["answerText"])
            if len(text) > len(texts.get(key, "")):
                texts[key] = text
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
                  overrides_cfg=None, since_days=None, log=None, skip_hidden=False):
    """Score every unscored ref, then apply editorial overrides.

    Stores per batch, so a crash or credit exhaustion keeps what was scored
    and the next run resumes. max_refs caps one run's spend; the remainder
    is reported (never silently dropped) and picked up next time.
    """
    log = log or (lambda _msg: None)
    pending = unscored_refs(conn, skip_hidden=skip_hidden)
    deferred = 0
    if max_refs and len(pending) > max_refs:
        deferred = len(pending) - max_refs
        pending = pending[:max_refs]
    if not pending:
        return {"scored": 0, "failed_batches": 0, "deferred": 0, "overridden": 0}

    texts = build_text_map(raw_dir, since_days=since_days)
    evidence = [Evidence(ref=r["ref"], kind=r["kind"], line=r["line"] or "",
                         areas=json.loads(r["areas"]) if r["areas"] else [],
                         text=texts.get(r["ref"], ""),
                         excerpt=(r["excerpt"] if "excerpt" in r.keys() else "") or "")
                for r in pending]

    scored, failed = 0, 0

    def _spend(usage, model):
        from src import spend as _spend_mod
        _spend_mod.record(conn, "stance", model, usage, dated=scored_at)

    for batch in _batches(evidence):
        try:
            results = classify_batch(batch, api_key=api_key, usage_sink=_spend)
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


def ensure_snapshot_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS ca_snapshots ("
                 "area INTEGER, edition TEXT, counts TEXT, "
                 "PRIMARY KEY (area, edition))")
    conn.commit()


def record_snapshot(conn, area, edition, counts):
    """Store one area's gradient counts for an edition (idempotent)."""
    ensure_snapshot_table(conn)
    conn.execute("INSERT OR REPLACE INTO ca_snapshots (area, edition, counts) "
                 "VALUES (?, ?, ?)", (area, edition, json.dumps(counts)))
    conn.commit()


def previous_snapshot(conn, area, before_edition):
    """The most recent stored counts for an area before this edition, or None.

    Week-on-week movement is the point of a tracker: a count is a fact, a
    change is a story.
    """
    ensure_snapshot_table(conn)
    row = conn.execute(
        "SELECT counts FROM ca_snapshots WHERE area = ? AND edition < ? "
        "ORDER BY edition DESC LIMIT 1", (area, before_edition)).fetchone()
    return json.loads(row["counts"]) if row else None


KIND_LABEL = {"vote": "a vote", "debate": "a speech", "edm": "a motion sponsored",
              "edm-signed": "a motion signed", "pq": "a question"}


def based_on(kind, date, today=None):
    """"a vote, 14 months ago": what the placement rests on, and how old it is.

    A placement resting on a 2020 speech and one resting on last month's
    division look identical in every column but this one.
    """
    if not kind:
        return "no evidence"
    label = KIND_LABEL.get(kind, kind)
    if not date:
        return label
    today = today or datetime.date.today()
    try:
        then = datetime.date.fromisoformat(date)
    except ValueError:
        return label
    days = (today - then).days
    if days < 14:
        age = "this week" if days < 7 else "last week"
    elif days < 60:
        age = "{0} weeks ago".format(days // 7)
    elif days < 730:
        age = "{0} months ago".format(max(2, round(days / 30.44)))
    else:
        years = days / 365.25
        age = "{0:.0f} years ago".format(years)
    return "{0}, {1}".format(label, age)


# -- per-member state: what moved, and whether the member or we moved ---------

MEMBER_STATE = """
CREATE TABLE IF NOT EXISTS ca_member_state (
  area INTEGER, member_id INTEGER, placement TEXT, decided_ref TEXT,
  changed_at TEXT, prev_placement TEXT, movement TEXT,
  PRIMARY KEY (area, member_id)
);
"""

NEW, MOVED_UP, MOVED_DOWN, REASSESSED, UNCHANGED = (
    "NEW", "UP", "DOWN", "REASSESSED", "UNCHANGED")


def ensure_member_state(conn):
    conn.executescript(MEMBER_STATE)
    conn.commit()


def _rank(column):
    return {"++": 2, "+": 1, "0": 0, "-": -1, "--": -2}.get(column, 0)


def update_member_state(conn, area, rows, today):
    """Diff this run's placements against the stored ones.

    The distinction that makes this column honest: if the DECIDING EVIDENCE
    changed, the member did something new and moved. If the deciding evidence
    is the same piece rescored, WE moved and the member did not. Tonight's
    rescore shifted ~460 speeches; without this split the column would have
    reported hundreds of members changing position when none had.
    """
    ensure_member_state(conn)
    prior = {r["member_id"]: r for r in conn.execute(
        "SELECT member_id, placement, decided_ref, changed_at, movement "
        "FROM ca_member_state WHERE area = ?", (area,))}
    out = {}
    for r in rows:
        mid, placement, ref = r["member_id"], r["column"], r["decided_ref"]
        was = prior.get(mid)
        if was is None:
            movement, changed_at, prev = NEW, today, None
        elif was["placement"] == placement:
            movement = UNCHANGED
            changed_at, prev = was["changed_at"], was["placement"]
        elif ref and was["decided_ref"] and ref == was["decided_ref"]:
            movement, changed_at, prev = REASSESSED, today, was["placement"]
        else:
            movement = MOVED_UP if _rank(placement) > _rank(was["placement"]) else MOVED_DOWN
            changed_at, prev = today, was["placement"]
        out[mid] = {"movement": movement, "changed_at": changed_at, "prev": prev}
        conn.execute(
            "INSERT INTO ca_member_state (area, member_id, placement, decided_ref, "
            "changed_at, prev_placement, movement) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(area, member_id) DO UPDATE SET placement=excluded.placement, "
            "decided_ref=excluded.decided_ref, changed_at=excluded.changed_at, "
            "prev_placement=excluded.prev_placement, movement=excluded.movement",
            (area, mid, placement, ref, changed_at, prev, movement))
    conn.commit()
    return out


def movement_label(movement, prev, placement, changed_at):
    """The words shown in the Moved column, in the bills board's vocabulary."""
    if movement == NEW:
        return "NEW", "first sheet"
    if movement == UNCHANGED:
        return "no change", ""
    detail = "{0} to {1}".format(prev or "?", placement)
    if changed_at:
        detail += " · " + changed_at
    if movement == REASSESSED:
        return "reassessed", detail
    return ("moved up" if movement == MOVED_UP else "moved down"), detail


def applicable_caps(evidence_rows, caps):
    """Cap rules triggered by a member's evidence -> [(ceiling, note)].

    A cap limits the upside only: a bad vote that must not read as strong
    support, without erasing the good record that sits alongside it.
    """
    hits = []
    for rule in caps or []:
        want = (rule.get("direction") or "").lower()
        when_any = [w.lower() for w in (rule.get("when_any") or [])]
        unless_any = [w.lower() for w in (rule.get("unless_any") or [])]
        for r in evidence_rows:
            ref = r["ref"] or ""
            if want and not ref.endswith(":" + want):
                continue
            title = (r["line"] or "").split(": ", 1)[-1]
            low = title.lower()
            if (rule.get("match") or "").lower() not in low:
                continue
            # A Bill's name is in every division on it, and on a report-stage
            # amendment Aye can be OUR side (Kruger on the "burden" exclusion).
            # when_any/unless_any narrow a cap to the stage votes it means, as
            # they do for overrides. Without them the assisted-suicide cap
            # caught 278 members, Kruger and Leigh among them (12 Sept 2026).
            if when_any and not any(w in low for w in when_any):
                continue
            if unless_any and any(w in low for w in unless_any):
                continue
            hits.append((int(rule.get("ceiling", 2)), rule.get("note") or ""))
            break
    return hits


def suggest_confidence(column, decided_kind, decided_whip, n_events,
                       n_directional, conflict, n_minority=0):
    """(tier, reason) for a placement: 'strong' | 'moderate' | 'thin'.

    Deterministic and explainable -- a campaigner reading the marker must be
    able to see why, so every tier carries its reason. The ordering encodes
    the evidence philosophy:

      * a genuinely split record is thin no matter how much evidence exists,
        but a sliver of contrary evidence only downgrades one tier: Danny
        Kruger at 134 items against 6 misread committee speeches is not
        "thin", he is strong-with-an-asterisk;
      * a FREE vote is the member's own conviction on the record and is
        strong on its own -- two Terminally Ill Adults (End of Life) Bill
        free votes say more than twenty whipped ones;
      * a whipped vote proves obedience, not conviction, so it caps at
        moderate without corroboration (the NC7 lesson: 93 members were
        being credited for following a whip);
      * an all-neutral record is a real placement (the 5CA's 0 column) but
        its confidence scales with volume: one neutral question is nothing,
        ten neutral items is a consistently neutral member.
    """
    if not n_events:
        return None, None
    if conflict and n_minority >= 2 and n_minority * 4 >= n_directional:
        return "thin", ("genuinely split record - {0} of {1} directional items "
                        "run the other way".format(n_minority, n_directional))

    def _conflicted(tier, reason):
        """Contrary evidence, graded by its share of the directional record.

        Under 10% is a blemish: stated, never downgraded -- Danny Kruger at
        6 misread committee speeches against 134 aligned items must not read
        "moderate" or campaigners will stop trusting the marker. 10-25% costs
        one tier. Above 25% never reaches here (genuine split, thin)."""
        if not conflict:
            return tier, reason
        note = "{0}; {1} contrary item{2} on record".format(
            reason, n_minority, "" if n_minority == 1 else "s")
        if n_minority * 10 < n_directional:
            return tier, note
        down = {"strong": "moderate", "moderate": "thin", "thin": "thin"}[tier]
        return down, note

    if decided_kind == "vote" and decided_whip == "free vote":
        return _conflicted("strong", "decided by a free vote")
    if column == "0":
        if n_events >= 5:
            return "moderate", "consistently neutral across {0} items".format(n_events)
        return "thin", "little on record, none of it directional"
    if n_events <= 2:
        return "thin", "only {0} evidence item{1} on record".format(
            n_events, "" if n_events == 1 else "s")
    if decided_kind == "vote":
        if n_directional >= 3:
            return _conflicted("strong",
                               "a vote corroborated by {0} further directional item{1}".format(
                                   n_directional - 1, "" if n_directional == 2 else "s"))
        if decided_whip == "whipped":
            return _conflicted("moderate", "decided by a whipped vote")
        return _conflicted("moderate", "a vote with little corroboration")
    if decided_kind == "debate":
        if n_directional >= 3:
            return _conflicted("moderate", "consistent speeches, but no vote on record")
        return "thin", "speeches only, and few of them directional"
    if decided_kind == "edm":
        if n_directional >= 3:
            return _conflicted("moderate", "sponsored motions, but no vote on record")
        return "thin", "motion sponsorship only"
    return "thin", "weak evidence kinds only (questions or co-signatures)"


def stance_to_column(stance):
    return {2: "++", 1: "+", 0: "0", -1: "-", -2: "--"}[max(-2, min(2, stance or 0))]


WAVER_MAJORITY = 5000
WAVER_MIN_GOOD_VOTES = 2
_TARGET_RE = re.compile(r"^(?:Tell|Urge|Ask)\s+(?:Sir\s+|Dame\s+|Dr\s+)?([A-Z][a-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,2}?)(?::|\s+to\b|\s+is\b|\s+knows\b|\s+No\b|\s*[-–—])")


def campaign_targets(conn):
    """{member_id: [(campaign name, launch_date)]} from MP-named petitions in
    campaign_performance ("Tell Clive Lewis: No to assisted suicide", "Urge Sarah
    Pochin to vote no..."). Name matching against the members cache; a first name
    plus surname must both appear, so "Tell Richard" matches nobody."""
    try:
        rows = conn.execute("SELECT name, launch_date FROM campaign_performance").fetchall()
        members = conn.execute("SELECT id, name FROM members").fetchall()
    except Exception:                                       # noqa: BLE001
        return {}
    by_key = {}
    for mid, mname in members:
        parts = re.sub(r"^(Sir|Dame|Dr|Mr|Mrs|Ms|Lord|Baroness)\s+", "", mname or "").split()
        if len(parts) >= 2:
            by_key.setdefault((parts[0].lower(), parts[-1].lower()), []).append(mid)
    out = {}
    for name, launched in rows:
        m = _TARGET_RE.match(name or "")
        if not m:
            continue
        parts = m.group(1).split()
        if len(parts) < 2:
            continue
        for mid in by_key.get((parts[0].lower(), parts[-1].lower()), []):
            out.setdefault(mid, []).append((name, launched))
    return out


def majorities(conn):
    try:
        return {r[0]: r[1] for r in conn.execute("SELECT member_id, majority FROM member_seat WHERE majority IS NOT NULL")}
    except Exception:                                       # noqa: BLE001
        return {}


def wavering(column, evs, majority, today=None):
    """(flag, why) -- a member placed against us on this area who nonetheless shows
    a reason to think they could move: backed our side in WAVER_MIN_GOOD_VOTES or
    more votes (the June 2025 safeguards: Myer 3, Daby 2), sits on a majority under
    WAVER_MAJORITY (Myer 214), or said something in the last year that did not read
    as hostile. Christopher, 12 Sept 2026: a list of those was drawable a year before
    the vote and held two of the five who moved."""
    if column not in ("-", "--"):
        return False, ""
    why = []
    good_votes = sum(1 for r in evs if r["kind"] == "vote" and (r["stance"] or 0) > 0)
    if good_votes >= WAVER_MIN_GOOD_VOTES:
        why.append("backed our side in %d vote%s" % (good_votes, "" if good_votes == 1 else "s"))
    if majority is not None and majority < WAVER_MAJORITY:
        why.append("majority %s" % format(int(majority), ","))
    cutoff = ((today or datetime.date.today()) - datetime.timedelta(days=365)).isoformat()
    soft = [r for r in evs if r["kind"] in ("debate", "pq", "edm") and r["date"] >= cutoff and (r["stance"] or 0) >= 0]
    if soft:
        why.append("%d recent contribution%s not hostile" % (len(soft), "" if len(soft) == 1 else "s"))
    return (bool(why), "; ".join(why))


def suggest_rows(conn, area, full_roster=False, overrides_cfg=None,
                 house="Commons", as_at=None):
    """5CA Plan rows for `area`, strongest evidence first.

    full_roster=False: one row per member (either House) with ledger
    activity on the area. full_roster=True: one row per sitting member of
    `house` -- Commons (members.current_mp=1, ~650) or Lords
    (members.current_peer=1, ~800), the actual voting body the 5CA
    targets; members the ledger has never seen sit at 0 with "No recorded
    activity", and the other chamber is excluded.

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
    # as_at reconstructs the sheet as it stood BEFORE a date -- the only
    # honest way to evaluate a prediction against a vote, since after the
    # vote the vote itself is evidence and the sheet would be marking its
    # own homework. Strictly earlier: a division on the day is excluded.
    where, args = "", []
    if as_at:
        where, args = "WHERE e.date < ?", [as_at]
    rows = conn.execute(
        "SELECT e.member_id, e.date, e.kind, e.ref, e.line, e.areas, e.excerpt, "
        "s.stance, s.why, m.name, m.party, m.seat, m.house "
        "FROM mp_events e LEFT JOIN stance s ON s.ref = e.ref "
        "LEFT JOIN members m ON m.id = e.member_id "
        "{0} ORDER BY e.date DESC".format(where), args).fetchall()

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
        flag = "current_peer" if house == "Lords" else "current_mp"
        roster = {r["id"]: r for r in conn.execute(
            "SELECT id, name, party, seat FROM members WHERE {0} = 1".format(flag))}
        per_member = {mid: evs for mid, evs in per_member.items() if mid in roster}

    out = []
    targets = campaign_targets(conn)
    maj = majorities(conn)
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
        column = stance_to_column(stance)
        n_pos = sum(1 for r in evs if (r["stance"] or 0) > 0)
        n_neg = sum(1 for r in evs if (r["stance"] or 0) < 0)
        tier, tier_why = suggest_confidence(column, best["kind"], _whip(best),
                                            len(evs), n_pos + n_neg, conflict,
                                            n_minority=min(n_pos, n_neg))
        waver, waver_why = wavering(column, evs, maj.get(mid), today=(datetime.date.fromisoformat(as_at) if as_at else None))
        if waver:
            comments.append("WAVERING: " + waver_why)
        hit = targets.get(mid) or []
        if hit:
            comments.append("TARGETED: " + "; ".join("%s (%s)" % (n, (d or "")[:10]) for n, d in hit[:3]))
        out.append({
            "member_id": mid,
            "decision_maker": name + (" ({0})".format(detail) if detail else ""),
            "house": first["house"] or "",
            "column": column,
            "conflict": conflict,
            "wavering": waver,
            "wavering_why": waver_why,
            "targeted": [n for n, _d in hit],
            "n_events": len(evs),
            "confidence": tier,
            "confidence_why": tier_why,
            "comments": " | ".join(comments),
            # What actually decided the placement. Both the "moved" and the
            # "based on" columns depend on this: a change of deciding evidence
            # means the member moved, the same evidence rescored means we did.
            "decided_kind": best["kind"],
            "decided_date": best["date"],
            "decided_ref": best["ref"],
        })

    for mid, m in roster.items():
        if mid in per_member:
            continue
        detail = ", ".join(x for x in (m["party"], m["seat"]) if x)
        out.append({
            "member_id": mid,
            "decision_maker": (m["name"] or "Member {0}".format(mid))
                              + (" ({0})".format(detail) if detail else ""),
            "house": house,
            "column": "0",
            "conflict": False,
            "wavering": False, "wavering_why": "", "targeted": [],
            "n_events": 0,
            "confidence": None,
            "confidence_why": None,
            "comments": "No recorded activity on this area (ledger from 2026-02-03)",
            "decided_kind": None, "decided_date": None, "decided_ref": None,
        })

    order = {c: i for i, c in enumerate(COLUMNS)}
    out.sort(key=lambda r: (order[r["column"]], -r["n_events"], r["decision_maker"]))
    return out
