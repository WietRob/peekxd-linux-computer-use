# Evidence

Implemented exactly one GREEN candidate: `cli-click-type-on-element`.

## What changed
- Added `peekxd click --on ELEMENT_ID` to resolve a semantic element from the current semantic snapshot, click the element bounding-box center, and preserve the existing coordinate-based click path.
- Added `peekxd type TEXT --on ELEMENT_ID` to resolve a semantic element, center-click it for focus, then type the text; the existing current-cursor type path remains unchanged.
- Added CLI tests proving `--on` derives centers from known semantic bboxes and calls the existing input provider methods.

## Why
The cycle-7 dreamer classified this as GREEN: additive CLI flags, low-risk, trivial rollback, and highly testable via mocked semantic snapshots. Existing semantic helpers already rehydrate elements and perform center click/type behavior, so the CLI can reuse those paths without introducing a broader snapshot cache or architecture changes.

## Scope controls
- One candidate only: `cli-click-type-on-element`.
- Product-code change is limited to `peekxd/cli.py`.
- Existing `click X Y` and `type TEXT` behavior remains tested and unchanged.
