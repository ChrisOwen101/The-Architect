from __future__ import annotations
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup
from . import command


@command(
    name="scrape",
    description="Fetches the HTML at a given URL, extracts readable text, title, metadata, and links, then returns the cleaned content along with a concise summary and key insights.",
    params=[
        ("url", str, "The URL to scrape", True)
    ]
)
async def scrape_handler(url: str, matrix_context: Optional[dict] = None) -> Optional[str]:
    """
    Scrapes a URL and extracts readable content, metadata, and links.

    Args:
        url: The URL to scrape
        matrix_context: Optional Matrix event context

    Returns:
        A formatted string with title, metadata, extracted text, links, and summary,
        or an error message if scraping fails.
    """
    # Validate URL
    if not url or not url.strip():
        return "Error: URL cannot be empty"

    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        # Fetch the URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return f"Error: HTTP {response.status} - Could not fetch URL"

                html = await response.text()

        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for script in soup(['script', 'style', 'nav', 'footer', 'header']):
            script.decompose()

        # Extract title
        title = soup.title.string.strip() if soup.title else "No title"

        # Extract metadata
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            meta_desc = soup.find('meta', property='og:description')
        if meta_desc:
            description = meta_desc.get('content', '').strip()

        # Extract main text content
        text_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
        text_lines = []
        for elem in text_elements:
            text = elem.get_text().strip()
            if text:
                text_lines.append(text)

        full_text = '\n'.join(text_lines)

        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            link_text = link.get_text().strip()
            if href and href.startswith('http') and link_text:
                links.append(f"{link_text}: {href}")

        # Limit links to top 10
        links = links[:10]

        # Generate summary and insights
        word_count = len(full_text.split())
        summary_parts = []

        if description:
            summary_parts.append(f"Description: {description[:200]}")

        if word_count > 0:
            # Extract first few sentences as summary
            sentences = full_text.split('.')[:3]
            brief_summary = '. '.join(s.strip() for s in sentences if s.strip())
            if brief_summary and not description:
                summary_parts.append(f"Summary: {brief_summary[:200]}...")

        summary_parts.append(f"Word count: {word_count}")
        summary_parts.append(f"Links found: {len(links)}")

        # Build response (keeping under 4000 chars)
        response_parts = [
            f"**Title:** {title}\n",
            f"**URL:** {url}\n",
            f"\n**Summary:**\n{chr(10).join(summary_parts)}\n"
        ]

        # Add a snippet of the content
        if full_text:
            snippet = full_text[:1000]
            if len(full_text) > 1000:
                snippet += "..."
            response_parts.append(f"\n**Content Preview:**\n{snippet}\n")

        # Add links
        if links:
            response_parts.append(f"\n**Key Links:**")
            for link in links[:5]:  # Limit to 5 links
                response_parts.append(f"- {link}")

        response = '\n'.join(response_parts)

        # Ensure response is under 4000 characters
        if len(response) > 4000:
            response = response[:3997] + "..."

        return response

    except aiohttp.ClientError as e:
        return f"Error: Network error - {str(e)}"
    except Exception as e:
        return f"Error: Failed to scrape URL - {str(e)}"
