"""Vote pages, a vote tracker and bill timelines for the new countries
(UK feature parity, 11 October 2026).

    from src import country_votes as cv
    data = cv.build(conn, "pl", today)          # one country's vote page data
    rows = cv.tracker_rows([data, ...])         # the multi-country tracker
    tl = cv.timelines(conn, "pl", today)        # watched bills, dated events

    python3 tools/make_country_votes.py         # the weekly step

What the UK, Germany, the US, Ireland and Australia have on the partner site
(tools/make_vote_tracker.py, make_de_votes.py, make_us_votes.py,
make_ie_votes.py, make_au_votes.py), for every new country whose store holds
member-level or party-group votes: Italy, Switzerland, France, the
Netherlands, Belgium, Austria, Portugal, Poland, Slovakia, Croatia, Spain,
Hungary, Brazil, Argentina, Mexico, Chile, Peru, Ecuador, the Dominican
Republic, El Salvador, Guatemala and Colombia. Three outputs, all in
partner_site/ behind the partner passphrase (src/partner.py's middleware,
fail-closed, as every UK vote page):

  <cc>-votes.html        the votes on our ground, newest first: the tally and
                         result as the chamber records them, the split by
                         party or group, who voted against their group's
                         majority, and every member's position, verbatim;
                         a member search gives one member's record.
  votes-countries.html   the tracker: one row per country (votes on our
                         ground, the latest, members, what party means
                         there, readings confirmed and awaiting sign-off),
                         and the latest votes across all of them.
  bill-timelines.html    every watched bill the store holds, with its dated
                         events: introduced, the stages the store keeps,
                         each agenda slot (src/agenda.py's country_agenda),
                         each recorded vote on it, and its end where known.

ON OUR GROUND IS THE EDITION'S, not a second classification: the vote list
is src/member_profiles.vote_items, the country's own edition adapter over the
whole store with its noise rules, mutes and session-judge scores. A vote the
edition would leave out is not on a page.

MEMBERS AND PARTIES come from src/member_profiles.py's Specs (the same SQL
the profiles read) and its party_of(): every position line carries what the
party claim rests on.
  * at the vote   the record names the party or group;
  * X6, as listed the record names none: the party shown is the member
                  list's, labelled "as listed, not party at the vote";
                  sourced history (Chile's BCN and militancias, Croatia's
                  transcripts) says so where it covers the day;
  * X5, DERIVED   party-group countries (AT, PT, NL show of hands): each
                  member's position is the group's vote, labelled DERIVED,
                  never counted as a recorded position.
"Against their group's majority" is arithmetic on RECORDED positions whose
party is the party at the vote (the record's, or a sourced history on the
day). Members with no group line to break (no group, non-attached,
independents, mixed groups: country_edition.no_group_line, #80) are never
counted, nor is anyone whose party is as listed (X6) or derived (X5).

LENGTH OF SERVICE (additive, 11 October 2026, src/member_service.py): where
the store holds service rows, each member card says "serving since" (or the
terms the source names) and nothing more, and the party-group countries'
DERIVED positions are given only for a day the member sat, by their group on
that day (src/member_profiles.positions_of, the same correction the profiles
make).

TALLIES AND RESULTS are the store's (src/country5ca.py's division SQL), in
the chamber's own words; where the store has no tally the page counts the
stored positions and says so.

NO VERDICTS BEFORE SIGN-OFF. Which way a vote cut for CitizenGO is a signed
human judgement (config/<cc>_stance.yaml, src/country5ca.py). A division
whose reading is not CONFIRMED (status confirmed, confirmed_by and
confirmed_on, readings5ca.status) ships with NO direction fields at all and
the page says "awaiting sign-off". A confirmed reading is shown as what it
is: who confirmed it, when, and the -2..2 values of a Yes and a No. No page
places a member in a 5CA column; that stays with the 5CA pages
(tools/make_country_5ca_web.py), gated on confirmed placements.

PORTRAITS AND PARTY COLOURS (additive, 12 October 2026, src/portraits.py):
build() also returns "_keys" (the member keys, aligned with "members"; never
rendered). tools/make_country_votes.py passes the data to portraits.attach,
which adds "colours" (party label -> chip colour, config/party-colours.yaml)
and, only for a country whose photo licence is OK
(docs/portraits-logos-licences.md), "portraits" and "portrait_credit": the
member card shows the thumbnail with the licence line. No party logo is used.

Read-only on the store and the config; fetches nothing; no AI call.
"""

from __future__ import annotations

import datetime
import html
import json
import os
import re
import sqlite3

from src import country5ca as c5
from src import country_edition as ce
from src import member_profiles as mp
from src import readings5ca as r5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every country with member-level or party-group votes (Uruguay's profiles
# hold questions only: no votes we can reach).
COUNTRIES = tuple(cc for cc, s in mp.SPECS.items() if s.positions is not None)

# Size: France has over 1,200 votes on our ground by 577 deputies. A page
# lists the latest MAX_DIVISIONS, with every member's position on each; the
# count of earlier ones is stated, and they stay in the store, the profiles
# and the editions. 300 by 577 is about 2 MB of page.
MAX_DIVISIONS = 300
TRACKER_DAYS = 90
TRACKER_MAX = 80
REBEL_MIN_GROUP = 3            # a group of two has no majority to break from
SAMPLE_MARK = "SAMPLE PAGE"

AWAITING = "awaiting sign-off"
NOT_DRAFTED = "no reading drafted"


def page_name(cc):
    return "{0}-votes.html".format(cc)


def _chamber_label(cc, code):
    code = ce.clean(code) or ""
    if cc in c5.SPECS and code in c5.SPECS[cc].chambers:
        return c5.SPECS[cc].chambers[code]
    return mp.CHAMBERS.get(cc, {}).get(code, code) or None


def at_vote_basis(basis):
    """True when a party claim is the party at the vote: the record's own, or
    a sourced party history covering the day (Chile)."""
    b = basis or ""
    return b == mp.AT_VOTE or b.startswith("on the day")


def side_of(cc, word):
    """'yea', 'nay', 'abstain' or None for a stored position (country5ca's
    lists of what each chamber records as a Yes, a No, an abstention)."""
    if cc not in c5.SPECS:
        return None
    return c5.SPECS[cc].side(word)


def reading_of(entry):
    """What a page may say about CitizenGO's reading of a division.

    Confirmed: {state, by, on, yea, nay}. Anything else: {state} only, with
    no direction fields at all, so an unsigned call can never reach a page."""
    if not entry:
        return {"state": NOT_DRAFTED}
    if r5.status(entry) != "confirmed":
        return {"state": AWAITING}
    return {"state": "confirmed", "by": ce.clean(entry.get("confirmed_by")),
            "on": str(entry.get("confirmed_on")), "yea": entry.get("yea"),
            "nay": entry.get("nay")}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class _Index:
    """Values to small integers, for a compact page."""

    def __init__(self):
        self.items, self._at = [], {}

    def __call__(self, value):
        if value not in self._at:
            self._at[value] = len(self.items)
            self.items.append(value)
        return self._at[value]


def rebels(cc, rows):
    """Member indexes whose recorded Yes or No went against their group's
    Yes/No majority. `rows` are (member index, group, word, basis) for one
    division. Left out: derived (X5) and as-listed (X6) parties, members with
    no group line to break (#80), groups under REBEL_MIN_GROUP, ties."""
    counted = [(mi, g, side_of(cc, w)) for mi, g, w, basis in rows
               if g and at_vote_basis(basis) and not ce.no_group_line(g)]
    counts = {}
    for _mi, g, s in counted:
        if s in ("yea", "nay"):
            c = counts.setdefault(g, [0, 0])
            c[0 if s == "yea" else 1] += 1
    out = []
    for mi, g, s in counted:
        c = counts.get(g)
        if s not in ("yea", "nay") or not c or sum(c) < REBEL_MIN_GROUP or c[0] == c[1]:
            continue
        if s != ("yea" if c[0] > c[1] else "nay"):
            out.append(mi)
    return sorted(set(out))


def build(conn, cc, today, config_dir=None, max_divisions=MAX_DIVISIONS):
    """One country's vote page data. Read-only."""
    spec = mp.SPECS[cc]
    conn.row_factory = sqlite3.Row
    ros = mp.roster(conn, spec)
    labels = ({str(a): b for a, b in mp._rows(conn, spec.group_labels)}
              if spec.group_labels else {})
    service = mp.service_context(conn, cc, ros)
    ctx = {"history": spec.history(conn) if spec.history else {}, "labels": labels,
           "service": service["by_member"]}
    for m in ros.by_key.values():
        if m.party:
            m.party = labels.get(str(m.party), m.party)
        m.service = service["by_member"].get(m.key)
    items = mp.vote_items(conn, cc, today, config_dir)
    conn.row_factory = sqlite3.Row
    store_divs = {r["key"]: r for r in c5.divisions(conn, cc)} if cc in c5.SPECS else {}
    entries = c5.load(cc, config_dir)[0] if cc in c5.SPECS else {}
    seen, ordered = set(), []
    for it in sorted(items, key=lambda i: (i["date"] or "", str(i["key"])), reverse=True):
        div = str(it.get("division") or it["key"])
        if div not in seen:
            seen.add(div)
            ordered.append((div, it))
    total = len(ordered)
    members, words, groups, bases = _Index(), _Index(), _Index(), _Index()
    member_rows = {}
    divisions = []
    counts = {"recorded": 0, "derived": 0, "as_listed": 0, "awaiting": 0, "confirmed": 0}
    for div, it in ordered[:max_divisions]:
        pos, rows = [], []
        for p in mp.positions_of(conn, spec, div, service):
            m = ros.resolve(p.get("member_id"), p.get("name"))
            if m is None:
                continue
            recorded = labels.get(str(p.get("party")), p.get("party"))
            party, basis = mp.party_of(spec, ctx, m, it["date"], ce.clean(recorded) or None,
                                       p.get("derived"), p.get("basis"))
            word = mp.spelt(spec, ce.clean(p.get("position")) or "(no position recorded)")
            if m.key not in member_rows:
                member_rows[m.key] = members(m.key)
            mi = member_rows[m.key]
            derived = bool(p.get("derived")) or basis in (mp.DERIVED, mp.DERIVED_DAY)
            counts["derived" if derived else ("recorded" if at_vote_basis(basis)
                                              else "as_listed")] += 1
            pos.append([mi, words(word), groups(ce.clean(party) or ""), bases(basis or "")])
            rows.append((mi, ce.clean(party) or "", ce.clean(p.get("position")) or "",
                         None if derived else basis))
        conn.row_factory = sqlite3.Row
        sd = store_divs.get(div) or {}
        reading = reading_of(entries.get(div))
        if reading["state"] == "confirmed":
            counts["confirmed"] += 1
        elif reading["state"] == AWAITING:
            counts["awaiting"] += 1
        divisions.append({
            "k": div, "d": it["date"], "t": ce.clean(it["title"]),
            "g": ce.clean(it.get("group_title")) or None,
            "tk": ce.clean(it.get("takeaway")) or None, "u": it.get("url"),
            "c": _chamber_label(cc, sd.get("chamber")),
            "a": [a for a in (it.get("areas") or []) if a not in ce.HIDDEN_AREAS],
            "w": bool(it.get("watched")), "tier": _int(it.get("tier")),
            "y": _int(sd.get("yes")), "n": _int(sd.get("no")), "ab": _int(sd.get("abstain")),
            "r": ce.clean(sd.get("result")) or None,
            "p": pos, "rb": rebels(cc, rows), "reading": reading})
    by_key = {v: k for k, v in member_rows.items()}
    member_list = []
    for i in range(len(members.items)):
        m = ros.by_key[by_key[i]]
        member_list.append([m.name, m.party or "", m.chamber or "", m.region or "",
                            None if m.current is None else bool(m.current), bool(m.stub),
                            _service_text(cc, m, service, today)])
    yes_label, no_label = (c5.SPECS[cc].labels if cc in c5.SPECS else ("Yes", "No"))
    wl = mp.watchlist(cc, config_dir)
    return {
        "cc": cc, "name": mp.country_name(cc), "today": today,
        "basis": spec.basis, "party_note": mp.party_note({"spec": spec, "service": service}),
        "store_note": c5.SPECS[cc].note if cc in c5.SPECS else "",
        "labels": [yes_label, no_label],
        "members": member_list, "words": words.items, "groups": groups.items,
        "bases": bases.items, "bases_short": [mp.short_basis(b) for b in bases.items],
        "derived_bases": [i for i, b in enumerate(bases.items)
                          if b in (mp.DERIVED, mp.DERIVED_DAY)],
        "service_note": _service_note(service, spec),
        "divisions": divisions,
        "total": total, "shown": len(divisions), "counts": counts,
        "watched_total": sum(1 for _d, it in ordered if it.get("watched")),
        "latest": ordered[0][1]["date"] if ordered else None,
        "chambers": sorted({d["c"] for d in divisions if d["c"]}),
        "readings": {k: sum(1 for e in entries.values() if r5.status(e) == k)
                     for k in ("confirmed", "draft", "unread", "unplaceable")},
        "watchlist_size": len(wl), "area_labels": {str(k): v for k, v in
                                                   ce.AREA_LABELS.items()},
        "attribution": mp.attribution(conn, cc),
        # The member keys, aligned with "members", for src/portraits.attach;
        # never rendered (render_page drops every "_" key).
        "_keys": [by_key[i] for i in range(len(members.items))],
    }


def _service_text(cc, m, service, today):
    """The member card's service line (src/member_service.short), or None."""
    if m.service is None:
        return None
    from src import member_service as ms
    return ms.short(cc, m.service, service["covers"], today, m.current)


def _service_note(service, spec):
    """The page's line on where the service lines come from, or None."""
    if not service.get("runs"):
        return None
    text = ("Service: the parliament's own record of each member's periods ({0}); 'serving "
            "since' is the start of the current unbroken run, and a source that names terms "
            "only gives no date.".format("; ".join(r["covers"] or r["source"]
                                                   for r in service["runs"])))
    if spec.basis == "derived":
        text += (" DERIVED positions are given only for a day the member sat, by their group "
                 "that day where the parliament dates it ({0} left out).".format(
                     service.get("dropped", 0)))
    return text


# --- the page -----------------------------------------------------------------------

TEMPLATE = os.path.join(ROOT, "templates", "country-votes.html")


def render_page(data, sample=False, template=TEMPLATE):
    with open(template, encoding="utf-8") as fh:
        page = fh.read()
    data = {k: v for k, v in data.items() if not k.startswith("_")}
    data["sample"] = SAMPLE_MARK if sample else None
    # </script> inside a string would close the page's script early.
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = "{0}: votes on our ground".format(data["name"])
    return (page.replace("/*__DATA__*/{}", blob)
            .replace("__TITLE__", html.escape(title)))


# --- the tracker ----------------------------------------------------------------------

BASIS_WORDS = {
    "at_vote": "recorded per member, party at the vote",
    "as_listed": "recorded per member, party as listed (X6)",
    "derived": "group votes, member positions DERIVED (X5)",
}


def tracker_rows(datas):
    """One summary row per country, from build() outputs."""
    out = []
    for d in datas:
        out.append({
            "cc": d["cc"], "name": d["name"], "page": page_name(d["cc"]),
            "total": d["total"], "shown": d["shown"], "watched": d["watched_total"],
            "latest": d["latest"], "chambers": d["chambers"],
            "members": len(d["members"]), "basis": BASIS_WORDS.get(d["basis"], d["basis"]),
            "confirmed": d["readings"]["confirmed"],
            "awaiting": d["readings"]["draft"] + d["readings"]["unread"],
        })
    return sorted(out, key=lambda r: r["name"])


def latest_votes(datas, today, days=TRACKER_DAYS, limit=TRACKER_MAX):
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()
    rows = []
    for d in datas:
        for v in d["divisions"]:
            if (v["d"] or "") >= since:
                rows.append(dict(v, cc=d["cc"], country=d["name"], labels=d["labels"]))
    rows.sort(key=lambda v: (v["d"] or "", v["country"], v["k"]), reverse=True)
    return rows[:limit]


def plural(n, one, many):
    return "{0} {1}".format(n, one if n == 1 else many)


def _e(text):
    return html.escape(str(text or ""), quote=True)


def _date(iso):
    try:
        return ce.long_date(ce.day(iso))
    except (TypeError, ValueError):
        return iso or "date not recorded"


def tally_text(v, labels):
    if v.get("y") is None and v.get("n") is None:
        return "tally not in the store"
    bits = ["{0} {1}".format(labels[0], v["y"] if v.get("y") is not None else "?"),
            "{0} {1}".format(labels[1], v["n"] if v.get("n") is not None else "?")]
    if v.get("ab") is not None:
        bits.append("abstentions {0}".format(v["ab"]))
    return ", ".join(bits)


PAGE_HEAD = """<!DOCTYPE html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title} · CitizenGO</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
body{{font:15px/1.55 Roboto,system-ui,sans-serif;color:#52575C;max-width:64rem;margin:0 auto;padding:1rem 1.4rem 3rem}}
a{{color:#4285f4;text-decoration:none}} a:hover{{text-decoration:underline}}
h1{{color:#20242a;font-size:1.6rem;border-bottom:4px solid #4285f4;padding-bottom:.4rem}}
h2{{color:#20242a;font-size:1.2rem;margin-top:2rem}} h3{{color:#20242a;font-size:1.02rem;margin:.2rem 0}}
.note{{background:#f6f7f9;border:1px solid #e2e5e9;border-radius:8px;padding:.7rem 1rem;font-size:.9em}}
.sample{{background:#FFEBAD;border-left:4px solid #DB544F;padding:.6rem 1rem;font-weight:700}}
table{{border-collapse:collapse;width:100%;font-size:.88em;margin:.6rem 0}}
th,td{{border-bottom:1px solid #EEEEEE;padding:.35rem .5rem;text-align:left;vertical-align:top}}
th{{color:#20242a;font-weight:500}}
.tag{{display:inline-block;font-size:.72em;font-weight:700;border-radius:4px;padding:.05em .45em;margin-right:.3em;background:#EAF1FE;color:#2f6fe0}}
.tag.w{{background:#4285f4;color:#fff}}
.bill{{border:1px solid #eef0f3;border-radius:10px;padding:.8rem 1rem;margin:.8rem 0}}
.ev{{font-size:.9em;margin:.25rem 0}} .ev .d{{font-weight:700;margin-right:.4rem;white-space:nowrap}}
.kind{{font-size:.7em;font-weight:700;border-radius:999px;padding:.05em .5em;background:#4285f4;color:#fff;margin-right:.35em}}
.kind.agenda{{background:#55B159}} .kind.vote{{background:#2f6fe0}} .kind.end{{background:#52575C}}
.kind.stage{{background:#8a6d1f}}
small{{color:#8a9097}}
</style></head><body>
<p><a href="/index.html">Partner edition</a> | <a href="/votes-countries.html">Votes in other countries</a> | <a href="/bill-timelines.html">Bill timelines</a></p>
"""


def render_tracker(datas, today, sample=False):
    rows = tracker_rows(datas)
    out = [PAGE_HEAD.format(title="Votes in other countries")]
    out.append("<h1>Votes on our ground in other countries</h1>")
    if sample:
        out.append('<p class="sample">{0}: built from scoping stores, never published.</p>'.format(
            SAMPLE_MARK))
    out.append(
        '<p class="note">How parliamentarians in {0} voted on our issues, from the '
        "parliamentary monitor's store as read on {1}. Every position is the record's own word; "
        "titles are verbatim. <b>No page says which way a vote cut for CitizenGO</b>: each "
        "reading is a signed judgement, and until a named person confirms it the page says "
        "\"awaiting sign-off\". Party-group countries show member positions DERIVED from the "
        "group's vote (X5); where the record names no party, the party shown is as listed, "
        "not party at the vote (X6).</p>".format(plural(len(rows), "country", "countries"),
                                                 _e(_date(today))))
    out.append("<table><tr><th>Country</th><th>Votes on our ground</th><th>Latest</th>"
               "<th>Chambers</th><th>Members</th><th>Member positions</th>"
               "<th>Readings</th></tr>")
    for r in rows:
        shown = (" ({0} latest listed)".format(r["shown"]) if r["shown"] < r["total"] else "")
        out.append(
            '<tr><td><a href="/{page}">{name}</a></td><td>{total}{shown}{w}</td><td>{latest}</td>'
            "<td>{ch}</td><td>{members}</td><td>{basis}</td><td>{conf} confirmed, {aw} awaiting "
            "sign-off</td></tr>".format(
                page=_e(r["page"]), name=_e(r["name"]), total=r["total"], shown=shown,
                w=", {0} watched".format(r["watched"]) if r["watched"] else "",
                latest=_e(_date(r["latest"])) if r["latest"] else "none",
                ch=_e(", ".join(r["chambers"])), members=r["members"], basis=_e(r["basis"]),
                conf=r["confirmed"], aw=r["awaiting"]))
    out.append("</table>")
    latest = latest_votes(datas, today)
    out.append("<h2>The latest votes, all countries ({0} days)</h2>".format(TRACKER_DAYS))
    if not latest:
        out.append("<p>No vote on our ground in the last {0} days.</p>".format(TRACKER_DAYS))
    else:
        out.append("<table><tr><th>Date</th><th>Country</th><th>Vote</th><th>Tally</th>"
                   "<th>Result</th><th>Reading</th></tr>")
        for v in latest:
            out.append(
                '<tr><td>{d}</td><td>{country}</td><td>{w}<a href="/{page}#v={k}"><i>{t}</i></a>'
                "</td><td>{tally}</td><td>{r}</td><td>{reading}</td></tr>".format(
                    d=_e(_date(v["d"])), country=_e(v["country"]),
                    w='<span class="tag w">watched</span>' if v["w"] else "",
                    page=_e(page_name(v["cc"])), k=_e(v["k"]), t=_e(ce.clip(v["t"], 160)),
                    tally=_e(tally_text(v, v["labels"])), r=_e(v.get("r") or ""),
                    reading=_e(reading_words(v["reading"]))))
        out.append("</table>")
    out.append("<p><small>Generated by tools/make_country_votes.py from the store each week; "
               "do not edit by hand.</small></p></body></html>")
    return "\n".join(out) + "\n"


def reading_words(reading):
    if reading.get("state") == "confirmed":
        return "confirmed by {0} on {1}".format(reading["by"], reading["on"])
    return reading.get("state") or AWAITING


# --- bill timelines ----------------------------------------------------------------------
#
# What each store keeps about a bill: its key, title, introduction date, the
# latest stage in the source's own words and its date, and its end (a law,
# a promulgation, a closure) where recorded. Columns, in order: key, title,
# introduced, stage, stage_date, end_date, end_label. A country without a
# bill table (Ecuador, El Salvador's piezas carry no stage) has none: its
# timelines hold agenda slots and votes only.

BILLS = {
    "it": "SELECT bill_key, COALESCE(short_title, title), presented, status, status_date, "
          "NULL, CASE WHEN law IS NOT NULL THEN 'Law ' || law END FROM it_bills",
    "ch": "SELECT short_number, COALESCE(title_de, title_fr, title_it), submission_date, status, "
          "status_date, NULL, NULL FROM ch_businesses WHERE short_number IS NOT NULL",
    "fr": "SELECT dossier_ref, title, NULL, last_act_label, last_act_at, promulgated_at, "
          "'Promulgated' FROM fr_dossiers",
    "nl": "SELECT zaak_nummer, COALESCE(titel, onderwerp), gestart, soort, NULL, NULL, "
          "CASE WHEN afgedaan THEN 'Afgedaan' END FROM nl_zaken",
    "be": "SELECT dossier_key, COALESCE(title_fr, title_nl), deposited, status, NULL, NULL, "
          "NULL FROM be_dossiers",
    "pl": "SELECT process_key, title, start_date, last_stage, last_stage_date, closure_date, "
          "'Closed' FROM pl_processes",
    "hr": "SELECT bill_key, title, NULL, vote_state, NULL, NULL, NULL FROM hr_items "
          "WHERE bill_key IS NOT NULL",
    "sk": "SELECT bill_key, title, delivered, type_name, NULL, NULL, NULL FROM sk_bills",
    "es": "SELECT initiative_key, objeto, presentada, situacion, NULL, NULL, resultado "
          "FROM es_initiatives",
    "br": "SELECT bill_key, ementa, presented, status, NULL, NULL, NULL FROM br_bills",
    "ar": "SELECT exp_key, title, published, NULL, NULL, NULL, "
          "CASE WHEN law IS NOT NULL THEN 'Law ' || law END FROM ar_bills",
    "mx": "SELECT ini_key, title, presented, status, NULL, NULL, NULL FROM mx_iniciativas",
    "hu": "SELECT paper_key, title, submitted_on, status, NULL, promulgated_on, 'Promulgated' "
          "FROM hu_papers",
    "at": "SELECT item_key, title, introduced, NULL, last_date, NULL, NULL FROM at_items",
    "pt": "SELECT ini_key, title, entered, latest_phase, latest_phase_at, NULL, NULL "
          "FROM pt_initiatives",
    "cl": "SELECT boletin, title, introduced, TRIM(COALESCE(stage, '') || CASE WHEN status "
          "IS NOT NULL THEN ' (' || status || ')' ELSE '' END), NULL, NULL, "
          "CASE WHEN law_number IS NOT NULL THEN 'Law ' || law_number END FROM cl_bills",
    "pe": "SELECT bill_key, title, presented, status, NULL, NULL, NULL FROM pe_bills",
    "do": "SELECT bill_key, title, deposited, status, last_change, promulgated, 'Promulgated' "
          "FROM do_bills",
    "gt": "SELECT numero, resumen, NULL, NULL, NULL, NULL, NULL FROM gt_initiatives",
    "co": "SELECT bill_key, COALESCE(nickname, title), filed_at, status, NULL, NULL, NULL "
          "FROM co_bills",
}

_ES_STEP = re.compile(r"([^\n]+?)\s*\n\s*([^\n]+?)\s*\n\s*desde (\d{2}/\d{2}/\d{4})"
                      r"(?: hasta (\d{2}/\d{2}/\d{4}))?")


def _dmy(text):
    d, m, y = text.split("/")
    return "{0}-{1}-{2}".format(y, m, d)


def es_history(conn, key):
    """Spain: the Congreso's procedural history (es_initiatives.tramitacion),
    as printed: 'Comisión de Igualdad / Enmiendas / desde .. hasta ..'."""
    got = mp._rows(conn, "SELECT tramitacion FROM es_initiatives WHERE initiative_key = ?",
                   (key,))
    text = (got[0][0] if got else None) or ""
    out = []
    for body, stage, start, end in _ES_STEP.findall(text):
        label = "{0}: {1}".format(ce.clean(body), ce.clean(stage))
        if end:
            label += " (until {0})".format(_date(_dmy(end)))
        out.append((_dmy(start), "stage", label))
    return out


HISTORY = {"es": es_history}


def bill_rows(conn, cc):
    """{key: (title, introduced, stage, stage_date, end_date, end_label)}."""
    sql = BILLS.get(cc)
    out = {}
    for r in mp._rows(conn, sql) if sql else []:
        if r[0] is not None:
            out[str(r[0])] = tuple(r[1:7])
    return out


def agenda_rows(conn, cc):
    """Every stored agenda point of the country (src/agenda.py), or []."""
    from src import country_debatepack as dp
    return dp.agenda_points(conn, cc, "0000-00-00", "9999-12-31") or []


def timelines(conn, cc, today, config_dir=None):
    """Every watched key of the country with at least one dated event, newest
    activity first: {key, title, url, areas, introduced, stage, events}.
    Events are (date, kind, text, link) with kind one of introduced, stage,
    agenda, vote, end. Read-only."""
    from src import country_debatepack as dp
    conn.row_factory = sqlite3.Row
    wl = mp.watchlist(cc, config_dir)
    if not wl:
        return []
    bills = bill_rows(conn, cc)
    agenda = agenda_rows(conn, cc)
    items = {}
    try:
        if os.path.exists(mp.edition_module(cc)):
            got = ce.gather(conn, ce.adapter(cc), mp.ALL_TIME, today, config_dir)
        else:
            from src import latam
            got = latam.country_items(conn, cc, mp.ALL_TIME, today, ledger={"moves": []},
                                      config_dir=config_dir)
    except Exception:                                           # noqa: BLE001
        got = []
    for it in got:
        for k in {it["key"], it.get("watch_key")} - {None}:
            items.setdefault(str(k), []).append(it)
    conn.row_factory = sqlite3.Row
    labels = c5.SPECS[cc].labels if cc in c5.SPECS else ("Yes", "No")
    out = []
    for key in wl:
        key = str(key)
        row = bills.get(key)
        events = []
        title, url, areas = None, None, []
        if row:
            title = row[0]
            if row[1]:
                events.append((ce.day(row[1]), "introduced", "Introduced", None))
            if row[2] and row[3]:
                events.append((ce.day(row[3]), "stage", ce.clean(row[2]), None))
            if row[4]:
                events.append((ce.day(row[4]), "end", ce.clean(row[5]) or "Ended", None))
        for e in (HISTORY[cc](conn, key) if cc in HISTORY else []):
            events.append(e + (None,))
        for it in items.get(key, []):
            title = title or it["title"]
            url = url or (it.get("url") if it["key"] == key else None)
            areas = areas or [a for a in it.get("areas") or [] if a not in ce.HIDDEN_AREAS]
            if it["kind"] == "law" and it.get("date"):
                events.append((it["date"], "end", ce.clean(it.get("status")) or "Law", it.get("url")))
        for p in agenda:
            if key in p["bill_keys"] or key in p["refs"] or key in p["watch_keys"]:
                text = "{0}: {1}".format(ce.clean(p.get("body")) or "Sitting",
                                         ce.clip(p.get("title") or "", 200))
                if p.get("status"):
                    text += " ({0})".format(ce.clean(p["status"]))
                events.append((ce.day(p["date"]), "agenda", text, p.get("url")))
        for d in dp.bill_divisions(conn, cc, [key], wl):
            tally = tally_text({"y": _int(d.get("yes")), "n": _int(d.get("no")),
                                "ab": _int(d.get("abstain"))}, labels)
            question = ce.clip(d.get("question") or "", 200).rstrip(".")
            sep = " " if question.endswith(("…", "...")) else ". "
            text = "{0}{1}{2}{3}".format(question, sep, tally,
                                        "; " + ce.clean(d["result"]) if d.get("result") else "")
            events.append((d["date"], "vote", text, "/{0}#v={1}".format(page_name(cc), d["key"])))
            title = title or d.get("subject")
        conn.row_factory = sqlite3.Row
        dated = sorted({e for e in events if e[0]}, key=lambda e: (e[0], e[1], e[2]))
        if not dated:
            continue
        entry = wl.get(key) if isinstance(wl.get(key), dict) else {}
        out.append({
            "key": key, "title": ce.clean(title) or key, "url": url,
            "areas": areas or [a for a in (entry.get("areas") or []) if isinstance(a, int)
                               and a not in ce.HIDDEN_AREAS],
            "introduced": ce.day(row[1]) if row and row[1] else None,
            "stage": ce.clean(row[2]) if row and row[2] else None,
            "stage_date": ce.day(row[3]) if row and row[3] else None,
            "upcoming": [e for e in dated if e[0] > today],
            "events": dated, "last": dated[-1][0]})
    out.sort(key=lambda b: (b["last"], b["key"]), reverse=True)
    return out


KIND_WORDS = {"introduced": "introduced", "stage": "stage", "agenda": "agenda",
              "vote": "vote", "end": "end"}


def render_timelines(per_country, today, sample=False):
    """per_country: [(cc, name, [timeline...])]."""
    out = [PAGE_HEAD.format(title="Bill timelines")]
    out.append("<h1>Watched bills: timelines</h1>")
    if sample:
        out.append('<p class="sample">{0}: built from scoping stores, never published.</p>'.format(
            SAMPLE_MARK))
    n = sum(len(t) for _cc, _n, t in per_country)
    out.append(
        '<p class="note">{0} watched bill(s) in {1}, from the store as read on {2}: '
        "when each was introduced, the stages the store keeps (most stores keep the latest "
        "stage only; Spain's keeps the Congreso's whole procedural history), every agenda slot "
        "collected for it, every recorded vote on it and its end where known. Titles and "
        "stages are the source's own words. Dates after today are upcoming slots on the "
        "published agenda, not predictions.</p>".format(
            n, plural(sum(1 for _c, _n, t in per_country if t), "country", "countries"),
            _e(_date(today))))
    out.append("<p>" + " | ".join('<a href="#{0}">{1}</a> ({2})'.format(cc, _e(name), len(t))
                                  for cc, name, t in per_country if t) + "</p>")
    for cc, name, tls in per_country:
        if not tls:
            continue
        out.append('<h2 id="{0}">{1}</h2>'.format(cc, _e(name)))
        for b in tls:
            head = '<i>{0}</i>'.format(_e(ce.clip(b["title"], 220)))
            if b.get("url"):
                head = '<a href="{0}">{1}</a>'.format(_e(b["url"]), head)
            facts = ["key {0}".format(_e(b["key"]))]
            if b.get("areas"):
                facts.append(_e(ce.area_text(b["areas"])))
            if b.get("stage"):
                facts.append("latest stage recorded: {0}{1}".format(
                    _e(b["stage"]), " ({0})".format(_e(_date(b["stage_date"])))
                    if b.get("stage_date") else ""))
            if b["upcoming"]:
                facts.append("<b>next on the agenda {0}</b>".format(_e(_date(b["upcoming"][0][0]))))
            out.append('<div class="bill" id="{0}-{1}"><h3>{2}</h3><small>{3}</small>'.format(
                cc, _e(re.sub(r"[^A-Za-z0-9]+", "-", b["key"])), head, " · ".join(facts)))
            for d, kind, text, link in b["events"]:
                body = _e(text)
                if link:
                    body = '<a href="{0}">{1}</a>'.format(_e(link), body)
                out.append('<div class="ev"><span class="d">{0}</span><span class="kind {1}">{2}'
                           "</span>{3}{4}</div>".format(
                               _e(_date(d)), kind, KIND_WORDS[kind], body,
                               " <small>(upcoming)</small>" if d > today else ""))
            out.append("</div>")
    out.append("<p><small>Generated by tools/make_country_votes.py from the store each week; "
               "do not edit by hand.</small></p></body></html>")
    return "\n".join(out) + "\n"
