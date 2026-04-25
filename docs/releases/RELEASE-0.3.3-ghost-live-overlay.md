# Release: Softbox Ghost Live Overlay V3

- **Release-Name:** Softbox Ghost Live Overlay V3
- **Version:** 0.3.3
- **Datum:** 2026-04-25
- **Kanonisches Repo:** `~/projects/peekxd-linux-computer-use`

## Commits

- **Release-Commit:** e3d0a6a (Tag: `v0.3.3-ghost-live-overlay`)
- **Review-Commit:** 4ea38d4 (Manifest + Patch-Korrektur)
- **Final HEAD:** 4ea38d4

## Tests

- **Unit-Tests:** 401/401 passed (Repo + Runtime)
- **Overlay-Tests:** 36 new (18 overlay + 12 orchestrator_overlay + 6 cli_overlay)
- **Shadow/Ghost-Regression:** bestaetigt

## GUI-Backend (Tkinter Smoke Test)

- **XDG_SESSION_TYPE:** wayland
- **DISPLAY:** :0
- **tkinter:** AVAILABLE
- **TkinterOverlayBackend Smoke:** PASS
  - decision: `{'approved': False, 'cancelled': False, 'timed_out': True, 'backend': 'tkinter', 'reason': 'Timed out after 2s'}`
  - elapsed: 2.03s
  - kein Haenger

## GHOST Non-Execution Semantics

- **approved=True → _execute_action NOT called:** PASS
- **executed=False in Result:** PASS
- **executed=False in Audit:** PASS
- **overlay_decision in Result + Audit:** PASS

## Release-Artefakte (Final)

### FINAL Patch
- **Pfad:** `/home/roberto_schmidt/projects/peekxd_softbox_v3_ghost_overlay_FINAL.patch`
- **Zeilen:** 1109
- **diff-headers:** 11 (alle Pflichtdateien)
- **Groesse:** 41,589 Bytes
- **SHA256:** `311cb9bc85d977dd1b16eeccc67ee5f507bba9b4beba461520ee1cc5d94eff98`

### REVIEWED ZIP
- **Pfad:** `/home/roberto_schmidt/projects/Kimi_Agent_Peekaboo_Linux_Skill_V6_Ghost_Live_Overlay_REVIEWED.zip`
- **Dateien:** 109
- **Groesse:** 162,379 Bytes
- **SHA256:** `e54b51e6e38c22bfa49e722d5b53bfdfeb279d17e8be179b07c9dd7060890dd2`
- **Clean:** kein __pycache__, keine .pytest_cache, keine egg-info

### Veraltete Artefakte (NICHT verwenden)
- `/home/roberto_schmidt/projects/peekxd_softbox_v3_ghost_overlay.patch` — unvollstaendig (5/11 Dateien)
- `/home/roberto_schmidt/projects/Kimi_Agent_Peekaboo_Linux_Skill_V6_Ghost_Live_Overlay.zip` — nicht review-validiert

## Runtime-Sync

- **Runtime-Pfad:** `~/.hermes/skills/linux-computer-use`
- **Runtime-Version:** 0.3.3
- **Runtime-Tests:** 401/401 passed

## Governance

- **OPT-011:** V3 Implementation (APPLIED)
- **OPT-012:** Release-Integrity Review (APPLIED)
- **OPT-013:** Final Artifact Reconciliation (APPLIED)
- **validate:** ALL RECORDS VALID
- **gate:** PASS
