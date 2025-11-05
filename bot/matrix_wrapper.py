"""Thread-safe wrapper around matrix-nio AsyncClient.

This module provides a wrapper class that adds asyncio.Lock protection around
matrix-nio AsyncClient methods to prevent race conditions when multiple coroutines
try to use the same client instance concurrently.

Key features:
- Single global lock for all Matrix operations
- Wraps room_send, room_messages, sync, and other critical methods
- Maintains backward compatibility with existing code
- Provides logging for debugging concurrent access
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional, Any
from nio import AsyncClient

logger = logging.getLogger(__name__)


class MatrixClientWrapper:
    """Thread-safe wrapper for matrix-nio AsyncClient.

    This wrapper adds asyncio.Lock protection around AsyncClient methods to
    prevent race conditions during concurrent operations. All wrapped methods
    maintain the same signature and behavior as the underlying AsyncClient.

    Example:
        >>> client = AsyncClient(homeserver, user_id)
        >>> wrapped_client = MatrixClientWrapper(client)
        >>> # Use wrapped_client exactly like client
        >>> await wrapped_client.room_send(room_id, "m.room.message", content)
    """

    def __init__(self, client: AsyncClient):
        """Initialize wrapper with AsyncClient instance.

        Args:
            client: matrix-nio AsyncClient instance to wrap
        """
        self._client = client
        self._lock = asyncio.Lock()
        logger.info("MatrixClientWrapper initialized")

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to wrapped client.

        For attributes/methods not explicitly wrapped, forward to the
        underlying client. This maintains compatibility with all
        AsyncClient features.

        Args:
            name: Attribute name

        Returns:
            Attribute value from wrapped client
        """
        return getattr(self._client, name)

    async def room_send(
        self,
        room_id: str,
        message_type: str,
        content: dict,
        tx_id: Optional[str] = None,
        ignore_unverified_devices: bool = False
    ):
        """Send a message to a room (thread-safe).

        Args:
            room_id: Room ID to send to
            message_type: Message type (e.g., "m.room.message")
            content: Message content dict
            tx_id: Optional transaction ID
            ignore_unverified_devices: Whether to ignore unverified devices

        Returns:
            RoomSendResponse from matrix-nio
        """
        async with self._lock:
            logger.debug(f"Sending message to {room_id} (locked)")
            return await self._client.room_send(
                room_id,
                message_type,
                content,
                tx_id=tx_id,
                ignore_unverified_devices=ignore_unverified_devices
            )

    async def room_messages(
        self,
        room_id: str,
        start: str,
        end: Optional[str] = None,
        direction: str = "b",
        limit: int = 10,
        message_filter: Optional[dict] = None
    ):
        """Get messages from a room (thread-safe).

        Args:
            room_id: Room ID to fetch from
            start: Token to start fetching from
            end: Optional token to stop at
            direction: Direction to fetch ("b" for backward, "f" for forward)
            limit: Maximum messages to fetch
            message_filter: Optional filter dict

        Returns:
            RoomMessagesResponse from matrix-nio
        """
        async with self._lock:
            logger.debug(f"Fetching messages from {room_id} (locked)")
            return await self._client.room_messages(
                room_id,
                start,
                end=end,
                direction=direction,
                limit=limit,
                message_filter=message_filter
            )

    async def sync(
        self,
        timeout: Optional[int] = None,
        sync_filter: Optional[dict] = None,
        since: Optional[str] = None,
        full_state: bool = False
    ):
        """Sync with the Matrix server (thread-safe).

        Args:
            timeout: Timeout in milliseconds
            sync_filter: Optional sync filter
            since: Optional sync token to start from
            full_state: Whether to fetch full state

        Returns:
            SyncResponse from matrix-nio
        """
        async with self._lock:
            logger.debug("Syncing with server (locked)")
            return await self._client.sync(
                timeout=timeout,
                sync_filter=sync_filter,
                since=since,
                full_state=full_state
            )

    async def set_displayname(self, displayname: str):
        """Set the bot's display name (thread-safe).

        Args:
            displayname: Display name to set

        Returns:
            ProfileSetDisplayNameResponse from matrix-nio
        """
        async with self._lock:
            logger.debug(f"Setting display name to '{displayname}' (locked)")
            return await self._client.set_displayname(displayname)

    async def close(self):
        """Close the client connection (thread-safe).

        Returns:
            Close response from matrix-nio
        """
        async with self._lock:
            logger.info("Closing client connection (locked)")
            return await self._client.close()

    async def whoami(self):
        """Get information about the current user (thread-safe).

        Returns:
            WhoamiResponse from matrix-nio
        """
        async with self._lock:
            logger.debug("Calling whoami (locked)")
            return await self._client.whoami()
