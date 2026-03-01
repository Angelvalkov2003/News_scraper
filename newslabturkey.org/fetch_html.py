"""
Fetch article HTML from www.newslabturkey.org and save to HTML_files/.
Extracts only the main article block: <div class="elementor-widget-wrap elementor-element-populated"> that contains h1.entry-title and .entry-content.
Run from newslabturkey.org folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_newslabturkey(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # The article is inside the elementor-widget-wrap that contains entry-title and entry-content
    for div in soup.find_all("div", class_=True):
        c = div.get("class") or []
        cls = " ".join(c) if isinstance(c, list) else c
        if "elementor-widget-wrap" not in cls or "elementor-element-populated" not in cls:
            continue
        if div.find("h1", class_=lambda c: c and "entry-title" in (c if isinstance(c, str) else " ".join(c))) and div.find("div", class_=lambda c: c and "entry-content" in (c if isinstance(c, str) else " ".join(c))):
            return (
                '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
                + str(div)
                + "</body></html>"
            )
    return html


class NewslabturkeyHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_newslabturkey(html)

    def url_to_slug(self, url: str) -> str:
        """newslabturkey.org/2026/01/26/slug-name/ -> slug-name"""
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].split("/")
        return path[-1] if path else "page"


if __name__ == "__main__":
    NewslabturkeyHtmlFetcher().main()
