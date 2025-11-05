"""Memory storage and retrieval system for the Matrix bot.

This module provides persistent memory storage using markdown files with YAML frontmatter.
Memories are organized per-user and per-room, with importance scoring based on recency
and access frequency.
"""
from __future__ import annotations
import logging
import math
import re
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import aiofiles
import yaml

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Represents a single memory entry."""

    id: str  # UUID for unique identification
    timestamp: float  # Unix timestamp when memory was created
    user_id: str  # Matrix user ID (@user:domain.com)
    room_id: str  # Matrix room ID (!room:domain.com)
    content: str  # The memory content
    context: Optional[str] = None  # Optional contextual information
    tags: list[str] = None  # Optional tags for categorization
    access_count: int = 0  # Number of times this memory was accessed
    last_accessed: Optional[float] = None  # Last access timestamp

    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []
        if self.last_accessed is None:
            self.last_accessed = self.timestamp

    def calculate_importance(self, current_time: Optional[float] = None) -> float:
        """Calculate importance score based on recency and access frequency.

        Formula: importance = (1.0 / (days_old + 1)) * log(access_count + 1)

        Args:
            current_time: Current timestamp (defaults to now)

        Returns:
            Importance score (higher = more important)
        """
        if current_time is None:
            current_time = time.time()

        # Calculate age in days
        age_seconds = current_time - self.timestamp
        days_old = age_seconds / 86400.0  # 86400 seconds in a day

        # Recency score: decreases with age
        recency_score = 1.0 / (days_old + 1.0)

        # Access frequency score: logarithmic scaling
        frequency_score = math.log(self.access_count + 1.0) + 1.0

        return recency_score * frequency_score

    def to_markdown(self) -> str:
        """Convert memory entry to markdown format with YAML frontmatter.

        Returns:
            Markdown string with YAML frontmatter
        """
        # Build frontmatter dict
        frontmatter = {
            'id': self.id,
            'timestamp': self.timestamp,
            'user_id': self.user_id,
            'room_id': self.room_id,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed,
        }

        if self.context:
            frontmatter['context'] = self.context
        if self.tags:
            frontmatter['tags'] = self.tags

        # Convert to YAML
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

        # Build markdown
        return f"---\n{yaml_str}---\n\n{self.content}\n"

    @classmethod
    def from_markdown(cls, markdown: str) -> MemoryEntry:
        """Parse a markdown memory entry.

        Args:
            markdown: Markdown string with YAML frontmatter

        Returns:
            MemoryEntry instance

        Raises:
            ValueError: If markdown format is invalid
        """
        # Extract frontmatter and content
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n\n(.*)$', markdown, re.DOTALL)
        if not match:
            raise ValueError("Invalid markdown format: missing frontmatter")

        yaml_str, content = match.groups()

        # Parse YAML frontmatter
        try:
            frontmatter = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}")

        # Create MemoryEntry
        return cls(
            id=frontmatter['id'],
            timestamp=frontmatter['timestamp'],
            user_id=frontmatter['user_id'],
            room_id=frontmatter['room_id'],
            content=content.strip(),
            context=frontmatter.get('context'),
            tags=frontmatter.get('tags', []),
            access_count=frontmatter.get('access_count', 0),
            last_accessed=frontmatter.get('last_accessed')
        )


class MemoryStore:
    """Persistent memory storage using markdown files."""

    def __init__(self, data_dir: str = "data"):
        """Initialize memory store.

        Args:
            data_dir: Root directory for data storage
        """
        self.data_dir = Path(data_dir)
        self.users_dir = self.data_dir / "memories" / "users"
        self.rooms_dir = self.data_dir / "memories" / "rooms"

        # Create directories if they don't exist
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self.rooms_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Memory store initialized: {self.data_dir}")

    def _get_user_memory_file(self, user_id: str) -> Path:
        """Get the memory file path for a user.

        Args:
            user_id: Matrix user ID

        Returns:
            Path to user's memory file
        """
        # Sanitize user_id for filename (replace : with _)
        safe_name = user_id.replace(':', '_').replace('/', '_')
        return self.users_dir / f"{safe_name}.md"

    def _get_room_memory_file(self, room_id: str) -> Path:
        """Get the memory file path for a room.

        Args:
            room_id: Matrix room ID

        Returns:
            Path to room's memory file
        """
        # Sanitize room_id for filename
        safe_name = room_id.replace(':', '_').replace('/', '_')
        return self.rooms_dir / f"{safe_name}.md"

    async def _read_memories(self, file_path: Path) -> list[MemoryEntry]:
        """Read all memory entries from a markdown file.

        Args:
            file_path: Path to memory file

        Returns:
            List of MemoryEntry objects
        """
        if not file_path.exists():
            return []

        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()

            if not content.strip():
                return []

            # Split into individual memory entries (separated by double newlines + frontmatter)
            # Pattern: split on "---\n" that's preceded by newlines or start of string
            entries = re.split(r'\n\n(?=---\n)', content.strip())

            memories = []
            for entry_text in entries:
                if entry_text.strip():
                    try:
                        memory = MemoryEntry.from_markdown(entry_text)
                        memories.append(memory)
                    except ValueError as e:
                        logger.warning(f"Skipping invalid memory entry: {e}")

            return memories

        except Exception as e:
            logger.error(f"Error reading memories from {file_path}: {e}", exc_info=True)
            return []

    async def _write_memories(self, file_path: Path, memories: list[MemoryEntry]) -> None:
        """Write memory entries to a markdown file.

        Args:
            file_path: Path to memory file
            memories: List of MemoryEntry objects to write
        """
        try:
            # Convert all memories to markdown
            markdown_entries = [memory.to_markdown() for memory in memories]
            content = '\n\n'.join(markdown_entries)

            # Write to file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)

            logger.debug(f"Wrote {len(memories)} memories to {file_path}")

        except Exception as e:
            logger.error(f"Error writing memories to {file_path}: {e}", exc_info=True)
            raise

    async def add_memory(
        self,
        user_id: str,
        room_id: str,
        content: str,
        context: Optional[str] = None,
        tags: Optional[list[str]] = None,
        scope: str = "user"
    ) -> str:
        """Add a new memory entry.

        Args:
            user_id: Matrix user ID
            room_id: Matrix room ID
            content: The memory content
            context: Optional contextual information
            tags: Optional list of tags
            scope: "user" for user-specific or "room" for room-wide (default: "user")

        Returns:
            Memory ID (UUID)
        """
        # Create new memory entry
        memory = MemoryEntry(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            user_id=user_id,
            room_id=room_id,
            content=content,
            context=context,
            tags=tags or []
        )

        # Get appropriate file path
        if scope == "room":
            file_path = self._get_room_memory_file(room_id)
        else:
            file_path = self._get_user_memory_file(user_id)

        # Read existing memories
        memories = await self._read_memories(file_path)

        # Append new memory
        memories.append(memory)

        # Write back to file
        await self._write_memories(file_path, memories)

        logger.info(f"Added {scope} memory {memory.id} for {user_id} in {room_id}")
        return memory.id

    async def get_recent_memories(
        self,
        user_id: str,
        room_id: str,
        days: int = 30,
        scope: str = "user"
    ) -> list[MemoryEntry]:
        """Get recent memories within a time window.

        Args:
            user_id: Matrix user ID
            room_id: Matrix room ID
            days: Number of days to look back (default: 30)
            scope: "user" for user-specific or "room" for room-wide

        Returns:
            List of MemoryEntry objects sorted by importance (descending)
        """
        # Get appropriate file path
        if scope == "room":
            file_path = self._get_room_memory_file(room_id)
        else:
            file_path = self._get_user_memory_file(user_id)

        # Read all memories
        all_memories = await self._read_memories(file_path)

        # Filter by time window
        current_time = time.time()
        cutoff_time = current_time - (days * 86400)

        recent_memories = [
            m for m in all_memories
            if m.timestamp >= cutoff_time
        ]

        # Update access counts and timestamps
        for memory in recent_memories:
            memory.access_count += 1
            memory.last_accessed = current_time

        # Write updated memories back
        await self._write_memories(file_path, all_memories)

        # Sort by importance (descending)
        recent_memories.sort(
            key=lambda m: m.calculate_importance(current_time),
            reverse=True
        )

        logger.debug(f"Retrieved {len(recent_memories)} recent memories (last {days} days)")
        return recent_memories

    async def search_memories(
        self,
        user_id: str,
        room_id: str,
        query: Optional[str] = None,
        start_date: Optional[float] = None,
        end_date: Optional[float] = None,
        limit: int = 10,
        scope: str = "user"
    ) -> list[MemoryEntry]:
        """Search memories with optional filters.

        Args:
            user_id: Matrix user ID
            room_id: Matrix room ID
            query: Optional text search query (case-insensitive substring match)
            start_date: Optional start timestamp for date filtering
            end_date: Optional end timestamp for date filtering
            limit: Maximum number of results to return
            scope: "user" for user-specific or "room" for room-wide

        Returns:
            List of MemoryEntry objects sorted by importance
        """
        # Get appropriate file path
        if scope == "room":
            file_path = self._get_room_memory_file(room_id)
        else:
            file_path = self._get_user_memory_file(user_id)

        # Read all memories
        all_memories = await self._read_memories(file_path)

        # Apply filters
        filtered = all_memories

        # Date range filter
        if start_date is not None:
            filtered = [m for m in filtered if m.timestamp >= start_date]
        if end_date is not None:
            filtered = [m for m in filtered if m.timestamp <= end_date]

        # Text search filter
        if query:
            query_lower = query.lower()
            filtered = [
                m for m in filtered
                if query_lower in m.content.lower() or
                (m.context and query_lower in m.context.lower()) or
                any(query_lower in tag.lower() for tag in m.tags)
            ]

        # Update access counts
        current_time = time.time()
        for memory in filtered:
            memory.access_count += 1
            memory.last_accessed = current_time

        # Write updated memories back
        await self._write_memories(file_path, all_memories)

        # Sort by importance
        filtered.sort(
            key=lambda m: m.calculate_importance(current_time),
            reverse=True
        )

        # Apply limit
        results = filtered[:limit]

        logger.debug(f"Search returned {len(results)} memories (query: {query})")
        return results

    async def delete_memory(
        self,
        memory_id: str,
        user_id: str,
        room_id: str,
        scope: str = "user"
    ) -> bool:
        """Delete a specific memory by ID.

        Args:
            memory_id: Memory UUID to delete
            user_id: Matrix user ID (for ownership verification)
            room_id: Matrix room ID
            scope: "user" for user-specific or "room" for room-wide

        Returns:
            True if deleted, False if not found or unauthorized
        """
        # Get appropriate file path
        if scope == "room":
            file_path = self._get_room_memory_file(room_id)
        else:
            file_path = self._get_user_memory_file(user_id)

        # Read all memories
        memories = await self._read_memories(file_path)

        # Find and remove the memory
        original_count = len(memories)
        memories = [
            m for m in memories
            if not (m.id == memory_id and m.user_id == user_id)
        ]

        if len(memories) == original_count:
            logger.warning(f"Memory {memory_id} not found or unauthorized")
            return False

        # Write back
        await self._write_memories(file_path, memories)

        logger.info(f"Deleted memory {memory_id} for {user_id}")
        return True

    async def get_stats(
        self,
        user_id: str,
        room_id: str,
        scope: str = "user"
    ) -> dict:
        """Get statistics about stored memories.

        Args:
            user_id: Matrix user ID
            room_id: Matrix room ID
            scope: "user" for user-specific or "room" for room-wide

        Returns:
            Dictionary with statistics
        """
        # Get appropriate file path
        if scope == "room":
            file_path = self._get_room_memory_file(room_id)
        else:
            file_path = self._get_user_memory_file(user_id)

        # Read all memories
        memories = await self._read_memories(file_path)

        if not memories:
            return {
                'total_count': 0,
                'oldest_memory': None,
                'newest_memory': None,
                'most_accessed': None,
                'avg_importance': 0.0
            }

        # Calculate statistics
        current_time = time.time()

        # Find oldest and newest
        oldest = min(memories, key=lambda m: m.timestamp)
        newest = max(memories, key=lambda m: m.timestamp)
        most_accessed = max(memories, key=lambda m: m.access_count)

        # Calculate average importance
        importances = [m.calculate_importance(current_time) for m in memories]
        avg_importance = sum(importances) / len(importances)

        return {
            'total_count': len(memories),
            'oldest_memory': {
                'id': oldest.id,
                'timestamp': oldest.timestamp,
                'content_preview': oldest.content[:50] + '...' if len(oldest.content) > 50 else oldest.content
            },
            'newest_memory': {
                'id': newest.id,
                'timestamp': newest.timestamp,
                'content_preview': newest.content[:50] + '...' if len(newest.content) > 50 else newest.content
            },
            'most_accessed': {
                'id': most_accessed.id,
                'access_count': most_accessed.access_count,
                'content_preview': most_accessed.content[:50] + '...' if len(most_accessed.content) > 50 else most_accessed.content
            },
            'avg_importance': avg_importance
        }
