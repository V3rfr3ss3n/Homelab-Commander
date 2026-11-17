---
title: Linux package feature and provider boundary
status: proposed
updated: 2026-11-17
tags: [architecture, linux, providers, compatibility]
---

# ADR-0028: Linux package feature and provider boundary

## Context and decision

After the owner-approved policy foundation (#46, !42 / PR #72), #45 extracts
existing APT behavior without changing `/api/v1`, Host identity or Home Assistant.
Keep the modular monolith, FastAPI, SQLite and pinned dependencies. There is no
framework replacement, schema migration, new production dependency or privilege.

`linux/domain.py` owns immutable package scope, normalized status and system facts.
The application service depends on provider-resolution and normalized transport
Protocols, without Ansible JSON, HTTP or SQLite. A static composition registers
APT only. The feature's Ansible adapter normalizes callback payloads and invokes
fixed provider module/argv specifications through the existing isolated runner.
The APT adapter owns parsing, commands and lock-error classification. Common
Python/sudo failures remain transport concerns. The existing Debian custom-task
probe moves unchanged into the feature; this does not generalize task prerequisites
to other distributions.

The compatibility executor delegates package checks/updates to that service. Shared
execution results move to `execution/results.py`; old `automation` and
`package_providers` imports remain available. Production code can inject a reviewed
static provider registry; no runtime plugin, import path or executable is selected
from an API request. Unsupported providers fail before transport; unsupported
single/selected scopes fail before command creation, never widen to a full update.
The transport retains fixed setup/list/stat conventions; a provider requiring
other transports needs its own reviewed typed adapter.

## Capabilities and execution

`PackageCapability` implements the shared versioned provider assessment/validation
port for `linux.check_updates` and `linux.update`. Its immutable request distinguishes
status from explicit full/single/selected mutation; provider scope support is checked
by the validator. Results are normalized immutable status, never arbitrary JSON.
Checks retain job-based execution; updates declare mutating risk and never-replay
recovery. Assessment performs no I/O, supplies no authority and reports readiness
unknown as unavailable, rather than promising that an unprobed Host is ready.
Non-Host targets are unsupported. Legacy Info capability strings do not change.
These bindings are internal contract definitions, not new public execution routes.

The existing API, policy, immutable job scope, canonical Host locks, recovery and
worker remain the execution path. Technical provider support never bypasses those
checks or grants permissions. No automatic retries of mutations or implicit reboots.

## Compatibility and provider proof

Keep the stored `debian_apt` key; `linux.apt` is namespaced contract metadata.
APT cache refresh, full dist upgrade and installed-package `state=latest
only_upgrade=true` semantics remain. Each update measures a fresh status without a
second cache refresh. Total/security counts remain independent of the bounded
50-row detail list; malformed external status is a safe classified failure.
All Host, resource, job and task IDs, stored state, SSH identities, review and HA
configuration remain untouched.

An independent **test-only synthetic provider**, with its own parser and command
vocabulary, exercises those same contracts and the real API/policy/worker/persistence
path. It supports only full updates; selected scopes demonstrably fail without I/O.
It is not an APT subclass, is never registered in production and makes no claim
of working DNF/Zypper/pacman/apk support. M2 must supply real provider adapters,
platform-specific safety and compatibility evidence. This proves an extension seam;
it does not by itself satisfy M1's eventual second-real-package-manager acceptance.

## Validation, maintenance and limits

Retain the APT parser, status, scope, callback, lock, standalone/Ingress browser,
HA, persistence and upgrade regressions. Add tests for unknown registrations,
invalid scopes/status, bounded counts, safe errors, versioned capabilities and the
synthetic provider through existing jobs. Run the complete release gate before
handoff. No real managed hosts, updates, reboots or production data are used.
No new external Wiki publication or release is part of this decision. The reviewed
source pages are handed off with the MR for subsequent authorized synchronization.
