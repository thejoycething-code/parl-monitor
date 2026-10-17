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

THE PURPOSE for the ledger gate is the OPERATIVE part (17 October 2026,
Chris): what the House is asked to decide, never the premises.

  * An order of the day, motion or resolution: from the line that opens the
    dispositive part to the signature, WHOLE. The Allegato A prints that
    opening on a line of its own after "La Camera, premesso che: ...":
    "impegna il Governo:", "impegna il Governo a:", "impegna il Governo"
    + "a valutare l'opportunità di ...", "impegnano il Governo", "impegna
    altresì il Governo", "impegna il Governo e il Ministro ...", "invita il
    Governo", "delibera", and a missions resolution's "autorizza" / "non
    autorizza". Only a LINE that opens with one counts: a premise citing
    another motion "che impegna il Governo alla stabilizzazione" mid-line is
    not the operative part (598_004). With no such line, the last mid-text
    "impegna il Governo" is used. The premises stay in the body as context:
    a tier-1 term there is review only.
    Version 4 clipped this purpose at 3,000 characters, so a commitment past
    it (motion 1-00545's "legge n. 194 del 1978", 5,400 characters into its
    operative part; 1-00526's, 4,000) never reached the gate. Now the whole
    operative part does (at most amendtext.TEXT_CHARS).
  * A vote on some commitments only reads those (vote_part); a vote on the
    premises reads none; a vote on "la premessa della parte dispositiva"
    reads only the opening line(s) before the first commitment.
  * An amendment: its whole operative text ("sostituire ...", "sopprimere
    ...", "aggiungere il seguente: ..."), up to its signature line ("1.30.
    Dori, Borrelli.") and without the financial-cover sentence ("Agli oneri
    derivanti ... si provvede ..."), which names the fund cut, not what the
    amendment is for.
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
PURPOSE_CHARS = amendtext.TEXT_CHARS   # a whole operative part (or amendment) is the purpose

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
_OPENS = re.compile(
    r"^(?:(?:e|ed)\s+)?(?:"
    r"(?:impegna(?:no)?|invita(?:no)?)(?:\s*,?\s*(?:altres[iì]|inoltre|pertanto|quindi|conseguentemente)\s*,?)?"
    r"\s+(?:il\s+Governo|l['’]\s*Esecutivo|il\s+Presidente\s+del\s+Consiglio)\b"
    r"|delibera\b|(?:non\s+)?autorizza\b)", re.I | re.M)
_SIGNED = re.compile(r"^(?:\((?:[16]-\d{3,5}|\d+/)|9/\d)", re.M)     # "(1-00191)(Nuova ...", "9/1866-A/2. L'Abbate."


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
        "diciannovesimo").split()
for _tens in ("vent", "trent", "quarant", "cinquant"):           # ventesimo ... cinquantanovesimo
    _v = "i" if _tens == "vent" else "a"
    _ORD += [_tens + "esimo"]
    _ORD += [_tens + x for x in ("unesimo", _v + "duesimo", _v + "treesimo", _v + "quattresimo", _v + "cinquesimo",
                                 _v + "seiesimo", _v + "settesimo", "ottesimo", _v + "novesimo")]
_ORD += ["sessantesimo"]
ORDINALS = {w: i + 1 for i, w in enumerate(_ORD)}
_NUM = r"(?:\d+(?:\s*-\s*\d+)?|{0})".format("|".join(sorted(ORDINALS, key=len, reverse=True)))
_NUMS = r"{0}(?:\s*(?:,|e)\s*{0})*".format(_NUM)
_ITEMS = re.compile(r"\b(?:CPV|capovers[oi]|IMP|impegn[oi])\s*(?:nn?\.\s*)?(?P<nums>{0})".format(_NUMS), re.I)
_ORDS = r"(?:{0})".format("|".join(sorted(ORDINALS, key=len, reverse=True)))
_ITEMS_AFTER = re.compile(r"\b(?P<nums>{0}(?:\s*(?:,|e)\s*{0})*)\s+(?:capovers[oi]|impegn[oi])\b".format(_ORDS), re.I)
_EXCEPT = re.compile(r"\b(?:ad\s+eccezion[ei]|eccetto|NO)\b", re.I)
_PREMISE = re.compile(r"\bpremess[ae]\b", re.I)
# a part the title names but the Allegato A does not number: a missions
# resolution's "IMP AGG SCHEDA 3" (the added commitment on mission 3) or "DISP
# AFRICA 22", "PARTE NON PRECLUSA", "CPV PREM E DISP" (unnumbered paragraphs),
# "la restante parte" (the complement of another part vote)
_UNLOCATED = re.compile(r"\bSCHED[AE]\b|\bIMP\s+AGG\b|\bDISP\s+(?:AFRICA|GDF|EUROPA|ASIA|AMERICA)\b|"
                        r"\bPARTE\s+NON\s+PRECLUSA\b|\bCPV\s+PREM|\brestante\s+parte\b", re.I)
# "PREM NO CPV 4, 5, 16 E 18": the premises, all but those paragraphs
_PREM_EXCEPT = re.compile(r"(?<!NO )\bPREM\w*\s+(?:NO|ad\s+eccezione)\b", re.I)
_ALINEA = re.compile(r"\bpremessa\s+(?:della|alla)\s+parte\s+dispositiva\b", re.I)
_DISPOSITIVE = re.compile(r"\b(?:dispositiv[oa]|impegn[oi]|IMP|CPV|capovers[oi])\b", re.I)


def vote_part(title):
    """What part of a motion or resolution a vote put: ('whole', []), ('premise', []),
    ('alinea', []), ('part', []) (named but not locatable: review only), ('items', [n, ...]) or ('except', [n, ...]), from the Camera's
    own wording: "limitatamente al capoverso terzo della parte dispositiva", "MOZ
    1-593 CPV 4, 5, 16, 18", "RIS 6-254 NO IMP 3, 4 E PREMESSE", "RIS 6-285,
    PREMESSA", "MOZ 1-526 RIF CPV 6 E 16 PREMESSA" (paragraphs of the premises),
    "sulla premessa della parte dispositiva" (the operative part's opening)."""
    t = " ".join((title or "").split())
    head = t.split(" - Votazione")[0]
    if _ALINEA.search(head):
        return "alinea", []
    if _UNLOCATED.search(head):
        return "part", []
    m = _ITEMS.search(head) or _ITEMS_AFTER.search(head)       # "CPV 4", "al ventunesimo capoverso"
    nums = []
    if m:
        for x in re.split(r"\s*(?:,|\be\b)\s*", m.group("nums"), flags=re.I):
            x = x.strip().lower()
            r = re.match(r"^(\d+)\s*-\s*(\d+)$", x)
            if r and int(r.group(1)) < int(r.group(2)) <= 60:
                nums.extend(range(int(r.group(1)), int(r.group(2)) + 1))
            elif x.isdigit():
                nums.append(int(x))
            elif x in ORDINALS:
                nums.append(ORDINALS[x])
    if nums:
        how = "except" if _EXCEPT.search(head[:m.start()][-40:]) else "items"
        if _PREM_EXCEPT.search(head[:m.start()]) and not re.match(r"\W*DIS", head[m.end():], re.I):
            return "premise", []
        if re.match(r"\W*(?:capovers\w*\s+)?(?:(?:della|delle|dalla|dalle)\s+)?(?:premess|P(?:REM\w*)?\b)",
                    head[m.end():], re.I):
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
    """The dispositive part of an order of the day, motion or resolution: from
    the line that opens it ("impegna il Governo:", "autorizza", ...) to the
    signature, or "" when there is none."""
    text = text or ""
    m = _OPENS.search(text)
    if m is None:
        mids = list(_IMPEGNA.finditer(text))
        if not mids:
            return ""
        m = mids[-1]               # the operative part comes last; an earlier one is a premise citing another text
    op = text[m.start():]
    end = _SIGNED.search(op)
    return (op[:end.start()] if end else op).strip()


def alinea(operative_text):
    """The opening of an operative part, before its first commitment: the
    lines up to "1)" when the commitments are numbered, else the first line."""
    lines = [l for l in (operative_text or "").split("\n") if l.strip()]
    if not lines:
        return ""
    out = [lines[0]]
    if operative_items(operative_text):
        for l in lines[1:]:
            if _ITEM_NO.match(l.strip()):
                break
            out.append(l)
    return "\n".join(out).strip()


_SIGNATURE = re.compile(r"^\*?\d+(?:-[a-z]+)*\.\s?0?\d+(?:-[a-z]+)*\.\s+\S", re.M)
_COVER = re.compile(r"(?:^|(?<=[.;:]\s))(?:Ai\s+|Agli\s+)(?:relativi\s+|maggiori\s+)?oneri\b[^\n]*?"
                    r"si\s+provvede\b[^\n]*?(?:\.(?=\s|$)|$)", re.I | re.M)


def amendment_operative(text):
    """An amendment's operative text: up to its signature line ("1.30. Dori,
    Borrelli."), without the financial-cover sentence."""
    text = text or ""
    end = _SIGNATURE.search(text)
    body = text[:end.start()] if end else text
    return _COVER.sub("", body).strip()


# FALSE FRIENDS in long Italian texts (17 October 2026). A whole operative
# part or amendment carries words a title never does; two tier-1 terms meet
# them in the stored Camera texts:
#   * "cittadinanza" (migration, tier 1, bare) for social citizenship: "favorire
#     il pieno sviluppo della persona, la cittadinanza, attraverso l'inclusione
#     sociale" (motion 1-00444 on the minimum wage), "reddito di cittadinanza",
#     "cittadinanza attiva / digitale". Masked in a text with no migration word.
#   * "silenzio-assenso" (organ donation, guarded by "organi") for the
#     administrative device: "si applica il meccanismo del silenzio-assenso"
#     to appointing an Agency's "organi" (amendment 1.64 to A.C. 2586).
#     Masked in a text with no donation or transplant word.
_CITIZEN_FF = re.compile(r"\b(?:reddito|pensione)\s+di\s+cittadinanza\b|"
                         r"\bcittadinanza\s+(?:attiva|digitale|scientifica|economica|sociale|consapevole|"
                         r"responsabile|onoraria|europea|democratica|globale|sanitaria)\b|"
                         r"\beducazione\s+(?:civica\s+e\s+)?alla\s+cittadinanza\b", re.I)
_MIGRATION = re.compile(r"stranier|migra|naturalizza|apolid|rifugiat|richiedent|\bius\s+(?:soli|scholae|culturae|"
                        r"sanguinis)\b|\b91\s+del\s+1992\b|91/1992|permess[oi]\s+di\s+soggiorno|"
                        r"cittadinanza\s+italiana|(?:domand|istanz|richiest|pratich|procediment)\w*\s+di\s+"
                        r"cittadinanza|cittadinanza\s+per\s+(?:matrimonio|residenza|discendenza|nascita)|(?:acquisto|concessione|conferimento|riconoscimento|revoca|"
                        r"perdita)\s+della\s+cittadinanza", re.I)
_CITIZEN = re.compile(r"\bcittadinanza\b", re.I)
_SILENZIO = re.compile(r"\bsilenzio[\s-]+assenso\b", re.I)
_DONATION = re.compile(r"donazion|donator|trapiant|espiant|prelievo\s+di\s+organi|organi\s+e\s+(?:di\s+)?tessuti", re.I)


def mask(text):
    """A text with the false friends above blanked, as the matcher sees it."""
    text = _CITIZEN_FF.sub(" ", text or "")
    if not _MIGRATION.search(text):
        text = _CITIZEN.sub(" ", text)
    if not _DONATION.search(text):
        text = _SILENZIO.sub(" ", text)
    return text


class ItalyReader(amendtext.Reader):
    cc, table, key_col = "it", "it_divisions", "division_key"
    version = "5"     # 2: premises / named commitments only; 3: capoversi; 4: capoversi of the premises;
                      # 5: the whole operative part (no 3,000-character clip), line-opening verbs, amendments' whole text

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
                         it.empty_watchlist(), mask)
        return self._tax

    def candidates(self, conn):
        rows = conn.execute(
            "SELECT division_key, date, title, areas FROM it_divisions WHERE chamber='camera' AND "
            "(title LIKE 'Emendament%' OR title LIKE 'Identici%' OR title LIKE 'Articol_ aggiuntiv%' "
            "OR title LIKE 'Subemendament%' OR title LIKE 'Ordine del giorno n.%' "
            "OR title LIKE 'Mozione n.%' OR title LIKE 'Risoluzione n.%' OR title LIKE 'MOZ %' "
            "OR title LIKE 'RIS %') ORDER BY date DESC, division_key DESC")
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
        limit = PURPOSE_CHARS
        if ref.startswith("eme "):
            kind = "amendment"
            purpose = amendment_operative(text)
        else:
            kind = ref.split()[0]
            purpose = operative(text)
            how, nums = vote_part(row.get("title"))
            if how != "whole":
                label = "{0} (vote on {1}{2}; whole text read)".format(
                    ref, {"premise": "the premises", "items": "commitment(s) ",
                          "except": "all but commitment(s) ",
                          "alinea": "the opening of the operative part",
                          "part": "a part not numbered in the text"}[how], ", ".join(str(n) for n in nums))
            if how in ("premise", "part"):
                purpose = ""              # the premises are context, and a part we cannot find is never guessed
            elif how == "alinea":
                purpose = alinea(purpose)
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
