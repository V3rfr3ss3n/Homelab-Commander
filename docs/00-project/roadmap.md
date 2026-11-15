---
title: Roadmap
status: active
updated: 2026-11-15
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

## `0.2.0-dev` – Native Backend

- natives FastAPI-/SQLite-/Ansible-Backend mit persistenten Jobs
- dasselbe Image für Standalone Docker und Home-Assistant-App
- native Providerwahl und Migration bestehender Semaphore-Einträge
- Ingress-Verwaltung für Hosts, Public Key, Jobs und Custom Tasks
- letzter Taskstatus, Backend Health und Queue-Zustände in Home Assistant

## `0.3.x` – Maintenance workflows

- [x] `0.3.0-dev.5`: Paketdetails mit begrenzter Speicherung, read-only API und
  Paketdialog und gezielten Einzel-/Auswahlupdates zur Review vorbereitet;
  [dev.5-Abnahme](../05-reviews/2026-11-14-dev5-acceptance.md) bleibt vor Release offen.
- Kompakte Releaseinformationen
- optionale Snapshot-/Backup-Vorbedingungen
- Hosttypen, Proxmox-Metadaten und Maintenance Mode
- konfigurierbare Update Policies ohne automatische Reboots

## `0.4.x` – Backend evolution

- weitere Adapter für Operations APIs
- Capability Discovery statt fest angenommener Funktionen
- Push-Status und Capability Negotiation bewerten

## Langfristig

Weitere Homelab-Funktionen werden nur aufgenommen, wenn sie in Home Assistant
einen klaren Nutzerwert haben und als eigener Capability-Bereich modelliert werden
können. Der Backlog ist die Sammelstelle, nicht die Zusage zur Umsetzung.

## Approved future-platform plan (2026-11-15)

The approved English [Product & Architecture Specification v1.0](../01-product/future-platform-specification.md) is the planning baseline for future work; it does **not** describe already shipped features. The priority sequence is:

1. Architecture & Platform Foundation (including host/service relationships, manual and smart groups, policy groundwork).
2. Linux Distribution Expansion (APT, DNF, Zypper, pacman, restricted AUR, apk and compatibility research).
3. Minecraft Management (Pterodactyl Client API only initially; extension updates, backup and protected restore).
4. Proxmox & Infrastructure.
5. Automation & External Services (Semaphore, n8n and workflows).
6. Secure AI Operations (restricted identity, safe update policies, backend-only human approvals).

Platform reliability, releases, legal compliance, quality and data migration cut across every phase. Decisions and unscoped future work are recorded in specification section 19. GitHub issue planning uses specification section links and explicit dependencies. Do not interpret the order as release-date commitments.
