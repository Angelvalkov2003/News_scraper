"""
Send Fintech Dünyası article HTML to Anthropic (Claude) API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.fintechdunyasi.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_fintechdunyasi_prompt(html_content: str) -> str:
    return f"""Extract this Fintech Dünyası (fintechdunyasi.com) article HTML into one JSON object.

STRICT RULES:
- Title: from the main h1 (article headline).
- document_date: from date on the page (e.g. "28 Nisan 2025" or "Fintech Dünyası 28 Nisan 2025"). Output ISO 8601 (e.g. 2025-04-28T12:00:00+03:00). If only date without time, use noon 12:00.
- Authors: if present; otherwise null.
- Categories: from breadcrumb links (e.g. Anasayfa, Fintech Dünyası e-Dergi, Melek Yatırımcılar & VC'ler). Use name and full URL ({BASE_URL}/...). Skip "Anasayfa" if you prefer.
- Tags: from tag links at bottom (e.g. Sedat Avşar, Fintech Dünyası, fintech, girişimcilik). name and url (full URL).
- Components: in document order. (1) Lead image if present. (2) The first styled paragraph (e.g. <p class="has-text-color has-background"> with the opening quote in em/strong) MUST be type "citation" with "citation_text" = that paragraph text and optionally "author_text" = the next paragraph if it is only the author/speaker line (e.g. "Techventure VC Kurucu Ortağı Sedat Avşar"). (3) Blockquotes and any other quotes as citation (citation_text, optional author_text). (4) Paragraphs as paragraph (preserve **bold**, *italic*, [text](url); do NOT duplicate asterisks: **T****ext** should be **Text**). (5) Headings h2–h6 as heading with level. (6) Lists: items with indent, bullet, content (content: single markdown string, no extra ** from split <strong>). (7) Images with url, optional description/caption. Do NOT paraphrase; copy text exactly. Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


class FintechDunyasiAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_fintechdunyasi_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    FintechDunyasiAiExtractor().main()
