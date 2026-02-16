"""
Validate parser output against scraped_article_json_schema.json.
No AI; used in production and tests to ensure strict schema compliance.
"""

import json
import sys
from pathlib import Path

import jsonschema

# Schema path relative to this file
SCHEMA_PATH = Path(__file__).parent / "scraped_article_json_schema.json"


def load_schema(path: Path | None = None) -> dict:
    """Load the canonical JSON schema. Raises if file missing or invalid."""
    path = path or SCHEMA_PATH
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_document(doc: dict, schema: dict | None = None) -> list[str]:
    """
    Validate a single article document against the schema.
    Returns a list of error messages (empty if valid).
    """
    schema = schema or load_schema()
    errors: list[str] = []
    try:
        jsonschema.validate(instance=doc, schema=schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation failed: {e.message}")
        if e.path:
            errors.append(f"  at: {'/'.join(str(p) for p in e.path)}")
    except jsonschema.SchemaError as e:
        errors.append(f"Invalid schema: {e}")
    return errors


def validate_documents(documents: list[dict], schema: dict | None = None) -> list[tuple[int, list[str]]]:
    """
    Validate a list of article documents (e.g. parser output).
    Returns list of (index, errors) for each invalid document; valid docs have empty errors.
    """
    schema = schema or load_schema()
    results: list[tuple[int, list[str]]] = []
    for i, doc in enumerate(documents):
        errs = validate_document(doc, schema)
        results.append((i, errs))
    return results


def main() -> None:
    """CLI: validate a JSON file of parsed articles."""
    import argparse
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description="Validate parsed articles JSON against schema.")
    parser.add_argument("json_file", type=Path, help="Path to parsed_articles.json (array of documents)")
    parser.add_argument("--schema", type=Path, default=None, help="Path to JSON schema (default: scraped_article_json_schema.json)")
    args = parser.parse_args()

    if not args.json_file.exists():
        print(f"File not found: {args.json_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.json_file, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("Expected JSON array of documents.", file=sys.stderr)
        sys.exit(1)

    schema = load_schema(args.schema) if args.schema else load_schema()
    results = validate_documents(data, schema)
    failed = [(i, errs) for i, errs in results if errs]
    if failed:
        for i, errs in failed:
            sys.stderr.write(f"Document [{i}]:\n")
            for e in errs:
                sys.stderr.write(f"  {e}\n")
        sys.exit(1)
    # Safe for Windows console
    print(f"Valid: {len(data)} document(s).")


if __name__ == "__main__":
    main()
