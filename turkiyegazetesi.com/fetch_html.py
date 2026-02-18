"""
Fetch article HTML from turkiyegazetesi.com.tr and save to HTML_files/ only the article content:
only <div class="article-scope"> with one <article> inside, no navbar, sidebar, recommendations, share, comments.
Run from turkiyegazetesi.com folder: python fetch_html.py <URL> [URL ...]
"""

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

# Meta tags for metadata (parser / AI)
_META_NAMES = ("datePublished", "dateModified", "dateCreated", "articleAuthor", "articleSection")
_META_PROPERTIES = ("article:published_time", "article:modified_time", "article:author", "article:section")

# Block classes to remove from article
_REMOVE_BLOCK_CLASSES = frozenset({
    "article-recommended", "article-related", "article-follow-us",
    "article-social-publish", "article-sp-share", "comments",
})
# Additional elements to remove (share, save, font-size buttons)
_REMOVE_SELECTORS = ("article-actions", "listenSummarySave")


def url_to_slug(url: str) -> str:
    """Last path segment: .../gundem/slug-1770154 -> slug-1770154"""
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


def _build_minimal_head(soup: BeautifulSoup) -> str:
    """Only meta for date, author, category – no scripts/styles/links."""
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


def _remove_comments_and_after(article: BeautifulSoup) -> None:
    """Remove the comments block and all following siblings in article."""
    comments = article.find("div", class_=lambda c: c and "comments" in (c if isinstance(c, str) else " ".join(c)))
    if not comments:
        return
    for s in list(comments.find_next_siblings()):
        s.decompose()
    comments.decompose()


def _remove_blocks_by_class(article: BeautifulSoup) -> None:
    """Remove all elements with the given block classes."""
    to_remove = []
    for tag in article.find_all(True):
        if not tag.get("class"):
            continue
        cls_str = " ".join(tag["class"]) if isinstance(tag["class"], list) else tag["class"]
        if any(block in cls_str for block in _REMOVE_BLOCK_CLASSES):
            to_remove.append(tag)
    for tag in to_remove:
        tag.decompose()


def _remove_actions_and_save(article: BeautifulSoup) -> None:
    """Remove article-actions and listenSummarySave (share, Kaydet, a-|+A)."""
    for sel in _REMOVE_SELECTORS:
        for tag in article.find_all(class_=lambda c: c and sel in (c if isinstance(c, str) else " ".join(c))):
            tag.decompose()


def _clean_media_containers(article: BeautifulSoup) -> None:
    """In media containers remove scripts, adContainer, playButton; keep video/source."""
    for tag in article.find_all("script"):
        tag.decompose()
    for tag in article.find_all("div", id=lambda x: x and str(x).startswith("playButton-")):
        tag.decompose()
    for tag in article.find_all("div", class_=lambda c: c and "adContainer" in (c if isinstance(c, str) else " ".join(c))):
        tag.decompose()


def _extract_article_clean(article_scope: BeautifulSoup):
    """Return cleaned <article> (Tag) with blocks and UI removed."""
    article = article_scope.find("article")
    if not article:
        return None
    article_soup = BeautifulSoup(str(article), "html.parser")
    article = article_soup.find("article")
    if not article:
        return None
    _remove_comments_and_after(article)
    _remove_blocks_by_class(article)
    _remove_actions_and_save(article)
    _clean_media_containers(article)
    return article


def extract_article_only(html: str) -> str:
    """
    Extract only div.article-scope and inside it only <article> with required content.
    Removes navbar, sidebar, recommendations, share, comments, buttons, scripts in media.
    Head: only the listed meta tags.
    If no article-scope, return original HTML unchanged.
    """
    soup = BeautifulSoup(html, "html.parser")
    article_scope = soup.find("div", class_=lambda c: c and "article-scope" in (c if isinstance(c, str) else " ".join(c)))
    if not article_scope:
        return html

    head_str = _build_minimal_head(soup)
    article_clean = _extract_article_clean(article_scope)
    if not article_clean:
        article_clean = article_scope.find("article")
    if not article_clean:
        return html

    article_html = article_clean.decode_contents() if hasattr(article_clean, "decode_contents") else str(article_clean)
    return (
        "<!DOCTYPE html><html>"
        + head_str
        + "<body><div class=\"article-scope\"><article>"
        + article_html
        + "</article></div></body></html>"
    )


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
