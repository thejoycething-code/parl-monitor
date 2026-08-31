"""Load the committed APPG register files into the store.

    python3 tools/load_appgs.py

Reads every data/appg/register-*.json and upserts appg_officers. OFFLINE by
design: publications.parliament.uk sits behind a Cloudflare JS challenge
that blocks CI (and the Wayback Machine holds no copy), so the register is
scraped in a browser session and committed -- the backfill_pq_links
pattern. To refresh when a new edition appears (roughly six-weekly):

  1. Open https://publications.parliament.uk/pa/cm/cmallparty/ via the
     year index on parliament.uk and find the newest edition's date path.
  2. In the browser, fetch each tracked group's page (the slugs below are
     the register's own page names) and copy Title / Purpose / Category /
     the Officers table into data/appg/register-<edition>.json, matching
     the existing file's shape.
  3. Run this tool, check the resolution line, commit.

Officer names resolve against the members table; a name that cannot be
claimed by exactly one member is stored with member_id NULL and PRINTED.
The newest edition is what the page builders read; older editions stay as
history.
"""

from __future__ import annotations

import glob
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db

# Name normalisation and the members index live in the attendance tool;
# imported rather than copied so the two can never disagree about what
# counts as the same name.
_spec = importlib.util.spec_from_file_location(
    "pbc", os.path.join(ROOT, "tools", "pull_pbc_attendance.py"))
_pbc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pbc)
norm, resolve = _pbc.norm, _pbc.resolve


def load_file(conn, path, names):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    edition = payload["edition"]
    unresolved = []
    rows = 0
    for slug, group in (payload.get("groups") or {}).items():
        for officer in group.get("officers") or []:
            member_id = names.get(norm(officer["name"]))
            if member_id is None:
                unresolved.append(officer["name"])
            conn.execute(
                "INSERT OR REPLACE INTO appg_officers (edition, slug, "
                "group_name, purpose, category, role, name, party, member_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (edition, slug, group.get("title") or slug,
                 group.get("purpose"), group.get("category"),
                 officer["role"], officer["name"], officer.get("party"),
                 member_id))
            rows += 1
    return edition, rows, unresolved


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    # prefer_current: the register can only name sitting members
    names = resolve(conn, prefer_current=True)
    paths = sorted(glob.glob(os.path.join(ROOT, "data", "appg", "register-*.json")))
    if not paths:
        print("no register files under data/appg/ -- nothing to load")
        return 0
    unresolved = set()
    for path in paths:
        edition, rows, missing = load_file(conn, path, names)
        unresolved.update(missing)
        print("{0}: {1} officer rows from {2}".format(
            edition, rows, os.path.basename(path)))
    conn.commit()
    latest, groups, officers = conn.execute(
        "SELECT MAX(edition), COUNT(DISTINCT slug), COUNT(*) "
        "FROM appg_officers WHERE edition = "
        "(SELECT MAX(edition) FROM appg_officers)").fetchone()
    print("latest edition {0}: {1} groups, {2} officers held".format(
        latest, groups, officers))
    if unresolved:
        # Printed, never suppressed: a NULL member_id means no page and no
        # 5CA row will carry this officer until someone looks at why.
        print("  {0} name(s) not resolved to a member id: {1}".format(
            len(unresolved), "; ".join(sorted(unresolved))))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
