"""Tests for MemoryStore file locking - concurrent access safety."""
from __future__ import annotations
import pytest
import asyncio
import tempfile
import shutil
from bot.memory_store import MemoryStore


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


@pytest.mark.asyncio
async def test_concurrent_add_memory_no_data_loss(memory_store):
    """Test that concurrent add_memory calls don't lose data."""
    user_id = "@user:example.com"
    room_id = "!room:example.com"

    # Add 20 memories concurrently
    tasks = [
        memory_store.add_memory(
            user_id=user_id,
            room_id=room_id,
            content=f"Memory {i}",
            scope="user"
        )
        for i in range(20)
    ]

    memory_ids = await asyncio.gather(*tasks)

    # All should have unique IDs
    assert len(set(memory_ids)) == 20

    # All should be retrievable
    memories = await memory_store.get_recent_memories(
        user_id=user_id,
        room_id=room_id,
        days=1,
        scope="user"
    )

    assert len(memories) == 20


@pytest.mark.asyncio
async def test_concurrent_read_write_no_corruption(memory_store):
    """Test that concurrent reads and writes don't corrupt data."""
    user_id = "@user:example.com"
    room_id = "!room:example.com"

    # Add initial memory
    await memory_store.add_memory(
        user_id=user_id,
        room_id=room_id,
        content="Initial memory",
        scope="user"
    )

    # Concurrent reads and writes
    async def write_task(i):
        await memory_store.add_memory(
            user_id=user_id,
            room_id=room_id,
            content=f"Memory {i}",
            scope="user"
        )

    async def read_task():
        memories = await memory_store.get_recent_memories(
            user_id=user_id,
            room_id=room_id,
            days=1,
            scope="user"
        )
        return len(memories)

    # Mix of reads and writes
    tasks = []
    for i in range(10):
        tasks.append(write_task(i))
        tasks.append(read_task())

    results = await asyncio.gather(*tasks)

    # Final check - should have initial + 10 new memories
    final_memories = await memory_store.get_recent_memories(
        user_id=user_id,
        room_id=room_id,
        days=1,
        scope="user"
    )
    assert len(final_memories) == 11


@pytest.mark.asyncio
async def test_different_users_dont_block_each_other(memory_store):
    """Test that different users' operations don't block each other."""
    room_id = "!room:example.com"

    import time
    start = time.time()

    # Add memories for 5 different users concurrently
    tasks = []
    for user_num in range(5):
        user_id = f"@user{user_num}:example.com"
        for mem_num in range(10):
            tasks.append(
                memory_store.add_memory(
                    user_id=user_id,
                    room_id=room_id,
                    content=f"User {user_num} memory {mem_num}",
                    scope="user"
                )
            )

    await asyncio.gather(*tasks)

    elapsed = time.time() - start

    # Should complete relatively quickly (users don't block each other)
    # 50 operations should take < 5 seconds even with file I/O
    assert elapsed < 5.0

    # Verify each user has 10 memories
    for user_num in range(5):
        user_id = f"@user{user_num}:example.com"
        memories = await memory_store.get_recent_memories(
            user_id=user_id,
            room_id=room_id,
            days=1,
            scope="user"
        )
        assert len(memories) == 10


@pytest.mark.asyncio
async def test_concurrent_search_and_add(memory_store):
    """Test concurrent search and add operations."""
    user_id = "@user:example.com"
    room_id = "!room:example.com"

    # Add initial memories
    for i in range(5):
        await memory_store.add_memory(
            user_id=user_id,
            room_id=room_id,
            content=f"Initial {i}",
            tags=["initial"],
            scope="user"
        )

    # Concurrent searches and adds
    async def search_task():
        return await memory_store.search_memories(
            user_id=user_id,
            room_id=room_id,
            query="initial",
            scope="user"
        )

    async def add_task(i):
        await memory_store.add_memory(
            user_id=user_id,
            room_id=room_id,
            content=f"New {i}",
            tags=["new"],
            scope="user"
        )

    tasks = []
    for i in range(10):
        tasks.append(search_task())
        tasks.append(add_task(i))

    await asyncio.gather(*tasks)

    # Final verification
    all_memories = await memory_store.get_recent_memories(
        user_id=user_id,
        room_id=room_id,
        days=1,
        scope="user"
    )
    assert len(all_memories) == 15  # 5 initial + 10 new


@pytest.mark.asyncio
async def test_concurrent_delete_operations(memory_store):
    """Test concurrent delete operations."""
    user_id = "@user:example.com"
    room_id = "!room:example.com"

    # Add memories
    memory_ids = []
    for i in range(10):
        mid = await memory_store.add_memory(
            user_id=user_id,
            room_id=room_id,
            content=f"Memory {i}",
            scope="user"
        )
        memory_ids.append(mid)

    # Delete all concurrently
    tasks = [
        memory_store.delete_memory(
            memory_id=mid,
            user_id=user_id,
            room_id=room_id,
            scope="user"
        )
        for mid in memory_ids
    ]

    results = await asyncio.gather(*tasks)

    # All should succeed
    assert all(results)

    # No memories should remain
    memories = await memory_store.get_recent_memories(
        user_id=user_id,
        room_id=room_id,
        days=1,
        scope="user"
    )
    assert len(memories) == 0


@pytest.mark.asyncio
async def test_access_count_increment_thread_safe(memory_store):
    """Test that access count increments are thread-safe."""
    user_id = "@user:example.com"
    room_id = "!room:example.com"

    # Add a memory
    await memory_store.add_memory(
        user_id=user_id,
        room_id=room_id,
        content="Test memory",
        scope="user"
    )

    # Access it 20 times concurrently
    tasks = [
        memory_store.get_recent_memories(
            user_id=user_id,
            room_id=room_id,
            days=1,
            scope="user"
        )
        for _ in range(20)
    ]

    await asyncio.gather(*tasks)

    # Get final memory
    memories = await memory_store.get_recent_memories(
        user_id=user_id,
        room_id=room_id,
        days=1,
        scope="user"
    )

    # Access count should be 21 (20 + 1 from final retrieval)
    assert memories[0].access_count == 21


@pytest.mark.asyncio
async def test_room_scope_concurrent_access(memory_store):
    """Test concurrent access to room-scoped memories."""
    room_id = "!room:example.com"

    # Multiple users adding to same room concurrently
    tasks = []
    for user_num in range(5):
        user_id = f"@user{user_num}:example.com"
        for mem_num in range(5):
            tasks.append(
                memory_store.add_memory(
                    user_id=user_id,
                    room_id=room_id,
                    content=f"User {user_num} memory {mem_num}",
                    scope="room"
                )
            )

    await asyncio.gather(*tasks)

    # All memories should be accessible from room scope
    memories = await memory_store.get_recent_memories(
        user_id="@any:example.com",  # User doesn't matter for room scope
        room_id=room_id,
        days=1,
        scope="room"
    )

    assert len(memories) == 25


@pytest.mark.asyncio
async def test_stats_during_concurrent_operations(memory_store):
    """Test getting stats while operations are in progress."""
    user_id = "@user:example.com"
    room_id = "!room:example.com"

    # Add some initial memories
    for i in range(5):
        await memory_store.add_memory(
            user_id=user_id,
            room_id=room_id,
            content=f"Memory {i}",
            scope="user"
        )

    # Concurrent add operations and stats calls
    async def add_task(i):
        await memory_store.add_memory(
            user_id=user_id,
            room_id=room_id,
            content=f"New memory {i}",
            scope="user"
        )

    async def stats_task():
        return await memory_store.get_stats(
            user_id=user_id,
            room_id=room_id,
            scope="user"
        )

    tasks = []
    for i in range(10):
        tasks.append(add_task(i))
        if i % 2 == 0:
            tasks.append(stats_task())

    results = await asyncio.gather(*tasks)

    # Final stats should show all memories
    final_stats = await memory_store.get_stats(
        user_id=user_id,
        room_id=room_id,
        scope="user"
    )
    assert final_stats['total_count'] == 15


@pytest.mark.asyncio
async def test_file_lock_per_user(memory_store):
    """Test that file locks are per-user/file, not global."""
    room_id = "!room:example.com"

    # Time operations for two different users
    import time

    async def timed_add_batch(user_id, count):
        start = time.time()
        tasks = [
            memory_store.add_memory(
                user_id=user_id,
                room_id=room_id,
                content=f"Memory {i}",
                scope="user"
            )
            for i in range(count)
        ]
        await asyncio.gather(*tasks)
        return time.time() - start

    # Time sequential execution (as baseline)
    time_user1_alone = await timed_add_batch("@user1:example.com", 10)

    # Reset store
    memory_store = MemoryStore(data_dir=memory_store.data_dir)

    # Time concurrent execution (different users)
    start = time.time()
    await asyncio.gather(
        timed_add_batch("@user2:example.com", 10),
        timed_add_batch("@user3:example.com", 10)
    )
    time_concurrent = time.time() - start

    # Concurrent should be faster than 2x sequential
    # (if locks were global, it would be similar to 2x sequential)
    # Allow for some overhead, but should be < 1.5x of single user time
    assert time_concurrent < (time_user1_alone * 1.5)


@pytest.mark.asyncio
async def test_no_deadlock_on_nested_operations(memory_store):
    """Test that nested operations don't cause deadlocks."""
    user_id = "@user:example.com"
    room_id = "!room:example.com"

    # Add initial memory
    await memory_store.add_memory(
        user_id=user_id,
        room_id=room_id,
        content="Initial",
        scope="user"
    )

    # This should not deadlock even though it's potentially nested
    async def complex_operation():
        # Read
        memories = await memory_store.get_recent_memories(
            user_id=user_id,
            room_id=room_id,
            days=1,
            scope="user"
        )

        # Write
        await memory_store.add_memory(
            user_id=user_id,
            room_id=room_id,
            content=f"New memory",
            scope="user"
        )

        # Read again
        memories = await memory_store.search_memories(
            user_id=user_id,
            room_id=room_id,
            query="memory",
            scope="user"
        )

        return len(memories)

    # Run multiple complex operations concurrently
    tasks = [complex_operation() for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # Should complete without deadlock
    assert all(r >= 1 for r in results)
