---
title: Risikoregister
status: active
updated: 2026-08-20
tags: [review, risk, project]
---

# Risikoregister

| ID | Risiko | Wkt. | Wirkung | Gegenmaßnahme | Status |
| --- | --- | --- | --- | --- | --- |
| R-01 | Semaphore API ändert Responses/Zustände | mittel | hoch | Adapter, Contract-Fixtures, unbekannte Zustände sicher | offen |
| R-02 | Task erfolgreich, Status noch veraltet | hoch | mittel | Backendstatus nie als Updatewahrheit; kontrollierter Refresh | offen |
| R-03 | Secret oder Topologie wird committed | mittel | sehr hoch | Public-by-default, Scanner, Review, Incidentprozess | mitigiert |
| R-04 | Home-Assistant-API ändert sich | hoch | mittel | Mindestversion pinnen, Dependency Updates, CI | offen |
| R-05 | Dynamische Hosts erzeugen doppelte Entities | mittel | hoch | `known_hosts`, stabile IDs, Lifecycle-Tests | offen |
| R-06 | Gleichzeitige Commands kollidieren | mittel | hoch | per-host/task concurrency policy, State Machine | offen |
| R-07 | Scope wächst zum unwartbaren Monolithen | hoch | hoch | Capabilities, Use Cases, ADRs, Backlog-Gates | mitigiert |
| R-08 | HACS-Release ist nicht reproduzierbar | mittel | hoch | gepinnte CI, Artefaktprüfung, isolierte Installation | offen |
| R-09 | Statuspayload wird zu groß/malicious | niedrig | hoch | Response-/Hostgrenzen und striktes Parsing festlegen | offen |
| R-10 | SSL-Option führt zu unsicherem Dauerbetrieb | mittel | mittel | sicherer Default, Warntext, keine globale Abschaltung | offen |
| R-11 | Home-Assistant-Teststack pinnt verwundbare Transitivdependency | mittel | mittel | [[security-exceptions|SE-2026-001]], Dependabot, Ablauf 2026-09-15 | offen |

Wahrscheinlichkeit und Wirkung werden bei jedem Milestone überprüft. Ein neues
hohes Risiko wird nicht nur hier eingetragen, sondern erhält ein konkretes TODO.
