---
title: ADR-0014 Guided host setup and failure review
status: accepted
date: 2026-11-09
tags: [architecture, backend, security, persistence, ui]
---

# ADR-0014: Guided host setup and failure review

## Context

An inspected failure should stop demanding attention without erasing its history.
Host onboarding needs explicit system, user-privilege and connection steps, including
scripts to update an existing automation user. Earlier setup intentionally never
configured sudo; the owner now explicitly requests selectable rights in scripts.

## Decision

Extend ADR-0012's onboarding policy and ADR-0013's failure-notice selection.
Migration 7 adds nullable `reviewed_at` to jobs. Authenticated POST review endpoints
accept only failed jobs (404 missing, 409 other state), retain the first timestamp,
and do not change outcome/logs or run work. UI mutations require CSRF. Review is
backend-wide. Notices exclude reviewed failures; later successful matching jobs
still resolve notices. Last-failed history remains independent.

Use a three-step host assistant: supported system, declarative user setup, connection.
Debian includes Proxmox VE; no new execution provider is introduced. Existing prepared
access can skip script setup; host editing provides an existing-user update path.
Generate scripts from validated fixed options, never arbitrary shell/sudo fragments.
Options cover create/reuse versus update-existing, sh/bash, no managed sudo versus
full passwordless root, key forwarding/terminal restrictions and an optional IP/CIDR.
Keep the version-1 output envelope separate from setup policy. Copy uses an already
rendered script in the click gesture; changed inputs invalidate the previous preview.

No sudo is selected by default. Selecting full root requires an explicit additional
UI acknowledgement before copying; the authenticated script endpoint can still render
that explicit choice. Only manual execution on the target applies it. Temporary
Ansible Python modules cannot support a trustworthy apt-path-only sudo whitelist.
A selected full rule therefore gives root-equivalent authority and is labelled so.
Only a marked, root-owned regular Commander sudoers file may be replaced or removed.
Use exclusive private candidate creation, visudo validation and atomic replacement.
Do not follow sudo/key symlinks, accept hardlinked key/rule files, or alter unrelated
rules/groups. Removing the managed rule does not revoke independently granted rights.
The executor explicitly disables SSH TTY allocation to support no-pty keys;
non-interactive sudo remains required. Scripts preserve other keys, replace this key's restrictions, set private file modes,
and install no packages or firewall/sshd policy. Update applies the selected shell;
create/reuse does not change an existing account's shell. Python and selected sudo
support remain prerequisites. Partial script failures are reported by the local
interpreter; this is not a transactional host-configuration manager.

## Consequences and validation

No production dependencies, automatic host actions or authentication changes.
Existing hosts/keys/tasks/logs remain valid. Migration, per-job review, new failures,
CSRF/auth, mobile standalone/nested Ingress, one-click clipboard and edit-to-update
paths require regression checks. Scripts execute only in isolated simulations with
all system commands mocked; managed infrastructure is never contacted by tests.
