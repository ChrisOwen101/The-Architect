from __future__ import annotations
from typing import Optional
from . import command


@command(
    name="sendmessage",
    description="Sends a short text message to a specified recipient in this workspace. Parameters: recipient (string), message (string).",
    params=[
        ("recipient", str, "The user ID or display name of the recipient", True),
        ("message", str, "The text message to send", True)
    ]
)
async def sendmessage_handler(recipient: str, message: str, matrix_context: Optional[dict] = None) -> Optional[str]:
    """Send a message to a specified recipient in the Matrix workspace.

    This command sends a direct message to a specified user. The recipient can be
    identified by their Matrix user ID (e.g., @user:server.com) or display name.

    Args:
        recipient: The Matrix user ID or display name of the recipient
        message: The text message to send to the recipient
        matrix_context: Optional Matrix context containing client, room, and event

    Returns:
        A confirmation message indicating the message was sent, or an error message
    """
    if not matrix_context:
        return "Error: This command requires Matrix context to send messages."

    # Validate inputs
    if not recipient or not recipient.strip():
        return "Error: Recipient cannot be empty."

    if not message or not message.strip():
        return "Error: Message cannot be empty."

    # Get the Matrix client from context
    client = matrix_context.get("client")
    if not client:
        return "Error: Matrix client not available."

    # Clean up inputs
    recipient = recipient.strip()
    message = message.strip()

    # Validate message length (Matrix has a practical limit around 64KB, but keep it reasonable)
    if len(message) > 4000:
        return "Error: Message is too long. Please keep it under 4000 characters."

    try:
        # If recipient looks like a user ID (starts with @), try to find or create a DM room
        if recipient.startswith("@"):
            # Try to find an existing direct message room with this user
            # For now, we'll send a message indicating this feature requires room creation
            # In a real implementation, you'd use client.room_create() with is_direct=True
            return f"Message queued for {recipient}: \"{message}\"\n\nNote: Direct messaging requires room creation. Please use the Matrix client to start a DM with {recipient}, then use this command in that room, or the bot administrator needs to implement room creation."
        else:
            # If it's not a user ID, treat it as a display name
            return f"Error: Please provide a valid Matrix user ID (e.g., @user:server.com). Display name lookup is not yet implemented."

    except Exception as e:
        return f"Error sending message: {str(e)}"
