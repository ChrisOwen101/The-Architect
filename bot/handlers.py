from __future__ import annotations
from nio import RoomMessageText, AsyncClient, RoomSendResponse
import asyncio
import logging
import time

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


async def generate_reply(body: str, client: AsyncClient = None, room = None, event: RoomMessageText = None) -> str | None:
    """Generate reply using the dynamic command registry.

    Args:
        body: The message body
        client: Optional Matrix client (for commands that need to send messages)
        room: Optional Matrix room
        event: Optional Matrix event

    Returns:
        Reply text or None
    """
    # Build matrix context dictionary if we have the components
    matrix_context = None
    if client and room and event:
        matrix_context = {
            'client': client,
            'room': room,
            'event': event
        }

    return await execute_command(body, matrix_context=matrix_context)


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

    try:
        # Check for protected commands first (!add, !remove, !list)
        body_stripped = event.body.strip()
        is_protected_command = (
            body_stripped.startswith('!add ') or
            body_stripped == '!list' or
            body_stripped.startswith('!remove ')
        )

        if is_protected_command:
            # Execute protected command via traditional registry
            logger.debug("Executing protected command via registry")
            reply = await generate_reply(event.body, client=client, room=room, event=event)
        else:
            # Check if bot is mentioned for function calling
            from .openai_integration import is_bot_mentioned, generate_ai_reply
            if is_bot_mentioned(client, event):
                logger.info("Bot mentioned, using function calling flow")
                reply = await generate_ai_reply(event, room, client, _config)
            else:
                # Not a protected command and not mentioned - ignore
                reply = None

        if not reply:
            return  # Nothing to send

        # Determine the thread root for threading
        # If the incoming event is already in a thread, use that thread root
        # Otherwise, start a new thread with the current event as root
        thread_root = event.event_id
        if hasattr(event, 'source') and isinstance(event.source, dict):
            relates_to = event.source.get('content', {}).get('m.relates_to', {})
            if relates_to.get('rel_type') == 'm.thread':
                # Event is part of an existing thread, use its root
                thread_root = relates_to.get('event_id', event.event_id)

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
    except Exception:  # pragma: no cover - log unexpected
        logger.exception("Failed handling message event")
