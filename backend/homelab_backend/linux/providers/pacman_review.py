"""Read-only ALPM solver preview and foreign-package inventory."""

import re

from ...execution.results import AutomationExecutionError
from ...models import MAX_PACKAGE_DETAILS, NativePackageVersion, PacmanReview

# Executed beneath the existing bounded command wrapper as the SSH user. The
# isolated sync DB is reused within this check only; the real local DB is read
# through checkupdates' symlink and all pacman commands after it are read-only.
REVIEW_SCRIPT = """
import os, subprocess, sys, tempfile
with tempfile.TemporaryDirectory(prefix="hlc-alpm-") as scratch:
    db = os.path.join(scratch, "db")
    env = dict(os.environ, CHECKUPDATES_DB=db,
               CHECKUPDATES_CHANGE=os.path.join(scratch, "state"))
    checked = subprocess.run(
        ("/usr/bin/checkupdates", "--nocolor"), env=env, timeout=90
    )
    if checked.returncode not in (0, 2):
        sys.exit(1)
    print("HLC_ALPM_PLAN", flush=True)
    pacman = ("/usr/bin/pacman", "--dbpath", db, "--logfile", "/dev/null",
              "--color", "never")
    plan = subprocess.run(
        (*pacman, "-Sup", "--noconfirm", "--print-format", "%n %v"), timeout=35
    )
    if plan.returncode != 0:
        sys.exit(1)
    print("HLC_ALPM_FOREIGN", flush=True)
    foreign = subprocess.run((*pacman, "-Qm"), timeout=20)
    sys.exit(0 if foreign.returncode in (0, 1) else 1)
"""

_NAME = r"[A-Za-z0-9@_+][A-Za-z0-9@._+-]{0,254}"
_VERSION = r"[A-Za-z0-9][A-Za-z0-9.:_+~-]{0,254}"
_VERSION_ROW = re.compile(rf"({_NAME}) ({_VERSION})")


def split_review(output: str) -> tuple[str, PacmanReview]:
    pending, delimiter, details = ("\n" + output).partition("\nHLC_ALPM_PLAN\n")
    if not delimiter:
        raise AutomationExecutionError("invalid_package_output", "")
    plan, marker, foreign = details.partition("HLC_ALPM_FOREIGN\n")
    if not marker:
        raise AutomationExecutionError("invalid_package_output", "")
    candidates = _versions(plan)
    foreign_packages = _versions(foreign)
    return pending, PacmanReview(
        candidates=candidates[:MAX_PACKAGE_DETAILS],
        candidate_count=len(candidates),
        foreign=foreign_packages[:MAX_PACKAGE_DETAILS],
        foreign_count=len(foreign_packages),
    )


def _versions(output: str) -> tuple[NativePackageVersion, ...]:
    rows: dict[str, NativePackageVersion] = {}
    for line in output.splitlines():
        if not line:
            continue
        match = _VERSION_ROW.fullmatch(line)
        if match is None or match[1] in rows:
            raise AutomationExecutionError("invalid_package_output", "")
        rows[match[1]] = NativePackageVersion(name=match[1], version=match[2])
    return tuple(rows[key] for key in sorted(rows))
