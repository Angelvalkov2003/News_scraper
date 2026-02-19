"""
Send article HTML to Claude API and save result to AI_files/. Tries Structured Outputs; on schema-too-large falls back to prompt+parse.
Run from birgun.net folder: python ai_extract.py <file.html> [file2.html ...]
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

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ai_schema_for_claude import load_and_prepare_schema


def _extract_json_from_response(text: str) -> str:
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    return m.group(1).strip() if m else text.strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: python ai_extract.py <file.html> [file2.html ...]", file=sys.stderr)
        sys.exit(1)
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY missing in .env (create .env in project root with ANTHROPIC_API_KEY=...)")
    try:
        import anthropic
    except ImportError:
        raise SystemExit("Install: pip install anthropic")
    schema = load_and_prepare_schema(ROOT)
    schema_raw = (ROOT / "scraped_article_json_schema.json").read_text(encoding="utf-8")
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
        prompt_short = f"""Extract this birgun.net article HTML into one JSON object. Follow these rules strictly.

STRICT RULES:
- Authors: Take ONLY from the HTML (meta, byline). EXACT name. When author has a link, url = FULL absolute URL (https://www.birgun.net/...), never relative. If no link, url: null.
- Categories: Take ONLY from section links or meta. name = exact link text. url = FULL absolute URL only (https://www.birgun.net/...), never relative paths like /kategori/.... If none, null.
- Tags: Set ONLY if the article page has tags explicitly shown in a dedicated place (tag section, tag links). If no dedicated tags block, use null. Do not invent tags.
- Title: Exact headline from the article (h1 or meta), not invented.
- document_date: ISO 8601 from meta article:published_time or datePublished only.
- Body text: Copy text EXACTLY from the HTML in the SAME order. One <p> → one paragraph component; one <h1>-<h6> → one heading. Do NOT paraphrase, summarize, or merge paragraphs. Do NOT add sentences that are not in the HTML. Preserve **bold** and *italic* as in source. Skip "related", "recommended", "Sıradaki Haber" and everything after the main story.

Output: metadata + components array in document order.

Article HTML:
{html_content}"""
        prompt_with_schema = f"""Extract this birgun.net article HTML. Return ONE valid JSON conforming to the schema below. Return ONLY JSON.

STRICT: authors = exact names from HTML (meta/article byline); categories = exact names and URLs from section links; do NOT invent. Body: copy paragraph/heading text EXACTLY in order, do NOT paraphrase or mix up text.

JSON Schema:
{schema_raw}

Article HTML:
{html_content}"""

        text = None
        for attempt in range(max_retries):
            try:
                message = client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt_short}],
                    output_config={"format": {"type": "json_schema", "schema": schema}},
                )
                text = (message.content[0].text if message.content else "").strip()
                break
            except anthropic.BadRequestError as e:
                err = str(e).lower()
                if "output format" in err or "grammar" in err:
                    message = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=8192,
                        messages=[{"role": "user", "content": prompt_with_schema}],
                    )
                    raw = (message.content[0].text if message.content else "").strip()
                    text = _extract_json_from_response(raw)
                    break
                raise
            except anthropic.RateLimitError as e:
                if attempt + 1 >= max_retries:
                    print("Error: rate limit (429). Try again in a minute.", file=sys.stderr)
                    raise SystemExit(1) from e
                print(f"Rate limit (429). Waiting {wait_seconds} s...", file=sys.stderr)
                time.sleep(wait_seconds)
        if text is None:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"Claude returned invalid JSON for {html_path.name}: {e}", file=sys.stderr)
            continue
        out_file = AI_FILES / f"{html_path.stem}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Written: {out_file}")


if __name__ == "__main__":
    main()
