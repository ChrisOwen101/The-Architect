"""Handles synchronous user input gathering during OpenAI function calls.

This module enables the bot to ask users questions and wait for their responses
during conversation flows. It uses asyncio.Event for non-blocking waiting while
allowing other Matrix messages to be processed.

Key components:
- PendingQuestion: Tracks questions awaiting user responses
- ask_user_and_wait(): Sends question and waits for response with timeout
- handle_user_response(): Routes incoming messages to waiting questions
- cleanup_expired_questions(): Background task to prevent memory leaks
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PendingQuestion:
    """Represents a pending question waiting for user response.

    Attributes:
        question: The question text sent to the user
        thread_root_id: Matrix thread root event ID
        user_id: Matrix user ID who should respond
        event: asyncio.Event that signals when response is received
        response: User's answer (set when response arrives)
        timeout_at: Unix timestamp when question expires
    """
    question: str
    thread_root_id: str
    user_id: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    response: Optional[str] = None
    timeout_at: float = 0.0


# Global registry of pending questions, keyed by thread_root_id
# This allows message handler to route responses to waiting questions
_pending_questions: Dict[str, PendingQuestion] = {}

# Background cleanup task reference
_cleanup_task: Optional[asyncio.Task] = None


async def ask_user_and_wait(
    question: str,
    matrix_context: dict,
    timeout: int = 120
) -> str:
    """Ask user a question and wait for their response.

    This function:
    1. Sends a question message to the user in Matrix (as threaded message)
    2. Registers the question in global pending state
    3. Waits asynchronously for the user's response via asyncio.Event
    4. Returns the user's answer or timeout/error message

    The waiting is non-blocking - other Matrix messages can be processed
    while waiting for the specific user's response in the specific thread.

    Args:
        question: Question to ask the user
        matrix_context: Matrix context dict with 'client', 'room', 'event' keys
        timeout: Timeout in seconds (default: 120 = 2 minutes)

    Returns:
        User's response string, or timeout/error message

    Example:
        >>> response = await ask_user_and_wait(
        ...     "What's your email?",
        ...     matrix_context,
        ...     timeout=60
        ... )
        >>> # User responds: "user@example.com"
        >>> print(response)  # "user@example.com"
    """
    client = matrix_context.get('client')
    room = matrix_context.get('room')
    event = matrix_context.get('event')

    if not all([client, room, event]):
        logger.error("Missing required matrix_context fields")
        return "[Error: Invalid matrix context]"

    # Determine thread root ID using same pattern as handlers.py
    thread_root_id = event.event_id
    if hasattr(event, 'source') and isinstance(event.source, dict):
        relates_to = event.source.get('content', {}).get('m.relates_to', {})
        if relates_to.get('rel_type') == 'm.thread':
            thread_root_id = relates_to.get('event_id', event.event_id)

    # Check if there's already a pending question in this thread
    if thread_root_id in _pending_questions:
        logger.warning(f"Thread {thread_root_id} already has a pending question")
        return "[Error: Another question is already pending in this thread]"

    # Create pending question
    pending = PendingQuestion(
        question=question,
        thread_root_id=thread_root_id,
        user_id=event.sender,
        timeout_at=time.time() + timeout
    )

    # Register globally
    _pending_questions[thread_root_id] = pending

    logger.info(f"Registered pending question in thread {thread_root_id}, timeout in {timeout}s")

    try:
        # Send question to user as threaded message
        # Use ❓ emoji to visually indicate it's a question
        await client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": f"❓ {question}",
                "m.relates_to": {
                    "rel_type": "m.thread",
                    "event_id": thread_root_id,
                    "is_falling_back": True,
                    "m.in_reply_to": {"event_id": event.event_id}
                },
            },
        )

        logger.info(f"Question sent to user {event.sender} in thread {thread_root_id}")

        # Wait for response with timeout
        # This is non-blocking - event loop can process other messages
        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout)

            # Response received
            response = pending.response or "[No response received]"
            logger.info(f"Received response in thread {thread_root_id}: {response[:50]}...")
            return response

        except asyncio.TimeoutError:
            # Timeout occurred
            logger.warning(f"Question timed out after {timeout}s in thread {thread_root_id}")
            return f"[Timeout after {timeout}s - no response received from user]"

    except Exception as e:
        logger.error(f"Error in ask_user_and_wait: {e}", exc_info=True)
        return f"[Error sending question: {e}]"

    finally:
        # Always clean up pending question
        _pending_questions.pop(thread_root_id, None)
        logger.debug(f"Cleaned up pending question for thread {thread_root_id}")


def handle_user_response(thread_root_id: str, user_id: str, response: str) -> bool:
    """Handle incoming user response to a pending question.

    This function is called from the message handler (on_message in handlers.py)
    when a message arrives that might be a response to a pending question.

    Args:
        thread_root_id: Thread ID where the response was sent
        user_id: User who sent the response
        response: Response text

    Returns:
        True if the response was for a pending question (and was handled),
        False if no pending question exists for this thread

    Example:
        >>> # In handlers.py on_message callback:
        >>> if is_pending_question(thread_root_id):
        ...     was_handled = handle_user_response(thread_root_id, user_id, body)
        ...     if was_handled:
        ...         return  # Don't process further
    """
    pending = _pending_questions.get(thread_root_id)

    if not pending:
        # No pending question in this thread
        return False

    if pending.user_id != user_id:
        # Response from wrong user - ignore
        logger.debug(
            f"Ignoring response from {user_id} - waiting for {pending.user_id}"
        )
        return False

    # Valid response - store it and signal the waiting coroutine
    pending.response = response
    pending.event.set()

    logger.info(f"Pending question answered in thread {thread_root_id}")
    return True


def is_pending_question(thread_root_id: str) -> bool:
    """Check if there's a pending question in the given thread.

    Args:
        thread_root_id: Thread ID to check

    Returns:
        True if a question is pending in this thread, False otherwise

    Example:
        >>> if is_pending_question(thread_root_id):
        ...     # Handle as response to pending question
        ...     handle_user_response(thread_root_id, user_id, message)
    """
    return thread_root_id in _pending_questions


async def cleanup_expired_questions() -> None:
    """Background task that periodically cleans up expired pending questions.

    This task runs every 60 seconds and:
    1. Identifies questions that have passed their timeout_at timestamp
    2. Signals their events (to unblock waiting coroutines)
    3. Removes them from the pending questions dict

    This prevents memory leaks if questions somehow don't get cleaned up
    properly in the finally block of ask_user_and_wait().

    The task runs indefinitely until cancelled.
    """
    logger.info("Starting cleanup task for expired pending questions")

    try:
        while True:
            await asyncio.sleep(60)  # Check every minute

            now = time.time()
            expired = [
                tid for tid, pq in _pending_questions.items()
                if now > pq.timeout_at
            ]

            if expired:
                logger.info(f"Cleaning up {len(expired)} expired pending questions")

                for tid in expired:
                    pq = _pending_questions.pop(tid, None)
                    if pq and not pq.event.is_set():
                        # Signal event to unblock waiting coroutine
                        pq.event.set()
                        logger.debug(f"Cleaned up expired question in thread {tid}")

    except asyncio.CancelledError:
        logger.info("Cleanup task cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}", exc_info=True)


def start_cleanup_task() -> None:
    """Start the background cleanup task if not already running.

    This should be called once during bot startup (e.g., in main.py).
    """
    global _cleanup_task

    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(cleanup_expired_questions())
        logger.info("Started cleanup task for pending questions")
    else:
        logger.debug("Cleanup task already running")


def stop_cleanup_task() -> None:
    """Stop the background cleanup task.

    This should be called during bot shutdown for clean teardown.
    """
    global _cleanup_task

    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        logger.info("Stopped cleanup task for pending questions")
