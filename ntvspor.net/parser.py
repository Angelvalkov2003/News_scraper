"""
Parse HTML from HTML_files/ (NTV Spor article, container-infinity) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://www.ntvspor.net"


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
    if tag.name == "h3":
        return "**" + "".join(_inline_to_markdown(c) for c in tag.children) + "**"
    return "".join(_inline_to_markdown(c) for c in tag.children)


def _normalize_datetime_to_iso(s: str) -> str | None:
    """Convert datetime attribute or '11.02.2026 15:03' to ISO 8601."""
    if not s or not s.strip():
        return None
    s = s.strip()
    # Already ISO-like: 2026-02-11T12:03:53.351Z
    if "T" in s and re.match(r"\d{4}-\d{2}-\d{2}", s):
        return re.sub(r"\.\d+Z$", "+00:00", s) if s.endswith("Z") else s
    # DD.MM.YYYY HH:MM
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{1,2}):(\d{2})", s)
    if m:
        d, mo, y, h, mi = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}:00+03:00"
    return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    # data-title on container or h1 in .info-text-card
    container = soup.find(
        "div",
        class_=lambda c: c and "container-infinity" in (c if isinstance(c, str) else " ".join(c)),
    )
    if container and container.get("data-title"):
        title = (container["data-title"] or "").strip()
    if not title:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)

    document_date = None
    time_el = soup.find("time", datetime=True)
    if time_el and time_el.get("datetime"):
        document_date = _normalize_datetime_to_iso(time_el["datetime"])
    if not document_date and time_el:
        document_date = _normalize_datetime_to_iso(time_el.get_text(strip=True))

    authors = None
    # Author: <p> next to time in .info-text-card (e.g. "Haber Merkezi")
    info_card = soup.find("div", class_=lambda c: c and "info-text-card" in (c if isinstance(c, str) else " ".join(c)))
    if info_card:
        ps = info_card.find_all("p")
        for p in ps:
            t = p.get_text(strip=True)
            if t and t != title and not re.match(r"^\d{2}\.\d{2}\.\d{4}", t):
                authors = [{"name": t, "url": None}]
                break

    categories = None
    nav = soup.find("nav", attrs={"aria-label": "Breadcrumb"})
    if nav:
        categories = []
        for li in nav.find_all("li"):
            if li.get("aria-current") == "page":
                continue  # skip current page (article title)
            a = li.find("a", href=True)
            if not a:
                continue
            name = (a.get_text(strip=True) or "").strip()
            if name:
                categories.append({"name": name, "url": urljoin(base_url, a["href"])})
        if not categories:
            categories = None

    tags = None
    tag_ul = soup.find("ul", class_=lambda c: c and "flex" in (c if isinstance(c, str) else " ".join(c)))
    if tag_ul:
        tag_links = tag_ul.find_all("a", href=True)
        if tag_links:
            tags = []
            for a in tag_links:
                name = (a.get_text(strip=True) or "").strip()
                if name:
                    tags.append({"name": name, "url": urljoin(base_url, a["href"])})
            if not tags:
                tags = None

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _table_to_component(table_tag: Tag) -> dict | None:
    """Convert <table> to schema table component: headers + rows. Supports figure > table."""
    table = table_tag if table_tag.name == "table" else table_tag.find("table")
    if not table:
        return None
    headers = []
    thead = table.find("thead")
    if thead:
        tr = thead.find("tr")
        if tr:
            for th in tr.find_all(["th", "td"]):
                headers.append(th.get_text(strip=True) or "")
    if not headers:
        first_row = table.find("tr")
        if first_row:
            for cell in first_row.find_all(["th", "td"]):
                headers.append(cell.get_text(strip=True) or "")
    rows = []
    tbody = table.find("tbody")
    body_rows = (tbody.find_all("tr") if tbody else []) or table.find_all("tr")[1:]
    for tr in body_rows:
        row = []
        for cell in tr.find_all(["td", "th"]):
            row.append(_inline_to_markdown(cell).strip() or "")
        if row:
            rows.append(row)
    if not headers and not rows:
        return None
    if not headers and rows:
        headers = [""] * len(rows[0]) if rows else []
    props = {"headers": headers, "rows": rows}
    fig = table_tag if table_tag.name == "figure" else table_tag.find_parent("figure")
    if fig:
        cap = fig.find("figcaption")
        if cap and cap.get_text(strip=True):
            props["caption"] = cap.get_text(strip=True)
    return {"type": "table", "properties": props}


def _components_from_ck_content(container: Tag) -> list:
    """Extract paragraphs and headings from .ck-content or .text-size-18 div."""
    components = []
    if not container:
        return components
    content_div = container.find("div", class_=lambda c: c and "ck-content" in (c if isinstance(c, str) else " ".join(c)))
    if not content_div:
        content_div = container.find("div", class_=lambda c: c and "text-size-18" in (c if isinstance(c, str) else " ".join(c)))
    if not content_div:
        content_div = container
    for child in content_div.children:
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
        elif child.name == "figure" and child.find("table"):
            tbl = _table_to_component(child)
            if tbl:
                components.append(tbl)
        elif child.name == "table":
            tbl = _table_to_component(child)
            if tbl:
                components.append(tbl)
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []

    # Summary: first h2 with text-size-24 / font-semibold in main column
    main_col = soup.find("div", class_=lambda c: c and "md:col-span-8" in (c if isinstance(c, str) else " ".join(c)))
    if main_col:
        summary_h2 = main_col.find("h2", class_=lambda c: c and "text-size-24" in (c if isinstance(c, str) else " ".join(c)))
        if summary_h2 and summary_h2.get_text(strip=True):
            components_list.append({
                "type": "heading",
                "properties": {"text": summary_h2.get_text(strip=True), "level": 2},
            })

    # Content: .inread-photo-area > section.inread-content-area > div[data-imageindex]
    inread_areas = soup.find_all("div", class_=lambda c: c and "inread-photo-area" in (c if isinstance(c, str) else " ".join(c)))
    for area in inread_areas:
        sections = area.find_all("section", class_=lambda c: c and "inread-content-area" in (c if isinstance(c, str) else " ".join(c)))
        for section in sections:
            blocks = section.find_all("div", attrs={"data-imageindex": True})
            for block in blocks:
                # Image first
                img = block.find("img", src=True)
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
                # Then text from ck-content
                comps = _components_from_ck_content(block)
                components_list.extend(comps)

    # If no inread areas, try single .info-text-card + any content divs
    if not components_list and main_col:
        for div in main_col.find_all("div", class_=lambda c: c and "ck-content" in (c if isinstance(c, str) else " ".join(c))):
            comps = _components_from_ck_content(div.parent)
            components_list.extend(comps)

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class NtvsporParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    NtvsporParser().main()
