"""Crawlers package for URL fetching and link discovery."""

from .fetcher import (
    FetchMode,
    FetchResult,
    fetch_url,
    fetch_static,
    fetch_with_browser,
)
from .link_discovery import (
    DiscoveredLink,
    discover_doc_links,
    extract_links_with_selectors,
    extract_links_with_llm,
)

__all__ = [
    "FetchMode",
    "FetchResult",
    "fetch_url",
    "fetch_static",
    "fetch_with_browser",
    "DiscoveredLink",
    "discover_doc_links",
    "extract_links_with_selectors",
    "extract_links_with_llm",
]
