"""Recall command - search and retrieve memories from past conversations."""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional
from . import command
from ..memory_store import MemoryStore

logger = logging.getLogger(__name__)

# Initialize memory store
_memory_store = MemoryStore(data_dir="data")


@command(
    name="recall",
    description="Search your conversation memories. Retrieve memories by keyword, date range, or view recent memories.",
    params=[
        ("query", str, "Optional search query to filter memories by keyword", False),
        ("days", int, "Number of days to look back (default: 30)", False),
        ("limit", int, "Maximum number of memories to return (default: 10)", False)
    ]
)
async def recall_handler(
    query: str = "",
    days: int = 30,
    limit: int = 10,
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """Search and display memories from past conversations.

    Args:
        query: Optional text search query (case-insensitive)
        days: Number of days to look back
        limit: Maximum number of results
        matrix_context: Matrix context with client, room, and event

    Returns:
        Formatted string with memory results
    """
    if not matrix_context:
        return "Error: This command requires Matrix context"

    try:
        # Extract user and room info from context
        event = matrix_context.get('event')
        room = matrix_context.get('room')

        if not event or not room:
            return "Error: Could not determine user or room context"

        user_id = event.sender
        room_id = room.room_id

        # Validate parameters
        if days <= 0:
            return "Error: 'days' must be a positive number"
        if limit <= 0 or limit > 50:
            return "Error: 'limit' must be between 1 and 50"

        logger.info(f"Recalling memories for {user_id} in {room_id} (query: {query}, days: {days}, limit: {limit})")

        # Calculate start date
        start_timestamp = (datetime.now() - timedelta(days=days)).timestamp()

        # Search user-specific memories
        memories = await _memory_store.search_memories(
            user_id=user_id,
            room_id=room_id,
            query=query if query else None,
            start_date=start_timestamp,
            limit=limit,
            scope="user"
        )

        if not memories:
            if query:
                return f"No memories found matching '{query}' in the last {days} days."
            else:
                return f"No memories found in the last {days} days."

        # Format memories for display
        lines = []
        lines.append(f"Found {len(memories)} memor{'y' if len(memories) == 1 else 'ies'}:\n")

        for i, memory in enumerate(memories, 1):
            # Format timestamp
            dt = datetime.fromtimestamp(memory.timestamp)
            date_str = dt.strftime("%Y-%m-%d %H:%M")

            # Build memory line
            lines.append(f"{i}. [{date_str}] {memory.content}")

            # Add context if available
            if memory.context:
                lines.append(f"   Context: {memory.context}")

            # Add tags if available
            if memory.tags:
                tags_str = ", ".join(memory.tags)
                lines.append(f"   Tags: {tags_str}")

            # Add importance score
            importance = memory.calculate_importance()
            lines.append(f"   Importance: {importance:.2f} (accessed {memory.access_count} times)")

            # Add memory ID for deletion reference
            lines.append(f"   ID: {memory.id}")

            lines.append("")  # Empty line between memories

        result = "\n".join(lines)
        logger.debug(f"Returning {len(memories)} memories")
        return result

    except Exception as e:
        logger.error(f"Error in recall command: {e}", exc_info=True)
        return f"Error retrieving memories: {str(e)}"
