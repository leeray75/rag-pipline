"""Discover documentation links from a seed URL using BS4 + LLM fallback."""

import json
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import structlog

logger = structlog.get_logger()


@dataclass
class DiscoveredLink:
    """A discovered documentation page link."""
    href: str
    title: str
    source: str  # "css_selector" or "llm_extraction"


def extract_links_with_selectors(
    html: str,
    base_url: str,
    nav_selectors: list[str] | None = None,
) -> list[DiscoveredLink]:
    """Extract documentation links using CSS selectors on nav/sidebar elements."""
    if nav_selectors is None:
        nav_selectors = [
            "nav a",
            "[class*='sidebar'] a",
            "[class*='nav'] a",
            "[class*='menu'] a",
            "[class*='toc'] a",
            "[role='navigation'] a",
            "aside a",
        ]

    soup = BeautifulSoup(html, "html.parser")
    parsed_base = urlparse(base_url)
    seen_urls: set[str] = set()
    links: list[DiscoveredLink] = []

    for selector in nav_selectors:
        for anchor in soup.select(selector):
            href = anchor.get("href")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            absolute_url = urljoin(base_url, href)
            parsed = urlparse(absolute_url)

            # Filter: same origin only
            if parsed.netloc != parsed_base.netloc:
                continue

            # Deduplicate
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            title = anchor.get_text(strip=True) or parsed.path.split("/")[-1]
            links.append(DiscoveredLink(
                href=clean_url, title=title, source="css_selector",
            ))

    logger.info("css_links_extracted", count=len(links), base_url=base_url)
    return links


async def extract_links_with_llm(
    html: str,
    base_url: str,
) -> list[DiscoveredLink]:
    """Use Claude to extract doc links when CSS selectors fail or find too few.

    IMPORTANT: Requires ANTHROPIC_API_KEY environment variable.
    """
    from langchain_anthropic import ChatAnthropic

    # Trim HTML to nav-relevant sections to save tokens
    soup = BeautifulSoup(html, "html.parser")
    nav_sections = []
    for tag in soup.find_all(["nav", "aside", "header"]):
        nav_sections.append(str(tag)[:5000])

    nav_html = "\n---\n".join(nav_sections) if nav_sections else html[:10000]

    llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=4096, temperature=0)

    prompt = f"""Extract all documentation page links from this HTML navigation.
The base URL is: {base_url}

Return ONLY a JSON array of objects with "href" and "title" keys.
Only include links that are part of the same documentation site.
Do not include external links, social media, or non-documentation pages.

HTML:
{nav_html}

JSON array:"""

    response = await llm.ainvoke(prompt)
    content = response.content

    try:
        # Parse JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        raw_links = json.loads(content.strip())
        links = []
        for item in raw_links:
            href = urljoin(base_url, item.get("href", ""))
            title = item.get("title", "")
            links.append(DiscoveredLink(href=href, title=title, source="llm_extraction"))

        logger.info("llm_links_extracted", count=len(links), base_url=base_url)
        return links
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("llm_link_extraction_failed", error=str(e))
        return []


async def discover_doc_links(
    html: str,
    base_url: str,
    min_links_threshold: int = 3,
) -> list[DiscoveredLink]:
    """Discover documentation links. Uses CSS selectors first, LLM fallback if too few found."""
    links = extract_links_with_selectors(html, base_url)

    if len(links) < min_links_threshold:
        logger.info("too_few_css_links_trying_llm", css_count=len(links))
        llm_links = await extract_links_with_llm(html, base_url)
        # Merge, preferring CSS-extracted links
        seen = {link.href for link in links}
        for link in llm_links:
            if link.href not in seen:
                links.append(link)
                seen.add(link.href)

    return links
