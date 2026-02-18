"""Temp script to inspect __NEXT_DATA__ structure."""
import json
import re
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
html_path = SITE_DIR / "HTML_files/2000-2022-arasinda-toplanan-deprem-vergisi-ne-kadar.html"
html = html_path.read_text(encoding="utf-8")
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', html)
if not m:
    print("No __NEXT_DATA__")
    exit(1)
data = json.loads(m.group(1))
(SITE_DIR / "Parsed_files/_next_keys.txt").write_text(json.dumps(list(data.keys()), indent=2), encoding="utf-8")
pp = data.get("props", {}).get("pageProps", {})
if isinstance(pp, dict):
    (SITE_DIR / "Parsed_files/_pageProps_keys.txt").write_text(json.dumps(list(pp.keys()), indent=2), encoding="utf-8")
    # Look for article/content/body
    for k in ["article", "content", "post", "bulten", "data"]:
        if k in pp:
            val = pp[k]
            if isinstance(val, dict):
                (SITE_DIR / f"Parsed_files/_pp_{k}_keys.txt").write_text(json.dumps(list(val.keys()), indent=2), encoding="utf-8")
            elif isinstance(val, str) and len(val) > 100:
                (SITE_DIR / f"Parsed_files/_pp_{k}_preview.txt").write_text(val[:3000], encoding="utf-8")
    content = pp.get("content")
    if isinstance(content, dict) and "contentBlocks" in content:
        blocks = content["contentBlocks"]
        out = (SITE_DIR / "Parsed_files" / "_contentBlocks_sample.txt")
        sample = blocks[:4] if isinstance(blocks, list) else [blocks]
        out.write_text(json.dumps(sample, indent=2, ensure_ascii=False)[:8000], encoding="utf-8")
        # Debug: type of contentBlocks and first element
        info = ["contentBlocks type: " + str(type(blocks)), "len: " + str(len(blocks) if isinstance(blocks, list) else "N/A")]
        if isinstance(blocks, list) and blocks:
            info.append("first el keys: " + str(list(blocks[0].keys()) if isinstance(blocks[0], dict) else type(blocks[0])))
        (SITE_DIR / "Parsed_files" / "_cb_info.txt").write_text("\n".join(info), encoding="utf-8")
else:
    (SITE_DIR / "Parsed_files/_pageProps_type.txt").write_text(str(type(pp)), encoding="utf-8")
