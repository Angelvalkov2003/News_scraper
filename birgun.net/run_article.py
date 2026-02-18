"""
Една команда: подаваш URL → fetch HTML; с флагове пускаш парсър и/или AI JSON.

Употреба:
  py run_article.py <URL>              → само fetch HTML в HTML_files/
  py run_article.py <URL> --parse      → fetch HTML + парсване в Parsed_files/
  py run_article.py <URL> --ai        → fetch HTML + генериране на JSON чрез Anthropic в AI_files/
  py run_article.py <URL> --parse --ai → fetch + парсване + AI JSON
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
    """От URL връща slug за име на файл (напр. .../makale/slug-691575 -> slug-691575)."""
    path = url.strip().rstrip("/").split("/")[-1] or "page"
    return path if not path.endswith(".html") else path[:-5]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch статия по URL (birgun.net); с --parse парсване до JSON, с --ai генериране на JSON чрез Anthropic API."
    )
    parser.add_argument("url", help="Пълен URL на статия (напр. https://www.birgun.net/makale/...)")
    parser.add_argument("--parse", "-p", action="store_true", help="След fetch: парсване до JSON (Parsed_files/)")
    parser.add_argument("--ai", "-a", action="store_true", help="След fetch: генериране на JSON чрез Anthropic API (AI_files/)")
    args = parser.parse_args()

    url = args.url.strip()
    if not url.startswith("http"):
        print("Дай пълен URL (с https://...)", file=sys.stderr)
        sys.exit(1)

    # 1. Fetch HTML
    print("Fetching HTML...")
    ret = subprocess.run(
        [sys.executable, str(SITE_DIR / "fetch_html.py"), url],
        cwd=str(SITE_DIR),
        capture_output=False,
    )
    if ret.returncode != 0:
        print("Грешка при fetch на HTML.", file=sys.stderr)
        sys.exit(ret.returncode)

    slug = url_to_slug(url)
    html_path = HTML_FILES / f"{slug}.html"
    if not html_path.exists():
        print(f"Очакван файл липсва: {html_path}", file=sys.stderr)
        sys.exit(1)
    print(f"Записано: {html_path}\n")

    # 2. Parse (ако е поискано)
    if args.parse:
        print("Парсване до JSON (Parsed_files/)...")
        ret = subprocess.run(
            [sys.executable, str(SITE_DIR / "parser.py"), str(html_path)],
            cwd=str(SITE_DIR),
            capture_output=False,
        )
        if ret.returncode != 0:
            print("Грешка при парсване.", file=sys.stderr)
            sys.exit(ret.returncode)
        print()

    # 3. AI extract (ако е поискано)
    if args.ai:
        print("Генериране на JSON чрез Anthropic API (AI_files/)...")
        ret = subprocess.run(
            [sys.executable, str(SITE_DIR / "ai_extract.py"), str(html_path)],
            cwd=str(SITE_DIR),
            capture_output=False,
        )
        if ret.returncode != 0:
            print("Грешка при AI извличане.", file=sys.stderr)
            sys.exit(ret.returncode)
        print()

    print("Done.")


if __name__ == "__main__":
    main()
