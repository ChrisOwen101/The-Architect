from __future__ import annotations
from typing import Optional
from . import command


@command(
    name="sendroommessage",
    description="Sends a text message to a specified Matrix room by room ID.",
    params=[
        ("room_id", str, "The Matrix room ID (e.g., !abc123:server.com)", True),
        ("message", str, "The text message to send to the room", True)
    ]
)
async def sendroommessage_handler(room_id: str, message: str, matrix_context: Optional[dict] = None) -> Optional[str]:
    """Send a message to a specified Matrix room by room ID.

    This command sends a message to any Matrix room that the bot has access to.
    The room must be identified by its room ID (e.g., !abc123:server.com).

    Args:
        room_id: The Matrix room ID where the message should be sent
        message: The text message to send to the room
        matrix_context: Optional Matrix context containing client, room, and event

    Returns:
        A confirmation message indicating the message was sent, or an error message
    """
    if not matrix_context:
        return "Error: This command requires Matrix context to send messages."

    # Validate inputs
    if not room_id or not room_id.strip():
        return "Error: Room ID cannot be empty."

    if not message or not message.strip():
        return "Error: Message cannot be empty."

    # Get the Matrix client from context
    client = matrix_context.get("client")
    if not client:
        return "Error: Matrix client not available."

    # Clean up inputs
    room_id = room_id.strip()
    message = message.strip()

    # Validate room ID format (should start with !)
    if not room_id.startswith("!"):
        return "Error: Invalid room ID format. Room IDs must start with '!' (e.g., !abc123:server.com)."

    # Validate message length (keep it reasonable)
    if len(message) > 4000:
        return "Error: Message is too long. Please keep it under 4000 characters."

    try:
        # Send the message to the specified room
        await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": message
            }
        )
        return f"Message sent successfully to room {room_id}"

    except Exception as e:
        return f"Error sending message to room: {str(e)}"
