"""Same-day vote briefs for the new country editions: the shared half.

Handover item 1 (docs/country-parity-handover.md, 10 October 2026): parity
with the UK division watch and the US, Irish and Australian briefs
(src/vote_brief.py) for every new country whose collector stores votes:

  * own editions: Italy, Switzerland, France, the Netherlands, Belgium,
    Poland, Croatia, Slovakia, Spain, Brazil, Argentina (Senate), Mexico,
    and Austria and Portugal, whose member positions are DERIVED from the
    group and labelled so (X5);
  * the Latam monitor's countries with member votes: Chile, Peru, Ecuador,
    the Dominican Republic, El Salvador and Guatemala.

WHAT IS BRIEFED: a recorded vote that is WATCHED (its bill is on the
country's watchlist), or TIER 1 with the minimum evidence the country's
noise rules ask for an alert (config/edition-noise-<cc>.yaml, or
config/latam-noise.yaml; src/noise.py). Where the free session judge has
read a tier-1 vote it must have scored 2 or 3, as for the Latam alerts.
A vote the edition's noise filters leave out (procedural votes, muted
items) is never briefed. The evidence is read on the vote's own title AND
the title of the bill it is on: 'Votazione finale' says nothing, its bill
does, and some stores keep no tier on a vote whose areas are its bill's
(Italy, Belgium), so a vote on a bill whose title carries a tier-1 term
counts as tier 1.

THE SAME ITEMS AS THE EDITION. Votes come from the edition's own reader
(src/country_edition.gather with the country's adapter, src/editions/<cc>.py)
or the Latam reader (src/latam.country_items), so the brief, the weekly
edition and the Latam monitor never disagree about what a vote is. The
adapters hand over every member position they read and the FULL list of
members who voted against their group's majority (country_edition.item's
`positions`, `rebels`, `rebels_note`); for the Latam countries this module
reads the positions itself (LATAM_POSITIONS). Croatia, Chile and Guatemala
name nobody against their party until party history is sourced (X6);
Austria and Portugal derive member positions from the group (X5), and
Portugal names only the deputies its record names as voting apart.

TWO WAYS IN, ONE LEDGER:

  * after each country's weekly (or fortnightly) collection, from the store
    (tools/country_vote_briefs.py --country <cc>, a step in jobs/<cc>-weekly.sh);
  * once a day for the countries whose source publishes votes the same day
    cheaply and openly (tools/country_vote_briefs.py --daily, ONE Mini job,
    jobs/vote-briefs-daily.sh): the collector's own parsing and
    classification run into a throwaway store holding only the last few
    days (src/vote_brief_sources.py), and the same reader runs over it.

Both record what they briefed in data/vote-briefs/<cc>.json (a vote is keyed
on country, item key, date and its title), so a vote briefed by the daily
job is never briefed again by the weekly one, nor by a GitHub backup. The
first pass for a country seeds the ledger silently, as tools/latam_alerts.py
does, so switching a country on never floods Chris with its backlog.

A VOTE WAITS FOR ITS POSITIONS. Where the source publishes positions after
the result (the Tweede Kamer, up to a day later; Openpolis for the Camera),
a vote whose positions are not read yet is held until it is HOLD_DAYS old
and then briefed without them, saying so ("held" in the ledger lists them).

THE RULES (src/vote_brief.py's, unchanged): facts of the record only, never
a verdict; the result is the record's own word; which side was CitizenGO's
is a signed human reading in config/<cc>_stance.yaml, and the brief gives
only that reading's STATUS; one DM per run, to Chris alone, whatever the
environment says; British spelling, no em dashes.

Briefs are written to data/briefs/<cc>-votes-<date>-<key>.md: one per bill
(or vote group) per day, its decisive vote first.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re

from src import country_edition as ce
from src import latam, vote_brief

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_DIR = os.path.join(ROOT, "data", "vote-briefs")
BRIEFS = vote_brief.BRIEFS
CHRIS = vote_brief.CHRISTOPHER
REPO = vote_brief.REPO

EDITIONS = ("it", "ch", "fr", "nl", "be", "pl", "hr", "sk", "es", "br", "ar", "mx", "at", "pt")
LATAM = ("cl", "pe", "ec", "do", "sv", "gt")
COUNTRIES = EDITIONS + LATAM
# Countries whose positions can arrive after the result: a vote without them
# is held (HOLD_DAYS) rather than briefed bare.
POSITIONS_LATER = ("it", "ch", "fr", "nl", "be", "pl", "sk", "es", "br", "ar", "mx")
HOLD_DAYS = 2
KEEP_DAYS = 400
MAX_DM_BRIEFS = 8
MAX_DM_VOTES = 3
MAX_DM_REBELS = 12

LATAM_CHAMBER = {"cl": "Congreso Nacional", "pe": "Congreso", "ec": "Asamblea Nacional",
                 "do": "Cámara de Diputados", "sv": "Asamblea Legislativa", "gt": "Congreso"}
X6 = "No member is named against their party until party history is sourced (X6)."

# Latam: (name, group, position) per vote, read from the store. `None` for
# the group means the source records none at the vote.
LATAM_POSITIONS = {
    "cl": ("SELECT COALESCE(m.name, v.member_key), v.party, v.position FROM cl_votes v "
           "LEFT JOIN cl_members m USING (member_key) WHERE v.division_key=?", X6),
    "pe": ("SELECT name_raw, bancada, position FROM pe_votes WHERE division_key=?", None),
    "ec": ("SELECT v.name, COALESCE(ro.party, ro.party_slug), v.position FROM ec_votes v "
           "LEFT JOIN ec_roster ro ON ro.name_key = v.name_key WHERE v.division_key=?", None),
    "do": ("SELECT COALESCE(name, member_key), party, position FROM do_votes WHERE division_key=?",
           None),
    "sv": ("SELECT name, party, position FROM sv_votes WHERE division_key=?", None),
    "gt": ("SELECT v.name, m.bloque, v.position FROM gt_votes v LEFT JOIN gt_members m "
           "ON m.name_key = v.name_key WHERE v.division_key=?", X6),
}
LATAM_CAVEAT = {"ec": "Party as the Asamblea's roster stands, not at the vote.",
                "gt": "Bloc as the Congreso's roster stands (GT4: current bloc only)."}
# Members with no group line to break: independents and mixed groups, as
# each source labels them (the adapters skip some already; the rest here).
INDEPENDENT = {"indep", "ind", "independiente", "independientes", "independent", "independente",
               "independant", "no club", "niez.", "misto", "nessun gruppo", "fraktionslos", "ni",
               "non-inscrits", "non inscrits", "no group", "sin bancada", "s/p", "sp"}
YES = tuple(sorted(latam.YES))
NO = tuple(sorted(latam.NO))


# --- names -------------------------------------------------------------------------

def country_name(cc):
    if cc in LATAM:
        return latam.NAMES.get(cc, cc)
    return ce.adapter(cc).name


def chamber(cc):
    if cc in LATAM:
        return LATAM_CHAMBER.get(cc, "")
    return ce.adapter(cc).chamber


def flag(cc):
    if cc in LATAM:
        return ":flag-{0}:".format(cc)
    return ce.adapter(cc).flag or ":flag-{0}:".format(cc)


# --- what qualifies ----------------------------------------------------------------

def probe(it, nz):
    """The vote as the evidence rules read it: its own title AND the title of
    the bill it is on (`group_title`, the bill titles in `refs`), with the
    tier-1 reading of either. A vote's own words are often only 'Votazione
    finale' or 'Articolo 1': the bill says what it is about, and several
    stores keep no tier on a vote whose areas are its bill's (Italy, Belgium)."""
    bill = " ".join(x for x in [it.get("group_title")]
                    + [r for r in (it.get("refs") or []) if isinstance(r, str)] if x)
    p = dict(it, title=" ".join(x for x in (it.get("title"), bill) if x))
    if p.get("tier") != 1 and (nz.title_tier1(dict(it, title=bill)) or
                               (p.get("tier") is None and nz.title_tier1(p))):
        p["tier"] = 1              # the collector's own tier 2 on its own words stands
    return p


def qualifies(it, nz, config_dir=None):
    """Watched, or tier 1 with the minimum evidence (both read on the vote and
    its bill, probe()); a tier-1 vote the session judge has read, only at 2
    or 3 (tools/latam_alerts.qualifies)."""
    if it["kind"] != "vote" or nz.muted(it, config_dir):
        return False
    if it.get("watched"):
        return True
    p = probe(it, nz)
    if p["tier"] != 1:
        return False
    if it.get("judge") is not None:
        return it["judge"] >= 2
    return nz.alert_reason(p, config_dir) is not None


def why(it, nz, config_dir=None):
    """'watched' or the evidence that made a tier-1 vote count."""
    if it.get("watched"):
        return "watched"
    if it.get("judge") is not None:
        return "tier 1, judge {0}/3".format(it["judge"])
    return nz.alert_reason(probe(it, nz), config_dir) or "tier 1"


def latam_positions(conn, cc, it):
    sql, note = LATAM_POSITIONS[cc]
    pos = [(r[0], r[1], r[2]) for r in ce.rows(conn, sql, (it["key"],))]
    if not pos:
        return it
    it = dict(it, positions=pos)
    if note:
        it["rebels_note"] = note
    else:
        it["rebels"] = ce.rebels([(n, g, (p or "").lower()) for n, g, p in pos], YES, NO)
        if LATAM_CAVEAT.get(cc):
            it["rebels_note"] = LATAM_CAVEAT[cc]
    return it


def group_of(rebel):
    """'Name (Group)' or 'Name (Group, against)' -> 'Group'."""
    hit = re.search(r"\(([^()]*)\)\s*$", rebel or "")
    return hit.group(1).split(",")[0].strip() if hit else ""


def drop_independents(it):
    """An independent cannot break from a group: leave them out of `rebels`."""
    if it.get("rebels"):
        it = dict(it, rebels=[r for r in it["rebels"]
                              if ce.noise_mod.fold(group_of(r)).strip() not in INDEPENDENT])
    return it


def candidates(conn, cc, since, until, config_dir=None):
    """[(item, why)] for the country's votes in the window that qualify."""
    if cc in LATAM:
        from src import latam_noise
        nz = latam_noise.NOISE
        got = latam.country_items(conn, cc, since, until, None, config_dir)
        got = [latam_positions(conn, cc, it) for it in got if it["kind"] == "vote"]
    else:
        country = ce.adapter(cc)
        nz = ce.noise_for(country)
        got = ce.gather(conn, country, since, until, config_dir)
    return [(drop_independents(it), why(it, nz, config_dir)) for it in got
            if qualifies(it, nz, config_dir)]


# --- the ledger --------------------------------------------------------------------

def vote_id(it):
    """Country, key, date and title: several adapters key a vote on its bill
    (Spain, Slovakia, Croatia), so the key alone is not one vote."""
    h = hashlib.sha1((it.get("title") or "").encode("utf-8")).hexdigest()[:10]
    return "{0}|{1}|{2}|{3}".format(it["cc"], stance_key(it), it["date"], h)


def stance_key(it):
    """The store's division key, which config/<cc>_stance.yaml uses
    (src/country5ca.py): the item's own key unless the adapter keyed the
    vote on its zaak or bill and said so (`division_key`)."""
    return it.get("division_key") or it["key"]


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
    got.setdefault("sent", {})
    got.setdefault("held", {})
    return got


def save(ledger, today, directory=None):
    cut = (datetime.date.fromisoformat(today) - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    ledger["sent"] = {k: v for k, v in ledger["sent"].items() if v >= cut}
    ledger["held"] = {k: v for k, v in ledger["held"].items() if v >= cut}
    path = ledger_path(ledger["cc"], directory)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def awaiting_positions(it):
    """True for a vote whose member positions the source has not published yet."""
    return it["cc"] in POSITIONS_LATER and not it.get("positions") and \
        it.get("rebels") is None and not it.get("rebels_note")


# --- grouping and rendering --------------------------------------------------------

def group_key(it):
    g = it.get("group")
    if g is None:
        return "key:" + it["key"]
    return "group:" + (json.dumps(g, ensure_ascii=False) if not isinstance(g, str) else g)


def brief_path(out_dir, cc, date, label):
    base = "{0}-votes-{1}-{2}".format(cc, date, vote_brief.safe_key(label)[:60] or "vote")
    path = os.path.join(out_dir, base + ".md")
    n = 2
    while os.path.exists(path):
        path = os.path.join(out_dir, "{0}-{1}.md".format(base, n))
        n += 1
    return path


def area_line(it):
    return ce.area_text(it["areas"]) or ("watched" if it.get("watched") else "none")


def position_table(positions):
    """Markdown rows: group | each position word as recorded, by frequency."""
    words, groups = {}, {}
    for _, g, p in positions:
        p = ce.clean(p) or "not recorded"
        words[p] = words.get(p, 0) + 1
        groups.setdefault(g or "no group recorded", {})
        groups[g or "no group recorded"][p] = groups[g or "no group recorded"].get(p, 0) + 1
    order = sorted(words, key=lambda w: (-words[w], w))
    out = ["| Group | " + " | ".join(order) + " |", "|---|" + "---|" * len(order)]
    for g in sorted(groups, key=lambda x: (-sum(groups[x].values()), x)):
        out.append("| {0} | {1} |".format(g, " | ".join(str(groups[g].get(w, 0)) for w in order)))
    return out


def rebels_text(it, limit=None):
    """The members who broke from their group, or why none are named."""
    reb = it.get("rebels")
    note = it.get("rebels_note")
    if reb:
        shown = reb if limit is None else reb[:limit]
        more = len(reb) - len(shown)
        text = "{0}{1}.".format("; ".join(shown), "; and {0} more (in the brief)".format(more)
                                if more > 0 else "")
        return "{0} ({1}): {2}".format("Broke from their group", len(reb), text) + (
            " " + note if note else "")
    if reb is not None:
        if note:
            return "Broke from their group: none named. " + note
        return "Broke from their group: none; every member voted with their group's " \
               "majority (abstentions aside)."
    if note:
        return note
    if awaiting_positions(it):
        return "Member positions not published yet; nobody can be named."
    return "No member positions in the record."


def order(votes):
    """The decisive vote first, then the rest in the record's order."""
    return sorted(votes, key=lambda it: (not it.get("final"), it["date"], it["key"],
                                         it.get("title") or ""))


def brief_markdown(cc, votes, reasons, generated=None, sample=False):
    votes = order(votes)
    head = votes[0]
    topic = head.get("group_title") or head["title"] or head["key"]
    out = ["# {0}{1} vote brief: {2}".format("SAMPLE (never sent). " if sample else "",
                                             country_name(cc), ce.clip(topic, 160)), ""]
    out.append("*{0}, {1}. {2} recorded vote{3} on our ground. Generated {4}. Facts of the "
               "record only: what a vote meant is a signed human reading "
               "(config/{5}_stance.yaml), never this brief's.*".format(
                   chamber(cc), ce.long_date(head["date"]), len(votes),
                   "" if len(votes) == 1 else "s",
                   generated or datetime.datetime.now().isoformat(timespec="minutes"), cc))
    out.append("")
    reasons = sorted(set(reasons))
    out.append("**Why it is here:** {0}. Areas: {1}.{2}".format(
        ", ".join(reasons), area_line(head),
        " Terms: {0}.".format(", ".join(ce.terms_of(head.get("terms"))[:8]))
        if ce.terms_of(head.get("terms")) else ""))
    out.append("")
    out.append("**5CA:** {0}".format(vote_brief.stance_status(cc, stance_key(head))))
    out.append("")
    for i, it in enumerate(votes, 1):
        label = "Decisive vote" if it.get("final") else (
            "Vote" if len(votes) == 1 else "Vote {0}".format(i))
        out.append("## {0}: {1}".format(label, ce.clip(it["title"], 300) or "(no title published)"))
        out.append("")
        if it.get("takeaway"):
            out.append(ce.sentence(it["takeaway"]))
            out.append("")
        if it.get("own") is False:
            out.append("*Areas from the bill it names, not the vote's own words.*")
            out.append("")
        if it is not head:
            out.append("5CA: {0}".format(vote_brief.stance_status(cc, stance_key(it))))
            out.append("")
        for line in it["lines"]:
            out.append("- " + line)
        out.append("")
        out.append("**{0}**".format(rebels_text(it)))
        out.append("")
        if it.get("positions"):
            out.extend(position_table(it["positions"]))
            out.append("")
        if it.get("url"):
            out.append("Record: [{0}]({0})".format(it["url"]))
            out.append("")
    out.append("---")
    out.append("")
    out.append("No meaning is attached here. Positions are the record's own words; a reading "
               "of config/{0}_stance.yaml is signed through its guide, docs/5ca-{0}-readings.md "
               "(tools/country_5ca.py).".format(cc))
    return vote_brief.house_style("\n".join(out) + "\n")


def dm_entry(cc, votes, reasons, brief_url):
    votes = order(votes)
    head = votes[0]
    topic = head.get("group_title") or head["title"] or head["key"]
    lines = ["{0} *{1}, {2}: {3}*".format(flag(cc), country_name(cc), ce.short_date(head["date"]),
                                          ce.clip(topic, 200))]
    lines.append("{0} · {1}".format(", ".join(sorted(set(reasons))), area_line(head)))
    for it in votes[:MAX_DM_VOTES]:
        tally = next((ln for ln in it["lines"] if ln.startswith("Tally:") or
                      ln.startswith("Result as recorded")), "")
        if it["title"] == topic:               # a lone vote: its title is the heading
            lines.append("• {0}".format(tally or "(no tally recorded)"))
        else:
            lines.append("• _{0}_{1}".format(ce.clip(it["title"], 160) or "(no title)",
                                             ": " + tally if tally else ""))
        if it.get("rebels") or not it.get("rebels_note"):
            lines.append("  " + rebels_text(dict(it, rebels_note=None), MAX_DM_REBELS))
    if len(votes) > MAX_DM_VOTES:
        lines.append("• and {0} more vote(s) on it, in the brief.".format(len(votes) - MAX_DM_VOTES))
    lines.append("5CA: {0}".format(vote_brief.stance_status(cc, stance_key(head))))
    lines.append("Brief: {0}".format(brief_url))
    if head.get("url"):
        lines.append("Record: {0}".format(head["url"]))
    return vote_brief.house_style("\n".join(lines))


# --- the run -----------------------------------------------------------------------

def send(text, secrets=None, sender=None):
    from src import publish
    got = dict(secrets if secrets is not None else publish.load_secrets())
    got["slack_dm_user_id"] = CHRIS            # Chris alone, whatever the env says
    return (sender or publish.slack_dm)(got, text)


def _age(it, today):
    try:
        return (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(it["date"])).days
    except (TypeError, ValueError):
        return HOLD_DAYS


def plan(conn, cc, since, until, today, ledger, config_dir=None, log=print):
    """The new votes to brief now, grouped: [(group key, [items], [reasons])].
    Updates the ledger's held votes in place."""
    fresh, groups = [], {}
    for it, reason in candidates(conn, cc, since, until, config_dir):
        vid = vote_id(it)
        if vid in ledger["sent"]:
            continue
        if awaiting_positions(it) and _age(it, today) < HOLD_DAYS:
            ledger["held"].setdefault(vid, today)
            log("  {0}: held for its member positions (voted {1})".format(it["key"], it["date"]))
            continue
        fresh.append((it, reason))
    for it, reason in fresh:
        k = (group_key(it), it["date"])
        groups.setdefault(k, ([], []))
        groups[k][0].append(it)
        groups[k][1].append(reason)
    return [(k, v[0], v[1]) for k, v in sorted(groups.items())]


def run(conn, countries, since, until, today=None, out_dir=BRIEFS, dm=True, secrets=None,
        sender=None, directory=None, config_dir=None, generated=None, log=print, label=None,
        sample=False):
    """Brief every new qualifying vote of `countries` in (since, until]. One DM
    for the whole run. Returns the number of briefs written."""
    today = today or until
    os.makedirs(out_dir, exist_ok=True)
    entries, written = [], 0
    for cc in countries:
        ledger = load(cc, directory)
        try:
            planned = plan(conn, cc, since, until, today, ledger, config_dir, log)
        except Exception as exc:          # one country's reader must not cost the others
            log("  [gap] {0}: the vote reader failed: {1}".format(cc, str(exc)[:160]))
            continue
        if not ledger["seeded"]:
            for _k, votes, _r in planned:
                for it in votes:
                    ledger["sent"][vote_id(it)] = today
                    ledger["held"].pop(vote_id(it), None)
            ledger["seeded"] = today
            log("{0}: seeded with {1} vote(s); nothing briefed on a first pass".format(
                cc, sum(len(v) for _k, v, _r in planned)))
            if dm:
                save(ledger, today, directory)
            continue
        for (gkey, date), votes, reasons in planned:
            head = order(votes)[0]
            path = brief_path(out_dir, cc, date, head.get("watch_key") or
                              (head["group"] if isinstance(head.get("group"), str) else None)
                              or head["key"])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(brief_markdown(cc, votes, reasons, generated, sample))
            written += 1
            rel = "data/briefs/" + os.path.basename(path)
            log("  {0}: {1} vote(s) -> {2}".format(cc, len(votes), rel))
            entries.append(dm_entry(cc, votes, reasons,
                                    "https://github.com/{0}/blob/main/{1}".format(REPO, rel)))
            for it in votes:
                ledger["sent"][vote_id(it)] = today
                ledger["held"].pop(vote_id(it), None)
        log("{0}: {1} brief(s) from {2} new vote(s)".format(
            cc, len(planned), sum(len(v) for _k, v, _r in planned)))
        if dm:
            save(ledger, today, directory)
    if entries:
        shown = entries[:MAX_DM_BRIEFS]
        text = "\n\n".join(shown)
        head = ":ballot_box_with_ballot: *{0}: {1} vote brief{2}*".format(
            label or "Same-day vote briefs", len(entries), "" if len(entries) == 1 else "s")
        text = head + "\n\n" + text
        if len(entries) > MAX_DM_BRIEFS:
            text += "\n\n_and {0} more brief(s) in data/briefs/._".format(len(entries) - MAX_DM_BRIEFS)
        text = vote_brief.house_style(text)
        if not dm:
            log("DM not sent (--no-dm). It would read:\n" + text)
        else:
            res = send(text, secrets, sender)
            log("DM: {0} ({1} brief(s))".format(
                "sent" if res.get("message_ts") or res.get("ok") else
                res.get("skipped") or res.get("error") or "sent", len(entries)))
    return written


def window_start(today, days):
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()
