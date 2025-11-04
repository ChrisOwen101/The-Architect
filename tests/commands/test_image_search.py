import pytest
from bot.commands.image_search import image_search_handler


@pytest.mark.asyncio
async def test_image_search_success():
    """Test successful image search with a valid search term."""
    result = await image_search_handler("!image_search cats")
    assert result is not None
    assert "cats" in result
    assert "Image search results" in result
    assert "https://www.google.com/search?tbm=isch&q=cats" in result


@pytest.mark.asyncio
async def test_image_search_multi_word():
    """Test image search with multiple word search term."""
    result = await image_search_handler("!image_search cute puppies")
    assert result is not None
    assert "cute puppies" in result
    assert "https://www.google.com/search?tbm=isch&q=cute+puppies" in result


@pytest.mark.asyncio
async def test_image_search_empty_term():
    """Test image search with no search term provided."""
    result = await image_search_handler("!image_search")
    assert result is not None
    assert "Please provide a search term" in result
    assert "Usage:" in result


@pytest.mark.asyncio
async def test_image_search_only_whitespace():
    """Test image search with only whitespace after command."""
    result = await image_search_handler("!image_search   ")
    assert result is not None
    assert "Please provide a search term" in result


@pytest.mark.asyncio
async def test_image_search_special_characters():
    """Test image search with special characters in search term."""
    result = await image_search_handler("!image_search dogs & cats")
    assert result is not None
    assert "dogs & cats" in result
    assert "Image search results" in result


@pytest.mark.asyncio
async def test_image_search_with_extra_spaces():
    """Test image search handles extra spaces properly."""
    result = await image_search_handler("!image_search   nature   photography  ")
    assert result is not None
    assert "nature   photography" in result
    assert "Image search results" in result
