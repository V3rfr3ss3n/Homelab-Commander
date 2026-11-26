---
title: Qualified Linux observations and compatibility evidence
status: proposed
updated: 2026-11-18
tags: [architecture, linux, capabilities, compatibility, testing]
---

# ADR-0029: Qualified Linux observations and compatibility matrix

## Context and decision

The owner accepted #45 (!43 / PR #73, merged at `9ea2130`). #47 is the next
roadmap block: define cross-manager semantics and reusable synthetic contracts
before implementing DNF/Zypper in #48. The legacy `PackageStatus` requires numeric
security counts and boolean reboot state. Copying that assumption to other managers
would erase missing evidence. Changing its existing API/SQLite/HA fields now would
prematurely expand a design/test issue into a multi-component provider rollout.

Add immutable internal `ObservedValue`, `PackageEvidence` and `InventoryEvidence`
under the Linux feature. Known numeric/boolean observations carry strict values;
unknown, unavailable and unsupported carry null plus a safe static reason code.
Keep these data-observation states separate from capability readiness and policy.
A successful inventory total is independently bounded against its partial detail
list; collection failure is an error, never a successful empty snapshot. Fields
contain normalized facts, no I/O, provider JSON, credentials or exception text.

Preserve `PackageStatus`, public capability schemas, `/api/v1`, SQLite, HA entries,
identities, SSH data and the UI. The new observation models are internal preparatory
contracts, not a public payload-version bump or a runtime provider activation.
A lossless legacy bridge is available for tests/future composition; it refuses any
missing signal instead of turning null into zero/false. Legacy APT origin/file
heuristics retain their existing meaning, not stronger provenance or coverage.
Future non-APT activation must carry missing-evidence metadata through API/UI/HA,
or fail closed where the old contract cannot express an observation. Unknown must
never be presented as a healthy security/reboot result.

## Matrix and test composition

The [capability matrix](../linux-provider-matrix.md) separates implementation state,
candidate distro/version baselines, actual fixture evidence and unresolved platform
checks. Machine-readable fixture metadata is test-owned, inert and not a runtime
catalog. APT is the sole production registration. Other families have explicit
missing-evidence scenarios and no supported execution claim; pacman partial
updates and AUR execution are excluded from routine update workflows.

The reusable injected-runner harness applies the same before/after count/list,
full/single/selected and no-implicit-reboot assertions to APT and the independent
synthetic provider. Family fixtures exercise normalized signal semantics only;
they do not manufacture native parser/execution success for absent adapters.
#48/#49/#51 must add native synthetic output/result-code cases, actual manager
version/architecture evidence and approved integration before claiming support.
M1's second-real-package-manager and real-platform acceptance remain open.

## Safety, maintenance and consequences

No dependency, framework, migration, privilege or automatic action is added. Tests
have no managed-host access, external fetches, real SSH/Ansible commands or sleeps.
Existing policy, job scope/conflicts and no-replay recovery remain authoritative.
The suite cannot certify an operating system, advisory completeness, transaction
rollback or exactly-once remote effects. Primary upstream sources inform the matrix
with explicit verification dates; their semantics must be rechecked when an adapter
is implemented. Complete release/coverage/CI gates remain required.

Maintaining a separate preparatory contract has a temporary cost: future provider
activation must explicitly implement its wire/storage transition. That cost is
preferable to silently coercing missing evidence or breaking legacy consumers in
this design/test block. No new provider/distribution is selectable in the GUI.
