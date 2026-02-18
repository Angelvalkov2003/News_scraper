# News Scraper

## Структура

**Корен (главна папка):**
- `.env` – API ключове (ANTHROPIC_API_KEY и др.)
- `scraped_article_json_schema.json` – обща схема за всички изходи
- `recent_posts_turkish_news_websites.json` – списък с постове/URL-и
- `requirements.txt` – Python зависимости
- `schema_validator.py` – валидация спрямо схемата
- `README.md` – този файл

**Папка за всеки уебсайт:** `birgun.net`, `turkiyegazetesi.com`, `bbc.com`, `dogrulukpayi.com` (добавяш още по същия модел).

Във всяка такава папка:
- **fetch_html.py** – взима HTML от уебсайта, записва в `HTML_files/` с име на статията (slug).
- **parser.py** – парсва HTML във формат `scraped_article_json_schema.json`, записва в `Parsed_files/` с име на статията.
- **ai_extract.py** – изпраща HTML към Claude API, записва в `AI_files/` в същия формат, с име на статията.
- **HTML_files/** – съхранени HTML файлове (име на файла = име на статията).
- **Parsed_files/** – JSON от парсъра (име на статията).
- **AI_files/** – JSON от Claude (име на статията).

## Пример за birgun.net

```bash
cd birgun.net
python fetch_html.py "https://www.birgun.net/makale/kultur-sanat-ajandasi-691769"
python parser.py
python ai_extract.py HTML_files/kultur-sanat-ajandasi-691769.html
```

За останалите сайтове (`turkiyegazetesi.com`, `bbc.com`, `dogrulukpayi.com`) fetch и parser са шаблон – адаптирай селекторите и URL логиката за всеки домейн. AI скриптът е готов за ползване.

## Една команда за turkiyegazetesi.com

От папката `turkiyegazetesi.com` можеш да подадеш само линк; с флагове се добавят парсване и/или AI JSON:

```bash
cd turkiyegazetesi.com
py run_article.py "https://www.turkiyegazetesi.com.tr/ekonomi/..."
py run_article.py "https://..." --parse          # + парсване в Parsed_files/
py run_article.py "https://..." --ai             # + JSON през Anthropic в AI_files/
py run_article.py "https://..." --parse --ai     # fetch + парсване + AI
```

## Една команда за dogrulukpayi.com

Същата логика за doğrulukpayi.com: fetch взима само `section.r-section.r-section-withcard` и спира преди логото (path.LogoCheck).

```bash
cd dogrulukpayi.com
py run_article.py "https://www.dogrulukpayi.com/dogrulama/..."
py run_article.py "https://..." --parse
py run_article.py "https://..." --ai
py run_article.py "https://..." --parse --ai
```
