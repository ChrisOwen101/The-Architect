"""Cancel reminder command - Cancel a scheduled reminder.

This command allows users to cancel a reminder by its ID.
"""
from __future__ import annotations
from typing import Optional
from . import command


@command(
    name="cancel_reminder",
    description="Cancel a scheduled reminder by its ID. Use list_reminders to see all reminder IDs.",
    params=[
        ("reminder_id", str, "The ID of the reminder to cancel", True)
    ]
)
async def cancel_reminder_handler(
    reminder_id: str,
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """Cancel a scheduled reminder by ID.

    Args:
        reminder_id: The UUID of the reminder to cancel
        matrix_context: Matrix context containing client, room, and event

    Returns:
        Confirmation message or error message

    Examples:
        >>> # User: "@architect cancel_reminder --reminder_id 12345678-1234-1234-1234-123456789abc"
        >>> # Returns: "✅ Reminder cancelled successfully."
    """
    from ..reminder_scheduler import get_scheduler

    # Validate matrix context
    if not matrix_context:
        return "❌ Error: This command requires Matrix context."

    # Get scheduler
    scheduler = get_scheduler()
    if not scheduler:
        return "❌ Error: Reminder scheduler is not available. Please contact the bot administrator."

    # Validate reminder_id format (basic check)
    if not reminder_id or len(reminder_id.strip()) == 0:
        return "❌ Error: Reminder ID cannot be empty."

    # Get user ID
    event = matrix_context.get('event')
    if not event:
        return "❌ Error: Could not determine user ID."

    user_id = event.sender

    # Get all user's reminders to verify ownership
    reminders = await scheduler.list_reminders(user_id=user_id)
    reminder_ids = [r.id for r in reminders]

    if reminder_id not in reminder_ids:
        return (
            f"❌ Error: Reminder '{reminder_id}' not found or you don't have permission to cancel it.\n\n"
            "Use the list_reminders command to see all your scheduled reminders."
        )

    # Cancel the reminder
    success = await scheduler.cancel_reminder(reminder_id)

    if success:
        return f"✅ Reminder cancelled successfully.\nID: {reminder_id}"
    else:
        return f"❌ Error: Failed to cancel reminder '{reminder_id}'. It may have already been sent or cancelled."
