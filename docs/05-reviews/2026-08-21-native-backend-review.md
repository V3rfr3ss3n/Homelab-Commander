---
title: Review Native Backend 0.2
status: active
updated: 2026-08-21
tags: [review, backend, add-on, security]
---

# Review Native Backend `0.2.0-dev`

## Scope

Drei-Komponenten-Architektur, native API/Persistenz/Execution, Provider-Migration,
Custom Tasks, Home-Assistant-App, Ingress-UI und Standalone-Container.

## Bestätigt

- Entities hängen an `HostProvider`/`AutomationBackend`, nicht an API-Pfaden.
- Alte Semaphore-Imports und Config Entries besitzen Kompatibilitätspfade.
- Host- und Jobidentitäten sind getrennte UUIDs; Anzeigenamen sind keine Ziele.
- Jobqueue ist persistent, HTTP-Actions sind kurz und Hostmutationen serialisiert.
- ED25519 Private Key bleibt unter `/data`, wird `0600` und besitzt keinen
  API-Endpunkt.
- Shell-Semantik ist explizit und standardmäßig deploymentweit deaktiviert.
- Reboot ist eine separate Aktion; Update erzeugt höchstens Rebootstatus.
- Ingress-/Containerdefinition fordert keine privilegierten Hostressourcen.
- Ingress bietet Dashboard, SSH-Onboarding, Host-/Task-Verwaltung, explizite
  Bestätigungen, Aktionen, Jobhistorie und begrenzte Joblogs.
- Tests verwenden ausschließlich Fake Executor, synthetische Daten und gemocktes
  HTTP; keine Automation erreicht einen realen Host.

## Verifikation

- `make quality`: grün, 207 Tests
- Coverage: 98,09 % Lines und 95,18 % Branches
- Ruff Preview, Strict Mypy, Pip Audit und Privacy Scan: grün
- Standalone-Image lokal gebaut; Compose-Modell validiert
- isolierter Container-Smoke-Test: Health `ok`, Hauptprozess UID `10001`,
  Produktionsabhängigkeit `cryptography 50.0.0`

## Bewusste Trade-offs

- `StrictHostKeyChecking=accept-new` benötigt eine vertrauenswürdige
  Erstverbindung; Fingerprint-Verifikation bleibt ein dokumentierter manueller
  Onboarding-Schritt.
- Ansible `become` mit Built-in-Modulen lässt sich nicht stabil auf einzelne
  sudoers-Binärpfade reduzieren. Der dedizierte Remote-Key ist daher als
  privilegierte Identität zu schützen.
- Der Ingress-Client ist ohne Frontend-Build als eingebettetes HTML implementiert.
  Das hält das Image klein, erfordert aber eine begründete Ruff-E501-Ausnahme für
  das minifizierte Asset.
- Gelöschte dynamische Custom Tasks hinterlassen ihre Home-Assistant-Registry-
  Entity unavailable; automatische Registry-Löschung wäre überraschend und wird
  nicht durchgeführt.

## Vor stabilem Release offen

- endgültige öffentliche Repository-/Issue-/Dokumentations-URLs
- Multi-Arch-Image bauen, signieren und in isolierter App-Installation prüfen
- Hassfest/HACS im öffentlichen Repository bestätigen
- Container- und App-Backup/Restore manuell mit rein synthetischer Umgebung

## Bekannte Grenzen des Development-Stands

- Produktiv unterstützt wird zunächst Debian/Ubuntu mit APT.
- Laufende Jobs können noch nicht über die API abgebrochen werden.
- Externes HTTPS wird über einen vorgeschalteten Reverse Proxy terminiert.
- Custom Tasks besitzen bewusst nur Command/Shell, Beschreibung und Enabled;
  feingranulare Become-, Timeout-, Bestätigungs- und Target-Policies sind Backlog.
- Das App-Image ist noch nicht veröffentlicht und deshalb noch nicht aus einem
  öffentlichen Add-on-Repository installierbar.

## Ergebnis

Die Architektur- und Security-Grenzen sind für einen Development-Stand
akzeptiert. Ein stabiles Release bleibt bis zu den aufgeführten externen und
manuellen Prüfungen blockiert.
