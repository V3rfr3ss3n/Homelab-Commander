---
title: Host package details
status: active
updated: 2026-11-15
tags: [wiki, user-guide, hosts, packages]
---

# Host package details

These controls are part of the dev.5 candidate under review and are not yet
available in the published dev.4 release.

Open **Hosts → Details → Package details** after a successful check. The dialog
shows package names, installed/available versions, security badges, last check
and the full pending count. Sort by security first, name A–Z or name Z–A. Sorting
never changes the selected names or starts work. Sorting and grouped selection
controls sit above a separate action bar; the highlighted action updates the
selection, while Update all remains a distinct secondary action. The date is a readable timestamp,
not markup printed into the dialog.

## Choose the update scope

- **Update** on a row queues only that named installed package after confirmation.
- **Skip** excludes a shown package from **Update selected (N)**. **Skip all**
  excludes every shown row; uncheck Skip for the names you want. **Select all**
  includes all shown rows again. An empty selection disables Update selected.
- **Update selected (N)** confirms the exact names and queues one persistent job
  for the selection. Sorting and dialog reopen keep this host's choices during
  the current signed-in page session. Reload/sign-out clears these choices.
- **Update all (N)** runs the normal full-host upgrade, including skipped and
  undisplayed packages. Its confirmation explicitly distinguishes this scope.

The list contains at most 50 rows, while pending counts include every available
update. A partial list states how many rows are shown. Selection covers shown
names only; a full update can include additional packages. Skip is not an APT hold:
APT may also update dependencies of a chosen package. Review the named targets
and plan maintenance before confirming. Neither update action requests a reboot;
review restart requirements and confirm reboots separately.

## Follow completion

Queueing/running leaves the last measured count/list visible and locks maintenance
controls. A successful update triggers a fresh package check and commits counts
and rows together. For example, updating one of 12 pending packages leaves 11 if
APT updated no other dependencies. Failed execution or failed post-check preserves
the last known snapshot; inspect the linked job and run a check before retrying.
Rerunning a scoped job keeps its original names instead of doing a full upgrade.

Before the first check the dialog asks you to run one. A verified empty list shows
**No packages need updates**. Existing hosts retain counts/history and acquire
package details after the next successful check following the backend upgrade.
See the [API contract](../../02-architecture/native-api.md) and
[dev.5 acceptance](../../05-reviews/2026-11-14-dev5-acceptance.md).
