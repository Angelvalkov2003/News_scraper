"""
Send İklim Haber article HTML to OpenAI/Anthropic API; output to AI_files/.
HTML is the main block: div.col-mod-main (header, thumbnail, entry-content).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.iklimhaber.org"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_iklimhaber_prompt(html_content: str) -> str:
    return f"""Extract this İklim Haber (iklimhaber.org) article HTML into one JSON object.

=== REQUIRED: components array MUST start with these 3 items in this exact order ===
1) Title as heading level 1 (copy text from h1.entry-title).
2) Lead image from .herald-post-thumbnail (img src → url, alt → description; figure.wp-caption-text → caption).
3) First content block from .entry-content: if it is <h3>, output as heading level 3; if it is <p>, output as paragraph. Do NOT skip or merge.

Example start of components array:
  "components": {{ "components": [
    {{ "type": "heading", "properties": {{ "text": "<article title from h1>", "level": 1 }} }},
    {{ "type": "image", "properties": {{ "url": "<full image URL>", "description": "<alt text>" }} }},
    {{ "type": "heading", "properties": {{ "text": "<first h3 text – summary/lead>", "level": 3 }} }},
    ...then the rest of paragraphs and headings in document order
  ] }}

=== HTML structure ===
div.col-mod-main: header.entry-header (h1.entry-title, .entry-meta with date/author), .herald-post-thumbnail (img + figure.wp-caption-text), .entry-content.herald-entry-content (h3, p, h2, h4…), .meta-tags, #extras (skip these in components).

Metadata: title from h1.entry-title; document_date from span.updated (e.g. "11 Şubat 2026" → ISO 8601); authors from .fn a; categories from .meta-category a; tags from .meta-tags a[rel="tag"]. Use full URLs ({BASE_URL}/...).

Body (after the first 3 components): walk .entry-content in order. Every <h3> → heading level 3; <h2> → level 2; <h4> → level 4. Every <p> → paragraph. Preserve **bold**, *italic*, [text](url). Do NOT output "Bu yazıları da okuyabilirsiniz", related, or author box as components.

Return ONLY valid JSON. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class IklimhaberAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_iklimhaber_prompt(html_content)

    def _build_fallback_prompt(self, html_content: str, schema_raw: str) -> str:
        """Used by OpenAI; must include our site-specific rules so title + lead image + h3 are not skipped."""
        comp = self.get_component_instructions()
        return self.build_prompt(html_content) + f"""

{comp}

JSON Schema (components array MUST start with: 1=heading title, 2=lead image, 3=heading or paragraph from first body element):
{schema_raw}
"""

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    IklimhaberAiExtractor().main()
