"""Status command - Show active conversations and bot status."""
from __future__ import annotations
import time
from typing import Optional
from . import command


@command(
    name="status",
    description="Show your active conversations and bot status"
)
async def status_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    """
    Show user's active conversations and overall bot status.

    Args:
        matrix_context: Optional Matrix context dict with 'client', 'room', 'event'

    Returns:
        Status message with conversation and bot information
    """
    if not matrix_context:
        return "Error: This command requires Matrix context."

    from ..conversation_manager import get_conversation_manager
    from ..rate_limiter import get_rate_limiter

    conv_manager = get_conversation_manager()
    rate_limiter = get_rate_limiter()
    user_id = matrix_context['event'].sender

    # Build status message
    message = "📊 Your Status:\n\n"

    if conv_manager:
        # Get all conversations
        all_conversations = await conv_manager.get_active_conversations()
        user_conversations = [c for c in all_conversations if c.user_id == user_id]

        if user_conversations:
            message += f"Active Conversations ({len(user_conversations)}/{conv_manager.max_per_user}):\n"
            for i, conv in enumerate(user_conversations, 1):
                status_emoji = "⏳" if conv.status.value == "active" else "💤"
                elapsed = int(time.time() - conv.started_at)
                message += f"{i}. {status_emoji} Thread {conv.thread_root_id[:8]}... ({elapsed}s ago)\n"
        else:
            message += "No active conversations.\n"

        message += f"\n📈 Bot Status:\n"
        message += f"• Active conversations: {len(all_conversations)}/{conv_manager.max_concurrent}\n"
    else:
        message += "No active conversations.\n"
        message += f"\n📈 Bot Status:\n"
        message += "• Conversation tracking: Not enabled\n"

    if rate_limiter:
        stats = await rate_limiter.get_stats()
        message += f"• Rate limit: {stats['rate']:.1f} req/s (burst: {stats['burst']})\n"
        message += f"• Global tokens available: {stats['global_tokens_available']}\n"
    else:
        message += "• Rate limiting: Not enabled\n"

    return message
