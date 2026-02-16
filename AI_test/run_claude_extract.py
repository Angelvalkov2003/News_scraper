"""
Изпраща HTML статия и scraped_article_json_schema.json към Claude API;
записва върнатия JSON в AI_test/<име_на_html_файла>/output.json.

Използвай: python AI_test/run_claude_extract.py <път_към_HTML>
Пример:   python AI_test/run_claude_extract.py ParsedHTMLs/birgun.net/baska-turlu-acim-dedi-691862.html

Изисква .env в корена на проекта с ANTHROPIC_API_KEY=...
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Под Windows конзолата често не е UTF-8 – принтирането на кирилица да работи и да можеш да копираш в Cursor
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Project root (parent of AI_test)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        raise SystemExit("Липсва .env в корена на проекта с ANTHROPIC_API_KEY=...")
    for line in env_path.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ[key] = value


def extract_json_from_response(text: str) -> str:
    """Ако отговорът е в ```json ... ```, извлича само JSON частта."""
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    return text.strip()


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(1)

    load_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("В .env липсва ANTHROPIC_API_KEY.")

    html_path = Path(sys.argv[1]).resolve()
    if not html_path.exists():
        raise SystemExit(f"Файлът не съществува: {html_path}")

    schema_path = PROJECT_ROOT / "scraped_article_json_schema.json"
    if not schema_path.exists():
        raise SystemExit(f"Схемата не е намерена: {schema_path}")

    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    schema_content = schema_path.read_text(encoding="utf-8")

    prompt = f"""Даден е HTML на статия от новинарски сайт и JSON Schema за изходния формат.

Задача: извлечи от HTML всичка информация (заглавие, автор, дата, категории, тагове, параграфи, заглавия, цитати, изображения и т.н.) и върни ЕДИН валиден JSON обект, който отговаря на следната схема. Върни САМО JSON, без обяснения преди или след него.

JSON Schema за изхода:
{schema_content}

HTML на статията:
{html_content}

Върни един JSON обект с полета "metadata" и "components" според схемата по-горе."""

    try:
        import anthropic
    except ImportError:
        raise SystemExit("Инсталирай: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    max_retries = 3
    wait_seconds = 65  # лимитът е „на минута“, изчакваме малко над 1 мин

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
                print("Грешка: лимит на заявки (429). Опитай след минута-две.", file=sys.stderr)
                raise SystemExit(1) from e
            print(f"Лимит (429). Изчаквам {wait_seconds} s, опит {attempt + 2}/{max_retries}...", file=sys.stderr)
            time.sleep(wait_seconds)
    response_text = message.content[0].text if message.content else ""

    raw_json = extract_json_from_response(response_text)
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        print("Claude върна невалиден JSON. Първи 500 символа:", file=sys.stderr)
        print(raw_json[:500], file=sys.stderr)
        raise SystemExit(e) from e

    out_dir = SCRIPT_DIR / html_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "output.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Записано: {out_file}")


if __name__ == "__main__":
    main()
