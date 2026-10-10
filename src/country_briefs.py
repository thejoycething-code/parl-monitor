"""Campaign briefs for the new countries (10 October 2026).

Parity item 7 of docs/country-parity-handover.md ("campaign tools"), built on
the 5CA-with-sign-off layer (src/country5ca.py). For each new subject in a
country's store, a watched or tier-1 bill that moved recently, it drafts a
CitizenGO Campaigns Brief in the RF4 template's shape
(docs/brief-builder/rulebook.md), as tools/de_briefs.py does for Germany,
and keeps it current while nobody has edited it.

WHAT FILLS IT. Only the record: the bill (title, key, stage, link, who
brought it where the store says), its dates (introduction, the last event,
the next agenda date where the store holds the agenda: France, Croatia), its
recorded votes (tallies as the chamber labels them), the deciding chamber
and its seats by party (the store's roster), the taxonomy area (Topic), the
country's list and language (config/country-briefs.yaml), and dates worked
out by the rulebook's rules (launch, delivery, urgency). No model is called
(X16; the paid judge stays off and no AI API is used). Everything the record
cannot give is an explicit [CAMPAIGNER: ...] placeholder naming what is
needed, never a guess and never an empty cell that looks considered.

CONFIRMED STANCES ONLY. A brief recommends nothing a person has not signed:
  * the ask, the storytelling line and the campaign name's verb follow the
    bill's direction in config/<cc>_stance.yaml `bill_directions`, and only
    once it is confirmed (`status: confirmed`, `confirmed_by`,
    `confirmed_on`; tools/country_5ca.py --confirm-direction);
  * the Five Column Analysis, the targets and the segment split come from
    src/country5ca.build_rows over CONFIRMED readings only; otherwise the
    brief carries the "5CA awaiting sign-off" block, which places nobody;
  * a brief is NOT READY, in a banner at its head, in the form's Notes line
    and in brief_log (status `not-ready`), until the bill's direction AND
    every reading of the bill's watched or tier-1 votes are confirmed. Then
    it says READY (brief_log status `draft`, as the German briefs).

THE LANGUAGE. The campaigner text is in the country's language
(src/brief_phrases.py, config `language: local`), as Chris asked on 10
October 2026; the cell labels are the template's own, the header values are
the Asana form's (English, rulebook cell 1 keeps the Campaign Name English),
and the Builder tab is English. `language: en` in the config switches the
campaigner text to English, which is what rulebook rule 6 and the German
briefs do.

UPDATE MODE (rulebook "Entry points and modes"). One brief per subject ever.
Each weekly run re-renders a brief whose file is exactly what the builder
last wrote (its fingerprint, kept in data/country-briefs/<cc>.json), so a
confirmation in the stance file reaches the brief the next week. A file a
person has edited is never touched; --force rewrites it on request. A slug
brief_log marks `rejected` is never written again.

Nothing is sent: no DM, no Asana task, no Drive upload (brief_log's
`not-ready` and `draft` are not statuses the Drive publisher picks up). The
UK and German editions carry no brief line, so neither do the country
editions.
"""

from __future__ import annotations

import collections
import csv
import datetime
import hashlib
import importlib.util
import io
import json
import os
import re
import sqlite3

import yaml

from src import brief_phrases
from src import country5ca as c5
from src import readings5ca as r5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "country-briefs.yaml")
BRIEFS_DIR = os.path.join(ROOT, "briefs")
LEDGER_DIR = os.path.join(ROOT, "data", "country-briefs")
EXCLUDED_AREAS = {11}          # migration: collated, never campaigned
BILL_KINDS = ("new", "moved", "updated")
RECENT_DAYS = 90               # a "new subject" moved within this many days
MAX_NEW = 8                    # new briefs per country per run, the rest wait a week
SLUG_TITLE_CHARS = 48
STATUS_NOT_READY, STATUS_READY = "not-ready", "draft"
OWN_STATUSES = (STATUS_NOT_READY, STATUS_READY)

TAGS = {"fact": "🔒", "draft": "✏️", "campaigner": "👤", "blank": "⛔"}

# A bill whose status or takeaway says it is over is no campaign subject.
# Folded (lower case, accents off). Deliberately narrow: a phrase that also
# names a live stage ("aprobado", "aangenomen": passed one chamber of two) is
# not here, so the error is an extra draft, never a lost one.
CONCLUDED = [re.compile(p) for p in (
    r"\bpassed\b", r"\blapsed\b", r"\brejected\b", r"\bwithdrawn\b", r"became law",
    r"published as", r"\bpromulgat",
    r"podpisal", r"odrzucon", r"wycofan",                                   # pl
    r"concluido", r"caducad", r"\bcerrado\b", r"retirad", r"rechazad", r"archivad",
    r"promulgad", r"sancionad",                                             # es
    r"approvato definitivamente", r"approvato in via definitiva", r"respint", r"ritirat",
    r"assorbit", r"decadut",                                                # it
    r"adopte definitivement", r"promulgu", r"\brejet", r"\bretire", r"\bcaduc",   # fr
    r"verworpen", r"ingetrokken", r"vervallen", r"tot wet verheven",        # nl
    r"abgelehnt", r"zuruckgezogen", r"\berledigt", r"abgeschrieben",        # de
    r"rejeitad", r"arquivad", r"transformad[oa] em (?:lei|norma)",          # pt
    r"odbijen", r"povucen",                                                 # hr
    r"vzaty spat", r"zamietnut",                                            # sk
    r"kihirdet", r"visszavon", r"elutasit",                                 # hu
)]

_STOP = r"(?:;|(?<!\bSen)(?<!\bDep)(?<!\bDip)(?<!\bOn)(?<!\bDr)(?<!\bSr)(?<!\bHon)(?<!\b[A-Z])\.\s|\.?$)"
SPONSOR = re.compile(r"(?:presented|brought|tabled|introduced|sponsored|filed) by (.+?)" + _STOP
                     + r"|\bfrom ((?:Grupo|Group|the ).+?)" + _STOP, re.I)


# --- configuration ---------------------------------------------------------------

def load_config(path=None):
    with open(path or CONFIG_PATH, encoding="utf-8") as h:
        cfg = yaml.safe_load(h) or {}
    cfg.setdefault("countries", {})
    cfg.setdefault("campaigner", {"name": "Christopher Joyce", "email": "cjoyce@citizengo.net"})
    cfg.setdefault("language", "local")
    return cfg


def country_cfg(cfg, cc):
    got = dict(cfg["countries"].get(cc) or {})
    got.setdefault("lang", "en")
    got.setdefault("chamber", cc.upper())
    got.setdefault("members", "members")
    got.setdefault("chambers", {})
    got.setdefault("glossary", {})
    got.setdefault("allies", [])
    got.setdefault("opponents", [])
    return got


def phrases_for(cfg, cc):
    ccfg = country_cfg(cfg, cc)
    lang = "en" if cfg.get("language") == "en" else ccfg["lang"]
    return brief_phrases.phrases(lang, swiss=bool(ccfg.get("swiss"))), lang


def fold(text):
    from src.filter import _fold
    return " ".join(_fold(text or "").lower().split())


def clip(text, n):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n - 3].rstrip() + "..."


def ascii_text(text):
    """Accents and special characters off, case kept (Zapier, rulebook cell 1)."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"[^A-Za-z0-9 ?!,:'-]", "", "".join(c for c in text if not unicodedata.combining(c)))


def slugify(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (text or "").lower())).strip("-")


def slug_for(cc, title, key):
    """'<cc>-<title>-<key>': the key makes it unique and stable (two bills
    may share a title; tools/de_briefs.py, the 'Mitteilung der Kommission'
    collision)."""
    stem = slugify(fold(title))[:SLUG_TITLE_CHARS].strip("-")
    return "{0}-{1}-{2}".format(cc, stem or "subject", slugify(key) or "x")


def add_working_days(day, n):
    """`day` plus n working days (Saturdays and Sundays skipped; public
    holidays are not known here, and the brief says so)."""
    step = 1 if n >= 0 else -1
    left = abs(n)
    while left:
        day += datetime.timedelta(days=step)
        if day.weekday() < 5:
            left -= 1
    return day


# --- the store ---------------------------------------------------------------------

def _items(conn, cc, since, until, config_dir=None):
    """(items, watchlist, Country or None): the country's items in the window,
    after its noise filters and mutes, with the session judge's scores; an
    unwatched item the judge scored 0 is dropped."""
    from src import country_edition as ce
    from src import edition_judge
    from src import latam
    conn.row_factory = sqlite3.Row
    if cc in latam.ADAPTERS:
        from src import latam_noise
        wl = latam.watchlist(cc, config_dir)
        got = latam.ADAPTERS[cc](conn, since, until, wl) or []
        got, _ = latam_noise.NOISE.split(got, config_dir)
        country = None
    else:
        country = ce.adapter(cc)
        wl = ce.watchlist_of(country, config_dir)
        got = country.items(conn, since, until, wl) or []
        got, _ = ce.noise_for(country).split(got, config_dir)
    got, _ = edition_judge.split(edition_judge.annotate(conn, got))
    return got, wl, country


def concluded(it):
    if it.get("kind") == "law":
        return True
    text = fold("{0} | {1}".format(it.get("status") or "", it.get("takeaway") or ""))
    return any(p.search(text) for p in CONCLUDED)


def _vote_keys(it):
    return {k for k in (it.get("watch_key"), it.get("group")) if k}


def _int_tier(t):
    try:
        return int(t)
    except (TypeError, ValueError):
        return None


def subjects(conn, cc, today, recent_days=RECENT_DAYS, config_dir=None):
    """Every watched or tier-1 bill of the country that is still live, newest
    activity first, each with `recent` True when it moved (was introduced,
    changed stage or was voted on) within `recent_days`. Only recent ones
    become NEW briefs; the rest are kept so an existing brief can refresh."""
    today_d = datetime.date.fromisoformat(today)
    items, wl, country = _items(conn, cc, "1900-01-01", today, config_dir)
    since = (today_d - datetime.timedelta(days=recent_days)).isoformat()
    recent_items, _, _ = _items(conn, cc, since, today, config_dir)
    recent_keys, recent_bill = set(), {}
    for it in recent_items:
        recent_keys.add(it["key"])
        recent_keys |= _vote_keys(it)
        if it["kind"] in BILL_KINDS:
            recent_bill[it["key"]] = it
    bills, votes = {}, collections.defaultdict(list)
    for it in items:
        if it["kind"] == "vote":
            for k in _vote_keys(it):
                votes[k].append(it)
        elif it["kind"] in BILL_KINDS:
            prev = bills.get(it["key"])
            if prev is None or (it["date"] or "") > (prev["date"] or ""):
                bills[it["key"]] = it
    ahead = []
    if country is not None and country.week_ahead:
        try:
            ahead = country.week_ahead(conn, today, wl) or []
        except Exception:                                    # noqa: BLE001
            ahead = []
    for a in ahead:
        # A bill on the current agenda is live and moving, whatever the edition
        # calls new (Croatia's first day of records is a baseline, not news).
        if a.get("key") and a["key"] not in bills and a.get("kind") == "agenda":
            bills[a["key"]] = a
            recent_keys.add(a["key"])
    out = []
    for key, it in bills.items():
        if key.startswith("item:"):
            continue                  # an agenda item that is no bill (Croatia's interpellations)
        watched = bool(it.get("watched")) or key in wl
        tier = _int_tier(it.get("tier"))
        if not watched and tier != 1:
            continue
        areas = [int(a) for a in it.get("areas") or [] if str(a).isdigit()]
        if not areas and watched:
            areas = [int(a) for a in (wl.get(key) or {}).get("areas") or [] if str(a).isdigit()]
        areas = [a for a in areas if a not in EXCLUDED_AREAS]
        if not areas:
            continue
        latest = recent_bill.get(key, it)
        if concluded(it) or concluded(latest):
            continue
        vts = sorted(votes.get(key, []), key=lambda v: (v["date"] or "", v["key"]))
        dates = [d for d in [it["date"], latest["date"]] + [v["date"] for v in vts] if d]
        nxt = sorted(a["date"] for a in ahead
                     if a.get("date") and a["date"] > today       # a standing note is dated today
                     and key in ({a.get("key"), a.get("watch_key"), a.get("group")} | set(a.get("refs") or [])))
        m = SPONSOR.search(latest.get("takeaway") or it.get("takeaway") or "")
        out.append({
            "cc": cc, "key": key, "slug": slug_for(cc, it["title"], key), "title": it["title"],
            "stage": latest.get("status") or it.get("status"), "url": latest.get("url") or it.get("url"),
            "areas": areas, "tier": tier, "watched": watched,
            "watch_note": (wl.get(key) or {}).get("why"),
            "takeaway": latest.get("takeaway") or it.get("takeaway"),
            "sponsor": (m.group(1) or m.group(2)).strip() if m else None,
            "first_date": it["date"], "last_date": max(dates) if dates else None,
            "last_item": latest, "vote_items": vts,
            "next_date": nxt[0] if nxt else None,
            "judge_why": latest.get("judge_why") or it.get("judge_why"),
            "recent": key in recent_keys,
        })
    out.sort(key=lambda s: s["last_date"] or "", reverse=True)
    out.sort(key=lambda s: not s["watched"])
    return out


# --- stances ------------------------------------------------------------------------

_QUAL = {}


def _qualifying(conn, cc):
    k = (id(conn), cc)
    if k not in _QUAL:
        _QUAL[k] = c5.qualifying(conn, cc) if cc in c5.SPECS else []
    return _QUAL[k]


def _divisions(conn, cc):
    k = (id(conn), cc, "all")
    if k not in _QUAL:
        _QUAL[k] = c5.divisions(conn, cc) if cc in c5.SPECS else []
    return _QUAL[k]


def _on_subject(spec, r, key):
    return key == r.get("watch_key") or key in [str(x) for x in spec.refs(r) if x]


def stance_state(conn, cc, subject, config_dir=None):
    """What has been signed for this subject: the bill's direction (and
    whether it is confirmed), the readings of its watched and tier-1 votes,
    those still waiting, and `ready`."""
    entries, bills, _ = c5.load(cc, config_dir)
    key = subject["key"]
    direction = bills.get(key)
    readings, pending = [], []
    if cc in c5.SPECS:
        spec = c5.SPECS[cc]
        for r in _qualifying(conn, cc):
            if not _on_subject(spec, r, key):
                continue
            e = entries.get(r["key"])
            st = r5.status(e)
            readings.append((r, e, st))
            if st not in ("confirmed", "unplaceable"):
                pending.append((r, e, st))
    dir_ok = c5.direction_confirmed(direction)
    return {"entries": entries, "direction": direction, "direction_ok": dir_ok,
            "readings": readings, "pending": pending,
            "stance_file": os.path.exists(c5.stance_path(cc, config_dir)),
            "ready": dir_ok and not pending}


def recorded_votes(conn, cc, subject):
    """The bill's recorded votes, oldest first: dicts of date, chamber,
    question, tally (the chamber's own labels), result."""
    if cc not in c5.SPECS:
        return [{"date": v["date"], "chamber": None, "question": v["title"], "tally": None,
                 "result": None} for v in subject.get("vote_items") or []]
    spec = c5.SPECS[cc]
    out = []
    for r in _divisions(conn, cc):
        if not any(str(x) == subject["key"] for x in spec.refs(r) if x):
            continue
        bits = []
        if r.get("yes") is not None:
            bits.append("{0} {1}".format(spec.labels[0], r["yes"]))
        if r.get("no") is not None:
            bits.append("{0} {1}".format(spec.labels[1], r["no"]))
        if r.get("abstain"):
            bits.append("{0} {1}".format("Abst.", r["abstain"]))
        out.append({"date": r["date"], "chamber": r.get("chamber"), "question": r.get("question"),
                    "tally": ", ".join(bits) or None, "result": r.get("result")})
    return out


def seats(conn, cc, chambers=None):
    """{chamber code: Counter(party)} of the sitting roster."""
    if cc not in c5.SPECS:
        return {}
    spec = c5.SPECS[cc]
    out = collections.defaultdict(collections.Counter)
    for m in c5._rows(conn, spec.roster_sql):
        if not m.get("sitting"):
            continue
        ch = str(m.get("chamber") or "")
        if chambers and ch not in chambers:
            continue
        if spec.chambers and ch not in spec.chambers:
            continue                  # a roster row of another body (the Swiss Federal Council)
        out[ch][(m.get("party") or "?").strip() or "?"] += 1
    return dict(out)


def chamber_name(ccfg, cc, code):
    if code is None or code == "":
        return ccfg["chamber"]
    names = dict(c5.SPECS[cc].chambers) if cc in c5.SPECS else {}
    names.update({str(k): v for k, v in (ccfg.get("chambers") or {}).items()})
    return names.get(str(code), ccfg["chamber"] if len(names) <= 1 else str(code))


def five_columns(conn, cc, subject, state, today):
    """The 5CA for the brief: kind 'na' (no member votes in the source),
    'wait' (nothing confirmed places anyone here) or 'placed' (rows from
    CONFIRMED readings only, src/country5ca.build_rows)."""
    if cc not in c5.SPECS:
        return {"kind": "na"}
    entries = state["entries"]
    excluded = r5.excluded_areas(ROOT)
    areas = [a for a in subject["areas"] if a not in excluded]
    chambers = sorted({str(r.get("chamber") or "") for r, _, _ in state["readings"]})
    confirmed = [e for e in entries.values() if r5.status(e) == "confirmed"]
    if not chambers:
        chambers = sorted({str(e.get("chamber") or "") for e in confirmed
                           if set(e.get("areas") or []) & set(areas)})
    for area in areas:
        for ch in chambers:
            if not any(area in (e.get("areas") or []) and str(e.get("chamber") or "") == ch
                       for e in confirmed):
                continue
            rows, listed, _ = c5.build_rows(conn, cc, ch, area, entries, today)
            signed = [e for e in listed if r5.status(e) == "confirmed"]
            placed = [r for r in rows if r["column"] != "0"]
            if not (signed and placed):
                continue
            s, u = r5.area_counts([{"division_key": str(e["key"])} for e in listed],
                                  {str(e["key"]): e for e in listed})
            tally = {c: 0 for c in r5.COLUMNS}
            for r in rows:
                if r["sitting"]:
                    tally[r["column"]] += 1
            for r in rows:
                r["target"] = "N" if r["column"] in ("++", "--") else "Y"
            return {"kind": "placed", "chamber": ch, "area": area, "rows": rows, "tally": tally,
                    "signed": s, "unsigned": u,
                    "footer": r5.readings_line(s, u, "area {0}".format(area)),
                    "targets": sum(1 for r in rows if r["sitting"] and r["target"] == "Y")}
    return {"kind": "wait"}


# --- the brief ----------------------------------------------------------------------

def _ph(P, key, **kw):
    return P["ph"].format(P[key].format(**kw) if kw else P[key])


def _num(items):
    return "\n".join("{0}. {1}".format(i + 1, x) for i, x in enumerate(items))


def build(conn, cc, subject, cfg, today, generated=None, config_dir=None):
    """Every cell of the brief, the 5CA, the readiness and the Builder tab
    notes, as one dict (render_markdown and render_csv write it out)."""
    from src.latam import AREA_LABELS
    mb = make_briefs()
    ccfg = country_cfg(cfg, cc)
    P, lang = phrases_for(cfg, cc)
    generated = generated or today
    # The dates a brief proposes (launch, delivery, urgency) count from the day
    # it was drafted, so a weekly refresh changes them only when the record
    # does (a new key date), never because a week has passed.
    today_d = datetime.date.fromisoformat(generated)
    state = stance_state(conn, cc, subject, config_dir)
    votes = recorded_votes(conn, cc, subject)
    fca = five_columns(conn, cc, subject, state, today)
    vote_chambers = sorted({str(v["chamber"]) for v in votes if v.get("chamber")})
    if fca["kind"] == "placed":
        vote_chambers = [fca["chamber"]]
    if not vote_chambers and cc == "it":
        m = re.search(r"/([CS])\.", subject["key"])          # 19/S.2057: the Senato's
        vote_chambers = [{"C": "camera", "S": "senato"}[m.group(1)]] if m else []
    chamber = chamber_name(ccfg, cc, vote_chambers[0] if len(vote_chambers) == 1 else None)
    members = ccfg["members"]
    seat_map = seats(conn, cc, set(vote_chambers) or None)
    direction = state["direction"] if state["direction_ok"] else None
    against = bool(direction) and direction["direction"] == "against"
    checklist = []

    def ph(key, cell, **kw):
        checklist.append(cell)
        return _ph(P, key, **kw)

    # dates (rulebook cells 4, 12, 13)
    nxt = subject.get("next_date")
    earliest = add_working_days(today_d, 3)
    if nxt:
        key_d = datetime.date.fromisoformat(nxt)
        delivery = add_working_days(key_d, -2)
        latest = delivery - datetime.timedelta(days=14)
        urgent = latest < earliest
        tight = not urgent and sum(1 for i in range((latest - earliest).days + 1)
                                   if (earliest + datetime.timedelta(days=i)).weekday() < 5) <= 6
        delivery_text = P["deliv_key"].format(date=delivery.isoformat(), key=nxt)
    else:
        latest, urgent, tight = None, False, False
        delivery = earliest + datetime.timedelta(days=21)
        delivery_text = P["deliv_est"].format(date=delivery.isoformat())
    launch_text = P["launch"].format(date=earliest.isoformat())

    title = subject["title"]
    stage = subject.get("stage")
    topic = mb.AREA_TOPIC.get(subject["areas"][0], "Other")
    topics = [mb.AREA_TOPIC.get(a, "Other") for a in subject["areas"]]

    # Background (cell 11): narrative, path to victory, fact sheet
    who = subject.get("sponsor") or ph("ph_sponsor", "Background / Context")
    next_text = (P["bg_next_agenda"].format(chamber=chamber, date=nxt) if nxt
                 else ph("ph_next", "Background / Context"))
    narrative = " ".join([
        P["bg_what"].format(title=title.rstrip(".")),
        P["bg_who"].format(sponsor=who, chamber=chamber),
        P["bg_stage"].format(stage=stage or ph("ph_stage", "Background / Context"),
                             date=subject.get("last_date") or "?"),
        P["bg_next"].format(next=next_text),
        P["bg_why"].format(why=ph("ph_why", "Background / Context")),
    ])
    if fca["kind"] == "placed":
        t = fca["tally"]
        fca_summary = P["fca_line"].format(a=t["++"] + t["+"], o=t["-"] + t["--"], p=t["0"],
                                           chamber=chamber_name(ccfg, cc, fca["chamber"]))
        path = "{0} {1} {2}".format(P["path_head"], fca_summary, ph("ph_routes", "Background / Context"))
    elif fca["kind"] == "na":
        fca_summary = P["fca_na"]
        path = "{0} {1}".format(P["path_head"], ph("ph_routes", "Background / Context"))
    else:
        fca_summary = P["path_wait"]
        path = "{0} {1}".format(P["path_head"], P["path_wait"])
    seat_lines = []
    for ch, cnt in sorted(seat_map.items()):
        seat_lines.append(P["seats_line"].format(
            chamber=chamber_name(ccfg, cc, ch),
            parties=", ".join("{0} {1}".format(p, n) for p, n in cnt.most_common())))
    sheet = "\n".join([
        "- {0}: {1} ({2})".format(P["fs_what"], title, subject["key"]),
        "- {0}: {1}; {2}".format(P["fs_who"], who, chamber),
        "- {0}: {1} ({2})".format(P["fs_stage"], stage or "?", subject.get("last_date") or "?"),
        "- {0}: {1}".format(P["fs_next"], nxt or P["fs_none"]),
        "- {0}: {1}{2}".format(P["fs_5ca"], fca_summary,
                               " " + " ".join(seat_lines) if seat_lines and fca["kind"] != "placed" else ""),
        "- {0}: {1}".format(P["fs_history"], ph("ph_history", "Background / Context")),
    ])
    background = "{0}\n\n{1}\n\n{2}".format(narrative, path, sheet)

    # header (form values; English, rulebook cells 1-7)
    glossary = ccfg.get("glossary") or {}
    if direction and glossary.get(subject["key"]):
        name = clip(ascii_text("{0} the {1}".format("Stop" if against else "Back",
                                                   glossary[subject["key"]])), 60)
    else:
        name = "[CAMPAIGNER: campaign name, English, max 60 characters, CitizenGO framing]"
        checklist.append("Campaign Name")
    notes = "Drafted with brief builder, see Builder tab"
    if tight and latest:
        notes += " · Launch by {0}".format(latest.isoformat())
    if not state["ready"]:
        notes += " · NOT READY: awaiting sign-off"
    header = [("Campaign Name", name), ("Campaigner", cfg["campaigner"]["email"]),
              ("Date of Submission", "(set by Zapier when the form is submitted)"),
              ("Urgency", "Urgent" if urgent else "Non-Urgent"),
              ("List", ccfg.get("list") or "[CAMPAIGNER: list]"), ("Sub-List", ""),
              ("Notes", notes), ("Approval Date", "")]

    # general information (cells 8-15)
    offline = _num([P["off_handover"].format(chamber=chamber, date=delivery.isoformat()),
                    P["off_letters"].format(members=members, date=delivery.isoformat()),
                    P["off_press"].format(chamber=chamber),
                    P["off_ads"].format(date=delivery.isoformat()),
                    P["off_vigil"].format(chamber=chamber, date=delivery.isoformat())])
    if nxt:
        purpose = "Political Impact: " + P["mp_pi"]
    else:
        purpose = ph("ph_purpose", "Main Purposes")
    general = [
        ("Type of Campaign", P["type_opp"], "draft"),
        ("Topic", topic, "fact"),
        ("Main Purposes", purpose, "draft"),
        ("Background / Context", background, "fact"),
        ("Estimated Launch date", launch_text, "draft"),
        ("Estimated date for Delivering Signatures", "{0}\n{1}:\n{2}".format(
            delivery_text, P["method"], _num([P["m1"].format(members=members), P["m2"],
                                               P["m3"].format(chamber=chamber)])), "draft"),
        ("Ideas for eventual Offline Actions", offline, "draft"),
        ("Petitions related TIM project (Targeting Inactive Members)",
         ph("ph_tim", "Petitions related TIM project"), "fact"),
    ]

    # plan phase (cells 16-22)
    addressed = P["addr_all"].format(chamber=chamber, members=members)
    if fca["kind"] == "placed":
        t = fca["tally"]
        addressed += "\n" + P["addr_split"].format(p=t["0"] + t["+"] + t["-"], a=t["++"], o=t["--"])
    addressed += "\n" + ph("ph_minister", "Who is the petition addressed to?")
    if direction:
        when = P["when_date"].format(date=nxt) if nxt else P["when_next"]
        ask = P["ask_against" if against else "ask_for"].format(bill=clip(title.rstrip("."), 90),
                                                                when=when)
        if fca["kind"] == "placed":
            ask += "\n" + P["seg"].format(ask=ask.rstrip("."))
        story_villain = ph("ph_villain", "What is happening that we are responding to?")
        story = P["story"].format(villain=story_villain, members=members, chamber=chamber)
    else:
        ask = ph("ph_ask", "What are we asking for in the petition?")
        story = ph("ph_story", "What is happening that we are responding to?")
    pressure = []
    if fca["kind"] == "placed":
        pressure.append("**{0}:** {1}".format(P["lbl_arith"], fca_summary))
    elif seat_lines:
        pressure.append("**{0}:** {1}".format(P["lbl_arith"], " ".join(seat_lines)))
    shown = [v for v in votes if v.get("tally")][-3:]
    if shown:
        pressure.append("**{0}:** {1}".format(P["lbl_votes"], "; ".join(
            "{0} '{1}' ({2})".format(v["date"], clip(v["question"], 90), v["tally"]) for v in shown)))
    pressure.append("**{0}:** {1}".format(P["lbl_whip"], ph("ph_whip", "Why would they listen to us?")))
    pressure.append("**{0}:** {1}".format(P["lbl_members"],
                                          ph("ph_members_seats", "Why would they listen to us?")))
    listen = "{0}\n{1}".format(ph("ph_lead", "Why would they listen to us?"), _num(pressure))
    if votes and (votes[-1]["date"] or "") >= (subject.get("last_date") or ""):
        v = votes[-1]
        event = P["ev_vote"].format(date=v["date"], chamber=chamber_name(ccfg, cc, v.get("chamber")),
                                    q=clip(v["question"], 120), tally=v.get("tally") or "?")
    else:
        event = P["ev_stage"].format(date=subject.get("last_date") or "?", title=clip(title, 120),
                                     stage=stage or "?")
    plan = [
        ("What is the language for this petition?", "{0}. {1}".format(
            ccfg.get("language") or "?", ccfg.get("terms") or ""), "fact"),
        ("Who will sign the emails for this petition?", cfg["campaigner"]["name"], "fact"),
        ("Who is the petition addressed to?", addressed, "draft"),
        ("What are we asking for in the petition?", ask, "draft"),
        ("Why would they listen to us?", listen, "draft"),
        ("What is happening that we are responding to?", "{0}\n{1}".format(event, story), "fact"),
        ("What is the key point of injustice that is at stake here?",
         ph("ph_injustice", "What is the key point of injustice"), "draft"),
    ]

    # prepare phase (cells 23-29)
    if nxt:
        days_left = (datetime.date.fromisoformat(nxt) - earliest).days
        dur = (P["dur_weeks"].format(n=days_left // 7) if days_left >= 14
               else P["dur_days"].format(n=max(days_left, 0)))
        mid = max(days_left // 2, 0)
        dur_mid = P["dur_weeks"].format(n=mid // 7) if mid >= 14 else P["dur_days"].format(n=mid)
        urgency = _num([P["u_launch"].format(stage=stage or "?", chamber=chamber, dur=dur),
                        P["u_mid"].format(dur=dur_mid, chamber=chamber),
                        P["u_final"].format(chamber=chamber), P["u_48"]])
    else:
        urgency = ph("ph_urgency", "Why is it urgent that we take action now?")
    sources = []
    if subject.get("url"):
        sources.append("- {0} [{1}]: {2}".format(clip(title, 160), ccfg.get("publisher") or chamber,
                                                 subject["url"]))
    sources.append("- " + ph("ph_news", "Which sources do you want to include?"))
    sources.append("- " + ph("ph_evidence", "Which sources do you want to include?"))
    image = ("Text-free 16:9 editorial photograph: the empty chamber of the {0} in soft morning "
             "light, papers on a desk in the foreground. Mood: a decision is coming. Avoid: "
             "identifiable real people, party colours or logos, anything graphic.\n"
             "Alternative 1: a close-up of a voting button panel, shallow depth of field.\n"
             "Alternative 2: the building's facade at dusk, lights on in the windows.\n"
             "Overlay: {1}").format(chamber, ph("ph_overlay", "What should the image look like?"))
    prepare = [
        ("What are some arguments supporting our point of view?",
         ph("ph_arguments", "What are some arguments"), "draft"),
        ("Why is it urgent that we take action now?", urgency, "draft"),
        ("Describe a bad outcome if we do not win this campaign:",
         ph("ph_bad", "Describe a bad outcome"), "draft"),
        ("Describe a good outcome if we do win this campaign:",
         ph("ph_good", "Describe a good outcome"), "draft"),
        ("If we are going to raise funds, what will we spend the money on?", P["funds_na"], "draft"),
        ("Which sources do you want to include? Please provide the titles plus URLs:",
         "\n".join(sources), "fact"),
        ("What should the image for this campaign look like?", image, "draft"),
    ]

    rf4 = [("RF#1", ph("ph_rf1", "RF#1 comment")),
           ("RF#2", ph("ph_rf2", "RF#2 comment")),
           ("RF#3", ph("ph_rf3", "RF#3 comment")),
           ("RF#4/1", "{0} {1}".format(P["see_good"], ph("ph_worth", "RF#4/1 comment"))),
           ("RF#4/2", P["see_bad"])]

    # banner
    if state["ready"]:
        who_signed = "; ".join(sorted({str(x) for x in [state["direction"].get("confirmed_by")]
                                       + [e.get("confirmed_by") for _, e, _ in state["readings"] if e]
                                       if x}))
        banner = [P["banner_ready"].format(who=who_signed)]
        banner_en = brief_phrases.EN["banner_ready"].format(who=who_signed)
    else:
        bits = [P["banner_nr"]]
        en = [brief_phrases.EN["banner_nr"]]
        if not state["direction_ok"]:
            k = "nr_dir" if state["direction"] else "nr_dir_none"
            bits.append(P[k])
            en.append(brief_phrases.EN[k])
        if state["pending"]:
            bits.append(P["nr_reads"].format(n=len(state["pending"])))
            en.append(brief_phrases.EN["nr_reads"].format(n=len(state["pending"])))
        bits.append(P["nr_tail"])
        en.append(brief_phrases.EN["nr_tail"])
        banner, banner_en = [" ".join(bits)], " ".join(en)

    # 5CA block
    if fca["kind"] == "na":
        fca_text = P["fca_na"]
    elif fca["kind"] == "wait":
        fca_text = (P["fca_wait"].format(n=len(state["pending"])) if state["readings"]
                    else P["fca_novote"] + " " + P["path_wait"])
    else:
        t = fca["tally"]
        fca_text = P["fca_done"].format(
            chamber=chamber_name(ccfg, cc, fca["chamber"]),
            tally="  ".join("{0} x{1}".format(c, t[c]) for c in r5.COLUMNS),
            t=fca["targets"], file=subject["slug"] + "-5ca.csv")

    builder = builder_notes(cc, subject, state, fca, votes, ccfg, lang, generated, nxt, earliest,
                            latest, delivery, urgent, tight, topics, checklist, AREA_LABELS)
    return {"subject": subject, "header": header, "general": general, "plan": plan,
            "prepare": prepare, "rf4": rf4, "fca": fca, "fca_text": fca_text,
            "banner": banner, "banner_en": banner_en, "lang": lang,
            "generated_note": P["generated"].format(date=generated), "ready": state["ready"],
            "state": state, "builder": builder, "checklist": checklist, "generated": generated}


def builder_notes(cc, subject, state, fca, votes, ccfg, lang, today, nxt, earliest, latest,
                  delivery, urgent, tight, topics, checklist, area_labels):
    """The Builder tab (rulebook: the only place the builder writes about
    itself), in English for Chris."""
    out = []
    out.append("Tier: B (open parliamentary data, the {0} store). Drafted by "
               "tools/country_briefs.py (rules and the record; no AI model).".format(cc.upper()))
    out.append("Subject: {0} `{1}`, {2}, areas {3}.".format(
        "WATCHED" if subject["watched"] else "tier 1", subject["key"], subject.get("url") or "no link",
        ", ".join("{0} ({1})".format(a, area_labels.get(a, "?")) for a in subject["areas"])))
    if len(set(topics)) > 1:
        out.append("Topic runner-up: {0}.".format(", ".join(sorted(set(topics[1:])))))
    if subject.get("watch_note"):
        out.append("Watchlist note: {0}".format(subject["watch_note"]))
    if subject.get("takeaway"):
        out.append("Store takeaway: {0}".format(subject["takeaway"]))
    if subject.get("judge_why"):
        out.append("Session judge: {0}".format(subject["judge_why"]))
    out.append("Key dates: introduced {0}; last recorded event {1}; next {2}.".format(
        subject.get("first_date") or "?", subject.get("last_date") or "?",
        "{0} (official agenda, {1} days away)".format(
            nxt, (datetime.date.fromisoformat(nxt) - datetime.date.fromisoformat(today)).days)
        if nxt else "none in the store (no Urgent proposed: news-only dates never trigger it)"))
    out.append("Launch window: earliest {0}{1}; delivery {2}{3}. Working days skip weekends only; "
               "the country's public holidays are not checked.{4}".format(
                   earliest.isoformat(), ", latest {0}".format(latest.isoformat()) if latest else "",
                   delivery.isoformat(), " (estimate)" if not nxt else "",
                   " URGENT: the key date is too close for a normal run." if urgent
                   else (" Tight window: launch by {0}.".format(latest.isoformat()) if tight else "")))
    d = state["direction"]
    if d is None:
        out.append("SIGN-OFF: no bill direction on file for `{0}`{1}. Add a `bill_directions` "
                   "line (direction with/against, why) to config/{2}_stance.yaml, then confirm it: "
                   "`python3 tools/country_5ca.py --cc {2} --confirm-direction {0} --by NAME`."
                   .format(subject["key"], "" if state["stance_file"] else " (no stance file yet)", cc))
    elif state["direction_ok"]:
        out.append("SIGN-OFF: bill direction `{0}` = {1}, confirmed by {2} on {3}.".format(
            subject["key"], d["direction"], d.get("confirmed_by"), d.get("confirmed_on")))
    else:
        out.append("SIGN-OFF: bill direction `{0}` = {1} is a DRAFT ({2}). Confirm with "
                   "`python3 tools/country_5ca.py --cc {3} --confirm-direction {0} --by NAME`; the "
                   "ask, the storytelling line and the campaign name wait for it.".format(
                       subject["key"], d.get("direction"), clip(d.get("why"), 160), cc))
    if state["readings"]:
        out.append("Readings of this bill's watched or tier-1 votes: {0} on file, {1} confirmed, "
                   "{2} waiting.".format(len(state["readings"]),
                                         len(state["readings"]) - len(state["pending"]),
                                         len(state["pending"])))
        for r, e, st in state["pending"][:12]:
            out.append("  - `{0}` {1} {2}: {3}".format(
                r["key"], r.get("date") or "?", clip(r.get("question"), 80),
                {"none": "no entry yet (drafted on Sunday's 5CA step)", "draft": "draft",
                 "unread": "needs reading"}.get(st, st)))
        if len(state["pending"]) > 12:
            out.append("  - and {0} more".format(len(state["pending"]) - 12))
        out.append("Confirm in docs/5ca-{0}-readings.md (tick, then `python3 tools/country_5ca.py "
                   "--cc {0} --sign-from-doc --by NAME`).".format(cc))
    elif cc in c5.SPECS:
        out.append("No watched or tier-1 vote on this bill in the store yet.")
    if fca["kind"] == "placed":
        out.append("5CA: {0} {1}, from CONFIRMED readings only. {2}".format(
            fca["chamber"], area_labels.get(fca["area"], fca["area"]), fca["footer"]))
    elif fca["kind"] == "na":
        out.append("5CA: none; the {0} source publishes no member votes.".format(cc.upper()))
    if votes:
        out.append("Recorded votes on the bill ({0}), newest last:".format(len(votes)))
        for v in votes[-6:]:
            out.append("  - {0} {1} '{2}' {3} {4}".format(v["date"], v.get("chamber") or "",
                                                         clip(v["question"], 90), v.get("tally") or "",
                                                         clip(v.get("result"), 40) or "").rstrip())
    out.append("Language: campaigner text in {0} ({1}), written from a phrase table without a "
               "native read (src/brief_phrases.py). Rulebook rule 6 says English: set `language: en` "
               "in config/country-briefs.yaml to switch.".format(ccfg.get("language"), lang))
    out.append("Not available to the builder: Bluebook (comparables, TIM, RF#1), the Asana campaigns "
               "calendar (launch clash check), postcode member counts, the framing glossary "
               "({0} entries), the allies and opponents registers ({1} / {2}), the hostile-outlet "
               "deny-list.".format(len(ccfg.get("glossary") or {}), len(ccfg.get("allies") or []),
                                   len(ccfg.get("opponents") or [])))
    if any(a in (7, 8) for a in subject["areas"]):
        out.append("Possible Survival: a free-speech or religious-freedom measure can reach CitizenGO "
                   "itself; check before typing it Opportunity.")
    if checklist:
        seen = []
        for c in checklist:
            if c not in seen:
                seen.append(c)
        out.append("Campaigner checklist (cells holding [CAMPAIGNER: ...]): " + "; ".join(seen) + ".")
    return out


# --- writing ------------------------------------------------------------------------

def render_markdown(b, changelog):
    s = b["subject"]
    lines = ["# Campaigns Brief (DRAFT): {0}".format(s["title"]), ""]
    for x in b["banner"]:
        lines += ["> **{0}**".format(x), ""]
    if b["lang"] != "en":
        lines += ["> (EN) {0}".format(b["banner_en"]), ""]
    lines += ["> {0}".format(b["generated_note"]), ""]
    lines += ["## Header (proposed values for the Asana form)", "", "| Field | Value |", "|---|---|"]
    for k, v in b["header"]:
        lines.append("| {0} | {1} |".format(k, str(v).replace("|", "/")))
    lines.append("")
    for head, rows in (("General information", b["general"]), ("Plan phase prompts", b["plan"]),
                       ("Prepare phase prompts", b["prepare"])):
        lines += ["## " + head, ""]
        for label, value, owner in rows:
            lines += ["### {0} {1}".format(TAGS[owner], label), "", value, ""]
    lines += ["## Red Fox Four (scores are the campaigner's call)", "",
              "| # | Question | Score (-10..+10) | Comment |", "|---|---|---|---|"]
    for (code, q), (_, comment) in zip(make_briefs().RF4, b["rf4"]):
        lines.append("| {0} | {1} | | {2} |".format(code, q, comment.replace("\n", " ")))
    lines += ["| | TOTAL IF WE WIN / TOTAL IF WE LOSE | | |", ""]
    lines += ["## Five Column Analysis", "", b["fca_text"], ""]
    lines += ["## Evaluate (after the campaign) " + TAGS["blank"], "",
              "Left blank at build time (rulebook cell 35).", ""]
    lines += ["## Builder tab", ""]
    lines += ["- " + x if not x.startswith("  ") else x for x in b["builder"]]
    lines += ["", "Changelog:", ""] + ["- " + x for x in changelog] + [""]
    return "\n".join(lines)


def render_csv(b, changelog):
    """The Default Brief tab, row for row as tools/make_briefs.py lays it out,
    then the Builder tab."""
    mb = make_briefs()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([k for k, _ in b["header"]])
    w.writerow([v for _, v in b["header"]])
    for head, rows in (("GENERAL INFORMATION", b["general"]),
                       ("PROMPTS FOR AI - PLAN PHASE", b["plan"]),
                       ("PROMPTS FOR AI - PREPARE PHASE", b["prepare"])):
        w.writerow([head])
        for label, value, _ in rows:
            w.writerow([label, value])
    w.writerow(["RED FOX FOUR"])
    w.writerow(["PLAN STAGE", "", "", "", "EVALUATE STAGE", "", ""])
    w.writerow(["#", "Question", "Scoring \n(-10 to +10)", "Comments",
                "Scoring\n(-10 to +10)", "Delta", "Comments"])
    for (code, q), (_, comment) in zip(mb.RF4, b["rf4"]):
        w.writerow([code, q, "", comment, "", "", ""])
    w.writerow(["TOTAL IF WE WIN", "", "0", "", "0", "0", ""])
    w.writerow(["TOTAL IF WE LOSE", "", "0", "", "0", "0", ""])
    w.writerow(["FIVE COLUMNS ANALYSIS", b["fca_text"]])
    w.writerow(["EVALUATE DASHBOARD"])
    for label in mb.EVALUATE_ROWS:
        w.writerow([label, ""])
    w.writerow(["BUILDER TAB"])
    for x in b["builder"]:
        w.writerow([x.strip()])
    for x in changelog:
        w.writerow(["Changelog: " + x])
    return buf.getvalue()


def render_5ca_csv(b):
    """The Five Column Analysis tab (rulebook cell 36): Section 1 Targets,
    Section 2 All members, the TOTAL over Section 2. Only for a 5CA placed
    from CONFIRMED readings; None otherwise."""
    fca = b["fca"]
    if fca["kind"] != "placed":
        return None
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["FIVE COLUMNS ANALYSIS (ONLY IF APPROPRIATE)"])
    w.writerow(["PLAN STAGE", "", "", "", "", "", "", "", "", "EVALUATE STAGE", ""])
    head = ["Decision-Maker", "# Seats", '"++"', '"+"', '"0"', '"-"', '"--"', "Target (Y/N)",
            "Comments", "Vote (Y/N)", "Comments"]

    def row(r):
        marks = ["1" if c == r["column"] else "0" for c in r5.COLUMNS]
        comment = " | ".join(r["comments"]) if r["n_events"] else "No recorded position"
        return [r["decision_maker"], "1"] + marks + [r["target"], comment, "", ""]

    rows = sorted((r for r in fca["rows"] if r["sitting"]), key=lambda r: r["decision_maker"])
    w.writerow(["SECTION 1: TARGETS"])
    w.writerow(head)
    for r in rows:
        if r["target"] == "Y":
            w.writerow(row(r))
    w.writerow([])
    w.writerow(["SECTION 2: ALL MEMBERS"])
    w.writerow(head)
    for r in rows:
        w.writerow(row(r))
    t = fca["tally"]
    w.writerow(["TOTAL", str(len(rows))] + [str(t[c]) for c in r5.COLUMNS] + ["", "", "", ""])
    w.writerow([fca["footer"] + " Vote Y/N, after the vote, is for or against the BILL, not us."])
    return buf.getvalue()


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ledger_path(cc, ledger_dir=None):
    return os.path.join(ledger_dir or LEDGER_DIR, "{0}.json".format(cc))


def load_ledger(cc, ledger_dir=None):
    path = ledger_path(cc, ledger_dir)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as h:
        return json.load(h)


def save_ledger(cc, ledger, ledger_dir=None):
    path = ledger_path(cc, ledger_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as h:
        json.dump(ledger, h, ensure_ascii=False, indent=1, sort_keys=True)
        h.write("\n")


def write_files(b, out_dir, changelog):
    """Write the brief's files; returns (md text, paths)."""
    slug = b["subject"]["slug"]
    os.makedirs(out_dir, exist_ok=True)
    md = render_markdown(b, changelog)
    paths = {"md": os.path.join(out_dir, slug + ".md"), "csv": os.path.join(out_dir, slug + ".csv"),
             "5ca": os.path.join(out_dir, slug + "-5ca.csv")}
    with open(paths["md"], "w", encoding="utf-8") as h:
        h.write(md)
    with open(paths["csv"], "w", encoding="utf-8", newline="") as h:
        h.write(render_csv(b, changelog))
    fca = render_5ca_csv(b)
    if fca:
        with open(paths["5ca"], "w", encoding="utf-8", newline="") as h:
            h.write(fca)
    elif os.path.exists(paths["5ca"]):
        os.remove(paths["5ca"])          # a 5CA no longer confirmed must not linger
    return md, paths


def _content_key(b):
    """What decides whether a refresh changed anything: the brief without its
    changelog and without the date it was generated."""
    return sha(render_markdown(dict(b, generated_note=""), []))


def brief_log_status(conn, slug):
    try:
        row = conn.execute("SELECT status FROM brief_log WHERE slug = ?", (slug,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


def log_brief(conn, slug, title, today, path, ready):
    """brief_log, as the German briefs: one row per slug. Our own statuses
    only (`not-ready`, `draft`); a status a person set is never changed."""
    mb = make_briefs()
    mb.ensure_log(conn)
    st = brief_log_status(conn, slug)
    want = STATUS_READY if ready else STATUS_NOT_READY
    rel = os.path.relpath(path, ROOT) if path.startswith(ROOT) else path
    if st is None:
        conn.execute("INSERT INTO brief_log (slug, subject, generated_at, path, status) "
                     "VALUES (?,?,?,?,?)", (slug, title, today, rel, want))
    elif st in OWN_STATUSES and st != want:
        conn.execute("UPDATE brief_log SET status = ? WHERE slug = ?", (want, slug))
    conn.commit()


def run(conn, cc, cfg, today, out_dir=None, ledger_dir=None, config_dir=None, recent_days=RECENT_DAYS,
        max_new=MAX_NEW, force=(), subject_keys=(), write_log=True, log=print):
    """One country's step: new briefs for new subjects, refreshes for the
    unedited ones. Returns a counts dict."""
    out_dir = out_dir or BRIEFS_DIR
    _QUAL.clear()
    ledger = load_ledger(cc, ledger_dir)
    subs = subjects(conn, cc, today, recent_days, config_dir)
    by_slug = {s["slug"]: s for s in subs}
    by_key = {s["key"]: s for s in subs}
    counts = {"subjects": len(subs), "new": 0, "refreshed": 0, "ready": 0, "now_ready": 0,
              "edited": 0, "waiting": 0}
    forced = set()
    for f in force:
        s = by_slug.get(f) or by_key.get(f)
        if s is None:
            hits = [x for x in by_slug if x.startswith(f)]
            s = by_slug[hits[0]] if len(hits) == 1 else None
        if s is None:
            log("  {0}: --force {1!r} matches no current subject".format(cc, f))
            continue
        forced.add(s["slug"])
    wanted = {by_key[k]["slug"] for k in subject_keys if k in by_key}
    for k in subject_keys:
        if k not in by_key:
            log("  {0}: --subject {1!r} is not a live watched or tier-1 bill in the store".format(cc, k))
    fresh = [s for s in subs if s["slug"] not in ledger and (s["recent"] or s["slug"] in wanted)
             and brief_log_status(conn, s["slug"]) != "rejected"]
    counts["waiting"] = max(len(fresh) - max_new, 0)
    todo = [(s, "new") for s in fresh[:max_new]]
    todo += [(by_slug[slug], "refresh") for slug in ledger if slug in by_slug]
    for s, why in todo:
        slug = s["slug"]
        if brief_log_status(conn, slug) == "rejected":
            continue
        rec = ledger.get(slug)
        b = build(conn, cc, s, cfg, today, generated=(rec or {}).get("generated"),
                  config_dir=config_dir)
        if b["ready"]:
            counts["ready"] += 1
        key = _content_key(b)
        md_path = os.path.join(out_dir, slug + ".md")
        if rec is not None:
            on_disk = None
            if os.path.exists(md_path):
                with open(md_path, encoding="utf-8") as h:
                    on_disk = sha(h.read())
            if on_disk != rec.get("sha") and slug not in forced:
                counts["edited"] += 1
                log("  {0}: edited by a person since it was written; left alone".format(slug))
                continue
            if key == rec.get("content") and slug not in forced:
                continue
            changelog = list(rec.get("changelog") or [])
            change = "refreshed by the builder" if slug not in forced else "rewritten (--force)"
            if b["ready"] and not rec.get("ready"):
                change += "; now READY (stances confirmed)"
                counts["now_ready"] += 1
            elif rec.get("ready") and not b["ready"]:
                change += "; NOT READY again (a confirmation was withdrawn)"
            changelog.append("{0} tools/country_briefs.py {1}".format(today, change))
            counts["refreshed"] += 1
        else:
            changelog = ["{0} tools/country_briefs.py drafted every cell".format(today)]
            counts["new"] += 1
        md, paths = write_files(b, out_dir, changelog)
        ledger[slug] = {"key": s["key"], "title": s["title"], "generated": b["generated"],
                        "ready": b["ready"], "sha": sha(md), "content": key, "changelog": changelog}
        if write_log:
            log_brief(conn, slug, s["title"], today, paths["md"], b["ready"])
        log("  {0} {1} {2}".format("new  " if why == "new" else "upd  ",
                                   "READY    " if b["ready"] else "not ready", slug))
    save_ledger(cc, ledger, ledger_dir)
    return counts


_MB = []


def make_briefs():
    """tools/make_briefs.py, for its RF4 questions, Evaluate rows, Topic map
    and brief_log; loaded by path because tools/ is not a package."""
    if not _MB:
        spec = importlib.util.spec_from_file_location(
            "make_briefs", os.path.join(ROOT, "tools", "make_briefs.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MB.append(mod)
    return _MB[0]
