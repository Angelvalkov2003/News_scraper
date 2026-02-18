"""
Fetch article HTML from dogrulukpayi.com and save to HTML_files/ only the article content.
Priority: section.r-section.r-section-withcard; if missing – body after trimming.
Removes: script, style, link, noscript, SVG outside figure, style/data-* attributes, content after LogoCheck.
"""

import json
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

_META_NAMES = ("datePublished", "dateModified", "dateCreated", "articleAuthor", "articleSection")
_META_PROPERTIES = ("article:published_time", "article:modified_time", "article:author", "article:section")


def url_to_slug(url: str) -> str:
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


def _build_minimal_head(soup: BeautifulSoup) -> str:
    parts = ['<head><meta charset="utf-8">']
    head = soup.find("head")
    if not head:
        return '<head><meta charset="utf-8"></head>'
    for meta in head.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").strip()
        if name in _META_NAMES or name in _META_PROPERTIES:
            parts.append(str(meta))
    author_meta = head.find("meta", attrs={"name": "author"})
    if author_meta and author_meta.get("content"):
        parts.append(str(author_meta))
    # datePublished/dateModified from JSON-LD if missing in meta (common for doğrulukpayi)
    if not any("datePublished" in p or "article:published_time" in p for p in parts):
        for script in head.find_all("script", type=re.compile(r"application/ld\+json")):
            try:
                raw = (script.string or "").strip()
                if not raw:
                    continue
                data = json.loads(raw)
                article_ld = None
                if isinstance(data, dict):
                    if data.get("@type") == "Article":
                        article_ld = data
                    for item in data.get("@graph") or []:
                        if isinstance(item, dict) and item.get("@type") == "Article":
                            article_ld = item
                            break
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "Article":
                            article_ld = item
                            break
                if article_ld:
                    if article_ld.get("datePublished"):
                        parts.append('<meta name="datePublished" content="' + article_ld["datePublished"] + '"/>')
                    if article_ld.get("dateModified"):
                        parts.append('<meta name="dateModified" content="' + article_ld["dateModified"] + '"/>')
                    break
            except (json.JSONDecodeError, TypeError):
                pass
    parts.append("</head>")
    return "".join(parts)


def _find_section_article(soup: BeautifulSoup):
    """Find section with classes r-section and r-section-withcard."""
    for section in soup.find_all("section"):
        c = section.get("class")
        if not c:
            continue
        s = " ".join(c) if isinstance(c, list) else c
        if "r-section" in s and "r-section-withcard" in s:
            return section
    for section in soup.find_all("section"):
        c = section.get("class")
        if c and "r-section" in (" ".join(c) if isinstance(c, list) else c):
            return section
    return None


def _cut_at_logo_check(container: BeautifulSoup) -> None:
    """Remove path.LogoCheck and everything after it in the container."""
    path_el = container.find("path", attrs={"data-name": "LogoCheck"})
    if not path_el:
        path_el = container.find("path", class_=lambda c: c and "LogoCheck" in (c if isinstance(c, str) else " ".join(c)))
    if not path_el:
        return
    node = path_el
    while node and node.parent != container:
        node = node.parent
    if not node:
        return
    for s in list(node.find_next_siblings()):
        s.decompose()
    node.decompose()


def _slim_content(container: BeautifulSoup) -> None:
    """
    Remove redundant content to reduce size and keep only the article.
    - script, style, link, noscript
    - SVG outside figure (icons/logo)
    - style and data-* attributes on all tags
    """
    for tag in container.find_all("script"):
        tag.decompose()
    for tag in container.find_all("style"):
        tag.decompose()
    for tag in container.find_all("link"):
        tag.decompose()
    for tag in container.find_all("noscript"):
        tag.decompose()
    # SVG outside figure (icons, logo) – remove; img inside figure stays
    for tag in list(container.find_all("svg")):
        if tag.find_parent("figure"):
            continue
        tag.decompose()
    # Remove style and data-* attributes for shorter HTML
    for tag in container.find_all(True):
        if tag.has_attr("style"):
            del tag["style"]
        data_attrs = [k for k in tag.attrs if isinstance(k, str) and k.startswith("data-")]
        for k in data_attrs:
            del tag[k]


def extract_article_only(html: str) -> str:
    """
    Extract article content: section.r-section (and withcard if present) or body.
    Applies _cut_at_logo_check and _slim_content. Head: only required meta.
    """
    soup = BeautifulSoup(html, "html.parser")
    section = _find_section_article(soup)
    if section:
        _cut_at_logo_check(section)
        _slim_content(section)
        head_str = _build_minimal_head(soup)
        section_html = section.decode_contents() if hasattr(section, "decode_contents") else str(section)
        return (
            "<!DOCTYPE html><html>"
            + head_str
            + "<body><section class=\"r-section r-section-withcard\">"
            + section_html
            + "</section></body></html>"
        )

    # Fallback: no section.r-section – return original HTML unchanged
    return html


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
