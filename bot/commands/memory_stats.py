"""Memory stats command - display statistics about stored memories."""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional
from . import command
from ..memory_store import MemoryStore

logger = logging.getLogger(__name__)

# Initialize memory store
_memory_store = MemoryStore(data_dir="data")


@command(
    name="memory_stats",
    description="Display statistics about your stored memories, including count, age range, and access patterns."
)
async def memory_stats_handler(
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """Display memory statistics for the current user.

    Args:
        matrix_context: Matrix context with client, room, and event

    Returns:
        Formatted statistics string
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

        logger.info(f"Fetching memory statistics for {user_id} in {room_id}")

        # Get statistics
        stats = await _memory_store.get_stats(
            user_id=user_id,
            room_id=room_id,
            scope="user"
        )

        # Format statistics
        lines = []
        lines.append("Memory Statistics\n")
        lines.append("=" * 40)
        lines.append("")

        total_count = stats.get('total_count', 0)
        lines.append(f"Total memories: {total_count}")

        if total_count == 0:
            lines.append("\nNo memories stored yet.")
            lines.append("I'll automatically remember important information from our conversations.")
            return "\n".join(lines)

        lines.append("")

        # Oldest memory
        oldest = stats.get('oldest_memory')
        if oldest:
            oldest_dt = datetime.fromtimestamp(oldest['timestamp'])
            oldest_date = oldest_dt.strftime("%Y-%m-%d %H:%M")
            age_days = (datetime.now() - oldest_dt).days
            lines.append(f"Oldest memory: {oldest_date} ({age_days} days ago)")
            lines.append(f"  Preview: {oldest['content_preview']}")
            lines.append("")

        # Newest memory
        newest = stats.get('newest_memory')
        if newest:
            newest_dt = datetime.fromtimestamp(newest['timestamp'])
            newest_date = newest_dt.strftime("%Y-%m-%d %H:%M")
            age_days = (datetime.now() - newest_dt).days
            if age_days == 0:
                age_str = "today"
            elif age_days == 1:
                age_str = "yesterday"
            else:
                age_str = f"{age_days} days ago"
            lines.append(f"Newest memory: {newest_date} ({age_str})")
            lines.append(f"  Preview: {newest['content_preview']}")
            lines.append("")

        # Most accessed memory
        most_accessed = stats.get('most_accessed')
        if most_accessed:
            access_count = most_accessed['access_count']
            lines.append(f"Most accessed memory: {access_count} times")
            lines.append(f"  Preview: {most_accessed['content_preview']}")
            lines.append("")

        # Average importance
        avg_importance = stats.get('avg_importance', 0.0)
        lines.append(f"Average importance score: {avg_importance:.2f}")
        lines.append("")

        lines.append("=" * 40)
        lines.append("\nUse 'recall' to search and view memories.")
        lines.append("Use 'forget <memory_id>' to delete a specific memory.")

        result = "\n".join(lines)
        logger.debug(f"Returning statistics for {total_count} memories")
        return result

    except Exception as e:
        logger.error(f"Error in memory_stats command: {e}", exc_info=True)
        return f"Error retrieving memory statistics: {str(e)}"
