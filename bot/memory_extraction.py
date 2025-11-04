"""Memory extraction and injection for conversation context.

This module handles automatic extraction of important facts from conversations
and injection of relevant memories into conversation context for the AI.
"""
from __future__ import annotations
import json
import logging
from typing import Optional
import aiohttp
from .memory_store import MemoryStore

logger = logging.getLogger(__name__)

# OpenAI API configuration
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
EXTRACTION_MODEL = "gpt-5"
EXTRACTION_TIMEOUT = 60  # seconds

# System prompt for memory extraction
EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction assistant. Your task is to analyze conversations and identify important information that should be remembered for future reference.

Extract and return facts about:
- User preferences, likes, and dislikes
- Projects or tasks users are working on
- Important dates, events, or milestones mentioned
- Personal information shared (names, locations, professions, etc.)
- Ongoing discussions or topics
- Goals and intentions expressed

Return ONLY a JSON array of memory objects. Each memory should have:
- "content": A clear, concise statement of the fact (1-2 sentences)
- "context": Optional additional context or explanation
- "tags": Optional array of relevant tags for categorization

If there's nothing important to remember, return an empty array: []

Example response format:
[
  {
    "content": "User prefers Python over JavaScript for backend development",
    "context": "Mentioned during discussion about web frameworks",
    "tags": ["preference", "programming"]
  },
  {
    "content": "User is working on a Matrix bot project",
    "context": "Current active project",
    "tags": ["project", "matrix", "bot"]
  }
]

Return ONLY the JSON array, no other text."""


async def extract_memories_from_conversation(
    messages: list[dict],
    user_id: str,
    room_id: str,
    api_key: str,
    memory_store: MemoryStore
) -> int:
    """Extract important memories from conversation history using OpenAI.

    This function runs as a background task and doesn't block the main conversation flow.

    Args:
        messages: OpenAI-format conversation history
        user_id: Matrix user ID
        room_id: Matrix room ID
        api_key: OpenAI API key
        memory_store: MemoryStore instance

    Returns:
        Number of memories extracted and stored
    """
    try:
        logger.info(f"Extracting memories for {user_id} in {room_id}")

        # Filter out system messages and format for extraction
        user_messages = [
            msg for msg in messages
            if msg.get('role') in ('user', 'assistant')
        ]

        if len(user_messages) < 2:
            logger.debug("Not enough messages for memory extraction")
            return 0

        # Build conversation text for analysis
        conversation_text = "\n\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in user_messages[-10:]  # Analyze last 10 messages
        ])

        # Call OpenAI for extraction
        extraction_messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this conversation and extract important memories:\n\n{conversation_text}"}
        ]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": EXTRACTION_MODEL,
            "messages": extraction_messages,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENAI_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=EXTRACTION_TIMEOUT)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        f"OpenAI API error: {response.status} - {error_text}")
                    return 0

                data = await response.json()

                if 'error' in data:
                    logger.error(f"OpenAI API error: {data['error']}")
                    return 0

                # Extract response content
                content = data['choices'][0]['message']['content']

                # Parse JSON response
                try:
                    memories_data = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to parse extraction response as JSON: {e}")
                    logger.debug(f"Response content: {content}")
                    return 0

                if not isinstance(memories_data, list):
                    logger.warning("Extraction response is not a list")
                    return 0

                # Store extracted memories
                count = 0
                for memory_data in memories_data:
                    if not isinstance(memory_data, dict):
                        continue

                    memory_content = memory_data.get('content')
                    if not memory_content:
                        continue

                    # Add memory to store
                    await memory_store.add_memory(
                        user_id=user_id,
                        room_id=room_id,
                        content=memory_content,
                        context=memory_data.get('context'),
                        tags=memory_data.get('tags', []),
                        scope="user"  # User-specific memories
                    )
                    count += 1

                logger.info(
                    f"Extracted and stored {count} memories for {user_id}")
                return count

    except aiohttp.ClientError as e:
        logger.error(f"Network error during memory extraction: {e}")
        return 0
    except Exception as e:
        logger.error(
            f"Unexpected error during memory extraction: {e}", exc_info=True)
        return 0


async def inject_memories_into_context(
    messages: list[dict],
    user_id: str,
    room_id: str,
    memory_store: MemoryStore,
    days: int = 30
) -> list[dict]:
    """Inject relevant memories into conversation context.

    Retrieves recent memories and adds them as a system message at the beginning
    of the conversation, giving the AI awareness of past interactions.

    Args:
        messages: OpenAI-format conversation history
        user_id: Matrix user ID
        room_id: Matrix room ID
        memory_store: MemoryStore instance
        days: Number of days to look back for memories (default: 30)

    Returns:
        Modified messages list with memory context injected
    """
    try:
        # Get recent user-specific memories
        user_memories = await memory_store.get_recent_memories(
            user_id=user_id,
            room_id=room_id,
            days=days,
            scope="user"
        )

        # Get recent room-wide memories
        room_memories = await memory_store.get_recent_memories(
            user_id=user_id,
            room_id=room_id,
            days=days,
            scope="room"
        )

        # Build memory context message
        memory_parts = []

        if user_memories:
            memory_parts.append("## Memories about this user:")
            for memory in user_memories:
                memory_parts.append(f"- {memory.content}")
                if memory.context:
                    memory_parts.append(f"  Context: {memory.context}")

        if room_memories:
            if memory_parts:
                memory_parts.append("")
            memory_parts.append("## Memories about this room:")
            for memory in room_memories:
                memory_parts.append(f"- {memory.content}")
                if memory.context:
                    memory_parts.append(f"  Context: {memory.context}")

        if not memory_parts:
            # No memories to inject
            logger.debug("No recent memories to inject into context")
            return messages

        # Create memory context message
        memory_context = "\n".join(memory_parts)
        memory_message = {
            "role": "system",
            "content": f"Relevant memories from past conversations:\n\n{memory_context}\n\nUse these memories to provide personalized and contextually aware responses."
        }

        # Insert after the main system prompt (index 0)
        # This ensures memories are seen by the AI but don't override the main prompt
        modified_messages = messages.copy()
        modified_messages.insert(1, memory_message)

        logger.info(
            f"Injected {len(user_memories)} user memories and {len(room_memories)} room memories into context")
        return modified_messages

    except Exception as e:
        logger.error(
            f"Error injecting memories into context: {e}", exc_info=True)
        # Return original messages if injection fails
        return messages


async def extract_and_store_memory(
    user_id: str,
    room_id: str,
    content: str,
    memory_store: MemoryStore,
    context: Optional[str] = None,
    tags: Optional[list[str]] = None,
    scope: str = "user"
) -> str:
    """Directly store a memory without extraction.

    This is a helper function for explicit memory storage (e.g., when a user
    explicitly asks the bot to remember something).

    Args:
        user_id: Matrix user ID
        room_id: Matrix room ID
        content: Memory content
        memory_store: MemoryStore instance
        context: Optional context
        tags: Optional tags
        scope: "user" or "room" scope

    Returns:
        Memory ID
    """
    return await memory_store.add_memory(
        user_id=user_id,
        room_id=room_id,
        content=content,
        context=context,
        tags=tags,
        scope=scope
    )
