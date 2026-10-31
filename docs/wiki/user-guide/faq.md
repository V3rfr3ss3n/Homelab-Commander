---
title: Frequently asked questions
status: active
updated: 2026-10-31
tags: [wiki, user-guide]
---

# Frequently asked questions

## Do I need both the App and the integration?

For the recommended native HA setup, yes. The App executes and manages operations;
the integration represents them in HA. A standalone backend can replace the App.
A compatible legacy Semaphore setup can use its own provider instead.

## Does HA need my host's SSH key?

No. The backend owns a persistent SSH identity. HA uses the backend's API token;
the private SSH key never belongs in an HA config entry or diagnostic export.

## Does installing updates reboot the host?

No. Reboot is always a separate explicit action. An update can report that a reboot
is needed. A repair prompt still requires confirmation and current-state validation.

## Does polling install anything?

No. HA coordinator polling reads status. The explicit native check action does
contact hosts and refresh APT metadata; it does not install packages or reboot.

## Why is an old failure still visible after success?

Latest job and latest failed job are separate records. This preserves useful
history without making a historical error the current connectivity state.

## Why are installation images public?

The Home Assistant App must pull its exactly versioned multi-architecture image
without asking users for registry credentials. Publication is a separate gated
release process; see [releases](../maintenance/releases.md).

## Can I use another package manager or manage VMs?

The built-in provider currently targets Debian/Ubuntu APT. Other package managers,
VM lifecycle and backup orchestration are roadmap ideas, not promised current
features. See [product scope](../product/scope.md).
