"""
Fetch article HTML from tr.euronews.com and save to HTML_files/ only the article block:
<div class="o-article-newsy__main"> (no navbar, sidebar, comments, related).
Run from tr.euronews.com folder: python fetch_html.py <URL> [URL ...]
"""

import gzip
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _fetch_euronews_bytes(url: str) -> bytes:
    """Fetch URL; ask for no compression so we get plain HTML bytes, then decode as UTF-8."""
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept-Encoding": "identity"})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()
    if len(raw) >= 2 and raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw


def _extract_article_only_euronews(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("div", class_=lambda c: c and "o-article-newsy__main" in (c if isinstance(c, str) else " ".join(c)))
    if not main:
        return html
    wrap = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>{str(main)}</body></html>'
    return wrap


class EuronewsHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def fetch_url(self, url: str, session) -> str:
        """GET url via urllib; decompress gzip, decode UTF-8, so HTML is saved as text like other folders."""
        raw = _fetch_euronews_bytes(url)
        return raw.decode("utf-8", errors="replace")

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_euronews(html)


if __name__ == "__main__":
    EuronewsHtmlFetcher().main()
