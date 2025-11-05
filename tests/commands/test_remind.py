"""Tests for the remind command."""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from bot.commands.remind import remind_handler, parse_time_delta


class TestParseTimeDelta:
    """Tests for the parse_time_delta helper function."""

    def test_parse_seconds(self):
        """Test parsing seconds format."""
        assert parse_time_delta('30s') == 30
        assert parse_time_delta('45sec') == 45
        assert parse_time_delta('60seconds') == 60
        assert parse_time_delta('1second') == 1

    def test_parse_minutes(self):
        """Test parsing minutes format."""
        assert parse_time_delta('5m') == 300
        assert parse_time_delta('10min') == 600
        assert parse_time_delta('15minutes') == 900
        assert parse_time_delta('1minute') == 60

    def test_parse_hours(self):
        """Test parsing hours format."""
        assert parse_time_delta('2h') == 7200
        assert parse_time_delta('3hr') == 10800
        assert parse_time_delta('4hours') == 14400
        assert parse_time_delta('1hour') == 3600

    def test_parse_days(self):
        """Test parsing days format."""
        assert parse_time_delta('1d') == 86400
        assert parse_time_delta('2day') == 172800
        assert parse_time_delta('3days') == 259200

    def test_parse_invalid_format(self):
        """Test parsing invalid formats."""
        assert parse_time_delta('invalid') is None
        assert parse_time_delta('5') is None
        assert parse_time_delta('m5') is None
        assert parse_time_delta('') is None
        assert parse_time_delta('5x') is None

    def test_parse_case_insensitive(self):
        """Test that parsing is case insensitive."""
        assert parse_time_delta('5M') == 300
        assert parse_time_delta('2H') == 7200
        assert parse_time_delta('30S') == 30

    def test_parse_with_whitespace(self):
        """Test parsing with whitespace."""
        assert parse_time_delta('  5m  ') == 300
        assert parse_time_delta(' 2h ') == 7200


@pytest.mark.asyncio
class TestRemindHandler:
    """Tests for the remind_handler function."""

    async def test_remind_without_matrix_context(self):
        """Test that remind fails without Matrix context."""
        result = await remind_handler(
            delay="5m",
            message="Test reminder"
        )
        assert result is not None
        assert "Error" in result
        assert "Matrix context" in result

    async def test_remind_with_invalid_delay(self):
        """Test that remind fails with invalid delay format."""
        # Mock scheduler
        mock_scheduler = AsyncMock()

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await remind_handler(
                delay="invalid",
                message="Test reminder",
                matrix_context=mock_context
            )
        assert result is not None
        assert "Invalid time format" in result

    async def test_remind_with_too_short_delay(self):
        """Test that remind fails with delay less than 10 seconds."""
        # Mock scheduler
        mock_scheduler = AsyncMock()

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await remind_handler(
                delay="5s",
                message="Test reminder",
                matrix_context=mock_context
            )
        assert result is not None
        assert "at least 10 seconds" in result

    async def test_remind_with_too_long_delay(self):
        """Test that remind fails with delay longer than 30 days."""
        # Mock scheduler
        mock_scheduler = AsyncMock()

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await remind_handler(
                delay="31d",
                message="Test reminder",
                matrix_context=mock_context
            )
        assert result is not None
        assert "cannot exceed 30 days" in result

    async def test_remind_success_current_room(self):
        """Test successful reminder creation in current room."""
        # Mock scheduler
        mock_scheduler = AsyncMock()
        mock_scheduler.add_reminder = AsyncMock()

        # Mock context
        mock_event = MagicMock(
            sender='@user:matrix.org',
            event_id='$event123'
        )
        mock_event.source = {
            'content': {
                'm.relates_to': {}
            }
        }

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': mock_event
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await remind_handler(
                delay="5m",
                message="Test reminder",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Reminder set" in result
        assert "5 minute" in result.lower()
        assert "Test reminder" in result
        mock_scheduler.add_reminder.assert_called_once()

    async def test_remind_success_different_room(self):
        """Test successful reminder creation in different room."""
        # Mock scheduler
        mock_scheduler = AsyncMock()
        mock_scheduler.add_reminder = AsyncMock()

        # Mock context
        mock_event = MagicMock(
            sender='@user:matrix.org',
            event_id='$event123'
        )
        mock_event.source = {
            'content': {
                'm.relates_to': {}
            }
        }

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!current:matrix.org'),
            'event': mock_event
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await remind_handler(
                delay="2h",
                message="Test reminder",
                room_id="!other:matrix.org",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Reminder scheduled" in result
        assert "2 hour" in result.lower()
        assert "!other:matrix.org" in result
        assert "Test reminder" in result

        # Verify scheduler was called with correct room
        call_args = mock_scheduler.add_reminder.call_args
        assert call_args.kwargs['room_id'] == "!other:matrix.org"

    async def test_remind_with_thread_context(self):
        """Test reminder creation in a thread."""
        # Mock scheduler
        mock_scheduler = AsyncMock()
        mock_scheduler.add_reminder = AsyncMock()

        # Mock event in a thread
        mock_event = MagicMock(
            sender='@user:matrix.org',
            event_id='$event123'
        )
        mock_event.source = {
            'content': {
                'm.relates_to': {
                    'rel_type': 'm.thread',
                    'event_id': '$thread_root'
                }
            }
        }

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': mock_event
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await remind_handler(
                delay="30s",
                message="Test reminder",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Reminder set" in result

        # Verify thread root was passed to scheduler
        call_args = mock_scheduler.add_reminder.call_args
        assert call_args.kwargs['thread_root_id'] == '$thread_root'

    async def test_remind_no_scheduler_available(self):
        """Test error when scheduler is not available."""
        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=None):
            result = await remind_handler(
                delay="5m",
                message="Test reminder",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Error" in result
        assert "scheduler is not available" in result

    async def test_remind_scheduler_raises_exception(self):
        """Test error handling when scheduler raises exception."""
        # Mock scheduler that raises exception
        mock_scheduler = AsyncMock()
        mock_scheduler.add_reminder = AsyncMock(side_effect=Exception("Database error"))

        # Mock context
        mock_event = MagicMock(
            sender='@user:matrix.org',
            event_id='$event123'
        )
        mock_event.source = {
            'content': {
                'm.relates_to': {}
            }
        }

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': mock_event
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await remind_handler(
                delay="5m",
                message="Test reminder",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Failed to schedule reminder" in result
        assert "Database error" in result

    async def test_remind_complex_duration_display(self):
        """Test that complex durations are displayed correctly."""
        # Mock scheduler
        mock_scheduler = AsyncMock()
        mock_scheduler.add_reminder = AsyncMock()

        # Mock context
        mock_event = MagicMock(
            sender='@user:matrix.org',
            event_id='$event123'
        )
        mock_event.source = {
            'content': {
                'm.relates_to': {}
            }
        }

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': mock_event
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            # Test 1 day, 2 hours, 30 minutes
            result = await remind_handler(
                delay="1d",
                message="Test reminder",
                matrix_context=mock_context
            )

        assert result is not None
        assert "1 day" in result
