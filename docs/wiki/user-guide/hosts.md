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
