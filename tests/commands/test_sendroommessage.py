"""Tests for the sendroommessage command."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.commands.sendroommessage import sendroommessage_handler


@pytest.mark.asyncio
async def test_sendroommessage_no_matrix_context():
    """Test sendroommessage without Matrix context."""
    result = await sendroommessage_handler(
        room_id="!test:example.com",
        message="Hello, room!"
    )
    assert result is not None
    assert "Error" in result
    assert "Matrix context" in result


@pytest.mark.asyncio
async def test_sendroommessage_empty_room_id():
    """Test sendroommessage with empty room ID."""
    mock_context = {"client": object()}
    result = await sendroommessage_handler(
        room_id="",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Room ID cannot be empty" in result


@pytest.mark.asyncio
async def test_sendroommessage_empty_message():
    """Test sendroommessage with empty message."""
    mock_context = {"client": object()}
    result = await sendroommessage_handler(
        room_id="!test:example.com",
        message="",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Message cannot be empty" in result


@pytest.mark.asyncio
async def test_sendroommessage_whitespace_only_room_id():
    """Test sendroommessage with whitespace-only room ID."""
    mock_context = {"client": object()}
    result = await sendroommessage_handler(
        room_id="   ",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Room ID cannot be empty" in result


@pytest.mark.asyncio
async def test_sendroommessage_whitespace_only_message():
    """Test sendroommessage with whitespace-only message."""
    mock_context = {"client": object()}
    result = await sendroommessage_handler(
        room_id="!test:example.com",
        message="   ",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Message cannot be empty" in result


@pytest.mark.asyncio
async def test_sendroommessage_message_too_long():
    """Test sendroommessage with message exceeding length limit."""
    mock_context = {"client": object()}
    long_message = "a" * 4001  # Exceeds 4000 character limit
    result = await sendroommessage_handler(
        room_id="!test:example.com",
        message=long_message,
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "too long" in result


@pytest.mark.asyncio
async def test_sendroommessage_no_client_in_context():
    """Test sendroommessage with Matrix context but no client."""
    mock_context = {"room": object(), "event": object()}
    result = await sendroommessage_handler(
        room_id="!test:example.com",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "client not available" in result


@pytest.mark.asyncio
async def test_sendroommessage_invalid_room_id_format():
    """Test sendroommessage with invalid room ID format (doesn't start with !)."""
    mock_context = {"client": object()}
    result = await sendroommessage_handler(
        room_id="test:example.com",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Invalid room ID format" in result
    assert "!" in result


@pytest.mark.asyncio
async def test_sendroommessage_strips_whitespace():
    """Test that sendroommessage strips leading/trailing whitespace."""
    mock_client = MagicMock()
    mock_client.room_send = AsyncMock()
    mock_context = {"client": mock_client}

    result = await sendroommessage_handler(
        room_id="  !test:example.com  ",
        message="  Hello!  ",
        matrix_context=mock_context
    )
    assert result is not None
    assert "sent successfully" in result
    assert "!test:example.com" in result

    # Verify room_send was called with stripped values
    mock_client.room_send.assert_called_once()
    call_kwargs = mock_client.room_send.call_args[1]
    assert call_kwargs["room_id"] == "!test:example.com"
    assert call_kwargs["content"]["body"] == "Hello!"


@pytest.mark.asyncio
async def test_sendroommessage_valid_at_length_limit():
    """Test sendroommessage with message exactly at 4000 character limit."""
    mock_client = MagicMock()
    mock_client.room_send = AsyncMock()
    mock_context = {"client": mock_client}

    message = "a" * 4000  # Exactly 4000 characters
    result = await sendroommessage_handler(
        room_id="!test:example.com",
        message=message,
        matrix_context=mock_context
    )
    assert result is not None
    # Should not error about length
    assert "too long" not in result.lower()
    assert "sent successfully" in result


@pytest.mark.asyncio
async def test_sendroommessage_success():
    """Test successful message sending to a room."""
    mock_client = MagicMock()
    mock_client.room_send = AsyncMock()
    mock_context = {"client": mock_client}

    result = await sendroommessage_handler(
        room_id="!test:example.com",
        message="Hello, room!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "sent successfully" in result
    assert "!test:example.com" in result

    # Verify room_send was called with correct parameters
    mock_client.room_send.assert_called_once()
    call_kwargs = mock_client.room_send.call_args[1]
    assert call_kwargs["room_id"] == "!test:example.com"
    assert call_kwargs["message_type"] == "m.room.message"
    assert call_kwargs["content"]["msgtype"] == "m.text"
    assert call_kwargs["content"]["body"] == "Hello, room!"


@pytest.mark.asyncio
async def test_sendroommessage_client_exception():
    """Test sendroommessage when client.room_send raises an exception."""
    mock_client = MagicMock()
    mock_client.room_send = AsyncMock(side_effect=Exception("Network error"))
    mock_context = {"client": mock_client}

    result = await sendroommessage_handler(
        room_id="!test:example.com",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error sending message" in result
    assert "Network error" in result
