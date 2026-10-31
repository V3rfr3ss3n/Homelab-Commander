---
title: Workflow modernization review
status: draft
updated: 2026-10-31
tags: [review, workflow, documentation, quality]
---

# Workflow modernization review

## Scope and evidence

T-034 modernizes the existing agent/development workflow. Runtime APIs, storage,
entity boundaries, dependencies and coverage thresholds are unchanged; no new
architecture decision is needed. `homelab_updates`, the App slug and `/api/v1`
remain intact. No managed hosts were contacted or changed.

The working tree already contained the T-033 documentation-link checker, three
regression tests, Docker-context exclusions and related notes. These were preserved,
reviewed and validated with this change; they are included in the MR rather than
silently discarded. The branch was advanced to the current GitLab `main` before
implementation, retaining its dependency and Python-image updates.

Implemented: compact shared agent rules with task-based reading; explicit
issue/change/bug/question handling; task-scaled planning; a Markdown documentation
index; a public-safe inventory and Wiki handoff; `quality-fast` composed from
existing checks; and GitLab MR/main CI reusing the complete local quality gate.
No new GitLab integration, mirror, visibility change or external Wiki publication.
Existing GitHub-specific validators/publication remain separate.

## Technical verification

`pyproject.toml`/`uv.lock` on the refreshed base already pin Home Assistant
`2026.8.3`, frontend `20260826.0`, Ruff `0.16.4`, FastAPI `0.141.1`, Uvicorn
`0.52.4`, ansible-core `2.21.3`, Mypy `2.3.1` and Playwright `1.62.0`.
The minimum Python remains `3.14.2`; local tests used `3.14.8`.

Official [HA release notes](https://www.home-assistant.io/blog/2026/08/05/release-20268/)
and [published metadata](https://pypi.org/pypi/homeassistant/2026.8.3/json) were
checked. That patch still pins `cryptography==48.0.1`, so it does not resolve
SE-2026-001. No untested monthly HA migration or global override was introduced.

The new GitLab and existing GitHub quality jobs pin `uv 0.13.6`, verified against
[official package metadata](https://pypi.org/pypi/uv/0.13.6/json) and used locally.
The separate development-lock uv dependency and Docker builder pin remain older;
changing the HA-constrained lock/runtime build needs separate compatibility and
container verification. No production dependency was added.

## Actual local checks

Dependencies restored with `UV_CACHE_DIR=/tmp/homelab-uv-cache uv sync --frozen`;
`UV_CACHE_DIR=/tmp/homelab-uv-cache uv lock --check --offline` passed unchanged.
The initial sandboxed sync could not resolve package hosts; the authorized
network-enabled retry succeeded.

```sh
UV_CACHE_DIR=/tmp/homelab-uv-cache ANSIBLE_LOCAL_TEMP=/tmp/homelab-ansible-tmp PYTEST_ADDOPTS='--timeout=30' make quality
```

- Ruff format: 123 files passed; Ruff lint passed.
- Mypy strict: 43 runtime modules passed. Additionally,
  `UV_CACHE_DIR=/tmp/homelab-uv-cache uv run mypy --strict scripts/check_doc_links.py`
  passed.
- Pytest: **287 passed**, including Chromium/HA-panel tests and T-033 regressions;
  no skipped tests. Line coverage **98.18%**, branch coverage **95.32%**.
- `make docs`: zero missing public file targets. External URLs, Wiki permission
  checks and heading anchors are outside this offline checker.
- `make audit`: failed on expired `SE-2026-001`; its following pip-audit command
  was not reached. Exceptions and ignore lists were not extended or weakened.
- `UV_CACHE_DIR=/tmp/homelab-uv-cache make privacy`: passed separately because
  audit stops the combined gate before privacy.
- `UV_CACHE_DIR=/tmp/homelab-uv-cache uv run pip-audit --skip-editable`: failed,
  reporting 88 advisory rows across ten packages in the installed development
  environment (including duplicate advisory rows). This is not a production-image
  audit. Affected packages: aiohttp, certifi, cryptography, filelock, msgpack,
  multidict, pillow, pyjwt, urllib3 and uv. Some need a newer HA compatibility
  baseline; do not suppress them merely to green the pipeline.
- GitLab `glab ci lint .gitlab-ci.yml --include-jobs` and
  `glab ci lint .gitlab-ci.yml --dry-run --ref main --include-jobs`: valid.
  One existing runner was online; actual MR pipeline results remain independent
  of static configuration validation.

The final `UV_CACHE_DIR=/tmp/homelab-uv-cache make quality-fast` passed all
constituent checks. GitLab CI lint/dry-run was repeated successfully after the
uv pin changed. `git diff --check` passed; staged changes and new files were
reviewed for secrets, infrastructure values and personal paths. Only synthetic
fixtures and public upstream references were added.

## Actual MR pipeline

The first MR pipeline failed before the gate: the existing runner uses a shell
executor and cannot run `apt-get`. The configuration was corrected to bootstrap
uv from official SHA-256-pinned archives in an isolated workspace directory,
with no system-package installation on shell runners. A second attempt revealed
missing `ensurepip`/venv support; the archive bootstrap removes that prerequisite.
Only disposable root containers install OS packages. Shell-runner
prerequisites are documented in the quality guide. The failed initial pipeline
is retained as evidence; a valid YAML/dry-run did not prove executor compatibility.
The exact final archive bootstrap was executed in an isolated temporary directory:
SHA-256 verification passed and the installed binary reported uv 0.13.6 on AMD64.
The AArch64 hash was read from the same official release metadata; execution on
AArch64 is not claimed.

## Remaining release/merge gates

The complete local gate is **red**, so T-033/T-034 remain open and the MR is a
Draft. Resolve the dependency findings on a compatible tested stack, then rerun
`make quality`; do not merge merely because the functional suite passes.

`make release-check` was not run separately: it includes the same failing quality
gate. `docker info --format '{{.ServerVersion}}'` found no running local daemon;
AMD64/AArch64 builds and `scripts/validate-container-image.sh` were not run.
Hassfest, HACS and Gitleaks history scanning were not run locally (no Gitleaks
binary; HA/HACS validators remain in existing GitHub workflows). Their current
success is not claimed. No release, image publication or live installation was
attempted.

The Wiki is enabled but empty on the public project. The proposed navigation is
prepared in the repository; external migration and any protected documentation
space still need owner approval and actual permission checks. Existing ADRs and
the Obsidian vault remain in place.
