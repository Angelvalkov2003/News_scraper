"""
Base classes for news site scrapers.
Website-specific modules inherit and override only what is needed.
"""

from base.base_fetcher import BaseHtmlFetcher
from base.base_parser import BaseParser
from base.base_ai_extractor import BaseAiExtractor
from base.base_runner import BaseRunner

__all__ = [
    "BaseHtmlFetcher",
    "BaseParser",
    "BaseAiExtractor",
    "BaseRunner",
]
