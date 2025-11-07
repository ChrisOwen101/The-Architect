"""Tests for the after command."""
from __future__ import annotations
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bot.commands.after import after_handler


@pytest.mark.asyncio
async def test_after_success_room_id():
    """Test successful message scheduling with room ID."""
    # Mock scheduler
    mock_scheduler = MagicMock()
    mock_scheduler.add_reminder = AsyncMock()

    # Mock matrix context
    mock_event = MagicMock()
    mock_event.sender = "@user:matrix.org"
    mock_event.event_id = "$event123"
    mock_event.source = {
        'content': {
            'm.relates_to': {}
        }
    }

    mock_room = MagicMock()
    mock_room.room_id = "!current:matrix.org"

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    # Patch get_scheduler to return mock
    with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
        result = await after_handler(
            seconds=60,
            target="!target:matrix.org",
            message="Test message",
            matrix_context=matrix_context
        )

    # Verify result
    assert result is not None
    assert "✅ Message scheduled!" in result
    assert "!target:matrix.org" in result
    assert "Test message" in result
    assert "1 minute" in result

    # Verify scheduler was called
    mock_scheduler.add_reminder.assert_called_once()
    call_args = mock_scheduler.add_reminder.call_args
    assert call_args.kwargs['message'] == "Test message"
    assert call_args.kwargs['room_id'] == "!target:matrix.org"
    assert call_args.kwargs['created_by'] == "@user:matrix.org"
    # Verify scheduled_time is approximately 60 seconds from now
    assert abs(call_args.kwargs['scheduled_time'] - (time.time() + 60)) < 2


@pytest.mark.asyncio
async def test_after_user_mention_not_supported():
    """Test that user mentions return error message."""
    mock_scheduler = MagicMock()
    mock_event = MagicMock()
    mock_event.sender = "@user:matrix.org"
    mock_room = MagicMock()

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
        result = await after_handler(
            seconds=60,
            target="@bob:matrix.org",
            message="Test message",
            matrix_context=matrix_context
        )

    assert "❌" in result
    assert "User mentions are not yet supported" in result


@pytest.mark.asyncio
async def test_after_invalid_target():
    """Test that invalid target format returns error."""
    mock_scheduler = MagicMock()
    mock_event = MagicMock()
    mock_room = MagicMock()

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
        result = await after_handler(
            seconds=60,
            target="invalid_target",
            message="Test message",
            matrix_context=matrix_context
        )

    assert "❌ Invalid target format" in result


@pytest.mark.asyncio
async def test_after_seconds_too_low():
    """Test that seconds below minimum returns error."""
    mock_scheduler = MagicMock()
    mock_event = MagicMock()
    mock_room = MagicMock()

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
        result = await after_handler(
            seconds=5,
            target="!room:matrix.org",
            message="Test message",
            matrix_context=matrix_context
        )

    assert "❌ Delay must be at least 10 seconds" in result


@pytest.mark.asyncio
async def test_after_seconds_too_high():
    """Test that seconds above maximum returns error."""
    mock_scheduler = MagicMock()
    mock_event = MagicMock()
    mock_room = MagicMock()

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
        result = await after_handler(
            seconds=31 * 86400,  # 31 days
            target="!room:matrix.org",
            message="Test message",
            matrix_context=matrix_context
        )

    assert "❌ Delay cannot exceed 30 days" in result


@pytest.mark.asyncio
async def test_after_no_matrix_context():
    """Test that missing matrix context returns error."""
    result = await after_handler(
        seconds=60,
        target="!room:matrix.org",
        message="Test message",
        matrix_context=None
    )

    assert "❌ Error: This command requires Matrix context" in result


@pytest.mark.asyncio
async def test_after_no_scheduler():
    """Test that missing scheduler returns error."""
    mock_event = MagicMock()
    mock_room = MagicMock()

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    with patch('bot.reminder_scheduler.get_scheduler', return_value=None):
        result = await after_handler(
            seconds=60,
            target="!room:matrix.org",
            message="Test message",
            matrix_context=matrix_context
        )

    assert "❌ Error: Message scheduler is not available" in result


@pytest.mark.asyncio
async def test_after_scheduler_exception():
    """Test handling of scheduler exceptions."""
    mock_scheduler = MagicMock()
    mock_scheduler.add_reminder = AsyncMock(side_effect=Exception("Database error"))

    mock_event = MagicMock()
    mock_event.sender = "@user:matrix.org"
    mock_event.event_id = "$event123"
    mock_event.source = {'content': {'m.relates_to': {}}}
    mock_room = MagicMock()

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
        result = await after_handler(
            seconds=60,
            target="!room:matrix.org",
            message="Test message",
            matrix_context=matrix_context
        )

    assert "❌ Failed to schedule message: Database error" in result


@pytest.mark.asyncio
async def test_after_duration_formatting():
    """Test that duration is formatted correctly for various time periods."""
    mock_scheduler = MagicMock()
    mock_scheduler.add_reminder = AsyncMock()

    mock_event = MagicMock()
    mock_event.sender = "@user:matrix.org"
    mock_event.event_id = "$event123"
    mock_event.source = {'content': {'m.relates_to': {}}}
    mock_room = MagicMock()

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    # Test various durations
    test_cases = [
        (10, "10 seconds"),
        (60, "1 minute"),
        (120, "2 minutes"),
        (3600, "1 hour"),
        (3660, "1 hour, 1 minute"),
        (86400, "1 day"),
        (90061, "1 day, 1 hour, 1 minute, 1 second"),
    ]

    for seconds, expected_duration in test_cases:
        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await after_handler(
                seconds=seconds,
                target="!room:matrix.org",
                message="Test",
                matrix_context=matrix_context
            )

        assert expected_duration in result, f"Expected '{expected_duration}' in result for {seconds}s"


@pytest.mark.asyncio
async def test_after_in_thread():
    """Test that messages scheduled from within a thread maintain thread context."""
    mock_scheduler = MagicMock()
    mock_scheduler.add_reminder = AsyncMock()

    # Mock event in a thread
    mock_event = MagicMock()
    mock_event.sender = "@user:matrix.org"
    mock_event.event_id = "$event123"
    mock_event.source = {
        'content': {
            'm.relates_to': {
                'rel_type': 'm.thread',
                'event_id': '$thread_root'
            }
        }
    }
    mock_room = MagicMock()

    matrix_context = {
        'client': MagicMock(),
        'room': mock_room,
        'event': mock_event
    }

    with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
        result = await after_handler(
            seconds=60,
            target="!room:matrix.org",
            message="Test message",
            matrix_context=matrix_context
        )

    # Verify thread_root_id was passed to scheduler
    call_args = mock_scheduler.add_reminder.call_args
    assert call_args.kwargs['thread_root_id'] == '$thread_root'
    assert "✅ Message scheduled!" in result
