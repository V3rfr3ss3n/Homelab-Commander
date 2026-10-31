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

If a job stops before tests, inspect its exact failed command. If all tests pass
and `Expired security exceptions: SE-2026-001` follows, the environment is working:
the dependency-security gate is the blocker. Keep the job red until a reviewed
compatible remediation exists. Do not remove the expiry check.

## Test boundaries and additional validators

Unit, adapter, HA lifecycle and real headless-browser tests use synthetic data,
controlled time/network and fake execution adapters. They never run actual managed
host operations. GitHub retains independent Hassfest, HACS, image and secret-scan
workflows. Their success must be checked separately from local tests or CI lint.

[Quality gates](../../03-development/quality-gates.md) define full policy and
[code rules](../../03-development/code-rules.md) define implementation conventions.
