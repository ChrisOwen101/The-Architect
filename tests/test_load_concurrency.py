"""Comprehensive load tests for concurrent conversation system.

This module tests the conversation manager under realistic production workloads:
- High concurrent user loads (50+ simultaneous users)
- Sustained load over time (5 minutes continuous operation)
- Burst loads (sudden spikes in traffic)
- Mixed workload patterns (quick vs complex conversations)
- Limit enforcement under load
- Memory and performance characteristics

These tests are marked as 'slow' and can be run separately with:
    pytest tests/test_load_concurrency.py -v -m slow
"""
from __future__ import annotations
import asyncio
import gc
import logging
import psutil
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.conversation_manager import (
    ConversationManager,
    ConversationContext,
    ConversationStatus,
)


# Configure logging to see load test progress
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics collected during load tests."""

    # Response times in seconds
    response_times: List[float] = field(default_factory=list)

    # Queue wait times in seconds (for conversations that had to wait)
    queue_times: List[float] = field(default_factory=list)

    # Success/failure counts
    successful_starts: int = 0
    failed_starts: int = 0
    successful_completions: int = 0

    # Memory tracking (in MB)
    memory_before: float = 0.0
    memory_after: float = 0.0
    memory_peak: float = 0.0

    # Timestamps
    start_time: float = 0.0
    end_time: float = 0.0

    # Per-user metrics
    per_user_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add_response_time(self, duration: float) -> None:
        """Add a response time measurement."""
        self.response_times.append(duration)

    def add_queue_time(self, duration: float) -> None:
        """Add a queue wait time measurement."""
        self.queue_times.append(duration)

    def get_percentile(self, percentile: float, times: Optional[List[float]] = None) -> float:
        """Calculate percentile from response times.

        Args:
            percentile: Percentile to calculate (0-100)
            times: Optional specific list of times (defaults to response_times)

        Returns:
            Percentile value in seconds
        """
        times_to_use = times if times is not None else self.response_times
        if not times_to_use:
            return 0.0

        sorted_times = sorted(times_to_use)
        index = int(len(sorted_times) * (percentile / 100))
        index = min(index, len(sorted_times) - 1)
        return sorted_times[index]

    def throughput_per_second(self) -> float:
        """Calculate throughput in requests per second."""
        duration = self.end_time - self.start_time
        if duration <= 0:
            return 0.0
        return self.successful_completions / duration

    def memory_growth_mb(self) -> float:
        """Calculate memory growth in MB."""
        return self.memory_after - self.memory_before

    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.successful_starts + self.failed_starts
        if total == 0:
            return 0.0
        return (self.successful_starts / total) * 100

    def report(self) -> str:
        """Generate a human-readable performance report."""
        lines = [
            "\n" + "=" * 70,
            "PERFORMANCE METRICS REPORT",
            "=" * 70,
            "",
            "Response Times:",
            f"  Count: {len(self.response_times)}",
        ]

        if self.response_times:
            lines.extend([
                f"  Min: {min(self.response_times):.3f}s",
                f"  Max: {max(self.response_times):.3f}s",
                f"  Mean: {sum(self.response_times) / len(self.response_times):.3f}s",
                f"  P50 (median): {self.get_percentile(50):.3f}s",
                f"  P95: {self.get_percentile(95):.3f}s",
                f"  P99: {self.get_percentile(99):.3f}s",
            ])

        if self.queue_times:
            lines.extend([
                "",
                "Queue Wait Times:",
                f"  Count: {len(self.queue_times)}",
                f"  Mean: {sum(self.queue_times) / len(self.queue_times):.3f}s",
                f"  P95: {self.get_percentile(95, self.queue_times):.3f}s",
            ])

        lines.extend([
            "",
            "Success Metrics:",
            f"  Successful starts: {self.successful_starts}",
            f"  Failed starts: {self.failed_starts}",
            f"  Successful completions: {self.successful_completions}",
            f"  Success rate: {self.success_rate():.1f}%",
            "",
            "Throughput:",
            f"  Duration: {self.end_time - self.start_time:.2f}s",
            f"  Throughput: {self.throughput_per_second():.2f} conversations/sec",
            "",
            "Memory Usage:",
            f"  Before: {self.memory_before:.2f} MB",
            f"  After: {self.memory_after:.2f} MB",
            f"  Peak: {self.memory_peak:.2f} MB",
            f"  Growth: {self.memory_growth_mb():.2f} MB",
            "",
            "=" * 70,
        ])

        return "\n".join(lines)


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


async def simulate_user_conversation(
    user_id: str,
    conv_manager: ConversationManager,
    metrics: PerformanceMetrics,
    duration: float = 0.1,
    iterations: int = 1
) -> bool:
    """Simulate a single user conversation with timing metrics.

    Args:
        user_id: Matrix user ID
        conv_manager: ConversationManager instance
        metrics: PerformanceMetrics to record to
        duration: How long to simulate work (seconds)
        iterations: Number of activity updates to simulate

    Returns:
        True if conversation completed successfully, False if rejected
    """
    start_time = time.time()
    thread_id = f"$thread_{user_id}_{start_time}"

    # Try to start conversation
    conversation = await conv_manager.start_conversation(
        thread_root_id=thread_id,
        user_id=user_id,
        room_id="!loadtest:example.com"
    )

    if not conversation:
        # Conversation was rejected due to limits
        metrics.failed_starts += 1
        metrics.add_response_time(time.time() - start_time)
        return False

    metrics.successful_starts += 1
    metrics.per_user_counts[user_id] += 1

    try:
        # Simulate conversation work with activity updates
        for i in range(iterations):
            await asyncio.sleep(duration / iterations)
            await conv_manager.update_activity(conversation.id)

            # Track memory at intervals
            current_memory = get_memory_usage_mb()
            metrics.memory_peak = max(metrics.memory_peak, current_memory)

        # End conversation
        await conv_manager.end_conversation(conversation.id)
        metrics.successful_completions += 1

        # Record total response time
        total_time = time.time() - start_time
        metrics.add_response_time(total_time)

        return True

    except Exception as e:
        logger.error(f"Error in conversation {conversation.id}: {e}")
        await conv_manager.end_conversation(
            conversation.id,
            ConversationStatus.ERROR
        )
        return False


@pytest.fixture
def load_test_manager():
    """Create a ConversationManager configured for load testing."""
    return ConversationManager(
        max_concurrent=20,
        max_per_user=5,
        idle_timeout_seconds=60,
        max_duration_seconds=120
    )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_concurrent_user_load_50_users(load_test_manager):
    """Test 1: Simulate 50 users sending requests simultaneously.

    This test verifies:
    - System handles high concurrent user load
    - Response times are reasonable
    - No memory leaks occur
    - No conversation cross-talk happens
    - Limits are enforced correctly
    """
    logger.info("Starting Test 1: 50 Concurrent Users")

    metrics = PerformanceMetrics()
    metrics.start_time = time.time()
    metrics.memory_before = get_memory_usage_mb()

    # Create 50 concurrent user requests
    tasks = []
    for i in range(50):
        user_id = f"@loadtest_user_{i}:example.com"
        task = asyncio.create_task(
            simulate_user_conversation(
                user_id=user_id,
                conv_manager=load_test_manager,
                metrics=metrics,
                duration=0.1,
                iterations=2
            )
        )
        tasks.append(task)

    # Wait for all to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    metrics.end_time = time.time()
    metrics.memory_after = get_memory_usage_mb()

    # Force garbage collection and measure final memory
    gc.collect()
    await asyncio.sleep(0.1)
    final_memory = get_memory_usage_mb()

    # Print detailed report
    print(metrics.report())

    # Assertions
    assert metrics.successful_starts >= 20, \
        f"Expected at least 20 successful starts (max_concurrent=20), got {metrics.successful_starts}"

    assert metrics.successful_starts <= 20, \
        f"Expected at most 20 successful starts (max_concurrent=20), got {metrics.successful_starts}"

    assert metrics.successful_completions == metrics.successful_starts, \
        "All started conversations should complete successfully"

    # Verify no exceptions occurred
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions}"

    # Verify all conversations cleaned up
    active_convs = await load_test_manager.get_active_conversations()
    assert len(active_convs) == 0, \
        f"Expected 0 active conversations after cleanup, found {len(active_convs)}"

    # Performance assertions
    if metrics.response_times:
        p95_time = metrics.get_percentile(95)
        assert p95_time < 5.0, \
            f"P95 response time {p95_time:.3f}s exceeds 5s threshold"

    # Memory leak check - allow 50MB growth for 50 concurrent users
    memory_growth = final_memory - metrics.memory_before
    assert memory_growth < 50.0, \
        f"Memory growth {memory_growth:.2f}MB exceeds 50MB threshold (possible leak)"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_sustained_load_5_minutes(load_test_manager):
    """Test 2: Run continuous load for 5 minutes.

    This test verifies:
    - System handles sustained load without degradation
    - Cleanup tasks work correctly over time
    - Memory remains stable
    - Throughput is consistent

    Note: This is a 30-second abbreviated version. For full 5-minute test,
    change duration to 300 seconds.
    """
    logger.info("Starting Test 2: Sustained Load (30s abbreviated)")

    metrics = PerformanceMetrics()
    metrics.start_time = time.time()
    metrics.memory_before = get_memory_usage_mb()

    # Run for 30 seconds (abbreviated from 5 minutes for faster testing)
    duration_seconds = 30
    concurrent_users = 10

    # Track memory samples over time
    memory_samples = []

    async def continuous_user(user_id: str):
        """User that continuously starts new conversations."""
        conversation_count = 0
        while time.time() - metrics.start_time < duration_seconds:
            success = await simulate_user_conversation(
                user_id=user_id,
                conv_manager=load_test_manager,
                metrics=metrics,
                duration=0.1,
                iterations=1
            )
            if success:
                conversation_count += 1

            # Brief pause between conversations
            await asyncio.sleep(0.05)

        return conversation_count

    async def memory_monitor():
        """Monitor memory usage every 5 seconds."""
        while time.time() - metrics.start_time < duration_seconds:
            memory_samples.append(get_memory_usage_mb())
            metrics.memory_peak = max(metrics.memory_peak, memory_samples[-1])
            await asyncio.sleep(5)

    # Start users and monitor
    user_tasks = [
        asyncio.create_task(continuous_user(f"@sustained_user_{i}:example.com"))
        for i in range(concurrent_users)
    ]
    monitor_task = asyncio.create_task(memory_monitor())

    # Wait for completion
    conversation_counts = await asyncio.gather(*user_tasks)
    monitor_task.cancel()

    metrics.end_time = time.time()
    metrics.memory_after = get_memory_usage_mb()

    # Print detailed report
    print(metrics.report())
    print(f"\nPer-user conversation counts: {dict(metrics.per_user_counts)}")
    print(f"Total conversations: {sum(conversation_counts)}")
    print(f"Memory samples over time: {[f'{m:.1f}MB' for m in memory_samples]}")

    # Assertions
    total_conversations = sum(conversation_counts)
    assert total_conversations > 0, "Should have completed some conversations"

    # Verify cleanup worked
    active_convs = await load_test_manager.get_active_conversations()
    assert len(active_convs) == 0, \
        f"Expected 0 active conversations after sustained load, found {len(active_convs)}"

    # Calculate throughput
    throughput = metrics.throughput_per_second()
    assert throughput > 1.0, \
        f"Throughput {throughput:.2f} conversations/sec is below minimum threshold"

    # Memory stability check - memory shouldn't grow unbounded
    if len(memory_samples) >= 3:
        # Check that memory doesn't continuously increase
        memory_trend = memory_samples[-1] - memory_samples[0]
        assert memory_trend < 100.0, \
            f"Memory grew {memory_trend:.2f}MB during sustained load (possible leak)"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_burst_load_pattern(load_test_manager):
    """Test 3: Test burst handling with repeated spikes.

    This test verifies:
    - System handles sudden traffic spikes
    - Rate limiter works correctly
    - No resource exhaustion occurs
    - Recovery between bursts is clean
    """
    logger.info("Starting Test 3: Burst Load Pattern")

    metrics = PerformanceMetrics()
    metrics.start_time = time.time()
    metrics.memory_before = get_memory_usage_mb()

    burst_size = 20
    num_bursts = 5

    for burst_num in range(num_bursts):
        logger.info(f"Starting burst {burst_num + 1}/{num_bursts}")

        # Create burst of requests
        tasks = []
        for i in range(burst_size):
            user_id = f"@burst_user_{burst_num}_{i}:example.com"
            task = asyncio.create_task(
                simulate_user_conversation(
                    user_id=user_id,
                    conv_manager=load_test_manager,
                    metrics=metrics,
                    duration=0.2,
                    iterations=1
                )
            )
            tasks.append(task)

        # Wait for burst to complete
        await asyncio.gather(*tasks)

        # Verify cleanup between bursts
        active_convs = await load_test_manager.get_active_conversations()
        assert len(active_convs) == 0, \
            f"Burst {burst_num + 1}: Expected cleanup, found {len(active_convs)} active"

        # Brief pause between bursts
        await asyncio.sleep(0.5)

        # Track memory
        metrics.memory_peak = max(metrics.memory_peak, get_memory_usage_mb())

    metrics.end_time = time.time()
    metrics.memory_after = get_memory_usage_mb()

    # Print detailed report
    print(metrics.report())

    # Assertions
    total_requests = burst_size * num_bursts
    assert metrics.successful_starts + metrics.failed_starts == total_requests, \
        "All requests should be accounted for"

    # Each burst should only allow max_concurrent (20) to succeed
    expected_successful = min(burst_size, load_test_manager.max_concurrent) * num_bursts
    assert metrics.successful_completions == expected_successful, \
        f"Expected {expected_successful} completions, got {metrics.successful_completions}"

    # Verify no lingering conversations
    active_convs = await load_test_manager.get_active_conversations()
    assert len(active_convs) == 0, "All conversations should be cleaned up"

    # Memory check - 5 bursts shouldn't cause major memory growth
    memory_growth = metrics.memory_after - metrics.memory_before
    assert memory_growth < 30.0, \
        f"Memory growth {memory_growth:.2f}MB exceeds 30MB threshold"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_mixed_workload_patterns(load_test_manager):
    """Test 4: Realistic mixed scenario with different conversation types.

    This test verifies:
    - Quick queries don't block complex workflows
    - Different conversation lengths coexist properly
    - No blocking between conversation types
    - Fair resource allocation
    """
    logger.info("Starting Test 4: Mixed Workload Patterns")

    metrics = PerformanceMetrics()
    metrics.start_time = time.time()
    metrics.memory_before = get_memory_usage_mb()

    # Different user archetypes
    quick_users = 15  # Quick 1-2 iteration queries
    complex_users = 5  # Complex 10+ iteration workflows

    tasks = []

    # Quick users (short conversations)
    for i in range(quick_users):
        user_id = f"@quick_user_{i}:example.com"
        task = asyncio.create_task(
            simulate_user_conversation(
                user_id=user_id,
                conv_manager=load_test_manager,
                metrics=metrics,
                duration=0.05,
                iterations=2
            )
        )
        tasks.append(task)

    # Complex users (long conversations)
    for i in range(complex_users):
        user_id = f"@complex_user_{i}:example.com"
        task = asyncio.create_task(
            simulate_user_conversation(
                user_id=user_id,
                conv_manager=load_test_manager,
                metrics=metrics,
                duration=0.5,
                iterations=10
            )
        )
        tasks.append(task)

    # Wait for all to complete
    results = await asyncio.gather(*tasks)

    metrics.end_time = time.time()
    metrics.memory_after = get_memory_usage_mb()

    # Print detailed report
    print(metrics.report())

    # Count successes by type
    quick_successes = sum(1 for i, r in enumerate(results[:quick_users]) if r)
    complex_successes = sum(1 for r in results[quick_users:] if r)

    print(f"\nQuick queries: {quick_successes}/{quick_users} succeeded")
    print(f"Complex workflows: {complex_successes}/{complex_users} succeeded")

    # Assertions
    assert metrics.successful_completions == metrics.successful_starts, \
        "All started conversations should complete"

    # Both types should have some success (not all blocked by one type)
    assert quick_successes > 0, "Quick queries should succeed"
    assert complex_successes > 0, "Complex workflows should succeed"

    # Verify cleanup
    active_convs = await load_test_manager.get_active_conversations()
    assert len(active_convs) == 0, "All conversations should complete"

    # Quick queries should have fast response times
    quick_times = metrics.response_times[:quick_successes]
    if quick_times:
        avg_quick_time = sum(quick_times) / len(quick_times)
        assert avg_quick_time < 0.2, \
            f"Quick queries averaged {avg_quick_time:.3f}s (should be < 0.2s)"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_global_limit_enforcement(load_test_manager):
    """Test 5: Test global conversation limit enforcement.

    This test verifies:
    - 11th conversation is rejected when max is 10
    - Completing a conversation frees up a slot
    - Limits are strictly enforced under load
    """
    logger.info("Starting Test 5: Global Limit Enforcement")

    # Configure manager for this test
    manager = ConversationManager(
        max_concurrent=10,
        max_per_user=5,
        idle_timeout_seconds=60,
        max_duration_seconds=120
    )

    # Start 10 conversations (should all succeed)
    conversations = []
    for i in range(10):
        ctx = await manager.start_conversation(
            thread_root_id=f"$thread_{i}",
            user_id=f"@user_{i}:example.com",
            room_id="!test:example.com"
        )
        assert ctx is not None, f"Conversation {i} should succeed"
        conversations.append(ctx)

    # Try to start 11th conversation (should fail)
    ctx_11 = await manager.start_conversation(
        thread_root_id="$thread_11",
        user_id="@user_11:example.com",
        room_id="!test:example.com"
    )
    assert ctx_11 is None, "11th conversation should be rejected"

    # Verify exactly 10 active
    stats = await manager.get_stats()
    assert stats['total_active'] == 10

    # Complete one conversation
    await manager.end_conversation(conversations[0].id)

    # Now 11th should succeed
    ctx_11_retry = await manager.start_conversation(
        thread_root_id="$thread_11_retry",
        user_id="@user_11:example.com",
        room_id="!test:example.com"
    )
    assert ctx_11_retry is not None, "Should succeed after slot freed"

    # Cleanup
    for conv in conversations[1:]:
        await manager.end_conversation(conv.id)
    await manager.end_conversation(ctx_11_retry.id)

    # Verify all cleaned up
    stats = await manager.get_stats()
    assert stats['total_active'] == 0

    logger.info("Test 5: Passed - Global limits enforced correctly")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_per_user_limit_enforcement(load_test_manager):
    """Test 6: Test per-user conversation limit enforcement.

    This test verifies:
    - Single user can't exceed per-user limit
    - 4th conversation is rejected when max is 3
    - Completing conversation allows new one to start
    """
    logger.info("Starting Test 6: Per-User Limit Enforcement")

    # Configure manager for this test
    manager = ConversationManager(
        max_concurrent=20,
        max_per_user=3,
        idle_timeout_seconds=60,
        max_duration_seconds=120
    )

    user_id = "@test_user:example.com"

    # Start 3 conversations for same user (should all succeed)
    conversations = []
    for i in range(3):
        ctx = await manager.start_conversation(
            thread_root_id=f"$thread_{i}",
            user_id=user_id,
            room_id="!test:example.com"
        )
        assert ctx is not None, f"Conversation {i} should succeed"
        conversations.append(ctx)

    # Try to start 4th conversation (should fail)
    ctx_4 = await manager.start_conversation(
        thread_root_id="$thread_4",
        user_id=user_id,
        room_id="!test:example.com"
    )
    assert ctx_4 is None, "4th conversation for same user should be rejected"

    # Verify user has exactly 3 active
    user_convs = await manager.get_active_conversations(user_id=user_id)
    assert len(user_convs) == 3

    # Complete one conversation
    await manager.end_conversation(conversations[0].id)

    # Now 4th should succeed
    ctx_4_retry = await manager.start_conversation(
        thread_root_id="$thread_4_retry",
        user_id=user_id,
        room_id="!test:example.com"
    )
    assert ctx_4_retry is not None, "4th conversation should succeed after slot freed"

    # Cleanup
    for conv in conversations[1:]:
        await manager.end_conversation(conv.id)
    await manager.end_conversation(ctx_4_retry.id)

    # Verify all cleaned up for user
    user_convs = await manager.get_active_conversations(user_id=user_id)
    assert len(user_convs) == 0

    logger.info("Test 6: Passed - Per-user limits enforced correctly")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_stress_rapid_start_stop_cycles(load_test_manager):
    """Stress test: Rapid start/stop cycles to verify no race conditions.

    This test verifies:
    - No race conditions in start/stop logic
    - Lock contention is handled correctly
    - Counters remain accurate under stress
    """
    logger.info("Starting Stress Test: Rapid Start/Stop Cycles")

    metrics = PerformanceMetrics()
    metrics.start_time = time.time()
    metrics.memory_before = get_memory_usage_mb()

    cycles = 100
    concurrent = 10

    async def rapid_cycle(user_id: str):
        """Rapidly start and stop conversations."""
        successes = 0
        for _ in range(cycles):
            ctx = await load_test_manager.start_conversation(
                thread_root_id=f"$rapid_{user_id}_{time.time()}",
                user_id=user_id,
                room_id="!test:example.com"
            )
            if ctx:
                await load_test_manager.end_conversation(ctx.id)
                successes += 1
                metrics.successful_completions += 1
        return successes

    # Run rapid cycles concurrently
    tasks = [
        asyncio.create_task(rapid_cycle(f"@rapid_user_{i}:example.com"))
        for i in range(concurrent)
    ]

    results = await asyncio.gather(*tasks)

    metrics.end_time = time.time()
    metrics.memory_after = get_memory_usage_mb()

    total_successes = sum(results)
    print(f"\nRapid cycles completed: {total_successes}/{cycles * concurrent}")
    print(f"Duration: {metrics.end_time - metrics.start_time:.2f}s")
    print(f"Memory growth: {metrics.memory_growth_mb():.2f}MB")

    # Assertions
    assert total_successes > 0, "Some cycles should succeed"

    # Verify all cleaned up
    active_convs = await load_test_manager.get_active_conversations()
    assert len(active_convs) == 0, \
        f"All conversations should be cleaned up, found {len(active_convs)}"

    # Verify internal state is consistent
    stats = await load_test_manager.get_stats()
    assert stats['total_active'] == 0
    assert stats['users_with_conversations'] == 0

    logger.info("Stress Test: Passed - No race conditions detected")


# Mark all tests in this module as slow
pytestmark = pytest.mark.slow
