"""
Fetch article HTML from www.webtekno.com and save to HTML_files/.
Keeps full HTML but removes: (1) sidebar "EN ÇOK OKUNANLAR", (2) site header, (3) masthead ad.
Run from webtekno.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _clean_webtekno_html(html: str) -> str:
    """
    Remove unwanted elements from full page:
    - div.home-sidebar-most-read / bg-sidebar-most-read (sidebar "EN ÇOK OKUNANLAR")
    - div.header.sticky (site header with logo, nav, badges)
    - div#masthead-ad-* (masthead ad)
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) Sidebar "EN ÇOK OKUNANLAR"
    for div in soup.find_all("div", class_=True):
        c = div.get("class") or []
        cls = " ".join(c) if isinstance(c, list) else c
        if "home-sidebar-most-read" in cls or "bg-sidebar-most-read" in cls:
            div.decompose()
            break

    # 2) Header (sticky top-0, logo, nav)
    for div in soup.find_all("div", class_=True):
        c = div.get("class") or []
        cls = " ".join(c) if isinstance(c, list) else c
        if "header" in cls and "sticky" in cls:
            div.decompose()
            break

    # 3) Masthead ad block (wrapper with .masthead-adv or div#masthead-ad)
    for div in soup.find_all("div", id=True):
        aid = div.get("id") or ""
        if aid == "masthead-ad" or aid.startswith("masthead-ad-"):
            parent = div.find_parent("div", class_=lambda c: c and "masthead-adv" in (c if isinstance(c, str) else " ".join(c)))
            if parent:
                parent.decompose()
            else:
                div.decompose()
            break

    return str(soup)


class WebteknoHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _clean_webtekno_html(html)

    def url_to_slug(self, url: str) -> str:
        """webtekno.com/slug-h212233.html -> slug-h212233"""
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].split("/")[-1] or "page"
        if path.endswith(".html"):
            path = path[:-5]
        return path


if __name__ == "__main__":
    WebteknoHtmlFetcher().main()
