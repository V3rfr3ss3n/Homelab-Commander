---
title: Resource job execution and safe recovery review
status: in-review
updated: 2026-11-17
tags: [review, jobs, architecture, migration, security]
---

# Resource jobs (#44)

## Delivered behavior

Additive schema 13 and immutable, credential-free execution snapshots preserve
legacy IDs/fields, selections, logs and review records. The worker now shares
canonical resource locks between a Host and associated Services; unrelated targets
remain concurrent. Queued work is claimed after its conflicts are held and current
identity/connection/task revision is revalidated. Running work blocks Host connection
changes/removal and Service relinking/removal. See
[ADR-0026](../02-architecture/adr/0026-resource-jobs-and-safe-recovery.md).

After restart, unstarted work survives. Interrupted updates/reboots/custom/generic
jobs fail with uncertain remote effects and require explicit review. Existing output
and original start are retained; later success does not acknowledge uncertainty.
Only existing observational connection/status checks may resume with interruption
metadata. Review and Run again remain separate explicit actions.

The internal resource-operation port has no production handler or public execution
route. Unknown operations and approval references are denied; synthetic handlers
prove enqueue/dispatch authorization and conflict behavior. Generic output is withheld
pending feature-owned input/result validation. #46 remains required for real policy,
approval and generic/group execution. No version, dependency, SSH file, HA identifier,
release channel or runtime privilege changes.

## Verification evidence

- A failing regression first demonstrated automatic replay of interrupted mutations;
  the corrected recovery tests pass.
- Focused synthetic tests cover immutable scopes, package selection, task/connection
  changes, Host/Service conflicts and independent concurrency, cancellation, restart,
  default deny, authorization races, safe diagnostics, API auth/CSRF/provenance and
  schema-12 upgrade/idempotence/rollback. Standalone/nested Ingress browser tests show
  the interrupted error and review action without executing the action again.
- Existing timeline regressions caught a nullable-error-code SQL boolean in review
  aggregation. It now uses a non-null comparison; original timeline assertions pass.
- Existing redaction test still exercises a stale first Host lookup and redacts the
  connection actually used; its queued scope now captures the accepted connection.
  New tests separately prove rejection of edits after queueing.
- The prior migration test compares every original named column unchanged, allowing
  new additive columns. Existing key-byte assertions remain. The API CRUD test waits
  for its synthetic task to finish before removing its Host; running removal has
  separate explicit 409 coverage. No timing sleep, assertion removal or lowered gate.
- Final `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check` passed: **524 tests**
  in 117.17 seconds, **98.58% line / 96.10% branch coverage**, Ruff, strict Mypy
  (78 files), docs (0 broken links), privacy, dependency audit (no known
  vulnerabilities) and unchanged version alignment `0.3.0-dev.5`.
- Final focused Job/API/browser/package run: 56 passed before the additional
  boundary tests; final focused resource suite: 30 passed. The final full run above
  includes all additions. Earlier full attempts exposed the regressions listed
  below; only the final passing run is the acceptance evidence.
- Remote results for the pushed commit are recorded in the MR; they are not implied
  by local checks. No release, image publication or deployment is requested.

## Threat model and limits

Authenticated callers cannot forge execution context/target/approval through legacy
request bodies. Shared admin credentials identify an entrance, not an individual.
Scope is evidence rather than permission. Generic handlers must not infer authority
from groups, tags, capability declarations or a UUID. Production installs none.

Locks assume the supported single process/one JobManager per database. They do not
coordinate distributed workers, establish fairness or make remote effects exactly
once. Legacy migration cannot reconstruct deleted targets or past connection values;
queued task revisions capture the definition available at migration. Future providers
need feature-owned validated inputs/results, authorization and complete conflict
resolution. No generic arbitrary parameter blob is accepted.

Downgrade to the old worker is unsafe: it may replay uncertain operations even with
an additive schema. Back up DB and SSH identity together, stop cleanly and use a
compatible artifact. No automatic remote reconciliation, rollback or cancellation.

## Local owner acceptance

On `feat/resource-job-execution`, stop an older preview and run
`uv run python -m homelab_backend.preview`; open http://127.0.0.1:8100.
Use only synthetic preview data. Check the existing Dashboard/Resources/Tasks/Jobs,
single/selected package updates and review actions. The deterministic restart,
concurrency and upgrade scenarios are in
`backend/tests/test_resource_jobs.py` and `test_resource_jobs_browser.py`; avoid
interrupting real host operations to reproduce uncertainty.

Owner review and an explicit merge remain pending. No Dev release is requested.
Updated Wiki sources remain unpublished pending owner approval of a reviewed
snapshot; do not overwrite the previously published snapshot silently.
