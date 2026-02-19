"""
Fetch article HTML from birgun.net and save to HTML_files/ only the article content:
from div.contentdetail (H1 title and body) up to before the first "Sıradaki Haber". No navbar, menu, ads.
Run from birgun.net folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

# Allow importing base package from project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from base.base_fetcher import BaseHtmlFetcher

# Meta tags used by parser for metadata (document_date, authors, categories, tags)
_META_NAMES = ("datePublished", "articleAuthor", "articleSection", "keywords", "ptime")
_META_PROPERTIES = ("datePublished",)


def _build_minimal_head(soup: BeautifulSoup) -> str:
    """Only meta tags for document_date, authors, categories, tags – no scripts/styles."""
    parts = ['<head><meta charset="utf-8">']
    head = soup.find("head")
    if not head:
        return '<head><meta charset="utf-8"></head>'
    for meta in head.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").strip()
        if name in _META_NAMES or name in _META_PROPERTIES:
            parts.append(str(meta))
    parts.append("</head>")
    return "".join(parts)


def _extract_article_only_birgun(html: str) -> str:
    """
    Keep only article content: div.contentdetail (from H1 up to before "Sıradaki Haber").
    In head write only the meta tags needed for metadata – no long scripts.
    """
    soup = BeautifulSoup(html, "html.parser")
    head_str = _build_minimal_head(soup)
    contentdetail = soup.find(
        "div",
        class_=lambda c: c and "contentdetail" in (c if isinstance(c, str) else " ".join(c)),
    )
    if not contentdetail:
        return html
    stop_text = contentdetail.find(string=lambda t: t and "Sıradaki Haber" in t)
    if stop_text:
        node = stop_text.parent
        while node and node.parent != contentdetail:
            node = node.parent
        if node and node.parent == contentdetail:
            for s in list(node.next_siblings):
                s.decompose()
            node.decompose()
    return (
        "<!DOCTYPE html><html>"
        + head_str
        + "<body>"
        + str(contentdetail)
        + "</body></html>"
    )


class BirgunHtmlFetcher(BaseHtmlFetcher):
    """Birgun.net HTML fetcher: extracts div.contentdetail, stops at Sıradaki Haber."""

    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_birgun(html)


if __name__ == "__main__":
    BirgunHtmlFetcher().main()
