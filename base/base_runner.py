"""
Base runner: one command URL -> fetch; with flags run parser and/or AI extract.
Subclasses override description/help strings only if desired.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from base._utils import ensure_utf8_stdout, url_to_slug


class BaseRunner:
    """Orchestrates fetch_html.py, parser.py, ai_extract.py via subprocess."""

    def __init__(self, site_dir: Path):
        self.site_dir = Path(site_dir)
        self.html_files = self.site_dir / "HTML_files"

    def url_to_slug(self, url: str) -> str:
        """Override if site uses different slug rule."""
        return url_to_slug(url)

    def main(self) -> None:
        """CLI: python run_article.py <URL> [--parse] [--ai]"""
        ensure_utf8_stdout()
        parser = argparse.ArgumentParser(
            description=self.get_description(),
        )
        parser.add_argument("url", help=self.get_url_help())
        parser.add_argument(
            "--parse", "-p",
            action="store_true",
            help="After fetch: parse HTML to JSON (Parsed_files/)",
        )
        parser.add_argument(
            "--ai", "-a",
            action="store_true",
            help="After fetch: generate JSON via Anthropic API (AI_files/)",
        )
        args = parser.parse_args()

        url = args.url.strip()
        if not url.startswith("http"):
            print("Provide a full URL (https://...)", file=sys.stderr)
            sys.exit(1)

        # 1. Fetch HTML
        print("Fetching HTML...")
        ret = subprocess.run(
            [sys.executable, str(self.site_dir / "fetch_html.py"), url],
            cwd=str(self.site_dir),
            capture_output=False,
        )
        if ret.returncode != 0:
            print("Error fetching HTML.", file=sys.stderr)
            sys.exit(ret.returncode)

        slug = self.url_to_slug(url)
        html_path = self.html_files / f"{slug}.html"
        if not html_path.exists():
            print(f"Expected file missing: {html_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Written: {html_path}\n")

        # 2. Parse (if requested)
        if args.parse:
            print("Parsing to JSON (Parsed_files/)...")
            ret = subprocess.run(
                [sys.executable, str(self.site_dir / "parser.py"), str(html_path)],
                cwd=str(self.site_dir),
                capture_output=False,
            )
            if ret.returncode != 0:
                print("Error parsing.", file=sys.stderr)
                sys.exit(ret.returncode)
            print()

        # 3. AI extract (if requested)
        if args.ai:
            print("Generating JSON via Anthropic API (AI_files/)...")
            ret = subprocess.run(
                [sys.executable, str(self.site_dir / "ai_extract.py"), str(html_path)],
                cwd=str(self.site_dir),
                capture_output=False,
            )
            if ret.returncode != 0:
                print("Error during AI extraction.", file=sys.stderr)
                sys.exit(ret.returncode)
            print()

        print("Done.")

    def get_description(self) -> str:
        """Override for site-specific description."""
        return "Fetch article by URL; with --parse run parser to JSON, with --ai generate JSON via Anthropic API."

    def get_url_help(self) -> str:
        """Override for site-specific URL help."""
        return "Full article URL (e.g. https://...)"
