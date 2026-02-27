"""
Send Ajansspor article HTML to OpenAI/Anthropic API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://ajansspor.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_ajansspor_prompt(html_content: str) -> str:
    return f"""Extract this Ajansspor (ajansspor.com) article HTML into one JSON object.

PARSER LOGIC (follow exactly):

1) CATEGORIES – from breadcrumb only (NOT from .news-tags):
   - Find <section class="breadcrumb">. Inside it find the <div class="d-flex flex-row align-items-center"> that contains: <a href="/">, <a href="/kategori/...">, and a <span> (the article title).
   - Categories = ONLY the <a> elements inside that div, in document order. Each: {{"name": "<link text>", "url": "{BASE_URL}" + href}}.
   - Include: the link with href="/" (e.g. "Spor Haberleri") and the link(s) with href="/kategori/..." (e.g. "Futbol"). Do NOT include the <span> (it repeats the article title).
   - Example result: categories = [{{"name": "Spor Haberleri", "url": "{BASE_URL}/"}}, {{"name": "Futbol", "url": "{BASE_URL}/kategori/16/futbol"}}]. Usually 2 items.
   - If there is no such breadcrumb section in the HTML, use categories = [{{"name": "Spor Haberleri", "url": "{BASE_URL}/"}}] plus the first .news-tags link if needed, so categories stay section path (Spor Haberleri, section), not the full tag list.

2) TAGS – from .news-tags only (different from categories):
   - Find <div class="news-tags"> (often inside <div class="d-flex flex-row align-items-center justify-between"> in the news header).
   - Tags = every <a href="..."> inside .news-tags: {{"name": "<link text>", "url": "{BASE_URL}" + href}}.
   - Example: tags = [{{"name": "Futbol", "url": "..."}}, {{"name": "Şampiyonlar Ligi", "url": "..."}}, {{"name": "Galatasaray", "url": "..."}}]. Can be 3 or more items.
   - Do NOT put .news-tags content into metadata.categories. Categories and tags are different; categories = breadcrumb path, tags = topic tags from .news-tags.

Metadata:
- Title: from h1.
- document_date: from .news-date or time[datetime]. Output ISO 8601 (e.g. 2026-02-11T14:55:00+03:00).
- Authors: from <a class="author-name"> (name + href to editor page).
- Categories: as in step 1 (breadcrumb <a> only, no <span>, no .news-tags).
- Tags: as in step 2 (.news-tags <a> only).

Components – in document order:
1. Lead/summary paragraph if present (first short paragraph under title).
2. Body: each h2 → heading (level 2); each p → paragraph; blockquote → citation; images → image (url; optional description/caption). Preserve **bold**, *italic*, [text](url). Do NOT paraphrase; copy text exactly.
3. Skip: share buttons, "Abone Ol", "Okuma süresi", related-articles lists, ads.

Output: metadata + components. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class AjanssporAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_ajansspor_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    AjanssporAiExtractor().main()
