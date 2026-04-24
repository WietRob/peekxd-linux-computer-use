# ADR-0002: Softbox Shadow Mode V2

## Status
Accepted (2026-04-24)

## Kontext
Softbox V1 (ADR-0001) führte GHOST-Mode ein: destruktive/riskante Aktionen werden
geblockt, als Preview visualisiert und mit `executed=False` auditiert. Normale
Aktionen (type, click) laufen über GUIDED/DIRECT ohne Snapshot-Vergleich.

Peekxd bietet einen See→Think→Act-Loop. Jede Aktion wird über `_act()` im
Orchestrator ausgeführt. Der Orchestrator hat Zugriff auf Screenshot-Provider
(`capture_screen()`), die Audit-Struktur (`ActionEntry.screenshot_before`,
`screenshot_after`) und `get_next_screenshot_path()` — aber diese Felder sind
bisher ungenutzt.

Der Bedarf: Normale UI-Aktionen (type, click) sollen ausgeführt, aber mit
Before/After-Snapshots dokumentiert werden — ohne Rollback, ohne VM-Sandbox,
ohne Live-Overlay. Diese "Shadow"-Zone schließt die Lücke zwischen GHOST
(Preview, keine Ausführung) und DIRECT (Ausführung, kein Audit).

## Entscheidung
Shadow Mode V2 wird implementiert mit folgenden Kernregeln:

1. **ZoneAssignment**: `type`-Aktionen ohne Risk-Faktoren → SHADOW (statt GUIDED).
   `click`-Aktionen → SHADOW (statt DIRECT). Read-only bleibt DIRECT.
2. **ShadowRecorder**: Neue Klasse in `peekxd/core/shadow.py`, die eine
   `action_callable` wrapped: Before-Screenshot → Ausführung → After-Screenshot
   → Vergleich → ShadowResult.
3. **Orchestrator-Integration**: In `_act()` wird nach GHOST-Block und vor
   legacy safety-check das SHADOW-Handling eingebaut.
4. **Audit**: Shadow-Aktionen bekommen `zone="shadow"`, `executed=True`,
   `screenshot_before`/`screenshot_after` gesetzt.
5. **Fehlertoleranz**: Snapshot-Fehler landen in `ShadowResult.error`, crashen
   nicht die Action.

## V2-Scope
- ZoneDecision: `type` (sicher) → SHADOW, `click` → SHADOW
- ShadowRecorder: Before/After-Screenshots + Vergleich
- Orchestrator: SHADOW-Pfad in `_act()`
- Tests: 15 Pflichttests für ShadowRecorder, ZoneDecision, Orchestrator
- Audit: shadow metadata, screenshot_before/after
- Version: 0.3.2

## Nicht-Ziele (V2)
- Kein Rollback
- Kein Live-Overlay
- Kein Record & Replay
- Keine VM-Sandbox
- Kein PIL-Pixel-Diff (optional, nicht verpflichtend)
- Kein globaler Safety-Außerhalb-Orchestrator-Umbau
- Keine GUIDED-Semantikänderung

## Zone-Semantik (V2)

| Zone    | Ausführung | Snapshot | Audit               | Rollback |
|---------|-----------|----------|---------------------|----------|
| GHOST   | NEIN      | Preview  | executed=False      | nein     |
| SHADOW  | JA        | vor/nach | executed=True,shadow| nein     |
| GUIDED  | JA        | nein     | executed=True       | nein     |
| DIRECT  | JA        | nein     | executed=True       | nein     |

**GHOST**: destruktive Commands, Credentials, protected paths, unknown actions,
force_ghost.
**SHADOW**: type mit normalem Text, click, bekannte UI-modifizierende Aktionen
ohne destruktive Muster.
**DIRECT**: capture_screen, scroll, mouse_move, read-only observation.
**GUIDED**: Fallback für Aktionen, die weder eindeutig DIRECT noch SHADOW noch
GHOST sind. Derzeit: unbekannte Aktionen ohne Risk-Faktoren, key/hotkey ohne
systemkritische Kombination.

## Datenfluss

```text
_act(plan, screen_state)
  → zone_decision = safety.check_zone(action, params)
  → force_ghost override

  → if GHOST:
       Preview + Audit executed=False
       return blocked preview result

  → if SHADOW:
       safety.check_action(action, params)
       ShadowRecorder.wrap(lambda: _execute_action(...), action, params, screen_state)
       audit.log_action(zone="shadow", executed=True, shadow=..., screenshot_before=..., screenshot_after=...)
       return action result + shadow metadata

  → else (GUIDED/DIRECT):
       bisheriger Pfad unverändert
```

## Audit-Struktur

```json
{
  "action": "type",
  "params": {"text": "Hello World"},
  "result": {
    "success": true,
    "shadow": {
      "snapshot_before": "/tmp/audit_001.png",
      "snapshot_after": "/tmp/audit_002.png",
      "changed": true,
      "diff_summary": "Screen changed: pixel difference detected"
    },
    "zone": "shadow",
    "executed": true
  },
  "screenshot_before": "/tmp/audit_001.png",
  "screenshot_after": "/tmp/audit_002.png"
}
```

## Snapshot-Fallbacks

- Wenn `screen_state` None ist oder kein `path`-Feld hat:
  `screenshot_before = None`, `changed = None`,
  `diff_summary = "No screen state available for before snapshot"`
- Wenn After-Screenshot fehlschlägt (Exception):
  `screenshot_after = None`, Fehler in `ShadowResult.error`
- Wenn Before und After identisch (byteweise):
  `changed = False`, `diff_summary = "No visual change detected"`
- Wenn Before oder After fehlt:
  `changed = None`, `diff_summary` erklärt welcher Snapshot fehlt

## Teststrategie
15 Pflichttests, alle mocked (keine echten Desktop-Aktionen):

1. ShadowRecorder erzeugt before snapshot aus screen_state["path"]
2. ShadowRecorder überlebt fehlendes screen_state
3. ShadowRecorder.compare erkennt identische Dateien (changed=False)
4. ShadowRecorder.compare erkennt unterschiedliche Dateien (changed=True)
5. ShadowRecorder.wrap ruft action_callable genau einmal auf
6. ShadowRecorder.wrap gibt action_result unverändert + ShadowResult zurück
7. ZoneDecision: normale type-action → SHADOW
8. ZoneDecision: click → SHADOW
9. ZoneDecision: capture_screen → DIRECT
10. ZoneDecision: destructive type → GHOST
11. Orchestrator SHADOW ruft _execute_action() genau einmal
12. Orchestrator SHADOW schreibt Audit zone=shadow executed=True
13. Orchestrator SHADOW enthält shadow metadata
14. GHOST Regression: destructive action ruft _execute_action() nicht auf
15. Full Suite bleibt grün (330+ Tests)

## Risiken
- **Screenshot-Crash**: ShadowRecorder isoliert Screenshot-Fehler in
  `ShadowResult.error`. Die Action selbst wird trotzdem ausgeführt und das
  Ergebnis zurückgegeben.
- **Performance**: Zwei zusätzliche Screenshots pro SHADOW-Action. Akzeptabel,
  da SHADOW nur für type/click (seltene, bedeutsame Aktionen) greift.
- **GHOST-Regression**: GHOST ruft `_execute_action()` nie auf. Tests 14 und 15
  stellen dies sicher.

## Backlog V3
- Live-Overlay für Shadow-Aktionen (GTK3 Overlay wie GHOST, aber grün statt rot)
- Rollback aus Before-Snapshot
- Record & Replay aus Audit-Trail
- PIL-Pixel-Diff für changed-Erkennung
- ShadowRecorder als globalen Sicherheits-Layer außerhalb Orchestrator
