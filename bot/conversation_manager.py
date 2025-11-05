"""Conversation context management and concurrency control.

This module provides conversation tracking and limits to ensure the bot
can handle multiple concurrent conversations without overload. It implements
per-user and global conversation limits, idle timeout, and context propagation.

Key features:
- Global conversation limit (default: 10 concurrent conversations)
- Per-user conversation limit (default: 3 concurrent conversations per user)
- Idle timeout (default: 5 minutes)
- Maximum duration timeout (default: 10 minutes)
- Background cleanup task for expired conversations
- Context propagation via contextvars
"""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ConversationStatus(Enum):
    """Conversation status enum."""
    ACTIVE = "active"
    IDLE = "idle"
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    ERROR = "error"


@dataclass
class ConversationContext:
    """Represents a single conversation context.

    Attributes:
        id: Unique conversation ID (UUID)
        thread_root_id: Matrix thread root event ID
        user_id: Matrix user ID who started the conversation
        room_id: Matrix room ID where conversation is happening
        started_at: Unix timestamp when conversation started
        last_activity_at: Unix timestamp of last activity
        status: Current conversation status
        metadata: Optional metadata dictionary for extensibility
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    thread_root_id: str = ""
    user_id: str = ""
    room_id: str = ""
    started_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    status: ConversationStatus = ConversationStatus.ACTIVE
    metadata: Dict[str, any] = field(default_factory=dict)

    def update_activity(self) -> None:
        """Update the last activity timestamp to now."""
        self.last_activity_at = time.time()

    def age_seconds(self) -> float:
        """Calculate conversation age in seconds.

        Returns:
            Age in seconds since conversation started
        """
        return time.time() - self.started_at

    def idle_seconds(self) -> float:
        """Calculate idle time in seconds.

        Returns:
            Seconds since last activity
        """
        return time.time() - self.last_activity_at


# Context variable for current conversation context
# This allows any function to access the current conversation context without
# explicitly passing it through function parameters
_current_conversation: ContextVar[Optional[ConversationContext]] = ContextVar(
    '_current_conversation',
    default=None
)


def get_current_conversation() -> Optional[ConversationContext]:
    """Get the current conversation context.

    Returns:
        Current ConversationContext or None if not in conversation
    """
    return _current_conversation.get()


def set_current_conversation(context: Optional[ConversationContext]) -> None:
    """Set the current conversation context.

    Args:
        context: ConversationContext to set, or None to clear
    """
    _current_conversation.set(context)


class ConversationManager:
    """Manages concurrent conversations with limits and cleanup.

    This class enforces conversation limits, tracks active conversations,
    and provides cleanup for idle/timed-out conversations.

    Example:
        >>> manager = ConversationManager(max_concurrent=10, max_per_user=3)
        >>> # Start conversation
        >>> context = await manager.start_conversation(
        ...     thread_root_id="$abc123",
        ...     user_id="@user:matrix.org",
        ...     room_id="!room:matrix.org"
        ... )
        >>> # Do work...
        >>> # End conversation
        >>> await manager.end_conversation(context.id)
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        max_per_user: int = 3,
        idle_timeout_seconds: int = 300,  # 5 minutes
        max_duration_seconds: int = 600   # 10 minutes
    ):
        """Initialize conversation manager.

        Args:
            max_concurrent: Maximum total concurrent conversations
            max_per_user: Maximum concurrent conversations per user
            idle_timeout_seconds: Idle timeout in seconds
            max_duration_seconds: Maximum conversation duration in seconds
        """
        self.max_concurrent = max_concurrent
        self.max_per_user = max_per_user
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_duration_seconds = max_duration_seconds

        # Active conversations indexed by conversation ID
        self._conversations: Dict[str, ConversationContext] = {}

        # User to conversation IDs mapping for per-user limits
        self._user_conversations: Dict[str, Set[str]] = {}

        # Lock for thread-safe access
        self._lock = asyncio.Lock()

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            f"ConversationManager initialized: max_concurrent={max_concurrent}, "
            f"max_per_user={max_per_user}, idle_timeout={idle_timeout_seconds}s, "
            f"max_duration={max_duration_seconds}s"
        )

    async def start_conversation(
        self,
        thread_root_id: str,
        user_id: str,
        room_id: str
    ) -> Optional[ConversationContext]:
        """Start a new conversation if limits allow.

        Args:
            thread_root_id: Matrix thread root event ID
            user_id: Matrix user ID
            room_id: Matrix room ID

        Returns:
            ConversationContext if started successfully, None if limits exceeded
        """
        async with self._lock:
            # Check global limit
            if len(self._conversations) >= self.max_concurrent:
                logger.warning(
                    f"Global conversation limit reached ({self.max_concurrent}), "
                    f"rejecting new conversation for {user_id}"
                )
                return None

            # Check per-user limit
            user_conv_count = len(self._user_conversations.get(user_id, set()))
            if user_conv_count >= self.max_per_user:
                logger.warning(
                    f"Per-user conversation limit reached ({self.max_per_user}) "
                    f"for {user_id}, rejecting new conversation"
                )
                return None

            # Create new conversation context
            context = ConversationContext(
                thread_root_id=thread_root_id,
                user_id=user_id,
                room_id=room_id
            )

            # Register conversation
            self._conversations[context.id] = context

            # Track user conversations
            if user_id not in self._user_conversations:
                self._user_conversations[user_id] = set()
            self._user_conversations[user_id].add(context.id)

            logger.info(
                f"Started conversation {context.id} for {user_id} in {room_id} "
                f"(global: {len(self._conversations)}/{self.max_concurrent}, "
                f"user: {user_conv_count + 1}/{self.max_per_user})"
            )

            return context

    async def end_conversation(
        self,
        conversation_id: str,
        status: ConversationStatus = ConversationStatus.COMPLETED
    ) -> bool:
        """End a conversation and free its slot.

        Args:
            conversation_id: Conversation ID to end
            status: Final status to set

        Returns:
            True if conversation was ended, False if not found
        """
        async with self._lock:
            context = self._conversations.get(conversation_id)
            if not context:
                logger.debug(f"Conversation {conversation_id} not found for ending")
                return False

            # Update status
            context.status = status

            # Remove from tracking
            self._conversations.pop(conversation_id, None)

            # Update user conversations
            user_convs = self._user_conversations.get(context.user_id)
            if user_convs:
                user_convs.discard(conversation_id)
                if not user_convs:
                    self._user_conversations.pop(context.user_id, None)

            logger.info(
                f"Ended conversation {conversation_id} for {context.user_id} "
                f"with status {status.value} "
                f"(duration: {context.age_seconds():.1f}s, "
                f"active: {len(self._conversations)})"
            )

            return True

    async def update_activity(self, conversation_id: str) -> bool:
        """Update activity timestamp for a conversation.

        Args:
            conversation_id: Conversation ID to update

        Returns:
            True if updated, False if conversation not found
        """
        async with self._lock:
            context = self._conversations.get(conversation_id)
            if not context:
                return False

            context.update_activity()
            logger.debug(f"Updated activity for conversation {conversation_id}")
            return True

    async def get_active_conversations(
        self,
        user_id: Optional[str] = None
    ) -> List[ConversationContext]:
        """Get list of active conversations.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of ConversationContext objects
        """
        async with self._lock:
            conversations = list(self._conversations.values())

            if user_id:
                conversations = [c for c in conversations if c.user_id == user_id]

            return conversations

    async def get_stats(self) -> Dict[str, any]:
        """Get conversation statistics.

        Returns:
            Dictionary with statistics
        """
        async with self._lock:
            return {
                'total_active': len(self._conversations),
                'max_concurrent': self.max_concurrent,
                'max_per_user': self.max_per_user,
                'users_with_conversations': len(self._user_conversations),
                'idle_timeout_seconds': self.idle_timeout_seconds,
                'max_duration_seconds': self.max_duration_seconds
            }

    async def _cleanup_expired_conversations(self) -> None:
        """Background task to clean up expired conversations.

        This task runs periodically and:
        1. Identifies conversations that have exceeded idle timeout
        2. Identifies conversations that have exceeded max duration
        3. Ends them with appropriate status
        """
        logger.info("Starting conversation cleanup task")

        try:
            while True:
                await asyncio.sleep(60)  # Check every minute

                now = time.time()
                to_end = []

                async with self._lock:
                    for conv_id, context in self._conversations.items():
                        # Check idle timeout
                        if context.idle_seconds() > self.idle_timeout_seconds:
                            logger.info(
                                f"Conversation {conv_id} idle timeout "
                                f"({context.idle_seconds():.1f}s > {self.idle_timeout_seconds}s)"
                            )
                            to_end.append((conv_id, ConversationStatus.IDLE))

                        # Check max duration
                        elif context.age_seconds() > self.max_duration_seconds:
                            logger.info(
                                f"Conversation {conv_id} duration timeout "
                                f"({context.age_seconds():.1f}s > {self.max_duration_seconds}s)"
                            )
                            to_end.append((conv_id, ConversationStatus.TIMED_OUT))

                # End expired conversations (outside lock to avoid blocking)
                for conv_id, status in to_end:
                    await self.end_conversation(conv_id, status)

                if to_end:
                    logger.info(f"Cleaned up {len(to_end)} expired conversations")

        except asyncio.CancelledError:
            logger.info("Conversation cleanup task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in conversation cleanup task: {e}", exc_info=True)

    def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(
                self._cleanup_expired_conversations()
            )
            logger.info("Started conversation cleanup task")
        else:
            logger.debug("Conversation cleanup task already running")

    def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Stopped conversation cleanup task")


# Global conversation manager instance
# Initialized with default values, can be reconfigured via set_conversation_manager()
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> Optional[ConversationManager]:
    """Get the global conversation manager instance.

    Returns:
        ConversationManager instance or None if not initialized
    """
    return _conversation_manager


def set_conversation_manager(manager: ConversationManager) -> None:
    """Set the global conversation manager instance.

    Args:
        manager: ConversationManager instance to set
    """
    global _conversation_manager
    _conversation_manager = manager
    logger.info("Global conversation manager set")
