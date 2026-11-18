---
title: DNF/Zypper and nullable observation review
status: in-review
updated: 2026-11-18
tags: [review, linux, providers, migration, compatibility, security]
---

# Native RPM providers (#48)

## Scope and branch relationship

This branch is stacked on the still-open #47 matrix/evidence work (!44 / PR #74,
`3e85799`). No merge of #47 is inferred or performed. Review/merge the parent
before retargeting this dependent MR to main. No version bump, tag, image
publication or Dev release is part of this block.

The [decision](../02-architecture/adr/0030-dnf-zypper-and-nullable-observations.md)
records exact target admission, native argv/metadata/solver behavior, missing
signals, schema 15, nullable API/HA compatibility and deployment limits. Existing
valid APT behavior, `/api/v1`, IDs, SSH/configuration, policy/conflicts and never-
replay recovery remain. No production dependency or runtime privilege is added.

## Delivered behavior

- Static `dnf`/`zypper` choices, target facts/version/manager admission and root
  verification. Fedora 45/dnf5 and RHEL-family 9/dnf4 admit ordinary full/single/
  selected upgrades. Leap 16.0 admits regular package updates. Tumbleweed exposes
  read-only inventory and no mutation scopes; no `dist-upgrade` is implemented.
- Architecture-qualified selections remain immutable in existing job scopes and
  must still be eligible at dispatch. Native solvers control dependencies and may
  leave candidates pending. Update once, then measure a fresh remaining inventory.
- No advisory completeness claim: native security is unknown at aggregate/row
  level. DNF restart is unknown; Zypper uses its own native signal. Result 102
  preserves a restart hint; 103 requires another human-reviewed invocation.
- Fixed argv runner, C locale, no shell/bootstrap/key import/signature bypass,
  bounded in-memory capture and deadlines. Excess output is drained; timeout and
  transport interruption can leave uncertain remote effects. No automatic replay,
  retry, rollback or reboot. Raw native output/repository/exception text is excluded
  from these adapters' job logs and user errors.
- Schema 15 adds evidence-known flags and observed scopes atomically. Existing
  known APT values/IDs survive; unknowns return null, never guarded storage zeros.
  Provider changes invalidate incompatible cached evidence. Failed package checks/
  updates preserve counts as stale until an explicit/read-only refresh succeeds.
- UI provider choices and observed action gating, read-only bulk exclusion,
  explicit unknown labels/notices and remaining counts. The isolated preview
  simulates two RPM rows and retains remaining state; it never falls back to SSH.
- Updated HA null validation, unknown sensors/summaries, disabled unknown reboot
  action, preserved prior repair and an unknown-status repair abort. Legacy valid
  APT values and entity/configuration identities remain unchanged.

## Compatibility and important limits

Update the integration/strict clients before enabling new RPM configurations.
Existing endpoints extend security/reboot fields with explicit null and additive
scope metadata. Old clients may reject these new observations safely; no old-client
support for new providers is implied. APT-only users retain known values. Back up
`/data`; downgrade of RPM-enabled data requires a pre-upgrade backup because older
code cannot interpret evidence flags. No real upgrade/downgrade is executed here.

All native fixtures are manufactured. No real distro/repository/architecture
certification or automatic rollback guarantee is claimed; Commander container
runtime validation does not certify managed Fedora/RHEL/openSUSE. Current onboarding
scripts remain Debian/Ubuntu only; other systems need independently prepared SSH,
Python compatible with pinned Ansible, sudo, RPM and native manager/repoquery.
No tool or test contacts a real managed host or performs real maintenance.

## Verification

- Original targeted APT/API/HA/matrix subset: 284 passed during iteration.
- Native provider suite: 54 passed before final bounded-detail/preview checks.
- API/worker persistence and schema-14-to-15 atomic rollback: 4 passed.
- Chromium Standalone/nested Ingress RPM UI: 2 passed.
- Final targeted approval/resource/native/persistence/repair subset: 123 passed.
- The first full gate found two historical migration-fixture failures: old-schema
  rows were created through the latest repository, which now requires schema 15.
  Fixed SQL fixture columns retain the exact schema-12/13 starting points; no
  original identity/job/state/authorization assertion was removed. Both suites
  pass (52 cases). The final complete gate is green.
- `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check`: **697 passed** in
  128.86 seconds, **98.62% line / 96.19% branch coverage**. The native RPM module
  has 100% statements/branches in this run; script behavior also has injected
  bounded-output/timeout/process-cleanup tests.
- Ruff, strict Mypy (99 production files), all Standalone/Ingress/HA regressions,
  docs (0 broken links), privacy, dependency audit (no known vulnerabilities) and
  version alignment `0.3.0-dev.5` passed. Independent 95% line/branch gates remain.
- Remote GitLab/GitHub validators and both container runtime checks are recorded
  in the MR; local results do not replace those or real-platform certification.

Test assertions cover root/version/manager admission, full/single/selected effects,
unknown security/reboot, malformed/entity-bearing XML, native result codes, output
limits/deadlines, no retry/rollback/reboot, frozen architecture-qualified scope,
failed transaction cache/recovery, schema rollback and provider invalidation.
HA tests verify explicit-null acceptance without relaxing malformed/missing fields,
unknown state rendering, retained repair and blocked unknown repair confirmation.

## Local acceptance

Stop an older preview and run on `feat/dnf-zypper-providers`:

```sh
uv run python -m homelab_backend.preview
```

Open http://127.0.0.1:8100. Add a synthetic Host using the existing prepared-SSH path
and choose DNF or Zypper in connection settings. The preview does not connect,
even for arbitrary entered addresses. Run a check; expect two mock RPM rows.
Check explicit unknown security, unknown DNF restart, package sorting/skip selection,
one-package/selected/full simulated updates and measured remaining counts across
refresh. Test provider edits and normal APT navigation/jobs as a brief regression.
Tumbleweed read-only behavior is deterministic in the automated browser fixture.

```sh
uv run pytest backend/tests/test_rpm_providers.py backend/tests/test_rpm_persistence.py backend/tests/test_rpm_browser.py --no-cov
```

Use synthetic data only. Real target access/updates, cancellation, reboot and
upgrade/downgrade are not requested for this local acceptance.

## Wiki

Affected source pages: technical/api, technical/execution, technical/persistence,
technical/home-assistant, technical/development and user-guide/host-package-details.
They are prepared for review, not published. Prior #45 snapshot publication at
`9ea2130` remains the last explicitly approved set. Check foreign edits and request
specific snapshot authorization before any new publication; no prior rejection is
bypassed and no new audience/visibility is introduced.
