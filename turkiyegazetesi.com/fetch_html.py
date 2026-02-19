"""
Fetch article HTML from turkiyegazetesi.com.tr and save to HTML_files/ only the article content:
only <div class="article-scope"> with one <article> inside, no navbar, sidebar, recommendations, share, comments.
Run from turkiyegazetesi.com folder: python fetch_html.py <URL> [URL ...]
"""

import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher

_META_NAMES = ("datePublished", "dateModified", "dateCreated", "articleAuthor", "articleSection")
_META_PROPERTIES = ("article:published_time", "article:modified_time", "article:author", "article:section")
_REMOVE_BLOCK_CLASSES = frozenset({
    "article-recommended", "article-related", "article-follow-us",
    "article-social-publish", "article-sp-share", "comments",
})
_REMOVE_SELECTORS = ("article-actions", "listenSummarySave")


def _build_minimal_head(soup: BeautifulSoup) -> str:
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
    comments = article.find("div", class_=lambda c: c and "comments" in (c if isinstance(c, str) else " ".join(c)))
    if not comments:
        return
    for s in list(comments.find_next_siblings()):
        s.decompose()
    comments.decompose()


def _remove_blocks_by_class(article: BeautifulSoup) -> None:
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
    for sel in _REMOVE_SELECTORS:
        for tag in article.find_all(class_=lambda c: c and sel in (c if isinstance(c, str) else " ".join(c))):
            tag.decompose()


def _clean_media_containers(article: BeautifulSoup) -> None:
    for tag in article.find_all("script"):
        tag.decompose()
    for tag in article.find_all("div", id=lambda x: x and str(x).startswith("playButton-")):
        tag.decompose()
    for tag in article.find_all("div", class_=lambda c: c and "adContainer" in (c if isinstance(c, str) else " ".join(c))):
        tag.decompose()


def _extract_article_clean(article_scope: BeautifulSoup):
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


def _extract_article_only_turkiyegazetesi(html: str) -> str:
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


class TurkiyegazetesiHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_turkiyegazetesi(html)


if __name__ == "__main__":
    TurkiyegazetesiHtmlFetcher().main()
