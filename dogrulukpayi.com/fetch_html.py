"""
Fetch article HTML from dogrulukpayi.com and save to HTML_files/ only the article content.
Priority: section.r-section.r-section-withcard; if missing – body after trimming.
Removes: script, style, link, noscript, SVG outside figure, style/data-* attributes, content after LogoCheck.
"""

import json
import re
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
    for tag in container.find_all("script"):
        tag.decompose()
    for tag in container.find_all("style"):
        tag.decompose()
    for tag in container.find_all("link"):
        tag.decompose()
    for tag in container.find_all("noscript"):
        tag.decompose()
    for tag in list(container.find_all("svg")):
        if tag.find_parent("figure"):
            continue
        tag.decompose()
    for tag in container.find_all(True):
        if tag.has_attr("style"):
            del tag["style"]
        data_attrs = [k for k in tag.attrs if isinstance(k, str) and k.startswith("data-")]
        for k in data_attrs:
            del tag[k]


def _extract_article_only_dogrulukpayi(html: str) -> str:
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
    return html


class DogrulukpayiHtmlFetcher(BaseHtmlFetcher):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def extract_article_only(self, html: str) -> str:
        return _extract_article_only_dogrulukpayi(html)


if __name__ == "__main__":
    DogrulukpayiHtmlFetcher().main()
