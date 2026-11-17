---
title: Linux package provider boundary review
status: in-review
updated: 2026-11-17
tags: [review, linux, architecture, providers, compatibility]
---

# Linux package boundary (#45)

## Implemented and preserved

The owner-approved policy foundation was merged in !42 / PR #72 at `425e619`.
This follow-up extracts package scope/status/facts, workflows, transport/provider
ports, APT adapter and fixed task probe into `linux/`. Shared executor result types
move to `execution/results.py` with compatibility exports retained. No production
dependency, framework replacement, migration, privilege, UI or API change is added.

APT remains the only production provider, stored as `debian_apt`. Its original
methods and the fixed Debian task-probe script are AST-identical to the merged
base. Cache/update semantics, count/security/detail limits and post-update measured
status remain. Versioned capability bindings validate immutable typed requests and
results, distinguish unsupported targets and never infer readiness or permission
from provider registration. See
[ADR-0028](../02-architecture/adr/0028-linux-package-provider-boundary.md).

The independent synthetic provider is test-only, not an APT subclass. It traverses
the existing authenticated API, policy, immutable job scope, worker and SQLite
status path without provider-specific core changes. Its full update executes once;
unsupported individual/selected requests fail before transport without changing
counts. Authentication remains required and no reboot executes. Real second-package-
manager support and M1's eventual real-platform acceptance remain open for M2.

## Threat model and limitations

- Registry composition is trusted static Python, never an API-supplied import,
  executable or plugin. Production registers no synthetic provider.
- Package names/selections are bounded and validated; unsupported selection never
  widens to full scope. Existing policy and execution revalidation remain in force.
- Ansible JSON is normalized at the feature adapter; malformed status fails with
  a static error code, without raw parser exception or provider output in the error.
- Existing SSH isolation, bounded process lifetime/log handling, Host lock and
  no-replay recovery remain. No automatic retry, update or reboot is introduced.
- Normalized transport still uses fixed facts/list/stat conventions. A genuinely
  different platform may require another reviewed adapter; this test does not
  certify arbitrary package managers or custom-task probes.
- Capability assessment is inert and reports unprobed Host readiness unavailable.
  It neither probes nor grants execution; Info capability strings remain compatible.

## Verification

- Focused original automation/jobs/packages plus the independent provider tests:
  75 passed before the final untrusted-value test was added.
- `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check`: **584 passed** in
  119.03 seconds, **98.67% line / 96.21% branch coverage**. Ruff, strict Mypy
  (96 production files), standalone/Ingress browser and HA regressions, docs
  (0 broken links), audit (no known vulnerabilities), privacy and version alignment
  `0.3.0-dev.5` all passed. Both independent 95% coverage thresholds remain enforced.
- Remote GitLab/GitHub checks are recorded in the MR; local gate success does not
  replace those checks or certify real additional distributions.
- Tests use synthetic fixtures only. The injected fake module runner rejects every
  unknown command and forbids fallback to the real runner. No managed host is
  contacted and no actual SSH/Ansible update or reboot executes.

## Local owner acceptance

On `feat/linux-provider-boundary`, stop an old preview and run:

```sh
uv run python -m homelab_backend.preview
```

Open http://127.0.0.1:8100. Existing navigation, graph/table, package dialog,
single/selected/full simulated updates, measured remaining counts, job details and
review should behave as before. There is no new distribution selector or provider
screen. The preview remains the existing disposable simulation; restart it after
switching branches. Do not test with real hosts or credentials.

The deterministic provider boundary test is:

```sh
uv run pytest backend/tests/test_linux_boundary.py --no-cov
```

## Handoff and Wiki synchronization

The three affected Wiki sources (`technical/api`, `technical/architecture`,
`technical/development`) are maintained with the change. Existing remote page
metadata and content snapshots were checked and retained locally; no remote page was overwritten or published. The new source
snapshot awaits owner review/publication authorization; earlier page approvals do
not silently cover this feature. This divergence is explicitly tracked here and
in the MR. No release, tag or merge of this follow-up is performed.
