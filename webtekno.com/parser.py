"""
Parse HTML from HTML_files/ (Webtekno article, full page without header/sidebar/ad) into scraped_article_json_schema format, write to Parsed_files/.
"""

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_parser import BaseParser

BASE_URL = "https://www.webtekno.com"

# YouTube thumbnail base for video component (schema: thumbnail_image_url)
YOUTUBE_THUMB = "https://i.ytimg.com/vi_webp/{id}/maxresdefault.webp"


def _youtube_video_id_from_tag(tag: Tag) -> str | None:
    """Extract YouTube video ID from div[data-video-id], iframe[src*='youtube.com/embed/'], or style background-image with i.ytimg.com/vi_webp/ID/."""
    if not isinstance(tag, Tag):
        return None
    vid = tag.get("data-video-id")
    if vid and isinstance(vid, str) and vid.strip():
        return vid.strip()
    if tag.name == "iframe":
        src = (tag.get("src") or "").strip()
        if "youtube.com/embed/" in src:
            m = re.search(r"embed/([a-zA-Z0-9_-]{11})", src)
            if m:
                return m.group(1)
    style = (tag.get("style") or "").strip()
    if "i.ytimg.com" in style and "vi_webp/" in style:
        m = re.search(r"vi_webp/([a-zA-Z0-9_-]{11})/", style)
        if m:
            return m.group(1)
    return None


def _video_component(video_id: str, *, name: str | None = None, caption: str | None = None, description: str | None = None) -> dict:
    """Build schema video component for YouTube (url required; optional name, caption, description, thumbnail)."""
    props = {
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail_image_url": YOUTUBE_THUMB.format(id=video_id),
    }
    if name:
        props["name"] = name
    if caption:
        props["caption"] = caption
    if description:
        props["description"] = description
    return {"type": "video", "properties": props}


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


def _normalize_datetime_to_iso(s: str) -> str | None:
    if not s or not s.strip():
        return None
    s = s.strip()
    if "T" in s and re.match(r"\d{4}-\d{2}-\d{2}", s):
        return re.sub(r"\.\d+Z$", "+00:00", s) if s.endswith("Z") else s
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{1,2}):(\d{2})", s)
    if m:
        d, mo, y, h, mi = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}:00+03:00"
    return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    detail = soup.find("div", class_=lambda c: c and "detail-content" in (c if isinstance(c, str) else " ".join(c)))
    if detail:
        h1 = detail.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)

    document_date = None
    time_el = soup.find("time", datetime=True)
    if time_el and time_el.get("datetime"):
        document_date = _normalize_datetime_to_iso(time_el["datetime"])

    authors = None
    author_link = None
    author_name_span = soup.find("span", class_=lambda c: c and "author-name" in (c if isinstance(c, str) else " ".join(c)))
    if author_name_span:
        author_link = author_name_span.find("a", href=lambda h: h and "/yazar/" in (h or ""))
    if not author_link and detail:
        author_block = detail.find("div", class_=lambda c: c and "author-and-share" in (c if isinstance(c, str) else " ".join(c)))
        if author_block:
            author_link = author_block.find("a", href=lambda h: h and "/yazar/" in (h or ""))
    if author_link:
        name = author_link.get_text(strip=True)
        if name:
            authors = [{"name": name, "url": urljoin(base_url, author_link.get("href", ""))}]
    if not authors and detail and detail.get("data-post-author"):
        authors = [{"name": detail["data-post-author"], "url": None}]

    categories = None
    breadcrumb = soup.find("div", class_=lambda c: c and "page-detail-breadcrumb" in (c if isinstance(c, str) else " ".join(c)))
    if breadcrumb:
        links = breadcrumb.find_all("a", href=True)
        if links:
            categories = []
            for a in links:
                # Prefer visible text (skip .hidden span)
                visible = a.find("span", class_=lambda c: c and "hidden" not in (c if isinstance(c, str) else " ".join(c)))
                name = (visible.get_text(strip=True) if visible else a.get_text(strip=True) or "").strip()
                if name:
                    categories.append({"name": name, "url": urljoin(base_url, a["href"])})
            if not categories:
                categories = None

    tags = None
    tags_div = soup.find("div", class_=lambda c: c and "content-tags-list" in (c if isinstance(c, str) else " ".join(c)))
    if tags_div:
        tag_links = tags_div.find_all("a", href=True)
        if tag_links:
            tags = [{"name": (a.get_text(strip=True) or "").strip(), "url": urljoin(base_url, a["href"])} for a in tag_links if (a.get_text(strip=True) or "").strip()]
            if not tags:
                tags = None

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _components_from_body(container: Tag, base_url: str) -> list:
    """Extract paragraphs, headings, images from .detail-content-body. Skip ad wrappers."""
    components = []
    if not container:
        return components
    for child in container.children:
        if not isinstance(child, Tag):
            continue
        cls = " ".join(child.get("class", []))
        if "content-adv-col" in cls:
            continue
        if child.name == "p":
            img = child.find("img", src=True)
            if img:
                url = (img.get("src") or img.get("data-src") or "").strip()
                if url and not url.startswith("data:"):
                    url = urljoin(base_url, url)
                if url:
                    props = {"url": url}
                    alt = (img.get("alt") or "").strip()
                    if alt:
                        props["description"] = alt
                    components.append({"type": "image", "properties": props})
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "paragraph", "properties": {"text": text}})
        elif child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = child.get_text(strip=True)
            if text:
                level = int(child.name[1])
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
        elif child.name == "div" and child.find("img", src=True):
            img = child.find("img", src=True)
            if img:
                url = (img.get("src") or img.get("data-src") or "").strip()
                if url and not url.startswith("data:"):
                    url = urljoin(base_url, url)
                if url:
                    props = {"url": url}
                    alt = (img.get("alt") or "").strip()
                    if alt:
                        props["description"] = alt
                    components.append({"type": "image", "properties": props})
        # YouTube embed: div[data-video-id] or .youtube-container with iframe
        elif child.name == "div":
            video_id = _youtube_video_id_from_tag(child)
            if not video_id:
                iframe = child.find("iframe", src=lambda s: s and "youtube.com/embed/" in (s or ""))
                if iframe:
                    video_id = _youtube_video_id_from_tag(iframe)
            if video_id:
                components.append(_video_component(video_id))
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []
    if metadata.get("title"):
        components_list.append({"type": "heading", "properties": {"text": metadata["title"], "level": 1}})
    detail = soup.find("div", class_=lambda c: c and "detail-content" in (c if isinstance(c, str) else " ".join(c)))
    if not detail:
        return {"metadata": metadata, "components": {"components": components_list}}

    # Excerpt (lead) first – as in the article
    excerpt = detail.find("div", class_=lambda c: c and "excerpt" in (c if isinstance(c, str) else " ".join(c)))
    if excerpt:
        h2 = excerpt.find("h2")
        if h2 and h2.get_text(strip=True):
            components_list.append({"type": "heading", "properties": {"text": h2.get_text(strip=True), "level": 2}})

    # Top video: YouTube embed outside .detail-content (e.g. .video-container above the article)
    for el in soup.find_all("div", attrs={"data-video-id": True}):
        if detail and el in detail.descendants:
            continue
        vid = _youtube_video_id_from_tag(el)
        if vid:
            components_list.append(_video_component(vid))
            break
    if not any(c.get("type") == "video" for c in components_list):
        for iframe in soup.find_all("iframe", src=lambda s: s and "youtube.com/embed/" in (s or "")):
            if detail and iframe in detail.descendants:
                continue
            vid = _youtube_video_id_from_tag(iframe)
            if vid:
                components_list.append(_video_component(vid))
                break
    if not any(c.get("type") == "video" for c in components_list):
        for el in soup.find_all("div", style=lambda s: s and "i.ytimg.com" in (s or "") and "vi_webp/" in (s or "")):
            if detail and el in detail.descendants:
                continue
            vid = _youtube_video_id_from_tag(el)
            if vid:
                components_list.append(_video_component(vid))
                break

    # Lead image (prefer data-src when src is a data URL)
    media = detail.find("div", class_=lambda c: c and "detail-content-media" in (c if isinstance(c, str) else " ".join(c)))
    if media:
        img = media.find("img")
        if img:
            src = (img.get("src") or "").strip()
            data_src = (img.get("data-src") or "").strip()
            url = data_src if (src.startswith("data:") and data_src) else (src or data_src)
            if url and not url.startswith("data:"):
                url = urljoin(base_url, url)
            if url:
                props = {"url": url}
                alt = (img.get("alt") or "").strip()
                if alt:
                    props["description"] = alt
                components_list.append({"type": "image", "properties": props})

    # Body: first .detail-content-body (skip ad blocks inside)
    body = detail.find("div", class_=lambda c: c and "detail-content-body" in (c if isinstance(c, str) else " ".join(c)))
    if body:
        components_list.extend(_components_from_body(body, base_url))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class WebteknoParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    WebteknoParser().main()
