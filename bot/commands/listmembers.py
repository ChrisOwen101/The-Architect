"""List members command - lists all members in the current Matrix room."""
from __future__ import annotations
from typing import Optional
from . import command


@command(
    name="listmembers",
    description="List all members in the current Matrix room, returning display names and user IDs"
)
async def listmembers_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    """
    List all members in the current Matrix room.

    Returns display names and user IDs for all room members.
    Requires matrix_context with client and room information.

    Args:
        matrix_context: Dictionary containing Matrix client, room, and event.
                       Keys: 'client', 'room', 'event'

    Returns:
        Formatted string with member list, or error message if context unavailable
    """
    # Check if matrix_context is provided
    if not matrix_context:
        return "Error: This command requires Matrix room context."

    # Extract client and room from context
    client = matrix_context.get('client')
    room = matrix_context.get('room')

    if not client or not room:
        return "Error: Unable to access room information."

    # Get room members
    if not hasattr(room, 'users') or not room.users:
        return "No members found in this room."

    # Build member list
    members = []
    for user_id, member in room.users.items():
        display_name = member.display_name if hasattr(member, 'display_name') and member.display_name else user_id
        members.append((display_name, user_id))

    # Sort by display name for consistency
    members.sort(key=lambda x: x[0].lower())

    if not members:
        return "No members found in this room."

    # Format response
    lines = [f"Room members ({len(members)}):"]
    for display_name, user_id in members:
        # If display name is different from user ID, show both
        if display_name != user_id:
            lines.append(f"  {display_name} ({user_id})")
        else:
            lines.append(f"  {user_id}")

    result = "\n".join(lines)

    # Check if response is too long (Matrix message limit is typically 64KB, but we keep it under 4000 for readability)
    if len(result) > 4000:
        # Truncate with message
        lines = lines[:40]  # Keep first 40 lines
        lines.append(f"  ... and {len(members) - 39} more members (list truncated)")
        result = "\n".join(lines)

    return result
