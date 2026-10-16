"""Italy (Camera): the amendment, order of the day, motion or resolution a
vote names (16 October 2026).

src/amendtext.py is the design; this is the Camera dei deputati's source and
identifiers. (The Senate's amendment texts are read from its own GitHub
repository by tools/it_senato_amendments.py into it_senate_amendments; Senate
votes linked there are matched here from the store, with no network.)

THE GAP. Camera votes are titled by the item put, not what it says:
"Emendamento 7-bis.1 ORRICO ANNA LAURA (M5S) - Votazione Emendamento 7-bis.1
DDL n. 2662", "Ordine del giorno n. 9/1866/11 BONETTI ELENA ...", "Mozione n.
1-00517 BOSCHI ...", "Risoluzione n. 6-00213 ...". 3,788 of the Camera's
3,912 amendment votes carried no area (store sha 12dfcd342515).

THE SOURCE. The Camera prints every amendment, order of the day, motion and
resolution put to the Assembly in the Allegato A to the sitting's record, on
documenti.camera.it (robots.txt allows it; aic.camera.it and
banchedati.camera.it disallow us and are not used; dati.camera.it's SPARQL
carries no texts and answered 502 on 16 October 2026):

    https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0554/allegato_a.htm

and marks each with the Camera's own identifier in the HTML:

    <p id="eme.1.28._1.29._ac.2662">   amendments 1.28 and 1.29 (identical) to A.C. 2662
    <div id="si.9_ac.2662_1">          order of the day 9/2662/1
    <div id="si.1-00517">              motion 1-00517 (".mod.v1": as reformulated)
    <div id="si.6-00213">              resolution 6-00213

THE LINK: the vote's sitting (its key, camera-vs19_<sitting>_<n>) and the
identifiers its title names (amendment number + A.C. number, ODG
9/<act>/<n>, motion 1-<n>, resolution 6-<n>). The texts of a bill's
amendments are printed in the Allegato A of the sitting where its examination
in the Assembly began, so the vote's own sitting is read first and then the
earlier ones, back at most LOOKBACK sittings; the first that carries the
identifier is used. A reformulated text (".mod.vN") printed in the same
Allegato A is preferred, highest N first. No identifier found in that window
is a gap. A vote on a part ("limitatamente al capoverso terzo", "premessa",
"dispositivo") is linked to the whole text, said so in the label; which
words the part was is never guessed.

THE PURPOSE for the ledger gate: an order of the day, motion or resolution
commits the Government in its operative part, "impegna il Governo ..." to the
end; the premises ("premesso che ...") are context. An amendment is short
operative text, and its opening is its purpose.
"""

from __future__ import annotations

import html
import json
import os
import re

from src import amendtext, filter as filt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGISLATURE = 19
ALLEGATO = "https://documenti.camera.it/leg{leg}/resoconti/assemblea/html/sed{sed:04d}/allegato_a.htm"
FEED = "it-amendment-text"
LOOKBACK = 25            # earlier sittings searched for a bill's amendment texts
PURPOSE_AMENDMENT = 350

_KEY = re.compile(r"^camera-vs(?P<leg>\d+)_(?P<sed>\d+)_\d+$")
_DDL = re.compile(r"\b(?:DDL|PDL|DOC|C\.)\s*n\.?\s*0*(?P<n>\d+)", re.I)
_AMD_NUM = r"\d+(?:-[a-z]+)*(?:\.\d+(?:-[a-z]+)*)+"
_AMEND = re.compile(r"^(?:Identici\s+)?(?:emendament[oi]|articol[oi]\s+aggiuntiv[oi]|subemendament[oi])\s+"
                    r"(?:n\.\s*)?(?P<num>{0})".format(_AMD_NUM), re.I)
_ODG = re.compile(r"^Ordine del giorno n\.\s*9/0*(?P<act>\d+)[^/]*/(?P<n>\d+)", re.I)
_ATTO = re.compile(r"^(?P<kind>Mozione|Risoluzione) n\.\s*(?P<num>[16]-\d{5})", re.I)
_ATTO_SHORT = re.compile(r"^(?P<kind>MOZ|RIS)\.?\s+(?P<t>[16])-0*(?P<n>\d{1,5})\b", re.I)
_PART = re.compile(r"limitatamente\s+[^-]+?(?=\s+[A-Z' ]{3,}\s*\(|\s+-\s+Votazione|$)|"
                   r",\s*(?:premessa|dispositivo)\b", re.I)
_IMPEGNA = re.compile(r"\bimpegna(?:no)?\s+il\s+Governo\b", re.I)


def refs_of(title, key):
    """The Camera identifiers a vote names: ['seduta 554', 'eme 7-bis.1 ac 2662'] etc., or []."""
    m = _KEY.match(key or "")
    if not m or int(m.group("leg")) != LEGISLATURE:
        return []
    t = " ".join((title or "").split())
    sed = "seduta {0}".format(int(m.group("sed")))
    a = _AMEND.match(t)
    if a:
        ddl = _DDL.search(t)
        return [sed, "eme {0} ac {1}".format(a.group("num").lower(), int(ddl.group("n")))] if ddl else []
    o = _ODG.match(t)
    if o:
        return [sed, "odg 9/{0}/{1}".format(int(o.group("act")), int(o.group("n")))]
    s = _ATTO.match(t)
    if s:
        return [sed, "{0} {1}".format(s.group("kind").lower(), s.group("num"))]
    s = _ATTO_SHORT.match(t)
    if s:
        kind = "mozione" if s.group("kind").upper() == "MOZ" else "risoluzione"
        return [sed, "{0} {1}-{2:05d}".format(kind, s.group("t"), int(s.group("n")))]
    return []


_ORD = ("primo secondo terzo quarto quinto sesto settimo ottavo nono decimo undicesimo dodicesimo "
        "tredicesimo quattordicesimo quindicesimo sedicesimo diciassettesimo diciottesimo "
        "diciannovesimo ventesimo").split()
_ORD += ["vent" + x for x in "unesimo iduesimo itreesimo iquattresimo icinquesimo iseiesimo isettesimo "
         "ottesimo inovesimo".split()] + ["trentesimo"]
ORDINALS = {w: i + 1 for i, w in enumerate(_ORD)}
_NUMS = r"(?:\d+|{0})(?:\s*(?:,|e)\s*(?:\d+|{0}))*".format("|".join(sorted(ORDINALS, key=len, reverse=True)))
_ITEMS = re.compile(r"\b(?:CPV|capovers[oi]|IMP|impegn[oi])\s+(?P<nums>{0})".format(_NUMS), re.I)
_EXCEPT = re.compile(r"\b(?:ad\s+eccezion[ei]|eccetto|NO)\b", re.I)
_PREMISE = re.compile(r"\bpremess[ae]\b", re.I)
_DISPOSITIVE = re.compile(r"\b(?:dispositiv[oa]|impegn[oi]|IMP|CPV|capovers[oi])\b", re.I)


def vote_part(title):
    """What part of a motion or resolution a vote put: ('whole', []), ('premise', []),
    ('items', [n, ...]) or ('except', [n, ...]), from the Camera's own wording:
    "limitatamente al capoverso terzo della parte dispositiva", "MOZ 1-593 CPV 4,
    5, 16, 18", "RIS 6-254 NO IMP 3, 4 E PREMESSE", "RIS 6-285, PREMESSA"."""
    t = " ".join((title or "").split())
    head = t.split(" - Votazione")[0]
    m = _ITEMS.search(head)
    nums = []
    if m:
        for x in re.split(r"\s*(?:,|\be\b)\s*", m.group("nums")):
            x = x.strip().lower()
            if x.isdigit():
                nums.append(int(x))
            elif x in ORDINALS:
                nums.append(ORDINALS[x])
    if nums:
        how = "except" if _EXCEPT.search(head[:m.start()][-40:]) else "items"
        if re.match(r"\W*(?:della|delle|dalla|dalle)\s+premess", head[m.end():], re.I):
            # paragraphs of the PREMISES: a vote on them is on context only;
            # all but some of them leaves the operative part whole, unless the
            # vote was limited to the premises as well
            if how == "items" or re.search(r"limitatamente\s+alla\s+premessa", head, re.I):
                return "premise", []
            return "whole", []
        if re.search(r"limitatamente\s+alla\s+premessa", head, re.I):
            return "premise", []
        return how, nums
    if _PREMISE.search(head) and not _DISPOSITIVE.search(head):
        return "premise", []
    return "whole", []


_ITEM_NO = re.compile(r"(?:(?<=\s)|(?<=:)|^)(\d{1,2})\)\s")


def capoversi(operative_text):
    """{n: paragraph} of an operative part whose commitments are unnumbered
    paragraphs, after the "impegna il Governo" line and before the signature."""
    lines = [l for l in (operative_text or "").split("\n")[1:] if l.strip()]
    lines = [l for l in lines if not re.match(r"^\((?:\d|[16]-\d)", l.strip())]
    return {i + 1: l for i, l in enumerate(lines)}


def operative_items(operative_text):
    """{n: text} of the numbered commitments "1) a ...; 2) a ..."."""
    marks = [(int(m.group(1)), m.start()) for m in _ITEM_NO.finditer(operative_text or "")]
    out = {}
    for i, (n, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(operative_text)
        out.setdefault(n, operative_text[pos:end].strip())
    return out


def _plain(fragment):
    text = re.sub(r"<\s*(?:br|/p)\s*/?>", "\n", fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    return "\n".join(" ".join(p.split()) for p in text.splitlines() if p.strip())


_BOUND = re.compile(r"<p\s+id=\"|<p\s+class=\"(?:center|tipologia|titoloSezione|sottoTitolo)|<div\b|</div>", re.I)


def parse_allegato(page):
    """{identifier: text} for the amendments ('eme <num> ac <n>', one per number
    in an identical group) and the 'si' items ('si.9_ac.2662_1', 'si.1-00517',
    with '.mod.vN' kept) of one Allegato A page."""
    out = {}
    for m in re.finditer(r"<p\s+id=\"eme\.(?P<ids>[^\"]+?)_ac\.0*(?P<ac>\d+)(?:-[A-Za-z0-9-]+)?\"", page):
        end = _BOUND.search(page, m.end())
        body = _plain(page[m.start():end.start() if end else len(page)])
        nums = [x.strip(".").lower() for x in m.group("ids").split("._") if x.strip(".")]
        for n in nums:
            out.setdefault("eme {0} ac {1}".format(n, int(m.group("ac"))), body)
    for m in re.finditer(r"<div\s+id=\"(?P<id>si\.[^\"]+)\"[^>]*>", page):
        end = page.find("</div>", m.end())
        out[m.group("id")] = _plain(page[m.end():end if end >= 0 else len(page)])
    return out


def _si_ids(ref):
    """The div id a 'si' reference is printed under, as a regex."""
    if ref.startswith("odg "):
        act, n = ref[4:].split("/")[1:]
        return re.compile(r"^si\.9_ac\.0*{0}(?:[-_][a-z0-9]+)*_{1}(?:\.mod\.v(\d+))?$".format(act, n), re.I)
    num = ref.split(" ", 1)[1]
    return re.compile(r"^si\.{0}(?:\.mod\.v(\d+))?$".format(re.escape(num)), re.I)


def operative(text):
    m = _IMPEGNA.search(text or "")
    return text[m.start():].strip() if m else ""


class ItalyReader(amendtext.Reader):
    cc, table, key_col = "it", "it_divisions", "division_key"
    version = "4"     # 2: premises / named commitments only; 3: capoversi; 4: capoversi of the premises

    def __init__(self, client):
        self.client = client
        self._tax = None
        self._pages = {}

    def taxonomy(self):
        if self._tax is None:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "it_rollcalls_for_amendtext", os.path.join(ROOT, "tools", "it_rollcalls.py"))
            it = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(it)
            self._tax = (filt.load_taxonomy(it.taxonomy_path(), country=it.TAXONOMY_COUNTRY),
                         it.empty_watchlist(), None)
        return self._tax

    def candidates(self, conn):
        rows = conn.execute(
            "SELECT division_key, date, title, areas FROM it_divisions WHERE chamber='camera' AND "
            "(title LIKE 'Emendament%' OR title LIKE 'Identici%' OR title LIKE 'Articol_ aggiuntiv%' "
            "OR title LIKE 'Subemendament%' OR title LIKE 'Ordine del giorno n.%' "
            "OR title LIKE 'Mozione n.%' OR title LIKE 'Risoluzione n.%' OR title LIKE 'MOZ %' "
            "OR title LIKE 'RIS %') ORDER BY date, division_key")
        return [dict(zip(("key", "date", "title", "areas"), r)) for r in rows]

    def refs(self, row):
        return refs_of(row.get("title"), row.get("key"))

    def _page(self, sed):
        if sed not in self._pages:
            url = ALLEGATO.format(leg=LEGISLATURE, sed=sed)
            try:
                raw = self.client.get_bytes(url, FEED, "allegato-a-{0}".format(sed), archive=False)
                self._pages[sed] = parse_allegato(raw.decode("utf-8", "replace"))
            except Exception as exc:                    # noqa: BLE001 - a missing sitting is not fatal
                if "404" in str(exc):
                    self._pages[sed] = {}
                else:
                    raise
        return self._pages[sed]

    def fetch(self, row, refs):
        sed = int(refs[0].split()[1])
        ref = refs[1]
        found = None
        try:
            for s in range(sed, max(0, sed - LOOKBACK), -1):
                page = self._page(s)
                if ref.startswith("eme "):
                    if ref in page:
                        found = (s, ref, page[ref], [(ref, page[ref])])
                else:
                    pat = _si_ids(ref)
                    hits = sorted(((int((pat.match(k).group(1) or 0)), k) for k in page if pat.match(k)),
                                  reverse=True)
                    if hits:
                        found = (s, hits[0][1], page[hits[0][1]], [(k, page[k]) for _, k in hits])
                if found:
                    break
        except Exception as exc:                        # noqa: BLE001 - fail loud
            return amendtext.unreadable(refs, "Allegato A unavailable: {0}".format(str(exc)[:140]))
        if not found:
            return amendtext.unreadable(refs, "{0} not printed in the Allegato A of sittings {1} to {2}".format(
                ref, max(1, sed - LOOKBACK + 1), sed))
        s, ident, text, versions = found
        part = _PART.search(row.get("title") or "")
        label = ref + (" (part put to the vote: '{0}'; whole text read)".format(part.group(0).strip(" ,"))
                       if part else "")
        limit = amendtext.PURPOSE_CHARS
        if ref.startswith("eme "):
            kind = "amendment"
            purpose = text[:PURPOSE_AMENDMENT]
        else:
            kind = ref.split()[0]
            purpose, limit = operative(text), amendtext.OPERATIVE_CHARS
            how, nums = vote_part(row.get("title"))
            if how != "whole":
                label = "{0} (vote on {1}{2}; whole text read)".format(
                    ref, {"premise": "the premises", "items": "commitment(s) ",
                          "except": "all but commitment(s) "}[how], ", ".join(str(n) for n in nums))
            if how == "premise":
                purpose = ""              # the premises are context: no ledger on them alone
            elif how in ("items", "except"):
                # The commitments are numbered "1) ..." or are the operative
                # part's paragraphs (capoversi). A reformulated text printed
                # after the vote may have dropped the ones voted on, so the
                # newest version that has them all is used.
                chosen = None
                for vid, vtext in versions:
                    op = operative(vtext)
                    for items in (operative_items(op), capoversi(op)):
                        if all(n in items for n in nums):
                            chosen = (vid, vtext, items)
                            break
                    if chosen:
                        break
                if chosen is None:
                    return amendtext.unreadable(refs, "{0}: commitment(s) {1} not found in the operative part of "
                                                      "any printed version ({2})".format(
                                                          ref, ", ".join(str(n) for n in nums),
                                                          ", ".join(v for v, _ in versions)))
                ident, text, items = chosen
                purpose = " ".join(items[n] for n in sorted(items) if (n in nums) == (how == "items"))
        url = ALLEGATO.format(leg=LEGISLATURE, sed=s) + "#" + ident
        return amendtext.Lookup("ok", refs=refs + [ident], texts=[amendtext.entry(
            label, kind, ident, url, purpose, text, purpose_chars=limit)])


def make_reader(client):
    return ItalyReader(client)
