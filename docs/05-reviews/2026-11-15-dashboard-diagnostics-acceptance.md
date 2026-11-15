---
title: Dashboard history and safe diagnostics acceptance
status: review
updated: 2026-11-15
tags: [review, dashboard, diagnostics, acceptance]
---

# Dashboard history and safe diagnostics acceptance

This is the shared stabilization block for GitHub #62 and #63. It does not
implement #41, change a version, merge code, tag or publish a release.

## Diagnosis and audit

| Boundary | Finding | Result in this branch |
| --- | --- | --- |
| History SQL | SQLite before 3.42 returns NULL for `unixepoch(..., 'subsec')`, silently filtering out existing jobs | A regression emulates this runtime and first failed with 0 instead of 2; a registered timestamp function now serves filters, sorting and buckets without a data rewrite |
| History UI | Failed reads were indistinguishable from empty results or left unmarked stale views | Persistent unavailable/stale state, query-specific cache, read-only retry and recovery; full offline refresh covered |
| Failed highlight | Title inherited the normal green link color | Failed titles/results are red with an explicit outcome label; review attention remains separate |
| API | Unexpected failures lacked a safe correlation boundary; default validation can echo input/context/extra names | Server-generated request references, additive metadata, sanitized validation and bounded code-location logging |
| Worker | Unexpected execution failures stored only a generic code | Existing safe code retained; protected job log and safe process log share the job reference and code locations |
| Browser requests | Raw network/JSON/response details could lose context or be surfaced directly | Local safe error taxonomy, static operation, UTC time, version and allowlisted references; expandable/copyable report |
| Notifications | Late navigation could erase a newer error; polling could repeat outage notices | Generation protection, explicit recovery and deduplicated polling failures; mutations are never automatically retried |
| HA native adapter | HTTP failures discarded response status/reference | Preserve numeric status and strictly validated opaque reference; retain auth and malformed-payload categories |
| HA config flows | Unexpected exceptions could log raw traces | Bounded code locations only, with secret-leak regression coverage |
| HA coordinators | Typed failures already become HA-native UpdateFailed/unavailable states | Preserve lifecycle, translations and recovery behavior; existing tests remain part of the full gate |
| Backend entrypoint | HTTP access logs include raw request targets | Disable access logging; failure references remain available in safe logs |

No real managed infrastructure was contacted. Reproducing the SQLite behavior is
not a claim to have inspected the reporter's installed SQLite runtime.

## Local owner acceptance

From the feature branch, use the existing VS Code launcher or run:

```bash
uv sync --frozen
uv run python -m homelab_backend.preview
```

Open `http://127.0.0.1:8100`. The preview uses temporary synthetic data and an
exclusively simulated executor; no host actions, SSH or Ansible are performed.
Stop an existing preview process before starting another one on port 8100.

- [ ] Seven-day graph and table each contain the same 14 seeded jobs. Check host,
  state and action filters, time ranges, sorting and reset.
- [ ] Last failed job has a red title and a visible failed label. Reviewing a
  failure changes attention, never its historical execution outcome.
- [ ] Start with `--history-failure-once`: the first filtered history request
  fails visibly, without claiming 0 jobs. Technical details and Copy diagnostics
  work; Retry history restores the stored jobs.
- [ ] Go offline in browser developer tools and refresh: matching history remains
  visibly stale. Change a filter: unavailable, not stale rows relabeled as the new
  query. Restore connectivity and retry; counts and online status recover.
- [ ] Copied diagnostics contain safe code, UTC time, version, static operation
  and available HTTP/reference data. They exclude tokens, host addresses,
  response bodies, command output and raw exception text.
- [ ] Job/log loading failures retain the job summary, offer technical error
  details and recover with Refresh job.
- [ ] Host edit/remove failure leaves the host and dialog state intact. A later
  successful operation still shows its normal success message.
- [ ] Check a narrow viewport and normal navigation after a failure; no blocking
  native dialogs or invisible error-only states.

## Automated validation

`UV_CACHE_DIR=/tmp/hlc-uv-cache make quality` passed on 2026-11-15: **445 tests**,
**98.61% line coverage** and **96.59% branch coverage**, checked independently.
Formatting, lint, strict types, documentation links, dependency audit (no known
vulnerabilities) and privacy passed. The command includes all unit, API,
HA and Chromium tests, strict types, formatting/lint, documentation, dependency
audit, privacy and independent 95% line/branch coverage requirements. The PR
records the actual result and remote check status. Local owner acceptance is not
replaced by automated tests.

## Documentation and repository alignment

The feature branch preserves the already approved PR #40 planning documents.
The later dev.5 main update omitted those five files/edits; their restoration is
explicitly part of this PR, without starting #41 or changing the approved scope.

The four changed Wiki source pages are `technical/api`, `technical/development`,
`user-guide/troubleshooting` and `user-guide/updates-and-jobs`. Inspect the remote
pages before any publication and preserve unexpected edits. Source pages in this
PR describe unreleased behavior; the live Wiki snapshot remains unchanged pending
review. This divergence is deliberate and must be resolved through the established
reviewed-snapshot publication process, not by silently overwriting live pages.

## Release boundary and remaining limits

Owner local acceptance precedes review and merge. A development release requires
a separate owner request. No new package dependency, schema migration, diagnostic
store, public log endpoint or telemetry service is introduced. An initial UI
failure may report version `unknown`; request references depend on ordinary
backend log retention. All reported details are deliberately allowlisted rather
than full stack/exception dumps.
