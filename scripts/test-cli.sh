#!/usr/bin/env bash
#
# Tengil CLI Smoke Tests
#
# Runs all CLI commands with --help to ensure they don't crash.
# Uses TG_MOCK=1 to avoid requiring real Proxmox infrastructure.
#
# Usage:
#   ./scripts/test-cli.sh
#

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
TOTAL=0

# Helper function to run a test
run_test() {
    local description="$1"
    local command="$2"
    TOTAL=$((TOTAL + 1))

    echo -n "Testing: $description ... "

    if eval "TG_MOCK=1 $command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}✗${NC}"
        FAILED=$((FAILED + 1))
        echo "  Command: $command"
    fi
}

# Header
echo "========================================="
echo "Tengil CLI Smoke Tests"
echo "========================================="
echo ""

# Main CLI
echo "Main CLI Commands:"
run_test "tg --help" "python3 -m tengil.cli --help"
run_test "tg version" "python3 -m tengil.cli version"
run_test "tg doctor" "python3 -m tengil.cli doctor"

echo ""

# Container Commands
echo "Container Commands:"
run_test "tg container --help" "python3 -m tengil.cli container --help"
run_test "tg container exec --help" "python3 -m tengil.cli container exec --help"
run_test "tg container shell --help" "python3 -m tengil.cli container shell --help"
run_test "tg container start --help" "python3 -m tengil.cli container start --help"
run_test "tg container stop --help" "python3 -m tengil.cli container stop --help"
run_test "tg container restart --help" "python3 -m tengil.cli container restart --help"

echo ""

# App Commands
echo "App Commands:"
run_test "tg app --help" "python3 -m tengil.cli app --help"
run_test "tg app sync --help" "python3 -m tengil.cli app sync --help"
run_test "tg app list --help" "python3 -m tengil.cli app list --help"

echo ""

# Compose Commands
echo "Compose Commands:"
run_test "tg compose --help" "python3 -m tengil.cli compose --help"
run_test "tg compose analyze --help" "python3 -m tengil.cli compose analyze --help"
run_test "tg compose validate --help" "python3 -m tengil.cli compose validate --help"
run_test "tg compose resolve --help" "python3 -m tengil.cli compose resolve --help"

echo ""

# Discover Commands
echo "Discover Commands:"
run_test "tg discover --help" "python3 -m tengil.cli discover --help"
run_test "tg discover datasets --help" "python3 -m tengil.cli discover datasets --help"
run_test "tg discover containers --help" "python3 -m tengil.cli discover containers --help"
run_test "tg discover docker --help" "python3 -m tengil.cli discover docker --help"

echo ""

# Env Commands
echo "Env Commands:"
run_test "tg env --help" "python3 -m tengil.cli env --help"
run_test "tg env list --help" "python3 -m tengil.cli env list --help"
run_test "tg env set --help" "python3 -m tengil.cli env set --help"
run_test "tg env sync --help" "python3 -m tengil.cli env sync --help"

echo ""

# Core Infrastructure Commands
echo "Core Infrastructure Commands:"
run_test "tg diff --help" "python3 -m tengil.cli diff --help"
run_test "tg apply --help" "python3 -m tengil.cli apply --help"
run_test "tg init --help" "python3 -m tengil.cli init --help"
run_test "tg import --help" "python3 -m tengil.cli import --help"
run_test "tg snapshot --help" "python3 -m tengil.cli snapshot --help"
run_test "tg rollback --help" "python3 -m tengil.cli rollback --help"
run_test "tg templates --help" "python3 -m tengil.cli templates --help"
run_test "tg packages --help" "python3 -m tengil.cli packages --help"

echo ""

# Summary
echo "========================================="
echo "Test Summary:"
echo "  Total:  $TOTAL"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "  ${RED}Failed: $FAILED${NC}"
    exit 1
else
    echo -e "  ${GREEN}All tests passed!${NC}"
    exit 0
fi
