# Evidence

## What was changed

- Updated `selftest.sh` to avoid recursive invocation by excluding `tests/test_selftest.py` from the `unit` pytest run via `--ignore tests/test_selftest.py`.
- Added/adjusted `tests/test_selftest.py` regression test to assert that `bash ./selftest.sh unit` exits with code 0 and reports the unit-test pass line in stdout.
- Replaced `rollback.md` with candidate-specific rollback and post-merge verification steps for `autonomy/peekxd/green-202606221326`.

## Why

- The existing self-test script passed normal unit tests but became vulnerable to self-referential recursion once a selftest regression test existed in `tests/`.
- Excluding the selftest file from the test command ensures deterministic runs.
- The new test prevents this regression in CI and documents the expected behavior for future changes.
- Rollback instructions were aligned with the green-build branch and no-revert policy.

## Verification

- `python3 -m pytest tests/test_selftest.py -q` -> passed
- `bash ./selftest.sh unit` -> passed
- `bash ./selftest.sh desktop` -> passed
- `python3 -m pytest tests/ -q` -> passed (491 tests)
