"""
Send HTML (article.post.post-news) to Anthropic (Claude) API; output to AI_files/.
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


def _build_nefes_prompt(html_content: str) -> str:
    return f"""Extract this Nefes Gazetesi article HTML into one JSON object. The HTML is only the main article block (article.post.post-news).

STRICT RULES:
- Title: from header h1 only.
- document_date: from .post-time time[datetime] (ISO 8601). Use exact value.
- Authors: from .post-reporter a. name = link text, url = FULL absolute URL (https://www.nefes.com.tr/...). If no link, url: null.
- Categories: from .breadcrumb a (skip "Nefes Gazetesi"). name = link text, url = FULL absolute URL.
- Tags: from .post-topics a only. name = link text, url = FULL absolute URL. If no post-topics, null.
- Components: in order. (1) Lead image from figure.post-image img (url, alt → description). (2) Then header h2 as heading level 2 (summary). (3) Then walk div.post-content: each p → paragraph (preserve **bold** and *italic* and [text](url) links), each h2–h6 → heading, each blockquote → citation (citation_text). Skip div.adpro, div.related-news, div.desktop-ad. Do NOT paraphrase; copy text exactly. Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


class NefesAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return "https://www.nefes.com.tr"

    def build_prompt(self, html_content: str) -> str:
        return _build_nefes_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    NefesAiExtractor().main()
