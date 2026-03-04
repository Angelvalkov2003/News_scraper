"""
Single command: pass URL → fetch HTML (optionally parse/AI).

Usage:
  py run_article.py <URL>              → only fetch HTML to HTML_files/
  py run_article.py <URL> --parse     → fetch HTML + parse to Parsed_files/
  py run_article.py <URL> --ai        → fetch HTML + generate JSON via API (AI_files/)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_runner import BaseRunner


class BusinessGoogleRunner(BaseRunner):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def url_to_slug(self, url: str) -> str:
        u = url.strip().rstrip("/")
        if not u.startswith("http"):
            return "page"
        path = u.split("?", 1)[0]
        parts = [p for p in path.rstrip("/").split("/") if p]
        return parts[-1] if parts else "page"

    def get_description(self) -> str:
        return "Fetch Think with Google article by URL; with --parse run parser to JSON, with --ai generate JSON via API."

    def get_url_help(self) -> str:
        return "Full article URL (e.g. https://business.google.com/en-all/think/search-and-video/crumbl-influencer-marketing-strategy/)"


if __name__ == "__main__":
    BusinessGoogleRunner().main()
