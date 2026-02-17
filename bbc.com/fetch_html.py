"""Сваля HTML на статии и записва в HTML_files/. TODO: адаптирай за bbc.com."""

import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
HTML_FILES = SITE_DIR / "HTML_files"


def url_to_slug(url: str) -> str:
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


def main():
    if len(sys.argv) < 2:
        print("Употреба: python fetch_html.py <URL> [URL ...]", file=sys.stderr)
        sys.exit(1)
    HTML_FILES.mkdir(parents=True, exist_ok=True)
    import requests
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    for url in sys.argv[1:]:
        url = url.strip()
        if not url:
            continue
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            slug = url_to_slug(url)
            (HTML_FILES / f"{slug}.html").write_bytes(r.content)
            print(f"Записано: {HTML_FILES / (slug + '.html')}")
        except Exception as e:
            print(f"Грешка {url}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
