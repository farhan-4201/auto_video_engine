"""Quick API test"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from core.pixabay_fetcher import PixabayFetcher

f = PixabayFetcher()
results = f.search(["Black Holes", "space"], "videos")
print(f"{len(results)} video results:")
for r in results[:3]:
    print(f"  id={r['id']}  {r['width']}x{r['height']}  dur={r.get('duration',0)}s  url={r['url'][:80]}...")
