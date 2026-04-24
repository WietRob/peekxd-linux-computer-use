# Release: Softbox Ghost Live Overlay V3

- **Release-Name:** Softbox Ghost Live Overlay V3
- **Version:** 0.3.3
- **Datum:** 2026-04-24
- **Kanonisches Repo:** `~/projects/peekxd-linux-computer-use`

## Teststatus

- Full suite: TBD (wird in Phase 7 bewiesen)

## GUI-Backend-Forensik (Phase 1)

- XDG_SESSION_TYPE: wayland
- DISPLAY: :0
- tkinter: AVAILABLE → Primaer-Backend
- gi (GTK): AVAILABLE
- PyQt6/PySide6: nicht verfuegbar
- zenity, notify-send, grim, slurp: vorhanden

## Kern-Aenderungen gegen V0.3.2

- **Neu:** `peekxd/core/overlay.py` — OverlayDecision, OverlayRequest, BaseOverlayBackend, NoopOverlayBackend, TkinterOverlayBackend, GhostOverlayController
- **Geaendert:** `peekxd/agent/orchestrator.py` — Overlay-Integration im GHOST-Pfad, neue Parameter
- **Geaendert:** `peekxd/cli.py` — `--ghost-overlay`, `--ghost-overlay-timeout`, `--ghost-overlay-backend`
- **Neu:** `tests/test_overlay.py` — Overlay-Unit-Tests
- **Neu:** `tests/test_orchestrator_overlay.py` — Orchestrator-Overlay-Integration
- **Neu:** `tests/test_cli_overlay.py` — CLI-Flag-Tests
- **Neu:** `docs/adr/ADR-0003-softbox-ghost-live-overlay.md`
- **Geaendert:** `pyproject.toml` — Version 0.3.3
- **Geaendert:** `README.md`, `SKILL.md` — Doku

## Sicherheit

- Overlay bestätigt nur Preview, fuehrt NICHT aus.
- GHOST bleibt `blocked=True`, `executed=False` auch bei Approval.
- Overlay darf niemals selbst klicken oder tippen.

## Hinweis

Commit/Tag/SHA256 werden nach Phase 9 ergaenzt.
