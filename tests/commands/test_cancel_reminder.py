"""Tests for the cancel_reminder command."""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from bot.commands.cancel_reminder import cancel_reminder_handler
from bot.reminder_scheduler import Reminder


@pytest.mark.asyncio
class TestCancelReminderHandler:
    """Tests for the cancel_reminder_handler function."""

    async def test_cancel_reminder_without_matrix_context(self):
        """Test that cancel_reminder fails without Matrix context."""
        result = await cancel_reminder_handler(reminder_id="test-id")
        assert result is not None
        assert "Error" in result
        assert "Matrix context" in result

    async def test_cancel_reminder_no_scheduler_available(self):
        """Test error when scheduler is not available."""
        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=None):
            result = await cancel_reminder_handler(
                reminder_id="test-id",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Error" in result
        assert "scheduler is not available" in result

    async def test_cancel_reminder_empty_id(self):
        """Test that cancel_reminder fails with empty ID."""
        mock_scheduler = AsyncMock()

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await cancel_reminder_handler(
                reminder_id="",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Error" in result
        assert "cannot be empty" in result.lower()

    async def test_cancel_reminder_not_found(self):
        """Test cancelling a reminder that doesn't exist."""
        # Mock scheduler with no reminders
        mock_scheduler = AsyncMock()
        mock_scheduler.list_reminders = AsyncMock(return_value=[])

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await cancel_reminder_handler(
                reminder_id="nonexistent-id",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Error" in result
        assert "not found" in result.lower()

    async def test_cancel_reminder_wrong_user(self):
        """Test that users cannot cancel other users' reminders."""
        # Create reminder owned by different user
        now = time.time()
        reminders = [
            Reminder(
                id='other-user-reminder',
                scheduled_time=now + 300,
                message='Test reminder',
                room_id='!test:matrix.org',
                thread_root_id='$thread1',
                created_by='@otheruser:matrix.org',
                created_at=now
            )
        ]

        # Mock scheduler
        mock_scheduler = AsyncMock()
        mock_scheduler.list_reminders = AsyncMock(return_value=[])  # Returns empty for requesting user

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await cancel_reminder_handler(
                reminder_id="other-user-reminder",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Error" in result
        assert "not found" in result.lower() or "permission" in result.lower()

    async def test_cancel_reminder_success(self):
        """Test successful reminder cancellation."""
        # Create reminder owned by the user
        now = time.time()
        reminders = [
            Reminder(
                id='reminder-to-cancel',
                scheduled_time=now + 300,
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
        mock_scheduler.cancel_reminder = AsyncMock(return_value=True)

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await cancel_reminder_handler(
                reminder_id="reminder-to-cancel",
                matrix_context=mock_context
            )

        assert result is not None
        assert "cancelled successfully" in result.lower()
        assert "reminder-to-cancel" in result
        # Verify scheduler methods were called
        mock_scheduler.list_reminders.assert_called_once_with(user_id='@user:matrix.org')
        mock_scheduler.cancel_reminder.assert_called_once_with("reminder-to-cancel")

    async def test_cancel_reminder_scheduler_failure(self):
        """Test handling of scheduler failure during cancellation."""
        # Create reminder
        now = time.time()
        reminders = [
            Reminder(
                id='reminder-id',
                scheduled_time=now + 300,
                message='Test reminder',
                room_id='!test:matrix.org',
                thread_root_id='$thread1',
                created_by='@user:matrix.org',
                created_at=now
            )
        ]

        # Mock scheduler that returns False on cancel
        mock_scheduler = AsyncMock()
        mock_scheduler.list_reminders = AsyncMock(return_value=reminders)
        mock_scheduler.cancel_reminder = AsyncMock(return_value=False)

        mock_context = {
            'client': AsyncMock(),
            'room': MagicMock(room_id='!test:matrix.org'),
            'event': MagicMock(sender='@user:matrix.org')
        }

        with patch('bot.reminder_scheduler.get_scheduler', return_value=mock_scheduler):
            result = await cancel_reminder_handler(
                reminder_id="reminder-id",
                matrix_context=mock_context
            )

        assert result is not None
        assert "Error" in result or "Failed" in result
