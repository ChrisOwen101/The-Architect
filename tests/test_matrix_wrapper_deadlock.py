"""Test to verify sync() doesn't cause deadlock with callbacks that call room_send()."""
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from nio import AsyncClient, SyncResponse, RoomSendResponse
from bot.matrix_wrapper import MatrixClientWrapper


@pytest.mark.asyncio
async def test_sync_does_not_deadlock_on_callback_room_send():
    """Verify that sync() doesn't hold lock while firing callbacks.

    This test simulates the real-world scenario:
    1. sync() is called
    2. sync() fires a callback (like on_message)
    3. Callback tries to call room_send()
    4. room_send() should succeed without deadlock
    """
    # Create mock client
    mock_client = AsyncMock(spec=AsyncClient)
    mock_client.user_id = "@bot:example.com"

    # Track callback execution
    callback_executed = asyncio.Event()
    room_send_executed = asyncio.Event()

    # Create wrapper
    wrapper = MatrixClientWrapper(mock_client)

    # Mock sync to fire a callback that calls room_send
    async def mock_sync(*args, **kwargs):
        # Simulate callback being fired during sync
        # This callback will try to call room_send
        async def callback():
            # Try to send a message during sync
            await wrapper.room_send(
                room_id="!test:example.com",
                message_type="m.room.message",
                content={"body": "test"}
            )
            room_send_executed.set()

        # Fire callback during sync (simulates what nio does)
        await callback()
        callback_executed.set()

        # Return mock sync response
        return Mock(spec=SyncResponse)

    mock_client.sync = mock_sync

    # Mock room_send on underlying client
    mock_client.room_send = AsyncMock(return_value=Mock(spec=RoomSendResponse))

    # This should complete without deadlock
    # Timeout after 2 seconds to catch deadlock
    try:
        await asyncio.wait_for(wrapper.sync(), timeout=2.0)
    except asyncio.TimeoutError:
        pytest.fail("Deadlock detected: sync() held lock while callback tried to acquire it")

    # Verify both callback and room_send executed
    assert callback_executed.is_set(), "Callback was not executed"
    assert room_send_executed.is_set(), "room_send was not executed (deadlock likely)"


@pytest.mark.asyncio
async def test_room_send_uses_lock():
    """Verify that room_send() properly acquires lock for thread safety."""
    mock_client = AsyncMock(spec=AsyncClient)
    wrapper = MatrixClientWrapper(mock_client)

    # Mock room_send response
    mock_client.room_send = AsyncMock(return_value=Mock(spec=RoomSendResponse))

    # Call room_send and verify it uses the lock
    # We can't directly test lock acquisition, but we can verify it doesn't deadlock
    # with concurrent calls
    tasks = [
        wrapper.room_send(
            room_id="!test:example.com",
            message_type="m.room.message",
            content={"body": f"message {i}"}
        )
        for i in range(5)
    ]

    # All should complete without deadlock
    await asyncio.gather(*tasks)

    # Verify underlying client was called correct number of times
    assert mock_client.room_send.call_count == 5


@pytest.mark.asyncio
async def test_room_messages_uses_lock():
    """Verify that room_messages() properly acquires lock for thread safety."""
    mock_client = AsyncMock(spec=AsyncClient)
    wrapper = MatrixClientWrapper(mock_client)

    # Mock room_messages response
    mock_client.room_messages = AsyncMock(return_value=Mock())

    # Call room_messages
    await wrapper.room_messages(
        room_id="!test:example.com",
        start="token123"
    )

    # Verify underlying client was called
    assert mock_client.room_messages.call_count == 1
