---
title: Home Assistant Main Panel Review
status: accepted
updated: 2026-08-22
tags: [review, home-assistant, panel, jobs, security]
---

# Home Assistant Main Panel Review

## Scope

T-026 entfernt die doppelte globale Native-Aktion und ergänzt eine
administratorgeschützte Home-Assistant-Hauptansicht für Hosts, Jobs, Logs und den
Link zur Backend-Verwaltung. Semaphore behält seine getrennten Check- und Export-
Templates.

## Review-Ergebnis

- Native zeigt nur **Hosts prüfen**. Diese Aktion erzeugt Check-Jobs; passive
  Coordinator-Polls laufen weiterhin automatisch. **Status aktualisieren** bleibt
  ausschließlich beim Semaphore-Provider mit eigener Export-Semantik.
- Der erste geladene Native-Eintrag registriert **Homelab Updates** als admin-only
  Seitenleisten-Panel. Beim Unload übernimmt deterministisch der nächste geladene
  Native-Eintrag.
- Ein Tracker veröffentlicht nach dem terminalen Ergebnis zusätzlich den Zustand
  nach seiner Entfernung. Dadurch wechseln Panel und Entity-Buttons sofort von
  `running` zu idle; ein bereits erfolgreicher Job kann nicht mehr mit
  **Prüfung läuft…** kombiniert erscheinen.
- Das Panel zeigt Connectivity, Hoststatus, laufende/wartende Jobs, letzten Job
  und historischen letzten Fehler getrennt.
- Statussnapshots enthalten keine Jobausgabe und keine Credentials. **Log öffnen**
  lädt genau einen begrenzten redigierten Log über einen getrennten admin-only
  Home-Assistant-WebSocket-Command.
- Der Backend-Token bleibt im Config Entry. Panelcode verwendet weder Local/
  Session Storage, Cookies, Authorization Header noch `innerHTML`; fremde Inhalte
  werden mit `textContent` gerendert.
- **Backend verwalten** enthält nur die bereits konfigurierte tokenfreie Basis-
  URL. Das App-Ingress heißt zur Abgrenzung **Homelab Updates Backend**.
- Die neue Entwicklungsabhängigkeit `home-assistant-frontend` ist exakt passend
  zur Home-Assistant-Testversion gepinnt und wird nicht zur Runtime-Abhängigkeit
  der Integration oder des Backend-Containers.

## Verifikation

`make quality` ist vollständig grün: 257 Tests, 98,22 % Line Coverage und
95,16 % Branch Coverage. Ruff Format/Lint, Mypy strict, echter Chromium,
Dependency Audit und Privacy-Scan sind ebenfalls grün. Die Regression deckt
Panel-Registrierung/Unload/Übergabe, Nicht-Admin-Ablehnung, token-/logfreie
Snapshots, expliziten Logabruf, Check-Command, sichere Textdarstellung und den
Management-Link mit ausschließlich synthetischen Daten ab.

## Entscheidung

Approve. Die neue Browser-/Home-Assistant-Vertrauensgrenze und der globale
Panel-Lifecycle sind in [[../02-architecture/adr/0007-home-assistant-main-panel]]
festgehalten. Eine sichtbare Auswahl mehrerer Native-Einträge bleibt ein
dokumentiertes Backlog-Thema und blockiert `0.2` nicht.
