"""
Parse HTML from HTML_files/ (Think with Google: main#page-content.simple-article, trimmed before return-to-top)
into scraped_article_json_schema format, write to Parsed_files/.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_parser import BaseParser
from base._utils import ensure_utf8_stdout

BASE_URL = "https://business.google.com"


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


def _month_to_iso(s: str) -> str | None:
    """e.g. 'February 2026' -> 2026-02-01T00:00:00+00:00"""
    if not s or not s.strip():
        return None
    s = s.strip()
    months = "January February March April May June July August September October November December".split()
    for i, m in enumerate(months, 1):
        if m in s:
            m = re.search(r"(\d{4})", s)
            year = m.group(1) if m else "2026"
            return f"{year}-{i:02d}-01T00:00:00+00:00"
    return None


def _get_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    main = soup.find("main", id="page-content", class_=lambda c: c and "simple-article" in (c if isinstance(c, str) else " ".join(c)))
    title = None
    document_date = None
    authors = None

    hero = soup.find("section", class_=lambda c: c and "simple-article-hero" in (c if isinstance(c, str) else " ".join(c)))
    if hero:
        h1 = hero.find("h1", class_=lambda c: c and "simple-article-hero__headline" in (c if isinstance(c, str) else " ".join(c)))
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
        info = hero.find("div", class_=lambda c: c and "simple-article-hero__article-info" in (c if isinstance(c, str) else " ".join(c)))
        if info and info.get_text(strip=True):
            document_date = _month_to_iso(info.get_text(strip=True))
        attr = hero.find("div", class_=lambda c: c and "simple-article-hero__article-attribution" in (c if isinstance(c, str) else " ".join(c)))
        if attr:
            author_span = attr.find("span", class_=lambda c: c and "author-list-item" in (c if isinstance(c, str) else " ".join(c)))
            if author_span and author_span.get_text(strip=True):
                authors = [{"name": author_span.get_text(strip=True), "url": None}]

    return {
        "title": title or None,
        "document_date": document_date,
        "authors": authors,
        "categories": None,
        "tags": None,
    }


def _components_from_body(body: Tag, base_url: str) -> list:
    components = []
    if not body:
        return components
    for child in body.children:
        if not isinstance(child, Tag):
            continue
        # Skip only element that has exact class "ion-article-spotlight" (not ArticlePage__ion-spotlight)
        c = child.get("class") or []
        if isinstance(c, str):
            c = [c]
        if "ion-article-spotlight" in c:
            continue
        cls = " ".join(c)
        if child.name == "p":
            text = _inline_to_markdown(child).strip()
            if text:
                components.append({"type": "paragraph", "properties": {"text": text}})
        elif child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = child.get_text(strip=True)
            if text:
                level = int(child.name[1])
                components.append({"type": "heading", "properties": {"text": text, "level": level}})
        elif child.name == "div":
            # Image block: .ion-article-data-chart or picture/img
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
                    cap = child.find("p", class_=lambda c: c and "glue-caption" in (c if isinstance(c, str) else " ".join(c)))
                    if cap and cap.get_text(strip=True):
                        props["caption"] = cap.get_text(strip=True)
                    components.append({"type": "image", "properties": props})
                continue
            # Video block: .glue-ambient-video or video source
            video = child.find("video")
            if video:
                src = video.find("source", src=True)
                url = (src.get("src") or "").strip() if src else ""
                if url and not url.startswith("data:"):
                    url = urljoin(base_url, url)
                if url:
                    props = {"url": url}
                    cap = child.find("p", class_=lambda c: c and "glue-caption" in (c if isinstance(c, str) else " ".join(c)))
                    if cap and cap.get_text(strip=True):
                        props["caption"] = cap.get_text(strip=True)
                    components.append({"type": "video", "properties": props})
                continue
            # Nested icon-callout / ion-article-data-chart
            inner = child.find("div", class_=lambda c: c and "ion-article-data-chart" in (c if isinstance(c, str) else " ".join(c)))
            if inner:
                img = inner.find("img", src=True)
                if not img:
                    pic = inner.find("picture")
                    if pic:
                        img = pic.find("img", src=True)
                if img:
                    url = (img.get("src") or "").strip()
                    if url and not url.startswith("data:"):
                        url = urljoin(base_url, url)
                    if url:
                        props = {"url": url}
                        alt = (img.get("alt") or "").strip()
                        if alt:
                            props["description"] = alt
                        footer = inner.find("div", class_=lambda c: c and "ion-article-data-chart__footer" in (c if isinstance(c, str) else " ".join(c)))
                        if footer:
                            cap = footer.find("p", class_=lambda c: c and "glue-caption" in (c if isinstance(c, str) else " ".join(c)))
                            if cap and cap.get_text(strip=True):
                                props["caption"] = cap.get_text(strip=True)
                        components.append({"type": "image", "properties": props})
            else:
                # ion-video__video-enhancement (when no ion-article-data-chart in this div)
                vid_div = child.find("div", class_=lambda c: c and "ion-video" in (c if isinstance(c, str) else " ".join(c)))
                if vid_div:
                    video = vid_div.find("video")
                    if video:
                        src = video.find("source", src=True)
                        url = (src.get("src") or "").strip() if src else ""
                        if url:
                            url = urljoin(base_url, url) if not url.startswith("http") else url
                            props = {"url": url}
                            cap = child.find("p", class_=lambda c: c and "glue-caption" in (c if isinstance(c, str) else " ".join(c)))
                            if cap and cap.get_text(strip=True):
                                props["caption"] = cap.get_text(strip=True)
                            components.append({"type": "video", "properties": props})
    return components


def parse_article_html(html_raw: bytes, base_url: str = BASE_URL) -> dict:
    soup = BeautifulSoup(html_raw, "html.parser")
    metadata = _get_metadata(soup, base_url)

    components_list = []
    if metadata.get("title"):
        components_list.append({"type": "heading", "properties": {"text": metadata["title"], "level": 1}})

    content = soup.find("div", class_=lambda c: c and "simple-article__content" in (c if isinstance(c, str) else " ".join(c)))
    body = content.find("section", class_=lambda c: c and "simple-article__body" in (c if isinstance(c, str) else " ".join(c))) if content else None
    if body:
        components_list.extend(_components_from_body(body, base_url))

    return {
        "metadata": metadata,
        "components": {"components": components_list},
    }


class BusinessGoogleParser(BaseParser):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent, base_url=BASE_URL)

    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        return parse_article_html(html_raw, base_url=base_url or self.base_url)

    def main(self) -> None:
        """Resolve input paths: if file not found, try HTML_files/<name>."""
        import sys as _sys
        ensure_utf8_stdout()
        self.parsed_files.mkdir(parents=True, exist_ok=True)
        if len(_sys.argv) > 1:
            paths = []
            for p in _sys.argv[1:]:
                path = Path(p).resolve()
                if not path.exists() and (self.html_files / Path(p).name).exists():
                    path = self.html_files / Path(p).name
                paths.append(path)
        else:
            paths = list(self.html_files.glob("*.html")) if self.html_files.exists() else []
        if not paths:
            print("No HTML files. Add paths or run fetch_html.py first.", file=_sys.stderr)
            _sys.exit(1)
        for path in paths:
            if not path.exists():
                print(f"Skipping (file missing): {path}", file=_sys.stderr)
                continue
            raw = path.read_bytes()
            try:
                doc = self.parse_article_html(raw, base_url=self.base_url)
            except Exception as e:
                print(f"Error parsing {path}: {e}", file=_sys.stderr)
                continue
            out = self.parsed_files / f"{path.stem}.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            print(f"  {out.name}")
        print(f"Written to {self.parsed_files}")


if __name__ == "__main__":
    BusinessGoogleParser().main()
