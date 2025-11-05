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

    def __setattr__(self, name: str, value: Any) -> None:
        """Forward attribute writes to wrapped client.

        Special handling for wrapper's own attributes (_client, _lock).
        All other attributes are forwarded to the underlying client to
        ensure properties like access_token and user_id are set correctly.

        Args:
            name: Attribute name
            value: Attribute value
        """
        # These are the wrapper's own attributes
        if name in ('_client', '_lock'):
            object.__setattr__(self, name, value)
        else:
            # Forward all other attributes to the wrapped client
            setattr(self._client, name, value)

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
        logger.debug(f"Acquiring lock for room_send to {room_id}...")
        async with self._lock:
            logger.debug(f"Lock acquired, sending message to {room_id}")
            try:
                result = await self._client.room_send(
                    room_id,
                    message_type,
                    content,
                    tx_id=tx_id,
                    ignore_unverified_devices=ignore_unverified_devices
                )
                logger.debug(f"Message sent to {room_id}, releasing lock")
                return result
            except Exception as e:
                logger.error(f"Error in room_send to {room_id}: {e}")
                raise

    async def room_messages(
        self,
        room_id: str,
        start: str,
        end: Optional[str] = None,
        direction: str = "b",
        limit: int = 10,
        message_filter: Optional[dict] = None,
        timeout: int = 30
    ):
        """Get messages from a room (thread-safe).

        Args:
            room_id: Room ID to fetch from
            start: Token to start fetching from
            end: Optional token to stop at
            direction: Direction to fetch ("b" for backward, "f" for forward)
            limit: Maximum messages to fetch
            message_filter: Optional filter dict
            timeout: Timeout in seconds (default: 30)

        Returns:
            RoomMessagesResponse from matrix-nio

        Raises:
            asyncio.TimeoutError: If the operation times out
        """
        logger.debug(f"Acquiring lock for room_messages from {room_id} (start={start[:20] if start else 'empty'}...)...")
        async with self._lock:
            logger.debug(f"Lock acquired, fetching messages from {room_id} (timeout={timeout}s)")
            try:
                result = await asyncio.wait_for(
                    self._client.room_messages(
                        room_id,
                        start,
                        end=end,
                        direction=direction,
                        limit=limit,
                        message_filter=message_filter
                    ),
                    timeout=timeout
                )
                logger.debug(f"Messages fetched from {room_id}, releasing lock")
                return result
            except asyncio.TimeoutError:
                logger.error(f"room_messages timed out after {timeout}s for room {room_id}")
                raise
            except Exception as e:
                logger.error(f"Error in room_messages from {room_id}: {e}")
                raise

    async def sync(
        self,
        timeout: Optional[int] = None,
        sync_filter: Optional[dict] = None,
        since: Optional[str] = None,
        full_state: bool = False
    ):
        """Sync with the Matrix server (thread-safe).

        NOTE: sync() does NOT use the lock because it fires callbacks
        that need to make their own API calls (like room_send). Holding
        the lock during sync would cause deadlock when callbacks try to
        acquire the same lock.

        Args:
            timeout: Timeout in milliseconds
            sync_filter: Optional sync filter
            since: Optional sync token to start from
            full_state: Whether to fetch full state

        Returns:
            SyncResponse from matrix-nio
        """
        logger.debug("Syncing with server (no lock - callbacks need access)")
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
