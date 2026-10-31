---
title: Custom tasks
status: active
updated: 2026-10-31
tags: [wiki, user-guide]
---

# Custom tasks

Create and maintain custom tasks in the backend's management UI. Tasks are stored
persistently and are exposed dynamically to the native integration where supported.
Every execution needs an explicit existing host target and deliberate confirmation.

Prefer the `command` type: it stores a JSON argument array and invokes Ansible's
command module without shell expansion. Define executable and arguments separately.
Shell operators such as pipes are not interpreted in this mode.

The `shell` type intentionally invokes a shell. It requires deployment-level
`allow_shell_tasks` / `HUL_ALLOW_SHELL_TASKS` opt-in and deserves the same review as
any privileged script. Do not enable it just to bypass validation.

Task definitions must never contain tokens, passwords or private SSH keys. Treat
any task using the automation account's sudo privileges as a privileged operation.
Review the target, purpose and expected result before executing. Inspect bounded
job output through [the authenticated job view](updates-and-jobs.md).

There is no built-in autonomous task scheduler or implicit update/reboot policy.

## Assign tasks to suitable hosts

Use **+** on Tasks, or **+ Create task** in host details. The dialog supports name,
description, command argv or opt-in shell mode, global activation and prerequisites.
Declare allowed lowercase OS IDs (for example `debian, ubuntu`), exact VERSION_ID
values, required programs/packages and whether execution needs sudo. Empty system
lists allow any system. The primary executable is always checked; shell tasks check
`/bin/sh` as well as their declared dependencies. Declare tools used inside shell
commands explicitly. The check cannot prove an arbitrary task will succeed.

Host details lists available and assigned tasks with **unchecked**, **suitable**,
**unsuitable** or **failed** results and reasons. Select **Check compatibility** to
run a read-only check of SSH/Python, system, programs, packages and requested sudo
context. It installs nothing. Package checks currently use dpkg; other package
managers need future probe adapters. After a suitable result, select **Assign to
host**. Global activation and per-host activation must both allow execution.
You can disable, enable or unassign a task independently on each host.

Checks expire after 24 hours. Connection or task execution/prerequisite changes
invalidate results. **Run task** requires a current suitable result and confirmation;
the worker probes again before execution. Assignment and compatibility rules apply
to external API calls too. Disabled or unassigned tasks cannot bypass the UI.

Upgrade preserves existing task definitions, IDs and host relationships by assigning
legacy tasks to existing hosts with their prior activation. They start unchecked
and need a successful check before running again. New hosts receive no automatic
task assignments. Existing HA task buttons become unavailable when their host is
not in the task's enabled assignments.
