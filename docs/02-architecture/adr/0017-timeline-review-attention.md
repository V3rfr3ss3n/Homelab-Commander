---
title: ADR-0017 Timeline review attention
status: accepted
date: 2026-11-11
tags: [architecture, backend, ui, jobs]
---

# ADR-0017: Timeline review attention

## Context

A historical failure stays failed after review. Using that outcome as a red point
continues demanding attention after the operator has resolved the notice.

## Decision

Extend [ADR-0014](0014-guided-setup-and-failure-review.md) and
[ADR-0016](0016-timestamp-job-timeline.md) with additive response fields:
`Job.needs_review` and `TimelinePoint.review_required`. Derive both from the same
predicate as unresolved failure notices: failed, unreviewed, and without a later
successful job matching host, action and custom task. Matching retries outside the
selected timeline period also resolve attention. Count every job in a bucket,
including jobs beyond the six previews. Red points indicate outstanding review;
reviewed/resolved failures use neutral points. Outcome curves retain history.

## Consequences

No persistence migration, dependency or execution changes. Existing API fields and
stored outcomes remain valid. Regression tests cover reviewed and resolved failures,
full bucket counts, mixed-state groups, and standalone/nested Ingress navigation.
