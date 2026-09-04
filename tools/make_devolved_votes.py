"""The public Senedd and Assembly voting pages.

    python3 tools/make_devolved_votes.py --nation wales
    python3 tools/make_devolved_votes.py --nation ni

Wales and Northern Ireland had no public voting page at all: 58,698
Welsh and 2,722 NI member-votes were collected and invisible (measured
2026-09-04). One template serves both because their pages need the same
thing -- search by member NAME or by SEAT, since neither chamber has a
single-member-per-postcode answer: a Senedd voter has a constituency
Member and four regional ones, and an Assembly voter has five or six
MLAs from one STV constituency. That is also why neither page pretends
to do postcode lookup, which is Westminster's shape, not theirs.

Holyrood keeps its own bespoke page (tools/make_msp_votes.py): it earns
one with the switcher analysis on the assisted dying Bill.

Verdicts come from sd_scored / ni_scored, which tools/devolved_score.py
writes from the nation's config -- and an unsigned division stores a
vote with verdict NULL, so this page shows HOW a member voted while
saying nothing about what it meant.

Reads the store; writes partner_site/ and docs/. Never writes the store.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, devolved

TEMPLATE = os.path.join(ROOT, "templates", "devolved-votes.html")

NATIONS = {
    "wales": {
        "out": "ms-votes.html",
        "config": "senedd_votes.yaml",
        "members": ("sd_members", "person_id", "name", "party", "post"),
        "divisions": ("sd_divisions", "key", "dated", "title",
                      "total_for", "total_against", "total_abstain"),
        # JOIN BY NAME, not id. sd_votes.member_id holds the Senedd's own
        # small integers (1, 143, 145) while sd_members.person_id holds
        # publicwhip URIs -- two id spaces that share nothing, which is why
        # the first build rendered 1,036 votes belonging to nobody. 94 of
        # the 96 sitting Members resolve by normalised name; the rest of
        # the 130 names in the votes table are departed Members and the
        # Presiding Officer's "Casting Vote", and the build says how many.
        "votes": ("sd_votes", "division_key", "member_name", "result"),
        "join": "name",
        "scored": "sd_scored",
        "title": "How did your Member of the Senedd vote?",
        "chamber": "Senedd Cymru",
        "member": "MS", "member_plural": "Members", "seat": "constituency",
        "placeholder": "Member name or constituency (e.g. Islwyn)…",
        "blurb": ("Divisions in Senedd Cymru on the issues we track, from "
                  "the Senedd's own published records. A Senedd voter has "
                  "a constituency Member and regional Members, so search "
                  "by name or by seat."),
        "source": "the Senedd's published division records",
    },
    "ni": {
        "out": "mla-votes.html",
        "config": "nia_votes.yaml",
        "members": ("ni_members", "person_id", "display_name", "party",
                    "constituency"),
        "divisions": ("ni_divisions", "doc_id", "dated", "subject",
                      None, None, None),
        "votes": ("ni_votes", "doc_id", "person_id", "vote"),
        "join": "id",
        "scored": "ni_scored",
        "title": "How did your MLA vote?",
        "chamber": "Northern Ireland Assembly",
        "member": "MLA", "member_plural": "MLAs", "seat": "constituency",
        "placeholder": "MLA name or constituency (e.g. West Tyrone)…",
        "blurb": ("Divisions in the Northern Ireland Assembly on the issues "
                  "we track, from the Assembly's own published records. "
                  "Each constituency returns five MLAs, so search by name "
                  "or by constituency."),
        "source": "the Assembly's published division records",
    },
}


def load_config(spec):
    import yaml
    path = os.path.join(ROOT, "config", spec["config"])
    if not os.path.exists(path):
        return {}
    divs = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get(
        "divisions") or []
    return {str(d["key"]): d for d in divs}


def _voters(conn, spec):
    """Ids of everyone with a vote in a division this page tracks.

    Resolved through the same bridge the rest of the build uses, so a
    former Member is listed on exactly the evidence that will be shown
    on their card -- never on a name that would not have matched.
    """
    vt, vkey, vmem, _ = spec["votes"]
    rows = conn.execute("SELECT DISTINCT {0} FROM {1}".format(vmem, vt))
    if spec.get("join") != "name":
        return {str(r[0]) for r in rows}
    index = devolved.roster(conn)          # every term, not just sitting
    got, _missing = devolved.resolve([r[0] for r in rows], index)
    return {str(v) for v in got.values()}


def build(conn, nation):
    spec = NATIONS[nation]
    cfg = load_config(spec)
    mt, mid, mname, mparty, mseat = spec["members"]
    cols = [c[1] for c in conn.execute("PRAGMA table_info({0})".format(mt))]
    has_end = "end_date" in cols
    has_start = "start_date" in cols
    # WHO IS LISTED. Everyone sitting, plus anyone who CAST A VOTE we
    # track, marked as a former Member. The roster holds every Member
    # the Senedd has ever had (227 people, 96 sitting), and listing all
    # of them invites a reader to write to someone who left in 2016 --
    # but listing only the 96 hid the votes of the Sixth Senedd
    # entirely, Mark Drakeford's and the First Minister's among them,
    # on divisions that are the only ones we track.
    voted = _voters(conn, spec)
    members = [{"id": str(r[mid]), "name": r[mname] or "?",
                "party": r[mparty], "seat": r[mseat],
                "former": bool(has_end and (r["end_date"] or "").strip()),
                # Carried so the card can tell "was not there" apart from
                # "did not vote". Every sitting Welsh Member starts
                # 2026-05-08 (the 96-seat Senedd), and every division we
                # track predates it -- 67 of 96 Members were not yet
                # elected, and a blank row would read as an absence.
                "start": (r["start_date"] if has_start else None)}
               for r in conn.execute(
                   "SELECT * FROM {0} ORDER BY {1}".format(mt, mname))
               if r[mname] and (not has_end
                                or not (r["end_date"] or "").strip()
                                or str(r[mid]) in voted)]
    dt, dkey, ddate, dtitle, dfor, dagainst, dabst = spec["divisions"]
    divisions = []
    for r in conn.execute(
            "SELECT * FROM {0} WHERE areas NOT IN ('', '[]') "
            "AND areas IS NOT NULL ORDER BY {1} DESC".format(dt, ddate)):
        key = str(r[dkey])
        c = cfg.get(key) or {}
        signed = bool(c.get("signed_off")) and c.get("our_side")
        d = {"key": key, "dated": (r[ddate] or "")[:10],
             "short": c.get("short") or r[dtitle] or key,
             "stage": c.get("stage") or "",
             "motion": c.get("motion"),
             "why": (r["why_it_matters"]
                     if "why_it_matters" in r.keys() else None),
             "for": r[dfor] if dfor and dfor in r.keys() else None,
             "against": (r[dagainst] if dagainst and dagainst in r.keys()
                         else None),
             "abstain": (r[dabst] if dabst and dabst in r.keys() else None),
             "signed": bool(signed)}
        if signed:
            d["meaning_good"] = (c.get("meaning_good") or "").strip()
            d["meaning_bad"] = (c.get("meaning_bad") or "").strip()
        divisions.append(d)

    vt, vkey, vmem, vvote = spec["votes"]
    # src/devolved.py owns the name->id bridge; the scorer uses the same
    # one, so a verdict written there is found here. EVERY TERM, not
    # just sitting Members: the page now lists anyone who cast a vote it
    # tracks, and resolving against the sitting 96 alone threw away the
    # Sixth Senedd's votes -- the very ones on the divisions we track.
    index = (devolved.roster(conn) if spec.get("join") == "name" else None)
    verdicts = {}
    try:
        for r in conn.execute("SELECT * FROM {0}".format(spec["scored"])):
            verdicts[(str(r["division_key"]), str(r["person_id"]))] = \
                r["verdict"]
    except Exception:
        pass
    keys = {d["key"] for d in divisions}
    votes = {}
    unresolved = set()
    for r in conn.execute("SELECT * FROM {0}".format(vt)):
        key = str(r[vkey])
        if index is not None:
            got, missing = devolved.resolve([r[vmem]], index)
            if missing:
                unresolved.update(missing)
                continue
            person = str(got[r[vmem]])
        else:
            person = str(r[vmem])
        if key not in keys:
            continue
        votes.setdefault(person, {})[key] = {
            "vote": r[vvote],
            "verdict": verdicts.get((key, person))}
    return {"members": members, "divisions": divisions, "votes": votes,
            "unresolved": sorted(unresolved),
            "built": datetime.date.today().isoformat()}


def main():
    # No --nation builds EVERY nation. run_monday.py drives its build
    # tools with no arguments, so a tool that needs a flag to do its job
    # silently builds one nation and leaves the other page stale.
    if "--nation" in sys.argv:
        nations = [sys.argv[sys.argv.index("--nation") + 1]]
    else:
        nations = list(NATIONS)
    for nation in nations:
        if nation not in NATIONS:
            print("unknown nation: {0} ({1})".format(
                nation, "|".join(NATIONS)))
            return 1
    # ONE head line for every nation, and no leading spaces on anything
    # that matters. run_monday.py relays a tool's first line, drops
    # INDENTED lines as library noise, and lifts the rest only when they
    # name a caveat -- so the 2026-09-04 dry run carried Wales's summary
    # and silently binned both NI's and the suppressed-voter line.
    stats, caveats = [], []
    for nation in nations:
        st, cav = build_page(nation)
        stats.append(st)
        caveats.extend(cav)
    print("; ".join(stats))
    for line in caveats:
        print(line)
    return 0


def build_page(nation):
    spec = NATIONS[nation]
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    data = build(conn, nation)
    page = open(TEMPLATE, encoding="utf-8").read()
    for token, value in (
            ("__PAGE_TITLE__", spec["title"]),
            ("__CHAMBER_UPPER__", spec["chamber"].upper()),
            ("__CHAMBER_NAME__", spec["chamber"]),
            ("__MEMBER_UPPER__", spec["member"]),
            ("__MEMBER_PLURAL__", spec["member_plural"]),
            ("__SEAT_UPPER__", spec["seat"].upper()),
            ("__PLACEHOLDER__", spec["placeholder"]),
            ("__BLURB__", spec["blurb"]),
            ("__SOURCE_NOTE__", spec["source"])):
        page = page.replace(token, value)
    page = page.replace("/*__DATA__*/{}",
                        json.dumps(data, ensure_ascii=False))
    written = []
    for out in (os.path.join(ROOT, "partner_site", spec["out"]),
                os.path.join(ROOT, "docs", spec["out"])):
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(page)
        written.append(out)
    signed = sum(1 for d in data["divisions"] if d["signed"])
    summary = ("{0} {1} members, {2} division(s), {3} signed, {4} votes"
               .format(nation, len(data["members"]), len(data["divisions"]),
                       signed, sum(len(v) for v in data["votes"].values())))
    caveats = []
    if data.get("unresolved"):
        # "missing" is load-bearing, and so is the absent indent: the
        # relay drops indented lines outright and lifts the rest only
        # when they name a caveat. A suppression nobody reads is a
        # silent suppression.
        caveats.append(
            "{0}: {1} voter name(s) are missing from the roster, "
            "so their votes are not shown: {2}{3}".format(
                nation, len(data["unresolved"]),
                ", ".join(data["unresolved"][:5]),
                " ..." if len(data["unresolved"]) > 5 else ""))
    for out in written:
        caveats.append("   -> {0}".format(out))
    conn.close()
    return summary, caveats


if __name__ == "__main__":
    sys.exit(main())
