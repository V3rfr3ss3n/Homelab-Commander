---
title: Resource and versioned capability contracts
status: accepted
updated: 2026-11-15
tags: [architecture, contracts, capabilities, compatibility]
---

# ADR-0022: Resource and versioned capability contracts

## Context

Owner-approved specification v1.0 and GitHub #41 require stable shared contracts
before adding the registry, generic jobs, providers and policy engine. Today the
Host/job API and existing HA identifiers must keep working. A folder move or a
second untyped dictionary API would not establish this boundary.

## Decision

Add standard-library-only immutable dataclasses and Protocols under the backend's
contracts package. Resource identity is a globally unique UUID plus kind; Host
identity is the existing Host UUID. A Managed Service is independent, optionally
linked to one Host and separately bound to a backend provider connection. Typed
edges express service placement, VM/container placement/linking and external
management without merging identities. Reserve infrastructure kinds without
implementing their discovery or lifecycle.

Capabilities have independent major/minor versions and named input/output schema
references, resource support, explicit permission/approval, risk, prerequisites,
limitations and execution/recovery semantics. Distinguish supported, unsupported,
unavailable and policy-blocked. Availability is observation, never authority.
Only an application policy boundary may authorize an effective operation; no
provider can grant human approval or trigger execution through these ports.

Use small generic validator/provider protocols and normalized immutable feature DTOs.
These contracts contain no provider JSON parser, network/SSH/SQLite I/O, runtime
plugin loading or execution entrance. Adapters validate untrusted payloads; a pure
compatibility projection reads the existing typed Host without altering it.

## Compatibility and rollout

No production route, API capability list, schema migration, dependency, version or
HA Config Entry/entity identifier changes in #41. Follow the explicit additive
[registry/jobs/policy migration sequence](../resource-capability-contracts.md#additive-migration-sequence-and-compatibility-ownership)
in #42/#44/#45/#46. Preserve every existing Host/job ID, database, package selection,
SSH identity and review state. Never migrate by replaying queued/uncertain actions.
Resource/capability endpoints are future additions beside compatible `/api/v1`.

## Consequences

A Linux identity and a hostless Pterodactyl service share core contracts without
inventing a duplicate Host or transporting credentials. Capabilities can express
provider limitations without false parity. Registry existence/cycle checks and
real authorization/recovery remain downstream work, explicitly not security
features already supplied by these declarations. No UI behavior or installable
provider is advertised by this change. Review of this ADR is part of the MR;
completion of #41 is not completion of the entire M1 acceptance matrix.

## Validation

[Executable contract examples](../../../backend/tests/test_resource_contracts.py)
cover Host/service identity, optional association, immutable DTOs, typed directed
edges, four availability states, versions, safe validators, risk/recovery guards
and compatibility projection against real isolated persistence and existing API.
Tests never contact a provider or managed host. Full quality/release checks,
independent 95% coverage thresholds and ordinary review remain required.
