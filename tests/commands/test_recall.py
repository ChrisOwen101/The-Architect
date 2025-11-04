"""Tests for recall command."""
from __future__ import annotations
import pytest
import pytest_asyncio
import tempfile
import shutil
from unittest.mock import MagicMock
from bot.commands.recall import recall_handler
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

    # Patch the global memory store in the recall command module
    import bot.commands.recall
    monkeypatch.setattr(bot.commands.recall, '_memory_store', memory_store)

    # Add test memories
    await memory_store.add_memory(
        user_id="@testuser:example.com",
        room_id="!testroom:example.com",
        content="User prefers Python programming",
        tags=["preference", "programming"],
        scope="user"
    )

    await memory_store.add_memory(
        user_id="@testuser:example.com",
        room_id="!testroom:example.com",
        content="User is working on a Matrix bot project",
        tags=["project", "matrix"],
        scope="user"
    )

    return memory_store


@pytest.mark.asyncio
async def test_recall_basic(setup_memories):
    """Test basic recall without query."""
    # Mock matrix context
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await recall_handler(matrix_context=matrix_context)

    assert result is not None
    assert "Found 2 memor" in result
    assert "Python" in result or "Matrix bot" in result


@pytest.mark.asyncio
async def test_recall_with_query(setup_memories):
    """Test recall with search query."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await recall_handler(query="Python", matrix_context=matrix_context)

    assert result is not None
    assert "Python" in result
    assert "Matrix bot" not in result or "Found 1 memory" in result


@pytest.mark.asyncio
async def test_recall_no_results(setup_memories):
    """Test recall when no memories match."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await recall_handler(query="nonexistent", matrix_context=matrix_context)

    assert result is not None
    assert "No memories found" in result


@pytest.mark.asyncio
async def test_recall_with_limit(setup_memories):
    """Test recall with limit parameter."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await recall_handler(limit=1, matrix_context=matrix_context)

    assert result is not None
    assert "Found 1 memory" in result


@pytest.mark.asyncio
async def test_recall_invalid_params():
    """Test recall with invalid parameters."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    # Invalid days
    result = await recall_handler(days=-1, matrix_context=matrix_context)
    assert "Error" in result

    # Invalid limit
    result = await recall_handler(limit=100, matrix_context=matrix_context)
    assert "Error" in result


@pytest.mark.asyncio
async def test_recall_no_context():
    """Test recall without matrix context."""
    result = await recall_handler()
    assert result is not None
    assert "Error" in result
