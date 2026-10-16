"""France: the amendment a scrutin's title only numbers (16 October 2026).

src/amendtext.py is the design; this is the Assemblee nationale's source and
identifiers.

THE GAP. 7,399 of the 8,672 scrutins of the 17th legislature are titled
"l'amendement n° 516 de Mme Sandrine Rousseau a l'article 44 ... de la
proposition de loi ...": the title names the TEXT amended, not what the
amendment does, and 6,288 of them carried no area at all (measured on the
published store, sha 12dfcd342515, 16 October 2026). Their areas came from
the dossier when the dossier was ours; an amendment putting abortion or
gender into an unrelated bill was invisible.

THE SOURCE. The Assemblee's own open data (data.assemblee-nationale.fr,
Licence Ouverte, keyless; robots.txt answers 404, i.e. no rules):
Amendements.json.zip, one JSON file per amendment of the legislature
(135,189 files, 327 MB, rebuilt nightly). It is NOT downloaded whole. The
server honours HTTP Range (accept-ranges: bytes, measured), so a run reads the
zip's central directory (16 MB: every member's path, offset and size) and
then only the members it needs, a few KB each. The member paths are the link:

    json/<dossier ref>/<text uid>/AMANR5L17<organe>B<text>P<part>D1N<numero>.json
    json/DLR5L17N54776/PIONANR5L17BTC1984/AMANR5L17PO838901BTC1984P0D1N000516.json

THE LINK, by the Assemblee's own identifiers only:
  1. the scrutin's dossier (fr_divisions.dossier_ref, which tools/fr_rollcalls
     took from the scrutin itself or a unique title match) and the amendment
     number its title names;
  2. the seance publique's organe (PO838901): committee amendments carry
     the same numbers under other organes and are never taken;
  3. among the members that match (a dossier's first and new readings number
     afresh), the one whose cycleDeVie.dateSort -- the day the seance
     disposed of it -- is the scrutin's date (or the next day: a sitting past
     midnight);
  4. a scrutin with no dossier (the budget bills sit in several dossiers and
     fr_rollcalls leaves them unjoined) is linked the same way across every
     dossier, and only when exactly one seance amendment of that number was
     disposed of that day.
Anything else -- no member, or more than one -- is a gap, never a guess. A
"sous-amendement n° 45 ... a l'amendement n° 39" vote reads n° 45, the text
put to the vote; "et les amendements identiques suivants" reads the first,
whose text the identical ones share by definition.

THE PURPOSE for the ledger gate: the expose sommaire's opening (the author's
own statement of what the amendment does, like a UK explanatory statement)
and the first sentences of the dispositif (which often IS the inserted
words). The rest of the dispositif and expose are body: a social-security
amendment citing "l'article L. 2212-1 du code de la sante publique" in a list
of exemptions is not an abortion amendment.

Known unreadable shapes, said so up front: the Senat's scrutins (chamber
'senat') are not read here (see tools/fr_senat.py; the Senat's ameli
amendment data has no per-scrutin identifier in our store), and article votes
("l'article 5 de ...") are the bill's own text, not an amendment.
"""

from __future__ import annotations

import datetime
import html
import json
import os
import re
import struct
import time
import zlib

from src import amendtext, filter as filt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGISLATURE = 17
ZIP_URL = ("https://data.assemblee-nationale.fr/static/openData/repository/{0}/loi/"
           "amendements_div_legis/Amendements.json.zip")
PUBLIC_URL = "https://www.assemblee-nationale.fr/dyn/{leg}/amendements/{texte}/AN/{numero}"
SEANCE = "PO838901"          # the Assemblee's seance publique (17th legislature)
FEED = "fr-amendment-text"
PAUSE = 0.15                 # seconds between ranged reads (they bypass the client's throttle)
PURPOSE_EXPOSE = 400         # characters of the expose sommaire the gate reads
PURPOSE_DISPOSITIF = 250     # and of the dispositif
MAX_POOL = 40                # same-numbered seance amendments read for one vote, at most
MAX_POOL_LOCAL = 400         # the same with a local copy of the zip, where a read costs nothing

_NUM = re.compile(r"^(?:l'|le\s+|les\s+)(?P<kind>sous-amendements?|amendements?)(?:\s+de\s+suppression)?"
                  r"\s+n[°o]\s*(?P<num>\d+)", re.I)
_MEMBER = re.compile(r"^json/(?P<dossier>[^/]+)/(?P<texte>[^/]+)/AMANR5L\d+(?P<organe>PO\d+)"
                     r"B(?P<tb>\w+?)P(?P<part>\d+)D\d+N(?P<numero>\d+)\.json$")


def refs_of(title):
    """[('amendement'|'sous-amendement', '516')] from a scrutin title, or []."""
    m = _NUM.match(" ".join((title or "").replace("’", "'").split()))
    if not m:
        return []
    kind = "sous-amendement" if m.group("kind").lower().startswith("sous") else "amendement"
    return ["{0} {1}".format(kind, int(m.group("num")))]


def plain(raw):
    """HTML fragment -> plain text (the AN's dispositif and expose are HTML)."""
    if not isinstance(raw, str):
        return ""
    text = re.sub(r"<\s*(?:br|/p|/li|/h\d)\s*/?>", "\n", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(html.unescape(text)).replace("\xa0", " ")
    return "\n".join(" ".join(p.split()) for p in text.splitlines() if p.strip())


def _opening(text, n):
    """The first sentences of `text`, up to about n characters."""
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    cut = text.rfind(". ", 0, n)
    return text[:cut + 1] if cut > n // 3 else text[:n]


def parse_member(raw):
    """The fields we keep from one amendment JSON file."""
    a = (json.loads(raw.decode("utf-8")) or {}).get("amendement") or {}
    ident = a.get("identification") or {}
    corps = (a.get("corps") or {}).get("contenuAuteur") or {}
    cycle = a.get("cycleDeVie") or {}
    sig = a.get("signataires") or {}
    div = ((a.get("pointeurFragmentTexte") or {}).get("division") or {})
    return {"uid": a.get("uid"), "numero": ident.get("numeroLong"),
            "texte": a.get("texteLegislatifRef"), "examen": a.get("examenRef"),
            "date_sort": (cycle.get("dateSort") or "")[:10] if isinstance(cycle.get("dateSort"), str) else "",
            "date_depot": cycle.get("dateDepot") if isinstance(cycle.get("dateDepot"), str) else "",
            "sort": cycle.get("sort") if isinstance(cycle.get("sort"), str) else None,
            "authors": plain(sig.get("libelle")), "article": div.get("titre") if isinstance(div.get("titre"), str) else "",
            "dispositif": plain(corps.get("dispositif")), "expose": plain(corps.get("exposeSommaire"))}


class AmendementsZip:
    """Members of the Assemblee's amendment zip, read by HTTP Range.

    THE CDN SERVES SEVERAL BUILDS AT ONCE. The zip is rebuilt every few hours
    and the CDN's caches answer with whichever build they hold (measured 16
    October 2026: three ETags, 327,380,221 and 327,379,995 bytes, in six
    consecutive requests). A central directory from one build and a member
    from another is garbage, so every ranged reply's ETag is checked against
    the build the index was read from, and a reply from another build is
    asked again (MAX_TRIES). The member's own local header must also name the
    file the index promised. Either check failing is a gap, never a misread.

    local: a downloaded copy of the zip (AMENDTEXT_FR_ZIP=<path>, for a
    backfill), read with zipfile and no network.
    """

    MAX_TRIES = 12

    def __init__(self, client, url=None, pause=PAUSE, sleep=time.sleep, local=None):
        self.client, self.url, self.pause, self.sleep = client, url or ZIP_URL.format(LEGISLATURE), pause, sleep
        self.local = local if local is not None else os.environ.get("AMENDTEXT_FR_ZIP")
        self.etag = None
        self.requests = 0
        self._index = None
        self._zf = None
        self._members = {}

    def _get(self, rng, slug):
        if self.pause:
            self.sleep(self.pause)
        self.requests += 1
        data = self.client.get_bytes(self.url, FEED, slug, headers={"Range": "bytes=" + rng})
        meta = getattr(self.client, "last_headers", None) or {}
        etag = next((v for k, v in meta.items() if k.lower() == "etag"), None)
        return data, etag

    def _range(self, start, end, slug):
        """Bytes start..end of the build the index was read from."""
        for _ in range(self.MAX_TRIES):
            data, etag = self._get("{0}-{1}".format(start, end), slug)
            if self.etag is None or etag == self.etag:
                if len(data) != end - start + 1:
                    raise ValueError("ranged read returned {0} bytes, asked {1}".format(len(data), end - start + 1))
                return data
        raise ValueError("the CDN did not serve build {0} in {1} tries".format(self.etag, self.MAX_TRIES))

    def index(self):
        """{(dossier, numero): [(name, offset, csize)]} for the seance's amendments."""
        if self._index is not None:
            return self._index
        if self.local:
            import zipfile
            self._zf = zipfile.ZipFile(self.local)
            self._index = index_names((i.filename, i.filename, i.compress_size) for i in self._zf.infolist())
            return self._index
        # the last 64 KB holds the end-of-central-directory records (zip64 too)
        tail, self.etag = self._get("-65536", "zip-tail")
        if not tail or len(tail) > 65536:          # shorter only when the whole file is shorter
            raise ValueError("the zip's tail came back as {0} bytes (Range not honoured?)".format(len(tail)))
        if not self.etag:
            raise ValueError("no ETag on the zip: cannot tell its builds apart")
        z64 = tail.rfind(b"PK\x06\x06")
        if z64 >= 0:
            _, _, _, _, _, _, _, _, cd_size, cd_off = struct.unpack("<IQHHIIQQQQ", tail[z64:z64 + 56])
        else:
            eocd = tail.rfind(b"PK\x05\x06")
            if eocd < 0:
                raise ValueError("no end of central directory in the zip's last 64 KB")
            _, _, _, _, _, cd_size, cd_off, _ = struct.unpack("<IHHHHIIH", tail[eocd:eocd + 22])
        cd = self._range(cd_off, cd_off + cd_size - 1, "zip-central-directory")
        self._index = index_central_directory(cd)
        return self._index

    def member(self, name, offset, csize):
        if name in self._members:
            return self._members[name]
        if self._zf is not None:
            self._members[name] = parse_member(self._zf.read(offset))
            return self._members[name]
        head = self._range(offset, offset + 30 + 512 + csize - 1, "member")
        if head[:4] != b"PK\x03\x04":
            raise ValueError("no local header at {0}".format(offset))
        _, _, _, method, _, _, _, _, _, nlen, elen = struct.unpack("<IHHHHHIIIHH", head[:30])
        got = head[30:30 + nlen].decode("utf-8", "replace")
        if got != name:
            raise ValueError("member at {0} is {1}, expected {2}".format(offset, got, name))
        start = 30 + nlen + elen
        body = head[start:start + csize]
        if len(body) < csize:
            body += self._range(offset + len(head), offset + start + csize - 1, "member-rest")
        raw = zlib.decompress(body, -15) if method == 8 else body
        self._members[name] = parse_member(raw)
        return self._members[name]


def index_central_directory(cd):
    """The central directory's (name, offset, compressed size) entries, indexed."""
    entries, p = [], 0
    while cd[p:p + 4] == b"PK\x01\x02":
        (_, _, _, _, _, _, _, _, csize, usize, nlen, elen, clen, _, _, _, off) = struct.unpack(
            "<IHHHHHHIIIHHHHHII", cd[p:p + 46])
        name = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen:p + 46 + nlen + elen]
        if 0xFFFFFFFF in (csize, usize, off):
            q = 0
            while q + 4 <= len(extra):
                hid, hs = struct.unpack("<HH", extra[q:q + 4])
                if hid == 1:
                    vals = list(struct.unpack("<{0}Q".format(hs // 8), extra[q + 4:q + 4 + hs]))
                    if usize == 0xFFFFFFFF:
                        usize = vals.pop(0)
                    if csize == 0xFFFFFFFF:
                        csize = vals.pop(0)
                    if off == 0xFFFFFFFF:
                        off = vals.pop(0)
                q += 4 + hs
        p += 46 + nlen + elen + clen
        entries.append((name, off, csize))
    return index_names(entries)


def index_names(entries):
    """Seance amendments by (dossier, numero) and by numero alone (key (None, numero)).
    entries: (member name, locator, compressed size); the locator is the
    member's offset (ranged reads) or its name (a local zipfile)."""
    out = {}
    for name, loc, csize in entries:
        m = _MEMBER.match(name)
        if not m or m.group("organe") != SEANCE:
            continue
        num = str(int(m.group("numero")))
        hit = (name, loc, csize)
        out.setdefault((m.group("dossier"), num), []).append(hit)
        out.setdefault((None, num), []).append(hit)
    return out


def _texte_number(texte_uid):
    m = re.search(r"B(?:TC)?(\d+)$", texte_uid or "")
    return str(int(m.group(1))) if m else None

_ARTICLE = re.compile(r"(?:à|après|avant)\s+l['’]article\s+(?P<art>premier|\d+(?:\s+(?:bis|ter|quater|quinquies|"
                      r"sexies|septies|octies|nonies|decies))?(?:\s+[A-Z]{1,2})?)\b", re.I)
_AUTHOR = re.compile(r"\bn[°o]\s*\d+(?:\s*\(rect\.\))?(?:\s+rectifié)?\s+(?:de\s+(?:M\.|Mme)\s+(?P<name>[^,]+?)|"
                     r"du\s+(?P<gov>Gouvernement)|de la\s+(?P<com>commission))\s+(?:à|après|avant|et|de)\b", re.I)


def _fold(text):
    import unicodedata
    t = unicodedata.normalize("NFKD", text or "")
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).lower().replace("’", "'").split())


def _days(date, before=0, after=0):
    d = datetime.date.fromisoformat(date)
    return {(d + datetime.timedelta(days=k)).isoformat() for k in range(-before, after + 1)}


def choose(members, title, date):
    """(the members a scrutin can be on, how they were chosen).

    By the day the seance disposed of the amendment: the scrutin's day or the
    next; failing that, within three days (a vote "précédemment réservé" or a
    sort recorded at the end of the sitting week); failing that, the one
    tabled by that day whose fate the Assemblee never recorded. Two left (a
    joint examination of an ordinary and an organic bill numbers both from 1)
    are told apart by the article and the author the title names."""
    hits = [m for m in members if m["date_sort"] in _days(date, 0, 1)]
    how = "disposed of on"
    if not hits:
        hits = [m for m in members if m["date_sort"] in _days(date, 3, 3)]
        how = "disposed of within three days of"
    if not hits:
        hits = [m for m in members if not m["date_sort"] and m["date_depot"] and m["date_depot"] <= date]
        how = "tabled by, with no recorded fate,"
    if len(hits) > 1:
        # one amendment filed under both the committee's text (BTC2755) and
        # the bill (B2755): the same words twice are one amendment
        seen, uniq = set(), []
        for m in hits:
            sig = (m["dispositif"], m["expose"])
            if sig not in seen:
                seen.add(sig)
                uniq.append(m)
        hits = uniq
    if len(hits) > 1:
        a = _ARTICLE.search(title or "")
        if a:
            art = _fold("article " + a.group("art")).replace("article premier", "article 1er")
            narrowed = [m for m in hits if _fold(m["article"]).replace("article premier", "article 1er") == art]
            hits = narrowed or hits
    if len(hits) > 1:
        au = _AUTHOR.search(title or "")
        if au:
            who = _fold(au.group("name") or au.group("gov") or au.group("com"))
            narrowed = [m for m in hits if who and who in _fold(m["authors"])[:len(who) + 30]]
            hits = narrowed or hits
    return hits, how


class FranceReader(amendtext.Reader):
    cc, table, key_col = "fr", "fr_divisions", "division_key"

    def __init__(self, client, zip_reader=None):
        self.client = client
        self.zip = zip_reader or AmendementsZip(client)
        self._tax = None

    def _fr(self):
        """tools/fr_rollcalls.py, loaded once: its taxonomy, masks and title helpers."""
        if getattr(self, "_frmod", None) is None:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "fr_rollcalls_for_amendtext", os.path.join(ROOT, "tools", "fr_rollcalls.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._frmod = mod
        return self._frmod

    def taxonomy(self):
        if self._tax is None:
            fr = self._fr()
            tax = filt.load_taxonomy(fr.taxonomy_path(), country=fr.TAXONOMY_COUNTRY)
            self._tax = (tax, fr.empty_watchlist(), fr.mask)
        return self._tax

    def candidates(self, conn):
        rows = [dict(zip(("key", "date", "title", "areas", "dossier_ref"), r)) for r in conn.execute(
            "SELECT division_key, date, title, areas, dossier_ref FROM fr_divisions "
            "WHERE chamber='an' AND (title LIKE 'l''amendement%' OR title LIKE 'le sous-amendement%' "
            "OR title LIKE 'les amendements%' OR title LIKE 'l’amendement%') ORDER BY date DESC, number DESC")]
        if any(not r["dossier_ref"] for r in rows):
            # The budget bills' texts are filed in several dossiers, so the
            # collector left those scrutins unjoined; the dossiers carrying
            # the text the title names narrow the search (the AN's own titles).
            fr = self._fr()
            dossiers = {}
            for ref, title, docs in conn.execute("SELECT dossier_ref, title, doc_titles FROM fr_dossiers"):
                try:
                    doc_titles = json.loads(docs or "[]")
                except ValueError:
                    doc_titles = []
                dossiers[ref] = {"title": title, "doc_titles": doc_titles}
            index = fr.title_index(dossiers)
            for r in rows:
                if not r["dossier_ref"]:
                    name = fr.text_name(r["title"] or "")
                    r["dossier_refs"] = sorted(index.get(name) or []) if name else []
        return rows

    def refs(self, row):
        return refs_of(row.get("title"))

    def fetch(self, row, refs):
        try:
            index = self.zip.index()
        except Exception as exc:                        # noqa: BLE001 - fail loud
            return amendtext.unreadable(refs, "the Assemblee's amendment zip unavailable: {0}".format(str(exc)[:140]))
        kind, num = refs[0].split(" ", 1)
        date = (row.get("date") or "")[:10]
        days = {date}
        try:
            days.add((datetime.date.fromisoformat(date) + datetime.timedelta(days=1)).isoformat())
        except ValueError:
            return amendtext.unreadable(refs, "the scrutin has no date")
        dossier = row.get("dossier_ref")
        if dossier:
            pool, where = index.get((dossier, num), []), "dossier {0}".format(dossier)
        elif row.get("dossier_refs"):
            pool = [h for d in row["dossier_refs"] for h in index.get((d, num), [])]
            where = "the dossiers carrying the text the title names ({0})".format(", ".join(row["dossier_refs"]))
        else:
            pool, where = index.get((None, num), []), "any dossier (the scrutin names none)"
        if not pool:
            return amendtext.unreadable(refs, "no seance {0} n° {1} in {2}".format(kind, num, where))
        if len(pool) > (MAX_POOL_LOCAL if self.zip.local else MAX_POOL):
            return amendtext.unreadable(refs, "{0} seance amendments numbered {1} in {2}: too many to "
                                              "read for one vote".format(len(pool), num, where))
        members = []
        for name, off, csize in pool:
            try:
                members.append(self.zip.member(name, off, csize))
            except Exception as exc:                    # noqa: BLE001
                return amendtext.unreadable(refs, "{0}: {1}".format(name.rsplit("/", 1)[-1], str(exc)[:120]))
        hits, how = choose(members, row.get("title"), date)
        if len(hits) != 1:
            return amendtext.unreadable(refs, "{0} seance {1}(s) n° {2} in {3} {4} {5}".format(
                len(hits), kind, num, where, how, date))
        m = hits[0]
        url = PUBLIC_URL.format(leg=LEGISLATURE, texte=_texte_number(m["texte"]) or "", numero=m["numero"])
        purpose = " ".join(x for x in (_opening(m["expose"], PURPOSE_EXPOSE),
                                       _opening(m["dispositif"], PURPOSE_DISPOSITIF)) if x)
        text = "{0}\n{1}\nExposé sommaire: {2}".format(m["article"] or "", m["dispositif"], m["expose"]).strip()
        return amendtext.Lookup("ok", refs=refs + [m["uid"]], texts=[amendtext.entry(
            "{0} n° {1}".format(kind, num), kind, m["uid"], url, purpose, text)])


def make_reader(client):
    return FranceReader(client)
