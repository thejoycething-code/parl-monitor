"""Issue pages: one page per campaign area, everything the monitor holds on it.

Christopher, 2026-09-07: "Build the issue pages." Until now "what have we
seen on surrogacy since May?" needed the store and a query. Each page is
that answer, built weekly from the store and read only:

  * the Bills on the board for the area, with what happens next;
  * the edition's items on the area in the last six months, dated, with the
    judge's line (score 2 or 3: what the edition carried);
  * activity by month for a year -- questions, speeches, motions, divisions --
    the plain count that says whether an issue is heating up;
  * debates: date, title, how many spoke, how the stance pass read them,
    linked to Hansard;
  * divisions the ledger holds, with the lobby counts and the record link;
  * sponsored motions and the most recent written questions, each linked;
  * petitions on the area, Westminster and devolved, with signatures.

Migration (area 11) is collated, never campaigned, so it has no page.
Public record and the monitor's own scoring only; no stance placement of
individual members appears here -- that is the 5CA's job.
"""

from __future__ import annotations

import datetime
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIDDEN = (11,)
WINDOW_DAYS = 183
DIRECTION = {2: "with us, strongly", 1: "with us", 0: "neutral", -1: "against us", -2: "against us, strongly"}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _areas(raw):
    """Area numbers from either shape the store uses: the ledger's JSON list
    ('[2, 6]') or the bills board's comma-separated string ('2,6')."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, int):
        return [raw]
    text = str(raw).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [int(a) for a in parsed]
        if isinstance(parsed, int):
            return [parsed]
    except (ValueError, TypeError):
        pass
    return [int(a) for a in re.findall(r"\d+", text)]


def _pq_url(conn, ref):
    pid = ref.split(":", 1)[1] if ":" in ref else ref
    row = conn.execute("SELECT uin, tabled FROM pq_link WHERE pq_id = ?", (pid,)).fetchone()
    if not row:
        return None
    return "https://questions-statements.parliament.uk/written-questions/detail/{0}/{1}".format(row[1], row[0])


def collect(conn, area, today=None, raw=None, window_days=WINDOW_DAYS):
    """Everything on one area, as plain dicts for the renderer."""
    today = today or datetime.date.today()
    from src import stance as _stance
    _stance.ensure_table(conn)                  # stance lives outside the schema; a fresh store has none yet
    since = (today - datetime.timedelta(days=window_days)).isoformat()
    year_ago = (today - datetime.timedelta(days=365)).isoformat()
    out = {"area": area, "since": since}

    out["bills"] = [dict(r) for r in conn.execute(
        "SELECT bill_id, title, house, stage, next_key_date, what_next, status, areas FROM bills_board "
        "WHERE status = 'live' ORDER BY COALESCE(next_key_date, '9999')") if area in _areas(r["areas"])]

    out["items"] = [dict(r) for r in conn.execute(
        "SELECT id, source_feed, title, url, event_date, deadline, triage_score, why_it_matters, issue_areas, captured_at "
        "FROM items WHERE triage_score >= 2 ORDER BY COALESCE(event_date, substr(captured_at, 1, 10)) DESC")
        if area in _areas(r["issue_areas"]) and (r["event_date"] or r["captured_at"] or "")[:10] >= since]

    events = [r for r in conn.execute(
        "SELECT e.member_id, e.date, e.kind, e.ref, e.line, e.areas, m.name, m.party, m.seat, m.house, s.stance "
        "FROM mp_events e LEFT JOIN members m ON m.id = e.member_id LEFT JOIN stance s ON s.ref = e.ref "
        "WHERE e.date >= ? ORDER BY e.date DESC", (year_ago,)) if area in _areas(r["areas"])]

    months = {}
    for r in events:
        m = months.setdefault(r["date"][:7], {"pq": 0, "debate": 0, "edm": 0, "vote": 0})
        k = "vote" if r["kind"] == "vote" else ("edm" if r["kind"] in ("edm", "edm-signed") else r["kind"])
        if k in m:
            m[k] += 1
    out["months"] = [dict(month=k, **v) for k, v in sorted(months.items(), reverse=True)][:12]

    recent = [r for r in events if r["date"] >= since]
    debates = {}
    for r in recent:
        if r["kind"] != "debate":
            continue
        meta = (raw.get(r["ref"])[1] if raw else None) or {}
        title = meta.get("debate") or re.sub(r"^Spoke: ", "", re.sub(r" \(re: [^)]*\)$", "", r["line"] or ""))
        key = meta.get("debate_id") or (r["date"], title.lower())
        d = debates.setdefault(key, {"date": meta.get("date") or r["date"], "title": title, "house": meta.get("house") or r["house"],
                                     "url": ("https://hansard.parliament.uk/{0}/{1}/debates/{2}/".format(
                                         meta.get("house"), meta.get("date"), meta["debate_id"]) if meta.get("debate_id") else None),
                                     "speakers": set(), "with": 0, "against": 0, "neutral": 0, "unscored": 0})
        d["speakers"].add(r["member_id"])
        s = r["stance"]
        if s is None:
            d["unscored"] += 1
        elif s > 0:
            d["with"] += 1
        elif s < 0:
            d["against"] += 1
        else:
            d["neutral"] += 1
    out["debates"] = sorted(({**d, "speakers": len(d["speakers"])} for d in debates.values()),
                            key=lambda d: d["date"], reverse=True)

    divisions = {}
    for r in recent:
        if r["kind"] != "vote":
            continue
        base, _, lobby = r["ref"].rpartition(":")
        d = divisions.setdefault(base, {"date": r["date"], "title": re.sub(r"^Voted (Aye|No): ", "", r["line"] or ""),
                                        "ayes": 0, "noes": 0, "house": "Lords" if base.startswith("div:l") else "Commons",
                                        "url": "https://votes.parliament.uk/Votes/{0}/Division/{1}".format(
                                            "Lords" if base.startswith("div:l") else "Commons", re.sub(r"\D", "", base))})
        d["ayes" if lobby == "aye" else "noes"] += 1
    out["divisions"] = sorted(divisions.values(), key=lambda d: d["date"], reverse=True)

    out["motions"] = [{"date": r["date"], "title": re.sub(r"^Sponsored EDM: ", "", re.sub(r" \(re: [^)]*\)$", "", r["line"] or "")),
                       "who": r["name"], "party": r["party"],
                       "url": "https://edm.parliament.uk/early-day-motion/{0}".format(r["ref"].split(":", 1)[1])}
                      for r in recent if r["kind"] == "edm"]

    seen = set()
    out["questions"] = []
    for r in recent:
        if r["kind"] != "pq" or r["ref"] in seen:
            continue
        seen.add(r["ref"])
        out["questions"].append({"date": r["date"], "title": re.sub(r" \(re: [^)]*\)$", "", r["line"] or ""),
                                 "who": r["name"], "party": r["party"], "seat": r["seat"], "url": _pq_url(conn, r["ref"])})
        if len(out["questions"]) >= 40:
            break
    out["questions_total"] = sum(1 for r in recent if r["kind"] == "pq")

    pets = []
    try:
        for r in conn.execute("SELECT action, url, signatures, milestone, areas FROM petitions ORDER BY signatures DESC"):
            if area in _areas(r["areas"]):
                pets.append({"where": "Westminster", "action": r["action"], "url": r["url"], "signatures": r["signatures"], "milestone": r["milestone"]})
        for r in conn.execute("SELECT nation, action, url, signatures, milestone, areas FROM dv_petitions ORDER BY signatures DESC"):
            if area in _areas(r["areas"]):
                pets.append({"where": {"wales": "Senedd", "scotland": "Holyrood"}.get(r["nation"], r["nation"]), "action": r["action"],
                             "url": r["url"], "signatures": r["signatures"], "milestone": r["milestone"]})
    except Exception:                                       # noqa: BLE001
        pass
    out["petitions"] = pets
    return out


def render(data, name, today=None):
    today = today or datetime.date.today()
    x = lambda s: (s or "").replace("|", "/")
    out = ["# {0}".format(name), "",
           "Everything the monitor holds on this area: the Bills, the edition's items since {0}, activity by month, "
           "the debates, divisions, motions, questions and petitions. Public record and the monitor's own scoring; "
           "refreshed each Monday. Generated {1}.".format(data["since"], today.isoformat()), ""]
    if data["bills"]:
        out += ["## Bills on the board", "", "| Bill | House and stage | Next key date | What happens next |", "|---|---|---|---|"]
        for b in data["bills"]:
            out.append("| [{0}](https://bills.parliament.uk/bills/{1}) | {2}, {3} | {4} | {5} |".format(
                x(b["title"]), b["bill_id"], b["house"] or "", b["stage"] or "", b["next_key_date"] or "TBA", x(b["what_next"])))
        out.append("")
    if data["items"]:
        out += ["## In the editions ({0})".format(len(data["items"])), "", "| Date | Type | Item | Why it matters |", "|---|---|---|---|"]
        for it in data["items"]:
            title = x(it["title"])
            link = "[{0}]({1})".format(title, it["url"]) if it["url"] else title
            out.append("| {0} | {1} | {2} | {3} |".format((it["event_date"] or it["captured_at"] or "")[:10], it["source_feed"],
                                                         link, x(it["why_it_matters"])))
        out.append("")
    if data["months"]:
        out += ["## Activity by month", "", "*Ledger events on this area: written questions, speeches, motions (sponsored and signed), and votes cast.*", "",
                "| Month | Questions | Speeches | Motions | Votes |", "|---|---|---|---|---|"]
        for m in data["months"]:
            out.append("| {0} | {1} | {2} | {3} | {4} |".format(m["month"], m["pq"], m["debate"], m["edm"], m["vote"]))
        out.append("")
    if data["debates"]:
        out += ["## Debates ({0})".format(len(data["debates"])), "",
                "*How the stance pass read the speakers: with us / against us / neutral / not yet scored.*", "",
                "| Date | Debate | Spoke | Read as |", "|---|---|---|---|"]
        for d in data["debates"]:
            title = "[{0}]({1})".format(x(d["title"]), d["url"]) if d["url"] else x(d["title"])
            out.append("| {0} | {1} ({2}) | {3} | {4} with · {5} against · {6} neutral · {7} unscored |".format(
                d["date"], title, d["house"] or "", d["speakers"], d["with"], d["against"], d["neutral"], d["unscored"]))
        out.append("")
    if data["divisions"]:
        out += ["## Divisions ({0})".format(len(data["divisions"])), "", "| Date | Division | Ayes | Noes |", "|---|---|---|---|"]
        for d in data["divisions"]:
            out.append("| {0} | [{1}]({2}) ({3}) | {4} | {5} |".format(d["date"], x(d["title"]), d["url"], d["house"], d["ayes"], d["noes"]))
        out += ["", "*Lobby counts are members the ledger recorded, not the official tally. Verdicts and every member's record are on the vote tracker.*", ""]
    if data["motions"]:
        out += ["## Early day motions ({0})".format(len(data["motions"])), "", "| Date | Motion | Sponsor |", "|---|---|---|"]
        for m in data["motions"]:
            out.append("| {0} | [{1}]({2}) | {3}{4} |".format(m["date"], x(m["title"]), m["url"], m["who"] or "",
                                                              " ({0})".format(m["party"]) if m["party"] else ""))
        out.append("")
    if data["questions"]:
        out += ["## Written questions ({0}, most recent {1})".format(data["questions_total"], len(data["questions"])), "",
                "| Date | Question | Member |", "|---|---|---|"]
        for q in data["questions"]:
            title = "[{0}]({1})".format(x(q["title"]), q["url"]) if q["url"] else x(q["title"])
            who = " ".join(x for x in (q["who"], "({0}{1})".format(q["party"] or "", ", " + q["seat"] if q["seat"] else "") if (q["party"] or q["seat"]) else "") if x)
            out.append("| {0} | {1} | {2} |".format(q["date"], title, who))
        out.append("")
    if data["petitions"]:
        out += ["## Petitions ({0})".format(len(data["petitions"])), "", "| Parliament | Petition | Signatures | Where it stands |", "|---|---|---|---|"]
        for p in data["petitions"]:
            out.append("| {0} | [{1}]({2}) | {3:,} | {4} |".format(p["where"], x(p["action"]), p["url"], p["signatures"] or 0, x(p["milestone"])))
        out.append("")
    return "\n".join(out)


def build(site_dir, conn, area_names, today=None, raw=None):
    """Write issue-<slug>.html per area and issues.html as the index. -> [paths]"""
    from src import partner
    today = today or datetime.date.today()
    if raw is None:
        try:
            from src import quotes
            raw = quotes.RawHansard(ROOT)
        except Exception:                                   # noqa: BLE001
            raw = None
    paths, index = [], ["# Issues", "", "One page per campaign area: the Bills, the editions' items, activity by month, debates, divisions, "
                        "motions, questions and petitions the monitor holds on it. Refreshed each Monday.", "",
                        "| Area | Bills on the board | Items since {0} | Debates | Divisions | Petitions |".format(
                            (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()), "|---|---|---|---|---|---|"]
    for area in sorted(a for a in area_names if a not in HIDDEN):
        name = area_names[area]
        data = collect(conn, area, today=today, raw=raw)
        page = partner.to_html(render(data, name, today), "{0} - issue page".format(name))
        path = os.path.join(site_dir, "issue-{0}.html".format(slug(name)))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(page)
        paths.append(path)
        index.append("| [{0}](/issue-{1}.html) | {2} | {3} | {4} | {5} | {6} |".format(
            name, slug(name), len(data["bills"]), len(data["items"]), len(data["debates"]), len(data["divisions"]), len(data["petitions"])))
    index.append("")
    ipath = os.path.join(site_dir, "issues.html")
    with open(ipath, "w", encoding="utf-8") as fh:
        fh.write(partner.to_html("\n".join(index), "Issues"))
    return [ipath] + paths
