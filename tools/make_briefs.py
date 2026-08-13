"""Generate Campaigns Brief drafts for newly surfaced bills and activity.

    python3 tools/make_briefs.py              # all new subjects since last run
    python3 tools/make_briefs.py --list       # show subjects without writing
    python3 tools/make_briefs.py --force SLUG # regenerate one brief

Subjects: live bills on the board and ACT-tagged items (consultations,
committee inquiries). Migration (area 11) is excluded: collated, never
campaigned. One brief per subject EVER (brief_log) -- a campaigner's edits
must not be overwritten by a Monday run, so re-generation is --force only.

The output mirrors the Campaigns Brief template (Cheat Sheet + Christopher's
own briefs as house style): General Information, the Plan/Prepare AI prompt
fields, Red Fox Four, Timeline, and the Five Column Analysis tally with a
pointer at the full sheets. What the store knows is filled deterministically.
Narrative fields (key injustice, arguments, outcomes) are drafted by the
model in CitizenGO voice when an API key is present, and left as marked
[CAMPAIGNER] placeholders otherwise -- the same stub-not-silence pattern as
triage. RF4 SCORES are never auto-filled: the Cheat Sheet is explicit that
scoring is the campaigner's judgement, so each question gets an evidence
hint and an empty score.

Written to briefs/<slug>.md (readable) and briefs/<slug>.csv (paste-in,
matching the Brief spreadsheet's row layout). Internal only: never copied
to partner_site or docs.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, stance

BRIEFS_DIR = os.path.join(ROOT, "briefs")
EXCLUDED_AREAS = {11}  # migration: collated, never campaigned

# CitizenGO Brief "Topic" per taxonomy area -- the template's own validation
# values (Life / Family & Education / Freedom / Patriotism).
AREA_TOPIC = {1: "Life", 2: "Life", 3: "Family & Education", 4: "Freedom",
              5: "Family & Education", 6: "Family & Education", 7: "Freedom",
              8: "Freedom", 9: "Family & Education", 10: "Life"}

RF4 = [
    ("RF#1", "Win or lose, just by fighting this fight, will it bring people "
             "or money to our cause?"),
    ("RF#2", "Win or lose, just by fighting this fight, will it help our "
             "friends or allies?"),
    ("RF#3", "Win or lose, just by fighting this fight, will it hurt our "
             "enemies and their allies?"),
    ("RF#4/1", "What's the gain for freedom and our values if we win?"),
    ("RF#4/2", "What's the cost to freedom and our values if we lose?"),
]

NARRATIVE_FIELDS = [
    ("ask", "What are we asking for in the petition?"),
    ("injustice", "What is the key point of injustice that is at stake here?"),
    ("arguments", "What are some arguments supporting our point of view?"),
    ("urgency", "Why is it urgent that we take action now?"),
    ("listen", "Why would they listen to us?"),
    ("bad_outcome", "Describe a bad outcome if we do not win this campaign:"),
    ("good_outcome", "Describe a good outcome if we do win this campaign:"),
    ("offline", "Ideas for eventual Offline Actions"),
    ("image", "What should the image for this campaign look like?"),
]

# The Evaluate dashboard rows, verbatim from the template. Always empty at
# generation: this is the after-the-campaign half.
EVALUATE_ROWS = [
    "Emails Bluebook link related to this campaign",
    "Number of total emails sent for this campaign",
    "Total Signatures", "New List Members", "Reactivated Members",
    "Acquired %", "Total \u20ac raised", "Total \u20ac spent",
    "Cost of the offline actions",
    "Asana link related to this campaign", "Asana link to the Evaluate task",
    "Google Doc link to the wording copy package",
    "Political impact evaluation", "Did you win the political fight?",
    "Did the media talk about the campaign?",
    "Did any politician talk about the campaign?",
    "Did you deliver the signatures?", "How did you deliver the signatures?",
    "Was it a good decision to run this campaign?",
    "Which good practices, if any, can we drawn from this campaign and repeat "
    "in future campaigns?",
    "Which improvement areas can you identify in this campaign, so that we can "
    "do better in future campaigns?",
    "Which specific conclusions can you draw analyzing data of this campaign?",
    "Top 3 Sources of New Members (by channel & % of total)",
    "Social Media Strategy in One Line", "Other comments", "Moving forward",
]

DRAFT_SYSTEM = """You draft Campaigns Brief narrative fields for CitizenGO UK,
a conservative advocacy organisation defending life, family and freedom.
Voice: urgent, direct, conviction-led, emotionally resonant, never corporate.
British spelling. No em dashes. Audience: values-driven supporters motivated
by faith and family.

You are given a parliamentary subject (a bill, consultation or inquiry), the
facts the monitoring pipeline holds about it, and CitizenGO's position areas
it touches. Draft the requested fields. Ground every claim in the supplied
facts; where a claim would need evidence the facts do not contain, write the
claim conservatively or flag it with [VERIFY]. Never assert that a
parliamentary stage has been passed, a vote has happened, or a decision has
been made unless the facts state it explicitly: "at 2nd reading" means
AWAITING that stage, not through it. Return a JSON object whose keys are
exactly the field ids requested."""


def ensure_log(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS brief_log ("
                 "slug TEXT PRIMARY KEY, subject TEXT, generated_at TEXT, path TEXT)")
    cols = [c[1] for c in conn.execute("PRAGMA table_info(brief_log)")]
    for col in ("status", "asana_gid"):
        if col not in cols:
            conn.execute("ALTER TABLE brief_log ADD COLUMN {0} TEXT".format(col))
    conn.commit()


def slugify(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:60]


def subjects(conn):
    """Brief-worthy subjects: live board bills + ACT items, minus migration."""
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    out = []
    for r in conn.execute("SELECT * FROM bills_board WHERE status != 'closed'").fetchall():
        # bills_board.areas is a bare string ('2', '1,6'), not the ledger's
        # JSON-list format.
        raw = r["areas"] or ""
        areas = [int(x) for x in re.findall(r"\d+", str(raw))]
        areas = [a for a in areas if a not in EXCLUDED_AREAS]
        if r["areas"] and not areas:
            continue  # migration-only bill: tracked, not campaigned
        out.append({
            "kind": "bill", "slug": "bill-" + slugify(r["title"]),
            "title": r["title"], "areas": areas,
            "area_labels": [names.get(a) for a in areas],
            "sponsor": r["sponsor"], "house": r["house"], "stage": r["stage"],
            "next_key_date": r["next_key_date"], "what_next": r["what_next"],
            "status": r["status"],
            "url": ("https://bills.parliament.uk/bills/{0}".format(r["bill_id"])
                    if (r["bill_id"] or 0) > 0 else None),
            "deadline": r["next_key_date"] if (r["next_key_date"] or "").count("-") == 2 else None,
        })
    for r in conn.execute("SELECT * FROM items WHERE priority_tag = 'ACT'").fetchall():
        areas = [a for a in json.loads(r["issue_areas"] or "[]") if a not in EXCLUDED_AREAS]
        if not areas:
            continue
        out.append({
            "kind": r["source_feed"], "slug": r["source_feed"] + "-" + slugify(r["title"]),
            "title": r["title"], "areas": areas,
            "area_labels": [names.get(a) for a in areas],
            "sponsor": None, "house": None, "stage": None,
            "next_key_date": r["deadline"], "what_next": None, "status": "open",
            "url": r["url"], "deadline": r["deadline"],
            "why": r["why_it_matters"],
        })
    return out


def ledger_context(conn, areas, since_days=180):
    """What Parliament has been doing on these areas lately, from the ledger."""
    if not areas:
        return {}
    cutoff = (datetime.date.today() - datetime.timedelta(days=since_days)).isoformat()
    rows = conn.execute("SELECT kind, areas FROM mp_events WHERE date >= ?", (cutoff,)).fetchall()
    counts = {}
    for r in rows:
        evs = json.loads(r["areas"]) if r["areas"] else []
        if any(a in areas for a in evs):
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    return counts


def fca_tally(conn, area, cfg, house="Commons"):
    rows = stance.suggest_rows(conn, area, full_roster=True, overrides_cfg=cfg, house=house)
    tally = {c: 0 for c in stance.COLUMNS}
    for r in rows:
        tally[r["column"]] += 1
    top_for = [r["decision_maker"] for r in rows if r["column"] == "++"][:5]
    top_against = [r["decision_maker"] for r in rows if r["column"] == "--"][:5]
    return tally, top_for, top_against, len(rows)


def rf1_hint(conn, areas):
    """What comparable campaigns on this topic actually did (RF#1 evidence).

    Christopher (2026-08-13): individual campaign performance and acquisition
    rates predict a new campaign far better than lifetime topic totals, so
    the top comparables lead, each with its acquisition rate (new members as
    a share of signatures); the topic rollup closes the line. Money comes
    from fundraising_series ONLY via an explicit petition join - the source
    is series-grain, starts 2025-01-23, and absence means not-available,
    never zero (Max's own caveat).
    """
    try:
        rows = conn.execute("SELECT petition_id, name, new_members, reactivated, "
                            "signatures, areas, logged_at FROM campaign_performance").fetchall()
        series = conn.execute("SELECT related_petition_id, value_eur "
                              "FROM fundraising_series WHERE related_petition_id "
                              "IS NOT NULL").fetchall()
    except Exception:
        rows, series = [], []
    money_by_pid = {r["related_petition_id"]: r["value_eur"] for r in series}
    hits = [r for r in rows
            if any(a in areas for a in json.loads(r["areas"] or "[]"))]
    if not hits:
        return ("No lifetime record logged for this topic yet - run "
                "tools/log_campaign_performance.py; interim: EOS dashboard.")

    def acq(r):
        if r["signatures"] and r["new_members"] is not None:
            return 100.0 * r["new_members"] / r["signatures"]
        return None

    top = sorted(hits, key=lambda r: -(r["new_members"] or 0))[:3]
    parts = []
    for r in top:
        a = acq(r)
        m = money_by_pid.get(r["petition_id"])
        parts.append("{0}: {1:,} new / {2:,} sigs{3}{4}".format(
            r["name"][:60], r["new_members"] or 0, r["signatures"] or 0,
            " ({0:.1f}% acquired)".format(a) if a is not None else "",
            ", \u20ac{0:,.0f} attributed".format(m) if m else ""))
    rates = [acq(r) for r in hits if acq(r) is not None]
    rates.sort()
    median = rates[len(rates) // 2] if rates else None
    logged = max((r["logged_at"] or "")[:10] for r in hits)
    return ("Comparable campaigns on this topic - {0}. Topic lifetime: {1} "
            "campaigns, {2:,} new members{3}. Baseline logged {4}.".format(
                " | ".join(parts), len(hits),
                sum(r["new_members"] or 0 for r in hits),
                ", median acquisition {0:.1f}%".format(median) if median else "",
                logged))


def addressed_to(subject):
    if subject["kind"] == "bill":
        if (subject["house"] or "").lower() == "lords":
            return "Members of the House of Lords ahead of the Bill's next stage"
        return ("Individual MPs who could be persuaded ahead of the Bill's "
                "next Commons stage")
    if subject["kind"] == "consultation":
        return "The responsible department, via the consultation response"
    if subject["kind"] == "committee":
        return "The committee, via written evidence, and its members directly"
    return "[CAMPAIGNER: decision-maker]"


def urgency_of(subject, today):
    d = subject.get("deadline")
    if d and d.count("-") == 2:
        days = (datetime.date.fromisoformat(d) - today).days
        if days <= 30:
            return "Urgent Campaign ({0} days to {1})".format(days, d)
    return "Non-Urgent Campaign (by default)"


def background(subject, activity):
    bits = []
    if subject["kind"] == "bill":
        bits.append("{0}{1} is at {2} in the {3}.".format(
            subject["title"],
            " (sponsor: {0})".format(subject["sponsor"]) if subject["sponsor"] else "",
            subject["stage"] or "an unknown stage", subject["house"] or "?"))
        if subject["next_key_date"]:
            bits.append("Next key date: {0}.".format(subject["next_key_date"]))
        if subject["what_next"]:
            bits.append(subject["what_next"] + ".")
    else:
        bits.append(subject["title"] + ".")
        if subject.get("why"):
            bits.append(subject["why"])
        if subject["deadline"]:
            bits.append("Deadline: {0}.".format(subject["deadline"]))
    if activity:
        order = ["vote", "debate", "edm", "edm-signed", "pq"]
        label = {"vote": "division votes", "debate": "debate contributions",
                 "edm": "motions", "edm-signed": "motion signatures",
                 "pq": "written questions"}
        parts = ["{0} {1}".format(activity[k], label[k]) for k in order if activity.get(k)]
        if parts:
            bits.append("Parliamentary activity on this issue in the last six "
                        "months (from the monitor's ledger): " + ", ".join(parts) + ".")
    return " ".join(bits)


def draft_narrative(subject, facts, api_key):
    """Model-drafted narrative fields; None on any failure (caller stubs)."""
    if not api_key:
        return None
    prompt = {
        "subject": subject["title"], "kind": subject["kind"],
        "areas": subject["area_labels"], "facts": facts,
        "fields": {fid: q for fid, q in NARRATIVE_FIELDS},
    }
    payload = {
        # The reply may open with a thinking block that spends from the same
        # budget; 2000 truncated mid-JSON on live runs.
        "model": stance.STANCE_MODEL, "max_tokens": 6000,
        "system": DRAFT_SYSTEM,
        "messages": [{"role": "user", "content": json.dumps(prompt)}],
    }
    try:
        reply = stance._default_transport(payload, api_key)
        # The model may lead with a thinking block; join the text blocks, as
        # stance._parse_reply does.
        text = "".join(b.get("text", "") for b in (reply.get("content") or [])).strip()
        text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
        start = text.find("{")
        if start > 0:
            text = text[start:]
        try:
            data = json.loads(text)
        except ValueError:
            # literal newlines inside string values (seen live: two of six
            # briefs, 2026-08-12) -- retry with control characters tolerated
            data = json.loads(text, strict=False)
        out = {}
        for fid, _ in NARRATIVE_FIELDS:
            v = data.get(fid)
            if isinstance(v, list):
                # arguments often arrive as an array of points
                v = "\n".join("- " + str(x) for x in v)
            if v:
                out[fid] = str(v)
        return out
    except Exception as exc:
        print("  narrative draft failed ({0}); placeholders used".format(exc))
        return None


def render_markdown(subject, fields, rf4_hints, fca, timeline, today):
    lines = ["# Campaigns Brief (DRAFT): {0}".format(subject["title"]), ""]
    lines.append("> Generated by parl-monitor on {0}. Facts come from the store; "
                 "narrative fields are drafts for the campaigner to own; RF4 "
                 "scores are deliberately blank. This file is never regenerated "
                 "once written (edit freely); `--force` rebuilds it.".format(today))
    lines.append("")
    lines.append("## General information")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| Campaigner | cjoyce@citizengo.net |")
    lines.append("| Date of Submission | {0} |".format(today))
    lines.append("| Urgency | {0} |".format(fields.get("urgency", "")))
    lines.append("| List | EN GB |")
    for k, v in fields["general"]:
        lines.append("| {0} | {1} |".format(k, str(v).replace("|", "/").replace("\n", " ")))
    lines.append("")
    lines.append("## Plan phase prompts")
    lines.append("")
    for label, value in fields["plan"]:
        lines.append("**{0}**".format(label))
        lines.append("")
        lines.append(value)
        lines.append("")
    lines.append("## Prepare phase prompts")
    lines.append("")
    for label, value in fields["prepare"]:
        lines.append("**{0}**".format(label))
        lines.append("")
        lines.append(value)
        lines.append("")
    lines.append("## Red Fox Four (scores are the campaigner's call)")
    lines.append("")
    lines.append("| # | Question | Score (-10..+10) | Evidence hint |")
    lines.append("|---|---|---|---|")
    for (code, q), hint in zip(RF4, rf4_hints):
        lines.append("| {0} | {1} | | {2} |".format(code, q, hint))
    lines.append("| | TOTAL IF WE WIN / TOTAL IF WE LOSE | | |")
    lines.append("")
    lines.append("## Timeline of major actions")
    lines.append("")
    lines.append("| Date | Action | Comment |")
    lines.append("|---|---|---|")
    for row in timeline:
        lines.append("| {0} | {1} | {2} |".format(*row))
    lines.append("")
    if fca:
        lines.append("## Five Column Analysis")
        lines.append("")
        lines.append(fca)
        lines.append("")
        lines.append("The filled 5CA sheet in the Brief template's exact columns "
                     "is beside this file as `{0}-5ca.csv` - paste it into the "
                     "Five Columns Analysis tab as-is.".format(subject["slug"]))
        lines.append("")
    lines.append("## Evaluate (fill after the campaign)")
    lines.append("")
    lines.append("Political impact; signatures and delivery; funds raised/spent; "
                 "was it a good decision; practices to repeat; improvement areas. "
                 "For tracked divisions the Evaluate 5CA can be generated with "
                 "tools/ca_campaign.py.")
    lines.append("")
    return "\n".join(lines)


def write_csv(path, subject, fields, rf4_hints, timeline, today):
    """The Default Brief tab, row for row as the template lays it out."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["Campaign Name", "Campaigner", "Date of Submission",
                    "Urgency", "List", "Notes", "Approval Date"])
        w.writerow([subject["title"] + " (DRAFT)", "cjoyce@citizengo.net",
                    today.isoformat(), fields["urgency"], "EN GB",
                    "Draft generated by parl-monitor", ""])
        w.writerow(["GENERAL INFORMATION"])
        for k, v in fields["general"]:
            w.writerow([k, v])
        w.writerow(["PROMPTS FOR AI - PLAN PHASE"])
        for label, value in fields["plan"]:
            w.writerow([label, value])
        w.writerow(["PROMPTS FOR AI - PREPARE PHASE"])
        for label, value in fields["prepare"]:
            w.writerow([label, value])
        w.writerow(["RED FOX FOUR"])
        w.writerow(["PLAN STAGE", "", "", "", "EVALUATE STAGE", "", ""])
        w.writerow(["#", "Question", "Scoring \n(-10 to +10)", "Comments",
                    "Scoring\n(-10 to +10)", "Delta", "Comments"])
        for (code, q), hint in zip(RF4, rf4_hints):
            w.writerow([code, q, "", hint, "", "", ""])
        w.writerow(["TOTAL IF WE WIN", "", "0", "", "0", "0", ""])
        w.writerow(["TOTAL IF WE LOSE", "", "0", "", "0", "0", ""])
        w.writerow(["TIMELINE OF MAJOR ACTIONS"])
        w.writerow(["Date", "Action", "Comment"])
        for row in timeline:
            w.writerow(list(row))
        w.writerow(["EVALUATE DASHBOARD"])
        for label in EVALUATE_ROWS:
            w.writerow([label.replace("\\u20ac", "\u20ac"), ""])
        w.writerow(["For more information on how to fill out or interpret this "
                    "document, check the Campaigns Brief Cheat Sheet"])


def write_5ca_csv(path, conn, subject, cfg):
    """The Five Columns Analysis tab, auto-filled, in the template's exact
    columns: Decision-Maker, # Seats, gradient, Target, Comments, then the
    empty Evaluate pair. Target stays blank (the campaigner's call), and the
    Vote columns stay blank until the Evaluate phase."""
    if not subject["areas"]:
        return False
    area = subject["areas"][0]
    house = "Lords" if (subject.get("house") or "").lower() == "lords" else "Commons"
    rows = stance.suggest_rows(conn, area, full_roster=True, overrides_cfg=cfg,
                               house=house)
    if not rows:
        return False
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["FIVE COLUMNS ANALYSIS (ONLY IF APPROPRIATE)"])
        w.writerow(["PLAN STAGE", "", "", "", "", "", "", "", "",
                    "EVALUATE STAGE", ""])
        w.writerow(["Decision-Maker", "# Seats", '"++"', '"+"', '"0"', '"-"',
                    '"--"', "Target (Y/N)", "Comments", "Vote (Y/N)", "Comments"])
        tally = {c: 0 for c in stance.COLUMNS}
        for r in rows:
            marks = ["1" if c == r["column"] else "0" for c in stance.COLUMNS]
            tally[r["column"]] += 1
            w.writerow([r["decision_maker"], ""] + marks
                       + ["", r["comments"], "", ""])
        w.writerow(["TOTAL", ""] + [tally[c] for c in stance.COLUMNS]
                   + ["", "", "", ""])
    return True


def main():
    force = None
    if "--force" in sys.argv:
        force = sys.argv[sys.argv.index("--force") + 1]
    list_only = "--list" in sys.argv

    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    ensure_log(conn)
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    today = datetime.date.today()

    api_key = None
    secrets_path = os.path.join(ROOT, "config", "secrets.yaml")
    if os.path.exists(secrets_path):
        import yaml
        api_key = (yaml.safe_load(open(secrets_path)) or {}).get("anthropic_api_key")
    api_key = os.environ.get("ANTHROPIC_API_KEY") or api_key

    subs = subjects(conn)
    done = {r["slug"] for r in conn.execute("SELECT slug FROM brief_log")}
    rejected = {r["slug"] for r in conn.execute(
        "SELECT slug FROM brief_log WHERE status = 'rejected'")}
    if force and force in rejected:
        print("{0} was REJECTED at review and archived; not regenerating. "
              "Clear its brief_log row deliberately if that decision has "
              "changed.".format(force))
        return 1
    todo = [s for s in subs if s["slug"] == force or (not force and s["slug"] not in done)]

    if list_only or (not todo):
        for s in subs:
            print("  {0} {1:12} {2}".format(
                "NEW " if s["slug"] not in done else "done", s["kind"], s["title"][:70]))
        if not todo:
            print("briefs: nothing new")
        return 0

    os.makedirs(BRIEFS_DIR, exist_ok=True)
    made = []
    for s in todo:
        activity = ledger_context(conn, s["areas"])
        bg = background(s, activity)
        facts = {"background": bg, "url": s["url"], "deadline": s.get("deadline"),
                 "stage": s.get("stage"), "house": s.get("house"),
                 "activity_6mo": activity}
        drafted = draft_narrative(s, facts, api_key) or {}

        def field(fid, question):
            v = drafted.get(fid)
            return (question, v if v else "[CAMPAIGNER: draft needed]")

        general = [
            ("Type of Campaign", "[CAMPAIGNER: Survival / Obligatory / Opportunity]"),
            ("Topic", " / ".join(sorted({AREA_TOPIC.get(a, "Freedom") for a in s["areas"]}))),
            ("Main Purposes", "Political Impact"),
            ("Background / Context", bg),
            ("Estimated Launch date", "[CAMPAIGNER]"),
            ("Estimated date for Delivering Signatures",
             ("Before {0}".format(s["deadline"]) if s.get("deadline") else "[CAMPAIGNER]")),
            field("offline", "Ideas for eventual Offline Actions"),
            ("Petitions related TIM project (Targeting Inactive Members)", ""),
        ]
        plan = [
            ("What is the language for this petition?", "English"),
            ("Who will sign the emails for this petition?", "Christopher Joyce"),
            ("Who is the petition addressed to?", addressed_to(s)),
            field("ask", "What are we asking for in the petition?"),
            ("What is happening that we are responding to?", bg),
            field("injustice", "What is the key point of injustice that is at stake here?"),
        ]
        prepare = [
            field("arguments", "What are some arguments supporting our point of view?"),
            field("urgency", "Why is it urgent that we take action now?"),
            field("listen", "Why would they listen to us?"),
            field("bad_outcome", "Describe a bad outcome if we do not win this campaign:"),
            field("good_outcome", "Describe a good outcome if we do win this campaign:"),
            ("Which sources do you want to include? Please provide the titles plus URLs:",
             " | ".join(x for x in [s["url"],
                                    "https://parl-monitor-partner.vercel.app/mp-votes.html"] if x)),
            field("image", "What should the image for this campaign look like?"),
        ]

        fca_block = ""
        rf4_ally_hint = "See the 5CA sheets for allies on this area."
        if s["areas"]:
            area = s["areas"][0]
            house = "Lords" if (s.get("house") or "").lower() == "lords" else "Commons"
            tally, top_for, top_against, n = fca_tally(conn, area, cfg, house)
            fca_block = (
                "Suggested gradient for **{0}** ({1}, {2} decision-makers): "
                "{3}\n\nStrongest allies: {4}\n\nStrongest opponents: {5}\n\n"
                "Full sheet: docs/5ca-sheets.html (Commons) / docs/5ca-peers.html "
                "(Lords); paste-in CSV via `python3 tools/make_5ca.py {6}{7}`."
            ).format(
                intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml")).get(area),
                house, n,
                "  ".join("{0} x{1}".format(c, tally[c]) for c in stance.COLUMNS),
                "; ".join(top_for) or "none placed ++",
                "; ".join(top_against) or "none placed --",
                area, " --peers" if house == "Lords" else "")
            rf4_ally_hint = ("5CA {0}: {1} with us (++/+), {2} against (-/--)."
                             .format(house, tally["++"] + tally["+"],
                                     tally["-"] + tally["--"]))

        rf4_hints = [
            rf1_hint(conn, s["areas"]),
            rf4_ally_hint,
            "Opponent organisations are not tracked by the monitor; campaigner's knowledge.",
            "If we win: see 'good outcome' above. Score the value, not the odds.",
            "If we lose: see 'bad outcome' above. Usually 0 unless losing accelerates harm.",
        ]
        timeline = []
        if s.get("next_key_date"):
            timeline.append((s["next_key_date"],
                             "Key parliamentary date" if s["kind"] == "bill" else "Deadline",
                             s.get("stage") or s["kind"]))
        timeline.append(("[CAMPAIGNER]", "Launch", ""))

        fields = {"general": general, "plan": plan, "prepare": prepare,
                  "urgency": urgency_of(s, today)}
        md_path = os.path.join(BRIEFS_DIR, s["slug"] + ".md")
        csv_path = os.path.join(BRIEFS_DIR, s["slug"] + ".csv")
        fca_path = os.path.join(BRIEFS_DIR, s["slug"] + "-5ca.csv")
        with open(md_path, "w", encoding="utf-8") as handle:
            handle.write(render_markdown(s, fields, rf4_hints, fca_block, timeline,
                                         today.isoformat()))
        write_csv(csv_path, s, fields, rf4_hints, timeline, today)
        if write_5ca_csv(fca_path, conn, s, cfg):
            print("  5ca:   {0}".format(os.path.basename(fca_path)))
        approval = {}
        try:
            from src import publish
            secrets = publish.load_secrets()
            approval = publish.asana_create_brief_approval(
                secrets, s["title"], s["slug"], deadline=s.get("deadline"))
        except Exception as exc:
            approval = {"error": str(exc)}
        if approval.get("error"):
            print("  approval task FAILED: {0} (brief kept; create the task "
                  "by hand)".format(approval["error"]))
        else:
            print("  approval task: {0}".format(approval.get("permalink") or
                                                approval.get("task_gid")))
        conn.execute("INSERT OR REPLACE INTO brief_log "
                     "(slug, subject, generated_at, path, status, asana_gid) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (s["slug"], s["title"], today.isoformat(), md_path,
                      "pending", approval.get("task_gid")))
        conn.commit()
        made.append((s["slug"], bool(drafted)))
        print("  brief: {0} ({1})".format(
            s["slug"], "narrative drafted" if drafted else "placeholders"))

    print("briefs: {0} generated -> {1}".format(len(made), BRIEFS_DIR))
    # Monthly check is for NEWLY CLOSED campaigns (Christopher, 2026-08-13):
    # a closed campaign's numbers are final and never re-swept; what goes
    # stale is the record of campaigns that closed since the last pull.
    row = conn.execute("SELECT MAX(logged_at) m FROM campaign_performance").fetchone()
    if row and row["m"]:
        age = (datetime.date.today()
               - datetime.date.fromisoformat(row["m"][:10])).days
        if age > 35:
            n_final = conn.execute("SELECT COUNT(*) FROM campaign_performance "
                                   "WHERE final = 1").fetchone()[0]
            print("  monthly EOS check due - stats stale for campaigns closed "
                  "since {0}: ask Max for lifetime numbers on campaigns "
                  "launched or active since then and re-run "
                  "tools/log_campaign_performance.py ({1} settled campaigns "
                  "are final and need no re-sweep)".format(row["m"][:10], n_final))
    return 0


if __name__ == "__main__":
    sys.exit(main())
