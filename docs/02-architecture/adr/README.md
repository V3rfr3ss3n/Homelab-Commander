---
title: Architecture Decision Records
status: active
updated: 2026-08-21
tags: [architecture, adr, index]
---

# Architecture Decision Records

| ADR | Status | Entscheidung |
| --- | --- | --- |
| [[0001-ports-and-adapters]] | accepted | Backendzugriffe hinter Application Protocols |
| [[0002-public-by-default]] | accepted | Repository enthält ausschließlich veröffentlichbare Daten |
| [[0003-quality-target]] | accepted | Gold-baseline plus sinnvolle Platinum-Regeln |
| [[0004-safe-reboot-flow]] | accepted | Neustarts nur bei Bedarf und nach Bestätigung |
| [[0005-native-backend-boundary]] | accepted | Integration, Backend und Add-on als getrennte Komponenten |

Neue ADRs verwenden [[../../templates/adr-template|die ADR-Vorlage]]. Akzeptierte
ADRs werden nicht rückwirkend umgeschrieben; eine neue ADR ersetzt die alte und
verlinkt sie als `superseded`.
