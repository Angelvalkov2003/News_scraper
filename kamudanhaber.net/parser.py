"""
Parse HTML from HTML_files/ (div.infinite-item.d-block only) into scraped_article_json_schema.json format, write to Parsed_files/.
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

from base._video_schema import extract_video_from_iframe, make_video_component
from base.base_parser import BaseParser

BASE_URL = "https://www.kamudanhaber.net"


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


def _parse_date_text(text: str) -> str | None:
    """Parse '11.02.2026 - 14:28' to ISO 8601."""
    if not text or not text.strip():
        return None
    text = text.strip()
    try:
        # "11.02.2026 - 14:28" or "11.02.2026 - 14:28"
        m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*[-–]\s*(\d{1,2}):(\d{2})", text)
        if m:
            d, mo, y, h, mi = m.groups()
            return dt(int(y), int(mo), int(d), int(h), int(mi)).strftime("%Y-%m-%dT%H:%M:%S+03:00")
    except (ValueError, TypeError):
        pass
    return None


def _get_metadata(root: Tag, base_url: str) -> dict:
    title = None
    header = root.find("div", class_=lambda c: c and "post-header" in (c if isinstance(c, str) else " ".join(c)))
    if header:
        h1 = header.find("h1", class_=lambda c: c and "headline" in (c if isinstance(c, str) else " ".join(c)))
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)

    document_date = None
    meta_author = root.find("div", class_=lambda c: c and "meta-author" in (c if isinstance(c, str) else " ".join(c)))
    if meta_author:
        time_el = meta_author.find("time", datetime=True)
        if time_el and time_el.get("datetime"):
            document_date = (time_el["datetime"] or "").strip() or None
        if not document_date:
            time_el = meta_author.find("time")
            if time_el and time_el.get_text(strip=True):
                document_date = _parse_date_text(time_el.get_text())

    authors = []  # kamudanhaber sample has no author block in snippet

    categories = None
    if header:
        breadcrumb = header.find("nav", class_=lambda c: c and "meta-category" in (c if isinstance(c, str) else " ".join(c)))
        if breadcrumb:
            links = breadcrumb.find_all("a", href=True)
            if links:
                categories = []
                for a in links:
                    name = (a.get_text(strip=True) or "").strip()
                    if not name:
                        continue
                    categories.append({"name": name, "url": urljoin(base_url, a["href"])})
                if not categories:
                    categories = None

    tags = None
    news_tags = root.find("div", class_=lambda c: c and "news-tags" in (c if isinstance(c, str) else " ".join(c)))
    if news_tags:
        tag_links = news_tags.find_all("a", href=True)
        if tag_links:
            tags = []
            for a in tag_links:
                name = (a.get_text(strip=True) or "").strip()
                if name:
                    tags.append({"name": name, "url": urljoin(base_url, a["href"])})

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors if authors else None,
        "categories": categories,
        "tags": tags,
    }


def _lead_media_components(root: Tag) -> list:
    out = []
    news_section = root.find("div", class_=lambda c: c and "news-section" in (c if isinstance(c, str) else " ".join(c)))
    if not news_section:
        return out
    inner = news_section.find("div", class_=lambda c: c and "inner" in (c if isinstance(c, str) else " ".join(c)))
    if not inner:
        return out
    img = inner.find("img", src=True)
    if img:
        url = (img.get("src") or "").strip()
        if url:
            props = {"url": url}
            alt = (img.get("alt") or "").strip()
            if alt:
                props["description"] = alt
            out.append({"type": "image", "properties": props})
    return out


def _components_from_article_text(article_text: Tag, base_url: str) -> list:
    components = []
    if not article_text:
        return components
    for child in article_text.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "script":
            continue
        if child.get("id") and str(child.get("id", "")).startswith("ad_"):
            continue
        if _has_class(child, "post-flash", "article-source", "ad-placeholder"):
            continue
        if child.get("class") and any("ad" in (c if isinstance(c, str) else " ".join(c)) for c in (child.get("class") or [])):
            continue
        if child.name == "p":
            iframe = child.find("iframe", src=True)
            if iframe:
                video_url, thumb = extract_video_from_iframe(iframe, base_url)
                if video_url:
                    components.append(make_video_component(video_url, thumbnail_image_url=thumb))
                    text = "".join(_inline_to_markdown(c) for c in child.children if c is not iframe).strip()
                    if text:
                        components.append({"type": "paragraph", "properties": {"text": text}})
                    continue
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "paragraph", "properties": {"text": text}})
            continue
        if child.name == "iframe":
            video_url, thumb = extract_video_from_iframe(child, base_url)
            if video_url:
                components.append(make_video_component(video_url, thumbnail_image_url=thumb))
            continue
        if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = child.get_text(strip=True)
            if text:
                level = int(child.name[1])
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
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
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    root = soup.find("div", class_=lambda c: c and "infinite-item" in (c if isinstance(c, str) else " ".join(c)) and "d-block" in (c if isinstance(c, str) else " ".join(c)))
    if not root:
        return {
            "metadata": {"title": None, "document_date": None, "authors": None, "categories": None, "tags": None},
            "components": {"components": []},
        }

    metadata = _get_metadata(root, base_url)

    components_list = []
    if metadata.get("title"):
        components_list.append({"type": "heading", "properties": {"text": metadata["title"], "level": 1}})
    components_list.extend(_lead_media_components(root))

    header = root.find("div", class_=lambda c: c and "post-header" in (c if isinstance(c, str) else " ".join(c)))
    if header:
        h2 = header.find("h2", class_=lambda c: c and "description" in (c if isinstance(c, str) else " ".join(c)))
        if h2 and h2.get_text(strip=True):
            components_list.append({"type": "heading", "properties": {"text": h2.get_text(strip=True), "level": 2}})

    article_text = root.find("div", class_=lambda c: c and "article-text" in (c if isinstance(c, str) else " ".join(c)))
    components_list.extend(_components_from_article_text(article_text, base_url))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class KamudanhaberParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    KamudanhaberParser().main()
