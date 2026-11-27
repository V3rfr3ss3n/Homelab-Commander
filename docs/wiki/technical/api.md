---
title: Native API
status: active
updated: 2026-11-23
tags: [wiki, technical]
---

# Native API

The external API uses `/api/v1`. `GET /api/v1/health` is public; other external
endpoints require `Authorization: Bearer <token>`. Canonical host/job/task IDs are
UUIDs. HA's native adapter does not follow redirects.

| Resource | Contract |
| --- | --- |
| `/info` | Version, API version and capabilities |
| `/public-key` | Public ED25519 key only |
| `/hosts` and `/hosts/{host_id}` | Inventory list/create/read/update/delete |
| `/hosts/{host_id}/actions/test-connection` | Explicit connection-test job |
| `/hosts/{host_id}/actions/check-updates` | Explicit status-check job |
| `/hosts/{host_id}/actions/update` | Explicit host-update job |
| `/hosts/{host_id}/actions/reboot` | Explicit reboot job |
| `/actions/check` | Create a check job for each managed host |
| `/jobs`, `/jobs/{job_id}`, `/jobs/{job_id}/log` | Bounded history, job state and authenticated bounded output |
| `/custom-tasks` and `/custom-tasks/{task_id}` | Structured task management |
| `/hosts/{host_id}/actions/tasks/{task_id}` | Execute a custom task on one host |

Action POSTs return `202` and a job instead of holding the request for Ansible.
Job responses retain `id`/`action` and add normalized metadata such as type, name,
timestamps, duration, safe error code and log availability. Unknown additive fields
may be ignored. Breaking schema changes need a version/migration decision.

OpenAPI is available at `/api/openapi.json`, with an interactive view at `/api/docs`.
The [versioned API contract](../../02-architecture/native-api.md) defines exact
methods, fields and compatibility requirements.

## Management API separation

`/ui-api` is a management interface, not another bearer-authenticated external API.
Standalone login/session/logout exchange the API token for an opaque HttpOnly
session. Ingress uses Supervisor auth. Both mutation paths enforce CSRF. UI cookies
do not authorize `/api/v1`, and external Bearer headers do not substitute for a
standalone management session.

## Dashboard, assignments and prerequisites

Additive read routes under both API prefixes are `/dashboard`, `/jobs/page`, `/jobs/timeline` and
`/hosts/{host_id}/task-compatibility`. Job pages accept `host_id`, `state`, `action`, an optional `start`/`end` pair
(maximum 366 days), `sort` (newest, oldest, host, action or state), `offset`
and `limit` (1–100, default 25), returning `items`, `total`, `offset` and `limit`.
The timeline requires start/end, accepts 12–120 bins, and returns complete counts
with at most six preview jobs per point. Point bounds are inclusive/exclusive so
they can be passed to the job page.
The existing `/jobs` list shape is preserved.

`POST /hosts/{host_id}/tasks/{task_id}/check` explicitly runs the fixed probe and
returns safe compatibility metadata (30-second deadline). `PUT` on the same base
plus `/assignment` accepts `{ "enabled": true }`; `DELETE` removes the assignment.
These are authenticated mutations and require CSRF on `/ui-api`. Unknown identities
return 404; unsuitable assignment or forbidden execution returns 409. A check result
can itself be unsuitable or failed and is returned as metadata for the operator.

Task responses add `requirements` and `host_ids` (enabled assignments). Requirements
contain `distributions`, `versions`, `programs`, `packages` and `requires_sudo`.
`GET /ui-api/onboarding?system=debian&username=automation&port=22` returns a command
for authenticated UI users; it executes nothing. Only Debian/Ubuntu and dedicated
non-root account names are accepted. See [ADR-0012](../../02-architecture/adr/0012-dashboard-task-compatibility.md).

## Visible checks and host websites

Host create/patch/read responses add `websites`, an array (maximum twelve) of
`{ "name": "Portal", "url": "https://service.example.invalid" }`. Omitted values
preserve existing sites on patch; an empty array clears them. Only HTTP(S) URLs
without userinfo are accepted. Sites are stored separately from connection identity.

`GET /ui-api/preferences/host-checks` reads `{ "enabled": true }`;
`PATCH` updates this shared persisted preference and requires UI auth plus CSRF.
`POST /ui-api/actions/check-visible` returns a list of queued status jobs and also
requires CSRF. It skips disabled/recent/busy/cooldown hosts atomically. The backend
does not schedule itself. Visibility/route/disconnect control belongs to the client.
The fixed interval/cooldown is five minutes. See
[ADR-0013](../../02-architecture/adr/0013-visible-dashboard-checks-and-websites.md).

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

## Safe error references

Failures retain HTTP status and `detail` and add a safe error code, request ID,
UTC timestamp, component, static operation and version. The server-generated
`X-Request-ID` connects an unexpected API failure to a sanitized backend code
location. Validation responses exclude input values and exception context.
Existing clients can ignore additive fields. No public diagnostic/log endpoint or
new authentication mechanism is added. See the
[failure contract](../../02-architecture/native-api.md#failure-diagnostics).

## Resource registry foundation

The next reviewed registry block adds bounded authenticated resource inventory,
service/instance metadata, explicit host links and typed relationships alongside
the existing v1 Host/job API. UI writes retain CSRF. No new provider or remote
execution is enabled. See the [exact API contract](../../02-architecture/native-api.md#resource-registry-schema-11).

## Groups and tags

Group/tag metadata, bounded preview and resource filters are documented in the [schema-12 API](../../02-architecture/native-api.md#groups-and-tags-schema-12). UI preview/writes retain CSRF; membership is not execution permission.

Resource discovery can additionally filter by group UUID and sort by name or kind,
ascending or descending, before paging. Missing groups fail rather than silently
showing all inventory. See the [API contract](../../02-architecture/native-api.md).

## Resource job execution metadata

Existing job responses add immutable `execution.scope` and `execution.context`,
plus interruption/recovery metadata. Context identifies the authenticated entrance,
not a claimed person or an approval grant. Legacy action bodies cannot override it.
Interrupted mutations fail safely rather than automatically replaying; running Host
connection changes/removal return 409. Generic service operations remain internal
and default denied. See [the API contract](../../02-architecture/native-api.md)
and [recovery guide](persistence.md).


## Central policy compatibility

Existing authenticated admin actions retain their API and CSRF contracts. Job
context adds a safe optional principal UUID/kind/source; it is never a credential or
client-selected role. Policy rejection uses 403, compatible `detail` and existing
safe diagnostics with `policy_denied`. Agent/automation subjects cannot use legacy
admin/task/key routes. No agent token provisioner or approval API is enabled.
See [the policy decision](../../02-architecture/adr/0027-central-policy-and-approval-contracts.md).


## Linux package provider compatibility

The Linux feature extraction changes internal ownership only. Host action URLs,
request scopes, job references, package totals/bounded details and Info capability
strings retain their existing contract. Stored `debian_apt` remains the production
provider; internal namespaced capability metadata does not enable a new provider
selection API or grant execution authority. A synthetic second provider is test-only.


## DNF/Zypper observations (#48 review)

Host configuration adds explicit `dnf` and `zypper` choices. Existing `/api/v1`
actions and valid APT values remain. For the new providers, host/package security
counts, row classification and reboot signals can be JSON null. Null is unknown,
never zero/false. Additive `package_scopes` lists observed update scopes; empty is
read-only, null is unobserved/legacy. New RPM configurations require the updated
integration or compatible clients before activation. The
[API contract](../../02-architecture/native-api.md#rpm-package-observations-schema-15-48-review)
and [ADR-0030](../../02-architecture/adr/0030-dnf-zypper-and-nullable-observations.md)
record admission, compatibility and synthetic-only certification limits.

The new-host UI explicitly sends `package_provider: auto` by default.
For compatibility, `POST /hosts` requests omitting the field retain `debian_apt`.
Explicit values and all stored rows are preserved. The `auto` value denotes a
selection policy, not an observed manager identifier. Checks expose observed
`package_scopes`; unknown or unsupported detection does not grant update access.

## Native package sources (review follow-up)

`package_sources` is optional host configuration: null keeps automatic composition
for `auto` or system-only behavior for explicit legacy providers. An explicit
nonempty array selects `system`, `flatpak_system`, and/or `flatpak_user`; PATCH null
resets this setting. Choices are unique/canonical. This config never owns packages.
Package responses add `sources` with native counts/scopes; host responses add
`package_observations`. Rows add source/display name/scopes. Existing field names,
legacy API omission defaults and `/api/v1` remain.

Composite row `name` references have the form `dnf::curl.x86_64` or
`flatpak_user::app:org.example.Editor:x86_64:stable`. Send these exact references
through the existing single/selected update request. `package_name: source::pacman`
requests a full Pacman source upgrade; an empty-body update covers every enabled
source. Sources/refs are validated against live native data, not a stored catalog.
Pacman individual/selected updates are unsupported; Flatpak targets include their
installation, kind, architecture and branch. Errors never trigger full-update
fallback or automatic retries. Source config changes invalidate queued revisions.

Package rows are transient, while totals and observation times persist. Following
restart, a response may have a positive total and no rows until another check.
Legacy cache bytes are preserved additively but are not routing authority. Missing
native data marks status stale; it does not publish zero. This requires no new
public endpoint, runtime dependency or integration identifier.

Known per-source security counts remain visible as a known minimum even when
another source's classification is unknown. The aggregate security total remains
unknown; this must not hide a positive native security observation from UI alerts.

The authenticated host package response can include a Pacman review after a
successful check. It contains bounded solver candidates and foreign packages
with independent counts. Rows contain only names and versions. Foreign
status does not prove AUR origin. Review details are transient. They do not
change job targeting or authorization.
