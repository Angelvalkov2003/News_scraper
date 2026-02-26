"""
Parse HTML from HTML_files/ (Ekonomi Gazetesi article, single-post-outer) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://www.ekonomigazetesi.com"


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
    """Convert '2026-02-11 14:08:00' to ISO 8601."""
    if not s or not s.strip():
        return None
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        g = m.groups()
        if len(g) == 5:
            return f"{g[0]}-{g[1]}-{g[2]}T{g[3]}:{g[4]}:00+03:00"
        return f"{g[0]}-{g[1]}-{g[2]}T{g[3]}:{g[4]}:{g[5] or '00'}+03:00"
    return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    h1 = soup.find("h1", class_=lambda c: c and "s-title" in (c if isinstance(c, str) else " ".join(c)))
    if not h1:
        h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    document_date = None
    time_el = soup.find("time", class_=lambda c: c and "published" in (c if isinstance(c, str) else " ".join(c)), datetime=True)
    if time_el and time_el.get("datetime"):
        document_date = _normalize_datetime_to_iso(time_el["datetime"])
    if not document_date:
        time_el = soup.find("time", datetime=True)
        if time_el and time_el.get("datetime"):
            document_date = _normalize_datetime_to_iso(time_el["datetime"])

    authors = None
    # Author can be set from first-byline paragraph in entry-content (see parse_article_html)

    categories = None
    cat_links = soup.select(".p-categories a.p-category[href]")
    if not cat_links:
        breadcrumb = soup.find("nav", class_=lambda c: c and "breadcrumb" in (c if isinstance(c, str) else " ".join(c)))
        if breadcrumb:
            cat_links = breadcrumb.find_all("a", href=True)
    if cat_links:
        categories = []
        for a in cat_links:
            name = (a.get_text(strip=True) or "").strip()
            if name and name.lower() not in ("ekonomi gazetesi", "anasayfa"):
                categories.append({"name": name, "url": urljoin(base_url, a["href"])})
        if not categories:
            categories = None

    tags = None

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _looks_like_byline_paragraph(p_tag: Tag) -> bool:
    """True if <p> contains only a single <strong> with short text like 'ERHAN BEDİR/BURSA'."""
    if p_tag.name != "p":
        return False
    strongs = p_tag.find_all("strong")
    if len(strongs) != 1:
        return False
    text = p_tag.get_text(strip=True)
    if not text or len(text) > 100:
        return False
    # Byline often: NAME/PLACE or NAME - PLACE, or all caps
    if "/" in text:
        return True
    if text.isupper() or (len(text) < 50 and not any(c in text for c in ".:?!")):
        return True
    return False


def _components_from_entry_content(container: Tag, base_url: str) -> tuple[list, str | None]:
    """Return (components, byline_author or None). If first <p> is a byline (e.g. <strong>ERHAN BEDİR/BURSA</strong>), return its text as author and do not add it as paragraph."""
    components = []
    byline_author = None
    if not container:
        return components, None
    first_p_checked = False
    for child in container.children:
        if not isinstance(child, Tag):
            continue
        if _has_class(child, "ruby-table-contents", "rbtoc", "entry-bottom", "e-shared-sec", "sticky-share-list-buffer"):
            continue
        if child.name == "p":
            text = _inline_to_markdown(child).strip()
            if text:
                if not first_p_checked and _looks_like_byline_paragraph(child):
                    byline_author = child.get_text(strip=True)
                    first_p_checked = True
                    continue
                first_p_checked = True
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
        if child.name in ("figure", "div") and child.find("img", src=True):
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
            continue
        if child.name == "ul" or child.name == "ol":
            items = []
            for j, li in enumerate(child.find_all("li", recursive=False)):
                t = _inline_to_markdown(li).strip()
                if t:
                    bullet = f"{j + 1}." if child.name == "ol" else "-"
                    items.append({"indent": 0, "bullet": bullet, "content": t})
            if items:
                components.append({"type": "list", "properties": {"items": items}})
            continue
    return components, byline_author


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []

    # 1) Tagline (h3.s-tagline) first – above the image
    tagline = soup.find("h3", class_=lambda c: c and "s-tagline" in (c if isinstance(c, str) else " ".join(c)))
    if tagline and tagline.get_text(strip=True):
        components_list.append({"type": "heading", "properties": {"text": tagline.get_text(strip=True), "level": 2}})

    # 2) Lead image: .s-feat img or .featured-lightbox-trigger
    feat = soup.find("div", class_=lambda c: c and "s-feat" in (c if isinstance(c, str) else " ".join(c)))
    if feat:
        img = feat.find("img", src=True)
        if not img:
            a = feat.find("a", href=True)
            if a and a.get("href"):
                url = urljoin(base_url, a["href"])
                if not url.startswith("data:"):
                    components_list.append({"type": "image", "properties": {"url": url}})
        else:
            url = (img.get("src") or img.get("data-src") or "").strip()
            if url and not url.startswith("data:"):
                url = urljoin(base_url, url)
                props = {"url": url}
                alt = (img.get("alt") or "").strip()
                if alt:
                    props["description"] = alt
                components_list.append({"type": "image", "properties": props})

    # 3) Main content: .entry-content; first <p> with <strong>NAME/PLACE</strong> → author, not paragraph
    article = soup.find("article") or soup
    content = article.find("div", class_=lambda c: c and "entry-content" in (c if isinstance(c, str) else " ".join(c)))
    if content:
        entry_components, byline_author = _components_from_entry_content(content, base_url)
        if byline_author:
            metadata["authors"] = [{"name": byline_author, "url": None}]
        components_list.extend(entry_components)

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class EkonomiGazetesiParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    EkonomiGazetesiParser().main()
