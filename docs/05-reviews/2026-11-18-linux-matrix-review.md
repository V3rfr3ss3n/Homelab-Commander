---
title: Linux capability matrix and evidence contract review
status: in-review
updated: 2026-11-18
tags: [review, linux, compatibility, contracts, testing]
---

# Linux matrix and evidence (#47)

## Delivered scope

Owner-accepted #45 was merged in !43 / PR #73 (`9ea2130`). This next block adds the
[capability/version matrix](../02-architecture/linux-provider-matrix.md), test-owned
machine-readable cases, reusable APT/synthetic-provider scope harness and internal
immutable qualified observations. See
[ADR-0029](../02-architecture/adr/0029-linux-evidence-and-compatibility-matrix.md).

Unknown, unavailable and unsupported security/reboot signals keep null and a safe
reason code; known zero/false remain real values. Contradictory counts, booleans
used as integers, duplicate/oversized rows and mutable raw structures fail safely.
A lossless-only legacy bridge refuses missing evidence; it never manufactures a
clean security/reboot result. The current APT API, persistence and HA schemas are
unchanged. No new provider is registered or selectable, no migration/dependency or
runtime privilege is added, and no automatic operation/retry is introduced.

## Evidence boundaries and remaining work

- The same injected-runner harness checks initial/fresh remaining counts and
  single/selected/full scope, unsupported denial before I/O, one mutation and no
  implicit reboot for actual APT and the independent synthetic provider.
- All seven matrix profiles have explicit operation/signal scenarios and required
  version targets. Those future-family cases are normalized semantic fixtures, not
  native DNF/Zypper/pacman/apk/Portage output parsers or real OS certification.
- Matrix docs and JSON rows are checked for consistency. Candidate versions do not
  imply latest release, vendor lifecycle or installed-platform support. Real
  manager versions, architecture, image digests and repository snapshots must be
  recorded before future activation.
- APT remains legacy origin-text/file heuristics, not comprehensive advisory or
  running-binary evidence. The bridge preserves these values without upgrading
  their provenance. Future providers must expose missing evidence through compatible
  API/UI/HA handling before activation; this block does not wire the new model in.
- #48 implements DNF/Zypper, including actual native synthetic parser/result-code,
  privilege, transaction and UI compatibility work. #49/#51 address pacman/apk;
  Portage feasibility and restricted AUR require separate decisions.
- Existing policy, canonical locks, revalidation and never-replay recovery remain
  authoritative. No cross-manager reboot-file assumption, partial pacman update,
  AUR execution or remote rollback guarantee is added.
- Primary references are linked in the matrix with the review date. Direct Arch
  page access was blocked; its primary search excerpt was available. No test or
  runtime performs an external documentation/advisory fetch.

## Checks

- Focused `test_linux_matrix.py`: **44 passed**.
- `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check`: **628 passed** in
  119.47 seconds, **98.69% line / 96.25% branch coverage**, independently enforced
  above 95%. New evidence contract: 100% statements and branches.
- Ruff, strict Mypy (97 production files), full standalone/Ingress and HA regression
  tests, docs (0 broken links), dependency audit (no known vulnerabilities), privacy
  and unchanged version alignment `0.3.0-dev.5` passed.
- Remote GitLab/GitHub CI results are recorded in the MR; local success alone does
  not replace those validators or real-platform certification.
Tests use manufactured package data and injected modules only. No managed host,
real SSH/Ansible package command, production snapshot or wall-clock sleep is used.

## Local acceptance

There is no new GUI in this design/test block. Stop an old preview and run:

```sh
uv run python -m homelab_backend.preview
```

At http://127.0.0.1:8100 check existing navigation, package dialog, simulated update
scopes/counts and job details/review. Existing behavior should remain unchanged.
Use disposable synthetic data only. The deterministic new suite is:

```sh
uv run pytest backend/tests/test_linux_matrix.py --no-cov
```

Review the matrix's supported/unsupported/unknown distinctions and future version
requirements. No real package-manager testing is requested from the operator for
this preparatory block. #48 comes next after this block's review.

## Wiki and release boundary

The previously accepted #45 snapshot (`technical/api`, `technical/architecture`,
`technical/development`, source `9ea2130`) remains unpublished: automatic approval
review required explicit permission for those exact pages. Permission was requested
separately; no remote change was made. Do not bypass that publication boundary.

Affected #47 sources: `technical/execution` and `technical/development`. Their new #47
snapshot awaits owner review before publication; remote edits must be checked
before any later synchronization. Earlier approvals cover only their named/reviewed
snapshots. The MR explicitly tracks this temporary divergence. No new merge, tag,
version bump or Dev release is requested or performed for this block.
