---
title: ADR-0015 Stable browser-side website icons
status: accepted
date: 2026-11-10
tags: [architecture, ui, security, persistence]
---

# ADR-0015: Stable browser-side website icons

## Context

Rebuilding host rows on every refresh recreates images, including failed HTTPS
loads. This causes repeated requests and visible flashing. A fixed `/favicon.ico`
path misses modern SVG/PNG assets, including sites with valid HTTPS certificates.
An external service may also reject embedded images even if top-level navigation
works. Browser image errors do not reliably distinguish TLS, access policy or 404.

## Decision

Extend ADR-0013's browser-only icon policy. Preserve the same anchor/image DOM
nodes by host, website list position, URL and optional icon URL for the connected
page. Render placeholders in rows and transplant cached nodes after rendering.
Keep the initial visible until an image loads; retain unavailable state after
failure. Refreshes and view changes do not recreate/retry those images, including
no-store image responses. Duplicate bookmarks remain independent. Remove stale
entries when a bookmark disappears/changes and cancel/clear the cache on logout.
Create new image loads only in Dashboard/Hosts/host-detail views.

For a default icon try exactly these bounded same-origin paths in order:
`/favicon.ico`, `/favicon.svg`, `/favicon.png`, `/apple-touch-icon.png`,
`/favicons/favicon-32x32.png`. Exhaustion leaves a stable initial and explanatory
tooltip. Never downgrade HTTPS to HTTP. Do not fetch/parse website HTML or manifests,
proxy through the backend, use third-party icon services, or weaken TLS/CSP.
An explicit **Retry saved website icons** in Edit host clears that host's page cache;
it uses saved inventory, not unsubmitted form values. Reloading the whole page also
starts a new cache. There is no persistent browser storage of images or metadata.

Allow optional `HostWebsite.icon_url`, a validated HTTP(S) image URL without
userinfo, as a single explicit override instead of path probing. It may point at
another operator-selected origin, so the UI/docs explain the additional browser
contact. Render images with no referrer and no Commander API/CSRF headers. Browser
certificate, cookie, privacy and external access controls still apply. A challenge
page is not an image and is never bypassed.

The field uses the existing websites JSON column; no schema migration, identity
change or production dependency is required. Absent/null overrides serialize to
the legacy two-field shape. Existing `name | website` form lines remain accepted;
`name | website | direct icon URL` adds an override. Editing preserves that value.

## Validation and limits

Synthetic HTTP/HTTPS browser routes reproduce missing fallback and assert image
node identity plus request counts across refreshes/view navigation, explicit retry,
blocked origins, duplicate bookmarks and custom URLs. Models reject schemes and
credentials, round-trip saved overrides and preserve legacy JSON. No real service
is contacted. Chromium covers the shared browser path, not Vivaldi-specific privacy
settings or a real Cloudflare deployment. A blocked endpoint still needs a publicly
loadable icon URL or adjusted operator-controlled access policy.
