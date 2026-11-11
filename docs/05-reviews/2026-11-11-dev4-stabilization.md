---
title: 0.3.0-dev.4 stabilization evidence
status: review
date: 2026-11-11
tags: [review, release, validation]
---

# 0.3.0-dev.4 stabilization evidence

## Candidate and changes

The owner requested the combined work from MRs !30–!33 as dev.4, with stability
fixes before release. The candidate combines dashboard/timeline, job/host
workspaces, deliberate bulk controls and Home Assistant update progress.
No new production dependency, public API, persistence migration or implicit
update/reboot is introduced. Compatibility identifiers and `/api/v1` are retained.

Browser timing assertions now select `en-US` and `de-DE` explicitly, checking
milliseconds, adaptive duration units, local date and UTC timezone plus original
ISO timestamps. The active-job regression seeds an old running update, 101 queued
records and 101 newer terminal jobs. Host-scoped counters, paginated active jobs,
update/reboot guards and bulk eligibility remain correct and recover at completion.
All execution adapters and inventory in these checks are synthetic.

The public GitHub Quality run on the intermediate timeline merge exposed a
detached orbit-center click. Repeated pointer events rebuilt the same preview,
discarding focused/clicked links. A focused-center regression failed before the
fix; keeping the current point preview intact passes in Standalone and Ingress
(2 targeted tests). Switching points, Escape and chart exit still close/change it.

## Validation record

- Targeted timing tests: 2 passed in explicit English/German locales.
- Targeted old-active-job browser regression: 1 passed, including second-page
  queued jobs and guard recovery after terminal state.
- Combined `UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/vhomelab-uv-cache make release-check`:
  passed on the combined candidate tree: 386 tests, 98.43% lines and 96.15%
  branches; format/lint/strict types/docs/audit/privacy and dev.4 version alignment
  passed. The full gate passed again after the orbit fix at `093b4fb6f7c1`
  with the same 386 tests and independent coverage values. The final main
  revision must also complete its CI gates.
- Exact-revision public Quality, HACS, Hassfest, CodeQL, secret and native
  AMD64/ARM64 container gates: pending after integration into main.

## Artifact and Supervisor acceptance limits

`docker info --format '{{.ServerVersion}}'` and the same command with
`--context default` fail because neither configured local Docker socket exists.
The actual dev.3-to-dev.4 container upgrade therefore has not been executed.
No isolated Supervisor test instance or `ha` CLI is available in this environment;
Store `version_latest`, one-button App upgrade and post-upgrade integration reload
have not been accepted.

Owner decision on 2026-11-11: publish this development prerelease after green
automated gates, without provisioning an additional Supervisor test instance.
The operator will validate Store recognition and the upgrade on their existing
installation after publication. This explicitly defers those manual acceptance
items for dev.4; it is not a successful upgrade-test claim or stable-release
acceptance. Automated tests never contact that installation or its managed hosts.

Once an isolated runtime is available, use the previous public dev.3 image and
synthetic data, then upgrade to the exact dev.4 artifact. Verify inventory/task/job
IDs, review state, preferences, website icons, SSH private/public key and known_hosts
bytes across upgrade and restart. Do not contact managed hosts or dispatch real
SSH/Ansible actions. Reload the upgraded integration and verify queued/running/
terminal update progress against a fake backend.

Tagging and image publication require the final automated gates, including native
multi-architecture runtime checks and anonymous image access. Release notes must
disclose the untested image-upgrade/Supervisor path. A missing Store version or
timeout still prevents closing operator acceptance under T-032; it must be
reported rather than presumed successful.
