"""FastAPI composition root for the native backend."""

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
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
)
from .ssh_keys import SshKeyStore
from .version import __version__

_bearer = HTTPBearer(auto_error=False)


def create_app(
    settings: Settings | None = None,
    *,
    executor: AutomationExecutor | None = None,
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

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await database.async_migrate()
        await keys.async_ensure()
        await jobs.async_start()
        try:
            yield
        finally:
            await jobs.async_stop()

    app = FastAPI(
        title="Homelab Updates Backend",
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

    async def authorize_ui(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> None:
        if not resolved.ingress_mode:
            await authorize(credentials)

    async def verify_csrf(
        supplied: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> None:
        if supplied is None or not secrets.compare_digest(supplied, csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid request token")

    authenticated = [Depends(authorize)]
    ui_authenticated = [Depends(authorize_ui)]
    ui_mutation = [Depends(authorize_ui), Depends(verify_csrf)]

    @app.get("/", response_class=HTMLResponse)
    async def user_interface() -> HTMLResponse:
        html = _UI_HTML.replace("__CSRF_TOKEN__", csrf_token).replace(
            "__INGRESS_MODE__", "true" if resolved.ingress_mode else "false"
        )
        return HTMLResponse(html)

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/info", response_model=InfoResponse, dependencies=authenticated)
    async def info() -> InfoResponse:
        return InfoResponse(
            name="Homelab Updates Backend",
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


_UI_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="csrf-token" content="__CSRF_TOKEN__"><title>Homelab Updates</title>
<style>
:root{color-scheme:dark;--bg:#111827;--card:#1f2937;--line:#374151;--text:#f3f4f6;--muted:#9ca3af;--accent:#03a9f4;--danger:#ef4444}
*{box-sizing:border-box}body{margin:0;font:15px system-ui;background:var(--bg);color:var(--text)}main{max-width:1100px;margin:auto;padding:24px}
h1{margin:0 0 6px}h2{font-size:18px}.sub{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-top:20px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}input,select,button{font:inherit;border-radius:7px;border:1px solid var(--line);padding:9px;background:#111827;color:var(--text)}
input{width:100%;margin:4px 0}button{cursor:pointer}button.primary{background:var(--accent);color:#001018}.danger{color:#fecaca;border-color:var(--danger)}
.row{display:flex;gap:8px;align-items:center;justify-content:space-between;border-top:1px solid var(--line);padding:10px 0}.actions{display:flex;gap:6px;flex-wrap:wrap}.mono{font-family:ui-monospace;overflow-wrap:anywhere}.error{color:#fca5a5}
</style></head><body><main><h1>Homelab Updates</h1><div class="sub">Native backend management</div>
<p id="auth"><input id="token" type="password" placeholder="API token for standalone mode"><button onclick="load()">Connect</button></p><p id="message"></p>
<div class="grid"><section><h2>Dashboard</h2><div id="dashboard"></div></section><section><h2>Public SSH key</h2><p class="sub">Install this key in the selected SSH user's authorized_keys file, then run Test.</p><div id="key" class="mono"></div><button onclick="copyKey()">Copy key</button></section><section><h2>Add host</h2>
<input id="host-name" placeholder="Display name"><input id="host-address" placeholder="node-01.example.invalid"><input id="host-user" placeholder="automation"><button class="primary" onclick="addHost()">Add host</button></section>
<section><h2>Hosts</h2><div id="hosts"></div></section><section><h2>Add command task</h2><input id="task-name" placeholder="Task name"><input id="task-argv" placeholder='Command argv, e.g. ["uptime"]'><button class="primary" onclick="addTask()">Add task</button></section>
<section><h2>Custom tasks</h2><div id="tasks"></div></section><section><h2>Recent jobs</h2><div id="jobs"></div><pre id="log" class="mono"></pre></section></div></main>
<script>
const ingress=__INGRESS_MODE__,csrf=document.querySelector('meta[name="csrf-token"]').content;
if(ingress)document.getElementById('auth').hidden=true;let state={hosts:[],custom_tasks:[],jobs:[]};
async function api(path,options={}){options.headers={...(options.headers||{}),'X-CSRF-Token':csrf};const token=document.getElementById('token').value;if(!ingress&&token)options.headers.Authorization=`Bearer ${token}`;const response=await fetch(`ui-api/${path}`,options);if(!response.ok)throw new Error((await response.json()).detail||response.statusText);return response.status===204?null:response.json()}
function esc(v){const d=document.createElement('div');d.textContent=v??'';return d.innerHTML}
async function load(){try{state=await api('snapshot');render();message('')}catch(e){message(e.message,true)}}
function message(v,bad=false){const e=document.getElementById('message');e.textContent=v;e.className=bad?'error':''}
function render(){const running=state.jobs.filter(j=>j.state==='queued'||j.state==='running').length,failed=state.jobs.filter(j=>j.state==='failed').length;document.getElementById('dashboard').innerHTML=`<div class="row"><span>Backend</span><span>healthy</span></div><div class="row"><span>Hosts</span><span>${state.hosts.length}</span></div><div class="row"><span>Active jobs</span><span>${running}</span></div><div class="row"><span>Failed jobs</span><span>${failed}</span></div>`;document.getElementById('key').textContent=state.public_key;document.getElementById('hosts').innerHTML=state.hosts.map(h=>`<div class="row"><span>${esc(h.name)}<br><small>${esc(h.status||'not checked')} · ${h.updates} updates</small></span><span class="actions"><button onclick="act('${h.id}','test_connection')">Test</button><button onclick="act('${h.id}','check_updates')">Check</button><button onclick="dangerAct('${h.id}','update')">Update</button><button class="danger" onclick="dangerAct('${h.id}','reboot')">Reboot</button><button onclick="editHost('${h.id}')">Edit</button><button class="danger" onclick="delHost('${h.id}')">Delete</button></span></div>`).join('');document.getElementById('tasks').innerHTML=state.custom_tasks.map(t=>`<div class="row"><span>${esc(t.name)}<br><small>${esc(t.description)}</small></span><span class="actions">${state.hosts.map(h=>`<button onclick="runTask('${h.id}','${t.id}')">${esc(h.name)}</button>`).join('')}<button onclick="editTask('${t.id}')">Edit</button><button class="danger" onclick="delTask('${t.id}')">Delete</button></span></div>`).join('');document.getElementById('jobs').innerHTML=state.jobs.map(j=>`<div class="row"><span>${esc(j.action)}<br><small>${esc(j.created_at)}</small></span><span class="actions"><span>${esc(j.state)}</span><button onclick="showLog('${j.id}')">Log</button></span></div>`).join('')}
async function mutate(path,method='POST',body){try{await api(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});await load()}catch(e){message(e.message,true)}}
function addHost(){mutate('hosts','POST',{name:document.getElementById('host-name').value,address:document.getElementById('host-address').value,username:document.getElementById('host-user').value})}
function addTask(){try{mutate('custom-tasks','POST',{name:document.getElementById('task-name').value,mode:'command',argv:JSON.parse(document.getElementById('task-argv').value)})}catch(e){message(e.message,true)}}
function act(h,a){mutate(`hosts/${h}/actions/${a}`)}function dangerAct(h,a){if(confirm(`Run ${a} on this host?`))act(h,a)}function runTask(h,t){if(confirm('Run this custom task on the selected host?'))mutate(`hosts/${h}/tasks/${t}`)}
function editHost(id){const h=state.hosts.find(v=>v.id===id),name=prompt('Display name',h.name),address=prompt('Address',h.address),username=prompt('SSH user',h.username);if(name&&address&&username)mutate(`hosts/${id}`,'PATCH',{name,address,username})}
function editTask(id){const t=state.custom_tasks.find(v=>v.id===id),name=prompt('Task name',t.name),raw=prompt('Command argv (JSON)',JSON.stringify(t.argv));if(name&&raw)try{mutate(`custom-tasks/${id}`,'PATCH',{name,argv:JSON.parse(raw)})}catch(e){message(e.message,true)}}
async function showLog(id){try{const log=await api(`jobs/${id}/log`);document.getElementById('log').textContent=log.output+(log.truncated?'\n[truncated]':'')}catch(e){message(e.message,true)}}
function copyKey(){navigator.clipboard.writeText(state.public_key).then(()=>message('Public key copied')).catch(e=>message(e.message,true))}
function delHost(h){if(confirm('Delete this host?'))mutate(`hosts/${h}`,'DELETE')}function delTask(t){if(confirm('Delete this task?'))mutate(`custom-tasks/${t}`,'DELETE')}load();
</script></body></html>"""
