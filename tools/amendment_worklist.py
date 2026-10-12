#!/usr/bin/env python3
"""The amendment READING WORKLIST (Chris, 12 October 2026: "score all
amendments and reverse France's decision").

    python3 tools/amendment_worklist.py --db data/parl-monitor.db \
        --out /path/worklist.json [--summary /path/worklist-summary.txt]

One object per `divisions` entry, in any new country's config/<cc>_stance.yaml,
that is an amendment or article vote (`vote_kind: amendment`, or `other` whose
wording the rules now read as one: src/country5ca.py is_amendment_entry),
still `status: needs_reading`, not taken out of play, and not collated only
(every area excluded from the 5CA). Each carries what a reader needs to FIND
the amendment's text and record whether ADOPTING it is with or against
CitizenGO: the vote's full wording (from the store when it holds the vote,
else the stance file's, clipped), the bill and its direction if any, the
result and tally, the areas, identifiers read from the store row and the
wording (amendment number, author, article, reading or stage, dossier or
print numbers), and the parliament's URLs (`urls`: each {kind, url, sure}:
`sure: false` marks a pattern with a part to fill or not checked).

The readers answer in the file tools/country_5ca.py --apply-amendments reads:
[{cc, key, direction: with|against|unclear|not_scored, why, source, flag,
yes_adopts}]. This tool reads the store read-only and the stance files; it
writes only --out and --summary, and makes no for/against judgement.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402

# The base table and key column of each store (for the raw row: identifiers
# the spec's SQL does not select).
TABLES = {"it": ("it_divisions", "division_key"), "ch": ("ch_divisions", "division_key"),
          "fr": ("fr_divisions", "division_key"), "nl": ("nl_divisions", "besluit_id"),
          "be": ("be_divisions", "division_key"), "pl": ("pl_divisions", "division_key"),
          "hr": ("hr_divisions", "division_key"), "sk": ("sk_divisions", "voting_id"),
          "es": ("es_divisions", "division_key"), "br": ("br_divisions", "division_key"),
          "ar": ("ar_divisions", "division_key"), "mx": ("mx_divisions", "division_key"),
          "hu": ("hu_divisions", "vote_ts"), "at": ("at_divisions", "division_key"),
          "pt": ("pt_divisions", "division_key"), "cl": ("cl_divisions", "division_key"),
          "pe": ("pe_divisions", "division_key"), "ec": ("ec_divisions", "division_key"),
          "do": ("do_divisions", "division_key"), "sv": ("sv_divisions", "division_key"),
          "gt": ("gt_divisions", "division_key")}
SKIP_COLS = ("positions", "matched_terms", "group_tallies", "members", "own_areas", "first_seen",
             "last_seen", "positions_fetched", "positions_pending", "positions_read", "positions_at",
             "positions_source", "areas")


def _rows(conn, sql, params=()):
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    except sqlite3.Error:
        return []


def store_rows(conn, cc, key):
    """(the spec's division row, the base table's raw row), either {} if absent."""
    if conn is None:
        return {}, {}
    spec = c5.SPECS[cc]
    got = _rows(conn, "SELECT * FROM ({0}) WHERE key = ?".format(spec.div_sql), (key,))
    table, col = TABLES[cc]
    raw = _rows(conn, "SELECT * FROM {0} WHERE {1} = ?".format(table, col), (key,))
    return (got[0] if got else {}), (raw[0] if raw else {})


def fr_dossier(conn, ref):
    if conn is None or not ref:
        return {}
    got = _rows(conn, "SELECT title, an_path, senat_url, procedure FROM fr_dossiers WHERE dossier_ref = ?",
                (ref,))
    return got[0] if got else {}


# --- identifiers read from the wording (best effort, never a judgement) -------------

NUMBER_PATS = (
    r"amendements?(?: identiques)?\s+n\s*[°ºo]\.?\s*(\d+(?:\s*rect\.?(?:ifié)?(?: \w+)?)?)",
    r"\bn\s*[°ºo]\s*(\d+)(?:\s*rectifi\w*)?(?:,| et)",               # "n° 9, présenté par ..."
    r"\b(?:em\.|emendament[oi]|articolo aggiuntivo|em)\s*(\d+\.\d+(?:\.\d+)?)",
    r"\b(?:emendamenti|em\.|emm\.)[^-]*?,\s*(\d+\.\d+)",
    r"\bpoprawk\w*\s+(?:nr\s*)?(\d+)",
    r"\benmiendas?\s+(?:n[úu]m(?:ero)?\.?\s*|n\.?\s*[ºo°]\s*)(\d+)",
    r"\bamendement(?:en)?\s+nr\.?\s*(\d+)",
    r"\(AA-(\d+)\)",
    r"\b(?:indicaci[oó]n|destaque)\s+(?:n[º°o.]\s*)?(\d+)",
    r"\bmotion\s+n\s*[°ºo]\s*(\d+)",
)
ARTICLE_PATS = (
    r"\b(?:l')?article\s+(premier|1er|\d+\s*(?:bis|ter|quater|quinquies|sexies|septies|octies)?)",
    r"\bart(?:icolo|ículo|iculo|ikel|igo|\.)\s*(\d+[\w-]*|único|unico|unique)",
    r"\bartyku\w*\s+(\d+\w*)",
    r"\bartículos?\s+(\d+(?:\s*y\s*\d+)?)",
)
AUTHOR_PATS = (
    r"\b(?:de|par)\s+((?:M\.|Mme|MM\.)\s+[A-ZÀ-Ý][\w'’ -]+?)(?=\s+(?:et|à|de suppression|tendant|au nom|,)|[,.(]|$)",
    r"présentée? par\s+((?:M\.|Mme)\s+[^,]+)",
    r"\bvan (?:het lid|de leden)\s+([A-Z][\w'’ -]+?)(?=\s+(?:over|ter|tot|c\.s\.)|[,.]|$)",
    r"\b(?:Em\.\s*\d+\.\d+,)\s*([A-Z][\w'’ ]+?)(?:\s+e altri)?$",
    r"\b(?:\d+\.\d+)\s+([A-ZÀ-Ý][A-ZÀ-Ý'’]+[A-ZÀ-Ý'’ ]+\s\([^)]+\))",
    r"\bder Abgeordneten\s+(.+?)(?:,? Kolleginnen und Kollegen|\s+\()",
    r"\b(?:de la diputada|del diputado|de los diputados|de las diputadas|por el diputado|por la diputada|"
    r"por los diputados|por las diputadas)\s+(.+?)(?:,\s*(?:que|para|de cuyo)|:|\.|$)",
    r"\b(?:wniosek|poprawk\w*) (?:posła|posłanki|klubu)\s+([^,.]+)",
    r"\bdel Grupo Parlamentario\s+([^,.]+)",
)
STAGE_PATS = (
    r"\(((?:première|deuxième|troisième|nouvelle) lecture)\)", r"\b(lecture définitive)\b",
    r"\b((?:prvé|druhé|tretie) čítanie)", r"\b((?:primer|segundo|tercer) trámite)\b",
    r"\b((?:primeiro|segundo) turno)\b", r"\b(en lo particular|en particular)\b",
    r"\b((?:trzecie|drugie|pierwsze) czytanie)\b", r"\b((?:zweite|dritte) lesung)\b",
)


def _first(pats, text, flags=re.I):
    for p in pats:
        m = re.search(p, text, flags)
        if m:
            return " ".join(m.group(1).split()).strip(" ,.")
    return None


def _all_numbers(text):
    seen = []
    for p in NUMBER_PATS:
        for m in re.finditer(p, text, re.I):
            n = " ".join(m.group(1).split())
            if n not in seen:
                seen.append(n)
    return seen


def wording_ids(question):
    q = question or ""
    out = {}
    nums = _all_numbers(q)
    if nums:
        out["amendment_numbers"] = nums
    art = _first(ARTICLE_PATS, q)
    if art:
        out["article"] = art
    who = _first(AUTHOR_PATS, q, 0)
    if who:
        out["author"] = who
    stage = _first(STAGE_PATS, q)
    if stage:
        out["reading_or_stage"] = stage
    return out


# --- the parliaments' URLs ----------------------------------------------------------

def U(kind, url, sure=True, note=None):
    d = {"kind": kind, "url": url, "sure": bool(sure)}
    if note:
        d["note"] = note
    return d


def urls_for(cc, key, row, raw, ids, extra):
    nums = ids.get("amendment_numbers") or []
    n0 = nums[0].split()[0] if nums else None
    out = []
    if cc == "fr":
        m = re.match(r"^an-(\d+)-(\d+)$", key)
        if m:
            leg, no = m.groups()
            out.append(U("vote record (links the amendment voted)",
                         "https://www.assemblee-nationale.fr/dyn/{0}/scrutins/{1}".format(leg, no)))
            out.append(U("amendment text", "https://www.assemblee-nationale.fr/dyn/{0}/amendements/"
                         "<texte>/AN/{1}".format(leg, n0 or "<numero>"), False,
                         "<texte> is the print number of the text in séance (on the scrutin page)"))
            if extra.get("an_path"):
                out.append(U("dossier", "https://www.assemblee-nationale.fr/dyn/{0}/dossiers/{1}".format(
                    leg, extra["an_path"])))
        m = re.match(r"^senat-(\d{4})-(\d+)$", key)
        if m:
            sess, no = m.groups()
            out.append(U("vote record", "https://www.senat.fr/scrutin-public/{0}/scr{0}-{1}.html".format(
                sess, no), False))
            out.append(U("amendment text", "https://www.senat.fr/amendements/{0}-{1}/<texte>/Amdt_{2}.html"
                         .format(sess, int(sess) + 1, n0 or "<numero>"), False,
                         "<texte> is the Senat's text number; the dossier page lists it"))
            if extra.get("senat_url"):
                out.append(U("dossier", extra["senat_url"]))
        if row.get("dossier_ref") and not extra.get("an_path"):
            out.append(U("dossier", "https://www.assemblee-nationale.fr/dyn/17/dossiers/{0}".format(
                row["dossier_ref"]), False))
        out.append(U("open data", "https://data.assemblee-nationale.fr/travaux-parlementaires/amendements",
                     True, "the Assemblée's amendments open data, by text and number"))
    elif cc == "it":
        m = re.match(r"^camera-vs(\d+)_(\d+)_(\d+)$", key)
        if m:
            leg, sitting, no = m.groups()
            out.append(U("vote record (open data)", "https://dati.camera.it/ocd/votazione.rdf/vs{0}_{1}_{2}"
                         .format(leg, sitting, no), False))
            out.append(U("sitting (resoconto and allegati with the emendamenti)",
                         "https://www.camera.it/leg{0}/410?idSeduta={1:04d}&tipo=documenti_seduta".format(
                             leg, int(sitting)), False))
        m = re.match(r"^senato-(\d+)-(\d+)-(\d+)$", key)
        if m:
            leg, sitting, no = m.groups()
            out.append(U("vote record (open data)", "https://dati.senato.it/votazione/{0}".format(key), False))
            out.append(U("emendamenti (fascicolo of the sitting)",
                         "https://www.senato.it/leg/{0}/BGT/Testi/Emend/...".format(leg), False,
                         "search the bill's 'Emendamenti' tab on senato.it for Em. {0}".format(n0 or "?")))
        bk = row.get("bill_key") or ""
        m = re.match(r"^(\d+)/C\.(\d+)", bk)
        if m:
            out.append(U("bill (Camera)", "https://www.camera.it/leg{0}/126?leg={0}&idDocumento={1}".format(
                *m.groups()), False))
        m = re.match(r"^(\d+)/S\.(\d+)", bk)
        if m:
            out.append(U("bill (Senato)", "https://www.senato.it/leg/{0}/BGT/Schede/Ddliter/...".format(
                m.group(1)), False, "search ddl S.{0}".format(m.group(2))))
    elif cc == "ch":
        if raw.get("business_id"):
            out.append(U("business (Curia Vista: the Fahne lists each Antrag)",
                         "https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={0}"
                         .format(raw["business_id"])))
        if raw.get("vote_id"):
            out.append(U("vote record (open data)",
                         "https://ws.parlament.ch/odata.svc/Vote?$filter=IdVote%20eq%20{0}%20and%20Language"
                         "%20eq%20'DE'".format(raw["vote_id"]), False))
        out.append(U("Amtliches Bulletin", "https://www.parlament.ch/de/ratsbetrieb/amtliches-bulletin", True,
                     "the debate on the business, by date, quotes the Anträge"))
    elif cc == "nl":
        z = raw.get("zaak_nummer")
        if z:
            out.append(U("amendment (Tweede Kamer)",
                         "https://www.tweedekamer.nl/kamerstukken/amendementen/detail?id={0}".format(z)))
            out.append(U("amendment (gegevensmagazijn, with its documents)",
                         "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Zaak?$filter=Nummer%20eq%20'{0}'"
                         "&$expand=Document".format(z)))
    elif cc == "be":
        dk = raw.get("dossier_key") or ""
        m = re.match(r"^(\d+)/(\d+)$", dk)
        for ref in c5._json_list(raw.get("doc_refs")):
            r = re.match(r"^(\d+)/(\d+)", ref)
            if m and r and r.group(1) == m.group(2):
                out.append(U("document with the amendments", "https://www.lachambre.be/FLWB/PDF/{0}/{1}/{0}K{1:0>4}"
                             "{2:0>3}.pdf".format(m.group(1), r.group(1), r.group(2)), False))
        if m:
            out.append(U("dossier", "https://www.lachambre.be/kvvcr/showpage.cfm?section=/flwb&language=fr&"
                         "cfm=/site/wwwcfm/flwb/flwbn.cfm?legislist=legisnr&dossierID={1:0>4}&legislat={0}"
                         .format(*m.groups()), False))
    elif cc == "pl":
        term, sitting, no = raw.get("term"), raw.get("sitting"), raw.get("number")
        if term and sitting and no:
            out.append(U("vote record", "https://www.sejm.gov.pl/Sejm{0}.nsf/agent.xsp?symbol=glosowania&"
                         "NrKadencji={0}&NrPosiedzenia={1}&NrGlosowania={2}".format(term, sitting, no)))
            out.append(U("vote record (API)", "https://api.sejm.gov.pl/sejm/term{0}/votings/{1}/{2}".format(
                term, sitting, no)))
        for p in c5._json_list(raw.get("print_numbers")):
            out.append(U("print (druk{0})".format("; the -A print is the additional report with the "
                                                  "amendments" if p.endswith("-A") else ""),
                         "https://api.sejm.gov.pl/sejm/term{0}/prints/{1}".format(term or 10, p)))
    elif cc == "sk":
        out.append(U("vote record", "https://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID={0}"
                     .format(key)))
        m = re.match(r"^(\d+)/(\d+)$", str(raw.get("bill_key") or ""))
        if m:
            out.append(U("bill (tlač; amendments in the spoločná správa and the debate)",
                         "https://www.nrsr.sk/web/Default.aspx?sid=zakony/cpt&ZakZborID=13&CisObdobia={0}&ID={1}"
                         .format(*m.groups())))
    elif cc == "es":
        if raw.get("json_url"):
            out.append(U("vote record (JSON)", raw["json_url"]))
        ik = raw.get("initiative_key") or ""
        m = re.match(r"^(\d+)/(\d+/\d+)$", ik)
        if m:
            roman = {"14": "XIV", "15": "XV", "16": "XVI"}.get(m.group(1), m.group(1))
            out.append(U("initiative (enmiendas in the BOCG under it)",
                         "https://www.congreso.es/es/busqueda-de-iniciativas?p_p_id=iniciativas&p_p_lifecycle=0&"
                         "_iniciativas_mode=mostrarDetalle&_iniciativas_legislatura={0}&_iniciativas_id={1}"
                         .format(roman, m.group(2).replace("/", "%2F")), False))
    elif cc == "br":
        sid = raw.get("source_id") or ""
        if raw.get("chamber") == "camara" and sid:
            out.append(U("vote record (API; names the destaque or emenda)",
                         "https://dadosabertos.camara.leg.br/api/v2/votacoes/{0}".format(sid)))
            out.append(U("bill", "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={0}"
                         .format(sid.split("-")[0])))
    elif cc == "ar":
        m = re.match(r"^sen-acta-(\d+)$", key)
        if m:
            out.append(U("vote record", "https://www.senado.gob.ar/votaciones/detalleActa/{0}".format(m.group(1)),
                         False))
        if raw.get("source_url"):
            out.append(U("source", raw["source_url"]))
    elif cc == "hu":
        motion, paper = raw.get("motion") or "", raw.get("paper_key") or ""
        m = re.match(r"^(\d+)/(\d+)$", motion)
        if m:
            out.append(U("motion paper (iromány)", "https://www.parlament.hu/irom43/{0:0>5}/{0:0>5}-{1:0>4}.pdf"
                         .format(*m.groups()), False, "43rd parliament (from May 2026) assumed"))
        if paper:
            out.append(U("iromány search", "https://www.parlament.hu/web/guest/iromanyok-lekerdezese", True,
                         "search {0}".format(paper)))
    elif cc == "at":
        if raw.get("protocol_url"):
            out.append(U("stenographic record at the vote", "https://www.parlament.gv.at" + raw["protocol_url"]))
        m = re.search(r"\(AA-(\d+)\)", row.get("question") or "")
        leg = (raw.get("item_key") or "XXVIII/").split("/")[0]
        if m:
            out.append(U("Abänderungsantrag", "https://www.parlament.gv.at/gegenstand/{0}/AA/{1}".format(
                leg, m.group(1))))
        if raw.get("item_key"):
            out.append(U("item", "https://www.parlament.gv.at/gegenstand/" + raw["item_key"]))
    elif cc == "cl":
        b = raw.get("boletin")
        if raw.get("chamber") == "camara" and raw.get("source_id"):
            out.append(U("vote record", "https://www.camara.cl/legislacion/sala_sesiones/votacion_detalle.aspx?"
                         "prmIdVotacion={0}".format(raw["source_id"]), False))
        if b:
            out.append(U("bill (Senado tramitación; indicaciones under it)",
                         "https://tramitacion.senado.cl/appsenado/templates/tramitacion/index.php?boletin_ini={0}"
                         .format(b), False))
    elif cc == "do":
        refs = c5._json_list(raw.get("bill_refs")) or [x for x in [extra.get("watched")] if x]
        for r in refs:
            out.append(U("bill (SIL)", "https://www.diputadosrd.gob.do/sil/", True,
                         "search initiative {0}".format(r)))
    return out


def bill_of(cc, e, row, bills):
    """(bill_key, bill_title, direction or None, direction status)."""
    spec = c5.SPECS[cc]
    cands = [e.get("watched")]
    if row:
        try:
            cands += list(spec.refs(row))
        except (KeyError, TypeError, IndexError):
            pass
    bkey = next((str(k) for k in cands if k and str(k) in bills), None) or next(
        (str(k) for k in cands if k), None)
    b = bills.get(bkey) if bkey else None
    title = (row.get("subject") if row else None) or e.get("on")
    d = b.get("direction") if b and b.get("direction") in ("with", "against") else None
    return bkey, title, d, (b.get("status") if b else None)


def item(conn, cc, key, e, bills):
    from src.latam import AREA_LABELS
    spec = c5.SPECS[cc]
    row, raw = store_rows(conn, cc, key)
    question = row.get("question") or e.get("title")
    extra = {"watched": e.get("watched")}
    if cc == "fr":
        extra.update(fr_dossier(conn, row.get("dossier_ref")))
    bkey, btitle, bdir, bstatus = bill_of(cc, e, row, bills)
    ids = wording_ids(question)
    for col in ("legislature", "term", "sitting", "session", "meeting", "number", "vote_number", "vote_no",
                "print_numbers", "doc_refs", "dossier_ref", "dossier_key", "business_id", "short_number",
                "zaak_nummer", "initiative_key", "expediente", "boletin", "stage", "motion", "paper_key",
                "item_key", "source_id", "bill_key", "bill_keys", "process_keys", "exp_keys", "bill_refs",
                "meaning_yes", "meaning_no", "subjects", "subgroup", "agendapunt", "draft_title", "topic",
                "description", "text", "vote_type", "kind", "motion_kind"):
        v = raw.get(col)
        if v not in (None, "", "[]"):
            ids.setdefault("store", {})[col] = v
    if cc == "fr" and extra.get("procedure"):
        ids.setdefault("store", {})["dossier_procedure"] = extra["procedure"]
    if raw:
        tally = {"yes": row.get("yes"), "no": row.get("no"), "abstain": row.get("abstain")}
    else:
        tally = None
    areas = c5.areas_of(e.get("areas"))
    return {
        "cc": cc, "country": spec.name, "key": key,
        "chamber": e.get("chamber"), "chamber_name": spec.chambers.get(e.get("chamber"), e.get("chamber")),
        "dated": e.get("dated"),
        "question": question, "question_source": "store" if row.get("question") else
        "stance file (clipped to 240 characters; the store does not hold this vote)",
        "vote_kind": e.get("vote_kind"),
        "bill_key": bkey, "bill_title": btitle, "bill_direction": bdir, "bill_direction_status": bstatus,
        "watched": e.get("watched"), "tier": e.get("tier"),
        "result": (row.get("result") if row.get("result") not in (None, "") else None) or e.get("result"),
        "result_line": e.get("result"), "tally": tally,
        "lobby_labels": {"yes": spec.labels[0], "no": spec.labels[1]},
        "lobbies": e.get("lobbies"),
        "areas": areas, "area_labels": [AREA_LABELS.get(a, str(a)) for a in areas],
        "identifiers": ids,
        "urls": urls_for(cc, key, row, raw, ids, extra),
        "read_first": e.get("read_first"),
        "amendment_flag": e.get("amendment_flag"),
        "answer_with": {"cc": cc, "key": key, "direction": "with|against|unclear|not_scored",
                        "why": "", "source": "", "flag": "", "yes_adopts": True},
    }


def selected(cc, config_dir=None):
    """[(key, entry)] of a country's stance file that need an amendment reading."""
    divs, bills, _ = c5.load(cc, config_dir)
    excl = c5.excluded()
    out = []
    for k, e in divs.items():
        if not c5.is_amendment_entry(e) or e.get("status") != "needs_reading":
            continue
        if e.get("draft") or e.get("confirmed_by") or c5.collated_only(e, excl):
            continue
        out.append((k, e))
    return out, bills


def build(conn, countries=c5.COUNTRIES, config_dir=None):
    items = []
    for cc in countries:
        if not os.path.exists(c5.stance_path(cc, config_dir)):
            continue
        sel, bills = selected(cc, config_dir)
        for k, e in sel:
            items.append(item(conn, cc, k, e, bills))
    items.sort(key=lambda x: (x["cc"], str(x["dated"] or ""), x["key"]))
    return items


def summary(items, db_note=""):
    from collections import Counter
    by = Counter(i["cc"] for i in items)
    in_store = Counter(i["cc"] for i in items if i["question_source"] == "store")
    with_dir = Counter(i["cc"] for i in items if i["bill_direction"])
    lines = ["Amendment reading worklist, {0}{1}".format(datetime.date.today().isoformat(), db_note),
             "Chris, 12 October 2026: \"score all amendments and reverse France's decision\".",
             "", "{0:<4} {1:<20} {2:>6} {3:>10} {4:>14}".format("cc", "country", "items", "in store",
                                                                "bill direction"), ""]
    for cc in sorted(by, key=lambda c: -by[c]):
        lines.append("{0:<4} {1:<20} {2:>6} {3:>10} {4:>14}".format(
            cc, c5.SPECS[cc].name, by[cc], in_store[cc], with_dir[cc]))
    lines += ["", "all  {0:<20} {1:>6} {2:>10} {3:>14}".format("", len(items), sum(in_store.values()),
                                                            sum(with_dir.values())),
              "", "Answer with a JSON list of {cc, key, direction: with|against|unclear|not_scored, why, "
              "source, flag, yes_adopts}", "and apply it with: python3 tools/country_5ca.py --apply-amendments "
              "FILE [--dry-run]"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary")
    ap.add_argument("--cc", action="append", default=[])
    args = ap.parse_args(argv)
    conn = c5.connect_ro(args.db) if os.path.exists(args.db) else None
    try:
        items = build(conn, tuple(args.cc) or c5.COUNTRIES)
    finally:
        if conn is not None:
            conn.close()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as h:
        json.dump(items, h, ensure_ascii=False, indent=1, default=str)
        h.write("\n")
    text = summary(items, "" if conn is not None else " (no store: wording from the stance files)")
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as h:
            h.write(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
