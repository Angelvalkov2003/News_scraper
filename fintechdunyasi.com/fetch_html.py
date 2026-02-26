"""
Fetch article HTML from www.fintechdunyasi.com and save to HTML_files/.
Extracts only <main class="site-main ... tipi-l-8"> (article block: hero, breadcrumbs, meta, entry-content, footer, related).
Run from fintechdunyasi.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_fintechdunyasi(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # <main class="site-main tipi-xs-12 main-block-wrap block-wrap tipi-col clearfix tipi-l-8">
    main = soup.find("main", class_=lambda c: c and "site-main" in (c if isinstance(c, str) else " ".join(c)))
    if main:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            + str(main)
            + "</body></html>"
        )
    return html


class FintechDunyasiHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_fintechdunyasi(html)


if __name__ == "__main__":
    FintechDunyasiHtmlFetcher().main()
