---
title: Dependency remediation and Wiki maintenance review
status: active
updated: 2026-10-31
tags: [review, dependencies, security, wiki, quality]
---

# Dependency remediation and Wiki maintenance review

## Scope and decision

The owner explicitly requested resolving the security blockers in the existing MR
and ensuring agents find and maintain the Wiki. The development baseline now uses
HA 2026.10.4, its declared frontend 20260930.5, test plugin 0.13.375 and refreshed
transitive pins. One reviewed replacement installs fixed Pillow 13.0.0 in the
development graph; production has no Pillow or HA dependency. Maintenance and the
upstream-pin divergence are documented in [ADR-0010](../02-architecture/adr/0010-secure-test-dependency-replacements.md).

SE-2026-001 is resolved, removed from the active expiry registry and retained as
historical documentation. All three advisory ignores are removed. Tests retain
expiry enforcement before/on/after the deadline. No exception was renewed and no
coverage/security gate weakened. The Docker builder now uses uv 0.13.6 and installs
only the frozen production graph; its post-sync cryptography override is removed.

HA's updated schema framework needs Probatio markers and schemas. A small typed
compatibility module retains Voluptuous for older installations without new
manifest requirements. Both validation paths and unrelated import-error propagation
are tested. Device classes use explicit framework modules on current HA and narrowly guarded
older public exports when the old release lacks those modules/classes. This retains
the published minimum rather than silently raising it; a direct check of official
HA 2026.8.3 sources identified the difference, and dedicated tests cover both forms
and propagation of unrelated import errors. A deprecated registry
lookup in an existing test now uses the supported config-entry helper.

`AGENTS.md` now explicitly starts with the English Wiki home and requires updating
relevant `docs/wiki/` pages with code, publishing the reviewed snapshot through the
existing authorized GitLab access and checking for remote edits. The Wiki's own
maintenance guide documents the same policy. No full-vault reading is reintroduced.

## Actual local verification

```sh
UV_CACHE_DIR=/tmp/homelab-uv-cache uv lock --upgrade
UV_CACHE_DIR=/tmp/homelab-uv-cache uv sync --frozen
UV_CACHE_DIR=/tmp/homelab-uv-cache uv lock --check --offline
UV_CACHE_DIR=/tmp/homelab-uv-cache ANSIBLE_LOCAL_TEMP=/tmp/homelab-ansible-tmp PYTEST_ADDOPTS='--timeout=30' make release-check
```

The final complete run passed: Ruff format/lint, strict Mypy for 45 runtime modules,
**301 tests**, **98.20% lines**, **95.37% branches**, documentation links, exception
expiry, unfiltered dependency audit, privacy and release-metadata checks. No skipped
tests. New regressions exercise HA/Pillow annotation, PNG/JPEG encode/decode and
resizing, the shipped image, both schema engines, broken import propagation and
security-exception expiry. Earlier runs found actual schema type incompatibilities
and a deprecated registry test call; both were fixed rather than suppressed.

Production was installed separately using:

```sh
UV_CACHE_DIR=/tmp/homelab-uv-cache UV_PROJECT_ENVIRONMENT=/tmp/homelab-production-audit uv sync --frozen --no-dev --no-editable
UV_CACHE_DIR=/tmp/homelab-uv-cache uv run pip-audit --path /tmp/homelab-production-audit/lib/python3.14/site-packages --skip-editable
```

The production dependency audit passed. The local first-party distribution is not
on PyPI and cannot be matched to public advisory data; it is covered by this
project's tests/review. Distribution inspection confirmed no HA, Pillow, pytest,
Ruff or pip-audit in that graph. Cryptography 50.0.1 comes from the shared lock.

## Independent checks and publication

GitLab CI and the existing GitHub validators must confirm the pushed source before
the MR is marked ready. Existing manual HACS/Hassfest triggers validate the same mirrored branch without
opening a second PR or publishing a release. Container
validation is explicitly `publish=false`; no image/visibility/permission change or
real managed-host operation is authorized by these checks.

The English Wiki's affected technical and maintenance pages are republished only
after comparing remote content with the previous reviewed snapshot. The exact
publication revision and independent CI results are recorded after verification.
A local green gate is not represented as an independently green pipeline.

## Independent baseline results

GitLab pipeline 363 passed the security-refreshed baseline. GitHub independently
passed Quality and the full-history Secret Scan on code/lock revision `7b44f24`.
The Container workflow passed AMD64 and AArch64 builds and runtime-contract checks
on that same revision with `publish=false`; publication/anonymous-pull jobs were
correctly skipped because no image was released. HACS and Hassfest passed on
`6168c4c` after a duplicate trigger was corrected. Both workflows already had
manual triggers; no new trigger is retained in the final change.

The final older-HA device-class fallback adds four regressions (301 total) and does
not change the backend graph, Dockerfile, manifest or publishing policy validated
above. The complete local `make release-check` was repeated after that change and
passed, including the unfiltered audit. GitLab CI must confirm the final pushed
integration revision before the MR is marked ready.

The Wiki was updated from reviewed revision `04b9623` to security baseline
`7b44f24`: all 27 remote contents were compared before writes and read back after.
A full-path API title preserves nested page slugs; the maintenance guide now records
that requirement. The final compatibility text is published with its source revision.

## Final validation and handoff

Final integration code revision `e2452cf` passed GitLab pipeline 364 and all four
applicable re-run GitHub validators:

- [Quality](https://github.com/V3rfr3ss3n/Homelab-Commander/actions/runs/41212024170)
- [Secret Scan](https://github.com/V3rfr3ss3n/Homelab-Commander/actions/runs/41212026159)
- [Hassfest](https://github.com/V3rfr3ss3n/Homelab-Commander/actions/runs/41212028113)
- [HACS](https://github.com/V3rfr3ss3n/Homelab-Commander/actions/runs/41212030109)

The unchanged backend/lock/Dockerfile passed the earlier
[AMD64/AArch64 container validation](https://github.com/V3rfr3ss3n/Homelab-Commander/actions/runs/41210991145).
No redundant container rebuild was needed for subsequent integration-only fallbacks.
All 27 Wiki pages were compared and read back exactly at revision `e2452cf`; nested
paths remain intact. The Wiki maintenance guide and AGENTS agree on source ownership
and the duty to maintain/publish relevant pages. No unexpected remote edits existed.

The final follow-up commit updates only these review/TODO records. GitLab reruns the
full gate on that handoff commit before the MR is marked ready; no skip flag is used.
There are no unresolved dependency findings or active security exceptions. The
maintained Pillow replacement and its test scope remain an explicit limitation,
not an advisory waiver. Release publication and fresh live installation remain
separate post-merge work; neither was performed or claimed by this MR.
