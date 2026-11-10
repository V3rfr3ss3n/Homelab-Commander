---
title: Backup, recovery and removal
status: active
updated: 2026-11-10
tags: [wiki, user-guide]
---

# Backup, recovery and removal

## Back up the complete data directory

The backend's `/data` contains the SQLite database, job history, custom tasks,
private SSH key and isolated `known_hosts` file. Protect the backup as privileged
credential material. Keep the database and identity together; restoring only the
database does not preserve the SSH identity trusted by managed hosts.

Use a consistent backup procedure for your App/container deployment, preferably
while the backend is stopped. Test recovery in an isolated environment before
relying on a backup. Never upload a real backup to an issue or repository.

## Restore

Stop the backend, restore the complete data directory with appropriate ownership
and private-key permissions, then start the same compatible application version.
Verify health and inventory before deliberately testing a host. A backend restart
invalidates standalone UI sessions; sign in again. Interrupted running jobs are
requeued on startup, so review job state and recovery behavior before restarting
a deployment with in-flight operations.

## Remove one managed host

Use **Hosts → Details → Remove host** or the same action at the top of **Edit host**.
Confirm the displayed host name. This removes the inventory entry and task
assignments, then returns to the host list. It does not delete the SSH account or
revoke the public key installed on that host. No remote command is executed by
removal; revoke access separately if needed. Cancelling does not change anything.

## Remove components

Remove the integration through Home Assistant's Devices & services interface.
It unloads its listeners and task tracking. Backend data remains independent.

For standalone Compose, `docker compose down` stops the stack without deleting
its named data volume. Deleting a volume is irreversible and is a separate,
intentional operation; make a protected backup first. Uninstalling the integration
does not revoke the public key installed on managed hosts. Revoke that access
separately if the backend is retired.
