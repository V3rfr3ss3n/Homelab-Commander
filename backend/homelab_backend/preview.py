"""Explicit loopback-only UI preview with disposable data and synthetic execution."""

from argparse import ArgumentParser
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .app import create_app
from .automation import ExecutionResult, HostSnapshot
from .config import Settings
from .custom_tasks import CustomTaskRepository
from .database import Database
from .hosts import HostRepository
from .jobs import JobRepository
from .models import (
    CustomTask,
    CustomTaskCreate,
    Host,
    HostCreate,
    JobAction,
    JobState,
    PackageInfo,
    ProbeFacts,
    TaskRequirements,
)
from .task_compatibility import TaskCompatibilityService


def demo_packages(
    updates: int,
    security: int,
) -> tuple[PackageInfo, ...]:
    """Synthetic upgradable-package rows matching the host's update counters."""
    if updates <= 0:
        return ()
    names = (
        "curl",
        "vim",
        "git",
        "nginx",
        "postgresql",
        "openssh",
        "python3",
        "systemd",
        "libssl3",
        "libcurl",
        "ca-certificates",
        "coreutils",
    )
    rows: list[PackageInfo] = []
    security_count = min(security, updates)
    for i, name in enumerate(names[:updates]):
        rows.append(
            PackageInfo(
                name=name,
                old_version=f"1.{i % 9}.{i % 7}",
                new_version=f"1.{i % 9 + 1}.{i % 7}",
                is_security=i < security_count,
            )
        )
    return tuple(rows)


class PreviewExecutor:
    """Simulate every action, even when an arbitrary address is entered in the UI."""

    def __init__(self) -> None:
        self._packages: dict[UUID, tuple[PackageInfo, ...]] = {}
        self._restart_required: dict[UUID, bool] = {}
        self._providers: dict[UUID, str] = {}

    async def async_execute(
        self,
        action: JobAction,
        host: Host,
        package_name: str | None = None,
        *,
        package_names: tuple[str, ...] = (),
    ) -> ExecutionResult:
        scope = package_names or ((package_name,) if package_name else ())
        rpm = host.package_provider in {"dnf", "zypper"}
        if self._providers.get(host.id, host.package_provider) != host.package_provider:
            self._packages.pop(host.id, None)
        self._providers[host.id] = host.package_provider
        initial = host.packages
        if rpm and not initial:
            initial = tuple(
                PackageInfo(
                    name=name + ".x86_64",
                    old_version="0:1-1",
                    new_version="0:2-1",
                    is_security=None,
                )
                for name in ("curl", "git")
            )
        remaining = self._packages.setdefault(host.id, initial)
        if action is JobAction.UPDATE:
            remaining = (
                tuple(p for p in remaining if p.name not in scope) if scope else ()
            )
        self._packages[host.id] = remaining
        restart = self._restart_required.setdefault(
            host.id, host.reboot_required is True
        )
        if action is JobAction.REBOOT:
            restart = False
        self._restart_required[host.id] = restart
        snapshot = HostSnapshot(
            distribution=(
                "Fedora" if host.package_provider == "dnf" else "openSUSE Leap"
            )
            if rpm
            else host.distribution or "Debian",
            distribution_version=("45" if host.package_provider == "dnf" else "16.0")
            if rpm
            else host.distribution_version or "12",
            kernel="6.8.0-demo",
            updates=len(remaining),
            security_updates=None
            if rpm
            else sum(p.is_security is True for p in remaining),
            reboot_required=None if host.package_provider == "dnf" else restart,
            package_scopes=("full", "selected", "single") if rpm else None,
            status="ok",
            checked_at=datetime.now(UTC),
            packages=remaining,
        )
        return ExecutionResult(
            output=f"SIMULATED {action.value}: no connection or system change.",
            snapshot=snapshot,
            reboot_required=snapshot.reboot_required,
        )

    async def async_execute_custom(
        self, _task: CustomTask, _host: Host
    ) -> ExecutionResult:
        return ExecutionResult(output="SIMULATED custom task: no command was executed.")

    async def async_probe(self, _task: CustomTask, host: Host) -> ProbeFacts:
        # Availability is synthetic; OS/version restrictions still use real policy.
        return ProbeFacts(
            distribution=(host.distribution or "debian").lower(),
            version=host.distribution_version or "12",
            missing_programs=(),
            missing_packages=(),
        )


async def seed_demo(settings: Settings, executor: PreviewExecutor) -> None:
    """Populate this launch's isolated SQLite database with synthetic UI examples."""
    database = Database(settings.database_path)
    hosts = HostRepository(database)
    tasks = CustomTaskRepository(database, allow_shell=False)
    jobs = JobRepository(database)
    now = datetime.now(UTC)
    demo_hosts: list[Host] = []
    for index, (system, version, updates, security, reboot) in enumerate(
        [
            ("Debian", "12", 12, 4, True),
            ("Ubuntu", "24.04", 3, 1, False),
            ("Debian", "12", 0, 0, False),
        ],
        start=1,
    ):
        host = await hosts.async_create(
            HostCreate(
                name=f"Demo node {index:02}",
                address=f"node-{index:02}.example.invalid",
                username="automation",
            )
        )
        await hosts.async_update_status(
            host.id,
            distribution=system,
            distribution_version=version,
            kernel="6.8.0-demo",
            updates=updates,
            security_updates=security,
            reboot_required=reboot,
            status="ok",
            checked_at=now - timedelta(hours=48 if index == 3 else 1),
            packages=demo_packages(updates, security),
        )
        demo_hosts.append(host)
    task = await tasks.async_create(
        CustomTaskCreate(
            name="Demo: read uptime",
            description="Simulation only. Assign this task to a demo host to try it.",
            argv=("uptime",),
            requirements=TaskRequirements(distributions=("debian", "ubuntu")),
        )
    )
    compatibility = TaskCompatibilityService(database, tasks, hosts, executor)
    await compatibility.async_check(task.id, demo_hosts[0].id)
    await compatibility.async_assign(task.id, demo_hosts[0].id, enabled=True)
    for days_ago in range(6, -1, -1):
        for offset in range(2):
            host = demo_hosts[(days_ago + offset) % len(demo_hosts)]
            job = await jobs.async_create(JobAction.CHECK_UPDATES, host.id)
            failed = days_ago in {0, 3} and offset == 0
            await jobs.async_finish(
                job.id,
                state=JobState.FAILED if failed else JobState.SUCCESS,
                output="Synthetic demo history. No host was contacted.",
                truncated=False,
                exit_code=1 if failed else 0,
                error_code="synthetic_demo_failure" if failed else None,
            )
            finished = now - timedelta(days=days_ago, minutes=10 + offset)
            started = finished - timedelta(seconds=3)
            await database.async_execute(
                "UPDATE jobs SET created_at=?, started_at=?, finished_at=? WHERE id=?",
                (
                    started.isoformat(),
                    started.isoformat(),
                    finished.isoformat(),
                    str(job.id),
                ),
            )


class PreviewHistoryFailure:
    """One explicit, loopback-only synthetic failure followed by normal recovery."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.pending = True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            self.pending
            and scope["type"] == "http"
            and (scope.get("client") or (None,))[0] == "127.0.0.1"
            and scope["path"] in {"/ui-api/jobs/timeline", "/ui-api/jobs/page"}
            and b"start=" in scope["query_string"]
        ):
            self.pending = False
            reference = uuid4().hex
            await JSONResponse(
                {
                    "detail": "Synthetic preview history failure",
                    "error_code": "http_503",
                },
                status_code=503,
                headers={"X-Request-ID": reference, "Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        await self.app(scope, receive, send)


def create_preview(data_dir: Path, *, history_failure_once: bool = False) -> FastAPI:
    """Simulate Ingress locally: loopback is the only accepted UI source."""
    settings = Settings(
        data_dir=data_dir,
        api_token="synthetic-local-preview-token-not-for-production",
        ingress_mode=True,
    )
    executor = PreviewExecutor()
    app = create_app(
        settings, executor=executor, ingress_proxy_addresses=frozenset({"127.0.0.1"})
    )
    if history_failure_once:
        app.add_middleware(PreviewHistoryFailure)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        async with original_lifespan(application):
            await seed_demo(settings, executor)
            yield

    app.router.lifespan_context = lifespan
    return app


def main(argv: Sequence[str] | None = None) -> None:
    """Use fresh disposable data on every F5 launch; never production state."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--history-failure-once", action="store_true")
    arguments = parser.parse_args(argv)
    with TemporaryDirectory(prefix="homelab-commander-vscode-demo-") as directory:
        uvicorn.run(
            create_preview(
                Path(directory), history_failure_once=arguments.history_failure_once
            ),
            host="127.0.0.1",
            port=8100,
            proxy_headers=False,
            access_log=False,
        )


if __name__ == "__main__":
    main()
