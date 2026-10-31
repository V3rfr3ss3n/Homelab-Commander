---
title: ADR-0012 Dashboard and Task Compatibility
status: accepted
date: 2026-10-31
tags: [architecture, backend, ui, persistence, security]
---

# ADR-0012: Dashboard and Task Compatibility

## Context

The backend UI mixes monitoring with creation forms and exposes every task on every
host. A dashboard should provide quick access while host details own administration.
Task assignment needs enforceable prerequisites, not only hidden UI controls.

## Decision

The dependency-free UI has hash routes for Dashboard, Hosts, Tasks and Jobs, with
host details and the existing job deep links. Creation/editing uses accessible
native dialogs. Dashboard aggregates query all stored jobs, separately from bounded
job pages. Seven UTC calendar days include today; completed jobs count on completion
day and active jobs on creation day. Historical failure remains independent of the
latest job. Security notices filter hosts and never imply security-only execution.

Tasks declare distributions, exact VERSION_ID values, programs, packages and sudo
need. A fixed read-only Python probe checks OS identity, executable availability and
installed dpkg packages through the existing SSH/Ansible adapter. It never runs a
user-supplied probe or task command and installs nothing. The primary task executable
(or `/bin/sh` for shell mode) is always checked. Sudo uses the same become context
as execution. Probes have a 30-second deadline with subprocess cancellation cleanup.

Assignments have independent per-host activation in addition to global activation.
New assignments/enabling require a successful current check. An unchecked migrated
assignment can always be disabled or removed. Persisted results expire after 24
hours and are invalidated by prerequisite/execution or connection changes. Queue
admission requires current suitability; workers repeat the probe after obtaining
the host mutation lock and re-read policy before executing. UI and external API use
the same policy. Failed checks expose only safe reasons, never raw SSH output.

An additive SQLite migration preserves all identities/jobs and assigns legacy tasks
to existing hosts with their prior enabled state. Their first check is unknown;
operators must check before running again. New hosts/tasks receive no assignments.
The additive `host_ids` task field contains enabled assignments; the HA adapter
validates UUIDs and entities honor this list. Older backends without it retain their
previous behavior. This deliberately tightens execution permission on the new
backend while retaining `/api/v1`, existing response fields and integration IDs.

Debian and Ubuntu onboarding templates share a versioned JSON import envelope.
Generated commands create/reuse a dedicated account and append the public key
idempotently. Python 3 and administrator execution are prerequisites. Commands do
not install packages or change sudo, firewall or sshd. The operator selects the
existing SSH port and reviews one reachable address from multiple reported choices.
Import fills a form only; saving and importing do not contact a host. Private keys
never leave the backend. Unsupported systems/formats fail visibly.

## Consequences

No production dependency, autonomous maintenance or implicit privilege grant is
introduced. SQLite backup remains necessary before upgrade; schema downgrade is not
supported. Existing task clients may now receive a safe 409 until tasks are checked
and assigned. Native shell mode still requires deployment opt-in. Tests use synthetic
adapters, mocked subprocesses and isolated filesystems, including legacy migration,
API bypass rejection and real-browser Standalone/Ingress flows.

## References

- [Native API](../native-api.md)
- [Backend boundary](0005-native-backend-boundary.md)
- [Security and privacy](../../04-operations/security-and-privacy.md)
- [Direct sidebar entry](0011-direct-backend-sidebar.md)
