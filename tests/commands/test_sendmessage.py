"""Tests for the sendmessage command."""
import pytest
from bot.commands.sendmessage import sendmessage_handler


@pytest.mark.asyncio
async def test_sendmessage_no_matrix_context():
    """Test sendmessage without Matrix context."""
    result = await sendmessage_handler(
        recipient="@user:example.com",
        message="Hello, world!"
    )
    assert result is not None
    assert "Error" in result
    assert "Matrix context" in result


@pytest.mark.asyncio
async def test_sendmessage_empty_recipient():
    """Test sendmessage with empty recipient."""
    mock_context = {"client": object()}
    result = await sendmessage_handler(
        recipient="",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Recipient cannot be empty" in result


@pytest.mark.asyncio
async def test_sendmessage_empty_message():
    """Test sendmessage with empty message."""
    mock_context = {"client": object()}
    result = await sendmessage_handler(
        recipient="@user:example.com",
        message="",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Message cannot be empty" in result


@pytest.mark.asyncio
async def test_sendmessage_whitespace_only_recipient():
    """Test sendmessage with whitespace-only recipient."""
    mock_context = {"client": object()}
    result = await sendmessage_handler(
        recipient="   ",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Recipient cannot be empty" in result


@pytest.mark.asyncio
async def test_sendmessage_whitespace_only_message():
    """Test sendmessage with whitespace-only message."""
    mock_context = {"client": object()}
    result = await sendmessage_handler(
        recipient="@user:example.com",
        message="   ",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "Message cannot be empty" in result


@pytest.mark.asyncio
async def test_sendmessage_message_too_long():
    """Test sendmessage with message exceeding length limit."""
    mock_context = {"client": object()}
    long_message = "a" * 4001  # Exceeds 4000 character limit
    result = await sendmessage_handler(
        recipient="@user:example.com",
        message=long_message,
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "too long" in result


@pytest.mark.asyncio
async def test_sendmessage_no_client_in_context():
    """Test sendmessage with Matrix context but no client."""
    mock_context = {"room": object(), "event": object()}
    result = await sendmessage_handler(
        recipient="@user:example.com",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    assert "client not available" in result


@pytest.mark.asyncio
async def test_sendmessage_valid_user_id():
    """Test sendmessage with valid user ID format."""
    mock_context = {"client": object()}
    result = await sendmessage_handler(
        recipient="@alice:matrix.org",
        message="Hello, Alice!",
        matrix_context=mock_context
    )
    assert result is not None
    # Should indicate the message is queued or provide implementation note
    assert "queued" in result.lower() or "note" in result.lower()
    assert "@alice:matrix.org" in result


@pytest.mark.asyncio
async def test_sendmessage_invalid_user_format():
    """Test sendmessage with invalid user format (not a user ID)."""
    mock_context = {"client": object()}
    result = await sendmessage_handler(
        recipient="alice",
        message="Hello!",
        matrix_context=mock_context
    )
    assert result is not None
    assert "Error" in result
    # Should suggest using proper user ID format
    assert "@" in result


@pytest.mark.asyncio
async def test_sendmessage_strips_whitespace():
    """Test that sendmessage strips leading/trailing whitespace."""
    mock_context = {"client": object()}
    result = await sendmessage_handler(
        recipient="  @user:example.com  ",
        message="  Hello!  ",
        matrix_context=mock_context
    )
    assert result is not None
    # Should process successfully (queued or noted)
    assert "@user:example.com" in result
    assert "Error: Recipient cannot be empty" not in result
    assert "Error: Message cannot be empty" not in result


@pytest.mark.asyncio
async def test_sendmessage_valid_at_length_limit():
    """Test sendmessage with message exactly at 4000 character limit."""
    mock_context = {"client": object()}
    message = "a" * 4000  # Exactly 4000 characters
    result = await sendmessage_handler(
        recipient="@user:example.com",
        message=message,
        matrix_context=mock_context
    )
    assert result is not None
    # Should not error about length
    assert "too long" not in result.lower()
