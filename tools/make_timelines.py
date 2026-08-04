"""Generate the internal MP timelines page from the mp_events ledger.

    python3 tools/make_timelines.py [N_members]

Writes docs/mp-timelines.html (internal only; never deployed -- docs/ is not
the partner_site/ directory). Re-run any time; it is a pure query over the
ledger, the same byproduct principle as the digest.
"""

from __future__ import annotations

import html
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel

PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>MP timelines (internal)</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
body {{ font: 15px/1.5 Roboto, sans-serif; color:#52575C; max-width:60rem;
       margin:0 auto; padding:1rem 1.5rem 3rem; }}
h1 {{ color:#52575C; font-size:1.3rem; border-bottom:4px solid #4285f4; padding-bottom:.4rem; }}
.internal {{ background:#FFEBAD; border-left:4px solid #DB544F; padding:.6rem 1rem;
            font-size:.88em; border-radius:0 4px 4px 0; margin-bottom:1.2rem; }}
.profiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:1rem; }}
.card {{ border:1px solid #EEEEEE; border-radius:6px; padding:.9rem 1.1rem; }}
.card h4 {{ margin:0; font-size:1.02em; }}
.card .role {{ font-size:.82em; opacity:.8; margin-bottom:.4rem; }}
.stat {{ font-size:.8em; margin:.3rem 0 .5rem; }} .stat b {{ color:#4285f4; }}
.tl {{ border-left:2px solid #EEEEEE; margin:.4rem 0 .2rem .35rem; padding-left:.9rem; }}
.ev {{ position:relative; font-size:.85em; margin:.4rem 0; }}
.ev::before {{ content:""; position:absolute; left:-1.22rem; top:.35em; width:.5em;
              height:.5em; border-radius:50%; background:#4285f4; }}
.ev .d {{ font-weight:700; opacity:.7; margin-right:.4rem; }}
.kind {{ font-size:.68em; font-weight:700; border-radius:999px; padding:.05em .5em;
        background:#4285f4; color:#FFF; margin-right:.3em; }}
.kind.signed {{ background:#FFF; color:#4285f4; border:1px solid #4285f4; }}
.areas {{ font-size:.75em; margin:.1rem 0 .4rem; }}
.area {{ display:inline-block; border:1px solid #4285f4; color:#4285f4; border-radius:3px;
        padding:.05em .45em; margin:.1em .2em .1em 0; }}
</style></head><body>
<h1>MP timelines - six-month ledger</h1>
<p class="internal"><strong>Internal only.</strong> Working intelligence from the mp_events ledger
({events} events, {members} parliamentarians, {earliest} to {latest}). Feeds Phase 3 profile
scoring; never appears in any edition or the partner site.</p>
<div class="profiles">
{cards}
</div></body></html>
"""

CARD = """<div class="card">
<h4>{name}</h4><div class="role">{role}</div>
<div class="stat"><b>{n}</b> recorded contributions</div>
<div class="areas">{areas}</div>
<div class="tl">
{events}
</div></div>"""

KIND_LABEL = {"edm-signed": "SIGNED"}


def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    conn = db.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    stats = intel.ledger_stats(conn)
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    activity = intel.area_activity(conn)

    tops = conn.execute(
        "SELECT e.member_id, m.name, m.party, m.seat, COUNT(*) n FROM mp_events e "
        "LEFT JOIN members m ON m.id = e.member_id "
        "GROUP BY e.member_id ORDER BY n DESC LIMIT ?", (top_n,)).fetchall()

    cards = []
    for t in tops:
        events = intel.member_timeline(conn, t["member_id"], limit=8)
        rows = "\n".join(
            '<div class="ev"><span class="d">{0}</span><span class="kind {3}">{1}</span>{2}</div>'.format(
                e["date"], KIND_LABEL.get(e["kind"], e["kind"].upper()),
                html.escape(e["line"] or ""),
                "signed" if e["kind"] == "edm-signed" else "")
            for e in events)
        role = ", ".join(x for x in (t["party"], t["seat"]) if x) or "unresolved"
        per = activity.get(t["member_id"], {})
        chips = "".join(
            '<span class="area">{0} &times;{1}</span>'.format(
                html.escape(names.get(a, "Area {0}".format(a))), n)
            for a, n in sorted(per.items(), key=lambda kv: -kv[1]))
        cards.append(CARD.format(name=html.escape(t["name"] or "Member %d" % t["member_id"]),
                                 role=html.escape(role), n=t["n"], events=rows,
                                 areas=chips or "&nbsp;"))
    conn.close()

    out = os.path.join(ROOT, "docs", "mp-timelines.html")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(PAGE.format(cards="\n".join(cards), **stats))
    print(out)


if __name__ == "__main__":
    main()
