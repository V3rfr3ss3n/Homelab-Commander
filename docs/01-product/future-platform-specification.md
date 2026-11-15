---
title: Homelab Commander — Product & Architecture Specification
status: approved
version: "1.0"
date: 2026-11-15
tags: [product, architecture, roadmap, security]
---

# Homelab Commander — Product & Architecture Specification

**Specification version:** 1.0  
**Date:** 2026-11-15  
**Status:** Owner-approved planning baseline  
**Product stage:** Development; no stable release exists  
**Implementation:** Separate issues and reviewed changes; approval of this specification does not waive release gates.

## 1. Vision and Product Scope

Homelab Commander shall evolve into a unified, secure platform for managing homelab infrastructure, operating systems, services and automation workflows. The user experience should be consistent while respecting provider-specific limitations.

**Principles:** security by design and default denial; modular monolith with explicit boundaries; capability-based operations; existing data and API preservation; broad Linux support without false parity claims; explicit and auditable administrative operations; backend-enforced agent restrictions; professional, tested feature modules; incremental migrations and working software at every stage; architecture before major feature expansion.

## 2. Architectural Foundation

### 2.1 Style and boundaries

Use a modular monolith based on Clean Architecture / Ports and Adapters. Separate domain entities and invariants, application use cases, capability contracts, provider adapters, persistence, API and presentation, identity/authorization and audit. Dependencies point inward toward domain/application contracts. Prefer composition and small interfaces; avoid deep inheritance, duplicated logic, oversized services and cross-feature access to internals.

### 2.2 Shared platform core

The core owns resource identity/registry, relationships, groups/tags, capability definitions/discovery, persistent jobs, scheduling and execution conflicts, authentication, authorization and risk classification, approval requests, audit events, secret management, database migrations and versioned APIs. Core contracts must not depend on Linux distributions, Minecraft variants or external automation providers.

### 2.3 Feature modules and extension strategy

Feature families: **Linux**, **Minecraft**, **Proxmox**, **Semaphore**, **n8n**, **Secure AI Operations**. Each owns models, use cases, adapters, tests and documentation; shared application contracts coordinate cross-feature work. Features ship with the versioned backend initially. Arbitrary runtime-installable third-party plugins are out of scope.

## 3. Resource Model

**Host:** an operating system or managed infrastructure node (e.g., Debian, Arch, Fedora, openSUSE, Alpine, Proxmox). Preserve existing host UUIDs, configuration and SSH identities.

**Managed Service:** independently managed application or service (Minecraft, Semaphore, n8n, database, web app), with stable UUID, service type, provider configuration, capabilities, state, grouping and policy context. A service can optionally reference an existing host; API-managed services need no host association. A host can run multiple services; never invent a duplicate Linux host to represent a service.

**Typed relationships** include Host runs Service, Proxmox Node hosts VM/LXC, VM corresponds to existing Host, Service managed by external platform, and Minecraft Service associated with existing Linux Host. Relate identities without silently merging them or duplicating machines.

## 4. Manual Groups, Dynamic Smart Groups and Tags

Manual groups must support stable IDs, names/descriptions, multi-membership, filtering and navigation. Examples: Proxmox, Production, Development, Minecraft, Media, Network.

Dynamic groups compute membership from validated, bounded deterministic rules using resource type, distribution, tags, parent/infrastructure relationships, capabilities, status or user metadata. Examples: all Arch hosts, Proxmox VMs, Minecraft services, hosts with security updates, resources tagged production.

Tags support search, filtering, categorization and optional policy targeting. The GUI must provide group overview, edit controls, filtering, dynamic-rule editing, preview and clear manual/dynamic distinction.

**Security:** group/tag membership never independently grants privilege. Policies referencing a group resolve and authorize individual effective targets, and revalidate at execution time. Group changes cannot silently extend agent permissions. Exact rule grammar, hierarchy and evaluation bounds remain a feature-level planning gap.

## 5. Resource Discovery and Onboarding

Manual onboarding comes first. Later automated discovery is separately scoped and read-only by default. Users must explicitly accept discovered resources; do not auto-enable mutations. Reconcile identities and avoid duplicate hosts for known VMs or services.

## 6. Capability Framework

Capabilities are explicit, versioned contracts, not assumed uniform functionality. Examples: `system.status.read`, `system.facts.read`, `packages.inventory.read`, `packages.update.single`, `packages.update.selected`, `packages.update.full`, `service.status.read`, `service.lifecycle.restart`, `backup.create`, `backup.restore`, `automation.run`.

Each declares stable ID, contract version, resource support, validated inputs/outputs, prerequisites, authorization, risk class, execution semantics, availability and limitations. Distinguish supported, unsupported, unavailable and policy-blocked. Never present unsupported actions as safely executable. Preserve package-manager-specific differences.

## 7. Jobs, Execution and Recovery

Generalize the persistent job framework without losing existing behavior. Jobs include stable ID; resource type/UUID; optional execution host; operation and immutable validated parameters; calling identity; authorization and approval context; state/timestamps; bounded sanitized logs; failure/review and recovery metadata.

Coordinate conflicting operations across relevant resources (host upgrades/reboots; Minecraft updates/restores/file edits; VM lifecycle). Locks and recovery must be deterministic, deadlock-resistant and tested. Interrupted destructive operations must not blindly replay uncertain remote side effects. Preserve existing host IDs, queued jobs, selections, task references, logs and review states through additive migrations. Keep `/api/v1` compatible unless a separately approved version transition is introduced.

## 8. Linux Distribution Expansion

**Goal:** broad, **verified** distribution coverage; never promise identical features when underlying managers differ.

| Family | Manager | Plan |
| --- | --- | --- |
| Debian / Ubuntu | APT | Preserve and generalize existing implementation |
| Fedora / RHEL / Rocky / AlmaLinux | DNF | Full target |
| openSUSE | Zypper | Full target where reliable |
| Arch Linux | pacman | Official-repository operations |
| Arch community | AUR | Separate restricted capability |
| Alpine Linux | apk | Targeted implementation |
| Gentoo | Portage | Feasibility followed by provider |
| Other Linux | Provider-specific | Expand by verified capability matrix |

Where supported, provide connectivity/system facts, installed/update inventories, reliable security classification, single/selected/full updates, reboot-needed detection and logs. Missing or unreliable security counts are **unknown**, never zero. Each family needs real capability/compatibility evidence and synthetic contract tests.

**Arch:** no unsafe partial-upgrade semantics masquerading as routine individual upgrades; align with rolling-release pacman behavior.

**AUR:** separate from official pacman. First offer foreign-package detection, AUR metadata, provenance, version information, PKGBUILD review and explicit plans. Do not autonomously build/install AUR packages; do not execute unreviewed PKGBUILDs or build as root. Restrict build environments/helpers, check provenance/integrity when possible, and require human admin confirmation. Execution support needs its own security review.

Later Linux operations: CPU/RAM/disk and filesystem health, service status/controlled lifecycle, maintenance mode, backup prerequisites, policies, maintenance windows, change history.

## 9. Minecraft Management

Minecraft is a **Managed Service**, optionally associated with an existing Linux Host; one host may run multiple instances. Initial provider: **Pterodactyl Client API only** with scoped client credential, validated HTTPS/server identity and least-privilege permissions. No Pterodactyl Application API admin credential or direct SSH fallback in the first release. Keep Pterodactyl server identifier distinct from internal service UUID.

Support Paper, Purpur, Fabric, Forge and NeoForge through explicit provider-specific capabilities, not guessed parity.

Initial feature scope: manually connect an existing Pterodactyl server; read identity/state/server software; inventory plugins/mods; identify installed/available versions and sources; compatibility/dependency warnings; single/selected update plans; backups and verification; administrator-approved updates; job results and a protected restoration workflow. Candidate metadata sources include Modrinth and Hangar, subject to licensing/API review. Never replace unknown JARs based only on filename.

Update plans identify files, source/version, dependencies, downtime/restart implications, backup prerequisites and recovery options. No implicit restart. Stage where safely possible; otherwise require a maintenance window/admin approval. Re-check state/versions after changes.

**Backups/restores are MVP requirements.** Prefer supported Pterodactyl backup capabilities, with states requested/running/completed/verified/failed/restore-eligible. A listed backup is not proof of recoverability. Restoration is destructive and always admin-approved; don't claim atomic rollback when unavailable. If the Client API cannot safely implement a feature, mark it unsupported, not silently via SSH. Console/player stats, advanced server version management and configuration are future extensions.

## 10. Proxmox and Infrastructure

First: Proxmox connectivity, node/VM/LXC discovery, status, resource relationships, existing-host linking, backup/snapshot visibility and grouping. Subsequently: controlled VM/LXC lifecycle actions, snapshots, backup orchestration and maintenance, with explicit authorization and no duplicate host creation.

## 11. Semaphore, n8n and Native Automation

**Semaphore:** evolve legacy provider into first-class service integration: health, projects, inventories, templates, task history, status and controlled execution. Preserve migration compatibility.

**n8n:** integrate through documented API/webhooks/events: health, bounded authorized workflow invocation, event exchange, correlation/results and audit. External workflows must not bypass backend policy. Review source-available licensing before embedding or redistribution.

**Native automation:** scheduled/event-triggered operations, reusable workflows, preconditions, conditional steps, maintenance windows, approvals and safe failure/recovery. All entrances invoke the same authorization checks.

## 12. Secure AI Operations

Agents have dedicated restricted technical identities, never UI admin sessions, SSH secrets, unrestricted shell, backend credentials, self-modifiable policies or human-approval rights.

First: authorized read-only hosts/services/capabilities, update/health inventory, sanitized jobs/diagnostics and ability to **propose** protected operations.

Later: narrowly scoped autonomous updates only under **administrator-created, default-deny policies** defining agent, exact resource targets, operation/update categories, exclusions, windows, frequency, scope, state and risk prerequisites. Forbidden autonomous operations include AUR builds, untrusted Minecraft extensions, reboots, backup restores, arbitrary shell, SSH/privilege changes and policy changes.

Agents can create **immutable Approval Requests** with target, action/parameters, reason, risk, observed state, expiry and identity; they cannot approve them. Only an authenticated human administrator GUI can approve; approvals are action/resource bound, time-limited, one-use, auditable and revalidated on execution. Alternative REST routes, Home Assistant actions, MCP skills, custom tasks, Semaphore, n8n and schedules must **never** bypass authorization.

The separate Skill/MCP project consumes documented versioned agent APIs, not backend databases, SSH identities or privileged adapters.

## 13. Security and License Compliance

Mandatory across features: authentication and least privilege, central authorization, strict validation, SSRF/path traversal defense, secrets isolation, safe remote files, download provenance/integrity, rate limits, concurrency/race controls, audit, safe failures and tested backup/recovery.

Before first stable release, perform an explicit Ansible GPL-3.0-or-later and full bundled dependency compliance review, including source-offer/notice requirements as applicable. Commercial/non-commercial status does not itself waive redistribution obligations.

## 14. Quality Requirements

Retain strict typing, Ruff, isolated unit/contract/integration tests, synthetic provider fixtures, migration and browser tests, security regressions, documentation/ADRs and existing independent 95% line/branch coverage thresholds. Do not weaken gates. CI/tests must never execute real managed-host updates/reboots or other destructive infrastructure actions.

## 15. Architecture Migration Plan

Work in reviewable, compatible increments:

1. Specify resource/capability contracts.
2. Add Resource Registry.
3. Add manual groups, dynamic groups and tags.
4. Add typed Host–Service relationships.
5. Generalize job targets and execution conflicts.
6. Establish policy/approval contracts.
7. Extract Linux behavior into feature modules.
8. Preserve and verify current APT provider.
9. Add a second representative package manager.
10. Add a minimal Managed Service.
11. Test existing data/API compatibility.
12. Pass complete release verification.

No big-bang rewrite. Folder rearrangement alone is not architectural proof.

## 16. Prioritized Development Roadmap

### M1 — Architecture & Platform Foundation

Modular architecture, Resource Registry, capabilities, manual/smart groups and tags, Host–Service relationships, generic jobs/conflict handling, policy foundation, existing Linux migration and compatibility.

### M2 — Linux Distribution Expansion

APT preservation; DNF, Zypper, pacman, restricted AUR, Alpine apk; additional Linux feasibility work; capability matrix, shared UI and manager-specific safety.

### M3 — Minecraft Management

Minecraft service, Pterodactyl Client API, optional host association, server/software status, plugin/mod inventory, compatibility, selected update plans, backup verification, administrator-protected restoration and no implicit restarts.

### M4 — Proxmox & Infrastructure

Proxmox connectivity and discovery, nodes/VMs/LXC, relationships, existing host linking, snapshots/backups and controlled lifecycle foundation.

### M5 — Automation & External Services

Semaphore first-class integration, n8n API/events, reusable workflows, scheduling and approval-aware automation.

### M6 — Secure AI Operations

Agent identity and restricted read API, scoped autonomous update policies, approval requests and administrator GUI, audit/abuse prevention, Skill/MCP integration.

**Cross-cutting Platform Reliability:** stable/dev channel separation (#38), Home Assistant App update detection (#39), deferred dependency updates, security/legal review, documentation, migrations and backup testing throughout.

## 17. Architecture Acceptance Criteria

M1 is accepted only when existing IDs/data/SSH identities, APT actions and job history survive; grouping and rule evaluation work; services can exist without host links; relationships avoid duplicate identities; a second package manager proves capability reuse; conflicts and policy bypass tests pass; old HA installations and `/api/v1` still work; clean full release checks and an existing-data upgrade test succeed.

## 18. GitHub Planning & Traceability

After approval, version this English specification under the project documentation and link from roadmap/indexes. Create six phase milestones, classify work with **area**, **type**, **priority** and **security** labels, reuse existing issues, and link relevant specification sections in each issue. Implementation issues must include problem, behavior, scope/non-goals, contracts, security, migration, synthetic tests, acceptance criteria and dependencies. Write ADRs for decisions; keep detailed unanswered choices visible rather than quietly treating them as settled.

## 19. Planning Gaps and Future Work Not Yet Scoped as Issues

Before corresponding implementation, design: supported distribution/version matrix; package-manager transaction semantics; isolated AUR build/review approach; smart-group rule grammar, cost/hierarchy; Pterodactyl version and Client API permissions; metadata-source terms and plugin matching; backup integrity and realistic recovery; Proxmox identity reconciliation; Semaphore legacy migration; n8n event contracts; agent policy persistence and change approval; API/database migration sequencing; performance/retention/observability budgets; threat models for each new trust boundary; operator manuals and real HA acceptance.

These gaps require discovery/ADR/implementation planning and are **not** claims of existing features. Keep them in the backlog/planning register even when not assigned a standalone issue yet.

## 20. Explicit Non-Goals

No arbitrary third-party runtime plugins; no autonomous AI admin; no implicit reboots; no arbitrary agent shell; no unreviewed AUR builds; no blind plugin/mod replacement; no automatic destructive restore; no Pterodactyl Application API or SSH fallback in initial Minecraft release; no silent host-ID replacement/data deletion; no unverified whole-app rewrite; no claims of identical features across Linux distributions.
