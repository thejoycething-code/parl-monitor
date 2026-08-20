"""Log lifetime campaign performance into the store, for the Briefs to cite.

    python3 tools/log_campaign_performance.py <reply.txt>   # parse + log
    python3 tools/log_campaign_performance.py --show        # collation by area

Source: Max (the ai_campaigner Slack agent), queried in #campaigns-en-gb for
the lifetime EN GB numbers per petition campaign - new members, reactivated,
signatures, launch and last-activity dates. His bullet format is parsed here
and written to campaign_performance, keyed by petition id, so re-logging a
fresher pull just updates rows.

Campaign names are mapped to taxonomy areas by an explicit keyword table,
never guessed: campaigns that match nothing are stored with no area and
listed as unmapped, because a silent guess would quietly misattribute a
campaign's supporters to the wrong topic (the briefs cite these numbers as
evidence). Add mappings here as new campaigns appear.

RF#1 on every generated Brief ("will this fight bring people or money to
our cause?") then cites the lifetime record for the subject's areas: what
previous fights on this topic actually brought, campaign start to end.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

# Explicit, auditable name -> areas map. Multi-area campaigns list every area.
KEYWORD_AREAS = [
    (r"assisted suicide|assisted dying|euthanasia", [2]),
    (r"abortion|pro-life|buffer zone", [1]),
    (r"wedding|marriage|cohabitation", [9]),
    (r"conversion therapy|conversion practices", [4]),
    # \brse\b is ANCHORED BOTH ENDS. Unanchored, "rse\b" matched the tail of
    # Reverse, Nurse, Verse and Morse, filing four campaigns into area 6 --
    # including a nurse's disciplinary case and a blasphemy trial. Area 6 is
    # the largest area, so the noise landed where it was hardest to notice.
    (r"lgbt.*(gcse|school|indoctrination|exam)|sex education|\brse\b", [6]),
    (r"online safety|censor|free speech|police training", [7]),
    (r"christian persecution|street preacher|moodley", [8]),
    (r"surrogacy", [10]),
    (r"gender|puberty blocker|trans(?!port)", [3]),
    (r"drag", [6]),
    (r"sex based|single-sex|women's spaces", [5]),
    (r"criminalising parents|parents opposing|parental", [6]),
    (r"lgbt (teaching|agenda|ideology)|woke.*curriculum|leger", [6]),
    (r"christian|blasphemy|persecut|r\u00e4s\u00e4nen|rasanen|pray|church|faith|bible", [8]),
    # "groom" was here and matched GROOMING PRODUCTS -- its only hit was
    # "Boycott Braun: Grooming brand glamourises mutilation", which still
    # reaches area 3 through "mutilat". It also filed grooming-gang campaigns
    # under gender medicine, which is now area 6 above.
    (r"reassignment|mutilat", [3]),
    (r"withdrawing treatment|let me live", [2]),
    (r"thought.*criminal|criminalis.*thought|hate crime|non-crime", [7]),
    # 2026-08-13 sweep of the unmapped list (Christopher). Explicit, auditable;
    # WHO/UN/pandemic-treaty, digital ID/CBDC, election tools, boycott-only and
    # foreign-policy campaigns stay unmapped as genuinely out-of-taxonomy.
    (r"suicide pod|sarco|care,? not killing|starved|let (archie|pippa)|"
     r"right to life for everyone", [2]),
    (r"pills.by.post|unborn|standing for life", [1]),
    (r"\bivf\b", [10]),
    (r"women'?s (sport|space|shelter|changing)|men out of women|erasing women|"
     r"what is a woman|male and female|joan of arc|male jail|"
     r"men going into women|darlington nurse|\bfeminine\b", [5]),
    (r"pregnant m[ae]n|cross-sex hormone|sutcliffe|detransition", [3]),
    (r"lawful (speech|facebook posts)|linehan|open justice|courtdesk|"
     r"twitter suspends|debate.*silenced|student authoritarians|"
     r"biological facts criminal|police accountable|manhandling|"
     r"banking (discrimination|betrayal)|discriminatory banking|"
     r"language control|harassing caroline", [7]),
    (r"religious freedom|conscien|pastor|jesus|chaplain|sabbath|"
     r"deborah samuel|reverend|rev richard|blasphem", [8]),
    (r"porn|sexualis|sexualiz|summer of sex|bonnie|cuties|family sex show", [6]),
    (r"rshe|ofsted|stonewall|indoctrination|bela bill|"
     r"lgbt.*(children|kids|toddler)|children.*lgbt|"
     r"(disney|netflix|bbc|lego|strictly).*(lgbt|agenda|lifestyle)|"
     r"lgbtq\+? (concert|films|set|agenda)", [6]),
    (r"deport|border|ceuta|dover|asylum|illegal migration", [11]),
    # 2026-08-20, from the widened Looker export. Each gap is a real campaign
    # the list missed, named here so the reason is auditable:
    #   creasy      "Exposing Stella Creasy's danger" -- her decriminalisation
    #               amendments; no local petition row at all, so keywords are
    #               the only route.
    #   csw\d       CSW68/69/70 and CSW67 are one annual series at the UN
    #               Commission on the Status of Women. CSW69 was already
    #               mapped [1] by name because it happened to say "Force
    #               Abortion"; 67, 68 and 70 were unmapped only because their
    #               titles word it differently. Mapping the series follows the
    #               precedent rather than the wording.
    #   parenthood  "Reject EU's Same-Sex Parenthood Certificate" -- the list
    #               had "marriage" and "parental" but not "parenthood".
    #   competition/sport for women  "PDC: Protect Darts Competition for
    #               Women!" -- the existing pattern wanted the possessive
    #               ("women's sport"), which this title does not use. Kept to
    #               these three nouns; a bare "for women" would swallow
    #               anything.
    (r"creasy", [1]),
    (r"\bcsw\d", [1]),
    (r"parenthood", [9]),
    (r"(competition|category|categories|sport) for women", [5]),
    #   \bpupil     "Sacked for Answering a Pupil's Question Honestly" held
    #               area 6 only by the Morse/rse false positive above; this
    #               keeps it, for the actual reason. One hit, no others.
    #               (\bteacher was considered and rejected: it would have added
    #               area 6 to Simon's free-speech sacking, which is area 7.)
    #   primary school  four local campaigns already map to 6 by other words;
    #               the Scottish one reached Looker as a slug that lost them.
    #   keira       "Stand with Keira and James" -- puberty blocker trials.
    #   justice for jennifer  a nurse disciplined over pronouns. Needs a
    #               keyword because the petition id DISAGREES between systems
    #               (15124 in Looker, 15129 locally), so the join misses it.
    # 2026-08-20, area 7 widened to civil liberties (Christopher's decision;
    # docs/keyword-taxonomy.md v0.6). ~400,000 signatures of EN GB campaigning
    # on health sovereignty, digital ID and UN governance had no benchmark.
    # NOTE this list is a SEPARATE lowercase regex layer from the taxonomy and
    # does NOT inherit its all-caps case-sensitivity, which is exactly how
    # "rse\b" came to match "nurse" -- so the acronyms are \b-anchored here.
    (r"pandemic|\bihr\b|\binb\b|international health regulation|"
     r"world health organi", [7]),
    (r"digital id|digital totalitarian|britcard|one login|\bcbdc\b", [7]),
    # UN governance: the flagged pair, one line to strike if unwanted.
    (r"agenda 2030|summit for development", [7]),
    # Aligns the campaign layer with the taxonomy, which already carries
    # Islamophobia and "Islamophobia definition" in area 7. Without this the
    # Islam free-speech campaign reached only area 8 via "blasphem", so the two
    # layers disagreed about the same campaign.
    (r"islamophobia", [7]),
    # 2026-08-20, clearing the residue of the widened Looker export. Each
    # pattern is deliberately narrow, with the campaign it exists for named:
    #   paedophilia   "Stop the UN's Push to Decriminalise Paedophilia"
    #                 (35,085). The NOUN only -- "paedophile" would also catch
    #                 Justice for Jennifer, a pronoun disciplinary case that is
    #                 area 3 and not child protection.
    #   children's rights  "Don't Let the UN Redefine Children's Rights!"
    #                 (33,277). UNCRC.
    #   protected a predator  "Pride in Surrey Protected a Predator" (28,436).
    #                 Narrow on purpose: a bare \bpredator would reach
    #                 "Deport Shabir Ahmed... Protect Our Children From
    #                 Predators", which sits in area 11 -- and area 11 is
    #                 excluded from briefs, so a second area would leak a
    #                 deliberately hidden campaign into area 6.
    #   cancel culture  "Save our Statues: Stop Cancel Culture" (9,119).
    #   life and death vote  "Runcorn and Helsby by-election". By-elections are
    #                 mapped by their SUBJECT here, as Gorton and Denton [3,7]
    #                 and Makerfield [4,3,7] already are.
    #   virgin island  the Channel 4 show, same family as the Netflix and
    #                 Disney content campaigns.
    # Child sexual exploitation -> area 6, child protection (Christopher,
    # 2026-08-20). It previously had FOUR different homes: Telford unmapped,
    # Sadiq Khan unmapped, the grooming-gangs cover-up campaign at area 7 via
    # its open-justice ask, and "Deport Shabir Ahmed" under migration (11).
    # Area 6 tier 2 already carried "grooming gang*" and "child protection" on
    # the parliamentary side, so this aligns the campaign layer with it.
    (r"grooming gang|child sexual (abuse|exploitation)|rape gang|"
     r"sexual abuse|ignoring abuse", [6]),
    # The named CSE towns. No hits today beyond Telford, so no false positives
    # are possible now; included because this is the vocabulary these campaigns
    # actually use when they name a place.
    (r"\btelford\b|\brotherham\b|\brochdale\b|\boldham\b", [6]),
    (r"paedophilia|pedophilia", [6]),
    (r"rights of the child|children'?s rights", [6]),
    (r"protected a predator", [6]),
    (r"cancel culture", [7]),
    (r"life and death vote", [2]),
    (r"virgin island", [6]),
    (r"\bpupil", [6]),
    (r"primary school", [6]),
    (r"\bkeira\b", [3]),
    (r"justice for jennifer", [3]),
]

# Fundraising arrives at SERIES grain (Looker Express Donations by Programs),
# not petition grain, with most series unmatched to a petition id. It is
# stored at its own grain in fundraising_series; petition-level attribution
# is derived only through an explicit related_petition_id, because Max's own
# caveat stands: absent campaigns are "not available in this source", never
# zero, and pre-2025 attribution does not exist in it at all.
SERIES_LINE = re.compile(
    r"^\W*(?P<name>[\w'()/-]+(?:[ ][\w'()/-]+)*)\s*\|\s*"
    r"related_petition_id:\s*(?P<pid>\d+|unmatched)[^|]*\|\s*"
    r"attributed_total_value_eur:\s*(?P<value>[\d,.]+)\s*\|\s*"
    r"one_time_donations:\s*(?P<once>[\d,]+)\s*\|\s*"
    r"monthly_donations:\s*(?P<monthly>[\d,]+)\s*\|\s*"
    r"projected_12_month_value_eur:\s*(?P<mo12>[\d,.]+)", re.I)


LINE = re.compile(
    r"^\W*(?P<name>.+?)\s*\|\s*petition_id:\s*(?P<id>\d+)"
    r"(?:\s*\|\s*launch(?:_date)?:\s*(?P<launch>[\d-]+|n/a|unknown))?"
    r"(?:\s*\|\s*last[_ ]activity(?:_date)?:\s*(?P<last>[\d-]+|n/a|unknown|live))?"
    r"(?:\s*\|\s*(?:lifetime_)?new_members:\s*(?P<new>[\d,]+))?"
    r"(?:\s*\|\s*(?:lifetime_)?reactivated(?:_members)?:\s*(?P<react>[\d,]+))?"
    r"(?:\s*\|\s*(?:lifetime_)?(?:total_)?signatures:\s*(?P<sigs>[\d,]+|n/a|unknown))?"
    r"(?:\s*\|\s*(?:total_)?raised(?:_eur)?:\s*€?(?P<raised>[\d,.]+|n/a|unknown))?"
    r"(?:\s*\|\s*one[_-]?time(?:_donations)?:\s*(?P<once>[\d,]+|n/a|unknown))?"
    r"(?:\s*\|\s*monthly(?:_donations)?:\s*(?P<monthly>[\d,]+|n/a|unknown))?"
    r"(?:\s*\|\s*(?:monthly_)?12mo(?:_value)?(?:_eur)?:\s*€?(?P<mo12>[\d,.]+|n/a|unknown))?",
    re.I)


def ensure_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS campaign_performance ("
                 "petition_id INTEGER PRIMARY KEY, name TEXT, launch_date TEXT, "
                 "last_activity TEXT, new_members INTEGER, reactivated INTEGER, "
                 "signatures INTEGER, areas TEXT, source TEXT, logged_at TEXT)")
    cols = [c[1] for c in conn.execute("PRAGMA table_info(campaign_performance)")]
    # Donations joined in later (RF#1 covers money as well as people); the
    # columns migrate on first touch so older stores upgrade in place.
    for col, typ in (("raised_eur", "REAL"), ("donations_once", "INTEGER"),
                     ("donations_monthly", "INTEGER"),
                     ("monthly_12mo_eur", "REAL"), ("final", "INTEGER")):
        if col not in cols:
            conn.execute("ALTER TABLE campaign_performance ADD COLUMN {0} {1}".format(col, typ))
    conn.execute("CREATE TABLE IF NOT EXISTS fundraising_series ("
                 "series TEXT PRIMARY KEY, related_petition_id INTEGER, "
                 "value_eur REAL, donations_once INTEGER, donations_monthly "
                 "INTEGER, monthly_12mo_eur REAL, areas TEXT, source TEXT, "
                 "logged_at TEXT)")
    conn.commit()


# Campaigns that map to NO area ON PURPOSE. Without this, a settled decision
# is indistinguishable from an unfixed gap, so the same rows get re-litigated
# every time somebody reads the list. Each reason states its own status: some
# are closed, some are open questions for Christopher.
OUT_OF_TAXONOMY = [
    (r"open letter to candidates|local councillors have more power",
     "SETTLED: a generic election tool with no issue subject to benchmark "
     "against. By-elections that DO name a subject are mapped by it."),
    (r"pride progress flag|progress pride flag|remove pride progress|"
     r"divisive.*flag",
     "SETTLED: civic symbolism in the public square. None of the eleven areas "
     "covers flags, and the 2026-08-13 sweep left these out deliberately."),
    (r"^fundraising",
     "SETTLED: a fundraising appeal, not a campaign."),
    (r"\btest[- ]",
     "SETTLED: a test program."),
    (r"children in need",
     "OPEN QUESTION: the name does not say what the funding objection was, so "
     "it cannot be mapped without one line of context."),
]


def _variants(name):
    """The name as written, and with hyphens read as word separators.

    Looker campaign names are program slugs, and punctuation there is arbitrary:
    "Virgin-Island-Scrap-Show" is hyphen-delimited where others are underscore-
    delimited (parse_program folds underscores only). Testing BOTH forms and
    unioning the result fixes the slug case without breaking patterns that want
    a real hyphen -- "pro-life", "single-sex", "non-crime" still match the
    unmodified form.
    """
    low = _fold(name)
    return (low, low.replace("-", " ")) if "-" in low else (low,)


def out_of_taxonomy(name):
    """The recorded reason this campaign maps nowhere, or None if it is a gap."""
    for low in _variants(name or ""):
        for pattern, reason in OUT_OF_TAXONOMY:
            if re.search(pattern, low):
                return reason
    return None


def _fold(name):
    """Lowercase, and fold smart quotes to straight ones.

    src/filter.py already does this for the taxonomy ("Children's" must match
    "Children\u2019s"); KEYWORD_AREAS did not, so any pattern containing an
    apostrophe silently failed on 31 of the 366 campaign names. Nothing was
    affected by luck alone -- until "children'?s rights" was added and matched
    nothing.
    """
    return (name or "").lower().replace("\u2019", "'").replace("\u2018", "'")


def areas_for(name):
    out = []
    for low in _variants(name):
        for pattern, areas in KEYWORD_AREAS:
            if re.search(pattern, low):
                out.extend(a for a in areas if a not in out)
    return out


def _num(v):
    if v is None or str(v).lower() in ("n/a", "unknown", ""):
        return None
    return int(str(v).replace(",", ""))


def _money(v):
    if v is None or str(v).lower() in ("n/a", "unknown", ""):
        return None
    return float(str(v).replace(",", ""))


def parse(text):
    rows = []
    for line in text.splitlines():
        if "petition_id" not in line:
            continue
        m = LINE.search(line)
        if not m:
            continue
        name = m.group("name")
        # Thread exports escape unicode (\u2022 bullets, \u2019 quotes)
        # and can prefix the poster's name; both pollute campaign names.
        name = re.sub(r"\\u([0-9a-fA-F]{4})",
                      lambda mm: chr(int(mm.group(1), 16)), name)
        name = re.sub(r"^.*?Max Hall:\s*", "", name)
        name = re.sub(r"^(?:u2022|[\u2022*>\s_-])+|[_*]+$", "", name).strip()
        rows.append({
            "petition_id": int(m.group("id")), "name": name,
            "launch_date": m.group("launch") if (m.group("launch") or "").count("-") == 2 else None,
            "last_activity": m.group("last") if (m.group("last") or "").count("-") == 2 else None,
            "new_members": _num(m.group("new")),
            "reactivated": _num(m.group("react")),
            "signatures": _num(m.group("sigs")),
            "raised_eur": _money(m.group("raised")),
            "donations_once": _num(m.group("once")),
            "donations_monthly": _num(m.group("monthly")),
            "monthly_12mo_eur": _money(m.group("mo12")),
            "areas": areas_for(name),
        })
    return rows


def collate(conn):
    from src import intel
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    rows = conn.execute("SELECT * FROM campaign_performance").fetchall()
    per_area, unmapped = {}, []
    for r in rows:
        areas = json.loads(r["areas"] or "[]")
        if not areas:
            unmapped.append(r["name"])
        for a in areas:
            agg = per_area.setdefault(a, {"campaigns": 0, "new": 0, "react": 0,
                                          "sigs": 0, "raised": 0.0, "top": None})
            agg["campaigns"] += 1
            agg["new"] += r["new_members"] or 0
            agg["react"] += r["reactivated"] or 0
            agg["sigs"] += r["signatures"] or 0
            agg["raised"] += r["raised_eur"] or 0.0
            if agg["top"] is None or (r["new_members"] or 0) > agg["top"][1]:
                agg["top"] = (r["name"], r["new_members"] or 0)
    for a in sorted(per_area):
        g = per_area[a]
        print("area {0:<2} {1:<28} {2} campaigns | {3:,} new members | "
              "{4:,} reactivated{5}{6} | biggest: {7} ({8:,})".format(
                  a, names.get(a, "?"), g["campaigns"], g["new"], g["react"],
                  " | {0:,} signatures".format(g["sigs"]) if g["sigs"] else "",
                  " | \u20ac{0:,.0f} raised".format(g["raised"]) if g["raised"] else "",
                  g["top"][0], g["top"][1]))
    if unmapped:
        gaps, settled = [], []
        for n in unmapped:
            reason = out_of_taxonomy(n)
            (settled if reason else gaps).append((n, reason))
        if gaps:
            print("\nunmapped and UNEXPLAINED ({0}) - these are gaps, add "
                  "keywords:".format(len(gaps)))
            for n, _ in gaps:
                print("  -", n)
        if settled:
            print("\nmap nowhere ON PURPOSE ({0}) - recorded in "
                  "OUT_OF_TAXONOMY, not gaps:".format(len(settled)))
            for n, reason in settled:
                print("  - {0}\n      {1}".format(n[:72], reason))
    return per_area


def main():
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    ensure_table(conn)
    if "--show" in sys.argv:
        collate(conn)
        return 0
    if "--rederive" in sys.argv:
        # areas is a STORED column, computed by areas_for() at load time, so
        # editing KEYWORD_AREAS changes nothing until this runs. Prints every
        # change rather than a count: a keyword edit that silently reclassified
        # campaigns would move a benchmark with no trace.
        changed = 0
        for r in conn.execute("SELECT petition_id, name, areas FROM "
                              "campaign_performance").fetchall():
            new_areas = areas_for(r["name"])
            if sorted(json.loads(r["areas"] or "[]")) != sorted(new_areas):
                print("  [{0}] {1}\n      {2} -> {3}".format(
                    r["petition_id"], r["name"][:70], r["areas"],
                    json.dumps(new_areas)))
                conn.execute("UPDATE campaign_performance SET areas = ? "
                             "WHERE petition_id = ?",
                             (json.dumps(new_areas), r["petition_id"]))
                changed += 1
        conn.commit()
        print("{0} campaign(s) re-derived.".format(changed))
        return 0
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    text = open(sys.argv[1], encoding="utf-8").read()
    rows = parse(text)
    series = []
    for line in text.splitlines():
        m = SERIES_LINE.search(line)
        if m:
            series.append(m)
    if not rows and not series:
        print("nothing parsed - has Max's format changed?")
        return 1
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for m in series:
        name = m.group("name").strip()
        pid = None if m.group("pid") == "unmatched" else int(m.group("pid"))
        conn.execute(
            "INSERT OR REPLACE INTO fundraising_series VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, pid, _money(m.group("value")), _num(m.group("once")),
             _num(m.group("monthly")), _money(m.group("mo12")),
             json.dumps(areas_for(name.replace("_", " "))),
             "Max (ai_campaigner), Looker Express Donations by Programs; "
             "series grain, from 2025-01-23; absence means not-available", now))
    if series:
        conn.commit()
        print("logged {0} fundraising series".format(len(series)))
    # A campaign is CLOSED - its start-to-end record final, never re-swept -
    # when it has been quiet for 60+ days OR is two years past launch
    # (Christopher, 2026-08-13: an evergreen petition trickling one signer a
    # week is not an open campaign). The monthly check is for newly closed
    # campaigns, not a re-sweep of settled history.
    settled = {r["petition_id"] for r in conn.execute(
        "SELECT petition_id FROM campaign_performance WHERE final = 1")}
    cutoff = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
    two_years = (datetime.date.today() - datetime.timedelta(days=730)).isoformat()
    skipped_final = 0
    for r in rows:
        if r["petition_id"] in settled:
            skipped_final += 1
            continue
        conn.execute(
            "INSERT INTO campaign_performance (petition_id, name, launch_date, "
            "last_activity, new_members, reactivated, signatures, areas, source, "
            "logged_at, raised_eur, donations_once, donations_monthly, "
            "monthly_12mo_eur) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(petition_id) DO UPDATE SET name=excluded.name, "
            "launch_date=excluded.launch_date, last_activity=excluded.last_activity, "
            "new_members=excluded.new_members, reactivated=excluded.reactivated, "
            "signatures=excluded.signatures, areas=excluded.areas, "
            "source=excluded.source, logged_at=excluded.logged_at, "
            # Money columns update only when the pull carried them: a
            # signatures-only re-log must not blank the donation record.
            "raised_eur=COALESCE(excluded.raised_eur, raised_eur), "
            "donations_once=COALESCE(excluded.donations_once, donations_once), "
            "donations_monthly=COALESCE(excluded.donations_monthly, donations_monthly), "
            "monthly_12mo_eur=COALESCE(excluded.monthly_12mo_eur, monthly_12mo_eur)",
            (r["petition_id"], r["name"], r["launch_date"], r["last_activity"],
             r["new_members"], r["reactivated"], r["signatures"],
             json.dumps(r["areas"]), "Max (ai_campaigner), Looker Petitions "
             "Signatures 3.0 + fundraising attribution", now,
             r.get("raised_eur"), r.get("donations_once"),
             r.get("donations_monthly"), r.get("monthly_12mo_eur")))
        closed = ((r["last_activity"] and r["last_activity"] < cutoff)
                  or (r["launch_date"] and r["launch_date"] < two_years))
        if closed:
            conn.execute("UPDATE campaign_performance SET final = 1 "
                         "WHERE petition_id = ?", (r["petition_id"],))
    conn.commit()
    n_final = conn.execute("SELECT COUNT(*) FROM campaign_performance "
                           "WHERE final = 1").fetchone()[0]
    print("logged {0} campaigns ({1} already final, untouched; {2} now "
          "marked final)".format(len(rows) - skipped_final, skipped_final, n_final))
    collate(conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
