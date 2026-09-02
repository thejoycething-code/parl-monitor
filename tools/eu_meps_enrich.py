"""MEP enrichment: country and political group, one detail call each.

    python3 tools/eu_meps_enrich.py

The tracker page and the EU 5CA both need who-sits-where: the search is
by name or COUNTRY (no postcodes in the EP), and group cohesion plays the
role the whip plays at Westminster. The roster listing carries neither,
so each MEP costs one detail fetch -- throttled to stay inside the API's
500-requests-per-5-minutes limit -- and each political-group org resolves
ONCE to its label, cached in-process (there are ~10 groups).

Incremental: only MEPs with no stored group are fetched, so the weekly
cost after the first run is new arrivals. The current group is the
EU_POLITICAL_GROUP membership with no end date; an MEP between groups
stores NULL and renders as unknown, never guessed.

Separation guarantee: writes eu_meps only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db
from src.http import FetchError, HttpClient

MEP = ("https://data.europarl.europa.eu/api/v2/meps/{0}"
       "?format=application%2Fld%2Bjson")
ORG = ("https://data.europarl.europa.eu/api/v2/corporate-bodies/{0}"
       "?format=application%2Fld%2Bjson")
THROTTLE_S = 0.65   # 500 requests / 5 min = one per 0.6s; stay under

# publications.europa.eu country-authority codes for the EU27. A code not
# here renders as itself -- never guessed.
COUNTRY = {
    "AUT": "Austria", "BEL": "Belgium", "BGR": "Bulgaria", "HRV": "Croatia",
    "CYP": "Cyprus", "CZE": "Czechia", "DNK": "Denmark", "EST": "Estonia",
    "FIN": "Finland", "FRA": "France", "DEU": "Germany", "GRC": "Greece",
    "HUN": "Hungary", "IRL": "Ireland", "ITA": "Italy", "LVA": "Latvia",
    "LTU": "Lithuania", "LUX": "Luxembourg", "MLT": "Malta",
    "NLD": "Netherlands", "POL": "Poland", "PRT": "Portugal",
    "ROU": "Romania", "SVK": "Slovakia", "SVN": "Slovenia", "ESP": "Spain",
    "SWE": "Sweden",
}


def ensure_columns(conn):
    cols = [c[1] for c in conn.execute("PRAGMA table_info(eu_meps)")]
    for col in ("country", "group_label", "group_org", "email"):
        if col not in cols:
            conn.execute("ALTER TABLE eu_meps ADD COLUMN {0} TEXT".format(col))
    conn.commit()


def current_group(memberships):
    """The EU_POLITICAL_GROUP membership with no end date, else None."""
    for mem in memberships or []:
        if not str(mem.get("membershipClassification", "")).endswith(
                "EU_POLITICAL_GROUP"):
            continue
        during = mem.get("memberDuring") or {}
        if not during.get("endDate"):
            return str(mem.get("organization", "")).rsplit("/", 1)[-1]
    return None


def enrich(conn, client, throttle=THROTTLE_S, log=print, limit=None):
    ensure_columns(conn)
    rows = conn.execute("SELECT person_id FROM eu_meps WHERE group_label "
                        "IS NULL OR email IS NULL ORDER BY person_id"
                        ).fetchall()
    if limit:
        rows = rows[:limit]
    groups = {}     # org id -> EN label, resolved once each

    def group_label(org_id):
        if org_id not in groups:
            reply = client.get_json(ORG.format(org_id), "eu-meps", org_id,
                                    archive=False)
            data = (reply.get("data") or [{}])[0]
            groups[org_id] = ((data.get("prefLabel") or {}).get("en")
                              or data.get("label"))
            time.sleep(throttle)
        return groups[org_id]

    done = gaps = 0
    for r in rows:
        pid = r["person_id"]
        try:
            reply = client.get_json(MEP.format(pid), "eu-meps", pid,
                                    archive=False)
        except (FetchError, ValueError) as exc:
            log("  [gap] mep {0}: {1}".format(pid, exc))
            gaps += 1
            time.sleep(throttle)
            continue
        m = (reply.get("data") or [{}])[0]
        code = str(m.get("citizenship", "")).rsplit("/", 1)[-1]
        org = current_group(m.get("hasMembership"))
        label = None
        if org:
            try:
                label = group_label(org)
            except (FetchError, ValueError) as exc:
                log("  [gap] org {0}: {1}".format(org, exc))
                gaps += 1
        email = str(m.get("hasEmail") or "").replace("mailto:", "") or None
        conn.execute("UPDATE eu_meps SET country = ?, group_label = ?, "
                     "group_org = ?, email = ? WHERE person_id = ?",
                     (COUNTRY.get(code, code or None), label, org, email,
                      pid))
        done += 1
        if done % 50 == 0:
            conn.commit()
            log("  ...{0}/{1}".format(done, len(rows)))
        time.sleep(throttle)
    conn.commit()
    return done, gaps


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    done, gaps = enrich(conn, client)
    have = conn.execute("SELECT COUNT(*) FROM eu_meps WHERE group_label "
                        "IS NOT NULL").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM eu_meps").fetchone()[0]
    print("eu-meps-enrich: {0} fetched, {1} gap(s); {2}/{3} carry a group."
          .format(done, gaps, have, total))
    for g, n in conn.execute("SELECT group_label, COUNT(*) FROM eu_meps "
                             "WHERE group_label IS NOT NULL GROUP BY 1 "
                             "ORDER BY 2 DESC"):
        print("  {0:4d}  {1}".format(n, g))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
