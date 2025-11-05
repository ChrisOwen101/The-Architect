"""Basic proof-of-concept concurrency test."""
from __future__ import annotations
import pytest
import asyncio
from bot.conversation_manager import ConversationManager


@pytest.fixture
def conversation_manager():
    """Create a ConversationManager for testing."""
    return ConversationManager(
        max_concurrent=10,
        max_per_user=3,
        idle_timeout_seconds=60,
        max_duration_seconds=120
    )


@pytest.mark.asyncio
async def test_five_concurrent_users(conversation_manager):
    """Simulate 5 concurrent users with conversations."""
    users = [
        "@alice:example.com",
        "@bob:example.com",
        "@charlie:example.com",
        "@diana:example.com",
        "@eve:example.com"
    ]

    contexts = []

    # Each user starts a conversation
    for user in users:
        ctx = await conversation_manager.start_conversation(
            thread_root_id=f"$thread_{user}",
            user_id=user,
            room_id="!room:example.com"
        )
        assert ctx is not None, f"Failed to start conversation for {user}"
        contexts.append((user, ctx))

    # Verify all 5 conversations are active
    stats = await conversation_manager.get_stats()
    assert stats['total_active'] == 5

    active_convs = await conversation_manager.get_active_conversations()
    assert len(active_convs) == 5

    # Verify each user has one conversation
    for user in users:
        user_convs = await conversation_manager.get_active_conversations(user_id=user)
        assert len(user_convs) == 1
        assert user_convs[0].user_id == user

    # Simulate some conversation activity
    for user, ctx in contexts:
        # Update activity
        success = await conversation_manager.update_activity(ctx.id)
        assert success is True

        # Verify context exists
        all_convs = await conversation_manager.get_active_conversations()
        assert any(c.id == ctx.id for c in all_convs)

    # End all conversations
    for user, ctx in contexts:
        success = await conversation_manager.end_conversation(ctx.id)
        assert success is True

    # Verify cleanup
    stats = await conversation_manager.get_stats()
    assert stats['total_active'] == 0

    active_convs = await conversation_manager.get_active_conversations()
    assert len(active_convs) == 0


@pytest.mark.asyncio
async def test_concurrent_user_workflows(conversation_manager):
    """Test realistic concurrent user workflows."""

    async def user_workflow(user_id, num_messages):
        """Simulate a user having a conversation."""
        # Start conversation
        ctx = await conversation_manager.start_conversation(
            thread_root_id=f"$thread_{user_id}",
            user_id=user_id,
            room_id="!room:example.com"
        )

        if not ctx:
            return None

        try:
            # Simulate sending messages over time
            for i in range(num_messages):
                # Simulate processing time
                await asyncio.sleep(0.05)

                # Update activity
                await conversation_manager.update_activity(ctx.id)

            return ctx.id

        finally:
            # End conversation
            await conversation_manager.end_conversation(ctx.id)

    # Start 5 users with different conversation lengths
    users = [
        ("@alice:example.com", 3),
        ("@bob:example.com", 5),
        ("@charlie:example.com", 2),
        ("@diana:example.com", 4),
        ("@eve:example.com", 3)
    ]

    # Run all workflows concurrently
    tasks = [user_workflow(user, msgs) for user, msgs in users]
    results = await asyncio.gather(*tasks)

    # All should complete successfully
    assert all(r is not None for r in results)

    # All conversations should be cleaned up
    stats = await conversation_manager.get_stats()
    assert stats['total_active'] == 0


@pytest.mark.asyncio
async def test_conversation_isolation(conversation_manager):
    """Test that conversations are properly isolated."""
    # Start conversations for different users in different rooms
    ctx1 = await conversation_manager.start_conversation(
        thread_root_id="$thread1",
        user_id="@alice:example.com",
        room_id="!room1:example.com"
    )

    ctx2 = await conversation_manager.start_conversation(
        thread_root_id="$thread2",
        user_id="@bob:example.com",
        room_id="!room2:example.com"
    )

    ctx3 = await conversation_manager.start_conversation(
        thread_root_id="$thread3",
        user_id="@alice:example.com",
        room_id="!room2:example.com"
    )

    # Verify all are active
    assert ctx1 is not None
    assert ctx2 is not None
    assert ctx3 is not None

    # Verify they're distinct
    assert ctx1.id != ctx2.id != ctx3.id

    # Verify user-specific queries work
    alice_convs = await conversation_manager.get_active_conversations(
        user_id="@alice:example.com"
    )
    assert len(alice_convs) == 2

    bob_convs = await conversation_manager.get_active_conversations(
        user_id="@bob:example.com"
    )
    assert len(bob_convs) == 1

    # Clean up
    await conversation_manager.end_conversation(ctx1.id)
    await conversation_manager.end_conversation(ctx2.id)
    await conversation_manager.end_conversation(ctx3.id)


@pytest.mark.asyncio
async def test_rapid_start_stop_cycles(conversation_manager):
    """Test rapid conversation start/stop cycles."""
    user_id = "@alice:example.com"

    # Rapidly start and stop conversations
    for i in range(20):
        ctx = await conversation_manager.start_conversation(
            thread_root_id=f"$thread{i}",
            user_id=user_id,
            room_id="!room:example.com"
        )
        assert ctx is not None

        # Immediately end it
        success = await conversation_manager.end_conversation(ctx.id)
        assert success is True

    # Should be no active conversations
    stats = await conversation_manager.get_stats()
    assert stats['total_active'] == 0


@pytest.mark.asyncio
async def test_basic_proof_of_concept():
    """Basic proof that concurrent conversation support works."""
    # Create manager
    manager = ConversationManager(
        max_concurrent=5,
        max_per_user=2,
        idle_timeout_seconds=10,
        max_duration_seconds=20
    )

    # Scenario: Three users (Alice, Bob, Charlie) each start a conversation
    users = ["@alice:example.com", "@bob:example.com", "@charlie:example.com"]
    contexts = {}

    print("\n=== Starting Conversations ===")
    for user in users:
        ctx = await manager.start_conversation(
            thread_root_id=f"$thread_{user}",
            user_id=user,
            room_id="!room:example.com"
        )
        contexts[user] = ctx
        print(f"✓ {user} started conversation {ctx.id[:8]}...")

    # Verify all are active
    stats = await manager.get_stats()
    print(f"\n=== Stats ===")
    print(f"Active conversations: {stats['total_active']}")
    print(f"Max concurrent: {stats['max_concurrent']}")
    print(f"Users with conversations: {stats['users_with_conversations']}")

    assert stats['total_active'] == 3

    # Alice sends a message (updates activity)
    print(f"\n=== Activity ===")
    await manager.update_activity(contexts["@alice:example.com"].id)
    print("✓ Alice's conversation activity updated")

    # Bob ends their conversation
    await manager.end_conversation(contexts["@bob:example.com"].id)
    print("✓ Bob's conversation ended")

    # Now only Alice and Charlie are active
    stats = await manager.get_stats()
    assert stats['total_active'] == 2

    # Charlie tries to start a second conversation (should succeed, limit is 2 per user)
    ctx2 = await manager.start_conversation(
        thread_root_id="$thread_charlie_2",
        user_id="@charlie:example.com",
        room_id="!room:example.com"
    )
    assert ctx2 is not None
    print("✓ Charlie started second conversation")

    # Charlie tries to start a third conversation (should fail, limit is 2)
    ctx3 = await manager.start_conversation(
        thread_root_id="$thread_charlie_3",
        user_id="@charlie:example.com",
        room_id="!room:example.com"
    )
    assert ctx3 is None
    print("✓ Charlie's third conversation rejected (per-user limit)")

    # Clean up
    print(f"\n=== Cleanup ===")
    await manager.end_conversation(contexts["@alice:example.com"].id)
    await manager.end_conversation(contexts["@charlie:example.com"].id)
    await manager.end_conversation(ctx2.id)

    stats = await manager.get_stats()
    assert stats['total_active'] == 0
    print(f"✓ All conversations ended (active: {stats['total_active']})")

    print("\n=== ✅ Proof of Concept Complete ===")
