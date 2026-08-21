---
title: ADR-0003 Qualitätsziel
status: accepted
updated: 2026-08-20
tags: [architecture, adr, quality]
---

# ADR-0003: Gold-Baseline plus Platinum-Technik

## Kontext

Java-Werkzeuge wie SpotBugs, PMD oder Sonatype passen nicht zu einer Python-
Custom-Integration. Home Assistant besitzt eine eigene Integration Quality Scale
und etablierte Validatoren.

## Entscheidung

Das Projekt richtet `0.1.0` an den für eine Custom Integration anwendbaren Gold-
Regeln aus und erfüllt von Beginn an die Platinum-Aspekte vollständig asynchroner
Dependencies und strikter Typisierung. Nicht anwendbare Regeln werden sichtbar
begründet, nicht stillschweigend ignoriert.

Blockierende Werkzeuge: Ruff Format/Lint, Mypy strict, Pytest mit mindestens
95 Prozent Zeilen- und Branch-Coverage, Hassfest, HACS Action, Dependency-/License-
Audit und Secret Scan. Toolversionen werden gepinnt und automatisiert aktualisiert.

## Konsequenzen

- Das erste Feature braucht mehr Tests und Dokumentation, spätere Erweiterungen
  werden dafür sicherer.
- Coverage ist Mindestindikator, kein Ersatz für sinnvolle Assertions.
- Neue Checks werden nur mit klarer Verantwortung und niedriger Doppelung ergänzt.
