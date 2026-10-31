---
title: English Wiki and runner follow-up review
status: draft
updated: 2026-10-31
tags: [review, wiki, documentation, ci, security]
---

# English Wiki and runner follow-up review

## Authorization and scope

The owner confirmed `make` was installed and explicitly authorized an English Wiki
with Technical, Product and User sections, plus useful additional sections. The
existing public Wiki and its visibility were checked through GitLab. No permission
or mirror setting is changed. Only public-safe explanatory documentation is published.

The reviewed source set contains 26 English pages and one custom sidebar under
`docs/wiki/`: User Guide (installation, configuration, hosts, jobs, tasks, recovery,
troubleshooting, FAQ), Product (scope, behavior, roadmap), Technical (architecture,
HA, API, execution, persistence, security, development) and Maintenance (contribution,
documentation, releases). Navigation works locally with relative Markdown links.
Publication maps Wiki links to slugs and detailed normative references to an exact
source revision. The repository is the maintenance source; Wiki pages are snapshots.

No runtime behavior, public API, persistence model or architecture boundary changes.
The original Obsidian vault, accepted ADRs and historical reviews remain intact.
These pages explain and link existing contracts; they do not replace or silently
translate accepted decisions. A new runtime ADR is unnecessary.

## Actual CI diagnosis

The owner's retried job 396 on MR pipeline 354 reached `make quality`. It passed
287 tests including browsers, with line coverage 98.18% and branch coverage 95.32%,
plus format/lint/types and documentation links. It then failed at:

```text
uv run python scripts/check_security_exceptions.py
Expired security exceptions: SE-2026-001
```

The runner is working; missing `make` is no longer an active blocker. The subsequent
pip-audit recipe and final privacy target were not reached in that combined run.
No expiry, ignore, gate or coverage requirement was weakened.

Official [HA 2026.10 release notes](https://www.home-assistant.io/blog/2026/10/07/release-202610/)
and [2026.10.4 package metadata](https://pypi.org/pypi/homeassistant/2026.10.4/json)
were checked for a compatible remediation. Its cryptography pin is fixed relative
to the expired exception, but it still requires Pillow 12.3.0, which the earlier
unfiltered audit reported as vulnerable. A version bump alone would not clear the
whole audit. No unsupported global override, untested stack migration or renewed
exception was introduced. Dependency remediation remains T-018 and an MR blocker.

## Validation and publication record

`UV_CACHE_DIR=/tmp/homelab-uv-cache make quality-fast` passed: Ruff formatting/lint,
strict Mypy for 43 runtime modules, zero missing local documentation file targets,
and the public-data scan. `git diff --check` passed. The new prose uses synthetic
examples and public project/upstream references only; no real deployment data.

No Python/runtime implementation changed, so the already successful local and CI
287-test runs were not redundantly repeated for this prose-only follow-up. The full
gate is still red for the documented audit failure; release/container/HA validators
have not been newly executed or claimed successful. `make release-check` would
include the same known failing gate.

The Wiki publication is a manual use of the existing authorized GitLab API, not a
new production dependency or automatic publication service. Exact remote content,
page inventory and rendered navigation are verified after publication. The published
revision marker identifies the snapshot independently of later MR bookkeeping.
