"""
Fetch article HTML from www.ekonomigazetesi.com and save to HTML_files/.
Extracts only <div class="single-post-outer activated" ...> (article block: breadcrumb, header, content, sidebar).
Run from ekonomigazetesi.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_ekonomigazetesi(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    outer = soup.find("div", class_=lambda c: c and "single-post-outer" in (c if isinstance(c, str) else " ".join(c)))
    if outer:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            + str(outer)
            + "</body></html>"
        )
    return html


class EkonomiGazetesiHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_ekonomigazetesi(html)


if __name__ == "__main__":
    EkonomiGazetesiHtmlFetcher().main()
