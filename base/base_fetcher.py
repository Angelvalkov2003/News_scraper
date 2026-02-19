"""
Base HTML fetcher for news article pages.
Subclasses override extract_article_only() for site-specific cleaning;
default is to return raw HTML.
"""

import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

import requests

from base._utils import ensure_utf8_stdout, url_to_slug


class BaseHtmlFetcher(ABC):
    """Template for fetching article HTML and saving to HTML_files/."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, site_dir: Path):
        self.site_dir = Path(site_dir)
        self.html_files = self.site_dir / "HTML_files"

    def get_user_agent(self) -> str:
        """Override to change User-Agent."""
        return self.DEFAULT_USER_AGENT

    def url_to_slug(self, url: str) -> str:
        """Override if site uses a different slug-from-URL rule."""
        return url_to_slug(url)

    def extract_article_only(self, html: str) -> str:
        """
        Extract/clean only the article content from full page HTML.
        Override in subclasses; default returns HTML unchanged.
        """
        return html

    def fetch_url(self, url: str, session: requests.Session) -> str:
        """GET url, set encoding, return response text."""
        r = session.get(url, timeout=30)
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        return r.text

    def save_html(self, html: str, slug: str) -> Path:
        """Write HTML to HTML_files/{slug}.html."""
        self.html_files.mkdir(parents=True, exist_ok=True)
        path = self.html_files / f"{slug}.html"
        path.write_text(html, encoding="utf-8")
        return path

    def main(self) -> None:
        """CLI: python fetch_html.py <URL> [URL ...]"""
        ensure_utf8_stdout()
        if len(sys.argv) < 2:
            print("Usage: python fetch_html.py <URL> [URL ...]", file=sys.stderr)
            sys.exit(1)
        session = requests.Session()
        session.headers["User-Agent"] = self.get_user_agent()
        urls = [u.strip() for u in sys.argv[1:] if u.strip()]
        for i, url in enumerate(urls):
            try:
                raw_html = self.fetch_url(url, session)
                html_clean = self.extract_article_only(raw_html)
                slug = self.url_to_slug(url)
                path = self.save_html(html_clean, slug)
                print(f"Written: {path}")
            except requests.RequestException as e:
                print(f"Error {url}: {e}", file=sys.stderr)
            if i < len(urls) - 1 and len(urls) > 1:
                time.sleep(1)
