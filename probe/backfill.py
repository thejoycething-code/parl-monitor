"""Measurement backfill into probe/scratch-full.db: bills from the pulled
pages (offline), then the real vote pass, classified with probe/terms-do.yaml."""
import datetime, glob, importlib.util, json, os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("dor", os.path.join(ROOT, "tools", "do_rollcalls.py"))
dor = importlib.util.module_from_spec(spec); spec.loader.exec_module(dor)
from src import db, drain
ES = dor.load_taxonomy(os.path.join(ROOT, "probe", "terms-do.yaml"))
WL = dor.empty_watchlist()
conn = db.init_db(db.connect(os.path.join(ROOT, "probe", "scratch-full.db")))
today = datetime.date.today().isoformat()
n = 0
for f in glob.glob(os.path.join(ROOT, "probe/out/pull/ini_*.json")):
    for r in json.load(open(f))["results"]:
        b = dor.parse_bill(r)
        dor.store_bill(conn, b, dor.classify_bill(ES, WL, b, {}), today); n += 1
conn.commit(); print("bills", n, flush=True)
out = dor.pull_votes(conn, dor.make_client(), today, tax=ES, wl=WL, watch={},
                     budget=drain.Budget(float(sys.argv[1]) if len(sys.argv) > 1 else 7200))
print("votes", out, flush=True)
dor.summary(conn)
