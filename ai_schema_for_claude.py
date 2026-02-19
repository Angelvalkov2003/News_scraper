"""
Load and prepare scraped_article_json_schema.json for Claude API Structured Outputs.
See: https://platform.claude.com/docs/en/build-with-claude/structured-outputs

- Removes unsupported constraints: minimum, maximum, minLength, maxLength, multipleOf
- Ensures all objects have additionalProperties: false
- Returns schema ready for output_config={"format": {"type": "json_schema", "schema": ...}}
"""

from pathlib import Path

_UNSUPPORTED_KEYS = frozenset({"minimum", "maximum", "minLength", "maxLength", "multipleOf"})


def _prepare_node(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_prepare_node(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _UNSUPPORTED_KEYS:
                continue
            out[k] = _prepare_node(v)
        if out.get("type") == "object" and "additionalProperties" not in out:
            out["additionalProperties"] = False
        return out
    return obj


def load_and_prepare_schema(root: Path) -> dict:
    """Load scraped_article_json_schema.json from root and prepare for Claude structured outputs."""
    path = root / "scraped_article_json_schema.json"
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    schema = __import__("json").loads(path.read_text(encoding="utf-8"))
    return _prepare_node(schema)
