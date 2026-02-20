"""
Parse HTML from HTML_files/ (only div.detail-content-box with property=articleBody) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://finans.mynet.com"


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


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    h1 = soup.find("h1", class_=lambda c: c and "post-title" in (c if isinstance(c, str) else " ".join(c)))
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)

    document_date = None
    time_el = soup.find("time", datetime=True)
    if time_el and time_el.get("datetime"):
        document_date = (time_el["datetime"] or "").strip()
    if not document_date:
        date_span = soup.find("span", class_=lambda c: c and "post-date-mobile" in (c if isinstance(c, str) else " ".join(c)))
        if date_span and date_span.get_text(strip=True):
            text = date_span.get_text(strip=True)
            m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})", text)
            if m:
                d, mo, y, h, mi = m.groups()
                try:
                    document_date = dt(int(y), int(mo), int(d), int(h), int(mi)).strftime("%Y-%m-%dT%H:%M:%S+03:00")
                except (ValueError, TypeError):
                    pass

    authors = []
    author_el = soup.find(class_=lambda c: c and "author-name" in (c if isinstance(c, str) else " ".join(c)))
    if author_el:
        name = author_el.get_text(strip=True)
        if name:
            name = re.sub(r"\s+/?\s*Muhabir\s*$", "", name, flags=re.I).strip()
        if name:
            a = author_el.find("a", href=True)
            if not a:
                a = author_el.find_parent("a", href=True)
            author_url = urljoin(base_url, a["href"]) if a and a.get("href") else None
            authors.append({"name": name, "url": author_url})
    if not authors:
        authors = None

    categories = None
    breadcrumb = soup.find(class_=lambda c: c and "breadcrumb" in (c if isinstance(c, str) else " ".join(c)))
    if breadcrumb:
        links = breadcrumb.find_all("a", href=True)
        if links:
            categories = []
            for a in links:
                name = (a.get("title") or "").strip()
                if not name:
                    span = a.find("span", attrs={"itemprop": "name"})
                    name = (span.get_text(strip=True) if span else a.get_text(strip=True) or "").strip()
                if name:
                    href = (a.get("href") or "").strip()
                    if href:
                        categories.append({"name": name, "url": urljoin(base_url, href)})
            if not categories:
                categories = None

    tags = None
    tags_cont = soup.find(class_=lambda c: c and "tags-word" in (c if isinstance(c, str) else " ".join(c)))
    if tags_cont:
        tag_links = tags_cont.find_all("a", href=True)
        if tag_links:
            tags = []
            for a in tag_links:
                name = (a.get_text(strip=True) or "").strip()
                if name:
                    tags.append({"name": name, "url": urljoin(base_url, a["href"])})
            if not tags:
                tags = None

    return {
        "title": title or None,
        "document_date": document_date or None,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _components_from_detail_content(container: Tag) -> list:
    components = []
    if not container:
        return components
    for child in container.children:
        if not isinstance(child, Tag):
            continue
        if _has_class(child, "ng-other-news-container", "content-banner-box", "detail-footer-tags"):
            continue
        if _has_class(child, "body-banner-block", "ad-enpara-container", "module-type-gallery-adv-full"):
            continue
        if _has_class(child, "reaction-box-wrapper", "mynet-user-reactions"):
            continue
        if child.get("id") in ("commentPostDiv", "tipp-comment"):
            continue
        if child.name == "script" or child.name == "style":
            continue
        if child.name == "p":
            for img in child.find_all("img"):
                url = (img.get("data-original") or img.get("src") or "").strip()
                if url:
                    props = {"url": url}
                    alt = (img.get("alt") or "").strip()
                    if alt:
                        props["description"] = alt
                    components.append({"type": "image", "properties": props})
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
        if child.name == "ul":
            for li in child.find_all("li", recursive=False):
                text = _inline_to_markdown(li).strip()
                if text:
                    components.append({"type": "paragraph", "properties": {"text": f"• {text}"}})
            continue
        if child.name == "blockquote":
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "citation", "properties": {"citation_text": text}})
            continue
        if child.name == "figure":
            img = child.find("img", src=True)
            if img:
                url = (img.get("src") or "").strip()
                if url:
                    props = {"url": url}
                    alt = (img.get("alt") or "").strip()
                    if alt:
                        props["description"] = alt
                    cap = child.find("figcaption")
                    if cap and cap.get_text(strip=True):
                        props["caption"] = cap.get_text(strip=True)
                    components.append({"type": "image", "properties": props})
            continue
        if child.name == "img" and child.get("src"):
            url = (child.get("src") or "").strip()
            if url:
                props = {"url": url}
                alt = (child.get("alt") or "").strip()
                if alt:
                    props["description"] = alt
                components.append({"type": "image", "properties": props})
            continue
        if child.name == "div" and _has_class(child, "content-inner-related-box", "featuredimg"):
            continue
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)
    components_list = []

    content_box = soup.find("div", attrs={"property": "articleBody"})
    if not content_box:
        content_box = soup.find("div", class_=lambda c: c and "detail-content-box" in (c if isinstance(c, str) else " ".join(c)))

    if content_box:
        feature_media = content_box.find("div", class_=lambda c: c and "feature-media" in (c if isinstance(c, str) else " ".join(c)))
        if feature_media:
            img = feature_media.find("img", src=True)
            if img:
                url = (img.get("data-original") or img.get("src") or "").strip()
                if url:
                    props = {"url": url}
                    alt = (img.get("alt") or "").strip()
                    if alt:
                        props["description"] = alt
                    components_list.append({"type": "image", "properties": props})

        post_spot = content_box.find("h2", class_=lambda c: c and "post-spot" in (c if isinstance(c, str) else " ".join(c)))
        if post_spot and post_spot.get_text(strip=True):
            components_list.append({"type": "heading", "properties": {"text": post_spot.get_text(strip=True), "level": 2}})

        detail_inner = content_box.find("div", class_=lambda c: c and "detail-content-inner" in (c if isinstance(c, str) else " ".join(c)))
        if not detail_inner:
            medyanet = content_box.find("div", class_=lambda c: c and "medyanet-content" in (c if isinstance(c, str) else " ".join(c)))
            if medyanet:
                detail_inner = medyanet.find("div", class_=lambda c: c and "detail-content-inner" in (c if isinstance(c, str) else " ".join(c)))
        if not detail_inner:
            detail_inner = content_box.find("div", id="contextual")
        if not detail_inner:
            detail_inner = content_box
        components_list.extend(_components_from_detail_content(detail_inner))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class FinansMynetParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    FinansMynetParser().main()
