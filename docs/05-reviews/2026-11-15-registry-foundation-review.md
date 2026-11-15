---
title: Resource registry, module boundaries and dependency follow-up
status: review
updated: 2026-11-15
tags: [review, registry, dependencies, compatibility]
---

# Registry foundation review (#42 / #61)

#41 was approved by the owner, merged in !38, and is the base for this separate
block. This MR adds real persistent registry functionality and incremental module
separation, plus the changes proposed by Dependabot #32/#33/#35/#36. Those PRs are
superseded only after this combined change is reviewed/merged, not merged blindly.

## Boundaries and operator expectations

- `resources/entities.py` and core contracts: immutable domain values, no I/O.
- `resources/application.py`: use cases and store Protocol, no database/HTTP imports.
- `resources/repository.py`: atomic SQLite implementation and row-to-domain validation.
- `resources/schemas.py` and `routes.py`: bounded typed admin HTTP boundary.
- `persistence/sqlite.py` and `migrations.py`: storage lifecycle/versioned schema;
  the old `database.py` import path remains compatible.

Existing dashboard/Host/task/job flows remain unchanged. Services and infrastructure
instances are metadata managed through the authenticated API; there are no new
provider connections, service controls, generic jobs, automatic host discovery or
agent grants. Multiple services can link one existing Host or have no Host. Instance
reconciliation retains external/internal identity separation and never creates an
extra Linux Host implicitly. The next feature blocks remain #43/#44/#45/#46.

## Local acceptance

Use the disposable preview (`uv run python -m homelab_backend.preview`), stop/restart
an older process first, and open `http://127.0.0.1:8100`.

- [ ] Dashboard/Host/task/job navigation and fake actions behave as before.
- [ ] A focused graph orbit survives pointer movement and overlapping refresh;
  its center still opens the corresponding jobs in the table.
- [ ] Open `/ui-api/resources` on that loopback preview: its three Hosts have their
  original IDs. Provider metadata is authenticated inventory, not bug-report data.
- [ ] Run `uv run pytest backend/tests/test_resource_registry.py --no-cov` to exercise
  service creation/host linking/removal, VM reconciliation, cycle/conflict handling,
  rollback, concurrent startup and external/UI auth/CSRF without real infrastructure.
- [ ] Review [ADR-0023](../02-architecture/adr/0023-resource-registry-and-module-boundaries.md)
  for the migration, incremental layout and exact dependency choices.

The original dev.5 synthetic rows are compared before/after migration: Hosts, jobs
(including queued/running/reviewed failures and selected-package scopes), tasks and
logs stay intact. SSH identity/known-host bytes are preserved. A deliberately failed
migration leaves no partial registry or schema marker; repeated startup is idempotent.
Full-suite testing reproduced a first-WAL race; schema initialization is now serialized,
not retried with sleeps or ignored. No tests use real SSH/managed backends.

## Dependency follow-up

All four bot proposal groups are included in the frozen lock/workflows. The new
frontend is tested against pinned HA Core; this does not claim a Core upgrade.
The Ansible callback has a direct no_log guard. FastAPI telemetry and exporters are
explicitly disabled, including telemetry logs and operation spans. No known advisory
or failing gate is ignored. A builder test now verifies immutable and consistent
pins while retaining all publication policy assertions.
The complete suite also exposed an unscoped TestClient worker thread during
diagnostic-test teardown; those clients now own their lifespan explicitly. No
thread-leak assertion, coverage threshold or other gate was disabled.
The new browser stack also exposed a focused orbit being replaced by an
overlapping history render. Pointer movement now preserves keyboard focus, and
history rerenders restore the corresponding group by job identities. A deterministic
standalone/Ingress regression covers pointer leave, adjacent hover and rerender.

## Executed validation

- `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check`: passed, including format,
  Ruff, strict Mypy, 480 tests, links, security-exception checks, dependency audit,
  privacy and version alignment. Independent line coverage: 98.64%; branch: 96.95%.
- `uv run pytest backend/tests/test_error_diagnostics.py
  backend/tests/test_resource_registry.py --no-cov -q`: 17 passed.
- `uv run pytest backend/tests/test_timeline_browser.py --no-cov -q`: both
  standalone/Ingress cases passed; the expanded regression failed before the fix.
- Historical migrations 1–10 compare byte-for-byte equal before/after extraction.
  Builder/setup-uv commit pins resolve to their official release tags.
- Remote GitLab/GitHub and native container runtime gates run on the pushed MR/PR
  head. Their live statuses are authoritative; the local command does not run them.

## Remaining review/release limits

Owner review and all remote gates precede merge. No version, tag, release or public
image is published by this block. Downgrade is not declared safe after registry writes;
back up database and SSH identity together before later operator upgrades. New Wiki
source changes remain a review snapshot; no authorization to publish them is inferred
from approval of the previous four stabilization pages.
