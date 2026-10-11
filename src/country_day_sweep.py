"""The daily sweep for the new country editions: a same-day alert for what is
NEW on our ground, not only votes.

Parity with the UK day sweep (tools/day_sweep.py, src/daysweep.py) and the
EU's (tools/eu_day_sweep.py), and with the Latam instant alerts
(tools/latam_alerts.py), for the countries whose sources publish new items
the same day cheaply and openly: the Netherlands, Poland, Switzerland,
Brazil, Italy, Austria, France (its agenda) and Spain (from 23 December
2026). See src/day_sweep_sources.py for what each reads and what it costs.

ONE DAILY JOB, NOT TWO. The sweep is a step of the daily vote-briefs job
(jobs/vote-briefs-daily.sh, tools/country_vote_briefs.py --daily): its
readers write into the same throwaway store, after the vote readers, and
the run sends ONE combined DM to Chris (the vote briefs first, then the new
items), and nothing at all when there is nothing.

WHAT IS SWEPT: the kinds "new" (bills, motions, initiatives, amendments),
"question" (written and oral questions, interpellations, requests for
information) and "agenda" (a point newly on the agenda of the next
AGENDA_DAYS), from the edition's own reader (src/country_edition.gather with
the country's adapter, so its noise filters and mute list apply, plus the
country's chamber questions and agenda) and, where the edition does not
carry a kind the sweep alerts, the reader's extra items (the Dutch motions;
NL3 keeps the Dutch edition to votes, speeches and questions).

WHAT ALERTS, as the vote briefs (src/country_vote_brief.qualifies): an item
that is WATCHED, or TIER 1 with the minimum evidence the country's noise
rules ask for an alert (config/edition-noise-<cc>.yaml `alert`, by kind
where set; src/noise.alert_reason). Where the free session judge has
scored a tier-1 item it must have scored 2 or 3. (The daily job pulls no
store, so the judge's scores are not at hand there and an item is judged by
its evidence; the gate is kept so a scored item never alerts below 2.)

NEVER TWICE, NEVER WHAT CHRIS HAS SEEN:

  * data/day-sweep/<cc>.json, the ledger: an item is keyed on its country,
    kind and key (an agenda point on its bill or title and its date, so a
    point the source renumbers does not alert again, and a point moved to
    another day does); the first pass for a country seeds silently, as the
    vote briefs and the Latam alerts do.
  * the weekly editions: an item whose key is in one of the country's
    editions of the last EDITION_DAYS (editions/<cc>-monitor-<date>.md) is
    not alerted.
  * the vote briefs of the same run: an item whose key is a vote's key, its
    watched bill, its group or a bill it names is left to the vote brief.

Facts of the record only: the title is the source's own, verbatim and in
italics, the English around it ours; never a verdict. British spelling, no
em dashes. The DM goes to Chris alone (src/country_vote_brief.send).

Every item alerted in a run is also written to data/briefs/day-sweep-<date>.md
(the DM shows at most MAX_DM_ITEMS).
"""

from __future__ import annotations

import dataclasses
import datetime
import glob
import json
import os
import re
import time

from src import country_edition as ce
from src import country_vote_brief as cvb
from src import day_sweep_sources as sources
from src import noise as noise_mod
from src import vote_brief

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_DIR = os.path.join(ROOT, "data", "day-sweep")
BRIEFS = cvb.BRIEFS
SWEEP_KINDS = ("new", "question", "agenda")
EDITION_DAYS = 21
KEEP_DAYS = 400
MAX_DM_ITEMS = 20
SWEEP_RETRIES = 1     # at most one retry a request: the weekly is the backstop
KIND_LABEL = {"new": "New", "question": "Question", "agenda": "On the agenda"}
# Latam countries read through the Latam alerts' path, de-duplicated against
# its ledger (data/latam-alerts/<cc>.json) both ways: what tools/latam_alerts.py
# sent is not alerted here, and what this run alerts is recorded there, so
# the alert step after the weekly collection does not send it again.
LATAM = sources.LATAM
LATAM_NOT_SWEPT = ("moved",)
LATAM_LEDGER_DIR = None     # data/latam-alerts (src/latam.LEDGER_DIR) when None
HEAD = re.compile(r"^\s*- \*\*[^*]+\*\* · (.+?) · ", re.M)


# --- what qualifies ----------------------------------------------------------------

def qualifies(it, nz, config_dir=None):
    """Watched, or tier 1 with the minimum evidence; a tier-1 item the session
    judge has read, only at 2 or 3. Muted items never."""
    if it["kind"] not in SWEEP_KINDS or nz.muted(it, config_dir):
        return False
    if it.get("watched"):
        return True
    if it.get("tier") != 1:
        return False
    if it.get("judge") is not None:
        return it["judge"] >= 2
    return nz.alert_reason(it, config_dir) is not None


def why(it, nz, config_dir=None):
    if it.get("watched"):
        return "watched"
    if it.get("judge") is not None:
        return "tier 1, judge {0}/3".format(it["judge"])
    return nz.alert_reason(it, config_dir) or "tier 1"


def sweep_country(cc, reader=None):
    """The adapter, widened: every kind (the sweep picks its own), the reader's
    extra items, and the agenda ahead of `today` (set on the items fn)."""
    country = ce.adapter(cc)
    reader = reader or sources.READERS.get(cc) or sources.Reader

    def items(conn, since, until, wl):
        got = list(country.items(conn, since, until, wl) or [])
        if reader.extra_items:
            got += reader.extra_items(conn, since, until, wl)
        if reader.AGENDA:
            from src import agenda
            got += agenda.ahead_items(conn, cc, until, wl, sources.AGENDA_DAYS)
        return got

    return country, dataclasses.replace(country, kinds=None, items=items)


def latam_candidates(conn, cc, since, until, config_dir=None):
    """[(item, why)] for a Latam country: the Latam alerts' own reader and rule
    (src/latam.country_items, tools/latam_alerts.qualifies: watched, or tier 1
    with config/latam-noise.yaml's minimum evidence, or judged 2 or 3), so the
    daily pass alerts exactly what the alert step after the weekly collection
    would (a register re-stamp, Bolivia's "updated", only when watched).
    Stage moves stay with that step: the scratch store holds no earlier
    status to move from."""
    from src import latam, latam_noise
    import latam_alerts
    out, briefs = [], {}
    for it in latam.country_items(conn, cc, since, until, None, config_dir):
        if it["kind"] in LATAM_NOT_SWEPT or not latam_alerts.qualifies(it, config_dir):
            continue
        if latam_alerts.briefed(it, briefs):      # a vote its brief has spoken for
            continue
        reason = "watched" if it.get("watched") else (
            "tier 1, judge {0}/3".format(it["judge"]) if it.get("judge") is not None
            else latam_noise.alert_reason(it, config_dir) or "tier 1")
        bits = ([it["status"]] if it.get("status") else []) + list(it.get("lines") or [])[:1]
        it = dict(it, takeaway="; ".join(latam.clean(b) for b in bits if b) or None,
                  latam_key=latam_alerts.alert_key(it))
        out.append((it, reason))
    return out


def candidates(conn, cc, since, until, config_dir=None, reader=None):
    """[(item, why)] for the country's new items in the window that qualify."""
    if cc in LATAM:
        return latam_candidates(conn, cc, since, until, config_dir)
    country, wide = sweep_country(cc, reader)
    nz = ce.noise_for(country)
    got = ce.gather(conn, wide, since, until, config_dir)
    return [(it, why(it, nz, config_dir)) for it in got if qualifies(it, nz, config_dir)]


# --- never twice -------------------------------------------------------------------

def sweep_id(it):
    if it.get("latam_key"):
        return it["latam_key"]
    if it["kind"] == "agenda":
        anchor = it.get("watch_key") or noise_mod.fold(it.get("title") or it["key"])[:80]
        return "{0}|agenda|{1}|{2}".format(it["cc"], anchor, it["date"])
    return "{0}|{1}|{2}".format(it["cc"], it["kind"], it["key"])


def ledger_path(cc, directory=None):
    return os.path.join(directory or LEDGER_DIR, "{0}.json".format(cc))


def load(cc, directory=None):
    path = ledger_path(cc, directory)
    got = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh) or {}
    got.setdefault("cc", cc)
    got.setdefault("seeded", None)
    got.setdefault("read", None)
    got.setdefault("sent", {})
    return got


def save(ledger, today, directory=None):
    cut = (datetime.date.fromisoformat(today) - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    ledger["sent"] = {k: v for k, v in ledger["sent"].items() if v >= cut}
    path = ledger_path(ledger["cc"], directory)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def edition_keys(cc, today, days=EDITION_DAYS, directory=None):
    """The item keys (as the edition clips them) in the country's editions of
    the last `days`, samples left out."""
    cut = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()
    keys = set()
    for path in glob.glob(os.path.join(directory or ce.EDITIONS, "{0}-monitor-*.md".format(cc))):
        stamp = os.path.basename(path)[len(cc) + len("-monitor-"):-3]
        if not (cut <= stamp <= today):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if ce.SAMPLE_MARK in text:
            continue
        keys.update(m.strip() for m in HEAD.findall(text))
    return keys


def vote_keys(votes):
    """Every key a vote brief of this run speaks for: the vote's own, its
    division, its watched bill, its group and the bills it names."""
    out = set()
    for it in votes:
        for k in (it.get("key"), it.get("division"), it.get("watch_key"),
                  it.get("group") if isinstance(it.get("group"), str) else None):
            if k:
                out.add(str(k))
        out.update(str(r) for r in it.get("refs") or [] if isinstance(r, str))
    return out


def latam_load(cc, directory=None):
    import latam_alerts
    return latam_alerts.load(cc, directory or LATAM_LEDGER_DIR)


def latam_record(ledger, picked, today, directory=None):
    """Record what this run alerted in the Latam alerts' ledger, so the alert
    step after the country's weekly collection does not send it again. One
    file per country; the Mini's run queue keeps the two jobs apart."""
    import latam_alerts
    for it, _r in picked:
        ledger["sent"][it["latam_key"]] = today
        ledger.get("held", {}).pop(it["latam_key"], None)
    latam_alerts.save(ledger, today, directory or LATAM_LEDGER_DIR)


# --- rendering ---------------------------------------------------------------------

def country_name(cc):
    if cc in LATAM:
        from src import latam
        return latam.NAMES.get(cc, cc)
    return cvb.country_name(cc)


def flag(cc):
    return ":flag-{0}:".format(cc) if cc in LATAM else cvb.flag(cc)


def label(it):
    if it["cc"] in LATAM:
        from src import latam
        return latam.KINDS.get(it["kind"], it["kind"])
    return KIND_LABEL.get(it["kind"], it["kind"])


def entry_lines(it, reason):
    when = ce.short_date(it["date"])
    head = "• *{0}* {1}, {2}{3}: _{4}_".format(
        label(it), ce.clip(it["key"], 40),
        "sitting " if it["kind"] == "agenda" else "", when,
        ce.clip(it["title"], 220) or "(no title published)")
    bits = []
    if it.get("takeaway"):
        bits.append(ce.sentence(ce.clip(it["takeaway"], 240)))
    bits.append("Why: {0}; {1}.".format(reason, ce.area_text(it["areas"]) or "watched"))
    if it.get("own") is False:
        bits.append("Its areas come from the bill it names.")
    out = [head, "  " + " ".join(bits)]
    if it.get("url"):
        out.append("  " + it["url"])
    return out


def country_block(cc, picked):
    head = "{0} *{1}: {2} new on our ground*".format(
        flag(cc), country_name(cc), len(picked))
    lines = [head]
    for it, reason in picked:
        lines += entry_lines(it, reason)
    return "\n".join(lines)


def report_markdown(today, blocks, generated=None, sample=False):
    out = ["# {0}Daily sweep, {1}".format("SAMPLE (never sent). " if sample else "",
                                          ce.long_date(today)), "",
           "*New items on our ground: watched, or tier 1 with the minimum evidence. "
           "Generated {0}. Titles are the source's own; no verdicts "
           "(src/country_day_sweep.py).*".format(
               generated or datetime.datetime.now().isoformat(timespec="minutes")), ""]
    for cc, picked in blocks:
        out.append("## {0}".format(country_name(cc)))
        out.append("")
        for it, reason in picked:
            out.append("- **{0}** · {1} · {2} · {3}{4}".format(
                label(it), it["key"], ce.short_date(it["date"]),
                reason, " · tier 1" if it.get("tier") == 1 else ""))
            out.append("  *{0}*".format(ce.clip(it["title"], 400) or "(no title published)"))
            if it.get("takeaway"):
                out.append("  " + ce.sentence(it["takeaway"]))
            out.append("  Areas: {0}.".format(ce.area_text(it["areas"]) or "watched"))
            if it.get("url"):
                out.append("  [Source]({0})".format(it["url"]))
        out.append("")
    return vote_brief.house_style("\n".join(out))


def report_path(out_dir, today):
    base = os.path.join(out_dir, "day-sweep-{0}".format(today))
    path, n = base + ".md", 2
    while os.path.exists(path):
        path = "{0}-{1}.md".format(base, n)
        n += 1
    return path


# --- the run -----------------------------------------------------------------------

def collect(conn, client, since, today, countries=sources.SWEEP, log=print, directory=None):
    """Fill the scratch store from the sweep readers. Returns (countries read,
    {cc: NoArchive client} for the readers that archive only on a hit)."""
    read, held = [], {}
    for cc in countries:
        reader = sources.READERS[cc]
        if reader.ACTIVE_FROM and today < reader.ACTIVE_FROM:
            log("{0}: not swept before {1}".format(cc, reader.ACTIVE_FROM))
            continue
        if reader.ONCE_A_DAY and load(cc, directory)["read"] == today:
            log("{0}: already swept today".format(cc))
            continue
        c = sources.NoArchive(client) if reader.ARCHIVE_ON_HIT else client
        ok, started = False, time.monotonic()
        try:
            with sources.retries(c, SWEEP_RETRIES):
                reader.collect(conn, c, since, today, log=log)
            ok = True
        except Exception as exc:          # noqa: BLE001 - one reader must not cost the others
            conn.rollback()
            log("  [gap] {0}: the sweep reader failed: {1}".format(cc, str(exc)[:160]))
        if reader.AGENDA:
            try:
                _pts, _ours, gaps = sources.agenda(conn, cc, c, today, log=log)
                ok = ok or not gaps
            except Exception as exc:      # noqa: BLE001
                conn.rollback()
                log("  [gap] {0}: the agenda was not read: {1}".format(cc, str(exc)[:160]))
        log("{0}: swept in {1:.0f} s".format(cc, time.monotonic() - started))
        if ok:
            read.append(cc)
            if reader.ARCHIVE_ON_HIT:
                held[cc] = c
    return read, held


def run(conn, countries, since, until, today=None, out_dir=BRIEFS, record=True, directory=None,
        config_dir=None, skip_keys=(), generated=None, log=print, sample=False,
        editions_dir=None, latam_dir=None):
    """Plan every new qualifying item of `countries` in (since, until] (agenda
    points ahead of `until`). Returns (DM text or None, [(cc, [(item, why)])],
    report path or None). Nothing is sent here: tools/country_vote_briefs.py
    joins the text to the vote briefs' and sends ONE DM. With `record`, the
    ledgers are written (the first pass for a country seeds silently)."""
    today = today or until
    skip = set(skip_keys or ())
    blocks = []
    for cc in countries:
        ledger = load(cc, directory)
        try:
            got = candidates(conn, cc, since, until, config_dir)
        except Exception as exc:          # noqa: BLE001
            log("  [gap] {0}: the sweep's reader failed: {1}".format(cc, str(exc)[:160]))
            continue
        seen_in = edition_keys(cc, today, directory=editions_dir)
        latam_ledger = latam_load(cc, latam_dir) if cc in LATAM else None
        picked, ids = [], set()
        for it, reason in got:
            sid = sweep_id(it)
            if sid in ledger["sent"] or sid in ids:
                continue
            ids.add(sid)
            if latam_ledger is not None and sid in latam_ledger["sent"]:
                log("  {0}: {1} already sent by the Latam alerts".format(cc, it["key"]))
                ledger["sent"][sid] = today
                continue
            if ce.clip(it["key"], 60) in seen_in:
                log("  {0}: {1} already in an edition".format(cc, it["key"]))
                ledger["sent"][sid] = today
                continue
            if {it["key"], it.get("watch_key")} & skip:
                log("  {0}: {1} left to its vote brief".format(cc, it["key"]))
                ledger["sent"][sid] = today
                continue
            picked.append((it, reason))
        if not ledger["seeded"]:
            for it, _r in picked:
                ledger["sent"][sweep_id(it)] = today
            ledger["seeded"] = today
            log("{0}: sweep seeded with {1} item(s); nothing alerted on a first pass".format(
                cc, len(picked)))
            picked = []
        else:
            for it, _r in picked:
                ledger["sent"][sweep_id(it)] = today
            log("{0}: {1} new item(s) on our ground to alert".format(cc, len(picked)))
        ledger["read"] = today
        if record:
            save(ledger, today, directory)
            if latam_ledger is not None and picked:
                latam_record(latam_ledger, picked, today, latam_dir)
        if picked:
            picked.sort(key=lambda p: (p[0]["kind"] != "new", not p[0].get("watched"),
                                       p[0]["kind"], p[0]["date"], p[0]["key"]))
            blocks.append((cc, picked))
    if not blocks:
        return None, [], None
    os.makedirs(out_dir, exist_ok=True)
    path = report_path(out_dir, today)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report_markdown(today, blocks, generated, sample))
    total = sum(len(p) for _cc, p in blocks)
    shown, texts = 0, []
    for cc, picked in blocks:
        room = MAX_DM_ITEMS - shown
        if room <= 0:
            break
        texts.append(country_block(cc, picked[:room]))
        shown += min(room, len(picked))
    rel = "data/briefs/" + os.path.basename(path)
    tail = "All {0} in {1}: https://github.com/{2}/blob/main/{1}".format(total, rel, cvb.REPO)
    if total > shown:
        tail = "_and {0} more_. ".format(total - shown) + tail
    text = "\n\n".join(texts) + "\n" + tail
    return vote_brief.house_style(text), blocks, path


def header(n_briefs, n_items):
    """The combined DM's first line."""
    bits = []
    if n_briefs:
        bits.append("{0} vote brief{1}".format(n_briefs, "" if n_briefs == 1 else "s"))
    if n_items:
        bits.append("{0} new item{1} on our ground".format(n_items, "" if n_items == 1 else "s"))
    return ":mag: *Daily watch: {0}*".format(", ".join(bits))
