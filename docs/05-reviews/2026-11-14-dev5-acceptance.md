---
title: dev.5 package update acceptance
status: review
date: 2026-11-14
tags: [review, release, packages, acceptance]
---

# dev.5 acceptance before publication

This MR prepares the existing package-details work for dev.5. It does not publish
or merge the candidate. Complete the following checks and record actual results
on the final release revision. Checked items describe reproduced automated cases;
operator/container acceptance remains open unless separately recorded.

## Package behavior

- [x] Single update uses APT latest/only-upgrade, then a measured read-only check.
  A synthetic 12-package snapshot becomes 11; remaining names and security counts
  match. No full-upgrade argument or reboot is dispatched.
- [x] Selected updates carry exactly the confirmed names in one job, survive
  worker recovery and retain scope when rerun. Empty/duplicate/unsafe/ambiguous
  or over-limit selections are rejected without queueing work.
- [x] Full update remains a separate no-body action. Confirmation explains that
  skipped/undisplayed packages and dependency updates can be included.
- [x] Counts/list remain unchanged while queued/running; success refreshes them
  together. Failed updates preserve previous counts/rows. Host controls are locked
  while mutating work is active.
- [x] Skip all, Select all, single Skip and sorting do not dispatch updates.
  Zero selection is disabled; sort preserves selected package identities.
- [x] Standalone and nested Ingress show readable time, correct package versions,
  security badges and refreshed remaining rows; mobile layout stays within width.
- [ ] Check the demo and operator flow with 12 pending packages: single → 11,
  selection → matching remainder, all → measured empty list, failed refresh →
  last known data with a failed job. A simulator must honor the same scoped
  adapter contract; a fake executor that zeroes everything is not evidence.
- [ ] Accept the explicit 50-row detail limit and full-vs-shown selection wording
  for dev.5, or extend the detail contract before claiming arbitrary list access.

## Data, quality and release gates

- [ ] Upgrade isolated synthetic dev.4 data (schema 7) and any existing package
  preview (schema 9) to schema 10; preserve host/task/job IDs, old single-package
  scope, preferences, logs/review state and SSH identity. Repeated migration works.
- [ ] Full `make release-check` on the final release revision: format, lint,
  strict types, all tests, independent ≥95% lines and branches, docs, audit,
  privacy and source version alignment. Record commands and real results.
- [ ] GitLab plus exact-commit GitHub Quality, HACS, Hassfest, CodeQL and secret
  scan pass; native AMD64/ARM64 builds and runtime contract pass.
- [ ] Review/merge the MR, verify dev.5 version metadata, publish through the
  existing protected workflow and verify anonymous multi-architecture manifest,
  pull/runtime and HACS artifacts before announcing the release.
- [ ] Refresh the App Store and verify dev.5 recognition and normal App/HACS
  upgrade, integration reload and UI reload. The owner previously chose operator
  validation on their installation rather than an additional Supervisor fixture;
  record this separately and never run automated SSH/updates/reboots there.
- [ ] Publish the reviewed Wiki snapshot after checking remote edits; notes state
  upgrade steps, known limits and outstanding manual acceptance honestly.

## Validation record

The combined local `UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/vhomelab-uv-cache make release-check`
passed: 414 tests, independent 98.43% line / 96.12% branch coverage, format/lint,
strict types, docs, dependency audit, privacy and dev.5 source version alignment.
Package tests include schema-7/9 migrations and a real browser rerun request.
The first full run exposed a hidden package-check button being selected as a host
check; the dialog now has a dedicated check handler and the full UI test passes.
All adapters/modules are synthetic or mocked. These local results do not close
the final merged-revision/publication/operator gates above. The MR records CI
results separately; unchecked items are not presumed passed.


## 2026-11-15 actual preview follow-up

The local VS Code preview maintained its own ignored adapter. Reproducing a vim
update with that exact adapter produced count 0, twelve retained rows and vim
still present: it ignored the package name and reset counts for every update.
Earlier package regressions used a different fake and missed this discrepancy.

The canonical preview now lives in the versioned backend module and the local
VS Code wrapper delegates to it. Tests start that same preview app and cover vim
12→11 (security 4→3), selected/full updates, a subsequent check, custom tasks,
reboot simulation, stale-inventory reads and loopback-only launch. The count/list invariant rejects a
contradictory adapter result before it can replace a stored snapshot. A real
browser checks the reorganized toolbar and the 11-row result on desktop/mobile.
Restart the preview process and reload its UI before repeating operator checks;
old Python processes keep the old adapter in memory. No managed-host operation
is involved in this preview.

Validation of the follow-up: `UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/vhomelab-uv-cache
make release-check` passed with 424 tests, independent 98.48% line / 96.21% branch
coverage, lint/format/strict types/docs/audit/privacy and dev.5 version alignment.
Desktop/mobile screenshots and the vim workflow use the actual preview factory,
not the earlier unrelated package-test fake. The local ignored VS Code shim now
delegates to the versioned entrypoint; no editor settings or generated preview databases are committed.
