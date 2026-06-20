# Evidence

Candidate: display-resolution-provider
Branch: autonomy/peekxd/display-resolution-provider-20260620

## What changed

- Added a read-only display provider module with:
  - `Display` dataclass for connected display geometry.
  - `DisplayProvider` ABC.
  - `XrandrDisplayProvider` for `xrandr --query` parsing.
  - `WlrrandrDisplayProvider` fallback for `wlr-randr` parsing.
  - `get_display_provider()` detector.
- Added `peekxd display list` CLI command to print connected display resolutions and offsets.
- Added unit tests for xrandr availability, xrandr parsing, detector behavior, and CLI output.

## Why

The Cycle 1 dreamer input classified `display-resolution-provider` as GREEN: additive, query-only, low risk, and useful for display-aware automation. The implementation avoids display mutation and only reads monitor geometry.

## Scope control

This task only implements the display-resolution-provider candidate. It does not implement coordinate transforms, monitor mutation, or any other Cycle 1 candidate.
