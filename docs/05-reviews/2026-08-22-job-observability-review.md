---
title: Job Observability Review
status: accepted
updated: 2026-08-22
tags: [review, jobs, home-assistant, ui, security]
---

# Job Observability Review

## Scope

T-025 trennt aktuelle Gesundheit, letzten Job und historisch letzten Fehler in
Home Assistant. Das native v1-Jobmodell wurde additiv erweitert; Standalone und
Ingress teilen eine authentifizierte Hash-Jobansicht.

## Review-Ergebnis

- Backend Connectivity ist ein `binary_sensor` mit Connectivity Device Class.
- Hub und Host wählen letzten Job und letzten fehlgeschlagenen Job unabhängig.
- Ein neuer Erfolg ändert den Latest-State, nicht den Zeitstempel des letzten
  Fehlers.
- Entityattribute enthalten nur begrenzte Metadaten und eine tokenfreie Job-URL;
  kein stdout/stderr wird in Home Assistant oder Diagnostics übernommen.
- `async_get_job_log` validiert UUID, Authfehler, Not-found und Antwortschema.
- `#/jobs/<job-id>` bewahrt den Ingress-Prefix. Standalone lädt erst nach gültiger
  Session; der gewünschte Hash bleibt während der Anmeldung erhalten.
- Custom Task, Check, Update und Reboot verwenden dasselbe persistente Jobmodell.
- Repairs und Event Entities wurden bewusst nicht ergänzt: Einzelne Jobfehler sind
  keine dauerhafte Integrationsstörung und sollen keinen Issue-/Event-Spam erzeugen.

## Verifikation

`make quality` ist vollständig grün: 250 Tests, 98,22 % Line Coverage und
95,56 % Branch Coverage. Ruff Format/Lint, Mypy strict, Dependency Audit und
Privacy-Scan sind ebenfalls grün. Browsertests decken Standalone, F5,
Sessionpflicht, Ingress-Prefix, Deep Link und tokenfreie URLs mit synthetischem
Executor ab.

## Entscheidung

Approve. Die Änderung ist additiv zu API v1 und verändert keine bestehende
Security- oder Persistenzgrenze; ein neues ADR ist daher nicht erforderlich.
