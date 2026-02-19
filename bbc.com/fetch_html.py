"""Fetch article HTML and save to HTML_files/. No article extraction; full page saved."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_fetcher import BaseHtmlFetcher


class BbcHtmlFetcher(BaseHtmlFetcher):
    """BBC: save raw HTML (no extract_article_only)."""

    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)


if __name__ == "__main__":
    BbcHtmlFetcher().main()
