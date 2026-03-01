"""
Send NewsLabTurkey article HTML to OpenAI/Anthropic API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.newslabturkey.org"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_newslabturkey_prompt(html_content: str) -> str:
    return f"""Extract this NewsLabTurkey (newslabturkey.org) article HTML into one JSON object.

The HTML is only the main article block: <div class="elementor-widget-wrap elementor-element-populated"> containing metadata, title, author, featured image, and .entry-content.

Metadata:
- Title: from h1.entry-title (e.g. "Türkiye'de bağımsız gazetecilik: Sürdürülebilirlik değil, hayatta kalma meselesi").
- document_date: from cmsmasters-postmeta [data-name="date"] (e.g. "26 Ocak 2026"). Output ISO 8601 like 2026-01-26T00:00:00+03:00.
- Authors: from cmsmasters-postmeta [data-name="author"] <a rel="author"> (name and full URL).
- Categories: from cmsmasters-postmeta [data-taxonomy="category"] .term (name and full URL). Omit if missing.

Components – STRICT ORDER. Output under "components": {{ "components": [ ... ] }}. DO NOT skip the title or the featured image.

1. TITLE (mandatory): Always add the article title as the FIRST component: {{ "type": "heading", "properties": {{ "text": "<title from h1.entry-title>", "level": 1 }} }}. Never omit this.
2. FEATURED IMAGE (mandatory when present): From .cmsmasters-post-featured-image .cmsmasters-widget-image__wrap img – add one "image" component (url from src; optional description from alt) as the SECOND component. Never skip the lead/featured image.
3. Body: from .entry-content. For each <p> → "paragraph" (preserve **bold**, *italic*, [text](url)). For each <h2> → "heading" (level 2). For <ul><li> → paragraphs with "• " prefix. For <hr> → paragraph "---". If a <p> contains an <img>, emit "image" then "paragraph" for the text.
4. Skip: share buttons, author box, post navigation, spacers, dividers outside entry-content.

Return ONLY valid JSON. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class NewslabturkeyAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_newslabturkey_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    NewslabturkeyAiExtractor().main()
