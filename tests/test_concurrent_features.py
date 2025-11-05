"""Tests for concurrent conversation support features (Phase 2.3 and Phase 3)."""
from __future__ import annotations
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bot.openai_integration import send_progress_update, get_openai_session, close_openai_session
from bot.handlers import send_queue_notification
from bot.conversation_manager import ConversationManager


class MockEvent:
    """Mock Matrix event."""
    def __init__(self, sender="@user:matrix.org", event_id="$test"):
        self.sender = sender
        self.event_id = event_id
        self.body = "test"


class MockRoom:
    """Mock Matrix room."""
    def __init__(self, room_id="!test:matrix.org"):
        self.room_id = room_id


class MockClient:
    """Mock Matrix client."""
    def __init__(self):
        self.user_id = "@bot:matrix.org"

    async def room_send(self, *args, **kwargs):
        return MagicMock(transport_response=MagicMock(ok=True))


# Test Phase 2.3.1: Progress Updates

@pytest.mark.asyncio
async def test_send_progress_update():
    """Test that progress updates are sent correctly."""
    client = MockClient()
    room = MockRoom()
    event = MockEvent()
    thread_root = "$thread_root"

    # Mock room_send to track calls
    send_calls = []

    async def mock_room_send(*args, **kwargs):
        send_calls.append(kwargs)
        return MagicMock(transport_response=MagicMock(ok=True))

    client.room_send = mock_room_send

    # Send progress update
    await send_progress_update(client, room, event, thread_root, 5, 20)

    # Verify the call was made
    assert len(send_calls) == 1
    assert "⏳ Working... (step 5/20)" in send_calls[0]['content']['body']


# Test Phase 2.3.2: Queue Notifications

@pytest.mark.asyncio
async def test_send_queue_notification():
    """Test queue notification is sent when limits exceeded."""
    client = MockClient()
    room = MockRoom()
    event = MockEvent()
    thread_root = "$thread_root"

    # Create a conversation manager with low limits
    conv_manager = ConversationManager(max_concurrent=2, max_per_user=1)

    # Mock room_send to track calls
    send_calls = []

    async def mock_room_send(*args, **kwargs):
        send_calls.append(kwargs)
        return MagicMock(transport_response=MagicMock(ok=True))

    client.room_send = mock_room_send

    # Fill up capacity
    await conv_manager.start_conversation("$thread1", "@user1:matrix.org", room.room_id)
    await conv_manager.start_conversation("$thread2", "@user2:matrix.org", room.room_id)

    # Send queue notification
    await send_queue_notification(client, room, event, thread_root, conv_manager)

    # Verify notification was sent
    assert len(send_calls) == 1
    body = send_calls[0]['content']['body']
    assert "🚦" in body
    assert "capacity" in body.lower() or "limit" in body.lower()


# Test Phase 3.1: Session Pooling

@pytest.mark.asyncio
async def test_openai_session_pooling():
    """Test that OpenAI session is reused across calls."""
    # Get session twice
    session1 = await get_openai_session()
    session2 = await get_openai_session()

    # Should be the same session instance
    assert session1 is session2

    # Cleanup
    await close_openai_session()


@pytest.mark.asyncio
async def test_openai_session_close():
    """Test that OpenAI session can be closed properly."""
    session = await get_openai_session()
    assert not session.closed

    await close_openai_session()
    assert session.closed


# Test Phase 3.2: Command Registry Versioning

@pytest.mark.asyncio
async def test_command_registry_versioning():
    """Test that command registry uses versioning for safe reloads."""
    from bot.commands import get_registry

    registry = get_registry()
    initial_version = registry._version

    # Perform reload
    await registry.reload_commands()

    # Version should increment
    assert registry._version == initial_version + 1

    # Old version should be saved
    assert len(registry._old_versions) > 0


@pytest.mark.asyncio
async def test_command_registry_cleanup():
    """Test that old versions are cleaned up after grace period."""
    from bot.commands import get_registry

    registry = get_registry()
    initial_version = registry._version

    # Perform reload
    await registry.reload_commands()

    # Old version should be present
    old_versions_count = len(registry._old_versions)
    assert old_versions_count > 0

    # Wait less than grace period
    await asyncio.sleep(0.1)

    # Old version should still be present
    assert len(registry._old_versions) == old_versions_count

    # Note: We don't wait 30 seconds in the test for full cleanup
    # as that would make tests too slow


# Integration test

@pytest.mark.asyncio
async def test_conversation_manager_integration():
    """Test conversation manager integration with handlers."""
    from bot.conversation_manager import ConversationManager, ConversationStatus

    conv_manager = ConversationManager(max_concurrent=5, max_per_user=2)

    # Start conversation
    conv1 = await conv_manager.start_conversation(
        thread_root_id="$thread1",
        user_id="@user:matrix.org",
        room_id="!room:matrix.org"
    )

    assert conv1 is not None
    assert conv1.status == ConversationStatus.ACTIVE

    # Get active conversations
    active = await conv_manager.get_active_conversations()
    assert len(active) == 1

    # End conversation
    result = await conv_manager.end_conversation(
        conv1.id,
        ConversationStatus.COMPLETED
    )

    assert result is True

    # Should be no active conversations now
    active = await conv_manager.get_active_conversations()
    assert len(active) == 0
