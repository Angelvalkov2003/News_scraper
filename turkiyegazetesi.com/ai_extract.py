"""
Send HTML to Anthropic (Claude) API; output to AI_files/. Tries Structured Outputs; on schema-too-large falls back to prompt+parse.
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
AI_FILES = SITE_DIR / "AI_files"
HTML_FILES = SITE_DIR / "HTML_files"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ai_schema_for_claude import load_and_prepare_schema


def _extract_json_from_response(text: str) -> str:
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    return m.group(1).strip() if m else text.strip()


def _strip_nulls_for_schema(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nulls_for_schema(v) for k, v in obj.items() if v is not None}
    return obj


def build_prompt(html_content: str) -> str:
    return f"""Extract this Türkiye Gazetesi article HTML into one JSON object. Follow these rules strictly.

STRICT RULES:
- Authors: Take ONLY from the HTML. Look for meta article:author or articleAuthor; also look for editor block (e.g. "Editör : ESMA KARAYEL" with optional link) and add as second author with EXACT name. When the author/editor has a link (<a href="...">), use that as author url — always as FULL absolute URL (https://www.turkiyegazetesi.com.tr/...), never a relative path. If no link, url: null.
- Categories: Take ONLY from .article-category-tag or section/category links. name = exact link text (e.g. "Gündem"). url = FULL absolute URL only: e.g. https://www.turkiyegazetesi.com.tr/gundem — never use relative paths like /gundem. If none, null.
- Tags: Set ONLY if the article has tags explicitly shown in a dedicated place. If no dedicated tags section, use null. Do not invent tags.
- Title: Exact headline from the article (h1 or meta), not invented.
- document_date: ISO 8601 from meta article:published_time or datePublished only.
- Body text: Copy text EXACTLY from the HTML in the SAME order. div.article-scope > article: first media in div.article-main-image (video or image) → one component; then in div.article-content walk in order: each h1–h6 → one heading, each p → one paragraph. Do NOT paraphrase, summarize, or merge paragraphs. Do NOT add text that is not in the HTML. Preserve **bold** and *italic*. Exclude "Editör", "Paylaş", "Yorum", "ÖNERİLEN", "ÇOK OKUNANLAR" and any block after the main article. Omit optional keys when no value.

Output: metadata + components in document order.

Article HTML:

{html_content}
"""


def main():
    if len(sys.argv) < 2:
        paths = list(HTML_FILES.glob("*.html")) if HTML_FILES.exists() else []
        if not paths:
            print("Usage: python ai_extract.py <file.html> [file2.html ...]", file=sys.stderr)
            sys.exit(1)
        html_args = [str(p) for p in paths]
    else:
        html_args = sys.argv[1:]
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY missing in .env (create .env in project root with ANTHROPIC_API_KEY=...)")
    try:
        import anthropic
    except ImportError as e:
        raise SystemExit(f"Install dependencies: pip install anthropic. {e}")
    schema = load_and_prepare_schema(ROOT)
    schema_raw = (ROOT / "scraped_article_json_schema.json").read_text(encoding="utf-8")
    client = anthropic.Anthropic(api_key=api_key)
    AI_FILES.mkdir(parents=True, exist_ok=True)
    max_retries, wait_seconds = 3, 65
    for html_arg in html_args:
        html_path = Path(html_arg).resolve()
        if not html_path.is_absolute() and (SITE_DIR / html_arg).exists():
            html_path = (SITE_DIR / html_arg).resolve()
        if not html_path.exists() and (HTML_FILES / html_arg).exists():
            html_path = (HTML_FILES / html_arg).resolve()
        if not html_path.exists():
            print(f"Skipping: {html_path}", file=sys.stderr)
            continue
        html_content = html_path.read_text(encoding="utf-8", errors="replace")
        prompt_short = build_prompt(html_content)
        prompt_with_schema = f"""Extract this Türkiye Gazetesi article HTML. Return ONE valid JSON conforming to the schema below. Return ONLY JSON.

STRICT: authors = exact names from HTML; author url = FULL absolute URL (https://www.turkiyegazetesi.com.tr/...) when there is a link, never relative. categories = exact names and FULL absolute URLs only (e.g. https://www.turkiyegazetesi.com.tr/gundem), never /gundem. Body: copy text EXACTLY in order.

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
            except anthropic.RateLimitError:
                if attempt + 1 >= max_retries:
                    raise SystemExit("Rate limit; try again later.")
                time.sleep(wait_seconds)
        if text is None:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON for {html_path.name}: {e}", file=sys.stderr)
            continue
        data = _strip_nulls_for_schema(data)
        out_file = AI_FILES / f"{html_path.stem}.json"
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Written: {out_file}")


if __name__ == "__main__":
    main()
