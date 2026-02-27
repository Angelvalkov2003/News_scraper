"""
Fetch article HTML from ajansspor.com and save to HTML_files/.
Extracts only <article class="news-detail"> (main article container).
Run from ajansspor.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_ajansspor(html: str) -> str:
    """
    Extract the main article container:
    <div class="container" data-page="...">
      <section class="breadcrumb">...</section>
      <section class="news">
        <article class="news-detail">...</article>
      </section>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    # Prefer the outer container with data-page (includes breadcrumb + news)
    outer = soup.find(
        "div",
        class_=lambda c: c and "container" in (c if isinstance(c, str) else " ".join(c)),
        attrs={"data-page": True},
    )
    if not outer:
        # Fallback: just the article if container not found
        outer = soup.find("article", class_=lambda c: c and "news-detail" in (c if isinstance(c, str) else " ".join(c)))
    if outer:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            + str(outer)
            + "</body></html>"
        )
    return html


class AjanssporHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_ajansspor(html)

    def url_to_slug(self, url: str) -> str:
        """ajansspor.com/haber/slug-718480 -> slug-718480"""
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].split("/")
        return path[-1] if path else "page"


if __name__ == "__main__":
    AjanssporHtmlFetcher().main()
