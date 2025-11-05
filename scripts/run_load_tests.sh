#!/bin/bash
# Load Test Runner Script
# Runs comprehensive load tests with formatted output

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "========================================================================"
echo "                   MATRIXBOT LOAD TEST SUITE                           "
echo "========================================================================"
echo ""

# Check for required dependencies
echo "Checking dependencies..."
python3 -c "import psutil" 2>/dev/null || {
    echo -e "${RED}Error: psutil not installed${NC}"
    echo "Install with: pip install psutil"
    exit 1
}

python3 -c "import pytest" 2>/dev/null || {
    echo -e "${RED}Error: pytest not installed${NC}"
    echo "Install with: pip install pytest pytest-asyncio"
    exit 1
}

echo -e "${GREEN}✓ All dependencies installed${NC}"
echo ""

# Parse command line arguments
TEST_PATTERN="tests/test_load_concurrency.py"
VERBOSE="-v"
SHOW_OUTPUT="-s"

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            TEST_PATTERN="tests/test_load_concurrency.py::test_global_limit_enforcement"
            shift
            ;;
        --no-output)
            SHOW_OUTPUT=""
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick       Run only quick tests (limit enforcement)"
            echo "  --no-output   Don't show detailed test output"
            echo "  --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run all load tests"
            echo "  $0 --quick            # Run only quick tests"
            echo "  $0 --no-output        # Run without detailed output"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run the tests
echo "Running load tests..."
echo "Pattern: $TEST_PATTERN"
echo ""

START_TIME=$(date +%s)

if python3 -m pytest "$TEST_PATTERN" $VERBOSE $SHOW_OUTPUT -m slow --tb=short; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    echo "========================================================================"
    echo -e "${GREEN}✓ ALL LOAD TESTS PASSED${NC}"
    echo "========================================================================"
    echo "Duration: ${DURATION}s"
    echo ""
    echo "Next steps:"
    echo "  - Review performance metrics in test output above"
    echo "  - Check for any warnings or performance degradation"
    echo "  - Compare with baseline metrics from previous runs"
    echo ""
    exit 0
else
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    echo "========================================================================"
    echo -e "${RED}✗ LOAD TESTS FAILED${NC}"
    echo "========================================================================"
    echo "Duration: ${DURATION}s"
    echo ""
    echo "Troubleshooting:"
    echo "  - Review test output above for specific failures"
    echo "  - Check if memory/CPU resources are constrained"
    echo "  - Review docs/LOAD_TESTING.md for debugging tips"
    echo ""
    exit 1
fi
