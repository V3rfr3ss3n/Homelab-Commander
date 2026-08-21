---
title: TODO
status: active
updated: 2026-08-20
tags: [project, todo]
---

# TODO

Dies ist die priorisierte Arbeitsliste. Es soll höchstens ein größeres Paket in
`In Arbeit` stehen.

## In Arbeit

- [ ] T-017 vollständige Abnahme, Privacy Audit und Release Candidate

## Als Nächstes

- [ ] T-002a endgültige GitHub-Repository-URL eintragen
- [ ] T-002b Git-Remote konfigurieren, sobald das öffentliche Repository existiert
- [ ] T-017a Hassfest und HACS Action im öffentlichen GitHub-Repository bestätigen
- [ ] T-017b isolierte manuelle Installation aus dem Releaseartefakt durchführen
- [ ] T-018 Home-Assistant-Patch mit gefixter `cryptography`-Version übernehmen
  und SE-2026-001 spätestens am 2026-09-15 entfernen

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
