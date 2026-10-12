"""Quebec: the Journal des débats, in French (tools/prov_speeches.py --prov qc).

THE SOURCE: the Journal des débats link of each sitting on the session's
sitting index -- the same listing, month by month through the page's own
form, that the vote collector reads for the procès-verbal
(src/ingest/prov_qc.list_records; the month form POST was approved by
Christopher on 3 October 2026). One HTML page per sitting, French only,
about 850 KB (16 June 2019, measured 2 October 2026). Robots.txt is read in
full (prov_fetch.star_rules); the JD pages are not disallowed.

  <p style="font-weight:bold;text-align: center;">Questions et réponses orales</p>   a rubric
  <p style="font-weight:bold;text-align: center;">Motif d'urgence ... laïcité ...</p> a subject
  <p style="font-weight:bold;text-align: center;">M. Simon Jolin-Barrette</p>       the speaker, in full
  <p style="text-align: justify"><b>M. Jolin-Barrette :</b> M. le Président, ...</p>

The centred heading that names a member is the speaker's full name for the
turn below it (a 'hint'), so 'M. Jolin-Barrette' resolves on his full name.
A bill's debate is headed "Projet de loi n° 21"; the stage headings under it
(Adoption, Prise en considération du rapport ...) keep its bill.

CLASSIFIED IN FRENCH: config/taxonomy-qc.yaml (an AI draft no Quebec reader
has reviewed yet), plus config/watchlist-prov.yaml. The English taxonomy is
never run over French text (src/prov_classify).

WHO SPOKE: with the vote collector's resolver (prov_qc.MemberPages over the
depcir roster, which completes a missing member from his own page and sets
aside a candidate who presided that day). Le Président, La Vice-Présidente,
Des voix and the table are counted, not stored.
"""

from __future__ import annotations

import re

from src import prov_names as pn, prov_speeches as sp
from src.ingest import prov_qc as base

PROV = "qc"
LANGUAGE = "fr"
CURRENT_SESSION = base.CURRENT_SESSION

_P = re.compile(r"<p\b([^>]*)>(.*?)</p\s*>", re.S | re.I)
_NAME = re.compile(r"^(?:M\.|Mme|Mlle)\s+[A-ZÀ-Ý][\w'’\-]*(?:\s+[A-ZÀ-Ý][\w'’\-]*){0,4}$")
_BILL_FR = re.compile(r"\bprojet\s+de\s+loi\s+n[°o]\s*(\d{1,3})\b", re.I)
_BILL_HEADING = re.compile(r"^Projet\s+de\s+loi\s+n[°o]\s*(\d{1,3})\s*$", re.I)
RUBRICS = {pn.fold(r) for r in (
    "Affaires courantes", "Affaires du jour", "Déclarations de députés", "Questions et réponses orales",
    "Motions sans préavis", "Avis touchant les travaux des commissions",
    "Renseignements sur les travaux de l'Assemblée", "Dépôt de documents", "Dépôt de rapports de commissions",
    "Dépôt de pétitions", "Présentation de projets de loi", "Débats de fin de séance", "Votes reportés",
    "Interventions portant sur une violation de droit ou de privilège", "Affaires prioritaires",
    "Affaires inscrites par les députés de l'opposition", "Déclarations ministérielles",
    "Réponses orales aux pétitions", "Questions et réponses orales (suite)", "Dépôts",
    "Débat sur le discours d'ouverture", "Débat sur le discours du budget", "Ajournement",
    "Présence de membres du corps consulaire")}
STAGES = ("adoption", "prise en consideration", "etude detaillee", "commission pleniere", "mise aux voix",
          "reprise du debat", "debat sur", "depot du rapport", "presentation", "poursuite du debat",
          "debat restreint", "demande d'inscription", "vote", "motion de renumerotation")
# Headings that say nothing about the debate they interrupt.
QUIET = ("document depose", "documents deposes", "suspension", "reprise")


def bill_fr(text):
    m = _BILL_FR.search(text or "")
    return m.group(1) if m else None


def parse_day(html):
    blocks = []
    in_bill = None                     # the bill a 'Projet de loi n° N' heading opened
    for attrs, inner in _P.findall(html or ""):
        style = attrs.lower()
        text = sp.text_of(inner)
        if not text:
            continue
        if "center" in style and "bold" in style:
            folded = pn.fold(text)
            if _NAME.match(text):
                blocks.append(("hint", text))
            elif folded in RUBRICS or any(folded.startswith(r) for r in ("ajournement au",)):
                blocks.append(("rubric", text))
                in_bill = None
            elif folded.startswith(QUIET):
                continue
            elif _BILL_HEADING.match(text):
                in_bill = _BILL_HEADING.match(text).group(1)
                blocks.append(("subject", text, in_bill))
            elif in_bill and folded.startswith(STAGES):
                blocks.append(("subsubject", text))
            else:
                in_bill = None
                blocks.append(("subject", text, bill_fr(text)))
            continue
        if "justify" not in style and "text-align" in style:
            continue                   # the table of contents and the page furniture
        lab = sp.bold_label(inner)
        if lab:
            blocks.append(("label", lab[0], lab[1]))
        else:
            blocks.append(("para", text))
    return sp.turns_from_blocks(blocks)


def list_days(ctx, session):
    leg, sess = base.parse_session(session)
    records, _pages = base.list_records(ctx, leg, sess)
    if not ctx.dry_run and not ctx.conn.execute("SELECT COUNT(*) FROM prov_members WHERE prov=?",
                                                (PROV,)).fetchone()[0]:
        base.fetch_roster(ctx)
    out = []
    for r in records:
        if not r.get("jd_url"):
            ctx.gap("qc {0} {1}: the listing has no Journal des débats link".format(session, r["date"]))
            continue
        key = "qc-{0}-{1}-{2}".format(leg, sess, r["date"]) + ("-" + r["part"] if r.get("part") else "")
        out.append({"key": key, "date": r["date"], "part": r.get("part"), "legislature": leg,
                    "session": sess, "url": r["jd_url"]})
    return out


def read_day(ctx, day):
    html = ctx.text(day["url"], "jd-{0}".format(day["key"]), archive=True)
    if html is None:
        return None, ["the Journal des débats was not fetched"]
    return parse_day(html), []


def resolver(ctx):
    pages = getattr(ctx, "_qc_member_pages", None)
    if pages is None:
        pages = base.MemberPages(ctx, pn.Resolver.from_conn(ctx.conn, PROV))
        ctx._qc_member_pages = pages
    return pages
