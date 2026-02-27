"""
Parse HTML from HTML_files/ (Goal.com article, main > article) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://www.goal.com"


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
    if not s or not s.strip():
        return None
    s = s.strip()
    if "T" in s and re.match(r"\d{4}-\d{2}-\d{2}", s):
        return re.sub(r"\.\d+Z$", "+00:00", s) if s.endswith("Z") else s
    return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    h1 = soup.find("h1", attrs={"data-testid": "article-title"}) or soup.find(
        "h1", class_=lambda c: c and "article_title" in (c if isinstance(c, str) else " ".join(c))
    )
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)

    document_date = None
    time_el = soup.find("time", datetime=True)
    if time_el and time_el.get("datetime"):
        document_date = _normalize_datetime_to_iso(time_el["datetime"])

    authors = None
    author_el = soup.find("span", attrs={"data-testid": "author-link"}) or soup.find(
        "span", class_=lambda c: c and "author" in (c if isinstance(c, str) else " ".join(c))
    )
    if author_el:
        # Name is the visible text; for Goal.com often the <span> wraps an <a>
        name = author_el.get_text(strip=True)
        if name:
            # Prefer an <a> inside the span (common structure), then fall back to ancestor <a>
            author_link = author_el.find("a", href=True) or author_el.find_parent("a", href=True)
            author_url = urljoin(base_url, author_link["href"]) if author_link and author_link.get("href") else None
            authors = [{"name": name, "url": author_url}]

    categories = None  # Goal.com uses tags; categories can be derived from URL path if needed

    tags = None
    # Tags: <div class="fco-scrollable-tag-list"> > <div class="fco-tag-button-container"> > <a class="fco-tag-button--link"> with <span class="fco-tag-button-text">
    scrollable = soup.find("div", class_=lambda c: c and "fco-scrollable-tag-list" in (c if isinstance(c, str) else " ".join(c)))
    if scrollable:
        tag_links = scrollable.find_all("a", href=True, class_=lambda c: c and "fco-tag-button" in (c if isinstance(c, str) else " ".join(c)))
    else:
        tag_list = soup.find("div", class_=lambda c: c and "tag-list" in (c if isinstance(c, str) else " ".join(c)))
        tag_links = tag_list.find_all("a", href=True, class_=lambda c: c and "fco-tag-button" in (c if isinstance(c, str) else " ".join(c))) if tag_list else []
    if tag_links:
        tags = []
        for a in tag_links:
            span = a.find("span", class_=lambda c: c and "fco-tag-button-text" in (c if isinstance(c, str) else " ".join(c)))
            name = (span.get_text(strip=True) if span else a.get_text(strip=True) or "").strip()
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


def _components_from_body(container: Tag, base_url: str) -> list:
    """Extract paragraphs, headings, images from article body. Skip video/match recirculation/ad blocks."""
    components = []
    if not container:
        return components
    # Body often has one wrapper div with all content; use its children
    direct_tags = [c for c in container.children if isinstance(c, Tag)]
    if len(direct_tags) == 1 and direct_tags[0].name == "div":
        content = direct_tags[0]
    else:
        content = container
    for child in content.children:
        if not isinstance(child, Tag):
            continue
        # Skip known non-content
        if child.get("class"):
            cls = " ".join(child.get("class", []))
            if "fco-fc-video-player" in cls or "fco-match-recirculation" in cls or "open-web-ad" in cls or "ad-slot" in cls:
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
        elif child.name == "span" and "fco-fc-video-player" in (child.get("class") or []):
            continue
        elif child.find("img", src=True):
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
                    components.append({"type": "image", "properties": props})
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []
    article_el = soup.find("article") or soup

    # Lead image from poster
    poster = article_el.find("div", class_=lambda c: c and "article_poster" in (c if isinstance(c, str) else " ".join(c)))
    if poster:
        img = poster.find("img", src=True)
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

    # Teaser
    teaser = article_el.find("p", attrs={"data-testid": "article-teaser"}) or article_el.find(
        "p", class_=lambda c: c and "article_teaser" in (c if isinstance(c, str) else " ".join(c))
    )
    if teaser:
        text = _inline_to_markdown(teaser).strip()
        if text:
            components_list.append({"type": "paragraph", "properties": {"text": text}})

    # Body: first main body under header/teaser (can be empty for gallery-style pages)
    body = article_el.find("div", attrs={"data-testid": "article-body"}) or article_el.find(
        "div", class_=lambda c: c and "article-body_body" in (c if isinstance(c, str) else " ".join(c))
    )
    if body:
        components_list.extend(_components_from_body(body, base_url))

    # Gallery/list slides: ul.list_slides__... contains multiple slides with h2 + body (and sometimes images)
    slides_ul = article_el.find(
        "ul",
        class_=lambda c: c and "list_slides" in (c if isinstance(c, str) else " ".join(c)),
    )
    if slides_ul:
        for li in slides_ul.find_all(
            "li",
            class_=lambda c: c and "standard-slide" in (c if isinstance(c, str) else " ".join(c)),
        ):
            # Optional image inside slide (separate from main poster)
            media = li.find(
                "div",
                class_=lambda c: c and "media_poster" in (c if isinstance(c, str) else " ".join(c)),
            )
            if media:
                img = media.find("img", src=True)
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

            # Slide heading
            h2 = li.find(
                "h2",
                class_=lambda c: c and "headline_headline" in (c if isinstance(c, str) else " ".join(c)),
            )
            if h2 and h2.get_text(strip=True):
                components_list.append(
                    {
                        "type": "heading",
                        "properties": {"text": h2.get_text(strip=True), "level": 2},
                    }
                )

            # Slide body content
            slide_body = li.find(
                "div",
                class_=lambda c: c and "article-body_body" in (c if isinstance(c, str) else " ".join(c)),
            )
            if slide_body:
                components_list.extend(_components_from_body(slide_body, base_url))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class GoalParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    GoalParser().main()
