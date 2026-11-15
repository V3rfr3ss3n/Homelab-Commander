---
title: Safe failure diagnostics and compatible history timestamps
status: accepted
updated: 2026-11-15
tags: [architecture, diagnostics, privacy, persistence]
---

# ADR-0021: Safe failure diagnostics and compatible history timestamps

## Context

GitHub #62 reports empty filtered history despite existing jobs and a green
last-failed title. SQLite before 3.42 returns NULL for the unsupported `subsec`
modifier; reproducing that behavior makes both history endpoints silently return
zero. GitHub #63 requests visible failures with useful, safe investigation data.
Some frontend failures lose context, worker unexpected errors lose their code
location, validation errors echo input, and HA flow logging includes raw traces.

## Decision

Register a deterministic `hlc_timestamp` function on every backend connection.
It parses the existing timezone-aware ISO timestamps with Python and returns
epoch seconds, preserving microsecond and UTC-offset semantics. Filtering,
sorting and timeline grouping share this expression. Existing interval semantics
remain start-inclusive/end-exclusive. No schema migration or SQLite upgrade is
required. Existing bounded queries retain their scan-based date computation.

Add a pure ASGI error boundary and compatible HTTP/validation handlers. Generate
an opaque request reference server-side, return it in `X-Request-ID`, and add
allowlisted metadata to error responses while preserving status and `detail`.
Unexpected failures expose a generic explanation. Log the reference, static
operation and at most six source basenames/line numbers; never log exception
text, source lines, locals, bodies or raw request targets. Disable standard
backend access logs. Interrupted responses propagate only a sanitized exception.

Worker failures keep `internal_execution_error` and use the existing job ID as
their reference in the bounded, authenticated job log. HA's native adapter keeps
only HTTP status and a strictly validated request reference. HA configuration
flows log bounded safe code locations rather than raw unexpected exceptions.

The management UI creates safe local errors for network/JSON/shape failures and
copies only version, static component/operation, code, UTC time, HTTP status and
validated request/job references. It does not export full payloads. History
failures are persistent and distinguish stale matching data from unavailable
different filters. Retrying history is read-only. Polling deduplicates outage
notifications and indicates recovery. Failed outcomes remain separate from review
attention. The explicit synthetic preview can fail one history request to prove
the retry path; production has no fault-control endpoint or setting.

## Consequences and compatibility

No dependency, persistent diagnostic store, public log endpoint, host mutation or
release automation is introduced. IDs, database contents, SSH identity and
`/api/v1` remain compatible. Validation response structure remains a list, but
input/context and unknown field names are deliberately excluded. Diagnostic
references expire with ordinary logs, not through a new retention service.
Code locations aid investigation without promising raw stack dumps or an external
telemetry service. Initial UI failures can report version `unknown` until connected.

## Validation

Regression tests emulate unsupported SQLite modifiers; verify precise boundaries,
offsets, pagination and matching graph/table results. API/worker/HA tests verify
correlation and privacy. Chromium tests cover standalone and nested Ingress,
stale/unavailable results, safe copy, malformed/network failures and recovery.
The full quality gate and local owner acceptance are required before merge.
