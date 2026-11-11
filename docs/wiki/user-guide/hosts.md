---
title: Host onboarding
status: active
updated: 2026-11-11
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

## Inspect and maintain a host

Host rows show the stored distribution with an inline OS icon. Hosts with known
pending updates have a subtle accent; security updates have their own count. A
positive **Restart required** flag is prominent. There is no routine "reboot not
required" text. Unchecked hosts retain an explicit unknown status.

Open **Details** for a host workspace with system/version/kernel and package-provider
facts, SSH endpoint and user, last-check freshness, task assignment/readiness counts,
recent jobs and inventory dates. Links open this host's jobs and task configuration.
Connection testing, checking updates, updating, rebooting, editing and removing remain
explicit actions. **Copy address** copies only the configured address. The workspace
shows existing backend facts; it does not infer hardware capacity or virtualization
type. A **PVE kernel** marker refers to the reported kernel, not proof of the host's
virtualization role. Icons do not fetch external logos.

On Dashboard, the compact host list sits below Important notices in the right-hand
column, even when no notices are active. On narrow screens the column follows the
job history. The full Hosts tab keeps search, status filters and sorting.

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

Open **Hosts → Details → Edit host**. The management actions at the top of the
dialog include **Update SSH user setup** and **Remove host**, before the connection
fields. Updating user setup does not submit the connection form; unsaved connection
values remain available when returning from setup. **Copy script** copies the visible
preview and confirms success inside the dialog.

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

In **Add host** or **Edit host**, enter up to twelve websites, one per line:

```text
Portal | https://service.example.invalid
Portal | https://service.example.invalid | https://assets.example.invalid/portal.svg
```

The optional third value is a direct image URL, useful when a site uses a different
icon location. Website and icon URLs must use HTTP(S) without embedded credentials.
Sites open in a separate tab. The browser tries `/favicon.ico`, `/favicon.svg`,
`/favicon.png`, `/apple-touch-icon.png` and `/favicons/favicon-32x32.png` on the website
origin, or only the supplied override. No backend or third-party icon service
fetches them. An override may contact another origin you explicitly choose.
Requests send no referrer or Commander authentication headers.

Loaded image nodes survive refreshes and host-view navigation. Failed icons retain
a stable initial and explanatory tooltip instead of flashing/retrying on each job
refresh. **Retry saved website icons** in Edit host explicitly retries the saved
links; unsaved edits are not used. A full page reload also starts new icon attempts.
HTTPS certificates must be trusted. Cloudflare challenges, access rules or browser
privacy settings can still block embedded images even if the site itself opens;
provide a publicly loadable image URL in that case. There is no HTTPS-to-HTTP fallback.


## Remove a host

Open **Hosts → Details → Remove host**, or use **Remove host** at the top of
**Edit host**. Confirm the named host to remove its inventory entry and task
assignments. The UI closes the edit dialog and returns to Hosts; it does not reload
the removed host's detail endpoints. Cancelling keeps the host and view unchanged;
a failed request keeps the host available and shows an error (inside Edit host if
open). Removal does not delete the remote user, revoke its installed SSH key or run
an SSH command. Review remote access separately when retiring a host.
