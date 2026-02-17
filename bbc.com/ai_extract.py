"""Изпраща HTML към Claude API и записва в AI_files/. Изисква .env в корена с ANTHROPIC_API_KEY=..."""

import json
import os
import re
import sys
import time
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
ROOT = SITE_DIR.parent
AI_FILES = SITE_DIR / "AI_files"


def load_env():
    for line in (ROOT / ".env").read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            if key.strip() and value.strip():
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def main():
    if len(sys.argv) < 2:
        print("Употреба: python ai_extract.py <файл.html> [...]", file=sys.stderr)
        sys.exit(1)
    load_env()
    schema_content = (ROOT / "scraped_article_json_schema.json").read_text(encoding="utf-8")
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    AI_FILES.mkdir(parents=True, exist_ok=True)
    for html_arg in sys.argv[1:]:
        html_path = Path(html_arg).resolve()
        if not html_path.exists():
            html_path = (SITE_DIR / html_arg).resolve()
        if not html_path.exists():
            continue
        html_content = html_path.read_text(encoding="utf-8", errors="replace")
        prompt = f"Извлечи от този HTML статия в JSON по дадена схема. Върни САМО JSON.\n\nSchema:\n{schema_content}\n\nHTML:\n{html_content}"
        for _ in range(3):
            try:
                message = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=8192, messages=[{"role": "user", "content": prompt}])
                break
            except anthropic.RateLimitError:
                time.sleep(65)
        text = message.content[0].text if message.content else ""
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        raw_json = m.group(1).strip() if m else text.strip()
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        (AI_FILES / f"{html_path.stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Записано: {AI_FILES / (html_path.stem + '.json')}")


if __name__ == "__main__":
    main()
