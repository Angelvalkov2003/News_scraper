"""
Fetch article HTML from www.iklimhaber.org and save to HTML_files/.
Extracts only the main content block: <div class="col-lg-9 col-md-9 col-mod-single col-mod-main">.
Run from iklimhaber.org folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_iklimhaber(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find(
        "div",
        class_=lambda c: c
        and "col-lg-9" in (c if isinstance(c, str) else " ".join(c))
        and "col-mod-single" in (c if isinstance(c, str) else " ".join(c))
        and "col-mod-main" in (c if isinstance(c, str) else " ".join(c)),
    )
    if div:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            + str(div)
            + "</body></html>"
        )
    return html


class IklimhaberHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_iklimhaber(html)

    def url_to_slug(self, url: str) -> str:
        """iklimhaber.org/.../slug/ -> slug (last path segment, strip trailing slash)"""
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].rstrip("/").split("/")
        return path[-1] if path else "page"


if __name__ == "__main__":
    IklimhaberHtmlFetcher().main()
