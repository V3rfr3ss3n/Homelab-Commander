"""Static deployment security and consistency checks."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


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
    assert config["ingress"] is True
    assert config["panel_admin"] is True
    assert config["panel_title"] == "Homelab Updates Backend"
    assert config["ingress_port"] == 8099
    assert config["ports"] == {"8099/tcp": None}
    assert config["image"] == "ghcr.io/v3rfr3ss3n/homelab-updates-backend"
    for forbidden in ("host_network", "privileged", "docker_api", "hassio_api"):
        assert forbidden not in config
    assert "map" not in config
    assert (ROOT / "addon/homelab_updates/icon.png").stat().st_size > 0
    assert (ROOT / "addon/homelab_updates/logo.png").stat().st_size > 0


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
