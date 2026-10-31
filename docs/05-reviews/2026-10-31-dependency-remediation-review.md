---
title: Dependency remediation and Wiki maintenance review
status: draft
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
are tested. Device classes use explicit framework modules. A deprecated registry
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

The final complete run passed: Ruff format/lint, strict Mypy for 44 runtime modules,
**297 tests**, **98.19% lines**, **95.34% branches**, documentation links, exception
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
the MR is marked ready. HACS/Hassfest gain manual triggers so they can validate the
same mirrored branch without opening a second PR or publishing a release. Container
validation is explicitly `publish=false`; no image/visibility/permission change or
real managed-host operation is authorized by these checks.

The English Wiki's affected technical and maintenance pages are republished only
after comparing remote content with the previous reviewed snapshot. The exact
publication revision and independent CI results are recorded after verification.
A local green gate is not represented as an independently green pipeline.
