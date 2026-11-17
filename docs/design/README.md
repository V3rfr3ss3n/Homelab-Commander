---
title: Operator UI design foundation
status: proposed
updated: 2026-11-16
tags: [design, architecture, ui]
---

# Operator UI design foundation

This is the review foundation for #69 and the Resources integration of #43 in
PR #68 / MR !40. The dark navy/teal style and direct maintenance workflows remain.
[ADR-0025](../02-architecture/adr/0025-operator-ui-and-incremental-modularity.md)
remains **proposed**. Implementation authorization does not accept all future design
choices. The [approved specification](../01-product/future-platform-specification.md),
security contracts and issue acceptance criteria take precedence over illustrations.

- [UI guidelines](ui-guidelines.md): tokens, density, accessibility and English copy.
- [Component contracts](component-contracts.md): lists, selection, filters, actions.
- [Navigation and workflows](navigation-and-workflows.md): current routes and future placement.
- [Architecture inventory](architecture-inventory.md): concrete risks and ownership.
- [Migration plan](migration-plan.md): implemented slice, later slices, rollback/gates.
- [Concept references](concepts/README.md): inspected M1–M6 images and discrepancies.

Implemented in this review branch: Groups is no longer a primary navigation item.
Resources keeps the existing Hosts view and provides **Inventory & groups**, using
one inventory for discovery, membership selection and tags. The existing inventory
is evolved, not copied. Group management is a dialog; group editing and resource
details share a contextual side panel. A pure list-state module and rendering module
sit behind an explicit bridge to the existing transport/auth/feedback functions.

Not implemented: complete five-destination sidebar, shared renderer migration for
all legacy screens, saved views, group execution, new providers, policy/approvals,
automation, localization or a frontend build/framework migration. No release or
Wiki publication is implied by this source review.
