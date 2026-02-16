"""
Tests for the deterministic article parser.
No AI is used in these tests. Validation is against the canonical JSON schema only.
Run: python -m unittest discover -s tests -p "test_*.py"
"""

import json
import sys
import unittest
from pathlib import Path

# Project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parse_article import parse_article_html
from schema_validator import load_schema, validate_document, validate_documents


class TestParser(unittest.TestCase):
    """Deterministic parser tests; no AI."""

    @classmethod
    def setUpClass(cls):
        cls.fixture_html = PROJECT_ROOT / "ParsedHTMLs" / "birgun.net" / "article.html"
        cls.schema_path = PROJECT_ROOT / "scraped_article_json_schema.json"

    def test_parser_produces_schema_compliant_document(self):
        """Parse fixture HTML and assert output validates against scraped_article_json_schema.json."""
        if not self.fixture_html.exists():
            self.skipTest("Fixture HTML missing (ParsedHTMLs/birgun.net/article.html)")
        raw = self.fixture_html.read_bytes()
        doc = parse_article_html(raw)
        schema = load_schema(self.schema_path)
        errors = validate_document(doc, schema)
        self.assertEqual(errors, [], f"Schema validation failed: {errors}")

    def test_parser_output_has_required_root_keys(self):
        """Assert every parsed document has metadata and components."""
        if not self.fixture_html.exists():
            self.skipTest("Fixture HTML missing")
        raw = self.fixture_html.read_bytes()
        doc = parse_article_html(raw)
        self.assertIn("metadata", doc)
        self.assertIn("components", doc)
        self.assertIn("components", doc["components"])
        self.assertIsInstance(doc["components"]["components"], list)

    def test_parser_preserves_component_order(self):
        """Assert components list is in document order (at least heading before many paragraphs)."""
        if not self.fixture_html.exists():
            self.skipTest("Fixture HTML missing")
        raw = self.fixture_html.read_bytes()
        doc = parse_article_html(raw)
        comps = doc["components"]["components"]
        types = [c["type"] for c in comps]
        self.assertIn("heading", types)
        self.assertLess(types.index("heading"), len(types) - 1)

    def test_validate_parsed_articles_json(self):
        """If parsed_articles.json exists (in Schemas or root), validate it against schema."""
        json_path = PROJECT_ROOT / "Schemas" / "birgun.net" / "parsed" / "parsed_articles.json"
        if not json_path.exists():
            json_path = PROJECT_ROOT / "parsed_articles.json"
        if not json_path.exists():
            self.skipTest("parsed_articles.json missing")
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        schema = load_schema(self.schema_path)
        results = validate_documents(data, schema)
        failed = [(i, e) for i, e in results if e]
        self.assertFalse(failed, f"parsed_articles.json has invalid documents: {failed}")


if __name__ == "__main__":
    unittest.main()
