"""
Send Think with Google (business.google.com) article HTML to OpenAI/Anthropic API; output to AI_files/.
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://business.google.com"


def _extract_main_only(html_content: str) -> str:
    """Keep only <main id="page-content"> to stay under API context limits."""
    soup = BeautifulSoup(html_content, "html.parser")
    main = soup.find("main", id="page-content", class_=lambda c: c and "simple-article" in (c if isinstance(c, str) else " ".join(c)))
    if main:
        return str(main)
    return html_content


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_prompt(html_content: str) -> str:
    html_content = _extract_main_only(html_content)
    return f"""Extract this Think with Google (business.google.com) article HTML into one JSON object.

The HTML below is <main id="page-content" class="simple-article"> only (no head/scripts).

Metadata:
- Title: from h1 inside .simple-article-hero (class simple-article-hero__headline).
- document_date: from .simple-article-hero__article-info (e.g. "February 2026"); use ISO date if possible (e.g. 2026-02-01T00:00:00+00:00).
- Authors: from .simple-article-hero__article-attribution .author-list-item (name only; url can be null).
- Categories and tags: leave null if not present.

Components – in document order. Output under "components": {{ "components": [ ... ] }}.
1. One "heading" (level 1) with the article title.
2. From .simple-article__body: each <p> → "paragraph" (preserve **bold**, *italic*, [text](url)); each <h3> → "heading" (level 3).
3. For image blocks (e.g. .ion-article-data-chart, picture/img): emit "image" with url (from img src), optional description (alt), optional caption (from .glue-caption).
4. For video blocks (.glue-ambient-video or <video><source src="...">): emit "video" with url (from source src), optional caption (from .glue-caption).
5. Skip: .ion-article-spotlight (author blurb at end), social share, return-to-top.

Return ONLY valid JSON. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class BusinessGoogleAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_prompt(html_content)

    def _build_fallback_prompt(self, html_content: str, schema_raw: str) -> str:
        """Use only <main id="page-content"> to stay under OpenAI context limit."""
        html_content = _extract_main_only(html_content)
        return super()._build_fallback_prompt(html_content, schema_raw)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    BusinessGoogleAiExtractor().main()
