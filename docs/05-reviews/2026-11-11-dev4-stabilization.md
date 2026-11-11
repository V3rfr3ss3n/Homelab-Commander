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

## Validation record

- Targeted timing tests: 2 passed in explicit English/German locales.
- Targeted old-active-job browser regression: 1 passed, including second-page
  queued jobs and guard recovery after terminal state.
- Combined `UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/vhomelab-uv-cache make release-check`:
  pending final run. Do not substitute individual MR results for this gate.
- Exact-revision public Quality, HACS, Hassfest, CodeQL, secret and native
  AMD64/ARM64 container gates: pending after integration into main.

## Blocking artifact and Supervisor acceptance

`docker info --format '{{.ServerVersion}}'` and the same command with
`--context default` fail because neither configured local Docker socket exists.
The actual dev.3-to-dev.4 container upgrade therefore has not been executed.
No isolated Supervisor test instance or `ha` CLI is available in this environment;
Store `version_latest`, one-button App upgrade and post-upgrade integration reload
have not been accepted. These are release blockers, not waived manual checks.

Once an isolated runtime is available, use the previous public dev.3 image and
synthetic data, then upgrade to the exact dev.4 artifact. Verify inventory/task/job
IDs, review state, preferences, website icons, SSH private/public key and known_hosts
bytes across upgrade and restart. Do not contact managed hosts or dispatch real
SSH/Ansible actions. Reload the upgraded integration and verify queued/running/
terminal update progress against a fake backend.

Tagging, image publication and release announcement must wait for the required
gates. A missing Store version or timeout still blocks acceptance. Track the
remaining acceptance under T-032 and the public installation checklist.
