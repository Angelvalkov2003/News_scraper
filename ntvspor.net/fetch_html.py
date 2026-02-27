"""
Fetch article HTML from www.ntvspor.net and save to HTML_files/.
Extracts only <div class="w-full container-infinity relative" ...> (main article container).
Run from ntvspor.net folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_ntvspor(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    outer = soup.find(
        "div",
        class_=lambda c: c and "container-infinity" in (c if isinstance(c, str) else " ".join(c)),
    )
    if outer:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            + str(outer)
            + "</body></html>"
        )
    return html


class NtvsporHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_ntvspor(html)

    def url_to_slug(self, url: str) -> str:
        """NTV Spor URLs can end with /1 or /slug-417629/1; use path segments joined by -."""
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].split("/", 3)[-1] if "/" in u else ""
        if not path:
            return "page"
        # e.g. "foto-galeri/fenerbahceden-trabzonspor-maci-oncesi-paylasim-417629/1" -> foto-galeri-fenerbahceden-...
        return path.replace("/", "-")


if __name__ == "__main__":
    NtvsporHtmlFetcher().main()
