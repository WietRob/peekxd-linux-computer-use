# Release: Softbox V4 — Confirmable Ghost Actions

- **Release-Name:** Softbox V4 — Confirmable Ghost Actions
- **Version:** 0.3.4
- **Datum:** 2026-04-25
- **Kanonisches Repo:** `~/projects/peekxd-linux-computer-use`
- **Vorherige Version:** 0.3.3 (Tag: `v0.3.3-ghost-live-overlay-reviewed`)

## Zusammenfassung

V4 fuehrt eine zweistufige Klassifizierung und einen neuen Routing-Pfad ein:

- **HARD_BLOCKED_GHOST** — Wird niemals ausgefuehrt, unabhaengig von Freigabe.
  Gilt fuer Aktionen im GHOST-Branch (mit Risikofaktoren). Kategorien: destruktive
  Befehle, Credential-Eingabe, geschuetzte Pfade, System-Key-Kombos, unbekannte
  Aktionen, force_ghost=True.
- **APPROVABLE_GHOST** — Sichere Aktionen in der SHADOW-Zone (keine Risikofaktoren),
  die nach expliziter Freigabe durch den Benutzer ueber das Overlay ausgefuehrt
  werden koennen. Kategorien: click, type, type_text mit `risk_factors=[]`.

**Wichtige Architektur-Entscheidung:** APPROVABLE_GHOST wird ueber den SHADOW-Branch
erreicht, NICHT ueber den GHOST-Branch. Sichere Aktionen (click, type "hello")
landen via `ZoneDecision.decide()` in `Zone.SHADOW`. Der neue Routing-Pfad
`_should_route_shadow_to_confirmable_ghost()` leitet diese SHADOW-Aktionen durch
den Overlay-Besttigungsfluss, wenn beide Feature-Flags aktiv sind.

Neues CLI-Flag: `--ghost-approval-execution`. Ohne dieses Flag verhaelt sich
peekxd wie V2 (SHADOW-Aktionen werden direkt mit Before/After-Snapshots ausgefuehrt).

## Neue CLI-Flags

| Flag | Zweck |
|------|-------|
| `--ghost-approval-execution` | Erlaubt Overlay-Besttigung fuer sichere SHADOW-Aktionen |

```bash
peekxd agent run "TASK" --ghost-overlay --ghost-approval-execution  # Sichere SHADOW-Aktionen fordern Overlay-Freigabe
peekxd agent run "TASK" --ghost-overlay                              # SHADOW-Aktionen werden normal ausgefuehrt (V2-kompatibel)
```

## Zone-Zuordnung (V4)

| Aktion | Risiko-frei Zone | V4 Confirmable Routing | Mit Risikofaktoren |
|--------|------------------|------------------------|---------------------|
| click  | SHADOW | APPROVABLE_GHOST (via SHADOW, wenn Flags + Freigabe) | GHOST -> HARD_BLOCKED_GHOST |
| type   | SHADOW | APPROVABLE_GHOST (via SHADOW, wenn Flags + Freigabe) | GHOST -> HARD_BLOCKED_GHOST |
| type_text | SHADOW | APPROVABLE_GHOST (via SHADOW, wenn Flags + Freigabe) | GHOST -> HARD_BLOCKED_GHOST |
| scroll | DIRECT | — | — |
| capture_screen | DIRECT | — (nicht SHADOW) | GHOST -> HARD_BLOCKED_GHOST |
| key/hotkey | DIRECT | — (nicht SHADOW) | GHOST -> HARD_BLOCKED_GHOST |
| unknown action | GHOST | — (Risikofaktoren) | GHOST -> HARD_BLOCKED_GHOST |

## HARD_BLOCKED vs. APPROVABLE

**HARD_BLOCKED_GHOST** (nie ausfuehren):
- Destruktive Befehle (rm, sudo, dd, mkfs, etc.)
- Credential-aehnliche Eingaben (password, token, key)
- Geschuetzte Pfade (/etc, /sys, /home)
- System-Key-Kombos (ctrl+alt+delete, ctrl+alt+t)
- Unbekannte Aktionstypen
- force_ghost=True

**APPROVABLE_GHOST** (ausfuehren nach Freigabe):
- Normale Clicks mit sicheren Koordinaten (Zone.SHADOW, risk_factors=[])
- Normale Texteingaben ohne Risikomuster (Zone.SHADOW, risk_factors=[])
- type_text ohne Risikomuster (Zone.SHADOW, risk_factors=[])

## Semantik

- **Ohne `--ghost-approval-execution`:** SHADOW-Aktionen werden normal mit
  Before/After-Snapshots ausgefuehrt (V2-Verhalten). GHOST-Aktionen bleiben
  preview-only (V3-Verhalten).
- **Mit `--ghost-approval-execution` + Benutzer-Freigabe:** APPROVABLE_GHOST
  wird ausgefuehrt. Audit-Trail zeigt `zone="shadow_confirmable_ghost"`,
  `executed=True`, `classification="approvable_ghost"`.
- **HARD_BLOCKED_GHOST:** Wird immer blockiert, unabhaengig von Flags oder
  Freigabe. Audit-Trail zeigt `zone="hard_blocked_ghost"`, `executed=False`.

## Tests

- **V2/V3-Tests:** Alle bestehenden Tests weiterhin gruen (446/446).
- **V4 Unit-Tests:** `test_confirmable_ghost.py` (20 Tests) — Klassifizierungslogik.
- **V4 Orchestrator-Tests:** `test_orchestrator_confirmable_ghost.py` (15 Tests) —
  Mock-basierte Integrationstests.
- **V4 Real-Tests:** `test_real_confirmable_ghost.py` (10 Tests) — Echte
  `ZoneDecision.decide()` OHNE `safety.check_zone`-Mock. Beweisen den
  SHADOW-to-confirmable-GHOST-Routing-Pfad.

## Rueckwaertskompatibilitaet

- Ohne `--ghost-approval-execution` ist das Verhalten identisch mit V2/V3.
- Alle existierenden CLI-Flags und Overlay-Backends funktionieren unverändert.
- Audit-Format ist erweitert (neue Zone `shadow_confirmable_ghost`), nicht gebrochen.
- V2 SHADOW-Verhalten bleibt vollstaendig erhalten wenn V4-Flags inaktiv.

## Release-Artefakte

Artefakte werden aus dem reviewed Tag erzeugt.

## Governance

- **OPT-015:** V4 Confirmable Ghost Actions (APPLIED)
- **validate:** ALL RECORDS VALID
- **gate:** PASS
