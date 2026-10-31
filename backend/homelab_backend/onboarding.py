"""Extensible setup templates with one versioned, non-secret import envelope."""

import json

from pydantic import BaseModel, ConfigDict

FORMAT = "homelab-commander-host"
TEMPLATES = {"debian": "Debian", "ubuntu": "Ubuntu"}


class OnboardingCommand(BaseModel):
    model_config = ConfigDict(frozen=True)
    system: str
    command: str


def setup_command(
    system: str, username: str, port: int, public_key: str
) -> OnboardingCommand:
    """Only callers with validated user/port and a backend-owned key may render."""
    if system not in TEMPLATES or username == "root":
        raise ValueError("Choose a supported system and a dedicated non-root account")
    values = json.dumps({
        "username": username,
        "port": port,
        "key": public_key,
        "system": system,
    })
    script = _LINUX_SETUP.replace("__SETUP_DATA__", repr(values))
    return OnboardingCommand(
        system=system, command="sudo python3 - <<'HLC_SETUP'\n" + script + "\nHLC_SETUP"
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
    subprocess.run(['useradd', '--create-home', '--shell', '/bin/sh',
                    '--', config['username']], check=True)
    account = pwd.getpwnam(config['username'])
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
        flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
        descriptor = os.open('authorized_keys', flags, 0o600, dir_fd=ssh)
        with os.fdopen(descriptor, 'r+') as keys:
            metadata = os.fstat(keys.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise SystemExit('authorized_keys must be a regular file')
            existing = keys.read()
            key = config['key'].strip()
            if key not in existing.splitlines():
                separator = '\n' if existing and not existing.endswith('\n') else ''
                keys.write(separator + key + '\n')
            os.fchmod(keys.fileno(), 0o600)
            os.fchown(keys.fileno(), account.pw_uid, account.pw_gid)
    finally:
        os.close(ssh)
finally:
    os.close(home)
addresses = subprocess.check_output(['hostname', '-I'], text=True).split()
addresses = list(dict.fromkeys(addresses))
name = socket.gethostname()
print('HLC_HOST_BEGIN')
print(json.dumps({'format': 'homelab-commander-host', 'version': 1, 'name': name,
                  'addresses': addresses or [name],
                  'username': config['username'], 'port': config['port']}))
print('HLC_HOST_END')
"""
