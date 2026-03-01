"""
Parse HTML from HTML_files/ (NewsLabTurkey article: elementor-widget-wrap with entry-title and entry-content) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://www.newslabturkey.org"

# Turkish month names -> number
_TR_MONTHS = {
    "ocak": "01", "şubat": "02", "mart": "03", "nisan": "04", "mayıs": "05",
    "haziran": "06", "temmuz": "07", "ağustos": "08", "eylül": "09",
    "ekim": "10", "kasım": "11", "aralık": "12",
}


def _has_class(tag, *names):
    if not tag or not getattr(tag, "get", None):
        return False
    c = tag.get("class")
    if not c:
        return False
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


def _parse_turkish_date(s: str) -> str | None:
    """e.g. '26 Ocak 2026' -> '2026-01-26T00:00:00+03:00'."""
    if not s or not s.strip():
        return None
    s = s.strip()
    # DD Month YYYY
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", s, re.IGNORECASE)
    if not m:
        return None
    day, month_name, year = m.groups()
    month_key = month_name.lower().replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ğ", "g")
    month = _TR_MONTHS.get(month_key)
    if not month:
        return None
    return f"{year}-{month}-{int(day):02d}T00:00:00+03:00"


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    h1 = soup.find("h1", class_=lambda c: c and "entry-title" in (c if isinstance(c, str) else " ".join(c)))
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    document_date = None
    for span in soup.find_all("span", attrs={"data-name": "date"}):
        content = span.find("span", class_=lambda c: c and "cmsmasters-postmeta__content" in (c if isinstance(c, str) else " ".join(c)))
        if content:
            text = content.get_text(strip=True)
            if text:
                document_date = _parse_turkish_date(text)
                break

    authors = None
    for span in soup.find_all("span", attrs={"data-name": "author"}):
        for author_link in span.find_all("a", rel="author", href=True):
            name = author_link.get_text(strip=True)
            if name:
                authors = [{"name": name, "url": urljoin(base_url, author_link["href"])}]
                break
        if authors:
            break

    categories = None
    for span in soup.find_all("span", attrs={"data-taxonomy": "category"}):
        term_link = span.find("a", class_=lambda c: c and "term" in (c if isinstance(c, str) else " ".join(c)), href=True)
        if term_link:
            name = term_link.get_text(strip=True)
            if name:
                categories = [{"name": name, "url": urljoin(base_url, term_link["href"])}]
            break

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors,
        "categories": categories,
        "tags": None,
    }


def _components_from_entry_content(entry_content: Tag, base_url: str) -> list:
    components = []
    if not entry_content:
        return components
    for child in entry_content.children:
        if not isinstance(child, Tag):
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
        elif child.name == "ul":
            for li in child.find_all("li", recursive=False):
                text = _inline_to_markdown(li).strip()
                if text:
                    components.append({"type": "paragraph", "properties": {"text": "• " + text}})
        elif child.name == "hr":
            components.append({"type": "paragraph", "properties": {"text": "---"}})
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)
    components_list = []

    # Title as first component (heading level 1)
    if metadata.get("title"):
        components_list.append({"type": "heading", "properties": {"text": metadata["title"], "level": 1}})

    # Featured image (before entry-content): cmsmasters-post-featured-image / cmsmasters-widget-image__wrap img
    feat = soup.find("div", class_=lambda c: c and "cmsmasters-post-featured-image" in (c if isinstance(c, str) else " ".join(c)))
    if feat:
        wrap = feat.find("div", class_=lambda c: c and "cmsmasters-widget-image__wrap" in (c if isinstance(c, str) else " ".join(c)))
        if wrap:
            img = wrap.find("img", src=True)
            if img:
                url = (img.get("src") or "").strip()
                if url and not url.startswith("data:"):
                    url = urljoin(base_url, url)
                if url:
                    props = {"url": url}
                    alt = (img.get("alt") or "").strip()
                    if alt:
                        props["description"] = alt
                    components_list.append({"type": "image", "properties": props})

    # Main content: .entry-content
    entry_content = soup.find("div", class_=lambda c: c and "entry-content" in (c if isinstance(c, str) else " ".join(c)))
    if entry_content:
        components_list.extend(_components_from_entry_content(entry_content, base_url))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class NewslabturkeyParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    NewslabturkeyParser().main()
