# Release: Softbox Shadow V2

- **Release-Name:** Softbox Shadow V2
- **Version:** 0.3.2
- **Datum:** 2026-04-24
- **Skill-Quelle (Runtime):** `~/.hermes/skills/linux-computer-use`
- **Kanonisches Repo:** `~/projects/peekxd-linux-computer-use`

## Teststatus

- 366/366 passed (pytest)
- Suite: tests/ (Shadow, Ghost, Zones, CLI, Orchestrator, Preview)

## Governance

- OPT-009: `peekxd-softbox-v2-shadow-hard-review` — APPLIED
- opt_record.py validate: ALL 9 RECORDS VALID
- opt_record.py gate: PASS

## Release-Artefakte (extern)

Diese Artefakte liegen ausserhalb des Git-Repos und sind referenziert:

| Artefakt | Pfad | SHA256 |
|----------|------|--------|
| Shadow-only Patch | `~/projects/peekxd_softbox_v2_shadow_ONLY.patch` | `03f824bc4b9c836bce374c56b5686e3a5d9aa634a7a912cbc52f4ced68b6b483` |
| Reviewed ZIP | `~/projects/Kimi_Agent_Peekaboo_Linux_Skill_V5_Softbox_Shadow_FINAL_REVIEWED.zip` | `bdc1ee675187fd92d9375d51b88cf6e2139606ee0a784b987db23d84ccadd58a` |
| Governance Backup | `~/projects/hermes_governance_backup_20260424.zip` | `9220b4a668c85010621f4d8f40a908dc89b642ba1d7b5ad8fe3639031303df25` |

## Kern-Aenderungen gegen V0.3.1

- **Neu:** `peekxd/core/shadow.py` — ShadowRecorder, ShadowResult, ShadowSnapshot
- **Geaendert:** `peekxd/core/zones.py` — SHADOW-Zone fuer type/click
- **Geaendert:** `peekxd/agent/orchestrator.py` — Shadow-Pfad mit before/after Snapshots
- **Neu:** `tests/test_shadow.py` — 292 Zeilen, Shadow-Unit-Tests
- **Neu:** `tests/test_orchestrator_shadow.py` — 270 Zeilen, Orchestrator-Shadow-Integration
- **Neu:** `docs/adr/ADR-0002-softbox-shadow-mode.md` — Architektur-Decision
- **Geaendert:** `pyproject.toml` — Version 0.3.2

## Hinweis

Die ZIP/Patch-Dateien bleiben externe Release-Artefakte.
Das Git-Repo (`~/projects/peekxd-linux-computer-use`) ist ab jetzt die kanonische Source-of-Truth fuer Code, Tests und Doku.
