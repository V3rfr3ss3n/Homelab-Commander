---
title: Native API v1
status: accepted
updated: 2026-11-17
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
| GET | `/hosts/{host_id}/packages` | begrenzte Paketdetails eines Hosts lesen |
| GET | `/ui-api/hosts/{host_id}/packages` | Paketdetails in der Management-UI lesen |
| POST | `/hosts/{host_id}/actions/test-connection` | Connection Job |
| POST | `/hosts/{host_id}/actions/check-updates` | Status Job |
| POST | `/hosts/{host_id}/actions/update` | Full update; optional single name or bounded `package_names` selection |
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
sind `queued`, `running`, `success`, `failed` oder `cancelled`. Nach Prozessabbruch
werden nur laufende Verbindungs-/Statusprüfungen erneut eingereiht. Unterbrochene
Updates, Reboots, Custom Tasks und generische Jobs werden `failed` mit
`execution_interrupted`; ihre möglichen Remote-Effekte müssen geprüft werden.
Alle Hostaktionen teilen das Host-Ressourcenlock; verknüpfte Servicejobs verwenden
dasselbe Lock. Ein unbekanntes oder verändertes Ziel scheitert vor Ausführung.

Jede Jobantwort behält die kompatiblen Felder `id` und `action` und ergänzt
`job_id`, `type`, `host_name`, `started_at`, `finished_at`, `exit_code`,
`short_error`, `duration` und `log_available`. `short_error` ist ein begrenzter,
sicherer Hinweis und niemals Prozessausgabe. `duration` wird nur aus vorhandenen
Start-/Endzeitstempeln berechnet. `log_available` verweist ausschließlich auf den
separat authentifizierten Log-Endpunkt.

Ein erfolgreicher Update Job kann `reboot_required=true` melden. Das ist nur ein
Statuswert und startet niemals selbst einen Reboot.
Ein Update ohne Body führt das bestehende vollständige Host-Upgrade aus. Ein Body
mit `package_name` wird im Job persistiert und aktualisiert nur dieses validierte
Paket. Die Management-UI stellt die Paketaktion separat dar und bestätigt den
Paketnamen vor dem Einreihen. Alternativ ist `{"package_names":["curl","git"]}`
für 1–50 eindeutige validierte Namen erlaubt. Genau ein Scope-Feld ist nötig;
leere, doppelte, ungültige oder mehrdeutige Auswahl ergibt 422, niemals Full Update.
Jobs speichern `package_names` zusätzlich zum bestehenden `package_name` für
Wiederanlauf und Rerun. APT nutzt `state=latest only_upgrade=true`; Abhängigkeiten
können mit aktualisiert werden. Counts und Paketliste stammen vom selben
Nachprüfungs-Snapshot; Queueing ändert sie nicht. Siehe
[ADR-0020](adr/ADR-0020-package-selection-and-snapshots.md).

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

## Dashboard und Host-Task-Zuordnungen

Zusätzliche authentifizierte Leseendpunkte unter `/api/v1` und `/ui-api`:
`GET /dashboard`, `GET /jobs/page`, `GET /jobs/timeline` und
`GET /hosts/{host_id}/task-compatibility`. Die Jobseite akzeptiert `host_id`,
`state`, optional `action`, `start`/`end` (UTC-Zeitfenster, beide erforderlich,
maximal 366 Tage), `sort` (newest/oldest/host/action/state), `offset >= 0`,
`limit = 1..100` (Default 25) und liefert
`items`, `total`, `offset`, `limit`; `/jobs` behält die bisherige Listenform.
Die Timeline benötigt `start` und `end`, erlaubt 12–120 Zeit-Buckets und liefert
`total`, `points` mit Start/Ende, mittlerem Zeitstempel, Zustandszählung und maximal
sechs Vorschau-Jobs. Der Endzeitpunkt ist exklusiv.
Dashboard-Aggregate verwenden die gesamte Datenbank und sieben UTC-Kalendertage.
Terminale Jobs werden nach Abschlussdatum, aktive nach Anlagedatum gruppiert.

`POST /hosts/{host_id}/tasks/{task_id}/check` prüft deklarierte Voraussetzungen
explizit und read-only mit 30-Sekunden-Deadline. Es liefert `task_id`, `host_id`,
`state`, `reasons`, `checked_at`, `assigned` und `enabled`. Zustände sind
`unchecked`, `suitable`, `unsuitable`, `failed`. Sichere fehlgeschlagene Checks
sind Metadatenantworten; unbekannte IDs ergeben 404.
`PUT /hosts/{host_id}/tasks/{task_id}/assignment` akzeptiert `enabled: bool`;
`DELETE` entfernt die Zuordnung. Aktivieren/Zuweisen ohne aktuelle geeignete
Prüfung und unzulässige Ausführungen ergeben 409. UI-Mutationen verlangen CSRF.

Tasks ergänzen `requirements` mit Listen `distributions` (OS-ID), `versions`
(exakte VERSION_ID), `programs`, `packages` sowie `requires_sudo`; `host_ids`
enthält aktivierte Hostzuordnungen. Leere Systemlisten erlauben beliebige Systeme;
der primäre Executable wird immer geprüft. Bekannte inkompatible Voraussetzungen
werden einzeln erklärt. Checks gelten höchstens 24 Stunden, Änderungen an SSH-
Verbindung oder Taskausführung/Voraussetzungen invalidieren sie. Der Worker prüft
nach Erwerb des Hostlocks erneut; keine API darf deaktivierte oder nicht
zugewiesene Tasks ausführen. Bestehende Taskclients müssen die neue Freigabe vor
der nächsten Ausführung erfüllen; Antwortfelder und `/api/v1` bleiben kompatibel.

`GET /ui-api/onboarding` akzeptiert `system` (`debian`/`ubuntu`), `username` und
`port` und liefert `system`, `command`. Es erzeugt nur Text, keine Hostaktion.
Das Importformat ist `format: homelab-commander-host`, `version: 1` mit `name`,
`addresses`, `username`, `port`, eingerahmt von `HLC_HOST_BEGIN`/`HLC_HOST_END`.
Siehe [ADR-0012](adr/0012-dashboard-task-compatibility.md).

## Visible UI checks and website metadata

Hosts add `websites` (maximum twelve named HTTP(S) URLs without userinfo), persisted
in an additive migration. Empty arrays clear sites; omitted patch fields preserve them.
The backend never fetches these URLs. Browser icons use origin favicons with no referrer.

Management-only `GET/PATCH /ui-api/preferences/host-checks` reads/writes `enabled`
(default true). `POST /ui-api/actions/check-visible` returns queued status jobs and
requires UI mutation auth/CSRF. An atomic claim rechecks preference, host age,
active jobs and the shared five-minute request cooldown. It never queues updates,
reboots or custom tasks, and no backend timer exists. Clients request only while
Dashboard/Hosts is visible and connected. See
[ADR-0013](adr/0013-visible-dashboard-checks-and-websites.md).

### Job review and setup choices

`POST /api/v1/jobs/{job_id}/review` (Bearer auth) and
`POST /ui-api/jobs/{job_id}/review` (UI auth + CSRF) acknowledge one failed job.
They return its additive nullable `reviewed_at`, preserving the initial timestamp
on repeated calls; 404 means absent and 409 means not failed. No request body or
host action is needed. Dashboard attention excludes reviewed failures.

Authenticated `GET /ui-api/onboarding` retains system/username/port and adds fixed
`mode=create|update`, `shell=/bin/sh|/bin/bash`, `sudo=none|full`,
`restricted_key=true|false` and optional `source` IP/CIDR. Defaults are create, sh,
none, true and empty. Unsupported/invalid values return 422. Rendering never applies
configuration. Output is still the marked version-1 host connection JSON envelope.

### Website icon override

Host website entries accept optional `icon_url`: an HTTP(S) image URL without
credentials. It is stored in existing website JSON and returned when set; absent
or null values retain the legacy `{name,url}` serialized shape. No image is fetched
by the backend. It may reference another explicitly operator-selected origin.
See [ADR-0015](adr/0015-stable-website-icons.md).

Job responses include additive `needs_review`: an unreviewed failure without a
later successful job matching host, action and custom task. Timeline points include
`review_required`, counted across the complete bucket rather than just previews.
These values share the dashboard notice predicate and do not alter stored outcomes.

## Paketdetails

`GET /api/v1/hosts/{host_id}/packages` (Bearer) und
`GET /ui-api/hosts/{host_id}/packages` (UI-Session beziehungsweise Ingress)
liefern ausschließlich Lesedaten. Die Hostliste enthält keine Paketdetails. Die
Antwort ist stabil und enthält höchstens 50 Einträge in Parserreihenfolge; `total`
bleibt die tatsächliche Zahl der vom letzten erfolgreichen Check erkannten
Updates. Vor einem erfolgreichen Check sind `checked_at` und `provider` null.

```json
{
  "packages": [
    {"name": "curl", "old_version": "8.3.0-1", "new_version": "8.8.0-1", "is_security": false}
  ],
  "total": 17,
  "security_updates": 0,
  "checked_at": "2026-11-11T12:00:00+00:00",
  "provider": "debian_apt"
}
```

Unbekannte Hosts ergeben 404; die API benötigt einen Bearer Token. Der UI-GET
verwendet die bestehende UI-Session-Prüfung und benötigt keinen CSRF-Header.
Siehe [ADR-0018](adr/ADR-0018-package-details.md) und
[ADR-0019](adr/ADR-0019-scoped-package-update.md).

## Failure diagnostics

HTTP failures retain their status and compatible `detail` string/list. They add
`error_code`, `request_id`, `timestamp` (timezone-aware UTC), `component`,
`operation` (static route name) and `version`. `X-Request-ID` is generated by the
server for every HTTP request; caller-supplied references are not trusted. Error
responses use `Cache-Control: no-store`. Validation details retain their list and
location/type/message structure, but remove submitted input/context and unknown
extra-field names. Clients must not depend on raw Pydantic message wording.

Unexpected errors return HTTP 500 and `internal_error`, without exception text.
The matching backend log contains only the reference, static operation and up to
six source filenames/line numbers. Worker failures retain
`internal_execution_error` and use the existing job UUID as their reference in the
bounded authenticated job log. No new diagnostic database or public log endpoint
is introduced. Native HA clients preserve a valid reference with the HTTP status
in their safe exception; authentication and malformed-data categories remain
unchanged. See [ADR-0021](adr/0021-safe-failure-diagnostics-and-history.md).

History filters and buckets use a registered deterministic timestamp function
rather than SQLite's version-dependent `unixepoch(..., 'subsec')`. Existing ISO
values, UTC offsets, IDs and stored data remain unchanged; the half-open interval
includes `start` and excludes `end`, with microsecond precision.

## Resource registry (schema 11)

Authenticated GET `/resources` lists active registry entries with `limit=1..100`
(default 25) and `offset>=0`; GET `/resources/{id}` returns one entry. Both are
available under `/api/v1` and `/ui-api`. External routes keep Bearer auth; UI uses
session/Ingress, with CSRF on writes. Existing Host/job API and Info capability-list
shape remain unchanged.

Admin metadata writes: POST `/resources/services` accepts name, service_type,
binding `{provider_id,connection_id,external_id}` and optional host_id; POST
`/resources/instances` accepts name, VM/container kind, binding and optional host_id
and reconciles the same external identity to the same UUID. No provider is contacted.
PATCH `/resources/{id}/host` explicitly links/unlinks a service (nullable host_id).
GET `/resources/{id}/relationships` reads directed edges with `limit=1..100`
(default 100) and `offset>=0`; POST/DELETE
`/resource-relationships` accepts kind, source and target `{kind,id}` references.
DELETE `/resources/{id}` tombstones non-host metadata; use the original host endpoint
for Host removal. Invalid/missing identities give safe 409/404 responses; malformed
DTOs give 422. Duplicate bindings, mismatched kinds, cyclic edges and conflicting
one-to-one VM/Host identities are rejected transactionally. A conflicting generic
host edge never silently reassigns a service.

Bindings are opaque backend configuration references, not stored credentials or
connectivity evidence. Resource metadata may be sensitive and is not exported as
failure diagnostics. These endpoints grant no remote execution permission. See
[ADR-0023](adr/0023-resource-registry-and-module-boundaries.md).

## Groups and tags (schema 12)

Both `/api/v1` and `/ui-api` expose the following authenticated metadata operations;
UI writes and preview require existing CSRF. Status/diagnostic error handling is
unchanged. Group membership is never execution authorization.

| Method | Relative path | Result |
| --- | --- | --- |
| GET | `/groups?query=&limit=25&offset=0` | Name-filtered group definitions |
| POST | `/groups` | New group with stable UUID (201) |
| GET/PUT/DELETE | `/groups/{id}` | Read/replace/delete metadata; missing GET/DELETE 404 |
| GET | `/groups/{id}/resources?limit=25&offset=0` | Current effective membership page |
| POST | `/groups/preview?limit=25&offset=0` | Evaluate unsaved definition without writes |
| GET | `/group-resources?query=&kind=&tag=&limit=25&offset=0` | Filtered registry facts page |
| PUT | `/resources/{id}/tags` | Replace tags (`{"tags":["production"]}`), 204 |

A definition contains `name`, `description`, `kind` (`manual`/`smart`), `members`
(UUIDs, manual only) and nullable `rule`. A smart rule is
`{"combine":"all","predicates":[{"field":"tag","value":"production"}]}`.
The response adds `id`. Pages return `total`, `items`, `limit`, `offset`; `total`
counts the entire selection, not the displayed slice. Items contain UUID, kind,
name, distro and known status/tag/capability/relationship facts, no Host address.
Absent capabilities are not inferred from the legacy Info capability list.

Invalid request definitions return 422 without submitted values. Inconsistent writes,
invalid stored rules and exceeded evaluation budgets return safe 409. Preview does
not cache or authorize future execution. For exact rule semantics, migration,
budgets, unknown values and future policy revalidation see
[ADR-0024](adr/0024-bounded-resource-groups.md).

Resource inventory accepts additive `group_id=<UUID>`, `sort=name|kind` (default
`name`) and `direction=asc|desc` (default `asc`). Group membership, literal name,
type and tag constraints intersect before sorting/pagination, so `total` covers the
same full filtered snapshot as the rows. Sorting uses name and UUID tie-breakers.
A missing group returns 404, malformed UUID/sort/direction returns 422; invalid
stored rules retain 409. No fallback widens a missing group to all resources. These
parameters do not authorize execution or change the existing members endpoint.

## Resource job scopes (#44)

Job responses add `execution` (nullable for orphaned historical jobs), containing
`scope` and `context`, plus `interrupted_at`, `interrupted_started_at` and
`recovery_count`. Scope records the internal resource kind/UUID, namespaced operation,
optional execution Host, canonical conflict references, exact package selection or
task identity/revision and a connection fingerprint. Context records only the
server-authenticated entrance, not an individual identity. Clients cannot supply
these values through legacy action bodies. `approval_id` remains null and confers
no permission. Old job fields, states, IDs, logs and routes remain compatible.

Running Host connection edits/removal return 409; display-name edits remain possible.
Changed queued targets or task revisions fail with `execution_scope_changed`.
Interrupted mutation failures require explicit review even after a later success.
Generic `resource_operation` jobs have only an internal, default-deny feature port;
no generic resource/group execution endpoint or production service handler exists.
See [ADR-0026](adr/0026-resource-jobs-and-safe-recovery.md) for migration and recovery.


## Central policy metadata and denials (#46)

Authenticated entrances bind a server-owned principal. New job
`execution.context.principal` contains only internal UUID/kind/source; migrated
snapshots may omit it and retain their legacy entrance. It is not a token, session
or individual human identity. Existing action bodies cannot supply principal, role,
policy or approval overrides. Non-admin identities cannot enter the legacy admin
API, key export, task or shell paths. Production continues recognizing its existing
admin credential only; no agent provisioning endpoint is added.

Policy rejection returns 403 with compatible `detail`, `error_code: policy_denied`
and existing safe diagnostics. Authenticated policy denials are audited without
request/credential/command data. Worker denial becomes a failed `policy_denied` job.
Existing direct admin actions, CSRF and authentication remain mandatory. Approval
requests are domain contracts, not new HTTP/UI endpoints; only statically composed
future protected operations can use the single-use service. Pending approvals do
not contribute to queued-job counts. See
[ADR-0027](adr/0027-central-policy-and-approval-contracts.md).
