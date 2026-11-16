---
title: Operator workspace, reusable lists and incremental modularity
status: proposed
updated: 2026-11-16
tags: [architecture, frontend, ux, accessibility, modularity, localization]
---

# ADR-0025: Operator workspace, reusable lists and incremental modularity

## Context

The owner-approved [platform specification v1.0](../../01-product/future-platform-specification.md) plans M1–M6. The existing management UI is English-only, uses Dashboard/Hosts/Tasks/Jobs navigation, and already has important shared list, selection/filter-context, direct host actions, history, and safe confirmation behavior. PR [#68](https://github.com/V3rfr3ss3n/Homelab-Commander/pull/68) adds metadata-only Groups/Tags, but a new top-level Groups tab and a largely separate workspace would not scale well to M2–M6. The existing dark navy/teal aesthetic is retained.

Backend ADR-[0022](0022-resource-and-capability-contracts.md), [0023](0023-resource-registry-and-module-boundaries.md), and proposed [0024](0024-bounded-resource-groups.md) establish resource identities, capability contracts, modular monolith boundaries, and non-executing group semantics. The frontend currently packages HTML/CSS/JS with FastAPI, and must work standalone and under Home Assistant Ingress. This proposal is a cross-layer design agreement, **not** permission to implement, merge, release, or expand feature scope.

## Options

1. Keep a top-level tab and bespoke view per feature: low initial cost, growing inconsistency and navigation sprawl.
2. Rewrite the whole frontend/backend or adopt a framework immediately: high migration/security/packaging cost without proven benefit.
3. **Preferred:** retain existing behavior and technology boundaries, establish shared UI contracts, evolve a compact shell, and migrate vertical slices incrementally.

## Decision (proposed)

### Navigation and information architecture

- Keep the existing visual language. Use a **compact, text-labeled left sidebar** and balanced information density; main workspaces are **Overview**, **Resources**, **Operations**, **Activity**, and **Settings**. These are *conceptual destinations*, not a command to immediately rename routes or add backend capabilities.
- **Resources** is the discover/find/filter/select workspace for Hosts and Managed Services, with group/tag facets integrated into the existing shared resource list, sorting, pagination and selection model. Groups and Tags are primarily discovery/organization aids. Maintain PR #68's valuable manual/smart group editor, preview, persistence, multi-membership and tag semantics; do not force a separate top-level Groups tab.
- **Minecraft belongs under Services** (a Managed Service, optionally linked to an existing Host), not a permanently separate top-level navigation item. Other future providers are likewise contextual to resources and capabilities.
- **Proxmox is integration-first**, chiefly discover/reconcile resource identities and show useful links to the Proxmox UI. Do not clone Proxmox administration merely to fill a screen. The canonical M4 issue governs supported discovery and safe future controls; any deeper integration or agent/MCP interoperability needs explicit justification and a separately reviewed contract.
- **Operations** retains the existing quick host/resource list as the default, with the established **right-hand contextual action area**. Do not place a duplicate action toolbar above the list, or force routine work into a permanent timeline/wizard. Open a focused dialog or separate detail view for advanced review, package selection, risky changes, or a meaningful multi-step procedure. **Activity** owns job history, audits and optional timeline views; do not delete existing valuable job visualizations.
- Preserve the **top-right filter/selection context**: show the exact current selection/filter scope, allow clearing it, and keep its behavior consistent as resources, services and jobs grow. List headers themselves remain sortable/selectable. Avoid creating a second list/control row where existing unified controls suffice.
- No permanently displayed “What would you like to do?”, tips, or onboarding banners in daily operations. Show guided onboarding contextually on fresh install or in an optional Help/Overview entry point, dismissibly; once completed it must not reappear by default.
- Display the minimum context needed for the current task; progressive disclosure via selection, details, contextual menus and focused dialogs. The interface remains understandable to non-specialists, with plain-English labels, explicit outcomes and visible risks.

### Update workflows and security boundaries

- Preserve the current **check updates → start update** operator path. A full package-by-package review is **optional by default**, not imposed on every update. Where supported, offer optional package inspection/selection in an appropriate dialog; provider-specific risks, policy decisions and security-required reviews may override this. In particular, never offer unsafe Arch/pacman partial upgrades, and AUR execution requires its own reviewed safeguards (#49/#50).
- Scheduled/automatic safe updates may be considered only within the approved product spec and future policy/scheduling contracts; **this ADR does not authorize a new autonomous update path or a default-on automation setting**. Explicit operator configuration, capability support, backend policy authorization, risk classification, logs, recovery behavior, and refusal of unsupported operations are prerequisites.
- Group or tag membership is never an authorization grant. PR #68 group previews cannot execute actions. Group-expanded targets and action conflicts/approval require #44/#46. The UI must not offer functional group bulk updates until backend scope snapshots, per-target policy and revalidation exist.
- Never use UI visibility as authorization. Reboot, restore, shell, credentials, risky package changes and protected operations remain guarded by approved backend contracts. Failure, stale, unavailable, unsupported, policy-blocked and unknown statuses must not be represented as success.

### Reusable components, localization and code structure

- Define semantic design tokens for surfaces, typography, spacing, border/radii, focus, risk/status, breakpoints and accessible contrast. Prefer small reusable components for AppShell, common resource/data list, sort header, selection/filter context, pager, status, forms, dialogs/confirmations, feedback and contextual detail/action panels.
- **One component, multiple contexts; no duplicated controls.** Shared table foundations own repeatable interaction mechanics, while feature-specific typed columns and actions remain extensible. Existing lists/selection should be **evolved**, not thrown away and redrawn as a second list.
- Keep presentation independent of HTTP transport and business policy. Feature code owns state/use cases, an API client owns request/error behavior, the view owns rendering/accessibility; clean up on navigation/logout and guard against late asynchronous responses.
- **English is the sole shipped UI language until a separately scoped localization feature is completed.** Do not add German copy, language selectors or partial translations during this preparatory effort. A future i18n issue must establish locale selection/persistence, extracted message catalogs, pluralization, dates/numbers, error and accessibility text, complete-coverage validation for *every* supported language, fallback rules and browser tests; launch another locale only when its UI strings are complete.
- Favor incremental dependency-free ES modules; framework/build-chain adoption requires independent review and demonstrated benefit. Maintain CSP, static asset paths, authentication, CSRF, HA panel/Ingress compatibility, keyboard operation, focus, contrast and responsive layouts. WCAG 2.2 AA is a testing target, not an unverified compliance claim.

### Backend and operational architecture

- Preserve FastAPI + SQLite modular monolith, Ports & Adapters and typed contracts. New features keep domain/application, repository/provider, transport and UI responsibilities separate. Application services define invariants; composition root wires dependencies; avoid growing central `app.py` and `ui.js` with more feature-specific logic.
- Audit existing Host/job/backend/HA boundaries and coupling **before** proposing extraction. Do not perform a big-bang refactor. Retain `/api/v1`, Host/job/resource UUIDs, SSH identity, persistence/history, current package-update and review semantics, release channels, diagnostics (ADR-0021), HA registration, UI session and Ingress trust. No migration solely for visual redesign.
- Keep tests synthetic/isolated: no real SSH/provider execution or managed-host mutations, full existing release-check, strict types/coverage/security/privacy, browser regression for standalone and nested Ingress, and useful UX/accessibility assertions.

### Delivery and examples

1. **Preparation only (candidate for a narrowly scoped follow-up to PR #68):** current UI/backend/HA inventory, English navigation/route map, existing-list interaction map, design token proposal, component ownership/contracts, explicit future feature placement and regression/migration strategy. Implementation of shared shell or bulk code moves is not automatically included.
2. Subsequent independently reviewed slices: shell/routing, integration of Groups/Tags into existing resource lists, reusable resource/operations lists and action context, then other feature migrations. Keep existing behavior and roll back by slice if needed.
3. Future M1–M6 extensions use these contracts. M5 automation UI and M6 AI/approval UX are **provisional**, to be designed closer to the real policy/provider contracts; do not infer extra permissions, scheduling behavior or runtime AI actions from mockups.
4. **Reference mockups are non-binding, example-only visual illustrations**, placed at the *end* of milestone planning sections, explicitly subordinate to the specification, issues, ADRs, API and threat models. Screens may depict unimplemented capabilities; no screenshot is an acceptance criterion or authorization to ship the depicted buttons. Correct duplicate controls/list and English text before attaching approved image assets.

## Consequences

Benefits: coherent growing navigation, familiar quick actions and selection mechanics, reduced duplication, non-technical usability, feasible stepwise migration and explicit preservation of backend safety. Costs: temporary legacy/new UI coexistence, contract and screenshot maintenance, and unresolved detailed IA for M5/M6. No framework, ORM, automatic updates, localization rollout, Proxmox full management suite or AI executor is decided here.

## Acceptance criteria for the preparatory step

- Inventory and map all current views, list controls, selection/filter context, flows, risky actions, translations/copy and backend/HA delivery constraints.
- Document one shared resource/data-list interaction standard with sortable headers, selection, pagination, contextual right-panel actions and no duplicate action strip.
- Provide tested/planned navigation and responsive layouts including standalone and HA Ingress; define semantic tokens, component contracts and English-only copy policy.
- Document update path: quick update preserved, review optional except provider/policy-required cases; automatic updates are *not* enabled by this ADR.
- Document modular backend boundaries and concrete risks before selecting any legacy refactor.
- Link M1–M6 placement and non-binding mockup policy; define incremental PR and test gates; no unauthorized functionality or changes to existing feature scope.

## References

- [Product & Architecture Specification v1.0](../../01-product/future-platform-specification.md)
- [Planning register](../../00-project/future-platform-issue-plan.md)
- [ADR-0021](0021-safe-failure-diagnostics-and-history.md), [ADR-0022](0022-resource-and-capability-contracts.md), [ADR-0023](0023-resource-registry-and-module-boundaries.md), [ADR-0024](0024-bounded-resource-groups.md)
- [PR #68](https://github.com/V3rfr3ss3n/Homelab-Commander/pull/68), [#43](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/43), [#44](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/44), [#46](https://github.com/V3rfr3ss3n/Homelab-Commander/issues/46)
