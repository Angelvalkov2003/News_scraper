"""
Single command: pass URL -> fetch HTML; with flags run parser and/or AI JSON.

Usage:
  py run_article.py <URL>              -> only fetch HTML to HTML_files/
  py run_article.py <URL> --parse      -> fetch HTML + parse to Parsed_files/
  py run_article.py <URL> --ai         -> fetch HTML + AI JSON to AI_files/
  py run_article.py <URL> --parse --ai -> fetch + parse + AI
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
        description="Fetch BBC article by URL; with --parse run parser to JSON, with --ai generate JSON via Anthropic API."
    )
    parser.add_argument("url", help="Full article URL (e.g. https://www.bbc.com/news/...)")
    parser.add_argument("--parse", "-p", action="store_true", help="After fetch: parse HTML to JSON (Parsed_files/)")
    parser.add_argument("--ai", "-a", action="store_true", help="After fetch: generate JSON via Anthropic API (AI_files/)")
    args = parser.parse_args()

    url = args.url.strip()
    if not url.startswith("http"):
        print("Provide a full URL (https://...)", file=sys.stderr)
        sys.exit(1)

    print("Fetching HTML...")
    ret = subprocess.run(
        [sys.executable, str(SITE_DIR / "fetch_html.py"), url],
        cwd=str(SITE_DIR),
        capture_output=False,
    )
    if ret.returncode != 0:
        print("Error fetching HTML.", file=sys.stderr)
        sys.exit(ret.returncode)

    slug = url_to_slug(url)
    html_path = HTML_FILES / f"{slug}.html"
    if not html_path.exists():
        print(f"Expected file missing: {html_path}", file=sys.stderr)
        sys.exit(1)
    print(f"Written: {html_path}\n")

    if args.parse:
        print("Parsing to JSON (Parsed_files/)...")
        ret = subprocess.run(
            [sys.executable, str(SITE_DIR / "parser.py"), str(html_path)],
            cwd=str(SITE_DIR),
            capture_output=False,
        )
        if ret.returncode != 0:
            print("Error parsing.", file=sys.stderr)
            sys.exit(ret.returncode)
        print()

    if args.ai:
        print("Generating JSON via Anthropic API (AI_files/)...")
        ret = subprocess.run(
            [sys.executable, str(SITE_DIR / "ai_extract.py"), str(html_path)],
            cwd=str(SITE_DIR),
            capture_output=False,
        )
        if ret.returncode != 0:
            print("Error during AI extraction.", file=sys.stderr)
            sys.exit(ret.returncode)
        print()

    print("Done.")


if __name__ == "__main__":
    main()
