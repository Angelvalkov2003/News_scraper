"""
Send article HTML to Claude API and save result to AI_files/ with article slug (scraped_article_json_schema.json).
Run from birgun.net folder: python ai_extract.py <file.html> [file2.html ...]
Requires .env in project root with ANTHROPIC_API_KEY=...
"""

import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SITE_DIR = Path(__file__).resolve().parent
ROOT = SITE_DIR.parent
HTML_FILES = SITE_DIR / "HTML_files"
AI_FILES = SITE_DIR / "AI_files"


def extract_json_from_response(text: str) -> str:
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    return text.strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: python ai_extract.py <file.html> [file2.html ...]", file=sys.stderr)
        sys.exit(1)
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY missing in .env (create .env in project root with ANTHROPIC_API_KEY=...)")
    schema_path = ROOT / "scraped_article_json_schema.json"
    if not schema_path.exists():
        raise SystemExit(f"Schema not found: {schema_path}")
    schema_content = schema_path.read_text(encoding="utf-8")
    try:
        import anthropic
    except ImportError:
        raise SystemExit("Install: pip install anthropic")
    client = anthropic.Anthropic(api_key=api_key)
    AI_FILES.mkdir(parents=True, exist_ok=True)
    max_retries, wait_seconds = 3, 65
    for html_arg in sys.argv[1:]:
        html_path = Path(html_arg).resolve()
        if not html_path.is_absolute() and (SITE_DIR / html_arg).exists():
            html_path = (SITE_DIR / html_arg).resolve()
        if not html_path.exists():
            print(f"Skipping (file missing): {html_path}", file=sys.stderr)
            continue
        html_content = html_path.read_text(encoding="utf-8", errors="replace")
        prompt = f"""You are given HTML of an article from a news site and a JSON Schema for the output format.
Task: extract all information from the HTML and return ONE valid JSON object that conforms to the schema below. Return ONLY JSON.

JSON Schema for output:
{schema_content}

Article HTML:
{html_content}

Return a single JSON object with "metadata" and "components" per the schema."""

        for attempt in range(max_retries):
            try:
                message = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except anthropic.RateLimitError as e:
                if attempt + 1 >= max_retries:
                    print("Error: rate limit (429). Try again in a minute.", file=sys.stderr)
                    raise SystemExit(1) from e
                print(f"Rate limit (429). Waiting {wait_seconds} s...", file=sys.stderr)
                time.sleep(wait_seconds)
        response_text = message.content[0].text if message.content else ""
        raw_json = extract_json_from_response(response_text)
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            print(f"Claude returned invalid JSON for {html_path.name}: {e}", file=sys.stderr)
            continue
        out_file = AI_FILES / f"{html_path.stem}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Written: {out_file}")


if __name__ == "__main__":
    main()
