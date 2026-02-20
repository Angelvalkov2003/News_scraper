"""
Parse HTML from HTML_files/ (first article.col.col7 + div.col.col10 only) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://www.forbes.com.tr"

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
    """Parse '11 Şubat 2026, 14:44' to ISO 8601."""
    if not text or not text.strip():
        return None
    text = text.strip()
    # "11 Şubat 2026, 14:44" or "11 Şubat 2026, 14:44"
    m = re.search(r"(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s+(\d{4})\s*,\s*(\d{1,2}):(\d{2})", text)
    if not m:
        return None
    day_s, month_s, year_s, hour_s, min_s = m.groups()
    month_s_lower = month_s.lower()
    month_num = _TR_MONTHS.get(month_s_lower)
    if month_num is None:
        return None
    try:
        return dt(int(year_s), month_num, int(day_s), int(hour_s), int(min_s)).strftime("%Y-%m-%dT%H:%M:%S+03:00")
    except (ValueError, TypeError):
        return None


def _get_metadata(soup: BeautifulSoup, article: Tag | None, col10: Tag | None, base_url: str) -> dict:
    title = None
    if col10:
        h1 = col10.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)

    document_date = None
    if article:
        # "11 Şubat 2026, 14:44" in a span inside .border-bottom.pb-10 or similar
        header_meta = article.find("div", class_=lambda c: c and "border-bottom" in (c if isinstance(c, str) else " ".join(c)) and "pb-10" in (c if isinstance(c, str) else " ".join(c)))
        if header_meta:
            span = header_meta.find("span")
            if span and span.get_text(strip=True):
                document_date = _parse_turkish_date(span.get_text())
        if not document_date:
            for span in (article.find_all("span") or []):
                t = span.get_text(strip=True)
                if t and re.search(r"\d{1,2}\s+[A-Za-zğüşıöç]+\s+\d{4}", t):
                    document_date = _parse_turkish_date(t)
                    if document_date:
                        break

    authors = []  # Forbes snippet has no author in article block; can be extended if present elsewhere

    categories = None
    if col10:
        nav = col10.find("nav", class_=lambda c: c and "icerik_nav" in (c if isinstance(c, str) else " ".join(c)))
        if nav:
            links = nav.find_all("a", href=True)
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

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors if authors else None,
        "categories": categories,
        "tags": tags,
    }


def _lead_media_components(article: Tag) -> list:
    out = []
    resim = article.find("div", class_=lambda c: c and "makaledetay_ust_resim" in (c if isinstance(c, str) else " ".join(c)))
    if not resim:
        return out
    img = resim.find("img", src=True)
    if img:
        url = (img.get("src") or "").strip()
        if not url:
            a = resim.find("a", href=True)
            if a and a.get("href"):
                url = (a["href"] or "").strip()
        if url:
            props = {"url": url}
            alt = (img.get("alt") or "").strip()
            if alt:
                props["description"] = alt
            out.append({"type": "image", "properties": props})
    return out


def _components_from_yazialani(content: Tag) -> list:
    components = []
    if not content:
        return components
    for child in content.children:
        if not isinstance(child, Tag):
            continue
        if _has_class(child, "article_masthead_ad", "makale_paylas"):
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
    article = soup.find("article", class_=lambda c: c and "col" in (c if isinstance(c, str) else " ".join(c)) and "col7" in (c if isinstance(c, str) else " ".join(c)))
    col10 = soup.find("div", class_=lambda c: c and "col" in (c if isinstance(c, str) else " ".join(c)) and "col10" in (c if isinstance(c, str) else " ".join(c)))

    if not article and not col10:
        return {
            "metadata": {"title": None, "document_date": None, "authors": None, "categories": None, "tags": None},
            "components": {"components": []},
        }

    metadata = _get_metadata(soup, article, col10, base_url)

    components_list = []
    if article:
        spot = article.find("div", class_=lambda c: c and "makaledetay_spot" in (c if isinstance(c, str) else " ".join(c)))
        if spot and spot.get_text(strip=True):
            components_list.append({"type": "heading", "properties": {"text": spot.get_text(strip=True), "level": 2}})
        components_list.extend(_lead_media_components(article))
        yazialani = article.find("div", class_=lambda c: c and "makaledetay_yazialani" in (c if isinstance(c, str) else " ".join(c)))
        components_list.extend(_components_from_yazialani(yazialani))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class ForbesParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    ForbesParser().main()
