# Evidence

Candidate: semantic-element-action-mapping
Task: t_2e6d2054
Branch: autonomy/peekxd/semantic-element-action-mapping-20260621

## Input reviewed

Read `/home/wietrob/.hermes/research-vault/ops/peekxd-buildroom-v09/dreamer/dreamer-cycle-6-20260621.md` and implemented exactly Candidate 1: `semantic-element-action-mapping`.

## What changed

- Added semantic bounding-box center calculation in `Geometry.center(scale=...)`, including zero-size element handling and HiDPI scaling.
- Added `SemanticElement.click_center(...)` and `SemanticElement.type_into(...)` helpers that delegate to an input provider.
- Added `semantic_element_from_mapping(...)` and `find_semantic_element(...)` so tool layers can map snapshot dictionaries back to actionable semantic elements by `element_id`.
- Added Hermes tools `peekxd_click_element` and `peekxd_type_into_element`; both build a current semantic snapshot, look up `element_id`, then delegate to existing click/type primitives.
- Added tests for center math, HiDPI scaling, zero-size edge cases, element lookup, tool definitions, and tool execution delegation.

## Why

The existing tool surface required clients to manually extract `bbox` from semantic snapshots and compute raw click coordinates. This candidate provides a bounded additive mapping from stable semantic element ids to concrete input actions while preserving existing coordinate-based tools.

## Safety / scope

- No screenshot or vision capture code was added.
- Existing `peekxd_click` and `peekxd_type` behavior remains unchanged.
- Changes are limited to two product-code files plus tests and evidence artifacts.
- No revert command was executed.
- Main was not checked out or changed directly; work was done in an isolated worktree.
