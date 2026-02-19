"""
Base parser: HTML -> scraped_article_json_schema.json (metadata + components).
Subclasses implement parse_article_html(); base handles paths and file I/O.
"""

import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from base._utils import ensure_utf8_stdout


class BaseParser(ABC):
    """Template for parsing article HTML into schema JSON."""

    def __init__(self, site_dir: Path, base_url: str):
        self.site_dir = Path(site_dir)
        self.html_files = self.site_dir / "HTML_files"
        self.parsed_files = self.site_dir / "Parsed_files"
        self.base_url = base_url

    @abstractmethod
    def parse_article_html(self, html_raw: bytes, base_url: str | None = None) -> dict:
        """
        Parse raw HTML bytes into a dict with keys: metadata, components.
        components must be {"components": [list of component dicts]}.
        """
        ...

    def main(self) -> None:
        """CLI: python parser.py [file.html ...] (default: all from HTML_files/)"""
        ensure_utf8_stdout()
        self.parsed_files.mkdir(parents=True, exist_ok=True)
        if len(sys.argv) > 1:
            paths = [Path(p).resolve() for p in sys.argv[1:]]
        else:
            paths = list(self.html_files.glob("*.html")) if self.html_files.exists() else []
        if not paths:
            print("No HTML files. Add paths or run fetch_html.py first.", file=sys.stderr)
            sys.exit(1)
        for path in paths:
            if not path.exists():
                print(f"Skipping (file missing): {path}", file=sys.stderr)
                continue
            raw = path.read_bytes()
            try:
                doc = self.parse_article_html(raw, base_url=self.base_url)
            except Exception as e:
                print(f"Error parsing {path}: {e}", file=sys.stderr)
                continue
            out = self.parsed_files / f"{path.stem}.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            print(f"  {out.name}")
        print(f"Written to {self.parsed_files}")
