"""
Send HTML to Anthropic (Claude) API; output to AI_files/. Tries Structured Outputs; on schema-too-large or token limit falls back.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

MAX_HTML_CHARS = 300_000


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_dogrulukpayi_prompt(html_content: str) -> str:
    return f"""Extract this doğrulukpayi.com article HTML into one JSON object. Follow these rules strictly.

STRICT RULES:
- Authors: Take ONLY from meta or visible author. EXACT name. When there is an author link, url = FULL absolute URL (https://www.dogrulukpayi.com/...), never relative. If no link, url: null.
- Categories: Take ONLY from links to /dogrulama/, /bulten/, /dogruluk-kontrolu/ or /kategoriler/. name = exact link text. url = FULL absolute URL only (https://www.dogrulukpayi.com/...), never relative paths. If none, null.
- Tags: Set ONLY if the article page has tags explicitly shown in a dedicated place (e.g. a "Tags" / "Etiketler" section, or clear tag links/chips). If there is no such dedicated tags block, use tags: null. Do not invent or infer tags from the text.
- Title: Exact headline from the article (h1 or meta).
- document_date: ISO 8601 from meta article:published_time or datePublished only.
- Body text: Walk section.r-section.r-section-withcard in order. Copy each paragraph and heading EXACTLY as in the HTML; one element → one component. Do NOT paraphrase or merge paragraphs. Do NOT add text that is not in the HTML. Preserve **bold**, *italic* markdown. Stop at path.LogoCheck / logo/footer; do not include text after. Omit optional keys (caption, description) when empty.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


class DogrulukpayiAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return "https://www.dogrulukpayi.com"

    def build_prompt(self, html_content: str) -> str:
        if len(html_content) > MAX_HTML_CHARS:
            html_content = html_content[:MAX_HTML_CHARS] + "\n\n[... HTML truncated for API token limit ...]"
        return _build_dogrulukpayi_prompt(html_content)

    def _build_fallback_prompt(self, html_content: str, schema_raw: str) -> str:
        if len(html_content) > 200_000:
            html_content = html_content[:200_000] + "\n\n[... truncated ...]"
        return f"""Extract this doğrulukpayi.com article HTML. Return ONE valid JSON conforming to the schema below. Return ONLY JSON. STRICT: authors/categories from HTML only; copy body text EXACTLY in order.

JSON Schema:
{schema_raw}

Article HTML:
{html_content}"""

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    DogrulukpayiAiExtractor().main()
