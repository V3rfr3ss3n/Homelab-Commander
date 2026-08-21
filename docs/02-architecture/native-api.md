---
title: Native API v1
status: accepted
updated: 2026-08-21
tags: [architecture, api, backend]
---

# Native API v1

Basis-Pfad ist `/api/v1`. Mit Ausnahme von `GET /health` benötigen alle
öffentlichen API-Endpunkte `Authorization: Bearer <token>`. Redirects werden vom
Home-Assistant-Client nicht verfolgt. IDs sind kanonische UUIDs.

## Endpunkte

| Methode | Pfad | Ergebnis |
| --- | --- | --- |
| GET | `/health` | einfacher Prozess-Healthcheck |
| GET | `/info` | Version, API-Version und Capabilities |
| GET | `/public-key` | ED25519 Public Key, niemals Private Key |
| GET/POST | `/hosts` | Hostliste bzw. Host anlegen |
| GET/PATCH/DELETE | `/hosts/{host_id}` | stabilen Host lesen/ändern/löschen |
| POST | `/hosts/{host_id}/actions/test-connection` | Connection Job |
| POST | `/hosts/{host_id}/actions/check-updates` | Status Job |
| POST | `/hosts/{host_id}/actions/update` | Update Job |
| POST | `/hosts/{host_id}/actions/reboot` | expliziter Reboot Job |
| POST | `/actions/check` | je vorhandenem Host einen Check Job anlegen |
| GET | `/jobs` | neueste Jobs, begrenztes `limit` |
| GET | `/jobs/{job_id}` | Jobzustand |
| GET | `/jobs/{job_id}/log` | begrenzte, redigierte Ausgabe |
| GET/POST | `/custom-tasks` | Taskdefinitionen lesen/anlegen |
| PATCH/DELETE | `/custom-tasks/{task_id}` | Task ändern/löschen |
| POST | `/hosts/{host_id}/actions/tasks/{task_id}` | Custom Task zielgenau starten |

OpenAPI liegt unter `/api/openapi.json`, die interaktive Entwicklungsansicht unter
`/api/docs`. Diese Dokumente ersetzen keine Autorisierungsprüfung.

## Jobsemantik

`POST`-Aktionen antworten sofort mit `202` und einem persistenten Job. Zustände
sind `queued`, `running`, `success` oder `failed`. Nach Prozessabbruch werden
`running`-Jobs beim Start erneut als `queued` aufgenommen. Update, Reboot und
Custom Tasks verwenden ein Lock je Host. Ein unbekannter Host oder Task scheitert
vor dem Anlegen beziehungsweise vor der Ausführung.

Ein erfolgreicher Update Job kann `reboot_required=true` melden. Das ist nur ein
Statuswert und startet niemals selbst einen Reboot.

## Schemakompatibilität

Additive Felder dürfen Clients ignorieren. Breaking Changes benötigen `/api/v2`,
eine Config-Entry-Migration und ein ADR. Externe Payloads werden an beiden Seiten
in typisierte, unveränderliche Modelle übersetzt.
