"""
Една команда: подаваш URL → fetch HTML; с флагове пускаш парсър и/или AI JSON.

Употреба:
  py run_article.py <URL>              → само fetch HTML в HTML_files/
  py run_article.py <URL> --parse      → fetch HTML + парсване в Parsed_files/
  py run_article.py <URL> --ai        → fetch HTML + генериране на JSON чрез Anthropic в AI_files/
  py run_article.py <URL> --parse --ai → fetch + парсване + AI JSON
"""

import sys
from pathlib import Path

# Allow importing base package from project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from base.base_runner import BaseRunner


class BirgunRunner(BaseRunner):
    """Birgun.net runner: URL -> fetch; --parse / --ai for parser and AI."""

    def __init__(self):
        super().__init__(site_dir=Path(__file__).resolve().parent)

    def get_description(self) -> str:
        return "Fetch статия по URL (birgun.net); с --parse парсване до JSON, с --ai генериране на JSON чрез Anthropic API."

    def get_url_help(self) -> str:
        return "Пълен URL на статия (напр. https://www.birgun.net/makale/...)"


if __name__ == "__main__":
    BirgunRunner().main()
