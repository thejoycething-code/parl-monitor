"""Portugal: the proposta de alteração a plenary vote puts (16 October 2026).

src/amendtext.py is the design; this is the Assembleia da República's source
and identifiers.

THE GAP, MEASURED SMALL. Amendments are voted in committee; the plenary votes
one only when it is called up (avocação) or the text is voted article by
article. In the XVII legislature that is 69 votes on 13 initiatives (store sha
12dfcd342515), described as "Proposta de alteração do PSD - Substituição do
artigo 6.º" or "Proposta de alteração, apresentada pelo PS, que substitui o
n.º 2 do artigo 2.º do texto final". Votes on the text's own articles
("Artigo 1.º do texto final", "Artigo 2.º - Votação requerida pelo PS") are
the bill's words, not an amendment, and are not read.

THE SOURCE. The Assembleia's open data, the same Iniciativas<LEG> dump
tools/pt_rollcalls.py reads (found through the Dados Abertos pages each run;
downloaded here only when a vote is still unread). Each event of an
initiative lists its annexes (AnexosFase): name and file on
app.parlamento.pt ("Proposta de Alteração PSD", "Propostas de Alteração PS
(aditamento)"). The file URLs are printed with http://; they are fetched over
https on the same host and path (src/http's rule: https only).

THE LINK, by the Assembleia's own identifiers: the initiative key and vote id
the vote was recorded under (pt_divisions.ini_key, vote_id) -> the event that
holds that vote, and its date -> the annexes of that initiative's events dated
on or before it named as proposals of the party the vote description names.
One such annex is read; several (a party's proposals and its "aditamento"
paper) are each read and the one naming the article the description names is
kept; none, or no way to choose, is a gap.

THE PURPOSE for the ledger gate: the passage of the proposals paper on the
article the description names ("artigo 6.º"), from that designation on, at
most PURPOSE_CHARS. A paper with no such passage gives no purpose: its text
is matched for review, never for the ledger. A party's paper holds all its
proposals on the bill, so the rest of it is body, not this vote's purpose.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re

from src import amendtext, filter as filt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = "pt-amendment-text"

_PROPOSAL = re.compile(r"\bPropostas?(?:\s+de\s+(?:alteração|aditamento|substituição|eliminação))?"
                       r"(?:,\s*apresentada\s+pel[oa]s?|\s+d[oa]s?|\s+apresentada\s+pel[oa]s?)\s+"
                       r"(?P<party>[A-Z][A-Za-z/-]{0,8})\b")
_ARTICLE = re.compile(r"\bartigo\s+(?P<art>\d+\.?\s*[º°o]?(?:\s*-\s*[A-Z])?)", re.I)


def _norm_art(text):
    m = re.match(r"(\d+)\.?\s*[º°o]?(?:\s*-\s*([A-Z]))?", (text or "").strip(), re.I)
    return (m.group(1) + ("-" + m.group(2).upper() if m.group(2) else "")) if m else None


def refs_of(row):
    """[ini_key, 'vote <id>', party, article] for a vote on a party's proposal, else []."""
    desc = " ".join((row.get("description") or "").split())
    m = _PROPOSAL.search(desc)
    if not m or not row.get("ini_key"):
        return []
    art = _ARTICLE.search(desc[m.end():]) or _ARTICLE.search(desc)
    return [row["ini_key"], "vote {0}".format(row.get("vote_id")), m.group("party"),
            _norm_art(art.group("art")) if art else ""]


def https(url):
    return re.sub(r"^http://app\.parlamento\.pt/", "https://app.parlamento.pt/", url or "")


def article_passage(text, art, n=amendtext.PURPOSE_CHARS):
    """The passage of a proposals paper from the first mention of article `art` ('6', '2-A')."""
    if not art:
        return ""
    num, _, letter = art.partition("-")
    # "2.º", "2º", "2." and nothing more: never the "2" of "2.º-A" or of "21.º"
    pat = r"\bartigo\s+{0}(?:\.?\s*[º°o]\.?|\.)?(?![º°o\d.]){1}".format(
        num, r"\s*-\s*" + letter if letter else r"(?!\s*-\s*[A-Z])")
    m = re.search(pat, text or "", re.I)
    return " ".join(text[m.start():m.start() + n].split()) if m else ""


class PortugalReader(amendtext.Reader):
    cc, table, key_col = "pt", "pt_divisions", "division_key"
    version = "2"     # 2: the article passage never stops at "2" of "2.º-A"

    def __init__(self, client, records=None):
        self.client = client
        self._records = records          # {ini_key: record} once loaded
        self._mod = None
        self._tax = None

    def _pt(self):
        if self._mod is None:
            spec = importlib.util.spec_from_file_location("pt_rollcalls_for_amendtext",
                                                          os.path.join(ROOT, "tools", "pt_rollcalls.py"))
            self._mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self._mod)
        return self._mod

    def taxonomy(self):
        if self._tax is None:
            pt = self._pt()
            self._tax = (filt.load_taxonomy(pt.taxonomy_path(), country=pt.TAXONOMY_COUNTRY),
                         pt.empty_watchlist(), None)
        return self._tax

    def candidates(self, conn):
        rows = conn.execute("SELECT division_key, vote_id, legislature, ini_key, date, phase, description, areas "
                            "FROM pt_divisions WHERE description LIKE '%Proposta%' ORDER BY date DESC, vote_id DESC")
        out = []
        for r in rows:
            d = dict(zip(("key", "vote_id", "legislature", "ini_key", "date", "phase", "description", "areas"), r))
            d["title"] = "{0}: {1}".format(d["phase"] or "", d["description"] or "")
            out.append(d)
        return out

    def refs(self, row):
        return refs_of(row)

    def _initiatives(self, legislature):
        if self._records is None:
            pt = self._pt()
            data = pt.fetch_dataset(self.client, "initiatives", legislature)
            self._records = {}
            for rec in data or []:
                if rec.get("IniLeg") and rec.get("IniTipo") and rec.get("IniNr"):
                    self._records[pt.ini_key(rec["IniLeg"], rec["IniTipo"], rec["IniNr"])] = rec
        return self._records

    def fetch(self, row, refs):
        ini, vote, party, art = refs[0], int(refs[1].split()[1]), refs[2], refs[3]
        try:
            rec = self._initiatives(row.get("legislature") or ini.split("/")[0]).get(ini)
        except Exception as exc:                        # noqa: BLE001 - fail loud
            return amendtext.unreadable(refs, "the Assembleia's Iniciativas dump: {0}".format(str(exc)[:140]))
        if rec is None:
            return amendtext.unreadable(refs, "initiative {0} not in the dump".format(ini))
        events = rec.get("IniEventos") or []
        held = [e for e in events if any(str(v.get("id")) == str(vote) for v in
                                         (e.get("Votacao") if isinstance(e.get("Votacao"), list)
                                          else [e.get("Votacao") or {}]))]
        if len(held) != 1:
            return amendtext.unreadable(refs, "vote {0} found in {1} events of {2}".format(vote, len(held), ini))
        day = (held[0].get("DataFase") or "")[:10]
        # A party's proposals are printed in a paper named for them, or in its
        # request to call them up to the plenary ("Requerimento de Avocação
        # do PS"); a text voted jointly may file them under another of the
        # joint initiatives, which the event names (IniciativasConjuntas).
        name = re.compile(r"(?:\bpropostas?\s+de\s+(?:alteração|aditamento|substituição)\b.*|"
                          r"\brequerimento\s+(?:de\s+)?avocação\s+(?:d[oa]s?\s+)?){0}\b".format(
                              re.escape(party)), re.I)
        pool = [rec]
        by_id = {str(r.get("IniId")): r for r in (self._records or {}).values()}
        for j in held[0].get("IniciativasConjuntas") or []:
            other = by_id.get(str(j.get("id")))
            if other is not None and other is not rec:
                pool.append(other)
        annexes = [(e.get("DataFase"), a) for r in pool for e in (r.get("IniEventos") or [])
                   if (e.get("DataFase") or "")[:10] <= day
                   for a in (e.get("AnexosFase") or []) if name.search(a.get("anexoNome") or "")]
        if not annexes:
            return amendtext.unreadable(refs, "no proposals paper of the {0} among the annexes of {1}{2} by "
                                              "{3}".format(party, ini, " and its joint initiatives" if len(pool) > 1
                                                           else "", day))
        read, blank = [], []
        for when, a in annexes:
            url = https(a.get("anexoFich"))
            try:
                raw = self.client.get_bytes(url, FEED, "annex-{0}".format(a.get("anexoNome")), archive=False)
                from src.amendtext_nl import document_text
                text = document_text(raw)
            except Exception as exc:                    # noqa: BLE001
                return amendtext.unreadable(refs, "annex '{0}' of {1}: {2}".format(a.get("anexoNome"), ini,
                                                                                 str(exc)[:120]))
            if not text.strip():
                blank.append(a.get("anexoNome"))       # a scanned paper: no text layer, not OCRed here
                continue
            read.append((a.get("anexoNome"), url, text, article_passage(text, art)))
        if not read:
            return amendtext.unreadable(refs, "the {0}'s proposals paper(s) on {1} are image-only PDFs ({2})".format(
                party, ini, "; ".join(blank)))
        if blank and not any(x[3] for x in read):
            return amendtext.unreadable(refs, "article {0} is in none of the readable papers; {1} image-only "
                                              "({2})".format(art or "?", len(blank), "; ".join(blank)))
        if len(read) > 1:
            named = [x for x in read if x[3]]
            if len(named) != 1:
                return amendtext.unreadable(refs, "{0} proposals papers of the {1} on {2} ({3}); {4} name article "
                                                  "{5}".format(len(read), party, ini, "; ".join(x[0] for x in read),
                                                               len(named), art or "?"))
            read = named
        nm, url, text, purpose = read[0]
        return amendtext.Lookup("ok", refs=refs, texts=[amendtext.entry(
            "{0} (artigo {1})".format(nm, art or "?"), "proposta de alteração", url, url, purpose, text)])


def make_reader(client):
    return PortugalReader(client)
