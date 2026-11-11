---
title: Timeline and App upgrade gate review
status: in-review
date: 2026-11-11
tags: [review, dashboard, release]
---

# Timeline and App upgrade gate review

## Facts

The dashboard uses a timestamp timeline from complete persisted jobs. The job
page and timeline share host, state, action and inclusive/exclusive time filters.
The response caps point previews and the job table remains paginated. Host, task
and job lists have compact filters and sort choices. A bulk update targets only
visible checked hosts with pending updates after one explicit confirmation;
per-host backend authorization and locks remain in force.

The candidate advances App and integration versions to dev.4; its image is
unpublished until the release workflow runs. Source alignment alone does not
prove Store availability.

A source version gate now compares the Python project, lock, backend, integration,
App config, Docker build default, Compose image and publication workflow. It runs
in `make release-check` and the container policy before any image publication.
A synthetic regression proves an old App metadata version fails. The incident in
which Home Assistant initially kept `version_latest` at dev.2 was a Supervisor
Store reload timeout, not a source version mismatch. The new installation
checklist therefore requires an actual previous-version-to-new-version update in
an isolated Supervisor test. This cannot be represented as a successful gate by
an image pull or integration update alone.

## Evidence and open acceptance

- Synthetic API tests cover more than 100 jobs, grouping, timestamps, filter/count
  agreement and invalid periods.
- Chromium tests cover standalone and nested Ingress, mobile grouping/orbit,
  group-to-table navigation, state/host/task filters and the explicit bulk-update
  confirmation with a fake executor.
- `make quality` and independent line/branch coverage are required before the MR.
- Fresh HA Supervisor Store recognition and one-button App upgrade remain a manual
  release acceptance gate. No stable release is authorized by this review.
- Wiki source updates are part of the MR. Publish them after merge and verify no
  intervening remote edits; publishing branch-only behavior before merge would
  diverge from the deployed main version.
