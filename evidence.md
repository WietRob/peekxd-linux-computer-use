# Evidence: peekxd yellow build

Branch: autonomy/peekxd/yellow-20260622
Timestamp: 2026-06-22T18:17:25+02:00
Candidate: yellow

## What changed

- Added explicit argument parsing to `selftest.sh`:
  - Supports documented `--module MODULE` and positional `MODULE` invocation.
  - Supports `--verbose` / `-v` and `--help` / `-h`.
  - Rejects unknown options, missing module values, duplicate positional arguments, and unknown modules with exit code 2.
- Marked `selftest.sh` executable so the documented `./selftest.sh` usage works.
- Expanded `tests/test_selftest.py` regression coverage for module-option behavior, unknown-module rejection, and executable script mode.
- Wrote `changes.patch`, `tests.md`, `rollback.md`, and this evidence report for the builder handoff.

## Why

The self-test usage header advertised `./selftest.sh [--verbose] [--module MODULE]`, but the script only read the first positional argument. As a result, `--module unit` silently selected a non-existent module named `--module`, ran zero checks, and still exited successfully. Unknown modules behaved the same way. This could create false-positive acceptance runs in automation.

## TDD evidence

Failing tests were added before implementation:

- `python3 -m pytest tests/test_selftest.py -q`
  - Result before implementation: 2 failed, 1 passed.
  - Failure reasons: `--module unit` ran zero checks; unknown module exited 0.
- `python3 -m pytest tests/test_selftest.py::test_selftest_script_is_executable_for_documented_usage -q`
  - Result before chmod: 1 failed because `selftest.sh` was not executable.

Passing verification after implementation:

- `python3 -m pytest tests/test_selftest.py -q` -> 4 passed in 4.81s.
- `./selftest.sh --module unit` -> Acceptance suite PASSED; Unit tests (490 tests).
- `python3 -m pytest tests/ -q` -> 494 passed in 6.88s.

## Known environmental notes

- `python` command was absent; `python3` was used for all successful test commands.
- `git fetch --all --prune` failed because GitHub SSH auth was unavailable in this environment; no push or PR was attempted per task instructions.
