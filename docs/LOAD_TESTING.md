# Load Testing Guide

This document describes the load testing infrastructure for the MatrixBot concurrent conversation system.

## Overview

The load testing suite (`tests/test_load_concurrency.py`) provides comprehensive tests to verify that the conversation management system can handle production workloads correctly. These tests simulate realistic user behavior patterns and measure performance characteristics.

## Installation

Install the test dependencies:

```bash
pip install -r requirements.txt
```

The load tests require `psutil` for memory monitoring, which is included in requirements.txt.

## Running Load Tests

### Quick Test (Excludes Slow Tests)

Run all tests except slow load tests:

```bash
pytest -v -m "not slow"
```

### Run Only Load Tests

Run only the load tests:

```bash
pytest tests/test_load_concurrency.py -v -m slow
```

### Run Specific Load Test

Run a single load test by name:

```bash
pytest tests/test_load_concurrency.py::test_concurrent_user_load_50_users -v
```

### Run All Tests (Including Load Tests)

Run everything:

```bash
pytest -v
```

## Test Scenarios

### Test 1: Concurrent User Load (50+ Users)

**Purpose**: Verify system handles high concurrent user load

**Test**: `test_concurrent_user_load_50_users`

**Simulates**:
- 50 users sending requests simultaneously
- Each user completes a 2-iteration conversation
- Total work time: ~0.1 seconds per conversation

**Verifies**:
- All requests are handled (20 succeed, 30 rejected due to limit)
- Response times are reasonable (P95 < 5 seconds)
- No memory leaks (< 50MB growth)
- No conversation cross-talk
- All conversations clean up properly

**Expected Duration**: ~5-10 seconds

### Test 2: Sustained Load

**Purpose**: Verify system handles continuous load without degradation

**Test**: `test_sustained_load_5_minutes`

**Simulates**:
- 10 concurrent users continuously for 30 seconds
- Each user completes conversation and starts new one
- Realistic continuous operation pattern

**Verifies**:
- Throughput remains consistent (> 1 conversation/sec)
- Memory remains stable (< 100MB growth over time)
- Cleanup tasks work correctly
- No resource exhaustion

**Expected Duration**: ~30 seconds (abbreviated from 5 minutes for testing)

**Note**: For full 5-minute test, modify `duration_seconds = 300` in the test code.

### Test 3: Burst Load Pattern

**Purpose**: Test burst handling and recovery

**Test**: `test_burst_load_pattern`

**Simulates**:
- 5 bursts of 20 simultaneous users
- 0.5 second pause between bursts
- Tests sudden traffic spikes

**Verifies**:
- System handles sudden spikes correctly
- Rate limiter enforces limits
- Clean recovery between bursts
- No resource exhaustion

**Expected Duration**: ~5-8 seconds

### Test 4: Mixed Workload Patterns

**Purpose**: Verify different conversation types coexist properly

**Test**: `test_mixed_workload_patterns`

**Simulates**:
- 15 quick users (1-2 iterations, ~0.05s each)
- 5 complex users (10+ iterations, ~0.5s total)
- Realistic mix of query types

**Verifies**:
- Quick queries don't block complex workflows
- Both types get fair resource allocation
- No blocking between conversation types
- Response times appropriate for each type

**Expected Duration**: ~3-5 seconds

### Test 5: Global Limit Enforcement

**Purpose**: Verify global conversation limits work correctly

**Test**: `test_global_limit_enforcement`

**Simulates**:
- Start 10 conversations (max limit)
- Try to start 11th (should fail)
- Complete one and retry (should succeed)

**Verifies**:
- Limits are strictly enforced
- Completing conversation frees slot
- No race conditions in limit checking

**Expected Duration**: ~1 second

### Test 6: Per-User Limit Enforcement

**Purpose**: Verify per-user conversation limits work correctly

**Test**: `test_per_user_limit_enforcement`

**Simulates**:
- Single user starts 3 conversations (max per-user limit)
- Tries to start 4th (should fail)
- Completes one and retries (should succeed)

**Verifies**:
- Per-user limits enforced correctly
- Other users not affected by one user's limit
- Completing conversation frees user's slot

**Expected Duration**: ~1 second

### Test 7: Stress - Rapid Start/Stop Cycles

**Purpose**: Verify no race conditions under extreme load

**Test**: `test_stress_rapid_start_stop_cycles`

**Simulates**:
- 10 users each doing 100 rapid start/stop cycles
- 1000 total conversations
- Minimal work per conversation

**Verifies**:
- No race conditions in start/stop logic
- Lock contention handled correctly
- Counters remain accurate
- Internal state consistent

**Expected Duration**: ~5-10 seconds

## Performance Metrics

Each test collects and reports detailed metrics:

### Response Time Metrics
- **Count**: Number of completed requests
- **Min/Max**: Fastest and slowest response times
- **Mean**: Average response time
- **P50 (Median)**: 50th percentile
- **P95**: 95th percentile (95% of requests faster than this)
- **P99**: 99th percentile

### Queue Wait Times
- For requests that had to wait for a slot
- Mean and P95 wait times

### Success Metrics
- **Successful starts**: Conversations accepted
- **Failed starts**: Conversations rejected (at limit)
- **Successful completions**: Conversations completed
- **Success rate**: Percentage of successful starts

### Throughput
- **Duration**: Total test duration
- **Throughput**: Conversations per second

### Memory Usage
- **Before**: Memory usage at test start (MB)
- **After**: Memory usage at test end (MB)
- **Peak**: Maximum memory during test (MB)
- **Growth**: Net memory increase (MB)

## Performance Thresholds

The tests enforce these performance requirements:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| P95 Response Time | < 5 seconds | 95% of users get fast response |
| Throughput | > 1 conversation/sec | Minimum acceptable throughput |
| Memory Growth (50 users) | < 50MB | No significant memory leaks |
| Memory Growth (sustained) | < 100MB | Stable under continuous load |
| Memory Growth (burst) | < 30MB | Efficient burst handling |
| Success Rate | 100% | All accepted conversations complete |
| Cleanup | 0 active conversations | Perfect cleanup after completion |

## Interpreting Results

### Good Results
```
Response Times:
  P50: 0.150s
  P95: 0.280s
  P99: 0.450s

Throughput: 15.2 conversations/sec
Memory Growth: 12.3 MB
Success Rate: 100.0%
```

### Warning Signs
```
Response Times:
  P95: 8.500s  ⚠️ Exceeds 5s threshold

Memory Growth: 75.2 MB  ⚠️ Possible leak

Success Rate: 87.5%  ⚠️ Should be 100% for accepted conversations
```

### Investigation Tips

**High P95 Response Times**:
- Check for lock contention in ConversationManager
- Review async/await patterns for blocking calls
- Check if cleanup tasks are interfering

**Memory Growth**:
- Look for conversation contexts not being freed
- Check for leaked references in user_conversations dict
- Review background task cleanup logic

**Low Success Rate**:
- Should be 100% for conversations that started
- If < 100%, check for exceptions in simulate_user_conversation
- Review error handling in end_conversation

**Low Throughput**:
- Check if artificial delays are too long
- Review lock contention issues
- Consider increasing max_concurrent limit

## Customizing Tests

### Adjust Concurrency Limits

Modify the `load_test_manager` fixture:

```python
@pytest.fixture
def load_test_manager():
    return ConversationManager(
        max_concurrent=50,  # Increase global limit
        max_per_user=10,    # Increase per-user limit
        idle_timeout_seconds=120,
        max_duration_seconds=300
    )
```

### Adjust Test Duration

For longer sustained load test:

```python
# In test_sustained_load_5_minutes
duration_seconds = 300  # 5 minutes
```

### Adjust User Counts

Modify test parameters:

```python
# In test_concurrent_user_load_50_users
for i in range(100):  # Test with 100 users instead of 50
```

### Add Custom Metrics

Extend `PerformanceMetrics` class:

```python
@dataclass
class PerformanceMetrics:
    # ... existing fields ...
    custom_metric: List[float] = field(default_factory=list)
```

## Continuous Integration

To run load tests in CI:

```yaml
# .github/workflows/load-tests.yml
name: Load Tests
on: [push, pull_request]
jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/test_load_concurrency.py -v -m slow --tb=short
```

## Troubleshooting

### Tests Time Out

Increase pytest timeout:
```bash
pytest tests/test_load_concurrency.py -v --timeout=300
```

### Memory Errors

Reduce concurrent users:
```python
concurrent_users = 5  # Instead of 10
```

### Flaky Tests

Add retries:
```bash
pytest tests/test_load_concurrency.py -v --reruns 3
```

## Best Practices

1. **Run load tests separately** from unit tests (use `-m slow` marker)
2. **Monitor system resources** during tests (CPU, memory, disk I/O)
3. **Run on dedicated hardware** for consistent results
4. **Establish baseline metrics** and track changes over time
5. **Investigate degradation** immediately when metrics worsen
6. **Update thresholds** as system capabilities improve

## Future Enhancements

Potential additions to the load testing suite:

- **Network latency simulation**: Add artificial delays to simulate real-world conditions
- **Database load**: Test with actual database operations instead of sleep
- **Chaos testing**: Random failures during conversation processing
- **Long-running stability**: 24-hour continuous load test
- **Scalability testing**: Gradually increase load to find breaking point
- **Resource profiling**: CPU and I/O profiling during tests
- **Comparison reports**: Track metrics over time and generate trend reports
