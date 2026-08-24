"""FastAPI composition root for the native backend."""

import asyncio
import secrets
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .automation import AnsibleExecutor, AutomationExecutor
from .config import Settings
from .custom_tasks import CustomTaskRepository, ShellTasksDisabledError
from .database import Database
from .hosts import DuplicateHostError, HostRepository
from .jobs import JobManager, JobRepository
from .models import (
    CustomTask,
    CustomTaskCreate,
    CustomTaskPatch,
    Host,
    HostCreate,
    HostPatch,
    InfoResponse,
    Job,
    JobAction,
    JobLog,
    PublicKeyResponse,
    UiLoginRequest,
    UiSessionResponse,
)
from .ssh_keys import SshKeyStore
from .ui import UI_HTML, UI_JAVASCRIPT, UI_STYLESHEET
from .ui_sessions import UI_SESSION_COOKIE, UI_SESSION_COOKIE_PATH, UiSessionStore
from .version import __version__

_bearer = HTTPBearer(auto_error=False)


async def _resolve_supervisor_ingress_addresses() -> frozenset[str]:
    """Resolve the stable Supervisor alias without persisting an environment IP."""
    try:
        address_info = await asyncio.get_running_loop().getaddrinfo(
            "supervisor",
            None,
            type=socket.SOCK_STREAM,
        )
    except OSError as err:
        raise RuntimeError("Unable to resolve the Supervisor ingress proxy") from err
    addresses = frozenset(
        address for result in address_info if isinstance((address := result[4][0]), str)
    )
    if not addresses:
        raise RuntimeError("Supervisor ingress proxy resolved without an IP address")
    return addresses


def create_app(
    settings: Settings | None = None,
    *,
    executor: AutomationExecutor | None = None,
    session_store: UiSessionStore | None = None,
    ingress_proxy_addresses: frozenset[str] | None = None,
) -> FastAPI:
    """Build an isolated application instance for production or tests."""
    resolved = settings or Settings.from_env()
    database = Database(resolved.database_path)
    hosts = HostRepository(database)
    custom_tasks = CustomTaskRepository(
        database, allow_shell=resolved.allow_shell_tasks
    )
    keys = SshKeyStore(resolved.private_key_path)
    jobs_repository = JobRepository(database)
    jobs = JobManager(
        jobs_repository,
        hosts,
        custom_tasks,
        executor
        or AnsibleExecutor(resolved.private_key_path, resolved.known_hosts_path),
        worker_count=resolved.worker_count,
    )
    csrf_token = secrets.token_urlsafe(32)
    ui_sessions = session_store or UiSessionStore()
    trusted_ingress_addresses = ingress_proxy_addresses or frozenset()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        nonlocal trusted_ingress_addresses
        if resolved.ingress_mode and ingress_proxy_addresses is None:
            trusted_ingress_addresses = await _resolve_supervisor_ingress_addresses()
        await database.async_migrate()
        await keys.async_ensure()
        await jobs.async_start()
        try:
            yield
        finally:
            await jobs.async_stop()

    app = FastAPI(
        title="Homelab Commander Backend",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    async def authorize(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> None:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
        if not secrets.compare_digest(credentials.credentials, resolved.api_token):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication failed")

    async def authorize_ingress_source(request: Request) -> None:
        if not resolved.ingress_mode:
            return
        if (
            request.client is None
            or request.client.host not in trusted_ingress_addresses
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Ingress access required",
            )

    async def authorize_ui(
        request: Request,
        session_id: Annotated[str | None, Cookie(alias=UI_SESSION_COOKIE)] = None,
    ) -> None:
        if resolved.ingress_mode:
            await authorize_ingress_source(request)
            return
        if not ui_sessions.authenticate(session_id):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "UI session expired")

    async def verify_csrf(
        supplied: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> None:
        if supplied is None or not secrets.compare_digest(supplied, csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid request token")

    authenticated = [Depends(authorize)]
    ui_authenticated = [Depends(authorize_ui)]
    ui_mutation = [Depends(authorize_ui), Depends(verify_csrf)]

    def info_response() -> InfoResponse:
        return InfoResponse(
            name="Homelab Commander Backend",
            version=__version__,
            api_version="v1",
            capabilities=(
                "host_crud",
                "managed_ssh_key",
                "persistent_jobs",
                "custom_tasks",
            ),
        )

    @app.get(
        "/",
        response_class=HTMLResponse,
        dependencies=[Depends(authorize_ingress_source)],
    )
    async def user_interface() -> HTMLResponse:
        ingress = "true" if resolved.ingress_mode else "false"
        api_base = "ui-api/"
        html = (
            UI_HTML
            .replace("__CSRF_TOKEN__", csrf_token)
            .replace("__INGRESS_MODE__", ingress)
            .replace("__API_BASE__", api_base)
        )
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                    "base-uri 'self'; frame-ancestors 'self'"
                ),
            },
        )

    @app.get(
        "/ui.js",
        include_in_schema=False,
        dependencies=[Depends(authorize_ingress_source)],
    )
    async def user_interface_javascript() -> Response:
        return Response(UI_JAVASCRIPT, media_type="application/javascript")

    @app.get(
        "/ui.css",
        include_in_schema=False,
        dependencies=[Depends(authorize_ingress_source)],
    )
    async def user_interface_stylesheet() -> Response:
        return Response(UI_STYLESHEET, media_type="text/css")

    @app.post(
        "/ui-api/auth/login",
        response_model=UiSessionResponse,
        dependencies=[Depends(verify_csrf)],
    )
    async def ui_login(
        data: UiLoginRequest,
        request: Request,
        response: Response,
        existing_session_id: Annotated[
            str | None, Cookie(alias=UI_SESSION_COOKIE)
        ] = None,
    ) -> UiSessionResponse:
        """Exchange the API token for a process-local opaque browser session."""
        if resolved.ingress_mode:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        if not secrets.compare_digest(data.api_token, resolved.api_token):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication failed")
        ui_sessions.revoke(existing_session_id)
        session_id = ui_sessions.create()
        response.set_cookie(
            UI_SESSION_COOKIE,
            session_id,
            secure=request.url.scheme == "https",
            httponly=True,
            samesite="strict",
            path=UI_SESSION_COOKIE_PATH,
        )
        return UiSessionResponse(authenticated=True)

    @app.get("/ui-api/auth/session", response_model=UiSessionResponse)
    async def ui_session(
        response: Response,
        session_id: Annotated[str | None, Cookie(alias=UI_SESSION_COOKIE)] = None,
    ) -> UiSessionResponse:
        """Recover a standalone page after reload without exposing credentials."""
        if resolved.ingress_mode:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        if not ui_sessions.authenticate(session_id):
            response.delete_cookie(UI_SESSION_COOKIE, path=UI_SESSION_COOKIE_PATH)
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return UiSessionResponse(authenticated=False)
        return UiSessionResponse(authenticated=True)

    @app.post(
        "/ui-api/auth/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(verify_csrf)],
    )
    async def ui_logout(
        response: Response,
        session_id: Annotated[str | None, Cookie(alias=UI_SESSION_COOKIE)] = None,
    ) -> Response:
        """Revoke the server session and expire its browser cookie."""
        if resolved.ingress_mode:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        ui_sessions.revoke(session_id)
        response.delete_cookie(UI_SESSION_COOKIE, path=UI_SESSION_COOKIE_PATH)
        response.status_code = status.HTTP_204_NO_CONTENT
        return response

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/info", response_model=InfoResponse, dependencies=authenticated)
    async def info() -> InfoResponse:
        return info_response()

    @app.get(
        "/api/v1/public-key",
        response_model=PublicKeyResponse,
        dependencies=authenticated,
    )
    async def public_key() -> PublicKeyResponse:
        return PublicKeyResponse(
            algorithm="ssh-ed25519", public_key=await keys.async_public_key()
        )

    @app.get("/api/v1/hosts", response_model=list[Host], dependencies=authenticated)
    async def list_hosts() -> tuple[Host, ...]:
        return await hosts.async_list()

    @app.post(
        "/api/v1/hosts",
        response_model=Host,
        status_code=status.HTTP_201_CREATED,
        dependencies=authenticated,
    )
    async def create_host(data: HostCreate) -> Host:
        try:
            return await hosts.async_create(data)
        except DuplicateHostError as err:
            raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from err

    @app.get("/api/v1/hosts/{host_id}", response_model=Host, dependencies=authenticated)
    async def get_host(host_id: UUID) -> Host:
        host = await hosts.async_get(host_id)
        if host is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Host not found")
        return host

    @app.patch(
        "/api/v1/hosts/{host_id}", response_model=Host, dependencies=authenticated
    )
    async def patch_host(host_id: UUID, data: HostPatch) -> Host:
        try:
            host = await hosts.async_patch(host_id, data)
        except DuplicateHostError as err:
            raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from err
        if host is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Host not found")
        return host

    @app.delete(
        "/api/v1/hosts/{host_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=authenticated,
    )
    async def delete_host(host_id: UUID) -> Response:
        if not await hosts.async_delete(host_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Host not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def enqueue(action: JobAction, host_id: UUID) -> Job:
        try:
            return await jobs.async_enqueue(action, host_id)
        except KeyError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Host not found") from err

    @app.post(
        "/api/v1/hosts/{host_id}/actions/test-connection",
        response_model=Job,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=authenticated,
    )
    async def test_connection(host_id: UUID) -> Job:
        return await enqueue(JobAction.TEST_CONNECTION, host_id)

    @app.post(
        "/api/v1/hosts/{host_id}/actions/check-updates",
        response_model=Job,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=authenticated,
    )
    async def check_updates(host_id: UUID) -> Job:
        return await enqueue(JobAction.CHECK_UPDATES, host_id)

    @app.post(
        "/api/v1/hosts/{host_id}/actions/update",
        response_model=Job,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=authenticated,
    )
    async def update_host(host_id: UUID) -> Job:
        return await enqueue(JobAction.UPDATE, host_id)

    @app.post(
        "/api/v1/hosts/{host_id}/actions/reboot",
        response_model=Job,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=authenticated,
    )
    async def reboot_host(host_id: UUID) -> Job:
        return await enqueue(JobAction.REBOOT, host_id)

    @app.post(
        "/api/v1/actions/check",
        response_model=list[Job],
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=authenticated,
    )
    async def check_all_hosts() -> tuple[Job, ...]:
        return tuple([
            await jobs.async_enqueue(JobAction.CHECK_UPDATES, host.id)
            for host in await hosts.async_list()
        ])

    @app.get("/api/v1/jobs", response_model=list[Job], dependencies=authenticated)
    async def list_jobs(
        limit: int = Query(default=100, ge=1, le=500),
    ) -> tuple[Job, ...]:
        return await jobs_repository.async_list(limit=limit)

    @app.get("/api/v1/jobs/{job_id}", response_model=Job, dependencies=authenticated)
    async def get_job(job_id: UUID) -> Job:
        job = await jobs_repository.async_get(job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        return job

    @app.get(
        "/api/v1/jobs/{job_id}/log",
        response_model=JobLog,
        dependencies=authenticated,
    )
    async def get_job_log(job_id: UUID) -> JobLog:
        job = await jobs_repository.async_get(job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        log = await jobs_repository.async_log(job_id)
        return log or JobLog(job_id=job_id, output="", truncated=False)

    @app.get(
        "/api/v1/custom-tasks",
        response_model=list[CustomTask],
        dependencies=authenticated,
    )
    async def list_custom_tasks() -> tuple[CustomTask, ...]:
        return await custom_tasks.async_list()

    @app.post(
        "/api/v1/custom-tasks",
        response_model=CustomTask,
        status_code=status.HTTP_201_CREATED,
        dependencies=authenticated,
    )
    async def create_custom_task(data: CustomTaskCreate) -> CustomTask:
        try:
            return await custom_tasks.async_create(data)
        except ShellTasksDisabledError as err:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(err)) from err

    @app.patch(
        "/api/v1/custom-tasks/{task_id}",
        response_model=CustomTask,
        dependencies=authenticated,
    )
    async def patch_custom_task(task_id: UUID, data: CustomTaskPatch) -> CustomTask:
        try:
            task = await custom_tasks.async_patch(task_id, data)
        except ShellTasksDisabledError as err:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(err)) from err
        if task is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Custom task not found")
        return task

    @app.delete(
        "/api/v1/custom-tasks/{task_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=authenticated,
    )
    async def delete_custom_task(task_id: UUID) -> Response:
        if not await custom_tasks.async_delete(task_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Custom task not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/v1/hosts/{host_id}/actions/tasks/{task_id}",
        response_model=Job,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=authenticated,
    )
    async def run_custom_task(host_id: UUID, task_id: UUID) -> Job:
        try:
            return await jobs.async_enqueue_custom(task_id, host_id)
        except KeyError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(err)) from err
        except ValueError as err:
            raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from err

    @app.get("/ui-api/snapshot", dependencies=ui_authenticated)
    async def ui_snapshot() -> dict[str, object]:
        """Return the bounded data needed by the Ingress management page."""
        return {
            "hosts": await hosts.async_list(),
            "custom_tasks": await custom_tasks.async_list(),
            "jobs": await jobs_repository.async_list(limit=50),
            "public_key": await keys.async_public_key(),
            "shell_tasks_enabled": resolved.allow_shell_tasks,
        }

    @app.get("/ui-api/info", response_model=InfoResponse, dependencies=ui_authenticated)
    async def ui_info() -> InfoResponse:
        return info_response()

    @app.get("/ui-api/hosts", response_model=list[Host], dependencies=ui_authenticated)
    async def ui_list_hosts() -> tuple[Host, ...]:
        return await hosts.async_list()

    @app.get(
        "/ui-api/public-key",
        response_model=PublicKeyResponse,
        dependencies=ui_authenticated,
    )
    async def ui_public_key() -> PublicKeyResponse:
        return PublicKeyResponse(
            algorithm="ssh-ed25519", public_key=await keys.async_public_key()
        )

    @app.get(
        "/ui-api/custom-tasks",
        response_model=list[CustomTask],
        dependencies=ui_authenticated,
    )
    async def ui_list_custom_tasks() -> tuple[CustomTask, ...]:
        return await custom_tasks.async_list()

    @app.get("/ui-api/jobs", response_model=list[Job], dependencies=ui_authenticated)
    async def ui_list_jobs() -> tuple[Job, ...]:
        return await jobs_repository.async_list(limit=100)

    @app.get("/ui-api/jobs/{job_id}", response_model=Job, dependencies=ui_authenticated)
    async def ui_get_job(job_id: UUID) -> Job:
        job = await jobs_repository.async_get(job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        return job

    @app.post(
        "/ui-api/hosts",
        response_model=Host,
        status_code=status.HTTP_201_CREATED,
        dependencies=ui_mutation,
    )
    async def ui_create_host(data: HostCreate) -> Host:
        try:
            return await hosts.async_create(data)
        except DuplicateHostError as err:
            raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from err

    @app.patch(
        "/ui-api/hosts/{host_id}",
        response_model=Host,
        dependencies=ui_mutation,
    )
    async def ui_patch_host(host_id: UUID, data: HostPatch) -> Host:
        try:
            host = await hosts.async_patch(host_id, data)
        except DuplicateHostError as err:
            raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from err
        if host is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Host not found")
        return host

    @app.delete(
        "/ui-api/hosts/{host_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=ui_mutation,
    )
    async def ui_delete_host(host_id: UUID) -> Response:
        if not await hosts.async_delete(host_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Host not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/ui-api/custom-tasks",
        response_model=CustomTask,
        status_code=status.HTTP_201_CREATED,
        dependencies=ui_mutation,
    )
    async def ui_create_task(data: CustomTaskCreate) -> CustomTask:
        try:
            return await custom_tasks.async_create(data)
        except ShellTasksDisabledError as err:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(err)) from err

    @app.patch(
        "/ui-api/custom-tasks/{task_id}",
        response_model=CustomTask,
        dependencies=ui_mutation,
    )
    async def ui_patch_task(task_id: UUID, data: CustomTaskPatch) -> CustomTask:
        try:
            task = await custom_tasks.async_patch(task_id, data)
        except ShellTasksDisabledError as err:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(err)) from err
        if task is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Custom task not found")
        return task

    @app.delete(
        "/ui-api/custom-tasks/{task_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=ui_mutation,
    )
    async def ui_delete_task(task_id: UUID) -> Response:
        if not await custom_tasks.async_delete(task_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Custom task not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/ui-api/jobs/{job_id}/log",
        response_model=JobLog,
        dependencies=ui_authenticated,
    )
    async def ui_job_log(job_id: UUID) -> JobLog:
        job = await jobs_repository.async_get(job_id)
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        log = await jobs_repository.async_log(job_id)
        return log or JobLog(job_id=job_id, output="", truncated=False)

    @app.post(
        "/ui-api/hosts/{host_id}/actions/{action}",
        response_model=Job,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=ui_mutation,
    )
    async def ui_host_action(host_id: UUID, action: JobAction) -> Job:
        if action is JobAction.CUSTOM_TASK:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Task ID required"
            )
        return await enqueue(action, host_id)

    @app.post(
        "/ui-api/hosts/{host_id}/tasks/{task_id}",
        response_model=Job,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=ui_mutation,
    )
    async def ui_run_task(host_id: UUID, task_id: UUID) -> Job:
        try:
            return await jobs.async_enqueue_custom(task_id, host_id)
        except KeyError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(err)) from err
        except ValueError as err:
            raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from err

    return app
