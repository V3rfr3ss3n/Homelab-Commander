---
title: Resources UI foundation review
status: proposed
updated: 2026-11-17
tags: [review, frontend, architecture, groups]
---

# Resources UI foundation — PR #68 / MR !40

## Scope and evidence

Owner request extends the existing groups branch with #69 preparation and integrated
Resources discovery. Upstream owner documentation commits through `8357fb4` were
fast-forwarded before editing; the existing unrelated `.gitignore` addition remains
unstaged and preserved. ADR-0024/0025 remain proposed. No merge, tag, version bump,
release, artifact publication, visibility change or deployment is authorized here.

Delivered: primary Resources label with existing Hosts view and Inventory & groups;
one evolved inventory for name/type/group/tag discovery, server-side name/type sort
before pages, explicit page selection and hidden-count summary, same top-right reset,
contextual tags/editor and paged group manager. Old group route remains an alias.
Add Resource calls the existing Host setup. Group preview still cannot execute.

Shared pure list-state/rendering ES modules receive an explicit shell bridge instead
of accessing mutable application globals. Static assets use a closed allowlist under
the existing Ingress source check. Semantic design tokens preserve the palette.
All six inspected reference PNGs have no metadata fields and remain non-binding;
concept discrepancies are documented. See [design index](../design/README.md) and
[architecture matrix](../design/architecture-inventory.md).

Preserved: schema-12 data/UUIDs, bounded smart rules, multi-membership and tags,
auth/CSRF, Host/job/task behavior, HA lifecycle and deliberate update/reboot paths.
No additional migration or dependency. No fine-grained policy/group bulk execution.

## Verification record

- `UV_CACHE_DIR=/tmp/hlc-uv-cache make quality-fast`: format/lint, strict Mypy
  (73 files), documentation links and privacy passed during implementation.
- Focused group/API/browser suite: `uv run pytest backend/tests/test_groups.py
  backend/tests/test_groups_browser.py backend/tests/test_backend_api.py --no-cov -xq`
  passed 38 tests before final follow-up assertions. Additional assertions verify
  delayed preview invalidation and tag draft preservation during refresh.
- Initial full gate correctly failed seven existing browser scenarios: the new
  creation button reused `[data-add-host]`, making locators ambiguous. The new entry
  now has its own ID and delegates to the same creation function; old tests were
  not weakened or filtered out. Targeted dashboard/group browser run passed six tests.
- Desktop and 390px screenshots from synthetic tests were inspected. The table owns
  horizontal scrolling and the context stacks above it. No images of real inventory
  were committed. Native dialogs/focus, loading/empty/error/recovery, selection bounds,
  stale navigation/preview and standalone/nested Ingress are covered.
- Final `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check` on 2026-11-17 passed:
  492 tests in 112.62 seconds, 98.74% independent line / 96.67% branch coverage,
  format/lint, strict Mypy (73 files), docs, privacy, audit (no known vulnerabilities)
  and version alignment at 0.3.0-dev.5. The final focused group browser suite passed
  four tests, including delayed previews, preserved tag drafts and Host creation mode.
- Exact-head remote CI results are recorded in the MR/PR handoff. Earlier successful
  commit checks do not count for this revised head.

## Owner acceptance (synthetic only)

Restart an older preview and run `uv run python -m homelab_backend.preview`; open
`http://127.0.0.1:8100`. Preview data is disposable and every Host action is simulated.

- [ ] Dashboard/graph, existing Hosts, Tasks and Jobs still work.
- [ ] Resources → Inventory & groups: search, collapsed Filters, sort headers and ×.
- [ ] Select rows, change filters, check hidden-selected count; top-right Reset returns
  default view. Select-all scope is the current page only.
- [ ] New manual group → Preview → Save; Manage groups → View members uses same list.
- [ ] Open resource name, save tags; smart group matching a tag previews without save.
- [ ] Edit/reload retains IDs/data; delete group retains resources/tags.
- [ ] Add Resource opens existing Host setup; cancel performs no operation.
- [ ] On mobile the editor stacks, table scroll stays internal, manager supports Escape.
- [ ] Optional browser offline/online against preview only: refresh shows unavailable/
  stale rows; Retry recovers. Leaving inventory or Disconnect clears unsaved drafts.

## Deferred work and risks

The full five-destination sidebar, migration of legacy Host/task/job lists, saved
views and client extraction are separate safe slices. #44/#46 must supply target
snapshots/conflicts/authority before group execution; #45 Linux extraction and #70
complete localization remain separate. Capability predicates currently match no
resources; persisted Host status is not fresh evidence. Concurrent metadata edits
remain last-write-wins; group definition and inventory reads are not execution-safe
snapshots. No generic provider support is implied. Python coverage is not JS coverage.

## Wiki publication boundary

The four Registry pages previously approved at `f3bfd64` stay published at that
snapshot. Updated group/UI Wiki sources in this PR remain **unpublished, pending
reviewed-snapshot authorization**. No remote edits were overwritten or new audience
activated. Owner review should approve the exact final source snapshot before the
normal guarded Wiki sync.
