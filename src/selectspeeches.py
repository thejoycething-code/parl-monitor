"""Choose the speeches worth cutting (Christopher, 2026-09-11: "more people spoke
against than just six. Let's select the best and crop those. We should have some
system that does that for us").

The reel draft took the LONGEST passages of the pass-read speakers, which is a fact
about word counts, not about which speeches a campaign should carry. This asks one
question of the model, once, over every confirmed-onside member who made a speech
(not an intervention): rank them for campaign value as standalone video, and name the
30-60 second passage you would cut. Then it checks the model's work the way the
report checker does -- every passage must be verbatim in the member's own words, every
name must be a member who spoke -- and writes selection.md (the ranking, with reasons)
and, on request, a sequence.md for the top N that tools/social_cut.py and
tools/speech_cut.py already understand.

Onside is still the checklist's decision. The selector never widens it; it only
orders what a person has already confirmed.
"""

import json
import re

from src import socialcut as sc

MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000          # per batch of BATCH speakers; two runs of 21 overran 12,000 on 11 Sept 2026
BATCH = 8                  # speakers per call, so the reply never nears the budget
MIN_WORDS = 250            # below this a contribution is an intervention, not a speech
WORDS_SHOWN = 700          # of the longest contribution, per member, to the judge

SYSTEM_PROMPT = """You are the picture editor for a campaign that OPPOSED the Bill debated here. You will be given the speeches of members who spoke against it. Rank them by their value as a standalone social video clip for that campaign.

Judge each speech on: one clear argument a viewer can repeat; emotional force; a passage of 30-60 seconds (roughly 75-150 words) in the member's OWN words that stands alone without the debate around it; a distinct angle from the others (personal testimony, medical authority, disability, coercion, palliative care, the vote's process, faith, law); and the speaker's standing (front bench, doctor, disabled member, someone who changed their vote).

Return ONLY a JSON array, one object per speaker, every speaker included:
[{"name": "<exactly as given>", "score": <1-10>, "angle": "<two to five words>", "why": "<at most fifteen words>", "passage": "<verbatim consecutive sentences from the speech, 75-150 words, copied exactly>"}]

RULES. Copy passages VERBATIM from the text supplied: never tidy, merge or paraphrase; if no passage of that length stands alone, copy the best shorter one. Never invent a name or a fact. Score honestly: a speech that is worthy but not clip-able scores low."""


def candidates(speeches, min_words=MIN_WORDS, words_shown=WORDS_SHOWN):
    """Confirmed-onside members with a real speech: [{name, party, seat, words, text, full_text, url}]."""
    out = []
    for s in speeches:
        if s.get("confirmed") != "yes":
            continue
        best = max(s.get("contributions") or [], key=lambda c: c.get("words") or 0, default=None)
        if not best or (best.get("words") or 0) < min_words:
            continue
        out.append({"name": s["name"], "party": s.get("party") or "", "seat": s.get("seat") or "",
                    "words": best.get("words") or 0, "url": best.get("url") or "",
                    "text": " ".join((best.get("text") or "").split()[:words_shown]),
                    "full_text": " ".join((c.get("text") or "") for c in s.get("contributions") or [])})
    return out


def build_payload(meta, cands, model=MODEL):
    user = {"debate": {"title": meta.get("title"), "date": meta.get("date"), "house": meta.get("house")},
            "speakers": [{k: c[k] for k in ("name", "party", "seat", "words", "text")} for c in cands]}
    return {"model": model, "max_tokens": MAX_TOKENS, "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": json.dumps(user, ensure_ascii=False)}]}


def parse_reply(text):
    """The JSON array, tolerating prose or a code fence around it -- and a reply cut
    off mid-array, from which every complete object is kept."""
    text = text or ""
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            rows = json.loads(m.group(0))
            return [r for r in rows if isinstance(r, dict) and r.get("name")]
        except ValueError:
            pass
    rows = []
    for obj in re.finditer(r"\{[^{}]*\}", text, re.S):
        try:
            r = json.loads(obj.group(0))
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("name"):
            rows.append(r)
    return rows


def _norm(text):
    text = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"(?<![A-Za-z])'|'(?![A-Za-z])", "", text)
    return re.sub(r"[^a-z0-9' ]", "", re.sub(r"\s+", " ", text).lower())


def verify(rows, cands):
    """Keep only what checks out: a known name, a numeric score, a passage that is
    verbatim in the member's words (or dropped, with a note). Returns (ranked, problems)."""
    by_name = {c["name"]: c for c in cands}
    ranked, problems = [], []
    for r in rows:
        c = by_name.get(r["name"])
        if not c:
            problems.append("unknown speaker from the judge: %s" % r["name"])
            continue
        try:
            score = float(r.get("score"))
        except (TypeError, ValueError):
            problems.append("%s: no numeric score" % r["name"])
            continue
        passage = " ".join((r.get("passage") or "").split())
        if passage and _norm(passage) not in _norm(c["full_text"]):
            problems.append("%s: the judge's passage is not verbatim; dropped" % r["name"])
            passage = ""
        ranked.append({"name": c["name"], "party": c["party"], "seat": c["seat"], "url": c["url"],
                       "score": score, "angle": (r.get("angle") or "").strip(), "why": (r.get("why") or "").strip(),
                       "passage": passage, "seconds": sc.spoken_seconds(passage) if passage else 0.0})
    missing = set(by_name) - {r["name"] for r in ranked}
    for name in sorted(missing):
        problems.append("%s: not ranked by the judge" % name)
    ranked.sort(key=lambda r: (-r["score"], r["name"]))
    return ranked, problems


def judge(meta, cands, api_key, transport=None, conn=None, log=print, batch=BATCH):
    """One call per BATCH speakers, scores pooled. Scores are comparable across
    batches because the rubric is absolute (1-10 against fixed criteria), not a
    ranking within the batch."""
    from src import spend, stance
    if not cands:
        raise SystemExit("no confirmed-onside speaker made a speech of %d words or more" % MIN_WORDS)
    rows, texts, usage = [], [], {"input_tokens": 0, "output_tokens": 0}
    for i in range(0, len(cands), batch):
        payload = build_payload(meta, cands[i:i + batch])
        reply = (transport or stance._default_transport)(payload, api_key)
        u = reply.get("usage") or {}
        usage["input_tokens"] += u.get("input_tokens") or 0
        usage["output_tokens"] += u.get("output_tokens") or 0
        if conn is not None:
            spend.record(conn, "speech-pick", reply.get("model") or MODEL, u)
        text = "".join(b.get("text", "") for b in (reply.get("content") or []) if b.get("type") == "text")
        if reply.get("stop_reason") == "max_tokens":
            log("[warn] batch %d: the judge's reply hit max_tokens (%d); the JSON is probably cut off" % (i // batch + 1, MAX_TOKENS))
        texts.append(text)
        rows.extend(parse_reply(text))
    text = "\n\n".join(texts)
    ranked, problems = verify(rows, cands)
    if not ranked:
        problems.append("the judge returned nothing usable (stop_reason %s, %d chars, %d rows parsed)"
                        % (reply.get("stop_reason"), len(text), len(rows)))
    return ranked, problems, usage, text


def selection_md(meta, ranked, problems, top):
    lines = ["# Selection: %s, %s" % (meta.get("title"), meta.get("date")), "",
             "*Ranked by one model call over every confirmed-onside member who made a speech of %d words or more;"
             " passages verified verbatim against the member's words. The top %d go to sequence.md. Onside itself"
             " is the checklist's decision, not the judge's.*" % (MIN_WORDS, top), "",
             "| # | Member | Score | Angle | Why |", "|---|---|---|---|---|"]
    for i, r in enumerate(ranked, 1):
        mark = "**" if i <= top else ""
        lines.append("| %d | %s[%s](%s)%s | %.0f | %s | %s |" % (i, mark, r["name"], r["url"], mark, r["score"],
                                                                r["angle"].replace("|", "/"), r["why"].replace("|", "/")))
    lines += ["", "## Passages", ""]
    for i, r in enumerate(ranked, 1):
        lines += ["### %d. %s (%s, %s) — %.0f" % (i, r["name"], sc.PARTY.get(r["party"], r["party"]), r["seat"], r["score"]),
                  "> %s" % (r["passage"] or "(no verbatim passage from the judge; the sequence falls back to reel_passage)"),
                  "*%.0f seconds spoken*" % r["seconds"] if r["passage"] else "", ""]
    if problems:
        lines += ["## Checks", ""] + ["* %s" % p for p in problems] + [""]
    return "\n".join(l for l in lines if l is not None)


def sequence_md(meta, ranked, top, speeches, patterns):
    """A sequence.md for the top N, in ranked order: the judge's passage when it is
    reel length, otherwise reel_passage over the member's longest contribution."""
    by_name = {s["name"]: s for s in speeches}
    out = ["# Sequence: %s, %s" % (meta.get("title"), meta.get("date")), "",
           "SELECTED by tools/pick_speeches.py: the top %d of the ranked speeches in selection.md, in rank order."
           " Passages are the judge's where they run %.0f-%.0f seconds and are verbatim, else reel_passage." % (top, sc.REEL_FLOOR_S, sc.REEL_HARD_CAP_S), ""]
    for r in ranked[:top]:
        passage = r["passage"] if r["passage"] and sc.REEL_FLOOR_S <= r["seconds"] <= sc.REEL_HARD_CAP_S else ""
        if not passage:
            s = by_name.get(r["name"])
            best = max(s["contributions"], key=lambda c: c.get("words") or 0) if s and s.get("contributions") else None
            passage = sc.reel_passage(best["text"], patterns) if best else None
        if not passage:
            out += ["<!-- %s: no reel-length passage found; add one by hand -->" % r["name"], ""]
            continue
        name = r["name"] if r["name"].endswith(" MP") else r["name"] + " MP"
        out += ["## %s" % name, "party: %s · %s" % (sc.PARTY.get(r["party"], r["party"]), r["seat"]), "> %s" % passage, ""]
    return "\n".join(out)
