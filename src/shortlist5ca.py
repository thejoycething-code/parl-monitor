"""Which 5CA readings to sign first: a ranked shortlist per country (11 October 2026).

The UK picks its past votes by hand from a review queue
(tools/find_division_candidates.py, tools/review_divisions.py,
docs/division-candidates*.md): the queue finds candidates, a person decides.
The new countries have the opposite problem. src/country5ca.py has already
drafted a reading for every watched and tier-1 vote (975 of them on
10 October 2026), and nothing is placed until a named person confirms each
one. Read in date order that backlog is not tractable. This module ranks it,
so a signer starts with the votes that matter most to a 5CA and reaches a
first publishable sheet soonest.

WHAT IT RANKS. Every reading in config/<cc>_stance.yaml that is not
confirmed: proposed readings (`status: draft` with values), procedural calls
(`placeable: false`) and the readings that need a person's values
(`needs_reading`). Confirmed readings are left out.

HOW (points, by rules, no AI call; each reason is printed with the item):

  * the kind of vote (src/country5ca.vote_kind, as drafted): the whole text
    +30, a motion to reject the text or an inverted vote +25, an
    amendment or article -10, procedure -30;
  * the LAST vote on the whole text (or to reject it) on its bill: +10, the
    decisive one of a bill's several readings;
  * a watched bill +15 (otherwise tier 1 +5);
  * values already proposed (one tick to sign) +15;
  * a close margin (Yes against No): within 5% +20, 10% +14, 20% +8;
    near-unanimous (the smaller side under 5% of those voting) -15;
  * groups split (from the entry's `lobbies:` line, or the store's positions
    when the line is missing): +3 per split group (at most +15) and +1 per
    two members against their group's majority (at most +10);
  * a vote-meaning line ready (src/vote_meanings.py: a person's, the free
    judge's, or a rule line in full English) +10, a rule line quoting the
    source's own language +3;
  * it feeds a live campaign (data/campaigns/<cc>/*.json): named as an
    outcome +25, on the campaign's area and chamber +10; or a campaign brief
    (data/country-briefs/<cc>.json, the brief's bill) +10;
  * recent: within 90 days +15, a year +10, two years +5;
  * only collated-only areas (config/stance_overrides.yaml
    `excluded_from_5ca`, e.g. migration): -100, last, it can never place anyone;
  * no longer on our ground in the store (a reclassification took its areas,
    src/country5ca.off_ground; needs the store): -100, last, marked with the
    command that prunes it.

Ties go to the newer vote, then the key.

WHAT IT WRITES. docs/5ca-<cc>-shortlist.md: the top N with why each
matters, the meaning line, the proposed values if any and the exact command
that signs it, then the best few per area. And `digest_lines`, the top 5 per
country that lead the weekly stance digest (src/country5ca.digest_text).

NOTHING HERE CONFIRMS ANYTHING. It reads the stance file, the campaign and
brief ledgers and (optionally, read-only) the store; it writes only the
shortlist document. The commands it prints are for a named person to run
after reading the item: tools/country_5ca.py --confirm still refuses a
`needs_reading` entry and anyone not listed in config/stance_signers.yaml.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shlex

from src import country5ca as c5
from src import readings5ca as r5

ROOT = c5.ROOT
CAMPAIGN_DIR = os.path.join(ROOT, "data", "campaigns")
BRIEFS_LEDGER_DIR = os.path.join(ROOT, "data", "country-briefs")
TOP = 20                 # items in the document
PER_AREA = 3             # items per area in the document's area section
DIGEST_TOP = 5           # items per country in the weekly DM

KIND_POINTS = {"final": 30, "reject": 25, "inverted": 25, "other": 0, "amendment": -10,
               "procedural": -30}
KIND_REASON = {"final": "a vote on the whole text", "reject": "a motion to reject the text",
               "inverted": "a vote whose Yes rejects the text",
               "amendment": "amendment-level", "procedural": "procedural",
               "other": "kind of vote not recognised"}


def shortlist_path(cc, docs_dir=None):
    return os.path.join(docs_dir or c5.DOCS, "5ca-{0}-shortlist.md".format(cc))


# --- reading the entry's own numbers ------------------------------------------------------

def tally(e, labels):
    """(yes, no) from the entry's `result:` ("Za 230, Przeciw 198, ..."), or
    None when it holds no numbers for both lobbies."""
    text = str(e.get("result") or "")
    got = []
    for label in labels:
        m = re.search(r"(?:^|[;,.(]\s*){0}\s+(\d+)".format(re.escape(label)), text)
        got.append(int(m.group(1)) if m else None)
    if None in got:
        return None
    return got[0], got[1]


_SIDE = re.compile(r"^\s*(.+?):\s*(.+)$")
_PARTY = re.compile(r"\s*(.+?)\s+(\d+)\s*$")


def groups(lobbies_text, labels):
    """{group: {'yea': n, 'nay': n, 'abstain': n}} from a `lobbies:` line
    ("Za: KO 150, PiS 2. Przeciw: PiS 180. Abstain: PSL 3"), {} if none."""
    text = re.sub(r"\s*\(counts include.*$", "", str(lobbies_text or ""))
    sides = {labels[0]: "yea", labels[1]: "nay", "Abstain": "abstain"}
    out = {}
    # Split on ". " only where the next words are a lobby label and a colon.
    pat = "|".join(re.escape(x) for x in sorted(sides, key=len, reverse=True))
    for chunk in re.split(r"\.\s+(?=(?:{0}):)".format(pat), text):
        m = _SIDE.match(chunk.strip().rstrip("."))
        if not m or m.group(1).strip() not in sides:
            continue
        side = sides[m.group(1).strip()]
        for part in m.group(2).split(", "):
            pm = _PARTY.match(part.rstrip(".").rstrip("…").strip())
            if pm:
                g = out.setdefault(pm.group(1), {"yea": 0, "nay": 0, "abstain": 0})
                g[side] += int(pm.group(2))
    return out


def splits(gs):
    """(groups split between Yes and No, members against their group's majority)."""
    split, rebels = [], 0
    for name, g in gs.items():
        if name.strip() in ("", "?"):       # no group recorded: nothing to break ranks with
            continue
        if g["yea"] and g["nay"]:
            split.append(name)
            rebels += min(g["yea"], g["nay"])
    return sorted(split), rebels


# --- what feeds a campaign or a brief -----------------------------------------------------

def campaign_context(cc, base=None):
    """{'outcomes': {key: slug}, 'areas': {(area, chamber): slug}} from the
    country's campaign files (src/country_campaign.py)."""
    base = base or CAMPAIGN_DIR
    out = {"outcomes": {}, "areas": {}}
    d = os.path.join(base, cc)
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, f), encoding="utf-8") as h:
                camp = json.load(h)
        except (OSError, ValueError):
            continue
        slug = camp.get("slug") or f[:-5]
        for o in camp.get("outcomes") or []:
            out["outcomes"][str(o.get("key"))] = slug
        if camp.get("area") is not None:
            out["areas"][(int(camp["area"]), str(camp.get("chamber")))] = slug
    return out


def brief_context(cc, base=None):
    """{bill key: (slug, ready)} from the country's brief ledger (src/country_briefs.py)."""
    path = os.path.join(base or BRIEFS_LEDGER_DIR, "{0}.json".format(cc))
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as h:
            got = json.load(h)
    except (OSError, ValueError):
        return {}
    out = {}
    for slug, b in (got.items() if isinstance(got, dict) else []):
        if isinstance(b, dict) and b.get("key"):
            out.setdefault(str(b["key"]), (slug, bool(b.get("ready"))))
    return out


# --- the meaning lines ----------------------------------------------------------------------

def meanings_for(cc, entries, conn=None, config_dir=None):
    """{key: meaning} (src/vote_meanings.py): the store's when open, else
    computed from the entry's own wording. Never fails the shortlist."""
    from src import vote_meanings as vm
    out = {}
    if conn is not None:
        try:
            out = vm.lookup_many(conn, cc, list(entries), config_dir)
        except Exception:                    # an old store: fall back to the rules
            out = {}
    try:
        people, _ = vm.overrides(cc, config_dir)
        wl, bills = vm._context(cc, config_dir)
    except Exception:
        return out
    for k, e in entries.items():
        if k not in out:
            try:
                m = vm.entry_meaning(cc, e, config_dir, people, wl, bills)
            except Exception:
                m = None
            if m:
                out[k] = m
    return out


# --- the score --------------------------------------------------------------------------

def bucket(e):
    """'proposed' | 'procedural' | 'needs_reading' | 'confirmed'."""
    if c5._is_confirmed(e) or e.get("status") == "confirmed":
        return "confirmed"
    if e.get("status") == "needs_reading" or e.get("status") not in ("draft",):
        return "needs_reading"
    if e.get("placeable") is False:
        return "procedural"
    return "proposed"


def _bill_of(k, e):
    """What a vote decides: a motion is its own text (the Netherlands' moties
    tabled in a bill's dossier), otherwise the watched bill or the subject."""
    if re.search(c5.MOTION, c5.fold(e.get("title"))):
        return k
    return e.get("watched") or e.get("on") or None


def last_decisive(entries):
    """The keys that are the latest final or reject vote on their bill."""
    best = {}
    for k, e in entries.items():
        if e.get("vote_kind") not in c5.FINAL_KINDS:
            continue
        bill = _bill_of(k, e)
        if not bill:
            continue
        rank = (str(e.get("dated") or ""), k)
        if bill not in best or rank > best[bill][0]:
            best[bill] = (rank, k)
    return {k for _, k in best.values()}


def score(cc, k, e, ctx, today):
    """(points, [reasons]) for one unconfirmed reading. `ctx` holds the
    country's context (see `rank`)."""
    spec = c5.SPECS[cc]
    pts, why = 0, []
    kind = e.get("vote_kind") or c5.vote_kind(e.get("title"))[0]
    kp = KIND_POINTS.get(kind, 0)
    pts += kp
    if kp > 0:
        why.append(KIND_REASON[kind])
    elif kind in ("amendment", "procedural"):
        why.append(KIND_REASON[kind] + " (lower)")
    if k in ctx["decisive"]:
        pts += 10
        why.append("the last such vote on its bill")
    if e.get("watched"):
        pts += 15
        why.append("watched bill {0}".format(e["watched"]))
    elif e.get("tier") == 1:
        pts += 5
        why.append("tier 1")
    b = bucket(e)
    if b == "proposed":
        pts += 15
        why.append("values proposed: one tick to sign")
    t = tally(e, spec.labels)
    gs = ctx["groups"].get(k) or {}
    if t is None and gs:
        t = (sum(g["yea"] for g in gs.values()), sum(g["nay"] for g in gs.values()))
    if t and sum(t) > 0:
        y, n = t
        margin = abs(y - n) / float(y + n)
        if min(y, n) / float(y + n) < 0.05:
            pts -= 15
            why.append("near-unanimous ({0}-{1}, lower)".format(y, n))
        elif margin <= 0.05:
            pts += 20
            why.append("close: {0}-{1}".format(y, n))
        elif margin <= 0.10:
            pts += 14
            why.append("close-ish: {0}-{1}".format(y, n))
        elif margin <= 0.20:
            pts += 8
            why.append("contested: {0}-{1}".format(y, n))
    split, rebels = splits(gs)
    if split:
        pts += min(15, 3 * len(split)) + min(10, rebels // 2)
        why.append("split {0} ({1} against their group)".format(
            ", ".join(split[:4]) + (" and {0} more".format(len(split) - 4) if len(split) > 4 else ""),
            rebels))
    m = ctx["meanings"].get(k)
    if m and m.get("yes"):
        if m.get("source") in ("person", "judge") or m.get("quality") == "full":
            pts += 10
            why.append("meaning line ready")
        else:
            pts += 3
            why.append("meaning line quotes the source")
    camps, briefs = ctx["campaigns"], ctx["briefs"]
    if k in camps["outcomes"]:
        pts += 25
        why.append("an outcome of campaign {0}".format(camps["outcomes"][k]))
    else:
        for a in e.get("areas") or []:
            slug = camps["areas"].get((int(a), str(e.get("chamber"))))
            if slug:
                pts += 10
                why.append("on campaign {0}'s ground".format(slug))
                break
        else:
            hit = briefs.get(str(e.get("watched") or ""))
            if hit:
                pts += 10
                why.append("feeds brief {0}{1}".format(hit[0], "" if hit[1] else " (NOT READY until signed)"))
    dated = str(e.get("dated") or "")[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", dated):
        age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(dated)).days
        if age <= 90:
            pts += 15
            why.append("recent")
        elif age <= 365:
            pts += 10
            why.append("this year")
        elif age <= 730:
            pts += 5
    areas = [int(a) for a in e.get("areas") or []]
    if areas and all(a in ctx["excluded"] for a in areas):
        pts -= 100
        why.append("collated-only area: places nobody (lowest)")
    if k in ctx.get("off_ground", ()):
        pts -= 100
        why.append("no longer on our ground in the store (reclassified): prune with "
                   "tools/country_5ca.py --cc {0} --prune-off-ground (lowest)".format(cc))
    return pts, why


def rank(cc, config_dir=None, conn=None, today=None, campaigns_dir=None, briefs_dir=None):
    """The unconfirmed readings of one country, best first: a list of dicts
    {key, entry, points, why, bucket, meaning}."""
    today = today or datetime.date.today().isoformat()
    divs, _, _ = c5.load(cc, config_dir)
    pending = {k: e for k, e in divs.items() if bucket(e) != "confirmed"}
    if not pending:
        return []
    spec = c5.SPECS[cc]
    gs = {}
    for k, e in pending.items():
        g = groups(e.get("lobbies"), spec.labels)
        if not g and conn is not None:
            try:
                g = groups(c5.lobbies(spec, c5.positions(conn, cc, k)), spec.labels)
            except Exception:
                g = {}
        gs[k] = g
    try:
        excluded = r5.excluded_areas(ROOT)
    except Exception:
        excluded = set()
    ctx = {"decisive": last_decisive(divs), "groups": gs,
           "meanings": meanings_for(cc, pending, conn, config_dir),
           "campaigns": campaign_context(cc, campaigns_dir), "briefs": brief_context(cc, briefs_dir),
           "excluded": excluded, "off_ground": set()}
    if conn is not None:
        try:
            ctx["off_ground"] = c5.off_ground(conn, cc) & set(pending)
        except Exception:
            ctx["off_ground"] = set()
    out = []
    for k, e in pending.items():
        pts, why = score(cc, k, e, ctx, today)
        out.append({"key": k, "entry": e, "points": pts, "why": why, "bucket": bucket(e),
                    "meaning": ctx["meanings"].get(k)})
    out.sort(key=lambda x: (-x["points"], 0 if x["entry"].get("dated") else 1,
                            _neg(str(x["entry"].get("dated") or "")), x["key"]))
    return out


def _neg(iso):
    return tuple(-ord(ch) for ch in iso)


# --- the commands -----------------------------------------------------------------------

def signer_name(cc):
    """The name for the printed command: the country's one named signer, else Chris."""
    named = [s for s in c5.signers(cc) if s not in c5.ALWAYS_SIGNS]
    return named[0] if len(named) == 1 else c5.ALWAYS_SIGNS[0]


def command(cc, item, by=None):
    """The exact command that signs this reading (to run after reading it)."""
    by = by or signer_name(cc)
    sign = "python3 tools/country_5ca.py --cc {0} --confirm {1} --by {2}".format(
        cc, shlex.quote(item["key"]), shlex.quote(by))
    if item["bucket"] == "needs_reading":
        return ("first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) "
                "under `{0}` in config/{1}_stance.yaml and set `status: draft`, then `{2}`".format(
                    item["key"], cc, sign))
    return "`{0}`".format(sign)


def _values(cc, e):
    spec = c5.SPECS[cc]
    if e.get("placeable") is False:
        return "procedural: evidence only, places nobody ({0})".format(r5.clip(e.get("reason"), 160))
    if e.get("yea") is None and e.get("nay") is None:
        return None
    return "{0} {1}, {2} {3}".format(spec.labels[0], c5._fmt(e.get("yea")), spec.labels[1],
                                     c5._fmt(e.get("nay")))


# --- the document -----------------------------------------------------------------------

def shortlist_markdown(cc, ranked, today=None, top=TOP, per_area=PER_AREA):
    from src import vote_meanings as vm
    from src.latam import AREA_LABELS
    spec = c5.SPECS[cc]
    today = today or datetime.date.today().isoformat()
    by = signer_name(cc)
    counts = {}
    for it in ranked:
        counts[it["bucket"]] = counts.get(it["bucket"], 0) + 1
    out = ["# {0} 5CA: sign these first".format(spec.name), "",
           "Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on {0}, by rules, "
           "no AI call. **This list confirms nothing.** It ranks the {1} readings waiting in "
           "`config/{2}_stance.yaml` ({3} proposed, {4} procedural, {5} need reading) so a signer "
           "starts with the votes that matter most: the decisive votes on watched bills, close "
           "margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, "
           "recent first; procedural, near-unanimous and amendment-level votes sink. Read each item "
           "(the full reading is in `docs/5ca-{2}-readings.md`), then run its command. The full "
           "rules are at the end.".format(today, len(ranked), cc, counts.get("proposed", 0),
                                         counts.get("procedural", 0), counts.get("needs_reading", 0)),
           "",
           "The commands sign as **{0}**{1}. `--confirm` refuses anyone not named in "
           "`config/stance_signers.yaml` (Chris signs for every country) and any reading that still "
           "needs reading.".format(by, " (no country signer is named yet; replace the name with "
                                       "whoever signs)" if by in c5.ALWAYS_SIGNS else ""), ""]
    shown = ranked[:top]
    ready = [it["key"] for it in shown if it["bucket"] in ("proposed", "procedural")]
    if ready:
        out += ["**All the proposed ones below in one go**, once each is read and agreed "
                "(leave out any you do not accept):", "",
                "    python3 tools/country_5ca.py --cc {0} --confirm {1} --by {2}".format(
                    cc, " ".join(shlex.quote(k) for k in ready), shlex.quote(by)), ""]
    out += ["## Top {0}".format(len(shown)), ""]
    for i, it in enumerate(shown, 1):
        e = it["entry"]
        out.append("### {0}. `{1}` {2}".format(i, it["key"], r5.clip(e.get("title"), 140)))
        out.append("")
        out.append("- **Why first ({0} points):** {1}.".format(
            it["points"], "; ".join(it["why"]) or "no signal"))
        meta = [str(x) for x in (e.get("dated"), spec.chambers.get(e.get("chamber"), e.get("chamber")),
                                 r5.clip(e.get("result"), 140)) if x]
        if meta:
            out.append("- **When / result:** " + "; ".join(meta))
        if e.get("on"):
            out.append("- **On:** " + r5.clip(e["on"], 220))
        if e.get("areas"):
            out.append("- **Area:** " + ", ".join(AREA_LABELS.get(int(a), str(a)) for a in e["areas"]))
        if e.get("lobbies"):
            out.append("- **Lobbies:** " + r5.clip(e["lobbies"], 300))
        ml = vm.line(it["meaning"], cc) if it.get("meaning") else None
        out.append("- " + (ml or "Meaning: none yet (no line from a person, the judge or the rules)."))
        vals = _values(cc, e)
        if vals:
            out.append("- **Proposed:** " + vals)
            if e.get("why_yea"):
                out.append("  - " + r5.clip(e["why_yea"], 220))
        else:
            out.append("- **Proposed:** nothing: " + r5.clip(
                e.get("read_first") or "needs a person's reading", 260))
        if e.get("flag"):
            out.append("- **Flag:** " + r5.clip(e["flag"], 240))
        out.append("- **Sign:** " + command(cc, it, by))
        out.append("")
    areas = {}
    for i, it in enumerate(ranked, 1):
        for a in it["entry"].get("areas") or []:
            areas.setdefault(int(a), []).append((i, it))
    if areas:
        out += ["## By area (rank in the whole list)", ""]
        for a in sorted(areas):
            got = areas[a][:per_area]
            out.append("- **{0}** ({1} waiting): {2}".format(
                AREA_LABELS.get(a, "area {0}".format(a)), len(areas[a]),
                "; ".join("#{0} `{1}` {2}, {3} pts".format(i, it["key"], it["entry"].get("dated") or "?",
                                                           it["points"]) for i, it in got)))
        out.append("")
    out += ["## How the points work", "",
            "Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article "
            "-10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 "
            "+5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; "
            "near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 "
            "per two members against their group (at most +10). Meaning line ready +10 (quoting "
            "the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief "
            "+10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: "
            "they place nobody); no longer on our ground in the store -100. Ties: newer first.", ""]
    return "\n".join(out) + "\n"


def write_shortlist(cc, config_dir=None, docs_dir=None, conn=None, today=None, top=TOP,
                    log=print, campaigns_dir=None, briefs_dir=None):
    """Write docs/5ca-<cc>-shortlist.md; remove a stale one when nothing waits.
    Returns the ranked list."""
    ranked = rank(cc, config_dir, conn, today, campaigns_dir, briefs_dir)
    path = shortlist_path(cc, docs_dir)
    if not ranked:
        if os.path.exists(path):
            os.remove(path)
        return ranked
    with open(path, "w", encoding="utf-8") as h:
        h.write(shortlist_markdown(cc, ranked, today, top))
    log("  {0}: shortlist of {1} waiting -> {2} (top: {3})".format(
        cc, len(ranked), os.path.relpath(path, ROOT) if path.startswith(ROOT) else path,
        ", ".join(it["key"] for it in ranked[:3])))
    return ranked


QUIET_REASONS = ("watched bill", "values proposed", "meaning line")


def short_why(why, n=3):
    """The reasons that tell items apart, for the DM: the bracket already says
    whether values are proposed, and nearly every item is on a watched bill."""
    return [w.replace("the last such vote on its bill", "the decisive one")
            for w in why if not w.startswith(QUIET_REASONS)][:n]


def digest_lines(cc, config_dir=None, today=None, n=DIGEST_TOP, ranked=None):
    """The top `n` of a country as DM lines, best first."""
    ranked = rank(cc, config_dir, None, today) if ranked is None else ranked
    out = []
    for i, it in enumerate(ranked[:n], 1):
        e = it["entry"]
        if it["bucket"] == "procedural":
            vals = "procedural, evidence only"
        elif it["bucket"] == "needs_reading":
            vals = "needs reading"
        else:
            vals = _values(cc, e) or "no values"
        out.append("  {0}. `{1}` {2} {3}: {4} [{5}]".format(
            i, it["key"], e.get("dated") or "?", r5.clip(e.get("title"), 60),
            "; ".join(short_why(it["why"])) or "no signal", vals))
    return out
