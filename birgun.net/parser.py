"""
Parse only article HTML (from HTML_files/): one div.contentdetail with H1 title and body up to "Sıradaki Haber".
Output: JSON in scraped_article_json_schema.json format (metadata + components), saved to Parsed_files/ with article slug.
Run from birgun.net folder: python parser.py [file.html ...]   (default: all from HTML_files/)
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Allow importing base package from project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_parser import BaseParser

BASE_URL = "https://www.birgun.net"


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


def _parse_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    document_date = _get_meta_content(soup, "datePublished") or _get_meta_content(soup, "datePublished", "property")
    if not document_date and _get_meta_content(soup, "ptime"):
        pt = _get_meta_content(soup, "ptime")
        if pt and len(pt) >= 14:
            document_date = f"{pt[:4]}-{pt[4:6]}-{pt[6:8]}T{pt[8:10]}:{pt[10:12]}:{pt[12:14]}:00+03:00"
    author_raw = _get_meta_content(soup, "articleAuthor")
    author_url = None
    section = _get_meta_content(soup, "articleSection")
    categories = [{"name": section.strip(), "url": None}] if section else None
    kw = _get_meta_content(soup, "keywords")
    tags = [{"name": t.strip(), "url": None} for t in kw.split(",") if t.strip()] if kw else None

    content = soup.find("div", class_=re.compile(r"contentdetail")) or soup.find("article") or soup.find("main")
    if content:
        # Author profile link: only use links that point to author profile (/profil/ or birgun.net/.../profil/)
        author_link = content.find("a", href=re.compile(r"^/profil/|profil", re.I))
        if not author_link:
            author_link = content.find("a", href=re.compile(r"^https?://[^/]*birgun\.net/profil/", re.I))
        if author_link and author_link.get("href"):
            author_url = _resolve_url(author_link["href"], base_url)
            if not author_raw:
                author_raw = (author_link.get_text(strip=True) or "").strip()
    authors = [{"name": (author_raw or "").strip() or None, "url": author_url}] if (author_raw or author_url) else None

    if content:
        cats_el = content.find(class_=re.compile(r"cats"))
        if cats_el:
            cat_links = cats_el.find_all("a", href=True)
            if cat_links:
                categories = [{"name": (a.get_text(strip=True) or "").strip(), "url": _resolve_url(a["href"], base_url)} for a in cat_links]
        tags_block = content.find(class_=re.compile(r"^tags$"))
        if tags_block:
            tag_links = tags_block.find_all("a", href=True)
            if tag_links:
                tags = [
                    {
                        "name": (lambda t: t[1:].strip() if t.startswith("#") else t)((a.get_text(strip=True) or "").strip()),
                        "url": _resolve_url(a["href"], base_url),
                    }
                    for a in tag_links
                ]

    title = _get_meta_content(soup, "og:title", "property") or _get_meta_content(soup, "title")
    if not title and content:
        h1 = content.find("h1")
        if h1:
            title = (h1.get_text(strip=True) or "").strip() or None

    return {
        "title": title or None,
        "document_date": document_date or None,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _is_inside_skip_block(tag) -> bool:
    """Skip author block (aplist, pitem, person-image), date (page-info), „Yazarın Son Yazıları“, tags."""
    skip_classes = ("aplist", "pitem", "person-image", "page-info", "latest-articles", "tags")
    parent = tag.find_parent(
        class_=lambda c: c and any(sc in (c if isinstance(c, str) else " ".join(c)) for sc in skip_classes)
    )
    return parent is not None


def _parse_components(soup: BeautifulSoup, base_url: str) -> list[dict]:
    content = soup.find("div", class_=re.compile(r"contentdetail")) or soup.find("article") or soup.find("main")
    if not content:
        return []
    components = []
    for tag in content.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "img", "blockquote", "ul", "ol", "table", "hr"]):
        if tag.find_parent(["li", "td", "th", "blockquote"]):
            continue
        if _is_inside_skip_block(tag):
            continue
        if tag.name == "img" and re.search(r"yazar-profil", tag.get("src") or "", re.I):
            continue
        if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = _html_to_markdown_text(tag)
            if text:
                components.append({"type": "heading", "properties": {"text": text, "level": int(tag.name[1])}})
        elif tag.name == "p":
            text = _html_to_markdown_text(tag)
            if text and not re.match(r"^\s*$", text):
                components.append({"type": "paragraph", "properties": {"text": text}})
        elif tag.name == "img":
            src = tag.get("src") or ""
            if re.search(
                r"(icon|logo|x\.png|x_w|facebook|whatsapp|twitter|bluesky|telegram|linkedin|google_news|share|button|abone_banner|/assets/images/)",
                src,
                re.I,
            ):
                continue
            url = _resolve_url(src, base_url) if src else None
            if url:
                caption = None
                parent = tag.find_parent("figure")
                if parent and parent.find("figcaption"):
                    caption = _html_to_markdown_text(parent.find("figcaption"))
                pa = tag.find_parent("a")
                link_url = _resolve_url(pa["href"], base_url) if pa and pa.get("href") else None
                components.append(
                    {"type": "image", "properties": _schema_props(url=url, caption=caption, description=tag.get("alt") or None, link_url=link_url)}
                )
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
    metadata = _parse_metadata(soup, base_url)
    components = _parse_components(soup, base_url)
    if metadata.get("title"):
        components.insert(0, {"type": "heading", "properties": {"text": metadata["title"], "level": 1}})
    return {
        "metadata": metadata,
        "components": {"components": components},
    }


class BirgunParser(BaseParser):
    """Birgun.net parser: contentdetail, meta + byline metadata, component extraction."""

    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    BirgunParser().main()
