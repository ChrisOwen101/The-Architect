"""Reminder scheduler for scheduling and delivering messages at specific times.

This module provides a persistent reminder system that:
- Stores reminders in JSON format
- Runs a background task to check for due reminders
- Delivers messages to rooms or DMs at scheduled times
- Survives bot restarts by persisting to disk
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from nio import AsyncClient

logger = logging.getLogger(__name__)

REMINDERS_FILE = Path("data/reminders.json")


@dataclass
class Reminder:
    """Represents a scheduled reminder."""
    id: str
    scheduled_time: float  # Unix timestamp
    message: str
    room_id: str
    thread_root_id: Optional[str]
    created_by: str
    created_at: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Reminder:
        """Create Reminder from dictionary."""
        return cls(**data)


class ReminderScheduler:
    """Manages scheduled reminders with persistence."""

    def __init__(self):
        self._reminders: dict[str, Reminder] = {}
        self._client: Optional[AsyncClient] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._load_reminders()

    def set_client(self, client: AsyncClient) -> None:
        """Set the Matrix client for sending messages."""
        self._client = client

    def _load_reminders(self) -> None:
        """Load reminders from disk."""
        if not REMINDERS_FILE.exists():
            logger.info("No reminders file found, starting fresh")
            return

        try:
            with open(REMINDERS_FILE, 'r') as f:
                data = json.load(f)
                self._reminders = {
                    reminder_id: Reminder.from_dict(reminder_data)
                    for reminder_id, reminder_data in data.items()
                }
            logger.info(f"Loaded {len(self._reminders)} reminder(s) from disk")
        except Exception:
            logger.exception("Failed to load reminders from disk")
            self._reminders = {}

    def _save_reminders(self) -> None:
        """Save reminders to disk."""
        try:
            # Ensure data directory exists
            REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Save to file
            with open(REMINDERS_FILE, 'w') as f:
                data = {
                    reminder_id: reminder.to_dict()
                    for reminder_id, reminder in self._reminders.items()
                }
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self._reminders)} reminder(s) to disk")
        except Exception:
            logger.exception("Failed to save reminders to disk")

    async def add_reminder(
        self,
        reminder_id: str,
        scheduled_time: float,
        message: str,
        room_id: str,
        thread_root_id: Optional[str],
        created_by: str
    ) -> None:
        """Add a new reminder.

        Args:
            reminder_id: Unique identifier for the reminder
            scheduled_time: Unix timestamp when to send the message
            message: Message to send
            room_id: Room ID to send message to
            thread_root_id: Optional thread root for threaded reply
            created_by: User ID who created the reminder
        """
        async with self._lock:
            reminder = Reminder(
                id=reminder_id,
                scheduled_time=scheduled_time,
                message=message,
                room_id=room_id,
                thread_root_id=thread_root_id,
                created_by=created_by,
                created_at=time.time()
            )
            self._reminders[reminder_id] = reminder
            self._save_reminders()
            logger.info(
                f"Added reminder {reminder_id} scheduled for "
                f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(scheduled_time))}"
            )

    async def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a reminder by ID.

        Args:
            reminder_id: ID of the reminder to cancel

        Returns:
            True if reminder was found and cancelled, False otherwise
        """
        async with self._lock:
            if reminder_id in self._reminders:
                del self._reminders[reminder_id]
                self._save_reminders()
                logger.info(f"Cancelled reminder {reminder_id}")
                return True
            return False

    async def list_reminders(self, user_id: Optional[str] = None) -> list[Reminder]:
        """List all reminders, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of reminders
        """
        async with self._lock:
            reminders = list(self._reminders.values())
            if user_id:
                reminders = [r for r in reminders if r.created_by == user_id]
            # Sort by scheduled time
            reminders.sort(key=lambda r: r.scheduled_time)
            return reminders

    async def _check_and_send_reminders(self) -> None:
        """Check for due reminders and send them."""
        if not self._client:
            logger.warning("No Matrix client set, cannot send reminders")
            return

        now = time.time()
        due_reminders = []

        # Find due reminders
        async with self._lock:
            for reminder in list(self._reminders.values()):
                if reminder.scheduled_time <= now:
                    due_reminders.append(reminder)
                    # Remove from active reminders immediately
                    del self._reminders[reminder.id]

            # Save updated state
            if due_reminders:
                self._save_reminders()

        # Send due reminders (outside lock to avoid blocking)
        for reminder in due_reminders:
            try:
                # Build message content
                content = {
                    "msgtype": "m.text",
                    "body": f"🔔 Reminder: {reminder.message}"
                }

                # Add thread relation if this is a threaded reminder
                if reminder.thread_root_id:
                    content["m.relates_to"] = {
                        "rel_type": "m.thread",
                        "event_id": reminder.thread_root_id,
                        "is_falling_back": True
                    }

                # Send message
                await self._client.room_send(
                    room_id=reminder.room_id,
                    message_type="m.room.message",
                    content=content
                )
                logger.info(
                    f"Sent reminder {reminder.id} to room {reminder.room_id}"
                )
            except Exception:
                logger.exception(
                    f"Failed to send reminder {reminder.id}, will not retry"
                )

    async def _run_scheduler(self) -> None:
        """Background task that checks for due reminders."""
        logger.info("Reminder scheduler started")
        try:
            while not self._stop_event.is_set():
                try:
                    await self._check_and_send_reminders()
                except Exception:
                    logger.exception("Error in reminder scheduler loop")

                # Check every 5 seconds
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=5.0
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    pass  # Continue loop
        finally:
            logger.info("Reminder scheduler stopped")

    def start(self) -> None:
        """Start the reminder scheduler background task."""
        if self._task and not self._task.done():
            logger.warning("Reminder scheduler already running")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("Reminder scheduler task started")

    def stop(self) -> None:
        """Stop the reminder scheduler background task."""
        if not self._task or self._task.done():
            logger.warning("Reminder scheduler not running")
            return

        self._stop_event.set()
        logger.info("Reminder scheduler stop requested")


# Global scheduler instance
_scheduler: Optional[ReminderScheduler] = None


def get_scheduler() -> Optional[ReminderScheduler]:
    """Get the global reminder scheduler instance."""
    return _scheduler


def set_scheduler(scheduler: ReminderScheduler) -> None:
    """Set the global reminder scheduler instance."""
    global _scheduler
    _scheduler = scheduler
