---
title: Host onboarding
status: active
updated: 2026-11-09
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

Use **+** beside the host list. The assistant has three steps:

1. Choose Debian (also used for Proxmox VE) or Ubuntu.
2. Select **Create or reuse account** or **Update existing account**, the SSH
   username, existing port, shell, key restrictions and optional allowed source IP/CIDR.
   Review the generated script and press **Copy script** once to copy it. Run it
   on the target as root; Python 3 must already be installed. The public key is
   available in an expandable section. If SSH is already prepared, skip this step.
3. Enter or import the SSH connection and save the host.

No sudo rule is selected by default. Built-in maintenance needs non-interactive
sudo; choosing **Passwordless root access** requires a separate acknowledgement
before copying. It gives the backend key root-equivalent authority, including more
than package maintenance. Key restrictions disable forwarding and interactive
terminals by default; an optional IP/CIDR restricts that key's source, not the
firewall. Verify that the source matches what the target sees.

**Edit host → Update SSH user setup** generates a script for an existing account.
Update mode applies the selected shell, replaces restrictions on this backend key
without duplicating it, and creates or removes only its own managed sudoers file.
It refuses to overwrite foreign rules. Other sudo rules and group memberships
remain active: selecting no managed rule does not guarantee removal of all sudo
access. Create/reuse mode leaves an existing account's shell unchanged.

Scripts install no packages and change no firewall or SSH daemon configuration.
They set private `.ssh`/key permissions and validate new sudo rules with `visudo`
before installation. A sudo selection requires sudo/visudo already installed;
update mode requires `/etc/sudoers.d` to exist. The port describes your existing
SSH listener. Restrict network access and verify the host fingerprint yourself.

Copy the output between `HLC_HOST_BEGIN` and `HLC_HOST_END` and paste it into a
connection field. The versioned format fills name, user, port and address after
validation; it carries no private key or credentials. Multiple reported addresses
require a choice of one reachable from the backend. Review all values before saving.
Malformed or unsupported versions show a form error. Pasting and saving only edit
inventory; connection testing and checks remain deliberate actions.

## Website shortcuts

In **Add host** or **Edit host**, enter up to twelve websites, one per line as
`Name | https://service.example.invalid`. Only HTTP(S) URLs without embedded login
credentials are accepted. Saved sites appear as compact clickable icons beside the
host and open in a separate tab. The browser loads the site's origin favicon without
sending a referrer; an unavailable icon falls back to the site's initial. The backend
never fetches website content or icons. Adding a site lets your browser contact that
site when its icon is displayed; avoid putting credentials in links.
