---
title: Vision und Scope
status: accepted
updated: 2026-08-21
tags: [project, vision, scope]
---

# Vision und Scope

## Vision

Homelab Updates wird eine erweiterbare Home-Assistant-Integrationsplattform für
lokale Homelab-Betriebsaufgaben. Der erste vertikale Funktionsumfang macht den
Updatezustand von Linux-Systemen sichtbar und stößt kontrollierte Updates oder
Reboots über ein externes Automatisierungsbackend an.

Home Assistant bleibt Bedien- und Darstellungsebene. Privilegierte Ausführung,
Inventar und Zugangsdaten liegen im separaten nativen Backend, das entweder als
Home-Assistant-Add-on oder eigenständiger Container betrieben wird. Semaphore
bleibt ein optionaler Legacy-Provider.

## Produktprinzipien

- **Public by default:** Jeder Commit darf ohne Bereinigung veröffentlicht werden.
- **UI first:** Installation und Konfiguration erfolgen über Home Assistants UI.
- **Backendunabhängiger Kern:** Entities kennen keine Semaphore-Endpunkte.
- **Read many, command deliberately:** Status wird effizient zentral gelesen;
  schreibende Aktionen sind explizit und nachvollziehbar.
- **Graceful degradation:** Ein ausgefallener Command-Backend darf lesbare
  Statusdaten nicht unbrauchbar machen.
- **Erweiterbar ohne God Module:** Neue Funktionen werden als klar begrenzte
  Fähigkeiten ergänzt, nicht in einen universellen Client gepackt.
- **Quality is blocking:** Typen, Tests, Security und Dokumentation sind Teil der
  Definition of Done.

## Scope `0.1.0`

- Config Flow, Reauthentication und Reconfigure vollständig über die UI
- Status-Provider für einen konfigurierbaren HTTP-JSON-Endpunkt
- Semaphore-Adapter für Check, Status-Export, Update und Reboot
- dynamische Geräte und Entities je Host
- native Update Entity sowie relevante Sensoren und Buttons
- zentrales Polling und asynchrones Task-Tracking
- englische und deutsche UI-Texte
- redigierte Diagnostics
- HACS-fähige Struktur und öffentlicher Release-Prozess
- automatisierte Tests und blockierende Quality Gates

## Nicht im Scope von `0.1.0`

- direkte SSH- oder Ansible-Ausführung in Home Assistant
- automatische Reboots oder implizite Updateausführung
- Verwaltung einzelner Pakete
- Windows-, Container-, Backup-, Snapshot- oder VM-Lifecycle-Management
- automatische Einrichtung von Semaphore oder Ansible
- mehrere Command-Backends innerhalb eines Config Entry
- Push/Websocket-Status

Diese Punkte sind keine Architekturverbote. Neue Fähigkeiten werden nach `0.1.0`
über Backlog, Anforderungen und ADRs aufgenommen.

## Zielbild `0.2.0-dev`

- drei getrennte Komponenten: Custom Integration, natives Backend und Add-on
- dasselbe Backend-Image für Add-on und eigenständigen Docker-Betrieb
- SQLite-Persistenz, Hostverwaltung und SSH-Schlüssel ausschließlich im Backend
- eingebaute, asynchrone Ansible-Aktionen für Status, Update und Reboot
- persistente Jobhistorie mit begrenzter, redigierter Ausgabe
- dynamisch verwaltete Custom Tasks
- auswählbarer Native- oder Semaphore-Provider je Config Entry
- Ingress-Oberfläche für die Backend-Verwaltung

Das Backend ist eine eigene Vertrauensgrenze. Die Integration erhält weder
private SSH-Schlüssel noch führt sie Prozesse aus. Neustarts bleiben immer
explizit; ein Update darf lediglich melden, dass anschließend ein Neustart nötig
ist.

## Erfolgskriterien

`0.1.0` ist erfolgreich, wenn ein neuer Nutzer die Integration ohne Quellcode-
Änderung konfigurieren kann, beliebige Host-IDs dynamisch erscheinen, Aktionen
zielgenau an den gewählten Host gehen, Fehler sicher und verständlich behandelt
werden und der vollständige Quality Gate reproduzierbar grün ist.

Siehe [[../01-product/acceptance|Abnahme]] und [[roadmap|Roadmap]].
