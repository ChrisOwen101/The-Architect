"""Tests for forget command."""
from __future__ import annotations
import pytest
import pytest_asyncio
import tempfile
import shutil
from unittest.mock import MagicMock
from bot.commands.forget import forget_handler
from bot.memory_store import MemoryStore


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest_asyncio.fixture
async def setup_memory(temp_data_dir, monkeypatch):
    """Set up a test memory and return its ID."""
    memory_store = MemoryStore(data_dir=temp_data_dir)

    # Patch the global memory store in the forget command module
    import bot.commands.forget
    monkeypatch.setattr(bot.commands.forget, '_memory_store', memory_store)

    # Add test memory
    memory_id = await memory_store.add_memory(
        user_id="@testuser:example.com",
        room_id="!testroom:example.com",
        content="Test memory to delete",
        scope="user"
    )

    return memory_id, memory_store


@pytest.mark.asyncio
async def test_forget_success(setup_memory):
    """Test successfully deleting a memory."""
    memory_id, memory_store = setup_memory

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

    result = await forget_handler(memory_id=memory_id, matrix_context=matrix_context)

    assert result is not None
    assert "has been deleted" in result
    assert memory_id in result

    # Verify memory is deleted
    memories = await memory_store.search_memories(
        user_id="@testuser:example.com",
        room_id="!testroom:example.com",
        scope="user"
    )
    assert len(memories) == 0


@pytest.mark.asyncio
async def test_forget_nonexistent_memory():
    """Test deleting a memory that doesn't exist."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await forget_handler(memory_id="nonexistent-id", matrix_context=matrix_context)

    assert result is not None
    assert "not found" in result or "don't have permission" in result


@pytest.mark.asyncio
async def test_forget_invalid_id():
    """Test deleting with invalid memory ID format."""
    mock_event = MagicMock()
    mock_event.sender = "@testuser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await forget_handler(memory_id="abc", matrix_context=matrix_context)

    assert result is not None
    assert "Invalid" in result or "Error" in result


@pytest.mark.asyncio
async def test_forget_wrong_user(setup_memory):
    """Test that users can't delete other users' memories."""
    memory_id, _ = setup_memory

    # Try to delete as different user
    mock_event = MagicMock()
    mock_event.sender = "@otheruser:example.com"
    mock_room = MagicMock()
    mock_room.room_id = "!testroom:example.com"

    matrix_context = {
        "event": mock_event,
        "room": mock_room,
        "client": MagicMock()
    }

    result = await forget_handler(memory_id=memory_id, matrix_context=matrix_context)

    assert result is not None
    assert "not found" in result or "don't have permission" in result


@pytest.mark.asyncio
async def test_forget_no_context():
    """Test forget without matrix context."""
    result = await forget_handler(memory_id="test-id")
    assert result is not None
    assert "Error" in result
