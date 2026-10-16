"""The review window for the new country editions (11 October 2026).

UK parity, as the UK loop worked (src/review.py, retired there on 21 August
2026): the weekly run writes a review file Chris may edit before the edition
goes out, his decisions survive a rerun, and the edition is sent at the end
of the window whether he looked or not. Change nothing and it goes out
unchanged.

FOR EACH OWN EDITION (src/country_edition.py, the fifteen countries) AND THE
LATAM MONTHLY (tools/latam_monitor.py), when config/edition-review.yaml has
the review on (the default for all sixteen):

1. The weekly job's `--edition --dm` no longer DMs. It writes the edition as
   a draft (a line under the subtitle says when it is sent), writes
   `reviews/<cc>-review-<date>.md` (the Latam one is `latam-review-<date>.md`)
   and records the window in `data/edition-reviews/<cc>-<date>.json`
   (committed with data/, one file per edition so two runners never touch
   the same file). `<date>` is the edition's own date, as in
   editions/<cc>-monitor-<date>.md.
2. Chris may edit the review file on main until the window ends: per item
   `DECISION: keep` (the default), `cut` or `edit` (with `TAKEAWAY:`, the
   English line under the title; titles stay the source's own words); for
   the whole edition `NOTE:` (one line under the subtitle and in the DM) and
   `PUBLISH: go` (the default), `hold` or `now`.
3. A rerun the same day (the job's "rewrite, not resend" branch) and the
   Sunday session judge's rewrite regenerate the file merge-preserving: every
   decision and the header are carried over; a decision for an item no
   longer listed is kept at the foot, and applies again if the item returns.
4. tools/edition_review.py --publish (jobs/edition-publish.sh, Mac Mini,
   06:31 and 21:10 London) renders each edition whose window has ended,
   honouring the review, rewrites editions/<cc>-monitor-<date>.md, DMs Chris
   alone as before, and keeps ONE combined Asana reading task per reading
   week for all of them (created by the first edition of the week, its notes
   rewritten as later ones go out), assigned as the UK reading task is.

Not reviewed, sent at once as before: the same-day vote briefs
(tools/country_vote_briefs.py), the Latam instant alerts
(tools/latam_alerts.py), the stance digest and the judge's notices.

The window: `publish_at` (London time, default 06:30) on the day
`after_days` (default 1) after the edition's date. So the Saturday weeklies
go out on Sunday at 06:31, Poland's Sunday edition on Monday, Slovakia's on
Wednesday, Hungary's on Thursday, the Netherlands' on Friday, and the Latam
monthly on the 2nd.

Pure functions here; the store is never read. Stdlib and PyYAML only.
"""

from __future__ import annotations

import datetime
import glob
import json
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "edition-review.yaml")
REVIEWS = os.path.join(ROOT, "reviews")
STATE = os.path.join(ROOT, "data", "edition-reviews")
LONDON = "Europe/London"

# The editions the review applies to: the own editions and the Latam monthly.
OWN = ("es", "it", "fr", "nl", "be", "at", "ch", "pl", "pt", "hr", "sk", "hu", "br",
       "ar", "mx")
LATAM = "latam"
# Editions rendered by their own tool, not src/country_edition.py (additive,
# 16 October 2026, branch de-ca-gaps): Germany's (tools/de_monitor.py, its
# review units its Vorgänge, recorded votes and Drucksachen).
OTHER = ("de",)
CCS = OWN + OTHER + (LATAM,)

DEFAULTS = {"review": True, "publish_at": "06:30", "after_days": 1}
DECISIONS = ("keep", "cut", "edit")
PUBLISH = ("go", "hold", "now")
CUT_REASON = "cut in review"
RUN_TIMES = "06:31 and 21:10 London"      # jobs/edition-publish.sh's slots

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _tz():
    from zoneinfo import ZoneInfo
    return ZoneInfo(LONDON)


# --- settings ----------------------------------------------------------------------

def load_config(path=None):
    path = path or CONFIG
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def settings(cc, config=None):
    """{review, publish_at, after_days} for cc: the defaults, the file's
    `default:` block, then the country's own line. Anything not in CCS is
    never reviewed (the UK, US, IE, AU and CA editions are not touched;
    Germany joined on 16 October 2026, OTHER)."""
    config = load_config() if config is None else config
    got = dict(DEFAULTS)
    got.update(config.get("default") or {})
    got.update((config.get("countries") or {}).get(cc) or {})
    if cc not in CCS:
        got["review"] = False
    return got


def enabled(cc, config=None):
    return bool(settings(cc, config).get("review"))


def deadline(cc, date, config=None):
    """When the window ends: an aware London datetime."""
    s = settings(cc, config)
    hh, mm = (int(x) for x in str(s.get("publish_at") or "06:30").split(":", 1))
    day = datetime.date.fromisoformat(date) + datetime.timedelta(days=int(s.get("after_days", 1)))
    return datetime.datetime(day.year, day.month, day.day, hh, mm, tzinfo=_tz())


def when_text(iso):
    """'06:30 London on Sunday 11 October 2026'."""
    d = datetime.datetime.fromisoformat(iso).astimezone(_tz())
    return "{0:02d}:{1:02d} London on {2} {3} {4} {5}".format(
        d.hour, d.minute, DAYS[d.weekday()], d.day, MONTHS[d.month - 1], d.year)


def now_london():
    return datetime.datetime.now(_tz())


# --- the window's state (data/edition-reviews/) -------------------------------------

def state_path(cc, date, state_dir=None):
    return os.path.join(state_dir or STATE, "{0}-{1}.json".format(cc, date))


def state(cc, date, state_dir=None):
    path = state_path(cc, date, state_dir)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_state(st, state_dir=None):
    path = state_path(st["cc"], st["date"], state_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def open_window(cc, date, config=None, state_dir=None, now=None):
    """Record the window for cc's edition of `date` (once; an existing
    record is returned unchanged)."""
    got = state(cc, date, state_dir)
    if got:
        return got
    now = now or now_london()
    st = {"cc": cc, "date": date, "opened_at": now.isoformat(timespec="seconds"),
          "deadline": deadline(cc, date, config).isoformat(timespec="minutes"),
          "published_at": None}
    save_state(st, state_dir)
    return st


def pending(cc, date, state_dir=None):
    """The window's deadline (ISO) while the edition is still unsent, else None."""
    st = state(cc, date, state_dir)
    return st["deadline"] if st and not st.get("published_at") else None


def all_states(state_dir=None):
    out = []
    for f in sorted(glob.glob(os.path.join(state_dir or STATE, "*.json"))):
        if os.path.basename(f).startswith("asana-"):
            continue
        with open(f, encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


def unsent(state_dir=None):
    return [st for st in all_states(state_dir) if not st.get("published_at")]


def is_due(st, review, now):
    """(due, why) for an unsent edition."""
    if review is not None and review.publish == "hold":
        return False, "held in review (PUBLISH: hold)"
    if review is not None and review.publish == "now":
        return True, "PUBLISH: now"
    if now >= datetime.datetime.fromisoformat(st["deadline"]):
        return True, "window ended " + when_text(st["deadline"])
    return False, "window open until " + when_text(st["deadline"])


# --- review units -------------------------------------------------------------------

def unit_id(it):
    """One line of the review per entry the edition renders: a vote group
    (one bill's votes render as one entry) or an item."""
    if it.get("kind") == "vote" and it.get("group"):
        return "{0}|vote-group|{1}".format(it["cc"], it["group"])
    return "{0}|{1}|{2}".format(it["cc"], it["kind"], it["key"])


class Review:
    """A parsed review file: the header and each unit's decision."""

    def __init__(self, publish="go", note="", decisions=None):
        self.publish = publish
        self.note = note
        self.decisions = decisions or {}      # id -> {"decision", "takeaway"}

    def decision(self, uid):
        d = self.decisions.get(uid) or {}
        dec = d.get("decision") or "keep"
        if dec == "keep" and d.get("takeaway"):
            dec = "edit"                       # a takeaway written is an edit
        if dec == "edit" and not d.get("takeaway"):
            dec = "keep"                       # an edit with nothing written changes nothing
        return dec, d.get("takeaway") or ""

    def counts(self):
        """(cut, edited) over every unit with a decision."""
        got = [self.decision(u)[0] for u in self.decisions]
        return got.count("cut"), got.count("edit")

    def changed(self):
        cut, edited = self.counts()
        return bool(cut or edited or self.note)


def _norm_decision(v):
    v = (v or "").strip().lower().strip("`*_ ")
    if v in ("cut", "drop", "x", "delete", "remove", "out"):
        return "cut"
    if v in ("edit", "edited", "change"):
        return "edit"
    return "keep"


def parse(text):
    rv = Review()
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("### item:"):
            cur = line.split("item:", 1)[1].strip()
            rv.decisions[cur] = {"decision": "keep", "takeaway": ""}
            continue
        m = re.match(r"^(PUBLISH|NOTE|DECISION|TAKEAWAY):(.*)$", line, re.I)
        if not m:
            continue
        key, val = m.group(1).upper(), m.group(2).strip()
        if cur is None:
            if key == "PUBLISH":
                v = val.lower().strip("`*_ ")
                rv.publish = v if v in PUBLISH else "go"
            elif key == "NOTE":
                rv.note = val
        elif key == "DECISION":
            rv.decisions[cur]["decision"] = _norm_decision(val)
        elif key == "TAKEAWAY":
            rv.decisions[cur]["takeaway"] = val
    return rv


def review_path(cc, date, directory=None):
    return os.path.join(directory or REVIEWS, "{0}-review-{1}.md".format(cc, date))


def load(cc, date, directory=None):
    """The parsed review for cc's edition of `date`, or an empty Review."""
    path = review_path(cc, date, directory)
    if not os.path.exists(path):
        return Review()
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read())


def apply(items, review):
    """(kept, cut): items with the review honoured. A cut item carries
    `dropped` = CUT_REASON (counted under Coverage like the noise filters'
    drops); an edited item's `takeaway` is replaced. Items the review does
    not list are kept as they are."""
    if review is None:
        return list(items), []
    kept, cut = [], []
    for it in items:
        dec, text = review.decision(unit_id(it))
        if dec == "cut":
            cut.append(dict(it, dropped=CUT_REASON))
        elif dec == "edit":
            kept.append(dict(it, takeaway=text, reviewed=True))
        else:
            kept.append(it)
    return kept, cut


def note_line(review):
    """The edition's line for Chris's NOTE, or None."""
    if review is None or not review.note:
        return None
    return "**Note from the review:** {0}".format(review.note)


def draft_line(deadline_iso):
    return ("_Draft under review: sent to Chris by DM at {0}, as it stands then "
            "(reviews/, config/edition-review.yaml)._".format(when_text(deadline_iso)))


def dm_review_line(review):
    """The DM's line saying what the review changed."""
    if review is None:
        return None
    cut, edited = review.counts()
    if not (cut or edited or review.note):
        return "_Review window ended with no changes: sent as drafted._"
    bits = []
    if cut:
        bits.append("{0} cut".format(cut))
    if edited:
        bits.append("{0} edited".format(edited))
    if review.note:
        bits.append("a note added")
    return "_Reviewed: {0}._{1}".format(", ".join(bits),
                                        "\n" + review.note if review.note else "")


# --- writing the review file ---------------------------------------------------------

HEADER = """# {name} edition: review before it is sent

Edition of {long} (`editions/{edition}`). **Sent to Chris by DM at {when}**, as it stands then.
Change nothing and it goes out unchanged.

How to review (edit this file on main before then; the publish step, {runs}, reads it):
- `DECISION: keep` leaves an item as drafted (the default).
- `DECISION: cut` leaves it out of the edition and the DM; Coverage counts it as cut in review.
- `DECISION: edit` replaces the English line under the title with your `TAKEAWAY:` text
  (writing a `TAKEAWAY:` is enough). Titles stay the source's own words.
- `NOTE:` one line of your own, under the edition's subtitle and in the DM.
- `PUBLISH: hold` keeps the whole edition back until you set `go`; `PUBLISH: now` sends it
  at the next publish run.
Do not edit the `### item:` lines. A rerun keeps every decision here.

PUBLISH: {publish}
NOTE: {note}

---
"""


def _unit_lines(uid, entry, prior):
    kind, date, title, areas, flags, takeaway = entry
    dec, text = prior.decision(uid) if prior else ("keep", "")
    return ["### item: {0}".format(uid),
            "- {0} · {1}{2}{3}".format(kind, date, " · " + areas if areas else "",
                                      " · " + flags if flags else ""),
            "- title: *{0}*".format(title or "(no title published)"),
            "- takeaway as drafted: {0}".format(takeaway or "(none)"),
            "DECISION: {0}".format(dec),
            "TAKEAWAY: {0}".format(text),
            ""]


def units(items, describe):
    """[(id, entry)] in edition order, one per vote group or item. `describe`
    turns an item into (kind label, date, title, areas, flags, takeaway)."""
    out, seen = [], {}
    for it in items:
        uid = unit_id(it)
        if uid in seen:
            continue
        entry = describe(it)
        if uid.split("|")[1] == "vote-group":
            group = [i for i in items if unit_id(i) == uid]
            title = it.get("group_title") or it["title"]
            entry = ("{0} recorded votes on one item".format(len(group))
                     if len(group) > 1 else entry[0],
                     entry[1], title, entry[3], entry[4], entry[5])
        seen[uid] = entry
        out.append((uid, entry))
    return out


def write(cc, date, name, items, describe, deadline_iso, directory=None, sections=None):
    """Write (or rewrite, merge-preserving) the review file. `sections`, when
    given, is [(heading, items)] (the Latam edition's countries); otherwise
    one list. Returns (path, number of units)."""
    path = review_path(cc, date, directory)
    prior = load(cc, date, directory) if os.path.exists(path) else None
    edition = "{0}-monitor-{1}.md".format(cc, date)
    d = datetime.date.fromisoformat(date)
    out = [HEADER.format(name=name, long="{0} {1} {2}".format(d.day, MONTHS[d.month - 1], d.year),
                         edition=edition, when=when_text(deadline_iso), runs=RUN_TIMES,
                         publish=prior.publish if prior else "go",
                         note=prior.note if prior else "")]
    listed = set()
    n = 0
    for heading, these in (sections or [(None, items)]):
        us = units(these, describe)
        if heading and us:
            out.append("## {0}\n".format(heading))
        if not us and not heading:
            out.append("Nothing on our ground in this edition: nothing to review.\n")
        for uid, entry in us:
            listed.add(uid)
            n += 1
            out.append("\n".join(_unit_lines(uid, entry, prior)))
    if prior:
        gone = [u for u in prior.decisions if u not in listed
                and (prior.decision(u)[0] != "keep")]
        if gone:
            out.append("## Decisions for items no longer in this edition\n\n"
                       "Kept so a rerun never loses them; each applies again if its item "
                       "returns.\n")
            for uid in gone:
                dec, text = prior.decision(uid)
                out.append("\n".join(["### item: {0}".format(uid), "DECISION: {0}".format(dec),
                                      "TAKEAWAY: {0}".format(text), ""]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out).rstrip("\n") + "\n")
    return path, n


# --- the combined Asana reading task -------------------------------------------------

def reading_week(date):
    """The Monday of the week the edition is read in: editions dated from a
    Saturday to the Friday after belong to the week commencing the Monday
    in between (the Saturday weeklies, Poland's Sunday, Slovakia's Tuesday,
    Hungary's Wednesday and the Netherlands' Thursday share one task)."""
    d = datetime.date.fromisoformat(date)
    sat = d - datetime.timedelta(days=(d.weekday() - 5) % 7)
    return (sat + datetime.timedelta(days=2)).isoformat()


def asana_state_path(week, state_dir=None):
    return os.path.join(state_dir or STATE, "asana-{0}.json".format(week))


def asana_state(week, state_dir=None):
    path = asana_state_path(week, state_dir)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_asana_state(week, st, state_dir=None):
    path = asana_state_path(week, state_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def published_in_week(week, state_dir=None):
    """The editions sent so far whose reading week is `week`, in date order."""
    return sorted((st for st in all_states(state_dir)
                   if st.get("published_at") and reading_week(st["date"]) == week),
                  key=lambda s: (s["date"], s["cc"]))
