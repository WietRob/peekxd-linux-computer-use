# Release: Softbox Ghost Live Overlay V3

- **Release-Name:** Softbox Ghost Live Overlay V3
- **Version:** 0.3.3
- **Datum:** 2026-04-24
- **Kanonisches Repo:** `~/projects/peekxd-linux-computer-use`

## Code-Release (Tag v0.3.3-ghost-live-overlay)

- **Commit:** e3d0a6a
- **Tag:** v0.3.3-ghost-live-overlay
- **Dateien geaendert:** 11 (5 Modified, 6 Added)
- **Zeilen:** +924 / -5

## Tests

- **Unit-Tests:** 401/401 passed
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

## Release-Artefakte (Review-korrigiert)

- **Finaler Patch:** `/home/roberto_schmidt/projects/peekxd_softbox_v3_ghost_overlay_FINAL.patch`
  - 1081 Zeilen, 11 diff-headers, alle Pflichtdateien enthalten
- **Alles Patch (unvollstaendig):** `/home/roberto_schmidt/projects/peekxd_softbox_v3_ghost_overlay.patch`
  - 199 Zeilen, 5 diff-headers — ENTHAELT NUR MODIFIED FILES, FEHLT 6 NEUE DATEIEN
- **REVIEWED ZIP:** `/home/roberto_schmidt/projects/Kimi_Agent_Peekaboo_Linux_Skill_V6_Ghost_Live_Overlay_REVIEWED.zip`
  - 158K, 109 Dateien, CLEAN
- **Ursprungs-ZIP (unreviewed):** `/home/roberto_schmidt/projects/Kimi_Agent_Peekaboo_Linux_Skill_V6_Ghost_Live_Overlay.zip`
  - 158K — Inhalte korrekt aber nicht review-validiert

## Runtime-Sync

- **Runtime-Pfad:** `~/.hermes/skills/linux-computer-use`
- **Runtime-Version:** 0.3.3
- **Runtime-Tests:** 401/401 passed

## Governance

- **OPT-ID:** OPT-011 (V3 Implementation) + OPT-012 (Release-Integrity Review)
- **validate:** ALL RECORDS VALID
- **gate:** PASS
