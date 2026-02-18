"""
Parse HTML from HTML_files/ into scraped_article_json_schema.json format, write to Parsed_files/.
Configured for dogrulukpayi.com: section.r-section (or body for full HTML), metadata from head + JSON-LD.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SITE_DIR = Path(__file__).resolve().parent
ROOT = SITE_DIR.parent
HTML_FILES = SITE_DIR / "HTML_files"
PARSED_FILES = SITE_DIR / "Parsed_files"
BASE_URL = "https://www.dogrulukpayi.com"


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


def _figcaption_text(figcap: Tag) -> str:
    if not figcap:
        return ""
    parts = []
    for c in figcap.children:
        if isinstance(c, NavigableString):
            parts.append(str(c))
        elif isinstance(c, Tag) and c.name != "img":
            parts.append(c.get_text())
    return "".join(parts).strip()


def _json_ld_article(soup: BeautifulSoup) -> dict | None:
    """Return Article object from JSON-LD in head if present."""
    head = soup.find("head")
    if not head:
        return None
    for script in head.find_all("script", type=re.compile(r"application/ld\+json")):
        raw = (script.string or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("@type") == "Article":
                return data
            for item in (data.get("@graph") or data if isinstance(data, dict) else []):
                if isinstance(item, dict) and item.get("@type") == "Article":
                    return item
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Article":
                        return item
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _get_metadata(soup: BeautifulSoup, content_root: Tag, base_url: str) -> dict:
    head = soup.find("head")
    article_ld = _json_ld_article(soup)

    title = None
    if article_ld and article_ld.get("headline"):
        title = article_ld["headline"].strip()
    if not title and head:
        title_tag = head.find("title")
        if title_tag and title_tag.get_text(strip=True):
            title = title_tag.get_text(strip=True)
    og_title = head and head.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = (title or og_title.get("content", "")).strip()

    document_date = None
    doc_meta = (head and head.find("meta", attrs={"name": "datePublished"})) or (head and head.find("meta", attrs={"property": "article:published_time"}))
    if doc_meta and doc_meta.get("content"):
        document_date = doc_meta.get("content", "").strip()
    if not document_date and article_ld and article_ld.get("datePublished"):
        document_date = article_ld["datePublished"].strip()

    authors = []
    author_meta = (head and head.find("meta", attrs={"name": "author"})) or (head and head.find("meta", attrs={"name": "articleAuthor"})) or (head and head.find("meta", attrs={"property": "article:author"}))
    if author_meta and author_meta.get("content"):
        author_url = None
        if author_meta.get("property") == "article:author" and author_meta.get("content", "").startswith("http"):
            author_url = author_meta.get("content", "").strip()
        authors.append({"name": author_meta.get("content", "").strip(), "url": author_url})
    if not authors and article_ld:
        auth = article_ld.get("author")
        if isinstance(auth, dict) and auth.get("name"):
            authors.append({"name": auth["name"].strip(), "url": (auth.get("url") or "").strip() or None})
        elif isinstance(auth, list):
            for a in auth:
                if isinstance(a, dict) and a.get("name"):
                    authors.append({"name": a["name"].strip(), "url": (a.get("url") or "").strip() or None})
    if content_root:
        author_block = content_root.find(class_=lambda c: c and ("author" in (c if isinstance(c, str) else " ".join(c)) or "article-author" in (c if isinstance(c, str) else " ".join(c))))
        if author_block:
            a_tag = author_block.find("a")
            name = (a_tag.get_text(strip=True) if a_tag else author_block.get_text(strip=True)) or ""
            if name and not any(x["name"] == name.strip() for x in authors):
                author_url = None
                if a_tag and a_tag.get("href"):
                    author_url = urljoin(base_url, a_tag.get("href"))
                authors.append({"name": name.strip(), "url": author_url})

    categories = None
    head = soup.find("head")
    if head:
        for script in head.find_all("script", type=re.compile(r"application/ld\+json")):
            raw = (script.string or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
                graph = data.get("@graph") if isinstance(data, dict) else []
                for item in (graph if isinstance(graph, list) else []):
                    if isinstance(item, dict) and item.get("@type") == "BreadcrumbList":
                        elems = item.get("itemListElement") or []
                        if elems:
                            categories = []
                            for e in elems[:5]:
                                if isinstance(e, dict) and e.get("name"):
                                    categories.append({"name": e["name"].strip(), "url": (e.get("item") or "").strip() or None})
                        break
            except (json.JSONDecodeError, TypeError):
                pass
            if categories:
                break
    if not categories and content_root:
        cat_links = content_root.find_all("a", href=re.compile(r"^/(dogrulama|bulten|dogruluk-kontrolu)/"))
        if cat_links:
            seen = set()
            categories = []
            for a in cat_links[:5]:
                name = (a.get_text(strip=True) or "").strip() or None
                if not name or name in seen:
                    continue
                seen.add(name)
                href = a.get("href")
                categories.append({"name": name, "url": urljoin(base_url, href) if href else None})

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors if authors else None,
        "categories": categories,
        "tags": None,
    }


def _lead_media_components(content_root: Tag) -> list:
    out = []
    if not content_root:
        return out
    first_media = content_root.find("div", class_=lambda c: c and "article-main-image" in (c if isinstance(c, str) else " ".join(c)))
    if first_media:
        video = first_media.find("video")
        if video:
            source = video.find("source", src=True)
            if source:
                props = {"url": source["src"]}
                poster = (video.get("poster") or "").strip()
                if poster:
                    props["thumbnail_image_url"] = poster
                out.append({"type": "video", "properties": props})
                return out
        img = first_media.find("img", src=True)
        if img and img.get("src", "").strip():
            props = {"url": img["src"].strip()}
            alt = (img.get("alt") or "").strip()
            if alt:
                props["description"] = alt
            figcap = first_media.find("figcaption")
            if figcap:
                cap = _figcaption_text(figcap)
                if cap:
                    props["caption"] = cap
            out.append({"type": "image", "properties": props})
            return out
    figure = content_root.find("figure")
    if figure:
        img = figure.find("img", src=True)
        if img and img.get("src", "").strip():
            props = {"url": img["src"].strip()}
            alt = (img.get("alt") or "").strip()
            if alt:
                props["description"] = alt
            figcap = figure.find("figcaption")
            if figcap:
                cap = _figcaption_text(figcap)
                if cap:
                    props["caption"] = cap
            out.append({"type": "image", "properties": props})
    return out


def _block_components_from_content(container: Tag) -> list:
    """Walk container children and add components (same logic as turkiyegazetesi)."""
    components = []
    if not container:
        return components

    def add_heading(tag):
        text = tag.get_text(strip=True)
        if not text:
            return
        level = int(tag.name[1])
        components.append({"type": "heading", "properties": {"text": text, "level": level}})

    def add_paragraph(tag):
        text = _inline_to_markdown(tag).strip()
        if not text:
            return
        components.append({"type": "paragraph", "properties": {"text": text}})

    def add_citation(tag):
        text = tag.get_text(strip=True)
        if not text:
            return
        components.append({"type": "citation", "properties": {"citation_text": text}})

    def add_image_from_tag(cont):
        img = cont.find("img", src=True)
        if not img or not img.get("src", "").strip():
            return
        url = img["src"].strip()
        props = {"url": url}
        alt = (img.get("alt") or "").strip()
        if alt:
            props["description"] = alt
        figcap = cont.find("figcaption")
        if figcap:
            cap = _figcaption_text(figcap)
            if cap:
                props["caption"] = cap
        components.append({"type": "image", "properties": props})

    def add_list(tag):
        is_ol = tag.name == "ol"
        items = []
        for i, li in enumerate(tag.find_all("li", recursive=False)):
            content = _inline_to_markdown(li).strip()
            bullet = f"{i + 1}." if is_ol else "-"
            items.append({"indent": 0, "bullet": bullet, "content": content})
        if items:
            components.append({"type": "list", "properties": {"items": items}})

    def add_table(tag):
        headers = []
        rows = []
        thead = tag.find("thead")
        if thead and thead.find("tr"):
            headers = [th.get_text(strip=True) for th in thead.find("tr").find_all(["th", "td"])]
        tbody = tag.find("tbody") or tag
        for tr in tbody.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if not cells:
                continue
            if not headers and not rows:
                headers = cells
                continue
            rows.append(cells)
        if headers:
            components.append({"type": "table", "properties": {"headers": headers, "rows": rows}})

    def add_code_block(tag):
        code = tag.get_text()
        if code is not None:
            components.append({"type": "code_block", "properties": {"code": code, "language": None}})

    for child in container.children:
        if not isinstance(child, Tag):
            continue
        if child.find("path", attrs={"data-name": "LogoCheck"}):
            continue
        if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            add_heading(child)
            continue
        if child.name == "p":
            add_paragraph(child)
            continue
        if child.name == "blockquote":
            add_citation(child)
            continue
        if child.name == "figure":
            add_image_from_tag(child)
            continue
        if child.name == "hr":
            components.append({"type": "horizontal_ruler", "properties": {}})
            continue
        if child.name == "ul":
            add_list(child)
            continue
        if child.name == "ol":
            add_list(child)
            continue
        if child.name == "table":
            add_table(child)
            continue
        if child.name == "pre":
            add_code_block(child)
            continue
        if child.name == "div":
            fig = child.find("figure")
            if fig:
                add_image_from_tag(fig)
            elif child.find("img", src=True):
                add_image_from_tag(child)
            else:
                components.extend(_block_components_from_content(child))

    return components


def _get_next_data_content(html_str: str) -> dict | None:
    """If page is Next.js, return props.pageProps. Otherwise None."""
    idx = html_str.find('id="__NEXT_DATA__"')
    if idx < 0:
        idx = html_str.find("id='__NEXT_DATA__'")
    if idx < 0:
        return None
    start = html_str.find(">", idx) + 1
    if start <= 0:
        return None
    end = html_str.find("</script>", start)
    if end < 0:
        return None
    json_str = html_str[start:end].strip()
    try:
        data = json.loads(json_str)
        return (data.get("props") or {}).get("pageProps") or {}
    except (json.JSONDecodeError, TypeError):
        return None


def _html_to_markdown(html_fragment: str) -> str:
    """Convert HTML fragment (<i>, <b>, <a>...) to markdown."""
    if not html_fragment or not html_fragment.strip():
        return ""
    soup = BeautifulSoup("<div>" + html_fragment.replace("\x00", "") + "</div>", "html.parser")
    div = soup.find("div")
    return _inline_to_markdown(div).strip() if div else ""


def _components_from_next_content_blocks(content_blocks) -> list:
    """Convert contentBlocks from __NEXT_DATA__ to components. May be dict with .blocks, or list of {blocks: [...]} or [...]."""
    blocks = []
    if isinstance(content_blocks, dict) and "blocks" in content_blocks:
        blocks = content_blocks.get("blocks") or []
    elif isinstance(content_blocks, list):
        for entry in content_blocks:
            if isinstance(entry, dict) and "blocks" in entry:
                blocks.extend(entry.get("blocks") or [])
            elif isinstance(entry, dict) and entry.get("type"):
                blocks.append(entry)
    if not isinstance(blocks, list):
        blocks = []
    components = []
    for blk in blocks:
        if not isinstance(blk, dict):
            continue
        typ = blk.get("type") or ""
        data = blk.get("data") or {}
        if typ == "paragraph":
            text = (data.get("text") or "").strip()
            if text:
                text = _html_to_markdown(text)
                if text:
                    components.append({"type": "paragraph", "properties": {"text": text}})
        elif typ == "header":
            text = (data.get("text") or "").strip()
            if text:
                level = max(1, min(6, int(data.get("level") or 1)))
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
        elif typ == "list":
            items_raw = data.get("items") or []
            if not items_raw:
                continue
            is_ordered = (data.get("style") or "").lower() in ("ordered", "order")
            items = [
                {"indent": 0, "bullet": f"{i + 1}." if is_ordered else "-", "content": (it if isinstance(it, str) else str(it)).strip()}
                for i, it in enumerate(items_raw)
            ]
            items = [x for x in items if x["content"]]
            if items:
                components.append({"type": "list", "properties": {"items": items}})
        elif typ == "image":
            file_obj = data.get("file") or {}
            url = (file_obj.get("url") or "").strip()
            if url:
                props = {"url": url}
                caption = (data.get("caption") or "").strip()
                if caption:
                    props["caption"] = caption
                components.append({"type": "image", "properties": props})
        elif typ == "quote" or typ == "citation":
            text = (data.get("text") or "").strip()
            if text:
                text = _html_to_markdown(text)
                if text:
                    components.append({"type": "citation", "properties": {"citation_text": text}})
    return components


def _metadata_from_next_content(content: dict, base_url: str) -> dict | None:
    """Enrich/return metadata from pageProps.content (title, authors, published, categories)."""
    if not content or not isinstance(content, dict):
        return None
    doc_date = None
    if content.get("published"):
        pub = content["published"]
        if isinstance(pub, str):
            doc_date = pub.strip()
        elif isinstance(pub, dict) and pub.get("date"):
            doc_date = pub["date"]
    authors = []
    for a in content.get("authors") or []:
        if not isinstance(a, dict):
            continue
        name = (a.get("name") or a.get("title") or a.get("fullName") or "").strip()
        if not name:
            continue
        url = (a.get("url") or "").strip() or None
        if not url and a.get("slug"):
            url = (base_url.rstrip("/") + "/yazar/" + str(a["slug"]).strip()).strip() or None
        authors.append({"name": name, "url": url})
    categories = None
    for c in content.get("categories") or []:
        if isinstance(c, dict) and c.get("name"):
            categories = categories or []
            categories.append({"name": c["name"].strip(), "url": (c.get("url") or c.get("slug") or "").strip() or None})
    return {
        "document_date": doc_date,
        "authors": authors if authors else None,
        "categories": categories,
        "title": (content.get("title") or "").strip(),
    }


def _collect_blocks_from_body(body: Tag) -> list:
    """For full HTML without section: collect all block elements in order (h1–h6, p, figure, ...), skip script/style/svg."""
    blocks = []
    skip_tags = {"script", "style", "link", "noscript", "svg"}

    def walk(tag):
        if not isinstance(tag, Tag):
            return
        if tag.name in skip_tags:
            return
        if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "figure", "hr", "ul", "ol", "table", "pre"):
            blocks.append(tag)
            return
        for c in tag.children:
            walk(c)

    for c in body.children:
        walk(c)
    return blocks


def _components_from_blocks(blocks: list) -> list:
    """Convert list of block tags to components (same logic as _block_components_from_content)."""
    components = []
    for tag in blocks:
        if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = tag.get_text(strip=True)
            if text:
                level = int(tag.name[1])
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
        elif tag.name == "p":
            text = _inline_to_markdown(tag).strip()
            if text:
                components.append({"type": "paragraph", "properties": {"text": text}})
        elif tag.name == "blockquote":
            text = tag.get_text(strip=True)
            if text:
                components.append({"type": "citation", "properties": {"citation_text": text}})
        elif tag.name == "figure" or (tag.name == "div" and tag.find("img", src=True)):
            img = tag.find("img", src=True)
            if img and img.get("src", "").strip():
                props = {"url": img["src"].strip()}
                alt = (img.get("alt") or "").strip()
                if alt:
                    props["description"] = alt
                figcap = tag.find("figcaption")
                if figcap:
                    cap = _figcaption_text(figcap)
                    if cap:
                        props["caption"] = cap
                components.append({"type": "image", "properties": props})
        elif tag.name == "hr":
            components.append({"type": "horizontal_ruler", "properties": {}})
        elif tag.name == "ul":
            items = [{"indent": 0, "bullet": "-", "content": _inline_to_markdown(li).strip()} for li in tag.find_all("li", recursive=False)]
            if items:
                components.append({"type": "list", "properties": {"items": items}})
        elif tag.name == "ol":
            items = [{"indent": 0, "bullet": f"{i+1}.", "content": _inline_to_markdown(li).strip()} for i, li in enumerate(tag.find_all("li", recursive=False))]
            if items:
                components.append({"type": "list", "properties": {"items": items}})
        elif tag.name == "table":
            thead = tag.find("thead")
            headers = []
            if thead and thead.find("tr"):
                headers = [th.get_text(strip=True) for th in thead.find("tr").find_all(["th", "td"])]
            rows = []
            for tr in (tag.find("tbody") or tag).find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                if not headers and not rows:
                    headers = cells
                    continue
                rows.append(cells)
            if headers:
                components.append({"type": "table", "properties": {"headers": headers, "rows": rows}})
        elif tag.name == "pre":
            code = tag.get_text()
            if code is not None:
                components.append({"type": "code_block", "properties": {"code": code, "language": None}})
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    """
    Parse HTML for dogrulukpayi.com: section.r-section, or __NEXT_DATA__.contentBlocks, or body/JSON-LD.
    """
    html_str = html_raw.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html_raw, "html.parser")
    content_root = soup.find("section", class_=lambda c: c and "r-section" in (c if isinstance(c, str) else " ".join(c)) and "r-section-withcard" in (c if isinstance(c, str) else " ".join(c)))
    if not content_root:
        content_root = soup.find("section", class_=lambda c: c and "r-section" in (c if isinstance(c, str) else " ".join(c)))

    metadata = _get_metadata(soup, content_root, base_url)
    components_list = []

    if content_root:
        components_list.extend(_lead_media_components(content_root))
        components_list.extend(_block_components_from_content(content_root))
    else:
        next_props = _get_next_data_content(html_str)
        content = (next_props or {}).get("content") if isinstance(next_props, dict) else None
        content_blocks_raw = content.get("contentBlocks") if content else None
        if content and content_blocks_raw:
            meta_next = _metadata_from_next_content(content, base_url)
            if meta_next:
                if meta_next.get("document_date") and not metadata.get("document_date"):
                    metadata["document_date"] = meta_next["document_date"]
                if meta_next.get("authors"):
                    metadata["authors"] = meta_next["authors"]
                if meta_next.get("categories") and not metadata.get("categories"):
                    metadata["categories"] = meta_next["categories"]
                if meta_next.get("title"):
                    metadata["title"] = meta_next["title"]
            components_list = _components_from_next_content_blocks(content_blocks_raw)
            title = (content.get("title") or "").strip()
            if title and (not components_list or components_list[0].get("type") != "heading"):
                components_list.insert(0, {"type": "heading", "properties": {"text": title, "level": 1}})
        if not components_list:
            body = soup.find("body")
            if body:
                blocks = _collect_blocks_from_body(body)
                components_list.extend(_lead_media_components(body))
                components_list.extend(_components_from_blocks(blocks))
            if not components_list:
                article_ld = _json_ld_article(soup)
                if article_ld and article_ld.get("description"):
                    desc = article_ld["description"].strip()
                    if desc:
                        components_list.append({"type": "paragraph", "properties": {"text": desc}})
                if article_ld and article_ld.get("headline") and not any(c.get("type") == "heading" for c in components_list):
                    components_list.insert(0, {"type": "heading", "properties": {"text": article_ld["headline"].strip(), "level": 1}})

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


def main():
    PARSED_FILES.mkdir(parents=True, exist_ok=True)
    paths = list(HTML_FILES.glob("*.html")) if HTML_FILES.exists() else []
    if not paths and len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        print("No HTML files. Run fetch_html.py first.", file=sys.stderr)
        sys.exit(1)
    for path in paths:
        if not path.exists():
            continue
        doc = parse_article_html(path.read_bytes())
        (PARSED_FILES / f"{path.stem}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {path.stem}.json")
    print(f"Written to {PARSED_FILES}")


if __name__ == "__main__":
    main()
