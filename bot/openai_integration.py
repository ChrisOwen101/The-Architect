from __future__ import annotations
import logging
from typing import Optional, TYPE_CHECKING, Any, Dict, List
import aiohttp
import asyncio

if TYPE_CHECKING:
    from nio import AsyncClient, RoomMessageText
    from .config import BotConfig

from .memory_store import MemoryStore
from .memory_extraction import inject_memories_into_context, extract_memories_from_conversation

logger = logging.getLogger(__name__)

# Initialize global memory store
_memory_store = MemoryStore(data_dir="data")

# OpenAI API configuration
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-5"
MAX_CONTEXT_MESSAGES = 50
API_TIMEOUT = 600  # seconds
MAX_FUNCTION_CALL_ITERATIONS = 20  # Prevent infinite loops

# The Architect system prompt
SYSTEM_PROMPT = """You are The Architect, a Matrix-themed AI assistant. You exist within the Matrix,
understanding its code and structure. You speak with wisdom and purpose, helping users navigate both
technical challenges and philosophical questions. You are knowledgeable, precise, and occasionally
reference Matrix concepts when appropriate. You are helpful and direct, without unnecessary verbosity."""

# User-friendly descriptions for function calls
FUNCTION_FRIENDLY_NAMES = {
    "list": "Checking available commands",
    "ping": "Testing responsiveness",
    "add": "Creating a new command",
    "remove": "Removing a command",
}


def is_bot_mentioned(client: AsyncClient, event: RoomMessageText) -> bool:
    """
    Check if the bot is mentioned in the message.

    Args:
        client: Matrix client with user_id
        event: Room message event

    Returns:
        True if bot is mentioned, False otherwise
    """
    bot_user_id = client.user_id
    if not bot_user_id:
        return False

    # Check plain text body
    if bot_user_id in event.body:
        return True

    # Check formatted body if available
    if hasattr(event, 'formatted_body') and event.formatted_body:
        if bot_user_id in event.formatted_body:
            return True

    return False


async def get_thread_context(
    client: AsyncClient,
    room,
    thread_root_id: str,
    limit: int = MAX_CONTEXT_MESSAGES
) -> list[RoomMessageText]:
    """
    Fetch messages from a thread for context.

    Args:
        client: Matrix client
        room: Room object
        thread_root_id: Event ID of the thread root
        limit: Maximum number of messages to fetch

    Returns:
        List of RoomMessageText events in chronological order
    """
    try:
        # Fetch recent room messages
        response = await client.room_messages(
            room_id=room.room_id,
            start="",
            limit=limit * 2,  # Fetch more to account for filtering
        )

        if not hasattr(response, 'chunk'):
            logger.warning("room_messages response has no chunk attribute")
            return []

        # Filter for messages in this thread
        thread_messages = []
        for event in response.chunk:
            # Include the thread root itself
            if event.event_id == thread_root_id:
                thread_messages.append(event)
                continue

            # Check if event is part of the thread
            if hasattr(event, 'source') and isinstance(event.source, dict):
                relates_to = event.source.get(
                    'content', {}).get('m.relates_to', {})
                if relates_to.get('event_id') == thread_root_id:
                    thread_messages.append(event)

        # Sort chronologically (oldest first)
        thread_messages.sort(key=lambda e: e.server_timestamp)

        # Limit to requested count
        return thread_messages[-limit:]

    except Exception as e:
        logger.error(f"Error fetching thread context: {e}", exc_info=True)
        return []


def build_conversation_history(
    messages: list[RoomMessageText],
    bot_user_id: str
) -> list[dict]:
    """
    Convert thread messages to OpenAI conversation format.

    Args:
        messages: List of Matrix messages
        bot_user_id: Bot's Matrix user ID

    Returns:
        List of message dicts in OpenAI format with role and content
    """
    conversation = []

    for msg in messages:
        # Determine role
        role = "assistant" if msg.sender == bot_user_id else "user"

        # Extract content (prefer plain body)
        content = msg.body

        # Add sender info for user messages (helps with multi-user threads)
        if role == "user":
            sender_name = msg.sender.split(':')[0].lstrip('@')
            content = f"[{sender_name}]: {content}"

        conversation.append({
            "role": role,
            "content": content
        })

    return conversation


async def send_status_message(
    client: AsyncClient,
    room,
    event: RoomMessageText,
    message: str,
    thread_root_id: str
) -> None:
    """
    Send a status update message to the user in a thread.

    Args:
        client: Matrix client
        room: Room object
        event: Original event being replied to
        message: Status message to send
        thread_root_id: Event ID of the thread root
    """
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
        logger.debug(f"Status message sent: {message}")
    except Exception as e:
        logger.warning(f"Failed to send status message: {e}")
        # Don't fail the command if status update fails


async def call_openai_api(
    messages: List[Dict[str, Any]],
    api_key: str,
    model: str = OPENAI_MODEL,
    tools: Optional[List[Dict[str, Any]]] = None
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Make HTTP request to OpenAI Chat Completions API.

    Args:
        messages: List of message dicts with role and content
        api_key: OpenAI API key
        model: Model name (default: gpt-5)
        tools: Optional list of function definitions for function calling

    Returns:
        Tuple of (response_dict, error_message)
        response_dict contains the full API response including tool_calls if any
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    # Add tools and parallel calling support if provided
    if tools:
        payload["tools"] = tools
        payload["parallel_tool_calls"] = True

    try:
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OPENAI_API_URL, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    message = data.get('choices', [{}])[0].get('message', {})

                    if message:
                        return message, None
                    else:
                        return None, "OpenAI API returned empty response"
                else:
                    error_text = await response.text()
                    logger.error(
                        f"OpenAI API error {response.status}: {error_text}")
                    return None, f"OpenAI API error: {response.status}"

    except asyncio.TimeoutError:
        logger.error("OpenAI API request timed out")
        return None, "OpenAI API request timed out"
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
        return None, f"Error calling OpenAI API: {str(e)}"


async def generate_ai_reply(
    event: RoomMessageText,
    room,
    client: AsyncClient,
    config: BotConfig
) -> Optional[str]:
    """
    Generate an AI reply to a message mentioning the bot.

    This function supports OpenAI function calling:
    1. Determines the thread root
    2. Fetches thread context (up to MAX_CONTEXT_MESSAGES)
    3. Builds conversation history
    4. Generates function schemas from command registry
    5. Calls OpenAI API with tools
    6. If tool_calls in response, executes functions and continues conversation
    7. Returns final synthesized response

    Args:
        event: Message event that mentions the bot
        room: Room object
        client: Matrix client
        config: Bot configuration

    Returns:
        Reply text or None if error
    """
    from .commands import get_registry
    from .function_executor import execute_functions

    try:
        # Determine thread root
        thread_root_id = event.event_id
        if hasattr(event, 'source') and isinstance(event.source, dict):
            relates_to = event.source.get(
                'content', {}).get('m.relates_to', {})
            if relates_to.get('rel_type') == 'm.thread':
                thread_root_id = relates_to.get('event_id', event.event_id)

        logger.info(f"Generating AI reply for thread {thread_root_id}")

        # Fetch thread context
        thread_messages = await get_thread_context(
            client, room, thread_root_id, MAX_CONTEXT_MESSAGES
        )

        if not thread_messages:
            # No thread context, just use current message
            thread_messages = [event]

        # Build conversation history
        conversation = build_conversation_history(
            thread_messages, client.user_id)

        # Add system prompt at the beginning
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}] + conversation

        # Inject relevant memories into context (last 30 days)
        messages = await inject_memories_into_context(
            messages=messages,
            user_id=event.sender,
            room_id=room.room_id,
            memory_store=_memory_store,
            days=30
        )

        # Generate function schemas from command registry
        registry = get_registry()
        function_schemas = registry.generate_function_schemas()

        if function_schemas:
            logger.info(
                f"Enabling {len(function_schemas)} function(s) for this conversation")
        else:
            logger.info("No functions available (only protected commands)")

        # Build matrix context for function execution
        matrix_context = {
            'client': client,
            'room': room,
            'event': event
        }

        # Multi-turn conversation loop to handle function calling
        iteration = 0
        while iteration < MAX_FUNCTION_CALL_ITERATIONS:
            iteration += 1
            logger.debug(
                f"API call iteration {iteration}/{MAX_FUNCTION_CALL_ITERATIONS}")

            # Call OpenAI API
            response_message, error = await call_openai_api(
                messages,
                config.openai_api_key,
                model=OPENAI_MODEL,
                tools=function_schemas if function_schemas else None
            )

            if error:
                logger.error(f"OpenAI API error: {error}")
                return f"Sorry, I encountered an error: {error}"

            if not response_message:
                return "Sorry, I received an empty response from the API."

            # Check if response contains tool_calls
            tool_calls = response_message.get('tool_calls')

            if tool_calls:
                # LLM wants to call functions
                logger.info(
                    f"LLM requested {len(tool_calls)} function call(s)")

                # Build user-friendly notification message
                tool_descriptions = []
                for tool_call in tool_calls:
                    function_name = tool_call.get(
                        'function', {}).get('name', 'unknown')
                    # Get friendly name or use generic description
                    friendly_name = FUNCTION_FRIENDLY_NAMES.get(
                        function_name,
                        f"Using the {function_name} tool"
                    )
                    tool_descriptions.append(friendly_name)

                # Send notification before execution
                if len(tool_descriptions) == 1:
                    notification = f"Let me help with that... {tool_descriptions[0]}..."
                else:
                    tools_list = "\n".join(
                        f"- {desc}" for desc in tool_descriptions)
                    notification = f"Let me help with that...\n{tools_list}"

                await send_status_message(client, room, event, notification, thread_root_id)

                # Add assistant's message with tool_calls to conversation
                messages.append(response_message)

                # Execute the functions
                tool_results = await execute_functions(tool_calls, matrix_context)

                # Add tool results to conversation
                messages.extend(tool_results)

                logger.debug(
                    "Tool results added, continuing conversation loop")
                # Continue loop to get LLM's synthesis
                continue

            # No tool_calls - this is the final text response
            content = response_message.get('content', '')

            if content:
                logger.info(
                    f"Generated final AI reply ({len(content)} chars, {iteration} iteration(s))")

                # Extract memories from conversation (background task, don't block response)
                asyncio.create_task(
                    extract_memories_from_conversation(
                        messages=messages,
                        user_id=event.sender,
                        room_id=room.room_id,
                        api_key=config.openai_api_key,
                        memory_store=_memory_store
                    )
                )

                return content.strip()
            else:
                logger.warning("Response has no content and no tool_calls")
                return "I processed your request but have nothing to say."

        # Max iterations reached
        logger.error(
            f"Reached max function call iterations ({MAX_FUNCTION_CALL_ITERATIONS})")
        return "Sorry, I got stuck in a loop trying to process your request. Please try rephrasing."

    except Exception as e:
        logger.error(f"Error in generate_ai_reply: {e}", exc_info=True)
        return f"Sorry, I encountered an unexpected error: {str(e)}"
