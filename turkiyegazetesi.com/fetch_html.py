"""
Сваля HTML на статии от turkiyegazetesi.com.tr и записва в HTML_files/ само съдържанието на новината:
само <div class="article-scope"> с един <article> вътре, без навбар, sidebar, препоръки, споделяне, коментари.
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

# Класове на блокове за премахване от article
_REMOVE_BLOCK_CLASSES = frozenset({
    "article-recommended", "article-related", "article-follow-us",
    "article-social-publish", "article-sp-share", "comments",
})
# Допълнителни елементи за премахване (бутони за споделяне, запазване, размер на шрифт)
_REMOVE_SELECTORS = ("article-actions", "listenSummarySave")


def url_to_slug(url: str) -> str:
    """Последният сегмент от пътя: .../gundem/slug-1770154 -> slug-1770154"""
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


def _build_minimal_head(soup: BeautifulSoup) -> str:
    """Само meta за дата, автор, категория – без скриптове/стилове/линкове."""
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


def _remove_comments_and_after(article: BeautifulSoup) -> None:
    """Премахва блока comments и всички следващи siblings в article."""
    comments = article.find("div", class_=lambda c: c and "comments" in (c if isinstance(c, str) else " ".join(c)))
    if not comments:
        return
    for s in list(comments.find_next_siblings()):
        s.decompose()
    comments.decompose()


def _remove_blocks_by_class(article: BeautifulSoup) -> None:
    """Премахва всички елементи с дадените блокови класове."""
    to_remove = []
    for tag in article.find_all(True):
        if not tag.get("class"):
            continue
        cls_str = " ".join(tag["class"]) if isinstance(tag["class"], list) else tag["class"]
        if any(block in cls_str for block in _REMOVE_BLOCK_CLASSES):
            to_remove.append(tag)
    for tag in to_remove:
        tag.decompose()


def _remove_actions_and_save(article: BeautifulSoup) -> None:
    """Премахва article-actions и listenSummarySave (споделяне, Kaydet, a-|+A)."""
    for sel in _REMOVE_SELECTORS:
        for tag in article.find_all(class_=lambda c: c and sel in (c if isinstance(c, str) else " ".join(c))):
            tag.decompose()


def _clean_media_containers(article: BeautifulSoup) -> None:
    """В контейнери с медия премахва скриптове, adContainer, playButton; запазва video/source."""
    for tag in article.find_all("script"):
        tag.decompose()
    for tag in article.find_all("div", id=lambda x: x and str(x).startswith("playButton-")):
        tag.decompose()
    for tag in article.find_all("div", class_=lambda c: c and "adContainer" in (c if isinstance(c, str) else " ".join(c))):
        tag.decompose()


def _extract_article_clean(article_scope: BeautifulSoup):
    """Връща очистен <article> (Tag) с премахнати бокове и UI."""
    article = article_scope.find("article")
    if not article:
        return None
    article_soup = BeautifulSoup(str(article), "html.parser")
    article = article_soup.find("article")
    if not article:
        return None
    _remove_comments_and_after(article)
    _remove_blocks_by_class(article)
    _remove_actions_and_save(article)
    _clean_media_containers(article)
    return article


def extract_article_only(html: str) -> str:
    """
    Взема само div.article-scope и вътре само <article> с нужното съдържание.
    Премахва навбар, sidebar, препоръки, споделяне, коментари, бутони, скриптове в медия.
    Head: само изброените meta тагове.
    Ако няма article-scope, връща оригиналния HTML непроменен.
    """
    soup = BeautifulSoup(html, "html.parser")
    article_scope = soup.find("div", class_=lambda c: c and "article-scope" in (c if isinstance(c, str) else " ".join(c)))
    if not article_scope:
        return html

    head_str = _build_minimal_head(soup)
    article_clean = _extract_article_clean(article_scope)
    if not article_clean:
        article_clean = article_scope.find("article")
    if not article_clean:
        return html

    article_html = article_clean.decode_contents() if hasattr(article_clean, "decode_contents") else str(article_clean)
    return (
        "<!DOCTYPE html><html>"
        + head_str
        + "<body><div class=\"article-scope\"><article>"
        + article_html
        + "</article></div></body></html>"
    )


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
