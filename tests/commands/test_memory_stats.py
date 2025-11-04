"""Tests for memory_stats command."""
from __future__ import annotations
import pytest
import pytest_asyncio
import tempfile
import shutil
from unittest.mock import MagicMock
from bot.commands.memory_stats import memory_stats_handler
from bot.memory_store import MemoryStore


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest_asyncio.fixture
async def setup_memories(temp_data_dir, monkeypatch):
    """Set up test memories."""
    memory_store = MemoryStore(data_dir=temp_data_dir)

    # Patch the global memory store in the memory_stats command module
    import bot.commands.memory_stats
    monkeypatch.setattr(bot.commands.memory_stats, '_memory_store', memory_store)

    # Add test memories with different characteristics
    await memory_store.add_memory(
        user_id="@testuser:example.com",
        room_id="!testroom:example.com",
        content="First memory",
        scope="user"
    )

    await memory_store.add_memory(
        user_id="@testuser:example.com",
        room_id="!testroom:example.com",
        content="Second memory",
        scope="user"
    )

    await memory_store.add_memory(
        user_id="@testuser:example.com",
        room_id="!testroom:example.com",
        content="Third memory",
        scope="user"
    )

    # Access one memory multiple times to make it "most accessed"
    for _ in range(5):
        await memory_store.search_memories(
            user_id="@testuser:example.com",
            room_id="!testroom:example.com",
            query="First",
            scope="user"
        )

    return memory_store


@pytest.mark.asyncio
async def test_memory_stats_with_memories(setup_memories):
    """Test memory_stats when memories exist."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await memory_stats_handler(matrix_context=matrix_context)

    assert result is not None
    assert "Memory Statistics" in result
    assert "Total memories: 3" in result
    assert "Oldest memory:" in result
    assert "Newest memory:" in result
    assert "Most accessed memory:" in result
    assert "Average importance score:" in result


@pytest.mark.asyncio
async def test_memory_stats_empty():
    """Test memory_stats when no memories exist."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await memory_stats_handler(matrix_context=matrix_context)

    assert result is not None
    assert "Total memories: 0" in result
    assert "No memories stored yet" in result


@pytest.mark.asyncio
async def test_memory_stats_shows_usage_hints(setup_memories):
    """Test that stats include usage hints."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await memory_stats_handler(matrix_context=matrix_context)

    assert result is not None
    assert "recall" in result
    assert "forget" in result


@pytest.mark.asyncio
async def test_memory_stats_no_context():
    """Test memory_stats without matrix context."""
    result = await memory_stats_handler()
    assert result is not None
    assert "Error" in result
