---
title: Host onboarding
status: active
updated: 2026-10-31
tags: [wiki, user-guide]
---

# Host onboarding

## Prepare access

1. Use a dedicated automation account on a supported Debian/Ubuntu host.
2. Open the backend's management UI and copy its **public** SSH key into that
   account's `authorized_keys`. Never export or copy the private key into HA.
3. Provide Python 3, APT and non-interactive sudo for the required maintenance
   operations. An unversioned `python` symlink is not required.
4. Restrict SSH network access to the backend's network origin. The HA integration
   does not initiate SSH connections.
5. Verify the first-contact host fingerprint through a trusted channel.

The backend uses its own `known_hosts` file with first-use acceptance. Later
connections are checked against that stored identity. Non-interactive sudo for
Ansible can amount to root-equivalent access: a path-only whitelist of temporary
Python modules is not a reliable restriction. Protect the key and account
accordingly; see [security](../technical/security.md).

## Add and test a host

In the management UI, create a host with a recognizable display name, its configured
SSH address, port and automation user. The backend assigns a stable UUID separate
from the display name. A name change does not create a new identity.

Select **Test connection**. This is an intentional real operation: it verifies
SSH, Python/facts and non-interactive sudo. It does not install updates or reboot.
A successful connection test does not guarantee a later APT operation cannot
encounter a lock or repository failure.

Run a deliberate status check to populate facts, update counts and reboot state.
The backend must have an outbound route to the target; exposing the UI port does
not create that route. Newly discovered hosts appear dynamically in HA. A host
missing temporarily from status becomes unavailable rather than immediately
being deleted from the registry.

Next: [updates and jobs](updates-and-jobs.md).

## Guided setup and paste import

Use **+** beside the host list to open **Add host**. The dialog contains the backend
public key, connection fields and **Copy Debian setup** / **Copy Ubuntu setup**.
Set a dedicated non-root user and your existing SSH port before copying. Run the
reviewed command on the selected target as an administrator; Python 3 must already
be present. Templates create/reuse that account and install only the public key,
with restrictive `.ssh` and `authorized_keys` permissions. Repeating the same command
does not duplicate the key. Other systems are not offered yet.

These commands install no packages and do not change sudo, firewall or SSH daemon
configuration. You must arrange Python and the intended non-interactive sudo rights,
restrict network access and verify host identity yourself. The port field describes
your existing SSH listener; it does not configure one.

Copy the output between `HLC_HOST_BEGIN` and `HLC_HOST_END` and paste it into a
connection field. The versioned format fills name, user, port and address after
validation; it carries no private key or credentials. Multiple reported addresses
require a choice of one reachable from the backend. Review all values before saving.
Malformed or unsupported versions show a form error. Pasting and saving only edit
inventory; connection testing and checks remain deliberate actions.
