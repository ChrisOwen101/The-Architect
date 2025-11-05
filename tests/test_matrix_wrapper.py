"""Tests for MatrixClientWrapper - thread-safe Matrix client."""
from __future__ import annotations
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from nio import AsyncClient
from bot.matrix_wrapper import MatrixClientWrapper


@pytest.fixture
def mock_client():
    """Create a mock AsyncClient."""
    client = MagicMock(spec=AsyncClient)
    client.user_id = "@bot:example.com"
    client.device_id = "DEVICEID"

    # Mock async methods
    client.room_send = AsyncMock(return_value=MagicMock(event_id="$event1"))
    client.room_messages = AsyncMock(return_value=MagicMock())
    client.sync = AsyncMock(return_value=MagicMock())
    client.set_displayname = AsyncMock(return_value=MagicMock())
    client.close = AsyncMock(return_value=MagicMock())
    client.whoami = AsyncMock(return_value=MagicMock())

    return client


@pytest.fixture
def wrapped_client(mock_client):
    """Create a MatrixClientWrapper with mock client."""
    return MatrixClientWrapper(mock_client)


@pytest.mark.asyncio
async def test_wrapper_initialization(mock_client):
    """Test creating a MatrixClientWrapper."""
    wrapper = MatrixClientWrapper(mock_client)

    assert wrapper._client == mock_client
    assert wrapper._lock is not None


@pytest.mark.asyncio
async def test_room_send_calls_underlying_client(wrapped_client, mock_client):
    """Test that room_send calls the underlying client."""
    result = await wrapped_client.room_send(
        room_id="!room:example.com",
        message_type="m.room.message",
        content={"body": "test", "msgtype": "m.text"}
    )

    mock_client.room_send.assert_called_once_with(
        "!room:example.com",
        "m.room.message",
        {"body": "test", "msgtype": "m.text"},
        tx_id=None,
        ignore_unverified_devices=False
    )
    assert result.event_id == "$event1"


@pytest.mark.asyncio
async def test_room_messages_calls_underlying_client(wrapped_client, mock_client):
    """Test that room_messages calls the underlying client."""
    await wrapped_client.room_messages(
        room_id="!room:example.com",
        start="token123",
        limit=50
    )

    mock_client.room_messages.assert_called_once_with(
        "!room:example.com",
        "token123",
        end=None,
        direction="b",
        limit=50,
        message_filter=None
    )


@pytest.mark.asyncio
async def test_sync_calls_underlying_client(wrapped_client, mock_client):
    """Test that sync calls the underlying client."""
    await wrapped_client.sync(
        timeout=30000,
        since="sync_token"
    )

    mock_client.sync.assert_called_once_with(
        timeout=30000,
        sync_filter=None,
        since="sync_token",
        full_state=False
    )


@pytest.mark.asyncio
async def test_concurrent_room_send_serialized(wrapped_client, mock_client):
    """Test that concurrent room_send calls are serialized."""
    call_order = []

    async def mock_room_send_with_delay(*args, **kwargs):
        call_order.append("start")
        await asyncio.sleep(0.1)  # Simulate network delay
        call_order.append("end")
        return MagicMock(event_id="$event")

    mock_client.room_send.side_effect = mock_room_send_with_delay

    # Start two concurrent sends
    task1 = asyncio.create_task(
        wrapped_client.room_send(
            "!room:example.com",
            "m.room.message",
            {"body": "msg1"}
        )
    )
    task2 = asyncio.create_task(
        wrapped_client.room_send(
            "!room:example.com",
            "m.room.message",
            {"body": "msg2"}
        )
    )

    await asyncio.gather(task1, task2)

    # Should be serialized: start, end, start, end
    # Not interleaved: start, start, end, end
    assert call_order == ["start", "end", "start", "end"]


@pytest.mark.asyncio
async def test_lock_prevents_simultaneous_access(wrapped_client, mock_client):
    """Test that lock prevents simultaneous access to client."""
    access_count = [0]  # Use list to allow modification in nested function

    async def mock_operation(*args, **kwargs):
        # Check that we're the only one accessing
        assert access_count[0] == 0, "Concurrent access detected!"
        access_count[0] += 1

        await asyncio.sleep(0.05)  # Hold the lock for a bit

        access_count[0] -= 1
        return MagicMock()

    mock_client.room_send.side_effect = mock_operation
    mock_client.sync.side_effect = mock_operation

    # Try concurrent operations
    tasks = [
        wrapped_client.room_send("!room:example.com", "m.room.message", {}),
        wrapped_client.sync(),
        wrapped_client.room_send("!room:example.com", "m.room.message", {}),
    ]

    await asyncio.gather(*tasks)

    # If we get here without assertion error, lock worked correctly


@pytest.mark.asyncio
async def test_attribute_forwarding(wrapped_client, mock_client):
    """Test that non-wrapped attributes are forwarded to client."""
    # Access attributes that aren't explicitly wrapped
    assert wrapped_client.user_id == "@bot:example.com"
    assert wrapped_client.device_id == "DEVICEID"


@pytest.mark.asyncio
async def test_close_is_thread_safe(wrapped_client, mock_client):
    """Test that close method is thread-safe."""
    await wrapped_client.close()

    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_whoami_is_thread_safe(wrapped_client, mock_client):
    """Test that whoami method is thread-safe."""
    await wrapped_client.whoami()

    mock_client.whoami.assert_called_once()


@pytest.mark.asyncio
async def test_set_displayname_is_thread_safe(wrapped_client, mock_client):
    """Test that set_displayname method is thread-safe."""
    await wrapped_client.set_displayname("New Name")

    mock_client.set_displayname.assert_called_once_with("New Name")


@pytest.mark.asyncio
async def test_error_propagation(wrapped_client, mock_client):
    """Test that errors from underlying client are propagated."""
    mock_client.room_send.side_effect = Exception("Network error")

    with pytest.raises(Exception, match="Network error"):
        await wrapped_client.room_send(
            "!room:example.com",
            "m.room.message",
            {}
        )


@pytest.mark.asyncio
async def test_all_methods_proxied_correctly(wrapped_client, mock_client):
    """Test that all wrapped methods proxy correctly."""
    # Test room_send
    await wrapped_client.room_send(
        "!room:example.com",
        "m.room.message",
        {"body": "test"},
        tx_id="tx1",
        ignore_unverified_devices=True
    )
    assert mock_client.room_send.called

    # Test room_messages
    await wrapped_client.room_messages(
        "!room:example.com",
        "start_token",
        end="end_token",
        direction="f",
        limit=100,
        message_filter={"types": ["m.room.message"]}
    )
    assert mock_client.room_messages.called

    # Test sync
    await wrapped_client.sync(
        timeout=10000,
        sync_filter={"room": {"timeline": {"limit": 10}}},
        since="token",
        full_state=True
    )
    assert mock_client.sync.called


@pytest.mark.asyncio
async def test_multiple_concurrent_different_methods(wrapped_client, mock_client):
    """Test concurrent calls to different methods are serialized."""
    results = []

    async def record_call(method_name):
        results.append(f"{method_name}_start")
        await asyncio.sleep(0.05)
        results.append(f"{method_name}_end")
        return MagicMock()

    mock_client.room_send.side_effect = lambda *a, **k: record_call("room_send")
    mock_client.sync.side_effect = lambda *a, **k: record_call("sync")
    mock_client.room_messages.side_effect = lambda *a, **k: record_call("room_messages")

    # Start concurrent calls to different methods
    tasks = [
        wrapped_client.room_send("!room:example.com", "m.room.message", {}),
        wrapped_client.sync(),
        wrapped_client.room_messages("!room:example.com", "token"),
    ]

    await asyncio.gather(*tasks)

    # Each method should complete before the next starts
    # (start and end should be paired)
    for i in range(0, len(results), 2):
        start = results[i]
        end = results[i + 1]
        assert start.endswith("_start")
        assert end.endswith("_end")
        assert start.replace("_start", "") == end.replace("_end", "")
