---
title: TODO
status: active
updated: 2026-08-22
tags: [project, todo]
---

# TODO

Dies ist die priorisierte Arbeitsliste. Es soll höchstens ein größeres Paket in
`In Arbeit` stehen.

## In Arbeit

- [ ] T-020a Container-Build und Healthcheck der UI-Änderung wiederholen,
  sobald ein lokaler Docker-Daemon erreichbar ist. Compose-Validierung und alle
  codebasierten Gates sind grün; Docker Desktop stellte keinen API-Socket bereit.

## Als Nächstes

- [ ] T-002a endgültige GitHub-Repository-URL eintragen
- [ ] T-002b Git-Remote konfigurieren, sobald das öffentliche Repository existiert
- [ ] T-017a Hassfest und HACS Action im öffentlichen GitHub-Repository bestätigen
- [ ] T-017b isolierte manuelle Installation aus dem Releaseartefakt durchführen
- [ ] T-018 Home-Assistant-Patch mit gefixter `cryptography`-Version übernehmen
  und SE-2026-001 spätestens am 2026-09-15 entfernen
- [ ] T-017 vollständige Abnahme, Privacy Audit und Release Candidate nach
  Abschluss der `0.2`-Entwicklung

## Blocker und offene Festlegungen

- Die endgültige GitHub-Repository-URL ist unbekannt. Das nicht veröffentlichte
  Entwicklungsmanifest verwendet deshalb reservierte
  `example.invalid`-URLs; `make release-check` blockiert damit jeden Release.
- Die Semaphore-Kompatibilitätsmatrix bleibt bis zu isolierten Tests mit
  synthetischen Response-Fixtures bewusst vorläufig.

## Done

- [x] Fachskizze bereinigt und von realen Infrastrukturbeispielen getrennt
- [x] Obsidian-tauglichen Wissensspeicher angelegt
- [x] Architektur-, Security-, Review- und Quality-Gate-Regeln festgelegt
- [x] T-001 öffentliche Projekt- und Dokumentationsgrundlage erstellt
- [x] Git-Repository auf Branch `main` initialisiert
- [x] GitHub-Owner und Manifest-Codeowner `@V3rfr3ss3n` festgelegt
- [x] T-003 Python-3.14-/uv-Projekt mit Lockfile angelegt
- [x] T-004 CI und Quality-Gate-Workflows angelegt
- [x] T-005 bis T-016 Integration, Adapter, Flows, Coordinator, Entities,
  Diagnostics, Übersetzungen, Tests und Benutzerhandbuch implementiert
- [x] T-019 Native Backend, App/Add-on, Standalone-Container,
  Provider-Migration, Ingress-Verwaltung und vollständiges Quality Gate für
  `0.2.0-dev` implementiert
- [x] T-020 Management-UI nach realem E2E-Smoke repariert und mit Chromium-
  Regressionstests für Standalone und Ingress-Prefix abgesichert
- [x] T-021 Standalone-UI mit explizitem Verbindungszustand, Disconnect und
  sicherem Session-Reset bei Reload sowie `401`/`403` ergänzt
- [x] T-022 Realen `check_updates`-Fehler bis zum Ad-hoc-Output-Parser analysiert;
  strukturierten Ansible-Callback, konsistente Interpreter-/sudo-Prüfung,
  robuste APT-Phasen, UI-Fehlertexte und vollständige Regression ergänzt
- [x] T-023 Standalone-Token gegen kurzlebige serverseitige HttpOnly-Session mit
  F5-Recovery, CSRF, Ablauf und serverseitigem Logout getauscht
- [x] T-024 Management-UI um einzelnes bedarfsgesteuertes Job-Polling mit
  Hostrefresh, Action-Locking, Backoff und Reload-/Disconnect-Lifecycle ergänzt
- [x] T-025 Native Job-Observability um Connectivity, getrennte Latest-/Failure-
  Semantik, kompakte HA-Metadaten, expliziten Logabruf und authentifizierte
  Standalone-/Ingress-Deep-Links ergänzt
- [x] T-026 Native Hub-Aktionen bereinigt und administratorgeschützte Home-
  Assistant-Hauptansicht mit Hosts, Jobs, bedarfsgesteuerten Logs und Backend-
  Link ergänzt
- [x] T-027 Task-Tracker-Abschluss veröffentlicht nach dem Entfernen den finalen
  Idle-Zustand, damit Panel und Action-Buttons nicht auf `running` stehen bleiben
