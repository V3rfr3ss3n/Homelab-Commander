"""Dependency-free management UI assets served by the backend."""

UI_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="csrf-token" content="__CSRF_TOKEN__"><meta name="api-base" content="__API_BASE__">
<meta name="ingress-mode" content="__INGRESS_MODE__"><title>Homelab Updates</title>
<link rel="stylesheet" href="./ui.css"><script src="./ui.js" defer></script></head>
<body><main><h1>Homelab Updates</h1><div class="sub">Native backend management</div>
<div id="connection-state" class="connection-state"><strong id="connection-label">Not connected</strong><span id="connection-hint">Enter your API token to load backend data.</span></div>
<form id="connect-form"><label id="token-field">API token<input id="token" type="password" autocomplete="off" minlength="32" required></label><button id="connect" type="submit">Connect</button><button id="disconnect" type="button" hidden>Disconnect</button></form>
<p id="message" role="status" aria-live="polite"></p>
<section id="connect-placeholder" class="connect-placeholder"><h2>Connect first</h2><p>Enter your API token to load backend data.</p></section>
<div id="protected-content" class="grid" hidden><section><h2>Dashboard</h2><div id="dashboard"></div></section>
<section><h2>Public SSH key</h2><p class="sub">Install this public key in the selected SSH user's authorized_keys file, then run Test connection.</p><div id="key" class="mono"></div><button id="copy-key" type="button">Copy key</button></section>
<section><h2>Add host</h2><form id="host-form"><input id="host-name" placeholder="Display name" required><input id="host-address" placeholder="node-01.example.invalid" required><input id="host-user" placeholder="automation" required><input id="host-port" type="number" value="22" min="1" max="65535" required><button type="submit" class="primary">Add host</button></form></section>
<section><h2>Hosts</h2><div id="hosts"></div></section>
<section><h2>Add command task</h2><form id="task-form"><input id="task-name" placeholder="Task name" required><input id="task-argv" placeholder='Command argv, e.g. ["uptime"]' required><button type="submit" class="primary">Add task</button></form></section>
<section><h2>Custom tasks</h2><div id="tasks"></div></section>
<section><h2>Recent jobs</h2><div id="jobs"></div></section>
<section id="job-detail" class="wide" hidden><div class="section-heading"><h2>Job details</h2><a href="#">Close</a></div><div id="job-metadata"></div><h3>Redacted job log</h3><pre id="log" class="mono"></pre></section></div></main></body></html>"""

UI_STYLESHEET = """
:root{color-scheme:dark;--bg:#111827;--card:#1f2937;--line:#374151;--text:#f3f4f6;--muted:#9ca3af;--accent:#03a9f4;--danger:#ef4444}
*{box-sizing:border-box}body{margin:0;font:15px system-ui;background:var(--bg);color:var(--text)}main{max-width:1100px;margin:auto;padding:24px}
h1{margin:0 0 6px}h2{font-size:18px}.sub{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-top:20px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}input,button{font:inherit;border-radius:7px;border:1px solid var(--line);padding:9px;background:#111827;color:var(--text)}
input{width:100%;margin:4px 0}button{cursor:pointer}button:disabled{cursor:wait;opacity:.6}button.primary{background:var(--accent);color:#001018}.danger{color:#fecaca;border-color:var(--danger)}
.row{display:flex;gap:8px;align-items:center;justify-content:space-between;border-top:1px solid var(--line);padding:10px 0}.actions{display:flex;gap:6px;flex-wrap:wrap}.mono{font-family:ui-monospace;overflow-wrap:anywhere;white-space:pre-wrap}.error{color:#fca5a5}.success{color:#86efac}
.connection-state{display:flex;gap:8px;align-items:baseline;margin:18px 0 10px}.connection-state strong{color:var(--muted)}.connection-state.connected strong{color:#86efac}.connection-state.connecting strong{color:#fcd34d}.connect-placeholder{margin-top:20px;border-style:dashed}[hidden]{display:none!important}
.wide{grid-column:1/-1}.section-heading{display:flex;align-items:center;justify-content:space-between}.section-heading h2{margin:0}.section-heading a{color:var(--accent)}h3{font-size:15px;margin-top:20px}.state-failed{color:#fca5a5}.state-success{color:#86efac}
"""

# Raw prevents Python from turning JavaScript escape sequences into invalid source.
UI_JAVASCRIPT = r"""
"use strict";
const apiBase = new URL(document.querySelector('meta[name="api-base"]').content, document.baseURI);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const ingress = document.querySelector('meta[name="ingress-mode"]').content === "true";
const ACTIVE_JOB_POLL_INTERVAL_MS = 1500;
const JOB_POLL_BACKOFF_MS = [1500, 3000, 5000];
const ACTIVE_JOB_STATES = new Set(["queued", "running"]);
const MUTATING_JOB_ACTIONS = new Set(["update", "reboot", "custom_task"]);
let state = {info:null, hosts:[], custom_tasks:[], jobs:[], public_key:""};
let connected = false;
let jobPollTimer = null;
let jobPollInFlight = false;
let jobPollFailureCount = 0;
let selectedJobId = null;
let selectedJobLog = null;

function element(id){return document.getElementById(id)}
function escapeHtml(value){const node=document.createElement("div");node.textContent=value??"";return node.innerHTML}
function message(value,kind=""){const target=element("message");target.textContent=value;target.className=kind}
function setBusy(button,busy){if(button)button.disabled=busy}
function jobError(errorCode){const labels={apt_lock_unavailable:"APT is locked by another process",check_updates_apt_cache_refresh_failed:"Check updates failed during APT cache refresh",check_updates_facts_failed:"Check updates failed while collecting system facts",check_updates_package_list_failed:"Check updates failed while listing packages",check_updates_reboot_status_failed:"Check updates failed while reading reboot status",invalid_ansible_output:"Ansible returned an invalid structured result",python_interpreter_unavailable:"Python 3 is not available on the host",reboot_failed:"Reboot failed",sudo_unavailable:"Non-interactive sudo is not available",test_connection_failed:"SSH connection test failed",test_connection_facts_failed:"Connection test failed while collecting system facts",update_packages_failed:"Package update failed"};return labels[errorCode]||errorCode.replaceAll("_"," ")}
function hasActiveJobs(){return state.jobs.some(job=>ACTIVE_JOB_STATES.has(job.state))}
function stopJobPolling(){if(jobPollTimer!==null)window.clearTimeout(jobPollTimer);jobPollTimer=null;jobPollFailureCount=0}
function scheduleJobPolling(delay=ACTIVE_JOB_POLL_INTERVAL_MS){if(!connected||!hasActiveJobs()||jobPollTimer!==null||jobPollInFlight)return;jobPollTimer=window.setTimeout(pollJobs,delay)}
function syncJobPolling(){if(connected&&hasActiveJobs())scheduleJobPolling();else stopJobPolling()}
function clearProtectedData(){stopJobPolling();state={info:null,hosts:[],custom_tasks:[],jobs:[],public_key:""};selectedJobId=null;selectedJobLog=null;for(const id of ["dashboard","key","hosts","tasks","jobs","job-metadata","log"])element(id).replaceChildren();element("job-detail").hidden=true;element("protected-content").hidden=true;element("connect-placeholder").hidden=false}
function setDisconnected(hint="Enter your API token to load backend data."){connected=false;element("token").value="";element("token").disabled=ingress;clearProtectedData();element("connection-state").className="connection-state";element("connection-label").textContent="Not connected";element("connection-hint").textContent=hint;element("connect").textContent=ingress?"Retry":"Connect";element("disconnect").hidden=true;element("token-field").hidden=ingress}
function setConnecting(){element("connection-state").className="connection-state connecting";element("connection-label").textContent="Connecting…";element("connection-hint").textContent="Loading backend data."}
function setConnected(){connected=true;element("token").disabled=true;element("connection-state").className="connection-state connected";element("connection-label").textContent="Connected";element("connection-hint").textContent="Backend data is loaded.";element("protected-content").hidden=false;element("connect-placeholder").hidden=true;element("connect").textContent="Refresh";element("token-field").hidden=true;element("disconnect").hidden=ingress;syncJobPolling()}

async function request(path,{method="GET",body}={}){
  const headers={Accept:"application/json"};
  if(method!=="GET")headers["X-CSRF-Token"]=csrf;
  if(body!==undefined)headers["Content-Type"]="application/json";
  let response;
  try{response=await fetch(new URL(path,apiBase),{method,headers,credentials:"same-origin",cache:"no-store",body:body===undefined?undefined:JSON.stringify(body)})}
  catch(error){throw new Error(`Connection failed: ${error instanceof Error?error.message:"network error"}`)}
  if(!response.ok){let detail=`Request failed (${response.status})`;try{const payload=await response.json();if(typeof payload.detail==="string")detail=payload.detail}catch{}if(response.status===401||(ingress&&response.status===403))setDisconnected(ingress?"Your Ingress session is not authorized. Reopen or retry the panel.":"Session expired. Please connect again.");throw new Error(detail)}
  return response.status===204?null:response.json();
}

async function refreshDashboard(){
  const [info,hosts,key,tasks,jobs]=await Promise.all([request("info"),request("hosts"),request("public-key"),request("custom-tasks"),request("jobs")]);
  state={info,hosts,custom_tasks:tasks,jobs,public_key:key.public_key};render();
  await loadJobRoute();
}

async function refreshLiveState(){const [hosts,jobs]=await Promise.all([request("hosts"),request("jobs")]);state={...state,hosts,jobs};render();const selected=state.jobs.find(job=>job.id===selectedJobId);if(selected?.log_available&&selectedJobLog===null)await loadJobRoute(true)}

async function pollJobs(){jobPollTimer=null;if(!connected||!hasActiveJobs())return;jobPollInFlight=true;try{const recovered=jobPollFailureCount>0;await refreshLiveState();jobPollFailureCount=0;if(recovered)message("Live job updates recovered.","success")}catch(error){if(connected){if(jobPollFailureCount===0)message("Live job refresh failed; retrying automatically.","error");jobPollFailureCount+=1}}finally{jobPollInFlight=false;if(connected&&hasActiveJobs()){const index=Math.min(jobPollFailureCount,JOB_POLL_BACKOFF_MS.length-1);scheduleJobPolling(JOB_POLL_BACKOFF_MS[index])}}}

async function run(button,operation,success){setBusy(button,true);message("Working…");try{await operation();message(success,"success");return true}catch(error){message(error instanceof Error?error.message:"Request failed","error");return false}finally{setBusy(button,false)}}

async function login(apiToken){const response=await fetch(new URL("auth/login",apiBase),{method:"POST",headers:{Accept:"application/json","Content-Type":"application/json","X-CSRF-Token":csrf},credentials:"same-origin",cache:"no-store",body:JSON.stringify({api_token:apiToken})});if(!response.ok){let detail="Authentication failed";try{const payload=await response.json();if(typeof payload.detail==="string")detail=payload.detail}catch{}throw new Error(detail)}}
async function connect(event){event.preventDefault();const button=element("connect"),wasConnected=connected;let enteredToken="";if(!ingress&&!connected){enteredToken=element("token").value.trim();if(enteredToken.length<32){message("The API token must contain at least 32 characters.","error");return}element("token").value=""}setConnecting();const success=await run(button,async()=>{if(!ingress&&!wasConnected)await login(enteredToken);enteredToken="";await refreshDashboard()},"Connected");enteredToken="";if(success)setConnected();else if(element("connection-label").textContent==="Connecting…"){if(wasConnected)setConnected();else setDisconnected("Connection failed. Check the backend and enter your API token to retry.")}}
async function disconnect(){const button=element("disconnect");stopJobPolling();const success=await run(button,async()=>{await request("auth/logout",{method:"POST"})},"Disconnected");setDisconnected();message(success?"Disconnected":"Disconnect failed; local data was cleared.",success?"success":"error")}

async function initialize(){setDisconnected();if(ingress){setConnecting();const success=await run(element("connect"),refreshDashboard,"Connected");if(success)setConnected();return}let response;try{response=await fetch(new URL("auth/session",apiBase),{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"})}catch{message("Could not check the existing UI session.","error");return}if(response.status===401)return;if(!response.ok){message(`Session check failed (${response.status}).`,"error");return}setConnecting();const success=await run(element("connect"),refreshDashboard,"Connected");if(success)setConnected();else setDisconnected("Session recovery failed. Please connect again.")}

function render(){
  const running=state.jobs.filter(job=>job.state==="running").length;
  const queued=state.jobs.filter(job=>job.state==="queued").length;
  const latest=state.jobs[0];
  const latestFailed=state.jobs.find(job=>job.state==="failed");
  element("dashboard").innerHTML=`<div class="row"><span>Backend</span><span class="state-success">Online</span></div><div class="row"><span>Hosts</span><span>${state.hosts.length}</span></div><div class="row"><span>Running jobs</span><span>${running}</span></div><div class="row"><span>Queued jobs</span><span>${queued}</span></div><div class="row"><span>Last job</span><span>${latest?`${escapeHtml(latest.state)} · ${escapeHtml(latest.type||latest.action)}`:"none"}</span></div><div class="row"><span>Last failed job</span><span>${latestFailed?`${escapeHtml(latestFailed.type||latestFailed.action)} · ${escapeHtml(latestFailed.error_code||"failed")}`:"none"}</span></div>`;
  element("key").textContent=state.public_key;
  element("hosts").innerHTML=state.hosts.map(host=>{const jobs=state.jobs.filter(job=>job.host_id===host.id&&ACTIVE_JOB_STATES.has(job.state)),locked=jobs.some(job=>MUTATING_JOB_ACTIONS.has(job.action)),system=[host.distribution,host.distribution_version].filter(Boolean).join(" ")||host.status||"not checked";const action=(name,label,danger=false)=>{const running=jobs.some(job=>job.action===name),disabled=running||(MUTATING_JOB_ACTIONS.has(name)&&locked);return `<button type="button" ${danger?'class="danger" ':""}data-host="${host.id}" data-action="${name}" ${disabled?"disabled":""}>${running?"Running…":label}</button>`};return `<div class="row"><span>${escapeHtml(host.name)}<br><small>${escapeHtml(system)} · ${host.updates} updates · ${host.security_updates} security · reboot ${host.reboot_required?"required":"not required"}</small></span><span class="actions">${action("test_connection","Test connection")}${action("check_updates","Check updates")}${action("update","Update")}${action("reboot","Reboot",true)}<button type="button" data-edit-host="${host.id}">Edit</button><button type="button" class="danger" data-delete-host="${host.id}">Delete</button></span></div>`}).join("");
  element("tasks").innerHTML=state.custom_tasks.map(task=>`<div class="row"><span>${escapeHtml(task.name)}<br><small>${escapeHtml(task.description)}</small></span><span class="actions">${state.hosts.map(host=>{const jobs=state.jobs.filter(job=>job.host_id===host.id&&ACTIVE_JOB_STATES.has(job.state)),running=jobs.some(job=>job.action==="custom_task"&&job.custom_task_id===task.id),locked=jobs.some(job=>MUTATING_JOB_ACTIONS.has(job.action));return `<button type="button" data-host="${host.id}" data-task="${task.id}" ${locked?"disabled":""}>${running?"Running…":escapeHtml(host.name)}</button>`}).join("")}<button type="button" data-edit-task="${task.id}">Edit</button><button type="button" class="danger" data-delete-task="${task.id}">Delete</button></span></div>`).join("");
  element("jobs").innerHTML=state.jobs.map(job=>`<div class="row"><span>${escapeHtml(job.type||job.action)}<br><small>${escapeHtml(job.host_name||"No host")} · ${escapeHtml(job.created_at)}</small></span><span class="actions"><span class="state-${escapeHtml(job.state)}">${escapeHtml(job.state==="failed"&&job.error_code?jobError(job.error_code):job.state)}</span><button type="button" data-job-log="${job.id}">Open</button></span></div>`).join("");
  renderSelectedJob();
  syncJobPolling();
}

function routeJobId(){const match=location.hash.match(/^#\/jobs\/([0-9a-f-]{36})$/i);return match?match[1].toLowerCase():null}
function formatDuration(value){return typeof value==="number"?`${value.toFixed(1)} s`:"—"}
function renderSelectedJob(){const detail=element("job-detail");if(!selectedJobId){detail.hidden=true;return}const job=state.jobs.find(value=>value.id===selectedJobId);if(!job){return}detail.hidden=false;element("job-metadata").innerHTML=`<div class="row"><span>Job ID</span><span class="mono">${escapeHtml(job.job_id||job.id)}</span></div><div class="row"><span>Host</span><span>${escapeHtml(job.host_name||"No host")}</span></div><div class="row"><span>Type</span><span>${escapeHtml(job.type||job.action)}</span></div><div class="row"><span>State</span><span class="state-${escapeHtml(job.state)}">${escapeHtml(job.state)}</span></div><div class="row"><span>Created</span><span>${escapeHtml(job.created_at)}</span></div><div class="row"><span>Started</span><span>${escapeHtml(job.started_at||"—")}</span></div><div class="row"><span>Finished</span><span>${escapeHtml(job.finished_at||"—")}</span></div><div class="row"><span>Duration</span><span>${formatDuration(job.duration)}</span></div><div class="row"><span>Exit code</span><span>${job.exit_code??"—"}</span></div><div class="row"><span>Error code</span><span>${escapeHtml(job.error_code||"—")}</span></div><div class="row"><span>Short error</span><span>${escapeHtml(job.short_error||"—")}</span></div>`;element("log").textContent=selectedJobLog===null?(job.log_available?"Loading…":"Log is available after the job completes."):selectedJobLog}
async function loadJobRoute(force=false){const jobId=routeJobId();if(!jobId){selectedJobId=null;selectedJobLog=null;renderSelectedJob();return}if(!force&&selectedJobId===jobId&&selectedJobLog!==null)return;selectedJobId=jobId;selectedJobLog=null;let job=state.jobs.find(value=>value.id===jobId);if(!job){job=await request(`jobs/${jobId}`);state.jobs=[job,...state.jobs]}renderSelectedJob();if(job.log_available){const log=await request(`jobs/${jobId}/log`);selectedJobLog=log.output+(log.truncated?"\n[truncated]":"");renderSelectedJob()}}

async function mutate(button,path,method="POST",body,success="Done"){return run(button,async()=>{const result=await request(path,{method,body});if(result?.id&&result?.state&&result?.action){state.jobs=[result,...state.jobs.filter(job=>job.id!==result.id)];render()}await refreshDashboard()},success)}
function hostActionPath(hostId,action){return `hosts/${hostId}/actions/${action}`}
function customTaskPath(hostId,taskId){return `hosts/${hostId}/tasks/${taskId}`}

async function addHost(event){event.preventDefault();const button=event.submitter;const name=element("host-name").value.trim(),address=element("host-address").value.trim(),username=element("host-user").value.trim(),port=Number(element("host-port").value);if(!name||!address||!username||!Number.isInteger(port)||port<1||port>65535){message("Complete all host fields with a valid SSH port.","error");return}if(await mutate(button,"hosts","POST",{name,address,username,port},"Host added")){event.target.reset();element("host-port").value="22"}}
async function addTask(event){event.preventDefault();const button=event.submitter;const name=element("task-name").value.trim();let argv;try{argv=JSON.parse(element("task-argv").value)}catch{message("Command argv must be valid JSON.","error");return}if(!name||!Array.isArray(argv)||argv.length===0||argv.some(value=>typeof value!=="string"||!value)){message("Enter a task name and a non-empty string array.","error");return}if(await mutate(button,"custom-tasks","POST",{name,mode:"command",argv},"Task added"))event.target.reset()}

async function copyKey(button){if(!state.public_key){message("Connect before copying the public key.","error");return}await run(button,async()=>{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(state.public_key);return}const area=document.createElement("textarea");area.value=state.public_key;area.setAttribute("readonly","");area.style.position="fixed";area.style.opacity="0";document.body.appendChild(area);area.select();const copied=document.execCommand("copy");area.remove();if(!copied)throw new Error("Clipboard access is unavailable. Select and copy the displayed key manually.")},"Copied")}

async function hostClick(event){const button=event.target.closest("button");if(!button)return;const hostId=button.dataset.host;if(button.dataset.action&&hostId){const action=button.dataset.action;if(["update","reboot"].includes(action)&&!confirm(`Run ${action} on this host?`))return;await mutate(button,hostActionPath(hostId,action),"POST",undefined,`${action.replace("_"," ")} queued`);return}if(button.dataset.deleteHost){if(confirm("Delete this host?"))await mutate(button,`hosts/${button.dataset.deleteHost}`,"DELETE",undefined,"Host deleted");return}if(button.dataset.editHost){const host=state.hosts.find(value=>value.id===button.dataset.editHost);const name=prompt("Display name",host.name),address=prompt("Address",host.address),username=prompt("SSH user",host.username);if(name&&address&&username)await mutate(button,`hosts/${host.id}`,"PATCH",{name,address,username},"Host updated")}}
async function taskClick(event){const button=event.target.closest("button");if(!button)return;if(button.dataset.task&&button.dataset.host){if(confirm("Run this custom task on the selected host?"))await mutate(button,customTaskPath(button.dataset.host,button.dataset.task),"POST",undefined,"Task queued");return}if(button.dataset.deleteTask){if(confirm("Delete this task?"))await mutate(button,`custom-tasks/${button.dataset.deleteTask}`,"DELETE",undefined,"Task deleted");return}if(button.dataset.editTask){const task=state.custom_tasks.find(value=>value.id===button.dataset.editTask);const name=prompt("Task name",task.name),raw=prompt("Command argv (JSON)",JSON.stringify(task.argv));if(name&&raw)try{await mutate(button,`custom-tasks/${task.id}`,"PATCH",{name,argv:JSON.parse(raw)},"Task updated")}catch(error){message(error instanceof Error?error.message:"Task update failed","error")}}}
async function jobClick(event){const button=event.target.closest("button[data-job-log]");if(!button)return;const target=`#/jobs/${button.dataset.jobLog}`;if(location.hash===target)await run(button,()=>loadJobRoute(true),"Job loaded");else location.hash=target}

document.addEventListener("DOMContentLoaded",()=>{element("connect-form").addEventListener("submit",connect);element("disconnect").addEventListener("click",disconnect);element("host-form").addEventListener("submit",addHost);element("task-form").addEventListener("submit",addTask);element("copy-key").addEventListener("click",event=>copyKey(event.currentTarget));element("hosts").addEventListener("click",hostClick);element("tasks").addEventListener("click",taskClick);element("jobs").addEventListener("click",jobClick);window.addEventListener("hashchange",()=>{if(connected)run(null,loadJobRoute,"Job loaded")});initialize()});
window.addEventListener("pagehide",stopJobPolling);
"""
