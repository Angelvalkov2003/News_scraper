"""
Една команда: дадеш линк → сваля HTML; с флагове парсваш / генерираш JSON през AI.

Употреба:
  py run_article.py <URL>              → само сваля HTML в HTML_files/
  py run_article.py <URL> --parse      → сваля HTML + парсва в Parsed_files/
  py run_article.py <URL> --ai         → сваля HTML + генерира JSON през Anthropic в AI_files/
  py run_article.py <URL> --parse --ai → сваля HTML + парсва + AI JSON
"""

import argparse
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SITE_DIR = Path(__file__).resolve().parent
HTML_FILES = SITE_DIR / "HTML_files"


def url_to_slug(url: str) -> str:
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


def main():
    parser = argparse.ArgumentParser(
        description="Сваля HTML от статия по URL (doğrulukpayi.com); с --parse парсва в JSON, с --ai генерира JSON през Anthropic API."
    )
    parser.add_argument("url", help="Пълен URL на статията (напр. https://www.dogrulukpayi.com/dogrulama/...)")
    parser.add_argument("--parse", "-p", action="store_true", help="След fetch: парсвай HTML в JSON (Parsed_files/)")
    parser.add_argument("--ai", "-a", action="store_true", help="След fetch: генерирай JSON през Anthropic API (AI_files/)")
    args = parser.parse_args()

    url = args.url.strip()
    if not url.startswith("http"):
        print("Укажи пълен URL (https://...)", file=sys.stderr)
        sys.exit(1)

    print("Свалям HTML...")
    ret = subprocess.run(
        [sys.executable, str(SITE_DIR / "fetch_html.py"), url],
        cwd=str(SITE_DIR),
        capture_output=False,
    )
    if ret.returncode != 0:
        print("Грешка при сваляне на HTML.", file=sys.stderr)
        sys.exit(ret.returncode)

    slug = url_to_slug(url)
    html_path = HTML_FILES / f"{slug}.html"
    if not html_path.exists():
        print(f"Очакван файл липсва: {html_path}", file=sys.stderr)
        sys.exit(1)
    print(f"Записано: {html_path}\n")

    if args.parse:
        print("Парсвам в JSON (Parsed_files/)...")
        ret = subprocess.run(
            [sys.executable, str(SITE_DIR / "parser.py"), str(html_path)],
            cwd=str(SITE_DIR),
            capture_output=False,
        )
        if ret.returncode != 0:
            print("Грешка при парсване.", file=sys.stderr)
            sys.exit(ret.returncode)
        print()

    if args.ai:
        print("Генерирам JSON през Anthropic API (AI_files/)...")
        ret = subprocess.run(
            [sys.executable, str(SITE_DIR / "ai_extract.py"), str(html_path)],
            cwd=str(SITE_DIR),
            capture_output=False,
        )
        if ret.returncode != 0:
            print("Грешка при AI извличане.", file=sys.stderr)
            sys.exit(ret.returncode)
        print()

    print("Готово.")


if __name__ == "__main__":
    main()
