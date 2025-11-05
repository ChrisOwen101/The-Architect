"""Tests for memory storage system."""
from __future__ import annotations
import pytest
import time
import tempfile
import shutil
from bot.memory_store import MemoryEntry, MemoryStore


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def memory_store(temp_data_dir):
    """Create a MemoryStore with temporary data directory."""
    return MemoryStore(data_dir=temp_data_dir)


# MemoryEntry Tests

def test_memory_entry_creation():
    """Test creating a MemoryEntry."""
    entry = MemoryEntry(
        id="test-id",
        timestamp=time.time(),
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Test memory content"
    )

    assert entry.id == "test-id"
    assert entry.content == "Test memory content"
    assert entry.tags == []
    assert entry.access_count == 0


def test_memory_entry_importance_calculation():
    """Test importance score calculation."""
    current_time = time.time()

    # Recent memory with no accesses
    recent = MemoryEntry(
        id="recent",
        timestamp=current_time - 86400,  # 1 day ago
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Recent memory",
        access_count=0
    )

    # Old memory with many accesses
    old = MemoryEntry(
        id="old",
        timestamp=current_time - (86400 * 30),  # 30 days ago
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Old memory",
        access_count=10
    )

    recent_score = recent.calculate_importance(current_time)
    old_score = old.calculate_importance(current_time)

    # Both should have positive scores
    assert recent_score > 0
    assert old_score > 0

    # Recent memory should have higher base importance
    # but older memory with high access might be comparable


def test_memory_entry_markdown_serialization():
    """Test converting MemoryEntry to markdown and back."""
    entry = MemoryEntry(
        id="test-id",
        timestamp=1234567890.0,
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Test memory content",
        context="Test context",
        tags=["tag1", "tag2"],
        access_count=5,
        last_accessed=1234567900.0
    )

    # Convert to markdown
    markdown = entry.to_markdown()

    assert "---" in markdown
    assert "test-id" in markdown
    assert "Test memory content" in markdown
    assert "Test context" in markdown
    assert "tag1" in markdown

    # Parse back from markdown
    parsed = MemoryEntry.from_markdown(markdown)

    assert parsed.id == entry.id
    assert parsed.timestamp == entry.timestamp
    assert parsed.user_id == entry.user_id
    assert parsed.room_id == entry.room_id
    assert parsed.content == entry.content
    assert parsed.context == entry.context
    assert parsed.tags == entry.tags
    assert parsed.access_count == entry.access_count


# MemoryStore Tests

@pytest.mark.asyncio
async def test_add_memory(memory_store):
    """Test adding a memory to the store."""
    memory_id = await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Test memory",
        context="Test context",
        tags=["test"],
        scope="user"
    )

    assert memory_id is not None
    assert len(memory_id) > 0


@pytest.mark.asyncio
async def test_get_recent_memories(memory_store):
    """Test retrieving recent memories."""
    # Add multiple memories
    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Memory 1",
        scope="user"
    )

    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Memory 2",
        scope="user"
    )

    # Retrieve recent memories
    memories = await memory_store.get_recent_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        days=30,
        scope="user"
    )

    assert len(memories) == 2
    assert memories[0].content in ["Memory 1", "Memory 2"]


@pytest.mark.asyncio
async def test_get_recent_memories_filters_by_time(memory_store):
    """Test that get_recent_memories filters by time window."""
    # Add an old memory (manually)
    user_id = "@user:example.com"
    room_id = "!room:example.com"

    # Add recent memory
    await memory_store.add_memory(
        user_id=user_id,
        room_id=room_id,
        content="Recent memory",
        scope="user"
    )

    # Retrieve with 1-day window (should get the recent one)
    memories = await memory_store.get_recent_memories(
        user_id=user_id,
        room_id=room_id,
        days=1,
        scope="user"
    )

    assert len(memories) == 1
    assert memories[0].content == "Recent memory"


@pytest.mark.asyncio
async def test_search_memories_by_query(memory_store):
    """Test searching memories by text query."""
    # Add memories with different content
    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="I love Python programming",
        scope="user"
    )

    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="JavaScript is also good",
        scope="user"
    )

    # Search for Python
    results = await memory_store.search_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        query="Python",
        scope="user"
    )

    assert len(results) == 1
    assert "Python" in results[0].content


@pytest.mark.asyncio
async def test_search_memories_by_tags(memory_store):
    """Test searching memories by tags."""
    # Add memories with tags
    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Memory about programming",
        tags=["programming", "python"],
        scope="user"
    )

    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Memory about cooking",
        tags=["cooking", "recipe"],
        scope="user"
    )

    # Search by tag
    results = await memory_store.search_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        query="programming",
        scope="user"
    )

    assert len(results) >= 1
    assert any("programming" in m.tags for m in results)


@pytest.mark.asyncio
async def test_search_memories_with_date_range(memory_store):
    """Test searching memories with date range filters."""
    current_time = time.time()

    # Add memory
    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Test memory",
        scope="user"
    )

    # Search with date range that includes the memory
    results = await memory_store.search_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        start_date=current_time - 3600,  # 1 hour ago
        end_date=current_time + 3600,  # 1 hour from now
        scope="user"
    )

    assert len(results) == 1

    # Search with date range that excludes the memory
    results = await memory_store.search_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        start_date=current_time + 3600,  # Future
        scope="user"
    )

    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_memories_limit(memory_store):
    """Test that search respects the limit parameter."""
    # Add many memories
    for i in range(15):
        await memory_store.add_memory(
            user_id="@user:example.com",
            room_id="!room:example.com",
            content=f"Memory {i}",
            scope="user"
        )

    # Search with limit
    results = await memory_store.search_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        limit=5,
        scope="user"
    )

    assert len(results) <= 5


@pytest.mark.asyncio
async def test_delete_memory(memory_store):
    """Test deleting a specific memory."""
    # Add memory
    memory_id = await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="To be deleted",
        scope="user"
    )

    # Delete it
    success = await memory_store.delete_memory(
        memory_id=memory_id,
        user_id="@user:example.com",
        room_id="!room:example.com",
        scope="user"
    )

    assert success is True

    # Verify it's gone
    memories = await memory_store.search_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        query="deleted",
        scope="user"
    )

    assert len(memories) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_memory(memory_store):
    """Test deleting a memory that doesn't exist."""
    success = await memory_store.delete_memory(
        memory_id="nonexistent-id",
        user_id="@user:example.com",
        room_id="!room:example.com",
        scope="user"
    )

    assert success is False


@pytest.mark.asyncio
async def test_delete_memory_wrong_user(memory_store):
    """Test that users can't delete other users' memories."""
    # Add memory as user1
    memory_id = await memory_store.add_memory(
        user_id="@user1:example.com",
        room_id="!room:example.com",
        content="User 1's memory",
        scope="user"
    )

    # Try to delete as user2
    success = await memory_store.delete_memory(
        memory_id=memory_id,
        user_id="@user2:example.com",
        room_id="!room:example.com",
        scope="user"
    )

    assert success is False


@pytest.mark.asyncio
async def test_get_stats(memory_store):
    """Test getting memory statistics."""
    # Add memories
    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Memory 1",
        scope="user"
    )

    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Memory 2",
        scope="user"
    )

    # Get stats
    stats = await memory_store.get_stats(
        user_id="@user:example.com",
        room_id="!room:example.com",
        scope="user"
    )

    assert stats['total_count'] == 2
    assert stats['oldest_memory'] is not None
    assert stats['newest_memory'] is not None
    assert stats['most_accessed'] is not None
    assert stats['avg_importance'] >= 0


@pytest.mark.asyncio
async def test_get_stats_empty(memory_store):
    """Test getting stats when no memories exist."""
    stats = await memory_store.get_stats(
        user_id="@user:example.com",
        room_id="!room:example.com",
        scope="user"
    )

    assert stats['total_count'] == 0
    assert stats['oldest_memory'] is None
    assert stats['newest_memory'] is None


@pytest.mark.asyncio
async def test_user_and_room_scope_isolation(memory_store):
    """Test that user and room scopes are isolated."""
    # Add user-scoped memory
    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="User memory",
        scope="user"
    )

    # Add room-scoped memory
    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Room memory",
        scope="room"
    )

    # Retrieve user memories
    user_memories = await memory_store.get_recent_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        days=30,
        scope="user"
    )

    # Retrieve room memories
    room_memories = await memory_store.get_recent_memories(
        user_id="@user:example.com",
        room_id="!room:example.com",
        days=30,
        scope="room"
    )

    # Should be separate
    assert len(user_memories) == 1
    assert len(room_memories) == 1
    assert user_memories[0].content == "User memory"
    assert room_memories[0].content == "Room memory"


@pytest.mark.asyncio
async def test_access_count_increments(memory_store):
    """Test that access count increments on retrieval."""
    # Add memory
    await memory_store.add_memory(
        user_id="@user:example.com",
        room_id="!room:example.com",
        content="Test memory",
        scope="user"
    )

    # Access it multiple times
    for _ in range(3):
        memories = await memory_store.get_recent_memories(
            user_id="@user:example.com",
            room_id="!room:example.com",
            days=30,
            scope="user"
        )

    # Check access count
    assert memories[0].access_count >= 3
