"""
Fetch Think with Google (business.google.com) article HTML and save to HTML_files/.
Uses Playwright (if installed) to get past consent/cookie page; falls back to requests.
Extracts only <main id="page-content">, trimmed before return-to-top (minimal doc).
Run from business.google.com folder: python fetch_html.py <URL> [URL ...]

Optional: pip install playwright && playwright install chromium
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


def _fetch_with_playwright(url: str) -> str:
    """Open URL in headless Chromium, accept consent if present, return full page HTML."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            browser.close()
            raise
        # Consent page: try to click Accept / Accept all (various locales)
        for _ in range(2):
            try:
                page.wait_for_selector("main#page-content", timeout=3000)
                break
            except Exception:
                pass
            clicked = False
            for text in ["Accept all", "Accept", "I agree", "Allow all", "Agree"]:
                try:
                    page.get_by_role("button", name=text).first.click(timeout=2000)
                    clicked = True
                    break
                except Exception:
                    try:
                        page.get_by_text(text).first.click(timeout=2000)
                        clicked = True
                        break
                    except Exception:
                        continue
            if clicked:
                try:
                    page.wait_for_selector("main#page-content", timeout=15000)
                except Exception:
                    pass
            break
        try:
            page.wait_for_selector("main#page-content", timeout=5000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    return html


def _extract_article_only_business_google(html: str) -> str:
    """
    Extract only <main id="page-content" class="simple-article">; inside it remove
    <section class="simple-article-return-to-top"> and everything after.
    If main is not found, return minimal placeholder.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main", id="page-content", class_=lambda c: c and "simple-article" in (c if isinstance(c, str) else " ".join(c)))
    if not main:
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
            "<p>Article main not found. The URL may have returned a consent/cookie page. "
            "Install Playwright: pip install playwright && playwright install chromium</p>"
            "</body></html>"
        )
    stop = main.find("section", class_=lambda c: c and "simple-article-return-to-top" in (c if isinstance(c, str) else " ".join(c)))
    if stop:
        for s in list(stop.find_next_siblings()):
            s.decompose()
        stop.decompose()
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>'
        + str(main)
        + "</body></html>"
    )


class BusinessGoogleHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def fetch_url(self, url: str, session) -> str:
        """Use Playwright to get past consent; fall back to requests if Playwright unavailable or fails."""
        try:
            return _fetch_with_playwright(url)
        except ImportError:
            print("Playwright not installed. Install: pip install playwright && playwright install chromium", file=sys.stderr)
            return super().fetch_url(url, session)
        except Exception as e:
            print(f"Playwright fetch failed ({e}), trying requests...", file=sys.stderr)
            return super().fetch_url(url, session)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_business_google(html)

    def url_to_slug(self, url: str) -> str:
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0]
        parts = [p for p in path.rstrip("/").split("/") if p]
        return parts[-1] if parts else "page"


if __name__ == "__main__":
    BusinessGoogleHtmlFetcher().main()
