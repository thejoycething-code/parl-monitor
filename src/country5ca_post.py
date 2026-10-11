"""The new countries' 5CA, posted to Chris alone and kept current (11 October 2026).

The new-country counterpart of tools/post_5ca.py (the UK's 5CA briefing as a
canvas) and tools/republish_canvas.py (a canvas rewritten in place), for every
country in src/country5ca.COUNTRIES, per chamber and issue area.

WHAT IS RENDERED. Only what src/country5ca.publishable_sheets lets through:
a chamber and area with at least one CONFIRMED reading (status: confirmed,
confirmed_by, confirmed_on) that places someone, through the same gate as
the CSV sheets and the 5CA web pages, so a canvas, a sheet and a page cannot
disagree. The cut is the UK briefing's: the shape of the chamber, the allies
and opponents by name, the members with no placement (the list a campaigner
works), mixed records, and the readings line. Party-group countries (AT, PT,
NL: X5) keep the DERIVED label on every member placed from the group's vote.
A derived placement under a group label that is no group at all (the
non-attached, independents, mixed groups: country_edition.no_group_line,
#80) is EXCLUDED, never placed: there is no group line to carry to them.

WHERE IT GOES. To Chris alone, never a channel, never anything public:

  * a canvas shared with his user id only (publish.slack_preview_canvas,
    the debate report's route, with his id forced whatever secrets.yaml
    says), created once per chamber and area and afterwards REWRITTEN IN
    PLACE (publish.slack_update_canvas), so the link he holds stays good;
  * and/or (--to dm|both) the same cut as a DM to him.

A run that touches canvases sends ONE DM listing them with their links.

STATE. data/5ca/country-post-state.json records, per "cc|chamber|area",
the canvas id and url, a fingerprint of the confirmed readings it was
rendered from, and when. A rerun by hand rewrites the same canvas; the
weekly refresh (--refresh, jobs/editions-session-judge.sh, after the Sunday
5CA step) rewrites only canvases whose confirmed readings changed, creates
one for a newly publishable sheet, and rewrites a canvas whose sheet is no
longer publishable with a "no confirmed reading places anyone now" note.
Nothing changed, or nothing confirmed (the state on 11 October 2026): no
Slack call and no message at all.

Read-only on the store and the stance files; writes only the state file.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os

from src import country5ca as c5
from src import readings5ca as r5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "5ca", "country-post-state.json")
CHRIS = "U05LJP0BT61"            # the DM and the canvases go to Chris alone
DM_CAP = 30000
LIST_CAP = 200                   # names per list in one canvas
TARGETS = ("canvas", "dm", "both")
FP_VERSION = 1                   # bump to make every canvas re-render once

COLUMN_LABEL = {"++": "strong ally", "+": "leans our way", "0": "no placement",
                "-": "leans against", "--": "strong opponent"}


def secrets_for_chris(secrets=None):
    """The Slack secrets with the recipient forced to Chris, as every new-country DM."""
    if secrets is None:
        from src import publish
        secrets = publish.load_secrets()
    secrets = dict(secrets)
    secrets["slack_dm_user_id"] = CHRIS          # Chris alone, whatever secrets.yaml says
    secrets.pop("slack_channel_id", None)        # no channel is ever in reach
    return secrets


# --- the state file ------------------------------------------------------------------

def sheet_key(cc, chamber, area):
    return "{0}|{1}|{2}".format(cc, chamber, area)


def load_state(path=None):
    path = path or STATE_PATH
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as h:
        try:
            return json.load(h) or {}
        except ValueError:
            return {}


def save_state(state, path=None):
    path = path or STATE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as h:
        json.dump(state, h, indent=1, sort_keys=True, ensure_ascii=False)
        h.write("\n")


def fingerprint(listed):
    """What a canvas was rendered from: the CONFIRMED readings among the
    sheet's votes (their values and who signed them). A draft changing does
    not move it; a confirmation, a withdrawal or a re-signed value does."""
    got = []
    for e in sorted(listed, key=lambda e: str(e.get("key"))):
        if r5.status(e) != "confirmed" or e.get("status") != "confirmed":
            continue
        got.append([str(e.get("key")), e.get("yea"), e.get("nay"), e.get("placeable"),
                    e.get("confirmed_by"), str(e.get("confirmed_on") or "")])
    raw = json.dumps([FP_VERSION, got], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def has_confirmed(entries):
    return any(e.get("status") == "confirmed" and r5.status(e) == "confirmed"
               for e in entries.values())


# --- the render ----------------------------------------------------------------------

def area_name(area):
    from src.latam import AREA_LABELS
    name = AREA_LABELS.get(area, "area {0}".format(area))
    return name[:1].upper() + name[1:]


def chamber_name(cc, chamber):
    return c5.SPECS[cc].chambers.get(chamber) or str(chamber) or "parliament"


def title_for(cc, chamber, area):
    return "5CA working draft - {0}, {1}: {2}".format(
        c5.SPECS[cc].name, chamber_name(cc, chamber), area_name(area))


def non_attached_derived(row):
    """A member placed from a 'group' vote whose group is no group (#80)."""
    from src.country_edition import no_group_line
    return "[DERIVED]" in row["decision_maker"] and no_group_line(row.get("party"))


def split_rows(rows):
    """(kept, excluded): the derived placements of the non-attached excluded."""
    kept, excluded = [], []
    for r in rows:
        (excluded if non_attached_derived(r) else kept).append(r)
    return kept, excluded


def _names(rows, cap=LIST_CAP):
    if not rows:
        return "- none"
    out = ["- {0}{1}".format(r["decision_maker"], " (capped at +)" if r.get("capped") else "")
           for r in rows[:cap]]
    if len(rows) > cap:
        out.append("- and {0} more (the full sheet is in data/5ca/)".format(len(rows) - cap))
    return "\n".join(out)


def render(cc, sheet, today=None):
    """(title, canvas markdown, summary) for one publishable sheet."""
    today = today or datetime.date.today().isoformat()
    chamber, area = sheet["chamber"], sheet["area"]
    kept, excluded = split_rows(sheet["rows"])
    sitting = [r for r in kept if r["sitting"]]
    by = {c: [r for r in sitting if r["column"] == c] for c in r5.COLUMNS}
    former = [r for r in kept if not r["sitting"] and r["column"] != "0"]
    mixed = [r for r in kept if r.get("conflict")]
    derived = [r for r in kept if "[DERIVED]" in r["decision_maker"]]
    confirmed = [e for e in sheet["listed"] if e.get("status") == "confirmed"
                 and r5.status(e) == "confirmed"]
    country, ch, an = c5.SPECS[cc].name, chamber_name(cc, chamber), area_name(area)

    lines = [
        "*{0}, {1}: {2}. Five Column Analysis, working draft*".format(country, ch, an), "",
        "Placed ONLY from readings a named person has confirmed ({0} confirmed, {1} still "
        "unsigned for this area). A member is placed by a recorded vote whose meaning was "
        "signed off; an unsigned vote places nobody. The Target column is left to a "
        "campaigner.".format(sheet["signed"], sheet["unsigned"]), "",
        "*The confirmed readings*", ""]
    for e in confirmed:
        lines.append("- {0} {1} (signed by {2} on {3})".format(
            e.get("dated") or "?", r5.clip(e.get("title"), 110), e.get("confirmed_by"),
            e.get("confirmed_on")))
    lines += ["", "*The shape of the chamber (sitting members)*", "",
              "| Column | Members |", "|---|---|"]
    for c in r5.COLUMNS:
        lines.append("| {0} {1} | {2} |".format(c, COLUMN_LABEL[c], len(by[c])))
    lines += ["", "*Allies ({0})*".format(len(by["++"]) + len(by["+"])), "",
              _names(by["++"] + by["+"]), "",
              "*Opponents ({0})*".format(len(by["--"]) + len(by["-"])), "",
              _names(by["--"] + by["-"]), "",
              "*No placement from the confirmed readings ({0})*".format(len(by["0"])), "",
              "Sitting members no confirmed reading places either way: absent, abstaining, or "
              "not yet in the chamber for these votes. The list a campaigner works.", "",
              _names(by["0"]), ""]
    if mixed:
        lines += ["*Mixed records ({0})*".format(len(mixed)), "",
                  "Directional evidence on both sides: read the votes, not the column.", "",
                  _names(mixed), ""]
    if former:
        lines += ["*Former members placed, not counted ({0})*".format(len(former)), "",
                  _names(former), ""]
    if excluded:
        lines += ["*Excluded: non-attached or independent ({0})*".format(len(excluded)), "",
                  "These members sit in no group, so a group's vote says nothing about them "
                  "(#80). They are not placed.", "",
                  _names(excluded), ""]
    lines += ["*Caveats*", ""]
    if derived or cc in c5.PARTY_GROUP:
        lines.append("- Rows marked [DERIVED] carry the group's vote, not the member's own "
                     "(X5): this parliament records the group, and the placement is an "
                     "inference that weighs less than a recorded vote.")
    lines += ["- Whipped votes measure the group line, not conviction.",
              "- " + r5.readings_line(sheet["signed"], sheet["unsigned"], an)]
    if sheet["unsigned"]:
        lines.append("- What to sign next: docs/5ca-{0}-shortlist.md.".format(cc))
    lines += ["", "---", "",
              "*Rendered {0} from the confirmed readings in config/{1}_stance.yaml. Shared with "
              "Chris alone; nothing was posted to a channel or anywhere public.*".format(today, cc)]
    summary = ("*5CA: {0}, {1}: {2}*. {3} confirmed reading(s): {4} strong allies, {5} lean "
               "our way, {6} lean against, {7} strong opponents, {8} with no placement.{9}").format(
        country, ch, an, len(confirmed), len(by["++"]), len(by["+"]), len(by["-"]),
        len(by["--"]), len(by["0"]),
        " {0} placed from the group vote (DERIVED).".format(len(derived)) if derived else "")
    return title_for(cc, chamber, area), "\n".join(lines) + "\n", summary


def render_withdrawn(cc, chamber, area, today=None):
    today = today or datetime.date.today().isoformat()
    body = ("*{0}, {1}: {2}. Five Column Analysis*\n\nNo confirmed reading places anyone in "
            "this area now (a reading was withdrawn or changed), so this 5CA shows no "
            "placement. It will be rewritten here when one does.\n\n---\n\n*Rewritten {3}. "
            "Shared with Chris alone.*\n").format(
        c5.SPECS[cc].name, chamber_name(cc, chamber), area_name(area), today)
    return title_for(cc, chamber, area), body, "*5CA: {0}* no longer places anyone.".format(
        title_for(cc, chamber, area))


# --- the run -------------------------------------------------------------------------

def plan(ccs, stores, default_db, config_dir=None, state=None, refresh=False, area=None,
         chamber=None, today=None, log=print, fp_field="fingerprint"):
    """What to post: a list of dicts (key, cc, chamber, area, action, title, body,
    summary, fingerprint, canvas_id). action: create, update or withdraw.
    Opens no store for a country with nothing confirmed and nothing posted."""
    state = state or {}
    todo, gaps = [], []
    for cc in ccs:
        if not os.path.exists(c5.stance_path(cc, config_dir)):
            continue
        entries = c5.load(cc, config_dir)[0]
        posted = [k for k in state if k.startswith(cc + "|")]
        if not has_confirmed(entries) and not posted:
            continue                       # nothing confirmed: nothing to say
        path = stores.get(cc, default_db)
        conn = c5.connect_ro(path) if path and os.path.exists(path) else None
        try:
            if conn is None and has_confirmed(entries):
                gaps.append("{0}: no store at {1}".format(cc, path))
                log("  [gap] {0}: confirmed readings but no store at {1}; nothing posted".format(
                    cc, path))
                continue
            for sh in c5.publishable_sheets(conn, cc, config_dir, today, entries):
                if area is not None and sh["area"] != area:
                    continue
                if chamber is not None and sh["chamber"] != chamber:
                    continue
                key = sheet_key(cc, sh["chamber"], sh["area"])
                prior = state.get(key) or {}
                if sh["rows"] is None:
                    if prior.get("canvas_id") and not prior.get("withdrawn"):
                        title, body, summary = render_withdrawn(cc, sh["chamber"], sh["area"], today)
                        todo.append(dict(key=key, cc=cc, chamber=sh["chamber"], area=sh["area"],
                                         action="withdraw", title=title, body=body,
                                         summary=summary, fingerprint=None,
                                         canvas_id=prior["canvas_id"]))
                    continue
                fp = fingerprint(sh["listed"])
                if refresh and prior.get(fp_field) == fp and not prior.get("withdrawn"):
                    continue
                title, body, summary = render(cc, sh, today)
                todo.append(dict(key=key, cc=cc, chamber=sh["chamber"], area=sh["area"],
                                 action="update" if prior.get("canvas_id") else "create",
                                 title=title, body=body, summary=summary, fingerprint=fp,
                                 canvas_id=prior.get("canvas_id")))
        except Exception as exc:          # one country's failure is a gap, not a lost run
            gaps.append("{0}: {1}: {2}".format(cc, type(exc).__name__, exc))
            log("  [gap] {0}: {1}: {2}".format(cc, type(exc).__name__, exc))
        finally:
            if conn is not None:
                conn.close()
    return todo, gaps


def run(ccs, stores, default_db, config_dir=None, state_path=None, to="canvas", refresh=False,
        dry_run=False, area=None, chamber=None, today=None, secrets=None, transport=None,
        announce=True, log=print):
    """Plan, then post to Chris alone (or print, with dry_run). Returns
    (done, gaps): done is the list of items acted on, with their results."""
    if to not in TARGETS:
        raise ValueError("to must be one of {0}".format(", ".join(TARGETS)))
    today = today or datetime.date.today().isoformat()
    state = load_state(state_path)
    todo, gaps = plan(ccs, stores, default_db, config_dir, state, refresh, area, chamber,
                      today, log, "dm_fingerprint" if to == "dm" else "fingerprint")
    if not todo:
        log("5CA posts: nothing to post ({0}).".format(
            "no confirmed reading changed" if state else "no confirmed reading places anyone"))
        return [], gaps
    if dry_run:
        for t in todo:
            what = {"create": "a NEW canvas shared with Chris alone",
                    "update": "canvas {0} rewritten in place".format(t["canvas_id"]),
                    "withdraw": "canvas {0} rewritten: no placement now".format(t["canvas_id"])}
            log("=" * 70)
            log("[dry run] {0}: {1}{2}".format(
                t["title"], what[t["action"]] if to != "dm" else "a DM to Chris",
                " and a DM to Chris" if to == "both" else ""))
            log(t["summary"])
            log("-" * 70)
            log(t["body"])
        log("[dry run] {0} item(s); nothing sent, no state written.".format(len(todo)))
        return todo, gaps

    from src import publish
    secrets = secrets_for_chris(secrets)
    done, links = [], []
    for t in todo:
        res = {}
        if to in ("canvas", "both"):
            if t["canvas_id"]:
                res = publish.slack_update_canvas(secrets, t["canvas_id"], t["body"],
                                                  transport=transport)
            else:
                res = publish.slack_preview_canvas(secrets, t["title"], t["body"], t["summary"],
                                                   transport=transport, announce=False)
            if not res.get("canvas_id"):
                gaps.append("{0}: {1}".format(t["key"], res.get("error") or res.get("skipped")))
                log("  [gap] {0}: {1}".format(t["title"], res.get("error") or res.get("skipped")))
                continue
            rec = dict(state.get(t["key"]) or {})
            rec.update({"canvas_id": res["canvas_id"],
                        "canvas_url": res.get("canvas_url") or rec.get("canvas_url"),
                        "title": t["title"], "updated_on": today,
                        "withdrawn": t["action"] == "withdraw"})
            rec.setdefault("created_on", today)
            if t["fingerprint"]:
                rec["fingerprint"] = t["fingerprint"]
            state[t["key"]] = rec
            links.append("- {0}: {1} ({2})".format(
                {"create": "new", "update": "rewritten", "withdraw": "no placement now"}[t["action"]],
                t["title"], rec["canvas_url"]))
            log("  {0}: canvas {1} {2}".format(t["title"], res["canvas_id"],
                                               "created" if t["action"] == "create"
                                               else "rewritten in place"))
        if to in ("dm", "both"):
            text = t["summary"] + "\n\n" + t["body"]
            if len(text) > DM_CAP:
                text = text[:DM_CAP] + "\n\n[cut: the full 5CA is in the canvas or data/5ca/]"
            dm = publish.slack_dm(secrets, text, transport=transport)
            res = dict(res, dm=dm)
            if dm.get("error") or dm.get("skipped"):
                gaps.append("{0}: DM {1}".format(t["key"], dm.get("error") or dm.get("skipped")))
            if to == "dm":
                rec = dict(state.get(t["key"]) or {})
                rec.update({"dm_on": today, "title": t["title"]})
                if t["fingerprint"]:
                    rec["dm_fingerprint"] = t["fingerprint"]
                state[t["key"]] = rec
        done.append(dict(t, result=res))
    save_state(state, state_path)
    if links and announce:
        text = "*New-country 5CA canvases ({0}), shared with you alone*\n{1}".format(
            len(links), "\n".join(links))
        dm = publish.slack_dm(secrets, text, transport=transport)
        if dm.get("error") or dm.get("skipped"):
            gaps.append("summary DM: {0}".format(dm.get("error") or dm.get("skipped")))
    return done, gaps
