"""
Parse HTML from HTML_files/ (Ajansspor article, news-detail) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://ajansspor.com"


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


def _normalize_datetime_to_iso(s: str) -> str | None:
    """Convert '11.02.2026 - 14:55' or datetime attr to ISO 8601."""
    if not s or not s.strip():
        return None
    s = s.strip()
    if "T" in s and re.match(r"\d{4}-\d{2}-\d{2}", s):
        return re.sub(r"\.\d+Z$", "+00:00", s) if s.endswith("Z") else s
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*[-–]\s*(\d{1,2}):(\d{2})", s)
    if m:
        d, mo, y, h, mi = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}:00+03:00"
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})", s)
    if m:
        d, mo, y, h, mi = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}:00+03:00"
    return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    document_date = None
    time_el = soup.find("time", datetime=True)
    if time_el and time_el.get("datetime"):
        document_date = _normalize_datetime_to_iso(time_el["datetime"])
    if not document_date and time_el:
        document_date = _normalize_datetime_to_iso(time_el.get_text(strip=True))
    if not document_date:
        for el in soup.find_all(["span", "div"], class_=True):
            c = " ".join(el.get("class", []))
            if "date" in c or "time" in c:
                document_date = _normalize_datetime_to_iso(el.get_text(strip=True))
                if document_date:
                    break

    authors = None
    author_link = soup.find("a", class_=lambda c: c and "author-name" in (c if isinstance(c, str) else " ".join(c)))
    if author_link:
        name = author_link.get_text(strip=True)
        if name:
            author_url = urljoin(base_url, author_link.get("href", "")) if author_link.get("href") else None
            authors = [{"name": name, "url": author_url}]

    categories = None
    # Breadcrumb: <div class="d-flex flex-row align-items-center"><a href="/">Spor Haberleri</a><a href="/kategori/...">Futbol</a><span>article title</span></div> – only <a>, not the span (article title)
    breadcrumb_div = None
    for div in soup.find_all("div", class_=lambda c: c and "d-flex" in (c if isinstance(c, str) else " ".join(c)) and "align-items-center" in (c if isinstance(c, str) else " ".join(c))):
        if div.find("a", href="/") and div.find("a", href=lambda h: h and "/kategori/" in h):
            breadcrumb_div = div
            break
    if breadcrumb_div:
        breadcrumb_links = breadcrumb_div.find_all("a", href=True)
        if breadcrumb_links:
            categories = []
            for a in breadcrumb_links:
                name = (a.get_text(strip=True) or "").strip()
                if name:
                    categories.append({"name": name, "url": urljoin(base_url, a["href"])})
            if not categories:
                categories = None
    if categories is None:
        # Fallback when breadcrumb is outside extracted article: use .news-tags
        news_tags_for_cat = soup.find("div", class_=lambda c: c and "news-tags" in (c if isinstance(c, str) else " ".join(c)))
        if news_tags_for_cat:
            links = news_tags_for_cat.find_all("a", href=True)
            if links:
                categories = [{"name": (a.get_text(strip=True) or "").strip(), "url": urljoin(base_url, a["href"])} for a in links if (a.get_text(strip=True) or "").strip()]
                if not categories:
                    categories = None

    tags = None
    news_tags = soup.find("div", class_=lambda c: c and "news-tags" in (c if isinstance(c, str) else " ".join(c)))
    if news_tags:
        tag_links = news_tags.find_all("a", href=True)
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


def _components_from_content(container: Tag, base_url: str) -> list:
    """Extract paragraphs, headings, images from article body."""
    components = []
    if not container:
        return components
    for child in container.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "p":
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "paragraph", "properties": {"text": text}})
        elif child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = child.get_text(strip=True)
            if text:
                level = int(child.name[1])
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
        elif child.name in ("figure", "div") and child.find("img", src=True):
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
                    cap = child.find("figcaption")
                    if cap and cap.get_text(strip=True):
                        props["caption"] = cap.get_text(strip=True)
                    components.append({"type": "image", "properties": props})
        elif child.name == "blockquote":
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "citation", "properties": {"citation_text": text}})
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []
    article_el = soup.find("article") or soup

    # Lead from .news-spot
    news_spot = article_el.find("div", class_=lambda c: c and "news-spot" in (c if isinstance(c, str) else " ".join(c)))
    if news_spot:
        for p in news_spot.find_all("p"):
            text = _inline_to_markdown(p).strip()
            if text:
                components_list.append({"type": "paragraph", "properties": {"text": text}})

    # Content blocks: .article-content (each has optional .news-cover, then .news-detail with h2 + article)
    for block in article_el.find_all("div", class_=lambda c: c and "article-content" in (c if isinstance(c, str) else " ".join(c))):
        news_cover = block.find("div", class_=lambda c: c and "news-cover" in (c if isinstance(c, str) else " ".join(c)))
        if news_cover:
            img = news_cover.find("img", src=True)
            if img:
                url = (img.get("src") or img.get("data-src") or "").strip()
                if url and not url.startswith("data:"):
                    url = urljoin(base_url, url)
                if url:
                    props = {"url": url}
                    alt = (img.get("alt") or "").strip()
                    if alt:
                        props["description"] = alt
                    components_list.append({"type": "image", "properties": props})
        news_detail = block.find("div", class_=lambda c: c and "news-detail" in (c if isinstance(c, str) else " ".join(c)))
        if news_detail:
            for child in news_detail.children:
                if not isinstance(child, Tag):
                    continue
                if child.name == "h2":
                    text = child.get_text(strip=True)
                    if text:
                        components_list.append({"type": "heading", "properties": {"text": text, "level": 2}})
                elif child.name == "article":
                    for p in child.find_all("p"):
                        text = _inline_to_markdown(p).strip()
                        if text:
                            components_list.append({"type": "paragraph", "properties": {"text": text}})

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class AjanssporParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    AjanssporParser().main()
