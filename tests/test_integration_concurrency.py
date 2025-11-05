"""Integration tests for concurrent conversation support."""
from __future__ import annotations
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from bot.conversation_manager import ConversationManager
from bot.rate_limiter import RateLimiter
from bot.matrix_wrapper import MatrixClientWrapper
from nio import AsyncClient


@pytest.fixture
def conversation_manager():
    """Create a ConversationManager for testing."""
    return ConversationManager(
        max_concurrent=10,
        max_per_user=3,
        idle_timeout_seconds=60,
        max_duration_seconds=120
    )


@pytest.fixture
def rate_limiter():
    """Create a RateLimiter for testing."""
    return RateLimiter(
        rate=5.0,
        burst=10,
        global_rate=10.0,
        global_burst=20
    )


@pytest.fixture
def mock_client():
    """Create a mock AsyncClient."""
    client = MagicMock(spec=AsyncClient)
    client.user_id = "@bot:example.com"
    client.room_send = AsyncMock(return_value=MagicMock(event_id="$event1"))
    client.room_messages = AsyncMock(return_value=MagicMock())
    client.sync = AsyncMock(return_value=MagicMock())
    return client


@pytest.fixture
def wrapped_client(mock_client):
    """Create a wrapped Matrix client."""
    return MatrixClientWrapper(mock_client)


@pytest.mark.asyncio
async def test_multiple_users_concurrent_requests(conversation_manager, rate_limiter):
    """Test multiple users sending requests simultaneously."""
    users = [f"@user{i}:example.com" for i in range(5)]

    async def user_workflow(user_id):
        # Start conversation
        ctx = await conversation_manager.start_conversation(
            thread_root_id=f"$thread_{user_id}",
            user_id=user_id,
            room_id="!room:example.com"
        )

        if ctx is None:
            return None

        # Acquire rate limit
        rate_ok = await rate_limiter.acquire(user_id, timeout=5.0)

        if not rate_ok:
            await conversation_manager.end_conversation(ctx.id)
            return None

        # Simulate work
        await asyncio.sleep(0.1)

        # End conversation
        await conversation_manager.end_conversation(ctx.id)

        return ctx.id

    # All users send requests concurrently
    tasks = [user_workflow(user) for user in users]
    results = await asyncio.gather(*tasks)

    # All should succeed
    assert all(r is not None for r in results)


@pytest.mark.asyncio
async def test_user_at_limit_gets_error(conversation_manager):
    """Test that user at limit receives appropriate error."""
    user_id = "@user1:example.com"

    # Start conversations up to limit
    contexts = []
    for i in range(3):  # Per-user limit is 3
        ctx = await conversation_manager.start_conversation(
            thread_root_id=f"$thread{i}",
            user_id=user_id,
            room_id="!room:example.com"
        )
        assert ctx is not None
        contexts.append(ctx)

    # Try to start another (should fail)
    ctx_overflow = await conversation_manager.start_conversation(
        thread_root_id="$thread_overflow",
        user_id=user_id,
        room_id="!room:example.com"
    )

    assert ctx_overflow is None


@pytest.mark.asyncio
async def test_rate_limiter_slows_rapid_requests(rate_limiter):
    """Test that rate limiter slows down rapid requests without failing."""
    user_id = "@user1:example.com"

    import time
    start = time.time()

    # Make 15 requests (burst is 10, so should wait for more tokens)
    for _ in range(15):
        success = await rate_limiter.acquire(user_id, timeout=10.0)
        assert success is True  # Should succeed eventually

    elapsed = time.time() - start

    # Should take some time (first 10 are burst, then need to wait for refill)
    # At 5 tokens/sec, 5 more tokens takes ~1 second
    assert elapsed >= 0.8  # Allow for timing variance


@pytest.mark.asyncio
async def test_conversation_cleanup_frees_resources(conversation_manager):
    """Test that conversation cleanup automatically frees resources."""
    conversation_manager.start_cleanup_task()

    try:
        user_id = "@user1:example.com"

        # Start conversations
        contexts = []
        for i in range(3):
            ctx = await conversation_manager.start_conversation(
                thread_root_id=f"$thread{i}",
                user_id=user_id,
                room_id="!room:example.com"
            )
            contexts.append(ctx)

        # Verify at limit
        stats = await conversation_manager.get_stats()
        assert stats['total_active'] == 3

        # Manually trigger cleanup for one conversation
        await conversation_manager.end_conversation(contexts[0].id)

        # Should be able to start new conversation
        new_ctx = await conversation_manager.start_conversation(
            thread_root_id="$thread_new",
            user_id=user_id,
            room_id="!room:example.com"
        )
        assert new_ctx is not None

    finally:
        conversation_manager.stop_cleanup_task()


@pytest.mark.asyncio
async def test_shutdown_cleanup_works(conversation_manager, rate_limiter):
    """Test that cleanup on shutdown works correctly."""
    # Start background tasks
    conversation_manager.start_cleanup_task()
    rate_limiter.start_refill_task()

    # Start some conversations
    for i in range(3):
        await conversation_manager.start_conversation(
            thread_root_id=f"$thread{i}",
            user_id=f"@user{i}:example.com",
            room_id="!room:example.com"
        )

    stats = await conversation_manager.get_stats()
    assert stats['total_active'] == 3

    # Stop tasks (simulating shutdown)
    conversation_manager.stop_cleanup_task()
    rate_limiter.stop_refill_task()

    # Give tasks time to cancel
    await asyncio.sleep(0.2)

    # Tasks should be cancelled or done
    assert conversation_manager._cleanup_task.done()
    assert rate_limiter._refill_task.done()


@pytest.mark.asyncio
async def test_matrix_wrapper_prevents_race_conditions(wrapped_client, mock_client):
    """Test that MatrixClientWrapper prevents race conditions."""
    # Simulate concurrent sends to same room
    tasks = [
        wrapped_client.room_send(
            "!room:example.com",
            "m.room.message",
            {"body": f"Message {i}", "msgtype": "m.text"}
        )
        for i in range(10)
    ]

    await asyncio.gather(*tasks)

    # All calls should have succeeded
    assert mock_client.room_send.call_count == 10


@pytest.mark.asyncio
async def test_full_workflow_integration(conversation_manager, rate_limiter, wrapped_client):
    """Test full workflow: conversation + rate limiting + Matrix send."""
    user_id = "@user1:example.com"
    room_id = "!room:example.com"

    async def full_workflow():
        # 1. Start conversation
        ctx = await conversation_manager.start_conversation(
            thread_root_id="$thread1",
            user_id=user_id,
            room_id=room_id
        )

        if not ctx:
            return "conversation_limit"

        try:
            # 2. Acquire rate limit
            rate_ok = await rate_limiter.acquire(user_id, timeout=5.0)

            if not rate_ok:
                return "rate_limit"

            # 3. Send Matrix message
            await wrapped_client.room_send(
                room_id,
                "m.room.message",
                {"body": "Test message", "msgtype": "m.text"}
            )

            # 4. Update activity
            await conversation_manager.update_activity(ctx.id)

            return "success"

        finally:
            # 5. End conversation
            await conversation_manager.end_conversation(ctx.id)

    # Run workflow
    result = await full_workflow()
    assert result == "success"


@pytest.mark.asyncio
async def test_concurrent_workflows_dont_interfere(conversation_manager, rate_limiter, wrapped_client):
    """Test that concurrent workflows don't interfere with each other."""
    async def workflow(user_id):
        ctx = await conversation_manager.start_conversation(
            thread_root_id=f"$thread_{user_id}",
            user_id=user_id,
            room_id="!room:example.com"
        )

        if not ctx:
            return False

        try:
            rate_ok = await rate_limiter.acquire(user_id, timeout=5.0)
            if not rate_ok:
                return False

            await wrapped_client.room_send(
                "!room:example.com",
                "m.room.message",
                {"body": f"Message from {user_id}", "msgtype": "m.text"}
            )

            return True
        finally:
            await conversation_manager.end_conversation(ctx.id)

    # Run 5 concurrent workflows
    tasks = [workflow(f"@user{i}:example.com") for i in range(5)]
    results = await asyncio.gather(*tasks)

    # All should succeed
    assert all(results)


@pytest.mark.asyncio
async def test_stress_test_concurrent_operations(conversation_manager, rate_limiter):
    """Stress test with many concurrent operations."""
    import time

    start = time.time()
    success_count = 0
    fail_count = 0

    async def stress_workflow(user_id, thread_id):
        nonlocal success_count, fail_count

        ctx = await conversation_manager.start_conversation(
            thread_root_id=thread_id,
            user_id=user_id,
            room_id="!room:example.com"
        )

        if not ctx:
            fail_count += 1
            return

        try:
            rate_ok = await rate_limiter.acquire(user_id, timeout=5.0)
            if rate_ok:
                success_count += 1
            else:
                fail_count += 1
        finally:
            await conversation_manager.end_conversation(ctx.id)

    # Simulate 50 concurrent requests from 10 users
    tasks = []
    for user_num in range(10):
        user_id = f"@user{user_num}:example.com"
        for req_num in range(5):
            tasks.append(stress_workflow(user_id, f"$thread_{user_num}_{req_num}"))

    await asyncio.gather(*tasks)

    elapsed = time.time() - start

    # Should complete in reasonable time
    assert elapsed < 10.0

    # Most should succeed (some might fail due to limits)
    assert success_count >= 40


@pytest.mark.asyncio
async def test_error_handling_in_workflow(conversation_manager, wrapped_client, mock_client):
    """Test error handling in integrated workflow."""
    # Make client raise error
    mock_client.room_send.side_effect = Exception("Network error")

    user_id = "@user1:example.com"

    # Start conversation
    ctx = await conversation_manager.start_conversation(
        thread_root_id="$thread1",
        user_id=user_id,
        room_id="!room:example.com"
    )

    assert ctx is not None

    # Try to send (should fail)
    with pytest.raises(Exception, match="Network error"):
        await wrapped_client.room_send(
            "!room:example.com",
            "m.room.message",
            {"body": "Test", "msgtype": "m.text"}
        )

    # Conversation should still be active (caller must clean up)
    stats = await conversation_manager.get_stats()
    assert stats['total_active'] == 1

    # Clean up
    await conversation_manager.end_conversation(ctx.id)

    stats = await conversation_manager.get_stats()
    assert stats['total_active'] == 0


@pytest.mark.asyncio
async def test_global_limit_across_users(conversation_manager):
    """Test that global limit is enforced across all users."""
    # Global limit is 10, per-user is 3
    # Start 10 conversations from different users (should succeed)
    contexts = []
    for i in range(10):
        ctx = await conversation_manager.start_conversation(
            thread_root_id=f"$thread{i}",
            user_id=f"@user{i}:example.com",
            room_id="!room:example.com"
        )
        assert ctx is not None
        contexts.append(ctx)

    # Try to start 11th conversation (should fail)
    ctx_overflow = await conversation_manager.start_conversation(
        thread_root_id="$thread_overflow",
        user_id="@user_overflow:example.com",
        room_id="!room:example.com"
    )

    assert ctx_overflow is None


@pytest.mark.asyncio
async def test_rate_limiter_global_limit(rate_limiter):
    """Test rate limiter global limit across users."""
    # Exhaust global bucket with different users
    success_count = 0

    for user_num in range(10):
        user_id = f"@user{user_num}:example.com"
        for _ in range(3):  # Each user tries 3 requests
            success = await rate_limiter.acquire(user_id, timeout=0.5)
            if success:
                success_count += 1

    # Should get close to global burst limit (20)
    assert 18 <= success_count <= 22
