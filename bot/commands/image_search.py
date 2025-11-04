from __future__ import annotations
from typing import Optional
from . import command

@command(
    name="image_search",
    description="search for an image based on a search term",
    pattern=r"^!image_search\s*(.*)$"
)
async def image_search_handler(body: str) -> Optional[str]:
    """
    Search for an image based on a search term.

    Usage: !image_search <search term>

    Args:
        body: The full message text containing the command and search term

    Returns:
        A response string with image search results, or None if no search term provided
    """
    import re

    # Extract search term from the command
    match = re.match(r"^!image_search\s*(.*)$", body.strip())
    if not match:
        return None

    search_term = match.group(1).strip()

    if not search_term:
        return "Please provide a search term. Usage: !image_search <search term>"

    # For now, return a simulated response with a search URL
    # In a real implementation, this would integrate with an image search API
    search_url = f"https://www.google.com/search?tbm=isch&q={search_term.replace(' ', '+')}"

    response = f"🔍 Image search results for: **{search_term}**\n\n"
    response += f"Search URL: {search_url}\n\n"
    response += "Note: This is a basic implementation. For actual image results, "
    response += "integration with an image search API (like Unsplash, Pexels, or Google Custom Search) would be needed."

    return response
