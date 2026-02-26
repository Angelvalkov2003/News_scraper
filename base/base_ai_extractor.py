"""
Base AI extractor: send article HTML to Claude (Anthropic) or OpenAI API, save JSON to AI_files/.
Uses OPENAI_API_KEY if set, else ANTHROPIC_API_KEY. Subclasses override build_prompt().
"""

import json
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

from base._utils import ensure_utf8_stdout


def _extract_json_from_response(text: str) -> str:
    """Extract JSON from markdown code block if present."""
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    return m.group(1).strip() if m else text.strip()


class BaseAiExtractor(ABC):
    """Template for AI extraction via OpenAI or Anthropic API."""

    # Anthropic
    DEFAULT_MODEL = "claude-sonnet-4-5"
    FALLBACK_MODEL = "claude-sonnet-4-20250514"
    # OpenAI
    OPENAI_MODEL = "gpt-4o-mini"
    MAX_RETRIES = 3
    RATE_LIMIT_WAIT = 65

    def __init__(self, site_dir: Path):
        self.site_dir = Path(site_dir)
        self.root = self.site_dir.parent
        self.html_files = self.site_dir / "HTML_files"
        self.ai_files = self.site_dir / "AI_files"

    def _ensure_root_in_path(self) -> None:
        root_str = str(self.root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

    @abstractmethod
    def build_prompt(self, html_content: str) -> str:
        """Return the user prompt for extraction (site-specific rules)."""
        ...

    def get_schema_raw(self) -> str:
        """Override if schema path or content differs."""
        return (self.root / "scraped_article_json_schema.json").read_text(encoding="utf-8")

    def get_base_url(self) -> str | None:
        """Override to return site base URL (e.g. https://tr.euronews.com). Used to turn relative URLs into full links."""
        return None

    def _ensure_absolute_urls(self, data: dict) -> dict:
        """If get_base_url() is set, replace any relative URL (starting with /) in metadata with full absolute URL."""
        base = self.get_base_url()
        if not base or not isinstance(data.get("metadata"), dict):
            return data
        base = base.rstrip("/")
        meta = data["metadata"]
        for key in ("authors", "categories", "tags"):
            items = meta.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"].strip().startswith("/"):
                    item["url"] = base + item["url"]
        return data

    def post_process_output(self, data: dict) -> dict:
        """Override to strip nulls or normalize; default returns data unchanged."""
        return data

    def main(self) -> None:
        """CLI: python ai_extract.py <file.html> [file2.html ...]"""
        ensure_utf8_stdout()
        self._ensure_root_in_path()
        from dotenv import load_dotenv

        load_dotenv(self.root / ".env")
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        use_openai = bool(openai_key)
        if not use_openai and not anthropic_key:
            raise SystemExit(
                "Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env (project root)."
            )

        schema_raw = self.get_schema_raw()
        if use_openai:
            try:
                from openai import OpenAI
            except ImportError:
                raise SystemExit("Install: pip install openai")
            client = OpenAI(api_key=openai_key)
        else:
            try:
                import anthropic
            except ImportError:
                raise SystemExit("Install: pip install anthropic")
            from ai_schema_for_claude import load_and_prepare_schema
            schema = load_and_prepare_schema(self.root)
            client = anthropic.Anthropic(api_key=anthropic_key)

        self.ai_files.mkdir(parents=True, exist_ok=True)

        if len(sys.argv) < 2:
            paths = list(self.html_files.glob("*.html")) if self.html_files.exists() else []
            if not paths:
                print("Usage: python ai_extract.py <file.html> [file2.html ...]", file=sys.stderr)
                sys.exit(1)
            html_args = [str(p) for p in paths]
        else:
            html_args = sys.argv[1:]

        for html_arg in html_args:
            html_path = Path(html_arg).resolve()
            if not html_path.is_absolute() and (self.site_dir / html_arg).exists():
                html_path = (self.site_dir / html_arg).resolve()
            if not html_path.exists() and (self.html_files / html_arg).exists():
                html_path = (self.html_files / html_arg).resolve()
            if not html_path.exists():
                print(f"Skipping (file missing): {html_path}", file=sys.stderr)
                continue
            html_content = html_path.read_text(encoding="utf-8", errors="replace")
            prompt = self.build_prompt(html_content)
            prompt_with_schema = self._build_fallback_prompt(html_content, schema_raw)

            if use_openai:
                text = self._call_openai(client, prompt_with_schema)
            else:
                text = self._call_api(client, anthropic, schema, prompt, prompt_with_schema, html_content)

            if text is None:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                print(f"API returned invalid JSON for {html_path.name}: {e}", file=sys.stderr)
                continue
            data = self._ensure_absolute_urls(data)
            data = self.post_process_output(data)
            out_file = self.ai_files / f"{html_path.stem}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Written: {out_file}")

    def _build_fallback_prompt(self, html_content: str, schema_raw: str) -> str:
        """Prompt used when structured output fails (schema in body). Override if needed."""
        return f"""Extract this article HTML. Return ONE valid JSON conforming to the schema below. Return ONLY JSON.

JSON Schema:
{schema_raw}

Article HTML:
{html_content}"""

    def _call_api(
        self,
        client,
        anthropic_module,
        schema: dict,
        prompt: str,
        prompt_with_schema: str,
        html_content: str,
    ) -> str | None:
        """Try structured output; on BadRequest (format/grammar) fall back to prompt+parse."""
        for attempt in range(self.MAX_RETRIES):
            try:
                message = client.messages.create(
                    model=self.DEFAULT_MODEL,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                    output_config={"format": {"type": "json_schema", "schema": schema}},
                )
                text = (message.content[0].text if message.content else "").strip()
                return text
            except anthropic_module.BadRequestError as e:
                err = str(e).lower()
                if "output format" in err or "grammar" in err:
                    message = client.messages.create(
                        model=self.FALLBACK_MODEL,
                        max_tokens=8192,
                        messages=[{"role": "user", "content": prompt_with_schema}],
                    )
                    raw = (message.content[0].text if message.content else "").strip()
                    return _extract_json_from_response(raw)
                raise
            except anthropic_module.RateLimitError:
                if attempt + 1 >= self.MAX_RETRIES:
                    print("Error: rate limit (429). Try again in a minute.", file=sys.stderr)
                    raise SystemExit(1)
                print(f"Rate limit (429). Waiting {self.RATE_LIMIT_WAIT} s...", file=sys.stderr)
                time.sleep(self.RATE_LIMIT_WAIT)
        return None

    def _call_openai(self, client, prompt_with_schema: str) -> str | None:
        """Call OpenAI Chat Completions with JSON mode; retry on rate limit."""
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = client.chat.completions.create(
                    model=self.OPENAI_MODEL,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt_with_schema}],
                    response_format={"type": "json_object"},
                )
                text = (resp.choices[0].message.content or "").strip()
                return text if text else None
            except Exception as e:
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str:
                    if attempt + 1 >= self.MAX_RETRIES:
                        print("Error: OpenAI rate limit (429). Try again later.", file=sys.stderr)
                        raise SystemExit(1)
                    print(f"OpenAI rate limit. Waiting {self.RATE_LIMIT_WAIT} s...", file=sys.stderr)
                    time.sleep(self.RATE_LIMIT_WAIT)
                else:
                    raise
        return None
