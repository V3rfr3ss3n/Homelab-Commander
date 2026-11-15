"""Executable contract examples, with no provider transport or host execution."""

from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from uuid import UUID

import pytest

from backend.homelab_backend.contracts.capabilities import (
    AuthorizationRequirement,
    CapabilityAssessment,
    CapabilityDefinition,
    CapabilityKey,
    CapabilityState,
    ContractVersion,
    ExecutionMode,
    RecoveryMode,
    RiskClass,
    SchemaRef,
)
from backend.homelab_backend.contracts.providers import (
    CapabilityProvider,
    PayloadValidator,
)
from backend.homelab_backend.contracts.resources import (
    HostResource,
    ManagedServiceResource,
    ProviderBinding,
    RelationshipKind,
    ResourceKind,
    ResourceRef,
    ResourceRelationship,
)
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import HostCreate, JobAction, JobState
from backend.homelab_backend.resource_compatibility import project_host
from backend.tests.test_backend_api import AUTH, FakeExecutor, _client

HOST_ID = UUID("00000000-0000-4000-8000-000000000001")
SERVICE_ID = UUID("00000000-0000-4000-8000-000000000002")
CONNECTION_ID = UUID("00000000-0000-4000-8000-000000000003")


def _definition(**changes: object) -> CapabilityDefinition:
    definition = CapabilityDefinition(
        key=CapabilityKey("system.status.read"),
        resource_kinds=frozenset({ResourceKind.HOST}),
        input_schema=SchemaRef("system.status.read.input"),
        output_schema=SchemaRef("system.status.read.output"),
        authorization=AuthorizationRequirement("resources.status.read"),
        risk=RiskClass.READ_ONLY,
        execution=ExecutionMode.READ,
        recovery=RecoveryMode.RETRY_READ,
        prerequisites=("provider.connected",),
        limitations=("Status is an observation, not permission to mutate",),
    )
    return replace(definition, **changes)


def test_resources_preserve_internal_identity_and_optional_host() -> None:
    host = HostResource(HOST_ID, "Node 01")
    binding = ProviderBinding(
        "minecraft.pterodactyl_client", CONNECTION_ID, "demo_server_01"
    )
    service = ManagedServiceResource(SERVICE_ID, "Demo Paper", "minecraft", binding)
    assert host.ref == ResourceRef(ResourceKind.HOST, HOST_ID)
    assert service.ref == ResourceRef(ResourceKind.MANAGED_SERVICE, SERVICE_ID)
    assert service.host is None
    assert service.id != service.binding.connection_id
    assert str(service.id) != binding.external_id
    assert "demo_server_01" not in repr(service)
    linked = replace(service, host=host.ref)
    assert linked.id == service.id
    assert linked.host == host.ref
    with pytest.raises(FrozenInstanceError):
        linked.name = "Changed"
    for target in (service.ref, ResourceRef(ResourceKind.HOST, SERVICE_ID)):
        with pytest.raises(ValueError, match="distinct existing host"):
            replace(service, host=target)
    with pytest.raises(ValueError, match="identities must differ"):
        replace(service, id=CONNECTION_ID)
    with pytest.raises(ValueError, match="service type"):
        replace(service, service_type="unsafe/type")
    with pytest.raises(ValueError, match="provider contract"):
        replace(binding, provider_id="invalid")
    with pytest.raises(ValueError, match="opaque provider"):
        replace(binding, external_id="https://service.example.invalid/secret")


@pytest.mark.parametrize(
    ("relationship", "source_kind", "target_kind"),
    [
        (
            RelationshipKind.RUNS_SERVICE,
            ResourceKind.HOST,
            ResourceKind.MANAGED_SERVICE,
        ),
        (
            RelationshipKind.HOSTS_INSTANCE,
            ResourceKind.HOST,
            ResourceKind.VIRTUAL_MACHINE,
        ),
        (RelationshipKind.HOSTS_INSTANCE, ResourceKind.HOST, ResourceKind.CONTAINER),
        (
            RelationshipKind.CORRESPONDS_TO_HOST,
            ResourceKind.VIRTUAL_MACHINE,
            ResourceKind.HOST,
        ),
        (
            RelationshipKind.CORRESPONDS_TO_HOST,
            ResourceKind.CONTAINER,
            ResourceKind.HOST,
        ),
        (
            RelationshipKind.MANAGED_BY,
            ResourceKind.MANAGED_SERVICE,
            ResourceKind.MANAGED_SERVICE,
        ),
        (
            RelationshipKind.MANAGED_BY,
            ResourceKind.VIRTUAL_MACHINE,
            ResourceKind.MANAGED_SERVICE,
        ),
    ],
)
def test_relationship_direction_and_no_identity_merging(
    relationship: RelationshipKind, source_kind: ResourceKind, target_kind: ResourceKind
) -> None:
    edge = ResourceRelationship(
        relationship,
        ResourceRef(source_kind, HOST_ID),
        ResourceRef(target_kind, SERVICE_ID),
    )
    assert edge.source.id == HOST_ID
    with pytest.raises(ValueError, match="endpoints"):
        replace(edge, target=ResourceRef(target_kind, HOST_ID))
    with pytest.raises(ValueError, match="endpoints"):
        replace(
            edge,
            source=ResourceRef(ResourceKind.CONTAINER, HOST_ID),
            target=ResourceRef(ResourceKind.CONTAINER, SERVICE_ID),
        )


@pytest.mark.parametrize(
    "version", [ContractVersion(1, 0), ContractVersion(1, 2), ContractVersion(2, 0)]
)
def test_capability_schema_versions_and_immutable_support(
    version: ContractVersion,
) -> None:
    definition = _definition(key=CapabilityKey("system.status.read", version))
    assert definition.key.version == version
    assert definition.resource_kinds == frozenset({ResourceKind.HOST})
    assert definition.authorization.permission == "resources.status.read"
    assert definition.prerequisites == ("provider.connected",)
    with pytest.raises(FrozenInstanceError):
        definition.risk = RiskClass.MUTATING


@pytest.mark.parametrize(("major", "minor"), [(0, 0), (1, -1)])
def test_invalid_contract_versions(major: int, minor: int) -> None:
    with pytest.raises(ValueError, match="version"):
        ContractVersion(major, minor)


@pytest.mark.parametrize(
    "value",
    ["invalid", "Shell.RUN", "https://service.example.invalid", "system.read;command"],
)
def test_contract_identifiers_are_not_executable_or_urls(value: str) -> None:
    for constructor in (CapabilityKey, SchemaRef, AuthorizationRequirement):
        with pytest.raises(ValueError, match="identifier"):
            constructor(value)


@pytest.mark.parametrize(
    "changes",
    [
        {"resource_kinds": frozenset()},
        {"risk": RiskClass.MUTATING},
        {"risk": RiskClass.MUTATING, "execution": ExecutionMode.JOB},
        {
            "risk": RiskClass.DESTRUCTIVE,
            "execution": ExecutionMode.JOB,
            "recovery": RecoveryMode.NEVER_REPLAY,
        },
        {
            "risk": RiskClass.DISRUPTIVE,
            "execution": ExecutionMode.JOB,
            "recovery": RecoveryMode.REVALIDATE,
            "authorization": AuthorizationRequirement(
                "service.restart", human_approval=True
            ),
        },
        {"prerequisites": ("invalid",)},
    ],
)
def test_capability_declarations_reject_unsafe_combinations(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match=r"requires|require|identifier"):
        _definition(**changes)


def test_explicit_mutation_and_restart_have_different_contracts() -> None:
    update = _definition(
        key=CapabilityKey("packages.update.full"),
        authorization=AuthorizationRequirement("packages.update.full"),
        risk=RiskClass.MUTATING,
        execution=ExecutionMode.JOB,
        recovery=RecoveryMode.REVALIDATE,
    )
    restart = _definition(
        key=CapabilityKey("service.lifecycle.restart"),
        risk=RiskClass.DISRUPTIVE,
        execution=ExecutionMode.JOB,
        recovery=RecoveryMode.NEVER_REPLAY,
        authorization=AuthorizationRequirement("service.restart", human_approval=True),
    )
    assert update.key != restart.key
    assert restart.authorization.human_approval
    assert update.recovery is RecoveryMode.REVALIDATE


@dataclass(frozen=True, slots=True)
class NoInput:
    """Synthetic empty input DTO."""


@dataclass(frozen=True, slots=True)
class StatusResult:
    state: str


class EmptyInputValidator:
    def validate(self, value: object) -> NoInput:
        if not isinstance(value, dict) or value:
            raise ValueError("Invalid status input")
        return NoInput()


class StatusOutputValidator:
    def validate(self, value: object) -> StatusResult:
        if (
            not isinstance(value, dict)
            or set(value) != {"state"}
            or not isinstance(value["state"], str)
            or value["state"] not in {"running", "stopped"}
        ):
            raise ValueError("Invalid normalized status output")
        return StatusResult(value["state"])


class SyntheticServiceProvider:
    """Illustrates a normalized Pterodactyl capability; never contacts its API."""

    @property
    def provider_id(self) -> str:
        return "minecraft.pterodactyl_client"

    @property
    def definition(self) -> CapabilityDefinition:
        return _definition(
            key=CapabilityKey("service.status.read"),
            resource_kinds=frozenset({ResourceKind.MANAGED_SERVICE}),
        )

    @property
    def input_validator(self) -> PayloadValidator[NoInput]:
        return EmptyInputValidator()

    @property
    def output_validator(self) -> PayloadValidator[StatusResult]:
        return StatusOutputValidator()

    async def async_assess(self, target: ResourceRef) -> CapabilityAssessment:
        definition = self.definition
        if target.kind not in definition.resource_kinds:
            return CapabilityAssessment(
                target,
                definition.key,
                CapabilityState.UNSUPPORTED,
                ("capability.resource_unsupported",),
            )
        return CapabilityAssessment(target, definition.key, CapabilityState.SUPPORTED)


async def test_typed_provider_boundary_and_four_distinct_states() -> None:
    provider: CapabilityProvider[NoInput, StatusResult] = SyntheticServiceProvider()
    assert provider.provider_id == "minecraft.pterodactyl_client"
    assert provider.input_validator.validate({}) == NoInput()
    assert provider.output_validator.validate({"state": "running"}) == StatusResult(
        "running"
    )
    supported = await provider.async_assess(
        ResourceRef(ResourceKind.MANAGED_SERVICE, SERVICE_ID)
    )
    unsupported = await provider.async_assess(ResourceRef(ResourceKind.HOST, HOST_ID))
    unavailable = replace(
        supported,
        state=CapabilityState.UNAVAILABLE,
        reason_codes=("provider.unreachable",),
    )
    blocked = replace(
        supported,
        state=CapabilityState.POLICY_BLOCKED,
        reason_codes=("policy.default_deny",),
    )
    assert (
        len({item.state for item in (supported, unsupported, unavailable, blocked)})
        == 4
    )
    assert blocked.target == supported.target
    assert not hasattr(provider, "execute")
    with pytest.raises(ValueError, match="reason code"):
        replace(supported, state=CapabilityState.UNAVAILABLE)
    with pytest.raises(ValueError, match="identifier"):
        replace(supported, reason_codes=("unsafe/raw response",))
    for value in ([], {"token": "synthetic-secret"}):
        with pytest.raises(ValueError, match="Invalid status input") as failure:
            provider.input_validator.validate(value)
        assert "synthetic-secret" not in str(failure.value)
    for value in ([], {"wrong": "synthetic-secret"}, {"state": "synthetic-secret"}):
        with pytest.raises(ValueError, match="Invalid normalized status output"):
            provider.output_validator.validate(value)


async def test_projection_preserves_database_jobs_review_and_v1(tmp_path: Path) -> None:
    database = Database(tmp_path / "homelab_updates.db")
    await database.async_migrate()
    host = await HostRepository(database).async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    jobs = JobRepository(database)
    job = await jobs.async_create(JobAction.CHECK_UPDATES, host.id)
    await jobs.async_finish(
        job.id,
        state=JobState.FAILED,
        output="Synthetic log",
        truncated=False,
        error_code="sudo_unavailable",
    )
    await jobs.async_review(job.id)
    queued = await jobs.async_create(JobAction.UPDATE, host.id)
    before = [
        tuple(row) for row in await database.async_fetch_all("SELECT * FROM jobs")
    ]
    original = host.model_dump_json()
    projected = project_host(host)
    assert projected.id == host.id
    assert projected.name == host.name
    assert host.model_dump_json() == original
    assert [
        tuple(row) for row in await database.async_fetch_all("SELECT * FROM jobs")
    ] == before
    assert (await jobs.async_get(queued.id)).state is JobState.QUEUED
    # Stop the synthetic queued job before starting the API worker: it is not
    # part of a registry projection and must never be replayed by this test.
    await jobs.async_finish(
        queued.id,
        state=JobState.CANCELLED,
        output="Synthetic cancellation",
        truncated=False,
    )
    with _client(tmp_path, FakeExecutor()) as client:
        key = client.get("/api/v1/public-key", headers=AUTH).json()
        response = client.get(f"/api/v1/hosts/{host.id}", headers=AUTH)
        assert response.json()["id"] == str(projected.id)
        assert "resource_kind" not in response.json()
        assert client.get("/api/v1/public-key", headers=AUTH).json() == key
        assert (
            client.get(f"/api/v1/jobs/{job.id}", headers=AUTH).json()["reviewed_at"]
            is not None
        )
        assert str(job.id) in {
            item["id"] for item in client.get("/api/v1/jobs", headers=AUTH).json()
        }
        assert client.get("/api/v1/resources", headers=AUTH).status_code == 200
