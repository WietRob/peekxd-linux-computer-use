# Softbox Optimization Findings

## OPT-009: Shadow V2 Hard Review

**Date:** 2026-04-24
**Source:** peekxd-softbox-v2-shadow-hard-review
**Reviewer:** glm-5.1 (secondary reviewer role)
**Status:** REVIEW OK

### Finding
Shadow Mode V2 reviewed and reconciled against V1.1.1 baseline.

### Review Summary
- Baseline: V0.3.1 (Kimi_Agent_Peekaboo_Linux_Skill_V4_Softbox_Ghost_FINAL.zip)
- Shadow-only Patch: 1300 lines, 11 files changed
- Test fix applied: test_shadow_snapshot_error_does_not_crash_orchestrator had
  incorrect mock setup (property setter on read-only @property) and wrong
  call_count logic. Fixed to mock _screenshot_prov directly.
- 366 tests pass (was 363 before fix — 3 test files now also pass the snapshot error test)

### Befunde

| Befund | Schwere | Fix |
|--------|---------|-----|
| Test mock on read-only property | medium | Ja, _screenshot_prov mock |
| Test call_count logic wrong | medium | Ja, simplified to always-fail capture |
| import time fehlt | - | Nein, bereits vorhanden |
| shadow metadata outside audit guard | - | Nein, bereits korrekt |
| zones.py display artifact `=***` | - | Nein, nur Rendering-Artefakt |

### opt_record.py Bug
opt_record.py hat einen Syntax-Fehler bei der Record-Erstellung:
`NameError: name 'true' is not defined` (Zeile 191, JSON-Boolean `true`
innerhalb eines Python dict literals statt `True`).
- `validate` funktioniert (liest bestehende Records korrekt)
- Neue Record-Erstellung crasht
- `gate --source` schlägt fehl weil noch kein OPT-009 existiert

### Release Artefakte
- Patch: /home/roberto_schmidt/projects/peekxd_softbox_v2_shadow_ONLY.patch (1300 lines)
- ZIP: /home/roberto_schmidt/projects/Kimi_Agent_Peekaboo_Linux_Skill_V5_Softbox_Shadow_FINAL_REVIEWED.zip (150K, CLEAN)
