# Load Testing Suite

## Quick Start

Run all load tests:
```bash
./scripts/run_load_tests.sh
```

Run quick verification test:
```bash
./scripts/run_load_tests.sh --quick
```

Run specific test:
```bash
pytest tests/test_load_concurrency.py::test_concurrent_user_load_50_users -v -s
```

## Test Coverage

The load testing suite (`test_load_concurrency.py`) provides 7 comprehensive tests:

1. **test_concurrent_user_load_50_users** - 50 simultaneous users
2. **test_sustained_load_5_minutes** - Continuous load for 30 seconds (abbreviated)
3. **test_burst_load_pattern** - 5 bursts of 20 users each
4. **test_mixed_workload_patterns** - Mix of quick and complex conversations
5. **test_global_limit_enforcement** - Verify global conversation limits
6. **test_per_user_limit_enforcement** - Verify per-user limits
7. **test_stress_rapid_start_stop_cycles** - 1000 rapid start/stop cycles

All tests verify:
- Correct limit enforcement
- No memory leaks
- Proper cleanup
- Acceptable response times
- No race conditions

## Performance Metrics

Each test reports:
- **Response Times**: Min, Max, Mean, P50, P95, P99
- **Success Rate**: Percentage of successful operations
- **Throughput**: Conversations per second
- **Memory Usage**: Before, After, Peak, Growth

## Expected Results

### Test 1: 50 Concurrent Users
- **Duration**: ~0.2 seconds
- **Successful Starts**: 20 (max_concurrent limit)
- **Failed Starts**: 30 (correctly rejected)
- **P95 Response Time**: < 5 seconds
- **Memory Growth**: < 50MB

### Test 2: Sustained Load (30s)
- **Duration**: ~30 seconds
- **Total Conversations**: 100-300 depending on timing
- **Throughput**: > 1 conversation/sec
- **Memory Growth**: < 100MB (stable over time)

### Test 3: Burst Load Pattern
- **Duration**: ~3-5 seconds
- **Total Bursts**: 5
- **Per Burst**: 20 users
- **Successful Per Burst**: 20 (max_concurrent)
- **Memory Growth**: < 30MB

### Test 4: Mixed Workload
- **Duration**: ~3-5 seconds
- **Quick Users**: 15 (1-2 iterations each)
- **Complex Users**: 5 (10+ iterations each)
- **Quick Avg Response**: < 0.2 seconds
- **Both types succeed**: True

### Test 5: Global Limit
- **Duration**: ~0.1 seconds
- **Tests**: Start 10, reject 11th, free slot, accept 11th
- **Result**: Limits enforced correctly

### Test 6: Per-User Limit
- **Duration**: ~0.1 seconds
- **Tests**: Start 3, reject 4th, free slot, accept 4th
- **Result**: Per-user limits enforced correctly

### Test 7: Stress Test
- **Duration**: ~5-10 seconds
- **Total Cycles**: 1000 (10 users × 100 cycles)
- **Successful**: Variable (depends on concurrency)
- **Final State**: 0 active conversations, consistent counters

## Interpreting Failures

### Assertion: "P95 response time exceeds 5s threshold"
**Cause**: System is too slow under load
**Check**:
- Lock contention in ConversationManager
- Blocking I/O operations
- CPU/memory constraints on test machine

### Assertion: "Memory growth exceeds threshold"
**Cause**: Possible memory leak
**Check**:
- Conversations not being freed after end_conversation
- Leaked references in _user_conversations dict
- Background tasks not cleaning up

### Assertion: "Expected 0 active conversations after cleanup"
**Cause**: Cleanup not working correctly
**Check**:
- end_conversation being called for all started conversations
- No exceptions during conversation processing
- Lock not being held during cleanup

### Assertion: "Success rate < 100%"
**Cause**: Accepted conversations are failing
**Check**:
- Exceptions in simulate_user_conversation
- Network/I/O failures
- Unexpected errors in conversation handling

## Customization

### Adjust Limits

Edit `load_test_manager` fixture in `test_load_concurrency.py`:

```python
@pytest.fixture
def load_test_manager():
    return ConversationManager(
        max_concurrent=50,     # Change from 20
        max_per_user=10,       # Change from 5
        idle_timeout_seconds=120,
        max_duration_seconds=300
    )
```

### Adjust Test Duration

For full 5-minute sustained load test:

```python
# In test_sustained_load_5_minutes
duration_seconds = 300  # Change from 30
```

### Adjust User Counts

```python
# In test_concurrent_user_load_50_users
for i in range(100):  # Change from 50
```

## Troubleshooting

### Import Errors
```bash
pip install -r requirements.txt
```

### Tests Timeout
```bash
pytest tests/test_load_concurrency.py -v --timeout=300
```

### Flaky Tests
```bash
pytest tests/test_load_concurrency.py -v --reruns 3
```

### Memory Errors
Reduce concurrent users in tests or increase system resources.

## CI Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Run Load Tests
  run: |
    pip install -r requirements.txt
    pytest tests/test_load_concurrency.py -v -m slow
```

## More Information

See [docs/LOAD_TESTING.md](/Users/chrisowen/Documents/Code/MatrixBot/docs/LOAD_TESTING.md) for comprehensive documentation.
