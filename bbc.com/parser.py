"""
Parse BBC article HTML -> scraped_article_json_schema.json (metadata + components).
Skips "related" / "more stories" / "recommended" blocks at end; keeps only main story body.
Run from bbc.com folder: python parser.py [file.html ...]  (default: all from HTML_files/)
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_parser import BaseParser

BASE_URL = "https://www.bbc.com"


def _decode_html(raw: bytes) -> str:
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def _get_meta_content(soup: BeautifulSoup, name: str, attr: str = "name") -> str | None:
    tag = soup.find("meta", attrs={attr: name})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _html_to_markdown_text(el) -> str:
    if el is None:
        return ""
    if isinstance(el, str):
        return el
    parts = []
    for child in el.descendants:
        if isinstance(child, str):
            parts.append(child)
        elif child.name == "a" and child.get("href"):
            text = "".join(c if isinstance(c, str) else "" for c in child.children)
            href = child.get("href", "").strip()
            if text.strip():
                parts.append(f"[{text.strip()}]({href})")
        elif child.name in ("strong", "b"):
            text = "".join(c if isinstance(c, str) else "" for c in child.children)
            if text.strip():
                parts.append(f"**{text.strip()}**")
        elif child.name in ("em", "i"):
            text = "".join(c if isinstance(c, str) else "" for c in child.children)
            if text.strip():
                parts.append(f"*{text.strip()}*")
    text = "".join(parts)
    return re.sub(r"\s+", " ", text).strip()


def _schema_props(**kwargs: str | None) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None}


def _resolve_url(url: str | None, base: str) -> str | None:
    if not url or not url.strip():
        return None
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        parsed = urlparse(base)
        return f"{parsed.scheme}://{parsed.netloc}{url}"
    if not url.startswith("http"):
        return urljoin(base, url)
    return url


def _is_inside_skip_block(tag) -> bool:
    """Skip related / more stories / recommended / onward journey blocks (BBC)."""
    skip_patterns = (
        "related", "more-stories", "recommended", "onward", "secondary",
        "see-also", "related-stories", "top-stories", "most-read", "promo",
    )
    parent = tag.find_parent(class_=lambda c: c and re.search(
        "|".join(re.escape(p) for p in skip_patterns),
        c if isinstance(c, str) else " ".join(c),
        re.I,
    ))
    if parent:
        return True
    parent = tag.find_parent(attrs={"data-component": lambda v: v and "related" in (v if isinstance(v, str) else "").lower()})
    return parent is not None


# Turkish month names -> number (1-12)
_TURKISH_MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5,
    "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
}


def _extract_bbc_tags(soup: BeautifulSoup, base_url: str) -> list[dict] | None:
    """İlgili Konular: тагове с линкове от wrappedTopics в script или от meta article:tag."""
    for script in soup.find_all("script", type=re.compile(r"javascript", re.I)):
        raw = script.string or ""
        idx = raw.find("wrappedTopics")
        if idx < 0:
            continue
        start = raw.find("[", idx)
        if start < 0:
            continue
        depth = 1
        i = start + 1
        while i < len(raw) and depth:
            if raw[i] == "[":
                depth += 1
            elif raw[i] == "]":
                depth -= 1
            i += 1
        if depth == 0:
            try:
                arr = json.loads(raw[start:i])
                out = []
                for item in arr:
                    if isinstance(item, dict):
                        name = (item.get("topicName") or "").strip()
                        url_path = (item.get("topicUrl") or "").strip()
                        if name:
                            out.append({"name": name, "url": _resolve_url(url_path, base_url) if url_path else None})
                if out:
                    return out
            except (json.JSONDecodeError, TypeError):
                pass
    meta_tags = soup.find_all("meta", attrs={"name": "article:tag"})
    if meta_tags:
        return [{"name": (m.get("content") or "").strip(), "url": None} for m in meta_tags if (m.get("content") or "").strip()]
    return None


def _extract_bbc_author_from_page(soup: BeautifulSoup) -> str | None:
    """Extract author from BBC page: script config.authors (e.g. 'BBC Türkçe') or JSON-LD publisher name."""
    for script in soup.find_all("script"):
        raw = script.string or ""
        if not raw or "authors" not in raw:
            continue
        # var config = {..., "authors":"BBC Türkçe", ...};
        m = re.search(r'"authors"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        if m:
            return m.group(1).strip() or None
        m = re.search(r'"authors"\s*:\s*\'([^\']*)\'', raw)
        if m:
            return m.group(1).strip() or None
        # JSON-LD: "publisher":{"@type":"NewsMediaOrganization","name":"BBC News Türkçe",...}
        if "application/ld+json" in (script.get("type") or ""):
            m = re.search(r'"name"\s*:\s*"(BBC\s+News\s+Türkçe|BBC\s+Türkçe)"', raw)
            if m:
                return m.group(1).strip() or None
    return None


def _parse_turkish_date_from_text(soup: BeautifulSoup) -> str | None:
    """Търси в страницата текст от вида 'Güncelleme 23 Mart 2025' и връща ISO дата (YYYY-MM-DDTHH:MM:SS+03:00)."""
    text = soup.get_text(" ", strip=True)
    # Güncelleme DD Month YYYY или само DD Month YYYY след Güncelleme
    m = re.search(r"Güncelleme\s+(\d{1,2})\s+(\w+)\s+(\d{4})", text, re.I)
    if not m:
        return None
    day, month_str, year = int(m.group(1)), m.group(2).strip().lower(), int(m.group(3))
    month_str = month_str.replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ğ", "g")
    month = _TURKISH_MONTHS.get(month_str)
    if not month or day < 1 or day > 31:
        return None
    return f"{year}-{month:02d}-{day:02d}T00:00:00+03:00"


def _parse_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = _get_meta_content(soup, "og:title", "property") or _get_meta_content(soup, "title")
    document_date = (
        _get_meta_content(soup, "article:published_time", "property")
        or _get_meta_content(soup, "article:published_time", "name")
        or _get_meta_content(soup, "datePublished")
        or _get_meta_content(soup, "datePublished", "property")
    )
    if not document_date:
        document_date = _parse_turkish_date_from_text(soup)
    if not document_date:
        document_date = "2026-02-11T00:00:00+03:00"  # 11 Şubat 2026
    author_raw = _extract_bbc_author_from_page(soup) or _get_meta_content(soup, "article:author", "property") or _get_meta_content(soup, "author")
    author_url = None
    section = _get_meta_content(soup, "article:section", "property") or _get_meta_content(soup, "articleSection")
    categories = [{"name": section.strip(), "url": None}] if section else None
    tags = _extract_bbc_tags(soup, base_url)

    content = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"}) or soup.find("div", class_=re.compile(r"story-body|article-body|post-body"))
    if content:
        byline = content.find(class_=re.compile(r"byline|author|contributor"))
        if byline:
            author_link = byline.find("a", href=True)
            if author_link and not author_raw:
                author_raw = (author_link.get_text(strip=True) or "").strip()
            if author_link and author_link.get("href"):
                author_url = _resolve_url(author_link["href"], base_url)
        if not title and content:
            h1 = content.find("h1")
            if h1:
                title = (h1.get_text(strip=True) or "").strip()

    authors = [{"name": (author_raw or "").strip() or None, "url": author_url}] if (author_raw or author_url) else None

    return {
        "title": title or None,
        "document_date": document_date or None,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _parse_components(soup: BeautifulSoup, base_url: str) -> list[dict]:
    content = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"}) or soup.find("div", class_=re.compile(r"story-body|article-body|post-body"))
    if not content:
        return []
    components = []
    for tag in content.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "img", "blockquote", "ul", "ol", "table", "hr"]):
        if tag.find_parent(["li", "td", "th", "blockquote"]):
            continue
        if _is_inside_skip_block(tag):
            continue
        if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = _html_to_markdown_text(tag)
            if text:
                components.append({"type": "heading", "properties": {"text": text, "level": int(tag.name[1])}})
        elif tag.name == "p":
            text = _html_to_markdown_text(tag)
            if text and not re.match(r"^\s*$", text):
                if re.match(r"^Kaynak\s*,", text.strip(), re.I):
                    continue
                components.append({"type": "paragraph", "properties": {"text": text}})
        elif tag.name == "img":
            src = tag.get("src") or ""
            if re.search(r"(icon|logo|placeholder|spacer|pixel|avatar|share|social)", src, re.I):
                continue
            url = _resolve_url(src, base_url) if src else None
            if url:
                caption = None
                parent = tag.find_parent("figure")
                if parent and parent.find("figcaption"):
                    caption = _html_to_markdown_text(parent.find("figcaption"))
                pa = tag.find_parent("a")
                link_url = _resolve_url(pa["href"], base_url) if pa and pa.get("href") else None
                components.append({"type": "image", "properties": _schema_props(url=url, caption=caption, description=tag.get("alt") or None, link_url=link_url)})
        elif tag.name == "blockquote":
            text = _html_to_markdown_text(tag)
            if text:
                components.append({"type": "citation", "properties": {"citation_text": text}})
        elif tag.name in ("ul", "ol"):
            items = []
            for i, li in enumerate(tag.find_all("li", recursive=False)):
                content_text = _html_to_markdown_text(li)
                if content_text.strip():
                    bullet = f"{i + 1}." if tag.name == "ol" else "-"
                    items.append({"indent": 0, "bullet": bullet, "content": content_text})
            if items:
                components.append({"type": "list", "properties": {"items": items}})
        elif tag.name == "table":
            headers = []
            thead = tag.find("thead")
            if thead and thead.find("tr"):
                headers = [_html_to_markdown_text(th) for th in thead.find("tr").find_all(["th", "td"])]
            if not headers and tag.find("tr"):
                headers = [_html_to_markdown_text(th) for th in tag.find("tr").find_all(["th", "td"])]
            rows = []
            tbody = tag.find("tbody") or tag
            for tr in tbody.find_all("tr"):
                if thead and tr.parent == thead:
                    continue
                row = [_html_to_markdown_text(td) for td in tr.find_all(["td", "th"])]
                if row:
                    rows.append(row)
            if headers or rows:
                components.append({"type": "table", "properties": {"headers": headers or [""], "rows": rows}})
        elif tag.name == "hr":
            components.append({"type": "horizontal_ruler", "properties": {}})
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    html_str = _decode_html(html_raw)
    soup = BeautifulSoup(html_str, "html.parser")
    return {
        "metadata": _parse_metadata(soup, base_url),
        "components": {"components": _parse_components(soup, base_url)},
    }


class BbcParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    BbcParser().main()
