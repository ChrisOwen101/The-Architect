"""Tests for RateLimiter - token bucket rate limiting."""
from __future__ import annotations
import pytest
import asyncio
import time
from bot.rate_limiter import RateLimiter, TokenBucket


@pytest.fixture
def rate_limiter():
    """Create a RateLimiter with test configuration."""
    return RateLimiter(
        rate=5.0,  # 5 requests per second
        burst=10,  # burst up to 10
        global_rate=10.0,  # 10 requests/sec globally
        global_burst=20
    )


# TokenBucket Tests

def test_token_bucket_creation():
    """Test creating a TokenBucket."""
    bucket = TokenBucket(capacity=10, tokens=10, rate=5.0)

    assert bucket.capacity == 10
    assert bucket.tokens == 10
    assert bucket.rate == 5.0


def test_token_bucket_consume():
    """Test consuming tokens from bucket."""
    bucket = TokenBucket(capacity=10, tokens=10, rate=5.0)

    # Should succeed
    assert bucket.consume(1) is True
    assert 8.9 <= bucket.tokens <= 9.1  # Allow for tiny refill during operation

    # Consume more
    assert bucket.consume(5) is True
    assert 3.5 <= bucket.tokens <= 4.5  # Allow for tiny refill during operation

    # Try to consume more than available
    tokens_before = bucket.tokens
    assert bucket.consume(10) is False
    # Tokens should be roughly unchanged (allow for small refill)
    assert abs(bucket.tokens - tokens_before) < 0.5


def test_token_bucket_refill():
    """Test token refill over time."""
    bucket = TokenBucket(capacity=10, tokens=0, rate=10.0)  # 10 tokens/sec

    # Wait for tokens to refill
    time.sleep(0.5)  # Should add ~5 tokens
    bucket.refill()

    assert bucket.tokens >= 4  # Allow for timing variance
    assert bucket.tokens <= 6


def test_token_bucket_refill_cap():
    """Test that refill doesn't exceed capacity."""
    bucket = TokenBucket(capacity=10, tokens=5, rate=100.0)  # Very high rate

    # Wait and refill
    time.sleep(0.5)
    bucket.refill()

    # Should be capped at capacity
    assert bucket.tokens == 10


def test_token_bucket_available():
    """Test getting available token count."""
    bucket = TokenBucket(capacity=10, tokens=7.5, rate=5.0)

    available = bucket.available()
    assert available == 7  # Rounds down


def test_token_bucket_time_until_available():
    """Test calculating time until tokens available."""
    bucket = TokenBucket(capacity=10, tokens=2, rate=10.0)  # 10 tokens/sec

    # Need 5 tokens, have 2, need 3 more
    # At 10 tokens/sec, should take 0.3 seconds
    wait_time = bucket.time_until_available(5)
    assert 0.25 <= wait_time <= 0.35


# RateLimiter Tests

@pytest.mark.asyncio
async def test_acquire_within_rate_limit(rate_limiter):
    """Test acquiring token within rate limit succeeds immediately."""
    start = time.time()
    success = await rate_limiter.acquire(
        user_id="@user1:example.com",
        timeout=5.0
    )
    elapsed = time.time() - start

    assert success is True
    assert elapsed < 0.1  # Should be near-instant


@pytest.mark.asyncio
async def test_acquire_exceeding_rate_limit(rate_limiter):
    """Test acquiring token exceeding rate limit waits."""
    user_id = "@user1:example.com"

    # Exhaust user's bucket (10 tokens)
    for _ in range(10):
        success = await rate_limiter.acquire(user_id, timeout=1.0)
        assert success is True

    # Next request should wait for refill
    start = time.time()
    success = await rate_limiter.acquire(user_id, timeout=1.0)
    elapsed = time.time() - start

    assert success is True
    assert elapsed >= 0.15  # Should have waited for at least one refill


@pytest.mark.asyncio
async def test_burst_handling(rate_limiter):
    """Test that burst up to limit is allowed."""
    user_id = "@user1:example.com"

    # Should be able to burst up to 10 requests immediately
    start = time.time()
    for _ in range(10):
        success = await rate_limiter.acquire(user_id, timeout=1.0)
        assert success is True
    elapsed = time.time() - start

    # All should complete quickly (no significant waiting)
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_per_user_isolation(rate_limiter):
    """Test that user A doesn't block user B."""
    user_a = "@user_a:example.com"
    user_b = "@user_b:example.com"

    # Exhaust user A's bucket
    for _ in range(10):
        await rate_limiter.acquire(user_a, timeout=1.0)

    # User B should still be able to acquire immediately
    start = time.time()
    success = await rate_limiter.acquire(user_b, timeout=1.0)
    elapsed = time.time() - start

    assert success is True
    assert elapsed < 0.1  # Should be immediate


@pytest.mark.asyncio
async def test_token_refill_over_time(rate_limiter):
    """Test that tokens refill over time."""
    user_id = "@user1:example.com"

    # Exhaust bucket
    for _ in range(10):
        await rate_limiter.acquire(user_id, timeout=1.0)

    # Wait for some refill (rate is 5/sec, so 1 second = 5 tokens)
    await asyncio.sleep(1.0)

    # Should be able to acquire again (multiple times)
    for _ in range(4):  # Conservative to account for timing
        success = await rate_limiter.acquire(user_id, timeout=0.5)
        assert success is True


@pytest.mark.asyncio
async def test_timeout_handling(rate_limiter):
    """Test that acquire returns False on timeout."""
    user_id = "@user1:example.com"

    # Exhaust bucket
    for _ in range(10):
        await rate_limiter.acquire(user_id, timeout=1.0)

    # Try to acquire with very short timeout
    success = await rate_limiter.acquire(user_id, timeout=0.01)
    assert success is False


@pytest.mark.asyncio
async def test_global_rate_limit(rate_limiter):
    """Test that global rate limit is enforced across users."""
    # Create many users and try to exhaust global bucket
    users = [f"@user{i}:example.com" for i in range(5)]

    # Each user has 10-token burst, but global has 20-token burst
    # So we should be able to get 20 requests total before waiting
    success_count = 0

    for user in users:
        for _ in range(4):  # 5 users * 4 requests = 20 total
            success = await rate_limiter.acquire(user, timeout=0.1)
            if success:
                success_count += 1

    # Should get close to 20 (global burst limit)
    assert 18 <= success_count <= 20


@pytest.mark.asyncio
async def test_stats(rate_limiter):
    """Test getting rate limiter statistics."""
    # Acquire some tokens
    await rate_limiter.acquire("@user1:example.com", timeout=1.0)
    await rate_limiter.acquire("@user2:example.com", timeout=1.0)

    stats = await rate_limiter.get_stats()

    assert stats['rate'] == 5.0
    assert stats['burst'] == 10
    assert stats['global_rate'] == 10.0
    assert stats['global_burst'] == 20
    assert stats['active_users'] >= 2
    assert '@user1:example.com' in stats['user_tokens']
    assert '@user2:example.com' in stats['user_tokens']


@pytest.mark.asyncio
async def test_refill_task_lifecycle(rate_limiter):
    """Test starting and stopping refill task."""
    # Start task
    rate_limiter.start_refill_task()
    assert rate_limiter._refill_task is not None
    assert not rate_limiter._refill_task.done()

    # Wait a bit for task to run
    await asyncio.sleep(1.5)

    # Stop task
    rate_limiter.stop_refill_task()
    await asyncio.sleep(0.1)

    assert rate_limiter._refill_task.cancelled() or rate_limiter._refill_task.done()


@pytest.mark.asyncio
async def test_cleanup_idle_buckets(rate_limiter):
    """Test cleaning up idle user buckets."""
    # Create some user buckets
    await rate_limiter.acquire("@user1:example.com", timeout=1.0)
    await rate_limiter.acquire("@user2:example.com", timeout=1.0)

    stats = await rate_limiter.get_stats()
    assert stats['active_users'] == 2

    # Clean up with very short idle threshold (everything should be removed)
    removed = await rate_limiter.cleanup_idle_buckets(idle_threshold_seconds=0.0)
    assert removed == 2

    stats = await rate_limiter.get_stats()
    assert stats['active_users'] == 0


@pytest.mark.asyncio
async def test_concurrent_acquires():
    """Test concurrent acquire requests are handled correctly."""
    limiter = RateLimiter(rate=10.0, burst=5)
    user_id = "@user1:example.com"

    # Try to acquire 10 tokens concurrently (burst is 5)
    tasks = [
        limiter.acquire(user_id, timeout=2.0)
        for _ in range(10)
    ]

    results = await asyncio.gather(*tasks)

    # All should eventually succeed (with some waiting)
    assert all(results)


@pytest.mark.asyncio
async def test_multiple_token_consumption(rate_limiter):
    """Test consuming multiple tokens at once."""
    user_id = "@user1:example.com"

    # Consume 3 tokens at once
    success = await rate_limiter.acquire(user_id, timeout=1.0, tokens=3)
    assert success is True

    # Should have consumed 3 tokens
    stats = await rate_limiter.get_stats()
    user_tokens = stats['user_tokens'][user_id]
    assert user_tokens <= 7  # Started with 10, consumed 3


@pytest.mark.asyncio
async def test_fifo_ordering():
    """Test that waiting requests are processed in FIFO order."""
    limiter = RateLimiter(rate=2.0, burst=1)  # Very limited
    user_id = "@user1:example.com"

    results = []

    async def acquire_and_record(index):
        success = await limiter.acquire(user_id, timeout=5.0)
        if success:
            results.append(index)

    # Start multiple concurrent requests
    tasks = [acquire_and_record(i) for i in range(5)]
    await asyncio.gather(*tasks)

    # All should succeed
    assert len(results) == 5
    # Results should be in order (FIFO)
    assert results == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_refill_task_refills_buckets(rate_limiter):
    """Test that refill task actually refills buckets."""
    rate_limiter.start_refill_task()

    try:
        user_id = "@user1:example.com"

        # Exhaust bucket
        for _ in range(10):
            await rate_limiter.acquire(user_id, timeout=1.0)

        # Check tokens
        stats = await rate_limiter.get_stats()
        tokens_before = stats['user_tokens'][user_id]

        # Wait for refill task to run (runs every 1 second)
        await asyncio.sleep(1.5)

        # Check tokens again
        stats = await rate_limiter.get_stats()
        tokens_after = stats['user_tokens'][user_id]

        # Should have refilled
        assert tokens_after > tokens_before

    finally:
        rate_limiter.stop_refill_task()
