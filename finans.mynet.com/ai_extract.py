"""
Send HTML (only div.detail-content-box with property=articleBody) to Anthropic (Claude) API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://finans.mynet.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_finans_mynet_prompt(html_content: str) -> str:
    return f"""Extract this Mynet Finans (finans.mynet.com) article HTML into one JSON object. The HTML contains only the article block (div.detail-content-box with property=articleBody): breadcrumb, h1.post-title, h2.post-spot, feature-media image, author/date, then detail-content-inner with body.

STRICT RULES:
- Title: from h1.post-title (or first h1).
- document_date: from time[datetime] or span.post-date-mobile (e.g. 11.02.2026 14:52). Output ISO 8601.
- Authors: from .author-name (strip "/ Muhabir" suffix). url = FULL absolute URL (https://www.mynet.com/profil/... or {BASE_URL}/...) when link present.
- Categories: from breadcrumb nav. name = link text, url = FULL absolute URL.
- Tags: from .tags-word a or .detail-footer-tags a. name = link text, url = FULL absolute URL. If none, null.
- Components (in order): (0) Lead image from .feature-media img (data-original or src), alt → description. (1) Summary as heading level 2 from h2.post-spot. (2) From .detail-content-inner: each p → paragraph; each h2–h6 → heading; each img → image (url, alt); each figure → image with optional figcaption. SKIP: .ng-other-news-container (İlginizi Çekebilir), .content-banner-box, .body-banner-block, .detail-footer-tags, .reaction-box-wrapper, .mynet-user-reactions, #commentPostDiv, ad containers. Copy text exactly; preserve **bold**, *italic*, [text](url). Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


class FinansMynetAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def build_prompt(self, html_content: str) -> str:
        return _build_finans_mynet_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    FinansMynetAiExtractor().main()
