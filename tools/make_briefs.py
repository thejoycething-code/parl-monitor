"""Generate Campaigns Brief drafts for newly surfaced bills and activity.

    python3 tools/make_briefs.py              # all new subjects since last run
    python3 tools/make_briefs.py --list       # show subjects without writing
    python3 tools/make_briefs.py --force SLUG # regenerate one brief


Subjects: live bills on the board and score-3 items (consultations,
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

from src import actionable, db, intel, stance

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
    ("campaign_name", "A campaign headline in the house pattern: 'Tell "
     "<decision-maker>: <the stake in one line>'. Never the official title "
     "of the consultation or bill."),
    ("addressee", "The single named decision-maker, formal style and office "
     "(e.g. 'Mr Paul Givan MLA, Minister of Education for Northern "
     "Ireland'). ONLY if the facts or source material name one; otherwise "
     "omit this field entirely."),
    ("ask", "What are we asking for in the petition?"),
    ("injustice", "What is the key point of injustice that is at stake here?"),
    ("arguments", "What are some arguments supporting our point of view?"),
    ("urgency", "Why is it urgent that we take action now?"),
    ("listen", "Why would they listen to us?"),
    ("bad_outcome", "Describe a bad outcome if we do not win this campaign:"),
    ("good_outcome", "Describe a good outcome if we do win this campaign:"),
    ("offline", "Ideas for eventual Offline Actions"),
    ("tim", "From facts.tim_candidates ONLY: the three most issue-relevant "
     "past petitions for Targeting Inactive Members, each as 'id - title - "
     "one-line reason it matches (issue, geography, audience)'. Copy ids "
     "verbatim from the candidate list; if the list is empty or nothing "
     "fits, omit this field."),
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
    "Social Media Strategy in One Line",
    "Top 5 signature sources (% each) and Top 5 new list member sources (% each)",
    "Paid vs. Organic: spend, signups, cost per paid signup, and most efficient "
    "channel",
    "Best-performing post: link + why it worked + one transferable learning",
    "Political impact: how social media was used to increase pressure or "
    "influence decision-makers?",
    "Other comments", "Moving forward",
]

# The Campaign Narrative tab. The Cheat Sheet is explicit that "a standardized
# format for it hasn't been established yet" and that it is used when a
# campaign goes to an Evaluation Meeting, so this is a scaffold carrying the
# guidance, never auto-filled prose.
NARRATIVE_SCAFFOLD = [
    ["CAMPAIGN NARRATIVE"],
    ["Used when a campaign is selected for an Evaluation Meeting, or whenever "
     "the campaigner wants the fuller story on record. Compile in "
     "chronological order and in low-context communication: the reader will "
     "know far less than you, possibly years later."],
    [],
    ["Date", "What happened / what we decided", "Why, and what it changed"],
    ["", "", ""], ["", "", ""], ["", "", ""], ["", "", ""], ["", "", ""],
    [],
    ["Prompts (delete what does not apply): campaign actions online and "
     "offline; decisions made and their rationale; data analysis; reports on "
     "offline activities; breaking news that changed the scenario; reactions "
     "by stakeholders; the campaign's outcome."],
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
AWAITING that stage, not through it.

HOUSE STYLE (set by the campaigner's own refinement of the RE Core Syllabus
brief, 2026-08-31 - match it):
- Coin ONE memorable hook phrase that captures the stake (his: "merely one
  worldview among many") and thread it through the campaign name, the ask,
  the injustice and the outcomes.
- The ask is one moral demand of the named decision-maker, in flowing
  prose: who must do what, and why it is owed (a promise made, a duty
  held). Policy specifics support the demand; they are never a bulleted
  list.
- injustice and arguments are a series of labelled points, each opening
  with a short assertive claim ending in a colon, then two or three
  sentences of support ("Children could be denied a secure foundation in
  Christianity: ..."). Injustice runs four to six points, arguments six to
  nine. Depth beats brevity in these two fields.
- urgency runs several short paragraphs in this order: the hard deadline;
  why the framework locks in after adoption; the promise or commitment
  this is the test of, if one exists; why silence would read as consent.
- bad_outcome and good_outcome name the decision-maker and the human
  stakes. The good outcome describes the concrete win, not a process.
- Flowing prose inside every field: no ALL-CAPS headers, no markdown
  headings. Internal telemetry (ledger activity counts) and internal
  fundraising figures never appear in petition-facing fields.

Return a JSON object whose keys are exactly the field ids requested."""


def ensure_log(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS brief_log ("
                 "slug TEXT PRIMARY KEY, subject TEXT, generated_at TEXT, path TEXT)")
    cols = [c[1] for c in conn.execute("PRAGMA table_info(brief_log)")]
    for col in ("status", "asana_gid", "followup_gid"):
        if col not in cols:
            conn.execute("ALTER TABLE brief_log ADD COLUMN {0} TEXT".format(col))
    conn.commit()


def slugify(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:60]


def subjects(conn, today=None):
    """Brief-worthy subjects: live board bills + triage-score-3 items +
    actionable devolved consultations, minus migration. Score 3 is the
    rubric's own campaign-trigger level -- the machine judgement that
    replaced the retired ACT tag (Christopher, 2026-08-21: he creates
    Asana tasks himself; the loop is gone). Devolved consultations use the
    action-window rule instead (they never pass through triage); see
    docs/parl-monitor-devolved-fix.md."""
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
    for r in conn.execute("SELECT * FROM items WHERE triage_score = 3").fetchall():
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
    # Devolved consultations meeting the action-window rule
    # (docs/parl-monitor-devolved-fix.md, 2026-08-31). Jurisdiction was a
    # proxy for actionability: everything routed to the Devolved watching
    # brief was unbriefable by construction, which is how the NI RE Core
    # Syllabus consultation -- the deliverable on a ministerial commitment
    # won with 96,328 signatures -- reached Edition 5 without a brief.
    # Same kind, same slug scheme, same downstream path as a Westminster
    # consultation; the ONLY differences are the `nation` key (which swaps
    # the 5CA grid for an explicit populate-manually marker) and that the
    # gate is the action-window rule rather than a triage score, because
    # the devolved stores never pass through LLM triage.
    today = (today or datetime.date.today()).isoformat() \
        if not isinstance(today, str) else today
    # EU consultations under the same action-window rule (Christopher,
    # 2026-09-01: wire EU briefs into the generator; good ones are passed
    # to team members by hand -- the approval task is that gate). Same
    # downstream shape as a devolved consultation: the nation key carries
    # "European Union", which swaps the 5CA grid for the populate-manually
    # marker and flags the List as the campaigner's call.
    for c in actionable.eu_actionable(conn, today):
        areas = [a for a in c["areas"] if a not in EXCLUDED_AREAS]
        if not areas:
            continue
        out.append({
            "kind": "consultation",
            "slug": "eu-" + slugify(c["title"]),
            "title": c["title"], "areas": areas,
            "area_labels": [names.get(a) for a in areas],
            "sponsor": None, "house": None, "stage": None,
            "next_key_date": c["closes"], "what_next": None, "status": "open",
            "url": c["url"], "deadline": c["closes"], "why": None,
            "nation": c["nation_label"],
            "late_detection": c["late_detection"],
        })
    for c in actionable.devolved_actionable(conn, today):
        areas = [a for a in c["areas"] if a not in EXCLUDED_AREAS]
        if not areas:
            continue
        out.append({
            "kind": "consultation",
            "slug": "consultation-" + slugify(c["title"]),
            "title": c["title"], "areas": areas,
            "area_labels": [names.get(a) for a in areas],
            "sponsor": None, "house": None, "stage": None,
            "next_key_date": c["closes"], "what_next": None, "status": "open",
            "url": c["url"], "deadline": c["closes"], "why": None,
            "nation": c["nation_label"],
            "late_detection": c["late_detection"],
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


# A row under this many signatures is not a campaign benchmark. Measured
# 2026-08-20: campaign_performance holds 366 rows and 129 of them have FEWER
# THAN TEN signatures -- one is literally named "Petition template EN-GB" --
# so the population mixes templates and dormant petitions with promoted
# campaigns. The all-rows median for area 1 is 3 signatures against a p75 of
# 5,689, which is two populations rather than a skew, and quoting that median
# into a Brief would be worse than quoting nothing. Excluding sub-100 rows is a
# rule that can be stated in the cell; picking a percentile is not.
#
# The RIGHT discriminator is promotion (did this campaign get an email series),
# which is not held locally -- aa_downstream_report.sent_emails has it. See
# docs/campaign-benchmarks.md.
MIN_BENCHMARK_SIGNATURES = 100

# A HIGHER floor for the Looker source, because that export is now the whole
# EN_GB population and the tail is measurably not campaigns. Of 104 rows, the
# 7 below 3,000 signatures have response rates (signatures / sent_emails) of
# 0.02%-0.78%; every row from 3,627 up runs 2.1%-8.4%. Two independent gaps --
# 4x in signatures (876 -> 3,627) and 4x in response rate -- partition the
# same 7 rows, so they are a different population, not weak campaigns: a send
# that reached 677,000 inboxes for 139 signatures did not function as a
# campaign. That band holds the one explicit "TEST-" program and the one
# segment split (INB_12th_Meeting-Yahoo, 323 signatures against its own
# parent's 22,697 under the same petition id 14242). They stay in the table --
# the store is the archive -- and are excluded HERE, with the count printed.
MIN_LOOKER_SIGNATURES = 3000

# MONEY ONLY, and only for the Looker source: donation figures are incomplete
# for campaigns started on or after this date. Measured over the 94 EN_GB
# campaigns above the floor, one-time donations per 1,000 signatures run:
#     2024   n=39   EUR 52.86
#     2025   n=48   EUR 53.27      <- stable to within 1%
#     2026   n=10   EUR  2.29      <- 23x collapse
# The break is sharp, not a taper: campaigns started to 2026-01-19 carry money
# (6,039 / 1,317 / 388 EUR), every one from 2026-02-02 on is under EUR 70.
# Signature and member counts for the SAME rows are normal (2026 median 24,105
# signatures), so this is the money columns specifically, not weak campaigns.
#
# UNRESOLVED: this is either a broken attribution join or donation asks being
# dropped from campaign emails -- the data cannot tell which, and whoever owns
# the money pipeline can. Both readings mean the same thing for a baseline, so
# the rows are excluded from MONEY only (their signatures still count) and the
# cell says how many. Revisit if the pipeline is fixed or the cause is a real
# change in practice, in which case the cutoff should move, not be deleted.
MONEY_COMPLETE_BEFORE = "2026-02-01"


def _quartile(values, pct):
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[min(int(len(ordered) * pct / 100), len(ordered) - 1)]


def rf1_expectation(conn, areas):
    """[(metric, basis)] for the RF#1 numerical expectation block.

    Antonio, #campaigns 2026-08-19: RF#1 should record what the campaign is
    EXPECTED to achieve numerically, so Evaluate compares a number with a
    number rather than with narrative. The expected cell is left BLANK -- the
    tool supplies the baseline to write it against, never the expectation
    itself, for the same reason RF4 scores stay empty and an NI stance line
    needs a human.

    A baseline is offered as a DISTRIBUTION with its n, not a point forecast:
    "median 15,652 (p25 6,745, p75 24,382, n=13)" is evidence a campaigner can
    argue with. A single number reads as a prediction the tool has no standing
    to make.
    """
    try:
        rows = conn.execute("SELECT signatures, new_members, raised_eur, areas "
                            "FROM campaign_performance").fetchall()
    except Exception:
        rows = []
    hits = [r for r in rows
            if any(a in areas for a in json.loads(r["areas"] or "[]"))]
    ranked = [r for r in hits
              if (r["signatures"] or 0) >= MIN_BENCHMARK_SIGNATURES]
    excluded = len(hits) - len(ranked)

    def band(field, unit=""):
        vals = [r[field] for r in ranked if r[field] is not None]
        if not vals:
            return ("no comparable campaign logged for this topic above {0} "
                    "signatures - baseline unavailable, write your own "
                    "expectation.".format(MIN_BENCHMARK_SIGNATURES))
        note = ""
        if len(vals) < 5:
            note = (" THIN: {0} campaigns only, treat as indicative."
                    .format(len(vals)))
        if excluded:
            note += (" {0} sub-{1}-signature row(s) excluded as templates or "
                     "dormant petitions.".format(
                         excluded, MIN_BENCHMARK_SIGNATURES))
        return ("comparable campaigns: median {0}{1} (p25 {2}, p75 {3}, n={4})."
                "{5}".format(unit, "{:,}".format(int(_quartile(vals, 50))),
                             "{:,}".format(int(_quartile(vals, 25))),
                             "{:,}".format(int(_quartile(vals, 75))),
                             len(vals), note))

    # THE LOOKER SOURCE. Loaded by tools/load_looker_campaigns.py from a
    # hand-pulled export, and kept in its own table because it is NOT the same
    # metric: campaign_performance holds lifetime PETITION totals, Looker holds
    # signatures attributed to an email CAMPAIGN. The same campaign appears in
    # both with different numbers (129,007 lifetime vs 100,521 attributed), so
    # they are never pooled -- whichever has more comparables is used, and the
    # cell says which.
    try:
        looker = conn.execute(
            "SELECT signatures, new_members, otd_eur, md_eur, areas, "
            "start_date FROM looker_campaigns WHERE list_name = 'EN_GB'").fetchall()
    except Exception:
        looker = []
    lk_hits = [r for r in looker
               if any(a in areas for a in json.loads(r["areas"] or "[]"))]
    lk = [r for r in lk_hits
          if (r["signatures"] or 0) >= MIN_LOOKER_SIGNATURES]
    lk_excluded = len(lk_hits) - len(lk)

    def lk_band(field, unit="", rows=None, dropped=0):
        vals = [r[field] for r in (lk if rows is None else rows)
                if r[field] is not None]
        if not vals:
            return None, 0
        note = (" THIN: {0} campaign(s) only, treat as indicative.".format(
            len(vals)) if len(vals) < 5 else "")
        # Never suppress silently: say what was dropped and why.
        if lk_excluded:
            note += (" {0} sub-{1}-signature Looker row(s) excluded as test "
                     "sends or list segments, not campaigns.".format(
                         lk_excluded, MIN_LOOKER_SIGNATURES))
        if dropped:
            note += (" {0} campaign(s) started on or after {1} excluded: "
                     "donation attribution is incomplete from that date "
                     "(EUR 2.29 per 1,000 signatures against 53 before it), "
                     "so their signatures count but their money cannot."
                     .format(dropped, MONEY_COMPLETE_BEFORE))
        return ("Looker (email-campaign attributed): median {0}{1} "
                "(p25 {2}, p75 {3}, n={4}).{5}".format(
                    unit, "{:,}".format(int(_quartile(vals, 50))),
                    "{:,}".format(int(_quartile(vals, 25))),
                    "{:,}".format(int(_quartile(vals, 75))),
                    len(vals), note)), len(vals)

    def better(field, lk_field, unit="", rows=None, dropped=0):
        """Whichever source has more comparables, labelled."""
        local_n = len([r for r in ranked if r[field] is not None])
        lk_text, lk_n = lk_band(lk_field, unit=unit, rows=rows,
                                dropped=dropped)
        if lk_n > local_n and lk_text:
            return lk_text
        text = band(field, unit=unit)
        if lk_n:
            text += " (Looker holds {0} on a different basis.)".format(lk_n)
        return text

    # Money follows the SAME source rule as the other two rather than being
    # pinned to Looker: raised_eur is unpopulated on all 366 local rows today,
    # but the column exists and a later Max pull may fill it, and silently
    # ignoring a populated column would be its own bug.
    local_money = [r["raised_eur"] for r in ranked if r["raised_eur"] is not None]
    money_rows = [r for r in lk
                  if (r["start_date"] or "") < MONEY_COMPLETE_BEFORE]
    money_dropped = len(lk) - len(money_rows)
    looker_money = [r["otd_eur"] for r in money_rows
                    if r["otd_eur"] is not None]
    if local_money or looker_money:
        money_basis = better("raised_eur", "otd_eur", unit="EUR ",
                             rows=money_rows, dropped=money_dropped)
        if looker_money and len(looker_money) >= len(local_money):
            money_basis += (" One-time donations only; monthly is a separate "
                            "column and much smaller.")
    else:
        money_basis = ("NOT HELD for this topic: raised_eur is unpopulated on "
                       "every campaign_performance row, and the Looker export "
                       "has no comparable EN_GB campaign in this area with "
                       "complete donation attribution. Estimate it.")
        if money_dropped:
            money_basis += (" {0} Looker campaign(s) in this area were "
                            "excluded for starting on or after {1}, when "
                            "donation attribution stops.".format(
                                money_dropped, MONEY_COMPLETE_BEFORE))

    return [("Expected signatures", better("signatures", "signatures")),
            ("Expected new members", better("new_members", "new_members")),
            ("Expected EUR raised", money_basis)]


def rf1_hint(conn, areas):
    """What comparable campaigns on this topic actually did (RF#1 evidence).

    PENDING (Antonio, #campaigns 2026-08-19): RF#1 should also carry a
    NUMERICAL EXPECTATION recorded at Planning -- expected signatures, new
    members and euros -- so Evaluate compares a number with a number rather
    than with narrative. Two things are needed and neither is built:
    blank expectation cells in the RF4 block (needs no data source), and a
    category BASELINE to write them against. See docs/campaign-benchmarks.md
    for the Looker survey, the field names, and the verified data-quality trap
    that makes every topic-level SUM in aa_downstream_report wrong.

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


NATION_TOKENS = {"European Union": (" eu ", "european union", "brussels",
                                    "european parliament", "meps"),
                 "N. Ireland": ("northern ireland", " ni ", "stormont"),
                 "Scotland": ("scotland", "scottish", "holyrood"),
                 "Wales": ("wales", "welsh", "senedd")}


def tim_candidates(conn, subject):
    """Past petitions the TIM row may cite, from the logged campaign record.

    The model picks the most issue-relevant three; this is the WHITELIST it
    picks from, so an id can only ever be one we logged. Area overlap is
    the base filter, widened for devolved subjects by a nation mention in
    the petition name: Christopher's refinement of the RE brief led with
    petition 17165 (area 8, name '... in NI Schools') on a subject tagged
    [6] - geography made it the exact match, and areas alone would have
    missed it.
    """
    try:
        rows = conn.execute(
            "SELECT petition_id, name, signatures, new_members, areas "
            "FROM campaign_performance WHERE petition_id IS NOT NULL "
            "AND name IS NOT NULL").fetchall()
    except Exception:
        return []
    tokens = NATION_TOKENS.get(subject.get("nation") or "", ())
    out = []
    for r in rows:
        r_areas = json.loads(r["areas"] or "[]")
        by_area = any(a in subject["areas"] for a in r_areas)
        padded = " " + (r["name"] or "").lower() + " "
        by_nation = any(t in padded for t in tokens)
        if by_area or by_nation:
            out.append({"id": r["petition_id"], "title": r["name"],
                        "signatures": r["signatures"],
                        "new_members": r["new_members"]})
    out.sort(key=lambda r: -(r["new_members"] or 0))
    return out[:15]


def build_sources(subject, source_text=None):
    """The sources field: '- Title: URL' lines. URLs are NEVER authored -
    only the subject's own record and lines copied verbatim from the source
    material's **Sources** section. The internal monitor link is gone
    (Christopher's refinement, 2026-08-31: internal tooling is not a
    campaign source)."""
    lines = []
    if source_text:
        m = re.search(r"\*\*Sources\*\*\s*\n(.*?)(?=\n\*\*[A-Z]|\Z)",
                      source_text, re.S)
        if m:
            lines = [ln.strip() for ln in m.group(1).strip().splitlines()
                     if ln.strip().startswith("-")]
    if subject.get("url") and not any(subject["url"] in ln for ln in lines):
        lines.insert(0, "- {0}: {1}".format(subject["title"], subject["url"]))
    return "\n".join(lines) if lines else "[CAMPAIGNER: sources]"


def delivery_date(deadline):
    """A concrete delivery date a few days before the close, not 'Before X'
    (Christopher set 26 September against a 30 September close)."""
    try:
        d = datetime.date.fromisoformat(deadline) - datetime.timedelta(days=4)
        return "{0} (close: {1})".format(d.isoformat(), deadline)
    except (ValueError, TypeError):
        return "Before {0}".format(deadline)


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
    # The ledger activity tally stays OUT of the rendered Background: it is
    # internal telemetry, and Christopher's refinement of the RE brief cut
    # it ("105 debate contributions and 23 written questions" is not
    # supporter-facing). The model still receives it in facts.activity_6mo.
    return " ".join(bits)


NARRATIVE_TOKENS = 12000
NARRATIVE_TOKENS_RETRY = 20000
NARRATIVE_EFFORT = "medium"


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
        # budget; 2000 truncated mid-JSON on live runs, and 6000 did too on
        # 21 Sept 2026 ("Unterminated string ... char 5186": the twelve fields
        # are long prose and Sonnet 5 thinks by default). Effort is capped the
        # way the stance read caps it, the budget doubled, and a reply the
        # model could not finish is retried once with room, then reported as
        # what it is rather than parsed as if it were whole.
        "model": stance.STANCE_MODEL, "max_tokens": NARRATIVE_TOKENS,
        "output_config": {"effort": NARRATIVE_EFFORT},
        "system": DRAFT_SYSTEM,
        "messages": [{"role": "user", "content": json.dumps(prompt)}],
    }
    try:
        reply = stance._default_transport(payload, api_key)
        if reply.get("stop_reason") == "max_tokens":
            payload = dict(payload, max_tokens=NARRATIVE_TOKENS_RETRY)
            reply = stance._default_transport(payload, api_key)
            if reply.get("stop_reason") == "max_tokens":
                raise ValueError("reply hit max_tokens twice ({0} then {1}); the draft "
                                 "needs a shorter brief, not a looser parser"
                                 .format(NARRATIVE_TOKENS, NARRATIVE_TOKENS_RETRY))
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


def render_markdown(subject, fields, rf4_hints, expectation, fca,
                    timeline, today):
    lines = ["# Campaigns Brief (DRAFT): {0}".format(
        fields.get("campaign_name", subject["title"])), ""]
    if fields.get("campaign_name") and fields["campaign_name"] != subject["title"]:
        lines.append("Subject: {0}".format(subject["title"]))
        lines.append("")
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
    # An EU subject's list is the campaigner's call: good EU briefs are
    # passed to team members across country lists (Christopher, 2026-09-01),
    # so EN GB must not be baked in.
    lines.append("| List | {0} |".format(
        "[CAMPAIGNER: which list(s)]"
        if subject.get("nation") == "European Union" else "EN GB"))
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
    if fields.get("risks"):
        # Verbatim from the campaigner-supplied source material: handling
        # notes summarised are handling notes lost.
        lines.append("## Risks and handling notes")
        lines.append("")
        lines.append(fields["risks"])
        lines.append("")
    lines.append("## Red Fox Four (scores are the campaigner's call)")
    lines.append("")
    lines.append("| # | Question | Score (-10..+10) | Evidence hint |")
    lines.append("|---|---|---|---|")
    for (code, q), hint in zip(RF4, rf4_hints):
        lines.append("| {0} | {1} | | {2} |".format(code, q, hint))
    lines.append("| | TOTAL IF WE WIN / TOTAL IF WE LOSE | | |")
    lines.append("")
    lines.append("## RF#1 numerical expectation")
    lines.append("")
    lines.append("Expected is BLANK on purpose: the baseline is evidence, the")
    lines.append("expectation is the campaigner's. Fill it at Planning so")
    lines.append("Evaluate compares a number with a number.")
    lines.append("")
    lines.append("| Metric | Expected (Plan) | Actual (Evaluate) | Delta | "
                 "Baseline (evidence) |")
    lines.append("|---|---|---|---|---|")
    for metric, basis in expectation:
        lines.append("| {0} | | | | {1} |".format(metric, basis))
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


def write_csv(path, subject, fields, rf4_hints, expectation, timeline,
              today):
    """The Default Brief tab, row for row as the template lays it out."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["Campaign Name", "Campaigner", "Date of Submission",
                    "Urgency", "List", "Notes", "Approval Date"])
        w.writerow([fields.get("campaign_name", subject["title"]) + " (DRAFT)",
                    "cjoyce@citizengo.net",
                    today.isoformat(), fields["urgency"],
                    ("[CAMPAIGNER: which list(s)]"
                     if subject.get("nation") == "European Union"
                     else "EN GB"),
                    "Draft generated by parl-monitor. Subject: "
                    + subject["title"], ""])
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
        # RF#1's numerical expectation, in the SAME seven columns as RF4 above
        # so the paste-in shape of the Brief template does not change: the
        # existing Plan / Evaluate / Delta geometry already fits
        # expected / actual / delta exactly.
        w.writerow(["RF#1 NUMERICAL EXPECTATION"])
        w.writerow(["Metric", "", "Expected (Plan)", "Baseline (evidence)",
                    "Actual (Evaluate)", "Delta", "Comments"])
        for metric, basis in expectation:
            w.writerow([metric, "", "", basis, "", "", ""])
        w.writerow(["TIMELINE OF MAJOR ACTIONS"])
        w.writerow(["Date", "Action", "Comment"])
        for row in timeline:
            w.writerow(list(row))
        w.writerow(["EVALUATE DASHBOARD"])
        for label in EVALUATE_ROWS:
            w.writerow([label.replace("\\u20ac", "\u20ac"), ""])
        w.writerow(["For more information on how to fill out or interpret this "
                    "document, check the Campaigns Brief Cheat Sheet"])


def eu_5ca_block(conn):
    """The EU brief's Five Columns block: (markdown, rf4 hint, rows).

    Built from make_eu_5ca's placements over SIGNED divisions. With
    nothing signed the marker returns and rows is empty -- the same
    never-an-empty-grid rule the devolved marker enforces.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_eu_5ca", os.path.join(ROOT, "tools", "make_eu_5ca.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    divisions = m.signed_divisions(conn)
    if not divisions:
        return ("**EU 5CA not built: no signed-off divisions yet** - sign "
                "verdicts in config/eu_divisions.yaml and regenerate.",
                "EU 5CA awaits signed division verdicts.", [])
    rows = m.placements(conn, divisions)
    tally = {}
    for r in rows:
        tally[r["column"]] = tally.get(r["column"], 0) + 1
    top_for = [r["name"] for r in rows if r["column"] == "++"][:5]
    top_against = [r["name"] for r in rows if r["column"] == "--"][:5]
    block = ("Suggested gradient over {0} signed EU division(s), {1} MEPs: "
             "{2}\n\nStrongest allies: {3}\n\nStrongest opponents: {4}\n\n"
             "Full grid: briefs/eu-5ca.csv (regenerate with `python3 "
             "tools/make_eu_5ca.py`). Group cohesion rides in its Comments "
             "column - the EP has no whip, so the group split is the "
             "pressure map.").format(
                 len(divisions), len(rows),
                 "  ".join("{0} x{1}".format(c, tally.get(c, 0))
                           for c in ("++", "+", "0", "-", "--")),
                 "; ".join(top_for) or "none placed ++",
                 "; ".join(top_against) or "none placed --")
    hint = "EU 5CA: {0} with us (++/+), {1} against (-/--).".format(
        tally.get("++", 0) + tally.get("+", 0),
        tally.get("-", 0) + tally.get("--", 0))
    return block, hint, rows


def write_eu_5ca_csv(path, rows):
    """The per-brief paste-in grid, from eu_5ca_block's rows."""
    if not rows:
        return False
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["Decision-Maker", "Country", "Group", "Column",
                    "Comments"])
        for r in rows:
            w.writerow([r["name"], r["country"], r["group"], r["column"],
                        r["comments"]])
    return True


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
    # --source PATH (with --force): research the monitor cannot derive from
    # the parliamentary feeds -- quotes from consultation documents, prior
    # campaign results, ministerial commitments, handling notes. The whole
    # file is handed to the narrative model as grounding, and its "Risks
    # and handling notes" section (if it has one) is carried into the
    # brief VERBATIM: handling notes summarised are handling notes lost.
    source_text = None
    if "--source" in sys.argv:
        if not force:
            print("--source only makes sense with --force SLUG")
            return 1
        source_path = sys.argv[sys.argv.index("--source") + 1]
        with open(source_path, encoding="utf-8") as handle:
            source_text = handle.read()

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
                 "activity_6mo": activity,
                 "tim_candidates": tim_candidates(conn, s)}
        if source_text:
            # The source's own Background section joins the deterministic
            # line VERBATIM: the standing facts live there -- prior petition
            # results net of duplicates, ministerial commitments -- and the
            # model paraphrasing them is exactly what must not happen.
            m = re.search(r"\*\*Background / Context\*\*\s*\n(.*?)(?=\n\*\*[A-Z])",
                          source_text, re.S)
            if m:
                bg = bg + " " + " ".join(m.group(1).split())
                facts["background"] = bg
            facts["source_material"] = source_text
            facts["source_rules"] = (
                "Ground every claim in the source material. Carry its "
                "quotes, dates and figures EXACTLY; signature counts are "
                "always quoted net of duplicates. Follow its risks and "
                "handling notes -- in particular any framing it warns "
                "against. Never invent names of parliamentarians or "
                "officials; use only those the source names.")
        drafted = draft_narrative(s, facts, api_key) or {}

        def field(fid, question):
            v = drafted.get(fid)
            return (question, v if v else "[CAMPAIGNER: draft needed]")

        general = [
            ("Type of Campaign", "[CAMPAIGNER: Survival / Obligatory / Opportunity]"),
            ("Topic", " / ".join(sorted({AREA_TOPIC.get(a, "Freedom") for a in s["areas"]}))),
            # Acquisition, not Political Impact (Christopher's default,
            # 2026-08-31, set refining the RE brief).
            ("Main Purposes", "Acquisition"),
            ("Background / Context", bg),
            ("Estimated Launch date", "[CAMPAIGNER]"),
            ("Estimated date for Delivering Signatures",
             (delivery_date(s["deadline"]) if s.get("deadline") else "[CAMPAIGNER]")),
            field("offline", "Ideas for eventual Offline Actions"),
            ("Petitions related TIM project (Targeting Inactive Members)",
             drafted.get("tim") or "[CAMPAIGNER: related petitions for TIM]"),
        ]
        plan = [
            ("What is the language for this petition?", "English"),
            ("Who will sign the emails for this petition?", "Christopher Joyce"),
            ("Who is the petition addressed to?",
             drafted.get("addressee") or addressed_to(s)),
            field("ask", "What are we asking for in the petition?"),
            field("listen", "Why would they listen to us?"),
            ("What is happening that we are responding to?", bg),
            field("injustice", "What is the key point of injustice that is at stake here?"),
        ]
        prepare = [
            field("arguments", "What are some arguments supporting our point of view?"),
            field("urgency", "Why is it urgent that we take action now?"),
            field("bad_outcome", "Describe a bad outcome if we do not win this campaign:"),
            field("good_outcome", "Describe a good outcome if we do win this campaign:"),
            ("Which sources do you want to include? Please provide the titles plus URLs:",
             build_sources(s, source_text)),
            field("image", "What should the image for this campaign look like?"),
        ]

        fca_block = ""
        eu_rows = []
        rf4_ally_hint = "See the 5CA sheets for allies on this area."
        if s.get("nation") == "European Union":
            # The EU 5CA exists since 2026-09-01 (make_eu_5ca: verdicts x
            # roll calls x groups over SIGNED divisions). An EU brief gets
            # the real grid; with nothing signed the tool refuses and the
            # marker returns -- never an empty grid.
            fca_block, rf4_ally_hint, eu_rows = eu_5ca_block(conn)
        elif s.get("nation"):
            # The 5CA is built from Westminster division lists; there is no
            # devolved equivalent wired in. An explicit marker, never an
            # empty grid that looks like an oversight (the spec's open
            # question, resolved to the marker option, 2026-08-31).
            fca_block = ("**5CA not available for devolved items - populate "
                         "manually.** The Five Column Analysis is built from "
                         "Westminster division lists; no {0} membership "
                         "source is wired in yet.".format(s["nation"]))
            rf4_ally_hint = ("5CA not available for devolved items - "
                             "populate manually.")
        elif s["areas"]:
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

        expectation = rf1_expectation(conn, s["areas"])
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
                  "urgency": urgency_of(s, today),
                  # The campaign carries a campaign headline, never the
                  # subject's official title (Christopher's refinement:
                  # "Tell Paul Givan: Don't let Christianity become merely
                  # one worldview among many"). The slug, brief_log and the
                  # Drive file name keep the official title for traceability.
                  "campaign_name": drafted.get("campaign_name") or s["title"]}
        if source_text:
            m = re.search(r"^#+\s*RISKS AND HANDLING NOTES\s*$\n(.*?)(?=^#+ |\Z)",
                          source_text, re.M | re.S | re.I)
            if m:
                fields["risks"] = m.group(1).strip()
            rf4_hints.append("Suggested RF4 scores and reasoning are in the "
                             "source material; scores stay the campaigner's "
                             "call.")
        md_path = os.path.join(BRIEFS_DIR, s["slug"] + ".md")
        csv_path = os.path.join(BRIEFS_DIR, s["slug"] + ".csv")
        fca_path = os.path.join(BRIEFS_DIR, s["slug"] + "-5ca.csv")
        with open(md_path, "w", encoding="utf-8") as handle:
            handle.write(render_markdown(s, fields, rf4_hints, expectation,
                                         fca_block, timeline,
                                         today.isoformat()))
        write_csv(csv_path, s, fields, rf4_hints, expectation, timeline, today)
        has_5ca = (write_eu_5ca_csv(fca_path, eu_rows)
                   if s.get("nation") == "European Union"
                   else False if s.get("nation")
                   else write_5ca_csv(fca_path, conn, s, cfg))
        if has_5ca:
            print("  5ca:   {0}".format(os.path.basename(fca_path)))
        # One spreadsheet per brief, Default Brief section then Five Columns
        # Analysis, mirroring how the team's real Briefs are shaped
        # (Christopher, 2026-08-13: "they should look like sheets"). This is
        # the file that goes to Drive for review; the split CSVs stay for
        # tab-by-tab paste-in.
        narr_path = os.path.join(BRIEFS_DIR, s["slug"] + "-narrative.csv")
        with open(narr_path, "w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(NARRATIVE_SCAFFOLD)
        sheet_path = os.path.join(BRIEFS_DIR, s["slug"] + "-sheet.csv")
        with open(sheet_path, "w", encoding="utf-8", newline="") as handle:
            w = csv.writer(handle)
            for src in ([csv_path] + ([fca_path] if has_5ca else [])):
                with open(src, encoding="utf-8", newline="") as inp:
                    for r in csv.reader(inp):
                        # The evidence column is megabytes of dated trails: it
                        # belongs in the paste-in CSV, not the review sheet.
                        if len(r) >= 11:
                            r = r[:8] + ["(evidence in briefs/{0}-5ca.csv)".format(s["slug"])] + r[9:11]
                        w.writerow(r)
                w.writerow([])
            # Only three tabs are reproduced: Default Brief, Five Column
            # Analysis and Campaign Narrative (Christopher, 2026-08-14). The
            # template's relaunch tabs belong to later relaunches, not to a
            # new brief.
            for row in NARRATIVE_SCAFFOLD:
                w.writerow(row)
        print("  sheet: {0}".format(os.path.basename(sheet_path)))
        # The Asana approval task is BACK (Christopher, 2026-08-31, third
        # asking -- superseding the 2026-08-21 retirement): each generated
        # brief creates a review task in the EN GB Weekly Meeting agenda
        # project. A missing PAT reports itself skipped, as everything in
        # publish.py does; rejection remains a deliberate act and is still
        # load-bearing (regeneration guard + the Drive publisher gate).
        approval = {}
        try:
            from src import publish as _pub
            _secrets = _pub.load_secrets()
            if _secrets.get("asana_pat"):
                approval = _pub.asana_create_brief_approval(
                    _secrets, s["title"], s["slug"],
                    deadline=s.get("deadline")) or {}
                if approval.get("task_gid"):
                    print("  asana: review task {0}".format(
                        approval.get("permalink") or approval["task_gid"]))
                elif approval.get("error"):
                    print("  asana: {0}".format(approval["error"]))
        except Exception as exc:                        # noqa: BLE001
            print("  asana: skipped ({0})".format(exc))
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
