---
title: ADR-0007 Home Assistant Main Panel
status: accepted
updated: 2026-08-22
tags: [architecture, adr, home-assistant, ui, security]
---

# ADR-0007: Home Assistant Main Panel

## Kontext

Native Jobmetadaten existieren als Entities, vollständige redigierte Logs bleiben
absichtlich im Backend. Dadurch ist Home Assistants Geräteansicht sicher, aber
kein verständlicher operativer Einstieg: Logs sind nicht direkt sichtbar und
die native globale Aktion `Status aktualisieren` dupliziert technisch
`Hosts prüfen`. Die Backend-Management-UI ist bei Standalone über eine eigene URL
und bei der App über Supervisor Ingress erreichbar.

Eine Hauptansicht in Home Assistant darf den Backend-Token nicht in den Browser
geben, keine vollständigen Logs in Entities/Recorder kopieren und keine zweite
dauerhafte Browsersession etablieren.

## Optionen

1. Nur Entities und Dashboard-Vorlagen dokumentieren.
2. Die Backend-Management-UI in einem generischen Iframe einbetten.
3. Ein kleines natives HA-Panel registrieren, das über admin-only WebSocket-
   Commands auf die vorhandenen Runtime Services zugreift.

## Entscheidung

Option 3 wird für Native umgesetzt:

- Der erste geladene Native-Config-Entry registriert `/homelab-updates` als
  administratorgeschütztes `panel_custom`; bei Unload wird ein weiterer
  geladener Native-Eintrag übernommen.
- Ein statisches Web Component ohne zusätzliche Runtime-Abhängigkeit rendert
  Coordinator- und Jobmetadaten ausschließlich als Text.
- Ein abonnierter WebSocket-Command streamt kompakte Snapshots ohne Logs und
  Secrets. Coordinator- und Task-Manager-Listener lösen Updates aus.
- Jobausgabe wird nur nach **Log öffnen** über einen getrennten admin-only Command
  durch den serverseitig authentifizierten Native Adapter geladen.
- **Hosts prüfen** startet `CHECK_ALL`. Der doppelte Native-Refresh-Button wird
  entfernt; Semaphore behält seine getrennte Export-/Refresh-Aktion.
- **Backend verwalten** verlinkt tokenfrei auf die konfigurierte Backend-URL.
  App-Ingress bleibt wegen seiner Supervisor-spezifischen URL eine separate
  Management-Oberfläche.

## Konsequenzen

- Home Assistant besitzt eine klare Hauptansicht, ohne Backend-Credentials an den
  Browser zu übertragen oder Logs zu persistieren.
- Panel und Commands sind auf Administratoren begrenzt. Ein kompromittierter
  HA-Admin besitzt ohnehin die Berechtigung, Integrationsaktionen auszulösen.
- Die konfigurierte Backend-URL muss browser-erreichbar sein, damit der direkte
  Management-Link funktioniert. Für App-Betrieb bleibt der Ingress-Eintrag.
- Mehrere Native-Einträge teilen zunächst ein globales Panel. Eine sichtbare
  Entry-Auswahl ist als mögliche Erweiterung im Backlog dokumentiert.
- Tests benötigen in der isolierten Entwicklungsumgebung das zu Home Assistant
  passende `home-assistant-frontend`; produktiv ist es Plattformbestandteil.

## Links

- [[../overview|Architekturübersicht]]
- [[../../01-product/requirements|Produktanforderungen]]
- [[../../04-operations/security-and-privacy|Security und Privacy]]
- [[../../04-operations/native-backend|Native Backend Betrieb]]
- [[0005-native-backend-boundary]]
- [[0006-standalone-ui-session]]
