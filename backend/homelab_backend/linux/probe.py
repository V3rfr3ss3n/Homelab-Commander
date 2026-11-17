"""Existing Debian task prerequisite probe, unchanged during package extraction."""

# This fixed script only reads OS identity and checks programs/package status.
PROBE_SCRIPT = r"""
import json, os, shlex, shutil, subprocess, sys
requirements = json.loads(sys.argv[1])
release = {}
with open('/etc/os-release') as source:
    for line in source:
        key, sep, value = line.strip().partition('=')
        if sep and key in ('ID', 'VERSION_ID'):
            parsed = shlex.split(value)
            release[key] = parsed[0] if parsed else ''
missing_packages = []
for package in requirements['packages']:
    if not shutil.which('dpkg-query'):
        missing_packages.append(package)
        continue
    result = subprocess.run(['dpkg-query', '-W', '-f=${Status}', '--', package],
                            capture_output=True, text=True, timeout=5)
    if result.returncode or result.stdout.strip() != 'install ok installed':
        missing_packages.append(package)
missing_programs = [n for n in requirements['programs'] if not shutil.which(n)]
print(json.dumps({'distribution': release.get('ID', ''),
                  'version': release.get('VERSION_ID', ''),
                  'missing_programs': missing_programs,
                  'missing_packages': missing_packages}))
"""
