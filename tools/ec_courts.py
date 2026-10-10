#!/usr/bin/env python3
"""Ecuador's Corte Constitucional: its judgments and press bulletins (X8).

    python3 tools/ec_courts.py                    # the weekly read
    python3 tools/ec_courts.py --since 2024-01-01 # a backfill from a date (Mini)
    python3 tools/ec_courts.py --dry-run
    python3 tools/ec_courts.py --reclassify
    python3 tools/ec_courts.py --db /tmp/ec.db

On our ground the Court has moved Ecuador more than the Asamblea has in a
decade: abortion for rape (34-19-IN/21, and the Asamblea legislated after
it), same-sex civil marriage (11-18-CN/19, 10-18-CN/19), euthanasia
(67-23-IN, February 2024). docs/ecuador-scope.md, phase 3; X8 approved
10 October 2026.

THE SOURCE: the Court's own WordPress site, www.corteconstitucional.gob.ec,
through its REST API (`/wp-json/wp/v2/posts`), keyless; robots.txt (Yoast)
disallows nothing. Probed 10 October 2026. Three categories are read:

  20   NOVEDADES JURISPRUDENCIALES  one post per judgment or dictamen,
       titled 'Sentencia 92-22-IN/26', with the Court's own plain-language
       summary ("¿Qué argumentaron...? ¿Qué analizó la Corte? ¿Qué decidió
       la Corte?") and a link to the decision in its case system (esacc).
       1,182 posts. Kind 'ruling', keyed on the case number.
  202  Boletines Comunicacionales  the Court's press bulletins (192): kind
       'ruling' when the headline reports a decision ("emite sentencia",
       "declara", "dictamina", "resuelve", "niega", "acepta"), 'hearing'
       when it reports a case admitted or heard, else 'press'.
  204  Comunicados  statements (127), classed the same way.

Category 203 (Actividades Jurisdiccionales: session agendas, admission
chambers, 1,345 posts) is not read: its posts are lists of case numbers
with no subject.

WHAT IS CLASSIFIED: the post's own text (the Court's summary, never the
judgment, which esacc serves as a PDF and which cites its precedents). The
date is the post's: when the Court published the summary, usually weeks
after the decision, which the post does not date.

The weekly read asks for posts published since 30 days before the newest
stored one (365 days on the first run), at most 100 a page, two seconds
apart. ONE WRITER AT A TIME on data/parl-monitor.db. Exit 3: stored what it
could and recorded gaps.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import courts, db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

CC = "ec"
FEED = "ec-courts"
COURT = "Corte Constitucional del Ecuador"
API = "https://www.corteconstitucional.gob.ec/wp-json/wp/v2/posts"
FIELDS = "id,date,modified,title,link,content,categories"
CATEGORIES = {20: "Novedades jurisprudenciales", 202: "Boletines comunicacionales",
              204: "Comunicados"}
PER_PAGE = 100
MAX_PAGES = 20
FIRST_DAYS = 365
OVERLAP_DAYS = 30
THROTTLE_S = 2.0

# '34-19-IN/21', '1313-19-JP/26', '1-26-OP/26', with or without '/yy'.
CASE = re.compile(r"\b(\d{1,4}-\d{2}-[A-Z]{2}(?:/\d{2})?)\b")
DECIDED = re.compile(r"\b(emite (?:sentencia|dictamen)|dictamina|declara|resuelve|resolvi[oó]|"
                     r"niega|acepta|concedi[oó]|concede|desestim|aclara que la sentencia|"
                     r"inconstitucional)", re.I)
HEARD = re.compile(r"\b(admite a tr[aá]mite|audiencia|avoca conocimiento)", re.I)
DECISION = re.compile(r"¿\s*Qu[eé] (?:decidi[oó]|concluy[oó]|resolvi[oó]) la Corte\s*\?\s*(.*)",
                      re.I | re.S)


def kind_of(categories, title):
    if 20 in categories:
        return "ruling"
    if DECIDED.search(title or ""):
        return "ruling"
    if HEARD.search(title or ""):
        return "hearing"
    return "press"


def parse(posts):
    out = []
    for p in posts or []:
        cats = [c for c in (p.get("categories") or []) if c in CATEGORIES]
        if not cats:
            continue
        title = courts.flat((p.get("title") or {}).get("rendered"))
        body = courts.flat((p.get("content") or {}).get("rendered"))
        if body.startswith(title):
            body = body[len(title):].strip()
        kind = kind_of(cats, title)
        case = CASE.search(title) or (CASE.search(body) if kind != "press" else None)
        case_no = case.group(1) if case else None
        if cats[0] == 20 and case_no:
            key = "ec:" + case_no
        else:
            key = "ec-post:{0}".format(p.get("id"))
        if cats[0] == 20 and body:
            # 'Sentencia 92-22-IN/26' says nothing: the summary opens with the
            # Court's own headline for the ruling (no full stop after it, so
            # the opening is clipped, not split).
            head = re.sub(r"\s*:\s*", " ", title).strip()
            lead = body if len(body) <= 160 else body[:160].rsplit(" ", 1)[0] + "\u2026"
            title = "{0}: {1}".format(head, lead)
        decided = DECISION.search(body)
        out.append({
            "ruling_key": key, "court": COURT, "kind": kind, "case_no": case_no,
            "date": (p.get("date") or "")[:10] or None,
            "title": title, "summary": body,
            "decision": courts.clip(decided.group(1), 600) if decided else None,
            "formation": CATEGORIES[cats[0]],
            "url": p.get("link"), "source": "corteconstitucional.gob.ec wp/v2 posts",
        })
    return out


def since_date(conn, override=None, today=None):
    if override:
        return override
    today = today or datetime.date.today()
    got = conn.execute("SELECT MAX(date) FROM ec_rulings").fetchone()
    if got and got[0]:
        return (datetime.date.fromisoformat(got[0][:10])
                - datetime.timedelta(days=OVERLAP_DAYS)).isoformat()
    return (today - datetime.timedelta(days=FIRST_DAYS)).isoformat()


def pull(conn, client, today, tax, since, log=print):
    """Returns (read, new, ours, gaps)."""
    read = new = ours = 0
    for page in range(1, MAX_PAGES + 1):
        url = "{0}?categories={1}&after={2}T00:00:00&per_page={3}&page={4}&_fields={5}".format(
            API, ",".join(str(c) for c in CATEGORIES), since, PER_PAGE, page, FIELDS)
        try:
            posts = client.get_json(url, FEED, "posts-{0}-p{1}".format(since, page))
        except (FetchError, ValueError) as exc:
            if page > 1 and "400" in str(exc):
                break      # WordPress answers 400 past the last page
            db.record_gap(conn, FEED, "posts page {0} unreadable: {1}".format(
                page, str(exc)[:120]), today)
            conn.commit()
            return read, new, ours, 1
        for row in parse(posts):
            read += 1
            is_new, areas = courts.upsert(conn, CC, row, tax, today)
            new += is_new
            if courts.on_ground(areas):
                ours += 1
                if is_new:
                    log("  [court] {0} {1} {2}: {3}".format(row["kind"], row["ruling_key"], areas,
                                                         row["title"][:70]))
        conn.commit()
        if len(posts or []) < PER_PAGE:
            break
    return read, new, ours, 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--since", help="read posts published after this ISO date")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    tax = courts.load_taxonomy(CC)
    conn = db.init_db(db.connect(":memory:" if args.dry_run else args.db))
    if args.reclassify:
        print("ec-courts: {0} ruling(s) reclassified".format(courts.reclassify(conn, CC, tax)))
        return 0
    client = HttpClient(raw_dir=args.raw_dir, throttle=THROTTLE_S)
    since = since_date(conn, args.since)
    read, new, ours, gaps = pull(conn, client, today, tax, since)
    print("ec-courts: {0} post(s) since {1}, {2} new, {3} on our ground{4}.".format(
        read, since, new, ours, " (dry run, nothing stored)" if args.dry_run else ""))
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
