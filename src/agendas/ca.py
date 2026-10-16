"""Canada (federal): the week ahead in the House of Commons and the Senate
(16 October 2026).

Five reads, each one request, every host's robots.txt asked at run time
(tools/country_agenda.py wraps the client in src/robots_guard.guard;
measured 16 October 2026: ourcommons.ca disallows only /Embed/, /Search/,
/PublicationSearch/, /ParlDataWidgets/ and /ErrorPage/; sencanada.ca's
robots.txt is empty; none of the paths below is refused). Neither House
publishes its committee schedule or order of business as an open-data
export (the ourcommons open-data page lists members, votes, petitions and
LEGISinfo only), so these are the parliaments' own published pages, read as
tools/ca_committees.py and tools/ca_senate_committees.py already read them.

  1. House committee meetings: ourcommons.ca/Committees/en/Meetings?
     meetingDate=<today>, every committee's notices from that day on (the
     House publishes them about a week ahead). One point per meeting: the
     committee, its studies and activities (bills named in them become
     refs, '45-1/C-31'), in camera or cancelled as the page marks it.
     Joint committees are listed here, so they are left out of the
     Senate's list.
  2. The House's Projected Order of Business (DocumentViewer/en/house/
     latest/projected-business): the next sitting's business, bilingual.
     One point per bill or motion on it, from the English half only: the
     number, the sponsor, the title and the stage, as printed, and the
     rubric (Government Orders, Private Members' Business, Deferred
     Recorded Divisions). It covers ONE sitting; the Coverage line says so.
  3. The House sitting calendar (en/sitting-calendar): the sitting days,
     for the next sitting.
  4. Senate committee meetings: the schedule's own table
     (umbraco/surface/CommitteesAjax/GetTablePartialView?tableName=
     Meetings, the call the schedule page makes), upcoming, 100 a page.
     One point per meeting: the committee, each study or bill and the
     activity printed under it, in camera as marked; witnesses are counted,
     never named here.
  5. The Senate's Order Paper and Notice Paper for its next sitting (the
     latest issue linked from en/in-the-chamber/order-papers-notice-papers/).
     One point per BILL item of the Orders of the Day, as printed. These are
     items that MAY be called that day, not a schedule: each says so.

Classification is the edition adapter's (src/editions/ca.py): the English
taxonomy unchanged, on each point's own words (studies, the bill line, the
Order Paper item; never the committee's name), plus the stored areas of the
bills it names (ca_bills, by key). A watched bill key is watched.

Titles are kept verbatim. The em dashes the House prints BETWEEN fields
(number, sponsor, title, stage) are separators and are not kept; a dash
inside a title is the title's own. tools/ca_monitor.py renders every point
through its oneline(), so the edition carries no em dash.
"""

from __future__ import annotations

import datetime
import html as htmlmod
import re

from src import agenda
from src.http import FetchError

CC = "ca"
SOURCE = ("the House's committee notices, Projected Order of Business and sitting calendar; "
          "the Senate's committee schedule and Order Paper")
BILLS = ("ca_bills", "bill_key", "COALESCE(short_title, long_title)")
FEED = "ca-agenda"
SESSION = "45-1"            # the fallback when a page names none (tools/ca_rollcalls.CURRENT_SESSION)

HOC = "https://www.ourcommons.ca"
SEN = "https://sencanada.ca"
HOUSE_MEETINGS = HOC + "/Committees/en/Meetings?meetingDate={0}"
PROJECTED = HOC + "/DocumentViewer/en/house/latest/projected-business"
CALENDAR = HOC + "/en/sitting-calendar"
SENATE_MEETINGS = (SEN + "/umbraco/surface/CommitteesAjax/GetTablePartialView?tableName=Meetings"
                   "&committeeId=0&Lang=en&TabSelected=UPCOMING&session={0}&PageSize=100"
                   "&SortOrder=DATEASC")
SENATE_OP_INDEX = SEN + "/en/in-the-chamber/order-papers-notice-papers/"

BILL = re.compile(r"\b(?:Bill\s+)?([CS]-\d{1,4}[A-Z]?)\b")
BILL_NAMED = re.compile(r"\bBill\s+([CS]-\d{1,4}[A-Z]?)\b")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
SHORT_MONTHS = tuple(m[:3] for m in MONTHS)


def clean(text):
    return " ".join(htmlmod.unescape(text or "").replace("\xa0", " ").split())


def flat(page):
    """A page's visible words as one line (scripts and styles dropped)."""
    body = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", page or "")
    return clean(re.sub(r"<[^>]+>", " ", body))


def bill_ref(number, session=SESSION):
    return "{0}/{1}".format(session, number.upper())


def _hm(text):
    """'11:00 a.m.' or '04:00 p.m.' -> '11:00' / '16:00'; None otherwise."""
    m = re.search(r"(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", text or "", re.I)
    if not m:
        return None
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return "{0:02d}:{1}".format(h, m.group(2))


# --- 1. House committee meetings -------------------------------------------------

BLOCK = re.compile(r'<div class="accordion-item meeting-item-(\d{4}-\d{2}-\d{2})\s*"\s+'
                   r'id="meeting-item-(\d+)"')
STUDY = re.compile(r'class="studies-activities-item">([^<]*)<')
ACRONYM = re.compile(r'class="meeting-acronym">\s*([^<]*?)\s*<')
TIME = re.compile(r'<time datetime="\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})')
NAME = re.compile(r'meeting-card-committee-details-name">\s*<a href="[^"]*">\s*([^<]*?)\s*</a>')
NOTICE = re.compile(r'href="((?:https?:)?//www\.(?:ourcommons|parl)\.ca/DocumentViewer/en/'
                    r'(\d{1,2}-\d)/([A-Z]{4})/meeting-(\d+)/notice)"')


def parse_house_meetings(page, today):
    """[point] for the House's meeting list, meetings dated today or later."""
    legend = page.find("meeting-icons-legend")
    text = page[:legend] if legend > 0 else page
    starts = list(BLOCK.finditer(text))
    out = []
    for i, m in enumerate(starts):
        date, site_id = m.group(1), m.group(2)
        if date < today:
            continue        # the page can carry an old notice (TRAN, 20 April 2026)
        chunk = text[m.start(): starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        studies = []
        for s in STUDY.findall(chunk):
            s = clean(s)
            if s and s not in studies:
                studies.append(s)
        acr = ACRONYM.search(chunk)
        name = NAME.search(chunk)
        notice = NOTICE.search(chunk)
        session = notice.group(2) if notice else SESSION
        committee = clean(name.group(1)) if name else (clean(acr.group(1)) if acr else "")
        status = []
        if "icon-cancel" in chunk:
            status.append("Cancelled")
        if 'title="In Camera"' in chunk:
            status.append("In camera")
        url = None
        if notice:
            url = notice.group(1)
            url = "https:" + url if url.startswith("//") else url
        refs = [bill_ref(b, session) for b in BILL_NAMED.findall(" ".join(studies))]
        tm = TIME.search(chunk)
        out.append(agenda.point(
            "hoc-mtg-" + site_id, date, "; ".join(studies) or committee,
            body="House committee: {0}".format(committee or "committee"), kind="committee",
            time=tm.group(1) if tm else None, detail=committee, refs=refs, url=url,
            status=", ".join(status) or None, text=" ".join(studies) or None))
    return out


# --- 2. the House's Projected Order of Business ----------------------------------------

LONG_DATE = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
                       r"(" + "|".join(MONTHS) + r") (\d{1,2}), (\d{4})\b")
SITTING = re.compile(r"SITTING\s+No\.\s*(\d+)")
PAGE_SESSION = re.compile(r"/(\d{2})-(\d)/house/|/Content/House/(\d{2})(\d)/")
RUBRICS = ("PRIVATE MEMBERS' BUSINESS", "GOVERNMENT ORDERS", "DEFERRED RECORDED DIVISIONS",
           "ROUTINE PROCEEDINGS", "STATEMENTS BY MEMBERS", "ORAL QUESTIONS",
           "ADJOURNMENT PROCEEDINGS", "EMERGENCY DEBATE", "TAKE-NOTE DEBATE")
ITEM_START = re.compile(r"(?:(?<=\s)|^)([CSM]-\d{1,4}[A-Z]?|Opposition motion)\s+—\s+")
ITEM_END = re.compile(r"\s(?:[CSM]-\d{1,4}[A-Z]?\s+—|Opposition motion\s+—|Motion de l|"
                      r"Length of|Durée|——|Debate —|Voting —|Recorded division|"
                      r"\d{1,2}:\d{2}\s*[ap]\.m\.|\d{1,2} h(?:eures| \d)|"
                      + "|".join(re.escape(r) for r in RUBRICS) + r")")
ENGLISH_STAGE = re.compile(r"\b(reading|stage|consideration|amendments?|concurrence|message|"
                           r"debate|motion)\b", re.I)
FRENCH = re.compile(r"\b(lecture|étape|débat|amendements|député|ministre|Loi)\b")


def _iso_long(m):
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), MONTHS.index(m.group(1)) + 1,
                                        int(m.group(2)))


def parse_projected(page, url=PROJECTED):
    """(date, sitting, [point]) from the Projected Order of Business."""
    text = flat(page)
    dm = LONG_DATE.search(text)
    if not dm:
        return None, None, []
    date = _iso_long(dm)
    sm = SITTING.search(text)
    sitting = sm.group(1) if sm else date
    ps = PAGE_SESSION.search(page or "")
    session = ("{0}-{1}".format(ps.group(1), ps.group(2)) if ps and ps.group(1) else
               "{0}-{1}".format(ps.group(3), ps.group(4)) if ps else SESSION)
    body_from = dm.end()
    out, seen = [], set()
    for m in ITEM_START.finditer(text, body_from):
        end = ITEM_END.search(text, m.end())
        seg = text[m.end(): end.start() if end else len(text)].strip()
        fields = [f.strip() for f in re.split(r"\s+—\s+", seg) if f.strip()]
        label = m.group(1)
        if label == "Opposition motion":
            if len(fields) < 2 or FRENCH.search(" ".join(fields)):
                continue
            mover, subject = fields[0], " — ".join(fields[1:])
            title, stage, number = subject, "Opposition motion", None
        else:
            if len(fields) < 3:
                continue
            mover, stage = fields[0], fields[-1]
            title = " — ".join(fields[1:-1])
            if not ENGLISH_STAGE.search(stage) or re.search(r"\blecture\b|\bétape\b", stage):
                continue        # the French half of the bilingual page
            number = label
        key = (label, title)
        if key in seen:
            continue
        seen.add(key)
        before = text[body_from: m.start()]
        rubric = max(((before.rfind(r), r) for r in RUBRICS), default=(-1, None))
        times = re.findall(r"(\d{1,2}:\d{2}\s*[ap]\.m\.)", before)
        head = "{0}, {1}".format(number, title) if number else title
        refs = [bill_ref(number, session)] if number and number[0] in "CS" else []
        detail = "; ".join(x for x in (
            rubric[1].title().replace("'S", "'s") if rubric[0] >= 0 else None,
            "{0}: {1}".format("moved by" if not number else "sponsor", mover)) if x)
        out.append(agenda.point(
            "hoc-pob-{0}-{1}".format(sitting, re.sub(r"[^A-Za-z0-9]+", "-", number or
                                                    "opp-" + title[:40]).strip("-")),
            date, "{0}: {1}".format(head, stage), body="House of Commons", kind="plenary",
            time=_hm(times[-1]) if times else None, detail=detail, refs=refs, url=url,
            status="Projected Order of Business (subject to change)",
            text="{0} {1}".format(title, stage)))
    return date, sitting, out


# --- 3. the House sitting calendar -----------------------------------------------------

SITTING_DAY = re.compile(r'class="(\d{4}-\d{2}-\d{2}) chamber-meeting"')


def parse_calendar(page):
    """Every sitting day the calendar marks, sorted."""
    return sorted(set(SITTING_DAY.findall(page or "")))


# --- 4. Senate committee meetings ---------------------------------------------------------

ROW = re.compile(r"(?s)<tr[^>]*>(.*?)</tr>")
CELL = re.compile(r"(?s)<td[^>]*>(.*?)</td>")
SEN_NOTICE = re.compile(r'href="(/en/committees/([A-Za-z]{4})/noticeofmeeting/(\d+)/(\d{2}-\d))"')
SEN_DATE = re.compile(r"\b(" + "|".join(SHORT_MONTHS) + r")[a-z]*\.? (\d{1,2}), (\d{4})")


def parse_senate_meetings(page, today):
    """[point] for the Senate's upcoming committee meetings (joint committees
    left out: the House's list carries them)."""
    out = []
    for row in ROW.findall(page or ""):
        cells = CELL.findall(row)
        if len(cells) < 3:
            continue
        nm = SEN_NOTICE.search(cells[0])
        dm = SEN_DATE.search(clean(re.sub(r"<[^>]+>", " ", cells[0])))
        if not nm or not dm:
            continue
        date = "{0}-{1:02d}-{2:02d}".format(int(dm.group(3)), SHORT_MONTHS.index(dm.group(1)) + 1,
                                            int(dm.group(2)))
        if date < today:
            continue
        committee = clean(re.sub(r"<[^>]+>", " ", cells[1]))
        if "(Joint)" in committee:
            continue
        study_cell = cells[2]
        witnesses = len(re.findall(r"<li>", study_cell.split("Witnesses", 1)[1])) \
            if "Witnesses" in study_cell else 0
        study_part = study_cell.split("<div>Witnesses", 1)[0]
        studies = [clean(re.sub(r"<[^>]+>", " ", s))
                   for s in re.findall(r"(?s)<strong>(.*?)</strong>", study_part)]
        studies = [s for s in studies if s]
        activities = [clean(re.sub(r"<[^>]+>", " ", s))
                      for s in re.findall(r"(?s)<em>(.*?)</em>", study_part)]
        session = nm.group(4)
        refs = [bill_ref(b, session) for b in BILL_NAMED.findall(" ".join(studies))]
        status = []
        links = cells[4] if len(cells) > 4 else ""
        if 'alt="In Camera"' in links:
            status.append("In camera")
        elif 'alt="Partial In Camera"' in links:
            status.append("Partly in camera")
        detail_bits = [committee] + ([", ".join(a for a in activities if a)] if activities else [])
        if witnesses:
            detail_bits.append("{0} witness(es) listed".format(witnesses))
        out.append(agenda.point(
            "sen-mtg-" + nm.group(3), date, "; ".join(studies) or committee,
            body="Senate committee: {0}".format(committee), kind="committee",
            time=_hm(clean(re.sub(r"<[^>]+>", " ", cells[0]))), detail="; ".join(detail_bits),
            refs=refs, url=SEN + nm.group(1), status=", ".join(status) or None,
            text=" ".join(studies + activities) or None))
    return out


# --- 5. the Senate's Order Paper ---------------------------------------------------------

OP_LINK = re.compile(r'href="(/en/content/sen/chamber/(\d{2})(\d)/orderpaper/(\d+)op_'
                     r'(\d{4}-\d{2}-\d{2})-e)"')
DASH = "[–—-]"
BUSINESS = re.compile(r"\b(Government Business|Other Business)\b")
OP_HEADS = re.compile(
    r"(Bills " + DASH + r" Messages from the House of Commons|"
    r"(?:Senate Public |Commons Public |Private )?Bills " + DASH +
    r" (?:Third Reading|Reports of Committees|Second Reading)|"
    r"Reports of Committees " + DASH + r" Other|Motions|Inquiries|Other)"
    r"(?= (?:Nil|No\. \d|Rule 4-14))")
OP_ITEM = re.compile(r"No\. (\d+)\.\s+(?:\((\w+(?:-\w+)?)\)\s+)?")


def latest_order_paper(index_page):
    """(url, session '45-1', issue, date) of the newest Order Paper linked, or None."""
    got = [(m.group(5), int(m.group(4)), m) for m in OP_LINK.finditer(index_page or "")]
    if not got:
        return None
    date, issue, m = max(got)
    return SEN + m.group(1), "{0}-{1}".format(m.group(2), m.group(3)), issue, date


def parse_order_paper(page, date, session=SESSION, url=None, issue=None):
    """[point] for each BILL item of the Orders of the Day, as printed."""
    text = flat(page)
    start = text.find("Orders Of The Day Government Business")
    if start < 0:
        return []
    end = re.compile(r"\bNotice Paper (?=Motions|Inquiries|Notices)").search(text, start)
    body = text[start: end.start() if end else len(text)]
    heads = [(m.start(), m.group(1)) for m in OP_HEADS.finditer(body)]
    kinds = [(m.start(), m.group(1)) for m in BUSINESS.finditer(body)]
    items = list(OP_ITEM.finditer(body))
    out = []
    for i, m in enumerate(items):
        stop = min([p for p, _h in heads if p > m.start()] +
                   ([items[i + 1].start()] if i + 1 < len(items) else []) + [len(body)])
        words = body[m.end(): stop].strip()
        bills = BILL_NAMED.findall(words)
        if not bills:
            continue
        section = next((h for p, h in reversed(heads) if p < m.start()), None)
        business = next((h for p, h in reversed(kinds) if p < m.start()), None)
        words = re.sub(r"^[A-Z][a-z]+ \d{1,2}, \d{4}\s*—\s*", "", words)   # the date it was set down
        refs = [bill_ref(b, session) for b in dict.fromkeys(bills)]
        out.append(agenda.point(
            "sen-op-{0}-{1}-{2}".format(issue or date, re.sub(r"[^A-Za-z]+", "-", section or
                                                           "item").strip("-").lower(),
                                        m.group(1)),
            date, words[:400], body="Senate (Order Paper)", kind="plenary",
            detail="; ".join(x for x in (business, section) if x), refs=refs, url=url,
            status="On the Order Paper for the sitting; may be called, not scheduled",
            text=words))
    return out


# --- the fetch ---------------------------------------------------------------------------

def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    points, gaps, notes = [], [], []
    next_sitting = None

    def read(url, slug, what):
        try:
            return client.get_text(url, FEED, slug)
        except FetchError as exc:
            gaps.append("{0} unreadable: {1}".format(what, str(exc)[:100]))
            return None

    page = read(HOUSE_MEETINGS.format(today), "house-meetings-" + today, "House committee meetings")
    if page is not None:
        got = [p for p in parse_house_meetings(page, today) if p["date"] <= end]
        points += got
        last = max((p["date"] for p in got), default=None)
        notes.append("House committees: {0} meeting(s) noticed{1}".format(
            len(got), " to " + last if last else ""))
    page = read(PROJECTED, "house-projected-" + today, "the House's Projected Order of Business")
    if page is not None:
        date, sitting, got = parse_projected(page)
        if date and date >= today:
            points += got
            notes.append("the House's Projected Order of Business covers sitting {0} ({1}) "
                         "only".format(sitting, date))
        elif date:
            notes.append("the House's latest Projected Order of Business is for {0}, past".format(
                date))
    page = read(CALENDAR, "house-calendar-" + today, "the House sitting calendar")
    if page is not None:
        days_ = parse_calendar(page)
        ahead = [d for d in days_ if d >= today]
        next_sitting = ahead[0] if ahead else None
        within = [d for d in ahead if d <= end]
        notes.append("the House sits on {0} day(s) to {1}".format(len(within), end))
    page = read(SENATE_MEETINGS.format(SESSION), "senate-meetings-" + today,
                "Senate committee meetings")
    if page is not None:
        got = [p for p in parse_senate_meetings(page, today) if p["date"] <= end]
        points += got
        notes.append("Senate committees: {0} meeting(s) scheduled".format(len(got)))
    index = read(SENATE_OP_INDEX, "senate-op-index-" + today, "the Senate's Order Paper list")
    op = latest_order_paper(index) if index else None
    if op:
        url, session, issue, date = op
        if date >= today:
            page = read(url, "senate-op-{0}".format(date), "the Senate's Order Paper")
            if page is not None:
                got = parse_order_paper(page, date, session, url, issue)
                points += got
                notes.append("the Senate's Order Paper for {0}: {1} bill item(s) that may be "
                             "called".format(date, len(got)))
        else:
            notes.append("the Senate's latest Order Paper is for {0}, past".format(date))
    elif index is not None:
        gaps.append("the Senate's Order Paper list links no issue")
    log("ca-agenda: " + "; ".join(notes))
    return agenda.fetched(points, next_sitting=next_sitting,
                          note=("; ".join(notes)[:1].upper() + "; ".join(notes)[1:]) or None,
                          gaps=gaps)
