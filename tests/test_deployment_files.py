"""Static deployment security and consistency checks."""

import json
import struct
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def _png_dimensions(path: Path) -> tuple[int, int]:
    """Return dimensions from a local PNG without an image dependency."""
    payload = path.read_bytes()
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert payload[12:16] == b"IHDR"
    return struct.unpack(">II", payload[16:24])


def test_home_assistant_public_metadata_and_translation_contract() -> None:
    """Public metadata and config-flow translations follow the HA schema."""
    integration = ROOT / "custom_components/homelab_updates"
    manifest = json.loads((integration / "manifest.json").read_text())
    assert list(manifest) == [
        "domain",
        "name",
        "codeowners",
        "config_flow",
        "dependencies",
        "documentation",
        "integration_type",
        "iot_class",
        "issue_tracker",
        "requirements",
        "version",
    ]
    assert "http" in manifest["dependencies"]
    assert manifest["documentation"].endswith("/V3rfr3ss3n/Homelab-Commander")
    assert manifest["issue_tracker"].endswith("/V3rfr3ss3n/Homelab-Commander/issues")

    expected_abort_reasons = {
        "already_configured",
        "reauth_successful",
        "reconfigure_successful",
    }
    for language in ("de", "en"):
        translations = json.loads(
            (integration / f"translations/{language}.json").read_text()
        )
        assert "abort" not in translations
        assert set(translations["config"]["abort"]) == expected_abort_reasons


def test_secret_scan_uses_github_token_on_pull_requests_and_pushes() -> None:
    """Gitleaks v3 receives only GitHub's ephemeral workflow token."""
    workflow = (ROOT / ".github/workflows/secrets.yml").read_text()
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "gitleaks/gitleaks-action@v2" not in workflow
    assert "# v3" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow


def test_addon_uses_ingress_without_privileged_host_access() -> None:
    """The app manifest exposes only the intended API and Ingress boundary."""
    config = yaml.safe_load((ROOT / "addon/homelab_updates/config.yaml").read_text())
    assert config["name"] == "Homelab Updates Backend"
    assert config["ingress"] is True
    assert config["panel_admin"] is True
    assert config["panel_title"] == "Homelab Updates Backend"
    assert config["ingress_port"] == 8099
    assert "ingress_entry" not in config
    assert config["ports"] == {"8099/tcp": None}
    assert config["image"] == "ghcr.io/v3rfr3ss3n/homelab-updates-backend"
    assert config["version"] == "0.2.0-dev.1"
    assert config["url"] == "https://github.com/V3rfr3ss3n/Homelab-Commander"
    assert config["arch"] == ["aarch64", "amd64"]
    for forbidden in ("host_network", "privileged", "docker_api", "hassio_api"):
        assert forbidden not in config
    assert "map" not in config


def test_public_installation_docs_have_only_public_navigation_links() -> None:
    """Installed App documentation never resolves into Home Assistant files."""
    public_documents = (
        ROOT / "README.md",
        ROOT / "addon/homelab_updates/DOCS.md",
        ROOT / "addon/homelab_updates/README.md",
    )
    for document in public_documents:
        content = document.read_text()
        assert "/config/" not in content
        assert "/" + "home/" not in content
        assert "../../docs/" not in content
    assert (
        "https://github.com/V3rfr3ss3n/Homelab-Commander"
        in (ROOT / "addon/homelab_updates/DOCS.md").read_text()
    )


def test_development_release_versions_stay_aligned() -> None:
    """Integration, backend, App and publication use one release version."""
    expected = "0.2.0-dev.1"
    manifest = json.loads(
        (ROOT / "custom_components/homelab_updates/manifest.json").read_text()
    )
    assert manifest["version"] == expected
    assert (
        f'VERSION: Final = "{expected}"'
        in (ROOT / "custom_components/homelab_updates/const.py").read_text()
    )
    assert (
        f'__version__ = "{expected}"'
        in (ROOT / "backend/homelab_backend/version.py").read_text()
    )
    assert (
        f"image: homelab-updates-backend:{expected}"
        in (ROOT / "compose.yaml").read_text()
    )
    assert (
        f"default: {expected}" in (ROOT / ".github/workflows/container.yml").read_text()
    )
    assert f"ARG BUILD_VERSION={expected}" in (ROOT / "Dockerfile").read_text()


def test_packaged_branding_is_valid_and_consistent() -> None:
    """Integration and app packages ship matching square PNG assets."""
    integration_brand = ROOT / "custom_components/homelab_updates/brand"
    addon = ROOT / "addon/homelab_updates"
    integration_icon = integration_brand / "icon.png"
    integration_icon_2x = integration_brand / "icon@2x.png"
    addon_icon = addon / "icon.png"
    addon_logo = addon / "logo.png"

    assert _png_dimensions(integration_icon) == (256, 256)
    assert _png_dimensions(integration_icon_2x) == (512, 512)
    assert _png_dimensions(addon_icon) == (256, 256)
    assert _png_dimensions(addon_logo) == (512, 512)
    assert integration_icon.read_bytes() == addon_icon.read_bytes()
    assert integration_icon_2x.read_bytes() == addon_logo.read_bytes()


def test_public_app_repository_metadata_is_complete() -> None:
    """The App Store entry links to its public project and has release notes."""
    repository = yaml.safe_load((ROOT / "repository.yaml").read_text())
    assert repository == {
        "name": "Homelab Updates",
        "url": "https://github.com/V3rfr3ss3n/Homelab-Commander",
        "maintainer": "V3rfr3ss3n",
    }
    assert (ROOT / "addon/homelab_updates/CHANGELOG.md").is_file()


def test_container_workflow_builds_multi_arch_and_gates_publication() -> None:
    """Public images use the HA builder and an anonymous runtime gate."""
    workflow = (ROOT / ".github/workflows/container.yml").read_text()
    builder_ref = (
        "home-assistant/builder/actions/"
        "prepare-multi-arch-matrix@4de35182ce1e329181bffcbcc84d33db5e2c7e10"
    )
    assert builder_ref in workflow
    assert workflow.count("@4de35182ce1e329181bffcbcc84d33db5e2c7e10") == 4
    assert 'ARCHITECTURES: \'["amd64", "aarch64"]\'' in workflow
    assert "image-name: ${{ env.IMAGE_NAME }}" in workflow
    assert "if: needs.policy.outputs.publish != 'true'" in workflow
    assert "if: needs.policy.outputs.publish == 'true'" in workflow
    assert "packages: write" in workflow
    assert "container-registry-password: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "docker logout ghcr.io || true" in workflow
    assert "docker buildx imagetools inspect --raw" in workflow
    assert "scripts/validate-container-image.sh" in workflow
    assert "latest," not in workflow


def test_compose_hardens_the_shared_image() -> None:
    """Standalone defaults bind locally and drop Linux capabilities."""
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    service = compose["services"]["homelab-updates"]
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert service["ports"] == ["127.0.0.1:8099:8099"]
    assert service["environment"]["HUL_ALLOW_SHELL_TASKS"] == "false"


def test_container_has_no_embedded_deployment_secret() -> None:
    """Runtime secrets arrive only through environment or Supervisor options."""
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "HUL_API_TOKEN=" not in dockerfile
    assert "openssh-client" in dockerfile
    assert "homelab_backend.container_entrypoint" in dockerfile
