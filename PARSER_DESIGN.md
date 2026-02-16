# Article Parser – Design & Constraints

## Principles

- **Deterministic**: Same HTML input always produces the same JSON output. No randomness, no model calls.
- **Production-grade**: Robust to malformed HTML, encoding variants, and site-specific structure. Failures are explicit and debuggable.
- **Schema-strict**: Every output document conforms to `scraped_article_json_schema.json`. The schema is fixed; parsers adapt to it, not the other way around.

---

## AI vs Production

| Use case | AI allowed? | Purpose |
|----------|-------------|--------|
| **Production parsing** | **No** | The parser that runs in production (`parse_article.py`) uses only rule-based HTML parsing (e.g. BeautifulSoup). No LLMs, no embeddings, no external AI APIs. |
| **Reference / testing** | Yes | AI may be used to produce reference JSON (golden outputs) for given HTML, or to suggest selectors. Those outputs are then used as **tests** or **documentation**. The production parser is validated against schema and optionally against these references. |

So: **AI is never invoked during production parsing.** AI is only a tool to help build and test the deterministic parser.

---

## Order of Components

- The **order** of items in `components.components` is significant. It must reflect the document order of the main article content (as it appears in the HTML).
- Parsers must walk the article container in document order and emit one component per logical element (heading, paragraph, image, list, table, etc.) without reordering.

---

## Schema Compliance

- Output must validate against `scraped_article_json_schema.json`.
- Use the `schema_validator` module or `--validate` to check every produced document.
- No extra top-level keys; no missing required keys; component `type` and `properties` must match the schema’s `anyOf` definitions.

---

## Robustness & Debuggability

- **Single responsibility**: One module parses HTML → structured dict; another validates dict → schema. Keep parsing and validation separate so failures are easy to locate.
- **Explicit errors**: On parse failure, raise or log with clear message and, when possible, the offending element or selector.
- **Encoding**: Support UTF-8 and UTF-16 (BOM) for raw HTML. Decode once, then work in Unicode.
- **Content isolation**: Only the main article body is parsed (e.g. `div.contentdetail` or equivalent). Navigation, ads, sidebars, and footers are ignored.

---

## File Roles

- `parse_article.py` – Production parser (no AI). Entrypoint for batch or single-file parsing.
- `scraped_article_json_schema.json` – Canonical schema. Do not change per site.
- `schema_validator.py` – Validates parser output against the schema. Used by tests and optionally by CLI.
- `tests/test_parser.py` – Runs parser on fixtures, validates output against schema (and optionally reference JSON). No AI is used in test logic; reference outputs may be produced once (e.g. by AI or by hand) and committed for regression comparison.
