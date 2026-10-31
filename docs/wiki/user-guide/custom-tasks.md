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
