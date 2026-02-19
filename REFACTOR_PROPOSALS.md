# Proposals: Further Extraction into Base (do not auto-apply)

After migrating all four sites (birgun.net, bbc.com, dogrulukpayi.com, turkiyegazetesi.com) to use `BaseHtmlFetcher`, `BaseParser`, `BaseAiExtractor`, and `BaseRunner`, the following duplicated logic remains. These are **proposals only**; apply incrementally and only where the benefit justifies the change.

---

## 1. Shared parser helpers (base or shared module)

**Where:** birgun.net/parser.py, bbc.com/parser.py (and partly dogrulukpayi, turkiyegazetesi).

**Duplicated:**

- **`_decode_html(raw: bytes) -> str`** — identical in birgun and bbc (UTF-16 BOM check, else utf-8).
- **`_get_meta_content(soup, name, attr="name")`** — same in birgun and bbc.
- **`_resolve_url(url, base) -> str | None`** — same in birgun and bbc (//, /, http); dogrulukpayi/turkiyegazetesi use `urljoin` only.
- **`_schema_props(**kwargs)`** — same in birgun and bbc (drop None values).
- **HTML-to-markdown for inline elements** — birgun/bbc have `_html_to_markdown_text(el)` (walk descendants, `<a>`→`[text](url)`, `<strong>`→`**text**`, `<em>`→`*text*`). dogrulukpayi/turkiyegazetesi have `_inline_to_markdown(tag)` (recursive over children). Logic is similar; API differs slightly.

**Proposal:**

- Add `base/parser_utils.py` (or similar) with:
  - `decode_html(raw: bytes) -> str`
  - `get_meta_content(soup, name, attr="name") -> str | None`
  - `resolve_url(url, base) -> str | None`
  - `schema_props(**kwargs) -> dict`
  - optionally a single `html_to_markdown_text(el)` that both “descendants” and “children” styles can use or wrap.
- Birgun and BBC parsers import and use these; dogrulukpayi/turkiyegazetesi adopt only where it simplifies (e.g. `resolve_url` if they need full-URL handling).

**Risk:** Low. Keep site-specific parsing logic (metadata extraction, skip blocks, component rules) in site folders.

---

## 2. Common parsing patterns (component building)

**Where:** All four parsers output the same schema: `heading`, `paragraph`, `image`, `citation`, `list`, `table`, `horizontal_ruler`, (optional) `code_block`.

**Duplicated:**

- Turning a `<table>` into `{"type": "table", "properties": {"headers": [...], "rows": [...]}}` (thead/tr/td).
- Turning `<ul>`/`<ol>` into `{"type": "list", "properties": {"items": [{indent, bullet, content}, ...]}}`.
- Turning `<blockquote>` into `{"type": "citation", "properties": {"citation_text": ...}}`.
- Heading level from tag name (`int(tag.name[1])`).
- Image: url, caption from figcaption, description from alt, optional link_url from parent `<a>`.

**Proposal:**

- Add in `base/parser_utils.py` (or a new `base/component_builders.py`) small helpers, e.g.:
  - `table_to_component(tag, base_url, text_fn)` → dict
  - `list_to_component(tag, text_fn)` → dict
  - `blockquote_to_citation(tag, text_fn)` → dict
  - `image_properties(tag, base_url, text_fn)` → dict for `properties`
- Sites still decide *which* tags to visit and how to get text (e.g. `_html_to_markdown_text` vs `_inline_to_markdown`); they just call these helpers to build the component dict. This reduces copy-paste and keeps schema shape in one place.

**Risk:** Medium. Selectors and “skip” rules stay site-specific; only the “tag → component dict” step is shared.

---

## 3. Fetcher: minimal head builder

**Where:** birgun.net, dogrulukpayi.com, turkiyegazetesi.com (fetch_html) all build a minimal `<head>` with charset + a list of meta names/properties.

**Duplicated:**

- `_build_minimal_head(soup)` — same idea: loop over `<head>` metas, keep those whose `name` or `property` is in a whitelist, optionally add JSON-LD date injection (dogrulukpayi).

**Proposal:**

- Add `BaseHtmlFetcher.build_minimal_head(soup, meta_names=(), meta_properties=(), json_ld_dates=False)` (or a standalone helper in `base/_utils.py` / `base/fetcher_utils.py`) that takes whitelists and returns the head string. Each site passes its own `_META_NAMES` and `_META_PROPERTIES`. dogrulukpayi can pass `json_ld_dates=True` and the helper can encapsulate the JSON-LD Article date extraction.

**Risk:** Low. Sites keep their own meta whitelists and any extra head logic.

---

## 4. AI: reusable prompt fragments and post-process

**Where:** All four ai_extract.py scripts.

**Duplicated:**

- **Prompt structure:** “Extract this [site] article HTML… STRICT RULES: Authors… Categories… Tags… Title… document_date… Body… Output: metadata + components.”
- **Full-URL rule:** “url = FULL absolute URL (https://...), never relative” (and birgun already has a post-process that forces full URLs).
- **`_strip_nulls_for_schema(obj)`** — identical in dogrulukpayi and turkiyegazetesi; removes keys with `None` values recursively.

**Proposal:**

- **Prompt fragments:** Add in `base` (e.g. `base/ai_prompt_fragments.py`) optional constants or small functions:
  - e.g. `STRICT_URL_RULE = "Every url field must be a full absolute URL (https://...), never a relative path."`
  - e.g. `body_copy_rule(scope_description: str)` → “Copy text EXACTLY from the HTML in the SAME order. … Do NOT paraphrase. …” so each site passes its scope (e.g. “div.article-scope > article”).
- Sites keep their full `build_prompt()` but can compose from these fragments to avoid drift and make “all sites use full URLs” easier to enforce.
- **Post-process:** Add `base/base_ai_extractor.strip_nulls_for_schema(obj)` and call it from a default `post_process_output` (or from a mixin). Sites that need it (dogrulukpayi, turkiyegazetesi) use it; birgun can keep its URL-only post-process and optionally call `strip_nulls` as well.

**Risk:** Low. Prompts stay site-owned; fragments are optional and additive.

---

## 5. What to leave in site folders

- **Selectors and structure:** e.g. `div.contentdetail`, `section.r-section`, `div.article-scope`, `article`, BBC’s `story-body` / `data-component`.
- **Skip rules:** e.g. `_is_inside_skip_block`, BBC skip patterns, birgun’s “Sıradaki Haber”, dogrulukpayi’s LogoCheck.
- **Metadata extraction:** where title/date/author/categories/tags come from (meta, JSON-LD, byline, script config) is site-specific.
- **AI prompt text:** site-specific rules (e.g. “Editör”, “İlgili Konular”, “path.LogoCheck”) should remain in each site’s `build_prompt()`.

---

## Summary

| Area              | Proposal                                      | Risk   |
|-------------------|-----------------------------------------------|--------|
| Parser helpers    | `base/parser_utils.py`: decode_html, get_meta_content, resolve_url, schema_props, optional html_to_markdown | Low    |
| Component building| Helpers for table/list/citation/image dicts   | Medium |
| Fetcher head      | Shared `build_minimal_head(soup, names, props, json_ld_dates?)` | Low    |
| AI fragments      | Optional URL rule + body rule + strip_nulls    | Low    |

Apply one area at a time, run existing flows (fetch → parse → AI) per site, and keep all site-specific behavior in site folders.
