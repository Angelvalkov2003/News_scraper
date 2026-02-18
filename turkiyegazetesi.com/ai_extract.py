"""
Изпраща HTML към Anthropic (Claude) API; моделът извлича съдържанието и връща JSON
стриктно по scraped_article_json_schema.json (MarkdownDocument). Запис в AI_files/.
Изисква .env в корена на проекта с ANTHROPIC_API_KEY=...
"""

import json
import os
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SITE_DIR = Path(__file__).resolve().parent
ROOT = SITE_DIR.parent
AI_FILES = SITE_DIR / "AI_files"
HTML_FILES = SITE_DIR / "HTML_files"


def load_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise SystemExit("Липсва .env в корена на проекта с ANTHROPIC_API_KEY=...")
    for line in env_path.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value:
            os.environ[key] = value


def extract_json_from_response(text: str) -> str:
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _strip_nulls_for_schema(obj):
    """Remove keys with null/None so schema (string-only for optional fields) validates."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_strip_nulls_for_schema(x) for x in obj]
    if isinstance(obj, dict):
        return {
            k: _strip_nulls_for_schema(v)
            for k, v in obj.items()
            if v is not None
        }
    return obj


def build_prompt(schema_content: str, html_content: str) -> str:
    return f"""Ти си асистент, който извлича структурирани данни от HTML статия и ги връща като един валиден JSON обект.

СТРУКТУРА НА ИЗХОДА (задължително спазвай):
- Коренът е обект с точно два ключа: "metadata" и "components".
- "metadata": обект с ключове document_date, authors, categories, tags (всички от head/article както са описани по-долу).
- "components": обект с един ключ "components", чиято стойност е масив от компоненти в реда на срещане в текста.

METADATA (от head и article):
- document_date: ISO 8601 дата от meta[property="article:published_time"] или meta[name="datePublished"] (content). Ако липсва → null.
- authors: масив от {{"name": "<име>", "url": null}}. Добави автор от meta[property="article:author"] или meta[name="articleAuthor"]. Ако в article има блок за редактор (напр. "Editör : ..." с линк), добави втори елемент с името на редактора, url: null.
- categories: масив от {{"name": "<категория>", "url": "<пълен URL ако има href>"}} от елементите в .article-category-tag (напр. линк с текст "Ekonomi" и href="/ekonomi" → name "Ekonomi", url "https://www.turkiyegazetesi.com.tr/ekonomi"). Ако няма → null.
- tags: винаги null.

COMPONENTI (в реда на поява в article):
HTML съдържа div.article-scope > article. В него може да има:
- Първа медия (преди article-content): div.article-main-image с <video> или <img>. Video → type "video", properties {{"url": src от <source>, "thumbnail_image_url": poster от <video> ако има}}. Image → type "image", properties {{"url": src, "description": alt, "caption": текст от figcaption ако има}}.
- В div.article-content (itemprop="articleBody"): обходи елементите в ред и създай компоненти:
  - h1–h6 → {{"type": "heading", "properties": {{"text": "<съдържание>", "level": 1–6}}}}
  - p → {{"type": "paragraph", "properties": {{"text": "<текст с markdown: **bold**, *italic*>"}}}}
  - blockquote → {{"type": "citation", "properties": {{"citation_text": "<цитат>"}}}}
  - figure / img с опционално figcaption → {{"type": "image", "properties": {{"url": "<src>", "description": "<alt>", "caption": "<figcaption текст> ако има"}}}}. Не включвай ключ caption ако няма caption.
  - hr → {{"type": "horizontal_ruler", "properties": {{}}}}
  - ul → {{"type": "list", "properties": {{"items": [{{"indent": 0, "bullet": "-", "content": "<текст на li>"}}, ...]}}}}
  - ol → {{"type": "list", "properties": {{"items": [{{"indent": 0, "bullet": "1.", "content": "..."}}, {{"indent": 0, "bullet": "2.", "content": "..."}}, ...]}}}}
  - table → {{"type": "table", "properties": {{"headers": ["<th или първи ред>"], "rows": [["<cell>", ...], ...]}}}}
  - pre/code → {{"type": "code_block", "properties": {{"code": "<съдържание>", "language": null}}}}
- Блокове като "Editör", "Paylaş", коментари, препоръки — не ги превръщай в компоненти; използвай редактора само за metadata.authors.

ПРАВИЛА:
- Върни САМО един валиден JSON обект, без коментари и без текст преди/след него.
- Не добавяй празни компоненти. Не дублирай съдържание.
- За optional полета (caption, description и т.н.) не включвай ключа, ако няма стойност — не пиши "caption": null.
- Текстът в paragraph/heading трябва да запазва markdown: **удебелен**, *курсив*, ***и двете***.

JSON Schema (за референция по типовете и имената):

{schema_content}

---

HTML на статията:

{html_content}
"""


def main():
    if len(sys.argv) < 2:
        paths = list(HTML_FILES.glob("*.html")) if HTML_FILES.exists() else []
        if not paths:
            print("Употреба: python ai_extract.py <файл.html> [файл2.html ...]", file=sys.stderr)
            sys.exit(1)
        html_args = [str(p) for p in paths]
    else:
        html_args = sys.argv[1:]
    load_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("В .env липсва ANTHROPIC_API_KEY.")
    schema_path = ROOT / "scraped_article_json_schema.json"
    if not schema_path.exists():
        raise SystemExit(f"Схемата не е намерена: {schema_path}")
    schema_content = schema_path.read_text(encoding="utf-8")
    try:
        import anthropic
        import jsonschema
    except ImportError as e:
        raise SystemExit(f"Инсталирай зависимостите: pip install anthropic jsonschema. {e}")
    schema = json.loads(schema_content)
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
            print(f"Пропускам: {html_path}", file=sys.stderr)
            continue
        html_content = html_path.read_text(encoding="utf-8", errors="replace")
        prompt = build_prompt(schema_content, html_content)
        message = None
        for attempt in range(max_retries):
            try:
                message = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except anthropic.RateLimitError:
                if attempt + 1 >= max_retries:
                    raise SystemExit("Rate limit; опитай по-късно.")
                time.sleep(wait_seconds)
        if not message or not message.content:
            print(f"Празен отговор за {html_path.name}", file=sys.stderr)
            continue
        response_text = message.content[0].text if message.content else ""
        raw_json = extract_json_from_response(response_text)
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            print(f"Невалиден JSON за {html_path.name}: {e}", file=sys.stderr)
            continue
        data = _strip_nulls_for_schema(data)
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            print(f"Внимание: изходът не отговаря на схемата за {html_path.name}: {e}", file=sys.stderr)
        out_file = AI_FILES / f"{html_path.stem}.json"
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Записано: {out_file}")


if __name__ == "__main__":
    main()
