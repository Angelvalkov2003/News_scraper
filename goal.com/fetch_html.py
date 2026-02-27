"""
Fetch article HTML from www.goal.com/tr and save to HTML_files/.
Uses Playwright so the tag list (fco-scrollable-tag-list) is rendered by JS before saving.
Extracts only <main class="wrapper_component-layout-main__..."> (article wrapper).
Requires: pip install playwright && playwright install chromium
Run from goal.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher
from base._utils import ensure_utf8_stdout


def _fetch_with_playwright(url: str) -> str:
    """Fetch URL with Playwright so JS-rendered content (e.g. tag list) is present."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent=BaseHtmlFetcher.DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 720},
            )
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait for tag list to be rendered (replaces skeleton)
            try:
                page.wait_for_selector(".fco-scrollable-tag-list", timeout=8000)
            except Exception:
                pass  # continue with whatever HTML we have
            time.sleep(0.5)  # allow any late DOM updates
            return page.content()
        finally:
            browser.close()


def _extract_article_only_goal(html: str) -> str:
    """
    Extract the main article wrapper:
    <main class="wrapper_component-layout-main__NxKxF">
      <article class="article_article__0zDYK component-article">...</article>
    </main>
    """
    soup = BeautifulSoup(html, "html.parser")
    # main with class containing layout-main (e.g. wrapper_component-layout-main__NxKxF)
    outer = soup.find(
        "main",
        class_=lambda c: c and "layout-main" in (c if isinstance(c, str) else " ".join(c)),
    )
    if not outer:
        # Fallback: first main that contains article.article
        for main in soup.find_all("main"):
            if main.find("article", class_=lambda c: c and "article" in (c if isinstance(c, str) else " ".join(c))):
                outer = main
                break
    if outer:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            + str(outer)
            + "</body></html>"
        )
    return html


class GoalHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_goal(html)

    def url_to_slug(self, url: str) -> str:
        """goal.com/tr/haber/.../blt4dbbfaa571259166 -> blt4dbbfaa571259166"""
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].split("/")
        return path[-1] if path else "page"

    def main(self) -> None:
        """Fetch with Playwright so tag list is in HTML, then extract main and save."""
        ensure_utf8_stdout()
        if len(sys.argv) < 2:
            print("Usage: python fetch_html.py <URL> [URL ...]", file=sys.stderr)
            sys.exit(1)
        urls = [u.strip() for u in sys.argv[1:] if u.strip()]
        for i, url in enumerate(urls):
            try:
                raw_html = _fetch_with_playwright(url)
                html_clean = self.extract_article_only(raw_html)
                slug = self.url_to_slug(url)
                path = self.save_html(html_clean, slug)
                print(f"Written: {path}")
            except Exception as e:
                print(f"Error {url}: {e}", file=sys.stderr)
            if i < len(urls) - 1 and len(urls) > 1:
                time.sleep(1)


if __name__ == "__main__":
    GoalHtmlFetcher().main()
