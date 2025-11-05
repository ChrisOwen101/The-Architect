# Testing Strategy

## Overview

The MatrixBot testing infrastructure consists of three layers:

1. **Unit Tests** - Fast, isolated tests of individual components
2. **Integration Tests** - Tests of component interactions
3. **Load Tests** - Production workload simulation and performance verification

## Test Organization

```
tests/
├── test_*.py                    # Unit and integration tests
├── test_load_concurrency.py     # Load tests (marked @pytest.mark.slow)
├── commands/                    # Command-specific tests
└── conftest.py                  # Shared fixtures
```

## Running Tests

### All Tests (Excluding Load Tests)
```bash
pytest -v -m "not slow"
```
**Duration**: ~1-2 minutes
**Use Case**: Regular development, CI/CD pipelines

### Only Load Tests
```bash
pytest tests/test_load_concurrency.py -v -m slow
# OR
./scripts/run_load_tests.sh
```
**Duration**: ~30-40 seconds
**Use Case**: Performance verification, before releases

### Quick Load Test
```bash
./scripts/run_load_tests.sh --quick
```
**Duration**: ~1 second
**Use Case**: Quick verification of limits

### All Tests (Including Load Tests)
```bash
pytest -v
```
**Duration**: ~2-3 minutes
**Use Case**: Comprehensive verification before major releases

### Specific Test File
```bash
pytest tests/test_conversation_manager.py -v
```

### Specific Test
```bash
pytest tests/test_load_concurrency.py::test_concurrent_user_load_50_users -v
```

## Test Categories

### Unit Tests
**Location**: `tests/test_*.py`
**Markers**: None (default)
**Characteristics**:
- Fast execution (milliseconds to seconds)
- Isolated components
- Mocked dependencies
- 100% deterministic

**Examples**:
- `test_conversation_manager.py` - ConversationManager logic
- `test_memory_store.py` - Memory storage operations
- `test_command_registry.py` - Command registration

### Integration Tests
**Location**: `tests/test_integration_*.py`, `tests/test_concurrent_*.py`
**Markers**: None (default)
**Characteristics**:
- Moderate execution time (seconds)
- Multiple components working together
- Some real I/O operations
- Mostly deterministic

**Examples**:
- `test_integration_concurrency.py` - Full conversation flow
- `test_concurrent_features.py` - Concurrent operations
- `test_openai_integration.py` - AI reply generation

### Load Tests
**Location**: `tests/test_load_concurrency.py`
**Markers**: `@pytest.mark.slow`
**Characteristics**:
- Longer execution time (seconds to minutes)
- Simulates production workloads
- Performance metrics collection
- May have slight timing variations

**Examples**:
- `test_concurrent_user_load_50_users` - High user load
- `test_sustained_load_5_minutes` - Continuous operation
- `test_stress_rapid_start_stop_cycles` - Stress testing

## Test Markers

Configure in `pytest.ini`:

```ini
markers =
    slow: marks tests as slow (load tests, stress tests)
    unit: marks tests as unit tests (default, fast)
    integration: marks tests as integration tests
```

Usage:
```bash
pytest -m slow           # Run only slow tests
pytest -m "not slow"     # Skip slow tests
pytest -m unit           # Run only unit tests
```

## Coverage Goals

### Unit Tests
- **Target Coverage**: 90%+
- **Critical Components**: 95%+
  - ConversationManager
  - MemoryStore
  - CommandRegistry
  - RateLimiter

### Integration Tests
- **Target**: All major user flows
- **Scenarios**:
  - Full conversation lifecycle
  - Concurrent operations
  - Error handling paths
  - Edge cases

### Load Tests
- **Target**: All production scenarios
- **Scenarios**:
  - Expected load (normal operations)
  - Peak load (traffic spikes)
  - Sustained load (continuous operation)
  - Stress conditions (beyond capacity)

## Continuous Integration

### Pre-Commit (Local)
```bash
pytest -v -m "not slow"
```

### Pull Request (CI)
```yaml
- name: Run Tests
  run: |
    pytest -v -m "not slow" --cov=bot --cov-report=term
```

### Nightly Build (CI)
```yaml
- name: Run All Tests
  run: |
    pytest -v --cov=bot --cov-report=html
```

### Release Candidate (CI)
```yaml
- name: Run Load Tests
  run: |
    pytest tests/test_load_concurrency.py -v -m slow
```

## Performance Baselines

Track these metrics over time:

### Unit Tests
- **Total Duration**: < 2 minutes
- **Average Test**: < 1 second
- **Slowest Test**: < 15 seconds

### Load Tests
- **P95 Response Time**: < 5 seconds
- **Throughput**: > 1 conversation/sec
- **Memory Growth (50 users)**: < 50MB
- **Memory Growth (sustained)**: < 100MB
- **Success Rate**: 100% for accepted conversations

## Troubleshooting

### Slow Test Suite
**Symptom**: Unit tests take > 5 minutes

**Solutions**:
- Run with `-m "not slow"` to exclude load tests
- Use `-x` to stop on first failure
- Run specific test files instead of full suite

### Flaky Tests
**Symptom**: Tests pass/fail inconsistently

**Solutions**:
- Check for timing dependencies (add delays if needed)
- Review async/await usage
- Ensure proper test isolation
- Use `pytest --reruns 3` to identify flaky tests

### Memory Issues
**Symptom**: Tests killed due to memory usage

**Solutions**:
- Run load tests separately
- Reduce concurrent users in load tests
- Check for memory leaks with `pytest --memprof`

### Import Errors
**Symptom**: `ModuleNotFoundError`

**Solutions**:
```bash
pip install -r requirements.txt
```

### Timeout Errors
**Symptom**: Tests timeout

**Solutions**:
```bash
pytest --timeout=300  # 5 minute timeout
```

## Best Practices

### Writing Tests

1. **Use descriptive names**
   ```python
   def test_conversation_manager_rejects_11th_concurrent_conversation():
   ```

2. **Follow AAA pattern**
   ```python
   # Arrange
   manager = ConversationManager(max_concurrent=10)

   # Act
   result = await manager.start_conversation(...)

   # Assert
   assert result is None
   ```

3. **Test one thing per test**
   - Each test should verify a single behavior
   - Use multiple assertions for same behavior
   - Split complex scenarios into multiple tests

4. **Use fixtures for common setup**
   ```python
   @pytest.fixture
   def conversation_manager():
       return ConversationManager(max_concurrent=5)
   ```

5. **Mock external dependencies**
   ```python
   @patch('bot.openai_integration.call_openai_api')
   async def test_ai_reply(mock_api):
       mock_api.return_value = {"response": "Hello"}
   ```

### Running Tests

1. **Run frequently during development**
   ```bash
   pytest tests/test_conversation_manager.py -v
   ```

2. **Run full suite before commits**
   ```bash
   pytest -v -m "not slow"
   ```

3. **Run load tests before releases**
   ```bash
   ./scripts/run_load_tests.sh
   ```

4. **Use `-x` to stop on first failure**
   ```bash
   pytest -v -x
   ```

5. **Use `-k` to run matching tests**
   ```bash
   pytest -k "conversation" -v
   ```

### Debugging Tests

1. **Use `-s` to see print output**
   ```bash
   pytest tests/test_file.py -v -s
   ```

2. **Use `--tb=short` for concise tracebacks**
   ```bash
   pytest -v --tb=short
   ```

3. **Use `--pdb` to drop into debugger on failure**
   ```bash
   pytest tests/test_file.py --pdb
   ```

4. **Use `-vv` for extra verbose output**
   ```bash
   pytest -vv
   ```

## Metrics and Reporting

### Coverage Report
```bash
pytest --cov=bot --cov-report=html
open htmlcov/index.html
```

### Test Duration Report
```bash
pytest --durations=10
```

### Verbose Output
```bash
pytest -v --tb=short
```

## Related Documentation

- [Load Testing Guide](LOAD_TESTING.md) - Detailed load test documentation
- [tests/README_LOAD_TESTS.md](/Users/chrisowen/Documents/Code/MatrixBot/tests/README_LOAD_TESTS.md) - Quick reference for load tests
- [pytest.ini](/Users/chrisowen/Documents/Code/MatrixBot/pytest.ini) - Test configuration

## Future Enhancements

### Planned Additions

1. **Mutation Testing**
   - Use `mutmut` to verify test quality
   - Ensure tests catch real bugs

2. **Property-Based Testing**
   - Use `hypothesis` for edge case discovery
   - Test with random inputs

3. **Performance Regression Testing**
   - Track metrics over time
   - Alert on performance degradation

4. **Contract Testing**
   - Verify API contracts
   - Ensure backward compatibility

5. **Chaos Engineering**
   - Random failure injection
   - Network latency simulation
   - Resource exhaustion testing
