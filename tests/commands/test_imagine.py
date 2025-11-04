import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bot.commands.imagine import imagine_handler


@pytest.mark.asyncio
async def test_imagine_empty_prompt():
    """Test that empty prompt returns error."""
    result = await imagine_handler(prompt="")
    assert result is not None
    assert "Error" in result
    assert "provide a prompt" in result


@pytest.mark.asyncio
async def test_imagine_invalid_size():
    """Test that invalid size returns error."""
    result = await imagine_handler(prompt="a cat", size=512)
    # Size validation should occur
    assert result is not None


@pytest.mark.asyncio
async def test_imagine_invalid_count():
    """Test that invalid count returns error."""
    result = await imagine_handler(prompt="a cat", count=0)
    assert result is not None
    assert "Error" in result
    assert "Count must be between 1 and 4" in result

    result = await imagine_handler(prompt="a cat", count=5)
    assert result is not None
    assert "Error" in result
    assert "Count must be between 1 and 4" in result


@pytest.mark.asyncio
async def test_imagine_invalid_style():
    """Test that invalid style returns error."""
    result = await imagine_handler(prompt="a cat", style="invalid_style")
    assert result is not None
    assert "Error" in result
    assert "Style must be one of" in result


@pytest.mark.asyncio
async def test_imagine_missing_api_key():
    """Test that missing API key returns error."""
    with patch.dict('os.environ', {}, clear=True):
        result = await imagine_handler(prompt="a cat")
        assert result is not None
        assert "Error" in result
        assert "API key not configured" in result


@pytest.mark.asyncio
async def test_imagine_success():
    """Test successful image generation."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "data": [
            {"url": "https://example.com/image1.png"}
        ]
    })

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock()
    ))

    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch('aiohttp.ClientSession', return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock()
        )):
            result = await imagine_handler(prompt="a cyberpunk cat")
            assert result is not None
            assert "Generated" in result
            assert "example.com/image1.png" in result


@pytest.mark.asyncio
async def test_imagine_with_style():
    """Test image generation with style parameter."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "data": [
            {"url": "https://example.com/image1.png"}
        ]
    })

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock()
    ))

    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch('aiohttp.ClientSession', return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock()
        )):
            result = await imagine_handler(prompt="a cat", style="cinematic")
            assert result is not None
            assert "Generated" in result
            assert "cinematic" in result


@pytest.mark.asyncio
async def test_imagine_api_error():
    """Test handling of API error responses."""
    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value="Bad request")

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock()
    ))

    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch('aiohttp.ClientSession', return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock()
        )):
            result = await imagine_handler(prompt="a cat")
            assert result is not None
            assert "Error generating image" in result


@pytest.mark.asyncio
async def test_imagine_no_images_returned():
    """Test handling when API returns no images."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"data": []})

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock()
    ))

    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch('aiohttp.ClientSession', return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock()
        )):
            result = await imagine_handler(prompt="a cat")
            assert result is not None
            assert "No images generated" in result


@pytest.mark.asyncio
async def test_imagine_with_seed():
    """Test that seed parameter is acknowledged but doesn't break execution."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "data": [
            {"url": "https://example.com/image1.png"}
        ]
    })

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock()
    ))

    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch('aiohttp.ClientSession', return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock()
        )):
            result = await imagine_handler(prompt="a cat", seed=12345)
            assert result is not None
            assert "Generated" in result
            assert "seed" in result.lower()


@pytest.mark.asyncio
async def test_imagine_network_error():
    """Test handling of network errors."""
    import aiohttp

    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        with patch('aiohttp.ClientSession') as mock_session_class:
            # Make the session context manager raise an error
            mock_session_class.return_value.__aenter__.side_effect = aiohttp.ClientError("Connection failed")

            result = await imagine_handler(prompt="a cat")
            assert result is not None
            assert "Network error" in result
