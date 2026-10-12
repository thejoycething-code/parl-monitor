"""Member portraits and party colour chips for the country vote pages
(12 October 2026; Chris: member portraits and party logos, "check photo
licences first").

    from src import portraits as pt
    pt.SOURCES["pl"].licence_class        # 'attribution'
    pt.fetch_country(client, cc, keys)    # tools/fetch_portraits.py, the Mini step
    pt.attach(data, out_dir)              # tools/make_country_votes.py

THE GATE IS docs/portraits-logos-licences.md. Every legislature with a
monitor is classed there from its own terms:
  attribution   an open licence or an explicit permission to reuse with
                credit (CC BY, CC0, Licence Ouverte, public domain);
  internal      reuse allowed for non-commercial or informational purposes
                with the source cited (the partner pages are passphrase-gated
                and non-commercial, so they qualify);
  not_allowed   all rights reserved or an explicit prohibition (or the
                site's robots.txt bars us): NEVER fetched;
  unclear       no terms found;
  unclear_used  used on Chris's instruction, licence unclear (12 October
                2026: "use the photos anyway where possible"); the page
                credits "Photo: <institution> (official portrait)".
Only a country in SOURCES whose class is in USABLE gets portraits; every
other country's page renders exactly as before. Adding a country means a
licence row in the doc first, then a Source here.

CHRIS, 12 OCTOBER 2026 (additive): the partner pages (passphrase-gated,
shared with partners) count as allowed non-commercial/internal use, so the
internal-only Italy, Netherlands, Austria and Switzerland are enabled ("Yes
for all four"); and the 21 "unclear" legislatures moved to unclear_used.
Each is fetched only where the store's member key leads to the official
photo; the doc says which are not mappable yet and why.

ROBOTS (12 October 2026): Robots now reads robots.txt through the per-run
guard (src/robots_guard.RobotsGuard, src/prov_fetch.read_robots: patient
reads, a 24-hour copy, a 5xx or no answer = Disallow: / for the host,
Crawl-delay honoured), with DOCUMENTED_APIS fetched as the collectors fetch
them (the Sejm API, Tweede Kamer OData; docs/robots-runtime.md). Stricter
than the guard for photos: a robots.txt answering 401/403 still means no
fetch from that host.

WHAT IS STORED. tools/fetch_portraits.py downloads each member's official
photo from the parliament's own site (src/http.py: honest UA, per-host
throttle; robots.txt checked first, a refusal is respected), shrinks it to a
THUMB-px JPEG with macOS sips (the Mini; no sips and no PIL means no
thumbnail, never a full-size file), and keeps:
  data/portraits/<cc>/<file>.jpg   the thumbnail cache (gitignored);
  data/portraits/<cc>.json         the manifest (committed): per member the
                                   image URL, the member's page, the licence
                                   and credit line, fetched date, sha256.
Nothing is hotlinked: the vote page build (attach) copies only the
thumbnails of members on the page into partner_site/portraits/<cc>/ (behind
the partner passphrase, like every vote page) and prunes the rest. A member
with no manifest entry, or whose thumbnail is in neither place, gets the
initials circle, as the UK tracker does when its image fails. DMs never carry
a portrait.

PARTY LOGOS ARE NOT USED. Party logos are trademarks with no open licence
from any official source we found (docs/portraits-logos-licences.md, "Party
logos"); the existing UK slot (partner_site/logos/README.md) stays empty by
CitizenGO's choice. Pages show a party colour chip instead, from
config/party-colours.yaml (a colour is not a mark), and no chip where the
colour is not listed.

Read-only on the store. No paid service, no AI call.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Callable, Optional
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "data", "portraits")
SITE_SUBDIR = "portraits"
COLOURS_PATH = os.path.join(ROOT, "config", "party-colours.yaml")

THUMB = 96                 # px, the longer side; about 3-5 KB a JPEG
QUALITY = 70
RECHECK_MISSING_DAYS = 30  # a member with no photo is looked for again after this
REFRESH_DAYS = 180         # a fetched photo is refreshed after this
FEED = "portraits"

CLASSES = ("attribution", "internal", "not_allowed", "unclear", "unclear_used")
USABLE = ("attribution", "internal", "unclear_used")


@dataclasses.dataclass
class Source:
    cc: str
    legislature: str
    licence_class: str                  # one of CLASSES
    licence: str                        # the licence or terms, in a few words
    terms_url: str
    credit: str                         # the attribution line the page shows
    # fn(key, member) -> (image_url, page_url) or (None, None); `member` is
    # the profiles' Member (name, chamber) for sources keyed by name.
    photo: Optional[Callable] = None
    # fn(client, key, member) -> (image_url, page_url): sources that need the
    # member's page read to find the image (one extra request per member).
    photo_from_page: Optional[Callable] = None
    chambers: tuple = ()                # only these chambers (Member.chamber); () = all

    @property
    def usable(self):
        return self.licence_class in USABLE and bool(self.photo or self.photo_from_page)


# --- the sources (each one's licence row: docs/portraits-logos-licences.md) ----------

def _br(key, m):
    """Camara: the open data API's urlFoto by deputy id; Senado: the API's
    UrlFotoParlamentar by senator code. Both keyed in the store."""
    k = str(key)
    if k.startswith("camara-") and k[7:].isdigit():
        n = k[7:]
        return ("https://www.camara.leg.br/internet/deputado/bandep/{0}.jpg".format(n),
                "https://www.camara.leg.br/deputados/{0}".format(n))
    if k.startswith("senado-") and k[7:].isdigit():
        n = k[7:]
        return ("https://www.senado.leg.br/senadores/img/fotos-oficiais/senador{0}.jpg".format(n),
                "https://www25.senado.leg.br/web/senadores/senador/-/perfil/{0}".format(n))
    return None, None


HR_SITE = "https://www.sabor.hr"
HR_PHOTO = re.compile(r'(?:src|href)="(/sites/default/files/uploads/sabor/[^"]+\.(?:jpe?g|png))"', re.I)


def hr_photo_in(page_html):
    """The portrait path on a Sabor member page, or None."""
    m = HR_PHOTO.search(page_html or "")
    return html.unescape(m.group(1)) if m else None


def _hr_from_page(client, key, m):
    """Sabor: no id-based photo URL; the member's own page names the file."""
    k = str(key)
    if not re.fullmatch(r"[a-z0-9-]+", k):
        return None, None
    page = "{0}/hr/zastupnici/{1}".format(HR_SITE, k)
    path = hr_photo_in(client.get_text(page, FEED, "hr-page-" + k, archive=False))
    return (HR_SITE + path if path else None), page


def _pl(key, m):
    """Sejm: the store keys a deputy '<term>/<id>' (api.sejm.gov.pl MP id);
    the documented API serves the official photo at /MP/{id}/photo."""
    hit = re.fullmatch(r"(\d{1,2})/(\d{1,4})", str(key))
    if not hit:
        return None, None
    term, n = hit.group(1), hit.group(2)
    return ("https://api.sejm.gov.pl/sejm/term{0}/MP/{1}/photo".format(term, n),
            "https://www.sejm.gov.pl/Sejm{0}.nsf/posel.xsp?id={1:03d}&type=A".format(
                term, int(n)))


def _pt(key, m):
    """Assembleia da Republica: the store keys a deputy by BID, the id the
    Parliament's own image service and biography page use."""
    k = str(key)
    if not k.isdigit():
        return None, None
    return ("https://app.parlamento.pt/webutils/getimage.aspx?id={0}&type=deputado".format(k),
            "https://www.parlamento.pt/DeputadoGP/Paginas/Biografia.aspx?BID={0}".format(k))


def _ch(key, m):
    """Swiss Parliament: the store keys a member by PersonNumber
    (src/ch_store.py); parlament.ch files the portrait under it."""
    k = str(key)
    if not k.isdigit():
        return None, None
    img = "https://www.parlament.ch/SiteCollectionImages/profil/portrait-260/{0}.jpg".format(k)
    return img, img


NL_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _nl(key, m):
    """Tweede Kamer: the store keys a member by the gegevensmagazijn Persoon
    Id; the OData Persoon resource is the official photo (some persons have
    none: a 404 is recorded as missing and rechecked after a month)."""
    k = str(key).lower()
    if not NL_UUID.fullmatch(k):
        return None, None
    base = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Persoon({0})".format(k)
    return base + "/resource", base


AT_SITE = "https://www.parlament.gv.at"
AT_PHOTO = re.compile(r"(/dokument/bild/\d+/\d+_384\.jpg)")


def at_photo_in(page_html):
    """The 384 px portrait path on a parlament.gv.at person page, or None."""
    m = AT_PHOTO.search(page_html or "")
    return m.group(1) if m else None


def _at_from_page(client, key, m):
    """Parlament Oesterreich: the store keys a member by PAD ('/person/88386');
    the person page names the portrait file (no id-based photo URL)."""
    k = str(key)
    if not k.isdigit():
        return None, None
    page = "{0}/person/{1}".format(AT_SITE, k)
    path = at_photo_in(client.get_text(page, FEED, "at-page-" + k, archive=False))
    return (AT_SITE + path if path else None), page


def _none(key, m):
    return None, None


def _src(cc, legislature, cls, licence, terms, credit="", photo=None, photo_from_page=None):
    return Source(cc, legislature, cls, licence, terms, credit, photo, photo_from_page)


# Every country with a vote page (src/country_votes.COUNTRIES), classed from
# docs/portraits-logos-licences.md. Only a usable class WITH a photo route
# fetches anything.
UNCLEAR_CREDIT = "{0} (official portrait)"
SOURCES = {
    # OK with attribution, and a photo URL we can build from the store's key.
    "br": _src("br", "Camara dos Deputados and Senado Federal", "attribution",
               "free reuse with credit (Camara terms; Agencia Senado policy)",
               "https://www2.camara.leg.br/termo-de-uso-e-politica-de-privacidade/termos-gerais",
               "Arquivo/Camara dos Deputados; Agencia Senado (free reuse with credit)", photo=_br),
    "hr": _src("hr", "Hrvatski sabor", "attribution",
               "may be downloaded without permission, source cited, unaltered",
               "https://www.sabor.hr/hr/pravne-napomene",
               "Hrvatski sabor (source cited, reproduced unaltered, shown at thumbnail size)",
               photo_from_page=_hr_from_page),
    # OK, but no photo URL from what the store keeps (no id): not fetched yet.
    "es": _src("es", "Congreso de los Diputados", "attribution",
               "reuse allowed citing the source, unaltered (aviso legal)",
               "https://www.congreso.es/es/cem/aviso-legal",
               "Fuente: Congreso de los Diputados"),
    "ar": _src("ar", "Camara de Diputados de la Nacion", "attribution",
               "public domain, source to be cited (HCDN site notice)",
               "https://www.hcdn.gob.ar/diputados/",
               "Fuente: Honorable Camara de Diputados de la Nacion"),
    # OK internal-only; Chris, 12 October 2026: the passphrase-gated partner
    # pages count as allowed non-commercial/internal use ("Yes for all four").
    "nl": _src("nl", "Tweede Kamer", "internal", "CC BY-NC 4.0 (disclaimer)",
               "https://www.tweedekamer.nl/applicaties/disclaimer",
               "Tweede Kamer (CC BY-NC 4.0; non-commercial use)", photo=_nl),
    "at": _src("at", "Parlament Oesterreich", "internal",
               "reporting, political education, private non-commercial use only",
               "https://www.parlament.gv.at/services/hilfe/nutzungsbedingungen/",
               "Parlamentsdirektion (official portrait; non-commercial informational use)",
               photo_from_page=_at_from_page),
    "ch": _src("ch", "Bundesversammlung", "internal",
               "media and informational use; commercial use needs written consent",
               "https://www.parlament.ch/de/services/mediathek/fotos-nutzungsbedingungen",
               "Parlamentsdienste / ParlCH (official portrait; non-commercial use)", photo=_ch),
    # Italy: enabled, but not mappable yet. The Camera's photo is filed by
    # Camera ID and the store keys deputies by Openpolis membership id with
    # no Camera ID (it_members.camera_id empty); senato.it serves us empty
    # pages (no photo path readable, nothing bypassed).
    "it": _src("it", "Camera dei deputati and Senato", "internal",
               "non-commercial reuse, integrity kept, source cited",
               "https://comunicazione.camera.it/policy/avvisolegale",
               "Fonte: Camera dei deputati; Senato della Repubblica"),
    # Not allowed: never fetched.
    "fr": _src("fr", "Assemblee nationale and Senat", "not_allowed",
               "photographs need prior agreement; all rights reserved",
               "https://www.assemblee-nationale.fr/dyn/info-site"),
    "sk": _src("sk", "Narodna rada SR", "not_allowed", "all rights reserved",
               "https://www.nrsr.sk/"),
    "do": _src("do", "Camara de Diputados and Senado", "not_allowed",
               "all rights reserved; the Senado's robots.txt bars us",
               "https://camaradediputados.gob.do/"),
    # Used on Chris's instruction, licence unclear (12 October 2026, "use the
    # photos anyway where possible"). Mapped where the key leads to the photo.
    "pl": _src("pl", "Sejm", "unclear_used", "no terms found for the API photos",
               "https://api.sejm.gov.pl/", UNCLEAR_CREDIT.format("Sejm RP"), photo=_pl),
    "pt": _src("pt", "Assembleia da Republica", "unclear_used",
               "open data terms do not mention photos",
               "https://www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx",
               UNCLEAR_CREDIT.format("Assembleia da Republica"), photo=_pt),
    # ... and not mappable yet (the reason is the doc's "Not mappable yet").
    "be": _src("be", "Chambre des representants / Kamer", "unclear_used",
               "no portrait terms found (the Chamber's firewall refuses us)",
               "https://www.dekamer.be/", UNCLEAR_CREDIT.format("Chambre / Kamer")),
    "hu": _src("hu", "Orszaggyules", "unclear_used", "terms behind a CAPTCHA",
               "https://parlament.hu/documents/d/guest/jogi-nyilatkozat",
               UNCLEAR_CREDIT.format("Orszaggyules")),
    "mx": _src("mx", "Camara de Diputados and Senado", "unclear_used", "no terms found",
               "https://www.diputados.gob.mx/", UNCLEAR_CREDIT.format("Congreso de la Union")),
    "cl": _src("cl", "Camara, Senado and BCN", "unclear_used",
               "no terms on the sites; BCN's CC BY-SA 3.0 CL is second-hand",
               "https://www.bcn.cl/historiapolitica/resenas_parlamentarias/",
               UNCLEAR_CREDIT.format("Camara de Diputadas y Diputados; Senado de Chile")),
    "pe": _src("pe", "Congreso de la Republica", "unclear_used", "no terms found",
               "https://diputados.congreso.gob.pe/politica-de-privacidad/",
               UNCLEAR_CREDIT.format("Congreso de la Republica")),
    "ec": _src("ec", "Asamblea Nacional", "unclear_used",
               "no terms on the site (its Flickr is CC BY-SA 2.0, per photo)",
               "https://www.flickr.com/photos/asambleanacional",
               UNCLEAR_CREDIT.format("Asamblea Nacional")),
    "sv": _src("sv", "Asamblea Legislativa", "unclear_used",
               "site unreachable (certificate error)", "https://www.asamblea.gob.sv/",
               UNCLEAR_CREDIT.format("Asamblea Legislativa")),
    "gt": _src("gt", "Congreso de la Republica", "unclear_used", "site refuses us (403)",
               "https://www.congreso.gob.gt/", UNCLEAR_CREDIT.format("Congreso de la Republica")),
    "co": _src("co", "Camara and Senado", "unclear_used", "terms PDF unreadable; Senado none",
               "https://www.camara.gov.co/", UNCLEAR_CREDIT.format("Congreso de Colombia")),
    "uy": _src("uy", "Parlamento", "unclear_used", "site refuses us (403)",
               "https://parlamento.gub.uy/", UNCLEAR_CREDIT.format("Parlamento del Uruguay")),
}


def usable_countries():
    return sorted(cc for cc, s in SOURCES.items() if s.usable)


# --- files ----------------------------------------------------------------------------

def file_for(key):
    """A stable, path-safe thumbnail name for a member key."""
    return hashlib.sha1(str(key).encode("utf-8")).hexdigest()[:16] + ".jpg"


def manifest_path(cc, cache_dir=CACHE_DIR):
    return os.path.join(cache_dir, "{0}.json".format(cc))


def load_manifest(cc, cache_dir=CACHE_DIR):
    try:
        with open(manifest_path(cc, cache_dir), encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        got = {}
    got.setdefault("members", {})
    got.setdefault("missing", {})
    return got


def save_manifest(cc, manifest, cache_dir=CACHE_DIR):
    os.makedirs(cache_dir, exist_ok=True)
    src = SOURCES.get(cc)
    if src:
        manifest.update({"country": cc, "legislature": src.legislature,
                         "licence_class": src.licence_class, "licence": src.licence,
                         "terms_url": src.terms_url, "credit": src.credit})
    manifest["members"] = dict(sorted(manifest["members"].items()))
    manifest["missing"] = dict(sorted(manifest["missing"].items()))
    text = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    path = manifest_path(cc, cache_dir)
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
    if old != text:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)


def is_image(raw):
    """JPEG, PNG, GIF or WebP magic bytes: a page or an error body is not a photo."""
    return bool(raw) and (raw[:3] == b"\xff\xd8\xff" or raw[:8] == b"\x89PNG\r\n\x1a\n"
                          or raw[:6] in (b"GIF87a", b"GIF89a")
                          or (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"))


def shrink(raw, size=THUMB):
    """Image bytes -> a size-px JPEG (sips on macOS, else PIL), or None.
    Never returns the original: no thumbnail is better than a full-size copy."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in"), os.path.join(d, "out.jpg")
        with open(src, "wb") as fh:
            fh.write(raw)
        if shutil.which("sips"):
            r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions",
                                str(QUALITY), "-Z", str(size), src, "--out", dst],
                               capture_output=True)
            if r.returncode == 0 and os.path.exists(dst):
                with open(dst, "rb") as fh:
                    return fh.read()
            return None
        try:
            from PIL import Image  # optional; not a dependency
        except ImportError:
            return None
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((size, size))
                im.save(dst, "JPEG", quality=QUALITY)
            with open(dst, "rb") as fh:
                return fh.read()
        except Exception:
            return None


# --- robots.txt -----------------------------------------------------------------------

class _WatchRobots:
    """Passes everything to the client; notes the hosts whose robots.txt
    answered 401/403 (the guard reads any 4xx as "no rules")."""

    def __init__(self, client, refused):
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_refused", refused)

    def __getattr__(self, name):
        return getattr(self._client, name)

    def __setattr__(self, name, value):
        setattr(self._client, name, value)

    def get_text(self, url, feed, slug, *args, **kwargs):
        try:
            return self._client.get_text(url, feed, slug, *args, **kwargs)
        except Exception as exc:
            status = getattr(getattr(exc, "cause", None), "code", None)
            if url.endswith("/robots.txt") and status in (401, 403):
                self._refused.add(urlsplit(url).netloc)
            raise


class Robots:
    """robots.txt per host, read once per run through the per-run guard
    (src/robots_guard.RobotsGuard over src/prov_fetch.read_robots): a missing
    file (404) allows; a 5xx or no answer means Disallow: / for the host (a
    copy read in the last 24 hours stands in); Crawl-delay raises that host's
    throttle. Documented machine APIs (robots_guard.DOCUMENTED_APIS: the Sejm
    API, Tweede Kamer OData) are fetched as every collector fetches them.
    Stricter than the guard for photos: a robots.txt that answers 401/403
    means no fetch from that host. An unreadable robots.txt never becomes a
    licence to fetch."""

    def __init__(self, client, log=None, exempt=None, **robots_kwargs):
        from src import robots_guard as rg
        self.client = client
        self.refused_hosts = set()
        self.exempt = rg.DOCUMENTED_APIS if exempt is None else tuple(exempt)
        self._is_api = rg.is_documented_api
        self.guard = rg.RobotsGuard(_WatchRobots(client, self.refused_hosts), FEED,
                                    log=log or (lambda *a, **k: None), **robots_kwargs)

    def allowed(self, url):
        if self.exempt and self._is_api(url, self.exempt):
            return True
        refused = self.guard.refusal(url)
        if urlsplit(url).netloc in self.refused_hosts:
            return False
        return refused is None


# --- fetching -------------------------------------------------------------------------

class PageRefused(Exception):
    """A member page robots.txt does not allow; it was never requested."""

    def __init__(self, url):
        super().__init__("robots.txt disallows " + url)
        self.url = url


class _Checked:
    """The client as photo_from_page sees it: a member page is requested only
    when robots.txt allows it (12 October 2026; the image was always checked)."""

    def __init__(self, client, robots):
        self._client, self._robots = client, robots

    def __getattr__(self, name):
        return getattr(self._client, name)

    def get_text(self, url, *args, **kwargs):
        if not self._robots.allowed(url):
            raise PageRefused(url)
        return self._client.get_text(url, *args, **kwargs)


def _days_since(iso, today):
    try:
        return (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(iso[:10])).days
    except (TypeError, ValueError):
        return 10 ** 6


def due(manifest, key, today):
    """True when a member's photo should be (re)fetched."""
    got = manifest["members"].get(key)
    if got:
        return _days_since(got.get("fetched"), today) >= REFRESH_DAYS
    miss = manifest["missing"].get(key)
    if miss:
        return _days_since(miss.get("checked"), today) >= RECHECK_MISSING_DAYS
    return True


def fetch_country(client, cc, members, today, max_fetch=200, cache_dir=CACHE_DIR,
                  shrink_fn=shrink, robots=None, log=print):
    """Fetch the due portraits of `members` ([(key, Member)]) for one country.
    Returns {fetched, missing, refused, skipped_not_due, left}. Writes the
    cache and the manifest; never the store."""
    src = SOURCES.get(cc)
    if src is None or not src.usable:
        raise ValueError("no usable portrait source for {0} "
                         "(docs/portraits-logos-licences.md)".format(cc))
    robots = robots or Robots(client)
    manifest = load_manifest(cc, cache_dir)
    folder = os.path.join(cache_dir, cc)
    os.makedirs(folder, exist_ok=True)
    out = {"fetched": 0, "missing": 0, "refused": 0, "not_due": 0, "left": 0}
    budget = max_fetch
    for key, m in members:
        key = str(key)
        if src.chambers and (getattr(m, "chamber", None) not in src.chambers):
            continue
        if not due(manifest, key, today):
            out["not_due"] += 1
            continue
        if budget <= 0:
            out["left"] += 1
            continue
        budget -= 1
        try:
            if src.photo_from_page:
                image_url, page_url = src.photo_from_page(_Checked(client, robots), key, m)
            else:
                image_url, page_url = src.photo(key, m)
        except PageRefused as exc:
            manifest["missing"][key] = {"checked": today, "why": "robots.txt disallows",
                                        "page_url": exc.url}
            out["refused"] += 1
            continue
        except Exception as exc:
            image_url, page_url = None, None
            log("  portraits {0}: {1}: no photo URL ({2})".format(cc, key, exc))
        if not image_url:
            manifest["missing"][key] = {"checked": today, "why": "no photo URL for this member"}
            out["missing"] += 1
            continue
        if not robots.allowed(image_url):
            manifest["missing"][key] = {"checked": today, "why": "robots.txt disallows",
                                        "image_url": image_url}
            out["refused"] += 1
            continue
        try:
            raw = client.get_bytes(image_url, FEED, "{0}-{1}".format(cc, file_for(key)[:-4]),
                                   archive=False)
        except Exception as exc:
            manifest["missing"][key] = {"checked": today, "why": "fetch failed: {0}".format(
                str(exc)[:120]), "image_url": image_url}
            out["missing"] += 1
            continue
        thumb = shrink_fn(raw) if is_image(raw) else None
        if not thumb:
            manifest["missing"][key] = {"checked": today, "image_url": image_url,
                                        "why": "not an image" if not is_image(raw)
                                        else "could not make a thumbnail"}
            out["missing"] += 1
            continue
        name = file_for(key)
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(thumb)
        manifest["missing"].pop(key, None)
        manifest["members"][key] = {
            "file": name, "image_url": image_url, "page_url": page_url or image_url,
            "fetched": today, "sha256": hashlib.sha256(thumb).hexdigest(), "bytes": len(thumb)}
        out["fetched"] += 1
    save_manifest(cc, manifest, cache_dir)
    return out


# --- the page -------------------------------------------------------------------------

def attach(data, out_dir, cache_dir=CACHE_DIR, colours=None):
    """Add portraits and party colours to a vote page's data (country_votes.build)
    and copy the thumbnails of members on the page into
    <out_dir>/portraits/<cc>/, pruning any others there. Additive keys:
      portraits        {member index: [src, page_url]}
      portrait_credit  the licence line (shown on the member card and in the notes)
      colours          {party or group label: "#rrggbb"}
    A country with no usable source gets no portrait keys and nothing copied."""
    cc = data["cc"]
    keys = data.get("_keys") or []
    colours = load_colours() if colours is None else colours
    mine = colours.get(cc) or {}
    labels = set(data.get("groups") or []) | {m[1] for m in data.get("members") or [] if m[1]}
    data["colours"] = {p: c for p, c in mine.items() if p in labels}
    src = SOURCES.get(cc)
    if src is None or not src.usable:
        return data
    manifest = load_manifest(cc, cache_dir)
    site = os.path.join(out_dir, SITE_SUBDIR, cc)
    wanted, got = set(), {}
    for i, key in enumerate(keys):
        row = manifest["members"].get(str(key))
        if not row or not row.get("file"):
            continue
        name = row["file"]
        cached = os.path.join(cache_dir, cc, name)
        target = os.path.join(site, name)
        if os.path.exists(cached):
            os.makedirs(site, exist_ok=True)
            if not os.path.exists(target) or _sha(target) != _sha(cached):
                shutil.copyfile(cached, target)
        if not os.path.exists(target):
            continue      # neither cached here nor already published: initials
        wanted.add(name)
        got[i] = ["{0}/{1}/{2}".format(SITE_SUBDIR, cc, name), row.get("page_url")]
    if os.path.isdir(site):
        for name in os.listdir(site):
            if name.endswith(".jpg") and name not in wanted:
                os.remove(os.path.join(site, name))
    if got:
        data["portraits"] = got
        data["portrait_credit"] = src.credit
        data["portrait_terms"] = src.terms_url
    return data


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_colours(path=COLOURS_PATH):
    """{cc: {party label: '#rrggbb'}} from config/party-colours.yaml; {} when absent.
    Only well-formed hex colours are kept."""
    try:
        import yaml
    except ImportError:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except OSError:
        return {}
    out = {}
    for cc, parties in (raw.get("countries") or {}).items():
        out[str(cc)] = {str(p): str(c) for p, c in (parties or {}).items()
                        if re.fullmatch(r"#[0-9a-fA-F]{6}", str(c or ""))}
    return out
