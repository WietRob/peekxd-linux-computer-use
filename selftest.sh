#!/usr/bin/env bash
# peekxd for Linux — Self-Test / Acceptance Suite
# Usage: ./selftest.sh [--verbose] [--module MODULE]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERBOSE="${VERBOSE:-0}"
MODULE_FILTER="all"
VALID_MODULES=(all unit desktop screenshot input inspection window vision cli config mcp)

usage() {
    cat <<EOF
Usage: ./selftest.sh [--verbose] [--module MODULE]
       ./selftest.sh [MODULE]

Modules: ${VALID_MODULES[*]}
EOF
}

is_valid_module() {
    local candidate="$1"
    local module
    for module in "${VALID_MODULES[@]}"; do
        if [[ "$candidate" == "$module" ]]; then
            return 0
        fi
    done
    return 1
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --module|-m)
                if [[ $# -lt 2 || "$2" == --* ]]; then
                    echo "Missing module name after $1" >&2
                    usage >&2
                    exit 2
                fi
                MODULE_FILTER="$2"
                shift 2
                ;;
            --verbose|-v)
                VERBOSE=1
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            --*)
                echo "Unknown option: $1" >&2
                usage >&2
                exit 2
                ;;
            *)
                if [[ "$MODULE_FILTER" != "all" ]]; then
                    echo "Unexpected argument: $1" >&2
                    usage >&2
                    exit 2
                fi
                MODULE_FILTER="$1"
                shift
                ;;
        esac
    done

    if ! is_valid_module "$MODULE_FILTER"; then
        echo "Unknown module: $MODULE_FILTER" >&2
        usage >&2
        exit 2
    fi
}

PASSED=0
FAILED=0
WARNINGS=0

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}PASS${NC}: $1"
    PASSED=$((PASSED + 1))
}

fail() {
    echo -e "${RED}FAIL${NC}: $1"
    if [[ $# -gt 1 ]]; then
        echo "      $2"
    fi
    FAILED=$((FAILED + 1))
}

warn() {
    echo -e "${YELLOW}WARN${NC}: $1"
    WARNINGS=$((WARNINGS + 1))
}

header() {
    echo ""
    echo "=== $1 ==="
}

# --- Python tests ---
test_python_unit() {
    header "Python Unit Tests"
    cd "$SCRIPT_DIR"

    if ! python3 -m pytest tests/ -v --tb=short --ignore tests/test_selftest.py 2>&1 | tee /tmp/peekxd_test.log; then
        fail "Unit tests" "See /tmp/peekxd_test.log"
    else
        local count
        count=$(grep -c "PASSED" /tmp/peekxd_test.log || echo "0")
        pass "Unit tests ($count tests)"
    fi
}

# --- Screenshot ---
test_screenshot() {
    header "Screenshot Module"

    python3 -c "
from peekxd.screenshot import get_screenshot_provider
try:
    p = get_screenshot_provider()
    print('Provider:', type(p).__name__)
    print('Available: True')
except Exception as e:
    print('Available: False -', e)
" 2>&1 | while read -r line; do
        if [[ "$line" == *"Provider:"* ]]; then
            pass "Screenshot provider detected: ${line#Provider: }"
        elif [[ "$line" == *"Available: False"* ]]; then
            warn "Screenshot: ${line#Available: False - }"
        fi
    done
}

# --- Input ---
test_input() {
    header "Input Module"

    python3 -c "
from peekxd.input import get_input_provider
try:
    p = get_input_provider()
    print('Provider:', type(p).__name__)
    print('Available: True')
except Exception as e:
    print('Available: False -', e)
" 2>&1 | while read -r line; do
        if [[ "$line" == *"Provider:"* ]]; then
            pass "Input provider detected: ${line#Provider: }"
        elif [[ "$line" == *"Available: False"* ]]; then
            warn "Input: ${line#Available: False - }"
        fi
    done
}

# --- Inspection ---
test_inspection() {
    header "Inspection Module"

    python3 -c "
from peekxd.inspection import get_inspection_provider
try:
    p = get_inspection_provider()
    print('Provider:', type(p).__name__)
    print('Available: True')
except Exception as e:
    print('Available: False -', e)
" 2>&1 | while read -r line; do
        if [[ "$line" == *"Provider:"* ]]; then
            pass "Inspection provider detected: ${line#Provider: }"
        elif [[ "$line" == *"Available: False"* ]]; then
            warn "Inspection: ${line#Available: False - }"
        fi
    done
}

# --- Window ---
test_window() {
    header "Window Module"

    python3 -c "
from peekxd.window import get_window_provider
try:
    p = get_window_provider()
    print('Provider:', type(p).__name__)
    print('Available: True')
except Exception as e:
    print('Available: False -', e)
" 2>&1 | while read -r line; do
        if [[ "$line" == *"Provider:"* ]]; then
            pass "Window provider detected: ${line#Provider: }"
        elif [[ "$line" == *"Available: False"* ]]; then
            warn "Window: ${line#Available: False - }"
        fi
    done
}

# --- Vision ---
test_vision() {
    header "Vision Module"

    python3 -c "
from peekxd.vision import get_vision_provider
try:
    p = get_vision_provider()
    print('Provider:', p.name)
    print('Available: True')
except Exception as e:
    print('Available: False -', e)
" 2>&1 | while read -r line; do
        if [[ "$line" == *"Provider:"* ]]; then
            pass "Vision provider detected: ${line#Provider: }"
        elif [[ "$line" == *"Available: False"* ]]; then
            warn "Vision: ${line#Available: False - }"
        fi
    done
}

# --- CLI ---
test_cli() {
    header "CLI"

    if command -v peekxd &>/dev/null; then
        local ver
        ver=$(peekxd version 2>&1 || echo "unknown")
        pass "CLI installed: $ver"
    else
        warn "CLI not in PATH (pip install may be needed)"
    fi
}

# --- Desktop detection ---
test_desktop() {
    header "Desktop Environment"

    python3 -c "
from peekxd.core import detect_desktop
d = detect_desktop()
print(f'Detected: {d.value}')
" 2>&1 | while read -r line; do
        if [[ "$line" == *"Detected:"* ]]; then
            pass "Desktop: ${line#Detected: }"
        fi
    done
}

# --- Config ---
test_config() {
    header "Configuration"

    python3 -c "
from peekxd.config import ConfigManager
c = ConfigManager()
print('Config OK')
" 2>&1 | while read -r line; do
        if [[ "$line" == *"Config OK"* ]]; then
            pass "Configuration module"
        fi
    done
}

# --- MCP ---
test_mcp() {
    header "MCP Server"

    python3 -c "
try:
    from peekxd.mcp_server import create_mcp_server
    print('MCP OK')
except ImportError as e:
    print(f'MCP import failed: {e}')
" 2>&1 | while read -r line; do
        if [[ "$line" == *"MCP OK"* ]]; then
            pass "MCP server module"
        elif [[ "$line" == *"MCP import failed"* ]]; then
            warn "MCP: ${line#MCP import failed: }"
        fi
    done
}

# --- Main ---
main() {
    echo "=== peekxd for Linux — Acceptance Suite ==="
    echo "Date: $(date)"
    echo "Python: $(python3 --version 2>&1)"
    echo "Platform: $(uname -a)"
    echo ""

    case "$MODULE_FILTER" in
        all|unit) test_python_unit ;;
    esac

    case "$MODULE_FILTER" in
        all|desktop) test_desktop ;;
    esac

    case "$MODULE_FILTER" in
        all|screenshot) test_screenshot ;;
    esac

    case "$MODULE_FILTER" in
        all|input) test_input ;;
    esac

    case "$MODULE_FILTER" in
        all|inspection) test_inspection ;;
    esac

    case "$MODULE_FILTER" in
        all|window) test_window ;;
    esac

    case "$MODULE_FILTER" in
        all|vision) test_vision ;;
    esac

    case "$MODULE_FILTER" in
        all|cli) test_cli ;;
    esac

    case "$MODULE_FILTER" in
        all|config) test_config ;;
    esac

    case "$MODULE_FILTER" in
        all|mcp) test_mcp ;;
    esac

    # --- Summary ---
    echo ""
    echo "========================================"
    echo "Results:"
    echo -e "  ${GREEN}PASSED${NC}:   $PASSED"
    echo -e "  ${RED}FAILED${NC}:   $FAILED"
    echo -e "  ${YELLOW}WARNINGS${NC}: $WARNINGS"
    echo ""

    if [[ $FAILED -gt 0 ]]; then
        echo -e "${RED}Acceptance suite FAILED${NC}"
        exit 1
    elif [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}Acceptance suite PASSED with warnings${NC}"
        exit 0
    else
        echo -e "${GREEN}Acceptance suite PASSED${NC}"
        exit 0
    fi
}

parse_args "$@"
main
