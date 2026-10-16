"""Shared bits for the Latin American gov_docs reader tests (ar, br, co, mx, cl, pe)."""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "gov_docs")


def fixture(cc, name):
    with open(os.path.join(FIX, cc, name), encoding="utf-8") as fh:
        return fh.read()


def load_petitions(conn, cc, name):
    """Insert captured country_petitions rows (the petitions step's output) for a mirror."""
    rows = json.loads(fixture(cc, name))
    for r in rows:
        cols = ",".join(r)
        conn.execute("INSERT INTO country_petitions ({0}) VALUES ({1})".format(
            cols, ",".join("?" * len(r))), list(r.values()))
    conn.commit()
    return rows
