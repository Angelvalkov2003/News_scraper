# News Scraper

## Structure

**Root:**
- `.env` – API keys (ANTHROPIC_API_KEY, etc.)
- `scraped_article_json_schema.json` – shared schema for all outputs
- `recent_posts_turkish_news_websites.json` – list of posts/URLs
- `requirements.txt` – Python dependencies
- `schema_validator.py` – validation against the schema
- `README.md` – this file

**Per-site folder:** `birgun.net`, `turkiyegazetesi.com`, `bbc.com`, `dogrulukpayi.com` (add more following the same pattern).

In each site folder:
- **fetch_html.py** – fetches HTML from the site, saves to `HTML_files/` with the article slug as filename.
- **parser.py** – parses HTML into `scraped_article_json_schema.json` format, saves to `Parsed_files/` with the article slug.
- **ai_extract.py** – sends HTML to Claude API, saves to `AI_files/` in the same format, with the article slug.
- **HTML_files/** – saved HTML files (filename = article slug).
- **Parsed_files/** – JSON from the parser (article slug).
- **AI_files/** – JSON from Claude (article slug).

## Example for birgun.net

```bash
cd birgun.net
python fetch_html.py "https://www.birgun.net/makale/kultur-sanat-ajandasi-691769"
python parser.py
python ai_extract.py HTML_files/kultur-sanat-ajandasi-691769.html
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
