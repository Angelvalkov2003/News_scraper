"""Send HTML to Claude API and save to AI_files/. Uses Structured Outputs (schema via output_config)."""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

SITE_DIR = Path(__file__).resolve().parent
ROOT = SITE_DIR.parent
AI_FILES = SITE_DIR / "AI_files"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ai_schema_for_claude import load_and_prepare_schema


def main():
    if len(sys.argv) < 2:
        print("Usage: python ai_extract.py <file.html> [...]", file=sys.stderr)
        sys.exit(1)
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY missing in .env (create .env in project root with ANTHROPIC_API_KEY=...)")
    import anthropic
    schema = load_and_prepare_schema(ROOT)
    client = anthropic.Anthropic(api_key=api_key)
    AI_FILES.mkdir(parents=True, exist_ok=True)
    for html_arg in sys.argv[1:]:
        html_path = Path(html_arg).resolve()
        if not html_path.exists():
            html_path = (SITE_DIR / html_arg).resolve()
        if not html_path.exists():
            continue
        html_content = html_path.read_text(encoding="utf-8", errors="replace")
        prompt = f"""Extract this BBC article HTML into one JSON object. Follow these rules strictly.

STRICT RULES:
- Authors: Take ONLY from the HTML (script "authors", meta, byline). Use EXACT name. author url = FULL absolute URL (https://...) when there is a link, never relative. If no author, null.
- Categories: Take ONLY from meta article:section or section links. Exact name. url = FULL absolute URL only (e.g. https://www.bbc.com/...), never relative paths. If none, null.
- Tags: Set ONLY if the article has tags explicitly shown in a dedicated place (e.g. "İlgili Konular" / topic links). If there is no dedicated tags section, use null. Do not invent tags.
- Title: Exact headline from <h1> or og:title/meta title (strip site suffix like " - BBC News Türkçe" if you want only the headline).
- document_date: ISO 8601 from meta article:published_time or datePublished only.
- Body text: Copy paragraph and heading text EXACTLY from the HTML, in the SAME order as in the document. Do NOT paraphrase, summarize, or merge paragraphs. Do NOT add text that is not in the HTML. Each <p> → one paragraph component; each <h1>-<h6> → one heading component. Preserve **bold** and *italic* markdown as in the source. Do not mix up or reorder content from different parts of the article.

Output: metadata (title, document_date, authors, categories, tags) and components (array of heading, paragraph, image, citation, list, table, etc.) in document order.

HTML:
{html_content}"""
        for _ in range(3):
            try:
                message = client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                    output_config={"format": {"type": "json_schema", "schema": schema}},
                )
                break
            except anthropic.RateLimitError:
                time.sleep(65)
        text = (message.content[0].text if message.content else "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        (AI_FILES / f"{html_path.stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Written: {AI_FILES / (html_path.stem + '.json')}")


if __name__ == "__main__":
    main()
