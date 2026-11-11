#!/usr/bin/env python3
"""Reject mismatched source versions before a release candidate is published."""

import json
import re
import sys
import tomllib
from pathlib import Path


def versions(root: Path) -> dict[str, str]:
    project = tomllib.loads((root / "pyproject.toml").read_text())
    locked = tomllib.loads((root / "uv.lock").read_text())
    package = next(
        item for item in locked["package"] if item["name"] == project["project"]["name"]
    )
    app = (root / "addon/homelab_updates/config.yaml").read_text()
    workflow = (root / ".github/workflows/container.yml").read_text()
    dockerfile = (root / "Dockerfile").read_text()
    compose = (root / "compose.yaml").read_text()
    backend = (root / "backend/homelab_backend/version.py").read_text()
    integration = (root / "custom_components/homelab_updates/const.py").read_text()

    def match(pattern: str, content: str, name: str) -> str:
        found = re.search(pattern, content, re.MULTILINE)
        if found is None:
            raise ValueError(f"Missing version in {name}")
        return found.group(1)

    return {
        "project": project["project"]["version"],
        "lock": package["version"],
        "App": match(r"^version:\s*([0-9A-Za-z.-]+)\s*$", app, "App config"),
        "backend": match(r'^__version__ = "([^"]+)"$', backend, "backend"),
        "integration manifest": json.loads(
            (root / "custom_components/homelab_updates/manifest.json").read_text()
        )["version"],
        "integration constant": match(
            r'^VERSION: Final = "([^"]+)"$', integration, "integration constant"
        ),
        "container build": match(
            r"^ARG BUILD_VERSION=([^\s]+)$", dockerfile, "Dockerfile"
        ),
        "Compose image": match(
            r"^\s*image: homelab-updates-backend:([^\s]+)$", compose, "Compose"
        ),
        "publish workflow": match(
            r"^\s*default: ([0-9]+\.[0-9]+\.[0-9]+-[^\s]+)$",
            workflow,
            "container workflow",
        ),
    }


def main(root: Path) -> int:
    found = versions(root)
    canonical = found["App"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?", canonical):
        print("Invalid App release version", file=sys.stderr)
        return 1
    normalized = canonical.replace("-dev.", ".dev")
    mismatches = {
        name: value
        for name, value in found.items()
        if value != (normalized if name in {"project", "lock"} else canonical)
    }
    if mismatches:
        print(
            f"Version mismatch: App={canonical}, differing={mismatches}",
            file=sys.stderr,
        )
        return 1
    print(f"Version alignment: {canonical}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()))
