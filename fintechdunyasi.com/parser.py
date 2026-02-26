"""
Parse HTML from HTML_files/ (Fintech Dünyası article) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://www.fintechdunyasi.com"

_TR_MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5,
    "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
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


def _normalize_adjacent_bold(md: str) -> str:
    """Merge adjacent bold markers from split HTML (e.g. <strong>T</strong><strong>echventure</strong> -> **Techventure**)."""
    if not md or "**" not in md:
        return md
    # Collapse **** between two bold segments: **X****Y** -> **XY** (repeat to handle multiple splits)
    for _ in range(10):
        prev = md
        md = re.sub(r"\*\*([^*]*)\*\*\*\*([^*]*)\*\*", r"**\1\2**", md)
        if md == prev:
            break
    return md


def _parse_turkish_date(text: str) -> str | None:
    """Parse '28 Nisan 2025' or '28 Nisan 2025, 14:30' to ISO 8601."""
    if not text or not text.strip():
        return None
    text = text.strip()
    # With time: "28 Nisan 2025, 14:30"
    m = re.search(r"(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s+(\d{4})\s*,\s*(\d{1,2}):(\d{2})", text)
    if m:
        day_s, month_s, year_s, hour_s, min_s = m.groups()
        month_num = _TR_MONTHS.get(month_s.lower())
        if month_num is not None:
            try:
                return dt(int(year_s), month_num, int(day_s), int(hour_s), int(min_s)).strftime("%Y-%m-%dT%H:%M:%S+03:00")
            except (ValueError, TypeError):
                pass
    # Date only: "28 Nisan 2025"
    m = re.search(r"(\d{1,2})\s+([a-zA-ZğüşıöçĞÜŞİÖÇ]+)\s+(\d{4})", text)
    if m:
        day_s, month_s, year_s = m.groups()
        month_num = _TR_MONTHS.get(month_s.lower())
        if month_num is not None:
            try:
                return dt(int(year_s), month_num, int(day_s), 12, 0).strftime("%Y-%m-%dT%H:%M:%S+03:00")
            except (ValueError, TypeError):
                pass
    return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    # Prefer h1.entry-title (main article title)
    title = None
    h1 = soup.find("h1", class_=lambda c: c and "entry-title" in (c if isinstance(c, str) else " ".join(c)))
    if not h1:
        h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    document_date = None
    time_el = soup.find("time", datetime=True)
    if time_el and time_el.get("datetime"):
        document_date = (time_el["datetime"] or "").strip()
    if not document_date:
        for el in soup.find_all(["time", "span", "div"]):
            t = el.get_text(strip=True) if el else ""
            if t and re.search(r"\d{1,2}\s+[A-Za-zğüşıöç]+\s+\d{4}", t):
                document_date = _parse_turkish_date(t)
                if document_date:
                    break

    authors = []
    for author_el in soup.find_all(class_=lambda c: c and "byline-part" in (c if isinstance(c, str) else " ".join(c)) and "author" in (c if isinstance(c, str) else " ".join(c))):
        cls = author_el.get("class") or []
        cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
        if "author-avatar" in cls_str:
            continue
        a = author_el.find("a", href=True)
        if a:
            name = (a.get_text(strip=True) or "").strip()
            if name:
                authors.append({"name": name, "url": urljoin(base_url, a["href"])})
                break
    if not authors:
        authors = None

    categories = None
    breadcrumb = soup.find(class_=lambda c: c and "breadcrumbs" in (c if isinstance(c, str) else " ".join(c)))
    if breadcrumb:
        links = breadcrumb.find_all("a", href=True)
        if links:
            categories = []
            for a in links:
                span = a.find("span")
                name = (span.get_text(strip=True) if span else a.get_text(strip=True) or "").strip()
                if not name:
                    name = (a.get_text(strip=True) or "").strip()
                if name and name.lower() not in ("anasayfa", "home"):
                    categories.append({"name": name, "url": urljoin(base_url, a["href"])})
            if not categories:
                categories = None
    if not categories:
        cat_link = soup.find("a", class_=lambda c: c and "cat " in (c if isinstance(c, str) else " ".join(c)) and "cat-with-bg" in (c if isinstance(c, str) else " ".join(c)), href=True)
        if cat_link:
            name = (cat_link.get_text(strip=True) or "").strip()
            if name:
                categories = [{"name": name, "url": urljoin(base_url, cat_link["href"])}]

    tags = None
    tag_cont = soup.find(class_=lambda c: c and "post-tags" in (c if isinstance(c, str) else " ".join(c)))
    if tag_cont:
        tag_links = tag_cont.find_all("a", href=True)
    else:
        tag_links = soup.find_all("a", href=re.compile(r"/tag/"))
    if tag_links:
        tags = []
        seen = set()
        for a in tag_links:
            name = (a.get_text(strip=True) or "").strip()
            if name and name not in seen:
                seen.add(name)
                tags.append({"name": name, "url": urljoin(base_url, a.get("href", ""))})
        if not tags:
            tags = None

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _is_lead_quote_p(tag: Tag) -> bool:
    """True if <p> looks like the styled lead quote (has-background / has-text-color, often starts with quote)."""
    if tag.name != "p":
        return False
    return _has_class(tag, "has-background", "has-text-color")


def _components_from_content(container: Tag, base_url: str) -> list:
    components = []
    if not container:
        return components
    children = [c for c in container.children if isinstance(c, Tag)]
    i = 0
    while i < len(children):
        child = children[i]
        if child.name in ("script", "noscript"):
            i += 1
            continue
        if _has_class(child, "_df_book", "wp-block-embed", "block-loader"):
            i += 1
            continue
        if child.name == "p":
            text = _normalize_adjacent_bold(_inline_to_markdown(child).strip())
            if not text:
                i += 1
                continue
            # Lead quote <p>: emit as citation (schema: citation_text, optional author_text)
            if _is_lead_quote_p(child):
                author_text = None
                skip_author_at = None
                for j in range(i + 1, min(i + 5, len(children))):
                    el = children[j]
                    if el.name == "p":
                        next_text = _inline_to_markdown(el).strip()
                        if next_text and el.find("strong") and not el.find("a", href=True):
                            author_text = _normalize_adjacent_bold(next_text)
                            if author_text:
                                skip_author_at = j
                        break
                    if el.name not in ("hr", "br"):
                        break
                props = {"citation_text": text}
                if author_text:
                    props["author_text"] = author_text
                components.append({"type": "citation", "properties": props})
                i += 1
                if skip_author_at is not None:
                    i = skip_author_at
                i += 1
                continue
            components.append({"type": "paragraph", "properties": {"text": text}})
            i += 1
            continue
        if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = child.get_text(strip=True)
            if text:
                level = int(child.name[1])
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
            i += 1
            continue
        if child.name == "blockquote":
            text = _normalize_adjacent_bold(_inline_to_markdown(child).strip())
            if text:
                components.append({"type": "citation", "properties": {"citation_text": text}})
            i += 1
            continue
        if child.name in ("figure", "div") and child.find("img", src=True):
            img = child.find("img", src=True)
            if img:
                url = (img.get("src") or "").strip()
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
            i += 1
            continue
        if child.name == "ul" or child.name == "ol":
            items = []
            for j, li in enumerate(child.find_all("li", recursive=False)):
                t = _normalize_adjacent_bold(_inline_to_markdown(li).strip())
                if t:
                    bullet = f"{j + 1}." if child.name == "ol" else "-"
                    items.append({"indent": 0, "bullet": bullet, "content": t})
            if items:
                components.append({"type": "list", "properties": {"items": items}})
            i += 1
            continue
        if _has_class(child, "wp-block-image", "figure"):
            img = child.find("img", src=True)
            if img:
                url = (img.get("src") or "").strip()
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
        i += 1
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []
    # Main article block (avoid related posts)
    main_article = soup.find("main")
    if not main_article:
        main_article = soup.find(class_=lambda c: c and "single-content" in (c if isinstance(c, str) else " ".join(c)))
    content = None
    def _is_entry_content(c):
        s = (c if isinstance(c, str) else " ".join(c)) if c else ""
        return "entry-content" in s and "entry-content-wrap" not in s
    if main_article:
        content = main_article.find("div", class_=_is_entry_content)
    if not content:
        content = soup.find("div", class_=_is_entry_content)
    if not content:
        content = soup.find("article") or soup.find("main") or soup.find("body") or soup

    # Lead image: .hero-wrap .hero img or first real img (prefer data-lazy-src if src is placeholder)
    hero = main_article.find("div", class_=lambda c: c and "hero-wrap" in (c if isinstance(c, str) else " ".join(c))) if main_article else None
    first_img = hero.find("img", src=True) if hero else soup.find("img", src=True)
    if first_img:
        url = (first_img.get("src") or first_img.get("data-lazy-src") or "").strip()
        if url and not url.startswith("data:"):
            url = urljoin(base_url, url)
            props = {"url": url}
            alt = (first_img.get("alt") or "").strip()
            if alt:
                props["description"] = alt
            components_list.append({"type": "image", "properties": props})

    components_list.extend(_components_from_content(content, base_url))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class FintechDunyasiParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    FintechDunyasiParser().main()
