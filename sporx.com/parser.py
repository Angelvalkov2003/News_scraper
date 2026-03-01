"""
Parse HTML from HTML_files/ (sporx.com: div.pg-left.wide-682 with #titleheadline, #haberimg, #haberbody)
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

BASE_URL = "https://www.sporx.com"

# Turkish month names -> number
_TR_MONTHS = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}


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


def _parse_turkish_datetime(text: str) -> str | None:
    """Parse '11 Şubat 2026 14:58' to ISO 8601."""
    if not text or not text.strip():
        return None
    text = text.strip()
    m = re.search(r"(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s+(\d{4})\s+(\d{1,2}):(\d{2})", text)
    if m:
        day_s, month_s, year_s, hour_s, min_s = m.groups()
        month_num = _TR_MONTHS.get(month_s.lower())
        if month_num is not None:
            try:
                return f"{year_s}-{month_num:02d}-{int(day_s):02d}T{int(hour_s):02d}:{int(min_s):02d}:00+03:00"
            except (ValueError, TypeError):
                pass
    m = re.search(r"(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s+(\d{4})", text)
    if m:
        day_s, month_s, year_s = m.groups()
        month_num = _TR_MONTHS.get(month_s.lower())
        if month_num is not None:
            try:
                return f"{year_s}-{month_num:02d}-{int(day_s):02d}T00:00:00+03:00"
            except (ValueError, TypeError):
                pass
    return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    h1 = soup.find("h1", id="habertitle")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    document_date = None
    date_block = soup.find("div", id="haberdate")
    if date_block:
        span = date_block.find("span")
        if span and span.get_text(strip=True):
            document_date = _parse_turkish_datetime(span.get_text())

    authors = None
    kaynak = soup.find("div", class_=lambda c: c and "haberkaynak" in (c if isinstance(c, str) else " ".join(c)))
    if kaynak and kaynak.get_text(strip=True):
        source_text = kaynak.get_text(strip=True)
        if source_text:
            authors = [{"name": source_text, "url": None}]

    categories = None
    breadcrumb = soup.find("ul", class_=lambda c: c and "breadcrumb" in (c if isinstance(c, str) else " ".join(c)))
    if breadcrumb:
        items = breadcrumb.find_all("li", class_=lambda c: c and "breadcrumb-item" in (c if isinstance(c, str) else " ".join(c)))
        cat_list = []
        for li in items:
            a = li.find("a", href=True)
            if not a:
                continue
            span = a.find("span", itemprop="name")
            name = (span.get_text(strip=True) if span else a.get_text(strip=True)) or None
            if name:
                href = a.get("href") or ""
                url = urljoin(base_url, href) if href.startswith("/") else (href if href.startswith("http") else urljoin(base_url, href))
                cat_list.append({"name": name, "url": url})
        if cat_list:
            categories = cat_list

    return {
        "title": title,
        "document_date": document_date,
        "authors": authors,
        "categories": categories,
        "tags": None,
    }


def _paragraphs_from_haberic_body(haberic_body: Tag) -> list:
    """Extract paragraphs from #habericBody: div.no-select content split by <br><br>."""
    if not haberic_body:
        return []
    no_select = haberic_body.find("div", class_=lambda c: c and "no-select" in (c if isinstance(c, str) else " ".join(c)))
    if not no_select:
        return []
    parts = []
    current = []
    for child in no_select.children:
        if isinstance(child, NavigableString):
            current.append(str(child))
        elif isinstance(child, Tag):
            if child.name == "br":
                if current:
                    text = "".join(current).strip()
                    if text:
                        parts.append(text)
                    current = []
            elif child.name == "script":
                continue
            else:
                current.append(_inline_to_markdown(child))
    if current:
        text = "".join(current).strip()
        if text:
            parts.append(text)
    return parts


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []

    if metadata.get("title"):
        components_list.append({"type": "heading", "properties": {"text": metadata["title"], "level": 1}})

    h2 = soup.find("h2", id="haberheadline")
    if h2:
        adm = h2.find("div", id="admdiv")
        if adm:
            adm.decompose()
        summary = "".join(_inline_to_markdown(c) for c in h2.children).strip()
        if summary:
            components_list.append({"type": "heading", "properties": {"text": summary, "level": 2}})

    haberimg = soup.find("div", id="haberimg")
    if haberimg:
        img = haberimg.find("img", src=True)
        if img:
            url = (img.get("src") or "").strip()
            if url and not url.startswith("data:"):
                url = urljoin(base_url, url) if url.startswith("/") else ("https:" + url if url.startswith("//") else url)
            if url:
                props = {"url": url}
                alt = (img.get("alt") or "").strip()
                if alt:
                    props["description"] = alt
                cap_div = haberimg.find("div", style=re.compile(r"position:\s*absolute"))
                if cap_div and cap_div.get_text(strip=True):
                    props["caption"] = cap_div.get_text(strip=True)
                components_list.append({"type": "image", "properties": props})

    haberic_body = soup.find("div", id="habericBody")
    for text in _paragraphs_from_haberic_body(haberic_body):
        if text:
            components_list.append({"type": "paragraph", "properties": {"text": text}})

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class SporxParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    SporxParser().main()
