"""Extensible setup templates with one versioned, non-secret import envelope."""

import json
from ipaddress import ip_network
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import SshUser

FORMAT = "homelab-commander-host"
TEMPLATES = {"debian": "Debian", "ubuntu": "Ubuntu"}


class SetupOptions(BaseModel):
    """Declarative, validated choices; no arbitrary shell or sudo rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    mode: Literal["create", "update"] = "create"
    shell: Literal["/bin/sh", "/bin/bash"] = "/bin/sh"
    sudo: Literal["none", "full"] = "none"
    restricted_key: bool = True
    source: str = Field(default="", max_length=64)

    @model_validator(mode="after")
    def validate_source(self) -> SetupOptions:
        if self.source:
            ip_network(self.source, strict=False)
        return self


class OnboardingCommand(BaseModel):
    model_config = ConfigDict(frozen=True)
    system: str
    command: str


def setup_command(
    system: str,
    username: SshUser,
    port: int,
    public_key: str,
    options: SetupOptions | None = None,
) -> OnboardingCommand:
    """Only callers with validated user/port and a backend-owned key may render."""
    if system not in TEMPLATES or username == "root":
        raise ValueError("Choose a supported system and a dedicated non-root account")
    options = options or SetupOptions()
    values = json.dumps({
        "username": username,
        "port": port,
        "key": public_key,
        "system": system,
        **options.model_dump(),
    })
    script = (_LINUX_SETUP + _PRIVILEGES + _OUTPUT).replace(
        "__SETUP_DATA__", repr(values)
    )
    return OnboardingCommand(
        system=system,
        command=(
            "# Run as root; otherwise use sudo python3 for the command below.\n"
            "python3 - <<'HLC_SETUP'\n" + script + "\nHLC_SETUP"
        ),
    )


# Python is a prerequisite; never download or install code/packages during setup.
_LINUX_SETUP = r"""import json, os, pwd, shlex, socket, stat, subprocess
config = json.loads(__SETUP_DATA__)
with open('/etc/os-release') as source:
    release = dict(line.strip().split('=', 1) for line in source if '=' in line)
if shlex.split(release.get('ID', '')) != [config['system']]:
    raise SystemExit('Selected system does not match this host')
if os.geteuid() != 0:
    raise SystemExit('Run this preparation with sudo or as an administrator')
try:
    account = pwd.getpwnam(config['username'])
except KeyError:
    if config['mode'] == 'update':
        raise SystemExit('Account does not exist; choose Create or reuse account')
    subprocess.run(['useradd', '--create-home', '--shell', config['shell'],
                    '--', config['username']], check=True)
    account = pwd.getpwnam(config['username'])
if account.pw_uid == 0:
    raise SystemExit('Refusing to configure a root-equivalent account')
if config['mode'] == 'update':
    subprocess.run(['usermod', '--shell', config['shell'], '--', config['username']],
                   check=True)
home = os.open(account.pw_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    try:
        os.mkdir('.ssh', 0o700, dir_fd=home)
    except FileExistsError:
        pass
    ssh = os.open('.ssh', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=home)
    try:
        os.fchmod(ssh, 0o700)
        os.fchown(ssh, account.pw_uid, account.pw_gid)
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
        descriptor = os.open('authorized_keys', flags, 0o600, dir_fd=ssh)
        with os.fdopen(descriptor, 'r+') as keys:
            metadata = os.fstat(keys.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise SystemExit('authorized_keys must be a regular file')
            existing = keys.read()
            key = config['key'].strip()
            restrictions = []
            if config['restricted_key']:
                restrictions.extend(['no-agent-forwarding', 'no-port-forwarding',
                                     'no-X11-forwarding', 'no-pty'])
            if config['source']:
                restrictions.append('from="' + config['source'] + '"')
            line = (','.join(restrictions) + ' ' if restrictions else '') + key
            identity = key.split()[:2]
            retained = []
            for old in existing.splitlines():
                tokens = old.split()
                if not any(tokens[i:i+2] == identity for i in range(len(tokens)-1)):
                    retained.append(old)
            keys.seek(0)
            keys.truncate()
            keys.write('\n'.join([*retained, line]) + '\n')
            os.fchmod(keys.fileno(), 0o600)
            os.fchown(keys.fileno(), account.pw_uid, account.pw_gid)
    finally:
        os.close(ssh)
finally:
    os.close(home)
"""

# Changes are restricted to our own sudoers file. No package or network operations.
_PRIVILEGES = r"""
if config['sudo'] == 'full' or config['mode'] == 'update':
    import secrets
    directory = os.open('/etc/sudoers.d', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        filename = 'homelab-commander-' + config['username']
        marker = '# Managed by Homelab Commander: ' + config['username'] + '\n'
        try:
            existing_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW,
                                  dir_fd=directory)
        except FileNotFoundError:
            existing_fd = None
        if existing_fd is not None:
            with os.fdopen(existing_fd) as existing_rule:
                metadata = os.fstat(existing_rule.fileno())
                if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                        or metadata.st_uid != 0 or existing_rule.readline() != marker):
                    raise SystemExit('Refusing to replace an unmanaged sudoers file')
        if config['sudo'] == 'full':
            temporary = '.hlc-' + secrets.token_hex(12)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            fd = os.open(temporary, flags,
                         0o440, dir_fd=directory)
            try:
                with os.fdopen(fd, 'w') as rule:
                    os.fchmod(rule.fileno(), 0o440)
                    rule.write(marker + config['username']
                               + ' ALL=(root) NOPASSWD: ALL\n')
                    rule.flush()
                    os.fsync(rule.fileno())
                subprocess.run(['visudo', '-cf', '/etc/sudoers.d/' + temporary],
                               check=True)
                os.replace(temporary, filename, src_dir_fd=directory,
                           dst_dir_fd=directory)
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
        elif existing_fd is not None:
            os.unlink(filename, dir_fd=directory)
    finally:
        os.close(directory)
print('Other sudo rules, group memberships and SSH daemon settings are unchanged.')
"""

_OUTPUT = r"""addresses = subprocess.check_output(['hostname', '-I'], text=True).split()
addresses = list(dict.fromkeys(addresses))
name = socket.gethostname()
print('HLC_HOST_BEGIN')
print(json.dumps({'format': 'homelab-commander-host', 'version': 1, 'name': name,
                  'addresses': addresses or [name],
                  'username': config['username'], 'port': config['port']}))
print('HLC_HOST_END')
"""
