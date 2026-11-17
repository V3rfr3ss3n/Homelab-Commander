---
title: Reusable operator component contracts
status: proposed
updated: 2026-11-16
tags: [design, frontend, contracts]
---

# Component contracts

## List ownership

One feature inventory owns its search, filters, ordering, paging and selection.
[ListState](../../backend/homelab_backend/frontend/list-state.js) is the first shared
mechanic: identity selection (maximum 500), page boundary, sorting and request
revision. It has no DOM, HTTP or permissions. The Resources controller injects the
existing request/error/session functions through `operatorUI`. Pure
[resource rendering](../../backend/homelab_backend/frontend/resource-view.js) receives
facts and escaping; backend rule evaluation is never duplicated in JavaScript.

The existing resource inventory is reused for viewing, membership selection and tag
editing. The group manager lists **definitions**, not a second resource inventory.
Preview is a labeled textual result, not a competing selectable table. The legacy
operational Host list remains in its existing view during this limited slice; later
migration reuses these mechanics rather than copying its business logic.

| Mechanic | Current Resources behavior | Future reusable contract |
| --- | --- | --- |
| Columns | Selection, name, type, system, tags | Domain-specific columns; no universal schema |
| Search | Name substring, explicit Enter/Search | List-owned, bounded query |
| Filters | Collapsed type/tag/group; badge and × | Badge counts active constraints; clear stays local |
| Groups | Searchable paged definition picker | Dynamic membership evaluated on server |
| Saved views | Not implemented; no decorative selector | Reset paging, explicitly reconcile/clear selection |
| Sort | Name/type headers, server ordering before paging | Accessible direction, stable ID tie-breaker |
| Paging | 25 rows, full matching count, previous/next | No client-page-only sort or guessed totals |
| Selection | Explicit immutable IDs, page-only select-all | Never infer all matching rows from one checkbox |
| Details | Single resource button opens side panel | Context owns actions; no duplicate toolbar |
| Errors | Stale/unavailable status + read-only Retry | Never report failure as empty success |

## Selection lifecycle

- A name button opens details without selecting a target; checkbox selects metadata
  membership. Selection never starts jobs or grants permission.
- Select-all adds/removes **this page** only. The summary includes off-page selected
  count. Atomic bounds reject a selection larger than 500 rather than truncating it.
- Search, filter, sort and page changes retain explicit IDs, display hidden count,
  and never add targets. Clear selection clears all pages; × clears filters only.
- Top-right context includes resource filters and selected count. Its Reset clears
  filters, sort, page, selected IDs and editor to restore the default inventory.
- New manual group starts from explicit selection; editing replaces it with stored
  members. Saving is explicitly a complete membership replacement. Missing/tombstoned
  members cause the existing safe conflict, never silent target substitution.
- Smart rules do not include checked rows as overrides. The editor says so.
- Leaving Resources or logout/session expiry clears selection, filters, dialogs and
  drafts. Reload does not persist unsaved selection. Backend metadata persists.
- Request revisions reject late list responses; preview revisions change with every
  rule/input/selection edit. Session/navigation epochs reject late writes/readback.
  No automatic retry of metadata writes or Host actions is introduced.

## Detail panels, dialogs and operations

Resources' side panel is either resource details/tag editing or a focused group
editor. Manual member selection uses the same table. Smart syntax is progressive
help; the manager is a native modal with bounded search/pages. Delete confirms that
only group metadata is removed. Add Resource invokes the existing Host setup; other
creation providers are absent because they have no supported UI workflow yet.

Current Host update/reboot/task controls remain untouched and use the same backend
checks. The target Operations design uses the right-hand context as its sole action
surface; moving current row controls is a later slice, not claimed here. Future
standard/custom/provider operations use an action descriptor with label/icon,
compatibility, disabled reason, input schema, risk and result-job link; backend
capability/policy decisions stay authoritative. Quick update remains available;
package review is optional unless required by provider or policy. No unsafe pacman
partial updates, unreviewed AUR execution or group execution (#44/#46) is supplied.

## Ownership and testing

The shell owns navigation/session and top-right context. The feature controller owns
its drafts/request lifetimes. The shared client owns CSRF, safe error mapping and
transport. Rendering owns text escaping and semantics. Backend application services
own membership and eligibility; adapters own external validation and persistence.
Extract a shared component only when these small contracts demonstrate reuse; do
not add a generic component framework, dynamic plugin loader or build pipeline.
