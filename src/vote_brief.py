"""The same-day vote brief for the US, Ireland and Australia: the shared half.

Christopher, 9 October 2026: "start the same-day vote briefs" for the US,
Ireland and Australia, in parity with the UK division watch
(tools/division_brief.py). Each country's tool (tools/us_division_brief.py,
ie_division_brief.py, au_division_brief.py) reads its source directly,
classifies each recorded vote the way that country's collector does, and
hands this module a list of Vote dicts. This module decides what is new,
writes data/briefs/<cc>-division-<id>.md and sends ONE DM per run.

THE RULES (the UK brief's, unchanged):

  * Facts of the record only. No verdict: the brief never says a vote was
    won or lost for anyone, good or bad. The result is the record's own word
    ("Passed", "Carried", "Agreed to"). Which lobby is CitizenGO's is a
    signed human judgement in config/<cc>_stance.yaml, and the brief reports
    only the STATUS of that reading -- "awaiting sign-off" while it is a
    draft -- never its direction.
  * Speaks once per division: a brief that exists is neither rewritten nor
    resent (--force overrides), so overlapping slots, or the Mac Mini and a
    late GitHub backup, are harmless.
  * DMs go to Christopher alone: the recipient is fixed here, whatever the
    environment says.
  * No store. Each tool reads the source; the payloads it fetches are
    archived under data/raw and published by the job (raw_state.py --push).

A Vote dict carries:
  cc, key (the store's and the stance file's division key), file_key (safe
  for a filename), house (label), date, business (the measure or debate),
  question, result (the record's word), tally (a display string), parties
  [(party, {position: n})], positions (display order), names {position:
  [label]}, matched ('own text' | 'amendment' | 'bill only'), areas [int],
  terms [str], url, links [(label, url)], amendment (text or None), notes
  [str], on_ground (bool).
"""

from __future__ import annotations

import datetime
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from src import intel, publish  # noqa: E402
from src import readings5ca as r5  # noqa: E402

BRIEFS = os.path.join(ROOT, "data", "briefs")
REPO = "thejoycething-code/parl-monitor"
CHRISTOPHER = "U05LJP0BT61"
HIDDEN_AREAS = (11,)    # migration is collated, never campaigned (src/partner.py)
COUNTRY = {"us": "US Congress", "ie": "Oireachtas", "au": "Australian Parliament"}
# Words a brief of ours must never use about a vote: the result is the
# record's own word, and direction is a signed human judgement.
VERDICT_WORDS = re.compile(r"\b(win|wins|won|winning|defeat|defeated|victory|loss for|"
                           r"good news|bad news|our side|for us|against us)\b", re.I)


def visible(areas):
    return [a for a in (areas or []) if a not in HIDDEN_AREAS]


def area_names():
    return intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))


def brief_path(out_dir, vote):
    return os.path.join(out_dir, "{0}-division-{1}.md".format(vote["cc"], vote["file_key"]))


def safe_key(key):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", key or "").strip("-")


# --- the 5CA reading's status ------------------------------------------------

def stance_status(cc, key, path=None):
    """One line about the signed reading for this vote, never its direction."""
    path = path or os.path.join(ROOT, "config", "{0}_stance.yaml".format(cc))
    rel = os.path.relpath(path, ROOT)
    entry = r5.load_stance(path, "divisions").get(key)
    status = r5.status(entry)
    return {
        "none": "no 5CA reading for this vote yet ({0} has no entry).".format(rel),
        "draft": "reading awaiting sign-off (a draft in {0}).".format(rel),
        "unread": "listed in {0} to read first; no reading proposed.".format(rel),
        "unplaceable": "signed as evidence only in {0}: it places no member.".format(rel),
        "confirmed": "reading signed in {0}.".format(rel),
    }[status]


# --- rendering ---------------------------------------------------------------

def party_line(vote, limit=None):
    parts = []
    for party, counts in vote["parties"][:limit]:
        shown = [str(counts.get(p, 0)) for p in vote["split_positions"]]
        parts.append("{0} {1}".format(party, "–".join(shown)))
    return "; ".join(parts)


def brief_markdown(vote, names, stance, generated=None):
    v = vote
    out = ["# {0} division brief: {1}".format(COUNTRY[v["cc"]], " ".join((v["business"] or "").split())), ""]
    out.append("*{0}, {1}. Division {2}. Generated {3}. Facts of the record only: what a vote "
               "meant is a signed human reading (config/{4}_stance.yaml), never this brief's.*".format(
                   v["house"], v["date"], v["key"],
                   generated or datetime.datetime.now().isoformat(timespec="minutes"), v["cc"]))
    out.append("")
    if v.get("question"):
        out.append("**Question:** {0}".format(" ".join(v["question"].split())))
        out.append("")
    out.append("**Result: {0}. {1}.**".format(v["result"] or "not recorded", v["tally"]))
    out.append("")
    out.append("**What matched:** {0}. Areas: {1}.{2}".format(
        v["matched"], ", ".join(names.get(a, str(a)) for a in visible(v["areas"])) or "none",
        " Terms: {0}.".format(", ".join(v["terms"][:8])) if v.get("terms") else ""))
    out.append("")
    out.append("**5CA:** {0}".format(stance))
    out.append("")
    if v.get("amendment"):
        out.append("**Amendment:** {0}".format(" ".join(v["amendment"].split())))
        out.append("")
    for note in v.get("notes") or []:
        out.append("*{0}*".format(note))
        out.append("")
    out.append("Sources: " + " · ".join("[{0}]({1})".format(l, u) for l, u in
                                         [("the record", v["url"])] + list(v.get("links") or []) if u))
    out.append("")
    out.append("## By party")
    out.append("")
    out.append("| Party | " + " | ".join(v["split_positions"]) + " |")
    out.append("|---|" + "---|" * len(v["split_positions"]))
    for party, counts in v["parties"]:
        out.append("| {0} | {1} |".format(party, " | ".join(str(counts.get(p, 0)) for p in v["split_positions"])))
    out.append("")
    for position in v["positions"]:
        people = v["names"].get(position) or []
        if not people:
            continue
        out.append("## {0} ({1})".format(position, len(people)))
        out.append("")
        out.append("; ".join(sorted(people)))
        out.append("")
    out.append("---")
    out.append("")
    out.append("No meaning is attached here. Read the question in the record; a reading is signed "
               "through the 5CA sign-off guide for config/{0}_stance.yaml.".format(v["cc"]))
    return house_style("\n".join(out) + "\n")


def house_style(text):
    """No em dashes in anything we render, even quoted from the record
    (Hansard's 'the bells being rung\u2014')."""
    return text.replace(" \u2014 ", ", ").replace("\u2014", ", ")


def dm_text(vote, names, stance, brief_url):
    v = vote
    lines = [":ballot_box_with_ballot: *{0}, {1}: {2}*".format(
        v["house"], v["date"], " ".join((v["business"] or "").split())[:200])]
    if v.get("question"):
        lines.append("Question: {0}".format(" ".join(v["question"].split())[:300]))
    lines.append("Result: {0}. {1}.".format(v["result"] or "not recorded", v["tally"]))
    if v["parties"]:
        lines.append("By party ({0}): {1}.".format("–".join(v["split_positions"]), party_line(v, 6)))
    lines.append("Matched: {0} ({1}).".format(
        v["matched"], ", ".join(names.get(a, str(a)) for a in visible(v["areas"])) or "none"))
    lines.append("5CA: {0}".format(stance))
    lines.append("Brief: {0}".format(brief_url))
    lines.append("Record: {0}".format(v["url"]))
    return house_style("\n".join(lines))


# --- the run -----------------------------------------------------------------

def run(cc, votes, out_dir=BRIEFS, force=False, dm=True, secrets=None, log=print,
        stance_path=None, generated=None, sender=None):
    """Brief every NEW vote on our ground. Returns the number written."""
    names = area_names()
    ours = [v for v in votes if v["on_ground"]]
    log("{0}: {1} recorded vote(s) in the window, {2} on our ground.".format(cc, len(votes), len(ours)))
    os.makedirs(out_dir, exist_ok=True)
    written, messages = 0, []
    for v in ours:
        path = brief_path(out_dir, v)
        rel = "data/briefs/" + os.path.basename(path)
        if os.path.exists(path) and not force:
            log("  {0}: already briefed ({1})".format(v["key"], rel))
            continue
        stance = stance_status(cc, v["key"], stance_path)
        md = brief_markdown(v, names, stance, generated)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(md)
        written += 1
        log("  {0}: brief written -> {1}".format(v["key"], rel))
        url = "https://github.com/{0}/blob/main/{1}".format(REPO, rel)
        messages.append(dm_text(v, names, stance, url))
    if messages:
        text = "\n\n".join(messages)
        if len(messages) > 1:
            text = "*{0}: {1} divisions on our ground.*\n\n".format(COUNTRY[cc], len(messages)) + text
        if not dm:
            log("  DM not sent (--no-dm). It would read:\n" + text)
        else:
            got = dict(secrets if secrets is not None else publish.load_secrets())
            got["slack_dm_user_id"] = CHRISTOPHER      # Christopher alone, whatever the env says
            result = (sender or publish.slack_dm)(got, text)
            log("  DM: {0} ({1} division(s) in one message)".format(
                "sent" if result.get("message_ts") or result.get("ok") else
                result.get("skipped") or result.get("error") or "sent", len(messages)))
    log("{0}: {1} brief(s) written.".format(cc, written))
    return written


def window_start(today, days):
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()
