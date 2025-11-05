from __future__ import annotations
from nio import RoomMessageText, AsyncClient, RoomSendResponse
import asyncio
import logging
import time
from typing import Optional

from .commands import execute_command

logger = logging.getLogger(__name__)

# Record bot start time (ms) to filter historical events on first sync.
START_TIME_MS = int(time.time() * 1000)
HISTORICAL_SKEW_MS = 5000  # allow 5s clock skew / startup delay

# Store config for use in handlers
_config = None


def set_config(config):
    """Set the bot config for use in handlers."""
    global _config
    _config = config


async def send_queue_notification(
    client: AsyncClient,
    room,
    event: RoomMessageText,
    thread_root_id: str,
    conv_manager
) -> None:
    """
    Send queue position notification to user when limits are exceeded.

    Args:
        client: Matrix client
        room: Room object
        event: Original event being replied to
        thread_root_id: Event ID of the thread root
        conv_manager: ConversationManager instance
    """
    from .conversation_manager import ConversationManager

    # Get current state
    stats = await conv_manager.get_stats()
    active_count = stats['total_active']
    max_concurrent = stats['max_concurrent']

    # Calculate approximate queue position
    queue_position = max(1, active_count - max_concurrent + 1)

    # Build appropriate message based on queue depth
    if queue_position > 3:
        # Long queue - suggest trying later
        message = f"🚦 I'm at capacity right now ({max_concurrent} concurrent conversations).\n"
        message += f"You're approximately #{queue_position} in queue. Please try again in a few minutes.\n\n"
        message += "Tip: You can check my status anytime with: @architect status"
    else:
        # Short queue - just ask to wait briefly
        message = f"🚦 I'm handling {active_count} conversations right now (limit: {max_concurrent}).\n"
        message += "Please try again in about 1 minute."

    try:
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": message,
                "m.relates_to": {
                    "rel_type": "m.thread",
                    "event_id": thread_root_id,
                    "is_falling_back": True,
                    "m.in_reply_to": {"event_id": event.event_id}
                },
            },
        )
        logger.info(f"Sent queue notification to {event.sender} (position: ~{queue_position})")
    except Exception as e:
        logger.warning(f"Failed to send queue notification: {e}")


async def generate_reply(body: str, client: AsyncClient = None, room=None, event: RoomMessageText = None) -> str | None:
    """Generate reply using OpenAI function calling.

    This function is deprecated but kept for backward compatibility.
    All commands now go through the OpenAI function calling system.

    Args:
        body: The message body
        client: Optional Matrix client
        room: Optional Matrix room
        event: Optional Matrix event

    Returns:
        Reply text or None
    """
    # All commands now go through OpenAI function calling
    from .openai_integration import is_bot_mentioned, generate_ai_reply
    if is_bot_mentioned(client, event):
        return await generate_ai_reply(event, room, client, _config)
    return None


def is_old_event(event) -> bool:
    server_ts = getattr(event, "server_timestamp", None)
    return isinstance(server_ts, (int, float)) and server_ts < START_TIME_MS - HISTORICAL_SKEW_MS


async def on_message(client: AsyncClient, room, event: RoomMessageText):
    # Ignore events that are older than when the bot started (minus skew)
    if is_old_event(event):
        logger.debug("Ignoring old event %s from %s in %s",
                     event.event_id, event.sender, room.room_id)
        return

    # Ignore messages from the bot itself
    if event.sender == client.user_id:
        logger.debug("Ignoring message from self")
        return

    # Check if room is allowed (if config has allowed_rooms list)
    if _config and _config.allowed_rooms and room.room_id not in _config.allowed_rooms:
        logger.debug("Ignoring message from non-allowed room: %s", room.room_id)
        return

    # Check if this is a response to a pending question (before bot mention check)
    # This allows users to respond to questions without mentioning the bot
    from .user_input_handler import is_pending_question, handle_user_response

    # Determine thread root using same logic as later in this function
    thread_root = event.event_id
    if hasattr(event, 'source') and isinstance(event.source, dict):
        relates_to = event.source.get('content', {}).get('m.relates_to', {})
        if relates_to.get('rel_type') == 'm.thread':
            thread_root = relates_to.get('event_id', event.event_id)

    # If there's a pending question in this thread, route the message there
    if is_pending_question(thread_root):
        was_handled = handle_user_response(thread_root, event.sender, event.body)
        if was_handled:
            logger.info("Message was response to pending question in thread %s", thread_root)
            return  # Don't process as new command

    try:
        # All commands now require bot mention and use OpenAI function calling
        from .openai_integration import is_bot_mentioned, generate_ai_reply
        from .conversation_manager import get_conversation_manager, ConversationStatus

        if not is_bot_mentioned(client, event):
            # Not mentioned - ignore
            return

        logger.info("Bot mentioned, using function calling flow")

        # Determine thread root before starting conversation
        thread_root = event.event_id
        if hasattr(event, 'source') and isinstance(event.source, dict):
            relates_to = event.source.get('content', {}).get('m.relates_to', {})
            if relates_to.get('rel_type') == 'm.thread':
                # Event is part of an existing thread, use its root
                thread_root = relates_to.get('event_id', event.event_id)

        # Try to start conversation
        conv_manager = get_conversation_manager()
        conversation = None

        if conv_manager:
            conversation = await conv_manager.start_conversation(
                thread_root_id=thread_root,
                user_id=event.sender,
                room_id=room.room_id
            )

            if not conversation:
                # Limits exceeded - send queue notification
                await send_queue_notification(client, room, event, thread_root, conv_manager)
                return

        try:
            # Generate AI reply
            reply = await generate_ai_reply(event, room, client, _config)

            if not reply:
                return  # Nothing to send

            logger.info("Replying in %s to %s (thread root: %s): %s",
                        room.room_id, event.sender, thread_root, reply)
            resp: RoomSendResponse = await client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": reply,
                    "m.relates_to": {
                        "rel_type": "m.thread",
                        "event_id": thread_root,
                        "is_falling_back": True,
                        "m.in_reply_to": {"event_id": event.event_id}
                    },
                },
            )
            # type: ignore[attr-defined]
            if hasattr(resp, 'transport_response') and resp.transport_response.ok:
                logger.debug("Message sent successfully")
            else:
                logger.warning("Message send may have failed: %s", resp)
        finally:
            # Always end conversation when done
            if conv_manager and conversation:
                await conv_manager.end_conversation(
                    conversation.id,
                    ConversationStatus.COMPLETED
                )
    except Exception:  # pragma: no cover - log unexpected
        logger.exception("Failed handling message event")
        # Make sure to end conversation on error
        if conv_manager and conversation:
            try:
                await conv_manager.end_conversation(
                    conversation.id,
                    ConversationStatus.ERROR
                )
            except Exception:
                logger.exception("Failed to end conversation after error")
