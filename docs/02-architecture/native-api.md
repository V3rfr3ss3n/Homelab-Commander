---
title: Native API v1
status: accepted
updated: 2026-08-23
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

## Management-UI-Grenze

`/ui-api` ist kein alternativer externer API-Zugang. Standalone verwendet
`POST /ui-api/auth/login`, `GET /ui-api/auth/session` und
`POST /ui-api/auth/logout` für eine kurzlebige HttpOnly-Session. Mutationen
verlangen zusätzlich `X-CSRF-Token`. Ingress verwendet dieselben Management-
Routen ohne diese Session, weil Supervisor authentifiziert; CSRF bleibt aktiv.
Bearer Header verleihen außerhalb von Ingress keinen Zugriff auf `/ui-api`, und
UI-Cookies verleihen keinen Zugriff auf `/api/v1`.

Die App verwendet den von Home Assistant vorgegebenen Ingress-Einstieg `/` und
setzt deshalb keinen redundanten `ingress_entry`. HTML, Assets und `/ui-api`
akzeptieren im Ingress-Modus nur Verbindungen von den beim Start über den stabilen
DNS-Alias `supervisor` aufgelösten Proxy-Adressen. Die Quelle wird weder fest
kodiert noch persistiert. Der öffentliche `/api/v1`-Vertrag bleibt davon getrennt
und verlangt weiterhin den Bearer Token.

## Jobsemantik

`POST`-Aktionen antworten sofort mit `202` und einem persistenten Job. Zustände
sind `queued`, `running`, `success`, `failed` oder `cancelled`. Nach Prozessabbruch werden
`running`-Jobs beim Start erneut als `queued` aufgenommen. Update, Reboot und
Custom Tasks verwenden ein Lock je Host. Ein unbekannter Host oder Task scheitert
vor dem Anlegen beziehungsweise vor der Ausführung.

Jede Jobantwort behält die kompatiblen Felder `id` und `action` und ergänzt
`job_id`, `type`, `host_name`, `started_at`, `finished_at`, `exit_code`,
`short_error`, `duration` und `log_available`. `short_error` ist ein begrenzter,
sicherer Hinweis und niemals Prozessausgabe. `duration` wird nur aus vorhandenen
Start-/Endzeitstempeln berechnet. `log_available` verweist ausschließlich auf den
separat authentifizierten Log-Endpunkt.

Ein erfolgreicher Update Job kann `reboot_required=true` melden. Das ist nur ein
Statuswert und startet niemals selbst einen Reboot.

Ein fehlgeschlagener Job enthält einen sicheren `error_code`; technische Details
bleiben im authentifizierten, redigierten Log. Native Built-ins verwenden unter
anderem `python_interpreter_unavailable`, `sudo_unavailable`,
`apt_lock_unavailable`, die phasengenauen `check_updates_*_failed`-Codes und
`invalid_ansible_output`. Clients müssen unbekannte additive Codes generisch
darstellen können.

## Schemakompatibilität

Additive Felder dürfen Clients ignorieren. Breaking Changes benötigen `/api/v2`,
eine Config-Entry-Migration und ein ADR. Externe Payloads werden an beiden Seiten
in typisierte, unveränderliche Modelle übersetzt.
