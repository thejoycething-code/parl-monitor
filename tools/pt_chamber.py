#!/usr/bin/env python3
"""Portugal: the Assembleia da República's written questions and requests.

    python3 tools/pt_chamber.py                      # the last three weeks
    python3 tools/pt_chamber.py --since 2026-09-01
    python3 tools/pt_chamber.py --dry-run
    python3 tools/pt_chamber.py --reclassify

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. From the
Assembleia's open data (parlamento.pt, the dataset pages
tools/pt_rollcalls.py already discovers files through); the rest is
src/chamber_store.py.

QUESTIONS. PerguntasRequerimentos, one file for the legislature
(RequerimentosXVII_json.txt, 7.8 MB, three requests to find and fetch):
4,076 in the XVII on 10 October 2026, 2,801 written questions (perguntas)
and 1,275 requests (requerimentos), each with its subject (Assunto), its
authors and their group (Autores: nome, GP), the date sent, and each
addressee (Destinatarios: nomeEntidade) with the replies received
(respostas: dataResposta). Classified on the Assunto alone; the first
answer's date is recorded, its PDF never read. A question is keyed on its
legislature, session, type and number ('XVII/2/P/17').

DEBATES ARE NOT COLLECTED: the Intervencoes dataset is empty for the XVII
(2 bytes, docs/portugal-scope.md), and the Diário da Assembleia is page by
page PDF (debates.parlamento.pt), a later phase.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402
import pt_rollcalls as pt  # noqa: E402

CC = "pt"
LEG = pt.CURRENT_LEGISLATURE
DATASET = ("/Cidadania/Paginas/DAPerguntasRequerimentos.aspx", "Requerimentos")
DETAIL = ("https://www.parlamento.pt/ActividadeParlamentar/Paginas/"
          "DetalhePerguntaRequerimento.aspx?BID={0}")
KINDS = {"Pergunta": ("written", "P"), "Requerimento": ("request", "R")}


def parse(rec):
    kind, code = KINDS.get(rec.get("Tipo"), ("written", "P"))
    authors = rec.get("Autores") or []
    first = authors[0] if authors else {}
    asker = first.get("nome")
    if asker and len(authors) > 1:
        asker = "{0} and {1} other(s)".format(asker, len(authors) - 1)
    to = [d.get("nomeEntidade") for d in rec.get("Destinatarios") or [] if d.get("nomeEntidade")]
    replies = [r.get("dataResposta") for d in rec.get("Destinatarios") or []
               for r in d.get("respostas") or [] if r.get("dataResposta")]
    return {"question_id": "{0}/{1}/{2}/{3}".format(rec.get("Legislatura") or LEG,
                                                    rec.get("Sessao"), code, rec.get("Nr")),
            "kind": kind, "date": (rec.get("DataEnvio") or rec.get("DtEntrada") or "")[:10],
            "title": rec.get("Assunto") or "", "text": None, "asker": asker,
            "party": first.get("GP"), "addressee": "; ".join(dict.fromkeys(to)) or None,
            "answered": min(replies)[:10] if replies else None,
            "url": DETAIL.format(rec.get("Id")) if rec.get("Id") else None}


def questions(run):
    pt.DATASETS.setdefault("questions", DATASET)
    try:
        recs = pt.fetch_dataset(run.client, "questions", LEG)
    except (FetchError, ValueError) as exc:
        run.gap("PerguntasRequerimentos {0} unreadable: {1}".format(LEG, str(exc)[:100]))
        return
    listed = matched = 0
    for rec in recs if isinstance(recs, list) else []:
        q = parse(rec)
        if not q["date"] or q["date"] <= run.since:
            # Re-read an older question only to record its answer, when stored.
            if q["answered"] and run.conn.execute(
                    "SELECT 1 FROM pt_questions WHERE question_id=? AND answered IS NULL",
                    (q["question_id"],)).fetchone() and not run.dry_run:
                run.conn.execute("UPDATE pt_questions SET answered=?, last_seen=? WHERE "
                                 "question_id=?", (q["answered"], run.today, q["question_id"]))
            continue
        listed += 1
        m = cs.classify_question(run.taxes, q["title"])
        if not m:
            continue
        matched += 1
        run.question(q, m)
    run.read("perguntas:{0}:{1}".format(run.since, run.today), "questions", run.today, None,
             listed, matched, 0)
    run.log("  [perguntas] {0} sent since {1}, {2} on our ground".format(
        listed, run.since, matched))


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"questions": questions}, doc=__doc__))
