"""Measure: English taxonomy vs proposed Spanish terms over SIL titles."""
import collections, glob, importlib.util, json, os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("dor", os.path.join(ROOT, "tools", "do_rollcalls.py"))
dor = importlib.util.module_from_spec(spec); spec.loader.exec_module(dor)
EN = dor.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
ES = dor.load_taxonomy(os.path.join(ROOT, "probe", "terms-do.yaml"))
WL = dor.empty_watchlist()
per = sys.argv[1]
show = sys.argv[2] if len(sys.argv) > 2 else None
rows = {}
for f in glob.glob(os.path.join(ROOT, "probe/out/pull/ini_%s_*.json" % per)):
    for r in json.load(open(f))["results"]:
        rows[r["numero"]] = r
print(per, "titles", len(rows))
en_hits = []; es = collections.Counter(); tier1 = 0; ours = 0; byterm = collections.Counter(); hits = []
for k, r in rows.items():
    b = dor.parse_bill(r)
    e = dor.classify_bill(EN, WL, b, {})
    if e.issue_areas: en_hits.append((k, e.issue_areas, e.matched_terms, b["title"][:100]))
    s = dor.classify_bill(ES, WL, b, {})
    if dor.on_our_ground(s.issue_areas):
        ours += 1; tier1 += s.tier == 1
        for a in s.issue_areas:
            if a != 11: es[a] += 1
        for t in s.matched_terms: byterm[t] += 1
        hits.append((k, s.issue_areas, s.tier, s.matched_terms, b["status"], b["title"][:150]))
print("EN taxonomy areas on", len(en_hits))
for h in en_hits[:15]: print("  EN", h)
print("ES on our ground (not migration only):", ours, "tier1:", tier1)
print("by area:", sorted(es.items()))
print("terms:", byterm.most_common(60))
if show:
    for h in hits:
        if show == "all" or any(str(a) == show for a in h[1]) or any(show in t for t in h[3]):
            print(" ", h)
