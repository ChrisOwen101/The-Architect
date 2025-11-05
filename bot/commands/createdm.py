"""Create DM command - creates or reuses a direct message room with a specified user."""
from __future__ import annotations
from typing import Optional
from . import command
from nio.responses import DirectRoomsResponse, RoomCreateResponse, RoomCreateError


@command(
    name="createdm",
    description="Create (or reuse if it already exists) a direct-message room with a specified user ID or display name, and return the room ID.",
    params=[
        ("user_identifier", str, "The Matrix user ID (e.g., @user:server.com) or display name of the user to create a DM with", True)
    ]
)
async def createdm_handler(user_identifier: str, matrix_context: Optional[dict] = None) -> Optional[str]:
    """Create or reuse a direct message room with a specified user.

    This command creates a new direct message room with the specified user, or returns
    an existing DM room if one already exists. The user can be identified by their
    Matrix user ID (e.g., @user:server.com) or display name.

    Args:
        user_identifier: The Matrix user ID or display name of the user
        matrix_context: Optional Matrix context containing client, room, and event

    Returns:
        A message with the room ID of the DM, or an error message
    """
    if not matrix_context:
        return "Error: This command requires Matrix context."

    # Validate input
    if not user_identifier or not user_identifier.strip():
        return "Error: User identifier cannot be empty."

    # Get the Matrix client from context
    client = matrix_context.get("client")
    if not client:
        return "Error: Matrix client not available."

    # Clean up input
    user_identifier = user_identifier.strip()

    try:
        # Resolve user identifier to user ID
        target_user_id = None

        # If it looks like a user ID (starts with @), use it directly
        if user_identifier.startswith("@"):
            target_user_id = user_identifier
        else:
            # Try to find user by display name in the current room
            room = matrix_context.get("room")
            if room and hasattr(room, 'users'):
                for user_id, member in room.users.items():
                    display_name = member.display_name if hasattr(member, 'display_name') else None
                    if display_name and display_name.lower() == user_identifier.lower():
                        target_user_id = user_id
                        break

            if not target_user_id:
                return f"Error: Could not find user with display name '{user_identifier}'. Please use a Matrix user ID (e.g., @user:server.com) instead."

        # Check if a DM room already exists with this user
        direct_rooms_response = await client.list_direct_rooms()

        if isinstance(direct_rooms_response, DirectRoomsResponse):
            # direct_rooms_response.rooms is Dict[str, List[str]] where key is user_id
            # and value is list of room_ids that are DMs with that user
            if target_user_id in direct_rooms_response.rooms:
                existing_rooms = direct_rooms_response.rooms[target_user_id]
                if existing_rooms:
                    # Return the first existing DM room
                    room_id = existing_rooms[0]
                    return f"DM room already exists with {target_user_id}: {room_id}"

        # No existing DM found, create a new one
        create_response = await client.room_create(
            is_direct=True,
            invite=[target_user_id],
            preset=None  # Let server choose appropriate preset
        )

        if isinstance(create_response, RoomCreateResponse):
            room_id = create_response.room_id
            return f"Created new DM room with {target_user_id}: {room_id}"
        elif isinstance(create_response, RoomCreateError):
            return f"Error creating DM room: {create_response.message} (status code: {create_response.status_code})"
        else:
            return "Error creating DM room: Unexpected response type"

    except Exception as e:
        return f"Error creating DM: {str(e)}"
