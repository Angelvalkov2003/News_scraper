"""
Parse HTML from HTML_files/ (div.o-article-newsy__main only) into scraped_article_json_schema.json format, write to Parsed_files/.
"""

import re
import sys
from datetime import datetime as dt
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_parser import BaseParser

BASE_URL = "https://tr.euronews.com"


def _has_class(tag, *names):
    if not tag.get("class"):
        return False
    c = tag["class"]
    s = " ".join(c) if isinstance(c, list) else c
    return any(n in s for n in names)


def _inline_to_markdown(tag) -> str:
    if isinstance(tag, NavigableString):
        return str(tag)
    if not isinstance(tag, Tag):
        return ""
    if tag.name in ("strong", "b"):
        return "**" + "".join(_inline_to_markdown(c) for c in tag.children) + "**"
    if tag.name in ("i", "em"):
        return "*" + "".join(_inline_to_markdown(c) for c in tag.children) + "*"
    if tag.name == "a":
        text = "".join(_inline_to_markdown(c) for c in tag.children)
        href = tag.get("href") or ""
        return f"[{text}]({href})" if text or href else text
    return "".join(_inline_to_markdown(c) for c in tag.children)


def _get_metadata(main: Tag, base_url: str) -> dict:
    title = None
    h1 = main.find("h1", class_=lambda c: c and "c-article-redesign-title" in (c if isinstance(c, str) else " ".join(c)))
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    document_date = None
    pub_div = main.find("div", class_=lambda c: c and "c-article-publication-date" in (c if isinstance(c, str) else " ".join(c)))
    if pub_div:
        time_el = pub_div.find("time", datetime=True)
        if time_el and time_el.get("datetime"):
            document_date = (time_el["datetime"] or "").strip() or None
        if not document_date and pub_div.get("data-timestamp"):
            ts = int(pub_div["data-timestamp"])
            document_date = dt.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    authors = []
    contrib = main.find("div", class_=lambda c: c and "c-article-contributors" in (c if isinstance(c, str) else " ".join(c)))
    if contrib:
        b = contrib.find("b")
        if b and b.get_text(strip=True):
            authors.append({"name": b.get_text(strip=True), "url": None})
        else:
            text = contrib.get_text(strip=True)
            if text:
                name = re.sub(r"^By\s+", "", text, flags=re.I).strip()
                if name:
                    authors.append({"name": name, "url": None})

    categories = None
    breadcrumbs = main.find("nav", class_=lambda c: c and "c-article-breadcrumbs" in (c if isinstance(c, str) else " ".join(c)))
    if breadcrumbs:
        links = breadcrumbs.find_all("a", class_=lambda c: c and "c-article-breadcrumbs__link" in (c if isinstance(c, str) else " ".join(c)))
        if links:
            categories = []
            for a in links:
                name = (a.get_text(strip=True) or "").strip()
                if not name or "Ana Sayfa" in name:
                    continue
                href = a.get("href")
                url = urljoin(base_url, href) if href else None
                categories.append({"name": name, "url": url})
            if not categories:
                categories = None

    tags = None
    tags_ul = main.find("ul", class_=lambda c: c and "c-tags-list" in (c if isinstance(c, str) else " ".join(c)))
    if tags_ul:
        tag_links = tags_ul.find_all("a", href=True)
        if tag_links:
            tags = []
            for a in tag_links:
                name = (a.get_text(strip=True) or "").strip()
                if name:
                    url = urljoin(base_url, a["href"])
                    tags.append({"name": name, "url": url})

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors if authors else None,
        "categories": categories,
        "tags": tags,
    }


def _lead_media_components(main: Tag) -> list:
    out = []
    media = main.find("div", class_=lambda c: c and "c-article-image-video" in (c if isinstance(c, str) else " ".join(c)))
    if not media:
        return out
    img = media.find("img", src=True)
    if img:
        url = (img.get("src") or "").strip()
        if url:
            caption_el = media.find("span", class_=lambda c: c and "c-article-caption__text" in (c if isinstance(c, str) else " ".join(c)))
            caption = caption_el.get_text(strip=True) if caption_el else None
            props = {"url": url}
            alt = (img.get("alt") or "").strip()
            if alt:
                props["description"] = alt
            if caption:
                props["caption"] = caption
            out.append({"type": "image", "properties": props})
    return out


def _figcaption_text(figcap: Tag) -> str:
    if not figcap:
        return ""
    wrap = figcap.find("span", class_=lambda c: c and "widget__captionText" in (c if isinstance(c, str) else " ".join(c)))
    if wrap:
        return wrap.get_text(strip=True) or ""
    return figcap.get_text(strip=True) or ""


def _components_from_article_content(content_div: Tag) -> list:
    components = []
    if not content_div:
        return components

    for child in content_div.children:
        if not isinstance(child, Tag):
            continue
        if _has_class(child, "c-ad", "connatix-container"):
            continue
        if child.name == "p":
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "paragraph", "properties": {"text": text}})
            continue
        if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = child.get_text(strip=True)
            if text:
                level = int(child.name[1])
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
            continue
        if child.name == "div" and _has_class(child, "widget"):
            fig = child.find("figure", class_=lambda c: c and "widget__figure" in (c if isinstance(c, str) else " ".join(c)))
            if not fig:
                fig = child.find("figure")
            if fig:
                img = fig.find("img", src=True)
                if img:
                    url = (img.get("src") or "").strip()
                    if url:
                        caption = _figcaption_text(fig.find("figcaption"))
                        props = {"url": url}
                        alt = (img.get("alt") or "").strip()
                        if alt:
                            props["description"] = alt
                        if caption:
                            props["caption"] = caption
                        components.append({"type": "image", "properties": props})
            continue
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    main = soup.find("div", class_=lambda c: c and "o-article-newsy__main" in (c if isinstance(c, str) else " ".join(c)))
    if not main:
        return {
            "metadata": {"title": None, "document_date": None, "authors": None, "categories": None, "tags": None},
            "components": {"components": []},
        }

    metadata = _get_metadata(main, base_url)

    components_list = []
    components_list.extend(_lead_media_components(main))

    summary = main.find("h2", class_=lambda c: c and "c-article-summary" in (c if isinstance(c, str) else " ".join(c)))
    if summary and summary.get_text(strip=True):
        components_list.append({"type": "heading", "properties": {"text": summary.get_text(strip=True), "level": 2}})

    content = main.find("div", class_=lambda c: c and "c-article-content" in (c if isinstance(c, str) else " ".join(c)) and "js-article-content" in (c if isinstance(c, str) else " ".join(c)))
    components_list.extend(_components_from_article_content(content))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class EuronewsParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    EuronewsParser().main()
