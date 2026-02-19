# News Scraper

## Structure

**Root:**
- `base/` – **shared base classes** (Template Method pattern)
  - `base_fetcher.py` – `BaseHtmlFetcher` (fetch URL, optional `extract_article_only`, save to `HTML_files/`)
  - `base_parser.py` – `BaseParser` (paths, I/O; subclasses implement `parse_article_html()`)
  - `base_ai_extractor.py` – `BaseAiExtractor` (env, schema, retries; subclasses implement `build_prompt()`)
  - `base_runner.py` – `BaseRunner` (orchestrates fetch → parse → AI via subprocess)
- `.env` – API keys (ANTHROPIC_API_KEY, etc.)
- `scraped_article_json_schema.json` – shared schema for all outputs
- `recent_posts_turkish_news_websites.json` – list of posts/URLs
- `requirements.txt` – Python dependencies
- `schema_validator.py` – validation against the schema
- `README.md` – this file

**Per-site folder:** `birgun.net`, `turkiyegazetesi.com`, `bbc.com`, `dogrulukpayi.com` (add more following the same pattern).

In each site folder (only overrides; common logic lives in `base/`):
- **fetch_html.py** – site fetcher class (inherits `BaseHtmlFetcher`, overrides `extract_article_only()` if needed).
- **parser.py** – site parser class (inherits `BaseParser`, implements `parse_article_html()`).
- **ai_extract.py** – site AI extractor (inherits `BaseAiExtractor`, implements `build_prompt()`).
- **run_article.py** – site runner (inherits `BaseRunner`, optional help/description overrides).
- **HTML_files/** – saved HTML files (filename = article slug).
- **Parsed_files/** – JSON from the parser (article slug).
- **AI_files/** – JSON from Claude (article slug).

## Example for birgun.net (refactored with base classes)

`birgun.net` is refactored to use the base classes; other sites keep their current scripts.

```bash
cd birgun.net
python fetch_html.py "https://www.birgun.net/makale/kultur-sanat-ajandasi-691769"
python parser.py
python ai_extract.py HTML_files/kultur-sanat-ajandasi-691769.html
# Or one command:
python run_article.py "https://www.birgun.net/makale/..." --parse --ai
```

For other sites (`turkiyegazetesi.com`, `bbc.com`, `dogrulukpayi.com`), fetch and parser are templates – adapt selectors and URL logic per domain. The AI script is ready to use.

## One-command for turkiyegazetesi.com

From the `turkiyegazetesi.com` folder you can pass just the URL; flags add parsing and/or AI JSON:

```bash
cd turkiyegazetesi.com
py run_article.py "https://www.turkiyegazetesi.com.tr/ekonomi/..."
py run_article.py "https://..." --parse          # + parse to Parsed_files/
py run_article.py "https://..." --ai             # + JSON via Anthropic to AI_files/
py run_article.py "https://..." --parse --ai     # fetch + parse + AI
```

## One-command for dogrulukpayi.com

Same flow for doğrulukpayi.com: fetch keeps only `section.r-section.r-section-withcard` and stops before the logo (path.LogoCheck).

```bash
cd dogrulukpayi.com
py run_article.py "https://www.dogrulukpayi.com/dogrulama/..."
py run_article.py "https://..." --parse
py run_article.py "https://..." --ai
py run_article.py "https://..." --parse --ai
```
