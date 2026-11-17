---
title: Development, tests and CI
status: active
updated: 2026-11-18
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

The current development baseline is HA 2026.10.4 with its pinned test plugin and the explicitly tested frontend pairing below.
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

## Synthetic local UI preview

Run `uv run python -m homelab_backend.preview` to serve the preview on loopback
port 8100. It creates disposable synthetic inventory/history for each launch and
always injects the fake executor, even for newly entered addresses or custom
commands. It does not read production runtime configuration or execute SSH/Ansible.
Stop and restart it to reset the sample data. Never supply a production data path
to the preview factory used by tests.

VS Code launchers should use module `homelab_backend.preview`. An older local
`.vscode/preview_backend.py` can be a thin wrapper calling that module's `main`;
keep no independent mock implementation there. After updating the source, stop
and restart the existing preview process and reload the browser UI. Editing the
file does not replace a Python class already loaded by a running debugger.

The versioned preview and browser regressions share the same adapter. A single
`vim` update changes the seeded 12/4 counts to 11/3 and removes the vim row. A
subsequent check preserves that result. The simulator keeps its own session state
so stale inventory objects cannot resurrect removed packages or restart warnings. Selected/full updates remove exactly the
simulated scope, and contradictory count/row snapshots are rejected before storage.

## Local stabilization acceptance (#62 / #63)

From the repository root, start the existing disposable synthetic preview:

```bash
uv sync --frozen
uv run python -m homelab_backend.preview
```

Open `http://127.0.0.1:8100`. All host actions are simulated, including arbitrary
addresses entered in this preview; data and its SSH identity are temporary.
Stop the preview before starting a second instance on the same port. VS Code's
existing local launcher uses this versioned module too.

To reproduce one history failure, start instead:

```bash
uv run python -m homelab_backend.preview --history-failure-once
```

The first filtered history request fails with a synthetic HTTP 503. Open its
technical details, copy the report and choose **Retry history**; seven days of
seeded history return without resetting data. The fault option exists only on the
explicit preview launcher, never on the normal backend entrypoint.

Local acceptance:

- Graph and table each show 14 seeded jobs over seven days; filter/reset both.
- The historical failed card is red and explicitly says failed.
- A history failure displays unavailable rather than zero; retry recovers.
- In browser developer tools, go offline and refresh: existing history is stale.
  Change filters while offline: history is unavailable. Restore the network and
  retry; the view recovers. Do not use this procedure on production host actions.
- Copy diagnostics: safe code, time, operation and reference are present; host
  addresses, tokens and raw response/log content are absent.

`make quality` remains the complete local merge gate, including independent 95%
line/branch thresholds. This branch does not change version, publish an image or
request a release. Local approval precedes merge; a development release requires
a separate owner request.

## Dependency maintenance baseline

The registry follow-up tests HA Core 2026.10.4 with frontend 20261028.5, HTTPX2 2.16.0,
Playwright 1.65.0, Mypy 2.4.1 and Ruff 0.17.4, using one frozen lockfile. This is a tested
pairing, not a claim that frontend/Core release numbers match. Runtime pins advance
to FastAPI 0.162.4 and ansible-core 2.22.0. FastAPI telemetry/exporters are explicitly
disabled and the callback suppresses no_log payloads. Reviewed Builder/setup-uv
actions remain SHA-pinned. See the [review](../../05-reviews/2026-11-15-registry-foundation-review.md).

## Resources UI foundation (#43 / #69)

In the synthetic preview, use Resources → Inventory & groups. Check selection across
pages, Filters/group picker, name/type sorting, tag details and manual/smart group
editing. Use the same top-right Reset to return to default inventory. Existing
Hosts, Tasks and Jobs remain regression checks. The
[design migration plan](../../design/migration-plan.md) records scope and rollback;
[component contracts](../../design/component-contracts.md) define selection/lifetimes.
Frontend behavioral tests run in Chromium; Python coverage percentages are not a
JavaScript branch-coverage claim. New Wiki sources await owner snapshot approval.

## Resource jobs (#44)

Run `uv run pytest backend/tests/test_resource_jobs.py backend/tests/test_resource_jobs_browser.py --no-cov`
for target snapshots, upgrade/rollback, conflict ordering, cancellation, safe restart,
API/auth/provenance and browser recovery. Only synthetic operation handlers are
injected; production has no generic execution binding. `execution/` owns scope values,
resource locks, target resolution and the SQLite job adapter; `jobs.py` remains the
legacy-compatible worker. Full `make release-check` remains required for review.


## Central policy acceptance (#46)

Use `uv run pytest backend/tests/test_policy.py backend/tests/test_approvals.py --no-cov`
for restricted-subject, API/task/automation bypass, expiry, immutable-scope,
concurrent one-use and schema-13 upgrade/rollback checks. All providers and credentials
are synthetic. Generic test handlers now require an explicit registered operation
policy; a readiness callback alone is insufficient. Runtime still has only the
existing admin authentication paths. Full `make release-check`, independent 95%
line/branch thresholds and remote CI remain required before review.


## Linux provider boundary tests

Run `uv run pytest backend/tests/test_linux_boundary.py backend/tests/test_automation.py
backend/tests/test_jobs.py backend/tests/test_packages.py --no-cov` as one shell
command for focused provider, APT, job and status regressions. Then run the complete
`make release-check`; focused tests do not replace coverage or browser gates.
The independent synthetic package provider lives only in tests, overrides all
execution and is never registered in the production app or local UI preview.
The preview keeps its existing disposable simulation; unchanged GUI behavior is
expected for this internal extraction. No real SSH or host action is part of tests.


## Cross-manager contract suite

Run `uv run pytest backend/tests/test_linux_matrix.py --no-cov` for the reusable
APT/synthetic-provider scope harness, strict observation invariants, missing-signal
cases for all planned manager families and matrix/document consistency. Raw native
outputs and execution remain untested for absent providers. The
[compatibility matrix](../../02-architecture/linux-provider-matrix.md) records
version/architecture/fixture prerequisites before enabling each future provider.
The full release gate and independent 95% line/branch thresholds still apply.
