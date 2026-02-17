"""
Сваля HTML на статии от birgun.net и записва в HTML_files/ само съдържанието на новината:
от div.contentdetail (заглавие H1 и тяло) до преди първия „Sıradaki Haber“. Без навбар, меню, реклами.
Пусни от папката birgun.net: python fetch_html.py <URL> [URL ...]
"""

import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SITE_DIR = Path(__file__).resolve().parent
HTML_FILES = SITE_DIR / "HTML_files"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def url_to_slug(url: str) -> str:
    """От URL връща slug за име на файл (напр. .../makale/slug-123 -> slug-123)."""
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


# Meta тагове, които парсърът използва за metadata (document_date, authors, categories, tags)
_META_NAMES = ("datePublished", "articleAuthor", "articleSection", "keywords", "ptime")
_META_PROPERTIES = ("datePublished",)  # property="datePublished" и т.н.


def _build_minimal_head(soup: BeautifulSoup) -> str:
    """Само meta тагове за document_date, authors, categories, tags – без скриптове/стилове."""
    parts = ['<head><meta charset="utf-8">']
    head = soup.find("head")
    if not head:
        return '<head><meta charset="utf-8"></head>'
    for meta in head.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").strip()
        if name in _META_NAMES or name in _META_PROPERTIES:
            parts.append(str(meta))
    parts.append("</head>")
    return "".join(parts)


def extract_article_only(html: str) -> str:
    """
    Оставя само съдържанието на статията: div.contentdetail (от H1 до преди „Sıradaki Haber“).
    В head записва само нужните meta тагове за metadata (дата, автор, категория, тагове) – без дълги скриптове.
    """
    soup = BeautifulSoup(html, "html.parser")
    head_str = _build_minimal_head(soup)
    contentdetail = soup.find("div", class_=lambda c: c and "contentdetail" in (c if isinstance(c, str) else " ".join(c)))
    if not contentdetail:
        return html
    stop_text = contentdetail.find(string=lambda t: t and "Sıradaki Haber" in t)
    if stop_text:
        node = stop_text.parent
        while node and node.parent != contentdetail:
            node = node.parent
        if node and node.parent == contentdetail:
            for s in list(node.next_siblings):
                s.decompose()
            node.decompose()
    return '<!DOCTYPE html><html>' + head_str + '<body>' + str(contentdetail) + '</body></html>'


def main():
    if len(sys.argv) < 2:
        print("Употреба: python fetch_html.py <URL> [URL ...]", file=sys.stderr)
        sys.exit(1)
    HTML_FILES.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = UA
    for url in sys.argv[1:]:
        url = url.strip()
        if not url:
            continue
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            html_clean = extract_article_only(r.text)
            slug = url_to_slug(url)
            path = HTML_FILES / f"{slug}.html"
            path.write_text(html_clean, encoding="utf-8")
            print(f"Записано: {path}")
        except requests.RequestException as e:
            print(f"Грешка {url}: {e}", file=sys.stderr)
        if len(sys.argv) > 2:
            time.sleep(1)


if __name__ == "__main__":
    main()
