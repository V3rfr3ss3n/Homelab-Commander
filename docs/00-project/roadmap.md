---
title: Roadmap
status: active
updated: 2026-08-20
tags: [project, roadmap]
---

# Roadmap

Die Roadmap beschreibt Ergebnisse, keine Terminzusagen. Versionen bleiben klein
und veröffentlichbar; unfertige Features werden nicht über Versionsnummern
kaschiert.

## Phase 0 – Foundation

- öffentliche Dokumentations- und Repository-Basis
- Architekturentscheidungen und Privacy-Grenzen
- Python-Projekt, lokale Entwicklungsumgebung und CI
- minimale Integration, die von Home Assistant und Hassfest geladen wird

## `0.1.0` – Linux update operations

- UI-Konfiguration, Reauth und Reconfigure
- dynamischer Hoststatus, Devices und Kern-Entities
- Update-/Reboot-/Check-/Export-Aktionen über Semaphore
- robustes Task-Tracking und Statusrefresh
- Diagnostics, Übersetzungen, Tests und Release-Dokumentation

## `0.2.x` – Operational feedback

- letzter Taskstatus, Laufzeit und verständlichere Fehlerzustände
- Security-only Update, falls das Backend dies eindeutig unterstützt
- optionaler Check je Host
- Benachrichtigungen und intelligentere Refresh-Strategie

## `0.3.x` – Maintenance workflows

- Paketdetails und kompakte Releaseinformationen
- optionale Snapshot-/Backup-Vorbedingungen
- Hosttypen, Proxmox-Metadaten und Maintenance Mode
- konfigurierbare Update Policies ohne automatische Reboots

## `0.4.x` – Backend evolution

- erster Adapter für eine dedizierte Homelab Operations API
- Capability Discovery statt fest angenommener Funktionen
- Migrationspfad von Status-JSON plus Semaphore ohne Entity-Neuschreibung

## Langfristig

Weitere Homelab-Funktionen werden nur aufgenommen, wenn sie in Home Assistant
einen klaren Nutzerwert haben und als eigener Capability-Bereich modelliert werden
können. Der Backlog ist die Sammelstelle, nicht die Zusage zur Umsetzung.
