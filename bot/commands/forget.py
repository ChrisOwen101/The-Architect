"""Forget command - delete specific memories by ID."""
from __future__ import annotations
import logging
from typing import Optional
from . import command
from ..memory_store import MemoryStore

logger = logging.getLogger(__name__)

# Initialize memory store
_memory_store = MemoryStore(data_dir="data")


@command(
    name="forget",
    description="Delete a specific memory by its ID. Use the 'recall' command to see memory IDs.",
    params=[
        ("memory_id", str, "The ID of the memory to delete", True)
    ]
)
async def forget_handler(
    memory_id: str,
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """Delete a specific memory by ID.

    Args:
        memory_id: UUID of the memory to delete
        matrix_context: Matrix context with client, room, and event

    Returns:
        Confirmation message or error
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

        # Validate memory_id format (basic UUID check)
        if not memory_id or len(memory_id) < 8:
            return "Error: Invalid memory ID format"

        logger.info(f"Attempting to delete memory {memory_id} for {user_id}")

        # Attempt to delete the memory
        success = await _memory_store.delete_memory(
            memory_id=memory_id,
            user_id=user_id,
            room_id=room_id,
            scope="user"
        )

        if success:
            logger.info(f"Successfully deleted memory {memory_id}")
            return f"Memory {memory_id} has been deleted."
        else:
            logger.warning(f"Memory {memory_id} not found or unauthorized")
            return (
                f"Memory {memory_id} not found or you don't have permission to delete it.\n"
                "Use the 'recall' command to see your memory IDs."
            )

    except Exception as e:
        logger.error(f"Error in forget command: {e}", exc_info=True)
        return f"Error deleting memory: {str(e)}"
