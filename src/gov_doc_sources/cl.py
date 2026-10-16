"""Chile: the Diario Oficial's Normas Generales (laws, decrees and
resolutions of general application).

Probed 16 October 2026. www.diariooficial.interior.gob.cl's robots.txt
disallows /publicaciones/, /edicionelectronica/ and /media/ for every
agent, then allows "/publicaciones/*/*/*/*/01/" (the Normas Generales
section's PDFs) and "/edicionelectronica/index.php" (the edition's
summary page). Only that page is read:

  * /edicionelectronica/index.php (no query) is today's edition: the
    Normas Generales summary under PODER LEGISLATIVO / PODER EJECUTIVO /
    other headings, by ministry (title4) and service (title5), one row per
    norm with its official summary line ("Resolución exenta número 668, de
    2026.- Determina ...") and its PDF (CVE number) under the allowed
    /publicaciones/.../01/ path;
  * index.php?date=DD-MM-YYYY&edition=N is an earlier edition. Editions are
    numbered in sequence; a wrong date for a number answers an empty page.
    Asking for the date only redirects to select_edition.php, which
    robots.txt disallows (the guard refuses the hop), so the reader walks
    back from today's number, trying each earlier number against the
    preceding few dates (no edition on Sundays and holidays).

Each run reads the editions of the last DAYS days. The PDFs are not read.

doc_type: "Ley núm." and decrees with force of law ("Decreto con fuerza de
ley") are 'law'; a norm that puts a draft out for public consultation
("Somete a consulta pública") is a 'regulation_draft' (its period is in the
PDF, so no closing date); every other row is a 'regulation'.

Not used: the ministries' "consultas ciudadanas" (each ministry runs its
own page; no national listing found).
"""

from __future__ import annotations

import datetime
import html as htmlmod
import re

from src import gov_docs as G

CC = "cl"
TAXONOMIES = (("taxonomy-es.yaml", "cl"),)
BASE = "https://www.diariooficial.interior.gob.cl/edicionelectronica/"
TODAY_URL = BASE + "index.php"
EDITION = BASE + "index.php?date={0}&edition={1}"
DAYS = 14
TRIES = 4           # dates tried for one edition number (Sunday + holiday + slack)
MAX_PAGES = 30

LAW = re.compile(r"(?i)^(ley\s+n[uú]m|decreto\s+con\s+fuerza\s+de\s+ley)")
DRAFT = re.compile(r"(?i)somete\s+a\s+consulta\s+p[uú]blica|consulta\s+ciudadana")
ROW = re.compile(r'<tr>\s*<td class="title([345])">(.*?)</td>|<tr class="content">\s*<td>(.*?)</td>\s*'
                 r'<td><a[^>]*href="([^"]+)"[^>]*>\s*Ver PDF \(CVE-(\d+)\)', re.S)
SMALL = {"de", "la", "del", "los", "las", "y", "e", "en", "para", "por", "el", "a"}


def nice(name):
    words = (name or "").lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def flat(fragment):
    return G.one_line(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def doc_type(line):
    if DRAFT.search(line or ""):
        return "regulation_draft"
    if LAW.search(line or ""):
        return "law"
    return "regulation"


def has_edition(page):
    return 'class="title2">Normas Generales' in (page or "")


def current_edition(page):
    """(date ISO, edition number) of the page index.php answers with no query."""
    m = re.search(r"index\.php\?date=(\d{2}-\d{2}-\d{4})&(?:amp;)?edition=(\d+)", page or "")
    if not m:
        return None, None
    return G.iso(m.group(1)), int(m.group(2))


def parse_edition(page, published):
    """Entries from one edition's Normas Generales summary."""
    out = []
    branch = ministry = service = ""
    for m in ROW.finditer(page or ""):
        if m.group(1):
            level, name = m.group(1), flat(m.group(2))
            if level == "3":
                branch, ministry, service = name, "", ""
            elif level == "4":
                ministry, service = name, ""
            else:
                service = name
            continue
        line, url, cve = flat(m.group(3)), m.group(4), m.group(5)
        if not line:
            continue
        body = " / ".join(x for x in (nice(ministry) if ministry.isupper() else ministry, service) if x) \
            or nice(branch)
        head, _, rest = line.partition(".- ")
        title = line if len(line) <= 300 else line[:297] + "..."
        out.append(G.entry("do", cve, title, doc_type(line), body=body or None, published=published,
                           url=url, summary=rest if rest and len(line) > 300 else None,
                           status="Diario Oficial, Normas Generales" + (", " + nice(branch)
                                                                        if branch else ""),
                           refs=[head.strip()] if rest else ()))
    return out


def fetch(client, today, log=print):
    gaps = []
    try:
        page = client.get_text(TODAY_URL, "cl-govdocs", "do-today")
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["Diario Oficial unreadable: {0}".format(str(exc)[:140])])
    date, number = current_edition(page)
    if not date:
        return G.fetched([], gaps=["Diario Oficial: today's edition number not found"])
    entries = parse_edition(page, date)
    editions, pages = 1, 1
    stop = (datetime.date.fromisoformat(today) - datetime.timedelta(days=DAYS)).isoformat()
    d = datetime.date.fromisoformat(date)
    number -= 1
    while pages < MAX_PAGES:
        found = False
        for back in list(range(1, TRIES + 1)) + [0]:     # same date last: extraordinarias
            day = d - datetime.timedelta(days=back)
            if day.isoformat() < stop:
                continue
            pages += 1
            try:
                got = client.get_text(EDITION.format(day.strftime("%d-%m-%Y"), number), "cl-govdocs",
                                      "do-{0}-{1}".format(number, day.isoformat()))
            except Exception as exc:                    # noqa: BLE001
                gaps.append("edition {0} ({1}) unreadable: {2}".format(number, day, str(exc)[:100]))
                break
            if has_edition(got):
                entries += parse_edition(got, day.isoformat())
                editions += 1
                d, found = day, True
                break
        if not found:
            break
        number -= 1
    return G.fetched(entries, gaps=gaps, note="Normas Generales of {0} edition(s) back to {1} "
                     "({2} page(s) asked)".format(editions, d.isoformat(), pages))


SOURCES = (
    G.Source(code="do", name="Diario Oficial, Normas Generales",
             url="https://www.diariooficial.interior.gob.cl/edicionelectronica/", fetch=fetch),
)
