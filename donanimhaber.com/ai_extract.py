"""
Send DonanımHaber article HTML to OpenAI/Anthropic API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.donanimhaber.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_donanimhaber_prompt(html_content: str) -> str:
    return f"""Extract this DonanımHaber (donanimhaber.com) article HTML into one JSON object.

The HTML is only the main article block: <main class="icerik detail"> with data-title, .detay (title, summary), .temel-bilgi (date, category), article.post (author, section.kolon.yazi body).

Metadata:
- Title: from main[data-title] or h1.post-baslik.
- document_date: from <time datetime="..."> in .temel-bilgi (e.g. 2026-02-11T14:43:00+03:00).
- Authors: from a[rel="author"] in .editor-yan (name and full URL).
- Categories: from .temel-bilgi .kategori a (name and full URL).

Components – STRICT ORDER. DO NOT skip title or lead image.
1. TITLE (mandatory): First component: {{ "type": "heading", "properties": {{ "text": "<article title>", "level": 1 }} }}.
2. Summary: h2.surmanset as heading level 2.
3. Lead image: from figure.resim (img src or picture/source; description from figcaption or alt). Never skip.
4. Body: from section.kolon.yazi. Each figure.resim → image then paragraph (figcaption text). Each h2 → heading level 2. Each p → paragraph. Preserve **bold**, *italic*, [text](url).
5. Skip: .lnk-bkz (related article box), .lnk-kaynak (source link as separate block), .medyalar, .detay-yatay-sorgu, comments, share buttons.

Return ONLY valid JSON. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class DonanimhaberAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_donanimhaber_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    DonanimhaberAiExtractor().main()
