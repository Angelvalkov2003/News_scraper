"""
Fetch article HTML from finans.mynet.com and save to HTML_files/.
Keep ONLY the article block: <div class="detail-content-box ng-detail-content-box" property="articleBody">.
Minimal head (charset + meta for date, author, title) is preserved for parser/AI.
Run from finans.mynet.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher

_META_NAMES = ("datePublished", "dateModified", "articleAuthor", "articleSection")
_META_PROPERTIES = ("article:published_time", "article:modified_time", "article:author", "article:section", "og:title")


def _build_minimal_head(soup: BeautifulSoup) -> str:
    parts = ['<head><meta charset="utf-8">']
    head = soup.find("head")
    if head:
        for meta in head.find_all("meta"):
            name = (meta.get("name") or meta.get("property") or "").strip()
            if name in _META_NAMES or name in _META_PROPERTIES:
                parts.append(str(meta))
    parts.append("</head>")
    return "".join(parts)


def _extract_article_only_finans_mynet(html: str) -> str:
    """Keep only div.detail-content-box with property=articleBody; minimal head for metadata."""
    soup = BeautifulSoup(html, "html.parser")
    content_box = soup.find(
        "div",
        class_=lambda c: c and "detail-content-box" in (c if isinstance(c, str) else " ".join(c)),
        attrs={"property": "articleBody"},
    )
    if not content_box:
        return html
    head_str = _build_minimal_head(soup)
    body_content = str(content_box)
    return f"<!DOCTYPE html><html>{head_str}<body>{body_content}</body></html>"


class FinansMynetHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_finans_mynet(html)


if __name__ == "__main__":
    FinansMynetHtmlFetcher().main()
