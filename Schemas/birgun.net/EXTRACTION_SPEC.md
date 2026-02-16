# Birgun.net – формална спецификация за извличане

## 1. Metadata (head) – extraction rules

| Поле           | Source   | Selector / източник                    | Attribute   | Required | Fallback |
|----------------|----------|----------------------------------------|-------------|----------|----------|
| title          | head     | `meta[property="og:title"]`            | content     | yes      | `<title>` text (strip) |
| published_at   | head     | `meta[name="datePublished"]`           | content     | yes      | от `meta[name="ptime"]` → ISO 8601 (YYYYMMDDHHmmss → YYYY-MM-DDTHH:mm:ss+03:00) |
| modified_at    | head     | `meta[name="dateModified"]`            | content     | no       | null |
| author         | head     | `meta[name="articleAuthor"]`          | content     | no       | null |
| section        | head     | `meta[name="articleSection"]`          | content     | no       | null |
| keywords       | head     | `meta[name="keywords"]`               | content     | no       | null; ако има – split по запетая, trim на всеки елемент |

- Всички стойности се нормализират: trim на whitespace; празни низове след trim → null (или пропускане при optional).
- `published_at` и `modified_at` трябва да са валиден ISO 8601 (format date-time).

---

## 2. Body – root container и allowed tags

- **Root container:** първият (единствен) елемент `div` с клас, съдържащ подниза **`contentdetail`** (напр. `div[class*="contentdetail"]`).
- **Traversal:** document order – обхождане на всички потомци в дървото в реда на поява в DOM; за блокове се вземат само елементи от списъка по-долу.
- **Allowed tags за блокове:** `h1`, `h2`, `h3`, `h4`, `h5`, `h6`, `p`, `img`, `blockquote`, `ul`, `ol`, `table`, `hr`. Всеки такъв елемент, който не е вътре в вече обработен родител (напр. `li`, `td`, `th`, `blockquote`), се мапва до един body block.

---

## 3. Body block – extraction rules по тип

### 3.1 Heading (h1–h6)

| Field    | Source        | Selector / източник | Required |
|----------|---------------|----------------------|----------|
| type     | fixed         | `"heading"`          | yes      |
| level    | tag name      | 1–6 от h1–h6         | yes      |
| content  | element text  | text content (inline HTML → plain text или markdown) | yes      |

- Празен content след normalize → блокът се пропуска.

### 3.2 Paragraph (p)

| Field    | Source        | Required |
|----------|----------------|----------|
| type     | `"paragraph"`  | yes      |
| content  | text от `<p>`  | yes      |

- Inline scripts (напр. `googletag.cmd.push(...)`) в текста се премахват преди запазване.
- Празен или само whitespace content → блокът се пропуска.

### 3.3 Image (img)

| Field    | Source        | Selector / attribute | Required |
|----------|----------------|----------------------|----------|
| type     | `"image"`      | —                    | yes      |
| src      | img            | attribute `src`      | yes      |
| alt      | img            | attribute `alt`      | no       |

- **Exclude:** ако `src` съдържа (case-insensitive) някой от: `icon`, `logo`, `x.png`, `x_w`, `facebook`, `whatsapp`, `twitter`, `bluesky`, `telegram`, `linkedin`, `google_news`, `share`, `button`, `abone_banner`, `/assets/images/` → блокът не се добавя (социални икони, реклами, банери).
- `src` се нормализира до абсолютен URL (base URL на страницата).

### 3.4 Blockquote (blockquote)

| Field    | Source          | Required |
|----------|-----------------|----------|
| type     | `"blockquote"`  | yes      |
| content  | text от елемента| yes      |

### 3.5 List (ul / ol)

| Field    | Source        | Required |
|----------|----------------|----------|
| type     | `"list"`       | yes      |
| ordered  | true за `<ol>`, false за `<ul>` | yes |
| items    | масив от текст на всяко `li`    | yes      |

- Празни `li` (само whitespace) се пропускат.
- **Exclude:** списък с един елемент, който изглежда като дата (напр. "11.02.2026 12:53") или съдържа само "Giriş:" / "Güncelleme:" → блокът се пропуска (повторена дата / шум).

### 3.6 Table (table)

| Field    | Source        | Required |
|----------|----------------|----------|
| type     | `"table"`      | yes      |
| headers  | първи ред (th/td) или thead | yes |
| rows     | масив от редове (всеки ред = масив от клетки) | yes |

### 3.7 Horizontal rule (hr)

| Field    | Source              | Required |
|----------|---------------------|----------|
| type     | `"horizontal_rule"` | yes      |

- Няма content/src; само type.

---

## 4. Exclusions и филтри (body)

- **Социални икони:** img с `src` съдържащ (case-insensitive): `icon`, `logo`, `x.png`, `x_w`, `facebook`, `whatsapp`, `twitter`, `bluesky`, `telegram`, `linkedin`, `google_news`, `share`, `button`, `abone_banner`, `/assets/images/`.
- **Реклами / банери:** същият филтър за img; блокове, които са само рекламни контейнери (по id/class), не се обхождат ако са извън contentdetail (контейнерът вече изключва целия лайаут извън contentdetail).
- **Inline scripts в текст:** при извличане на текст от `<p>` (и др.) премахване на поднизове от вида `googletag.cmd.push(...)` и подобни скриптови фрагменти.
- **Повторени дати / Giriş / Güncelleme:** списъци или параграфи, които съдържат само такива редове, се пропускат (или не се добавят като блокове).
- **Дублирани блокове:** при наличие на множество „виртуални“ секции (напр. Content_0, Content_1) да се използва само първата съдържателна секция ИЛИ да се приложи дедупликация по нормализиран content (напр. hash на текста) – всеки уникален блок се добавя само веднъж.

---

## 5. Parser algorithm (стъпки)

1. **Parse HTML → DOM**  
   - Вход: суров HTML (bytes или string).  
   - Декодиране: UTF-8 или UTF-16 (BOM); един низ в паметта.  
   - Парсване с HTML parser → дърво (напр. BeautifulSoup или съответник за избраната среда).

2. **Extract metadata**  
   - Върху корена на DOM намери `<head>`.  
   - За всяко поле от таблицата в §1: приложи selector/attribute, използвай fallback ако няма стойност.  
   - Нормализирай стойностите (trim, празни → null).  
   - Преобразувай `published_at` (и при нужда `modified_at`) до валиден ISO 8601.

3. **Locate contentdetail container**  
   - Намери първия `div` с клас съдържащ `contentdetail`.  
   - Ако няма такъв: опционално fallback на `<article>` или `<main>`; иначе → грешка (няма body).

4. **Traverse nodes (document order)**  
   - Върху контейнера обходи всички потомци в document order.  
   - За всеки елемент от allowed tags (h1–h6, p, img, blockquote, ul, ol, table, hr):  
     - Ако е вътре в вече обработен родител (li, td, th, blockquote) → skip.  
     - Приложи exclusions (§4): img филтър, датови списъци, Giriş/Güncelleme.  
     - Мапни елемента до един body block по правилата в §3.  
     - Ако блокът има празен content (където е приложимо) → skip.  
     - Добави блок в списък `body.blocks`.

5. **Normalize**  
   - Текст: trim, collapse whitespace до един интервал (или според изискванията за markdown).  
   - URL за img: resolve към абсолютен URL с base URL на страницата.  
   - Премахване на остатъчни inline script фрагменти от текстови полета.

6. **Deduplicate**  
   - По избор: дедупликация на блокове по нормализиран content (напр. текст или src за изображения), така че един и същ блок да не се повтаря (напр. при Content_0 / Content_1).

7. **Build output**  
   - Сглоби обект `{ "metadata": { ... }, "body": { "blocks": [ ... ] } }` според article_schema.json в тази папка.

8. **Validate output срещу схемата**  
   - Валидирай с JSON Schema (article_schema.json):  
     - title не е празен.  
     - published_at е валиден ISO 8601 (format date-time).  
     - body.blocks има поне 1 елемент.  
     - Няма блок от тип image с src, съдържащ share/рекламни ключови думи (валидаторът може да проверява филтъра или това да е гарантирано от стъпка 4).  
   - При грешка: върни/логвай грешките и не считай изхода за валиден.

---

## 6. Validation (кратки правила)

- **title:** `metadata.title` съществува и `length ≥ 1` след trim.  
- **published_at:** `metadata.published_at` съществува и отговаря на ISO 8601 (date-time).  
- **body:** `body.blocks` е масив с `length ≥ 1`.  
- **Няма share иконки/реклами в body:** никой блок от тип `image` не има `src`, съдържащ (case-insensitive) поднизовете от списъка с exclusions в §4 (или еквивалентна проверка след филтрите в стъпка 4).

Схемата за структурата на изхода е дефинирана в **article_schema.json** в тази папка.
