"""
Send Webtekno article HTML to OpenAI/Anthropic API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.webtekno.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_webtekno_prompt(html_content: str) -> str:
    return f"""Extract this Webtekno (webtekno.com) article HTML into one JSON object.

The HTML is the full page with header/sidebar/masthead ad removed. Main article is in .detail-content.

Metadata:
- Title: from h1 inside .detail-content.
- document_date: from <time datetime="..."> (e.g. 2026-02-11T11:25:31+03:00).
- Authors: from <a href="/yazar/..."> in .author-name; name and url.
- Categories: from .page-detail-breadcrumb: each <a href="..."> in order (e.g. Webtekno, Ürün); do not include the current page (span only).
- Tags: from .content-tags-list: each <a href="/konu/..."> (e.g. Microsoft, Windows).

Components – STRICT ORDER. Output under "components": {{ "components": [ ... ] }}.

Step 1 – Excerpt: one "heading" (level 2) with text from .excerpt h2.
Step 2 – Lead image (if present): one "image" from .detail-content-media img (url from src or data-src, optional description from alt).
Step 3 – VIDEO (mandatory when present): Search the ENTIRE HTML for ANY YouTube embed and add a "video" component:
  - Search for: data-video-id="...", or iframe src containing youtube.com/embed/, or style="...i.ytimg.com/vi_webp/XXXX/maxresdefault...".
  - Extract the 11-character video ID (e.g. umawHGyuVHA).
  - Add exactly: {{"type":"video","properties":{{"url":"https://www.youtube.com/watch?v=VIDEO_ID","thumbnail_image_url":"https://i.ytimg.com/vi_webp/VIDEO_ID/maxresdefault.webp"}}}}.
  - If the video is at the top of the article (before .detail-content-body), place this component RIGHT AFTER the excerpt heading (or after lead image). If it is inside the body, place it between paragraphs where it appears.
  - If you find NO YouTube embed anywhere, omit the video component. If you find one or more, include one "video" component per embed in order.
Step 4 – Body: from .detail-content-body, each <p> → "paragraph", each <h2> → "heading" (level 2). Preserve **bold**, *italic*, [text](url). If a block contains an image, emit "image" then "paragraph" for the text.
Step 5 – Skip: .content-adv-col, comment sections, ad divs.

EXAMPLE – For a page that has a top video and then text, components must look like this (replace VIDEO_ID with the id from the HTML, e.g. umawHGyuVHA):
  "components": {{ "components": [
    {{ "type": "heading", "properties": {{ "text": "Excerpt text from .excerpt h2", "level": 2 }} }},
    {{ "type": "video", "properties": {{ "url": "https://www.youtube.com/watch?v=VIDEO_ID", "thumbnail_image_url": "https://i.ytimg.com/vi_webp/VIDEO_ID/maxresdefault.webp" }} }},
    {{ "type": "paragraph", "properties": {{ "text": "First paragraph..." }} }},
    {{ "type": "paragraph", "properties": {{ "text": "Second paragraph..." }} }}
  ] }}

Return ONLY valid JSON. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class WebteknoAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_webtekno_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    WebteknoAiExtractor().main()
