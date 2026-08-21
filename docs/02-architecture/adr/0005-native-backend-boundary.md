---
title: ADR-0005 Native Backend Boundary
status: accepted
updated: 2026-08-21
tags: [architecture, adr, backend, add-on]
---

# ADR-0005: Native Backend Boundary

## Kontext

Die `0.1`-Integration liest einen separaten Status-Export und delegiert Aktionen
an Semaphore. Für eine eigenständig nutzbare Lösung werden Inventar, SSH,
Ansible, Jobs und Verwaltung benötigt. Diese Verantwortungen in Home Assistant
würden Prozess-, Credential- und Lifecycle-Grenzen vermischen.

## Optionen

1. SSH und Ansible direkt in der Custom Integration ausführen.
2. Nur Semaphore erweitern und als zwingende Infrastruktur voraussetzen.
3. Ein eigenes Backend bauen und es im Add-on sowie als Standalone-Container
   ausliefern; Semaphore bleibt Adapteroption.

## Entscheidung

Option 3 wird umgesetzt. Das System besteht aus:

- der Home-Assistant-Integration als Bedien- und Entity-Schicht,
- einem nativen, API-basierten Operations Backend,
- einer dünnen Add-on-Verpackung desselben Backend-Images mit Ingress-UI.

Die Integration kennt ausschließlich `HostProvider`- und
`AutomationBackend`-Protocols. Native und Semaphore-Adapter normalisieren ihre
Payloads in dieselben unveränderlichen Domainmodelle. Task-IDs sind opak und
können numerische Legacy-IDs oder UUIDs sein.

Private SSH-Schlüssel und Inventar verbleiben im Backend. Mutierende Operationen
fordern genau eine kanonische Host-UUID und werden je Host serialisiert. Das
Backend startet nie automatisch einen Reboot. Add-on und Standalone-Modus nutzen
denselben Anwendungskern und dieselben Migrationen.

## Konsequenzen

- Provider können ohne Änderungen an Entity-Plattformen ergänzt werden.
- Das Backend wird eine eigene Security-, Persistenz- und Release-Grenze.
- Der Add-on-Layer bleibt klein, benötigt aber Home-Assistant-spezifische
  Authentifizierungs- und Ingress-Konfiguration.
- Legacy-Einträge brauchen eine explizite Config-Entry-Migration.
- API- und Datenbankschemas müssen versioniert und getestet werden.
- Direkte SSH-Ausführung in Home Assistant bleibt ausgeschlossen.

## Links

- [[../overview|Architekturübersicht]]
- [[../../01-product/requirements|Produktanforderungen]]
- [[../../00-project/todo|TODO T-019]]
- [[0001-ports-and-adapters]]
- [[0004-safe-reboot-flow]]
