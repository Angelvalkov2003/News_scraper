"""
Parse HTML from HTML_files/ (DonanımHaber article: main.icerik.detail) into scraped_article_json_schema format, write to Parsed_files/.
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

BASE_URL = "https://www.donanimhaber.com"


def _video_component(url: str, *, name: str | None = None, caption: str | None = None, description: str | None = None, thumbnail_image_url: str | None = None) -> dict:
    """Build video component per scraped_article_json_schema (url required; optional name, caption, description, thumbnail_image_url)."""
    props = {"url": url}
    if name:
        props["name"] = name
    if caption:
        props["caption"] = caption
    if description:
        props["description"] = description
    if thumbnail_image_url:
        props["thumbnail_image_url"] = thumbnail_image_url
    return {"type": "video", "properties": props}


def _video_url_from_element(elt: Tag, base_url: str) -> tuple[str | None, str | None]:
    """Extract video URL from iframe or similar. Returns (url, thumbnail_url or None)."""
    if elt.name == "iframe":
        src = (elt.get("src") or "").strip()
        if not src:
            return None, None
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = urljoin(base_url, src)
        if "yukle.donanimhaber.com/Embed" in src or "youtube.com/embed" in src or "vimeo.com" in src or "player." in src:
            thumb = None
            if "youtube.com/embed/" in src:
                m = re.search(r"embed/([a-zA-Z0-9_-]{11})", src)
                if m:
                    thumb = f"https://i.ytimg.com/vi_webp/{m.group(1)}/maxresdefault.webp"
            return src, thumb
    return None, None


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
    main = soup.find("main", class_=lambda c: c and "icerik" in (c if isinstance(c, str) else " ".join(c)) and "detail" in (c if isinstance(c, str) else " ".join(c)))
    title = None
    if main and main.get("data-title"):
        title = (main["data-title"] or "").strip()
    if not title:
        h1 = soup.find("h1", class_=lambda c: c and "post-baslik" in (c if isinstance(c, str) else " ".join(c)))
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)

    document_date = None
    time_el = soup.find("time", datetime=True)
    if time_el and time_el.get("datetime"):
        document_date = _normalize_datetime_to_iso(time_el["datetime"])

    authors = None
    for author_link in soup.find_all("a", rel="author", href=True):
        name = author_link.get_text(strip=True)
        if name:
            authors = [{"name": name, "url": urljoin(base_url, author_link["href"])}]
            break

    categories = None
    temel = soup.find("aside", class_=lambda c: c and "temel-bilgi" in (c if isinstance(c, str) else " ".join(c)))
    if temel:
        kat = temel.find("div", class_=lambda c: c and "kategori" in (c if isinstance(c, str) else " ".join(c)))
        if kat:
            a = kat.find("a", href=True, class_=lambda c: c and "veri" in (c if isinstance(c, str) else " ".join(c)))
            if not a:
                a = kat.find("a", href=True)
            if a:
                name = a.get_text(strip=True)
                if name:
                    categories = [{"name": name, "url": urljoin(base_url, a["href"])}]

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors,
        "categories": categories,
        "tags": None,
    }


def _components_from_yazi(section: Tag, base_url: str) -> list:
    components = []
    if not section:
        return components
    for child in section.children:
        if not isinstance(child, Tag):
            continue
        cls = " ".join(child.get("class", []))
        if "lnk-bkz" in cls or "lnk-kaynak" in cls:
            continue
        if child.name == "aside" and child.find(class_=lambda c: c and "lnk-bkz" in (c if isinstance(c, str) else " ".join(c))):
            continue
        if child.name == "figure" and "resim" in cls:
            img = child.find("img", src=True)
            if not img:
                a = child.find("a", href=True)
                if a:
                    img = a.find("img", src=True)
            if not img:
                pic = child.find("picture")
                if pic:
                    img = pic.find("img", src=True)
            figcap = child.find("figcaption")
            if img:
                url = (img.get("src") or "").strip()
                if url and not url.startswith("data:"):
                    url = urljoin(base_url, url)
                if url:
                    props = {"url": url}
                    if figcap and figcap.get_text(strip=True):
                        props["description"] = _inline_to_markdown(figcap).strip()
                    elif img.get("alt"):
                        props["description"] = (img.get("alt") or "").strip()
                    components.append({"type": "image", "properties": props})
            if figcap and figcap.get_text(strip=True):
                text = _inline_to_markdown(figcap).strip()
                if text:
                    components.append({"type": "paragraph", "properties": {"text": text}})
        elif child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = child.get_text(strip=True)
            if text:
                level = int(child.name[1])
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
        elif child.name == "p":
            if child.find(class_=lambda c: c and "lnk-bkz" in (c if isinstance(c, str) else " ".join(c))):
                continue
            iframe = child.find("iframe", src=True)
            if iframe:
                video_url, thumb = _video_url_from_element(iframe, base_url)
                if video_url:
                    components.append(_video_component(video_url, thumbnail_image_url=thumb))
                    text = "".join(_inline_to_markdown(c) for c in child.children if c is not iframe and (c.name != "br" or None)).strip()
                    if text:
                        components.append({"type": "paragraph", "properties": {"text": text}})
                    continue
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "paragraph", "properties": {"text": text}})
        elif child.name == "iframe":
            video_url, thumb = _video_url_from_element(child, base_url)
            if video_url:
                components.append(_video_component(video_url, thumbnail_image_url=thumb))
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)
    components_list = []

    if metadata.get("title"):
        components_list.append({"type": "heading", "properties": {"text": metadata["title"], "level": 1}})

    # Summary (h2.surmanset) after title
    surmanset = soup.find("h2", class_=lambda c: c and "surmanset" in (c if isinstance(c, str) else " ".join(c)))
    if surmanset and surmanset.get_text(strip=True):
        components_list.append({"type": "heading", "properties": {"text": surmanset.get_text(strip=True), "level": 2}})

    # Article body: section.kolon.yazi
    yazi = soup.find("section", class_=lambda c: c and "kolon" in (c if isinstance(c, str) else " ".join(c)) and "yazi" in (c if isinstance(c, str) else " ".join(c)))
    if yazi:
        components_list.extend(_components_from_yazi(yazi, base_url))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class DonanimhaberParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)


if __name__ == "__main__":
    DonanimhaberParser().main()
