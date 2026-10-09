"""Sample the AN Legislativa news feed back to a cutoff date (scope probe only).
Usage: python3 tools/ve_news_crawl.py 2026-04-09  (2s throttle, raw pages archived)."""
import sys, re, time, json, gzip, html, urllib.request
from pathlib import Path
sys.path.insert(0, 'tools')
UA = "CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)"
OUT = Path('data/raw/ve-probe/news'); OUT.mkdir(parents=True, exist_ok=True)
B = "https://www.asambleanacional.gob.ve"
def get(url):
    slug = re.sub(r'[^A-Za-z0-9]+', '_', url)[-150:]
    p = OUT / (slug + '.gz')
    if p.exists(): return gzip.decompress(p.read_bytes()).decode('utf-8', 'replace')
    time.sleep(2)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            b = r.read()
    except Exception as e:
        ERR.append((url, str(e))); return ""
    p.write_bytes(gzip.compress(b)); return b.decode('utf-8', 'replace')
ERR = []
cutoff = sys.argv[1]  # YYYY-MM-DD
items = []
for page in range(1, 200):
    h = get(f"{B}/noticias?categoria=Legislativa&page={page}")
    found = re.findall(r'<a href="(https://www\.asambleanacional\.gob\.ve/noticias/[^"]+)"><h3[^>]*><b>(.*?)</b>.*?Fecha: (\d\d)/(\d\d)/(\d{4})', h, re.S)
    if not found: break
    for url, title, d, m, y in found:
        items.append({"url": url, "title": html.unescape(title).strip(), "date": f"{y}-{m}-{d}"})
    if min(f"{y}-{m}-{d}" for *_, d, m, y in found) < cutoff: break
items = [i for i in items if i["date"] >= cutoff]
for i in items:
    t = get(i["url"])
    a = t.find('Fecha:'); b = t.find('an-text-white', a)
    t = t[a:b] if a >= 0 and b > a else t
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
    i["text"] = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))
json.dump(items, open('data/raw/ve-probe/news.json', 'w'), ensure_ascii=False)
print("errors", len(ERR), ERR[:5]); print(len(items), "items", items[-1]["date"] if items else "", "pages", page)
