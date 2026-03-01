"""
Send Sporx article HTML to OpenAI/Anthropic API; output to AI_files/.
HTML: ul.breadcrumb + div.pg-left.wide-682 (#titleheadline, #haberimg, #haberbody).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.sporx.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_sporx_prompt(html_content: str) -> str:
    return f"""Extract this Sporx (sporx.com) article HTML into one JSON object.

=== REQUIRED: components array MUST start with these 3 items in this exact order ===
1) Title as heading level 1 (from h1#habertitle).
2) Summary as heading level 2 (from h2#haberheadline; ignore inner #admdiv).
3) Lead image from #haberimg img (url, description from alt, optional caption from the div overlay at bottom).

Then all body paragraphs from #habericBody div.no-select (text split by <br><br>). Preserve **bold**, *italic*, [text](url).

=== HTML structure ===
- ul.breadcrumb: categories = each li.breadcrumb-item that has an <a>: name from span[itemprop="name"], url = full href. Skip the last li (article title, no link).
- #titleheadline: h1#habertitle (title), h2#haberheadline (summary, may contain <b>).
- #habershare: #haberdate span (date e.g. "11 Şubat 2026 14:58" → ISO 8601), .haberkaynak = full source line (e.g. "Haber:AA,Fotoğraf:AA" or "Haber: Sporx.com dış haberler, Fotoğraf: Imago").
- #haberimg: one img (lead image), optional caption in the overlay div.
- #haberbody / #habericBody: div.no-select contains article text with <br><br> between paragraphs. Skip .newsBodyHead, share buttons, comments, "EN ÇOK OKUNANLAR", ads.

Metadata: title from #habertitle; document_date from #haberdate (Turkish date → ISO); authors = ONE object with the FULL text from .haberkaynak as "name" (e.g. "Haber:AA,Fotoğraf:AA" or "Haber:Sporx.com dış haberler,Fotoğraf:Imago") – do NOT shorten to just "AA" or "Imago"; copy the entire haberkaynak text. categories from breadcrumb (name + full URL {BASE_URL}/...). Omit optional keys when no value.

Return ONLY valid JSON matching scraped_article_json_schema.

Article HTML:

{html_content}
"""


class SporxAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_sporx_prompt(html_content)

    def _build_fallback_prompt(self, html_content: str, schema_raw: str) -> str:
        """Used by OpenAI; include site-specific rules so title + h2 + image are not skipped."""
        comp = self.get_component_instructions()
        return self.build_prompt(html_content) + f"""

{comp}

JSON Schema (components MUST start with: 1=heading title, 2=heading level 2 summary, 3=lead image, then paragraphs):
{schema_raw}
"""

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    SporxAiExtractor().main()
