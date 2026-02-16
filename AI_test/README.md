# AI_test – изход в конзолата и копиране в Cursor

## Защо не мога да принтирам кирилица и да го копирам в Cursor?

Под Windows терминалът по подразбиране не използва UTF-8. Затова при `print("Записано: ...")` може да получиш грешка или „каляска“ и да не можеш да копираш текста в Cursor.

## Как да го оправиш

### 1. В този скрипт

`run_claude_extract.py` вече задава изхода на конзолата в UTF-8 в началото. Ако пак има проблем, пусни терминала с UTF-8 (виж по-долу).

### 2. В Cursor / VS Code

В долния терминал обикновено вече е UTF-8. Ако не е:
- Отвори Command Palette (Ctrl+Shift+P) → **Terminal: Select Default Profile** → избери **Windows PowerShell** или **Command Prompt** и след това в настройките на профила потърси **encoding** или задай в `settings.json`:
  ```json
  "terminal.integrated.shellArgs.windows": ["-NoExit", "-Command", "chcp 65001"]
  ```

### 3. В обикновен PowerShell (извън Cursor)

Преди да пуснеш скрипта:
```powershell
chcp 65001
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```
След това принтираният текст ще е четим и ще можеш да го копираш в Cursor.

### 4. Запис във файл вместо принтиране

Ако искаш изхода директно във файл (и после да го отвориш в Cursor):
```powershell
python AI_test/run_claude_extract.py ParsedHTMLs/birgun.net/article.html 2>&1 | Out-File -Encoding utf8 AI_test/log.txt
```
Съдържанието ще е в `AI_test/log.txt` – отвори го в Cursor и копирай оттам.
