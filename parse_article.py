"""
Parse raw HTML article pages into JSON following scraped_article_json_schema.json.
No LLMs; deterministic extraction. Main content only (no nav, ads, sidebars).
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


# Base URL for resolving relative links (birgun.net)
DEFAULT_BASE_URL = "https://www.birgun.net"


def _decode_html(raw: bytes) -> str:
    """Decode HTML, handling UTF-16 BOM and UTF-8."""
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def _get_meta_content(soup: BeautifulSoup, name: str, attr: str = "name") -> str | None:
    """Get content of first meta tag by name or property."""
    tag = soup.find("meta", attrs={attr: name})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _html_to_markdown_text(el) -> str:
    """Convert inline HTML to plain text; links become [text](url)."""
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


def _text_only(el) -> str:
    """Get plain text, no markdown."""
    if el is None:
        return ""
    return el.get_text(separator=" ", strip=True)


def _schema_props(**kwargs: str | None) -> dict:
    """Build component properties dict; omit keys whose value is None (schema does not allow null for optional string fields)."""
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
    """Extract metadata from head (meta tags)."""
    document_date = _get_meta_content(soup, "datePublished") or _get_meta_content(
        soup, "datePublished", "property"
    )
    if not document_date and _get_meta_content(soup, "ptime"):
        # ptime = 20260211125300
        pt = _get_meta_content(soup, "ptime")
        if pt and len(pt) >= 14:
            document_date = f"{pt[:4]}-{pt[4:6]}-{pt[6:8]}T{pt[8:10]}:{pt[10:12]}:{pt[12:14]}:00+03:00"

    author_raw = _get_meta_content(soup, "articleAuthor")
    authors = None
    if author_raw:
        authors = [{"name": author_raw.strip(), "url": None}]

    section = _get_meta_content(soup, "articleSection")
    categories = None
    if section:
        categories = [{"name": section.strip(), "url": None}]

    kw = _get_meta_content(soup, "keywords")
    tags = None
    if kw:
        tags = [{"name": t.strip(), "url": None} for t in kw.split(",") if t.strip()]

    return {
        "document_date": document_date or None,
        "authors": authors,
        "categories": categories,
        "tags": tags,
    }


def _parse_components(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract ordered components from main article content (div.contentdetail)."""
    content = soup.find("div", class_=re.compile(r"contentdetail"))
    if not content:
        content = soup.find("article") or soup.find("main")
    if not content:
        return []

    components = []
    # Walk in document order: direct and nested block-level elements we care about
    for tag in content.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "img", "blockquote", "ul", "ol", "table", "hr"]):
        # Skip if inside a nested structure we already processed (e.g. li inside ul)
        if tag.find_parent(["li", "td", "th", "blockquote"]):
            continue

        if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag.name[1])
            text = _html_to_markdown_text(tag)
            if text:
                components.append({
                    "type": "heading",
                    "properties": {"text": text, "level": level},
                })

        elif tag.name == "p":
            text = _html_to_markdown_text(tag)
            if text and not re.match(r"^\s*$", text):
                components.append({
                    "type": "paragraph",
                    "properties": {"text": text},
                })

        elif tag.name == "img":
            src = tag.get("src") or ""
            # Skip social/share icons, logos, banners, and small UI images
            if re.search(r"(icon|logo|x\.png|x_w|facebook|whatsapp|twitter|bluesky|telegram|linkedin|google_news|share|button|abone_banner|/assets/images/)", src, re.I):
                continue
            url = _resolve_url(src, base_url) if src else None
            if url:
                caption = None
                alt = tag.get("alt") or ""
                # caption from parent figure or next sibling
                parent = tag.find_parent("figure")
                if parent:
                    cap_el = parent.find("figcaption")
                    if cap_el:
                        caption = _html_to_markdown_text(cap_el)
                link_url = None
                parent_a = tag.find_parent("a")
                if parent_a and parent_a.get("href"):
                    link_url = _resolve_url(parent_a["href"], base_url)
                components.append({
                    "type": "image",
                    "properties": _schema_props(url=url, caption=caption or None, description=alt or None, link_url=link_url),
                })

        elif tag.name == "blockquote":
            text = _html_to_markdown_text(tag)
            if text:
                components.append({
                    "type": "citation",
                    "properties": {"citation_text": text},
                })

        elif tag.name in ("ul", "ol"):
            items = []
            for i, li in enumerate(tag.find_all("li", recursive=False)):
                content_text = _html_to_markdown_text(li)
                if not content_text.strip():
                    continue
                bullet = "1." if tag.name == "ol" else "-"
                if tag.name == "ol":
                    bullet = f"{i + 1}."
                items.append({"indent": 0, "bullet": bullet, "content": content_text})
            if items:
                components.append({"type": "list", "properties": {"items": items}})

        elif tag.name == "table":
            headers = []
            thead = tag.find("thead")
            if thead:
                row = thead.find("tr")
                if row:
                    for th in row.find_all(["th", "td"]):
                        headers.append(_html_to_markdown_text(th))
            if not headers:
                first = tag.find("tr")
                if first:
                    for th in first.find_all(["th", "td"]):
                        headers.append(_html_to_markdown_text(th))
            rows = []
            tbody = tag.find("tbody") or tag
            for tr in tbody.find_all("tr"):
                if thead and tr.parent == thead:
                    continue
                row = [_html_to_markdown_text(td) for td in tr.find_all(["td", "th"])]
                if row:
                    rows.append(row)
            if headers or rows:
                components.append({
                    "type": "table",
                    "properties": {"headers": headers or [""], "rows": rows},
                })

        elif tag.name == "hr":
            components.append({"type": "horizontal_ruler", "properties": {}})

    return components


def parse_article_html(html_raw: bytes, base_url: str = DEFAULT_BASE_URL) -> dict:
    """Parse one article HTML into schema-compliant JSON object."""
    html_str = _decode_html(html_raw)
    soup = BeautifulSoup(html_str, "html.parser")

    metadata = _parse_metadata(soup, base_url)
    comps = _parse_components(soup, base_url)

    return {
        "metadata": metadata,
        "components": {"components": comps},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse article HTML to schema JSON.")
    parser.add_argument(
        "html_files",
        nargs="+",
        type=Path,
        help="Paths to raw HTML article files",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("parsed_articles.json"),
        help="Output JSON file (default: parsed_articles.json)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help="Base URL for resolving relative links",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate output against scraped_article_json_schema.json after parsing",
    )
    parser.add_argument(
        "--per-file",
        action="store_true",
        help="Write one JSON file per HTML (output path = directory; each file = one article in schema format)",
    )
    args = parser.parse_args()

    results = []
    for path in args.html_files:
        if not path.exists():
            print(f"Skip (not found): {path}", file=sys.stderr)
            continue
        raw = path.read_bytes()
        try:
            doc = parse_article_html(raw, base_url=args.base_url)
            results.append((path, doc))
        except Exception as e:
            print(f"Error parsing {path}: {e}", file=sys.stderr)

    if args.per_file:
        out_dir = args.output if args.output.suffix != ".json" else args.output.parent
        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        for path, doc in results:
            stem = path.stem
            out_path = out_dir / f"{stem}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            print(f"  {out_path.name}")
        print(f"Saved {len(results)} article(s) to {out_dir} (one JSON per HTML)")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        docs_only = [doc for _, doc in results]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(docs_only, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(results)} article(s) to {args.output}")

    if args.validate and results:
        from schema_validator import validate_documents
        docs_only = [doc for _, doc in results]
        errs = validate_documents(docs_only)
        failed = [(i, e) for i, e in errs if e]
        if failed:
            for i, e in failed:
                print(f"Validation failed document [{i}]:", file=sys.stderr)
                for msg in e:
                    print(f"  {msg}", file=sys.stderr)
            sys.exit(1)
        print("Schema validation passed.")


if __name__ == "__main__":
    main()
