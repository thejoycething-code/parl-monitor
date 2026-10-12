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

  REGISTERS (four sejmiki). The sejmiki's own registers of resolutions in
  their BIP, where the register is a plain list: every resolution adopted,
  binding or not (stanowiska and apele included, which the journals never
  carry).
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
  The other twelve registers are a JavaScript application, a host that does
  not answer, or a layout not parsed yet: each is listed in the scope doc.

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
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt  # noqa: E402
from src import pl_regions_store as plr  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
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
REGISTERS = ("mz", "sl", "ld", "pk")

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
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
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


# --- classification and storing --------------------------------------------------

def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, wl, a, watch_path=None):
    res = filt.filter_item(tax, wl, a.get("title") or "", title=a.get("title") or "")
    return plr.add_watch_areas(res, a["key"], watch_path)


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


REGISTER_FETCH = {"mz": fetch_cms, "sl": fetch_cms, "ld": fetch_lodzkie, "pk": fetch_podkarpackie}


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
    client = GuardedClient(HttpClient(raw_dir=os.path.join(ROOT, "data", "raw")), FEED)
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
