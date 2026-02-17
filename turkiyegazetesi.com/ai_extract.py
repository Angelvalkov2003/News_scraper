"""
Изпраща HTML към Claude API и записва в AI_files/ (scraped_article_json_schema.json).
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


def main():
    if len(sys.argv) < 2:
        print("Употреба: python ai_extract.py <файл.html> [файл2.html ...]", file=sys.stderr)
        sys.exit(1)
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
    except ImportError:
        raise SystemExit("Инсталирай: pip install anthropic")
    client = anthropic.Anthropic(api_key=api_key)
    AI_FILES.mkdir(parents=True, exist_ok=True)
    max_retries, wait_seconds = 3, 65
    for html_arg in sys.argv[1:]:
        html_path = Path(html_arg).resolve()
        if not html_path.is_absolute() and (SITE_DIR / html_arg).exists():
            html_path = (SITE_DIR / html_arg).resolve()
        if not html_path.exists():
            print(f"Пропускам: {html_path}", file=sys.stderr)
            continue
        html_content = html_path.read_text(encoding="utf-8", errors="replace")
        prompt = f"""Даден е HTML на статия и JSON Schema. Извлечи всичка информация и върни ЕДИН валиден JSON обект (metadata + components). Върни САМО JSON.\n\nSchema:\n{schema_content}\n\nHTML:\n{html_content}"""
        for attempt in range(max_retries):
            try:
                message = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=8192, messages=[{"role": "user", "content": prompt}])
                break
            except anthropic.RateLimitError:
                if attempt + 1 >= max_retries:
                    raise SystemExit(1)
                time.sleep(wait_seconds)
        response_text = message.content[0].text if message.content else ""
        raw_json = extract_json_from_response(response_text)
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            print(f"Невалиден JSON за {html_path.name}: {e}", file=sys.stderr)
            continue
        out_file = AI_FILES / f"{html_path.stem}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Записано: {out_file}")


if __name__ == "__main__":
    main()
