from __future__ import annotations
from typing import Optional
from . import command
import os
import aiohttp
import re


@command(
    name="gif",
    description="return a giphy gif URL for the given search phrase",
    pattern=r"^!gif\s*(.*)$"
)
async def gif_handler(body: str) -> Optional[str]:
    """
    Return a Giphy GIF URL for the given search phrase.
    
    Usage: !gif <search phrase>
    
    Requires GIPHY_API_KEY environment variable to be set.
    """
    match = re.match(r"^!gif\s*(.*)$", body.strip())
    if not match:
        return None
    
    search_phrase = match.group(1).strip()
    
    if not search_phrase:
        return "Please provide a search phrase. Usage: !gif <search phrase>"
    
    api_key = os.environ.get("GIPHY_API_KEY")
    if not api_key:
        return "Error: GIPHY_API_KEY environment variable not set"
    
    try:
        url = "https://api.giphy.com/v1/gifs/search"
        params = {
            "api_key": api_key,
            "q": search_phrase,
            "limit": 1,
            "rating": "g"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return f"Error: Giphy API returned status {response.status}"
                
                data = await response.json()
                
                if not data.get("data") or len(data["data"]) == 0:
                    return f"No GIFs found for '{search_phrase}'"
                
                gif_url = data["data"][0]["images"]["original"]["url"]
                return gif_url
    
    except aiohttp.ClientError as e:
        return f"Error connecting to Giphy API: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"