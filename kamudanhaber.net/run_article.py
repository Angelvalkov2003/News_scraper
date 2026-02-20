"""
Single command: pass URL → fetch HTML (only div.infinite-item.d-block); with flags run parser and/or AI JSON.

Usage:
  py run_article.py <URL>              → only fetch HTML to HTML_files/
  py run_article.py <URL> --parse     → fetch HTML + parse to Parsed_files/
  py run_article.py <URL> --ai        → fetch HTML + generate JSON via Anthropic to AI_files/
  py run_article.py <URL> --parse --ai → fetch + parse + AI
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_runner import BaseRunner


class KamudanhaberRunner(BaseRunner):
    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_description(self) -> str:
        return "Fetch Kamudanhaber article by URL; with --parse run parser to JSON, with --ai generate JSON via Anthropic API."

    def get_url_help(self) -> str:
        return "Full article URL (e.g. https://www.kamudanhaber.net/...)"


if __name__ == "__main__":
    KamudanhaberRunner().main()
