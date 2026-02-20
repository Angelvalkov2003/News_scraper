"""
Send HTML (div.o-article-newsy__main) to Anthropic (Claude) API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_euronews_prompt(html_content: str) -> str:
    return f"""Extract this Euronews Türkçe article HTML into one JSON object. The HTML is only the main article block (div.o-article-newsy__main).

STRICT RULES:
- Title: from h1.c-article-redesign-title only.
- document_date: from .c-article-publication-date time[datetime] (ISO 8601) or data-timestamp (Unix → ISO). Use exact value.
- Authors: from .c-article-contributors (e.g. "By Euronews" → name "Euronews", url null). Only what is in the HTML.
- Categories: from breadcrumbs .c-article-breadcrumbs__link (skip "Ana Sayfa"). name = link text, url = FULL absolute URL (https://tr.euronews.com/...).
- Tags: from .c-tags-list a only. name = link text, url = FULL absolute URL. If no tags section, null.
- Components: in order. (1) Lead image from .c-article-image-video img (url, alt → description, caption from .c-article-caption__text). (2) Then h2.c-article-summary as heading level 2. (3) Then walk .c-article-content.js-article-content: each p → paragraph (preserve **bold** and *italic*), each h2–h6 → heading, each div.widget with figure img → image (url, description from alt, caption from widget__captionText). Skip .c-ad, share, comments, "Bu haberler de ilginizi çekebilir", outbrain, vuukle. Do NOT paraphrase; copy text exactly. Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


BASE_URL = "https://tr.euronews.com"


class EuronewsAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_euronews_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    EuronewsAiExtractor().main()
