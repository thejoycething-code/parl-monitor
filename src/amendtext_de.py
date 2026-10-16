"""Germany (Bundestag): the Drucksache a roll call is on (16 October 2026).

src/amendtext.py is the design; this is the Bundestag's source and
identifiers.

THE GAP. de_divisions holds abgeordnetenwatch's roll calls; their labels are
abgeordnetenwatch's own short headlines ("Bisherigen Umfang der
NIPT-Kassenleistung erhalten (Änderungsantrag)", "Einführung einer
Übergewinnsteuer"), and only 62 of the Bundestag's 596 polls without a kind
in the label, and none of its four "(Änderungsantrag)" polls, carried an area
(store sha 12dfcd342515). The words the House voted on are in the Drucksache.

THE SOURCE. DIP, the Bundestag's documentation system
(search.dip.bundestag.de/api/v1; src/dip.py: DIP_API_KEY, then
config/secrets.yaml, then the key the Bundestag prints in its own OpenAPI
spec, as every German tool here does). /drucksache gives a Drucksache's type,
title and Vorgang; /drucksache-text its full text. abgeordnetenwatch's API is
NOT read here: its robots.txt disallows /api/v2/, and Chris's 13 October 2026
exception covers only tools/de_rollcalls.py and tools/de_profiles.py
(docs/robots-runtime.md).

THE LINK, by the Bundestag's own identifiers:
  1. the Drucksache the poll names (de_divisions.document_url, which
     de_rollcalls took from the poll itself: dserver's path carries the
     number, /btd/21/038/2103873.pdf is 21/3873);
  2. when the label names a different kind of paper than that Drucksache is
     -- "(Änderungsantrag)" or "(Entschließungsantrag)" on a poll whose link
     is the Antrag or the bill (abgeordnetenwatch links the parent: poll 6727
     links 21/3873, the Antrag, and was a vote on its Änderungsantrag
     21/8475) -- the paper the House's own record says was put to the roll
     call: DIP's Vorgangsposition for that day's sitting on the linked
     paper's Vorgang lists each decision with its kind ("Namentliche
     Abstimmung"), tenor ("Annahme des Änderungsantrags") and Drucksache.
     Failing that record, the one paper of that kind of the same Vorgang
     dated in the three days before the vote. Anything else is a gap.

THE PURPOSE for the ledger gate: the Drucksache's DIP title (the House's own
heading) and its operative words, from "Der Bundestag wolle beschließen" (a
motion, an amendment, a resolution) or "A. Problem und Ziel" (a bill), at
most PURPOSE_OPERATIVE characters. The Begründung and a bill's articles are
body: a tax bill citing the Schwangerschaftskonfliktgesetz in a list is not
an abortion bill.

Polls with no paper linked (most before about 2019) are found in the same
record by date and their yes:no:abstain tally ("661:0:7"; within
TALLY_SLACK votes, since abgeordnetenwatch counts members' recorded votes and
the House a corrected list, and with the sides swapped for a recommendation
to reject a motion), clearly closer than any other roll call that day, or a
gap; the decision's first Drucksache (the
Vorlage) is read. DIP records no tallies before the 17th Wahlperiode, so the
55 polls of 2006-2009 with no paper linked are known unreadable and not tried.

Landtag polls (Bayern and the other Länder in de_divisions) are not read:
their papers are not in DIP, and each Land's own system is another source.
"""

from __future__ import annotations

import datetime
import os
import re

from src import amendtext, dip, filter as filt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = "de-amendment-text"
BUNDESTAG = "5"
PURPOSE_OPERATIVE = 600
WINDOW_DAYS = 3
# DIP records no roll-call tallies for the 16th Wahlperiode and before
# (measured 16 October 2026: none of the 55 such polls of 2006-2009 found),
# so polls before the 17th's first sitting with no paper linked are not read.
FIRST_TALLY_DAY = "2009-10-27"
TALLY_SLACK = 3

_DSERVER = re.compile(r"/btd/(?P<wp>\d{1,2})/\d{3}/(?P=wp)(?P<num>\d{5})\.pdf$")
_KIND = re.compile(r"\((Änderungsantrag|Entschließungsantrag)\)", re.I)
_OPERATIVE = re.compile(r"Der\s+Bundestag\s+wolle\s+beschlie(?:ß|ss)en\s*:?|A\.\s*Problem\s+und\s+Ziel", re.I)
_VORAB = re.compile(r"V\s*\n?\s*orabfassung\s*[–-]\s*w\s*\n?\s*ird durch die lektorierte Fassung ersetzt\.?", re.I)


def drucksache_of(url):
    """'21/3873' from a dserver PDF path, or None."""
    m = _DSERVER.search(url or "")
    return "{0}/{1}".format(int(m.group("wp")), int(m.group("num"))) if m else None


def clean(text):
    """DIP's text without the 'Vorabfassung' banner repeated on every page."""
    return _VORAB.sub(" ", text or "")


def purpose_of(title, text):
    m = _OPERATIVE.search(text or "")
    op = " ".join(text[m.end():m.end() + PURPOSE_OPERATIVE].split()) if m else ""
    return " ".join(x for x in (title or "", op) if x)


class GermanyReader(amendtext.Reader):
    cc, table, key_col = "de", "de_divisions", "vote_id"

    def __init__(self, client, key=None):
        self.client = client
        self._key = key
        self._tax = None
        self._meta = {}
        self._day = {}

    def taxonomy(self):
        if self._tax is None:
            tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
            wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))
            self._tax = (tax, wl, None)
        return self._tax

    def key(self):
        if self._key is None:
            self._key = dip.api_key(self.client, log=lambda *a: None) or ""
        return self._key

    def candidates(self, conn):
        rows = conn.execute("SELECT vote_id, date, label, areas, document_url, yes, no, abstain "
                            "FROM de_divisions WHERE parliament=? AND (document_url IS NOT NULL OR date >= ?) "
                            "ORDER BY date DESC, vote_id DESC", (BUNDESTAG, FIRST_TALLY_DAY))
        return [dict(zip(("key", "date", "title", "areas", "document_url", "yes", "no", "abstain"), r))
                for r in rows]

    def refs(self, row):
        ds = drucksache_of(row.get("document_url"))
        kind = _KIND.search(row.get("title") or "")
        if ds:
            return [ds] + ([kind.group(1)] if kind else [])
        if row.get("yes") is not None and row.get("no") is not None:
            # no paper linked (polls before about 2019): the roll call is
            # found in the House's record of that day by its own tally
            return ["tally {0}:{1}:{2}".format(row["yes"], row["no"], row.get("abstain") or 0)]
        return []

    def _drucksache(self, number):
        if number not in self._meta:
            docs = (self.client.get_json(dip.url("drucksache", self.key(), **{"f.dokumentnummer": number}),
                                         FEED, "ds-{0}".format(number.replace("/", "-")), archive=False)
                    or {}).get("documents") or []
            self._meta[number] = docs[0] if len(docs) == 1 else None
        return self._meta[number]

    def _of_kind_on(self, kind, start, end):
        k = (kind, start, end)
        if k not in self._day:
            out = []
            for page in dip.pages(self.client, "drucksache", self.key(), feed=FEED, slug="kind-{0}".format(start),
                                  limit_pages=10, log=lambda *a: None, **{"f.drucksachetyp": kind,
                                                                         "f.datum.start": start,
                                                                         "f.datum.end": end}):
                out.extend(page.get("documents") or [])
            self._day[k] = out
        return self._day[k]

    def _voted_paper(self, doc, kind, date, number):
        """(the paper of `kind` the roll call was on, None) or (None, why).

        First the House's own record: DIP's Vorgangspositionen of the linked
        paper's Vorgang list, for the plenary sitting of that day, each
        decision with its type ("Namentliche Abstimmung"), its tenor
        ("Annahme des Änderungsantrags") and the Drucksache decided. Failing
        that, the one paper of that kind of the same Vorgang dated in the
        three days before the vote."""
        vorgaenge = sorted({str(v.get("id")) for v in doc.get("vorgangsbezug") or []})
        stem = kind.lower()[:-1] if kind.lower().endswith("g") else kind.lower()
        voted = []
        for vid in vorgaenge:
            for page in dip.pages(self.client, "vorgangsposition", self.key(), feed=FEED,
                                  slug="vp-{0}".format(vid), limit_pages=5, log=lambda *a: None,
                                  **{"f.vorgang": vid}):
                for pos in page.get("documents") or []:
                    if (pos.get("datum") or "")[:10] != date:
                        continue
                    for b in pos.get("beschlussfassung") or []:
                        if "namentlich" not in (b.get("abstimmungsart") or "").lower():
                            continue
                        if stem not in (b.get("beschlusstenor") or "").lower():
                            continue
                        voted.extend(n.strip() for n in (b.get("dokumentnummer") or "").split(","))
        voted = sorted({n for n in voted if n and n != number})
        if len(voted) == 1:
            found = self._drucksache(voted[0])
            if found is not None and (found.get("drucksachetyp") or "").lower() == kind.lower():
                return found, None
        if len(voted) > 1:
            return None, "the House's record of {0} names {1} {2}s put to a roll call: {3}".format(
                date, len(voted), kind, ", ".join(voted))
        start = (datetime.date.fromisoformat(date) - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
        hits = [d for d in self._of_kind_on(kind, start, date)
                if set(vorgaenge) & {str(v.get("id")) for v in d.get("vorgangsbezug") or []}]
        if len(hits) == 1:
            return hits[0], None
        return None, "{0} {1}(s) of Vorgang {2} dated {3} to {4}, and no roll call on one in the House's record " \
                     "(the poll links {5}, a {6})".format(len(hits), kind, ", ".join(vorgaenge) or "?", start, date,
                                                           number, doc.get("drucksachetyp"))

    def _by_tally(self, tally, date):
        """(the Drucksache of the day's roll call with this yes:no:abstain tally, None) or (None, why).

        DIP's Vorgangspositionen of the day carry each decision's type and its
        official tally ("Namentliche Abstimmung", "661:0:7"); the poll's own
        counts must equal one of them exactly, once."""
        want = [int(x) for x in tally.split(":")]
        scored = {}
        for page in dip.pages(self.client, "vorgangsposition", self.key(), feed=FEED, slug="day-{0}".format(date),
                              limit_pages=20, log=lambda *a: None, **{"f.datum.start": date, "f.datum.end": date}):
            for pos in page.get("documents") or []:
                for b in pos.get("beschlussfassung") or []:
                    if "namentlich" not in (b.get("abstimmungsart") or "").lower():
                        continue
                    first = (b.get("dokumentnummer") or "").split(",")[0].strip()
                    for found in re.findall(r"(\d+):(\d+):(\d+)", b.get("abstimm_ergebnis_bemerkung") or ""):
                        y, n, a = (int(x) for x in found)
                        # a vote on a recommendation to REJECT a motion: the
                        # House counts Ayes for rejecting, abgeordnetenwatch
                        # for the motion, so the two sides swap
                        d = min(abs(y - want[0]) + abs(n - want[1]), abs(n - want[0]) + abs(y - want[1]))
                        d += abs(a - want[2])
                        if first and d < scored.get(first, 99):
                            scored[first] = d
        ranked = sorted(scored.items(), key=lambda kv: kv[1])
        # abgeordnetenwatch counts members' recorded votes and the House's
        # tally can differ by a corrected vote or two: the closest within
        # TALLY_SLACK, and clearly closer than any other roll call that day
        if ranked and ranked[0][1] <= TALLY_SLACK and (len(ranked) == 1 or ranked[1][1] > ranked[0][1] + 10):
            return ranked[0][0], None
        return None, "no roll call of {0} in the House's record within {1} votes of the tally {2}{3}".format(
            date, TALLY_SLACK, tally, " (closest: {0} off)".format(ranked[0][1]) if ranked else "")

    def fetch(self, row, refs):
        if not self.key():
            return amendtext.unreadable(refs, "no DIP key (environment, secrets or the published spec)")
        number, kind = refs[0], (refs[1] if len(refs) > 1 else None)
        try:
            if number.startswith("tally "):
                number, why = self._by_tally(number[6:], (row.get("date") or "")[:10])
                if number is None:
                    return amendtext.unreadable(refs, why)
            doc = self._drucksache(number)
            if doc is None:
                return amendtext.unreadable(refs, "DIP has no single Drucksache {0}".format(number))
            if kind and (doc.get("drucksachetyp") or "").lower() != kind.lower():
                found, why = self._voted_paper(doc, kind, (row.get("date") or "")[:10], number)
                if found is None:
                    return amendtext.unreadable(refs, why)
                doc = found
            body = (self.client.get_json(dip.url("drucksache-text", self.key(),
                                                 **{"f.id": doc.get("id")}),
                                         FEED, "text-{0}".format(doc.get("id")), archive=False)
                    or {}).get("documents") or []
        except Exception as exc:                        # noqa: BLE001 - fail loud
            return amendtext.unreadable(refs, "DIP: {0}".format(str(exc)[:140]))
        text = clean((body[0].get("text") if len(body) == 1 else "") or "")
        if not text.strip():
            return amendtext.unreadable(refs, "DIP holds no text for Drucksache {0} yet".format(
                doc.get("dokumentnummer")))
        dn = doc.get("dokumentnummer")
        url = "https://dserver.bundestag.de/btd/{0}/{1}/{0}{2}.pdf".format(
            dn.split("/")[0], dn.split("/")[1].zfill(5)[:3], dn.split("/")[1].zfill(5))
        return amendtext.Lookup("ok", refs=refs + ([dn] if dn != number else []), texts=[amendtext.entry(
            "{0} {1}".format(doc.get("drucksachetyp") or "Drucksache", dn), (doc.get("drucksachetyp") or "").lower(),
            dn, url, purpose_of(doc.get("titel"), text), text)])

    def apply(self, conn, row, result):
        return amendtext.apply_columns(conn, "de_divisions", "vote_id", row["key"], result)


def make_reader(client):
    return GermanyReader(client)
