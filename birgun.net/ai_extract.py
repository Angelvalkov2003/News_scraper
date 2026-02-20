"""
Send article HTML to Claude API and save result to AI_files/. Tries Structured Outputs; on schema-too-large falls back to prompt+parse.
Run from birgun.net folder: python ai_extract.py <file.html> [file2.html ...]
"""

import sys
from pathlib import Path

# Allow importing base package from project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.birgun.net"


def _resolve_birgun_url(url: str | None) -> str | None:
    """Convert relative birgun URL to full absolute URL."""
    if not url or not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if url.startswith("https://"):
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    if not url.startswith("http"):
        return BASE_URL + "/" + url.lstrip("/")
    return url


def _build_birgun_prompt(html_content: str) -> str:
    return f"""Extract this birgun.net article HTML into one JSON object. Follow these rules strictly.

STRICT RULES:
- Authors: Take ONLY from the HTML (meta, byline). EXACT name. When the author has a link (e.g. <a href="/profil/...">), set url to the FULL absolute URL: https://www.birgun.net/profil/author-slug (NEVER relative like /profil/...). If no author link, url: null.
- Categories: Take ONLY from section/category links or meta. name = exact link text. url MUST be FULL absolute URL: https://www.birgun.net/kategori/guncel-7 — NEVER write only /kategori/guncel-7 or relative path. If no category link, url: null.
- Tags: Only if the article has a dedicated tag section. For each tag link, url MUST be FULL: https://www.birgun.net/etiket/etiket-slug-123 — NEVER only /etiket/.... If no tag link, url: null.
- Title: Exact headline (h1 or meta).
- document_date: ISO 8601 from meta only.
- Body text: Copy EXACTLY in order; one <p> → one paragraph, one heading → one heading. Do NOT paraphrase. Skip "Sıradaki Haber" and everything after.

URL RULE: Every url field (author, category, tag) must start with https://www.birgun.net/ — never output relative paths like /kategori/... or /etiket/... or /profil/...

Output: metadata + components in document order.

Article HTML:
{html_content}"""


def _metadata_urls_to_absolute(obj):
    """Recursively ensure all url fields in metadata (authors, categories, tags) are full URLs."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_metadata_urls_to_absolute(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "url" and isinstance(v, str):
                out[k] = _resolve_birgun_url(v) or v
            else:
                out[k] = _metadata_urls_to_absolute(v)
        return out
    return obj


class BirgunAiExtractor(BaseAiExtractor):
    """Birgun.net AI extractor: site-specific prompt and fallback."""

    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_birgun_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        """Ensure all metadata URLs (author, category, tag) are full https://www.birgun.net/... URLs."""
        if isinstance(data, dict) and "metadata" in data:
            data = dict(data)
            data["metadata"] = _metadata_urls_to_absolute(data["metadata"])
        return data


if __name__ == "__main__":
    BirgunAiExtractor().main()
