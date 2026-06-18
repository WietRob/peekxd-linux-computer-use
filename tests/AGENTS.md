# PeekXD Test Harness

**Repository:** peekxd-linux-computer-use
**Framework:** pytest
**Test Count:** 31 files
**Location:** `tests/`

---

## Test Structure

```
tests/
├── test_agent_actions.py              # Agent action tests
├── test_agent_hermes_tools.py         # Hermes tools integration
├── test_agent_markup.py               # Markup tests
├── test_audit.py                      # Audit tests
├── test_cleanup.py                    # Cleanup tests
├── test_cli.py                        # CLI tests
├── test_cli_doctor.py                 # Doctor CLI tests
├── test_cli_ghost.py                  # Ghost CLI tests
├── test_cli_overlay.py                # Overlay CLI tests
├── test_config.py                     # Config tests
├── test_confirmable_ghost.py          # Confirmable ghost tests
├── test_doctor.py                     # Doctor tests
├── test_function_calling.py           # Function calling tests
├── test_input.py                      # Input tests
├── test_inspection.py                 # Inspection tests
├── test_mcp.py                        # MCP tests
├── test_memory.py                     # Memory tests
├── test_orchestrator_*.py             # Orchestrator tests (5 files)
├── test_overlay.py                    # Overlay tests
├── test_preview_artifact.py           # Preview artifact tests
├── test_real_confirmable_ghost.py     # Real confirmable ghost tests
├── test_safety.py                     # Safety tests
├── test_screenshot.py                 # Screenshot tests
├── test_screenshot_wslg.py            # WSLg screenshot tests
├── test_shadow.py                     # Shadow tests
├── test_vision.py                     # Vision tests
├── test_window.py                     # Window tests
└── test_zones.py                      # Zones tests
```

## Golden Commands

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=peekxd --cov-report=html

# Run specific test file
pytest tests/test_cli.py -v

# Run with timeout (if pytest-timeout installed)
pytest tests/ -v --timeout=60

# Run async tests
pytest tests/ -v --asyncio-mode=auto
```

## Dependencies

```bash
pip install pytest pytest-asyncio
# Optional: pip install pytest-timeout pytest-cov
```

## Configuration

No `pytest.ini` or `conftest.py` currently present. Tests use default pytest discovery.

## Notes for Agents

- Tests are **not** marked with `@pytest.mark` categories (no e2e/integration/unit markers)
- No `conftest.py` for shared fixtures
- Tests appear to use direct imports, not factory functions
- Some tests may require display/X11 for screenshot/window tests
- `test_orchestrator_*.py` files test orchestrator patterns

---

*Test harness maintained by Hermes Research-Agent v0.1*
*Last updated: 2026-06-18*
