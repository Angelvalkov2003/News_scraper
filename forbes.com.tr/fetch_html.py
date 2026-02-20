"""
Fetch article HTML from www.forbes.com.tr and save to HTML_files/ only:
- First <article class="col col7"> (main article body)
- <div class="col col10"> (breadcrumb nav + h1 title)
Run from forbes.com.tr folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_forbes(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article", class_=lambda c: c and "col" in (c if isinstance(c, str) else " ".join(c)) and "col7" in (c if isinstance(c, str) else " ".join(c)))
    col10 = soup.find("div", class_=lambda c: c and "col" in (c if isinstance(c, str) else " ".join(c)) and "col10" in (c if isinstance(c, str) else " ".join(c)))
    parts = []
    if col10:
        parts.append(str(col10))
    if article:
        parts.append(str(article))
    if not parts:
        return html
    body_content = "\n".join(parts)
    wrap = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><div class="forbes-extract">{body_content}</div></body></html>'
    return wrap


class ForbesHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_forbes(html)


if __name__ == "__main__":
    ForbesHtmlFetcher().main()
