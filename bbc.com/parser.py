"""Парсва HTML -> scraped_article_json_schema.json в Parsed_files/. TODO: имплементирай за bbc.com."""

import json
import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
HTML_FILES = SITE_DIR / "HTML_files"
PARSED_FILES = SITE_DIR / "Parsed_files"


def parse_article_html(html_raw: bytes, base_url: str = "https://www.bbc.com") -> dict:
    return {"metadata": {}, "components": {"components": []}}


def main():
    PARSED_FILES.mkdir(parents=True, exist_ok=True)
    paths = list(HTML_FILES.glob("*.html")) if HTML_FILES.exists() else ([] if len(sys.argv) < 2 else [Path(p) for p in sys.argv[1:]])
    if not paths:
        print("Няма HTML файлове.", file=sys.stderr)
        sys.exit(1)
    for path in paths:
        if not path.exists():
            continue
        doc = parse_article_html(path.read_bytes())
        (PARSED_FILES / f"{path.stem}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {path.stem}.json")
    print(f"Записано в {PARSED_FILES}")


if __name__ == "__main__":
    main()
