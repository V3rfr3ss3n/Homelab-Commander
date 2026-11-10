---
title: Stable website icons and HTTPS fallback
status: review
date: 2026-11-10
tags: [review, ui, security, regression]
---

# Stable website icons and HTTPS fallback

## Evidence and implementation

The existing renderer replaces image elements at every refresh and only attempts
`/favicon.ico`. A synthetic HTTPS regression fails before changes when its icon is
available only as SVG. The owner reports trusted HTTPS behind Cloudflare, so a
certificate error is not assumed. Preserve per-bookmark image nodes and failures,
try five bounded paths, and accept an explicitly configured direct icon URL.
Expose manual retry in Edit host. Duplicate bookmarks retain separate nodes.

## Security and compatibility

No new production dependency, schema migration, backend network proxy, third-party
icon discovery, TLS bypass or HTTPS downgrade. No referrer or Commander credential
headers are sent on image requests. The existing website JSON stores optional
validated HTTP(S) icon URLs; absent values preserve legacy serialized shape.
Changed/deleted bookmarks invalidate cache entries; logout cancels/clears them.
Cloudflare or browser access blocking still requires an accessible icon endpoint.

## Validation

HTTP/HTTPS routes and failures are entirely synthetic. Browser tests cover modern
paths, explicit custom images, duplicate links, persistent nodes/request counts
across refresh/navigation, manual retry, edit/save and invalid schemes. Model/API
tests cover credential rejection, persistence and legacy omission. Vivaldi itself
and real Cloudflare deployments were not contacted; Chromium covers the shared
browser behavior. `UV_NO_SYNC=1 make quality` passed with 367 tests, 98.43% lines
and 95.89% branches independently; formatting/lint/strict types/docs/audit/privacy
are included. The final gate also covers logout/reconnect and stale-cache cleanup.
