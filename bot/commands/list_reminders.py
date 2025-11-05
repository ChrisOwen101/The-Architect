"""List reminders command - Display all scheduled reminders.

This command shows all reminders created by the user, sorted by scheduled time.
"""
from __future__ import annotations
import time
from typing import Optional
from . import command


@command(
    name="list_reminders",
    description="List all your scheduled reminders, sorted by scheduled time."
)
async def list_reminders_handler(
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """List all reminders created by the current user.

    Args:
        matrix_context: Matrix context containing client, room, and event

    Returns:
        List of reminders or message if no reminders found

    Examples:
        >>> # User: "@architect list_reminders"
        >>> # Returns: "📋 Your scheduled reminders (3):..."
    """
    from ..reminder_scheduler import get_scheduler

    # Validate matrix context
    if not matrix_context:
        return "❌ Error: This command requires Matrix context."

    # Get scheduler
    scheduler = get_scheduler()
    if not scheduler:
        return "❌ Error: Reminder scheduler is not available. Please contact the bot administrator."

    # Get user ID
    event = matrix_context.get('event')
    if not event:
        return "❌ Error: Could not determine user ID."

    user_id = event.sender

    # Get reminders for this user
    reminders = await scheduler.list_reminders(user_id=user_id)

    if not reminders:
        return "📋 You have no scheduled reminders."

    # Build response
    lines = [f"📋 Your scheduled reminders ({len(reminders)}):"]
    lines.append("")

    for idx, reminder in enumerate(reminders, 1):
        # Calculate time until reminder
        now = time.time()
        seconds_until = int(reminder.scheduled_time - now)

        if seconds_until < 0:
            time_str = "⏰ Due now (pending delivery)"
        else:
            # Build human-readable duration
            duration_parts = []
            remaining = seconds_until

            days = remaining // 86400
            if days > 0:
                duration_parts.append(f"{days}d")
                remaining %= 86400

            hours = remaining // 3600
            if hours > 0:
                duration_parts.append(f"{hours}h")
                remaining %= 3600

            minutes = remaining // 60
            if minutes > 0:
                duration_parts.append(f"{minutes}m")
                remaining %= 60

            if remaining > 0 or not duration_parts:
                duration_parts.append(f"{remaining}s")

            time_str = f"⏰ In {' '.join(duration_parts)}"

        # Format scheduled time
        scheduled_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reminder.scheduled_time))

        # Build reminder entry
        lines.append(f"{idx}. {time_str}")
        lines.append(f"   Message: \"{reminder.message}\"")
        lines.append(f"   Scheduled: {scheduled_str}")
        lines.append(f"   Room: {reminder.room_id}")
        lines.append(f"   ID: {reminder.id}")
        lines.append("")

    return "\n".join(lines)
