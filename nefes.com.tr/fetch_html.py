"""
Fetch article HTML from www.nefes.com.tr and save to HTML_files/ only the article block:
<article class="post post-news"> (no navbar, sidebar, ads, comments).
Run from nefes.com.tr folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_nefes(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article", class_=lambda c: c and "post" in (c if isinstance(c, str) else " ".join(c)) and "post-news" in (c if isinstance(c, str) else " ".join(c)))
    if not article:
        return html
    wrap = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>{str(article)}</body></html>'
    return wrap


class NefesHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_nefes(html)


if __name__ == "__main__":
    NefesHtmlFetcher().main()
