"""
Fetch article HTML from birgun.net and save to HTML_files/ only the article content:
from div.contentdetail (H1 title and body) up to before the first "Sıradaki Haber". No navbar, menu, ads.
Run from birgun.net folder: python fetch_html.py <URL> [URL ...]
"""

import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SITE_DIR = Path(__file__).resolve().parent
HTML_FILES = SITE_DIR / "HTML_files"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def url_to_slug(url: str) -> str:
    """Return slug for filename from URL (e.g. .../makale/slug-123 -> slug-123)."""
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


# Meta tags used by parser for metadata (document_date, authors, categories, tags)
_META_NAMES = ("datePublished", "articleAuthor", "articleSection", "keywords", "ptime")
_META_PROPERTIES = ("datePublished",)  # property="datePublished" etc.


def _build_minimal_head(soup: BeautifulSoup) -> str:
    """Only meta tags for document_date, authors, categories, tags – no scripts/styles."""
    parts = ['<head><meta charset="utf-8">']
    head = soup.find("head")
    if not head:
        return '<head><meta charset="utf-8"></head>'
    for meta in head.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").strip()
        if name in _META_NAMES or name in _META_PROPERTIES:
            parts.append(str(meta))
    parts.append("</head>")
    return "".join(parts)


def extract_article_only(html: str) -> str:
    """
    Keep only article content: div.contentdetail (from H1 up to before "Sıradaki Haber").
    In head write only the meta tags needed for metadata (date, author, category, tags) – no long scripts.
    """
    soup = BeautifulSoup(html, "html.parser")
    head_str = _build_minimal_head(soup)
    contentdetail = soup.find("div", class_=lambda c: c and "contentdetail" in (c if isinstance(c, str) else " ".join(c)))
    if not contentdetail:
        return html
    stop_text = contentdetail.find(string=lambda t: t and "Sıradaki Haber" in t)
    if stop_text:
        node = stop_text.parent
        while node and node.parent != contentdetail:
            node = node.parent
        if node and node.parent == contentdetail:
            for s in list(node.next_siblings):
                s.decompose()
            node.decompose()
    return '<!DOCTYPE html><html>' + head_str + '<body>' + str(contentdetail) + '</body></html>'


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_html.py <URL> [URL ...]", file=sys.stderr)
        sys.exit(1)
    HTML_FILES.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = UA
    for url in sys.argv[1:]:
        url = url.strip()
        if not url:
            continue
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            html_clean = extract_article_only(r.text)
            slug = url_to_slug(url)
            path = HTML_FILES / f"{slug}.html"
            path.write_text(html_clean, encoding="utf-8")
            print(f"Written: {path}")
        except requests.RequestException as e:
            print(f"Error {url}: {e}", file=sys.stderr)
        if len(sys.argv) > 2:
            time.sleep(1)


if __name__ == "__main__":
    main()
