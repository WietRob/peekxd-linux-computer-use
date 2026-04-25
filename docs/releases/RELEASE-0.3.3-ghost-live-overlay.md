# Release: Softbox Ghost Live Overlay V3

- **Release-Name:** Softbox Ghost Live Overlay V3
- **Version:** 0.3.3
- **Datum:** 2026-04-25
- **Kanonisches Repo:** `~/projects/peekxd-linux-computer-use`
- **Kanonische Build-Quelle:** Tag `v0.3.3-ghost-live-overlay-reviewed`

## Commits

- **Release-Commit:** e3d0a6a (Tag: `v0.3.3-ghost-live-overlay`)
- **Review-Commit:** 4ea38d4 (Manifest + Patch-Korrektur)
- **Final HEAD / Reviewed Tag:** siehe `git rev-parse v0.3.3-ghost-live-overlay-reviewed`

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

## Release-Artefakte

Artefakte werden aus dem reviewed Tag erzeugt. SHA256-Checksums werden
extern gespeichert, nicht hier, um selbstreferenzielle Abhaengigkeiten
zu vermeiden (das ZIP enthaelt dieses Manifest).

### Patch (aus reviewed Tag)
- **Pfad:** `~/projects/peekxd_softbox_v3_ghost_overlay_FINAL.patch`
- **Erzeugung:** `git diff v0.3.2-shadow-v2..v0.3.3-ghost-live-overlay-reviewed`
- **diff-headers:** 11 (alle Pflichtdateien)
- **SHA256:** `/home/roberto_schmidt/projects/peekxd_softbox_v3_ghost_overlay_FINAL.sha256`

### ZIP (aus reviewed Tag)
- **Pfad:** `~/projects/Kimi_Agent_Peekaboo_Linux_Skill_V6_Ghost_Live_Overlay_REVIEWED.zip`
- **Erzeugung:** `git archive` aus reviewed Tag, verpackt als `linux-computer-use/`
- **Dateien:** 109
- **Clean:** kein __pycache__, keine .pytest_cache, keine egg-info
- **SHA256:** `/home/roberto_schmidt/projects/Kimi_Agent_Peekaboo_Linux_Skill_V6_Ghost_Live_Overlay_REVIEWED.sha256`

### Kombinierte Checksum-Datei
- `/home/roberto_schmidt/projects/peekxd_v0.3.3_release_artifacts.sha256`

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
- **OPT-014:** Non-Self-Referential Artifact Freeze (APPLIED)
- **validate:** ALL RECORDS VALID
- **gate:** PASS
