---
title: ADR-0011 Direct Backend Sidebar
status: accepted
date: 2026-10-31
tags: [architecture, home-assistant, ui, security]
---

# ADR-0011: Direct Backend Sidebar

## Context

The HA summary duplicates hosts and jobs already shown in the backend UI and adds
an unnecessary click before administration. The sidebar should open that UI directly.
This supersedes the summary UI decision in [ADR-0007](0007-home-assistant-main-panel.md)
and the extra management-link step in [ADR-0009](0009-supervisor-native-backend-discovery.md).
Their administrator boundary and discovery rules remain applicable.

## Decision

Keep the administrator-only `/homelab-updates` panel and its existing ownership and
unload lifecycle. Its component immediately replaces the current location with the
configured management destination. A matching discovered local App uses HA's
`/app/<identifier>` route, preserving Supervisor Ingress authentication and HA
navigation. Remote backends open their configured HTTP(S) URL in the current tab
and retain standalone UI authentication. Replacement avoids a Back redirect loop.
The component accepts only local same-origin App routes or absolute HTTP(S) URLs
without userinfo. It never forwards the config-entry token or starts a host action.

Retain existing admin-only WebSocket commands for compatibility; the sidebar no
longer subscribes to them. Do not embed remote UI in an iframe: its existing
`frame-ancestors 'self'` policy and strict session cookies remain unchanged.

## Consequences

There is one management overview. Remote users leave HA and can return with Back;
the configured URL must be browser-reachable and may require UI login. Local users
remain in HA's Ingress experience. No data migration or production dependency is
required. Multiple native entries continue to share the first loaded entry's panel.
Browser tests use synthetic destinations and verify direct navigation and Back;
existing boundary tests continue to verify admin-only commands.
