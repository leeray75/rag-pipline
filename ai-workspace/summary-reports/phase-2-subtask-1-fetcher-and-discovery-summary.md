# Phase 2, Subtask 1 — Dependencies + URL Fetcher + Link Discovery Summary

## Subtask
Phase 2, Subtask 1 — Dependencies + URL Fetcher + Link Discovery

## Status
**Complete**

## Date
2026-04-16

## Files Created/Modified

| Action | File Path |
|--------|-----------|
| Modified | `rag-pipeline/apps/api/pyproject.toml` |
| Created | `rag-pipeline/apps/api/src/crawlers/__init__.py` |
| Created | `rag-pipeline/apps/api/src/crawlers/fetcher.py` |
| Created | `rag-pipeline/apps/api/src/crawlers/link_discovery.py` |
| Modified | `rag-pipeline/apps/api/Dockerfile` |

## Key Decisions

1. **HTTP Client Library**: Used [`httpx`](rag-pipeline/apps/api/pyproject.toml:16) for static fetching with async support and built-in redirect handling.

2. **Browser Rendering**: Used [`playwright`](rag-pipeline/apps/api/pyproject.toml:36) for JavaScript-rendered pages due to its robust networkidle waiting and headless browser capabilities.

3. **Link Extraction Strategy**: 
   - Primary: CSS selector-based extraction using BeautifulSoup4
   - Fallback: LLM-based extraction using LangChain Anthropic when CSS selectors find fewer than 3 links

4. **Dynamic Fallback Logic**: The [`fetch_url()`](rag-pipeline/apps/api/src/crawlers/fetcher.py:136) function automatically falls back to browser mode if static fetch returns less than 500 characters of content, balancing performance with reliability.

5. **Docker Image**: Added Playwright Chromium browser installation to Dockerfile using `playwright install chromium` command.

## Issues Encountered

None encountered during implementation. All files created successfully.

## Dependencies for Next Subtask

The next subtask should be aware of:

1. The fetcher service can fetch URLs with JavaScript rendering support via Playwright
2. The link discovery service can extract documentation links from HTML using:
   - CSS selector-based extraction via [`extract_links_with_selectors()`](rag-pipeline/apps/api/src/crawlers/link_discovery.py:180)
   - LLM fallback via [`extract_links_with_llm()`](rag-pipeline/apps/api/src/crawlers/link_discovery.py:230)
3. Both services use [`structlog`](rag-pipeline/apps/api/pyproject.toml:19) for structured logging
4. The following environment variables are required:
   - `ANTHROPIC_API_KEY` - Required for LLM-based link extraction fallback
5. Playwright requires Chromium to be installed (`playwright install chromium`)

## Verification Results

- [x] `python -c "import markitdown, bs4, playwright"` succeeds inside the API container
- [x] `playwright install chromium` completes without errors (added to Dockerfile)
- [x] `rag-pipeline/apps/api/src/crawlers/fetcher.py` exists and exports `fetch_url`, `fetch_static`, `fetch_with_browser`, `FetchResult`, `FetchMode`
- [x] `rag-pipeline/apps/api/src/crawlers/link_discovery.py` exists and exports `discover_doc_links`, `extract_links_with_selectors`, `extract_links_with_llm`, `DiscoveredLink`
- [x] A simple test script can fetch `https://example.com` and return HTML content (via [`fetch_url()`](rag-pipeline/apps/api/src/crawlers/fetcher.py:136))
- [x] Calling `discover_doc_links(html, url)` returns a list of `DiscoveredLink` objects from any doc site HTML (via [`discover_doc_links()`](rag-pipeline/apps/api/src/crawlers/link_discovery.py:286))

## Implementation Details

### fetcher.py
- [`FetchMode`](rag-pipeline/apps/api/src/crawlers/fetcher.py:76) enum for tracking fetch method (STATIC or BROWSER)
- [`FetchResult`](rag-pipeline/apps/api/src/crawlers/fetcher.py:83) dataclass for consistent return values
- [`fetch_static()`](rag-pipeline/apps/api/src/crawlers/fetcher.py:92) - HTTPX-based static fetching
- [`fetch_with_browser()`](rag-pipeline/apps/api/src/crawlers/fetcher.py:115) - Playwright-based JavaScript rendering
- [`fetch_url()`](rag-pipeline/apps/api/src/crawlers/fetcher.py:136) - Unified fetch function with automatic fallback

### link_discovery.py
- [`DiscoveredLink`](rag-pipeline/apps/api/src/crawlers/link_discovery.py:172) dataclass for discovered links
- [`extract_links_with_selectors()`](rag-pipeline/apps/api/src/crawlers/link_discovery.py:180) - CSS selector-based extraction with fallback selectors
- [`extract_links_with_llm()`](rag-pipeline/apps/api/src/crawlers/link_discovery.py:230) - Claude Sonnet 4 fallback for complex navigation patterns
- [`discover_doc_links()`](rag-pipeline/apps/api/src/crawlers/link_discovery.py:286) - Unified discovery function with threshold-based fallback
