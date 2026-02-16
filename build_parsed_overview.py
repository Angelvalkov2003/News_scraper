"""
Build parsed_overview.json and parsed_overview.md from all sites that have
parsed output. Lets you see each site's data in the schema (titles, dates, authors).
No AI. Run from project root.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SCHEMAS = PROJECT_ROOT / "Schemas"
SITES_JSON = SCHEMAS / "sites.json"


def get_title(doc: dict) -> str:
    """First h1 heading text from components."""
    for c in doc.get("components", {}).get("components", []):
        if c.get("type") == "heading" and c.get("properties", {}).get("level") == 1:
            return (c.get("properties") or {}).get("text", "").strip()
    return "—"


def get_author(doc: dict) -> str:
    """First author name from metadata."""
    authors = doc.get("metadata", {}).get("authors") or []
    if authors and authors[0].get("name"):
        return authors[0]["name"].strip()
    return "—"


def get_category(doc: dict) -> str:
    """First category/section name."""
    cats = doc.get("metadata", {}).get("categories") or []
    if cats and cats[0].get("name"):
        return cats[0]["name"].strip()
    return "—"


def load_parsed_articles(schema_dir: Path) -> list[dict]:
    """Load articles: from parsed_articles.json if present, else from parsed/*.json (one doc per file)."""
    parsed_dir = schema_dir / "parsed"
    single_file = parsed_dir / "parsed_articles.json"
    if single_file.exists():
        with open(single_file, encoding="utf-8") as f:
            articles = json.load(f)
        return articles if isinstance(articles, list) else []
    articles = []
    for path in sorted(parsed_dir.glob("*.json")):
        if path.name.startswith("parsed_overview"):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc, dict) and ("metadata" in doc or "components" in doc):
                articles.append(doc)
        except (json.JSONDecodeError, OSError):
            continue
    return articles


def build_overview() -> dict:
    with open(SITES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    sites = data.get("sites", [])
    overview = {"canonical_schema": data.get("canonical_output_schema"), "sites": []}
    for site in sites:
        site_id = site.get("id", "")
        schema_dir = PROJECT_ROOT / site.get("schema_dir", "")
        parsed_dir = schema_dir / "parsed"
        if not parsed_dir.exists():
            overview["sites"].append({
                "id": site_id,
                "name": site.get("name", site_id),
                "parsed_path": str(parsed_dir.relative_to(PROJECT_ROOT)),
                "article_count": 0,
                "articles": [],
            })
            continue
        articles = load_parsed_articles(schema_dir)
        articles_summary = []
        for i, doc in enumerate(articles):
            articles_summary.append({
                "index": i,
                "title": get_title(doc),
                "document_date": (doc.get("metadata") or {}).get("document_date") or "—",
                "author": get_author(doc),
                "category": get_category(doc),
                "component_count": len((doc.get("components") or {}).get("components") or []),
            })
        overview["sites"].append({
            "id": site_id,
            "name": site.get("name", site_id),
            "parsed_path": str(parsed_dir.relative_to(PROJECT_ROOT)),
            "article_count": len(articles),
            "articles": articles_summary,
        })
    return overview


def main() -> None:
    overview = build_overview()
    out_json = SCHEMAS / "parsed_overview.json"
    out_md = SCHEMAS / "parsed_overview.md"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)
    lines = [
        "# Преглед на парснати данни по схема",
        "",
        "Генерирано от `build_parsed_overview.py`. Показва данните от всички уебсайтове с HTML, върнати в схемата (metadata + components).",
        "",
        "| Сайт | Брой статии | Файл |",
        "|------|-------------|------|",
    ]
    for s in overview["sites"]:
        lines.append(f"| {s['name']} (`{s['id']}`) | {s['article_count']} | `{s['parsed_path']}` |")
    lines.append("")
    for s in overview["sites"]:
        if s["article_count"] == 0:
            continue
        lines.append(f"## {s['name']} ({s['id']})")
        lines.append("")
        lines.append("| # | Заглавие | Дата | Автор | Категория | Компоненти |")
        lines.append("|---|----------|------|-------|-----------|------------|")
        for a in s["articles"]:
            title_short = (a["title"][:50] + "…") if len(a["title"]) > 50 else a["title"]
            title_cell = title_short.replace("|", " / ")
            lines.append(f"| {a['index']+1} | {title_cell} | {a['document_date']} | {a['author']} | {a['category']} | {a['component_count']} |")
        lines.append("")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
