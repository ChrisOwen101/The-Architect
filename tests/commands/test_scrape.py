from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bot.commands.scrape import scrape_handler


@pytest.mark.asyncio
async def test_scrape_no_url():
    """Test scrape command with no URL provided."""
    result = await scrape_handler("!scrape")
    assert result == "Usage: !scrape <url>"


@pytest.mark.asyncio
async def test_scrape_no_url_with_whitespace():
    """Test scrape command with only whitespace."""
    result = await scrape_handler("!scrape   ")
    assert result == "Usage: !scrape <url>"


@pytest.mark.asyncio
async def test_scrape_invalid_url_no_protocol():
    """Test scrape command with URL missing http/https protocol."""
    result = await scrape_handler("!scrape example.com")
    assert "Error: URL must start with http:// or https://" in result


@pytest.mark.asyncio
async def test_scrape_success():
    """Test successful scraping of a URL with a title."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page Title</title>
    </head>
    <body>
        <h1>Hello World</h1>
    </body>
    </html>
    """

    # Mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=html_content)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Mock session
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler("!scrape https://example.com")
        assert result == "Title: Test Page Title"


@pytest.mark.asyncio
async def test_scrape_no_title():
    """Test scraping a URL with no title element."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
    </head>
    <body>
        <h1>Hello World</h1>
    </body>
    </html>
    """

    # Mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=html_content)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Mock session
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler("!scrape https://example.com")
        assert result == "No title found in the HTML document"


@pytest.mark.asyncio
async def test_scrape_http_error():
    """Test scraping a URL that returns HTTP error."""
    # Mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.reason = "Not Found"
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Mock session
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler("!scrape https://example.com/notfound")
        assert "Error: HTTP 404" in result


@pytest.mark.asyncio
async def test_scrape_network_error():
    """Test scraping a URL that causes a network error."""
    # Mock session that raises an error
    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=Exception("Connection failed"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler("!scrape https://example.com")
        assert "Error:" in result


@pytest.mark.asyncio
async def test_scrape_long_title():
    """Test scraping a URL with a very long title (truncation test)."""
    long_title = "A" * 5000  # Title longer than 3900 chars
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{long_title}</title>
    </head>
    <body>
        <h1>Hello World</h1>
    </body>
    </html>
    """

    # Mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=html_content)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Mock session
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler("!scrape https://example.com")
        # Should be truncated to 3900 chars + "Title: " prefix
        assert len(result) <= 3910
        assert result.startswith("Title: ")


@pytest.mark.asyncio
async def test_scrape_url_with_extra_whitespace():
    """Test scraping with URL that has extra whitespace."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Title</title>
    </head>
    </html>
    """

    # Mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=html_content)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Mock session
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler("!scrape   https://example.com   ")
        assert result == "Title: Test Title"
