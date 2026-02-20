"""
Send HTML (first article.col.col7 + div.col.col10) to Anthropic (Claude) API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.forbes.com.tr"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_forbes_prompt(html_content: str) -> str:
    return f"""Extract this Forbes Türkiye article HTML into one JSON object. The HTML contains: (1) div.col.col10 with nav.icerik_nav (breadcrumb) and h1 title; (2) first article.col.col7 with the article body.

STRICT RULES:
- Title: from div.col10 h1 only (the big white title).
- document_date: from the date span inside the article (e.g. "11 Şubat 2026, 14:44"). Output ISO 8601 (e.g. 2026-02-11T14:44:00+03:00).
- Authors: if present in the article block; otherwise null.
- Categories: from nav.icerik_nav a. Include every link (e.g. Ana Sayfa/FORBES, Ekonomi). name = link text, url = FULL absolute URL ({BASE_URL}/...).
- Tags: if present; otherwise null.
- Components: in order. (1) Summary as heading level 2 from .makaledetay_spot first. (2) Lead image from .makaledetay_ust_resim (picture/img or a[href] for full image). (3) Then walk .makaledetay_yazialani: each p → paragraph (preserve **bold**, *italic*, [text](url)); each h2–h6 → heading; each blockquote → citation (citation_text). Skip .makale_paylas, .article_masthead_ad, hr. Do NOT paraphrase; copy text exactly. Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


class ForbesAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_forbes_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    ForbesAiExtractor().main()
