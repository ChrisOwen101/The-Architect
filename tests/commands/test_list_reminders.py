"""Tests for the list_reminders command."""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from bot.commands.list_reminders import list_reminders_handler
from bot.reminder_scheduler import Reminder


@pytest.mark.asyncio
class TestListRemindersHandler:
    """Tests for the list_reminders_handler function."""

    async def test_list_reminders_without_matrix_context(self):
        """Test that list_reminders fails without Matrix context."""
        result = await list_reminders_handler()
        assert result is not None
        assert "Error" in result
        assert "Matrix context" in result

    async def test_list_reminders_no_scheduler_available(self):
        """Test error when scheduler is not available."""
        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=None):
            result = await list_reminders_handler(matrix_context=mock_context)

        assert result is not None
        assert "Error" in result
        assert "scheduler is not available" in result

    async def test_list_reminders_empty(self):
        """Test listing reminders when user has none."""
        # Mock scheduler with no reminders
        mock_scheduler = AsyncMock()
        mock_scheduler.list_reminders = AsyncMock(return_value=[])

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await list_reminders_handler(matrix_context=mock_context)

        assert result is not None
        assert "no scheduled reminders" in result.lower()

    async def test_list_reminders_with_reminders(self):
        """Test listing reminders when user has some."""
        # Create mock reminders
        now = time.time()
        reminders = [
            Reminder(
                id='reminder-1',
                scheduled_time=now + 300,  # 5 minutes from now
                message='Test reminder 1',
                room_id='!test:matrix.org',
                thread_root_id='$thread1',
                created_by='@user:matrix.org',
                created_at=now - 100
            ),
            Reminder(
                id='reminder-2',
                scheduled_time=now + 7200,  # 2 hours from now
                message='Test reminder 2',
                room_id='!other:matrix.org',
                thread_root_id='$thread2',
                created_by='@user:matrix.org',
                created_at=now - 200
            )
        ]

        # Mock scheduler
        mock_scheduler = AsyncMock()
        mock_scheduler.list_reminders = AsyncMock(return_value=reminders)

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await list_reminders_handler(matrix_context=mock_context)

        assert result is not None
        assert "scheduled reminders (2)" in result.lower()
        assert "Test reminder 1" in result
        assert "Test reminder 2" in result
        assert "reminder-1" in result
        assert "reminder-2" in result
        # Verify scheduler was called with user_id
        mock_scheduler.list_reminders.assert_called_once_with(user_id='@user:matrix.org')

    async def test_list_reminders_time_formatting(self):
        """Test that time remaining is formatted correctly."""
        # Create mock reminder with specific time
        now = time.time()
        reminders = [
            Reminder(
                id='reminder-1',
                scheduled_time=now + 3665,  # 1h 1m 5s from now
                message='Test reminder',
                room_id='!test:matrix.org',
                thread_root_id='$thread1',
                created_by='@user:matrix.org',
                created_at=now
            )
        ]

        # Mock scheduler
        mock_scheduler = AsyncMock()
        mock_scheduler.list_reminders = AsyncMock(return_value=reminders)

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await list_reminders_handler(matrix_context=mock_context)

        assert result is not None
        # Check that time is formatted (exact format may vary slightly)
        assert "1h" in result
        assert "1m" in result

    async def test_list_reminders_overdue(self):
        """Test that overdue reminders are marked correctly."""
        # Create mock overdue reminder
        now = time.time()
        reminders = [
            Reminder(
                id='reminder-1',
                scheduled_time=now - 60,  # 1 minute ago
                message='Overdue reminder',
                room_id='!test:matrix.org',
                thread_root_id='$thread1',
                created_by='@user:matrix.org',
                created_at=now - 100
            )
        ]

        # Mock scheduler
        mock_scheduler = AsyncMock()
        mock_scheduler.list_reminders = AsyncMock(return_value=reminders)

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await list_reminders_handler(matrix_context=mock_context)

        assert result is not None
        assert "Due now" in result or "pending delivery" in result.lower()
