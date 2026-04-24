# ADR-0003: Softbox Ghost Live Overlay (V3)

**Status:** Accepted
**Date:** 2026-04-24
**Version:** 0.3.3

## Kontext

V1 (Ghost Mode) erzeugt bei GHOST-Aktionen ein `GhostPreviewResult`-Dict und eine optionale Markup-PNG.
Der Nutzer sieht diese Preview nur im CLI-Output oder Audit-Log — nie live auf dem Desktop.

V2 (Shadow Mode) fuehrt Aktionen mit before/after Snapshots aus (type/click → SHADOW).

GHOST-Aktionen bleiben aber "unsichtbar" bis der Nutzer aktiv Logs prueft.

## Entscheidung

V3 fuegt ein optionales Live-Overlay hinzu, das bei GHOST-Aktionen ein Fenster zeigt:

- Aktion und Parameter
- Risiko-Faktoren
- Screenshot/Markup-Bild wenn verfuegbar
- Approve / Cancel Buttons
- Timeout (Default 5s)

## Backend-Strategie

- **Primaer:** Tkinter — verfuegbar, testbar, keine Zusatzabhaengigkeit.
- **Fallback:** `NoopOverlayBackend` — gibt `timed_out=True` zurueck, kein GUI.
- Lazy Import: `tkinter` wird nur innerhalb `TkinterOverlayBackend.show()` importiert.
- Headless/CI: `NoopOverlayBackend` verhindert Haenger.

## Sicherheitsregel

- Overlay bestätigt NUR, dass der Nutzer die Preview gesehen hat.
- Auch bei `approved=True` wird in V3 KEINE Aktion ausgefuehrt.
- GHOST bleibt non-executing. `blocked=True`, `executed=False`.
- Ein spaeteres V3.1 kann "approve-to-execute" separat und strenger behandeln.

## Nicht-Ziele

- Kein Rollback
- Kein Record & Replay
- Keine globale Safety ausserhalb Orchestrator
- Keine vollstaendige Sandbox
- Keine Bestaetigung fuer DIRECT/SHADOW
- Kein GTK/Qt-Backend (nur Tkinter + Noop)

## Akzeptanzkriterien

1. `peekxd/core/overlay.py` mit OverlayDecision, OverlayRequest, BaseOverlayBackend, NoopOverlayBackend, TkinterOverlayBackend, GhostOverlayController
2. Lazy Import: `import peekxd.core.overlay` funktioniert ohne tkinter
3. Orchestrator integriert Overlay bei GHOST + `enable_ghost_overlay=True`
4. GHOST bleibt non-executing auch bei Overlay-Approval
5. overlay_decision landet in Result und Audit
6. SHADOW und DIRECT bleiben unveraendert
7. CLI-Flags: `--ghost-overlay`, `--ghost-overlay-timeout`, `--ghost-overlay-backend`
8. Alle bestehenden Tests gruen
9. Mindestens 10 neue Tests fuer Overlay-Integration
