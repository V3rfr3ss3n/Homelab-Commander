"""Release gate refuses a stale App version even when integration code advances."""

import runpy
from pathlib import Path
from shutil import copy2


def test_release_version_gate_detects_stale_app_metadata(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    for name in (
        "pyproject.toml",
        "uv.lock",
        "addon/homelab_updates/config.yaml",
        ".github/workflows/container.yml",
        "Dockerfile",
        "compose.yaml",
        "backend/homelab_backend/version.py",
        "custom_components/homelab_updates/const.py",
        "custom_components/homelab_updates/manifest.json",
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(root / name, target)
    namespace = runpy.run_path(str(root / "scripts/check-version-alignment.py"))
    check = namespace["main"]
    assert check(tmp_path) == 0
    config = tmp_path / "addon/homelab_updates/config.yaml"
    config.write_text(
        config.read_text().replace("version: ", "version: 0.0.0-stale-", 1)
    )
    assert check(tmp_path) == 1
