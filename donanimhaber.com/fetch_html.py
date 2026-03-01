"""
Fetch article HTML from www.donanimhaber.com and save to HTML_files/.
Extracts only the article block: <main class="icerik detail" ...> (data-title, data-id, article content).
Run from donanimhaber.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_donanimhaber(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find(
        "main",
        class_=lambda c: c and "icerik" in (c if isinstance(c, str) else " ".join(c)) and "detail" in (c if isinstance(c, str) else " ".join(c)),
    )
    if main:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            + str(main)
            + "</body></html>"
        )
    return html


class DonanimhaberHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_donanimhaber(html)

    def url_to_slug(self, url: str) -> str:
        """donanimhaber.com/slug--201932 -> slug--201932 (last path segment)"""
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].split("/")
        return path[-1] if path else "page"


if __name__ == "__main__":
    DonanimhaberHtmlFetcher().main()
