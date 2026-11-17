---
title: Persistent resource registry and incremental module boundaries
status: accepted
updated: 2026-11-15
tags: [architecture, registry, migration, dependencies]
---

# ADR-0023: Persistent registry and incremental module boundaries

## Context and decision

After owner approval/merge of #41, #42 installs the registry behind those contracts.
The owner also requested a cleaner folder structure and integration of deferred
Dependabot #32/#33/#35/#36 (#61). Keep the modular monolith and existing FastAPI/
SQLite foundation; no replacement framework, ORM or runtime plugin loader is needed.

The new `resources` slice owns immutable registry values, an application service and
store Protocol, SQLite adapter, validated HTTP schemas and small API router. Domain/
application code does not import HTTP or SQLite. The existing composition root only
wires the service and reuses its existing authentication/CSRF dependencies.
`persistence` owns SQLite lifecycle and ordered migrations; `database.py` remains a
thin compatibility export for old consumers and historical migration fixtures.
Existing HostRepository remains the legacy host facade. Other feature extraction
is incremental (#45), not a repository-wide move for its own sake.

## Persistence and consistency

Migration 11 adds resources, service records and directed relationships. Backfill
copies every Host UUID unchanged. Transactional triggers mirror future host creation/
rename and tombstone removal; host deletion keeps current job/task behavior while
unlinking, never deleting, independent services. Active bindings are unique per
provider/connection/external ID. Resource identities are never reused after removal.
Explicit instance reconciliation reuses a matching external identity and permits
one existing OS Host per VM/container and one VM/container per OS Host. It does not
invent a second Linux Host, contact Proxmox or infer identity from a name/address.

Service host fields and runs-service edges change in one transaction. All edge
writes validate active endpoint kinds and reject cycles. Explicit service relinking
can replace its host; generic conflicting edge creation cannot do that silently.
Deleting non-host metadata leaves tombstones and removes incident live edges.
Hosts are deleted only through the established Host facade.

The migration runner holds a process-level schema lock (off the event loop) through
first WAL initialization, and uses BEGIN IMMEDIATE plus an in-lock version check.
Execute complete SQLite statements, including triggers, without executescript's
implicit commits so schema, backfill and version marker roll back together. Separate
Database objects cannot race startup. The supported backend still uses one process;
this change does not promise distributed workers or cross-process execution locks.

## API and security

Add bounded admin inventory endpoints beside existing `/api/v1/hosts` and jobs.
External API uses existing Bearer auth; UI routes require existing session/Ingress
and writes require CSRF. These operations change inventory metadata only. Provider
bindings contain opaque references, never credentials or endpoints, and are not
execution permissions or connectivity evidence. No provider transport, generic job
execution, automatic discovery or policy engine is enabled. Full policy work remains
#46; groups and generic job targets remain #43/#44. Legacy identifiers, Info capability
format, HA entries, SSH files, job selections, logs and review state stay compatible.

## Dependency and framework maintenance

Integrate the exact deferred bot proposals into one lockfile: FastAPI 0.162.4,
ansible-core 2.22.0, Hatchling 1.33.0, frontend 20261028.5, HTTPX2 2.16.0, Mypy 2.4.1,
Playwright 1.65.0 and Ruff 0.17.4. Core HA stays pinned at 2026.10.4; the updated test
frontend pairing is verified by the complete HA/browser suite, not described as a
same-release pair. Pin the reviewed Builder 2026.09.0/setup-uv 10.3.3 action commits.
Deployment tests require consistent immutable builder SHAs rather than duplicating
one historical SHA. Ruff's AsyncGenerator annotations and HTTPX2 cookie-jar tests
are updated without changing product authentication semantics.

FastAPI adds the transitive Apache-2.0 `opentelemetry-api` package. No exporter is
added: tracing, metrics, logs, operation spans and automatic configuration are all
explicitly disabled, including environment-based exporter setup. Safe existing
failure diagnostics remain the only application logging boundary. Runtime pins
and this policy must be rechecked on later FastAPI upgrades. See
[FastAPI release notes](https://fastapi.tiangolo.com/release-notes/) and
[Ansible 2.22 porting guide](https://docs.ansible.com/projects/ansible-core/2.22/porting_guides/porting_guide_core_2.22.html).
The Ansible callback keeps its bounded structured envelope and independently suppresses
no_log payloads before warning/serialization, with synthetic leak tests. No implicit
SSH/host action or new runtime privilege is introduced by the dependency updates.

## Validation and rollout

Synthetic tests cover dev.5 schema-10 upgrade/restart, queued/running/reviewed rows,
identity file bytes, failed backfill rollback, concurrent initializers, service
lifecycle, host deletion, binding/VM identity conflicts, cycles, API auth/CSRF,
malformed input and zero executor calls. Existing complete gates, >=95% independent
line/branch coverage, container validation and review remain mandatory. Back up
SQLite and SSH identity together before a real upgrade. Downgrades after writing new
registry state are not promised; restore a compatible backup/artifact deliberately.
