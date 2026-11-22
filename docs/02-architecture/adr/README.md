---
title: Architecture Decision Records
status: active
updated: 2026-11-17
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
| [[0006-standalone-ui-session]] | accepted | Kurzlebige HttpOnly-Session nur für die Standalone Management UI |
| [[0007-home-assistant-main-panel]] | accepted | Administratorgeschütztes Native-Panel über Home-Assistant-Auth |
| [[0008-public-container-publishing]] | accepted | Versionierte öffentliche Multi-Arch-Images mit anonymem Gate |
| [[0009-supervisor-native-backend-discovery]] | accepted | Lokale App-Erkennung über Supervisor mit Remote-Fallback |
| [[0010-secure-test-dependency-replacements]] | accepted | Gezielter, geprüfter Pillow-Sicherheitsersatz nur im Entwicklungsgraph |
| [[0011-direct-backend-sidebar]] | accepted | Direkter Backend-UI-Einstieg aus der HA-Seitenleiste |
| [[0012-dashboard-task-compatibility]] | accepted | Dashboard, Hostzuordnung und geprüfte Task-Voraussetzungen |

| [[0013-visible-dashboard-checks-and-websites]] | accepted | Sichtbare UI-Statusprüfungen und Host-Weblinks |

| [[0014-guided-setup-and-failure-review]] | accepted | Geführtes Benutzer-Setup und persistente Jobprüfung |

| [[0015-stable-website-icons]] | accepted | Stabile Browser-Icons, feste Fallbacks und explizite Icon-URL |

| [[0016-timestamp-job-timeline]] | accepted | Zeitgenauer Jobverlauf und gefilterte Verwaltungslisten |

| [[0017-timeline-review-attention]] | accepted | Rote Timeline-Punkte nur bei offener Fehlerprüfung |
| [[ADR-0018-package-details]] | accepted | Begrenzte Paketdetails im Hoststatus |
| [[ADR-0020-package-selection-and-snapshots]] | accepted | Paket-Auswahljobs und konsistente Status-Snapshots |
| [[ADR-0019-scoped-package-update]] | accepted | Paketdialog aktualisiert ein bestätigtes Paket gezielt |

| [[0021-safe-failure-diagnostics-and-history]] | accepted | Sichere Fehlerdiagnosen und SQLite-kompatibler Jobverlauf |

| [[0022-resource-and-capability-contracts]] | accepted | Ressourcenidentitäten, versionierte Capabilities und additive Kompatibilität |

| [[0023-resource-registry-and-module-boundaries]] | accepted | Registry, additive Migration, Modulgrenzen und geprüfte Dependency-Updates |

| [[0024-bounded-resource-groups]] | proposed | Manuelle Gruppen, Tags und begrenzte deterministische Smart-Regeln |
| [[0025-operator-ui-and-incremental-modularity]] | proposed | English-only operator UI, reusable lists, selection context and incremental modularity |

| [[0026-resource-jobs-and-safe-recovery]] | proposed | Immutable resource job scopes, canonical conflicts and no blind mutation replay |

| [[0027-central-policy-and-approval-contracts]] | proposed | Central identity-aware policy and single-use human approval-domain contracts |

| [[0028-linux-package-provider-boundary]] | proposed | Feature-owned Linux package workflows, preserved APT and synthetic provider contract proof |

| [[0029-linux-evidence-and-compatibility-matrix]] | proposed | Qualified package observations and explicit Linux compatibility/test evidence |

| [[0030-dnf-zypper-and-nullable-observations]] | proposed | Native RPM maintenance, qualified observations, schema 15 and safe compatibility rollout |

Neue ADRs verwenden [[../../templates/adr-template|die ADR-Vorlage]]. Akzeptierte
ADRs werden nicht rückwirkend umgeschrieben; eine neue ADR ersetzt die alte und
verlinkt sie als `superseded`.

- [ADR-0031: Automatic system manager selection](0031-automatic-system-manager-selection.md)
