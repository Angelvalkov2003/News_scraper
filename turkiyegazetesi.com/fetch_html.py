"""
Сваля HTML на статии от turkiyegazetesi.com.tr и записва в HTML_files/ само съдържанието на новината:
само колоната с статията (article-scope), без навбар, без дясна страница (ÇOK OKUNANLAR, YAZARLAR и т.н.),
и спираме преди YORUMLAR (Yorumunuzu yazın / Gönder / Yorum için giriş yapın).
Пусни от папката turkiyegazetesi.com: python fetch_html.py <URL> [URL ...]
"""

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

# Meta тагове за metadata (парсър / AI)
_META_NAMES = ("datePublished", "dateModified", "dateCreated", "articleAuthor", "articleSection")
_META_PROPERTIES = ("article:published_time", "article:modified_time", "article:author", "article:section")


def url_to_slug(url: str) -> str:
    """Последният сегмент от пътя: .../gundem/slug-1770154 -> slug-1770154"""
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


def _build_minimal_head(soup: BeautifulSoup) -> str:
    """Само meta за дата, автор, категория – без скриптове/стилове."""
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
    Взема само колоната с статията (div.article-scope), без sidebar.
    Вътре премахва целия блок с коментари (YORUMLAR / Yorumunuzu yazın / Gönder / Yorum için giriş yapın).
    Head: само нужните meta тагове.
    """
    soup = BeautifulSoup(html, "html.parser")
    head_str = _build_minimal_head(soup)

    article_scope = soup.find("div", class_=lambda c: c and "article-scope" in (c if isinstance(c, str) else " ".join(c)))
    if not article_scope:
        return html

    # Премахваме div.comments (блокът YORUMLAR) и всичко след него
    comments_div = article_scope.find("div", class_=lambda c: c and "comments" in (c if isinstance(c, str) else " ".join(c)))
    if comments_div:
        comments_div.decompose()

    return '<!DOCTYPE html><html>' + head_str + '<body><div class="article-scope">' + str(article_scope.decode_contents()) + '</div></body></html>'


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
