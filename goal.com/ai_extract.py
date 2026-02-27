"""
Send Goal.com article HTML to OpenAI/Anthropic API; output to AI_files/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor

BASE_URL = "https://www.goal.com"


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def _build_goal_prompt(html_content: str) -> str:
    return f"""Extract this Goal.com (goal.com/tr) article HTML into one JSON object.

The HTML is only the main article wrapper: <main> containing <article> (poster image, meta, title, tag list, teaser, body).

Metadata:
- Title: from h1 (data-testid="article-title" or class containing article_title).
- document_date: from <time datetime="...">. Output ISO 8601 (e.g. 2026-02-11T11:42:54+00:00).
- Authors: from the author span (data-testid="author-link" or class containing "author"); name and URL from parent <a> if present.
- Categories: null (Goal.com uses tags).
- Tags: from <div class="fco-scrollable-tag-list">: inside it each <div class="fco-tag-button-container"> has an <a class="fco-tag-button fco-tag-button--link" href="...">. Use the text from <span class="fco-tag-button-text"> as name; url = "{BASE_URL}" + href. Example: [{{"name": "Galatasaray", "url": "{BASE_URL}/tr/takım/galatasaray/..."}}, {{"name": "A. Wenger", "url": "..."}}, {{"name": "O. Buruk", "url": "..."}}, {{"name": "Transfers", "url": "..."}}].

Components – in document order:
1) Lead image:
   - From .article_poster (img in article_poster / media_poster): type "image", url; optional description from alt.

2) Teaser:
   - From p with data-testid="article-teaser" or class article_teaser → one paragraph at the start of components.

3) Main body + gallery/list slides – DO NOT STOP AFTER FIRST SECTION:
   - Main body: from the first [data-testid="article-body"] / .article-body_body immediately under the header/teaser: each p → "paragraph"; each h2/h3/h4 → "heading" (with level 2/3/4); images inside → "image".
   - Gallery/list slides: many Goal.com articles are built as a list:
       * Find <ul class="list_slides__...">.
       * For each <li class="standard-slide_slide__..."> in document order:
           - Optional image: <div class="media_poster__..."> with <img> → add an "image" component (url; description from alt).
           - Slide heading: <h2 class="headline_headline__..."> → "heading" (level 2) with that text.
           - Slide body: inside a nested <div class="article-body_body__ASOmp body" data-testid="article-body">, each <p> → "paragraph".
   - Include ALL such slides until the end (e.g. sections like "Frank kalacağına 'emin'di", "Frank'in Spurs'taki kötü performansı", "Sırada ne var?") and ALL paragraphs inside them.

4) Styling and links:
   - Preserve **bold**, *italic*, and [text](url) exactly as in the HTML where possible. Do NOT paraphrase or shorten text; copy it verbatim.

5) Skip non-article elements:
   - Skip: .fco-fc-video-player, .fco-twitter-embed, .fco-match-recirculation, .open-web-ad, ad slots, comments widgets, "Most Read" widgets, unrelated sidebars.

Output: metadata + components. Omit optional keys when no value.

Article HTML:

{html_content}
"""


class GoalAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_base_url(self) -> str:
        return BASE_URL

    def build_prompt(self, html_content: str) -> str:
        return _build_goal_prompt(html_content)

    def post_process_output(self, data: dict) -> dict:
        return _strip_nulls_for_schema(data)


if __name__ == "__main__":
    GoalAiExtractor().main()
