import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bot.commands.scrape import scrape_handler


@pytest.mark.asyncio
async def test_scrape_success():
    """Test successful URL scraping with valid HTML."""
    mock_html = """
    <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="This is a test page description">
        </head>
        <body>
            <h1>Welcome</h1>
            <p>This is a test paragraph with some content.</p>
            <p>Here is another paragraph.</p>
            <a href="https://example.com/link1">Link One</a>
            <a href="https://example.com/link2">Link Two</a>
        </body>
    </html>
    """

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=mock_html)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler(url="https://example.com")

    assert result is not None
    assert "Test Page" in result
    assert "This is a test page description" in result
    assert "example.com" in result


@pytest.mark.asyncio
async def test_scrape_empty_url():
    """Test scraping with an empty URL."""
    result = await scrape_handler(url="")
    assert result == "Error: URL cannot be empty"


@pytest.mark.asyncio
async def test_scrape_whitespace_url():
    """Test scraping with a whitespace-only URL."""
    result = await scrape_handler(url="   ")
    assert result == "Error: URL cannot be empty"


@pytest.mark.asyncio
async def test_scrape_adds_https_prefix():
    """Test that URLs without http/https prefix get https added."""
    mock_html = "<html><head><title>Test</title></head><body><p>Content</p></body></html>"

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=mock_html)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler(url="example.com")

    assert result is not None
    # Verify the session.get was called with https:// prefix
    mock_session.get.assert_called_once()
    called_url = mock_session.get.call_args[0][0]
    assert called_url.startswith("https://")


@pytest.mark.asyncio
async def test_scrape_http_error():
    """Test handling of HTTP error responses."""
    mock_response = AsyncMock()
    mock_response.status = 404

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler(url="https://example.com/notfound")

    assert result is not None
    assert "Error: HTTP 404" in result


@pytest.mark.asyncio
async def test_scrape_network_error():
    """Test handling of network errors."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(side_effect=Exception("Network error"))

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler(url="https://example.com")

    assert result is not None
    assert "Error: Failed to scrape URL" in result


@pytest.mark.asyncio
async def test_scrape_no_title():
    """Test scraping HTML with no title tag."""
    mock_html = "<html><body><p>Content without title</p></body></html>"

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=mock_html)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler(url="https://example.com")

    assert result is not None
    assert "No title" in result


@pytest.mark.asyncio
async def test_scrape_with_links():
    """Test that links are extracted correctly."""
    mock_html = """
    <html>
        <head><title>Link Test</title></head>
        <body>
            <p>Some content</p>
            <a href="https://example.com/page1">Page One</a>
            <a href="https://example.com/page2">Page Two</a>
            <a href="https://example.com/page3">Page Three</a>
        </body>
    </html>
    """

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=mock_html)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler(url="https://example.com")

    assert result is not None
    assert "Key Links" in result or "Links found: 3" in result


@pytest.mark.asyncio
async def test_scrape_response_length_limit():
    """Test that responses are truncated to 4000 characters."""
    # Create very large HTML content
    large_content = "<p>" + ("This is a very long paragraph. " * 500) + "</p>"
    mock_html = f"<html><head><title>Large Page</title></head><body>{large_content}</body></html>"

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=mock_html)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        result = await scrape_handler(url="https://example.com")

    assert result is not None
    assert len(result) <= 4000
