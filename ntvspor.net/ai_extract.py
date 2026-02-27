"""
Send NTV Spor article HTML to OpenAI/Anthropic API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.ntvspor.net"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_ntvspor_prompt(html_content: str) -> str:
    return f"""Extract this NTV Spor (ntvspor.net) article HTML into one JSON object.

The HTML is only the main article container: <div class="w-full container-infinity relative"> (breadcrumb, title, date, author, summary, and inread photo blocks).

STRICT RULES:

Metadata:
- Title: from data-title on the container or from h1 (e.g. "UEFA Uluslar Ligi kura çekimi ne zaman, saat kaçta, hangi kanalda?").
- document_date: from <time datetime="...">. Output ISO 8601 (e.g. 2026-02-11T15:03:00+03:00).
- Authors: from the <p> next to the time in the header (e.g. "Haber Merkezi"). As [{{"name": "<exact text>", "url": null}}].
- Categories: from breadcrumb nav (e.g. Spor Haberleri, Foto Galeri). Use name and full URL ({BASE_URL}/...). Skip generic "Spor Haberleri" if it is just the section.
- Tags: from the tag links at the bottom of the article if present (e.g. Uefa Uluslar Ligi, Kura Çekimi); name and full URL. Otherwise null.

Components – ORDER IS FIXED:
1. FIRST: Summary/lead from the first h2 (e.g. "UEFA Uluslar Ligi'nin 2026-2027 sezonunda...") as a single heading (type "heading", level 2).
2. THEN: For each .inread-photo-area block in document order: first the image (img src; optional description from alt), then the text from the same block (.ck-content or .text-size-18: paragraphs, subheadings). Preserve **bold**, *italic*, [text](url). Do NOT paraphrase; copy text exactly.
3. Skip: ads (dyg-ldb, taboola, dyg-mpu), "Paylaş" buttons, related-articles sidebar, breadcrumb.
4. Do not put the lead image at the end; keep the order as in the HTML (summary heading → block1 image → block1 text → block2 image → block2 text → ...).

Output: metadata + components in this exact order. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class NtvsporAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_ntvspor_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    NtvsporAiExtractor().main()
