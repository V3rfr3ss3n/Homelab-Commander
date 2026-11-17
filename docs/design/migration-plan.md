---
title: Incremental UI migration and verification
status: proposed
updated: 2026-11-16
tags: [design, migration, testing]
---

# Incremental UI migration

| Slice | State | Boundary / proof |
| --- | --- | --- |
| #43 + #69 foundation in PR #68 | Implemented for review | Preserve schema-12 groups; Resources facets/editor, tokens, list mechanics, architecture/design records |
| Shell and transport | Proposed follow-up | Text-labeled compact sidebar, five destinations, route aliases and existing context; same Ingress/session contract |
| Legacy Host/task/job lists | Proposed follow-up | Adopt common mechanics one list at a time; preserve direct actions/filters/package scope, remove superseded renderer only after parity |
| Generic jobs and policy #44/#46 | Planned prerequisite | Effective target snapshots, conflicts, backend per-target authorization/revalidation; no UI-only grants |
| #45 and M2–M6 vertical features | Planned | Reuse resource details/actions and typed provider capabilities; no speculative providers |
| #70 localization | Planned | Complete catalogs/locale/fallback/accessibility/test coverage before another UI language |

Do not combine framework migration, backend folder churn or later provider features
with this review. ADR-0025 remains proposed; owner review decides larger shell UX.

## Compatibility and rollback

This UI follow-up adds optional group/sort query parameters, static ES-module assets
and no new database migration beyond the existing PR's schema 12. Existing API URLs,
Host/job/task/resource UUIDs, SSH identity, state and direct actions are retained.
Legacy `#/groups` resolves to inventory. The prior `a488e37` implementation is the
UI rollback baseline: revert the follow-up commits without reverting schema 12 or
dropping group tables. Do not downgrade a populated schema-12 database to older
binaries as a UI rollback strategy. No reset/reseed of production data.

## Regression gates

Focused group/API/browser tests cover persisted membership/tags, bounded smart
rules, unknown evidence, preview without writes, group deletion, auth/CSRF,
server-side sorting and filtering before pagination, off-page selection, clear/reset,
manager/editor focus, responsive layout, errors/recovery and stale response rejection.
Standalone and nested Ingress run with isolated databases, synthetic executors and
auto-checks disabled in targeted inventory tests. No actual provider calls.

Run `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check` on the final implementation.
It includes quality/strict types/docs/audit/privacy and independent 95% line/branch
thresholds. Separately verify GitLab and GitHub Quality, HACS, Hassfest, CodeQL,
secret scan, AMD64/ARM64 build and runtime-contract jobs on the final commit.
Publication jobs remain skipped in a PR. Record failures/unavailable commands; no
assertion, test or gate weakening. Owner preview acceptance precedes merge; no merge,
Wiki publication, release, version bump or deployment is part of this task.
