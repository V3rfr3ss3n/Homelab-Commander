---
title: Groups and tags
status: proposed
updated: 2026-11-16
tags: [groups, inventory, tags]
---

# Groups and tags

Open **Resources → Inventory & groups** to organize existing inventory. The Hosts
view keeps its existing direct maintenance workflow. Groups never grant access or
run updates, reboots or tasks. **Add Resource** currently opens the supported Host
setup; future service/provider creation is not offered.

## Discover and select

Search resource names. **Filters** reveals type, tag and group constraints; choose
a group from its paged/searchable manager to view its members in the same inventory.
Name and Type headers sort the entire matching set before paging. × clears filters;
the top-right Reset also clears selection, sort, page and an open editor.

Checkboxes select explicit resource IDs for manual group membership. Select-all
means **the current page only**, not all matches. Selection remains across filters,
sort and pages, with an explicit off-page count. **Clear selection** removes every
selected ID. Leaving inventory or disconnecting clears unsaved selections/drafts.
A stale/failed load is visibly unavailable and cannot accept new selection; retry
is read-only. No automatic write/action retry is performed.

## Groups and tags

Choose **New group** from a selection, enter a name, then Preview membership and
Save group. The side editor uses this same table for manual membership. Editing a
manual group loads its complete selected IDs; Save replaces the whole membership.
Smart groups use All/Any positive rules instead; checked rows are not overrides.
Preview does not save anything. Editing retains group identity; **Manage groups**
provides edit/delete, and deletion removes group metadata, not resources or tags.

Open a resource by its name to edit comma-separated tags in the contextual panel.
Tags use lowercase letters, digits, `_` and `-`. Save tags replaces that resource's
tag set. Hosts link to their existing detail/actions; no group bulk operations exist.

## Rules and limits

Rules match type, exact distribution, tag, last observed status, versioned capability
or an incident relationship to a specific resource UUID. Unknown facts do not match;
services do not inherit Host health. Current capability evidence is unavailable,
so capability rules match no resources. Status may be stale. Examples: `tag` =
`production`, `distro` = `Debian`, `status` = `security_updates`. Capability syntax
is `packages.update.full@1`; the name alone is not proof of support.

Limits: 16 rules, 500 explicit members, 32 tags/resource, 5,000 resources/20,000
relationships per bounded evaluation. Preview labels its first 100 results and
complete count; saved group members can be paged through the inventory. Missing
members/invalid rules/exceeded budgets fail safely, never becoming permission or
an empty success. See [ADR-0024](../../02-architecture/adr/0024-bounded-resource-groups.md).
