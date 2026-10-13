#!/usr/bin/env python3
"""Poland's voivodeship assemblies (sejmiki województw, 13 October 2026):
the sixteen sejmiki's resolutions, into plr_acts (src/pl_regions_store.py).

    python3 tools/pl_regions.py                        # every source below
    python3 tools/pl_regions.py --region mz ld         # some voivodeships
    python3 tools/pl_regions.py --source journal       # one layer only
    python3 tools/pl_regions.py --reclassify           # offline, after a taxonomy change
    python3 tools/pl_regions.py --dry-run              # one read per source, store nothing

Scoped, live-probed, in docs/poland-regions-scope.md. Two layers:

  JOURNALS (fifteen of sixteen). Every voivode publishes an official journal
  (Dziennik Urzędowy Województwa ...), and fifteen of them run the same
  e-Dziennik platform, whose month list is one JSON reply
  (/api/positions?year=Y&month=M&isList=true): every position of the month
  with its title, act type, act date, publication date and publishers. Kept:
  the positions a sejmik published (its local law, budget, statutes,
  programmes) and the voivode's supervisory rulings (rozstrzygnięcia
  nadzorcze) whose subject is a sejmik. The current month and the one
  before are re-read each run, two requests per journal. The
  Kujawsko-Pomorskie journal (edzienniki.bydgoszcz.uw.gov.pl) does not
  answer from the UK; it is listed but not read by default (`--region kp`
  tries it).

  REGISTERS (thirteen sejmiki, nine added on 13 October 2026). The sejmiki's
  own registers of resolutions in their BIP: every resolution adopted,
  binding or not (stanowiska, apele and declarations included, which the
  journals never carry).
    mz  Mazowieckie and
    sl  Śląskie: the same BIP CMS, a year page listing months
        ('?p=2026^wrzesień') and a month page listing each resolution's
        number, date and subject. The newest two months are read each run;
        the whole current year on a register's first read.
    ld  Łódzkie: one page, a table of the whole term (number, date, title,
        link), re-read whole.
    pk  Podkarpackie: an index of sittings, each sitting a page whose
        attachments are its resolutions ('XXXI/520/26 - w sprawie ...').
        The newest three sittings are read each run (robots.txt asks for a
        3-second crawl delay: honoured).
    ma  Małopolskie,
    pm  Pomorskie and
    ds  Dolnośląskie: one BIP platform whose pages are a JavaScript
        application over its own JSON API on the same host (/api/menu/<id>,
        /api/menu/<id>/articles), which robots.txt does not disallow. The
        register menu has a child per year; the current year's list is read
        (Małopolskie's deklaracje and apele too, which are numbered apart).
    lu  Lubelskie: the BIP's document lists are filled by the page's own
        JSON call (DataTables 'list-ajax'): the register (menu 56) and the
        stanowiska and apele (menu 57, unnumbered: keyed by document id).
    sk  Świętokrzyskie: the term's register is one PDF (pypdf; a gap
        without it), re-published after each sitting.
    wp  Wielkopolskie: an index of sittings, each a table; newest two.
    wn  Warmińsko-Mazurskie: the BIP's act list filtered to the sejmik (a
        GET filter), two pages of 20, and its stanowiska category.
    lb  Lubuskie: the BIP's act list filtered by its own form (a POST; the
        filter lives in the PHP session, so the run keeps cookies): the
        year's newest 30.
    kp  Kujawsko-Pomorskie: no list of adopted resolutions is published
        (the sejmik's own site answers our client 403), so the newest two
        sittings' agendas are read and their draft resolutions stored as
        drafts ('kp/druk/64/26', kind 'projekt uchwały').
  Not read: Zachodniopomorskie (since 2021 a staff application, no public
  list found), Podlaskie (BIP domain gone), Opolskie (no answer). Each is in
  the scope doc.

ROLL CALLS AND MEMBERS. Every sejmik must publish each councillor's vote
(art. 19 of the voivodeship self-government act), but as PDFs or on eSesja
(lodzkie.esesja.pl and the other *.esesja.pl sites), which answers our
client with a Cloudflare bot check: not read, never bypassed. Phase 2.

CLASSIFICATION as the national collector does it (tools/pl_rollcalls.py):
config/taxonomy-pl.yaml for "pl" on the title, and config/watchlist-pl.yaml's
`regional` section BY KEY. Nothing is hand-classified.

Exit 0, or 3 when it stored what it could and recorded gaps (the gaps table
and [gap] lines): jobs/pl-weekly.sh treats its failure as a [gap] line and
never as the run's.

ROBOTS.TXT AT RUN TIME: every request goes through
src/robots_guard.GuardedClient, which reads each host's robots.txt once per
run, before the first request. A disallowed URL, or a host whose robots.txt
answers 5xx or not at all, is a [gap] line and a gaps row, never fetched and
never fatal; a Crawl-delay raises that host's interval.
"""

from __future__ import annotations

import argparse
import datetime
import html
import http.cookiejar
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt  # noqa: E402
from src import pl_regions_store as plr  # noqa: E402
from src.http import FetchError, HttpClient, tls_context  # noqa: E402
from src.robots_guard import GuardedClient  # noqa: E402

FEED = "pl-regions"
TAXONOMY_PL = os.path.join(ROOT, "config", "taxonomy-pl.yaml")
TAXONOMY_COUNTRY = "pl"
BUDGET_S = 300

# --- the journals (e-Dziennik) -------------------------------------------------

JOURNALS = {
    "mz": "https://edziennik.mazowieckie.pl",
    "sl": "https://dzienniki.slask.eu",
    "wp": "https://edziennik.poznan.uw.gov.pl",
    "ma": "https://edziennik.malopolska.uw.gov.pl",
    "ds": "https://edzienniki.duw.pl",
    "ld": "https://dziennik.lodzkie.eu",
    "pm": "https://edziennik.gdansk.uw.gov.pl",
    "pk": "https://edziennik.rzeszow.uw.gov.pl",
    "lu": "https://edziennik.lublin.uw.gov.pl",
    "kp": "https://edzienniki.bydgoszcz.uw.gov.pl",
    "zp": "https://e-dziennik.szczecin.uw.gov.pl",
    "wn": "https://edzienniki.olsztyn.uw.gov.pl",
    "sk": "https://edziennik.kielce.uw.gov.pl",
    "pd": "https://edziennik.bialystok.uw.gov.pl",
    "lb": "https://dzienniki.luw.pl",
    "op": "https://duwo.opole.uw.gov.pl",
}
# Not read unless asked for (--region kp): no answer from the UK
# (13 October 2026, connection timed out three times in a day).
JOURNALS_OFF = ("kp",)

# --- the registers ---------------------------------------------------------------

CMS = {
    "mz": "https://bip.mazovia.pl/pl/bip/sejmik/uchwaly-sejmiku/",
    "sl": "https://bip.slaskie.pl/sejmik_wojewodztwa/sesje_sejmiku/uchwaly/uchwaly.html",
}
CMS_MONTHS = 2
LD_LIST = "https://bip.lodzkie.pl/sejmik-wojewodztwa/uchwaly"
PK_INDEX = "https://bip.podkarpackie.pl/sejmik/uchwaly-sejmiku"
PK_SESSIONS = 3

# 13 October 2026 ("Build all reachable ones"): nine more registers.
# Wielkopolskie: an index of sittings, each a table (number, subject, PDF).
WP_INDEX = "https://bip.umww.pl/106---k_112---k_uchwaly-sejmiku--vii-kadencja"
WP_SESSIONS = 2
# Lubelskie: the BIP's document list is filled by the page's own JSON call
# (DataTables, '?id=<menu>&action=list-ajax', robots.txt answers 404: no
# rules). Menu 56 is the register of resolutions (every term, newest first),
# menu 57 the stanowiska, oświadczenia and apele, which carry no number.
LU_BASE = "https://umwl.bip.lubelskie.pl/index.php"
LU_MENUS = ((56, 60, 450), (57, 20, 40))      # (menu, rows a run, rows on the first read)
# Kujawsko-Pomorskie: no list of adopted resolutions in the BIP (the sejmik's
# own site answers our client 403); each sitting's agenda lists the draft
# resolutions it takes, with their print (druk) numbers. Stored as drafts.
KP_INDEX = "https://bip.kujawsko-pomorskie.pl/12537/sesje-sejmiku-wojewodztwa-vii-kadencji.html"
KP_SESSIONS = 2
# Warmińsko-Mazurskie: the BIP's act list filtered to the sejmik (a GET
# filter, 20 rows a page), and the category of its stanowiska.
WN_LIST = ("https://bip.warmia.mazury.pl/akty.html?VAktPrawnySearch%5Brodzaj%5D="
           "Uchwa%C5%82y+Sejmiku")
WN_STANOWISKA = "https://bip.warmia.mazury.pl/kategoria/159/stanowiska-sejmiku.html"
WN_PAGES = 2
# Świętokrzyskie: the term's register is one PDF (number, subject, organ),
# re-published after each sitting; its link is on this page.
SK_REGISTER = ("https://bip.sejmik.kielce.pl/156-rejestr-uchwal-sejmiku/13304-rejestr-uchwal-"
               "sejmiku-wojewodztwa-swietokrzyskiego-vii-kadencji-lata-2024-2029.html")
# Lubuskie: the BIP's act list, filtered by a POST of its own filter form
# (the filter lives in the PHP session, so the run keeps cookies); the
# sejmik's acts of the year, newest first, 30 rows.
LB_LIST = "https://bip.lubuskie.pl/akty/20/typ/"
LB_YEAR_GROUP = {2026: "59", 2025: "57", 2024: "55"}   # fallback: the form's own options win
# Małopolskie, Pomorskie, Dolnośląskie: one BIP platform (Madkom) whose
# pages are a JavaScript application over a JSON API at /api/ on the same
# host, which robots.txt does not disallow: /api/menu/<id> is the menu tree,
# /api/menu/<id>/articles?limit=&offset= a menu's list, newest first. The
# register is a menu with one child per year.
MADKOM = {
    "ma": ("https://bip.malopolska.pl/", (("uchwała", "1032", 60), ("deklaracja", "1070", 20),
                                         ("apel", "1088", 20))),
    "pm": ("https://bip.pomorskie.eu/", (("uchwała", "42", 60),)),
    "ds": ("https://bip.dolnyslask.pl/", (("uchwała", "1914", 60),)),
}
MADKOM_FIRST = 200

REGISTERS = ("mz", "sl", "ld", "pk", "ma", "lu", "sk", "wp", "pm", "ds", "wn", "lb", "kp")

MONTHS_PL = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
             "sierpnia", "września", "października", "listopada", "grudnia")


# --- small helpers -------------------------------------------------------------

def text(s):
    """Tags dropped, entities decoded, whitespace folded."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).replace(" ", " ").strip()


def iso(s):
    """'2026-10-02T09:03:45', '2026-10-02', '22.09.2026' or '22 września 2026'
    -> '2026-10-02'; None when there is no date."""
    s = (s or "").strip()
    m = re.search(r"(\d{4})-(\d\d)-(\d\d)", s)
    if m:
        return "-".join(m.groups())
    m = re.search(r"(\d{1,2})[.-](\d{1,2})[.-](\d{4})", s)
    if m:
        return "{2}-{1:0>2}-{0:0>2}".format(*m.groups())
    m = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS_PL) + r")\s+(\d{4})", s, re.I)
    if m:
        return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), MONTHS_PL.index(m.group(2).lower()) + 1,
                                            int(m.group(1)))
    return None


def kind_of(title):
    """What a register's resolution is, from its subject."""
    t = (title or "").lower()
    if re.search(r"\bstanowisk|\bst\. sejmiku", t):
        return "stanowisko"
    if re.search(r"\bapel", t):
        return "apel"
    if re.search(r"\brezolucj", t):
        return "rezolucja"
    if re.search(r"\bdeklaracj", t):
        return "deklaracja"
    if re.search(r"^oświadczeni|\boświadczeni[ae] sejmiku", t):
        return "oświadczenie"
    return "uchwała"


def _number(title):
    """'Uchwała nr XXXI/396/2026 Sejmiku ...' -> 'XXXI/396/2026'."""
    m = re.search(r"\bnr\.?\s*([0-9IVXLC]+(?:/[0-9IVXLC]+)+)", title or "", re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b([0-9IVXLC]+(?:/[0-9IVXLC]+)+)\b", title or "")
    return m.group(1) if m else None


# --- parsers (pure: text in, acts out) -----------------------------------------

def journal_url(base, year, month):
    return "{0}/api/positions?year={1}&month={2}&isList=true&Csession=1".format(base, year, month)


def _nominative(name):
    """'Sejmiku Województwa Podlaskiego' (some journals print the genitive)
    -> 'sejmik województwa podlaskiego'."""
    return re.sub(r"^sejmiku\b", "sejmik", re.sub(r"\s+", " ", (name or "").strip().lower()))


def _sejmik_publisher(p, region):
    """'own' when the sejmik published the position, 'about' when it is a
    ruling whose subject is the sejmik, else None."""
    name = plr.SEJMIK[region].lower()
    pubs = [_nominative(x.get("Name")) for x in (p.get("PublishersList") or [])]
    subject = _nominative(p.get("Subject"))
    if name in pubs:
        return "own"
    if subject.startswith(name):
        return "about"
    return None


def parse_journal(reply, region, base):
    """Sejmik acts from one month of a journal ({'Positions': [...]})."""
    out = []
    for p in (reply or {}).get("Positions") or []:
        who = _sejmik_publisher(p, region)
        if not who or p.get("IsTechnicalPosition") or not p.get("Position"):
            continue
        year, pos = p.get("Year"), p.get("Position")
        title = text(p.get("Title"))
        kind = (p.get("LegalActType") or "").strip().lower() or None
        if who == "about":
            # A voivode's ruling on a sejmik's act: its title names the
            # voivode, its subject the sejmik.
            title = "{0} ({1})".format(title, text(p.get("Subject")))
        dup = p.get("DuplicateChar") or ""
        out.append({
            "key": "{0}/dz/{1}/{2}{3}".format(region, year, pos, dup), "region": region,
            "source": "journal", "number": _number(p.get("Title")) if who == "own" else None,
            "kind": kind, "title": title, "adopted": iso(p.get("ActDate")),
            "published": iso(p.get("PublicationDate")), "session": None,
            "journal_ref": "Dziennik Urzędowy Województwa {0} {1}, poz. {2}".format(
                plr.SEJMIK[region].split("Województwa ", 1)[1], year, pos),
            "url": "{0}/legalact/{1}/{2}/".format(base, year, pos)})
    return out


def parse_cms_months(page, base):
    """Month pages of a CMS year page, newest first, as absolute URLs."""
    out = []
    for href in re.findall(r'href="(\?p=\d{4}(?:%5E|\^)[^"]+)"', page):
        url = urllib.parse.urljoin(base, html.unescape(href))
        url = urllib.parse.quote(url, safe=":/?=%&")
        if url not in out:
            out.append(url)
    return out


_CMS_ITEM = re.compile(r'<li class="component-item">\s*<a href="([^"]+)"\s*title="([^"]*)".*?</a>'
                       r'(.*?)</li>', re.S)


def parse_cms(page, region, base):
    """Resolutions from one month of the Mazowieckie / Śląskie CMS register."""
    out = []
    for href, title_attr, rest in _CMS_ITEM.findall(page):
        head = text(title_attr)
        if not re.match(r"(?i)uchwa", head):
            continue
        number = _number(head)
        desc = re.search(r'<p>(.*?)</p>', rest, re.S)
        subject = text(desc.group(1)) if desc else ""
        subject = re.sub(r"^(Czego dotyczy uchwała:|W sprawie:)\s*", "", subject, flags=re.I)
        if subject and not re.match(r"(?i)(w sprawie|zmieniaj|uchylaj|o\s)", subject):
            subject = "w sprawie " + subject
        if not number:
            continue
        out.append({
            "key": "{0}/{1}".format(region, number), "region": region, "source": "bip",
            "number": number, "kind": kind_of(subject), "title": subject or head,
            "adopted": iso(head), "published": None, "session": None, "journal_ref": None,
            "url": urllib.parse.urljoin(base, html.unescape(href))})
    return out


def parse_lodzkie(page, base=LD_LIST):
    """Resolutions from Łódzkie's one-page table of the term."""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 3:
            continue
        number, adopted, title = text(cells[0]), iso(text(cells[1])), text(cells[2])
        if not re.match(r"^[IVXLC]+/\d+/\d{2,4}$", number) or not adopted:
            continue
        link = re.search(r'href="([^"]+)"', cells[3] if len(cells) > 3 else "")
        out.append({
            "key": "ld/{0}".format(number), "region": "ld", "source": "bip", "number": number,
            "kind": kind_of(title), "title": title, "adopted": adopted, "published": None,
            "session": "{0} sesja".format(number.split("/")[0]), "journal_ref": None,
            "url": urllib.parse.urljoin(base, html.unescape(link.group(1))) if link else base})
    return out


def parse_pk_index(page, base=PK_INDEX):
    """[(url, title)] of Podkarpackie's sittings, newest first."""
    out = []
    for href, title in re.findall(r'<h2 itemprop="name">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        url = urllib.parse.urljoin(base, html.unescape(href))
        if (url, text(title)) not in out:
            out.append((url, text(title)))
    return out


def parse_pk_session(page, url, title=None):
    """Resolutions of one Podkarpackie sitting (its attachments)."""
    if not title:
        h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", page, re.S)
        title = text(h1[-1]) if h1 else ""
    adopted = iso(title)
    session = re.match(r"^([IVXLC]+) sesja", title or "")
    out = []
    for name in re.findall(r'title="Pobierz załącznik:\s*([^"]+)"', page):
        name = text(name)
        m = re.match(r"^([IVXLC]+/\d+/\d{2,4})\s*[-–]\s*(.+)$", name)
        if not m:
            continue
        number, subject = m.group(1), m.group(2).strip()
        subject = re.sub(r"\bst\. Sejmiku\b", "stanowiska Sejmiku", subject)
        out.append({
            "key": "pk/{0}".format(number), "region": "pk", "source": "bip", "number": number,
            "kind": kind_of(subject), "title": subject, "adopted": adopted, "published": None,
            "session": "{0} sesja".format(session.group(1)) if session else None,
            "journal_ref": None, "url": url})
    return out


_PREFIX = re.compile(r"^(?:uchwała|uchwały|uchwale)\s+(?:nr\.?\s*\S+\s+)?(?:sejmiku\s+województwa\s+\S+\s+)?"
                     r"(?:z\s+dnia\s+\d{1,2}\s+\S+\s+\d{4}\s*(?:r\.|roku)?\s*)?", re.I)


def subject(title):
    """'Uchwała Nr XXXIV/513/26 Sejmiku Województwa Małopolskiego z dnia 28
    września 2026 r. w sprawie: zmian ...' or 'Uchwała w sprawie: zmian ...'
    -> 'w sprawie zmian ...' (the subject, as the other registers give it)."""
    t = _PREFIX.sub("", text(title)).strip()
    t = re.sub(r"(?i)^w sprawie\s*:\s*", "w sprawie ", t)
    return t or text(title)


def _reg_act(region, number, title, adopted, url, key=None, kind=None, session=None, published=None):
    return {"key": key or "{0}/{1}".format(region, number), "region": region, "source": "bip",
            "number": number, "kind": kind or kind_of(title), "title": title, "adopted": adopted,
            "published": published, "session": session, "journal_ref": None, "url": url}


_NUMBER = re.compile(r"^(?:nr\.?\s*)?([0-9IVXLC]+(?:/[0-9IVXLC]+)+)$", re.I)


def parse_wp_index(page, base=WP_INDEX):
    """[(url, session, date)] of Wielkopolskie's sittings, newest first."""
    out = []
    for href, label in re.findall(r'<a [^>]*href="(106---k_112---k_348---[^"]+)"[^>]*>(.*?)</a>', page, re.S):
        label = text(label)
        m = re.search(r"na ([IVXLC]+) Sesji", label, re.I)
        url = urllib.parse.urljoin(base, html.unescape(href))
        if m and url not in [u for u, _, _ in out]:
            out.append((url, "{0} sesja".format(m.group(1).upper()), iso(label)))
    return out


def parse_wp_session(page, url, session=None, adopted=None):
    """Resolutions of one Wielkopolskie sitting: a table of (Lp., number,
    subject, PDF)."""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 3:
            continue
        m = _NUMBER.match(text(cells[1]))
        if not m:
            continue
        link = re.search(r'href="([^"]+)"', cells[3] if len(cells) > 3 else "")
        number, title = m.group(1), subject(cells[2])
        out.append(_reg_act("wp", number, title, adopted, urllib.parse.urljoin(
            url, html.unescape(link.group(1))) if link else url, session=session))
    return out


def lu_url(menu, rows):
    return ("{0}?id={1}&action=list-ajax&sEcho=1&iDisplayStart=0&iDisplayLength={2}"
            "&iSortCol_0=5&sSortDir_0=desc".format(LU_BASE, menu, rows))


def parse_lubelskie(reply, menu):
    """Rows of Lubelskie's document list (the page's own JSON): menu 56 the
    resolutions ('znak' is the number), menu 57 the unnumbered positions,
    keyed by the BIP's document id."""
    out = []
    for r in (reply or {}).get("aaData") or []:
        title, doc = text(r.get("tresc")), str(r.get("id_dokumentu") or "")
        if not title or not doc:
            continue
        url = "{0}?id={1}&p1=szczegoly&p2={2}".format(LU_BASE, menu, doc)
        number = re.sub(r"(?i)^nr\.?\s*", "", text(r.get("znak") or ""))
        if menu == 56 and number:
            out.append(_reg_act("lu", number, title, iso(r.get("data_utworzenia")), url))
        elif menu != 56:
            out.append(_reg_act("lu", None, title, iso(r.get("data_utworzenia")), url,
                                key="lu/doc/{0}".format(doc)))
    return out


def parse_kp_index(page):
    """[(url, session, date)] of the Kujawsko-Pomorskie sittings' agendas,
    newest first."""
    out = []
    for href, label in re.findall(r'<a [^>]*href="(https://bip\.kujawsko-pomorskie\.pl/\d+/porzadek-obrad-[^"]+)"'
                                  r'[^>]*>(.*?)</a>', page, re.S):
        label = text(label)
        m = re.search(r"obrad ([IVXLC]+)\b", label)
        if m and href not in [u for u, _, _ in out]:
            out.append((href, "{0} sesja".format(m.group(1)), iso(label)))
    return sorted(out, key=lambda x: x[2] or "", reverse=True)


def parse_kp_agenda(page, url, session=None, date=None):
    """The draft resolutions on one Kujawsko-Pomorskie agenda ('Rozpatrzenie
    i podjęcie uchwały w sprawie ... – projekt zarządu województwa – druk nr
    64/26'), keyed by print."""
    out = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", page, re.S):
        t = text(li)
        m = re.search(r"(?i)podjęcie uchwały\s+(.*?)\s+[–-]\s+projekt\b.*?druk nr\s*(\d+/\d+)", t)
        if not m:
            continue
        title, druk = m.group(1).strip(), m.group(2)
        if any(a["number"] == "druk nr " + druk for a in out):
            continue
        out.append(_reg_act("kp", "druk nr " + druk, title, date, url, key="kp/druk/" + druk,
                            kind="projekt uchwały", session=session))
    return out


_WN_ROW = re.compile(r'<tr[^>]*data-key="(\d+)"[^>]*>(.*?)</tr>', re.S)


def parse_wn(page, base=WN_LIST):
    """Rows of the Warmińsko-Mazurskie BIP's act list or its stanowiska
    category: date, number (acts only), title with link."""
    out = []
    for doc, row in _WN_ROW.findall(page):
        date = re.search(r"data-col-date>([^<]*)<", row)
        num = re.search(r"data-col-text>([^<]*)<", row)
        link = re.search(r'data-col-main>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
        if not link:
            continue
        url = urllib.parse.urljoin(base, html.unescape(link.group(1)))
        number = text(num.group(1)) if num else ""
        title = subject(link.group(2))
        if number:
            out.append(_reg_act("wn", number, title, iso(date.group(1) if date else ""), url))
        else:
            out.append(_reg_act("wn", None, text(link.group(2)), iso(date.group(1) if date else ""), url,
                                key="wn/doc/{0}".format(doc)))
    return out


def parse_sk_pdf_link(page, base=SK_REGISTER):
    m = re.search(r'href="(/download/[^"]+)"', page)
    return urllib.parse.urljoin(base, html.unescape(m.group(1))) if m else None


def pdf_text(data):
    """The PDF's text, page by page (pypdf, imported only here: without it
    the Świętokrzyskie register is a gap, never the run)."""
    try:
        import io
        import pypdf
    except ImportError:
        raise ValueError("pypdf is not installed: the Świętokrzyskie register (a PDF) is not read")
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


_SK_SESSION = re.compile(r"(?i)\b([IVXLC]+|\d+)\.?\s+sesj[ai]\s+Sejmiku\s+Województwa\s+Świętokrzyskiego"
                         r"(?:\s+\S+\s+kadencji)?(?:\s+(?:z\s+dnia|w\s+dniu))?\s+(\d{1,2}\s+\S+\s+\d{4})")
_SK_ENTRY = re.compile(r"(?m)^\s*(?:Uchwała\s+nr\s*)?([IVXLC]+/\d+/\d{2})\b")
_SK_ORGAN = re.compile(r"(?:\bWojewoda\s+Świętokrzyski\b|\bWojewoda\b|\bRIO\b|\bPubl\.)")


def parse_sk_register(txt, url=SK_REGISTER):
    """Resolutions from the text of Świętokrzyskie's register PDF: sittings
    as headings ('XXX sesja Sejmiku ... z dnia 25 czerwca 2026 r.'), then
    'Uchwała nr XXX/359/26 / w sprawie ... / Wojewoda Świętokrzyski'."""
    txt = re.sub(r"(?i)Uchwała\s+nr\s*\n\s*", "Uchwała nr ", txt or "")
    marks = sorted([(m.start(), "s", m) for m in _SK_SESSION.finditer(txt)]
                   + [(m.start(), "e", m) for m in _SK_ENTRY.finditer(txt)], key=lambda x: x[0])
    out, seen, adopted, session = [], set(), None, None
    for i, (pos, kind, m) in enumerate(marks):
        if kind == "s":
            adopted, session = iso(m.group(2)), m.group(1)
            continue
        end = marks[i + 1][0] if i + 1 < len(marks) else len(txt)
        body = re.sub(r"\s+", " ", txt[m.end():end])
        body = re.sub(r"(?i)\s*Rejestr uchwał podjętych podczas.*$", "", body)
        body = re.sub(r"\s+", " ", _SK_ORGAN.sub(" ", body)).strip(" .")
        number = m.group(1)
        if number in seen or not body:
            continue
        seen.add(number)
        out.append(_reg_act("sk", number, body, adopted, url,
                            session="{0} sesja".format(number.split("/")[0])))
    return out


def parse_lubuskie(page):
    """The sejmik's resolutions from the Lubuskie BIP's (filtered) act list:
    'UCHWAŁA NR XXIII/365/26 SEJMIKU WOJEWÓDZTWA LUBUSKIEGO z dnia 21
    września 2026 r. w sprawie ...'."""
    out, seen = [], set()
    for href, label in re.findall(r'<a href="(https://bip\.lubuskie\.pl/akty/20/\d+/[^"]+)"[^>]*>(.*?)</a>',
                                  page, re.S):
        label = text(label)
        if not re.search(r"(?i)sejmiku województwa lubuskiego", label):
            continue
        number = _number(label)
        if not number or number in seen:
            continue
        seen.add(number)
        out.append(_reg_act("lb", number, subject(label), iso(label), html.unescape(href)))
    return out


def lb_year_group(page, year):
    """The filter's group id for the sejmik's resolutions of `year`, from
    the form's own option list ('<option value="59" >Uchwały Sejmiku 2026'),
    else LB_YEAR_GROUP."""
    for value, label in re.findall(r'<option value="(\d+)"[^>]*>([^<]*)', page or ""):
        if re.match(r"(?i)\s*uchwały sejmiku\s+{0}\b".format(year), html.unescape(label)):
            return value
    return LB_YEAR_GROUP.get(year)


def madkom_menu_url(site, menu):
    return "{0}api/menu/{1}".format(site, menu)


def madkom_articles_url(site, menu, limit):
    return "{0}api/menu/{1}/articles?limit={2}&offset=0".format(site, menu, limit)


def madkom_years(tree, menu):
    """[(year, menu id)] of a register menu's children, newest first."""
    def find(nodes):
        for n in nodes or []:
            if str(n.get("id")) == str(menu):
                return n.get("children") or []
            got = find(n.get("children"))
            if got:
                return got
        return []
    out = []
    for c in find(tree if isinstance(tree, list) else [tree]):
        m = re.match(r"\s*(\d{4})\b", c.get("name") or "")
        if m:
            out.append((int(m.group(1)), str(c.get("id"))))
    return out


def parse_madkom(reply, region, kind, site):
    """A Madkom register list: the title field, the number (from the title,
    else the 'Nr'/'Symbol' column), the date (the title's 'z dnia', else the
    adoption column, else the publication date)."""
    cols = (reply or {}).get("columns") or []
    title_ids, number_ids, adopted_ids, any_ids = set(), [], set(), []
    for c in cols:
        cname = (c.get("name") or "").lower()
        for f in c.get("columnFields") or []:
            fid = str(f.get("id"))
            fname = (f.get("name") or "").lower()
            if f.get("fieldContent") == "title" or fid == "title":
                title_ids.add(fid)
            elif re.search(r"\bnr\b|numer|symbol", cname) and "data" not in fname:
                number_ids.append(fid)
            elif re.search(r"podjęcia|utworzenia aktu|z dnia", cname + " " + fname):
                adopted_ids.add(fid)
            else:
                any_ids.append(fid)
    out = []
    for a in (reply or {}).get("articles") or []:
        vals = {str(f.get("fieldId")): html.unescape(str(f.get("value") or "")) for f in a.get("columnFields") or []}
        full = text(next((vals[i] for i in title_ids if vals.get(i)), ""))
        if not full:
            continue
        number = _number(full) or "".join(vals.get(i, "") for i in number_ids).strip() or None
        if number and not re.search(r"/", number):
            number = None
        adopted = iso(re.search(r"z dnia\s+\d{1,2}\s+\S+\s+\d{4}", full).group(0)) if re.search(
            r"z dnia\s+\d{1,2}\s+\S+\s+\d{4}", full) else None
        adopted = adopted or next((iso(vals[i]) for i in adopted_ids if iso(vals.get(i))), None)
        published = next((iso(vals[i]) for i in any_ids if iso(vals.get(i))), None)
        url = site + (a.get("link") or "").lstrip("/")
        if kind == "uchwała":
            if not number:
                continue
            title = subject(full)
            out.append(_reg_act(region, number, title, adopted or published, url, published=published))
        else:
            key = "{0}/{1}/{2}".format(region, kind, number) if number else "{0}/doc/{1}".format(region, a.get("id"))
            out.append(_reg_act(region, number, full, adopted or published, url, key=key, kind=kind,
                                published=published))
    return out


# --- classification and storing --------------------------------------------------

def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, wl, a, watch_path=None):
    res = filt.filter_item(tax, wl, a.get("title") or "", title=a.get("title") or "")
    return plr.add_watch_areas(res, a["key"], watch_path, title=a.get("title"))


def store_act(conn, a, res, today, seed):
    """Insert or update one act. Returns 'new' or 'same'."""
    old = conn.execute("SELECT 1 FROM plr_acts WHERE act_key=?", (a["key"],)).fetchone()
    conn.execute(
        "INSERT INTO plr_acts (act_key, region, source, number, kind, title, adopted, published, "
        "session, journal_ref, url, areas, matched_terms, tier, first_seen, last_seen, seed) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(act_key) DO UPDATE SET number=excluded.number, kind=excluded.kind, "
        "title=excluded.title, adopted=excluded.adopted, published=excluded.published, "
        "session=COALESCE(excluded.session, plr_acts.session), journal_ref=excluded.journal_ref, "
        "url=excluded.url, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen",
        (a["key"], a["region"], a["source"], a.get("number"), a.get("kind"), a.get("title"),
         a.get("adopted"), a.get("published"), a.get("session"), a.get("journal_ref"),
         a.get("url"), plr.dumps(res.issue_areas),
         plr.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
         res.tier, today, today, 1 if seed else 0))
    return "same" if old else "new"


def store_all(conn, acts, tax, wl, today, seed=False):
    """(read, on our ground, new)."""
    n = ours = new = 0
    for a in acts:
        res = classify(tax, wl, a)
        new += store_act(conn, a, res, today, seed) == "new"
        n += 1
        if [x for x in (res.issue_areas or []) if x != 11]:
            ours += 1
    conn.commit()
    return n, ours, new


def mark_read(conn, source, today, items, status):
    conn.execute("INSERT INTO plr_reads (source, last_seen, items, status) VALUES (?,?,?,?) "
                 "ON CONFLICT(source) DO UPDATE SET last_seen=excluded.last_seen, "
                 "items=excluded.items, status=excluded.status",
                 (source, today, items, (status or "")[:200]))
    conn.commit()


def first_read(conn, source):
    """True until a read of `source` has stored something: its rows are seed.
    A source that has only ever failed is still on its first read."""
    return conn.execute("SELECT 1 FROM plr_acts WHERE source=? AND region=? LIMIT 1",
                        tuple(source.split(":", 1))).fetchone() is None


def _gap(conn, today, detail, log=print):
    log("  [gap] " + detail)
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    conn.commit()


# --- fetching --------------------------------------------------------------------

def _months(today, n=2):
    d = datetime.date.fromisoformat(today)
    out = [(d.year, d.month)]
    while len(out) < n:
        y, m = out[-1]
        out.append((y - 1, 12) if m == 1 else (y, m - 1))
    return out


def fetch_journal(client, region, today, first=False, budget=None, log=print):
    base = JOURNALS[region]
    acts, gaps = [], 0
    for year, month in _months(today, 2):
        if budget is not None and budget.exhausted():
            log(budget.disclose("journal months", len(acts)))
            return acts, gaps + 1
        reply = client.get_json(journal_url(base, year, month), FEED,
                                "journal-{0}-{1}-{2:02d}".format(region, year, month))
        acts += parse_journal(reply, region, base)
    return acts, gaps


def fetch_cms(client, region, today, first=False, budget=None, log=print):
    base = CMS[region]
    year = int(today[:4])
    sep = "&" if "?" in base else "?"
    months = parse_cms_months(client.get_text("{0}{1}p={2}".format(base, sep, year), FEED,
                                              "register-{0}-{1}".format(region, year)), base)
    if len(months) < CMS_MONTHS:
        months += parse_cms_months(client.get_text("{0}{1}p={2}".format(base, sep, year - 1), FEED,
                                                   "register-{0}-{1}".format(region, year - 1)), base)
    acts, gaps = [], 0
    for i, url in enumerate(months if first else months[:CMS_MONTHS]):
        if budget is not None and budget.exhausted():
            log(budget.disclose("register months", i))
            return acts, gaps + 1
        acts += parse_cms(client.get_text(url, FEED, "register-{0}-m{1}".format(region, i)), region, base)
    return acts, gaps


def fetch_lodzkie(client, region="ld", today=None, first=False, budget=None, log=print):
    return parse_lodzkie(client.get_text(LD_LIST, FEED, "register-ld")), 0


def fetch_podkarpackie(client, region="pk", today=None, first=False, budget=None, log=print):
    sessions = parse_pk_index(client.get_text(PK_INDEX, FEED, "register-pk"))
    acts, gaps = [], 0
    for i, (url, title) in enumerate(sessions if first else sessions[:PK_SESSIONS]):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Podkarpackie sittings", i))
            return acts, gaps + 1
        acts += parse_pk_session(client.get_text(url, FEED, "register-pk-s{0}".format(i)), url, title)
    return acts, gaps


def _each(items, budget, log, what):
    """Yield the items until the time budget is spent; the caller counts a
    partial read as one gap."""
    for i, x in enumerate(items):
        if budget is not None and budget.exhausted():
            log(budget.disclose(what, i))
            return
        yield x


def fetch_wielkopolskie(client, region="wp", today=None, first=False, budget=None, log=print):
    sessions = parse_wp_index(client.get_text(WP_INDEX, FEED, "register-wp"))
    todo = sessions[:WP_SESSIONS * 3 if first else WP_SESSIONS]
    acts, done = [], 0
    for i, (url, session, adopted) in enumerate(_each(todo, budget, log, "Wielkopolskie sittings")):
        acts += parse_wp_session(client.get_text(url, FEED, "register-wp-s{0}".format(i)), url, session, adopted)
        done += 1
    return acts, int(done < len(todo))


def fetch_lubelskie(client, region="lu", today=None, first=False, budget=None, log=print):
    acts = []
    for menu, rows, first_rows in LU_MENUS:
        if budget is not None and budget.exhausted():
            log(budget.disclose("Lubelskie lists", len(acts)))
            return acts, 1
        acts += parse_lubelskie(client.get_json(lu_url(menu, first_rows if first else rows), FEED,
                                                "register-lu-{0}".format(menu)), menu)
    return acts, 0


def fetch_kujawsko(client, region="kp", today=None, first=False, budget=None, log=print):
    sessions = parse_kp_index(client.get_text(KP_INDEX, FEED, "register-kp"))
    todo = sessions[:KP_SESSIONS * 2 if first else KP_SESSIONS]
    acts, done = [], 0
    for i, (url, session, date) in enumerate(_each(todo, budget, log, "Kujawsko-Pomorskie agendas")):
        acts += parse_kp_agenda(client.get_text(url, FEED, "register-kp-s{0}".format(i)), url, session, date)
        done += 1
    return acts, int(done < len(todo))


def fetch_warminsko(client, region="wn", today=None, first=False, budget=None, log=print):
    pages = [WN_LIST] + ["{0}&page={1}".format(WN_LIST, n) for n in range(2, (WN_PAGES * 3 if first else WN_PAGES) + 1)]
    pages.append(WN_STANOWISKA)
    acts, done = [], 0
    for i, url in enumerate(_each(pages, budget, log, "Warmińsko-Mazurskie pages")):
        acts += parse_wn(client.get_text(url, FEED, "register-wn-{0}".format(i)), url)
        done += 1
    return acts, int(done < len(pages))


def fetch_swietokrzyskie(client, region="sk", today=None, first=False, budget=None, log=print):
    link = parse_sk_pdf_link(client.get_text(SK_REGISTER, FEED, "register-sk"))
    if not link:
        raise ValueError("no PDF link on the Świętokrzyskie register page")
    return parse_sk_register(pdf_text(client.get_bytes(link, FEED, "register-sk-pdf")), SK_REGISTER), 0


def fetch_lubuskie(client, region="lb", today=None, first=False, budget=None, log=print):
    year = int((today or datetime.date.today().isoformat())[:4])
    page = client.get_text(LB_LIST, FEED, "register-lb")   # also opens the PHP session the filter is kept in
    group = lb_year_group(page, year)
    if not group:
        raise ValueError("the Lubuskie filter lists no 'Uchwały Sejmiku {0}' group yet".format(year))
    fields = {"filtr[id_typ]": "2", "filtr[id_grupa]": group, "filtr[id_sesja]": "0",
              "filtr[id_miesiac]": "0", "filtr[iloscNaStronie]": "30", "filtr[temat]": "",
              "filtr[numer_ap]": "", "filtr[id_status]": "0", "filtr[dni]": "0",
              "data_publikacji_od": "", "data_publikacji_do": "", "filtr[czysc_filtr]": "0"}
    return parse_lubuskie(client.post_form(LB_LIST, fields, FEED, "register-lb-filter")), 0


def fetch_madkom(client, region, today=None, first=False, budget=None, log=print):
    site, menus = MADKOM[region]
    year = int((today or datetime.date.today().isoformat())[:4])
    acts, gaps = [], 0
    for kind, menu, limit in menus:
        if budget is not None and budget.exhausted():
            log(budget.disclose("{0} lists".format(plr.REGIONS[region]), len(acts)))
            return acts, gaps + 1
        years = madkom_years(client.get_json(madkom_menu_url(site, menu), FEED,
                                             "register-{0}-{1}".format(region, menu)), menu)
        todo = [mid for y, mid in years if y == year]
        if first or (kind == "uchwała" and int((today or "2000-12")[5:7]) <= 2):
            # Early in a year the new year's list is short: the year before too.
            todo += [mid for y, mid in years if y == year - 1][:1]
        for mid in todo:
            acts += parse_madkom(client.get_json(madkom_articles_url(site, mid, MADKOM_FIRST if first else limit),
                                                 FEED, "register-{0}-{1}".format(region, mid)), region, kind, site)
        if kind == "uchwała" and not todo:
            raise ValueError("no {0} list for {1} in the menu".format(plr.REGIONS[region], year))
    return acts, gaps


REGISTER_FETCH = {"mz": fetch_cms, "sl": fetch_cms, "ld": fetch_lodzkie, "pk": fetch_podkarpackie,
                  "wp": fetch_wielkopolskie, "lu": fetch_lubelskie, "kp": fetch_kujawsko,
                  "wn": fetch_warminsko, "sk": fetch_swietokrzyskie, "lb": fetch_lubuskie,
                  "ma": fetch_madkom, "pm": fetch_madkom, "ds": fetch_madkom}


def sources(regions, layer=None, asked=False):
    """[(source id, region, fetch fn)] in reading order: journals, then registers."""
    out = []
    if layer in (None, "journal"):
        for r in plr.REGIONS:
            if r in regions and r in JOURNALS and (asked or r not in JOURNALS_OFF):
                out.append(("journal:" + r, r, fetch_journal))
    if layer in (None, "bip"):
        for r in REGISTERS:
            if r in regions:
                out.append(("bip:" + r, r, REGISTER_FETCH[r]))
    return out


def reclassify(conn, tax, watch_path=None):
    wl = empty_watchlist()
    n = 0
    for r in conn.execute("SELECT act_key, title FROM plr_acts").fetchall():
        res = classify(tax, wl, {"key": r[0], "title": r[1]}, watch_path)
        conn.execute("UPDATE plr_acts SET areas=?, matched_terms=?, tier=? WHERE act_key=?",
                     (plr.dumps(res.issue_areas),
                      plr.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, r[0]))
        n += 1
    conn.commit()
    print("pl-regions: reclassified {0} regional act(s)".format(n))


def summary(conn):
    for source, region in conn.execute("SELECT source, region FROM plr_acts GROUP BY source, region "
                                       "ORDER BY source, region").fetchall():
        row = conn.execute("SELECT COUNT(*), SUM(CASE WHEN areas NOT IN ('[]','[11]') THEN 1 ELSE 0 "
                           "END), MAX(COALESCE(published, adopted)) FROM plr_acts WHERE source=? AND "
                           "region=?", (source, region)).fetchone()
        print("pl-regions: {0} {1}: {2} act(s) stored, {3} on our ground, newest {4}".format(
            plr.REGIONS[region], "journal" if source == "journal" else "register",
            row[0], row[1] or 0, row[2] or "-"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--region", nargs="*", choices=list(plr.REGIONS), help="default: every voivodeship")
    ap.add_argument("--source", choices=("journal", "bip"), help="default: both layers")
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--today", help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true",
                    help="read each source once, print what was parsed, store nothing")
    args = ap.parse_args(argv)
    # robots.txt asked on THIS run, per host, before any request
    # (src/robots_guard). A refusal raises RobotsRefused, a FetchError, so
    # the source becomes a "not read" gap below and the run goes on.
    # Cookies kept for the run: the Lubuskie list's filter lives in its PHP
    # session (fetch_lubuskie). Nothing is stored between runs.
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls_context()),
                                         urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    client = GuardedClient(HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), opener=opener), FEED)
    today = args.today or datetime.date.today().isoformat()
    todo = sources(args.region or list(plr.REGIONS), args.source, asked=bool(args.region))
    if args.dry_run:
        for source, region, fetch in todo:
            try:
                acts, _ = fetch(client, region, today, first=False, budget=drain.Budget(60))
            except (FetchError, ValueError) as e:
                print("pl-regions: {0}: FAILED {1}".format(source, str(e)[:200]))
                continue
            newest = max((a.get("published") or a.get("adopted") or "" for a in acts), default="-")
            print("pl-regions: {0} ({1}): {2} act(s), newest {3}".format(
                source, plr.REGIONS[region], len(acts), newest or "-"))
        return 0
    if not os.path.exists(TAXONOMY_PL):
        print("pl-regions: config/taxonomy-pl.yaml is missing; nothing classified")
        return 1
    conn = db.init_db(db.connect(args.db))
    tax = filt.load_taxonomy(TAXONOMY_PL, country=TAXONOMY_COUNTRY)
    print("pl-regions: taxonomy taxonomy-pl.yaml (v{0})".format(tax.version))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    for i, (source, region, fetch) in enumerate(todo):
        name = "{0} {1}".format(plr.REGIONS[region], "journal" if source.startswith("journal") else "register")
        if budget.exhausted():
            print(budget.disclose("sources", i))
            _gap(conn, today, "{0}: time budget spent before it was read".format(name))
            gaps += 1
            continue
        first = first_read(conn, source)
        try:
            acts, g = fetch(client, region, today, first=first, budget=budget)
        except (FetchError, ValueError) as e:
            _gap(conn, today, "{0}: not read ({1})".format(name, str(e)[:200]))
            mark_read(conn, source, today, 0, "failed: " + str(e)[:150])
            gaps += 1
            continue
        if g:
            _gap(conn, today, "{0}: read in part (time budget)".format(name))
        gaps += g
        if not acts and source.startswith("bip"):
            _gap(conn, today, "{0}: the register answered with no resolutions".format(name))
            mark_read(conn, source, today, 0, "failed: no resolutions parsed")
            gaps += 1
            continue
        n, ours, new = store_all(conn, acts, tax, wl, today, seed=first)
        mark_read(conn, source, today, n, "ok")
        print("pl-regions: {0}: {1} sejmik act(s) read, {2} on our ground, {3} new to the store{4}".format(
            name, n, ours, new, " (first read: kept as seed)" if first and new else ""))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
