
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
let visibleCheckTimer = null;
let visibleCheckInFlight = false;
const VISIBLE_CHECK_INTERVAL_MS = 300000;
function stopVisibleChecks(){if(visibleCheckTimer!==null)clearTimeout(visibleCheckTimer);visibleCheckTimer=null}
function visibleHostView(){return document.visibilityState==="visible"&&["dashboard","hosts"].includes(view().name)}
function syncVisibleChecks(){
  if(!connected||!visibleHostView()||!state.preferences?.enabled){stopVisibleChecks();return}
  if(visibleCheckTimer===null&&!visibleCheckInFlight)visibleCheckTimer=setTimeout(checkVisibleHosts,0);
}
async function checkVisibleHosts(){
  visibleCheckTimer=null;if(!connected||!visibleHostView()||!state.preferences?.enabled||visibleCheckInFlight)return;
  visibleCheckInFlight=true;
  try{state.preferences=await request("preferences/host-checks");element("auto-host-checks").checked=state.preferences.enabled;if(connected&&visibleHostView()&&state.preferences.enabled){const jobs=await request("actions/check-visible",{method:"POST"});if(connected&&jobs.length){state.jobs=[...jobs,...state.jobs.filter(job=>!jobs.some(queued=>queued.id===job.id))];await refreshLiveState()}}}
  catch(error){if(connected)message("Automatic host check failed. Retry with the check icon or Refresh.","error")}
  finally{visibleCheckInFlight=false;if(connected&&visibleHostView()&&state.preferences?.enabled)visibleCheckTimer=setTimeout(checkVisibleHosts,VISIBLE_CHECK_INTERVAL_MS)}
}


function element(id){return document.getElementById(id)}
function escapeHtml(value){const node=document.createElement("div");node.textContent=value??"";return node.innerHTML.replaceAll('"',"&quot;").replaceAll("'","&#39;")}
function message(value,kind=""){const target=element("message");target.textContent=value;target.className=kind;target.hidden=!value}
function setBusy(button,busy){if(button)button.disabled=busy}
function backendUnavailable(){state.unavailable=true;element("connection-hint").textContent="Backend unavailable. Displayed data may be out of date.";renderBackendStatus()}
function jobError(errorCode){const labels={apt_lock_unavailable:"APT is locked by another process",check_updates_apt_cache_refresh_failed:"Check updates failed during APT cache refresh",check_updates_facts_failed:"Check updates failed while collecting system facts",check_updates_package_list_failed:"Check updates failed while listing packages",check_updates_reboot_status_failed:"Check updates failed while reading reboot status",invalid_ansible_output:"Ansible returned an invalid structured result",python_interpreter_unavailable:"Python 3 is not available on the host",reboot_failed:"Reboot failed",sudo_unavailable:"Non-interactive sudo is not available",test_connection_failed:"SSH connection test failed",test_connection_facts_failed:"Connection test failed while collecting system facts",update_packages_failed:"Package update failed"};return labels[errorCode]||errorCode.replaceAll("_"," ")}
function hasActiveJobs(){return (state.dashboard?.running_jobs||state.dashboard?.queued_jobs||0)>0||state.jobs.some(job=>ACTIVE_JOB_STATES.has(job.state))}
function stopJobPolling(){if(jobPollTimer!==null)window.clearTimeout(jobPollTimer);jobPollTimer=null;jobPollFailureCount=0}
function scheduleJobPolling(delay=ACTIVE_JOB_POLL_INTERVAL_MS){if(!connected||!hasActiveJobs()||jobPollTimer!==null||jobPollInFlight)return;jobPollTimer=window.setTimeout(pollJobs,delay)}
function syncJobPolling(){if(connected&&hasActiveJobs())scheduleJobPolling();else stopJobPolling()}
function clearProtectedData(){stopJobPolling();stopVisibleChecks();document.querySelectorAll("dialog[open]").forEach(d=>d.close());state={info:null,hosts:[],custom_tasks:[],jobs:[],public_key:""};selectedJobId=null;selectedJobLog=null;for(const id of ["backend-status","job-highlights","dashboard","key","hosts","tasks","jobs","job-metadata","log","notices","history","activity","host-info","host-tasks","host-jobs"])element(id).replaceChildren();element("job-detail").hidden=true;element("protected-content").hidden=true;element("connect-placeholder").hidden=false}
function setDisconnected(hint="Enter your API token to load backend data."){connected=false;element("token").value="";element("token").disabled=ingress;clearProtectedData();element("connection-state").className="connection-state";element("connection-label").textContent="Not connected";element("connection-hint").textContent=hint;element("connect").textContent=ingress?"Retry":"Connect";element("disconnect").hidden=true;element("token-field").hidden=ingress}
function setConnecting(){element("connection-state").className="connection-state connecting";element("connection-label").textContent="Connecting…";element("connection-hint").textContent="Loading backend data."}
function setConnected(){connected=true;element("token").disabled=true;element("connection-state").className="connection-state connected";element("connection-label").textContent="Connected";element("connection-hint").textContent="Backend data is loaded.";element("protected-content").hidden=false;element("connect-placeholder").hidden=true;element("connect").textContent="Refresh";element("token-field").hidden=true;element("disconnect").hidden=ingress;syncJobPolling();syncVisibleChecks()}

async function request(path,{method="GET",body}={}){
  const headers={Accept:"application/json"};
  if(method!=="GET")headers["X-CSRF-Token"]=csrf;
  if(body!==undefined)headers["Content-Type"]="application/json";
  let response;
  try{response=await fetch(new URL(path,apiBase),{method,headers,credentials:"same-origin",cache:"no-store",body:body===undefined?undefined:JSON.stringify(body)})}
  catch(error){backendUnavailable();throw new Error(`Connection failed: ${error instanceof Error?error.message:"network error"}`)}
  if(!response.ok){if(response.status>=500)backendUnavailable();let detail=`Request failed (${response.status})`;try{const payload=await response.json();if(typeof payload.detail==="string")detail=payload.detail}catch{}if(response.status===401||(ingress&&response.status===403))setDisconnected(ingress?"Your Ingress session is not authorized. Reopen or retry the panel.":"Session expired. Please connect again.");throw new Error(detail)}
  return response.status===204?null:response.json();
}

async function refreshDashboard(){
  const [info,hosts,key,tasks,jobs,dashboard,preferences]=await Promise.all([request("info"),request("hosts"),request("public-key"),request("custom-tasks"),request("jobs"),request("dashboard"),request("preferences/host-checks")]);
  state={info,hosts,custom_tasks:tasks,jobs,public_key:key.public_key,dashboard,preferences};
  await loadView();render();await loadJobRoute();
}

async function refreshLiveState(){const [hosts,jobs,dashboard]=await Promise.all([request("hosts"),request("jobs"),request("dashboard")]);state={...state,hosts,jobs,dashboard,unavailable:false};await loadView();render();const selected=state.jobs.find(job=>job.id===selectedJobId);if(selected?.log_available&&selectedJobLog===null)await loadJobRoute(true)}

async function pollJobs(){jobPollTimer=null;if(!connected||!hasActiveJobs())return;jobPollInFlight=true;try{const recovered=jobPollFailureCount>0;await refreshLiveState();jobPollFailureCount=0;if(recovered)message("Live job updates recovered.","success")}catch(error){if(connected){if(jobPollFailureCount===0)message("Live job refresh failed; retrying automatically.","error");jobPollFailureCount+=1}}finally{jobPollInFlight=false;if(connected&&hasActiveJobs()){const index=Math.min(jobPollFailureCount,JOB_POLL_BACKOFF_MS.length-1);scheduleJobPolling(JOB_POLL_BACKOFF_MS[index])}}}

async function run(button,operation,success=""){setBusy(button,true);message(success?"Working…":"");try{await operation();message(success,"success");return true}catch(error){message(error instanceof Error?error.message:"Request failed","error");return false}finally{setBusy(button,false)}}

async function login(apiToken){const response=await fetch(new URL("auth/login",apiBase),{method:"POST",headers:{Accept:"application/json","Content-Type":"application/json","X-CSRF-Token":csrf},credentials:"same-origin",cache:"no-store",body:JSON.stringify({api_token:apiToken})});if(!response.ok){let detail="Authentication failed";try{const payload=await response.json();if(typeof payload.detail==="string")detail=payload.detail}catch{}throw new Error(detail)}}
async function connect(event){event.preventDefault();const button=element("connect"),wasConnected=connected;let enteredToken="";if(!ingress&&!connected){enteredToken=element("token").value.trim();if(enteredToken.length<32){message("The API token must contain at least 32 characters.","error");return}element("token").value=""}setConnecting();const success=await run(button,async()=>{if(!ingress&&!wasConnected)await login(enteredToken);enteredToken="";await refreshDashboard()});enteredToken="";if(success)setConnected();else if(element("connection-label").textContent==="Connecting…"){if(wasConnected)setConnected();else setDisconnected("Connection failed. Check the backend and enter your API token to retry.")}}
async function disconnect(){const button=element("disconnect");stopJobPolling();const success=await run(button,async()=>{await request("auth/logout",{method:"POST"})},"Disconnected");setDisconnected();message(success?"Disconnected":"Disconnect failed; local data was cleared.",success?"success":"error")}

async function initialize(){setDisconnected();if(ingress){setConnecting();const success=await run(element("connect"),refreshDashboard);if(success)setConnected();return}let response;try{response=await fetch(new URL("auth/session",apiBase),{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"})}catch{message("Could not check the existing UI session.","error");return}if(response.status===401)return;if(!response.ok){message(`Session check failed (${response.status}).`,"error");return}setConnecting();const success=await run(element("connect"),refreshDashboard);if(success)setConnected();else setDisconnected("Session recovery failed. Please connect again.")}

let currentHostTasks = [];
let currentHostJobs = [];
let currentJobPage = {items:[], total:0, offset:0, limit:25};
let editingHost = null;
let editingTask = null;
let taskTargetHost = null;
function view(){
  const raw=location.hash.slice(1)||"/dashboard";
  const [path,query]=raw.split("?");
  const parts=path.split("/").filter(Boolean);
  return {name:parts[0]||"dashboard",id:parts[1]||null,params:new URLSearchParams(query||"")};
}
function actionName(value){return ({check_updates:"Check for updates",test_connection:"Connection test",update:"System update",reboot:"Restart host",custom_task:"Custom task"})[value]||String(value||"Job").replaceAll("_"," ")}
function timeLabel(value){
  if(!value)return "Not yet";
  const date=new Date(value);if(Number.isNaN(date.getTime()))return "Unknown";
  const seconds=Math.round((date-Date.now())/1000),absolute=Math.abs(seconds);
  const units=absolute<60?[seconds,"second"]:absolute<3600?[Math.round(seconds/60),"minute"]:absolute<86400?[Math.round(seconds/3600),"hour"]:absolute<604800?[Math.round(seconds/86400),"day"]:null;
  const text=units?new Intl.RelativeTimeFormat(navigator.language,{numeric:"auto"}).format(...units):new Intl.DateTimeFormat(navigator.language,{dateStyle:"medium",timeStyle:"short"}).format(date);
  return `<time datetime="${escapeHtml(value)}" title="${escapeHtml(value)}">${escapeHtml(text)}</time>`;
}
function websiteLinks(host){return (host.websites||[]).map(site=>{const url=new URL(site.url);return `<a class="website-icon" href="${escapeHtml(url.href)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer" title="${escapeHtml(site.name)}" aria-label="Open ${escapeHtml(site.name)}"><span aria-hidden="true">${escapeHtml(site.name.slice(0,1).toUpperCase())}</span><img src="${escapeHtml(url.origin)}/favicon.ico" alt="" loading="lazy" referrerpolicy="no-referrer"></a>`}).join("")}
function renderBackendStatus(){const online=Boolean(state.info&&!state.unavailable);element("backend-status").className=`backend-status ${online?"online":"offline"}`;element("backend-status").textContent=online?"Backend online":"Backend unavailable"}
function highlightJob(job,label){
  if(!job)return `<article class="job-highlight"><small>${label}</small><p class="empty">No job yet</p></article>`;
  const preview=job.short_error||(job.error_code?jobError(job.error_code):job.state==="success"?"Completed successfully":job.state==="running"?"Currently running":job.state==="queued"?"Waiting for a worker":"Job details available");
  return `<article class="job-highlight"><small>${label}</small><a class="job-title" href="#/jobs/${job.id}" title="${escapeHtml(job.action)}">${escapeHtml(actionName(job.action))}</a><p>${escapeHtml(job.host_name||"All hosts")} · ${timeLabel(job.finished_at||job.created_at)}</p><p class="job-preview state-${job.state}" title="${escapeHtml(job.error_code||job.state)}">${escapeHtml(preview)}</p><div class="actions"><a href="#/jobs/${job.id}">Open job →</a>${job.log_available?`<button class="text-button" data-preview-log="${job.id}">Log preview</button>`:""}</div></article>`;
}
function renderHistory(history){
  const width=720,height=220,left=40,top=18,bottom=38,plotHeight=height-top-bottom;
  const max=Math.ceil(Math.max(4,...history.flatMap(day=>Object.values(day.counts)))/4)*4;
  const x=index=>left+index*(width-left-18)/Math.max(1,history.length-1),y=count=>top+plotHeight-count/max*plotHeight;
  const grid=Array.from({length:5},(_,i)=>{const value=max*i/4;return `<line class="graph-grid" x1="${left}" x2="${width-15}" y1="${y(value)}" y2="${y(value)}"/><text x="${left-8}" y="${y(value)+4}" text-anchor="end">${Number.isInteger(value)?value:value.toFixed(1)}</text>`}).join("");
  const series=["success","failed","cancelled","running","queued"].map(status=>{const points=history.map((day,i)=>`${x(i)},${y(day.counts[status]||0)}`).join(" ");return `<g class="graph-series ${status}"><polyline points="${points}"/>${history.map((day,i)=>`<circle tabindex="0" cx="${x(i)}" cy="${y(day.counts[status]||0)}" r="4"><title>${escapeHtml(day.day)} (UTC) · ${status}: ${day.counts[status]||0}</title></circle>`).join("")}</g>`}).join("");
  const labels=history.map((day,i)=>`<text x="${x(i)}" y="${height-12}" text-anchor="middle"><title>${escapeHtml(day.day)} (UTC)</title>${escapeHtml(new Intl.DateTimeFormat(navigator.language,{month:"short",day:"numeric",timeZone:"UTC"}).format(new Date(day.day+"T12:00:00Z")))}</text>`).join("");
  element("history").innerHTML=`<svg class="history-graph" viewBox="0 0 ${width} ${height}" role="img" aria-label="Job counts by day; exact UTC dates and counts are available on each point">${grid}${series}${labels}</svg>`;
}
function hostRow(host,detail=false){
  const jobs=state.jobs.filter(job=>job.host_id===host.id&&ACTIVE_JOB_STATES.has(job.state));
  const locked=jobs.some(job=>MUTATING_JOB_ACTIONS.has(job.action));
  const action=(name,label,danger=false)=>`<button type="button" ${danger?'class="danger" ':""}data-host="${host.id}" data-action="${name}" aria-label="${name==="check_updates"?"Check for updates":label}" title="${name==="check_updates"?"Check for updates":label}" ${jobs.some(job=>job.action===name)||(MUTATING_JOB_ACTIONS.has(name)&&locked)?"disabled":""}>${name==="check_updates"?`<span class="refresh-glyph ${jobs.some(job=>job.action===name)?"spinning":""}" aria-hidden="true">↻</span>`:jobs.some(job=>job.action===name)?"Running…":label}</button>`;
  const system=[host.distribution,host.distribution_version].filter(Boolean).join(" ")||host.status||"Not checked";
  return `<div class="row"><span>${detail?"":`<a href="#/hosts/${host.id}">${escapeHtml(host.name)}</a>`}<span class="website-links">${websiteLinks(host)}</span><small>${escapeHtml(system)} · ${host.checked_at?`${host.updates} updates · ${host.security_updates} security · reboot ${host.reboot_required?"required":"not required"}`:"Update status unknown · reboot status unknown"}</small></span><span class="actions">${action("check_updates","↻")}${action("update","Update")}${action("reboot","Reboot",true)}${detail?"":`<a href="#/hosts/${host.id}">Details</a>`}</span></div>`;
}
function jobRow(job){return `<div class="row"><span><span title="${escapeHtml(job.type||job.action)}">${escapeHtml(actionName(job.type||job.action))}</span><small>${escapeHtml(job.host_name||"No host")} · ${timeLabel(job.finished_at||job.created_at)}</small></span><span class="actions"><span class="state-${escapeHtml(job.state)}" title="${escapeHtml(job.error_code||job.state)}">${escapeHtml(job.state==="failed"&&job.error_code?jobError(job.error_code):job.state)}</span><button type="button" data-job-log="${job.id}">Open</button></span></div>`}
function staleHost(host){return !host.checked_at||Date.now()-Date.parse(host.checked_at)>86400000}
function render(){
  const route=view(),page=route.name==="hosts"&&route.id?"host":route.name==="jobs"&&route.id?"job":route.name;
  document.querySelectorAll("[data-views]").forEach(section=>section.hidden=!section.dataset.views.split(" ").includes(page));
  document.querySelectorAll("nav a").forEach(link=>{if(link.hash===`#/${route.name}`)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current")});
  const summary=state.dashboard;
  const latest=summary?.last_job,failed=summary?.last_failed_job;
  renderBackendStatus();
  const checkedHosts=state.hosts.filter(host=>host.checked_at),unchecked=state.hosts.length-checkedHosts.length;
  const updates=checkedHosts.reduce((total,host)=>total+host.updates,0),securityCount=checkedHosts.reduce((total,host)=>total+host.security_updates,0);
  const updateStatus=checkedHosts.length?`${updates} ${unchecked?"known ":""}updates · ${securityCount} ${unchecked?"known ":""}security updates`:state.hosts.length?"Update status unknown":"No hosts yet";
  const metrics=[["Hosts",state.hosts.length,updateStatus+(unchecked?` · ${unchecked} unchecked ${unchecked===1?"host":"hosts"}`:"")],["Running jobs",summary?.running_jobs??0,"Being processed now"],["Queued jobs",summary?.queued_jobs??0,"Waiting for a worker"]];
  element("dashboard").innerHTML=metrics.map(([label,value,detail])=>`<div class="metric"><small>${label}</small><span class="value">${escapeHtml(value)}</span><span class="metric-detail">${escapeHtml(detail)}</span></div>`).join("");
  element("job-highlights").innerHTML=highlightJob(latest,"Last job")+highlightJob(failed,"Last failed job");
  element("auto-host-checks").checked=state.preferences?.enabled??true;
  element("key").textContent=state.public_key;
  const notices=[];
  const security=state.hosts.filter(h=>h.security_updates>0),reboot=state.hosts.filter(h=>h.reboot_required),stale=state.hosts.filter(staleHost);
  if(security.length)notices.push(`<a class="notice urgent" href="#/hosts?filter=security">${security.length} ${security.length===1?"host has":"hosts have"} security updates. Review affected hosts and run a regular system update.</a>`);
  if(reboot.length)notices.push(`<a class="notice" href="#/hosts?filter=reboot">${reboot.length} ${reboot.length===1?"host needs":"hosts need"} a restart. Review and confirm separately.</a>`);
  const attention=summary?.attention_job===undefined?failed:summary.attention_job;
  if(attention)notices.push(`<a class="notice urgent" href="#/jobs/${attention.id}">Last failed job: ${escapeHtml(attention.short_error||jobError(attention.error_code||attention.action))}. Review the job.</a>`);
  if(stale.length)notices.push(`<a class="notice" href="#/hosts?filter=stale">${stale.length} ${stale.length===1?"host needs":"hosts need"} a fresh status check. No check in the last 24 hours.</a>`);
  element("notices").innerHTML=notices.join("");
  element("notices-panel").hidden=page!=="dashboard"||notices.length===0;
  element("dashboard-layout").classList.toggle("has-notices",page==="dashboard"&&notices.length>0);
  const filter=route.params.get("filter");
  let hosts=state.hosts.filter(h=>filter==="security"?h.security_updates>0:filter==="reboot"?h.reboot_required:filter==="stale"?staleHost(h):true);
  if(page==="dashboard")hosts=hosts.slice(0,5);
  element("host-filter").textContent=page==="hosts"&&filter?`Filter: ${filter}. Use Hosts above to clear.`:"";
  element("hosts").innerHTML=hosts.map(host=>hostRow(host)).join("")||'<p class="empty">No hosts to show.</p>';
  element("all-hosts").hidden=page!=="dashboard";
  element("host-section").classList.toggle("wide",page==="hosts");
  element("jobs-section").classList.toggle("wide",page==="jobs");
  element("jobs-heading").textContent=page==="jobs"?"Jobs":"Recent jobs";
  element("job-filters").hidden=page!=="jobs";
  element("job-pagination").hidden=page!=="jobs";
  const jobs=page==="jobs"?currentJobPage.items:state.jobs.slice(0,5);
  element("jobs").innerHTML=jobs.map(jobRow).join("")||'<p class="empty">No jobs yet.</p>';
  element("jobs-count").textContent=`${currentJobPage.offset+Math.min(1,currentJobPage.total)}–${Math.min(currentJobPage.offset+currentJobPage.limit,currentJobPage.total)} of ${currentJobPage.total}`;
  element("jobs-previous").disabled=currentJobPage.offset===0;
  element("jobs-next").disabled=currentJobPage.offset+currentJobPage.limit>=currentJobPage.total;
  element("job-host").innerHTML='<option value="">All hosts</option>'+state.hosts.map(h=>`<option value="${h.id}">${escapeHtml(h.name)}</option>`).join("");
  element("job-host").value=route.params.get("host_id")||"";
  element("job-state").value=route.params.get("state")||"";
  const history=summary?.history||[];
  renderHistory(history);
  element("activity").innerHTML=(summary?.recent_completions||[]).map(jobRow).join("")||'<p class="empty">No completed jobs yet.</p>';
  element("tasks").innerHTML=state.custom_tasks.map(task=>`<div class="row"><span>${escapeHtml(task.name)}<small>${escapeHtml(task.description)} · ${task.enabled?"Enabled":"Globally disabled"} · ${task.host_ids.length} enabled host assignment(s)</small></span><span class="actions"><button data-edit-task="${task.id}">Edit</button><button data-toggle-task="${task.id}">${task.enabled?"Disable globally":"Enable globally"}</button><button class="danger" data-delete-task="${task.id}">Delete</button></span></div>`).join("")||'<p class="empty">No custom tasks yet. Use + to create one.</p>';
  if(page==="host"){element("hosts").replaceChildren();renderHostDetail(route.id)}
  else{element("host-info").replaceChildren();element("host-tasks").replaceChildren();element("host-jobs").replaceChildren()}
  renderSelectedJob();
  syncJobPolling();
  syncVisibleChecks();
}
function renderHostDetail(id){
  const host=state.hosts.find(h=>h.id===id);
  element("host-title").textContent=host?.name||"Host not found";
  if(!host){element("host-info").replaceChildren();element("host-tasks").replaceChildren();element("host-jobs").replaceChildren();return}
  element("host-info").innerHTML=hostRow(host,true)+`<p>${escapeHtml(host.address)}:${host.port} · ${escapeHtml(host.username)} · Kernel ${escapeHtml(host.kernel||"unknown")}</p><p>Last checked: ${timeLabel(host.checked_at)}</p><div class="actions"><button data-host="${id}" data-action="test_connection">Test connection</button><button data-edit-host="${id}">Edit host</button><button class="danger" data-delete-host="${id}">Delete host</button></div>`;
  element("host-tasks").innerHTML=state.custom_tasks.map(task=>{const result=currentHostTasks.find(c=>c.task_id===task.id)||{state:"unchecked",reasons:[],assigned:false,enabled:false};const suitable=result.state==="suitable",busy=state.jobs.some(j=>j.host_id===id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action));return `<div class="host-task"><strong>${escapeHtml(task.name)}</strong> <span class="state-${result.state}">${result.state}</span><p>${result.assigned?(result.enabled?"Assigned and enabled":"Assigned and disabled"):"Not assigned"} · ${task.enabled?"Globally enabled":"Globally disabled"}</p><p>${escapeHtml(result.reasons.join("; "))||(suitable?"Prerequisites verified. Ready when assigned and enabled.":"Check prerequisites before assigning or running this task.")}</p><small>${result.checked_at?`Checked ${timeLabel(result.checked_at)} · valid up to 24 hours`:"Not checked"}</small><div class="actions"><button data-check-task="${task.id}" data-host="${id}">Check compatibility</button><button data-assign-task="${task.id}" data-host="${id}" ${!suitable&&!result.enabled?"disabled":""}>${result.enabled?"Disable for host":result.assigned?"Enable for host":"Assign to host"}</button>${result.assigned?`<button data-unassign-task="${task.id}" data-host="${id}">Unassign</button>`:""}<button data-task="${task.id}" data-host="${id}" ${!suitable||!result.enabled||!task.enabled||busy?"disabled":""}>Run task</button><button data-edit-task="${task.id}">Edit</button></div></div>`}).join("")||'<p class="empty">No tasks yet. Create a task for this host above.</p>';
  element("host-jobs").innerHTML=currentHostJobs.map(jobRow).join("")||'<p class="empty">No jobs for this host.</p>';
  element("host-all-jobs").href=`#/jobs?host_id=${id}`;
}
async function loadView(){
  const route=view();
  if(route.name==="hosts"&&route.id){
    const [checks,jobs]=await Promise.all([request(`hosts/${encodeURIComponent(route.id)}/task-compatibility`),request(`jobs/page?host_id=${encodeURIComponent(route.id)}&limit=5`)]);
    currentHostTasks=checks;currentHostJobs=jobs.items;
  }else if(route.name==="jobs"&&!route.id){currentJobPage=await request(`jobs/page?${route.params}`)}
}

function routeJobId(){const match=location.hash.match(/^#\/jobs\/([0-9a-f-]{36})$/i);return match?match[1].toLowerCase():null}
function formatDuration(value){if(typeof value!=="number")return "Not available";return value<60?`${value.toFixed(1)} seconds`:`${Math.floor(value/60)} min ${Math.round(value%60)} sec`}
function renderSelectedJob(){const detail=element("job-detail");if(!selectedJobId){detail.hidden=true;return}const job=state.jobs.find(value=>value.id===selectedJobId);if(!job){return}detail.hidden=false;element("job-metadata").innerHTML=`<div class="row"><span>Job ID</span><span class="mono">${escapeHtml(job.job_id||job.id)}</span></div><div class="row"><span>Host</span><span>${escapeHtml(job.host_name||"No host")}</span></div><div class="row"><span>Type</span><span>${escapeHtml(actionName(job.type||job.action))}</span></div><div class="row"><span>State</span><span class="state-${escapeHtml(job.state)}">${escapeHtml(job.state)}</span></div><div class="row"><span>Created</span><span>${timeLabel(job.created_at)}</span></div><div class="row"><span>Started</span><span>${timeLabel(job.started_at)}</span></div><div class="row"><span>Finished</span><span>${timeLabel(job.finished_at)}</span></div><div class="row"><span>Duration</span><span>${formatDuration(job.duration)}</span></div><div class="row"><span>Exit code</span><span>${job.exit_code??"—"}</span></div><div class="row"><span>Error code</span><span>${escapeHtml(job.error_code||"—")}</span></div><div class="row"><span>Short error</span><span>${escapeHtml(job.short_error||"—")}</span></div>${job.state==="failed"?`<div class="row"><span>Review</span><span>${job.reviewed_at?`Reviewed ${timeLabel(job.reviewed_at)}`:`<button type="button" data-review-job="${job.id}">Mark as reviewed</button>`}</span></div>`:""}<details class="technical-details"><summary>Technical details</summary><pre>${escapeHtml(JSON.stringify(job,null,2))}</pre></details>`;element("log").textContent=selectedJobLog===null?(job.log_available?"Loading…":"Log is available after the job completes."):selectedJobLog}
async function loadJobRoute(force=false){const jobId=routeJobId();if(!jobId){selectedJobId=null;selectedJobLog=null;renderSelectedJob();return}if(!force&&selectedJobId===jobId&&selectedJobLog!==null)return;selectedJobId=jobId;selectedJobLog=null;let job=state.jobs.find(value=>value.id===jobId);if(!job){job=await request(`jobs/${jobId}`);state.jobs=[job,...state.jobs]}renderSelectedJob();if(job.log_available){const log=await request(`jobs/${jobId}/log`);selectedJobLog=log.output+(log.truncated?"\n[truncated]":"");renderSelectedJob()}}

async function mutate(button,path,method="POST",body,success="Done"){return run(button,async()=>{const result=await request(path,{method,body});if(result?.id&&result?.state&&result?.action){state.jobs=[result,...state.jobs.filter(job=>job.id!==result.id)];render()}await refreshDashboard()},success)}
function hostActionPath(hostId,action){return `hosts/${hostId}/actions/${action}`}
function customTaskPath(hostId,taskId){return `hosts/${hostId}/tasks/${taskId}`}

let setupCommand="";
let setupRequest=0;
function hostStep(step){
  for(const [index,id] of ["host-system-step","host-preparation","host-connection-step"].entries())element(id).hidden=index!==step;
  element("host-step-label").textContent=editingHost&&step===2?"Edit connection":"Step "+(step+1)+" of 3 · "+["Host system","User setup","SSH connection"][step];
  element(step===1?"setup-user-fields":"connection-user-fields").appendChild(element("ssh-settings"));
  element("host-connection-back").hidden=Boolean(editingHost);
  element("host-update-setup").hidden=!editingHost;
  element("host-form-error").textContent="";
  if(step===1)generateSetup();else{setupRequest++;setupCommand="";element("copy-setup").disabled=true}
}
function openHostDialog(host=null){
  editingHost=host;element("host-form").reset();element("host-name").value=host?.name||"";element("host-address").value=host?.address||"";element("host-user").value=host?.username||"automation";element("host-port").value=host?.port||22;element("host-websites").value=(host?.websites||[]).map(site=>`${site.name} | ${site.url}`).join("\n");
  element("setup-system").value=host?.distribution?.toLowerCase()==="ubuntu"?"ubuntu":"debian";element("setup-mode").value=host?"update":"create";
  element("host-dialog-title").textContent=host?"Edit host":"Add host";element("host-form").querySelector("button[type=submit]").textContent=host?"Save host":"Add host";element("address-choice").hidden=true;element("setup-preview").textContent="";hostStep(host?2:0);element("host-dialog").showModal();
}
function updateSetupConsent(){const full=element("setup-sudo").value==="full";element("setup-root-warning").hidden=!full;element("setup-root-consent").hidden=!full;element("copy-setup").disabled=!setupCommand||(full&&!element("setup-root-confirm").checked)}
async function generateSetup(){
  const generation=++setupRequest;setupCommand="";updateSetupConsent();element("setup-preview").textContent="";
  const username=element("host-user").value.trim(),port=Number(element("host-port").value);
  if(!validHost({name:"setup",address:"node-01",username,port})||username==="root"){element("setup-status").textContent="Choose a dedicated non-root user and a valid SSH port.";return}
  const params=new URLSearchParams({system:element("setup-system").value,username,port,mode:element("setup-mode").value,shell:element("setup-shell").value,sudo:element("setup-sudo").value,restricted_key:element("setup-restricted").checked,source:element("setup-source").value.trim()});element("setup-status").textContent="Preparing script…";
  try{const result=await request(`onboarding?${params}`);if(generation!==setupRequest)return;setupCommand=result.command;element("setup-preview").textContent=setupCommand;element("setup-status").textContent="Ready to copy. Review before running.";updateSetupConsent()}
  catch(error){if(generation===setupRequest)element("setup-status").textContent="Could not prepare script. Check the username, port and optional source IP/CIDR."}
}

async function addHost(event){event.preventDefault();const name=element("host-name").value.trim(),address=element("host-address").value.trim(),username=element("host-user").value.trim(),port=Number(element("host-port").value);if(!validHost({name,address,username,port})){element("host-form-error").textContent="Complete all fields with a valid SSH address, user and port.";return}let websites;try{websites=element("host-websites").value.split("\n").filter(line=>line.trim()).map(line=>{const split=line.indexOf("|");if(split<1)throw Error("Use name | https://address for each website.");const name=line.slice(0,split).trim(),url=new URL(line.slice(split+1).trim());if(!["http:","https:"].includes(url.protocol)||url.username||url.password)throw Error("Websites require HTTP(S) URLs without credentials.");return {name,url:url.href}})}catch(error){element("host-form-error").textContent=error.message;return}const result=await mutate(event.submitter,editingHost?`hosts/${editingHost.id}`:"hosts",editingHost?"PATCH":"POST",{name,address,username,port,websites},editingHost?"Host updated":"Host added");if(result){element("host-dialog").close();element("host-form").reset()}else element("host-form-error").textContent=element("message").textContent}
function validHost(h){return typeof h.name==="string"&&h.name.trim().length>0&&h.name.length<=100&&typeof h.address==="string"&&/^[A-Za-z0-9][A-Za-z0-9.:-]{0,254}$/.test(h.address)&&typeof h.username==="string"&&/^[a-z_][a-z0-9_-]{0,31}$/.test(h.username)&&Number.isInteger(h.port)&&h.port>0&&h.port<65536}
function importHost(event){const text=event.clipboardData?.getData("text")||"";if(!text.includes("HLC_HOST_BEGIN")&&!text.trim().startsWith("{"))return;event.preventDefault();try{if(text.length>16384)throw Error("Import is too large");const match=text.match(/HLC_HOST_BEGIN\s*([\s\S]*?)\s*HLC_HOST_END/);const data=JSON.parse(match?match[1]:text);if(data.format!=="homelab-commander-host"||data.version!==1)throw Error("Unsupported host import format or version");if(!Array.isArray(data.addresses)||data.addresses.length===0||data.addresses.length>64||data.addresses.some(address=>!validHost({...data,address})))throw Error("Invalid host import fields");element("host-name").value=data.name;element("host-user").value=data.username;element("host-port").value=data.port;element("import-address").replaceChildren(...data.addresses.map(address=>new Option(address,address)));element("address-choice").hidden=data.addresses.length===1;element("host-address").value=data.addresses.length===1?data.addresses[0]:"";if(data.addresses.length>1)element("import-address").prepend(new Option("Choose a reachable address","",true,true));element("host-form-error").textContent=data.addresses.length>1?"Choose one of the reported addresses before saving.":""}catch(error){element("host-form-error").textContent=error.message}}
function openTaskDialog(task=null){editingTask=task;taskTargetHost=view().name==="hosts"?view().id:null;element("task-form").reset();element("task-name").value=task?.name||"";element("task-description").value=task?.description||"";element("task-mode").value=task?.mode||"command";element("task-argv").value=task?.argv?JSON.stringify(task.argv):"";element("task-shell").value=task?.shell_command||"";for(const field of ["distributions","versions","programs","packages"])element(`task-${field}`).value=(task?.requirements?.[field]||[]).join(", ");element("task-sudo").checked=task?.requirements?.requires_sudo||false;element("task-enabled").checked=task?.enabled??true;element("task-form-error").textContent="";element("task-target").textContent=taskTargetHost?"After saving, check compatibility and assign this task to the current host.":"After saving, open a host to check compatibility and assign this task.";element("task-dialog-title").textContent=task?"Edit task":"Create task";element("task-dialog").showModal()}
async function addTask(event){event.preventDefault();try{const mode=element("task-mode").value;const requirements={requires_sudo:element("task-sudo").checked};for(const field of ["distributions","versions","programs","packages"])requirements[field]=element(`task-${field}`).value.split(",").map(v=>v.trim()).filter(Boolean);const body={name:element("task-name").value.trim(),description:element("task-description").value.trim(),mode,argv:mode==="command"?JSON.parse(element("task-argv").value):null,shell_command:mode==="shell"?element("task-shell").value:null,enabled:element("task-enabled").checked,requirements};if(mode==="command"&&(!Array.isArray(body.argv)||!body.argv.length||body.argv.some(v=>typeof v!=="string"||!v)))throw Error("Enter a non-empty JSON string array.");if(await mutate(event.submitter,editingTask?`custom-tasks/${editingTask.id}`:"custom-tasks",editingTask?"PATCH":"POST",body,editingTask?"Task updated":"Task added"))element("task-dialog").close();else element("task-form-error").textContent=element("message").textContent}catch(error){element("task-form-error").textContent=error.message}}
async function copyText(value){if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);return}const area=document.createElement("textarea");area.value=value;area.setAttribute("readonly","");area.style.position="fixed";area.style.opacity="0";(document.querySelector("dialog[open]")||document.body).appendChild(area);area.select();const copied=document.execCommand("copy");area.remove();if(!copied)throw Error("Clipboard unavailable. Select and copy the displayed text manually.")}
async function copySetup(button){if(!setupCommand||button.disabled)return;await run(button,()=>copyText(setupCommand),"Setup command copied");updateSetupConsent()}


async function copyKey(button){if(!state.public_key){message("Connect before copying the public key.","error");return}await run(button,()=>copyText(state.public_key),"Copied")}

async function hostClick(event){const button=event.target.closest("button");if(!button)return;const hostId=button.dataset.host;if(button.dataset.action&&hostId){const action=button.dataset.action;if(["update","reboot"].includes(action)&&!confirm(`Run ${action} on this host?`))return;await mutate(button,hostActionPath(hostId,action),"POST",undefined,`${action.replace("_"," ")} queued`);return}if(button.dataset.deleteHost){if(confirm("Delete this host?")){if(await mutate(button,`hosts/${button.dataset.deleteHost}`,"DELETE",undefined,"Host deleted"))location.hash="/hosts"}return}if(button.dataset.editHost)openHostDialog(state.hosts.find(value=>value.id===button.dataset.editHost))}
async function taskClick(event){const button=event.target.closest("button");if(!button)return;const host=button.dataset.host;if(button.dataset.task&&host){if(confirm("Run this custom task on the selected host? Prerequisites will be checked again."))await mutate(button,customTaskPath(host,button.dataset.task),"POST",undefined,"Task queued");return}if(button.dataset.checkTask){await run(button,async()=>{await request(`hosts/${host}/tasks/${button.dataset.checkTask}/check`,{method:"POST"});await loadView();render()},"Compatibility checked");return}if(button.dataset.assignTask){const result=currentHostTasks.find(c=>c.task_id===button.dataset.assignTask);await mutate(button,`hosts/${host}/tasks/${button.dataset.assignTask}/assignment`,"PUT",{enabled:!result?.enabled},"Assignment updated");return}if(button.dataset.unassignTask){await mutate(button,`hosts/${host}/tasks/${button.dataset.unassignTask}/assignment`,"DELETE",undefined,"Task unassigned");return}if(button.dataset.toggleTask){const task=state.custom_tasks.find(t=>t.id===button.dataset.toggleTask);await mutate(button,`custom-tasks/${task.id}`,"PATCH",{enabled:!task.enabled},"Task updated");return}if(button.dataset.deleteTask){if(confirm("Delete this task?"))await mutate(button,`custom-tasks/${button.dataset.deleteTask}`,"DELETE",undefined,"Task deleted");return}if(button.dataset.editTask)openTaskDialog(state.custom_tasks.find(value=>value.id===button.dataset.editTask))}
async function reviewJob(button){await run(button,async()=>{await request(`jobs/${button.dataset.reviewJob}/review`,{method:"POST"});await refreshDashboard();await loadJobRoute(true)},"Job marked as reviewed")}
async function jobClick(event){const button=event.target.closest("button[data-job-log]");if(!button)return;const target=`#/jobs/${button.dataset.jobLog}`;if(location.hash===target)await run(button,()=>loadJobRoute(true),"Job loaded");else location.hash=target}

async function previewLog(button){
  const id=button.dataset.previewLog;element("log-preview-output").textContent="Loading log…";element("log-preview-link").href=`#/jobs/${id}`;element("log-preview").showModal();
  try{const log=await request(`jobs/${id}/log`);element("log-preview-output").textContent=log.output.slice(0,3000)+(log.output.length>3000||log.truncated?"\n… Open the full job for more.":"")||"No output recorded."}catch(error){element("log-preview-output").textContent=error.message}
}
document.addEventListener("DOMContentLoaded",()=>{
  element("connect-form").addEventListener("submit",connect);element("disconnect").addEventListener("click",disconnect);
  element("host-form").addEventListener("submit",addHost);element("task-form").addEventListener("submit",addTask);
  element("host-system-next").addEventListener("click",()=>hostStep(1));
  element("host-skip-setup").addEventListener("click",()=>hostStep(2));
  element("host-setup-back").addEventListener("click",()=>hostStep(0));
  element("host-setup-next").addEventListener("click",()=>hostStep(2));
  element("host-connection-back").addEventListener("click",()=>hostStep(1));
  element("host-update-setup").addEventListener("click",()=>{element("setup-mode").value="update";hostStep(0)});
  for(const id of ["setup-system","setup-mode","setup-shell","setup-sudo","setup-restricted","setup-source","host-user","host-port"])element(id).addEventListener("input",()=>{element("setup-root-confirm").checked=false;if(!element("host-preparation").hidden)generateSetup()});
  element("setup-root-confirm").addEventListener("change",updateSetupConsent);
  element("copy-setup").addEventListener("click",event=>copySetup(event.currentTarget));
  element("copy-key").addEventListener("click",event=>copyKey(event.currentTarget));
  for(const id of ["host-name","host-address","host-user","host-port"])element(id).addEventListener("paste",importHost);
  element("import-address").addEventListener("change",()=>{element("host-address").value=element("import-address").value;element("host-form-error").textContent=""});
  document.addEventListener("click",event=>{const button=event.target.closest("button");if(!button)return;if(button.hasAttribute("data-add-host"))openHostDialog();if(button.hasAttribute("data-add-task"))openTaskDialog();if(button.hasAttribute("data-close-dialog"))button.closest("dialog").close();if(button.dataset.previewLog)previewLog(button);if(button.dataset.reviewJob)reviewJob(button);hostClick(event);taskClick(event);jobClick(event)});
  element("job-filters").addEventListener("submit",event=>{event.preventDefault();const params=new URLSearchParams();if(element("job-state").value)params.set("state",element("job-state").value);if(element("job-host").value)params.set("host_id",element("job-host").value);location.hash=`/jobs?${params}`});
  const pageJobs=delta=>{const params=view().params;params.set("offset",Math.max(0,currentJobPage.offset+delta*currentJobPage.limit));location.hash=`/jobs?${params}`};element("jobs-previous").addEventListener("click",()=>pageJobs(-1));element("jobs-next").addEventListener("click",()=>pageJobs(1));
  element("auto-host-checks").addEventListener("change",event=>{stopVisibleChecks();state.preferences={enabled:event.target.checked};return run(event.target,async()=>{state.preferences=await request("preferences/host-checks",{method:"PATCH",body:{enabled:event.target.checked}});stopVisibleChecks();render()},"Host check preference saved")});
  document.addEventListener("visibilitychange",syncVisibleChecks);
  element("log-preview-link").addEventListener("click",()=>element("log-preview").close());
  document.addEventListener("error",event=>{if(event.target.matches?.(".website-icon img"))event.target.hidden=true},true);
  window.addEventListener("hashchange",()=>{if(connected)run(null,async()=>{await loadView();render();await loadJobRoute()})});initialize();
});
window.addEventListener("pagehide",()=>{stopJobPolling();stopVisibleChecks()});
