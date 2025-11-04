from __future__ import annotations
from typing import Optional
from . import command
import re
import aiohttp
from html.parser import HTMLParser


class TitleExtractor(HTMLParser):
    """HTML parser to extract the title element."""

    def __init__(self):
        super().__init__()
        self.title = None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title = data.strip()


@command(
    name="scrape",
    description="Given a url, scrape its html and extract the title element from it",
    pattern=r"^!scrape\s*(.*)$"
)
async def scrape_handler(body: str) -> Optional[str]:
    """
    Scrape a URL and extract its HTML title element.

    Usage: !scrape <url>

    Args:
        body: The full message text containing the command and URL

    Returns:
        The extracted title or an error message
    """
    # Extract the URL from the command
    match = re.match(r"^!scrape\s+(.+)$", body.strip())
    if not match:
        return "Usage: !scrape <url>"

    url = match.group(1).strip()

    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        return "Error: URL must start with http:// or https://"

    try:
        # Fetch the URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return f"Error: HTTP {response.status} - {response.reason}"

                # Read the HTML content
                html_content = await response.text()

                # Extract the title
                parser = TitleExtractor()
                parser.feed(html_content)

                if parser.title:
                    # Truncate if too long
                    title = parser.title[:3900] if len(parser.title) > 3900 else parser.title
                    return f"Title: {title}"
                else:
                    return "No title found in the HTML document"

    except aiohttp.ClientError as e:
        return f"Error fetching URL: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"
