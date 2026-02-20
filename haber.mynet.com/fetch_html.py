"""
Fetch article HTML from haber.mynet.com and save to HTML_files/.
Keep everything EXCEPT:
- <header class="my-header" ...> (global header/nav)
- <div class="sc-heading-container sc-heading-container-short"> (Vitrin logo/menu, when present)
- <div class="col-12 affiliate-sidebar-section"> (İş birliği İçerikleri sidebar) and we don't need content below it.
Run from haber.mynet.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _has_class(tag, *names):
    if not tag.get("class"):
        return False
    c = tag["class"]
    s = " ".join(c) if isinstance(c, list) else c
    return all(n in s for n in names)


def _extract_article_only_mynet(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for header in soup.find_all("header", class_=lambda c: c and "my-header" in (c if isinstance(c, str) else " ".join(c))):
        header.decompose()

    for div in soup.find_all("div", class_=lambda c: c and "sc-heading-container" in (c if isinstance(c, str) else " ".join(c))):
        div.decompose()

    for div in soup.find_all("div", class_=lambda c: c and "affiliate-sidebar-section" in (c if isinstance(c, str) else " ".join(c))):
        div.decompose()

    return str(soup)


class MynetHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_mynet(html)


if __name__ == "__main__":
    MynetHtmlFetcher().main()
