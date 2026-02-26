"""
Send Ekonomi Gazetesi article HTML to OpenAI/Anthropic API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.ekonomigazetesi.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_ekonomigazetesi_prompt(html_content: str) -> str:
    return f"""Extract this Ekonomi Gazetesi (ekonomigazetesi.com) article HTML into one JSON object.

STRICT RULES:

Metadata:
- Title: from h1.s-title (article headline).
- document_date: from time[datetime] (e.g. "2026-02-11 14:08:00"). Output ISO 8601 (e.g. 2026-02-11T14:08:00+03:00).
- Authors: IMPORTANT – If the first paragraph inside .entry-content is a short line in <strong> that looks like a byline (e.g. "ERHAN BEDİR/BURSA", "ALİ FUAT GÜRLE/ANKARA" – name and place, often with /), put that exact text in metadata.authors as [{{"name": "<exact text>", "url": null}}]. Do NOT add that paragraph as a component in the body. If there is no such byline paragraph, authors can be null.
- Categories: from .p-categories a or breadcrumb links (e.g. Şehir). Use name and full URL ({BASE_URL}/...). Skip "Ekonomi Gazetesi" if home.
- Tags: if present; otherwise null.

Components – ORDER IS FIXED (do not put the image at the end):
1. FIRST: Tagline/subtitle from h3.s-tagline as a single heading (type "heading", level 2). If present, this must be the first component.
2. SECOND: Lead image from .s-feat (one image with url; optional description/caption from img alt or data). This must come right after the tagline heading, not at the end of the article.
3. THIRD: Body from .entry-content only, in document order: each p → paragraph (except skip the first p if it is the byline – see Authors above); each h2–h6 → heading; blockquote → citation; images inside body → image. Preserve **bold**, *italic*, [text](url). Skip .ruby-table-contents, .entry-bottom, share sections. Do NOT paraphrase; copy text exactly.

So the order is always: [tagline heading] → [lead image] → [paragraphs and other body components]. Never put the lead image last.

Output: metadata + components in this exact order. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class EkonomiGazetesiAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_ekonomigazetesi_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    EkonomiGazetesiAiExtractor().main()
