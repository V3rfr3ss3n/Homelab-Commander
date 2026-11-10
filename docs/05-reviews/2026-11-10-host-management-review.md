---
title: Host management navigation and edit actions
status: review
date: 2026-11-10
tags: [review, ui, regression]
---

# Host management navigation and edit actions

## Finding and fix

Reproduced host removal failure before editing: DELETE succeeds, then the generic
mutation refresh calls task compatibility for the removed detail route. A 404
leaves the UI at that route with "Host not found". The regression failed at its
host-list navigation assertion. A dedicated removal action now changes route
before refresh and closes an open host edit dialog only after successful DELETE.
Cancel/error preserves the view; an open dialog receives its error locally.

Edit host now exposes existing-user setup and host removal before the connection
form. Setup navigation preserves unsaved values and allows copying without form
submission. Copy feedback is visible inside the dialog. Confirmation identifies
the saved host and explains removal does not revoke remote SSH access.

## Boundaries

This is a presentation fix on the pending guided-setup MR !26. Existing removal
API/persistence semantics and authentication/CSRF are unchanged. No remote user,
key, privilege or active job is modified by the UI fix. No production dependency,
new migration, merge or release is introduced. The published dev.2 App does not yet
contain !26's setup assistant; delivery requires that dependency and a later release.

## Validation

Synthetic mobile standalone and nested Ingress browser tests cover detail/edit
removal, cancellation, failed requests, successful navigation/reload, no deleted
host endpoint requests, preserved fields, copied update scripts and in-dialog copy
feedback. No managed host is contacted; execution adapters remain synthetic.
`UV_NO_SYNC=1 make quality` passed: 359 tests, 98.43% lines and 95.87% branches
independently. Formatting, lint, strict types, documentation links, dependency audit
and privacy checks passed. The before-fix regression log is local synthetic evidence;
no private host addresses or logs are committed.
