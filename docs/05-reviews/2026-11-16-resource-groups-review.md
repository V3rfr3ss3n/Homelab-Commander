---
title: Resource groups and tags review
status: review
updated: 2026-11-16
tags: [review, groups, security, migration]
---

# Resource groups and tags (#43)

Owner approval of the registry block was followed by merge !39; both mirrors' main
contain `f3bfd64bde349d98753ed072d9a9ff9aec5d1676`. GitHub #66 is closed; the
actual commit ancestry, not that UI label, proves inclusion. #42/#61 are complete.
Dependabot #36 moved to a newer 0.162.5 proposal during cleanup. Its accidental
closure was reversed with explicit owner approval, restoring its exact source
commit through the existing mirror; no new dependency is merged here.

## Scope and limits

Manual and smart groups, stable UUIDs, tags, bounded evaluation, read-only previews,
resource filters and a dedicated Groups editor. Schema 12 is additive. Pure rules,
use cases/port, snapshot adapter, HTTP DTO/router and browser workspace are separate.
There is no group execution endpoint or permission inheritance. Rule grammar,
threat model, bounds and future policy requirements are in
[ADR-0024](../02-architecture/adr/0024-bounded-resource-groups.md).

Capabilities without explicit supported evidence do not match. No capability
producer is installed in the current inventory adapter. Services do not inherit
Host health, and persisted Host status is not fresh connectivity evidence. Unknowns
are never guessed. Preview can list the first 100 matches and the complete count;
API pagination inspects the remainder. Over-budget inventories return a safe error,
not partial targets. Concurrent administrator edits use atomic last-write-wins.

## Owner local acceptance

Restart an older preview, then run `uv run python -m homelab_backend.preview` and
open `http://127.0.0.1:8100`. All inventory/actions are synthetic/disposable.

- [ ] Existing Dashboard, Hosts, Tasks, Jobs and graph work as before.
- [ ] Groups → New group → select a Demo Host → Preview → Save; edit retains ID.
- [ ] Clear selection permits a fresh manual selection, including after deletions.
- [ ] Save `production` as a resource tag; create a smart group using `tag` =
  `production`. Preview does not create/save the group; Save persists its definition.
- [ ] Resource name/type/tag filters and both page controls work. Manual selection
  remains across pages; group search and manual/smart distinction remain clear.
- [ ] Edit/rename/reload retains group definition/tags. Delete group requires
  confirmation and does not delete inventory. Invalid rules produce visible errors.
- [ ] A failed preview shows unavailable, never an old or empty selection. Retry
  recovers. Disconnect clears resource data and drafts; late previews stay cleared.

## Automated evidence

Tests use only temporary databases, fake executors, immutable synthetic snapshots
and loopback browsers. Coverage includes positive/unknown predicates, invalid and
nested rules, multi-membership and Host/service links, bounds, restart, additive
migration rollback, auth/CSRF, preview non-mutation and zero executor calls. The
schema-10 fixture now explicitly names its historical boundary, retaining the
original registry backfill/rollback assertions when schema 12 is appended.

## Executed checks

- `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check`: passed on the complete
  grouping implementation: 488 tests, 98.74% independent line coverage, 96.66%
  branch coverage, format/lint, strict types, documentation links, dependency audit,
  privacy and version alignment. No known audited vulnerabilities or ignored gates.
- Focused domain/API/migration and standalone/nested-Ingress browser tests passed;
  browser scenarios include selection reset, preview failure/recovery and logout
  draft cleanup. No real managed host/backend is contacted.
- Remote checks run on the pushed MR/PR head. Live pipeline/check results remain
  authoritative; local release-check does not itself build both container images.

## Review and rollout

No version bump, merge, release, image publication or new runtime privilege in this
block. Back up data/SSH state together before later operator upgrades; no downgrade
promise after group writes. New Wiki pages remain unreviewed source snapshots until
owner acceptance and publication. The owner separately authorized publication of the four registry pages
`technical/api`, `technical/architecture`, `technical/development` and
`technical/persistence` at merged main `f3bfd64bde34`; all four were published and
read back successfully on 2026-11-16 after matching their previous source snapshots.
The new groups snapshot remains unpublished; unexpected remote edits must never
be overwritten. #44/#46 remain the
next target/job and authorization work, not implemented by grouping.
