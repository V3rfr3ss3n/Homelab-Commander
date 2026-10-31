---
title: Native API
status: active
updated: 2026-10-31
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

Additive read routes under both API prefixes are `/dashboard`, `/jobs/page` and
`/hosts/{host_id}/task-compatibility`. Job pages accept `host_id`, `state`, `offset`
and `limit` (1–100, default 25), returning `items`, `total`, `offset` and `limit`.
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
