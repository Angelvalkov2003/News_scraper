"""
Fetch article HTML from www.kamudanhaber.net and save to HTML_files/ only the article block:
<div class="infinite-item d-block"> (no navbar, sidebar, comments, related).
Run from kamudanhaber.net folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_kamudanhaber(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("div", class_=lambda c: c and "infinite-item" in (c if isinstance(c, str) else " ".join(c)) and "d-block" in (c if isinstance(c, str) else " ".join(c)))
    if not main:
        return html
    wrap = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>{str(main)}</body></html>'
    return wrap


class KamudanhaberHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_kamudanhaber(html)


if __name__ == "__main__":
    KamudanhaberHtmlFetcher().main()
