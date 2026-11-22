---
title: Host package details
status: active
updated: 2026-11-18
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


## RPM providers (next development version, #48 review)

Choose the package provider in the Host connection dialog after preparing SSH,
Python 3 and non-interactive sudo manually. Onboarding scripts currently cover
Debian/Ubuntu only. DNF admits Fedora 45 and the RHEL-9 family; Zypper permits
regular package maintenance on Leap 16.0 and read-only inventory on Tumbleweed.
A fresh check populates eligible scopes; disabled buttons are not permissions.

RPM rows use architecture-qualified names such as `curl.x86_64`. Single/selected
updates apply only to freshly eligible installed packages; dependencies are still
resolved by the native manager. Full updates use the regular native package
workflow, not an OS migration or vendor switch. Security classification is currently
unknown and shown explicitly; DNF restart status is also unknown. Review services
and downtime manually, and confirm any reboot separately.

A failed operation can have partial effects. Old counts are marked stale until a
fresh check succeeds; no retry, package rollback or reboot occurs automatically.
Zypper may require another manually reviewed invocation after updating itself.
Update the HA integration before enabling these providers. These profiles have
synthetic contract tests, not a blanket real-platform certification.

## Automatic detection

New hosts default to **Auto-detect system package manager**. The setting is stored
as `auto`; an explicit check or update reads distribution and package-manager
facts and delegates to APT, DNF or Zypper. It does not try another manager after a
failure. Existing explicit provider choices remain unchanged. Unsupported facts
fail safely, and all provider restrictions still apply, including Tumbleweed's
read-only inventory. Update controls become available after a successful check.

This selects one system package manager. Independent package sources on the same
host need separate package identities, observations and job targets; simultaneous
source management is not claimed by this implementation.
