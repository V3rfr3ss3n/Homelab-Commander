---
title: Code-Regeln
status: accepted
updated: 2026-08-20
tags: [development, code, standards]
---

# Code-Regeln

## Architektur und Verantwortungen

- Module haben einen erkennbaren Zweck und eine gerichtete Abhängigkeit.
- Externes JSON wird einmal validiert und in typisierte, bevorzugt immutable
  Dataclasses überführt.
- Entities lesen Zustände und delegieren Aktionen; sie parsen kein Backend-JSON.
- Coordinator und Application Services werden injiziert, nicht über globale
  Dictionaries gesucht.
- Semaphore-Begriffe bleiben im Adapter, außer bei explizit backendbezogener
  Konfiguration.
- Neue Homelab-Funktionalität erhält ein Modell und einen Use Case statt weiterer
  Boolescher Sonderfälle in einem universellen Manager.

## Python

- vollständige Typannotationen; Mypy strict ist das Ziel
- kein breites `Any`; `object` plus Validierung an untrusted boundaries
- `dataclass(slots=True, frozen=True)` für unveränderliche Domainwerte
- explizite, projektspezifische Exceptions mit sicherer User Message
- keine blockierenden Funktionen im Event Loop
- `asyncio.sleep` nur im Produktiv-State-Machine-Code; in Tests wird Zeit
  kontrolliert
- Konstanten statt Magic Numbers, aber keine Konfiguration als Konstante
- Docstrings erklären öffentliche Verträge und nicht offensichtliche Gründe
- schmale `# noqa`/`type: ignore` nur mit Fehlercode und Begründung

## Home Assistant

- UI Config Flow statt YAML
- typisiertes `ConfigEntry.runtime_data`
- `DataUpdateCoordinator` für gemeinsamen Poll
- `async_config_entry_first_refresh()` beim Setup
- korrekter Unload und Cancellation aller Listener/Tasks
- `has_entity_name = True`, Entity Descriptions und Translation Keys
- stabile Unique IDs ohne URL, IP oder Anzeigenamen
- `UpdateEntityFeature.INSTALL` für Updates
- Device Classes und Entity Categories wo semantisch passend
- Exceptions und Reauth nach aktuellen Home-Assistant-Patterns

## Sicherheit

- Safe-by-construction Logging: strukturierte IDs sind erlaubt, Konfiguration und
  Response Bodies nicht.
- Authorization Header wird ausschließlich beim Request aufgebaut und nie
  gespeichert oder repräsentiert.
- URLs werden vor Nutzung validiert; Redirect- und SSL-Verhalten wird explizit
  entschieden und getestet.
- Diagnostics folgt einer Allowlist und redigiert Secrets zusätzlich.
- Schreibende Aktionen brauchen zielgenaue Host-ID und begrenzte Laufzeit.

## Tests

Ein Verhaltenstest beschreibt den öffentlichen Effekt, nicht private
Implementierungsdetails. Kritisch sind Parsergrenzen, Config Flows, Lifecycle,
dynamische Hosts, Availability, alle Commandzustände und Secret Leakage. Ein
Bugfix beginnt mit einem fehlgeschlagenen Regressionstest.

## Kommentare und Sprache

Code, Identifier, öffentliche Docs und User-facing English sind Englisch.
Projektinterne deutsche Dokumente sind erlaubt. Kommentare erklären das Warum;
offene Arbeit gehört als referenziertes Backlog-Item in die Dokumentation, nicht
als namenloses `TODO` im Code.
