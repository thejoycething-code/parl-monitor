"""France: the Assemblée nationale's and the Sénat's e-petition platforms.

Both are Decidim sites (petitions.assemblee-nationale.fr, petitions.senat.fr),
probed 11 October 2026. Their GraphQL API (/api) answers 500 to every query,
even `{ __typename }`, so the public listing is read instead: one card per
petition with its id (i-NNNN), title, petitioner, status ('Enregistrée',
'En cours'), the committee it is assigned to (Assemblée), the date it was
filed, the first hundred-odd characters of its text, and its signature count
against the 100,000 threshold. The listing's default filter is the open
petitions; per_page=100 is accepted, so the Assemblée's ~1,950 open petitions
are 20 pages and the Sénat's 89 one. robots.txt allows both.

THE ITEM PAGE carries the closing date ('Date limite de recueil des
signatures' at the Assemblée, open until the end of the legislature;
'Période de recueil des signatures' with both dates at the Sénat, six months)
and the full text (in the share widget's data-desc attribute). The Sénat's
pages are read for every new petition (89 open); the Assemblée's only for a
petition whose listed words are already on our ground, because its open list
is two thousand long. So an Assemblée petition whose title and opening line
say nothing of our ground is not seen; noted in the Coverage line.

THRESHOLDS. Assemblée (Règlement, art. 148): 100,000 signatures and the
petition goes online for the Conférence des présidents, which may decide a
debate in séance; 500,000 from at least 30 departments or overseas
territories and the Conférence may organise a debate in séance publique.
Sénat: 100,000 within six months and the Conférence des présidents decides
any follow-up (a control mission, a text on the agenda, a debate).
"""

from __future__ import annotations

import html as htmlmod
import re

from src import petitions as P

CC = "fr"
AN = "https://petitions.assemblee-nationale.fr"
SENAT = "https://petitions.senat.fr"
LIST = "{0}/initiatives?order=recent&per_page=100&page={1}"
MAX_PAGES = 40           # the Assemblée's open list is 20 pages; a runaway guard

AN_THRESHOLDS = (
    (100000, "online for the Conférence des présidents, which may decide a debate"),
    (500000, "from 30 departments, the Conférence may organise a debate in séance publique"),
)
SENAT_THRESHOLDS = (
    (100000, "within six months, the Conférence des présidents decides any follow-up"),
)

_CARD = re.compile(r'<div class="column" id="initiative_')


def _text(fragment):
    return P.one_line(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def _first(pattern, text, flags=re.S):
    m = re.search(pattern, text, flags)
    return m.group(1) if m else None


def parse_list(page, base, source):
    """[entry] for one listing page of a Decidim petitions site."""
    out = []
    parts = _CARD.split(page)
    for part in parts[1:]:
        pid = _first(r'href="/initiatives/(i-\d+)"', part)
        if not pid:
            continue
        title = _text(_first(r'<span class="card__title"[^>]*>(.*?)</span>', part))
        status = _text(_first(r'card__text--status">(.*?)</span>', part))
        summary = _first(r'card__text--status">.*?</span>\s*<span[^>]*>(.*?)</span>', part)
        author = _text(_first(r'<span class="author__name">(.*?)</span>', part))
        tags = _first(r'<ul class="tags[^"]*">(.*?)</ul>', part) or ""
        body = _text(_first(r'<a [^>]*>(.*?)</a>', tags))
        filed = _text(_first(r'creation_date_status">(.*?)</li>', part))
        sigs = _text(_first(r'progress__bar__number">(.*?)</span>', part))
        out.append(P.entry(source, pid, title, summary=_text(summary).rstrip(". ").rstrip("…")
                           if summary else None, status=status, opened=filed, signatures=sigs,
                           author=author, body=body, url="{0}/initiatives/{1}".format(base, pid)))
    return out


def last_page(page):
    nums = [int(n) for n in re.findall(r"[?&](?:amp;)?page=(\d+)", page)]
    return max(nums) if nums else 1


def parse_detail(page):
    """{closes, opened, text, signatures} from an item page."""
    dates = re.findall(r"\d{2}/\d{2}/\d{4}", _first(
        r'<span class="phase-date">(.*?)</span>', page) or "")
    text = _first(r"data-desc='(.*?)' data-via", page)
    sigs = _text(_first(r'progress__bar__number">(.*?)</span>', page))
    out = {"text": htmlmod.unescape(text).strip()[:P.TEXT_CAP] if text else None,
           "signatures": P.number(sigs)}
    if len(dates) >= 2:
        out["opened"], out["closes"] = P.iso(dates[0]), P.iso(dates[-1])
    elif dates:
        out["closes"] = P.iso(dates[0])
    return out


def _fetch(base, source):
    def fetch(client, today, log=print):
        entries, gaps, pages = [], [], 0
        page, last = 1, 1
        while page <= min(last, MAX_PAGES):
            try:
                raw = client.get_text(LIST.format(base, page), "fr-petitions",
                                      "{0}-list-{1}".format(source, page))
            except Exception as exc:                # noqa: BLE001
                gaps.append("listing page {0} unreadable: {1}".format(page, str(exc)[:120]))
                break
            pages += 1
            got = parse_list(raw, base, source)
            if not got:
                break
            entries += got
            last = max(last, last_page(raw))
            page += 1
        return P.fetched(entries, note="{0} listing page(s), open petitions".format(pages)
                         + ("; pages read only when the listed words match" if source == "an"
                            else ""), gaps=gaps)
    return fetch


def _detail(source):
    def detail(client, e, log=print):
        raw = client.get_text(e["url"], "fr-petitions",
                              "{0}-{1}".format(source, e["item_id"].split(":")[-1]))
        return parse_detail(raw)
    return detail


SOURCES = (
    P.Source(code="an", name="Assemblée nationale e-petitions", kind="petition",
             fetch=_fetch(AN, "an"), detail=_detail("an"), thresholds=AN_THRESHOLDS, url=AN),
    P.Source(code="senat", name="Sénat e-petitions", kind="petition",
             fetch=_fetch(SENAT, "senat"), detail=_detail("senat"), detail_all=True,
             thresholds=SENAT_THRESHOLDS, url=SENAT),
)
