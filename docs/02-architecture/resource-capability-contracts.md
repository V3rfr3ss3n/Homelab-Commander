---
title: Resource and capability contracts v1
status: proposed
updated: 2026-11-15
tags: [architecture, contracts, resources, capabilities, migration]
---

# Resource and capability contracts v1

This is the bounded design/typed-contract deliverable for GitHub #41, based on
[specification v1.0 §§2–3, 6, 15, 17](../01-product/future-platform-specification.md).
The types ship as an inert foundation: no registry, discovery endpoint, provider
transport, generic executor or policy engine is installed by this change.
[ADR-0022](adr/0022-resource-and-capability-contracts.md) records the decision.

## Identity and relationships

`ResourceRef(kind, id)` identifies an internal resource with a canonical UUID.
The namespace is global: preserve every existing host UUID exactly; newly created
services/instances receive independent UUIDs. Never derive internal IDs from names,
addresses, credentials, external IDs or provider connection configuration. Renames,
provider reconnection and host association do not change service identity.

`HostResource` is the minimal identity/name view of an existing host. The pure
`project_host` compatibility projection does not rewrite the stored Host model.
`ManagedServiceResource` owns an independent UUID, name, service type, binding and
optional Host reference. Multiple services can share one host, or have no host.
The host field and any `runs_service` relationship must agree when persisted;
#42's registry owns that transaction, not entity constructors.

`ProviderBinding(provider_id, connection_id, external_id)` references backend-only
connection configuration. The UUID of that connection is distinct from both the
internal service UUID and the opaque provider resource identifier. No token, URL,
SSH identity or configuration dictionary belongs in this value. External IDs are
operationally sensitive and omitted from its repr; this is not permission to
export them through diagnostics. Uniqueness is scoped to provider and connection.

| Relationship | Source → target | Meaning |
| --- | --- | --- |
| `runs_service` | Host → Managed Service | Explicit accepted host association |
| `hosts_instance` | Host → VM or Container | Infrastructure placement |
| `corresponds_to_host` | VM or Container → Host | Link existing OS inventory without merging identities |
| `managed_by` | Service, VM or Container → Managed Service | External management platform, represented as a service |

Direction and distinct endpoint IDs are checked locally. Existence, global UUID
uniqueness, duplicate edges, cycles, accepted discovery and deletion behavior are
registry invariants for #42. VM/container kinds and edges reserve neutral identity
semantics; their entities, discovery and reconciliation remain #55 work. No Proxmox
client or duplicate Linux-host creation is introduced.

## Capability definition and state

A `CapabilityKey` is a namespaced ID plus `ContractVersion(major, minor)`, separate
from product version and `/api/v1`. `SchemaRef` identifies a feature-owned validated
input/output DTO schema, not a URL to fetch or code to execute. Within one major,
only backward-compatible optional additions are allowed; removed/required fields
or changed semantics need a new major. Exact major and schema support must be
checked before use; absence of a compatible declaration means unsupported. There
is no automatic version negotiation, downgrade or API-version transition here.

A definition names supported resource kinds, both schemas, an explicit permission,
human-approval requirement, risk class, execution/recovery mode, coded prerequisites
and operator limitations. Inputs/outputs must be immutable feature DTOs. Adapters
validate external data once through typed validators; entities never parse provider
JSON, perform network I/O or resolve secrets.

| State | Meaning | User presentation |
| --- | --- | --- |
| `supported` | Technically implemented and currently ready | May offer an action only after separate authorization |
| `unsupported` | Missing capability, resource kind, version or provider evidence | Explain limitation; never silently emulate |
| `unavailable` | Supported operation cannot currently be used, e.g. connectivity/prerequisite failure | Show safe reason, preserve unknown status |
| `policy_blocked` | Central policy denies or awaits an authorized human approval | Explain restriction; no alternative bypass route |

The latter three states require safe reason codes. Codes are authored by the
adapter/application, never copied from raw remote error text. An assessment is
an ephemeral observation, not an authorization token, cache lease or approval.
An action entrance must revalidate current resource, capability/version, inputs,
prerequisites, identity, effective targets and approval under #46. Group/tag or
provider readiness never grants privilege. Unknown capability/policy is denied.

Read-only capabilities may use direct reads or jobs and read retry. Mutations
require jobs and guarded recovery. Disruptive/destructive capabilities require
human approval and `never_replay`; a normal update's `revalidate` mode is not an
automatic replay instruction. Updates and restart are separate capabilities.
No capability implicitly authorizes a reboot/restart. These declarations do not
change the existing worker's recovery behavior; #44 must handle uncertain remote
side effects before activating generalized mutation execution.

## Provider boundary and examples

`CapabilityProvider[InputT, OutputT]` binds one definition to typed input/output
validators and a read-only `async_assess(ResourceRef)`. It exposes neither execution
nor authorization/approval methods. One adapter can compose multiple bindings.
There is no provider registry, module scanner or runtime plugin loader yet.
The future application owns policy and job creation; feature adapters own remote
protocols and receive backend-resolved credentials only at their infrastructure
boundary. Home Assistant continues using its existing provider protocols.

Linux example: an existing APT Host keeps its UUID and can later expose
`system.status.read` and separately verified `packages.update.single`,
`packages.update.selected` and `packages.update.full`. A permission such as
`packages.update.full`, explicit parameters and limitations about dependencies
belong to the mutation definition; missing security classification stays unknown.
Do not infer Arch or other package-manager parity from the APT example. The
existing `debian_apt` provider value remains unchanged on stored/API Hosts. Future
contract bindings may name `linux.apt` through an explicit compatibility mapping;
renaming or rewriting the legacy field is not part of this contract block.

Pterodactyl example: internal service UUID `00000000-0000-4000-8000-000000000002`,
service type `minecraft`, provider `minecraft.pterodactyl_client`, independent
synthetic connection UUID and external ID `demo_server_01`. It can exist without a
Host and expose `service.status.read` after future provider validation. No SSH
fallback or Application API credential is implied. A disconnected provider is
unavailable; an unsupported backup operation is unsupported; a forbidden restart
is policy-blocked even when its technical prerequisites pass. Neither a backup
listing nor a completed job proves restore eligibility. These are normalized
contract examples, not claims of real Pterodactyl payload/API support.

Executable synthetic examples live in
[contract tests](../../backend/tests/test_resource_contracts.py). They demonstrate
validated immutable DTOs and protocol composition without remote infrastructure.

## Additive migration sequence and compatibility ownership

1. **#41 (this change):** inert types, pure Host projection, design and synthetic
   contracts. No migration, endpoint, API capability list or HA Config Entry change.
2. **#42:** add registry tables transactionally; backfill Host resources with the
   exact `hosts.id` UUID, never regenerate it or rewrite `hosts`. Reject conflicts
   before commit. Create services/bindings/relationships separately, and allow
   nullable host links. Keep tombstoned registry identity for historical jobs;
   deleting a host must not cascade-delete an independently managed service.
3. **#44:** add nullable generic target/context fields beside current job fields.
   Preserve job IDs, action, `host_id`, custom-task references, package selections,
   logs, times, review state and queued/running recovery evidence. Translate
   legacy jobs through a compatibility view; never requeue work as a migration
   side effect or replay an uncertain mutation merely to fill new fields.
4. **#45/#46:** compose verified feature capabilities behind the existing APT and
   authorization boundaries. Add policy enforcement and entrypoint bypass tests
   before enabling generic actions. Preserve deliberate update/reboot confirmation.
5. **Future API exposure:** add resource/capability read endpoints alongside
   `/api/v1/hosts` and existing jobs, never rename compatibility identifiers.
   Preserve `/api/v1/info`'s current string capability list; do not silently replace
   it with definitions. Breaking public changes require an approved versioned API
   transition and HA migration. Existing entity unique IDs, Config Entries and
   `runtime_data` lifecycle remain stable.

Before each persistence step, back up isolated synthetic databases and verify
upgrade, interrupted migration rollback and restart idempotence across supported
schemas. Preserve `/data`, SSH private/public key bytes and known-host state. A
post-upgrade API response must retain legacy shape/IDs and job/review history.
Rollback after writing new state needs an explicitly compatible artifact; do not
claim downgrades are safe merely because migrations are additive.

## Provider contract acceptance required in downstream issues

- Definition identity, schema versions and resource support are stable; invalid
  inputs and malformed/oversized output produce typed safe failures, never raw data.
- Readiness distinguishes unsupported/unavailable/policy-blocked; evidence is not
  reused as authorization and responses match the requested resource/capability.
- Unknown capabilities, incompatible versions and missing approval fail closed.
- No implicit mutation/restart, credential export, privilege fallback or real test
  infrastructure. Exercise HTTP/auth/timeout paths with synthetic adapters.
- Provider-specific update semantics and unknown facts remain explicit; test APT
  preservation and a second provider before claiming M1 acceptance (#45/#47).
- Migration/conflict/policy bypass and HA upgrade tests remain mandatory for their
  implementation issues. This small contract block alone does not satisfy all M1.
