"""
Fetch article HTML from www.sporx.com and save to HTML_files/.
Extracts only the main content block: <div class="pg-left wide-682">.
Run from sporx.com folder: python fetch_html.py <URL> [URL ...]

Sporx has two URL formats; the old one returns 404:
- Old: .../slug-1150941  → 404
- Current: .../slug-SXHBQ1150941SXQ → 200
On 404 we retry with the SXHBQ format.
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _extract_article_only_sporx(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    breadcrumb = soup.find("ul", class_=lambda c: c and "breadcrumb" in (c if isinstance(c, str) else " ".join(c)))
    div = soup.find(
        "div",
        class_=lambda c: c
        and "pg-left" in (c if isinstance(c, str) else " ".join(c))
        and "wide-682" in (c if isinstance(c, str) else " ".join(c)),
    )
    body_parts = []
    if breadcrumb:
        body_parts.append(str(breadcrumb))
    if div:
        body_parts.append(str(div))
    if body_parts:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            + "".join(body_parts)
            + "</body></html>"
        )
    return html


class SporxHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def _sporx_alt_url(self, url: str) -> str | None:
        """If path ends with -NUMBER (no SXHBQ), return ...-SXHBQNUMBERSXQ so server finds the article."""
        parsed = urlparse(url)
        path = (parsed.path or "").rstrip("/")
        m = re.match(r"^(.+)-(\d+)$", path)
        if not m:
            return None
        prefix, num = m.groups()
        new_path = f"{prefix}-SXHBQ{num}SXQ"
        return urlunparse((parsed.scheme, parsed.netloc, new_path, parsed.params, parsed.query, parsed.fragment))

    def fetch_url(self, url: str, session) -> str:
        """Decode as Turkish (ISO-8859-9) or UTF-8. On 404, retry with SXHBQ URL format."""
        r = session.get(url, timeout=30)
        if r.status_code == 404:
            alt = self._sporx_alt_url(url)
            if alt and alt != url:
                r = session.get(alt, timeout=30)
                if r.status_code == 200:
                    url = alt
                else:
                    r.raise_for_status()
            else:
                r.raise_for_status()
        else:
            r.raise_for_status()
        raw = r.content
        try:
            text = raw.decode("utf-8")
            if "\ufffd" in text or ("þ" in text and "ubat" in text):
                text = raw.decode("iso-8859-9", errors="replace")
        except UnicodeDecodeError:
            text = raw.decode("iso-8859-9", errors="replace")
        return text

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_sporx(html)

    def url_to_slug(self, url: str) -> str:
        """sporx.com/.../slug-SXHBQ... -> last path segment"""
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].rstrip("/").split("/")
        return path[-1] if path else "page"


if __name__ == "__main__":
    SporxHtmlFetcher().main()
