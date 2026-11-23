"""Cross-manager evidence semantics and reusable synthetic execution contracts."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from backend.homelab_backend.linux.domain import PackageStatus, UpdateScope
from backend.homelab_backend.linux.evidence import (
    EvidenceState,
    InventoryEvidence,
    ObservedValue,
    PackageEvidence,
)
from backend.homelab_backend.linux.registry import PackageProviders
from backend.homelab_backend.models import MAX_PACKAGE_DETAILS, PackageInfo
from backend.tests.linux_contract_harness import (
    PROVIDER_CASES,
    ProviderCase,
    exercise_scope,
)

_MATRIX = json.loads(
    (Path(__file__).parent / "fixtures/linux/provider-matrix.json").read_text()
)


def _row(name: str = "package-01", security: bool = False) -> PackageEvidence:
    return PackageEvidence(name, "1", "2", ObservedValue(EvidenceState.KNOWN, security))


def _inventory() -> InventoryEvidence:
    return InventoryEvidence(
        2,
        ObservedValue(EvidenceState.KNOWN, 1),
        ObservedValue(EvidenceState.KNOWN, False),
        (_row(security=True), _row("package-02")),
    )


@pytest.mark.parametrize(
    "case", PROVIDER_CASES, ids=lambda case: case.provider.provider_id
)
@pytest.mark.parametrize("scope", list(UpdateScope))
async def test_reusable_provider_scope_contract(
    case: ProviderCase, scope: UpdateScope, tmp_path: Path
) -> None:
    await exercise_scope(case, scope, tmp_path)


@pytest.mark.parametrize(
    "profile", _MATRIX["profiles"], ids=lambda profile: profile["id"]
)
def test_every_manager_has_explicit_scope_and_observation_contract(
    profile: dict[str, object],
) -> None:
    """Future-family fixtures are neutral semantics, not native output decoders."""
    assert profile["targets"]
    assert set(profile["scopes"]) == {s.value for s in UpdateScope}
    assert set(profile["scopes"].values()) <= {
        "supported",
        "unknown",
        "unavailable",
        "unsupported",
    }
    if profile["registered"]:
        key = profile.get("provider_key", "debian_apt")
        assert PackageProviders().resolve(key).provider_id == (
            "linux.apt" if key == "debian_apt" else "linux." + key
        )
        assert {scope.value for scope in PackageProviders().resolve(key).scopes} == {
            name for name, state in profile["scopes"].items() if state == "supported"
        }
    else:
        assert "supported" not in profile["scopes"].values()
        with pytest.raises(ValueError, match="unsupported"):
            PackageProviders().resolve(profile["id"])
    security_state = EvidenceState(profile["security"])
    reboot_state = EvidenceState(profile["reboot"])
    security = ObservedValue(
        security_state,
        1 if security_state is EvidenceState.KNOWN else None,
        None if security_state is EvidenceState.KNOWN else "linux.security_not_proven",
    )
    reboot = ObservedValue(
        reboot_state,
        False if reboot_state is EvidenceState.KNOWN else None,
        None if reboot_state is EvidenceState.KNOWN else "linux.reboot_not_proven",
    )
    result = InventoryEvidence(2, security, reboot, (_row(security=True),))
    assert result.total == 2
    assert not result.details_complete
    if security_state is EvidenceState.KNOWN and reboot_state is EvidenceState.KNOWN:
        assert result.to_legacy().updates == 2
    else:
        assert result.security.value is None or result.reboot.value is None
        with pytest.raises(ValueError, match="missing evidence"):
            result.to_legacy()
    if profile["id"] == "pacman":
        assert (
            profile["scopes"]["single"]
            == profile["scopes"]["selected"]
            == "unsupported"
        )


def test_matrix_inventory_is_complete_and_public_synthetic() -> None:
    assert _MATRIX["schema"] == 1
    assert _MATRIX["provenance"] == "synthetic-contract-cases-not-host-captures"
    assert {p["id"] for p in _MATRIX["profiles"]} == {
        "apt",
        "dnf4",
        "dnf5",
        "zypper",
        "pacman",
        "apk",
        "portage",
    }


@pytest.mark.parametrize(
    "state",
    [EvidenceState.UNKNOWN, EvidenceState.UNAVAILABLE, EvidenceState.UNSUPPORTED],
)
def test_missing_security_or_reboot_is_never_zero_false_or_legacy(
    state: EvidenceState,
) -> None:
    missing = ObservedValue(state, reason="linux.signal_missing")
    base = _inventory()
    for snapshot in (
        replace(base, security=missing),
        replace(base, reboot=missing),
        replace(base, packages=(replace(_row(), security=missing),)),
    ):
        with pytest.raises(ValueError, match="missing evidence"):
            snapshot.to_legacy()
    assert missing.value is None
    assert missing.state is state
    assert missing.reason == "linux.signal_missing"


def test_known_zero_and_false_round_trip_without_changing_legacy_semantics() -> None:
    for legacy in (
        PackageStatus(0, 0, False),
        PackageStatus(
            1,
            1,
            True,
            (
                PackageInfo(
                    name="package-01",
                    old_version="1",
                    new_version="2",
                    is_security=True,
                ),
            ),
        ),
    ):
        normalized = InventoryEvidence.from_legacy(legacy)
        assert normalized.to_legacy() == legacy
        assert normalized.details_complete
    snapshot = _inventory()
    assert snapshot.to_legacy().security_updates == 1
    assert snapshot.to_legacy().reboot_required is False
    with pytest.raises(FrozenInstanceError):
        snapshot.total = 0
    with pytest.raises(FrozenInstanceError):
        snapshot.security.value = 0


@pytest.mark.parametrize(
    ("state", "value", "reason"),
    [
        (EvidenceState.KNOWN, None, None),
        (EvidenceState.KNOWN, "untrusted", None),
        (EvidenceState.KNOWN, 0, "linux.reason"),
        (EvidenceState.UNKNOWN, 0, "linux.reason"),
        (EvidenceState.UNKNOWN, None, None),
        (EvidenceState.UNAVAILABLE, None, "unsafe raw detail"),
        ("known", 0, None),
    ],
)
def test_observation_rejects_ambiguous_evidence_safely(
    state: EvidenceState, value: object, reason: str | None
) -> None:
    with pytest.raises(ValueError, match=r"^Invalid package observation evidence$"):
        ObservedValue(state, value, reason)


@pytest.mark.parametrize(
    "change",
    [
        {"total": True},
        {"total": -1},
        {"packages": [_row()]},
        {"packages": ({"name": "untrusted"},)},
        {"security": {"value": 0}},
        {"reboot": {"value": False}},
        {"total": 0, "packages": (_row(),)},
        {"packages": (_row(), _row())},
        {"security": ObservedValue(EvidenceState.KNOWN, True)},
        {"security": ObservedValue(EvidenceState.KNOWN, -1)},
        {"security": ObservedValue(EvidenceState.KNOWN, 3)},
        {"security": ObservedValue(EvidenceState.KNOWN, 0)},
        {"reboot": ObservedValue(EvidenceState.KNOWN, 0)},
    ],
)
def test_inventory_rejects_incoherent_counts_and_boolean_coercion(
    change: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="Invalid"):
        replace(_inventory(), **change)


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", ""), ("old_version", "x" * 256), ("new_version", None)],
)
def test_package_detail_validates_normalized_fields(field: str, value: object) -> None:
    with pytest.raises(ValueError, match="normalized package detail"):
        replace(_row(), **{field: value})


def test_package_classification_is_boolean_or_explicitly_missing() -> None:
    with pytest.raises(ValueError, match="boolean observation"):
        replace(_row(), security=ObservedValue(EvidenceState.KNOWN, 1))


def test_bounded_rows_preserve_larger_independent_totals() -> None:
    snapshot = InventoryEvidence(
        100,
        ObservedValue(EvidenceState.KNOWN, 70),
        ObservedValue(EvidenceState.UNKNOWN, reason="linux.probe_missing"),
        tuple(_row(f"package-{i}", True) for i in range(MAX_PACKAGE_DETAILS)),
    )
    assert snapshot.total == 100
    assert snapshot.security.value == 70
    assert len(snapshot.packages) == MAX_PACKAGE_DETAILS
    assert not snapshot.details_complete
    with pytest.raises(ValueError, match="inventory counts"):
        replace(snapshot, packages=(*snapshot.packages, _row("extra")))


def test_documented_operation_table_matches_machine_readable_cases() -> None:
    document = (
        Path(__file__).parents[2] / "docs/02-architecture/linux-provider-matrix.md"
    ).read_text()
    for profile in _MATRIX["profiles"]:
        cells = [
            profile["id"],
            "; ".join(profile["targets"]),
            *(profile["scopes"][s.value] for s in UpdateScope),
            profile["security"],
            profile["reboot"],
        ]
        assert "| " + " | ".join(cells) + " |" in document
