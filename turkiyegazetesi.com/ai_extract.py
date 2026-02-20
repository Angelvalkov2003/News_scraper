"""
Send HTML to Anthropic (Claude) API; output to AI_files/. Tries Structured Outputs; on schema-too-large falls back to prompt+parse.
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


def _build_turkiyegazetesi_prompt(html_content: str) -> str:
    return f"""Extract this Türkiye Gazetesi article HTML into one JSON object. Follow these rules strictly.

STRICT RULES:
- Authors: Take ONLY from the HTML. Look for meta article:author or articleAuthor; also look for editor block (e.g. "Editör : ESMA KARAYEL" with optional link) and add as second author with EXACT name. When the author/editor has a link (<a href="...">), use that as author url — always as FULL absolute URL (https://www.turkiyegazetesi.com.tr/...), never a relative path. If no link, url: null.
- Categories: Take ONLY from .article-category-tag or section/category links. name = exact link text (e.g. "Gündem"). url = FULL absolute URL only: e.g. https://www.turkiyegazetesi.com.tr/gundem — never use relative paths like /gundem. If none, null.
- Tags: Set ONLY if the article has tags explicitly shown in a dedicated place. If no dedicated tags section, use null. Do not invent tags.
- Title: Exact headline from the article (h1 or meta), not invented.
- document_date: ISO 8601 from meta article:published_time or datePublished only.
- Body text: Copy text EXACTLY from the HTML in the SAME order. div.article-scope > article: first media in div.article-main-image (video or image) → one component; then in div.article-content walk in order: each h1–h6 → one heading, each p → one paragraph. Do NOT paraphrase, summarize, or merge paragraphs. Do NOT add text that is not in the HTML. Preserve **bold** and *italic*. Exclude "Editör", "Paylaş", "Yorum", "ÖNERİLEN", "ÇOK OKUNANLAR" and any block after the main article. Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


class TurkiyegazetesiAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return "https://www.turkiyegazetesi.com.tr"

    def build_prompt(self, html_content: str) -> str:
        return _build_turkiyegazetesi_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    TurkiyegazetesiAiExtractor().main()
