# Evidence: config-hermes-default build

Branch: autonomy/peekxd/config-hermes-default-20260622
Commit: 25f6a4a
Timestamp: 2026-06-22T22:20:22+02:00
Candidate: config-hermes-default

## What changed

1. Updated vision defaults in `peekxd/config/manager.py`:
   - Added Hermes to `vision.providers` list as first entry.
   - Set `vision.default_provider` to `hermes`.

2. Updated configuration tests in `tests/test_config.py`:
   - Added `test_default_vision_config` to verify Hermes is default and first provider.
   - Updated existing defaults assertions to reflect `vision.default_provider = hermes`.

3. Updated user docs in `README.md`:
   - Added note that `vision.default_provider` defaults to `hermes`.

## Why

Peekxd advertises Hermes Agent as the default/no-API-key vision path, but `DEFAULT_CONFIG` still defaulted to OpenAI. This update aligns runtime defaults and user-facing docs with intended behavior so fresh installs use Hermes by default when available.
