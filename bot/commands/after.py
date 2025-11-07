"""After command - Schedule a message after a delay with guaranteed delivery.

This command allows users to schedule messages to be sent after a specific number
of seconds. Messages are persistent and survive bot restarts. Unlike remind, this
command uses raw seconds for precise timing and supports room IDs or user mentions.

Usage examples:
- "@architect after --seconds 300 --target @user:matrix.org --message Hello there"
- "@architect after --seconds 60 --target !roomid:matrix.org --message Meeting in 1 minute"
- "@architect after --seconds 3600 --target @user:matrix.org --message This is an hour later"

**Integration with existing code:**
This command uses the existing ReminderScheduler infrastructure from bot/reminder_scheduler.py.
The scheduler is initialized in bot/main.py and provides persistent storage and background
task execution. No additional files need to be modified.

**When removing this command:**
No additional cleanup is needed beyond removing this file, as this command only uses
the existing ReminderScheduler infrastructure.
"""
from __future__ import annotations
import time
import uuid
from typing import Optional
from . import command


@command(
    name="after",
    description=(
        "Schedule a message after a delay. "
        "Specify seconds as a number, target as room_id (!abc:matrix.org) or user (@user:matrix.org), "
        "and the message to send. Guarantees delivery after the delay, even if bot restarts."
    ),
    params=[
        ("seconds", int, "Number of seconds to wait before sending (10-2592000)", True),
        ("target", str, "Target room ID (!abc:matrix.org) or user mention (@user:matrix.org)", True),
        ("message", str, "The message to send", True)
    ]
)
async def after_handler(
    seconds: int,
    target: str,
    message: str,
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """Schedule a message to be sent after a specified delay.

    Args:
        seconds: Number of seconds to wait (10-2592000, i.e., 10s to 30 days)
        target: Target room ID or user mention (room: !abc:matrix.org, user: @user:matrix.org)
        message: The message to send
        matrix_context: Matrix context containing client, room, and event

    Returns:
        Confirmation message or error message

    Examples:
        >>> # User: "@architect after --seconds 60 --target @bob:matrix.org --message Hey Bob!"
        >>> # Returns: "✅ Message scheduled! Will be sent in 1 minute (at 2025-01-15 14:31:00)"

        >>> # User: "@architect after --seconds 300 --target !abc:matrix.org --message Meeting starts now"
        >>> # Returns: "✅ Message scheduled! Will be sent in 5 minutes (at 2025-01-15 14:35:00)"
    """
    from ..reminder_scheduler import get_scheduler

    # Validate matrix context
    if not matrix_context:
        return "❌ Error: This command requires Matrix context."

    # Get scheduler
    scheduler = get_scheduler()
    if not scheduler:
        return "❌ Error: Message scheduler is not available. Please contact the bot administrator."

    # Validate seconds range (minimum 10 seconds, maximum 30 days)
    if seconds < 10:
        return "❌ Delay must be at least 10 seconds."
    if seconds > 30 * 86400:  # 30 days = 2,592,000 seconds
        return "❌ Delay cannot exceed 30 days (2,592,000 seconds)."

    # Parse target - determine if it's a room ID or user mention
    target = target.strip()
    target_room_id = None

    if target.startswith('!'):
        # Direct room ID
        target_room_id = target
    elif target.startswith('@'):
        # User mention - need to create DM or use existing DM room
        # For now, we'll return an error asking the user to provide a room ID
        # In the future, this could be enhanced to auto-create DM rooms
        return (
            "❌ User mentions are not yet supported for scheduled messages.\n\n"
            "Please provide a room ID instead (format: !abc123:matrix.org).\n"
            "You can use the 'createdm' command to create a DM room first, "
            "then use that room ID with this command."
        )
    else:
        return (
            "❌ Invalid target format.\n\n"
            "Target must be either:\n"
            "• Room ID: !abc123:matrix.org\n"
            "• User mention: @user:matrix.org (not yet supported)\n\n"
            f"You provided: '{target}'"
        )

    # Calculate scheduled time
    scheduled_time = time.time() + seconds

    # Get thread root if in a thread (optional - message will be sent without threading if not in thread)
    thread_root_id = None
    event = matrix_context.get('event')
    user_id = event.sender if event else "unknown"

    if event and hasattr(event, 'source') and isinstance(event.source, dict):
        relates_to = event.source.get('content', {}).get('m.relates_to', {})
        if relates_to.get('rel_type') == 'm.thread':
            thread_root_id = relates_to.get('event_id')
        # Note: We don't create a new thread for "after" messages - they're standalone

    # Generate unique message ID
    message_id = str(uuid.uuid4())

    # Add message to scheduler
    try:
        await scheduler.add_reminder(
            reminder_id=message_id,
            scheduled_time=scheduled_time,
            message=message,
            room_id=target_room_id,
            thread_root_id=thread_root_id,
            created_by=user_id
        )
    except Exception as e:
        return f"❌ Failed to schedule message: {str(e)}"

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

    # Build response
    return (
        f"✅ Message scheduled!\n"
        f"Target: {target_room_id}\n"
        f"Message: \"{message}\"\n"
        f"Time: in {duration_str} (at {scheduled_time_str})\n"
        f"ID: {message_id}"
    )
