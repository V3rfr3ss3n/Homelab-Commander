---
title: Groups and tags
status: review
updated: 2026-11-16
tags: [groups, inventory, tags]
---

# Groups and tags

The Groups workspace organizes existing resources. Groups do not grant access or
run updates, reboots or other operations.

Choose **New group**, enter a name and choose manual selection or smart rules.
For a manual group, select resources in the inventory below; selections remain
when paging or filtering. **Clear selection** removes the draft selection so you
can start again, including after a resource was deleted. A resource can belong to several groups. For a smart
group, choose **All rules** or **Any rule**, add the conditions, then use **Preview
membership**. Preview does not save anything. Save the group to keep its definition.
Edit retains its identity; Delete removes the group, not its resources or tags.

Rules match resource type, exact distribution, tag, last observed status, a versioned
capability or an incident relationship to a specific resource UUID. Tags are lowercase
words using letters, digits, `_` and `-`; edit comma-separated tags beside a resource
and choose **Save tags**. Resource filters support name, type and tag; groups have a
separate name search. A preview explicitly labels when only the first 100 matches
are displayed.

Unknown facts do not match. Service status is not inferred from its Host. No current
provider supplies the new capability evidence yet, so capability rules currently
match no resources. Status facts describe the last recorded check and may be stale.
Examples: `tag` = `production`, `distro` = `Debian`, `status` = `security_updates`.
Capability syntax is `packages.update.full@1`; it is not evidence of support by itself.
Relationship rules require the edge kind and the counterpart's UUID, not its name.

Limits are 16 rules, 500 explicit members, 32 tags per resource, and a preview
inventory budget of 5,000 resources/20,000 relationships. Invalid definitions or an
exceeded budget show an error; an error must never be interpreted as an empty group
or an authorization. Reopen/preview a group to see current membership after changes.
See [the design](../../02-architecture/adr/0024-bounded-resource-groups.md).
