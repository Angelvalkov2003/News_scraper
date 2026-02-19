"""
Parse HTML from HTML_files/ into scraped_article_json_schema.json format, write to Parsed_files/.
HTML is minimal (fetch_html.py): head with meta, div.article-scope > article.
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

BASE_URL = "https://www.turkiyegazetesi.com.tr"


def _has_class(tag, *names):
    if not tag.get("class"):
        return False
    c = tag["class"]
    s = " ".join(c) if isinstance(c, list) else c
    return any(n in s for n in names)


def _inline_to_markdown(tag) -> str:
    """Convert inline HTML (strong, i, em) to markdown. Recursive."""
    if isinstance(tag, NavigableString):
        return str(tag)
    if not isinstance(tag, Tag):
        return ""
    if tag.name == "strong" or tag.name == "b":
        return "**" + "".join(_inline_to_markdown(c) for c in tag.children) + "**"
    if tag.name in ("i", "em"):
        return "*" + "".join(_inline_to_markdown(c) for c in tag.children) + "*"
    if tag.name == "a":
        text = "".join(_inline_to_markdown(c) for c in tag.children)
        href = tag.get("href") or ""
        return f"[{text}]({href})" if text or href else text
    return "".join(_inline_to_markdown(c) for c in tag.children)


def _figcaption_text(figcap: Tag) -> str:
    """Text of figcaption without icon img."""
    if not figcap:
        return ""
    parts = []
    for c in figcap.children:
        if isinstance(c, NavigableString):
            parts.append(str(c))
        elif isinstance(c, Tag) and c.name != "img":
            parts.append(c.get_text())
    return "".join(parts).strip()


def _get_metadata(soup: BeautifulSoup, article: Tag, base_url: str) -> dict:
    head = soup.find("head")
    # document_date
    doc_date_tag = (head and head.find("meta", attrs={"property": "article:published_time"})) or (head and head.find("meta", attrs={"name": "datePublished"}))
    document_date = (doc_date_tag.get("content") or "").strip() or None

    # authors: meta author + editor from .article-author-info
    authors = []
    author_tag = (head and head.find("meta", attrs={"property": "article:author"})) or (head and head.find("meta", attrs={"name": "articleAuthor"}))
    author_name = (author_tag.get("content") or "").strip() if author_tag else None
    if author_name:
        authors.append({"name": author_name, "url": None})
    editor_block = article.find("div", class_=lambda c: c and "article-author-info" in (c if isinstance(c, str) else " ".join(c))) if article else None
    if editor_block:
        editor_link = editor_block.find("a")
        if editor_link:
            editor_name = editor_link.get_text(strip=True)
            editor_url = urljoin(base_url, editor_link.get("href")) if editor_link.get("href") else None
        else:
            editor_name = re.sub(r"Editör\s*:\s*", "", editor_block.get_text(strip=True))
            editor_url = None
        if editor_name:
            authors.append({"name": editor_name, "url": editor_url})

    # title: og:title, then h1 in article, then <title>
    title = None
    og_title = head and head.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = (og_title.get("content") or "").strip()
    if not title and article:
        h1 = article.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
    if not title and head:
        title_tag = head.find("title")
        if title_tag and title_tag.get_text(strip=True):
            title = title_tag.get_text(strip=True)

    # categories: .article-category-tag a
    categories = None
    cat_div = article.find("div", class_=lambda c: c and "article-category-tag" in (c if isinstance(c, str) else " ".join(c))) if article else None
    if cat_div:
        links = cat_div.find_all("a")
        if links:
            categories = []
            for a in links:
                name = (a.get_text(strip=True) or "").strip() or None
                href = a.get("href")
                url = urljoin(base_url, href) if href else None
                categories.append({"name": name, "url": url})

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors if authors else None,
        "categories": categories,
        "tags": None,
    }


def _lead_media_components(article: Tag) -> list:
    """Video or image from first .article-main-image (before article-content)."""
    out = []
    first_media = article.find("div", class_=lambda c: c and "article-main-image" in (c if isinstance(c, str) else " ".join(c))) if article else None
    if not first_media:
        return out
    video = first_media.find("video")
    if video:
        source = video.find("source", src=True)
        src = source["src"] if source else None
        if src:
            props = {"url": src}
            poster = (video.get("poster") or "").strip()
            if poster:
                props["thumbnail_image_url"] = poster
            out.append({"type": "video", "properties": props})
        return out
    img = first_media.find("img", src=True)
    if img:
        url = img.get("src", "").strip()
        if url:
            figcap = first_media.find("figcaption")
            caption = _figcaption_text(figcap) if figcap else None
            props = {"url": url}
            alt = (img.get("alt") or "").strip()
            if alt:
                props["description"] = alt
            if caption:
                props["caption"] = caption
            out.append({"type": "image", "properties": props})
    return out


def _block_components_from_article_content(article_content: Tag) -> list:
    """Parse div.article-content and yield components in order. Skip article-author-info."""
    components = []
    if not article_content:
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

    def add_image_from_tag(container):
        img = container.find("img", src=True)
        if not img:
            return
        url = img.get("src", "").strip()
        if not url:
            return
        figcap = container.find("figcaption")
        caption = _figcaption_text(figcap) if figcap else None
        props = {"url": url}
        alt = (img.get("alt") or "").strip()
        if alt:
            props["description"] = alt
        if caption:
            props["caption"] = caption
        components.append({"type": "image", "properties": props})

    def add_list(tag):
        is_ol = tag.name == "ol"
        items = []
        for i, li in enumerate(tag.find_all("li", recursive=False)):
            content = _inline_to_markdown(li).strip()
            bullet = f"{i + 1}." if is_ol else "-"
            items.append({"indent": 0, "bullet": bullet, "content": content})
        if not items:
            return
        components.append({"type": "list", "properties": {"items": items}})

    def add_table(tag):
        headers = []
        rows = []
        thead = tag.find("thead")
        if thead:
            tr = thead.find("tr")
            if tr:
                headers = [th.get_text(strip=True) for th in tr.find_all(["th", "td"])]
        tbody = tag.find("tbody") or tag
        for tr in tbody.find_all("tr"):
            if not headers and not rows:
                cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                if cells:
                    headers = cells
                    continue
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if not headers:
            return
        components.append({"type": "table", "properties": {"headers": headers, "rows": rows}})

    def add_code_block(tag):
        code = tag.get_text()
        if code is None:
            return
        components.append({"type": "code_block", "properties": {"code": code, "language": None}})

    for child in article_content.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "div" and _has_class(child, "article-author-info"):
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
        if child.name == "div" and _has_class(child, "article-main-image", "article-margin"):
            add_image_from_tag(child)
            continue
        # Nested figure inside div (e.g. figure.image > div.article-main-image > figure.article-image)
        if child.name == "div":
            fig = child.find("figure")
            if fig:
                add_image_from_tag(fig)
            else:
                add_image_from_tag(child)

    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    """
    Parse HTML from fetch_html.py for turkiyegazetesi.com and return a dict
    that strictly conforms to scraped_article_json_schema.json (MarkdownDocument).
    """
    soup = BeautifulSoup(html_raw, "html.parser")
    article_scope = soup.find("div", class_=lambda c: c and "article-scope" in (c if isinstance(c, str) else " ".join(c)))
    article = article_scope.find("article") if article_scope else None

    metadata = _get_metadata(soup, article, base_url) if article else {"title": None, "document_date": None, "authors": None, "categories": None, "tags": None}

    components_list = []
    if article:
        components_list.extend(_lead_media_components(article))
        article_content = (
            article.find("div", itemprop="articleBody") or
            article.find("div", class_=lambda c: c and "article-content" in (c if isinstance(c, str) else " ".join(c)))
        )
        components_list.extend(_block_components_from_article_content(article_content))

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
