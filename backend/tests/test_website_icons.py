"""Optional direct icon URLs retain safe, backwards-compatible inventory semantics."""

from pathlib import Path

import pytest

from backend.homelab_backend.models import HostWebsite
from backend.tests.test_backend_api import AUTH, FakeExecutor, _client, _create_host


@pytest.mark.parametrize(
    "icon",
    [
        "javascript:alert(1)",
        "file:///tmp/icon",
        "https://user:secret@assets.example.invalid/icon.png",
        "https://user@assets.example.invalid/icon.png",
        "not a URL",
    ],
)
def test_icon_urls_reject_non_http_and_credentials(icon: str) -> None:
    with pytest.raises(ValueError, match="validation error"):
        HostWebsite(name="Portal", url="https://portal.example.invalid", icon_url=icon)


def test_icon_url_roundtrip_and_legacy_omission(tmp_path: Path) -> None:
    legacy = {"name": "Portal", "url": "https://portal.example.invalid/app"}
    assert HostWebsite(**legacy).model_dump(mode="json") == legacy
    custom = {**legacy, "icon_url": "https://assets.example.invalid/portal.svg"}
    with _client(tmp_path, FakeExecutor()) as client:
        host = _create_host(client)
        endpoint = f"/api/v1/hosts/{host['id']}"
        response = client.patch(endpoint, headers=AUTH, json={"websites": [custom]})
        assert response.status_code == 200
        assert response.json()["websites"] == [custom]
        assert response.json()["id"] == host["id"]
    with _client(tmp_path, FakeExecutor()) as client:
        assert client.get(endpoint, headers=AUTH).json()["websites"] == [custom]
        assert client.patch(endpoint, headers=AUTH, json={"websites": [legacy]}).json()[
            "websites"
        ] == [legacy]
