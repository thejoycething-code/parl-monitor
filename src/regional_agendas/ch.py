"""Switzerland: the cantonal parliaments' forward business (regional_agenda,
16 October 2026).

Region codes are tools/ch_cantons.py's ('zh', 'be', ...), so the edition can
join. Every route was probed live on 16 October 2026 with robots.txt read
first (docs/switzerland-cantons-scope.md, "Forward agenda").

ONE SHARED ROUTE FOR SIXTEEN CANTONS: OpenParlData.ch (api.openparldata.ch,
the opendata.ch association's harmonised API of Swiss parliaments, CC BY 4.0,
"Source: OpenParlData.ch"; robots.txt allows the API). Its `meetings` carry
each canton's booked sittings (plenary, and for some committees) and its
`agendas` the published order of business (Traktanden, with the business
number). The canton readers below share one read per run (cached on the
run's ctx): the meetings of every OpenParlData canton, newest first, until
the window is covered; the agenda items of the meetings in the window; the
names of their bodies. A meeting with no items yet is 'to be announced' (a
session's half-day sittings are not, when the session itself carries the
items). Multilingual items (Bern de/fr, Graubünden de/it/rm) are one item in
the canton's main language with the other titles as detail.

OWN ROUTES where OpenParlData has nothing ahead or the canton's own system is
richer:
  zh  the Kantonsrat's CMI service (parlzhcdws.cmicloud.ch, the backend of
      kantonsrat.zh.ch; the SITZUNGENDETAIL index the site's own calendar
      asks): every Kantonsrat and committee sitting in the window; committee
      Traktanden are structured, the Kantonsrat's are read from the
      Traktandenliste document's full text in the same reply.
  ge  the Grand Conseil's sessions page (/grandconseil/sessions/seances/<year>/)
      and, for a session whose order of the day is out, its HTML order of
      the day (seances-odj-lion); later sessions are 'to be announced' per
      sitting day.
  vd  the Grand Conseil's sittings list; a sitting dated today or later is
      read from its own page (the order of the day with each object's
      number). The calendar is a PDF and is not read.
  ti  the Gran Consiglio's order of the day (the next sitting) and its
      calendar of sessions.
  vs  the Grand Conseil's own JSON (parlement.vs.ch/api/fe/v1, what its app
      loads): the latest sessions and each session's sittings with their
      agenda items once the programme is out.
  zg  the Kantonsrat's business system (kr-geschaefte.zug.ch/gast/
      traktandenlisten): a Traktandenliste dated today or later is read.
"""

from __future__ import annotations

import datetime
import html as _html
import re
import urllib.parse

from src import regional_agenda as ra
from src.http import FetchError

CC = "ch"
TAXONOMIES = (("taxonomy-atch.yaml", "ch"),)
THROTTLES = {"api.openparldata.ch": 1.5, "ge.ch": 1.5, "parlement.vs.ch": 1.5}
FEED = ra.feed(CC)

DE, FR, IT = "taxonomy-atch.yaml", "taxonomy-fr.yaml", "taxonomy-it.yaml"
LANG_FILE = {"de": DE, "fr": FR, "it": IT}

# --- OpenParlData ---------------------------------------------------------------

OPD = "https://api.openparldata.ch/v1/"
# Aargau is NOT read through OpenParlData (lead's decision, 16 October 2026):
# its own host disallows the whole parliament section and whether to ask its
# Parlamentsdienst is still with Chris (docs/switzerland-cantons-scope.md,
# "Waiting on Chris" 3); reading its business through a republisher would
# step round that refusal. Fifteen cantons.
OPD_CANTONS = ("be", "lu", "ur", "sz", "ow", "nw", "gl", "so", "bs", "bl", "ar", "ai", "sg",
               "gr", "tg")
OPD_PAGE = 500
OPD_MAX_PAGES = 4
OPD_MEETINGS = (OPD + "meetings/?body_key={keys}&sort_by=-begin_date&limit={limit}&offset={offset}"
                "&lang_format=flat&fields=id,body_key,external_id,type,parent_external_id,name_de,"
                "name_fr,name_it,group_id,begin_date,end_date,state,url_external_de,"
                "url_external_fr,url_external_it")
OPD_AGENDAS = (OPD + "agendas/?meeting_id={ids}&limit=1000&offset={offset}&lang_format=flat"
               "&fields=id,meeting_id,item_date,item_title,item_number_display,item_number,"
               "item_description,item_category,item_status,item_url,item_affair_number,"
               "item_language,item_external_id")
OPD_GROUPS = (OPD + "groups/?id={ids}&limit=200&lang_format=flat"
              "&fields=id,body_key,name_de,name_fr,name_it,type_harmonized")
OPD_SOURCE = "OpenParlData.ch meetings + agendas (CC BY 4.0, Source: OpenParlData.ch)"

HOUSE = {"zh": "Kantonsrat", "be": "Grosser Rat", "lu": "Kantonsrat", "ur": "Landrat",
         "sz": "Kantonsrat", "ow": "Kantonsrat", "nw": "Landrat", "gl": "Landrat",
         "zg": "Kantonsrat", "fr": "Grand Conseil", "so": "Kantonsrat", "bs": "Grosser Rat",
         "bl": "Landrat", "sh": "Kantonsrat", "ar": "Kantonsrat", "ai": "Grosser Rat",
         "sg": "Kantonsrat", "gr": "Grosser Rat", "ag": "Grosser Rat", "tg": "Grosser Rat",
         "ti": "Gran Consiglio", "vd": "Grand Conseil", "vs": "Grand Conseil",
         "ne": "Grand Conseil", "ge": "Grand Conseil", "ju": "Parlement"}
MAIN_LANG = {"fr": "fr", "ge": "fr", "vd": "fr", "ne": "fr", "ju": "fr", "ti": "it"}


def _day(ts):
    return (ts or "")[:10] or None


def _time(ts):
    t = (ts or "")[11:16]
    return t if t and t != "00:00" else None


def _first(row, field, langs=("de", "fr", "it")):
    for l in langs:
        v = row.get("{0}_{1}".format(field, l))
        if v:
            return v
    return row.get(field)


def opd_items(code, meetings, agendas, groups, ctx):
    """One canton's items from OpenParlData rows (pure)."""
    key = code.upper()
    mine = [m for m in meetings if m.get("body_key") == key and ctx.in_window(_day(m.get("begin_date")))]
    by_meeting = {}
    for a in agendas:
        by_meeting.setdefault(a.get("meeting_id"), []).append(a)
    with_items = {m["id"] for m in mine if by_meeting.get(m["id"])}
    ext_with_items = {m.get("external_id") for m in mine if m["id"] in with_items}
    sessions_with_children = {m.get("parent_external_id") for m in mine if m.get("parent_external_id")}
    main = MAIN_LANG.get(code, "de")
    out = []
    for m in sorted(mine, key=lambda x: (x.get("begin_date") or "", x["id"])):
        group = groups.get(m.get("group_id")) or {}
        if not group or group.get("type_harmonized") == "council_legislative":
            body = HOUSE.get(code, "Parlament")
        else:
            body = _first(group, "name") or HOUSE.get(code, "Parlament")
        mid = "opd-{0}".format(m["id"])
        url = _first(m, "url_external")
        name = _first(m, "name")
        rows = by_meeting.get(m["id"]) or []
        if not rows:
            if m.get("parent_external_id") in ext_with_items:
                continue            # a half-day sitting of a session whose items are listed
            if m.get("type") == "session" and m.get("external_id") in sessions_with_children:
                continue            # its sittings carry the 'to be announced' rows
            out.append(ra.item(_day(m["begin_date"]), "", body, item_time=_time(m["begin_date"]),
                               meeting_id=mid, detail=name, url=url))
            continue
        groups_of = {}
        for a in rows:
            k = a.get("item_affair_number") or a.get("item_number_display") or \
                a.get("item_external_id") or a.get("item_title")
            groups_of.setdefault(k, []).append(a)
        for k, alts in groups_of.items():
            alts.sort(key=lambda a: (a.get("item_language") != main, a.get("id") or 0))
            a = alts[0]
            title = ra.one_line(a.get("item_title"))
            if not title:
                continue
            others = [ra.one_line(x.get("item_title")) for x in alts[1:]
                      if x.get("item_title") and ra.one_line(x.get("item_title")) != title]
            langs = {x.get("item_language") for x in alts if x.get("item_language")}
            lang = None if len(langs) != 1 else LANG_FILE.get(next(iter(langs)))
            detail = "; ".join(x for x in [a.get("item_category"), a.get("item_description"),
                                           a.get("item_status")] + others if x)
            dated = _day(a.get("item_date")) or _day(m.get("begin_date"))
            if not ctx.in_window(dated):
                continue
            out.append(ra.item(dated, title, body, item_time=_time(a.get("item_date")) or
                               _time(m.get("begin_date")), order=a.get("item_number"),
                               meeting_id=mid, detail=detail or name,
                               reference=a.get("item_affair_number"),
                               url=a.get("item_url") or url, lang=lang))
    return out


def _opd(client, ctx):
    """The one OpenParlData read a run shares: (meetings in the window,
    their agenda items, {group id: group})."""
    cached = getattr(ctx, "_ch_opd", None)
    if isinstance(cached, Exception):
        raise cached
    if cached is not None:
        return cached
    try:
        keys = ",".join(c.upper() for c in OPD_CANTONS)
        meetings, offset = [], 0
        for page in range(OPD_MAX_PAGES):
            d = client.get_json(OPD_MEETINGS.format(keys=keys, limit=OPD_PAGE, offset=offset), FEED,
                                "opd-meetings-{0}".format(page), archive=False)
            rows = (d or {}).get("data") or []
            meetings += rows
            oldest = min((_day(r.get("begin_date")) or "9999") for r in rows) if rows else ""
            if not rows or not (d.get("meta") or {}).get("has_more") or oldest < ctx.today:
                break
            offset += OPD_PAGE
        win = [m for m in meetings if ctx.in_window(_day(m.get("begin_date")))]
        agendas, ids = [], [str(m["id"]) for m in win]
        for i in range(0, len(ids), 80):
            offset = 0
            while True:
                d = client.get_json(OPD_AGENDAS.format(ids=",".join(ids[i:i + 80]), offset=offset),
                                    FEED, "opd-agendas-{0}-{1}".format(i, offset), archive=False)
                rows = (d or {}).get("data") or []
                agendas += rows
                if not rows or not (d.get("meta") or {}).get("has_more"):
                    break
                offset += 1000
        gids = sorted({str(m["group_id"]) for m in win if m.get("group_id")})
        groups = {}
        if gids:
            d = client.get_json(OPD_GROUPS.format(ids=",".join(gids)), FEED, "opd-groups",
                                archive=False)
            groups = {g["id"]: g for g in (d or {}).get("data") or []}
        cached = (win, agendas, groups)
    except Exception as exc:                            # noqa: BLE001 - every OPD canton gaps
        setattr(ctx, "_ch_opd", exc)
        raise
    setattr(ctx, "_ch_opd", cached)
    return cached


def opd_reader(code):
    def read(client, ctx):
        win, agendas, groups = _opd(client, ctx)
        return ra.RegionRead(opd_items(code, win, agendas, groups, ctx),
                             [ra.window(ctx.today, ctx.until)], source=OPD_SOURCE)
    read.__name__ = "read_" + code
    return read


# --- Zürich: the Kantonsrat's CMI service ------------------------------------------

ZH_INDEX = "https://parlzhcdws.cmicloud.ch/parlzh3/cdws/Index/SITZUNGENDETAIL/searchdetails"
ZH_FILES = "https://parlzhcdws.cmicloud.ch/parlzh3/cdws/Files/{0}/1/pdf"
ZH_WEB = "https://www.kantonsrat.zh.ch/ratsbetrieb/sitzungenundprotokolle"


def zh_url(today, until, size=100):
    q = ('datum_start >= "{0} 00:00:00" and datum_start <= "{1} 23:59:59" '
         "sortBy datum_start/sort.ascending").format(today, until)
    return "{0}?l=de-CH&q={1}&m={2}&s=1".format(ZH_INDEX, urllib.parse.quote(q), size)


def _tag(fragment, name):
    m = re.search(r"<{0}(?:\s[^>]*)?>(.*?)</{0}>".format(name), fragment or "", re.S)
    return _html.unescape(m.group(1)).strip() if m else ""


ZH_TL_START = re.compile(r"^(\d{1,3})\.\s+(\S.*)$")
ZH_KIND = re.compile(r"^(?:Dringliche[sr]?\s|Postulat|Motion|Antrag|Interpellation|"
                     r"Parlamentarische|Einzelinitiative|Behördeninitiative|Beschluss|Bericht|"
                     r"Wahl|Leistungsmotion|Fraktionserklärung|Gesuch|Anfrage|Vorlage|"
                     r"Volksinitiative|Erklärung|Petition|KR-Nr\.|\d{4}[a-z]?\s{2,})")
ZH_END = re.compile(r"^Zürich, \d{1,2}\.")


def parse_zh_traktandenliste(text):
    """The Kantonsrat's Traktandenliste full text -> [(number, title, detail,
    reference)]: a numbered point's title runs until the line naming the
    business's kind (Postulat, Motion, Antrag ...) or its number."""
    lines = [l.strip() for l in (text or "").replace("\r", "").split("\n")]
    out, cur = [], None
    started = False
    for line in lines:
        if not started:
            started = line.startswith("Verhandlungsgegenstände")
            continue
        if ZH_END.match(line):
            break
        if not line or line.isdigit():
            continue
        m = ZH_TL_START.match(line)
        if m and int(m.group(1)) == (cur["num"] + 1 if cur else 1):
            if cur:
                out.append(cur)
            cur = {"num": int(m.group(1)), "title": [m.group(2)], "detail": [], "in_title": True}
            continue
        if cur is None:
            continue
        if cur["in_title"] and not ZH_KIND.match(line):
            cur["title"].append(line)
        else:
            cur["in_title"] = False
            cur["detail"].append(line)
    if cur:
        out.append(cur)
    result = []
    for c in out:
        title = ra.one_line(" ".join(c["title"]))
        detail = ra.one_line(" ".join(c["detail"]))
        ref = re.search(r"KR-Nr\.\s*(\d+[a-z]?/\d{4})", detail)
        vorlage = re.search(r"(?:^|\s)(\d{4}[a-z]?)\s+[A-Z]{2}\b", detail)
        result.append((c["num"], title, detail or None,
                       "KR-Nr. " + ref.group(1) if ref else (vorlage.group(1) if vorlage else None)))
    return result


def parse_zh(xml, ctx):
    """SITZUNGENDETAIL hits -> items: committee Traktanden as structured,
    the Kantonsrat's from its Traktandenliste document, else one 'to be
    announced' row per sitting."""
    out = []
    for hit in re.findall(r"<Hit .*?</Hit>", xml or "", re.S):
        guid = re.search(r'<Sitzung OBJ_GUID="([0-9a-f]+)"', hit)
        guid = guid.group(1) if guid else None
        head = hit.split("<Sitzungsdokumente>")[0]
        title = _tag(head, "Titel")
        start = re.search(r"<Datum><Start[^>]*>(\d{4}-\d{2}-\d{2})", hit)
        dated = start.group(1) if start else None
        if not ctx.in_window(dated):
            continue
        time = _tag(head, "Uhrzeit") or None
        gremium = re.search(r"<Gremium OBJ_GUID[^>]*><Name>(.*?)</Name><Kurzname>(.*?)</Kurzname>",
                            hit, re.S)
        body = _html.unescape(gremium.group(1)) if gremium else "Kantonsrat"
        mid = "zh-" + (guid or "{0}-{1}".format(dated, ra.slug(body, 20)))
        items = []
        for tr in re.findall(r"<Traktandum .*?</Traktandum>", hit, re.S):
            t = _tag(tr, "Titel")
            nr = _tag(tr, "TraktandenNr")
            vorlage = _tag(tr, "VorlageNr")
            krnr = _tag(tr, "KRNummer")
            if t:
                items.append(ra.item(dated, t, body, item_time=time,
                                     order=int(nr) if nr.isdigit() else None, meeting_id=mid,
                                     detail=title, reference=("KR-Nr. " + krnr) if krnr else
                                     (vorlage or None), url=ZH_WEB))
        if not items:
            for doc in re.findall(r"<Dokument .*?</Dokument>", hit, re.S):
                if _tag(doc, "Kategorie") != "Traktandenliste":
                    continue
                full = re.search(r"<Fulltext[^>]*>(.*?)</Fulltext>", doc, re.S)
                eid = re.search(r'<eDokument ID="([^"]+)"', doc)
                for num, t, detail, ref in parse_zh_traktandenliste(
                        _html.unescape(full.group(1)) if full else ""):
                    items.append(ra.item(dated, t, body, item_time=time, order=num, meeting_id=mid,
                                         detail=detail, reference=ref,
                                         url=ZH_FILES.format(eid.group(1)) if eid else ZH_WEB))
                break
        out += items or [ra.item(dated, "", body, item_time=time, meeting_id=mid, detail=title,
                                 url=ZH_WEB)]
    return out


def read_zh(client, ctx):
    xml = client.get_text(zh_url(ctx.today, ctx.until), FEED, "zh-sitzungen", archive=False)
    hits = re.search(r'numHits="(\d+)"', xml or "")
    if hits is None:
        raise FetchError(ZH_INDEX, FEED, "zh-sitzungen", 1, "no SearchDetailResponse in the reply")
    items = parse_zh(xml, ctx)
    gaps = []
    if int(hits.group(1)) > 100:
        gaps.append("zh: {0} sittings in the window, the first 100 read".format(hits.group(1)))
    return ra.RegionRead(items, [] if gaps else [ra.window(ctx.today, ctx.until)],
                         source="parlzhcdws.cmicloud.ch SITZUNGENDETAIL", gaps=gaps)


# --- Geneva --------------------------------------------------------------------------

GE = "https://ge.ch"
GE_SESSIONS = GE + "/grandconseil/sessions/seances/{0}/"
_FR_DAY = re.compile(r"(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi)\s+(\d{1,2})(?:er)?\s+"
                     r"([a-zéû]+)\s+à\s+(\d{1,2})h(\d{2})?", re.I)


def parse_ge_sessions(page, year):
    """The year's sessions -> [(session id, label, [(date, time)], odj url)]."""
    out = []
    parts = re.split(r'<div id="(\d{6})" class="anchor">', page or "")
    for i in range(1, len(parts) - 1, 2):
        sid, block = parts[i], parts[i + 1]
        label = ra.one_line(ra.clean(_tag(block, "h2")))
        odj = re.search(r'href="(/grandconseil/sessions/seances-odj-lion/[^"]+)"', block)
        sittings = []
        for m in _FR_DAY.finditer(ra.one_line(ra.clean(block))):
            d = ra.iso(m.group(1), m.group(2), year)
            if d:
                sittings.append((d, "{0}:{1}".format(m.group(3).zfill(2), m.group(4) or "00")))
        out.append((sid, label, sittings,
                    GE + _html.unescape(odj.group(1)) if odj else None))
    return out


def parse_ge_odj(page, dated, sid, url=None):
    """The HTML order of the day: each numbered point; an object row's
    number (PL 13694-A, M 3201, E 3249 ...) and title, a heading row's
    words."""
    out, order = [], 0
    for row in re.findall(r"<tr>(.*?)</tr>", page or "", re.S):
        num = re.search(r'<td class="numOdj">(.*?)</td>', row, re.S)
        if not num:
            continue
        number = ra.one_line(ra.clean(num.group(1)))
        obj = re.search(r'<td class="objet">(.*?)</td>', row, re.S)
        if obj:
            refm = re.search(r'<div class="num">(.*?)</div>', row, re.S)
            ref = ra.one_line(ra.clean(refm.group(1))) if refm else None
            text = obj.group(1).split('<div class="rapporteur">')[0]
            title = ra.one_line(ra.clean(text))
            rapp = ra.one_line(ra.clean(obj.group(1)[len(text):]))
            cat = re.search(r'<div class="categorie">(.*?)</div>', row, re.S)
            detail = "; ".join(x for x in [ra.one_line(ra.clean(cat.group(1))) if cat else "", rapp]
                               if x)
        else:
            head = re.search(r'<td colspan="2"\s+class="titre_4">(.*?)</td>', row, re.S)
            if not head or not number:
                continue
            title, ref, detail = ra.one_line(ra.clean(head.group(1))), None, ""
        if not title:
            continue
        order += 1
        out.append(ra.item(dated, title, "Grand Conseil", order=order, meeting_id="ge-" + sid,
                           detail=detail or None, reference=ref or (number or None), url=url))
    return out


def read_ge(client, ctx):
    items, gaps, ok, read = [], [], True, []
    for year in sorted({ctx.today[:4], ctx.until[:4]}):
        try:
            page = client.get_text(GE_SESSIONS.format(year), FEED, "ge-sessions-" + year)
        except FetchError as exc:
            if year == ctx.today[:4]:
                raise
            gaps.append("ge sessions {0}: {1}".format(year, str(exc)[:120]))
            continue
        for sid, label, sittings, odj in parse_ge_sessions(page, year):
            days = [s for s in sittings if ctx.in_window(s[0])]
            if not days:
                continue
            got = []
            if odj:
                try:
                    got = parse_ge_odj(client.get_text(odj, FEED, "ge-odj-" + sid), days[0][0], sid,
                                       odj)
                except FetchError as exc:
                    gaps.append("ge order of the day {0}: {1}".format(label, str(exc)[:120]))
                    ok = False
                    continue
                for it in got:
                    it["item_time"] = days[0][1]
                    it["detail"] = "; ".join(x for x in [it["detail"], "Session " + ", ".join(
                        d for d, _ in days)] if x)[:4000]
            if got:
                items += got
            else:
                seen = set()
                for d, t in days:
                    if d not in seen:
                        seen.add(d)
                        items.append(ra.item(d, "", "Grand Conseil", item_time=t,
                                             meeting_id="ge-{0}-{1}".format(sid, d),
                                             detail="Session " + label,
                                             url=GE_SESSIONS.format(year) + sid))
            read.append(sid)
    units = [ra.window(ctx.today, ctx.until)] if ok and not gaps else []
    return ra.RegionRead(items, units, source="ge.ch Grand Conseil sessions + orders of the day",
                         gaps=gaps)


# --- Vaud -------------------------------------------------------------------------------

VD = "https://www.vd.ch"
VD_LIST = VD + "/gc/seances-du-grand-conseil"


def parse_vd_list(page):
    """Sittings listed -> [(date, url)]."""
    out = []
    for m in re.finditer(r'<a[^>]*href="(/gc/seances-du-grand-conseil/detail-seance/seance-gc/\d+)"'
                         r'[^>]*>\s*Séance du Grand Conseil du ([^<]+)', page or ""):
        d = ra.find_date(m.group(2).replace("1er", "1"))
        if d:
            out.append((d, VD + m.group(1)))
    return out


def parse_vd_sitting(page, dated, url=None):
    out = []
    for p in re.findall(r'<div class="mb-4"><p>(.*?)</p></div>', page or "", re.S):
        p = re.sub(r"<strong>.*?</strong>|<em>.*?</em>", " ", p, flags=re.S)
        text = ra.one_line(ra.clean(p))
        m = re.match(r"(\d+(?:\.\d+)*)\.\s+(.*)", text)
        if not m:
            continue
        num, rest = m.groups()
        ref = re.match(r"\((\d{2}_[A-Z]+_\d+[A-Z]?)\)\s*(.*)", rest)
        title = ref.group(2) if ref else rest
        if not title:
            continue
        link = re.search(r'href="(/gc/seances-du-grand-conseil/point-seance/[^"]+)"', p)
        out.append(ra.item(dated, title, "Grand Conseil", meeting_id="vd-" + dated,
                           detail="point " + num, reference=ref.group(1) if ref else None,
                           url=VD + link.group(1) if link else url,
                           order=int(num.split(".")[0])))
    return out


def read_vd(client, ctx):
    listed = [(d, u) for d, u in parse_vd_list(client.get_text(VD_LIST, FEED, "vd-list"))
              if ctx.in_window(d)]
    items, gaps, ok = [], [], True
    for d, u in listed:
        try:
            items += parse_vd_sitting(client.get_text(u, FEED, "vd-" + d), d, u) or \
                [ra.item(d, "", "Grand Conseil", meeting_id="vd-" + d, url=u)]
        except FetchError as exc:
            gaps.append("vd sitting {0}: {1}".format(d, str(exc)[:120]))
            ok = False
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)] if ok else [],
                         source="vd.ch séances du Grand Conseil", gaps=gaps,
                         note="" if listed else "no sitting listed yet (the calendar is a PDF)")


# --- Ticino --------------------------------------------------------------------------------

TI = "https://www4.ti.ch/poteri/gc/attivita/"
TI_ODG = TI + "ordine-del-giorno/"
TI_CAL = TI + "calendario-delle-sedute"
_IT_DAY = re.compile(r"(Lunedì|Martedì|Mercoledì|Giovedì|Venerdì)\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})"
                     r"(?:\s*-\s*(\d{1,2}:\d{2}))?", re.I)


def parse_ti_odg(page):
    """The order of the day of the next sitting -> (date, time, [items])."""
    m = _IT_DAY.search(ra.one_line(ra.clean(page)))
    if not m:
        return None, None, []
    dated = ra.iso(m.group(2), m.group(3), m.group(4))
    out = []
    for row in re.split(r'<div class="row odgOggetto">', page or "")[1:]:
        num = re.search(r'numOggetto">\s*(\d+)', row)
        dept = re.search(r'<div class="col-xs-2">\s*([A-Z]+)', row)
        body = re.search(r'<div class="col-xs-7">(.*?)</div>', row, re.S)
        if not body:
            continue
        paras = [ra.one_line(ra.clean(p)).lstrip("•").strip()
                 for p in re.findall(r"<p>(.*?)</p>", body.group(1), re.S)]
        paras = [p for p in paras if p]
        if not paras:
            continue
        heads = [p for p in paras if not p.startswith("-")]
        title = heads[0] if heads else paras[0]
        link = re.search(r'href="(//www4\.ti\.ch/index\.php\?[^"]+)"', body.group(1))
        attid = re.search(r"\[attid\]=(\d+)", body.group(1))
        out.append(ra.item(dated, title, "Gran Consiglio", item_time=m.group(5),
                           order=int(num.group(1)) if num else None, meeting_id="ti-" + dated,
                           detail="; ".join(p.lstrip("- ") for p in paras[1:]) or None,
                           reference=attid.group(1) if attid else (dept.group(1) if dept else None),
                           url="https:" + _html.unescape(link.group(1)) if link else TI_ODG,
                           lang=IT))
    return dated, m.group(5), out


def parse_ti_calendar(page):
    """'26 - 27 ottobre 2026' / '10 maggio 2027' -> [(first day, last day, label)]."""
    out = []
    lines = ra.clean(page).split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s+([a-z]+)\s+(\d{4})$", line.strip())
        if not m:
            continue
        first = ra.iso(m.group(1), m.group(3), m.group(4))
        last = ra.iso(m.group(2), m.group(3), m.group(4)) if m.group(2) else first
        if first and last:
            out.append((first, last, lines[i + 1].strip() if i + 1 < len(lines) else ""))
    return out


def read_ti(client, ctx):
    dated, time, items = parse_ti_odg(client.get_text(TI_ODG, FEED, "ti-odg"))
    items = [it for it in items if ctx.in_window(it["dated"])]
    gaps = []
    try:
        sessions = parse_ti_calendar(client.get_text(TI_CAL, FEED, "ti-calendar"))
    except FetchError as exc:
        sessions = []
        gaps.append("ti calendar: {0}".format(str(exc)[:120]))
    for first, last, label in sessions:
        if not ctx.in_window(first) or (dated and first <= dated <= last and items):
            continue
        items.append(ra.item(first, "", "Gran Consiglio", meeting_id="ti-" + first,
                             detail="Sessione {0} - {1}: {2}".format(first, last, label),
                             url=TI_CAL))
    if gaps:
        units = [ra.meeting("ti-" + dated)] if dated and items else []
    else:
        units = [ra.window(ctx.today, ctx.until)]
    return ra.RegionRead(items, units, source="ti.ch ordine del giorno + calendario", gaps=gaps)


# --- Valais ------------------------------------------------------------------------------------

VS_API = "https://parlement.vs.ch/api/fe/v1/"
VS_SESSIONS = (VS_API + "parl_sessions?q%5Bsorts%5D%5B%5D=year%20desc&q%5Bsorts%5D%5B%5D="
               "month%20desc&limit=3&mode=short_detail")
VS_SESSION = VS_API + "parl_session?id={0}"
VS_WEB = "https://parlement.vs.ch/app/de/search/parl_session/{0}"


def parse_vs_session(data, ctx):
    """One session's sittings and their agenda items; a date with no
    sitting programme yet is 'to be announced'."""
    sid = data.get("id")
    out, scheduled = [], set()
    for day in data.get("sittings_schedule") or []:
        for sitting in day.get("sittings") or []:
            dated = sitting.get("date") or day.get("date")
            if not ctx.in_window(dated):
                continue
            scheduled.add(dated)
            mid = "vs-{0}".format(sitting.get("id"))
            when = {"am": "Vormittag", "pm": "Nachmittag"}.get(sitting.get("am_pm"))
            trs = sitting.get("parl_transactions") or []
            for order, tr in enumerate(trs, 1):
                label = ra.one_line(tr.get("label"))
                if label:
                    out.append(ra.item(dated, label, "Grand Conseil", order=order, meeting_id=mid,
                                       detail="; ".join(x for x in [tr.get("parl_process_category_label"),
                                                                     sitting.get("label")] if x),
                                       item_time=when, url=VS_WEB.format(sid)))
            if not trs:
                out.append(ra.item(dated, "", "Grand Conseil", meeting_id=mid, item_time=when,
                                   detail=sitting.get("label"), url=VS_WEB.format(sid)))
    for dated in data.get("dates") or []:
        if ctx.in_window(dated) and dated not in scheduled:
            out.append(ra.item(dated, "", "Grand Conseil", meeting_id="vs-{0}-{1}".format(sid, dated),
                               detail=data.get("label"), url=VS_WEB.format(sid)))
    return out


def read_vs(client, ctx):
    sessions = client.get_json(VS_SESSIONS, FEED, "vs-sessions")
    items = []
    for s in sessions or []:
        dates = s.get("dates") or []
        if not any(ctx.in_window(d) for d in dates):
            continue
        detail = client.get_json(VS_SESSION.format(s["id"]), FEED, "vs-session-{0}".format(s["id"]))
        detail.setdefault("dates", dates)
        items += parse_vs_session(detail, ctx)
    return ra.RegionRead(items, [ra.window(ctx.today, ctx.until)],
                         source="parlement.vs.ch app JSON (parl_sessions)")


# --- Zug ---------------------------------------------------------------------------------------

ZG = "https://kr-geschaefte.zug.ch"
ZG_LIST = ZG + "/gast/traktandenlisten"


def parse_zg_list(page):
    return [(ra.find_date(d), ZG + href) for href, d in
            re.findall(r'<a href="(/gast/traktandenlisten/\d+)">\s*(\d{2}\.\d{2}\.\d{4})', page or "")
            if ra.find_date(d)]


def parse_zg_agenda(page, dated, url=None):
    time = re.search(r"(\d{1,2})\.(\d{2})\s*-\s*ca\.", ra.clean(page))
    out = []
    for row in re.split(r"<tr data-traktandum-id=", page or "")[1:]:
        num = re.search(r'<td class="col-md-1">([\d.]+)</td>', row)
        cell = re.search(r'<td class="col-md-11">(.*)', row, re.S)
        if not num or not cell:
            continue
        head = cell.group(1).split("<table")[0]
        title = ra.one_line(ra.clean(head))
        if not title:
            continue
        nrs = re.findall(r'<td class="col-sm-2">\s*(\d{4})\.', cell.group(1))
        link = re.search(r'href="(/gast/geschaefte/\d+)"', head)
        out.append(ra.item(dated, title, "Kantonsrat", order=None, meeting_id="zg-" + dated,
                           item_time="{0}:{1}".format(time.group(1).zfill(2), time.group(2)) if time
                           else None, detail="Traktandum " + num.group(1).rstrip("."),
                           reference=nrs[0] if nrs else None,
                           url=ZG + link.group(1) if link else url))
    return out


def read_zg(client, ctx):
    listed = [(d, u) for d, u in parse_zg_list(client.get_text(ZG_LIST, FEED, "zg-list"))
              if ctx.in_window(d)]
    items, gaps = [], []
    for d, u in listed:
        try:
            items += parse_zg_agenda(client.get_text(u, FEED, "zg-" + d), d, u) or \
                [ra.item(d, "", "Kantonsrat", meeting_id="zg-" + d, url=u)]
        except FetchError as exc:
            gaps.append("zg agenda {0}: {1}".format(d, str(exc)[:120]))
    return ra.RegionRead(items, [] if gaps else [ra.window(ctx.today, ctx.until)],
                         source="kr-geschaefte.zug.ch Traktandenlisten", gaps=gaps,
                         note="" if listed else "no Traktandenliste published for the window yet "
                                                "(the sitting calendar is a PDF)")


BI_FR = [DE, FR]

REGIONS = {
    "zh": ra.region("Zürich", reader=read_zh),
    "be": ra.region("Bern", reader=opd_reader("be"), langs=BI_FR),
    "lu": ra.region("Luzern", reader=opd_reader("lu")),
    "ur": ra.region("Uri", reader=opd_reader("ur")),
    "sz": ra.region("Schwyz", reader=opd_reader("sz")),
    "ow": ra.region("Obwalden", reader=opd_reader("ow")),
    "nw": ra.region("Nidwalden", reader=opd_reader("nw")),
    "gl": ra.region("Glarus", reader=opd_reader("gl")),
    "zg": ra.region("Zug", reader=read_zg),
    "fr": ra.region("Fribourg", status="blocked", langs=BI_FR,
                    note="www.fr.ch robots.txt disallows /fr/, /search/ and ?page; the Grand "
                         "Council's parlinfo.fr.ch sitting pages redirect to www.fr.ch/node/..., "
                         "also disallowed; OpenParlData has no Fribourg meetings ahead"),
    "so": ra.region("Solothurn", reader=opd_reader("so")),
    "bs": ra.region("Basel-Stadt", reader=opd_reader("bs")),
    "bl": ra.region("Basel-Landschaft", reader=opd_reader("bl")),
    "sh": ra.region("Schaffhausen", status="no-route",
                    note="sh.ch's Kantonsrat pages answered 404/500 on 16 October 2026 and "
                         "OpenParlData has no Schaffhausen meetings; not built"),
    "ar": ra.region("Appenzell Ausserrhoden", reader=opd_reader("ar")),
    "ai": ra.region("Appenzell Innerrhoden", reader=opd_reader("ai")),
    "sg": ra.region("St. Gallen", reader=opd_reader("sg")),
    "gr": ra.region("Graubünden", reader=opd_reader("gr"), langs=[DE, IT]),
    "ag": ra.region("Aargau", status="blocked",
                    note="www.ag.ch robots.txt disallows the whole Grosser Rat section; "
                         "OpenParlData republishes it but is not used while the canton's own "
                         "refusal stands (waiting on Chris: ask the Parlamentsdienst)"),
    "tg": ra.region("Thurgau", reader=opd_reader("tg")),
    "ti": ra.region("Ticino", reader=read_ti, langs=[IT]),
    "vd": ra.region("Vaud", reader=read_vd, langs=[FR]),
    "vs": ra.region("Valais", reader=read_vs, langs=BI_FR),
    "ne": ra.region("Neuchâtel", status="no-route", langs=[FR],
                    note="orders of the day and the session plan only as PDFs on www.ne.ch "
                         "(/autorites/grand-conseil/ordres-du-jour); OpenParlData has no "
                         "Neuchâtel meetings"),
    "ge": ra.region("Genève", reader=read_ge, langs=[FR]),
    "ju": ra.region("Jura", status="no-route", langs=[FR],
                    note="jura.ch's plenary calendar and orders of the day are nested archive "
                         "pages with documents, no readable list found; OpenParlData has no "
                         "Jura meetings; not built"),
}
