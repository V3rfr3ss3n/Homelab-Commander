---
title: Development, tests and CI
status: active
updated: 2026-10-31
tags: [wiki, technical]
---

# Development, tests and CI

Use the versions recorded in `pyproject.toml` and `uv.lock`. Restore the frozen
environment with `uv sync --frozen`. The supported CI Python series is 3.14;
an open-ended project minimum is not a request to test with an unreviewed next series.

## Useful commands

| Command | Purpose |
| --- | --- |
| `make browser-install` | Install Chromium for local browser tests |
| `make quality-fast` | Existing format, lint, strict types, doc links and privacy checks |
| `uv run pytest tests/test_doc_links.py --no-cov` | Example focused regression check |
| `make quality` | Complete local gate with tests, independent coverage checks and audit |
| `make release-check` | Full quality gate plus release-readiness checks |

Focused feedback is not full acceptance. Do not run `quality` then `release-check`
on unchanged code merely to repeat the same complete suite. Both line and branch
coverage must independently reach 95%.

## GitLab runner

The MR/main pipeline invokes the same Makefile. Shell runners must already provide
Python 3.12+, Make, Git, OpenSSH and Chromium system libraries. The job checks basic
prerequisites early and installs SHA-256-verified uv into its workspace. It does not
install OS packages on a persistent shell runner. Disposable root containers may
install their own required packages. No privileged runner or Docker socket is needed
by the integration.

If a job stops before tests, inspect its exact failed command. Security findings
or expired exceptions remain blocking even when tests pass. SE-2026-001 was resolved
by updating the dependency graph; the expiry mechanism remains and the audit has
no advisory ignores. Never remove an expiry check to hide an unresolved finding.

The current development baseline is HA 2026.10.4 with its matching frontend/plugin.
A single reviewed replacement installs fixed Pillow 13.0.0 in the development graph;
Pillow is absent from production. See [ADR-0010](../../02-architecture/adr/0010-secure-test-dependency-replacements.md)
for compatibility evidence and the criterion for removing that replacement.

## Test boundaries and additional validators

Unit, adapter, HA lifecycle and real headless-browser tests use synthetic data,
controlled time/network and fake execution adapters. They never run actual managed
host operations. GitHub retains independent Hassfest, HACS, image and secret-scan
workflows. Their success must be checked separately from local tests or CI lint.

[Quality gates](../../03-development/quality-gates.md) define full policy and
[code rules](../../03-development/code-rules.md) define implementation conventions.
