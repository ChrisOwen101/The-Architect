"""Remind command - Schedule messages to be sent at specific times or after delays.

This command allows users to schedule reminder messages that will be delivered
at a specified time or after a delay. Reminders are persistent and survive bot
restarts.

Usage examples:
- "@architect remind --in 5m --message Take a break"
- "@architect remind --in 2h --message Check the deployment"
- "@architect remind --in 30s --room !abc:matrix.org --message Server maintenance"

Time format: <number><unit> where unit is:
- s or sec or seconds: seconds
- m or min or minutes: minutes
- h or hr or hours: hours
- d or day or days: days

**Files modified by this command:**
- bot/main.py: Initializes ReminderScheduler and starts/stops background task
- bot/reminder_scheduler.py: New file containing the scheduler implementation

When removing this command, also remove:
1. The ReminderScheduler initialization in bot/main.py
2. The reminder_scheduler.py file
3. The data/reminders.json file (if you want to delete stored reminders)
"""
from __future__ import annotations
import re
import time
import uuid
from typing import Optional
from . import command


def parse_time_delta(time_str: str) -> Optional[int]:
    """Parse a time string like '5m', '2h', '30s' into seconds.

    Args:
        time_str: Time string with number and unit (e.g., '5m', '2h', '30s')

    Returns:
        Number of seconds, or None if parsing fails

    Examples:
        >>> parse_time_delta('5m')
        300
        >>> parse_time_delta('2h')
        7200
        >>> parse_time_delta('30s')
        30
        >>> parse_time_delta('1d')
        86400
    """
    # Match pattern: number followed by unit
    match = re.match(r'^(\d+(?:\.\d+)?)(s|sec|seconds?|m|min|minutes?|h|hr|hours?|d|day|days?)$',
                     time_str.lower().strip())
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)

    # Convert to seconds
    if unit in ('s', 'sec', 'second', 'seconds'):
        return int(amount)
    elif unit in ('m', 'min', 'minute', 'minutes'):
        return int(amount * 60)
    elif unit in ('h', 'hr', 'hour', 'hours'):
        return int(amount * 3600)
    elif unit in ('d', 'day', 'days'):
        return int(amount * 86400)

    return None


@command(
    name="remind",
    description=(
        "Schedule a reminder message to be sent after a delay. "
        "Use --in <time> to specify delay (e.g., '5m', '2h', '30s'). "
        "Use --message to specify the reminder text. "
        "Optionally use --room <room_id> to send to a specific room (defaults to current room). "
        "The reminder will be delivered at the scheduled time, even if the bot restarts."
    ),
    params=[
        ("delay", str, "Time delay (e.g., '5m', '2h', '30s', '1d')", True),
        ("message", str, "The reminder message to send", True),
        ("room_id", str, "Optional room ID (defaults to current room)", False)
    ]
)
async def remind_handler(
    delay: str,
    message: str,
    room_id: Optional[str] = None,
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """Schedule a reminder to be sent after a specified delay.

    Args:
        delay: Time delay string (e.g., '5m', '2h', '30s', '1d')
        message: The reminder message to send
        room_id: Optional room ID (defaults to current room)
        matrix_context: Matrix context containing client, room, and event

    Returns:
        Confirmation message or error message

    Examples:
        >>> # User: "@architect remind --delay 5m --message Take a break"
        >>> # Returns: "✅ Reminder set! I'll remind you in 5 minutes (at 2025-01-15 14:35:00)"

        >>> # User: "@architect remind --delay 2h --message Check deployment --room !abc:matrix.org"
        >>> # Returns: "✅ Reminder set! I'll send the message in 2 hours (at 2025-01-15 16:30:00)"
    """
    from ..reminder_scheduler import get_scheduler

    # Validate matrix context
    if not matrix_context:
        return "❌ Error: This command requires Matrix context."

    # Get scheduler
    scheduler = get_scheduler()
    if not scheduler:
        return "❌ Error: Reminder scheduler is not available. Please contact the bot administrator."

    # Parse time delay
    seconds = parse_time_delta(delay)
    if seconds is None:
        return (
            f"❌ Invalid time format: '{delay}'\n\n"
            "Valid formats:\n"
            "• Seconds: 30s, 45sec, 60seconds\n"
            "• Minutes: 5m, 10min, 15minutes\n"
            "• Hours: 2h, 3hr, 4hours\n"
            "• Days: 1d, 2day, 3days\n\n"
            "Examples: '5m', '2h', '30s', '1d'"
        )

    # Validate delay range (minimum 10 seconds, maximum 30 days)
    if seconds < 10:
        return "❌ Delay must be at least 10 seconds."
    if seconds > 30 * 86400:  # 30 days
        return "❌ Delay cannot exceed 30 days."

    # Calculate scheduled time
    scheduled_time = time.time() + seconds

    # Determine target room
    target_room_id = room_id if room_id else matrix_context['room'].room_id

    # Get thread root if in a thread
    thread_root_id = None
    event = matrix_context.get('event')
    if event and hasattr(event, 'source') and isinstance(event.source, dict):
        relates_to = event.source.get('content', {}).get('m.relates_to', {})
        if relates_to.get('rel_type') == 'm.thread':
            thread_root_id = relates_to.get('event_id')
        else:
            # Use current event as thread root for new thread
            thread_root_id = event.event_id

    # Generate unique reminder ID
    reminder_id = str(uuid.uuid4())

    # Get user ID
    user_id = event.sender if event else "unknown"

    # Add reminder to scheduler
    try:
        await scheduler.add_reminder(
            reminder_id=reminder_id,
            scheduled_time=scheduled_time,
            message=message,
            room_id=target_room_id,
            thread_root_id=thread_root_id,
            created_by=user_id
        )
    except Exception as e:
        return f"❌ Failed to schedule reminder: {str(e)}"

    # Format scheduled time for display
    scheduled_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(scheduled_time))

    # Build human-readable duration
    duration_parts = []
    remaining = seconds

    days = remaining // 86400
    if days > 0:
        duration_parts.append(f"{days} day{'s' if days != 1 else ''}")
        remaining %= 86400

    hours = remaining // 3600
    if hours > 0:
        duration_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        remaining %= 3600

    minutes = remaining // 60
    if minutes > 0:
        duration_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        remaining %= 60

    if remaining > 0 or not duration_parts:
        duration_parts.append(f"{remaining} second{'s' if remaining != 1 else ''}")

    duration_str = ", ".join(duration_parts)

    # Different message if sending to a different room
    if target_room_id != matrix_context['room'].room_id:
        return (
            f"✅ Reminder scheduled!\n"
            f"Message: \"{message}\"\n"
            f"Room: {target_room_id}\n"
            f"Time: in {duration_str} (at {scheduled_time_str})\n"
            f"ID: {reminder_id}"
        )
    else:
        return (
            f"✅ Reminder set!\n"
            f"Message: \"{message}\"\n"
            f"Time: in {duration_str} (at {scheduled_time_str})\n"
            f"ID: {reminder_id}"
        )
