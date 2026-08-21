---
title: Entwicklungsworkflow
status: active
updated: 2026-08-20
tags: [development, workflow, git]
---

# Entwicklungsworkflow

## Von Idee zu Release

1. Idee in [[../00-project/backlog|Backlog]] erfassen.
2. Problem, Nutzerwert, Scope und Risiken klären.
3. Bei Architekturwirkung ADR vorschlagen und akzeptieren.
4. Akzeptanzkriterien definieren und Item ins [[../00-project/todo|TODO]] ziehen.
5. Kleine Änderung mit Tests und Dokumentation implementieren.
6. Lokalen Quality Gate und Self-Review ausführen.
7. Pull Request nach [[../05-reviews/code-review|Code Review]] prüfen lassen.
8. Nach grünem CI mergen; Releaseprozess bleibt separat und reproduzierbar.

## Branches und Commits

Kurzlebige Featurebranches werden bevorzugt. Commits sollen einzeln verständlich
sein und keine generierten, lokalen oder sensiblen Dateien enthalten. Force-Push
auf gemeinsam genutzte oder geschützte Branches ist nicht Teil des Workflows.

## Definition of Ready

- Problem und Nutzerwert sind klar.
- In-/Out-of-Scope und Akzeptanzkriterien existieren.
- Security-, Privacy- und Migrationsauswirkungen sind bewertet.
- Abhängigkeiten und betroffene Dokumente sind bekannt.

## Definition of Done

- Verhalten implementiert und typisiert
- relevante Tests inklusive Negativpfade vorhanden
- alle Gates lokal und in CI grün
- User-, Architektur- und Projektdokumentation aktuell
- keine Infrastruktur- oder Secret-Leaks
- Backlog/TODO und gegebenenfalls ADR aktualisiert
- Handoff nennt bekannte Einschränkungen ausdrücklich
