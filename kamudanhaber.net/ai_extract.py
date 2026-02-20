"""
Send HTML (div.infinite-item.d-block) to Anthropic (Claude) API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.kamudanhaber.net"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_kamudanhaber_prompt(html_content: str) -> str:
    return f"""Extract this Kamudanhaber article HTML into one JSON object. The HTML is only the main article block (div.infinite-item.d-block).

STRICT RULES:
- Title: from h1.headline (or [itemprop="headline"]) only.
- document_date: from .meta-author time (text like "11.02.2026 - 14:28" or time[datetime]). Output ISO 8601 (e.g. 2026-02-11T14:28:00+03:00).
- Authors: if present in the page; otherwise null.
- Categories: from ALL links in ol.breadcrumb (nav.meta-category ol.breadcrumb a). Both items are categories: the first (e.g. Haberler) and the second (e.g. Güncel). Include every breadcrumb link: name = link text, url = FULL absolute URL ({BASE_URL}/...).
- Tags: from .news-tags a only. name = link text, url = FULL absolute URL. If none, null.
- Components: in order. (1) Lead image from .news-section .col-lg-8 .inner img (url, alt → description). (2) Then h2.description as heading level 2 (summary). (3) Then walk div.article-text[property="articleBody"]: each p → paragraph (preserve **bold**, *italic*, [text](url)); each h2–h6 → heading; each blockquote → citation (citation_text). Skip div[id^="ad_"], .ad-placeholder, div.post-flash, .editors-choice, .related-news, #reactions, #comments, script. Do NOT paraphrase; copy text exactly. Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


class KamudanhaberAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_kamudanhaber_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    KamudanhaberAiExtractor().main()
