---
title: Central authorization and approval-domain review
status: in-review
updated: 2026-11-17
tags: [review, security, authorization, approvals, migration]
---

# Central policy foundation (#46)

## Implemented and preserved

Shared policy enforcement protects mutating Host/task/group/tag/registry/preference/
review use cases and worker dispatch. HTTP requests start anonymous, identities bind
only after existing authentication and CSRF remains mandatory. Jobs retain their
server-authenticated principal across queueing/restart. Unknown or agent/automation
execution denies; readiness callbacks and caller-supplied role/approval claims cannot
upgrade authority. Existing explicit admin maintenance and HA/API identifiers remain.
See [ADR-0027](../02-architecture/adr/0027-central-policy-and-approval-contracts.md).

The approval-domain service persists immutable request/risk/scope/state/expiry,
requires a human UI source for decisions, revalidates authoritative state and
consumes one approval for one job atomically before dispatch. Consumed approvals
are not rearmed after interruption. Approval proposals do not create queued jobs
or grant an agent execution rights. Production installs no approval routes, agent
provisioner, configurable policy editor or live generic provider binding.

Additive schema 14 introduces authorization audit and approval tables without
rewriting old snapshots, IDs, configuration or SSH identity. Shared-channel principal
UUIDs deliberately do not claim individual attribution. Old queued snapshots retain
their legacy entrance. Domain/application/HTTP/SQLite responsibilities remain separate.
No production dependency, version bump or additional runtime privilege.

## Threat model and important limits

- Network requests cannot fall through to trusted internal authority if a route
  misses its auth dependency. Internal Python/SQLite/SSH adapters remain trusted;
  this is not sandboxing untrusted code.
- No agent receives the existing master credential. Injected resolver contracts
  cannot label an Agent principal as a human by header/body claims; invalid source/
  kind combinations are rejected, and only API-admin authority enters legacy routes.
- API/system/agent/automation identities cannot decide human approvals. Future M6
  must supply nondelegable individual identity, credential revocation, current role
  lookup and the fully reviewable operator scope/expiry surface before activation.
- Metadata membership/readiness is never a permission. Each future protected feature
  needs a registered policy, typed parameters/results, target/conflict resolution
  and a mandatory authoritative StateValidator. Remote out-of-band races and exactly-
  once effects are not solved by this local contract.
- Audit stores only technical IDs, UTC time, permission and static reason/state code.
  No credentials, headers, addresses, command bodies, raw exceptions or provider text.
  Future untrusted callers need bounded retention/rate controls before activation.

## Regression evidence

- Synthetic tests cover direct metadata/task/probe/automation bypass attempts,
  forged request identity, queued-agent identity, API/key/shell/login denial,
  missing HTTP auth dependency and context cleanup.
- Approval tests cover immutable JSON, bounded expiry, non-human decisions, exact
  requester/resource/action/parameter digest, current state, duplicate consumption,
  job interruption without rearming and atomic schema-13 upgrade/rollback.
- Existing #44 synthetic generic handlers now receive explicit test-only operation
  registrations. The readiness callback alone no longer permits execution. Original
  denial, concurrency, recovery and mutation assertions remain; no gate is lowered.
- A failing browser regression reproduced Ingress policy 403 being mislabeled as
  expired authentication. The UI now recognizes only the safe `policy_denied` code,
  keeps the valid session and offers sanitized copyable diagnostics. Other Ingress
  403/authentication errors retain their original disconnect behavior. Standalone
  and nested Ingress are both checked.
- Final `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check` passed: **573 tests**
  in 120.79 seconds, **98.63% line / 96.10% branch coverage**, Ruff, strict Mypy
  (85 files), docs (0 broken links), privacy, dependency audit (no known
  vulnerabilities) and unchanged version alignment `0.3.0-dev.5`.
- Focused policy/approval suite: **47 passed**; standalone/Ingress policy-denial
  browser suite: **2 passed**. The final full gate includes both suites and the
  original Host/package/task/job/HA tests. Remote results are recorded in the MR.

## Local owner acceptance

On `feat/central-authorization`, stop an old preview and run
`uv run python -m homelab_backend.preview`; open http://127.0.0.1:8100.
Check existing navigation, package scope, deliberate update/reboot/task confirmation,
job details/review and session/reload behavior with synthetic data. Most of this
block is backend infrastructure; no new agent/approval management screen is expected.

Deterministic security cases run with
`uv run pytest backend/tests/test_policy.py backend/tests/test_approvals.py backend/tests/test_policy_browser.py --no-cov`.
Do not test with real credentials or interrupt real Host work. The synthetic generic
handlers perform no SSH, Ansible, provider update or reboot.

Owner review and explicit merge remain pending. No Dev release is requested. Affected
Wiki sources are prepared but remain unpublished until owner reviewed-snapshot
approval; prior publication authorization does not silently cover this new policy slice.
