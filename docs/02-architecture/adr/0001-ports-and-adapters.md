---
title: ADR-0001 Ports und Adapter
status: accepted
updated: 2026-08-20
tags: [architecture, adr, backend]
---

# ADR-0001: Ports und Adapter für externe Systeme

## Kontext

Der erste Release nutzt einen JSON-Statusendpoint und Semaphore. Langfristig soll
das Projekt weitere Homelab-Funktionen und ein dediziertes Backend unterstützen.
Direkte Semaphore-Aufrufe aus Entities würden diese Entwicklung blockieren.

## Entscheidung

Entity- und Flow-Code sprechen mit anwendungsnahen Services. Externe Systeme
werden über kleine typisierte Protocols und Adapter angebunden. Externe Payloads
werden unmittelbar an der Adaptergrenze in Domainmodelle übersetzt.

Der Coordinator ist Home-Assistant-Infrastruktur und orchestriert den
Status-Use-Case; er ist nicht selbst der HTTP-Client. Task-Tracking ist ein
Lifecycle-bewusster Application Service.

## Konsequenzen

- Semaphore kann ersetzt werden, ohne Entityplattformen neu zu schreiben.
- Zusätzliche Abstraktionen sind erlaubt, aber nur entlang echter Fähigkeiten.
- Adapter- und Contract-Tests werden zentral wichtig.
- Backend-spezifische Features benötigen Capability Modeling oder einen eigenen
  Use Case; sie dürfen nicht durch `if semaphore` in Entities durchsickern.
