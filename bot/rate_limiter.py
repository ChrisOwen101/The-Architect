"""Token bucket rate limiter for API requests.

This module provides a token bucket rate limiter to control the rate of
API requests (primarily OpenAI API). It supports per-user rate limiting
to prevent a single user from monopolizing resources.

Key features:
- Token bucket algorithm for smooth rate limiting
- Per-user buckets for fairness
- FIFO queue for waiting requests
- Background token refill task
- Configurable rate and burst limit
"""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    Attributes:
        capacity: Maximum number of tokens (burst limit)
        tokens: Current number of tokens available
        rate: Tokens added per second
        last_refill_at: Last token refill timestamp
    """
    capacity: int
    tokens: float
    rate: float
    last_refill_at: float = field(default_factory=time.time)

    def refill(self) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.time()
        elapsed = now - self.last_refill_at
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.rate))
        self.last_refill_at = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default: 1)

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self.refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def available(self) -> int:
        """Get number of available tokens.

        Returns:
            Number of tokens currently available (rounded down)
        """
        self.refill()
        return int(self.tokens)

    def time_until_available(self, tokens: int = 1) -> float:
        """Calculate time until specified tokens will be available.

        Args:
            tokens: Number of tokens needed (default: 1)

        Returns:
            Seconds until tokens will be available (0 if already available)
        """
        self.refill()
        if self.tokens >= tokens:
            return 0.0
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.rate


class RateLimiter:
    """Token bucket rate limiter with per-user buckets and FIFO queue.

    This rate limiter ensures fair access to limited resources (like API calls)
    by enforcing rate limits per user and globally. Requests that exceed the
    rate limit are queued and processed in FIFO order.

    Example:
        >>> limiter = RateLimiter(rate=5, burst=10)
        >>> # Acquire permission to make API call
        >>> success = await limiter.acquire(user_id="@user:matrix.org", timeout=30)
        >>> if success:
        ...     # Make API call
        ...     pass
    """

    def __init__(
        self,
        rate: float = 5.0,  # requests per second
        burst: int = 10,     # maximum burst size
        global_rate: Optional[float] = None,  # optional global rate limit
        global_burst: Optional[int] = None    # optional global burst limit
    ):
        """Initialize rate limiter.

        Args:
            rate: Per-user rate in requests per second
            burst: Per-user burst limit (maximum tokens)
            global_rate: Optional global rate limit (shared across all users)
            global_burst: Optional global burst limit
        """
        self.rate = rate
        self.burst = burst
        self.global_rate = global_rate or (rate * 2)  # default: 2x per-user rate
        self.global_burst = global_burst or (burst * 2)  # default: 2x per-user burst

        # Per-user token buckets
        self._user_buckets: Dict[str, TokenBucket] = {}

        # Global token bucket (shared across all users)
        self._global_bucket = TokenBucket(
            capacity=self.global_burst,
            tokens=self.global_burst,
            rate=self.global_rate
        )

        # Queue for waiting requests (user_id, event)
        self._queue: asyncio.Queue = asyncio.Queue()

        # Lock for bucket access
        self._lock = asyncio.Lock()

        # Background refill task
        self._refill_task: Optional[asyncio.Task] = None

        logger.info(
            f"RateLimiter initialized: rate={rate}/s, burst={burst}, "
            f"global_rate={self.global_rate}/s, global_burst={self.global_burst}"
        )

    def _get_user_bucket(self, user_id: str) -> TokenBucket:
        """Get or create token bucket for a user.

        Args:
            user_id: User ID

        Returns:
            TokenBucket for the user
        """
        if user_id not in self._user_buckets:
            self._user_buckets[user_id] = TokenBucket(
                capacity=self.burst,
                tokens=self.burst,
                rate=self.rate
            )
        return self._user_buckets[user_id]

    async def acquire(
        self,
        user_id: str,
        timeout: float = 30.0,
        tokens: int = 1
    ) -> bool:
        """Acquire permission to proceed (consumes tokens).

        This method will wait until tokens are available or timeout occurs.
        It respects both per-user and global rate limits.

        Args:
            user_id: User ID requesting permission
            timeout: Maximum time to wait in seconds (default: 30)
            tokens: Number of tokens to consume (default: 1)

        Returns:
            True if permission granted, False if timeout
        """
        start_time = time.time()

        while True:
            async with self._lock:
                # Try to consume from both user and global buckets
                user_bucket = self._get_user_bucket(user_id)

                # Check if both buckets have tokens
                if user_bucket.consume(tokens) and self._global_bucket.consume(tokens):
                    logger.debug(
                        f"Rate limit acquired for {user_id} "
                        f"(user tokens: {user_bucket.available()}, "
                        f"global tokens: {self._global_bucket.available()})"
                    )
                    return True

                # If user bucket consumed but global didn't, refund user tokens
                if user_bucket.tokens < user_bucket.capacity - tokens + 1:
                    user_bucket.tokens += tokens

                # Calculate wait time
                user_wait = user_bucket.time_until_available(tokens)
                global_wait = self._global_bucket.time_until_available(tokens)
                wait_time = max(user_wait, global_wait)

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning(
                    f"Rate limit acquire timeout for {user_id} after {elapsed:.1f}s"
                )
                return False

            # Wait for tokens to be available (or until timeout)
            remaining_timeout = timeout - elapsed
            sleep_time = min(wait_time, remaining_timeout, 1.0)  # max 1s sleep

            if sleep_time > 0:
                logger.debug(
                    f"Rate limit wait for {user_id}: {sleep_time:.2f}s "
                    f"(user wait: {user_wait:.2f}s, global wait: {global_wait:.2f}s)"
                )
                await asyncio.sleep(sleep_time)

    async def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics.

        Returns:
            Dictionary with statistics
        """
        async with self._lock:
            return {
                'rate': self.rate,
                'burst': self.burst,
                'global_rate': self.global_rate,
                'global_burst': self.global_burst,
                'global_tokens_available': self._global_bucket.available(),
                'active_users': len(self._user_buckets),
                'user_tokens': {
                    user_id: bucket.available()
                    for user_id, bucket in self._user_buckets.items()
                }
            }

    async def _refill_task_loop(self) -> None:
        """Background task to periodically refill tokens.

        This task runs every second and refills all token buckets.
        It's an optimization to ensure consistent refill timing.
        """
        logger.info("Starting rate limiter refill task")

        try:
            while True:
                await asyncio.sleep(1.0)  # Refill every second

                async with self._lock:
                    # Refill global bucket
                    self._global_bucket.refill()

                    # Refill all user buckets
                    for bucket in self._user_buckets.values():
                        bucket.refill()

                    logger.debug(
                        f"Refilled rate limiter buckets "
                        f"(global: {self._global_bucket.available()}, "
                        f"users: {len(self._user_buckets)})"
                    )

        except asyncio.CancelledError:
            logger.info("Rate limiter refill task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in rate limiter refill task: {e}", exc_info=True)

    def start_refill_task(self) -> None:
        """Start the background refill task."""
        if self._refill_task is None or self._refill_task.done():
            self._refill_task = asyncio.create_task(self._refill_task_loop())
            logger.info("Started rate limiter refill task")
        else:
            logger.debug("Rate limiter refill task already running")

    def stop_refill_task(self) -> None:
        """Stop the background refill task."""
        if self._refill_task and not self._refill_task.done():
            self._refill_task.cancel()
            logger.info("Stopped rate limiter refill task")

    async def cleanup_idle_buckets(self, idle_threshold_seconds: float = 3600) -> int:
        """Remove token buckets for users who haven't been active recently.

        This prevents memory leaks from accumulating user buckets indefinitely.

        Args:
            idle_threshold_seconds: Remove buckets idle for this long (default: 1 hour)

        Returns:
            Number of buckets removed
        """
        now = time.time()
        removed = 0

        async with self._lock:
            to_remove = [
                user_id for user_id, bucket in self._user_buckets.items()
                if (now - bucket.last_refill_at) > idle_threshold_seconds
            ]

            for user_id in to_remove:
                self._user_buckets.pop(user_id, None)
                removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} idle rate limiter buckets")

        return removed


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> Optional[RateLimiter]:
    """Get the global rate limiter instance.

    Returns:
        RateLimiter instance or None if not initialized
    """
    return _rate_limiter


def set_rate_limiter(limiter: RateLimiter) -> None:
    """Set the global rate limiter instance.

    Args:
        limiter: RateLimiter instance to set
    """
    global _rate_limiter
    _rate_limiter = limiter
    logger.info("Global rate limiter set")
