"""Assemblée nationale du Québec: roster, bills and recorded divisions.

Driven by tools/prov_collect.py --prov qc. Scope: docs/canada-provinces-scope.md
(Quebec: value 4, difficulty 4). Every source is official, open and keyless.
robots.txt is honoured in full -- including the groups urllib.robotparser
drops (src/prov_fetch.star_rules): the vote register's data feed under
/json/ is DISALLOWED and is never requested; the procès-verbaux are the
lawful route to the names.

  * SITTINGS. /fr/travaux-parlementaires/assemblee-nationale/<leg>-<sess>/
    index.html lists ONE month of sittings, each with its Journal des débats
    page and its procès-verbal (PV) PDF. Other months come only through the
    page's own ASP.NET form (a POST of the month select): the PV ids
    (MediaId=ANQ.Vigie.Bll.DocumentGenerique_220051) cannot be guessed, so
    every PV URL is taken from that listing, never constructed.
  * DIVISIONS. The PV body records each named vote -- "La motion est adoptée
    par le vote suivant : (Vote n° 165 en annexe) Pour : 73 Contre : 35
    Abstention : 0" -- and the ANNEXE at the end of the PV prints every
    member who voted as "Surname (PARTY)", with "(Riding)" on the next line
    where two members share a surname, in FOUR columns read top to bottom.
    A riding line wraps under ITS OWN column, so in the plain text stream it
    lands next to the wrong name; the annex is therefore read from pypdf's
    layout fragments with x-positions (parse_annex). The same annex layout
    is printed before and after electronic voting (2025): checked on the PVs
    of 29 Oct 2013, 16 Jun 2019, 7 Jun 2023 and 1 Apr 2026. Since electronic
    voting the Journal des débats prints totals only, so the PV is the only
    source of names; before it, the PV carries them too, and the Journal is
    not needed for votes at all.
  * PARTY AT THE VOTE is printed in the annex beside each name ("Dubé
    (IND)") and is stored exactly as printed: it is a fact of the record, not
    a join to a roster.
  * ROSTER, DATED. The heritage pages "Membres de l'Assemblée nationale par
    circonscription" (/fr/patrimoine/depcir/, one page per letter, each
    linking the next) list every riding's members election by election, with
    the member's id, the party ELECTED under, and remarks ("démissionne le
    16-12-2011"). Election dates come from /fr/patrimoine/election.html and
    by-election dates from /fr/patrimoine/partielles.html. A term runs from
    the election to the day before the next member's, the remark's date, or
    the next general election. The party on a term is the party at ELECTION
    and is undated (party_dated = 0): a floor-crosser's party at the vote
    comes from the annex, never from the term.
  * A GENERAL ELECTION IS DUE ON 5 OCTOBER 2026. The 43rd legislature's last
    term ends at the next general election once election.html lists it; new
    members arrive in depcir with the 2026 rows, and the roster is re-read
    when it is a week old (or with --refresh). Nothing about the roster
    assumes the 43rd legislature.
  * BILLS. The session's bill listing (projets-loi-<leg>-<sess>.html) gives
    every bill with its OWN page link: a bill reinstated from an earlier
    session keeps its first session's key (Bill 94 adopted in 43-2 is
    projet-loi-94-43-1, so qc-43-1/94), and a division naming "projet de loi
    n° 94" in 43-2 is joined through that listing, never by building a key.
    Each bill page gives the author (member id), the type, every stage with
    the sittings it was taken on and the page's own outcome notes ("Vote :
    Pour 73, Contre 35, Abstention 0", "à la majorité des voix"), and the
    presentation text PDF (French only), which is classified per passage
    with the French layer. The English page gives title_en.
  * VOICE. A stage (principe, prise en considération, adoption) whose final
    sitting on the bill page carries no "Vote :" note was decided without a
    recorded division, and is stored as kind = 'voice' with the page's own
    words.
  * CROSS-CHECK. Every bill-page "Vote : Pour X, Contre Y" on a day whose PV
    was read must match a recorded division on that bill with those totals,
    or it is a gap.

CLASSIFICATION is in FRENCH (config/taxonomy-qc.yaml, master
docs/keyword-taxonomy-qc.md), on the bill's French title and text and on
each vote's own words in the PV; the English taxonomy reads the English
title only. The Journal des débats (speeches) is not read yet.
"""

from __future__ import annotations

import datetime
import html as _html
import io
import json
import re
from urllib.parse import urljoin

from src import prov_classify as pc, prov_names as pn, prov_store as ps
from src.prov_fetch import Unreadable, html_text

PROV = "qc"
CURRENT_SESSION = "43-3"
BASE = "https://www.assnat.qc.ca"
SITTINGS = BASE + "/fr/travaux-parlementaires/assemblee-nationale/{0}-{1}/index.html"
BILLS = BASE + "/fr/travaux-parlementaires/projets-loi/projets-loi-{0}-{1}.html"
DEPCIR = BASE + "/fr/patrimoine/depcir/index.html"
ELECTIONS = BASE + "/fr/patrimoine/election.html"
BYELECTIONS = BASE + "/fr/patrimoine/partielles.html"
ROSTER = BASE + "/fr/deputes/index.html"
ROSTER_MAX_AGE_DAYS = 7
MONTH_FIELD = "ctl00$ColCentre$ContenuColonneGauche$ddlChoixMoisAnnee$MoisAnnee"
MONTH_BUTTON = "ctl00$ColCentre$ContenuColonneGauche$btnRechercher"

# Party names as depcir prints them -> the abbreviations the annex prints.
PARTIES = {
    "coalition avenir quebec": "CAQ", "liberal": "PLQ", "parti liberal du quebec": "PLQ",
    "parti quebecois": "PQ", "quebec solidaire": "QS", "action democratique du quebec": "ADQ",
    "independant": "IND", "independante": "IND", "option nationale": "ON",
    "parti conservateur du quebec": "PCQ", "equipe democratie": "ED",
}

_MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
           "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
           "decembre": 12}
_FR_DATE = re.compile(r"(\d{1,2})\s*(?:er|re)?\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})")
_NUM_DATE = re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b")


def parse_session(code):
    m = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not m:
        raise ValueError("Quebec session must look like 43-2, not {0!r}".format(code))
    return int(m.group(1)), int(m.group(2))


def fr_date(text):
    """ISO date of the first French date in `text` ('jeudi 2 avril 2026',
    '1er avril 2026', '16-12-2011'), or None."""
    s = pn.fold(text)
    m = _FR_DATE.search(s)
    if m:
        try:
            return datetime.date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = _NUM_DATE.search(s)
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def _day_before(iso):
    return (datetime.date.fromisoformat(iso) - datetime.timedelta(days=1)).isoformat()


def display_case(name):
    """'ST-PIERRE' -> 'St-Pierre', "D'AMOURS" -> "D'Amours". Display only:
    matching folds case."""
    def one(w):
        return w[:1].upper() + w[1:].lower() if w else w
    return re.sub(r"[^\s\-–—'’]+", lambda m: one(m.group(0)), name or "")


# -- the sitting index ------------------------------------------------------

def _attrs(tag):
    return {k.lower(): _html.unescape(v) for k, v in re.findall(r'([\w:$\-]+)="([^"]*)"', tag)}


def form_fields(page, month):
    """The page's own ASP.NET form, filled as the browser would send it with
    `month` (YYYYMM) chosen and the search button pressed."""
    fields = []
    for tag in re.findall(r"<input\b[^>]*>", page or "", re.I):
        a = _attrs(tag)
        if not a.get("name"):
            continue
        kind = a.get("type", "text").lower()
        if kind == "hidden":
            fields.append((a["name"], a.get("value", "")))
        elif kind == "text":
            fields.append((a["name"], ""))
    for m in re.finditer(r"<select\b([^>]*)>(.*?)</select>", page or "", re.S | re.I):
        a = _attrs(m.group(1))
        name = a.get("name")
        if not name:
            continue
        if name == MONTH_FIELD:
            fields.append((name, month))
            continue
        opts = re.findall(r'<option\b([^>]*)>', m.group(2))
        chosen = next((o for o in opts if "selected" in o), opts[0] if opts else None)
        fields.append((name, _attrs(chosen).get("value", "") if chosen else ""))
    fields.append((MONTH_BUTTON, "Rechercher"))
    return fields


def month_options(page):
    """['202604', '202603', ...] from the month select, and the selected one."""
    m = re.search(r'<select name="' + re.escape(MONTH_FIELD) + r'"[^>]*>(.*?)</select>', page or "", re.S)
    if not m:
        return [], None
    opts = re.findall(r'<option\s+(selected="selected"\s+)?value="(\d{6})"', m.group(1))
    return [v for _, v in opts], next((v for sel, v in opts if sel), None)


def parse_sittings(page):
    """[{date, label, extraordinary, jd_url, pv_url}] for the month shown."""
    out = []
    for block in re.split(r"<h3>\s*Le\s+", page or "")[1:]:
        head = re.sub(r"\s+", " ", _html.unescape(block[:block.find("</h3>")])).strip()
        date = fr_date(head)
        body = block[:block.find("<h3>")] if "<h3>" in block else block
        pv = re.search(r"<a href='([^']+)'>\s*Procès-verbal de l'Assemblée", body)
        jd = re.search(r"<a href='(/fr/travaux-parlementaires/assemblee-nationale/[^']+/journal-debats/\d{8}/\d+\.html)'",
                       body)
        if not date:
            continue
        out.append({"date": date, "label": head,
                    "extraordinary": "extraordinaire" in pn.fold(head),
                    "pv_url": urljoin(BASE, _html.unescape(pv.group(1))) if pv else None,
                    "jd_url": urljoin(BASE, jd.group(1)) if jd else None})
    return out


def list_records(ctx, legislature, session):
    """Every sitting of the session in the window, oldest first, each with
    the PV URL from the listing. Months outside the window are not asked."""
    url = SITTINGS.format(legislature, session)
    page = ctx.text(url, "sittings-{0}-{1}".format(legislature, session))
    if page is None:
        return [], 0
    months, shown = month_options(page)
    if not months:
        ctx.gap("qc sittings {0}-{1}: no month select on the index page".format(legislature, session))
    pages = 1
    records = parse_sittings(page)
    for mo in months:
        if mo == shown:
            continue
        first = "{0}-{1}-01".format(mo[:4], mo[4:])
        last = "{0}-{1}-31".format(mo[:4], mo[4:])
        if (ctx.since and last < ctx.since) or (ctx.until and first > ctx.until):
            continue
        got = ctx.post_form(url, form_fields(page, mo), "sittings-{0}-{1}-{2}".format(legislature, session, mo))
        if got is None:
            continue
        pages += 1
        _, now = month_options(got)
        if now != mo:
            ctx.gap("qc sittings {0}-{1}: asked for month {2}, the page shows {3}".format(
                legislature, session, mo, now))
            continue
        records.extend(parse_sittings(got))
    seen, out = set(), []
    for r in sorted(records, key=lambda r: (r["date"], r["label"])):
        if not ctx.in_window(r["date"]):
            continue
        key = (r["date"], r["pv_url"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    # Two sittings on one day get a part suffix so their keys differ.
    by_day = {}
    for r in out:
        by_day.setdefault(r["date"], []).append(r)
    for day in by_day.values():
        for k, r in enumerate(day):
            r["part"] = str(k + 1) if len(day) > 1 and k else None
    return out, pages


# -- the roster ---------------------------------------------------------------

# Any empty anchors may precede the name: FABRE carries '<a name="f"></a>' (the
# letter's own anchor) before its riding anchor, and a pattern that wanted one
# anchor filed Fabre's members under Duplessis.
_RIDING_HEAD = re.compile(r'<h3 class="textAligneCentre">(?:\s*<a[^>]*></a>)*(.*?)</h3>', re.S)
# A riding's years of existence, printed where a name was reused:
# "PRÉVOST (1973-2012)", "SOULANGES (1867 - 1936)". Not part of the name.
_RIDING_YEARS = re.compile(r"\s*\(\s*\d{4}\s*-\s*\d{4}\s*\)\s*$")
# Rows from general elections before this year are not stored: no division
# before it is read (the procès-verbal annexes checked run from 2013), and
# the 1867 and 1871 elections have no single polling date to start a term.
ROSTER_FROM_YEAR = 1960


def riding_name(heading_html):
    """'SAINT-HENRI<sup>__</sup>SAINTE-ANNE' -> 'SAINT-HENRI–SAINTE-ANNE':
    depcir prints the en dash of a compound riding as an underlined gap."""
    text = re.sub(r"<sup>\s*_+\s*</sup>", "–", heading_html or "")
    return _RIDING_YEARS.sub("", html_text(text).replace("__", "–")).strip()
# The link text may carry markup: '<span class="nomDepute">FOURNIER,
# Catherine</span>' (Marie-Victorin, 2016 and 2018). A pattern that wanted
# bare text dropped her rows WITHOUT A WORD and left 'Fournier (IND)'
# unresolved in 24 divisions of June 2019.
_MEMBER_LINK = re.compile(r'<a href="([^"]*/fr/deputes/[^"]*?-(\d+)/index\.html)">(.*?)</a>', re.S)


def parse_depcir(page):
    """{riding: [{year, by_election, member_id, href, surname, given, party, remark}]}
    and the relative links to the other letter pages."""
    out = {}
    chunks = _RIDING_HEAD.split(page or "")
    for i in range(1, len(chunks) - 1, 2):
        riding = riding_name(chunks[i])
        rows = []
        for tr in re.findall(r"<tr>(.*?)</tr>", chunks[i + 1], re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) < 3:
                continue
            year = html_text(tds[0])
            ym = re.match(r"^(\d{4})\b", year)
            if not ym:
                continue
            link = next((m for m in _MEMBER_LINK.finditer(tds[1]) if html_text(m.group(3))), None)
            cell = html_text(tds[1])
            if not link and re.match(r"^\(?\s*Voir\b", cell):
                continue                       # a cross-reference row, not a member
            if not link and "," not in cell:
                rows.append({"year": int(ym.group(1)), "unparsed": cell})
                continue
            # A member printed WITHOUT a link (Boissonneault, Arthabaska 2025;
            # Bernard, Rouyn-Noranda 2022): member_id None, joined to the
            # current roster by name in fetch_roster, else keyed by name.
            surname, _, given = (html_text(link.group(3)) if link else cell).partition(",")
            rows.append({"year": int(ym.group(1)), "by_election": "partielle" in pn.fold(year),
                         "member_id": link.group(2) if link else None,
                         "href": urljoin(BASE, link.group(1)) if link else None,
                         "surname": surname.strip(), "given": given.strip(),
                         "party": html_text(tds[2]) or None,
                         "remark": html_text(tds[3]) if len(tds) > 3 else ""})
        out.setdefault(riding, []).extend(rows)
    links = sorted(set(re.findall(r'href="([a-z][a-z\-]*\.html)"', page or "")))
    return out, links


def parse_elections(page):
    """({year: ISO polling date}, {ISO polling date: legislature number})
    from election.html, one row per general election since 1867. The
    legislature is the row's ORDINAL, counted over every row -- 1867's poll
    is printed as "Août-septembre 1867", which is no date but is still the
    1st legislature."""
    dates, numbers, n = {}, {}, 0
    for tr in re.findall(r"<tr>(.*?)</tr>", page or "", re.S):
        tds = [html_text(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) < 2 or not re.search(r"\b(1[89]\d\d|20\d\d)\b", tds[1]):
            continue
        n += 1
        d = fr_date(tds[1])
        if d:
            dates.setdefault(int(d[:4]), d)
            numbers[d] = n
    return dates, numbers


def parse_byelections(page):
    """{(squashed riding, year): [ISO dates]} from partielles.html."""
    out = {}
    for tr in re.findall(r"<tr>(.*?)</tr>", page or "", re.S):
        tds = [html_text(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) >= 2:
            d = fr_date(tds[0])
            if d:
                out.setdefault((pn.squash(tds[1].replace("__", "–")), int(d[:4])), []).append(d)
    return {k: sorted(v) for k, v in out.items()}


def party_code(name):
    return PARTIES.get(pn.fold(name or "").strip(), name)


def build_terms(ridings, elections, byelections, gaps=None, legislatures=None):
    """[(member_key, member, term)] -- one term per depcir row, dated.

    start: the general election of that year, or the by-election's date.
    end: the earliest of the day before the riding's next row starts, the
    remark's date (resignation, death, appointment) and the day before the
    next general election. No end while no later election is known: the
    current members' terms stay open until the next one is listed."""
    gaps = gaps if gaps is not None else []
    link_ids(ridings, {})                  # any row still without an id gets one
    general = sorted(elections.values())
    legislature_of = legislatures or {}
    out = []
    for riding, rows in ridings.items():
        # A riding's rows run forward in time. A year that goes BACK means a
        # heading was missed and another riding's members were filed here
        # (Fabre under Duplessis, until the heading pattern was fixed).
        years = [r["year"] for r in rows]
        if any(b < a for a, b in zip(years, years[1:])):
            gaps.append("qc roster: {0}: years run backwards ({1}); a riding heading was not "
                        "read, its rows are not trusted and not stored".format(
                            riding, ", ".join(str(y) for y in years[-8:])))
            continue
        rows = [r for r in rows if r["year"] >= ROSTER_FROM_YEAR]
        for r in [r for r in rows if "unparsed" in r]:
            gaps.append("qc roster: {0} {1}: no member link in the row ({2!r}); not stored".format(
                riding, r["year"], r["unparsed"][:60]))
        rows = [r for r in rows if "unparsed" not in r]
        starts, used = [], {}
        for r in rows:
            # A row is a by-election when depcir says so, or when its year
            # had no general election (Richelieu "2015" carries no marker).
            if r["by_election"] or r["year"] not in elections:
                dates = byelections.get((pn.squash(riding), r["year"])) or []
                k = used.get(r["year"], 0)
                used[r["year"]] = k + 1
                # Two by-elections in one riding and year (Gatineau 1972,
                # the first annulled) are taken in order.
                if k >= len(dates):
                    gaps.append("qc roster: {0} {1} ({2}): no matching by-election date on "
                                "partielles.html; term not stored".format(
                                    riding, r["year"], r["surname"]))
                    starts.append(None)
                    continue
                starts.append(dates[k])
            else:
                starts.append(elections[r["year"]])
        for k, r in enumerate(rows):
            start = starts[k]
            if not start:
                continue
            ends = []
            nxt = next((s for s in starts[k + 1:] if s and s > start), None)
            if nxt:
                ends.append(_day_before(nxt))
            gen = next((g for g in general if g > start), None)
            if gen:
                ends.append(_day_before(gen))
            left = fr_date(r["remark"]) if r["remark"] else None
            if left and left >= start:
                ends.append(left)
            prior = [g for g in general if g <= start]
            out.append((r["member_id"], {
                "surname": display_case(r["surname"]), "given": r["given"],
                "name": "{0} {1}".format(r["given"], display_case(r["surname"])).strip(),
                "href": r.get("href")}, {
                "legislature": legislature_of.get(prior[-1]) if prior else None,
                "party": party_code(r["party"]), "riding": display_case(riding),
                "start": start, "end": min(ends) if ends else None, "party_dated": 0}))
    return out


def parse_current_roster(page):
    """{member_id: (surname, given, riding, party, page url)} from
    /fr/deputes/index.html, whose names carry their real case ('LeBel',
    'McGraw')."""
    out = {}
    for href, mid, name, riding, party in re.findall(
            r'<a href="(/fr/deputes/[^"]*?-(\d+)/index\.html)">([^<]+)</a>\s*</td>\s*<td>\s*([^<]*?)\s*</td>'
            r'\s*<td>\s*([^<]*?)\s*</td>', page or ""):
        surname, _, given = _html.unescape(name).replace("\xa0", " ").partition(",")
        out[mid] = (surname.strip(), given.strip(), _html.unescape(riding).strip(),
                    _html.unescape(party).strip() or None, urljoin(BASE, href))
    return out


_MANDATE = re.compile(
    r"(?:Réélue?|Élue?)\s+députée?\s+de\s+la\s+circonscription\s+d(?:e\s+|')(?P<riding>.+?)\s+"
    r"(?:aux|à\s+l')\s+élections?\s+(?P<kind>générales|partielles?)\s+du\s+"
    r"(?P<date>\d{1,2}(?:er)?\s+\S+\s+\d{4})")


def parse_mandates(page):
    """[(riding, ISO date, by_election)] from a member's own page: "Réélu
    député de la circonscription de Vanier-Les Rivières aux élections
    générales du 3 octobre 2022", "... aux élections partielles du 17 mars
    2025". Oldest first."""
    out = []
    for m in _MANDATE.finditer(html_text(page or "")):
        d = fr_date(m.group("date"))
        if d:
            out.append((m.group("riding").strip(), d, m.group("kind").startswith("partielle")))
    return sorted(set(out), key=lambda x: x[1])


_PLACE = r"([A-ZÀ-Ý][\w'’]*(?:[\-–][\w'’]+)*(?:\s(?:[A-ZÀ-Ý]|de\s|des\s|du\s|la\s|l['’])[\w'’\-–]*)*)"
_BIO_LEFT = re.compile(r"[^.]*\b(?:démission|décédée?|nommée?\s+(?:juge|sénat))[^.]*")
_DATE_TXT = r"\d{1,2}(?:er)?\s+\S+\s+\d{4}"


def parse_bio_mandates(page, elections):
    """([(riding, ISO date, by_election)], departure date or None) from the
    PROSE biography a former member's page carries ("Élu député libéral dans
    Fabre en 2012. Réélu en 2014. ... du 2 juin 2014 au 24 août 2015, date de
    sa démission."). The riding is the one after "dans" (else after "de":
    "Élu député de Terrebonne pour la Coalition avenir Québec en 2018"), and
    a "Réélu en ..." keeps the last riding named. A year is the general
    election of that year, dated from election.html; a year that had none is
    skipped, never guessed."""
    text = html_text(page or "")
    out, riding = [], None
    # html_text joins <p> elements with no space: "démission.Élu député ..."
    for sentence in re.split(r"(?<=\.)\s*(?=[A-ZÀ-Ý])", text):
        if not re.match(r"(?:Élue?|Réélue?)\b", sentence):
            continue
        m = re.search(r"\bdans\s+(?:la\s+circonscription\s+d(?:e\s+|['’]))?" + _PLACE, sentence) \
            or re.match(r"(?:Élue?|Réélue?)\s+députée?\s+d(?:e\s+|['’])" + _PLACE, sentence)
        if m:
            riding = m.group(1).strip()
        if not riding:
            continue
        by = re.search(r"élection\s+partielle\s+du\s+(" + _DATE_TXT + ")", sentence)
        if by and fr_date(by.group(1)):
            out.append((riding, fr_date(by.group(1)), True))
            continue
        for y in re.findall(r"\ben\s+(\d{4})\b", sentence):
            if int(y) in elections:
                out.append((riding, elections[int(y)], False))
    left = None
    for m in _BIO_LEFT.finditer(text):
        dates = [fr_date(x) for x in re.findall(r"\d{1,2}(?:er)?\s+\S+\s+\d{4}", m.group(0))]
        dates = [d for d in dates if d]
        if dates:
            left = dates[-1]
    return sorted(set(out), key=lambda x: x[1]), left


def mandate_terms(mandates, elections, party, legislatures=None, since=None, left=None):
    """Terms from a member page's mandates: each runs to the day before the
    next mandate or the next general election, whichever is first, and
    never past `left` (a dated resignation or death)."""
    general = sorted(elections.values())
    legislatures = legislatures or {}
    out = []
    for k, (riding, start, _by) in enumerate(mandates):
        if since and start < since:
            continue
        ends = [_day_before(x[1]) for x in mandates[k + 1:k + 2]]
        gen = next((g for g in general if g > start), None)
        if gen:
            ends.append(_day_before(gen))
        prior = [g for g in general if g <= start]
        if left and left >= start:
            ends.append(left)
        out.append({"legislature": legislatures.get(prior[-1]) if prior else None,
                    "party": party, "riding": riding, "start": start,
                    "end": min(ends) if ends else None, "party_dated": 0})
    return out


def link_ids(ridings, current):
    """Give a depcir row printed without a member link an id: the same
    name elsewhere in depcir WITH a link, else the current roster's, else a
    name key 'x-<surname>-<given>' (stable, never another member's id)."""
    by_name = {}
    for rows in ridings.values():
        for r in rows:
            if r.get("member_id"):
                by_name.setdefault((pn.fold(r["surname"]), pn.fold(r["given"])), r["member_id"])
    for mid, (surname, given, *_rest) in current.items():
        by_name.setdefault((pn.fold(surname), pn.fold(given)), mid)
    for rows in ridings.values():
        for r in rows:
            if "unparsed" in r or r.get("member_id"):
                continue
            key = (pn.fold(r["surname"]), pn.fold(r["given"]))
            r["member_id"] = by_name.get(key) or "x-" + re.sub(r"[^a-z0-9]+", "-", " ".join(key)).strip("-")


def fetch_roster(ctx):
    have = ctx.conn.execute("SELECT COUNT(*), MAX(last_read) FROM prov_members WHERE prov=?",
                            (PROV,)).fetchone()
    fresh = have[1] and (datetime.date.today() - datetime.date.fromisoformat(have[1])).days < ROSTER_MAX_AGE_DAYS
    if have[0] and fresh and not ctx.refresh:
        ctx.log("  qc roster: {0} member(s) read on {1}; not re-read (--refresh to force)".format(*have))
        return have[0]
    elections, legislatures = parse_elections(ctx.text(ELECTIONS, "elections") or "")
    byelections = parse_byelections(ctx.text(BYELECTIONS, "byelections") or "")
    if not elections:
        ctx.gap("qc roster: no election dates parsed from election.html")
        return 0
    ridings, todo, done = {}, [DEPCIR], set()
    while todo and len(done) < 40:
        url = todo.pop(0)
        if url in done:
            continue
        done.add(url)
        page = ctx.text(url, "depcir-" + url.rsplit("/", 1)[1])
        if page is None:
            continue
        got, links = parse_depcir(page)
        for k, v in got.items():
            ridings.setdefault(k, []).extend(v)
        todo.extend(u for u in (urljoin(url, l) for l in links) if u not in done and u not in todo)
    current = parse_current_roster(ctx.text(ROSTER, "roster") or "")
    link_ids(ridings, current)
    gaps = []
    rows = build_terms(ridings, elections, byelections, gaps, legislatures)
    for g in gaps:
        ctx.gap(g)
    if not rows:
        ctx.gap("qc roster: no members parsed from the depcir pages")
        return 0
    if ctx.dry_run:
        return len({k for k, _, _ in rows})
    terms = {}
    for key, m, t in rows:
        terms.setdefault(key, (m, []))[1].append(t)
    # depcir is NOT complete for the current legislature (2 October 2026:
    # no 2022 row for Vanier-Les Rivières, Taschereau or Vaudreuil, nothing
    # for the 2025 Terrebonne by-election). A sitting member whose depcir
    # terms do not reach the latest general election gets the mandates
    # printed on their own member page.
    latest = max(elections.values())
    supplemented = 0
    for key, cur in sorted(current.items()):
        have = terms.get(key, (None, []))[1]
        if any(t["start"] >= latest or t["end"] is None for t in have):
            continue
        if ctx.stop():
            break
        page = ctx.text(cur[4], "member-" + key)          # the roster's own link
        mandates = parse_mandates(page)
        if not mandates:
            ctx.gap("qc roster: {0} {1} sits now, has no current depcir row and no mandate "
                    "on their member page".format(cur[1], cur[0]))
            continue
        extra = mandate_terms(mandates, elections, party_code(cur[3]), legislatures,
                              since=max([t["start"] for t in have] or ["0"]) if have else None)
        extra = [t for t in extra if not any(t["start"] == h["start"] for h in have)]
        m = {"surname": cur[0], "given": cur[1], "name": "{0} {1}".format(cur[1], cur[0])}
        terms[key] = (terms.get(key, (m, []))[0] or m, have + extra)
        supplemented += 1
    for key, (m, ts) in terms.items():
        cur = current.get(key)
        surname, given = (cur[0], cur[1]) if cur else (m["surname"], m["given"])
        last = max(ts, key=lambda t: t["start"])
        ps.upsert_member(ctx.conn, PROV, key, name="{0} {1}".format(given, surname).strip(),
                         surname=surname, given=given, riding=cur[2] if cur else last["riding"],
                         party=last["party"], sitting=1 if cur else (0 if current else None),
                         page_url=cur[4] if cur else m.get("href"))
        ps.replace_terms(ctx.conn, PROV, key, ts, "depcir")
    ctx.conn.commit()
    ctx.log("  qc roster: {0} riding(s) on {1} page(s), {2} member(s), {3} term(s); "
            "{4} sitting now, {5} completed from their member page".format(
                len(ridings), len(done), len(terms), sum(len(t[1]) for t in terms.values()),
                len(current), supplemented))
    return len(terms)


# -- bills ------------------------------------------------------------------

_BILL_ROW = re.compile(
    r"<tr>\s*<td>\s*(\d+)\s*</td>\s*<td>\s*<span style=\"display:none;\">([^<]*)</span>.*?"
    r"href='(/fr/travaux-parlementaires/projets-loi/projet-loi-(\d+)-(\d+)-(\d)\.html)'.*?</td>\s*"
    r"<td>\s*([^<]*?)\s*</td>\s*<td>\s*([^<]*?)\s*</td>", re.S)


def parse_bill_list(page):
    """[{number, title, href, key, type, last_stage}] -- the key from the
    bill's OWN page link, which names the session it was first presented in."""
    out = []
    for n, title, href, num, leg, sess, kind, stage in _BILL_ROW.findall(page or ""):
        out.append({"number": n, "title": _html.unescape(title).strip(),
                    "href": urljoin(BASE, href), "key": ps.bill_key(PROV, int(leg), int(sess), num),
                    "legislature": int(leg), "session": int(sess),
                    "type": re.sub(r"\s+", " ", _html.unescape(kind)).strip(),
                    "last_stage": _html.unescape(stage).strip()})
    return out


_STAGE_KEYS = {"adoption du principe": "principe",
               "prise en consideration du rapport de commission": "rapport",
               "prise en consideration du rapport": "rapport", "adoption": "adoption"}
_JD = re.compile(r"/assemblee-nationale/(\d+)-(\d)/journal-debats/(\d{4})(\d{2})(\d{2})/")
_TALLY = re.compile(r"Vote\s*:\s*Pour\s*(\d+)\s*,\s*Contre\s*(\d+)\s*,\s*Abstentions?\s*(\d+)", re.I)


def parse_bill_page(page):
    """{author, author_key, type, text_url, en_url, stages: [{stage, sittings:
    [{date, legislature, session, note, tally}]}]}"""
    out = {"author": None, "author_key": None, "type": None, "text_url": None,
           "en_url": None, "stages": []}
    page = page or ""
    a = re.search(r"<h3>Auteur</h3>.*?<a href=\"/fr/deputes/[^\"]*?-(\d+)/index\.html\">([^<]+)</a>", page, re.S)
    if a:
        out["author_key"] = a.group(1)
        sur, _, giv = _html.unescape(a.group(2)).partition(",")
        out["author"] = "{0} {1}".format(giv.strip(), sur.strip()).strip()
    t = re.search(r"<h3>Type</h3>\s*<p>\s*([^<]+)", page)
    out["type"] = re.sub(r"\s+", " ", _html.unescape(t.group(1))).strip() if t else None
    en = re.search(r'href="(/en/travaux-parlementaires/projets-loi/projet-loi-[^"]+\.html)"', page)
    out["en_url"] = urljoin(BASE, en.group(1)) if en else None
    start = page.find("Étapes de cheminement</h2>")
    body = page[start:] if start >= 0 else ""
    end = body.find("En complément")
    body = body[:end] if end > 0 else body
    for chunk in re.split(r"<h3>", body)[1:]:
        name = html_text(chunk[:chunk.find("</h3>")])
        rest = chunk[chunk.find("</h3>"):]
        sittings, docs = [], []
        for li in re.findall(r"<li>(.*?)</li>", rest, re.S):
            link = re.search(r"href='([^']+)'", li) or re.search(r'href="([^"]+)"', li)
            href = _html.unescape(link.group(1)) if link else ""
            if "Process.aspx" in href:
                docs.append(urljoin(BASE, href))
                continue
            jd = _JD.search(href)
            if not jd:
                continue
            after = html_text(li[li.find("</a>"):]) if "</a>" in li else ""
            note = after.strip()
            note = note[1:-1].strip() if note.startswith("(") and note.endswith(")") else note
            tally = _TALLY.search(note)
            sittings.append({"date": "{0}-{1}-{2}".format(jd.group(3), jd.group(4), jd.group(5)),
                             "legislature": int(jd.group(1)), "session": int(jd.group(2)),
                             "note": note or None, "jd_url": urljoin(BASE, href),
                             "tally": [int(x) for x in tally.groups()] if tally else None})
        out["stages"].append({"stage": name, "sittings": sittings, "docs": docs})
        if name == "Présentation" and docs and not out["text_url"]:
            out["text_url"] = docs[0]
    return out


def parse_en_title(page):
    m = re.search(r"SiteMapPathTitreContenu\"><span>([^<]+)</span>", page or "")
    if not m:
        return None
    title = _html.unescape(m.group(1)).strip()
    return re.sub(r"^Bill\s+\d+\s*,\s*", "", title)


def stage_key(name):
    return _STAGE_KEYS.get(pn.fold(name or "").strip())


def voice_stages(bill):
    """[(stage, sitting)] for each decided stage whose final sitting has no
    recorded vote: a stage the page shows decided without a named vote."""
    out = []
    for st in bill["stages"]:
        if not stage_key(st["stage"]) or not st["sittings"]:
            continue
        last = st["sittings"][-1]
        note = pn.fold(last["note"] or "")
        if last["tally"] or re.search(r"ajourn|report|amorce|reprise|suspend", note):
            continue
        out.append((st["stage"], last))
    return out


def fetch_bills(ctx, legislature, session, tax, fr_tax, wl):
    page = ctx.text(BILLS.format(legislature, session), "bills-{0}-{1}".format(legislature, session))
    items = parse_bill_list(page) if page else []
    if page and not items:
        ctx.gap("qc bills {0}-{1}: no bills parsed from the listing".format(legislature, session))
    ctx.bill_map = {it["number"]: it["key"] for it in items}
    if ctx.dry_run:
        return {"bills": len(items)}
    wanted = getattr(ctx, "bill_numbers", None)
    read = texts = 0
    for it in items:
        if wanted and it["number"] not in wanted:
            continue
        if ctx.budget is not None and ctx.budget.exhausted():
            ctx.log(ctx.budget.disclose("bill pages", read))
            break
        bpage = ctx.text(it["href"], "bill-" + it["key"].replace("/", "-"))
        if not bpage:
            continue
        bill = parse_bill_page(bpage)
        read += 1
        have = ctx.conn.execute("SELECT text_read, title_en FROM prov_bills WHERE bill_key=?",
                                (it["key"],)).fetchone()
        title_en = have[1] if have and have[1] and not ctx.refresh else None
        if bill["en_url"] and not title_en:
            title_en = parse_en_title(ctx.text(bill["en_url"], "bill-en-" + it["key"].replace("/", "-")))
        body, text_read = None, 0
        if bill["text_url"] and (ctx.refresh or not (have and have[0])):
            raw = ctx.bytes(bill["text_url"], "billtext-" + it["key"].replace("/", "-"))
            if raw:
                try:
                    from src.prov_fetch import pdf_text
                    body = pdf_text(raw)
                    text_read = 1
                    texts += 1
                except Unreadable as exc:
                    ctx.gap("{0}: bill text {1}: {2}".format(it["key"], bill["text_url"], exc))
        elif have and have[0]:
            text_read = None
        stages = [{"stage": st["stage"], "date": s["date"], "status": s["note"],
                   "session": "{0}-{1}".format(s["legislature"], s["session"]), "tally": s["tally"]}
                  for st in bill["stages"] for s in st["sittings"]]
        record = {"bill_key": it["key"], "prov": PROV, "legislature": it["legislature"],
                  "session": it["session"], "number": it["number"], "title_fr": it["title"],
                  "title_en": title_en, "sponsor": bill["author"], "sponsor_key": bill["author_key"],
                  "bill_type": bill["type"] or it["type"],
                  "is_government": 1 if "gouvernement" in pn.fold(bill["type"] or it["type"]) else 0,
                  "stages": stages, "latest_stage": it["last_stage"] or None,
                  "royal_assent": next((s["date"] for s in stages if s["stage"] == "Sanction"), None),
                  "page_url": it["href"], "text_url": bill["text_url"]}
        sanction = re.search(r"Date de la sanction\s*:\s*([^<]+)", bpage)
        if sanction:
            record["royal_assent"] = fr_date(sanction.group(1))
        if text_read is None:
            ps.store_bill(ctx.conn, dict(record, text_read=0, areas=None))
        else:
            res = pc.classify(tax, wl, PROV, title=title_en, bill_key=it["key"], fr_tax=fr_tax,
                              fr_title=it["title"], fr_texts=[body] if body else [])
            ps.store_bill(ctx.conn, dict(record, text_read=text_read, areas=res.areas,
                                         matched_terms=res.terms, tier=res.tier, excerpt=res.excerpt))
        store_voice(ctx, it["key"], bill, it["href"])
    ctx.conn.commit()
    ctx.log("  qc bills {0}-{1}: {2} listed, {3} page(s) read, {4} text(s) read".format(
        legislature, session, len(items), read, texts))
    return {"bills": len(items), "bill_pages": read, "bill_texts": texts}


def store_voice(ctx, key, bill, page_url):
    """A decided stage with no named vote is a VOICE decision, stored as
    such with the page's own words -- never as an empty roll-call."""
    areas, terms, tier = ps.bill_areas(ctx.conn, key)
    n = 0
    for stage, s in voice_stages(bill):
        if not ctx.in_window(s["date"]):
            continue
        ps.store_division(ctx.conn, {
            "division_key": ps.division_key(PROV, s["legislature"], s["session"], s["date"],
                                            "v{0}-{1}".format(key.rsplit("/", 1)[1], stage_key(stage))),
            "prov": PROV, "legislature": s["legislature"], "session": s["session"],
            "date": s["date"], "seq": "v", "kind": "voice", "bill_key": key, "stage": stage,
            "result": "{0} (page du projet de loi ; aucun vote par appel nominal)".format(
                s["note"] or "étape franchie"),
            "source_url": page_url, "areas": areas, "matched_terms": terms, "tier": tier})
        n += 1
    return n


# -- the procès-verbal: body -------------------------------------------------

_VOTE_MARK = re.compile(r"\(\s*Vote\s+n\s*[°o]\s*(\d+)\s+en\s+annexe\s*\)", re.I)
_TOTALS = re.compile(r"Pour\s*:\s*(\d+)\s+Contre\s*:\s*(\d+)\s+Abstentions?\s*:\s*(\d+)", re.I)
_RESULT = re.compile(r"((?:La|Le|Les|L['’])\s?[^.:;]{0,120}?\s(?:est|sont)\s+(?:adopté|rejeté)e?s?)\s+par\s+le\s+vote\s+suivant",
                     re.I)
_BILL_NO = re.compile(r"projet\s+de\s+loi\s+n\s*[°o]?\s*(\d+)", re.I)
_FURNITURE = re.compile(r"^\s*(?:=+PAGE|_+|\d{1,4}|\d{1,2}(?:er)?\s+\w+\s+\d{4})\s*$")


def clean_body(text):
    lines = [l for l in (text or "").splitlines() if not _FURNITURE.match(l)]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def stage_of(question, heading=None):
    """The stage, from the annex heading first ("Sur le rapport amendé de la
    commission plénière :") and the body's words second. None if neither
    says."""
    for text in (heading, question):
        got = _stage_in(pn.fold(text or "")[-700:])
        if got:
            return got
    return "Motion" if "motion" in pn.fold((heading or "") + (question or "")) else None


def _stage_in(q):
    if "procedure legislative d'exception" in q:
        return "Procédure législative d'exception"
    if "principe du projet de loi" in q or "adoption du principe" in q:
        return "Adoption du principe"
    if re.search(r"rapport[^.]{0,80}commission|prise en consideration|le rapport[^.]{0,40}mis aux voix", q):
        return "Prise en considération du rapport"
    if re.search(r"adoption du projet de loi|projet de loi n\s*[°o]?\s*\d+[^.]{0,200}soit adopte", q):
        return "Adoption"
    return None


def vote_on(question):
    q = pn.fold(question or "")[-400:]
    if "sous-amendement" in q:
        return "sous-amendement"
    if "amendement" in q:
        return "amendement"
    return "motion"


def _is_heading(lines, i):
    """A PV section heading: a short line on its own between blank lines,
    capitalised, with no closing punctuation ("Votes reportés", "Adoption du
    principe", "AFFAIRES DU JOUR", "Motions sans préavis")."""
    s = lines[i].strip()
    if not s or len(s) > 60 or s[-1] in ".:;,»)" or not s[0].isupper() or _FURNITURE.match(lines[i]):
        return False
    blank = lambda j: j < 0 or j >= len(lines) or not lines[j].strip() or _FURNITURE.match(lines[j])  # noqa: E731
    return blank(i - 1) and blank(i + 1)


def own_item(window):
    """The vote's own item: the text after the last section heading before
    its '(Vote n° N en annexe)'. Without the cut, 11 June 2019's vote on the
    Quebec City tramway (Bill 26) carried the notice of committee work on
    Bill 21 that preceded it, and was filed under laicity."""
    lines = (window or "").splitlines()
    cut = max((i for i in range(len(lines)) if _is_heading(lines, i)), default=-1)
    lines = lines[cut + 1:]
    # The consequence of the PREVIOUS vote opens the window ("En
    # conséquence, le projet de loi n° 94 est adopté."): it is not this
    # vote's subject. 30 October 2025's motion on Quebec's political weight
    # was joined to Bill 94 by it.
    while True:
        first = next((k for k, l in enumerate(lines) if l.strip() and not _FURNITURE.match(l)), None)
        if first is None or not lines[first].strip().startswith("En conséquence"):
            break
        end = next((k for k in range(first, len(lines)) if not lines[k].strip()), len(lines))
        lines = lines[end:]
    return "\n".join(lines)


def parse_pv_body(text):
    """[{number, question, result, totals: {Yea, Nay, Abstain}, bill_number,
    stage, vote_on}] -- one per '(Vote n° N en annexe)' in the body."""
    out = []
    prev = 0
    for m in _VOTE_MARK.finditer(text or ""):
        window = own_item(text[prev:m.start()])
        tot = _TOTALS.search(text, m.end(), m.end() + 300)
        prev = tot.end() if tot else m.end()
        question = clean_body(window)
        results = _RESULT.findall(question)
        bills = _BILL_NO.findall(question)
        q = question[-700:]
        if len(question) > 700:
            q = "... " + q[q.find(" ") + 1:]
        out.append({"number": int(m.group(1)), "question": q or None,
                    "result": re.sub(r"\s+", " ", results[-1]).strip() if results else None,
                    "totals": {"Yea": int(tot.group(1)), "Nay": int(tot.group(2)),
                               "Abstain": int(tot.group(3))} if tot else None,
                    "bill_number": bills[-1] if bills else None,
                    "stage": stage_of(q), "vote_on": vote_on(q)})
    return out


# -- the procès-verbal: the annex (layout) -----------------------------------

_ANNEX_LINE = re.compile(r"^\s*ANNEXE\s*$")
_VOTE_HEAD = re.compile(r"^\(\s*Vote\s+n\s*[°o]\s*(\d+)\s*\)$", re.I)
_POS_HEAD = re.compile(r"^(POUR|CONTRE|ABSTENTIONS?)\s*[-–]\s*(\d+)$")
_SAME_AS = re.compile(r"^\(\s*Identique\s+au\s+vote\s+n\s*[°o]?\s*(\d+)\s*\)$", re.I)
_PARTY = r"\(([A-Z]{2,4})\)"
_NAME_CELL = re.compile(r"^[^()]+\s*" + _PARTY + r"(?:\s*\([^()]*\)?)?$")
_RIDING_CELL = re.compile(r"^\([^()]*\)?$|^[^()]+\)$")
_SKIP = re.compile(r"^(?:ANNEXE|Votes par appel nominal|Votes électroniques|\d{1,4}|"
                   r"\d{1,2}(?:er)?\s+\S+\s+\d{4})$")
POSITION = {"POUR": "Yea", "CONTRE": "Nay", "ABSTENTION": "Abstain", "ABSTENTIONS": "Abstain"}


def pdf_pages(raw):
    """(plain text per page, pypdf reader). Unreadable for anything that is
    not a whole PDF -- a truncated record is a gap, never an empty sitting."""
    if not raw or raw[:5] != b"%PDF-":
        raise Unreadable("not a PDF ({0} bytes)".format(len(raw or b"")))
    if b"%%EOF" not in raw[-2048:]:
        raise Unreadable("truncated PDF: no %%EOF marker in {0} bytes".format(len(raw)))
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        return [p.extract_text() or "" for p in reader.pages], reader
    except Exception as exc:
        raise Unreadable("PDF could not be read: {0}".format(exc))


def page_fragments(reader, index):
    """[(tx, ty, end_x, text)] of one page from pypdf's layout engine (the
    private interface src/ca_gazette_pdf.py already relies on; pinned)."""
    import logging

    import pypdf
    from pypdf._text_extraction._layout_mode import _fixed_width_page as fw
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    page = reader.pages[index]
    contents = page.get_contents()
    if contents is None:
        return []
    ops = iter(pypdf.generic.ContentStream(contents, reader, "bytes").operations)
    frags = fw.text_show_operations(ops, page._layout_mode_fonts(), True, None)
    return [(round(f["tx"], 1), round(f["ty"], 1), round(f["displaced_tx"], 1), f["text"])
            for f in frags if f["text"].strip()]


def _lines(frags):
    """Fragments grouped into visual lines, top first: [[(tx, end, text)]]."""
    rows = []
    for tx, ty, end, text in sorted(frags, key=lambda f: (-f[1], f[0])):
        if rows and abs(rows[-1][0] - ty) <= 1.5:
            rows[-1][1].append((tx, end, text))
        else:
            rows.append([ty, [(tx, end, text)]])
    return [(ty, sorted(items)) for ty, items in rows]


def _cells(items, gap=6.0):
    """[(x, text)]: fragments closer than `gap` points are one cell."""
    out = []
    end = None
    for tx, e, text in items:
        if out and tx - end <= gap:
            x, t = out[-1]
            out[-1] = (x, t + ("" if tx - end < 1.0 else " ") + text)
        else:
            out.append((tx, text))
        end = max(e, end or e)
    return [(x, _tidy(t)) for x, t in out if t.strip()]


def _tidy(text):
    """'Arseneau ( PQ )' -> 'Arseneau (PQ)': the layout engine spaces glyph
    runs that the plain text joins."""
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\(\s+", "(", t)
    return re.sub(r"\s+\)", ")", t)


def plain_spellings(text):
    """{squashed name: spelling} from the annex's PLAIN text, whose word
    spacing is right where the layout engine's is not ("D 'A mour" in layout
    mode, "D'Amour" in the text stream, 29 October 2013). The plain text's
    COLUMNS are wrong, which is why it is used for spelling only."""
    out = {}
    for line in (text or "").splitlines():
        for name, _party in re.findall(r"([^()]+?)\s*" + _PARTY, _tidy(line)):
            name = name.strip()
            if name:
                out.setdefault(pn.squash(name), set()).add(name)
    return out


def _respell(label, spellings):
    m = re.match(r"^([^()]+?)(\s*\(.*)$", label or "")
    if not m or not spellings:
        return label
    seen = set(spellings.get(pn.squash(m.group(1)), ())) | {m.group(1).strip()}
    best = min(seen, key=lambda n: (n.count(" "), n))
    return best + m.group(2)


def _column_cells(items, edges):
    """[(x, text)]: the line's fragments grouped by the column each STARTS
    in (edges from _edges), joined in order within a column."""
    if not edges:
        return []
    groups, col = {}, None
    for tx, e, text in items:
        # A new cell starts only AT an edge; a fragment that starts between
        # edges ("Jean)" after "(Lac-Saint-") continues the cell before it.
        at_edge = any(abs(tx - edge) <= 8.0 for edge in edges)
        if col is None or at_edge:
            col = _column(tx, edges)
        groups.setdefault(col, []).append((tx, e, text))
    out = []
    for col in sorted(groups):
        joined = _cells(groups[col], gap=1e9)
        if joined:
            out.append((joined[0][0], " ".join(t for _, t in joined)))
    return out


def _line_text(cells):
    return " ".join(t for _, t in cells).strip()


# From autumn 2025 a long name wraps INSIDE its cell: "Lakhoyan Olivier" on
# one line, "(PLQ)" under it in the same column. The bare name is a cell of
# its own; the party cell after it, like a riding, attaches to it. Capitalised
# words only (particles allowed), no comma, colon or digit: prose never fits.
_BARE_NAME = re.compile(r"^(?:(?:[A-ZÀ-Ý][\w'’\-]*|de|du|des|la|le|van|von|di|da)\s?){1,4}$")


def _is_name_row(cells):
    """Every cell is 'Surname (PARTY)', a bare wrapped surname, or a
    '(...)' riding or party (whole, opened or closed): a row of the annex
    grid, or the continuation row under it."""
    return bool(cells) and all(_NAME_CELL.match(t) or _RIDING_CELL.match(t) or _BARE_NAME.match(t)
                               for _, t in cells)


def _edges(xs, tol=8.0):
    groups = []
    for x in sorted(xs):
        if groups and x - groups[-1][-1] <= tol:
            groups[-1].append(x)
        else:
            groups.append([x])
    # A column is where MANY cells start. One stray start (a wrapped riding
    # whose second half began at 169.8 pt, 30 October 2025) is not a column,
    # and taken as one it cut "(Lac-Saint-Jean)" in two.
    floor = max(1, int(0.15 * max((len(g) for g in groups), default=0)))
    return [g[0] for g in groups if len(g) >= floor]


def _column(x, edges, tol=8.0):
    best = 0
    for i, e in enumerate(edges):
        if e <= x + tol:
            best = i
    return best


def parse_annex(pages, plain=None):
    """{vote number: {heading, counts: {pos: n}, labels: {pos: [label]}}}

    pages: [[(tx, ty, end_x, text)]] for the annex pages, in order. Each
    position's names are read COLUMN BY COLUMN (four columns, top to bottom,
    left to right), across page breaks; a '(Riding)' cell belongs to the
    name before it in that order, which is the name above it in its own
    column -- not the name beside it in the text stream. `plain` (the
    annex's plain text) repairs spelling only (plain_spellings)."""
    spellings = plain_spellings(plain)
    votes, order = {}, []
    cur = pos = None
    heading = []
    cells_of = {}
    # Read from the "ANNEXE" line where there is one; an annex without the
    # heading (14 June 2019) is read from the top of its first page.
    started = not any(_ANNEX_LINE.match(_line_text(_cells(items)))
                      for _, items in _lines(pages[0] if pages else []))
    for pno, frags in enumerate(pages):
        raw_lines = _lines(frags)
        lines = [(ty, _cells(items)) for ty, items in raw_lines]
        # The grid's column edges, from the rows that look like grid rows.
        # A gap-joined cell can swallow its neighbour when a fragment's
        # recorded end runs on (6 April 2023: "Champagne Jourdain" and
        # "Guillemette (CAQ)" as one cell), so name rows are re-cut at the
        # edges, fragment by fragment.
        page_edges = _edges([x for _, cells in lines if _is_name_row(cells) for x, _ in cells])
        by_col = {ty: _column_cells(items, page_edges) for ty, items in raw_lines}
        page_cells = []
        for ty, cells in lines:
            text = _line_text(cells)
            if not started:
                started = bool(_ANNEX_LINE.match(text))
                continue
            vh = _VOTE_HEAD.match(text)
            if vh:
                cur, pos = int(vh.group(1)), None
                votes[cur] = {"heading": re.sub(r"\s+", " ", " ".join(heading)).strip() or None,
                              "counts": {}, "labels": {}}
                order.append(cur)
                heading = []
                continue
            same = _SAME_AS.match(text)
            if same and cur is not None:
                votes[cur]["same_as"] = int(same.group(1))
                continue
            ph = _POS_HEAD.match(text)
            if ph and cur is not None:
                pos = POSITION[ph.group(1)]
                votes[cur]["counts"][pos] = int(ph.group(2))
                continue
            if _SKIP.match(text):
                continue
            row = by_col.get(ty) if _is_name_row(by_col.get(ty)) else cells
            if pos is not None and cur is not None and _is_name_row(row):
                for x, t in row:
                    page_cells.append((cur, pos, x, ty, t))
                continue
            pos = None
            heading.append(text)
        edges = _edges([x for _, _, x, _, _ in page_cells])
        for cur_v, p, x, ty, t in page_cells:
            cells_of.setdefault((cur_v, p), []).append((pno, _column(x, edges), -ty, t))
    for (v, p), cells in cells_of.items():
        labels = []
        pending = None
        for _, _, _, t in sorted(cells):
            if pending is not None:
                t = pending + " " + t
                pending = None
            if t.count("(") > t.count(")"):
                pending = t
                continue
            if _RIDING_CELL.match(t) and not _NAME_CELL.match(t):
                if labels:
                    labels[-1] = labels[-1] + " " + t
                else:
                    labels.append(t)
                continue
            labels.append(t)
        if pending:
            labels.append(pending)
        votes[v]["labels"][p] = [_respell(l, spellings) for l in labels]
    # "(Identique au vote n° 109)" (2 June 2023): the same members voted the
    # same way. Their list is the earlier vote's, said so in `same_as`; the
    # body's own totals still have to match it.
    for v in votes.values():
        ref = votes.get(v.get("same_as"))
        if ref is not None and not v["labels"]:
            v["labels"] = {p: list(l) for p, l in ref["labels"].items()}
            v["counts"] = dict(ref["counts"])
    return votes


def split_label(label):
    """('Blais (Prévost)', 'CAQ') from 'Blais (CAQ) (Prévost)': the resolver's
    label (surname plus riding where printed) and the party AS PRINTED."""
    m = re.match(r"^(?P<name>[^()]+?)\s*" + _PARTY + r"\s*(?:\((?P<riding>[^()]+)\))?$", label or "")
    if not m:
        return label, None
    name = m.group("name").strip()
    if m.group("riding"):
        name += " (" + m.group("riding").strip() + ")"
    return name, m.group(2)


def split_pv(raw):
    """(body text, annex fragments per page, annex plain text) of one PV."""
    texts, reader = pdf_pages(raw)
    start = None
    for i, t in enumerate(texts):
        if any(_ANNEX_LINE.match(l) for l in t.splitlines()):
            start = i
            break
    if start is None:
        # 14 June 2019 has no "ANNEXE" heading: its named votes start on a
        # fresh page with "Sur la motion de ... : (Vote n° 153)". The first
        # page carrying a bare "(Vote n° N)" line is the annex.
        start = next((i for i, t in enumerate(texts)
                      if any(_VOTE_HEAD.match(l.strip()) for l in t.splitlines())), None)
    if start is None:
        return "\n".join(texts), [], None
    head = texts[start].splitlines()
    cut = next((k for k, l in enumerate(head) if _ANNEX_LINE.match(l)), 0)
    body = "\n".join(texts[:start] + ["\n".join(head[:cut])])
    plain = "\n".join(["\n".join(head[cut:])] + texts[start + 1:])
    try:
        frags = [page_fragments(reader, i) for i in range(start, len(texts))]
    except Exception as exc:  # the private layout interface moved: a gap, not bad votes
        raise Unreadable("annex layout could not be read: {0}".format(exc))
    return body, frags, plain


_PRESIDENCY = re.compile(
    r"Présidente?\s+de\s+l['’]Assemblée\s+nationale\s+(?:depuis\s+le\s+(?P<since>\d{1,2}(?:er)?\s+\S+\s+\d{4})|"
    r"du\s+(?P<start>\d{1,2}(?:er)?\s+\S+\s+\d{4})\s+au\s+(?P<end>\d{1,2}(?:er)?\s+\S+\s+\d{4}))")


def parse_presidencies(page):
    """[(start, end or None)] when the member was President (Speaker) of the
    Assembly, from their own page: "Présidente de l'Assemblée nationale
    depuis le 29 novembre 2022". Vice-presidencies are not matched."""
    out = []
    for m in _PRESIDENCY.finditer(html_text(page or "")):
        if m.group("since"):
            out.append((fr_date(m.group("since")), None))
        else:
            out.append((fr_date(m.group("start")), fr_date(m.group("end"))))
    return [(s, e) for s, e in out if s]


class MemberPages:
    """Lazy reads of members' own pages (the URL depcir or the roster links),
    for the two roster holes a procès-verbal exposes:

      * AMBIGUOUS: the annex prints a surname without a riding when only one
        VOTING member bears it, and the President does not vote. 'Roy (CAQ)'
        in 2025-2026 is Suzanne Roy: Nathalie Roy presides. A candidate who
        was President on the day is set aside -- from her own page's dated
        line, never assumed.
      * UNKNOWN: depcir has no row for some members of the 43rd legislature
        (Fitzgibbon, Terrebonne 2022). Their page's dated mandates are added
        as 'member-page' terms and the label is tried again.

    At most one fetch per member per run; anything still unresolved stays
    NULL and the division a gap."""

    def __init__(self, ctx, resolver):
        self.ctx, self.resolver, self.pages, self.completed = ctx, resolver, {}, set()
        self._elections = None

    def page(self, key):
        if key not in self.pages:
            row = self.ctx.conn.execute("SELECT page_url FROM prov_members WHERE prov=? AND member_key=?",
                                        (PROV, key)).fetchone()
            self.pages[key] = self.ctx.text(row[0], "member-" + key) if row and row[0] else None
        return self.pages[key]

    def presided(self, key, date):
        return any(s <= date and (e is None or e >= date) for s, e in parse_presidencies(self.page(key)))

    def elections(self):
        if self._elections is None:
            self._elections = parse_elections(self.ctx.text(ELECTIONS, "elections") or "")
        return self._elections

    def complete(self, surname):
        """Add member-page terms for every member of that surname not yet
        completed this run. True if any term was added."""
        added = False
        rows = self.ctx.conn.execute("SELECT member_key, surname, party FROM prov_members WHERE prov=? "
                                     "AND page_url IS NOT NULL", (PROV,)).fetchall()
        for key, sur, party in rows:
            if pn.fold(sur) != surname or key in self.completed:
                continue
            self.completed.add(key)
            elections, legislatures = self.elections()
            # A sitting member's page lists dated mandates; a former
            # member's carries a prose biography instead.
            mandates, left = parse_mandates(self.page(key)), None
            if not mandates:
                mandates, left = parse_bio_mandates(self.page(key), elections)
            if not mandates:
                continue
            have = {r[0] for r in self.ctx.conn.execute(
                "SELECT start FROM prov_member_terms WHERE prov=? AND member_key=? AND source!='member-page'",
                (PROV, key))}
            terms = [t for t in mandate_terms(mandates, elections, party, legislatures, left=left)
                     if t["start"] not in have]
            if terms:
                ps.replace_terms(self.ctx.conn, PROV, key, terms, "member-page")
                added = True
        if added:
            fresh = pn.Resolver.from_conn(self.ctx.conn, PROV)
            self.resolver.members, self.resolver.terms = fresh.members, fresh.terms
        return added

    def resolve(self, name, date, legislature=None):
        key, how = self.resolver.resolve(name, date, legislature)
        if key:
            return key, how
        if how.startswith("unknown") and self.complete(" ".join(pn.parse_label(name).tokens)):
            key, how = self.resolver.resolve(name, date, legislature)
            if key:
                return key, how + " (member page)"
        lab = pn.parse_label(name)
        if how.startswith("unknown") and lab.initials:
            # "H. Plante" is Marc H. Plante: the initial is part of the name
            # he sits under, not the first letter of his given name. Taken
            # only when the printed form ends the member's full name and he
            # sits that day.
            printed = pn.fold(re.sub(r"\s*\([^()]*\)\s*$", "", name))
            cands = [k for k, m in self.resolver.members.items()
                     if pn.fold(m.get("name")).endswith(" " + printed) and self.resolver.term_for(k, date)]
            if len(cands) == 1:
                return cands[0], "full-name (initial as printed)"
        if how.startswith("ambiguous: "):
            cands = how.split(": ", 1)[1].split(", ")
            keep = [c for c in cands if not self.presided(c, date)]
            if len(keep) == 1 and len(cands) == 2:
                return keep[0], "surname (the other was President of the Assembly)"
        return None, how


def resolve_division(body_vote, annex_vote, resolver, date, legislature=None):
    """Votes resolved, and the tally verdict against the BODY's printed
    totals (the annex's own counts must agree with them too). `resolver`
    is a prov_names.Resolver or a MemberPages."""
    votes, problems = [], []
    for position in ps.POSITIONS:
        for k, label in enumerate((annex_vote or {}).get("labels", {}).get(position, []), 1):
            name, party = split_label(label)
            key, how = resolver.resolve(name, date, legislature) if party else (None, "unparsed label")
            votes.append({"position": position, "ordinal": k, "raw_label": label,
                          "member_key": key, "how": how, "party_at_vote": party})
    printed = (body_vote or {}).get("totals")
    if annex_vote is None:
        problems.append("no annex list for this vote")
    elif printed:
        for position, n in (annex_vote.get("counts") or {}).items():
            if printed.get(position) != n:
                problems.append("annex says {0} - {1}, body says {2}".format(position, n, printed.get(position)))
    if not printed:
        problems.append("no 'Pour : Contre : Abstention :' line in the body")
        printed = {p: (annex_vote or {}).get("counts", {}).get(p) for p in ps.POSITIONS} \
            if annex_vote else {}
    ok, note = ps.tally(printed, votes)
    if problems:
        ok, note = False, "; ".join(problems + ([note] if note else []))
    return votes, ok, note, printed


def read_sitting(ctx, rec, legislature, session, resolver, tax_fr, wl):
    """Read one PV. Returns (divisions, gaps_in_it)."""
    skey = ps.sitting_key(PROV, legislature, session, rec["date"], rec.get("part"))
    url = rec["pv_url"]
    raw = ctx.bytes(url, "pv-{0}".format(skey))
    if raw is None:
        return 0, 1
    try:
        body, frags, plain = split_pv(raw)
    except Unreadable as exc:
        ctx.gap("{0}: {1}: {2}".format(skey, url, exc))
        ps.store_sitting(ctx.conn, PROV, skey, rec["date"], url, status="unreadable")
        return 0, 1
    body_votes = parse_pv_body(body)
    annex = parse_annex(frags, plain) if frags else {}
    numbers = sorted({v["number"] for v in body_votes} | set(annex))
    by_number = {v["number"]: v for v in body_votes}
    bill_map = getattr(ctx, "bill_map", None) or {}
    gaps = 0
    for n in numbers:
        bv, av = by_number.get(n), annex.get(n)
        votes, ok, note, printed = resolve_division(bv, av, resolver, rec["date"])
        # The annex heading names the vote's own subject; the body's last
        # 800 characters are the fallback. Neither: no bill, never a guess.
        number = (_BILL_NO.findall((av or {}).get("heading") or "") or [None])[-1] \
            or (bv or {}).get("bill_number")
        bkey = (bill_map.get(number) or ps.bill_key(PROV, legislature, session, number)) if number else None
        b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, bkey)
        inherit = pc.Result(b_areas, b_terms, b_tier) if b_areas else None
        question = (bv or {}).get("question") or (av or {}).get("heading")
        res = pc.classify(ctx.tax, wl, PROV, bill_key=bkey, inherit=inherit, fr_tax=tax_fr,
                          fr_texts=[question, (av or {}).get("heading")])
        dkey = ps.division_key(PROV, legislature, session, rec["date"], n)
        if not ok:
            gaps += 1
            ctx.gap("{0}: tally check failed ({1}); positions not trusted".format(dkey, note))
        ps.store_division(ctx.conn, {
            "division_key": dkey, "prov": PROV, "legislature": legislature, "session": session,
            "date": rec["date"], "seq": n, "kind": "recorded", "question": question,
            "vote_on": (bv or {}).get("vote_on"), "bill_key": bkey,
            "stage": stage_of((bv or {}).get("question"), (av or {}).get("heading")),
            "result": (bv or {}).get("result"), "yeas": printed.get("Yea"),
            "nays": printed.get("Nay"), "abstentions": printed.get("Abstain"), "source_url": url,
            "areas": res.areas, "matched_terms": res.terms, "tier": res.tier,
            "excerpt": res.excerpt, "positions_ok": 1 if ok else 0, "tally_note": note,
            "votes": votes})
    ps.store_sitting(ctx.conn, PROV, skey, rec["date"], url, divisions=len(numbers),
                     status="gap" if gaps else "ok")
    ctx.conn.commit()
    return len(numbers), gaps


def check_bill_tallies(ctx, read_dates):
    """Every bill-page 'Vote : Pour X, Contre Y' on a day whose PV was read
    must be a recorded division on that bill with those totals."""
    misses = 0
    for key, stages in ctx.conn.execute(
            "SELECT bill_key, stages FROM prov_bills WHERE prov=?", (PROV,)).fetchall():
        for s in json.loads(stages or "[]"):
            if not s.get("tally") or s.get("date") not in read_dates:
                continue
            yeas, nays = s["tally"][0], s["tally"][1]
            hit = ctx.conn.execute(
                "SELECT COUNT(*) FROM prov_divisions WHERE bill_key=? AND date=? AND kind='recorded' "
                "AND yeas=? AND nays=?", (key, s["date"], yeas, nays)).fetchone()[0]
            if not hit:
                # The PV's words did not name the bill ("Sur le rapport de la
                # Commission des relations avec les citoyens", Bill 11, 2
                # June 2023). The bill page is the record that this bill was
                # voted that day with those totals: if exactly ONE division
                # of that day with those totals names no bill, it is this one.
                # Two candidates (identical totals) stay unjoined, and a miss.
                free = ctx.conn.execute(
                    "SELECT division_key, areas, matched_terms, tier FROM prov_divisions WHERE prov=? "
                    "AND date=? AND kind='recorded' AND yeas=? AND nays=? AND bill_key IS NULL",
                    (PROV, s["date"], yeas, nays)).fetchall()
                if len(free) == 1:
                    b_areas, b_terms, b_tier = ps.bill_areas(ctx.conn, key)
                    areas = sorted(set(json.loads(free[0][1] or "[]")) | set(b_areas))
                    terms = json.loads(free[0][2] or "[]") + [t for t in b_terms if t not in (free[0][2] or "")]
                    tiers = [t for t in (free[0][3], b_tier) if t]
                    ctx.conn.execute(
                        "UPDATE prov_divisions SET bill_key=?, stage=?, areas=?, matched_terms=?, tier=? "
                        "WHERE division_key=?", (key, s["stage"], json.dumps(areas), json.dumps(terms),
                                                 min(tiers) if tiers else None, free[0][0]))
                    ctx.log("  {0}: joined to {1} by the bill page's own tally ({2}-{3})".format(
                        free[0][0], key, yeas, nays))
                    hit = 1
            if not hit:
                misses += 1
                ctx.gap("{0}: bill page says {1} on {2} was a named vote {3}-{4}; no recorded "
                        "division on that bill with those totals was read from that day's PV".format(
                            key, s["stage"], s["date"], yeas, nays))
    return misses


def collect(ctx, session=CURRENT_SESSION, roster=True, bills=True):
    legislature, sess = parse_session(session)
    ctx.tax = pc.load_taxonomy()
    tax_fr = pc.load_french_taxonomy(PROV)
    wl = pc.load_watchlist(PROV)
    stats = {}
    if roster:
        stats["members"] = fetch_roster(ctx)
    if bills:
        stats.update(fetch_bills(ctx, legislature, sess, ctx.tax, tax_fr, wl))
    else:
        # --no-bills still reads the session's bill LISTING (one page): a
        # division naming "projet de loi n° 94" in 43-2 is bill qc-43-1/94,
        # and only the listing says so.
        page = ctx.text(BILLS.format(legislature, sess), "bills-{0}-{1}".format(legislature, sess))
        ctx.bill_map = {it["number"]: it["key"] for it in parse_bill_list(page or "")}
    records, pages = list_records(ctx, legislature, sess)
    stats.update({"records_listed": len(records), "listing_pages": pages})
    missing = [r for r in records if not r["pv_url"]]
    for r in missing:
        ctx.gap("qc {0} {1}: the listing has no procès-verbal link".format(session, r["date"]))
    if ctx.dry_run:
        return stats
    resolver = MemberPages(ctx, pn.Resolver.from_conn(ctx.conn, PROV))
    read = divs = gaps = 0
    read_dates = set()
    for rec in records:
        if not rec["pv_url"]:
            continue
        if not ctx.refresh and ps.sitting_done(ctx.conn, rec["pv_url"]):
            read_dates.add(rec["date"])
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        n, g = read_sitting(ctx, rec, legislature, sess, resolver, tax_fr, wl)
        read += 1
        divs += n
        gaps += g
        if g == 0 or n:
            read_dates.add(rec["date"])
    stats.update({"records_read": read, "divisions": divs, "tally_gaps": gaps,
                  "tally_misses": check_bill_tallies(ctx, read_dates)})
    ctx.conn.commit()
    return stats
