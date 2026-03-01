"""
Parse HTML from HTML_files/ (iklimhaber.org: div.col-mod-main with header, thumbnail, entry-content)
into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://www.iklimhaber.org"

# Turkish month names -> number
_TR_MONTHS = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}


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


def _parse_turkish_date(text: str) -> str | None:
    """Parse '11 Şubat 2026' to ISO 8601 date."""
    if not text or not text.strip():
        return None
    text = text.strip()
    m = re.search(r"(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s+(\d{4})", text)
    if not m:
        return None
    day_s, month_s, year_s = m.groups()
    month_num = _TR_MONTHS.get(month_s.lower())
    if month_num is None:
        return None
    try:
        return f"{year_s}-{month_num:02d}-{int(day_s):02d}T00:00:00+03:00"
    except (ValueError, TypeError):
        return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    h1 = soup.find("h1", class_=lambda c: c and "entry-title" in (c if isinstance(c, str) else " ".join(c)))
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    document_date = None
    date_el = soup.find("span", class_=lambda c: c and "updated" in (c if isinstance(c, str) else " ".join(c)))
    if date_el and date_el.get_text(strip=True):
        document_date = _parse_turkish_date(date_el.get_text())

    authors = None
    author_el = soup.find("span", class_=lambda c: c and "fn" in (c if isinstance(c, str) else " ".join(c)))
    if author_el:
        a = author_el.find("a", href=True)
        if a:
            name = a.get_text(strip=True)
            if name:
                author_url = urljoin(base_url, a.get("href", "")) if a.get("href") else None
                authors = [{"name": name, "url": author_url}]

    categories = None
    cat_a = soup.find("span", class_=lambda c: c and "meta-category" in (c if isinstance(c, str) else " ".join(c)))
    if cat_a:
        a = cat_a.find("a", href=True)
        if a and a.get_text(strip=True):
            categories = [{"name": a.get_text(strip=True), "url": urljoin(base_url, a.get("href", ""))}]

    tags = None
    meta_tags = soup.find("div", class_=lambda c: c and "meta-tags" in (c if isinstance(c, str) else " ".join(c)))
    if meta_tags:
        tag_links = meta_tags.find_all("a", href=True, rel="tag")
        if tag_links:
            tags = []
            for a in tag_links:
                name = a.get_text(strip=True)
                if name:
                    tags.append({"name": name, "url": urljoin(base_url, a.get("href", ""))})

    return {
        "title": title,
        "document_date": document_date,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _components_from_entry_content(entry_content: Tag, base_url: str) -> list:
    """Walk .entry-content.herald-entry-content: h3 -> heading, p -> paragraph. Skip mailmunch, meta-tags."""
    components = []
    if not entry_content:
        return components
    for child in entry_content.children:
        if not isinstance(child, Tag):
            continue
        if _has_class(child, "mailmunch-forms-before-post", "mailmunch-forms-in-post-middle", "mailmunch-forms-after-post"):
            continue
        if _has_class(child, "meta-tags"):
            continue
        if child.name == "h3" or (child.name == "h2" or child.name == "h4"):
            text = child.get_text(strip=True)
            if text:
                level = int(child.name[1]) if child.name[1].isdigit() else 3
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
            continue
        if child.name == "p":
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "paragraph", "properties": {"text": text}})
            continue
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []

    if metadata.get("title"):
        components_list.append({"type": "heading", "properties": {"text": metadata["title"], "level": 1}})

    # Lead image from .herald-post-thumbnail
    thumb = soup.find("div", class_=lambda c: c and "herald-post-thumbnail" in (c if isinstance(c, str) else " ".join(c)))
    if thumb:
        img = thumb.find("img", src=True)
        if img:
            url = (img.get("src") or "").strip()
            if url and not url.startswith("data:"):
                url = urljoin(base_url, url)
            if url:
                props = {"url": url}
                alt = (img.get("alt") or "").strip()
                if alt:
                    props["description"] = alt
                fig = thumb.find("figure", class_=lambda c: c and "wp-caption-text" in (c if isinstance(c, str) else " ".join(c)))
                if not fig:
                    fig = thumb.find("figure")
                if fig and fig.get_text(strip=True):
                    props["caption"] = fig.get_text(strip=True)
                components_list.append({"type": "image", "properties": props})

    # Body from .entry-content.herald-entry-content
    entry_content = soup.find("div", class_=lambda c: c and "entry-content" in (c if isinstance(c, str) else " ".join(c)) and "herald-entry-content" in (c if isinstance(c, str) else " ".join(c)))
    if not entry_content:
        entry_content = soup.find("div", class_=lambda c: c and "entry-content" in (c if isinstance(c, str) else " ".join(c)))
    if entry_content:
        components_list.extend(_components_from_entry_content(entry_content, base_url))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class IklimhaberParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    IklimhaberParser().main()
