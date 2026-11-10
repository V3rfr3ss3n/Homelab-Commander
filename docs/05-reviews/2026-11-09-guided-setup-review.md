---
title: Guided setup and failed-job review
status: review
date: 2026-11-09
tags: [review, backend, security, ui]
---

# Guided setup and failed-job review

## Scope

A failed job can be acknowledged without changing its outcome/log. Migration 7
adds nullable review metadata and retains existing records. The host dialog guides
system selection, configurable user preparation and connection import, with an
existing-user update path. No new production dependency or automatic host action.

## Security review

Sudo defaults to no managed rule. Full root requires explicit selection and UI
acknowledgement before copy. Scripts use fixed validated options and run only when
the operator executes them on the target as root. Candidate rules use private,
exclusive creation, visudo validation and atomic replacement. Foreign rules,
symlinks/hardlinks and root-equivalent accounts are rejected; independent sudo
rules/groups remain active. Update mode changes the selected existing-user shell.
The backend never runs a setup script or contacts an onboarding target. SSH TTY
allocation is explicitly disabled for non-interactive restricted keys.

## Validation

Focused synthetic script/API tests and standalone/nested Ingress browser flows
cover direct clipboard copying, guarded root selection, imports, edit-to-update,
review from a notice, reload persistence, unchanged history and hidden empty notice
panels. Existing migration coverage checks unreviewed legacy jobs. System commands
and account/filesystem boundaries are simulated; no managed host was contacted.

`UV_NO_SYNC=1 make quality`: 355 tests passed; independent line coverage 98.43%
and branch coverage 95.87%, formatting/lint/types/docs/audit/privacy passed.
The final run also verifies clipboard fallback inside the active modal. Schema
downgrades and transactional rollback of manually executed setup scripts are not
provided. Removing a managed sudo rule does not revoke independent access.
