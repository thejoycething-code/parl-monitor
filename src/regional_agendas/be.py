"""Belgium: the community and regional parliaments' forward agendas
(16 October 2026; the past business is tools/be_regions.py, whose
parliament codes these regions reuse: vl, pw, bru, cocom, fwb).

    vl     Vlaams Parlement: the documented open-data web services
           (ws.vlpar.be/e/opendata/, in robots_guard.DOCUMENTED_APIS).
           /verg/komende?type=plen and ?type=comm list next week's plenary
           and committee meetings (status 'gepland'); /verg/<id>/agd is each
           meeting's agenda as JSON: one line per bill, motion, petition
           report, question or interpellation, with its document number.
           Reaches the coming week (the Parliament convenes a week ahead).
    pw     Parlement de Wallonie: the documented Open Data agenda
           (opendata/agenda_od.php?cal=recherche&idleg=12&annee=&mois=):
           every sitting and committee meeting of a month with its
           publications; the order of the day (ODJS plenary, ODJC committee)
           is a PDF on nautilus.parlement-wallon.be, read with pypdf when
           installed. Published on short notice (a few days ahead).
    bru    Parlement de la Région de Bruxelles-Capitale and
    cocom  the United Assembly of the COCOM (ARCCC): the website agenda
           (www.parlement.brussels/agenda/: this week and next week), each
           meeting with its convocation PDF. The links point at
           weblex.brussels, whose certificate does not match its name (TLS
           checks are never switched off); the same weblex service answers
           on weblex.irisnet.be, the host of every Brussels parliamentary
           document, so the convocation is read there. A joint PRB/ARCCC
           sitting is filed under bru.
    fwb    Parlement de la Fédération Wallonie-Bruxelles: www.pfwb.be/agenda
           lists the coming plenary sittings and committee meetings; each
           meeting page renders its order of the day server-side.
    cocof  Parlement francophone bruxellois: the Plone agenda
           (?navyear=&navmonth=), each meeting's page, and its convocation
           page listing the documents on the order of the day.
    pdg    German-speaking Community: blocked (Cloudflare challenge).
    vgc    Raad van de VGC: no route (PDFs only, no agenda list).

Classification: Dutch for vl (the country's default), French for pw, fwb
and cocof, both for the bilingual Brussels assemblies (the convocations
read are French).
"""

from __future__ import annotations

import datetime
import html as _html
import re

from src import regional_agenda as ra
from src.http import FetchError

CC = "be"
TAXONOMIES = (("taxonomy-nl.yaml", "be"),)
FR = ["taxonomy-fr.yaml"]
BILINGUAL = ["taxonomy-fr.yaml", "taxonomy-nl.yaml"]
THROTTLES = {"www.pfwb.be": 1.5, "www.parlement.brussels": 1.5,
             "weblex.irisnet.be": 1.5, "www.parlementfrancophone.brussels": 1.5,
             "nautilus.parlement-wallon.be": 1.5}
HTML = {"Accept": "text/html"}
MAX_MEETINGS = 40


def _feed():
    return ra.feed(CC)


def pdf_text(blob):
    """The text layer of a PDF; None without pypdf (the region then keeps
    its meetings as booked slots)."""
    try:
        import io
        import pypdf
    except ImportError:
        return None
    try:
        reader = pypdf.PdfReader(io.BytesIO(blob))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:                                   # noqa: BLE001 - a bad PDF is a gap
        return None


def _units(ctx, read_ok, meeting_ids, horizon):
    """The whole listed window when every meeting was read, else only the
    meetings that were (a failed meeting keeps its stored rows)."""
    if read_ok and horizon:
        return [ra.window(ctx.today, horizon)]
    return [ra.meeting(m) for m in meeting_ids]


# --- Vlaams Parlement -----------------------------------------------------------

VL = "https://ws.vlpar.be/e/opendata/"
VL_LIST = VL + "verg/komende?type={0}"
VL_WEB = "https://www.vlaamsparlement.be/nl/parlementair-werk/{0}/{1}"
_VL_SKIP_LINE = {"Tijdmarkering"}


def parse_vl_meetings(data):
    """[{id, date, time, body, plenary, kind, agenda_url, status}] from a
    /verg/komende reply."""
    out = []
    for it in (data or {}).get("items") or []:
        v = it.get("vergadering") or {}
        when = v.get("datumagendering") or v.get("datumbegin") or ""
        if not v.get("id") or len(when) < 10:
            continue
        comms = [c.get("titel") for c in v.get("commissie") or [] if c.get("titel")]
        plenary = (v.get("type") or "").lower().startswith("plen")
        body = "Plenaire vergadering" if plenary else (" / ".join(comms) or
                                                       v.get("subtype") or "Commissie")
        agenda = [l.get("href") for l in v.get("link") or [] if l.get("rel") == "agenda"]
        out.append({"id": str(v["id"]), "date": when[:10], "time": when[11:16] or None,
                    "body": body, "plenary": plenary, "kind": v.get("subtype") or "",
                    "status": v.get("status") or "",
                    "summary": ra.clean(" ".join(v.get("omschrijving-kort") or [])),
                    "agenda_url": agenda[0] if agenda else None})
    return out


def _vl_obj_text(o):
    return ra.one_line(o.get("titel") or o.get("onderwerp") or o.get("naam") or "")


def parse_vl_agenda(data, meeting):
    """Items of one meeting's agenda (/verg/<id>/agd). A document on the
    agenda twice (debate, then the roll-call vote) is one item, its stages
    in the detail. An agenda with no business is one booked slot."""
    items, index, section = [], {}, None
    for ai in (data or {}).get("agenda-item") or []:
        for line in ai.get("agenda-lijn") or []:
            ltype = ((line.get("agenda-lijn-type") or {}).get("naam") or "").strip()
            title = ra.one_line(ra.clean(line.get("titel") or ""))
            objs = []
            for key in ("parlementair-initiatief", "vrageninterpellatie", "verzoekschrift",
                        "debat", "gedachtewisseling"):
                for o in line.get(key) or []:
                    objs.append((key, o))
            if not objs:
                if ltype in _VL_SKIP_LINE or not title:
                    continue
                if ltype.startswith("Tekst kader") or line.get("vet"):
                    section = title
                    continue
                objs = [("tekst", {"titel": title})]
            for key, o in objs:
                business = _vl_obj_text(o)
                if not business:
                    continue
                kind = ((o.get("objecttype") or {}).get("naam") or "")
                stage = ltype or section or ""
                ref = None
                if o.get("nummer"):
                    ref = "{0} ({1})".format(o["nummer"], o.get("zittingsjaar") or "")
                    ref = ref.replace(" ()", "")
                k = (business, ref)
                if k in index:
                    it = index[k]
                    if stage and stage not in (it["detail"] or ""):
                        it["detail"] = "{0}; {1}".format(it["detail"], stage) if it["detail"] \
                            else stage
                    continue
                detail = "; ".join(x for x in (kind, section if section != stage else None,
                                               stage) if x) or None
                url = o.get("filewebpath") if key == "parlementair-initiatief" else None
                it = ra.item(meeting["date"], business, meeting["body"], meeting["time"],
                             len(items) + 1, "vl-" + meeting["id"], detail, ref,
                             url or VL_WEB.format("plenaire-vergaderingen" if meeting["plenary"]
                                                  else "commissies/commissievergaderingen",
                                                  meeting["id"]))
                index[k] = it
                items.append(it)
    return items


def read_vl(client, ctx):
    meetings, gaps = [], []
    for typ in ("plen", "comm"):
        data = client.get_json(VL_LIST.format(typ), _feed(), "vl-komende-" + typ)
        meetings += parse_vl_meetings(data)
    items, read, ok = [], [], True
    meetings = [m for m in meetings if ctx.in_window(m["date"])
                and m["status"].lower() not in ("afgelast", "geannuleerd")]
    for m in meetings[:MAX_MEETINGS]:
        if ctx.out_of_time():
            ok = False
            gaps.append("Vlaams Parlement: agendas read in part (time budget)")
            break
        got = []
        if m["agenda_url"]:
            try:
                got = parse_vl_agenda(client.get_json(m["agenda_url"], _feed(),
                                                      "vl-agd-" + m["id"]), m)
            except FetchError as e:
                ok = False
                gaps.append("Vlaams Parlement agenda {0} ({1}) not read: {2}".format(
                    m["id"], m["date"], str(e)[:120]))
                continue
        if not got:
            business = "" if m["plenary"] or m["kind"] == "Commissievergadering" else \
                ra.one_line("{0} {1}".format(m["kind"], m["summary"]))
            got = [ra.item(m["date"], business, m["body"], m["time"], 1, "vl-" + m["id"],
                           url=VL_WEB.format("plenaire-vergaderingen" if m["plenary"] else
                                             "commissies/commissievergaderingen", m["id"]))]
        items += got
        read.append("vl-" + m["id"])
    horizon = max([m["date"] for m in meetings], default=None)
    return ra.RegionRead(items, _units(ctx, ok, read, horizon),
                         source="ws.vlpar.be open data (verg/komende, agd)",
                         note="{0} meeting(s) convened".format(len(meetings)), gaps=gaps)


# --- Parlement de Wallonie --------------------------------------------------------

PW_AGENDA = ("https://www.parlement-wallonie.be/opendata/agenda_od.php?f=json&cal=recherche"
             "&idleg={leg}&annee={y}&mois={m}")
PW_LEG = "12"


def _months(ctx, cap=3):
    d, out = ctx.today_date.replace(day=1), []
    while d <= ctx.until_date and len(out) < cap:
        out.append((d.year, d.month))
        d = (d + datetime.timedelta(days=32)).replace(day=1)
    return out


def parse_pw_agenda(data):
    """[{id, date, time, body, plenary, odj}] from agenda_od.php."""
    out = []
    for e in (data or {}).get("agenda") or []:
        date = ra.find_date(e.get("event_date") or "")
        if not date:
            continue
        odj = [p for p in e.get("event_publications") or []
               if (p.get("pub_type") or "") in ("ODJS", "ODJC")]
        url = (odj[0].get("pub_lien") or "").replace("http://", "https://", 1) if odj else None
        out.append({"id": str(e.get("event_id")), "date": date,
                    "time": e.get("event_heure_minute") or None,
                    "body": ra.one_line(e.get("event_objet")) or "Séance plénière",
                    "plenary": str(e.get("event_id_com")) == "1", "odj": url})
    return out


_PW_ODJS_ITEM = re.compile(
    r"(?:^|\s)\d{1,2}\.\s+(.+?)\s*\(Doc\.\s*(\d+)\s*\((\d{4}-\d{4})\)[^)]*\)", re.S)
_PW_SECTION = re.compile(r"(?:^|\s)\d{1,2}\s*[–-]\s+([A-ZÀ-Ý'’ ,]{6,}?)(?=\s{2,}|\s\d{1,2}\.\s)")


def parse_pw_odjs(text, meeting):
    """The plenary order of the day: '1. Projet de décret ... (Doc. 664
    (2026-2027) N° 1 et 2)'. The first page (the convocation's summary)
    is skipped."""
    pages = (text or "").split("\n \n \n")
    body = " ".join(pages[1:]) if len(pages) > 1 and "Doc." not in pages[0] else (text or "")
    body = " ".join(body.split())
    sections = [(m.start(), m.group(1).strip().capitalize()) for m in _PW_SECTION.finditer(body)]
    items = []
    for m in _PW_ODJS_ITEM.finditer(body):
        what = re.split(r",\s+déposée?s?\s+par\s+", m.group(1))[0].strip()
        what = re.sub(r"^\d{1,2}\s*[–-]\s+[A-ZÀ-Ý'’ ,]+\s+\d{1,2}\.\s+", "", what)
        if len(what) < 10:
            continue
        sec = [s for pos, s in sections if pos < m.start()]
        items.append(ra.item(meeting["date"], what, meeting["body"], meeting["time"],
                             len(items) + 1, "pw-" + meeting["id"],
                             sec[-1] if sec else None,
                             "Doc. {0} ({1})".format(m.group(2), m.group(3)), meeting["odj"],
                             lang="taxonomy-fr.yaml"))
    return items


_PW_HEAD = re.compile(r"^([A-ZÀ-Ý][A-ZÀ-Ý '’,-]{4,})\d*$")
_PW_NUM = re.compile(r"^\d{1,3}(?:\s+\d{1,2}-)?(?:\s+\d{1,3}(?:\s+\d{1,2}-)?)*$")
_PW_SKIP = re.compile(r"^(?:Rapporteu|Échange de vues|Echange de vues|Discussion|Votes?$|"
                      r"Audition\s*:|- |Exposé|Désignation|Heure|Lieu|Date|PARLEMENT|CONVOCATION)",
                      re.I)


def parse_pw_odjc(text, meeting):
    """A committee's order of the day: the bills, petitions and hearings of
    its sections, and one item per interpellation or oral question
    ('Question orale de ... à ... sur ...')."""
    lines = [ra.one_line(l) for l in (text or "").splitlines()]
    items, section, block, started = [], None, None, False

    def add(business, kind=None):
        business = ra.one_line(business)
        if len(business) < 8:
            return
        items.append(ra.item(meeting["date"], business, meeting["body"], meeting["time"],
                             len(items) + 1, "pw-" + meeting["id"], section, None,
                             meeting["odj"], item_type=kind, lang="taxonomy-fr.yaml"))

    for ln in lines:
        if not ln:
            continue
        if ln.startswith("COMPOSITION DE LA COMMISSION"):
            break
        head = _PW_HEAD.match(ln)
        if head and ln.upper() == ln:
            if block:
                add(" ".join(block), "questions")
                block = None
            if head.group(1).strip() in ("PARLEMENT DE WALLONIE", "CONVOCATION"):
                continue
            section, started = head.group(1).strip().capitalize(), True
            continue
        if not started:
            continue
        if ln in ("Interpellation", "Question orale", "Question d'actualité"):
            if block:
                add(" ".join(block), "questions")
            block = [ln]
            continue
        if _PW_NUM.match(ln):
            if block:
                add(" ".join(block), "questions")
                block = None
            continue
        if block is not None:
            block.append(ln)
            continue
        if _PW_SKIP.match(ln) or len(ln) < 25:
            continue
        ln = re.sub(r"\d+$", "", ln).strip()
        if items and not re.search(r"[.;:)»]$", items[-1]["business"]) and ln[:1].islower() \
                and items[-1]["detail"] == section:
            items[-1]["business"] = ra.one_line(items[-1]["business"] + " " + ln)
            continue
        add(ln)
    if block:
        add(" ".join(block), "questions")
    return items


def read_pw(client, ctx):
    meetings, gaps = [], []
    for y, m in _months(ctx):
        data = client.get_json(PW_AGENDA.format(leg=PW_LEG, y=y, m=m), _feed(),
                               "pw-agenda-{0}-{1:02d}".format(y, m))
        meetings += parse_pw_agenda(data)
    meetings = [m for m in meetings if ctx.in_window(m["date"])]
    items, read, ok, nopdf = [], [], True, False
    for m in meetings[:MAX_MEETINGS]:
        got = []
        if m["odj"] and not ctx.out_of_time():
            try:
                text = pdf_text(client.get_bytes(m["odj"], _feed(), "pw-odj-" + m["id"]))
            except FetchError as e:
                ok = False
                gaps.append("Parlement de Wallonie order of the day {0} not read: {1}".format(
                    m["date"], str(e)[:120]))
                continue
            if text is None:
                nopdf = True
            else:
                got = parse_pw_odjs(text, m) if m["plenary"] else parse_pw_odjc(text, m)
        items += got or [ra.item(m["date"], "", m["body"], m["time"], 1, "pw-" + m["id"],
                                 url=m["odj"])]
        read.append("pw-" + m["id"])
    horizon = max([m["date"] for m in meetings], default=None)
    note = "{0} meeting(s) in the agenda".format(len(meetings))
    if nopdf:
        note += "; pypdf not installed, orders of the day kept as booked slots"
    return ra.RegionRead(items, _units(ctx, ok, read, horizon) if meetings else
                         [ra.window(ctx.today, ctx.until)],
                         source="parlement-wallonie.be Open Data agenda + ODJ PDFs",
                         note=note, gaps=gaps)


# --- Brussels: PRB and the COCOM's United Assembly ----------------------------------

BRU_AGENDA = "https://www.parlement.brussels/agenda/"
BRU_CONVOC = "https://weblex.irisnet.be/display_pdf.php?info=convoc_fr&key={0}"
_BRU_DAY = re.compile(r'<div class="g168[^"]*" id="(\d{1,2})_(\d{1,2})">(.*?)(?=<div class="g168|'
                      r'<div class="agendaNextWeek|<div class="noGoodWeek|</section>)', re.S)
_BRU_ENTRY = re.compile(r'<div class="infos">(.*?)</div>\s*<div class="title">(.*?)</div>', re.S)


def parse_bru_agenda(page, today):
    """[{date, time, body, assemblies, key}] from the website agenda (this
    week and next)."""
    t = datetime.date.fromisoformat(today)
    out, seen = [], set()
    for dd, mm, block in _BRU_DAY.findall(page or ""):
        year = t.year + (1 if int(mm) < t.month - 6 else 0) - (1 if int(mm) > t.month + 6 else 0)
        date = ra.iso(dd, mm, year)
        for infos, title in _BRU_ENTRY.findall(block):
            asm = re.findall(r"<abbr[^>]*>(PRB|ARCCC)</abbr>", title)
            key = re.search(r"convoc_fr&(?:amp;)?key=(\d+)", title)
            body = ra.one_line(_html.unescape(re.sub(r"<[^>]+>", " ", re.sub(
                r"<b>.*?</b>", " ", title, flags=re.S))))
            time = re.search(r"\d{1,2}:\d\d", infos)
            k = (date, key.group(1) if key else body + (time.group(0) if time else ""))
            if not body or k in seen or body.startswith("Bureau"):
                continue
            seen.add(k)
            out.append({"date": date, "time": time.group(0) if time else None, "body": body,
                        "assemblies": asm, "key": key.group(1) if key else None})
    return out


_BRU_REF = re.compile(r"\(\s*(?:n\s*[°o]?\s*s?\.?\s*)?([A-B]\s?-\s?\d+/[\d, et]+\s*[–-]\s*\d{4}/\d{4})\s*\)\.?",
                      re.I)
_BRU_QNUM = re.compile(r"\((\d{3,6})\)\s*\.?\s*$")
_BRU_HEAD = re.compile(r"^\s*(\d{1,2})\.\s+([A-ZÀ-Ý][^a-z]{3,})$")


def parse_bru_convocation(text, meeting, region):
    """Items of a convocation: one per bullet (a bill, a question, an
    interpellation), joined questions split off, the rapporteur and
    'discussion' sub-bullets dropped; a numbered heading with no bullet
    under it (question time) is one item."""
    lines = [l.rstrip() for l in (text or "").splitlines()]
    chunks, cur, section, pending_head = [], None, None, None

    def flush_head():
        nonlocal pending_head
        if pending_head:
            chunks.append((re.sub(r"\s*\(\*+\)", "", pending_head).capitalize(), pending_head))
            pending_head = None

    for raw in lines:
        ln = raw.strip()
        if not ln or ln.startswith("(*)") or ln.startswith("(**)") or \
                re.match(r"^\d{2}\.\d{2}\.\d{4}\s*[–-]|^L/C", ln) or re.search(r"−\s*\d/\d$", ln):
            if not ln and cur is not None and cur[-1] != "":
                cur.append("")
            continue
        head = _BRU_HEAD.match(ln)
        if head:
            if cur:
                chunks.append((" ".join(cur), section))
                cur = None
            flush_head()
            section = head.group(2).strip()
            pending_head = section
            continue
        if ln.startswith("•"):
            if cur:
                chunks.append((" ".join(cur), section))
            pending_head = None
            cur = [ln.lstrip("• ").strip()]
            continue
        if re.match(r"^o\s+[A-ZÉ]", ln):
            if cur:
                chunks.append((" ".join(cur), section))
                cur = None
            continue
        if cur is not None:
            if re.match(r"^(Demande d'explications|Question orale|Interpellation)\b.*\bjointe",
                        ln) and (len(cur) == 0 or cur[-1] == ""):
                chunks.append((" ".join(cur), section))
                cur = [ln]
            else:
                cur.append(ln)
    if cur:
        chunks.append((" ".join(cur), section))
    flush_head()
    items = []
    for text_, sec in chunks:
        business = ra.one_line(text_)
        if len(business) < 6 or re.match(r"^(sur les|Bruxelles, le)", business):
            continue
        ref = _BRU_REF.search(business) or _BRU_QNUM.search(business)
        if ref:
            business = ra.one_line(business[:ref.start()] + business[ref.end():]).rstrip(" .")
        items.append(ra.item(meeting["date"], business, meeting["body"], meeting["time"],
                             len(items) + 1, "{0}-{1}".format(region, meeting["key"]),
                             sec if sec and sec != text_ else None,
                             ref.group(1) if ref else None,
                             BRU_CONVOC.format(meeting["key"]), lang="taxonomy-fr.yaml"))
    return items


_BRU_CACHE = {}


def _bru_page(client):
    k = id(client)
    if k not in _BRU_CACHE:
        _BRU_CACHE.clear()
        _BRU_CACHE[k] = client.get_text(BRU_AGENDA, _feed(), "bru-agenda", headers=HTML)
    return _BRU_CACHE[k]


def _read_bru(client, ctx, region):
    meetings = parse_bru_agenda(_bru_page(client), ctx.today)
    if region == "cocom":
        meetings = [m for m in meetings if m["assemblies"] == ["ARCCC"]]
    else:
        meetings = [m for m in meetings if "PRB" in m["assemblies"] or not m["assemblies"]]
    meetings = [m for m in meetings if ctx.in_window(m["date"])]
    items, read, ok, gaps, nopdf = [], [], True, [], False
    for m in meetings[:MAX_MEETINGS]:
        mid = "{0}-{1}".format(region, m["key"] or ra.slug(m["date"] + m["body"] + (m["time"] or "")))
        got = []
        if m["key"] and not ctx.out_of_time():
            try:
                text = pdf_text(client.get_bytes(BRU_CONVOC.format(m["key"]), _feed(),
                                                 "{0}-convoc-{1}".format(region, m["key"])))
            except FetchError as e:
                ok = False
                gaps.append("{0} convocation {1} ({2}) not read: {3}".format(
                    region.upper(), m["key"], m["date"], str(e)[:120]))
                continue
            if text is None:
                nopdf = True
            else:
                got = parse_bru_convocation(text, m, region)
        items += got or [ra.item(m["date"], "", m["body"], m["time"], 1, mid,
                                 url=BRU_CONVOC.format(m["key"]) if m["key"] else BRU_AGENDA)]
        read.append(mid)
    horizon = max([m["date"] for m in meetings], default=None)
    t = ctx.today_date
    end_next_week = (t + datetime.timedelta(days=13 - t.weekday())).isoformat()
    note = "{0} meeting(s) this week and next".format(len(meetings))
    if nopdf:
        note += "; pypdf not installed, convocations kept as booked slots"
    units = [ra.window(ctx.today, min(end_next_week, ctx.until))] if ok else \
        [ra.meeting(m) for m in read]
    return ra.RegionRead(items, units, source="parlement.brussels agenda + weblex convocations",
                         note=note, gaps=gaps)


def read_bru(client, ctx):
    return _read_bru(client, ctx, "bru")


def read_cocom(client, ctx):
    return _read_bru(client, ctx, "cocom")


# --- Fédération Wallonie-Bruxelles ---------------------------------------------------

FWB_HOST = "https://www.pfwb.be"
FWB_AGENDA = FWB_HOST + "/agenda"
_FWB_LINK = re.compile(r'href="(/agendas/(seances-plenieres|commissions-[a-z-]+?)-'
                       r'(\d{4}-\d\d-\d\d)(?:-[0-9]+)?)"')


def parse_fwb_index(page):
    """[(url, kind, date)] of the plenary sittings and committee meetings
    the agenda page lists."""
    out = []
    for path, kind, date in _FWB_LINK.findall(page or ""):
        url = FWB_HOST + path
        if url not in [u for u, _, _ in out]:
            out.append((url, kind, date))
    return out


_FWB_QUESTION = re.compile(r"^(?:\d+(?:\.\d+)*\.\s+)?((?:Question orale|Question d'actualité|"
                           r"Interpellation)\b.+)$")


def parse_fwb_meeting(page, url, date):
    """Items of one meeting page: each numbered point; a block of oral
    questions or interpellations gives one item per question."""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page or "", re.S)
    body = ra.one_line(ra.clean(h1.group(1))) if h1 else "Séance plénière"
    if body.lower().startswith("séance pl"):
        body = "Séance plénière"
    elif body:
        body = body[0].upper() + body[1:]
    tm = re.search(r">\s*(\d{1,2}:\d\d)\s*-\s*\d{1,2}:\d\d\s*<", page or "")
    time = tm.group(1) if tm else None
    mid = "fwb-" + url.rsplit("/", 1)[-1]
    items = []
    parts = re.split(r'<li class="order-list__item"', page or "")[1:]
    for part in parts:
        part = part.split(">", 1)[1] if ">" in part else part
        part = re.split(r"</ol>\s*</section>", part)[0]
        lines = [l for l in ra.clean(part).splitlines() if l and l != "Voir plus"]
        if not lines:
            continue
        head = re.sub(r"^\d+(?:\.\d+)*\.\s*", "", lines[0])
        rest = lines[1:]
        if re.match(r"^\((?:En application|Eventuellement|Éventuellement)", head) and rest:
            head, rest = rest[0], rest[1:]
        ref = re.search(r"\((?:doc|Doc)\.\s*(\d+)\s*\((\d{4}-\d{4})\)[^)]*\)",
                        " ".join([head] + rest[:2]))
        head_clean = re.sub(r"\s*\((?:doc|Doc)\.\s*\d+.*$", "", head).strip()
        questions = [m.group(1) for m in (_FWB_QUESTION.match(l) for l in rest) if m]
        if re.match(r"^(Questions? orales?|Interpellations?|Questions d'actualité)", head_clean) \
                and questions:
            for q in questions:
                items.append(ra.item(date, q, body, time, len(items) + 1, mid, head_clean, None,
                                     url, item_type="questions", lang="taxonomy-fr.yaml"))
            continue
        items.append(ra.item(date, head_clean, body, time, len(items) + 1, mid,
                             "; ".join(l for l in rest if l.startswith("- "))[:500] or None,
                             "Doc. {0} ({1})".format(ref.group(1), ref.group(2)) if ref else None,
                             url, lang="taxonomy-fr.yaml"))
    if not items:
        items = [ra.item(date, "", body, time, 1, mid, url=url)]
    return items


def read_fwb(client, ctx):
    index = parse_fwb_index(client.get_text(FWB_AGENDA, _feed(), "fwb-agenda", headers=HTML))
    index = [x for x in index if ctx.in_window(x[2])]
    items, read, ok, gaps = [], [], True, []
    for url, kind, date in index[:MAX_MEETINGS]:
        if ctx.out_of_time():
            ok = False
            gaps.append("FWB: meetings read in part (time budget)")
            break
        try:
            page = client.get_text(url, _feed(), "fwb-" + url.rsplit("/", 1)[-1][:60],
                                   headers=HTML)
        except FetchError as e:
            ok = False
            gaps.append("FWB meeting {0} not read: {1}".format(url, str(e)[:120]))
            continue
        got = parse_fwb_meeting(page, url, date)
        items += got
        read.append(got[0]["meeting_id"])
    horizon = max([d for _, _, d in index], default=None)
    return ra.RegionRead(items, _units(ctx, ok, read, horizon) if index else
                         [ra.window(ctx.today, ctx.until)],
                         source="pfwb.be agenda (meeting pages)",
                         note="{0} meeting(s) listed".format(len(index)), gaps=gaps)


# --- COCOF: Parlement francophone bruxellois ----------------------------------------------

COCOF = "https://www.parlementfrancophone.brussels"
COCOF_MONTH = COCOF + "/agenda?navyear={0}&navmonth={1}"
_COCOF_EVENT = re.compile(r'<li class="([a-z-]*event)" id="event-([^"]+)">(.*?)</li>', re.S)


def parse_cocof_month(page):
    """[{id, date, time, body, url}] from one month of the agenda."""
    out = []
    for cls, eid, block in _COCOF_EVENT.findall(page or ""):
        date = re.search(r'id="d(\d{4}-\d\d-\d\d)"', block)
        when = re.search(r'<span>([^<]*\d{4}[^<]*)</span>', block)
        h3 = re.search(r"<h3>(.*?)</h3>", block, re.S)
        link = re.search(r'href="([^"]+)"', block)
        if not date or not h3:
            continue
        time = re.search(r"(\d{1,2}:\d\d)", when.group(1)) if when else None
        out.append({"id": eid, "date": date.group(1), "time": time.group(1) if time else None,
                    "body": ra.one_line(ra.clean(h3.group(1))), "kind": cls,
                    "url": link.group(1) if link else None})
    return out


def parse_cocof_event(page):
    """The convocation page linked from a meeting's page, or None."""
    m = re.search(r'class="order-of-the-day-link">\s*<a href="([^"]+)"', page or "")
    return m.group(1) if m else None


def parse_cocof_convocation(page, meeting):
    """The documents on a convocation's order of the day."""
    items = []
    for li in re.findall(r"<li[^>]*>\s*<div>(.*?)</div>\s*</li>", page or "", re.S):
        ref = re.search(r"<h4>\s*<a[^>]*>(.*?)</a>", li, re.S)
        title = re.search(r'<p class="intitule">(.*?)</p>', li, re.S)
        if not title:
            continue
        items.append(ra.item(meeting["date"], ra.clean(title.group(1)), meeting["body"],
                             meeting["time"], len(items) + 1, "cocof-" + meeting["id"], None,
                             ra.clean(ref.group(1)) if ref else None, meeting["url"],
                             lang="taxonomy-fr.yaml"))
    return items


def read_cocof(client, ctx):
    meetings = []
    for y, m in _months(ctx, cap=2):
        meetings += parse_cocof_month(client.get_text(COCOF_MONTH.format(y, m), _feed(),
                                                      "cocof-{0}-{1:02d}".format(y, m),
                                                      headers=HTML))
    meetings = [m for m in meetings if ctx.in_window(m["date"]) and m["kind"] != "burevent"]
    items, read, ok, gaps = [], [], True, []
    for m in meetings[:MAX_MEETINGS]:
        got = []
        try:
            if m["url"] and not ctx.out_of_time():
                conv = parse_cocof_event(client.get_text(m["url"], _feed(),
                                                         "cocof-ev-" + m["id"][:50], headers=HTML))
                if conv:
                    got = parse_cocof_convocation(client.get_text(
                        conv, _feed(), "cocof-conv-" + m["id"][:50], headers=HTML), m)
        except FetchError as e:
            ok = False
            gaps.append("COCOF meeting {0} not read: {1}".format(m["date"], str(e)[:120]))
            continue
        items += got or [ra.item(m["date"], "", m["body"], m["time"], 1, "cocof-" + m["id"],
                                 url=m["url"])]
        read.append("cocof-" + m["id"])
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)] if ok else
                         [ra.meeting(x) for x in read],
                         source="parlementfrancophone.brussels agenda + convocations",
                         note="{0} meeting(s) in the agenda".format(len(meetings)), gaps=gaps)


REGIONS = {
    "vl": ra.region("Vlaams Parlement", reader=read_vl),
    "pw": ra.region("Parlement de Wallonie", reader=read_pw, langs=FR),
    "bru": ra.region("Parlement de la Région de Bruxelles-Capitale", reader=read_bru,
                     langs=BILINGUAL),
    "cocom": ra.region("Assemblée réunie de la COCOM", reader=read_cocom, langs=BILINGUAL),
    "fwb": ra.region("Parlement de la Fédération Wallonie-Bruxelles", reader=read_fwb, langs=FR),
    "cocof": ra.region("Parlement francophone bruxellois (COCOF)", reader=read_cocof, langs=FR),
    "pdg": ra.region("Parlament der Deutschsprachigen Gemeinschaft", status="blocked",
                     note="pdg.be, www.pdg.be and ostbelgienlive.be answer a Cloudflare "
                          "challenge (HTTP 403), robots.txt included (16 October 2026); "
                          "never bypassed; no open data or feed found on another host"),
    "vgc": ra.region("Raad van de Vlaamse Gemeenschapscommissie", status="no-route",
                     note="vgc.be publishes the council's agendas and minutes only as PDFs "
                          "with no agenda list (be_regions scope, 13 October 2026)"),
}
