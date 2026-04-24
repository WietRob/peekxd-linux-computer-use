# ADR-0001: Softbox Ghost Mode V1

## Status
Accepted — V1 Implementierung in Arbeit

## Kontext
peekxd v0.3.0 hat SafetyGuard mit drei Levels (strict/normal/permissive) und ein Preview-Log. Es gibt aber keine automatische, risikobasierte Zonen-Entscheidung und keinen strukturierten Ghost-Mode, der Aktionen als Overlay/Preview darstellt ohne Ausführung.

Das Ziel ist Softbox: ein Guardrail-Sandbox-Hybrid mit 4 Zonen:
- GHOST — keine Ausführung, nur Preview
- SHADOW — Ausführung mit Before/After Snapshot + Audit
- GUIDED — normale Guardrails + Audit
- DIRECT — direkte Ausführung für vertrauenswürdige Aktionen

## Entscheidung

**V1 implementiert nur Zone 1 (GHOST) + eine minimale Zone-Entscheidung.**

Shadow/Record/Replay werden als ADR/Backlog dokumentiert, nicht implementiert.

### Warum Ghost zuerst
1. **Höchster Sicherheitsgewinn** — verhindert jede echte Ausführung riskanter Aktionen
2. **Keine Infrastruktur nötig** — braucht keine VM, Container, Snapshot-Filesystem
3. **Sofort testbar** — reines Code-Konstrukt, kein Desktop nötig
4. **Grundlage für Shadow** — Ghost-Preview-Struktur wird später für Before/After-Vergleich wiederverwendet

### Minimaler Scope V1
- `Zone` enum: GHOST, SHADOW, GUIDED, DIRECT
- `ZoneDecision` Klasse: risikobasierte Entscheidung pro Aktion
- `GhostPreviewResult` Dataclass: strukturiertes Preview-Objekt
- Integration in `AgentOrchestrator._act()`: vor `_execute_action()` Zone prüfen
- Bei GHOST: Preview erzeugen, Audit loggen (executed=false), KEINE echte Ausführung
- Erweiterung `SafetyGuard` um Zone-Entscheidung
- Tests: Risk Decision, Ghost Execution, Regression

### Nicht-Ziele V1
- Keine echte Overlay-UI (nur Preview-Objekt/Dict)
- Kein Shadow-Mode (kein Before/After-Snapshot-Vergleich)
- Kein Record & Replay
- Keine adaptive Zone-Anpassung basierend auf Historie
- Keine CLI-Flag-Erweiterung (nur API/config-seitig nutzbar)
- Keine Bild-basierte Ghost-Preview mit markierter Zielregion

### Sicherheitsgrenzen
- Ghost Mode verhindert KEINE direkten CLI-Aufrufe außerhalb des Orchestrators
- Keine VM-Sandbox — direkter Desktop-Zugriff bleibt möglich wenn Ghost nicht aktiv
- Zone-Entscheidung ist heuristisch (Pattern-Matching), nicht formal verifiziert
- Keine kryptographische Isolation

### Teststrategie
- 100% trockene Unit-Tests — keine echten Klicks/Typing
- Mock-ActionExecutor für Ghost-Tests
- Regression: normale Aktionen laufen weiterhin durch bisherigen Pfad
- Grep-Beweis nach Implementierung

### Backlog
| Item | Zielzone | Status |
|------|----------|--------|
| Shadow Mode (Before/After Snapshot) | SHADOW | Backlog |
| Record & Replay für Aktionen | SHADOW | Backlog |
| Adaptive Replay basierend auf Erfolgsrate | GUIDED/SHADOW | Backlog |
| Echte Overlay-UI mit markierter Zielregion | GHOST | Backlog |
| CLI-Flag `--zone-default` | alle | Backlog |
| Config-Option `softbox.default_zone` | alle | Backlog |

## Konsequenzen
- Positiv: Sofortiger Schutz gegen destruktive/unklare Aktionen im Agent-Loop
- Positiv: Testbare, erweiterbare Grundlage für weitere Zonen
- Negativ: Nutzer sieht Ghost-Preview nur als Text/Dict, nicht als visuelles Overlay
- Negativ: Kein Schutz für direkte Tool-Aufrufe außerhalb `AgentOrchestrator`
