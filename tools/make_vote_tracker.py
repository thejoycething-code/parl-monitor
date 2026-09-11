"""Build the MP vote tracker: how every sitting MP voted on our issues.

    python3 tools/make_vote_tracker.py            # build both audiences
    python3 tools/make_vote_tracker.py --candidates   # divisions we could add

Reads config/vote_tracker.yaml (issues, divisions, plain-English meaning
lines) and the archived division payloads in data/raw, and renders the
prototype's view layer from templates/vote-tracker.html.

Vote data comes from the archive, not a refetch: the payloads carry Ayes,
Noes, both sets of tellers AND NoVoteRecorded, which is what lets the tool
keep the distinction that matters most -- no vote recorded is NOT an
abstention, because the Commons does not record abstentions.

Written to partner_site/mp-votes.html (allies) and docs/mp-votes.html
(internal). Same page: it states what members did and what each vote meant,
which is public record either way.
"""

from __future__ import annotations

import datetime
import glob
import gzip
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src import filter as filt
from src import quotes, intel
from src.http import HttpClient
from src.ingest import divisions as div_ingest

TEMPLATE = os.path.join(ROOT, "templates", "vote-tracker.html")
CONFIG = os.path.join(ROOT, "config", "vote_tracker.yaml")
OUTPUTS = (os.path.join(ROOT, "partner_site", "mp-votes.html"),
           os.path.join(ROOT, "docs", "mp-votes.html"))

CODES = (("Ayes", "A"), ("Noes", "N"), ("AyeTellers", "TA"),
         ("NoTellers", "TN"), ("NoVoteRecorded", "X"))


# A Lords division answers in its OWN shape -- contents/notContents, camelCase
# member fields, no NoVoteRecorded block -- while everything downstream of
# here (CODES, party_splits, the votes map) speaks Commons. Normalising once,
# at the edge, is far less invasive than branching in six places, and it is
# how the assisted-dying divisions of 2006 and 2015 reach the page at all.
#
# There is no NoVoteRecorded for the Lords, which matters: absence from a
# Lords division list is not a recorded abstention, so nothing is invented
# to stand in for one.
def lords_to_commons_shape(payload):
    """A Lords division payload, rewritten in the Commons vocabulary."""
    def side(rows):
        out = []
        for m in (rows or []):
            out.append({"MemberId": m.get("memberId"),
                        "Name": m.get("name"),
                        "Party": m.get("party")})
        return out
    return {
        "DivisionId": payload.get("divisionId"),
        "House": "Lords",
        "Title": payload.get("title"),
        "Date": (payload.get("date") or "")[:10],
        "Ayes": side(payload.get("contents")),
        "Noes": side(payload.get("notContents")),
        "AyeTellers": side(payload.get("contentTellers")),
        "NoTellers": side(payload.get("notContentTellers")),
        "NoVoteRecorded": [],
        "AyeCount": payload.get("authoritativeContentCount"),
        "NoCount": payload.get("authoritativeNotContentCount"),
    }


def load_config():
    import yaml
    with open(CONFIG, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def archived_divisions():
    """{division_id: payload} from data/raw, newest file per id winning."""
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*",
                                              "division_cdetail-*.json.gz"))):
        try:
            with gzip.open(path, "rb") as handle:
                payload = json.loads(handle.read().decode("utf-8"))
        except Exception:
            continue
        if payload.get("DivisionId"):
            out[payload["DivisionId"]] = payload
    # Lords divisions, normalised into the same vocabulary on the way in.
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*",
                                              "division_ldetail-*.json.gz"))):
        try:
            with gzip.open(path, "rb") as handle:
                raw = json.loads(handle.read().decode("utf-8"))
        except Exception:
            continue
        if raw.get("divisionId"):
            shaped = lords_to_commons_shape(raw)
            out[shaped["DivisionId"]] = shaped
    return out


def candidates(conn):
    """Divisions in the ledger that could join the tracker, by area."""
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    have = {d["id"] for d in (load_config().get("divisions") or [])}
    rows = conn.execute(
        "SELECT ref, MIN(line) AS line, MIN(date) AS date, MIN(areas) AS areas "
        "FROM mp_events WHERE kind = 'vote' AND ref LIKE 'div:c%' GROUP BY ref "
        "ORDER BY date DESC").fetchall()
    seen = set()
    for r in rows:
        base = r["ref"].rsplit(":", 1)[0]
        div_id = int(base.split("c")[1])
        if base in seen or div_id in have:
            continue
        seen.add(base)
        title = re.sub(r"^Voted (Aye|No): ", "", r["line"] or "")
        if not re.search(r"Reading|New Clause|Amendment \d|Regulations", title):
            continue
        areas = [names.get(a, a) for a in json.loads(r["areas"] or "[]")]
        print("  id {0:5}  {1}  {2:66} {3}".format(
            div_id, r["date"], title[:66], ", ".join(str(a) for a in areas)))
    print("\nAdd the ones worth showing to config/vote_tracker.yaml with meaning "
          "lines a human has written.")


def fetch_missing(payloads, cfg):
    """Fetch any configured division the archive lacks.

    The sweep only archives divisions whose TITLE matched a sweep term, so the
    abortion decriminalisation vote was absent: it sits inside "Crime and
    Policing Bill Report Stage: New Clause 1", which matches nothing in the
    division term list. A division named in the config is wanted by definition,
    so fetch it (and it archives for next time).
    """
    wanted = [d for d in (cfg.get("divisions") or []) if d["id"] not in payloads]
    if not wanted:
        return 0
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    got = 0
    for div in wanted:
        div_id = div["id"]
        # A Lords division comes from a different API in a different shape.
        # Without this it was fetched from the Commons endpoint, which
        # answers 404 for a Lords id -- so a scored Lords division would
        # simply never appear, and say nothing about why.
        lords = (div.get("house") or "commons").lower() == "lords"
        url = ("{0}/Divisions/{1}".format(div_ingest.LORDS_API, div_id) if lords
               else "{0}/division/{1}.json".format(div_ingest.COMMONS_API, div_id))
        try:
            client.get_json(url, "division",
                            "{0}detail-{1}".format("l" if lords else "c", div_id))
            got += 1
        except Exception as exc:
            print("  could not fetch division {0}: {1}".format(div_id, exc))
    return got


MERGE_PARTY = {"Labour (Co-op)": "Labour"}  # whips together, reads together


def party_splits(payload, top=4):
    """[[party, ayes, noes], ...] for the largest parties in a division."""
    tally = {}
    for key, side in (("Ayes", 0), ("Noes", 1)):
        for m in (payload.get(key) or []):
            party = MERGE_PARTY.get(m.get("Party") or "?", m.get("Party") or "?")
            tally.setdefault(party, [0, 0])[side] += 1
    ranked = sorted(tally.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
    return [[p, a, n] for p, (a, n) in ranked[:top]]


def whip_label(d, issue_note, splits):
    """'free' | 'whipped' | {party: label} | None.

    Order: an explicit `whip:` in the config wins; then the editorial text;
    then the bloc arithmetic. The config value may be a single string or a
    per-party map, because WHIPPING IS PER PARTY and a division can be free
    for one side and instructed for the other -- a shape the old single
    value could not express at all (Christopher, 2026-08-24).

    The signed-off wording is authoritative where it speaks (the config
    review checked every claim against the record). Where it is silent,
    the bloc test decides: the two largest parties each voting >=98% one
    way, on opposite sides, is a party-line vote whatever anyone says.
    """
    declared = d.get("whip")
    if isinstance(declared, dict):
        return {str(k): str(v).lower() for k, v in declared.items()}
    if isinstance(declared, str) and declared.strip():
        value = declared.strip().lower()
        if value == "whipped":
            # A bare "whipped" says a whip was on; it does NOT say whose.
            # Applied division-wide it put "WHIPPED" on the page of a Reform
            # UK member for Crime and Policing New Clause 7, a claim nothing
            # in the record supports (Christopher, 2026-08-26). Name the
            # parties the arithmetic can actually identify; if it cannot
            # identify any, make no per-party claim at all.
            return party_line(splits) or {}
        return value
    text = " ".join([d.get("context") or "", issue_note or ""]).lower()
    # Negations first: the signed-off NI contexts say "this was NOT a whipped
    # vote", and a bare substring test read that as whipped (caught on the
    # first build, 2026-08-12).
    if ("not a whipped vote" in text or "not whipped" in text
            or "free vote" in text or "free-vote" in text or "free votes" in text):
        return "free"
    if "whipped" in text:
        return party_line(splits) or {}
    bloc = party_line(splits)
    if bloc:
        # PER PARTY, never division-wide (Christopher, 2026-08-26). The bloc
        # test looks at the two largest parties; saying "WHIPPED" from it on
        # the page of a Reform UK member -- whose party was not measured and
        # may not appear in the splits at all -- claims something we have no
        # evidence for. Only the parties that actually formed the bloc are
        # named, and every other party reads WHIP NOT RECORDED.
        return bloc
    return None


SYNOPSIS_SINCE = re.compile(r"since (\d{1,2}) (\w+) (\d{4})")
_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def continuous_since(synopsis):
    """The start of a member's CURRENT UNBROKEN service, per Parliament.

    Our own first-elected date is the earliest period, which is a different
    claim: Sir Christopher Chope first entered in 1983 but was out from 1992
    to 1997, so "MP since 9 June 1983" implies continuous service he did not
    have. 24 of 650 members differ this way, and Parliament is right in each
    case -- its synopsis says "has been an MP continually since ...".

    The general-election test used for `returned` cannot separate these: a
    member who lost a seat and won another at a LATER election also starts a
    period on an election date. Rather than re-derive that reasoning, this
    reads the date out of the authoritative sentence.
    """
    hit = SYNOPSIS_SINCE.search(synopsis or "")
    if not hit:
        return None
    month = _MONTHS.get(hit.group(2))
    if not month:
        return None
    return "{0}-{1:02d}-{2:02d}".format(hit.group(3), month, int(hit.group(1)))


def party_slug(party):
    """Must match partySlug() in templates/vote-tracker.html."""
    import unicodedata
    text = unicodedata.normalize("NFD", party or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", "and")
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text))


def party_logos():
    """{slug: filename} for logo files that actually exist.

    Detected at BUILD time so the page emits an <img> only where there is
    something to load: a drop-in slot that always emitted one would 404 on
    every member view for every party without a file. Adding a file and
    rebuilding is all it takes -- no list to maintain (Christopher,
    2026-08-27: "make it so we can drop in party logos").
    """
    found = {}
    for site in ("partner_site", "docs"):
        for path in sorted(glob.glob(os.path.join(ROOT, site, "logos", "*"))):
            name = os.path.basename(path)
            stem, ext = os.path.splitext(name)
            if ext.lower() in (".svg", ".png", ".webp", ".jpg", ".jpeg"):
                found.setdefault(stem, name)
    return found


def bill_of(d, issue):
    """The bill a division belongs to, for the card heading.

    The parental-rights card carried the heading "Various", because that is
    what the issue's `bill` says -- and it says that honestly, since the
    issue spans three different bills (Christopher, 2026-08-26). A heading
    describes the vote beneath it, so it is taken from the DIVISION: its
    title with the stage suffix removed, or its short description.
    """
    title = (d.get("title") or "").strip()
    if title:
        # "Children's Wellbeing and Schools Bill: Third Reading" -> the bill
        stage = (d.get("stage") or "").strip()
        if stage and title.lower().endswith(": " + stage.lower()):
            title = title[:-(len(stage) + 2)].strip()
        return title
    short = (d.get("short") or "").strip()
    if short:
        return short
    bill = (issue or {}).get("bill")
    if bill and bill.lower() != "various":
        return bill
    return (issue or {}).get("name") or ""


def party_line(splits, floor=20, share=0.98):
    """{party: 'whipped'} when a division shows the party-line pattern.

    The pattern is the two largest voting parties each going >=98% one way,
    on OPPOSITE sides. Unanimity alone proves nothing -- a party can agree
    without being told to -- but two large parties in perfect and opposite
    unanimity is a party-line vote whatever anyone says.

    Returns only the parties that formed the bloc. A third party voting
    unanimously alongside them is NOT included: it may simply agree.
    """
    two = [x for x in splits[:2] if x[1] + x[2] >= floor]
    if len(two) != 2:
        return None
    sides = []
    for _name, ayes, noes in two:
        total = ayes + noes
        if ayes >= total * share:
            sides.append("aye")
        elif noes >= total * share:
            sides.append("no")
        else:
            return None
    if sides[0] == sides[1]:
        return None
    return {str(two[0][0]): "whipped", str(two[1][0]): "whipped"}



def appg_short(title):
    """'All-Party Parliamentary Group on Dying Well' -> 'Dying Well'.

    The register's titles put the boilerplate in three different places
    ('... Group on X', '... Pro-Life Group', 'X All-Party Parliamentary
    Group'), so this strips the phrase wherever it sits rather than
    pattern-matching one arrangement.
    """
    t = re.sub(r"\bAll-Party Parliamentary\b", "", title or "")
    t = re.sub(r"\bGroup\b", "", t)
    t = re.sub(r"^\s*(?:on|for)\b", "", " ".join(t.split()))
    return " ".join(t.split()).strip(" -")


def appg_role(role):
    """'Chair & Registered Contact' -> 'Chair': the registered-contact half
    is register plumbing, not a parliamentary office."""
    return (role or "").split("&")[0].strip()


# The four ledger areas the page's six issues live in, with public labels.
RECORD_AREAS = {1: "Abortion", 2: "Assisted suicide",
                6: "Parental rights and education",
                7: "Free speech and civil liberties"}
# UK general elections. A membership period beginning on one of these is a
# re-election, not a return from absence.
GENERAL_ELECTIONS = {
    "1979-05-03", "1983-06-09", "1987-06-11", "1992-04-09", "1997-05-01",
    "2001-06-07", "2005-05-05", "2010-05-06", "2015-05-07", "2017-06-08",
    "2019-12-12", "2024-07-04",
}

# How many receipts get the full treatment -- kind chip, quote, source line.
# The REST are not dropped: every receipt is listed in a compact roll behind
# a disclosure, so the section can say "all 54" and mean it.
RECORD_FEATURED = 2
# Peers get more. Their record is ALL they have: an MP's page opens with
# votes and a verdict, while a peer has three Lords divisions from 2006 and
# 2015 and then whatever they have said. Two featured rows is thin for the
# only evidence on the page. The rest still list in the roll either way --
# this decides how many get the full treatment with a quote.
RECORD_FEATURED_PEER = 4
RECORD_CAP = 2          # per MP per area, for receipts NOT tied to a bill;
                        # the counts carry the volume, quotes illustrate it
BILL_QUOTE_CAP = 2      # quotes shown inside a bill card
QUOTE_SHORTLIST = 8     # candidates scanned before ranking
PQ_FLOOR = 80           # a written question is shorter than a speech

# Procedural containers: ways of scheduling business, not subjects. A member
# speaking during "Engagements" (PMQs) has not made a statement about our
# issues by doing so.
PROCEDURAL_TITLE = re.compile(
    r"^(?:topical questions|business of the house|engagements|"
    r"debate on the address|oral answers to questions|points? of order|"
    r"business without debate|speaker'?s statement|prime minister|"
    r"deferred divisions|petitions?|adjournment|royal assent|"
    r"business statement|urgent question|christmas adjournment|"
    r"point of order)\b", re.IGNORECASE)


def _clean_title(line):
    """Strip the ledger's internal dressing: the chip already says SPOKE, and
    "(re: term)" is our matching annotation, not something an MP said."""
    line = " ".join((line or "").split())
    title = re.sub(r"^(Spoke|Asked|Signed EDM|Proposed EDM|Sponsored EDM):\s*", "", line)
    return re.sub(r"\s*\(re: [^)]*\)\s*$", "", title).strip()


SITTING_SUFFIX = re.compile(r"\s*\((?:[A-Za-z][\w-]*(?:\s+[A-Za-z][\w-]*)?)\s+sitting\)\s*$",
                            re.IGNORECASE)


def collapse_sitting(title):
    """'... Bill (Twenty-fifth sitting)' -> '... Bill'.

    Christopher, 2026-08-27: "36 debates for Danny Kruger seems questionable.
    Perhaps it was 36 contributions against multiple debates?"

    He was right to push. Of his 37 distinct area-2 titles, 27 were committee
    sittings of ONE bill -- he sat on that committee, so he attended them all.
    "Spoke in 36 debates" reads as 36 separate occasions across the House
    when it is really 10 subjects, one of which ran to 28 sittings. Counting
    contributions instead is worse: that is 217.

    Handles "Twenty First sitting" as well as "Twenty-first sitting"; the
    Hansard titles are not consistent.
    """
    return SITTING_SUFFIX.sub("", title or "").strip()


def _sitting(title):
    """'... Bill (Twenty-ninth sitting)' -> 'Committee, twenty-ninth sitting'."""
    m = re.search(r"\(([A-Za-z-]+) sitting\)\s*$", title)
    return "Committee, {0} sitting".format(m.group(1).lower()) if m else None


# URLs were the single heaviest thing on the page -- 936KB across 6,826
# rows, more than the quotes themselves -- and most of each one is
# recoverable. A Hansard link is prefix + house + THE ROW'S OWN DATE +
# two GUIDs; a written-question link is prefix + THE ROW'S OWN DATE + a
# uin. Only the parts that vary per row are shipped, and the template
# rebuilds the address. Dashes come out of the GUIDs for the same reason.
HANSARD_LINK = re.compile(
    r"^https://hansard\.parliament\.uk/(Commons|Lords)/(\d{4}-\d\d-\d\d)"
    r"/debates/([0-9A-Fa-f-]+)/#contribution-([0-9A-Fa-f-]+)$")
WRITTEN_Q_LINK = re.compile(
    r"^https://questions-statements\.parliament\.uk/written-questions/"
    r"detail/(\d{4}-\d\d-\d\d)/(\S+)$")


def pack_url(url, dated):
    """Shrink a source link to what the row does not already carry.

    Returns the packed token, or the original URL when it is neither shape
    -- an unrecognised link must still work, so nothing is dropped.
    """
    if not url:
        return None
    hit = HANSARD_LINK.match(url)
    if hit:
        house, when, debate, contrib = hit.groups()
        if when == dated:              # the row's date, so do not repeat it
            return "h{0}:{1}:{2}".format(
                "L" if house == "Lords" else "C",
                debate.replace("-", ""), contrib.replace("-", ""))
        return "H{0}:{1}:{2}:{3}".format(
            "L" if house == "Lords" else "C", when,
            debate.replace("-", ""), contrib.replace("-", ""))
    hit = WRITTEN_Q_LINK.match(url)
    if hit:
        when, uin = hit.groups()
        return "q:{0}".format(uin) if when == dated else "Q:{0}:{1}".format(when, uin)
    return url


UNSOURCED = []


def leaving_dates(conn):
    """member_id -> last day they sat, for members who have left.

    Read from the WHOLE service record, not the periods the page ships:
    those are filtered to ones that can touch a tracked division, so a
    sitting member whose current period was filtered out looked like
    someone who had left in 2024 (22 of them did, on the first build).
    An open-ended period means they are still in the House and gets no
    leaving date -- inventing one would excuse absences that are real.
    """
    out = {}
    for row in conn.execute(
            "SELECT member_id, MAX(COALESCE(ended, '')) AS last_end, "
            "SUM(CASE WHEN ended IS NULL OR ended = '' THEN 1 ELSE 0 END) "
            "AS open FROM member_service GROUP BY member_id"):
        if not row["open"] and row["last_end"]:
            out[row["member_id"]] = row["last_end"]
    return out


def on_record(conn, member_ids, issues, raw, taxonomy, peers=()):
    """What each MP has said, asked and signed -- as receipts, never inferences.

    Returns (words, record).

      words[member][issue_id] -> quotes from debates ON THAT BILL (Option A)
      record[member][area]    -> counts, plus everything else (Option B)

    WHY IT IS SPLIT THIS WAY (Christopher, 2026-08-25). The first build
    grouped receipts under an issue heading, and 160 of them were published
    beneath a second heading that misdescribed them: a speech tagged
    areas [1, 2] rendered the SAME stored excerpt under both "Abortion" and
    "Assisted suicide". Danny Kruger's argument about conscience clauses in
    the assisted dying bill -- which cites the Abortion Act 1967 as precedent
    -- appeared under a heading that said Abortion.

    Keyword matching cannot tell "about X" from "cites X", so the fix is
    structural rather than smarter matching: a quote shown beside a vote comes
    from the bill it is shown beside (matched on the debate title), and EVERY
    quote carries its own debate title. Our grouping organises; the debate
    title attributes. A heading never speaks for the words underneath it.

    The stance table is deliberately not queried. Scores, placements and
    characterisations are campaign intelligence; this output is public.
    """
    import json as _json
    member_ids = {str(x) for x in member_ids}
    # sqlite affinity returns ids as int or str depending on how they were
    # written; this mismatch has now bitten three tools in one week
    area_of = {i["id"]: i.get("area") for i in issues}
    # A title match may be BOUNDED BY DATE (debate_from / debate_until,
    # both inclusive). The Leadbeater and Edwards Bills share one short
    # title -- "Terminally Ill Adults (End of Life) Bill" -- so the title
    # alone cannot say which Bill a debate belongs to. The calendar can: a
    # Bill cannot be debated after its session fell, so everything up to
    # the fall is the first Bill's and everything after is the second's
    # (Christopher, 2026-08-31: "the two Bills' speeches can't mix").
    # str() because YAML hands over unquoted dates as datetime.date.
    stems = {}
    for i in issues:
        ss = [s.lower() for s in (i.get("debate_match") or [])]
        if ss:
            stems[i["id"]] = (ss, str(i.get("debate_from") or ""),
                              str(i.get("debate_until") or "9999-12-31"))

    def patterns(area):
        out = []
        for _tier, items in sorted((taxonomy.terms.get(area) or {}).items()):
            out.extend(it[1] for it in items)
        return out

    pats = {a: patterns(a) for a in RECORD_AREAS}

    rows = conn.execute(
        "SELECT member_id, date, kind, ref, line, areas, excerpt "
        "FROM mp_events WHERE kind != 'vote' AND areas IS NOT NULL "
        "ORDER BY date DESC").fetchall()

    words, record = {}, {}
    for r in rows:
        mid = str(r["member_id"])
        if mid not in member_ids:
            continue
        try:
            areas = [a for a in _json.loads(r["areas"] or "[]")
                     if a in RECORD_AREAS]
        except ValueError:
            continue
        if not areas:
            continue
        title = _clean_title(r["line"])
        if not title or PROCEDURAL_TITLE.match(title):
            # "Engagements", "Topical Questions", "Business of the House":
            # containers, not subjects. 117 of the first build's receipts
            # were these, including a member thanking the Clerks at PMQs
            # filed under Assisted suicide.
            continue

        # which bill card, if any, does this debate belong to?
        low = title.lower()
        on_bill = [iid for iid, (ss, frm, until) in stems.items()
                   if frm <= r["date"] <= until
                   and any(x in low for x in ss)]

        # PROPOSING an early day motion and SIGNING one are different acts,
        # and the stronger of the two was being reported as the weaker: both
        # collapsed to "edm" here, and the count line only knew how to say
        # "signed". Nine blocks credited a member who TABLED a motion with
        # having signed it.
        kind = r["kind"] if r["kind"] in ("edm", "edm-signed") else r["kind"]
        # An event already shown beside the member's vote must not also be
        # counted here. It was excluded from the LIST further down but stayed
        # in the COUNT, so 298 of 1,038 blocks printed "spoke in 1 debate"
        # above an empty list. The count now matches the list exactly --
        # excluded on ANY bill, not just this area's, because a bill title
        # appearing on its card AND under a different area's heading is the
        # same title printed twice on one page. Tried it the other way round
        # first; OnRecordTests caught it.
        for area in areas:
            bucket = record.setdefault(mid, {}).setdefault(str(area), {
                "n": {"debate": 0, "pq": 0, "edm": 0, "edm-signed": 0},
                "items": [], "_seen": set()})
            # COUNT DISTINCT DEBATES, not contributions. Counting raw
            # contributions gave "spoke 216 times" for one member on one
            # issue -- true of interventions, absurd as a public statement,
            # and not what a reader understands "spoke" to mean. A member
            # speaking nine times in one committee sitting spoke once.
            # A bill committee is ONE debate, not one per sitting.
            key = (kind, collapse_sitting(title).lower())
            if key not in bucket["_seen"] and not on_bill:
                bucket["_seen"].add(key)
                bucket["n"][kind] = bucket["n"].get(kind, 0) + 1
            bucket["items"].append({
                "d": r["date"], "k": r["kind"], "t": title[:110],
                "ref": r["ref"], "areas": areas, "on_bill": on_bill,
                "excerpt": " ".join((r["excerpt"] or "").split()),
            })
        for iid in on_bill:
            a = area_of.get(iid)
            if a in areas:
                per = words.setdefault(mid, {}).setdefault(
                    iid, {"items": [], "n": 0, "_sittings": 0, "_seen": set()})
                if title.lower() not in per["_seen"]:
                    per["_seen"].add(title.lower())
                    per["n"] += 1     # distinct titles on THIS bill
                    if SITTING_SUFFIX.search(title):
                        per["_sittings"] += 1
                per["items"].append({
                    "d": r["date"], "t": title[:110], "ref": r["ref"], "a": a})

    # ---- quotes, computed lazily -------------------------------------------
    # Extracting a shareable quote means scanning a full contribution, so it
    # is done only for candidates that can actually be displayed: newest
    # first, stopping once the cap is met.
    def quote_for(ref, area):
        if not ref.startswith("hansard:") or raw is None:
            return None, None
        full, _meta = raw.get(ref)
        if not full:
            return None, None
        return quotes.shareable(full, pats.get(area) or []), raw.url(ref)

    # The written question permalink: dateTABLED + uin, neither of which the
    # ledger row carries. tools/backfill_pq_links.py recovers both from the
    # archived payloads, and ingest now stores them as it goes.
    pq_links = {}
    for row in conn.execute("SELECT pq_id, uin, tabled FROM pq_link"):
        pq_links[row["pq_id"]] = (row["uin"], row["tabled"])

    def pq_url(ref):
        pair = pq_links.get(ref.split(":", 1)[1] if ":" in ref else ref)
        if not pair:
            return None
        return ("https://questions-statements.parliament.uk"
                "/written-questions/detail/{0}/{1}".format(pair[1], pair[0]))

    for mid, per_issue in words.items():
        for iid, per in per_issue.items():
            items = sorted(per["items"], key=lambda x: x["d"], reverse=True)
            # Rank a shortlist rather than taking the newest that parses:
            # recency picked a request for the Minister to confirm a statutory
            # instrument over the same member saying what he actually
            # believed. Only the shortlist is scanned, so the cost stays
            # bounded.
            cands, seen = [], set()
            for it in items[:QUOTE_SHORTLIST]:
                q, url = quote_for(it["ref"], it["a"])
                if not q or q in seen:
                    continue
                seen.add(q)
                cands.append({"d": it["d"], "q": q,
                              "u": pack_url(url, it["d"]),
                              "t": _sitting(it["t"]) or it["t"],
                              "_s": quotes.quotability(q)})
            cands.sort(key=lambda x: (x["_s"], x["d"]), reverse=True)
            # Spread across DEBATES: both of Kruger's quotes were labelled
            # "Committee, twenty-ninth sitting", which reads like the same
            # remark printed twice. A second debate is worth more than a
            # marginally better sentence from one already quoted.
            kept, used = [], set()
            for c in cands:
                if len(kept) >= BILL_QUOTE_CAP:
                    break
                if c["t"] in used:
                    continue
                used.add(c["t"])
                kept.append({k: v for k, v in c.items() if k != "_s"})
            for c in cands:                    # only one debate available
                if len(kept) >= BILL_QUOTE_CAP:
                    break
                entry = {k: v for k, v in c.items() if k != "_s"}
                if entry not in kept:
                    kept.append(entry)
            # Label them for what they are: a committee that met 29 times is
            # 29 SITTINGS of one bill, not 29 debates.
            per_issue[iid] = {"q": kept, "n": per["n"],
                              "unit": "sitting" if per["_sittings"] > per["n"] / 2
                                      else "debate"}
        words[mid] = {k: v for k, v in per_issue.items()
                      if v["q"] or v["n"]}

    # Christopher, 2026-08-28: option A, "but with all speeches covered under
    # a collapsable list". Two things follow. The featured rows are chosen by
    # EVIDENCE STRENGTH rather than by date -- 88 blocks led with a bare row
    # while a quote sat below it -- and every receipt, not just the featured
    # two, is listed in a roll behind a disclosure.
    STRENGTH = {"debate": 4, "edm": 3, "pq": 2, "edm-signed": 1}

    for mid, per_area in record.items():
        for area, block in per_area.items():
            items = block["items"]
            # Deduplicate ONCE, here, so the featured rows and the roll are
            # drawn from the same list and cannot disagree about what exists.
            uniq, seen = [], set()
            for it in items:
                # The SAME key the count uses. Keying the roll on the raw
                # title while the count collapsed committee sittings made
                # the two disagree: "spoke in 8 debates" above a list of 29
                # numbered sittings of one bill.
                key = (it["k"], collapse_sitting(it["t"]).lower())
                if key in seen:
                    continue          # one receipt per debate, not per speech
                if it["on_bill"]:
                    continue          # already shown beside its vote
                seen.add(key)
                uniq.append(it)

            # Quote extraction scans a full contribution, so it runs on a
            # bounded shortlist rather than all 54 -- ranked by date first,
            # since a recent speech is the more useful one to quote.
            quoted, scanned = {}, 0

            def pq_quote(it):
                """A written question's own words, whole sentences, when they
                say more than the heading. One helper, used for RANKING and
                for the featured row, so the two cannot disagree."""
                ex = it.get("excerpt")
                if ex and ex.lower() not in it["t"].lower():
                    q = quotes.trim_to_sentence(ex, floor=PQ_FLOOR)
                    # The same bar a speech clears: a passage that ends in a
                    # question is rarely a position. The question path never
                    # applied it, and ranking questions by their quotes
                    # promoted one straight onto the page (2026-09-07).
                    return q if quotes.usable(q) else None
                return None

            # A quoted question outranks a bare speech (2026-09-07): the
            # rank counted only DEBATE quotes, so the first page rebuilt
            # from a current store led 54 blocks with an unquoted row while
            # a quoted question sat below it -- the very thing the
            # strength-not-date ordering was meant to end.
            for it in uniq:
                if it["k"] == "pq":
                    q = pq_quote(it)
                    if q:
                        quoted[id(it)] = (q, pq_url(it["ref"]))
            for it in uniq:
                # Count the shortlist in DEBATES, not in items. Counting
                # items meant a block whose eight newest receipts were EDM
                # signatures scanned no debate at all, however many it had.
                if it["k"] != "debate":
                    continue
                if scanned >= QUOTE_SHORTLIST:
                    break
                scanned += 1
                q, url = quote_for(it["ref"], int(area))
                if q:
                    quoted[id(it)] = (q, url)

            ranked = sorted(
                uniq,
                key=lambda x: (1 if id(x) in quoted else 0,
                               STRENGTH.get(x["k"], 0), x["d"]),
                reverse=True)

            def compact(it):
                """A roll entry: what it was, what it was called, and where."""
                entry = {"d": it["d"], "k": it["k"], "t": it["t"]}
                if it["ref"].startswith("edm:"):
                    entry["e"] = it["ref"].split(":", 1)[1]
                elif it["k"] == "pq":
                    u = pq_url(it["ref"])
                    if u:
                        entry["u"] = pack_url(u, it["d"])
                elif it["k"] == "debate" and raw is not None:
                    u = raw.url(it["ref"])       # metadata only, no text scan
                    if u:
                        entry["u"] = pack_url(u, it["d"])
                return entry

            # THE ROLL HOLDS EVERYTHING (two tests pin it), so a row
            # Hansard gives no URL for stays -- it is still this member's
            # record. It is COUNTED instead, because a row the reader
            # cannot check is a real cost and the build should say how
            # many there are rather than let the number drift.
            block["all"] = []
            for it in ranked:
                row = compact(it)
                block["all"].append(row)
                if not row.get("u") and not row.get("e"):
                    UNSOURCED.append((mid, it["k"], it["t"]))

            kept = []
            for it in ranked:
                if len(kept) >= (RECORD_FEATURED_PEER if mid in peers
                                 else RECORD_FEATURED):
                    break
                q, url = quoted.get(id(it), (None, None))
                if it["k"] == "debate" and not q:
                    # No quotable passage. The title and the Hansard link are
                    # a receipt on their own -- weaker than a quote, still
                    # checkable -- so the row is kept rather than silently
                    # dropped, which is what used to leave a block saying
                    # "spoke in 1 debate" above nothing at all.
                    url = raw.url(it["ref"]) if raw is not None else None
                    if not url:
                        continue          # nothing to show and nowhere to go
                elif it["k"] == "pq":
                    url = pq_url(it["ref"])
                    # The question text IS the member's own words, but it
                    # often just repeats the subject heading -- and unlike a
                    # speech it has no full-text source on disk, so the
                    # ledger's 260-character slice is all there is. Cut it
                    # back to whole sentences like everything else (a lower
                    # floor than a speech: a question is one sentence, ~115
                    # chars). Same helper as the ranking above.
                    q = pq_quote(it)
                entry = {"d": it["d"], "k": it["k"], "t": it["t"]}
                if q:
                    entry["q"] = q
                if url:
                    entry["u"] = pack_url(url, it["d"])
                if it["ref"].startswith("edm:"):
                    entry["e"] = it["ref"].split(":", 1)[1]
                kept.append(entry)
            block["items"] = kept
            block.pop("_seen", None)   # build-time only, never shipped

    # A block with no rows AND no counts renders as nothing -- the template
    # has always filtered it -- but it still shipped in the payload. Once
    # the counts stopped including what the vote cards show, 140 blocks fell
    # to all-zero. Drop them here rather than ship dead weight to 650 pages.
    for mid in list(record):
        for area in list(record[mid]):
            block = record[mid][area]
            # No rows means nothing to show, whatever the counts say.
            #
            # I first explained this by saying RawHansard indexes only the
            # COMMONS sweeps, so a Lords contribution had neither text nor a
            # link. That is FALSE, and measuring it says so: of 7,475
            # classified peer debate contributions, 7,470 have both full
            # text and a resolvable Hansard link. Five do not. The archive
            # covers the Lords perfectly well.
            #
            # The rule stands on its own without the story: a block that
            # ends with no rows promises a receipt it cannot produce,
            # whatever emptied it.
            if not block["items"]:
                del record[mid][area]
        if not record[mid]:
            del record[mid]
    return words, record


def build(conn, cfg, payloads):
    issues = cfg.get("issues") or []
    issue_notes = {i["id"]: i.get("note", "") for i in issues}

    # What happens NEXT, from the weekly bills board (Christopher,
    # 2026-08-31). An issue naming a board_id gets the board's forward date
    # attached, so the card can say "Next: 2nd reading, 11 September 2026"
    # without anyone hand-editing a status line when the date moves. Only a
    # LIVE row with a real date ships anything -- "TBA" is the board's honest
    # "unknown", and a closed bill's story belongs to the editorial status.
    for issue in issues:
        bid = issue.get("board_id")
        if not bid:
            continue
        row = conn.execute(
            "SELECT house, stage, status, next_key_date, what_next "
            "FROM bills_board WHERE bill_id = ?", (bid,)).fetchone()
        alive = bool(row) and row["status"] == "live"
        # The band tracks the BILL's life, not the absence of divisions
        # (Christopher, 2026-08-31: after 11 September the vote belongs in
        # The Record AND the Bill stays in LIVE NOW). `live` keeps an issue
        # in the band until its board row closes, divisions or none.
        issue["live"] = alive
        if row is None:
            print("  issue {0}: board_id {1} is not on the bills board -- "
                  "no forward date will show".format(issue["id"], bid))
        elif alive and re.match(r"\d{4}-\d\d-\d\d$", row["next_key_date"] or ""):
            issue["next"] = {"stage": row["what_next"] or row["stage"],
                             "house": row["house"],
                             "date": row["next_key_date"]}
        # The official bill page, for the LIVE NOW band's title link. The
        # board id IS the bills.parliament.uk id, so this costs nothing.
        if row is not None:
            issue["bill_url"] = "https://bills.parliament.uk/bills/{0}".format(bid)
        # The action dies only when the BILL has (Christopher, 2026-08-31:
        # "the petition only dies once the Bill has"). The first cut retired
        # it whenever the row was not provably live -- so a board hiccup, or
        # the gap between a bill falling at prorogation and its fresh
        # successor being re-pointed, would have silently pulled a live
        # petition from 1,144 pages. The default is now the other way up:
        # the button stays until the board SAYS the Bill ended.
        #
        # "Ended" is status='closed', whichever way it went -- a Bill that
        # fell is dead, and a Bill given Royal Assent is beyond stopping, so
        # a "stop the Bill" button would mislead either way. The log names
        # the outcome; a missing row keeps the button and says so, because
        # absence of evidence is not a death certificate.
        if issue.get("action") and row is not None and row["status"] == "closed":
            del issue["action"]
            print("  issue {0}: action retired -- board {1} is closed"
                  .format(issue["id"], bid))
        elif issue.get("action") and row is None:
            print("  issue {0}: board {1} missing; the action stays up until "
                  "the board records the Bill's end".format(issue["id"], bid))

    # Every action link that survives carries the monitor's tracking mark
    # (Christopher, 2026-08-31: "All petition UTMs from the parliamentary
    # monitor should include cgo-monitor somewhere"). Stamped at BUILD time
    # so the config URLs stay clean and no future action can ship untracked
    # by forgetting the parameters. A URL already carrying utm_ parameters
    # is left alone: a hand-tuned link wins over the default. utm_campaign
    # is cgo-monitor-<issue id>: the issue id says which card converted, and
    # the prefix keeps the monitor findable in a campaign-level report too
    # (Christopher, 2026-08-31: "cgo-monitor also in the campaign utm").
    for issue in issues:
        act = issue.get("action")
        if act and act.get("url") and "utm_" not in act["url"]:
            act["url"] += ("&" if "?" in act["url"] else "?") + \
                "utm_source=cgo-monitor&utm_medium=referral" + \
                "&utm_campaign=cgo-monitor-{0}".format(issue["id"])
    used_issues, divisions, votes = set(), [], {}
    missing = []
    for d in cfg.get("divisions") or []:
        payload = payloads.get(d["id"])
        if payload is None:
            missing.append(d["id"])
            continue
        used_issues.add(d["issue"])
        for key, code in CODES:
            for m in (payload.get(key) or []):
                votes.setdefault(m["MemberId"], {})[d["id"]] = code
        splits = party_splits(payload)
        our = str(d.get("our_side") or "").lower()
        divisions.append({
            "splits": splits,
            "whip": whip_label(d, issue_notes.get(d["issue"]), splits),
            # 'good' drives the internal build's GOOD/BAD VOTE chips. The
            # partner build strips it before writing (facts only in public),
            # so flipping the public page later is a one-line decision, not
            # a rebuild of anything.
            # AND ONLY WHEN SIGNED OFF. signed_off gated nothing before: the
            # tool warned that a division was unapproved and then shipped its
            # verdict anyway. The page already knows how to show a division
            # with no verdict -- "FOR THE RECORD, not scored" -- which is
            # exactly what an unapproved one should be. 2026-08-29, when the
            # three Lords divisions were scored from the campaign's settled
            # position but not by Christopher.
            "good": (our if our in ("aye", "no") and d.get("signed_off")
                     else None),
            "id": d["id"], "issue": d["issue"], "date": (payload.get("Date") or "")[:10],
            "stage": d["stage"], "stage_group": d.get("stage_group", d["stage"]),
            "landmark": bool(d.get("landmark")), "context": d.get("context", ""),
            # Which chamber divided. The page needs it to know who could
            # have voted: without it every MP is marked absent from a Lords
            # division and every peer from a Commons one.
            "house": (d.get("house") or "commons").lower(),
            "title": payload.get("Title"), "short": d["short"],
            "bill": bill_of({"title": payload.get("Title"), "short": d["short"],
                             "stage": d["stage"]},
                            next((i for i in issues if i["id"] == d["issue"]), None)),
            "ayes": payload.get("AyeCount"), "noes": payload.get("NoCount"),
            "passed": (payload.get("AyeCount") or 0) > (payload.get("NoCount") or 0),
            "meaning_aye": d["meaning_aye"], "meaning_no": d["meaning_no"],
            "signed_off": bool(d.get("signed_off")),
            # The official record, IN THE DIVISION'S OWN HOUSE. This was
            # hardcoded /Commons/, so a Lords division's link landed on
            # whatever unrelated Commons division shared its number --
            # Lord Alton's assisted-dying rows pointed at other business
            # entirely (Christopher, 2026-08-31).
            "url": "https://votes.parliament.uk/Votes/{0}/Division/{1}".format(
                "Lords" if (d.get("house") or "commons").lower() == "lords"
                else "Commons", d["id"]),
        })

    # Deputy Speakers identify themselves in the payloads: their listed party
    # is "Deputy Speaker". They do not vote, so their blank record is a role,
    # not a choice.
    deputies = {m["MemberId"] for p in payloads.values() for key, _ in CODES
                for m in (p.get(key) or []) if m.get("Party") == "Deputy Speaker"}

    # Real service history (member_service), not members.since -- which is
    # only the CURRENT period and reads "MP since 4 July 2024" on the page of
    # a member first elected in 1983. Only periods that can touch a tracked
    # division are shipped; `first` carries the rest.
    earliest = min([d["date"] for d in divisions] or ["1900-01-01"])
    service = {}
    for row in conn.execute(
            "SELECT member_id, started, ended FROM member_service "
            "ORDER BY member_id, started"):
        rec = service.setdefault(row["member_id"], {"first": None, "periods": [],
                                                    "returned": None})
        if rec["first"] is None or row["started"] < rec["first"]:
            rec["first"] = row["started"]
        if row["ended"] is None or row["ended"] >= earliest:
            rec["periods"].append([row["started"], row["ended"]])
    # Parliament records each Parliament as a SEPARATE membership period, so
    # every member re-elected in 2024 has a period starting 2024-07-04 and a
    # gap of roughly five weeks before it -- the dissolution. That is not a
    # break in service, and calling it one put "returned 4 Jul 2024" on 313
    # pages. The gap tells us nothing: Farage's genuine absence was 36 days,
    # a dissolution is 35. What distinguishes them is whether the period
    # begins AT a general election.
    for rec in service.values():
        starts = sorted(p[0] for p in rec["periods"]) or []
        current = starts[-1] if starts else None
        if (current and current != rec["first"]
                and current not in GENERAL_ELECTIONS):
            rec["returned"] = current

    # Party AT THE TIME of each division: a whip is a party instruction, and
    # members.party is only today's. Spells ending before the earliest tracked
    # division are dropped; spells STARTING AFTER THE LATEST ONE ARE KEPT,
    # which is a change (2026-08-31). They used to be dropped as unable to
    # touch a division, which was true for the whip -- but the page now also
    # DISPLAYS the history ("Conservative until 15 Sep 2025"), and a member
    # who crosses the floor after the last tracked vote is exactly the member
    # whose card most needs the note: their old votes sit under a new party.
    #
    # Adjacent same-party spells are collapsed. Parliament records each
    # Parliament as a separate membership, so nearly every member has one
    # spell per election of the SAME party -- shipped raw, the display logic
    # would have to re-derive "did anything actually change" on every render.
    # Collapsing across the dissolution gap is safe for the whip lookup too:
    # no division is held while Parliament is dissolved.
    parties = {}
    for row in conn.execute(
            "SELECT member_id, party, started, ended FROM member_party "
            "ORDER BY member_id, started"):
        if row["ended"] is not None and row["ended"] < earliest:
            continue
        spells = parties.setdefault(row["member_id"], [])
        if spells and spells[-1][0] == row["party"]:
            spells[-1][2] = row["ended"]
        else:
            spells.append([row["party"], row["started"], row["ended"]])

    # Published profile detail (member_contact / member_post / member_seat).
    # All of it is the register the member gave Parliament FOR publication;
    # no address is stored or shipped. Absent for a member is normal --
    # only 55% publish an X handle -- so the page renders what exists.
    contact = {}
    for row in conn.execute("SELECT member_id, kind, value FROM member_contact"):
        contact.setdefault(row["member_id"], {})[row["kind"]] = row["value"]
    posts = {}
    for row in conn.execute(
            "SELECT member_id, kind, name FROM member_post "
            "WHERE ended IS NULL ORDER BY member_id, kind, name"):
        posts.setdefault(row["member_id"], {}).setdefault(row["kind"], []).append(row["name"])
    seat = {}
    for row in conn.execute(
            "SELECT member_id, majority, electorate, turnout, result, "
            "election_date, synopsis FROM member_seat"):
        seat[row["member_id"]] = {
            "majority": row["majority"], "electorate": row["electorate"],
            "turnout": row["turnout"], "result": row["result"],
            "date": row["election_date"]}
        # The synopsis itself is not shipped -- it restates the party, seat
        # and date the header already carries. Only the one fact it knows
        # better than we do is taken from it.
        cont = continuous_since(row["synopsis"])
        if cont:
            seat[row["member_id"]]["continuous"] = cont

    # Declared interests: a COUNT and the official link, nothing more. The
    # detail (donor, value) stays in the store for campaign research; the
    # public page points at the register Parliament itself publishes,
    # which is both lighter and unarguable (Christopher, 2026-08-31).
    interests = {r["member_id"]: r["n"] for r in conn.execute(
        "SELECT member_id, COUNT(*) AS n FROM member_interest "
        "GROUP BY member_id")}

    # APPG offices from the LATEST register edition only -- the register is
    # a snapshot, and an office held in a superseded edition is history,
    # not a current fact. Unresolved names (member_id NULL) never reach a
    # page: a pill must belong to the member whose page it is on.
    appg = {}
    for row in conn.execute(
            "SELECT member_id, group_name, role FROM appg_officers "
            "WHERE edition = (SELECT MAX(edition) FROM appg_officers) "
            "AND member_id IS NOT NULL ORDER BY group_name"):
        appg.setdefault(row["member_id"], []).append(
            {"g": appg_short(row["group_name"]), "r": appg_role(row["role"])})

    # PEERS, added 2026-08-29. The store already held 50,066 peer events,
    # 49,655 of them classified onto our areas, and the page published none
    # of it -- while the Bill this campaign is about died in the Lords.
    #
    # A peer is included ONLY if they have classified evidence. Every MP is
    # rendered whether or not they have a record, because a constituent
    # looks up their own MP and must find them; nobody "has" a peer, so a
    # peer with nothing to show is weight on 650 other pages for no reader.
    peers_with_record = {r[0] for r in conn.execute(
        "SELECT DISTINCT e.member_id FROM mp_events e "
        "JOIN members m ON m.id = e.member_id "
        "WHERE m.current_peer = 1 AND e.kind != 'vote' "
        "AND e.areas IS NOT NULL AND e.areas NOT IN ('[]', '')")}

    # FORMER MEMBERS WHO VOTED. 344 MPs cast votes in divisions this page
    # tracks and have since left -- Mike Amesbury, Steve Tuckwell, Stephen
    # Flynn among them -- and a sitting-only list published none of it,
    # including their votes on the assisted dying Bill. They are listed
    # and labelled: a reader searching a name finds the vote, and a
    # reader searching a SEAT still reaches the member who holds it now.
    former_voters = {r[0] for r in conn.execute(
        "SELECT DISTINCT e.member_id FROM mp_events e "
        "JOIN members m ON m.id = e.member_id "
        "WHERE e.kind = 'vote' AND e.ref LIKE 'div:c%' "
        "AND COALESCE(m.current_mp, 0) = 0 "
        "AND COALESCE(m.current_peer, 0) = 0")}

    left_dates = leaving_dates(conn)
    members = []
    for r in conn.execute(
            "SELECT id, name, list_as, party, seat, since, current_mp, "
            "current_peer, house FROM members "
            "WHERE current_mp = 1 OR current_peer = 1 OR id IN ({0}) "
            "ORDER BY COALESCE(list_as, name)".format(
                ",".join("?" * len(former_voters)) or "NULL"),
            tuple(former_voters)):
        is_former = not r["current_mp"] and not r["current_peer"]
        is_peer = (not r["current_mp"] and r["current_peer"]) or (
            is_former and r["house"] == "Lords")
        if is_peer and r["id"] not in peers_with_record:
            continue
        party = "Labour" if r["party"] == "Labour (Co-op)" else r["party"]
        role = None
        if party == "Speaker":
            role = "speaker"
        elif r["id"] in deputies:
            role = "deputy"
        elif party and party.startswith("Sinn F"):
            role = "sf"
        members.append({
            "id": r["id"], "name": r["name"], "listAs": r["list_as"] or r["name"],
            # A peer has no constituency, no majority, no whip in the Commons
            # sense and -- until a Lords division is signed off -- no scored
            # vote. The house is shipped so the page can stop claiming any of
            # those about them rather than rendering blanks.
            "house": "lords" if is_peer else "commons",
            "former": is_former,
            "party": party, "constituency": None if is_peer else r["seat"],
            "since": r["since"],
            "first": service.get(r["id"], {}).get("first"),
            "served": service.get(r["id"], {}).get("periods") or [],
            "returned": service.get(r["id"], {}).get("returned"),
            # WHEN THEY LEFT, for the 345 former members whose service
            # Parliament does record. Without it the page could only say
            # "we cannot date their departure" and had to treat every
            # division after they went as unknowable. Only set when every
            # period has ended -- an open period means they are still in.
            "left": left_dates.get(r["id"]) if is_former else None,
            "parties": parties.get(r["id"]) or [],
            "contact": contact.get(r["id"]) or {},
            "posts": posts.get(r["id"]) or {},
            "seat": seat.get(r["id"]) or {},
            "role": role, "votes": votes.get(r["id"], {}),
            "interests": interests.get(r["id"], 0),
            "appg": appg.get(r["id"], []),
        })

    raw = quotes.RawHansard(ROOT)
    taxonomy = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    words, record = on_record(conn, {m["id"] for m in members},
                              issues, raw, taxonomy,
                              peers={str(m["id"]) for m in members
                                     if m["house"] == "lords"})
    for m in members:
        m["words"] = words.get(str(m["id"]), {})
        m["record"] = record.get(str(m["id"]), {})

    # A peer earns a page by having something ON it. Selecting on "has a
    # classified event" was not enough: on_record drops what a vote card
    # already shows and what has no quotable passage, so 68 peers came
    # through with an empty record -- a page with a name and nothing else.
    # Every MP still renders regardless: a constituent must find their own
    # MP, and finding an empty page is itself an answer.
    before = len(members)
    members = [m for m in members
               if m["house"] == "commons" or m["record"] or m["words"]
               or m["votes"]]
    dropped = before - len(members)
    peers_kept = sum(1 for m in members if m["house"] == "lords")
    print("members: {0} MPs + {1} peers ({2} peer(s) dropped as empty)".format(
        len(members) - peers_kept, peers_kept, dropped))

    # EVERY live bill, for the Order Paper panel on the landing page and
    # the LIVE NOW band on member cards (Christopher, 2026-08-31, choosing
    # mockups A and D). No cap and no dated-only filter -- the old
    # four-event strip could never show the Hospice Funding Bill or the
    # undated Lords Bill at all. Two exclusions, both deliberate:
    #   - hidden areas: migration is captured but never published
    #     (Christopher, 2026-08-06), and the Immigration and Asylum Bill
    #     sits live on the board with a TBA date -- without this filter
    #     the panel would have been the first place it leaked;
    #   - past-dated rows: a stale date is board lag, not business.
    today = datetime.date.today().isoformat()
    hidden = {str(a) for a in (cfg.get("hidden_areas") or [])}
    live_bills = []
    for row in conn.execute(
            "SELECT bill_id, title, house, COALESCE(what_next, stage) AS stage, "
            "next_key_date AS date, areas FROM bills_board "
            "WHERE status = 'live' "
            "ORDER BY (next_key_date GLOB '[0-9]*') DESC, next_key_date, title"):
        bill_areas = {a.strip() for a in (row["areas"] or "").split(",")
                      if a.strip()}
        if bill_areas & hidden:
            continue
        dated = bool(re.match(r"\d{4}-\d\d-\d\d$", row["date"] or ""))
        if dated and row["date"] < today:
            continue
        live_bills.append({"id": row["bill_id"], "title": row["title"],
                           "house": row["house"], "stage": row["stage"],
                           "date": row["date"] if dated else None})

    # Once the stage the band was counting down to HAS divided, the promise
    # is a fact: the date block gives way to the result and the stakes line
    # goes. Found 2026-09-11 an hour after the Second Reading vote, when the
    # band still read "2ND READING · TODAY" over a Bill the Commons had just
    # defeated 270-286. The board row lags the Chamber; the division does not.
    for issue in issues:
        nxt = issue.get("next")
        if not nxt:
            continue
        held = [d for d in divisions if d["issue"] == issue["id"] and d.get("date")
                and d["date"] >= nxt["date"] and d.get("house", "commons") == (nxt.get("house") or "Commons").lower()]
        if held:
            latest = max(held, key=lambda d: d["date"])
            issue["result"] = {"stage": latest["stage"], "date": latest["date"],
                               "ayes": latest.get("ayes"), "noes": latest.get("noes"),
                               "passed": bool(latest.get("passed"))}
            issue.pop("next", None)
            issue.pop("decides", None)

    dataset = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + " local",
        "live_bills": live_bills,
        # An issue ships if a division uses it OR it is marked `upcoming` --
        # a Bill before Parliament that has not divided yet, rendered as a
        # card with status, forward look and action but no votes. That is
        # how the 2026 assisted-suicide Bill gets its own card instead of
        # riding on the fallen Leadbeater Bill's (Christopher, 2026-08-31:
        # "they are two separate Bills").
        "issues": [i for i in issues
                   if i["id"] in used_issues or i.get("upcoming")
                   or i.get("live")],
        "areas": {str(k): v for k, v in RECORD_AREAS.items()},
        "logos": party_logos(),
        "divisions": sorted(divisions, key=lambda d: (d["issue"], d["date"])),
        "members": members,
    }
    return dataset, missing


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    if "--candidates" in sys.argv:
        candidates(conn)
        return 0

    cfg = load_config()
    payloads = archived_divisions()
    if fetch_missing(payloads, cfg):
        payloads = archived_divisions()   # re-read: the fetch archived them
    dataset, missing = build(conn, cfg, payloads)
    conn.close()

    if not dataset["members"]:
        print("no sitting MPs in the cache - run tools/pull_commons_roster.py first")
        return 1
    if missing:
        print("no archived payload for division(s) {0}: they are omitted. Capture "
              "them by running the divisions backfill, then rebuild.".format(missing))

    with open(TEMPLATE, encoding="utf-8") as handle:
        template = handle.read()
    # The sign-off line is derived, never hardcoded: a fixed "pending sign-off"
    # sentence stayed on the page after every division had been signed off,
    # telling readers the summaries were unchecked when they had been.
    pending = [d["id"] for d in dataset["divisions"] if not d["signed_off"]]
    if pending:
        signoff = ("{0} of {1} summaries are still pending editorial sign-off."
                   .format(len(pending), len(dataset["divisions"])))
    else:
        signoff = ("Every summary on this page has been checked against Hansard "
                   "and the official division record, and signed off editorially.")
    # Verdicts are PUBLIC (Christopher, 2026-08-24, reversing his 2026-08-12
    # decision to keep them internal while the site was passwordless). Both
    # builds now carry `good`, so the public page names a vote good or bad
    # rather than reporting the lobby and leaving the reader to judge. That
    # makes this a campaigning page, not only a transparency one -- a
    # deliberate change of what the page IS, asked for twice.
    #
    # A division with no `our_side` in config/vote_tracker.yaml still shows
    # no verdict, so the honest gap stays visible rather than defaulting to
    # a judgement nobody made.
    for path, ds in ((OUTPUTS[0], dataset), (OUTPUTS[1], dataset)):
        page = (template.replace("__DATASET__", json.dumps(ds, separators=(",", ":")))
                        .replace("__SIGNOFF__", signoff))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)

    unsigned = [d["id"] for d in dataset["divisions"] if not d["signed_off"]]
    # A FORMER Member has no start date by definition, so counting them
    # here turned a real warning ("the roster needs re-pulling") into 344
    # of noise the moment the page began listing them.
    no_since = sum(1 for m in dataset["members"]
                   if not m["since"] and not m.get("former"))
    former = sum(1 for m in dataset["members"] if m.get("former"))
    print("{0} divisions across {1} issues, {2} sitting member(s) and {3} "
          "former who voted".format(
              len(dataset["divisions"]), len(dataset["issues"]),
              len(dataset["members"]) - former, former))
    print("  roles: {0} speaker, {1} deputy, {2} Sinn Fein".format(
        *[sum(1 for m in dataset["members"] if m["role"] == r)
          for r in ("speaker", "deputy", "sf")]))
    if no_since:
        print("  {0} MPs without a start date: 'Not yet an MP' cannot be shown "
              "for them until the roster is re-pulled".format(no_since))
    if unsigned:
        print("  {0} of {1} divisions are NOT editorially signed off; the page "
              "carries the pending notice".format(len(unsigned), len(dataset["divisions"])))
    if UNSOURCED:
        print("  {0} roll row(s) carry no link or quotation: Hansard's "
              "metadata has no URL for them, so the reader cannot check "
              "those rows".format(len(UNSOURCED)))
    print("  -> " + "\n  -> ".join(OUTPUTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
