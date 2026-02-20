"""
Send HTML (page without my-header, sc-heading-container, affiliate-sidebar) to Anthropic (Claude) API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://haber.mynet.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_mynet_prompt(html_content: str) -> str:
    return f"""Extract this Mynet (haber.mynet.com) article HTML into one JSON object. The HTML has the global header, Vitrin sc-heading-container, and affiliate-sidebar-section already removed.

STRICT RULES:
- Title: from the first h1 on the page.
- document_date: from time[datetime] (e.g. 2026-02-16T09:41:28+03:00) or from "Son Güncelleme: DD.MM.YYYY HH:MM". Output ISO 8601.
- Authors: from .author-name (strip "MYNET YAZARI" suffix). name = text, url = FULL absolute URL if link present ({BASE_URL}/... or https://www.mynet.com/...).
- Categories: from breadcrumb nav (all nav a links). name = link text, url = FULL absolute URL.
- Tags: from .tags-word a or .detail-footer-tags a. name = link text, url = FULL absolute URL. If none, null.
- Components (in this order; do not skip the lead image):
  (0) LEAD IMAGE (mandatory when present): Search for div with class "showcase-feature-box", then inside it find the img with class containing "img-responsive" (often also "lazyload" or "lazyloaded"). Take the image URL from attribute "data-original" if present and non-empty, otherwise from "src". Take "alt" as description. Output as first component: {{"type": "image", "properties": {{"url": "<url>", "description": "<alt>"}}}}. If there is no such img, skip this step.
  (1) Summary as heading level 2 from .showcase-detail-content-box h2.post-spot.
  (2) Then from .detail-content-inner (or #contextual .detail-content-inner): each p → paragraph (preserve **bold**, *italic*, [text](url)); each h2–h6 → heading; each ul li → paragraph with "• " prefix; each img → image (url, alt → description); each figure img → image. SKIP: .interest-widget-container (İlginizi Çekebilir), .content-banner-box, .detail-footer-tags, .reaction-box-wrapper, .mynet-user-reactions, #commentPostDiv, affiliate buttons. Do NOT paraphrase; copy text exactly. Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


class MynetAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_mynet_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    MynetAiExtractor().main()
