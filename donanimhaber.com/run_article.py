"""
Single command: pass URL → fetch HTML; with flags run parser and/or AI JSON.

Usage:
  py run_article.py <URL>              → only fetch HTML to HTML_files/
  py run_article.py <URL> --parse     → fetch HTML + parse to Parsed_files/
  py run_article.py <URL> --ai        → fetch HTML + generate JSON via API (AI_files/)
  py run_article.py <URL> --parse --ai → fetch + parse + AI
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_runner import BaseRunner


class DonanimhaberRunner(BaseRunner):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def url_to_slug(self, url: str) -> str:
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0].split("/")
        return path[-1] if path else "page"

    def get_description(self) -> str:
        return "Fetch DonanımHaber article by URL; with --parse run parser to JSON, with --ai generate JSON via API."

    def get_url_help(self) -> str:
        return "Full article URL (e.g. https://www.donanimhaber.com/slug--201932)"


if __name__ == "__main__":
    DonanimhaberRunner().main()
