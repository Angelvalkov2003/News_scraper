"""Send HTML to Claude API and save to AI_files/. Uses Structured Outputs (schema via output_config)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_ai_extractor import BaseAiExtractor


def _build_bbc_prompt(html_content: str) -> str:
    return f"""Extract this BBC article HTML into one JSON object. Follow these rules strictly.

STRICT RULES:
- Authors: Take ONLY from the HTML (script "authors", meta, byline). Use EXACT name. author url = FULL absolute URL (https://...) when there is a link, never relative. If no author, null.
- Categories: Take ONLY from meta article:section or section links. Exact name. url = FULL absolute URL only (e.g. https://www.bbc.com/...), never relative paths. If none, null.
- Tags: Set ONLY if the article has tags explicitly shown in a dedicated place (e.g. "İlgili Konular" / topic links). If there is no dedicated tags section, use null. Do not invent tags.
- Title: Exact headline from <h1> or og:title/meta title (strip site suffix like " - BBC News Türkçe" if you want only the headline).
- document_date: ISO 8601 from meta article:published_time or datePublished only.
- Body text: Copy paragraph and heading text EXACTLY from the HTML, in the SAME order as in the document. Do NOT paraphrase, summarize, or merge paragraphs. Do NOT add text that is not in the HTML. Each <p> → one paragraph component; each <h1>-<h6> → one heading component. Preserve **bold** and *italic* markdown as in the source. Do not mix up or reorder content from different parts of the article.

Output: metadata (title, document_date, authors, categories, tags) and components (array of heading, paragraph, image, citation, list, table, etc.) in document order.

HTML:
{html_content}"""


class BbcAiExtractor(BaseAiExtractor):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def build_prompt(self, html_content: str) -> str:
        return _build_bbc_prompt(html_content)


if __name__ == "__main__":
    BbcAiExtractor().main()
