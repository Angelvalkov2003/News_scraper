# Parsed output за birgun.net

Тук се записват резултатите от парсера върху HTML файловете от **ParsedHTMLs/birgun.net/**.

Всеки уебсайт има **лични файлове**: за всяка статия един HTML в `ParsedHTMLs/` и един JSON тук във формата на **scraped_article_json_schema.json** (metadata + components).

- **По един JSON на статия** (препоръчително): `article.json`, `siginak-691861.json`, … — съответстват 1:1 на файловете в ParsedHTMLs/birgun.net/ (същото име без .html).
- **parsed_articles.json** (по избор): един масив от всички статии; може да се генерира отделно.

Генериране на лични JSON файлове (един на HTML):
```bash
python parse_article.py --per-file --validate -o Schemas/birgun.net/parsed ParsedHTMLs/birgun.net/*.html
```

Един общ файл:
```bash
python parse_article.py ParsedHTMLs/birgun.net/*.html -o Schemas/birgun.net/parsed/parsed_articles.json --validate
```
