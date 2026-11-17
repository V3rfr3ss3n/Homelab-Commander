---
title: Future platform GitHub planning register
status: active
updated: 2026-11-16
tags: [planning, github, milestones, issues, labels]
---

# Future platform GitHub planning register

This register tracks implementation issues derived from the owner-approved [Product & Architecture Specification v1.0](../01-product/future-platform-specification.md). It distinguishes approved direction from implementation status. No major future feature described here is considered shipped.

## GitHub milestones (ordered)

All six milestones below exist and the feature issues carry their assigned phase.
The existing area/type/priority labels are also configured (verified 2026-11-15).
The Development Roadmap project tracks status and label-derived priority; #41 and
#42/#61 and #62/#63 are Done, while #43 is In Progress. These planning states do not claim that M1
features have shipped.

| Order | GitHub milestone title | Purpose | Issues |
| --- | --- | --- | --- |
| 1 | M1 — Architecture & Platform Foundation | Resource registry, groups, service relationships, capabilities, jobs, policy | [#41](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/41)–[#46](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/46) |
| 2 | M2 — Linux Distribution Expansion | Broad verified package-manager support, Arch/pacman, restricted AUR | [#47](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/47)–[#51](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/51) |
| 3 | M3 — Minecraft Management | Pterodactyl Client API, extensions, backups and protected restore | [#52](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/52)–[#54](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/54) |
| 4 | M4 — Proxmox & Infrastructure | Nodes, VM/LXC identity/discovery and safe lifecycle planning | [#55](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/55) |
| 5 | M5 — Automation & External Services | Semaphore, n8n, events/workflows | [#56](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/56)–[#57](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/57) |
| 6 | M6 — Secure AI Operations | Agent identity, read API, restricted updates and human approval | [#58](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/58)–[#59](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/59) |


## Cross-milestone operator UI and code-quality direction (proposed ADR-0025)

[ADR-0025](../02-architecture/adr/0025-operator-ui-and-incremental-modularity.md) is a **proposed** operator UX/modularity design on PR #68; planning agreement is not approval to implement all pictured capabilities. Track the M1/cross-cutting foundation in [#69](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/69) and defer complete localization infrastructure to [#70](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/70).

**Shared UI direction:** English-only until another locale achieves audited 100% user-facing-string coverage, locale settings and browser/CI validation. Compact sidebar (Overview, Resources, Operations, Activity, Settings); balanced density; existing unified resource/list rows with sort, selection and top-right filter/selection context. Reuse the existing right-hand contextual operation actions, never add a duplicated command toolbar. Groups/Tags are searchable/filterable facets and persistent editors, not extra main navigation destinations; Minecraft is a Managed Service under Resources > Services. Proxmox should start as identity/discovery and useful direct links rather than reproducing its entire console.

**Daily operation:** preserve direct host actions such as check updates/start update. Package-by-package review is optional by default where safely supported, while required provider/policy/security checks remain mandatory; Arch partial upgrades and unreviewed AUR execution are never normalized. No automatic/scheduled update feature is authorized by this note: any future configuration must be explicitly reviewed against scheduler and policy contracts. Guided onboarding and tips are optional, dismissible first-run aids, not permanent dashboards. Advanced flows may open focused dialogs; avoid compulsory timelines/wizards for routine actions.

**Milestone-specific UI placement:**

| Milestone | Operator-facing result | Limits and reusable patterns |
| --- | --- | --- |
| M1 (#41–46) | Compact shell groundwork, Hosts/Resources + Groups/Tags discovery, existing Operations and Activity context | #69 defines preparation; PR #68 group previews remain non-executing; #44/#46 gate group targeting and approval |
| M2 (#47–51) | The same host list gains distro/package capability and optional detailed review | Keep quick update, provider-aware restrictions, mandatory AUR review before any separately approved execution; no automatic updates implied |
| M3 (#52–54) | Minecraft **within Services**, linked to existing hosts; extensions, backup and protected restore details in focused views | Reuse lists/detail panels, separate destructive confirmations; preserve Pterodactyl Client API limits |
| M4 (#55) | Proxmox-linked resources/relationships and external links | Focus discovery and identity reconciliation; do not rebuild Proxmox console without explicit use case or approval |
| M5 (#56–57) | Semaphore/n8n integrations and workflows under Operations/Integrations | Detailed information architecture provisional until real policies, triggers and provider contracts are designed |
| M6 (#58–59) | Agent access, read-only discovery and separately governed approvals | UX provisional; backend default deny and nondelegable human authorization always take precedence |

**Visual references (examples only, not acceptance criteria).** Milestone mockups can be appended **at the bottom of each milestone's planning material** once corrected examples are versioned/uploaded. Required caption: _"UI Concept – Non-binding visual example. This image illustrates one possible layout, may show unimplemented features, and does not amend the approved specification, issue acceptance criteria, provider contracts or authorization rules."_ Do not add unverified local image paths or treat a rendered button as an implementation requirement. M5/M6 illustrations remain especially provisional.

**Code-quality scope:** audit frontend/backend/HA coupling; choose narrow vertical feature slices and shared presentation contracts rather than a big-bang rewrite. Preserve FastAPI/SQLite modular-monolith architecture, `/api/v1`, identities, migration guarantees, authenticated API/Ingress, sanitized errors, release-check, and synthetic no-host-action tests.

## Cross-cutting platform reliability (not a seventh sequential feature milestone)

- [#38](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/38) — Stable/development release channels.
- [#39](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/39) — HA Backend App version discovery and reliable upgrades.
- [#60](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/60) — Ansible GPL and bundled-dependency compliance review.
- [#61](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/61) — Deferred Dependabot changes after dev.5.
- [#62](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/62) — Dashboard history and failed-outcome visibility.
- [#63](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/63) — Error-handling audit and safe actionable diagnostics.
- #62/#63 were owner-approved and merged in the stabilization block. #41 was
  separately approved and merged in !38. #42/#61 were approved and merged in !39; #43 implements groups/tags on a separate
  review branch; provider/policy execution
  remains downstream. No development release is implied.
- This work remains active across all six milestones. #38 and #39 are existing issues, not duplicated.

## Existing label taxonomy

The built-in `enhancement` label and the specific labels below exist and were
assigned in the approved planning setup. Keep their meaning stable when adding
new work.

| Dimension | Labels |
| --- | --- |
| Area | `area:architecture`, `area:linux`, `area:minecraft`, `area:proxmox`, `area:semaphore`, `area:automation`, `area:ai`, `area:security`, `area:release`, `area:documentation` |
| Work type | `type:feature`, `type:refactor`, `type:research`, `type:security`, `type:test`, `type:maintenance` |
| Priority | `priority:p0`, `priority:p1`, `priority:p2` |
| Planning | `status:needs-design`, `status:blocked` |

**Policy:** labels describe work; they do not replace threat models, versioned specification links, independent security review or acceptance criteria. All M1 tasks are prerequisites for their downstream M2–M6 consumers even if development overlaps.

## First implementation sequence

1. Review architecture/contract design [#41](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/41).
2. Establish Resource Registry and migrations [#42](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/42).
3. Design/implement group rules [#43](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/43), job targets [#44](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/44), and policy/approval boundaries [#46](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/46).
4. Extract APT and prove a second provider [#45](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/45).
5. Establish distro capability test matrix [#47](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/47), then the implementation issues. Begin Minecraft [#52](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/52) only after relevant service/policy dependencies are met.

All items require the existing full release-check and public-safe documentation before merge. No CI tests may run real host operations.

## Unresolved planning gaps — not yet standalone issues

The canonical specification's [§19](../01-product/future-platform-specification.md#19-planning-gaps-and-future-work-not-yet-scoped-as-issues) remains the formal backlog of unresolved decisions. In particular:

- Exact tested distro versions, security-feed parity, package transaction semantics and rollback claims.
- Portage feasibility and further distro/embedded-system targets.
- AUR sandbox threat model and review UX before optional build execution.
- Smart-group rule language, precedence, evaluation limits, nested groups and policy target-snapshot behavior.
- Pterodactyl version/API permission matrix, Client API capabilities for safe file and backup workflows.
- Minecraft source eligibility (Modrinth/Hangar), matching reliability, backup integrity and restore drills.
- Proxmox resource identity reconciliation and later lifecycle safeguards.
- Semaphore migration compatibility and n8n webhooks/event authentication.
- AI policy authoring, immutable approvals, replay protections, nondelegable admin identity and MCP interoperability.
- Performance, retention, telemetry, localization and operator documentation across features.
- Release channel, Supervisor Store behavior and dependency/legal compliance before stable distribution.

**When converting a gap into an issue:** first check whether an existing issue covers it; cite the specification section, describe security and migration risk, and add measurable acceptance tests. Do not automatically create speculative duplicate issues.

## Rollout and release discipline

The planning specification is approved, but source changes must proceed through an ordinary reviewed pull request, and **future implementation is not implicitly authorized by a planning issue**. The milestone sequence is priority, not a promise of calendar dates. Maintain existing HA compatibility and the stable/prerelease separation work.

## PR #68 UI foundation review

#43 and the bounded #69 foundation now share the existing review branch. See the
[design index](../design/README.md) for implemented Resources integration and the
[concept index](../design/concepts/README.md) for all six non-binding references.
Full shell migration, saved views and #70 localization remain later work; ADR-0025
is still proposed. No milestone description or future feature scope is rewritten.
