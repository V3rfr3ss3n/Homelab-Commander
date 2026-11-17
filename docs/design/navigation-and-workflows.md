---
title: Navigation and operator workflows
status: proposed
updated: 2026-11-16
tags: [design, navigation, workflows]
---

# Navigation and workflows

## Current review slice and route map

| Current entry/route | Current behavior | Target home |
| --- | --- | --- |
| Dashboard `#/dashboard` | History graph/table, notices, Host sidebar, last outcomes | Overview |
| Resources → Hosts `#/hosts` | Existing Host search/status/sort and deliberate operations | Resources / Operations |
| `#/hosts/<id>` | Host facts, package inspection, task/job context and actions | Resources details |
| Resources → Inventory & groups `#/resources` | All resource kinds, group/type/tag/name discovery, contextual tags/editor | Resources |
| Old `#/groups` | Compatible alias to resource inventory | Resources |
| Tasks `#/tasks` | Custom definitions, assignments/compatibility, explicit run | Operations |
| Jobs `#/jobs`, `#/jobs/<id>` | Filters, pagination, graph, detail/log/review/rerun | Activity |
| Header context, status, reload/disconnect | Existing global context plus active resource selection | Shared shell |
| Host/task/confirmation/package dialogs | Existing setup, explicit edits and safety review | Contextual workflows |

No new top-level Groups item. The Resources label replaces Hosts in primary
navigation without breaking Host bookmarks or its current direct workflow. An
in-area link exposes the existing, evolved registry inventory. The full compact
left sidebar with **Overview, Resources, Operations, Activity, Settings** is the
next independent shell slice; do not pretend this PR has migrated all screens.

## Hosting and state

Hash routes remain relative to document/Ingress prefix and contain no credentials.
New ES modules use relative same-origin imports and the same trusted-proxy asset
boundary. Standalone cookie/session recovery and UI CSRF remain; HA panel stays a
same-tab launcher without exposing its integration token. Existing Host context
continues across its tabs; Resources has its own explicit grouping selection and
includes it in the same top-right summary/reset.

## Workflows in this PR

1. Open Resources → Inventory & groups, search and reveal Filters if needed.
2. Choose a group from its searchable manager or filter type/tag. View members applies
   that group to the same resource table, including pagination and current rules.
3. Use a resource name for contextual tags or open its existing Host detail/actions.
4. Select rows and choose New group; preview without saving, then explicitly save.
   Smart groups use the rule editor instead of manual members.
5. Manage groups for edit/delete; deletion preserves resource identities and tags.

Quick maintenance remains check → update → job result, with deliberate reboot
confirmation and optional package selection. No mandatory planner or duplicate
operational action strip is added. Existing Tasks and Jobs are regression surfaces.

## Future placement, not functionality delivered

| Milestone | Placement / constraint |
| --- | --- |
| M1 | Resources registry/facets, Activity generalized jobs, backend policy contracts |
| M2 | Operations provider-aware Linux actions; optional safe package review |
| M3 | Resources → Services, Minecraft details/extensions/backups; optional Host link |
| M4 | Resources infrastructure discovery/relationships; direct Proxmox links, no UI clone |
| M5 | Contextual Operations/Integrations for Semaphore/n8n/events; UX provisional |
| M6 | Settings Agent Access/Policies; Activity approval queue/history; UX provisional |

Approval requests show expiry and are **not queued execution jobs**. Global queued
count means actual jobs only. Agents cannot approve themselves or bypass backend
checks. Future provider/scheduler/AI controls in illustrations are not actionable
requirements. Milestone scope remains in the [specification](../01-product/future-platform-specification.md#16-prioritized-development-roadmap);
[concepts](concepts/README.md) only illustrate possible layouts.
