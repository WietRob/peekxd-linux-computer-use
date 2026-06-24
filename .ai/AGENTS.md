# PeekXD Agent Layer

**Repository:** peekxd-linux-computer-use
**Purpose:** Linux automation that sees the screen and does the clicks
**Agent Role:** Evidence-Operator, Test-Runner, Documentation-Updater
**Version:** 0.3.4

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `pytest tests/ -v` | Run all tests |
| `./selftest.sh` | Run self-test suite |
| `pip install -e .` | Install in dev mode |
| `black peekxd/ tests/` | Format code |
| `ruff check peekxd/ tests/` | Lint code |

## Structure

```
peekxd-linux-computer-use/
├── peekxd/              # Main package
├── tests/               # 31 test files
├── docs/                # Documentation
├── examples/            # Examples
├── .ai/                 # Agent layer (this directory)
│   ├── evidence/        # Evidence and audit trail
│   └── work/            # Work-in-progress tracking
├── README.md            # User documentation
├── SKILL.md             # Skill documentation
├── TROUBLESHOOTING.md   # Troubleshooting guide
├── pyproject.toml       # Project config
├── install.sh           # Install script
└── selftest.sh          # Self-test script
```

## Agent Conventions

- **Read-only default:** Prefer observation over mutation
- **Test-first:** Run tests before and after changes
- **Bounded changes:** Max 3 files per cycle
- **Evidence:** Document all changes in `.ai/evidence/`
- **Branch:** Work on `hermes/peekxd-live-eval-2026-06-18`, not `main`

## Key Modules

| Module | File | Tests |
|--------|------|-------|
| CLI | `peekxd/cli.py` | `tests/test_cli.py` |
| Agent | `peekxd/agent.py` | `tests/test_agent_actions.py` |
| Screenshot | `peekxd/screenshot.py` | `tests/test_screenshot.py` |
| Vision | `peekxd/vision.py` | `tests/test_vision.py` |
| MCP | `peekxd/mcp.py` | `tests/test_mcp.py` |

---

*Agent layer maintained by Hermes Research-Agent v0.1*
*Last updated: 2026-06-18*
