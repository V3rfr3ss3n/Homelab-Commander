
"use strict";
const apiBase = new URL(document.querySelector('meta[name="api-base"]').content, document.baseURI);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const ingress = document.querySelector('meta[name="ingress-mode"]').content === "true";
const ACTIVE_JOB_POLL_INTERVAL_MS = 1500;
const JOB_POLL_BACKOFF_MS = [1500, 3000, 5000];
const ACTIVE_JOB_STATES = new Set(["queued", "running"]);
const MUTATING_JOB_ACTIONS = new Set(["update", "reboot", "custom_task"]);
let state = {info:null, hosts:[], custom_tasks:[], jobs:[], active_jobs:[], public_key:""};
let connected = false;
let jobPollTimer = null;
let jobPollInFlight = false;
let jobPollFailureCount = 0;
let selectedJobId = null;
let selectedJobLog = null;
let selectedJob = null;
let selectedJobError = null;
let selectedJobLogError = null;
let selectedJobTruncated = false;
let jobDetailRequest = 0;
let renderedJobLog = null;
let jobLogMatches = [];
let jobLogMatch = 0;
let jobRerunPending = false;
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
function syncSearch(id,value){const input=element(id);if(document.activeElement!==input)input.value=value}
function escapeHtml(value){const node=document.createElement("div");node.textContent=value??"";return node.innerHTML.replaceAll('"',"&quot;").replaceAll("'","&#39;")}
let messageTimer=null;
function message(value,kind="",link=null){
  if(messageTimer!==null)clearTimeout(messageTimer);messageTimer=null;
  const target=element("message"),anchor=element("message-link");
  element("message-text").textContent=value;target.className=kind;target.hidden=!value;
  target.setAttribute("role",kind==="error"?"alert":"status");
  anchor.hidden=!link;if(link){anchor.href=link.href;anchor.textContent=link.label||"Open job"}else{anchor.removeAttribute("href");anchor.textContent=""}
  if(value&&kind==="success")messageTimer=setTimeout(()=>{target.hidden=true;messageTimer=null},8000);
}
function confirmAction(title,description,targets=[],confirmLabel="Confirm",options={}){return new Promise(resolve=>{
  const dialog=element("confirm-dialog"),accept=element("confirm-accept"),cancel=element("confirm-cancel"),ack=element("confirm-ack");
  element("confirm-title").textContent=title;element("confirm-description").textContent=description;element("confirm-targets").replaceChildren(...targets.map(value=>{const item=document.createElement("div");item.textContent=value;return item}));
  element("confirm-ack-label").hidden=!options.acknowledgement;element("confirm-ack-text").textContent=options.acknowledgement||"";ack.checked=false;accept.disabled=Boolean(options.acknowledgement);accept.textContent=confirmLabel;
  const changed=()=>accept.disabled=Boolean(options.acknowledgement)&&!ack.checked;
  const finish=value=>{dialog.close();accept.removeEventListener("click",yes);cancel.removeEventListener("click",no);dialog.removeEventListener("cancel",escape);ack.removeEventListener("change",changed);resolve(value)};
  const yes=()=>{if(!accept.disabled)finish(true)},no=()=>finish(false),escape=event=>{event.preventDefault();finish(false)};
  accept.addEventListener("click",yes);cancel.addEventListener("click",no);dialog.addEventListener("cancel",escape);ack.addEventListener("change",changed);dialog.showModal();cancel.focus();
})}
function setBusy(button,busy){if(button)button.disabled=busy}
function backendUnavailable(){state.unavailable=true;element("connection-hint").textContent="Backend unavailable. Displayed data may be out of date.";renderBackendStatus()}
function jobError(errorCode){const labels={apt_lock_unavailable:"APT is locked by another process",check_updates_apt_cache_refresh_failed:"Check updates failed during APT cache refresh",check_updates_facts_failed:"Check updates failed while collecting system facts",check_updates_package_list_failed:"Check updates failed while listing packages",check_updates_reboot_status_failed:"Check updates failed while reading reboot status",invalid_ansible_output:"Ansible returned an invalid structured result",python_interpreter_unavailable:"Python 3 is not available on the host",reboot_failed:"Reboot failed",sudo_unavailable:"Non-interactive sudo is not available",test_connection_failed:"SSH connection test failed",test_connection_facts_failed:"Connection test failed while collecting system facts",update_packages_failed:"Package update failed"};return labels[errorCode]||errorCode.replaceAll("_"," ")}
function activeJobs(){const jobs=new Map(state.active_jobs.map(job=>[job.id,job]));for(const job of state.jobs)jobs.set(job.id,job);return [...jobs.values()].filter(job=>ACTIVE_JOB_STATES.has(job.state))}
function hasActiveJobs(){return Boolean(selectedJob&&ACTIVE_JOB_STATES.has(selectedJob.state))||(state.dashboard?.running_jobs||state.dashboard?.queued_jobs||0)>0||activeJobs().length>0}
function stopJobPolling(){if(jobPollTimer!==null)window.clearTimeout(jobPollTimer);jobPollTimer=null;jobPollFailureCount=0}
function scheduleJobPolling(delay=ACTIVE_JOB_POLL_INTERVAL_MS){if(!connected||!hasActiveJobs()||jobPollTimer!==null||jobPollInFlight)return;jobPollTimer=window.setTimeout(pollJobs,delay)}
function syncJobPolling(){if(connected&&hasActiveJobs())scheduleJobPolling();else stopJobPolling()}
function clearProtectedData(){stateRequest++;clearWebsiteIcons();stopJobPolling();stopVisibleChecks();document.querySelectorAll("dialog[open]").forEach(d=>d.close());state={info:null,hosts:[],custom_tasks:[],jobs:[],active_jobs:[],public_key:""};selectedJobId=null;selectedJob=null;selectedJobLog=null;selectedJobError=null;selectedJobLogError=null;jobDetailRequest++;viewRequest++;for(const id of ["backend-status","job-highlights","dashboard","key","hosts","tasks","jobs","job-metadata","log","notices","history","activity","host-info","host-tasks","host-jobs"])element(id).replaceChildren();element("job-detail").hidden=true;element("protected-content").hidden=true;element("connect-placeholder").hidden=false;element("host-context").hidden=true;element("selection-info").textContent="";element("filter-count").textContent="0";closeSelection();closeTimelinePoint()}
function setDisconnected(hint="Enter your API token to load backend data."){connected=false;element("token").value="";element("token").disabled=ingress;clearProtectedData();element("connection-state").className="connection-state";element("connection-label").textContent="Not connected";element("connection-hint").textContent=hint;element("connect").hidden=false;element("refresh").hidden=true;element("connect").textContent=ingress?"Retry":"Connect";element("disconnect").hidden=true;element("token-field").hidden=ingress}
function setConnecting(){element("connection-state").className="connection-state connecting";element("connection-label").textContent="Connecting…";element("connection-hint").textContent="Loading backend data."}
function setConnected(){connected=true;element("token").disabled=true;element("connection-state").className="connection-state connected";element("connection-label").textContent="Connected";element("connection-hint").textContent="Backend data is loaded.";element("protected-content").hidden=false;element("connect-placeholder").hidden=true;element("connect").hidden=true;element("refresh").hidden=false;element("token-field").hidden=true;element("disconnect").hidden=ingress;syncJobPolling();syncVisibleChecks()}

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

let stateRequest=0;
async function loadActiveJobs(){
  const groups=await Promise.all([...ACTIVE_JOB_STATES].map(async status=>{
    const jobs=[],params=new URLSearchParams({state:status,sort:"oldest",limit:"100",offset:"0"});
    let total=null;
    do{params.set("offset",String(jobs.length));const page=await request(`jobs/page?${params}`);if(total===null)total=page.total;jobs.push(...page.items);if(!page.items.length)break}while(jobs.length<total);
    return jobs;
  }));
  return [...new Map(groups.flat().map(job=>[job.id,job])).values()];
}
async function refreshDashboard(){
  const generation=++stateRequest;
  const [info,hosts,key,tasks,jobs,dashboard,preferences,active_jobs]=await Promise.all([request("info"),request("hosts"),request("public-key"),request("custom-tasks"),request("jobs"),request("dashboard"),request("preferences/host-checks"),loadActiveJobs()]);
  if(generation!==stateRequest)return;
  state={info,hosts,custom_tasks:tasks,jobs,active_jobs,public_key:key.public_key,dashboard,preferences};
  await loadView();render();await loadJobRoute(true);
}

async function refreshLiveState(){const generation=++stateRequest;const [hosts,jobs,dashboard,active_jobs]=await Promise.all([request("hosts"),request("jobs"),request("dashboard"),loadActiveJobs()]);if(generation!==stateRequest)return;state={...state,hosts,jobs,dashboard,active_jobs,unavailable:false};await loadView();render();if(routeJobId())await loadJobRoute(true,false)}

async function pollJobs(){jobPollTimer=null;if(!connected||!hasActiveJobs())return;jobPollInFlight=true;try{const recovered=jobPollFailureCount>0;await refreshLiveState();jobPollFailureCount=0;if(recovered)message("Live job updates recovered.","success")}catch(error){if(connected){if(jobPollFailureCount===0)message("Live job refresh failed; retrying automatically.","error");jobPollFailureCount+=1}}finally{jobPollInFlight=false;if(connected&&hasActiveJobs()){const index=Math.min(jobPollFailureCount,JOB_POLL_BACKOFF_MS.length-1);scheduleJobPolling(JOB_POLL_BACKOFF_MS[index])}}}

async function run(button,operation,success=""){setBusy(button,true);message(success?"Working…":"");try{const result=await operation();message(success,"success",result?.notification);return true}catch(error){message(error instanceof Error?error.message:"Request failed","error");return false}finally{setBusy(button,false)}}

async function login(apiToken){const response=await fetch(new URL("auth/login",apiBase),{method:"POST",headers:{Accept:"application/json","Content-Type":"application/json","X-CSRF-Token":csrf},credentials:"same-origin",cache:"no-store",body:JSON.stringify({api_token:apiToken})});if(!response.ok){let detail="Authentication failed";try{const payload=await response.json();if(typeof payload.detail==="string")detail=payload.detail}catch{}throw new Error(detail)}}
async function connect(event){event.preventDefault();const button=element("connect"),wasConnected=connected;let enteredToken="";if(!ingress&&!connected){enteredToken=element("token").value.trim();if(enteredToken.length<32){message("The API token must contain at least 32 characters.","error");return}element("token").value=""}setConnecting();const success=await run(button,async()=>{if(!ingress&&!wasConnected)await login(enteredToken);enteredToken="";await refreshDashboard()});enteredToken="";if(success)setConnected();else if(element("connection-label").textContent==="Connecting…"){if(wasConnected)setConnected();else setDisconnected("Connection failed. Check the backend and enter your API token to retry.")}}
async function disconnect(){const button=element("disconnect");stopJobPolling();const success=await run(button,async()=>{await request("auth/logout",{method:"POST"})},"Disconnected");setDisconnected();message(success?"Disconnected":"Disconnect failed; local data was cleared.",success?"success":"error")}

async function initialize(){setDisconnected();if(ingress){setConnecting();const success=await run(element("connect"),refreshDashboard);if(success)setConnected();return}let response;try{response=await fetch(new URL("auth/session",apiBase),{headers:{Accept:"application/json"},credentials:"same-origin",cache:"no-store"})}catch{message("Could not check the existing UI session.","error");return}if(response.status===401)return;if(!response.ok){message(`Session check failed (${response.status}).`,"error");return}setConnecting();const success=await run(element("connect"),refreshDashboard);if(success)setConnected();else setDisconnected("Session recovery failed. Please connect again.")}

let viewRequest = 0;
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
function renderSelection(){
  const route=view(),hostId=route.name==="hosts"&&route.id?route.id:route.params.get("host_id"),host=state.hosts.find(item=>item.id===hostId),labels=[];
  let count=0;
  if(host){labels.push(`Selected host: ${host.name}`);count++}
  if(route.name==="jobs"&&route.id){labels.push(`Job: ${actionName(state.jobs.find(job=>job.id===route.id)?.action)}`);count++}
  const names={state:"State",action:"Action",filter:"Host status",h_search:"Find host",t_filter:"Tasks",t_search:"Find task"};
  for(const [key,label] of Object.entries(names)){const value=route.params.get(key);if(value){labels.push(`${label}: ${key==="action"?actionName(value):value}`);count++}}
  const range=route.params.get("range"),defaultRange=route.name==="jobs"?"all":"7d";
  if(route.params.has("start")||route.params.has("end")||(range&&range!==defaultRange)){labels.push(`Period: ${range||"custom"}`);count++}
  const defaults={range:defaultRange,display:route.name==="jobs"?"table":"graph",sort:"newest",h_sort:"name",t_sort:"name",offset:"0"};
  const viewOptions=["display","sort","h_sort","t_sort","offset"].filter(key=>route.params.has(key)&&route.params.get(key)!==defaults[key]);
  if(viewOptions.length)labels.push("View options changed");
  const active=Boolean(count||viewOptions.length);element("host-context").hidden=!state.info;element("filter-count").textContent=count;element("filter-count").classList.toggle("empty",count===0);
  element("reset-view").disabled=!active;element("selection-info").textContent=labels.join("\n")||"Default view · no active filters";
  element("selection-toggle").title=labels.join(" · ")||"No active filters";element("selection-toggle").setAttribute("aria-label",`Selection and filters: ${count} active`);
}

function resetView(){
  const route=view(),tab=["dashboard","hosts","tasks","jobs"].includes(route.name)?route.name:"dashboard";
  closeSelection();location.hash=`/${tab}`;
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
// Keep the same image nodes and failure state throughout this authenticated page.
const websiteIcons=new Map();
const FAVICON_PATHS=["/favicon.ico","/favicon.svg","/favicon.png","/apple-touch-icon.png","/favicons/favicon-32x32.png"];
function websiteIconKey(host,site,index){return JSON.stringify([host.id,index,site.url,site.icon_url||""])}
function websiteLinks(host){return (host.websites||[]).map((site,index)=>`<span data-website-icon="${escapeHtml(websiteIconKey(host,site,index))}"></span>`).join("")}
function clearWebsiteIcons(hostId=null){
  for(const [key,entry] of websiteIcons){if(hostId&&entry.hostId!==hostId)continue;entry.cancelled=true;entry.image.removeAttribute("src");websiteIcons.delete(key)}
}
function syncWebsiteIcons(visible){
  const sites=new Map(state.hosts.flatMap(host=>(host.websites||[]).map((site,index)=>[websiteIconKey(host,site,index),{host,site}])));
  for(const [key,entry] of websiteIcons){if(!sites.has(key)){entry.cancelled=true;entry.image.removeAttribute("src");websiteIcons.delete(key)}}
  if(!visible)return;
  for(const placeholder of document.querySelectorAll("[data-website-icon]")){
    const key=placeholder.dataset.websiteIcon,value=sites.get(key);if(!value)continue;
    let entry=websiteIcons.get(key);
    if(!entry){
      const {host,site}=value,url=new URL(site.url),anchor=document.createElement("a"),initial=document.createElement("span"),image=new Image(18,18);
      anchor.className="website-icon";anchor.href=url.href;anchor.target="_blank";anchor.rel="noopener noreferrer";anchor.referrerPolicy="no-referrer";anchor.dataset.iconStatus="loading";
      initial.setAttribute("aria-hidden","true");image.alt="";image.loading="eager";image.referrerPolicy="no-referrer";image.hidden=true;anchor.append(initial,image);
      entry={hostId:host.id,anchor,initial,image,cancelled:false,index:0,sources:site.icon_url?[site.icon_url]:FAVICON_PATHS.map(path=>new URL(path,url.origin).href)};
      const current=entry;
      image.addEventListener("load",()=>{if(current.cancelled)return;image.hidden=false;anchor.dataset.iconStatus="loaded";anchor.title=current.name});
      image.addEventListener("error",()=>{if(current.cancelled)return;image.hidden=true;if(++current.index<current.sources.length){image.src=current.sources[current.index]}else{anchor.dataset.iconStatus="unavailable";image.removeAttribute("src");anchor.title=current.name+" — Icon unavailable. Check the icon URL, certificate or site access rules. Retry from Edit host."}});
      websiteIcons.set(key,entry);image.src=entry.sources[0];
    }
    entry.name=value.site.name;entry.initial.textContent=value.site.name.slice(0,1).toUpperCase();entry.anchor.setAttribute("aria-label","Open "+value.site.name);
    entry.anchor.title=value.site.name+(entry.anchor.dataset.iconStatus==="unavailable"?" — Icon unavailable. Check the icon URL, certificate or site access rules. Retry from Edit host.":"");
    placeholder.replaceWith(entry.anchor);
  }
}

function renderBackendStatus(){const online=Boolean(state.info&&!state.unavailable);element("backend-status").className=`backend-status ${online?"online":"offline"}`;element("backend-status").textContent=online?"Backend online":"Backend unavailable";element("backend-status").title=element("backend-status").textContent}
function highlightJob(job,label){
  if(!job)return `<article class="job-highlight"><small>${label}</small><p class="empty">No job yet</p></article>`;
  const preview=job.short_error||(job.error_code?jobError(job.error_code):job.state==="success"?"Completed successfully":job.state==="running"?"Currently running":job.state==="queued"?"Waiting for a worker":"Job details available");
  return `<article class="job-highlight"><small>${label}</small><a class="job-title" href="#/jobs/${job.id}" title="${escapeHtml(job.action)}">${escapeHtml(actionName(job.action))}</a><p>${escapeHtml(job.host_name||"All hosts")} · ${timeLabel(job.finished_at||job.created_at)}</p><p class="job-preview state-${job.state}" title="${escapeHtml(job.error_code||job.state)}">${escapeHtml(preview)}</p><div class="actions"><a href="#/jobs/${job.id}">Open job →</a>${job.log_available?`<button class="text-button" data-preview-log="${job.id}">Log preview</button>`:""}</div></article>`;
}
let currentTimeline={points:[],total:0};
let shownHosts=[];
function historyMode(){const route=view();return route.params.get("display")||(route.name==="jobs"?"table":"graph")}
function historyPeriod(){
  const params=view().params,range=params.get("range")||(view().name==="jobs"?"all":"7d");
  if(params.has("start")&&params.has("end"))return {start:params.get("start"),end:params.get("end")};
  if(range==="all"&&historyMode()==="table")return null;
  const hours=({"1h":1,"24h":24,"7d":168,"30d":720,"90d":2160})[range]||168;
  const end=new Date(Date.now()+1000);end.setMilliseconds(0);return {start:new Date(end-hours*3600000).toISOString(),end:end.toISOString()};
}
function jobQuery(){const params=new URLSearchParams();for(const key of ["host_id","state","action","sort","offset"])if(view().params.has(key))params.set(key,view().params.get(key));const period=historyPeriod();if(period){params.set("start",period.start);params.set("end",period.end)}return params}
function updateRoute(values){const route=view(),params=route.params;for(const [key,value] of Object.entries(values)){if(value===null||value==="")params.delete(key);else params.set(key,value)}location.hash=`/${route.name}?${params}`}
function filteredHosts(){
  const params=view().params,filter=params.get("filter"),search=(params.get("h_search")||"").toLocaleLowerCase();
  return state.hosts.filter(h=>(h.name+" "+h.address).toLocaleLowerCase().includes(search)).filter(h=>filter==="security"?h.security_updates>0:filter==="updates"?h.updates>0:filter==="reboot"?h.reboot_required:filter==="stale"?staleHost(h):true).sort((a,b)=>{
    const sort=params.get("h_sort"),primary=sort==="updates"?b.updates-a.updates:sort==="security"?b.security_updates-a.security_updates:sort==="checked"?(Date.parse(a.checked_at)||0)-(Date.parse(b.checked_at)||0):0;
    return primary||a.name.localeCompare(b.name,undefined,{numeric:true,sensitivity:"base"});
  });
}
function filteredTasks(){const params=view().params,search=(params.get("t_search")||"").toLocaleLowerCase(),filter=params.get("t_filter");return state.custom_tasks.filter(t=>(t.name+" "+t.description).toLocaleLowerCase().includes(search)).filter(t=>filter==="enabled"?t.enabled:filter==="disabled"?!t.enabled:filter==="assigned"?t.host_ids.length>0:true).sort((a,b)=>(params.get("t_sort")==="hosts"?b.host_ids.length-a.host_ids.length:0)||a.name.localeCompare(b.name))}
function pointRoute(point){const params=view().params;params.set("start",point.start);params.set("end",point.end);params.set("range","custom");params.set("display","table");params.delete("offset");return `#/${view().name}?${params}`}
function localDateInput(value){const date=new Date(value);return new Date(date-date.getTimezoneOffset()*60000).toISOString().slice(0,19)}
function timelinePath(points,status,x,y){
  if(!points.length)return "";
  const coordinates=points.map(point=>({x:x(point.timestamp),y:y(point.counts[status]||0)}));
  if(coordinates.length===1)return `M ${coordinates[0].x} ${coordinates[0].y}`;
  const slopes=coordinates.slice(0,-1).map((point,index)=>
    (coordinates[index+1].y-point.y)/(coordinates[index+1].x-point.x));
  const tangents=coordinates.map((point,index)=>{
    if(index===0)return slopes[0];
    if(index===coordinates.length-1)return slopes.at(-1);
    const before=slopes[index-1],after=slopes[index];
    if(before===0||after===0||Math.sign(before)!==Math.sign(after))return 0;
    const left=coordinates[index].x-coordinates[index-1].x,right=coordinates[index+1].x-coordinates[index].x;
    return (left+right)/((left/before)+(right/after));
  });
  let path=`M ${coordinates[0].x} ${coordinates[0].y}`;
  for(let index=0;index<coordinates.length-1;index++){
    const first=coordinates[index],last=coordinates[index+1],width=last.x-first.x;
    const low=Math.min(first.y,last.y),high=Math.max(first.y,last.y);
    const controlOne=Math.max(low,Math.min(high,first.y+tangents[index]*width/3));
    const controlTwo=Math.max(low,Math.min(high,last.y-tangents[index+1]*width/3));
    path+=` C ${first.x+width/3} ${controlOne}, ${last.x-width/3} ${controlTwo}, ${last.x} ${last.y}`;
  }
  return path;
}
function pointStatus(job){return job.needs_review?"needs-review":job.state==="failed"?"reviewed":job.state}
function renderHistory(){
  const graph=historyMode()==="graph",period=historyPeriod(),params=view().params;
  element("history-toggle").textContent=graph?"▤":"⌁";element("history-toggle").setAttribute("aria-label",graph?"Show table":"Show graph");element("history-toggle").title=graph?"Show table":"Show graph";
  element("job-sort-label").hidden=graph;
  element("history-chart").hidden=!graph;element("jobs-section").hidden=graph;closeTimelinePoint();
  element("history-range").value=params.get("range")||(view().name==="jobs"?"all":"7d");
  element("history-custom").hidden=element("history-range").value!=="custom";
  if(period){syncSearch("history-start",localDateInput(period.start));syncSearch("history-end",localDateInput(period.end))}
  const dateFormat=new Intl.DateTimeFormat(navigator.language,{dateStyle:"medium",timeStyle:"short"});
  element("history-period").textContent=period?`${dateFormat.format(new Date(period.start))} – ${dateFormat.format(new Date(period.end))}`:"All stored jobs";
  const historyCount=graph?currentTimeline.total:currentJobPage.total;
  element("history-total").textContent=`${historyCount} ${historyCount===1?"job":"jobs"}`;
  if(!graph)return;
  const width=900,height=365,left=98,right=98,top=90,bottom=90,plotHeight=height-top-bottom,points=currentTimeline.points;
  const start=Date.parse(currentTimeline.start),end=Date.parse(currentTimeline.end),max=Math.max(1,...points.map(p=>p.total));
  const x=time=>left+(Date.parse(time)-start)/(end-start)*(width-left-right),y=count=>top+plotHeight-count/max*plotHeight;
  const grid=Array.from({length:5},(_,i)=>{const value=max*i/4;return `<line class="graph-grid" x1="${left}" x2="${width-right}" y1="${y(value)}" y2="${y(value)}"/><text x="${left-8}" y="${y(value)+4}" text-anchor="end">${Number.isInteger(value)?value:value.toFixed(1)}</text>`}).join("");
  const series=["success","failed","cancelled","running","queued"].map(status=>`<g class="graph-series ${status}"><path d="${timelinePath(points,status,x,y)}"/></g>`).join("");
  const markers=points.map((point,index)=>{const single=point.total===1?point.jobs[0]:null;const dominant=Object.entries(point.counts).filter(([,count])=>count>0).sort((left,right)=>right[1]-left[1])[0];const anchorState=single?.state||dominant?.[0]||"success",anchorCount=single?1:dominant?.[1]||0,status=point.review_required>0?"needs-review":anchorState==="failed"?"reviewed":anchorState,highlight=point.jobs.some(j=>j.id===state.dashboard?.last_job?.id||j.id===state.dashboard?.last_failed_job?.id);const distribution=Object.entries(point.counts).filter(([,count])=>count>0).map(([name,count])=>`${name} ${count}`).join(", ");const title=single?`${actionName(single.action)} · ${single.host_name||"No host"} · ${single.state} · ${single.finished_at||single.started_at||single.created_at}`:`${point.total} jobs · ${distribution} · ${point.review_required} need review · anchor ${anchorState} ${anchorCount} · ${point.start} – ${point.end}`;const markerY=y(anchorCount);return `<a href="${single?`#/jobs/${single.id}`:escapeHtml(pointRoute(point))}" data-point="${index}" data-anchor-state="${anchorState}" data-anchor-count="${anchorCount}" aria-label="${escapeHtml(title)}"><g class="timeline-point ${status} ${highlight?"latest-point":""}"><circle cx="${x(point.timestamp)}" cy="${markerY}" r="${point.total>1?Math.min(17,9+Math.log2(point.total)):5}"/><title>${escapeHtml(title)}</title>${point.total>1?`<text x="${x(point.timestamp)}" y="${markerY+4}" text-anchor="middle">${point.total}</text>`:""}</g></a>`}).join("");
  const labels=Array.from({length:5},(_,i)=>{const time=new Date(start+(end-start)*i/4);return `<text x="${x(time.toISOString())}" y="${height-12}" text-anchor="${i===0?"start":i===4?"end":"middle"}"><title>${time.toISOString()}</title>${escapeHtml(new Intl.DateTimeFormat(navigator.language,(end-start)<=86400000?{hour:"2-digit",minute:"2-digit"}:{month:"short",day:"numeric",hour:"2-digit"}).format(time))}</text>`}).join("");
  element("history").innerHTML=`<svg class="history-graph" viewBox="0 0 ${width} ${height}" role="group" aria-label="Job timeline; select a point to open a job or grouped time window">${grid}${series}${markers}${labels}<g id="history-popover" hidden></g></svg>${points.length?"":'<p class="empty">No jobs in this period. Choose a longer period or adjust the filters.</p>'}`;
}
function closeTimelinePoint(){const preview=element("history-popover");if(preview){preview.setAttribute("hidden","");preview.removeAttribute("data-source-point")}}
function showTimelinePoint(target){
  const anchor=target.closest?.("[data-point]");if(!anchor)return;
  const point=currentTimeline.points[Number(anchor.dataset.point)],preview=element("history-popover");if(!point||!preview)return;
  if(!preview.hasAttribute("hidden")&&preview.dataset.sourcePoint===anchor.dataset.point)return;
  const circle=anchor.querySelector("circle"),cx=Number(circle.getAttribute("cx")),cy=Number(circle.getAttribute("cy"));
  preview.setAttribute("transform",`translate(${cx} ${cy})`);preview.dataset.sourcePoint=anchor.dataset.point;
  if(point.total===1){
    const job=point.jobs[0],label=`${actionName(job.action)} · ${job.host_name||"No host"} · ${job.state}`;
    const labelX=cx>450?-310:12;
    preview.innerHTML=`<a href="#/jobs/${job.id}" aria-label="${escapeHtml(label)}"><rect class="point-tooltip" x="${labelX}" y="-62" width="298" height="42" rx="8"/><text class="point-tooltip-label" x="${labelX+10}" y="-37">${escapeHtml(label.slice(0,48))}</text><title>${escapeHtml(label)}</title></a>`;
  }else{
    const jobs=point.jobs.map((job,index)=>{
      const angle=-Math.PI/2+index*2*Math.PI/point.jobs.length,x=Math.cos(angle)*64,y=Math.sin(angle)*64;
      const label=`${actionName(job.action)} · ${job.host_name||"No host"} · ${job.state} · ${job.needs_review?"Needs review · ":""}${job.finished_at||job.created_at}`;
      return `<a class="orbit-job state-${pointStatus(job)}" href="#/jobs/${job.id}" aria-label="Open job: ${escapeHtml(label)}"><circle cx="${x}" cy="${y}" r="17"/><circle class="orbit-core" cx="${x}" cy="${y}" r="3"/><title>${escapeHtml(label)}</title></a>`;
    }).join("");
    preview.innerHTML=`<a class="orbit-center" href="${escapeHtml(pointRoute(point))}" aria-label="${point.total} jobs. Open these jobs in the table."><circle r="${Number(circle.getAttribute("r"))+3}"/></a>${jobs}<text class="orbit-caption" y="94" text-anchor="middle">${point.jobs.length} of ${point.total} jobs · select center for all</text>`;
  }
  preview.removeAttribute("hidden");
}

async function updateShown(button){
  const targets=state.hosts.filter(h=>h.checked_at&&h.updates>0&&!activeJobs().some(j=>j.host_id===h.id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action)));
  if(!targets.length)return;
  if(!await confirmAction(`Update all (${targets.length}) hosts?`,`Run regular system updates on these hosts during a suitable maintenance window? No host reboot is requested. Review restart requirements after completion.`,targets.map(host=>`${host.name} · ${host.updates} updates${host.reboot_required?" · Restart already required":""}`),"Queue updates",{acknowledgement:"I will review completed updates and restart requirements. Any host reboot must be confirmed separately."}))return;
  await run(button,async()=>{let count=0;const failed=[];for(const host of targets){try{await request(hostActionPath(host.id,"update"),{method:"POST"});count++}catch{failed.push(host.name)}}await refreshDashboard();if(failed.length)throw Error(`${count} updates queued. Could not queue: ${failed.join(", ")}. Review host status before retrying.`);return {notification:{href:"#/jobs?action=update",label:"Open jobs"}}},"Updates queued");
}
function hostSystem(host){
  const distribution=(host.distribution||"").toLowerCase();
  const icon=distribution.includes("proxmox")||(host.kernel||"").includes("-pve")?"proxmox":distribution.includes("ubuntu")?"ubuntu":distribution.includes("debian")?"debian":"linux";
  const label=[host.distribution,host.distribution_version].filter(Boolean).join(" ")||"System not checked";
  return {icon,label:icon==="proxmox"&&!distribution.includes("proxmox")?`${label} · PVE kernel`:label};
}
function systemIcon(host){const system=hostSystem(host);return `<span class="system-icon" data-os="${system.icon}" title="${escapeHtml(system.label)}" aria-hidden="true">${buttonIcon(system.icon)}</span>`}
function hostActions(host,details=false){
  const jobs=activeJobs().filter(job=>job.host_id===host.id),locked=jobs.some(job=>MUTATING_JOB_ACTIONS.has(job.action));
  const action=(name,label,icon,danger=false)=>{const busy=jobs.some(job=>job.action===name);return `<button type="button" ${danger?'class="danger" ':""}data-host="${host.id}" data-action="${name}" aria-label="${label}" title="${label}" ${busy||(MUTATING_JOB_ACTIONS.has(name)&&locked)?"disabled":""}>${name==="check_updates"?`<span class="refresh-glyph ${busy?"spinning":""}">${buttonIcon(icon)}</span>`:buttonIcon(icon)}<span class="action-label">${busy&&name!=="check_updates"?"Running…":label}</span></button>`};
  return action("check_updates","Check for updates","refresh")+action("update","Update","update")+action("reboot","Reboot","reboot",true)+(details?"":`<a href="#/hosts/${host.id}" data-icon="info">Details</a>`);
}
function hostMaintenance(host){
  return `${host.checked_at?`<span class="update-count ${host.updates>0?"pending-updates":""}">${host.updates} updates</span>${host.security_updates>0?`<span class="security-count">${host.security_updates} security</span>`:""}`:'<span class="unknown-status">Update status unknown</span>'}${host.reboot_required?`<span class="restart-required">${buttonIcon("warning")}Restart required</span>`:!host.checked_at?'<span class="unknown-status">Reboot status unknown</span>':""}`;
}
function hostRow(host){
  const system=hostSystem(host),updates=Boolean(host.checked_at&&(host.updates>0||host.security_updates>0));
  return `<div class="row host-row ${updates?"has-updates":""} ${host.reboot_required?"needs-reboot":""}"><div class="host-row-main">${systemIcon(host)}<div><a class="host-name" href="#/hosts/${host.id}">${escapeHtml(host.name)}</a><span class="website-links">${websiteLinks(host)}</span><small>${escapeHtml(system.label)}</small><div class="host-maintenance">${hostMaintenance(host)}</div></div></div><div class="actions">${hostActions(host)}</div></div>`;
}
function hostOverview(host){
  const system=hostSystem(host),assigned=currentHostTasks.filter(task=>task.assigned),enabled=assigned.filter(task=>task.enabled),unready=assigned.filter(task=>task.state!=="suitable");
  const value=text=>escapeHtml(text??"Not recorded");
  const field=(label,text)=>`<dt>${label}</dt><dd>${value(text)}</dd>`;
  return `<div class="host-identity">${systemIcon(host)}<div><h2 id="host-title">${escapeHtml(host.name)}</h2><p>${escapeHtml(system.label)} · ${escapeHtml(host.status||(!host.checked_at?"Not checked":"Stored status"))}</p></div></div><div class="host-detail-actions actions">${hostActions(host,true)}<button data-edit-host="${host.id}">${buttonIcon("edit")}Edit host</button></div>${host.reboot_required?`<div class="restart-alert" role="status">${buttonIcon("warning")}<div><strong>Restart required</strong><p>Plan downtime before restarting. Review running services and confirm the reboot separately.</p></div></div>`:""}<div class="host-overview-metrics"><a class="host-metric ${host.checked_at&&host.updates>0?"pending-updates":""}" href="#/jobs?host_id=${host.id}&action=check_updates"><small>Available updates</small><strong>${host.checked_at?host.updates:"Unknown"}</strong><span>${host.checked_at?`${host.security_updates} security ${host.security_updates===1?"update":"updates"}`:"Run a check to populate status"}</span></a><a class="host-metric" href="#/tasks?host_id=${host.id}"><small>Task assignments</small><strong>${enabled.length} enabled</strong><span>${assigned.length} assigned · ${unready.length} need a compatibility check</span></a><div class="host-metric"><small>Last checked</small><strong id="host-last-checked">${host.checked_at?timeLabel(host.checked_at):"Never"}</strong><span class="${staleHost(host)?"status-stale":""}">${staleHost(host)?"Status missing or older than 24 hours":"Stored status is recent"}</span></div></div><div class="host-detail-grid"><section class="host-info-card"><h3>${buttonIcon("linux")}System</h3><dl>${field("Distribution",host.distribution)}${field("Version",host.distribution_version)}${field("Kernel",host.kernel)}${field("Package provider",host.package_provider==="debian_apt"?"APT (Debian / Ubuntu)":host.package_provider)}<dt>Last status time</dt><dd>${host.checked_at?jobTimeLabel(host.checked_at):"No successful check recorded"}</dd></dl></section><section class="host-info-card"><h3>${buttonIcon("connection")}Connection</h3><dl>${field("SSH address",host.address)}${field("SSH port",host.port)}${field("Automation user",host.username)}</dl><div class="actions"><button data-host="${host.id}" data-action="test_connection">${buttonIcon("connection")}Test connection</button><button data-copy-address="${host.id}" data-icon="copy">Copy address</button></div><div class="host-websites">${websiteLinks(host)}</div></section><section class="host-info-card host-recent"><div class="section-heading"><h3>${buttonIcon("jobs")}Recent jobs</h3><a href="#/jobs?host_id=${host.id}">All host jobs →</a></div>${currentHostJobs.map(job=>jobRow(job,true)).join("")||'<p class="empty">No recorded jobs for this host.</p>'}</section></div><details class="technical-details"><summary>Inventory details</summary><dl class="host-inventory">${field("Host ID",host.id)}<dt>Registered</dt><dd>${jobTimeLabel(host.created_at)}</dd><dt>Last configuration change</dt><dd>${jobTimeLabel(host.updated_at)}</dd></dl></details><div class="host-retire"><span class="sub">Remove only this inventory entry and its task assignments.</span><button class="danger" data-delete-host="${host.id}">${buttonIcon("trash")}Remove host</button></div>`;
}
function decorateIcons(){
  const groups={reboot:"[data-action=reboot]",update:"[data-action=update]",connection:"[data-action=test_connection]",refresh:"[data-action=check_updates]",trash:"[data-delete-host],[data-delete-task],#host-delete",edit:"[data-edit-host],[data-edit-task]",plus:"[data-add-host],[data-add-task]",run:"[data-task]",review:"[data-check-task]",link:"[data-assign-task]",unlink:"[data-unassign-task]",power:"[data-toggle-task]",jobs:"[data-job-log],[data-preview-log]"};
  for(const [icon,selector] of Object.entries(groups))document.querySelectorAll(selector).forEach(node=>node.dataset.icon=icon);
  document.querySelectorAll("[data-add-host],[data-add-task]").forEach(node=>{for(const child of node.childNodes)if(child.nodeType===Node.TEXT_NODE)child.textContent=child.textContent.replace(/^\+\s*/,"")});
  document.querySelectorAll("[data-icon]").forEach(node=>{if(!node.querySelector(".button-icon"))node.insertAdjacentHTML("afterbegin",buttonIcon(node.dataset.icon))});
}
function closeSelection(){element("selection-panel").hidden=true;element("selection-toggle").setAttribute("aria-expanded","false")}

function jobRow(job,detailed=false){
  const type=escapeHtml(actionName(job.type||job.action)),host=escapeHtml(job.host_name||"No host");
  const when=job.finished_at||job.started_at||job.created_at;
  const absolute=when?new Intl.DateTimeFormat(navigator.language,{dateStyle:"medium",timeStyle:"short"}).format(new Date(when)):"Not yet";
  const detail=detailed?`<small title="${escapeHtml(when||"")}">${escapeHtml(absolute)} · ${escapeHtml(job.state)}${typeof job.duration==="number"?` · ${formatDuration(job.duration)}`:""}</small>${job.reboot_required?`<small class="restart-required">${buttonIcon("warning")}Restart required</small>`:""}${job.short_error?`<small class="state-failed">${escapeHtml(job.short_error)}</small>`:""}`:`<small>${host} · ${timeLabel(when)}</small>`;
  return `<div class="row"><span><span title="${escapeHtml(job.type||job.action)}">${type}</span>${detailed?`<small>${host}</small>`:""}${detail}</span><span class="actions"><span class="state-${escapeHtml(job.state)}" title="${escapeHtml(job.error_code||job.state)}">${escapeHtml(job.state==="failed"&&job.error_code?jobError(job.error_code):job.state)}</span><button type="button" data-job-log="${job.id}">Open</button></span></div>`;
}
function staleHost(host){return !host.checked_at||Date.now()-Date.parse(host.checked_at)>86400000}
function render(){
  const route=view(),page=route.name==="hosts"&&route.id?"host":route.name==="jobs"&&route.id?"job":route.name;
  element("dashboard-layout").classList.toggle("is-dashboard",page==="dashboard");
  const hostContainer=page==="dashboard"?element("dashboard-sidebar"):element("host-list-slot"),hostSection=element("host-section");
  const focused=hostSection.parentElement!==hostContainer&&hostSection.contains(document.activeElement)?document.activeElement:null;
  if(hostSection.parentElement!==hostContainer)hostContainer.append(hostSection);
  document.querySelectorAll("[data-views]").forEach(section=>section.hidden=!section.dataset.views.split(" ").includes(page));
  if(focused)focused.focus({preventScroll:true});
  const contextId=route.id&&route.name==="hosts"?route.id:route.params.get("host_id");
  const contextHost=state.hosts.find(host=>host.id===contextId);
  document.querySelectorAll("nav a").forEach(link=>{const tab=link.dataset.tab;if(tab){link.href=tab==="hosts"?(contextId?`#/hosts/${encodeURIComponent(contextId)}`:"#/hosts"):`#/${tab}${contextId?`?host_id=${encodeURIComponent(contextId)}`:""}`}if(link.dataset.tab===route.name)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current")});
  renderSelection();
  const summary=state.dashboard;
  const latest=state.jobs.find(job=>ACTIVE_JOB_STATES.has(job.state))||summary?.last_job||state.jobs[0],failed=summary?.last_failed_job||state.jobs.find(job=>job.state==="failed");
  renderBackendStatus();
  const scopedHosts=contextHost?[contextHost]:state.hosts,checkedHosts=scopedHosts.filter(host=>host.checked_at),unchecked=scopedHosts.length-checkedHosts.length;
  const updates=checkedHosts.reduce((total,host)=>total+host.updates,0),securityCount=checkedHosts.reduce((total,host)=>total+host.security_updates,0);
  const updateStatus=checkedHosts.length?`${updates} ${unchecked?"known ":""}updates · ${securityCount} ${unchecked?"known ":""}security updates`:scopedHosts.length?"Update status unknown":"No hosts yet";
  const metrics=[["Hosts",contextHost?1:state.hosts.length,updateStatus+(unchecked?` · ${unchecked} unchecked ${unchecked===1?"host":"hosts"}`:"")],["Running jobs",contextHost?activeJobs().filter(job=>job.host_id===contextHost.id&&job.state==="running").length:summary?.running_jobs??0,"Being processed now"],["Queued jobs",contextHost?activeJobs().filter(job=>job.host_id===contextHost.id&&job.state==="queued").length:summary?.queued_jobs??0,"Waiting for a worker"]];
  element("dashboard").innerHTML=metrics.map(([label,value,detail],index)=>{const params=new URLSearchParams();if(contextId)params.set("host_id",contextId);if(index)params.set("state",index===1?"running":"queued");const href=index===0?(contextId?`#/hosts/${encodeURIComponent(contextId)}`:"#/hosts"):`#/jobs?${params}`;return `<a class="toolbar-metric" href="${href}" title="${escapeHtml(detail)}"><small>${label}</small><strong>${escapeHtml(value)}</strong><span class="sr-only">${escapeHtml(detail)}</span></a>`}).join("");
  element("job-highlights").innerHTML=highlightJob(latest,"Last job")+highlightJob(failed,"Last failed job");
  element("job-highlights").hidden=page!=="dashboard";
  element("auto-host-checks").checked=state.preferences?.enabled??true;
  element("key").textContent=state.public_key;
  const notices=[];
  const security=state.hosts.filter(h=>h.security_updates>0),reboot=state.hosts.filter(h=>h.reboot_required),stale=state.hosts.filter(staleHost);
  if(security.length)notices.push(`<a class="notice urgent" href="#/hosts?filter=security">${security.length} ${security.length===1?"host has":"hosts have"} security updates. Review affected hosts and run a regular system update.</a>`);
  if(reboot.length)notices.push(`<a class="notice restart-notice" href="#/hosts?filter=reboot">${buttonIcon("warning")}${reboot.length} ${reboot.length===1?"host needs":"hosts need"} a restart. Review and confirm separately.</a>`);
  const attention=summary?.attention_job===undefined?failed:summary.attention_job;
  if(attention)notices.push(`<a class="notice urgent" href="#/jobs/${attention.id}">Last failed job: ${escapeHtml(attention.short_error||jobError(attention.error_code||attention.action))}. Review the job.</a>`);
  if(stale.length)notices.push(`<a class="notice" href="#/hosts?filter=stale">${stale.length} ${stale.length===1?"host needs":"hosts need"} a fresh status check. No check in the last 24 hours.</a>`);
  element("notices").innerHTML=notices.join("");
  element("notices-panel").hidden=page!=="dashboard"||notices.length===0;
  element("dashboard-layout").classList.toggle("has-notices",page==="dashboard"&&notices.length>0);
  const filtered=filteredHosts();shownHosts=contextId&&page==="dashboard"?state.hosts.filter(host=>host.id===contextId):page==="dashboard"?filtered.slice(0,5):filtered;
  element("host-filter").value=route.params.get("filter")||"";
  syncSearch("host-search",route.params.get("h_search")||"");element("host-sort").value=route.params.get("h_sort")||"name";
  element("host-section").querySelector("h2").textContent=contextHost&&page==="dashboard"?"Selected host overview":"Hosts";
  element("context-host-tasks").hidden=!contextHost||page!=="tasks";element("context-host-jobs").hidden=!contextHost||page!=="jobs";
  if(contextHost){element("context-tasks-title").textContent=`Tasks for ${contextHost.name}`;element("context-jobs-title").textContent=`Recent jobs for ${contextHost.name}`}
  element("host-count").textContent=`${shownHosts.length} of ${state.hosts.length} hosts`;
  const eligible=state.hosts.filter(h=>h.checked_at&&h.updates>0&&!activeJobs().some(j=>j.host_id===h.id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action)));
  const unknown=state.hosts.filter(h=>!h.checked_at).length,active=state.hosts.filter(h=>activeJobs().some(j=>j.host_id===h.id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action))).length;
  element("update-shown").textContent=`Update all (${eligible.length})`;element("update-shown").disabled=eligible.length===0;element("update-shown").title=`${unknown} hosts have unknown update status; ${active} hosts have an update already running. Only hosts with known pending updates are included.`;element("update-skipped").textContent=unknown||active?`${unknown} unknown · ${active} already updating (skipped)`:"";
  element("hosts").innerHTML=shownHosts.map(host=>hostRow(host)).join("")||`<p class="empty">${state.hosts.length?"No hosts match these filters.":"No hosts to show."}</p>`;
  element("all-hosts").hidden=page!=="dashboard";
  element("jobs").innerHTML=currentJobPage.items.map(job=>jobRow(job,true)).join("")||'<p class="empty">No jobs yet.</p>';
  element("jobs-count").textContent=`${currentJobPage.offset+Math.min(1,currentJobPage.total)}–${Math.min(currentJobPage.offset+currentJobPage.limit,currentJobPage.total)} of ${currentJobPage.total}`;
  element("jobs-previous").disabled=currentJobPage.offset===0;
  element("jobs-next").disabled=currentJobPage.offset+currentJobPage.limit>=currentJobPage.total;
  element("job-host").innerHTML='<option value="">All hosts</option>'+state.hosts.map(h=>`<option value="${h.id}">${escapeHtml(h.name)}</option>`).join("");
  element("job-host").value=route.params.get("host_id")||"";element("job-state").value=route.params.get("state")||"";
  element("job-action").value=route.params.get("action")||"";element("job-sort").value=route.params.get("sort")||"newest";
  if(["dashboard","jobs"].includes(page))renderHistory();
  const tasks=filteredTasks().filter(task=>!contextId||!task.host_ids.length||task.host_ids.includes(contextId));syncSearch("task-search",route.params.get("t_search")||"");element("task-filter").value=route.params.get("t_filter")||"";element("task-sort").value=route.params.get("t_sort")||"name";element("task-count").textContent=`${tasks.length} of ${state.custom_tasks.length} tasks`;
  element("tasks").innerHTML=tasks.map(task=>`<div class="row"><span>${escapeHtml(task.name)}<small>${escapeHtml(task.description)} · ${task.enabled?"Enabled":"Globally disabled"} · ${task.host_ids.length} enabled host assignment(s)</small></span><span class="actions"><button data-edit-task="${task.id}">Edit</button><button data-toggle-task="${task.id}">${task.enabled?"Disable globally":"Enable globally"}</button><button class="danger" data-delete-task="${task.id}">Delete</button></span></div>`).join("")||'<p class="empty">No tasks match these filters. Use + to create one.</p>';
  if(page==="host"){element("hosts").replaceChildren();renderHostDetail(route.id)}
  else if(contextHost){renderHostDetail(contextHost.id)}
  else{element("host-info").replaceChildren();element("host-tasks").replaceChildren();element("host-jobs").replaceChildren()}
  decorateIcons();
  syncWebsiteIcons(["dashboard","hosts","host"].includes(page));
  renderSelectedJob();
  syncJobPolling();
  syncVisibleChecks();
}
function renderHostDetail(id){
  const host=state.hosts.find(h=>h.id===id);
  if(!host){element("host-info").innerHTML="<h2>Host not found</h2>";element("host-tasks").replaceChildren();element("host-jobs").replaceChildren();return}
  element("host-info").innerHTML=hostOverview(host);

  element("host-tasks").innerHTML=state.custom_tasks.map(task=>{const result=currentHostTasks.find(c=>c.task_id===task.id)||{state:"unchecked",reasons:[],assigned:false,enabled:false};const suitable=result.state==="suitable",busy=activeJobs().some(j=>j.host_id===id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action));return `<div class="host-task"><strong>${escapeHtml(task.name)}</strong> <span class="state-${result.state}">${result.state}</span><p>${result.assigned?(result.enabled?"Assigned and enabled":"Assigned and disabled"):"Not assigned"} · ${task.enabled?"Globally enabled":"Globally disabled"}</p><p>${escapeHtml(result.reasons.join("; "))||(suitable?"Prerequisites verified. Ready when assigned and enabled.":"Check prerequisites before assigning or running this task.")}</p><small>${result.checked_at?`Checked ${timeLabel(result.checked_at)} · valid up to 24 hours`:"Not checked"}</small><div class="actions"><button data-check-task="${task.id}" data-host="${id}">Check compatibility</button><button data-assign-task="${task.id}" data-host="${id}" ${!suitable&&!result.enabled?"disabled":""}>${result.enabled?"Disable for host":result.assigned?"Enable for host":"Assign to host"}</button>${result.assigned?`<button data-unassign-task="${task.id}" data-host="${id}">Unassign</button>`:""}<button data-task="${task.id}" data-host="${id}" ${!suitable||!result.enabled||!task.enabled||busy?"disabled":""}>Run task</button><button data-edit-task="${task.id}">Edit</button></div></div>`}).join("")||'<p class="empty">No tasks yet. Create a task for this host above.</p>';
  element("host-jobs").innerHTML=currentHostJobs.map(jobRow).join("")||'<p class="empty">No jobs for this host.</p>';
  element("host-all-jobs").href=`#/jobs?host_id=${id}`;
}
async function loadView(){
  const generation=++viewRequest,routeHash=location.hash,route=view(),contextId=route.name==="hosts"&&route.id?route.id:route.params.get("host_id");
  const current=()=>generation===viewRequest&&routeHash===location.hash;
  if(contextId){
    const [checks,jobs]=await Promise.all([request(`hosts/${encodeURIComponent(contextId)}/task-compatibility`),request(`jobs/page?host_id=${encodeURIComponent(contextId)}&limit=5`)]);
    if(!current())return;currentHostTasks=checks;currentHostJobs=jobs.items;
  }
  if(["dashboard","jobs"].includes(route.name)&&!route.id){
    const params=jobQuery();
    if(historyMode()==="graph"){params.delete("offset");params.delete("sort");const timeline=await request(`jobs/timeline?${params}`);if(current())currentTimeline=timeline}
    else{const page=await request(`jobs/page?${params}`);if(current())currentJobPage=page}
  }
}

function routeJobId(){const match=location.hash.match(/^#\/jobs\/([0-9a-f-]{36})$/i);return match?match[1].toLowerCase():null}
function formatDuration(value){
  if(typeof value!=="number"||!Number.isFinite(value)||value<0)return "Not available";
  const ms=Math.round(value*1000),number=(value,digits)=>new Intl.NumberFormat(navigator.language,{maximumFractionDigits:digits}).format(value);
  if(value>0&&value<0.001)return "<1 ms";
  if(ms<1000)return `${number(value*1000,1)} ms`;
  if(Math.round(value*100)/100<60)return `${number(ms/1000,2)} s`;
  const seconds=Math.round(ms/1000),minutes=Math.floor(seconds/60),hours=Math.floor(minutes/60);
  return hours?`${hours} h ${minutes%60} min ${seconds%60} s`:`${minutes} min ${seconds%60} s`;
}
function jobTimeLabel(value){
  const date=new Date(value);if(Number.isNaN(date.getTime()))return "Not recorded";
  const clock=new Intl.DateTimeFormat(navigator.language,{hour:"2-digit",minute:"2-digit",second:"2-digit",fractionalSecondDigits:3,timeZoneName:"short",hourCycle:"h23"}).format(date);
  const day=new Intl.DateTimeFormat(navigator.language,{dateStyle:"medium"}).format(date);
  return `<time datetime="${escapeHtml(value)}" title="${escapeHtml(value)}"><span class="job-clock">${escapeHtml(clock)}</span><span class="job-date">${escapeHtml(day)}</span></time>`;
}
function buttonIcon(name){
  const paths={
trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
edit:'<path d="m15 4 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 14Z"/>',
plus:'<path d="M12 4v16M4 12h16"/>',
update:'<path d="m3 7 9-4 9 4v10l-9 4-9-4ZM3 7l9 4 9-4m-9 4v10M7 5l10 4"/>',
reboot:'<path d="M4 9a8 8 0 1 1 0 7M4 3v6h6M12 6v6"/>',
power:'<path d="M12 2v9M6 5a9 9 0 1 0 12 0"/>',
warning:'<path d="m12 3 10 18H2Z"/><path d="M12 9v5m0 3v1"/>',
info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
filter:'<path d="M3 4h18l-7 8v7l-4 2v-9Z"/>',
close:'<path d="m6 6 12 12M18 6 6 18"/>',
dashboard:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
hosts:'<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6h1m-1 11h1m5-11h5m-5 11h5"/>',
tasks:'<path d="m3 6 2 2 4-4M12 6h9M3 14l2 2 4-4m3 2h9M3 21h18"/>',
jobs:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8m-8 5h8m-8 5h5"/>',
connection:'<path d="M4 5h16v12H4ZM8 21h8m-4-4v4M7 9l3 3-3 3m6-1h4"/>',
link:'<path d="m10 13 4-4m-6 7-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0m2 1 2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0"/>',
unlink:'<path d="m4 4 16 16M10 5l2-2a4 4 0 0 1 6 6l-2 2M8 13l-2 2a4 4 0 0 0 6 6l2-2"/>',
linux:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3m6 0h4"/>',
debian:'<path d="M19 8c-2-6-12-6-14 1-3 9 10 14 15 7 4-6-3-12-7-8-4 4 2 8 4 4M7 19l-2 3"/>',
ubuntu:'<circle cx="12" cy="12" r="6"/><circle cx="12" cy="3" r="2"/><circle cx="4" cy="17" r="2"/><circle cx="20" cy="17" r="2"/><path d="M12 5v3m-6 8 3-2m9 2-3-2"/>',
proxmox:'<path d="m3 4 9 8-9 8m18-16-9 8 9 8M8 4l4 4 4-4M8 20l4-4 4 4"/>',
copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',refresh:'<path d="M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 13-3l2 2M4 17l2 2a8 8 0 0 0 13-3"/>',run:'<path d="m8 5 11 7-11 7Z"/>',review:'<path d="m5 12 4 4L19 6"/>'};
  return `<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name]||""}</svg>`;
}
function jobRerunReason(job){
  if(ACTIVE_JOB_STATES.has(job.state))return "Wait for this job to finish.";
  if(!state.hosts.some(host=>host.id===job.host_id))return "The original host is no longer available.";
  if(activeJobs().some(item=>item.host_id===job.host_id&&ACTIVE_JOB_STATES.has(item.state)&&MUTATING_JOB_ACTIONS.has(item.action)))return "The host already has work in progress.";
  if(job.action==="custom_task"){
    const task=state.custom_tasks.find(item=>item.id===job.custom_task_id);
    if(!task?.enabled||!task.host_ids.includes(job.host_id))return "Review this task's activation and host assignment first.";
  }else if(!["test_connection","check_updates","update","reboot"].includes(job.action))return "This job type cannot be repeated here.";
  return "";
}
function renderSelectedJob(){
  const detail=element("job-detail");detail.hidden=!selectedJobId;
  if(!selectedJobId)return;
  const job=selectedJob;
  if(!job){element("review-job").hidden=true;element("job-rerun-note").hidden=true;element("job-metadata").innerHTML=`<h2>${selectedJobError?"Job unavailable":"Loading job…"}</h2><p class="${selectedJobError?"error":"sub"}">${escapeHtml(selectedJobError||"Loading job…")}</p>`;element("log").textContent="";element("job-log-note").textContent=selectedJobError?"Job output is unavailable.":"Loading job…";for(const id of ["rerun-job","copy-job-log","download-job-log"])element(id).disabled=true;return}
  const task=state.custom_tasks.find(item=>item.id===job.custom_task_id),host=state.hosts.find(item=>item.id===job.host_id);
  const title=task?.name||actionName(job.action),active=ACTIVE_JOB_STATES.has(job.state);
  const outcome=job.state==="success"?"Completed successfully":job.state==="failed"?(job.reviewed_at?"Reviewed failure":job.needs_review?"This job needs attention":"Failure resolved by a later run"):job.state==="cancelled"?"Job cancelled":job.state==="running"?"Work is in progress":"Waiting for a worker";
  const explanation=job.short_error||(job.error_code?jobError(job.error_code):job.state==="success"?"The command completed. Check the output below for its results.":job.state==="running"?"Status updates automatically while this job is active. Output is available after completion.":job.state==="queued"?"The backend will start this job when the host and a worker are available.":job.state==="cancelled"?"This job stopped before completing.":"Inspect the redacted log before deciding what to do next.");
  const elapsed=job.duration??(active&&job.started_at?Math.max(0,(Date.now()-Date.parse(job.started_at))/1000):null);
  const duration=elapsed===null?(active?"Not started":"Not recorded"):formatDuration(elapsed);
  const steps=[["Queued",job.created_at],["Started",job.started_at],[active?"Finished":job.state==="failed"?"Failed":job.state==="cancelled"?"Cancelled":"Finished",job.finished_at]];
  const description=[outcome,job.state==="failed"?explanation:""].filter(Boolean).join(". ");
  element("job-metadata").innerHTML=`<div class="job-hero"><div><h2>${escapeHtml(title)} <span class="job-title-host">· ${escapeHtml(job.host_name||"Host unavailable")}</span></h2><p id="job-result" class="job-description state-${job.state}" role="status">${escapeHtml(description)}${job.reboot_required?`<span class="job-restart-required">${buttonIcon("warning")}Restart required · review and confirm on the host</span>`:""}${selectedJobError?`<span class="error"> · Could not refresh: ${escapeHtml(selectedJobError)}</span>`:""}</p></div><span id="job-state-badge" class="job-state-badge state-${job.state}">${escapeHtml(job.state)}</span></div><div class="job-facts"><div><small>${active&&job.started_at?"Running time":"Duration"}</small><strong id="job-duration">${duration}</strong></div><div><small>Exit code</small><strong>${job.exit_code??(active?"Pending":"Not recorded")}</strong></div></div><ol id="job-timeline" class="job-timeline">${steps.map(([label,time])=>`<li class="${time?"complete":"pending"}"><strong>${label}</strong><span>${time?jobTimeLabel(time):active?"Not yet":"Not recorded"}</span></li>`).join("")}</ol><div class="job-related">${host?`<a id="job-host-link" href="#/hosts/${host.id}">Open host →</a><a href="#/jobs?host_id=${host.id}">Host job history →</a>`:'<span class="sub">Original host no longer available</span>'}${job.custom_task_id&&host?`<a href="#/tasks?host_id=${host.id}">Review host tasks →</a>`:""}</div><details class="technical-details"><summary>Technical details and identifiers</summary><dl class="job-identifiers"><dt>Job ID</dt><dd class="mono">${escapeHtml(job.job_id||job.id)}</dd><dt>Action</dt><dd>${escapeHtml(actionName(job.action))}</dd><dt>Error code</dt><dd>${escapeHtml(job.error_code||"None")}</dd>${job.reviewed_at?`<dt>Reviewed</dt><dd>${jobTimeLabel(job.reviewed_at)}</dd>`:""}</dl><pre>${escapeHtml(JSON.stringify(job,null,2))}</pre></details>`;
  element("review-job").hidden=!(job.state==="failed"&&job.needs_review&&!job.reviewed_at);element("review-job").dataset.reviewJob=job.id;
  const reason=jobRerunReason(job);element("rerun-job").disabled=jobRerunPending||Boolean(reason);element("rerun-job").title=reason||"Confirm a new run with the same action and host";element("job-rerun-note").hidden=!reason;element("job-rerun-note").textContent=reason;
  for(const id of ["copy-job-log","download-job-log"])element(id).disabled=selectedJobLog===null;
  const note=element("job-log-note");note.className=selectedJobLogError?"error":"sub";
  note.textContent=selectedJobLogError?`Could not load output: ${selectedJobLogError}. Use Refresh job to try again.`:selectedJobLog===null?(active?"Output will appear when the job finishes.":job.log_available?"Loading redacted output…":"No output was recorded for this job."):selectedJobTruncated?"Output was truncated by the backend. Copy and download include only this available redacted output.":selectedJobLog===""?"This job recorded no output.":`${selectedJobLog.split("\n").length} ${selectedJobLog.includes("\n")?"lines":"line"} · Redacted by the backend`;
  renderJobLog();
}
function renderJobLog(reset=false){
  const log=element("log"),output=selectedJobLog??"",query=element("job-log-search").value.toLocaleLowerCase();
  const key=JSON.stringify([selectedJobId,output,query]);
  if(!reset&&key===renderedJobLog)return;
  renderedJobLog=key;jobLogMatch=0;
  if(!query){log.textContent=output;jobLogMatches=[];updateLogMatch();return}
  const lower=output.toLocaleLowerCase();let cursor=0,html="",index=0;
  while(index<500){const found=lower.indexOf(query,cursor);if(found<0)break;html+=escapeHtml(output.slice(cursor,found))+`<mark>${escapeHtml(output.slice(found,found+query.length))}</mark>`;cursor=found+query.length;index++}
  log.innerHTML=html+escapeHtml(output.slice(cursor));jobLogMatches=[...log.querySelectorAll("mark")];updateLogMatch();
}
function updateLogMatch(scroll=false){
  const count=jobLogMatches.length;jobLogMatches.forEach((mark,index)=>mark.classList.toggle("current-match",index===jobLogMatch));
  element("job-log-matches").textContent=element("job-log-search").value?count?`${jobLogMatch+1} of ${count}${count===500?"+":""} ${count===1?"match":"matches"}`:"No matches":"";
  element("job-log-next").disabled=!count;element("job-log-previous").disabled=!count;
  if(scroll&&count)jobLogMatches[jobLogMatch].scrollIntoView({block:"nearest",inline:"nearest"});
}
async function loadJobRoute(force=false,refreshLog=true){
  const jobId=routeJobId();
  if(!jobId){jobDetailRequest++;selectedJobId=null;selectedJob=null;selectedJobLog=null;renderSelectedJob();return}
  const changed=selectedJobId!==jobId;
  if(!force&&!changed&&selectedJob)return;
  const generation=++jobDetailRequest;selectedJobId=jobId;
  if(changed){selectedJob=null;selectedJobLog=null;selectedJobTruncated=false;selectedJobLogError=null;selectedJobError=null;element("job-log-search").value="";jobLogMatches=[];jobLogMatch=0;updateLogMatch();renderedJobLog=null}
  renderSelectedJob();
  const current=()=>generation===jobDetailRequest&&routeJobId()===jobId;
  try{
    const job=await request(`jobs/${jobId}`);if(!current())return;
    selectedJob=job;selectedJobError=null;state.unavailable=false;renderBackendStatus();state.jobs=[job,...state.jobs.filter(item=>item.id!==job.id)];renderSelectedJob();renderSelection();syncJobPolling();
    if(job.log_available&&(refreshLog||selectedJobLog===null)){
      try{const log=await request(`jobs/${jobId}/log`);if(!current())return;selectedJobLog=log.output;selectedJobTruncated=log.truncated;selectedJobLogError=null}
      catch(error){if(!current())return;selectedJobLogError=error.message}
    }
    if(current())renderSelectedJob();
  }catch(error){if(!current())return;selectedJobError=error.message;renderSelectedJob();throw error}
}
async function rerunJob(button){
  const job=selectedJob;if(!job||jobRerunPending||jobRerunReason(job))return;
  jobRerunPending=true;renderSelectedJob();
  try{
  if(job.action==="custom_task"){
    const checks=await request(`hosts/${job.host_id}/task-compatibility`),check=checks.find(item=>item.task_id===job.custom_task_id);
    if(!check?.enabled||!check.assigned||check.state!=="suitable"){message("Review task prerequisites and activation before running again.","error",{href:`#/tasks?host_id=${job.host_id}`,label:"Review task"});return}
  }
  const host=state.hosts.find(item=>item.id===job.host_id),title=state.custom_tasks.find(item=>item.id===job.custom_task_id)?.name||actionName(job.action);
  if(!await confirmAction("Run this job again?",`Create a new ${title} job for ${host.name}? The original job and its log stay in history.${job.action==="custom_task"?" The current task definition and permissions apply.":""}`,[host.name],"Run again"))return;
  await mutate(button,job.action==="custom_task"?customTaskPath(job.host_id,job.custom_task_id):hostActionPath(job.host_id,job.action),"POST",undefined,"New job queued");
  }finally{jobRerunPending=false;renderSelectedJob()}
}
function downloadJobLog(){
  if(selectedJobLog===null||!selectedJobId)return;
  const url=URL.createObjectURL(new Blob([selectedJobLog],{type:"text/plain;charset=utf-8"})),link=document.createElement("a");
  link.href=url;link.download=`commander-job-${selectedJobId}.txt`;link.click();setTimeout(()=>URL.revokeObjectURL(url),0);
}

async function mutate(button,path,method="POST",body,success="Done"){return run(button,async()=>{const result=await request(path,{method,body});const job=result?.id&&result?.state&&result?.action?result:null;if(job){state.jobs=[job,...state.jobs.filter(item=>item.id!==job.id)];render()}await refreshDashboard();return job?{notification:{href:`#/jobs/${job.id}`,label:"Open job"}}:null},success)}
function hostActionPath(hostId,action){return `hosts/${hostId}/actions/${action}`}
function customTaskPath(hostId,taskId){return `hosts/${hostId}/tasks/${taskId}`}

let setupCommand="";
let setupRequest=0;
function hostStep(step){
  for(const [index,id] of ["host-system-step","host-preparation","host-connection-step"].entries())element(id).hidden=index!==step;
  element("host-step-label").textContent=editingHost&&step===2?"Edit connection":"Step "+(step+1)+" of 3 · "+["Host system","User setup","SSH connection"][step];
  element(step===1?"setup-user-fields":"connection-user-fields").appendChild(element("ssh-settings"));
  element("host-connection-back").hidden=Boolean(editingHost);
  element("host-edit-actions").hidden=!editingHost||step!==2;
  element("host-form-error").textContent="";
  if(step===1)generateSetup();else{setupRequest++;setupCommand="";element("copy-setup").disabled=true}
}
function openHostDialog(host=null){
  editingHost=host;element("host-form").reset();element("host-name").value=host?.name||"";element("host-address").value=host?.address||"";element("host-user").value=host?.username||"automation";element("host-port").value=host?.port||22;element("host-websites").value=(host?.websites||[]).map(site=>`${site.name} | ${site.url}${site.icon_url?" | "+site.icon_url:""}`).join("\n");
  element("setup-system").value=host?.distribution?.toLowerCase()==="ubuntu"?"ubuntu":"debian";element("setup-mode").value=host?"update":"create";
  element("host-delete").dataset.deleteHost=host?.id||"";element("host-retry-icons").hidden=!host;element("website-icon-status").textContent="";
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

async function addHost(event){event.preventDefault();const name=element("host-name").value.trim(),address=element("host-address").value.trim(),username=element("host-user").value.trim(),port=Number(element("host-port").value);if(!validHost({name,address,username,port})){element("host-form-error").textContent="Complete all fields with a valid SSH address, user and port.";return}let websites;try{websites=element("host-websites").value.split("\n").filter(line=>line.trim()).map(line=>{const parts=line.split("|").map(value=>value.trim());if(parts.length<2||parts.length>3||!parts[0])throw Error("Use name | website URL | optional icon URL for each website.");const [name,address,icon]=parts,url=new URL(address),iconUrl=icon?new URL(icon):null;for(const value of [url,iconUrl])if(value&&(!["http:","https:"].includes(value.protocol)||value.username||value.password))throw Error("Websites and icons require HTTP(S) URLs without credentials.");return {name,url:url.href,...(iconUrl?{icon_url:iconUrl.href}:{})}})}catch(error){element("host-form-error").textContent=error.message;return}const result=await mutate(event.submitter,editingHost?`hosts/${editingHost.id}`:"hosts",editingHost?"PATCH":"POST",{name,address,username,port,websites},editingHost?"Host updated":"Host added");if(result){element("host-dialog").close();element("host-form").reset()}else element("host-form-error").textContent=element("message").textContent}
function validHost(h){return typeof h.name==="string"&&h.name.trim().length>0&&h.name.length<=100&&typeof h.address==="string"&&/^[A-Za-z0-9][A-Za-z0-9.:-]{0,254}$/.test(h.address)&&typeof h.username==="string"&&/^[a-z_][a-z0-9_-]{0,31}$/.test(h.username)&&Number.isInteger(h.port)&&h.port>0&&h.port<65536}
function importHost(event){const text=event.clipboardData?.getData("text")||"";if(!text.includes("HLC_HOST_BEGIN")&&!text.trim().startsWith("{"))return;event.preventDefault();try{if(text.length>16384)throw Error("Import is too large");const match=text.match(/HLC_HOST_BEGIN\s*([\s\S]*?)\s*HLC_HOST_END/);const data=JSON.parse(match?match[1]:text);if(data.format!=="homelab-commander-host"||data.version!==1)throw Error("Unsupported host import format or version");if(!Array.isArray(data.addresses)||data.addresses.length===0||data.addresses.length>64||data.addresses.some(address=>!validHost({...data,address})))throw Error("Invalid host import fields");element("host-name").value=data.name;element("host-user").value=data.username;element("host-port").value=data.port;element("import-address").replaceChildren(...data.addresses.map(address=>new Option(address,address)));element("address-choice").hidden=data.addresses.length===1;element("host-address").value=data.addresses.length===1?data.addresses[0]:"";if(data.addresses.length>1)element("import-address").prepend(new Option("Choose a reachable address","",true,true));element("host-form-error").textContent=data.addresses.length>1?"Choose one of the reported addresses before saving.":""}catch(error){element("host-form-error").textContent=error.message}}
function openTaskDialog(task=null){editingTask=task;taskTargetHost=view().name==="hosts"&&view().id?view().id:view().params.get("host_id");element("task-form").reset();element("task-name").value=task?.name||"";element("task-description").value=task?.description||"";element("task-mode").value=task?.mode||"command";element("task-argv").value=task?.argv?JSON.stringify(task.argv):"";element("task-shell").value=task?.shell_command||"";for(const field of ["distributions","versions","programs","packages"])element(`task-${field}`).value=(task?.requirements?.[field]||[]).join(", ");element("task-sudo").checked=task?.requirements?.requires_sudo||false;element("task-enabled").checked=task?.enabled??true;element("task-form-error").textContent="";element("task-target").textContent=taskTargetHost?"After saving, check compatibility and assign this task to the current host.":"After saving, open a host to check compatibility and assign this task.";element("task-dialog-title").textContent=task?"Edit task":"Create task";element("task-dialog").showModal()}
async function addTask(event){event.preventDefault();try{const mode=element("task-mode").value;const requirements={requires_sudo:element("task-sudo").checked};for(const field of ["distributions","versions","programs","packages"])requirements[field]=element(`task-${field}`).value.split(",").map(v=>v.trim()).filter(Boolean);const body={name:element("task-name").value.trim(),description:element("task-description").value.trim(),mode,argv:mode==="command"?JSON.parse(element("task-argv").value):null,shell_command:mode==="shell"?element("task-shell").value:null,enabled:element("task-enabled").checked,requirements};if(mode==="command"&&(!Array.isArray(body.argv)||!body.argv.length||body.argv.some(v=>typeof v!=="string"||!v)))throw Error("Enter a non-empty JSON string array.");if(await mutate(event.submitter,editingTask?`custom-tasks/${editingTask.id}`:"custom-tasks",editingTask?"PATCH":"POST",body,editingTask?"Task updated":"Task added"))element("task-dialog").close();else element("task-form-error").textContent=element("message").textContent}catch(error){element("task-form-error").textContent=error.message}}
async function copyText(value){if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);return}const area=document.createElement("textarea");area.value=value;area.setAttribute("readonly","");area.style.position="fixed";area.style.opacity="0";(document.querySelector("dialog[open]")||document.body).appendChild(area);area.select();const copied=document.execCommand("copy");area.remove();if(!copied)throw Error("Clipboard unavailable. Select and copy the displayed text manually.")}
async function copySetup(button){if(!setupCommand||button.disabled)return;const copied=await run(button,()=>copyText(setupCommand),"Setup command copied");element("setup-status").textContent=copied?"Script copied. Run it on the target as root.":element("message").textContent;updateSetupConsent()}


async function copyKey(button){if(!state.public_key){message("Connect before copying the public key.","error");return}await run(button,()=>copyText(state.public_key),"Copied")}

async function removeHost(button,hostId){
  const host=state.hosts.find(value=>value.id===hostId);if(!host)return;
  if(!await confirmAction("Remove host?",`Remove ${host.name} from Commander? This removes its inventory entry and task assignments. It does not revoke SSH access or remove the user on the target.`,[host.name],"Remove host"))return;
  const success=await run(button,async()=>{
    await request(`hosts/${hostId}`,{method:"DELETE"});
    if(element("host-dialog").open)element("host-dialog").close();
    // Leave the deleted detail route before any refresh can request it again.
    location.hash="/hosts";
    await refreshDashboard();
  },"Host removed");
  if(!success&&element("host-dialog").open)element("host-form-error").textContent=element("message").textContent;
}
async function hostClick(event){const button=event.target.closest("button");if(!button)return;const hostId=button.dataset.host;if(button.dataset.action&&hostId){const action=button.dataset.action;if(["update","reboot"].includes(action)&&!await confirmAction(action==="reboot"?"Restart host?":"Run system update?",`${action==="reboot"?"Restart":"Run regular system updates on"} ${state.hosts.find(host=>host.id===hostId)?.name||"this host"}?`,[],action==="reboot"?"Restart":"Queue update"))return;await mutate(button,hostActionPath(hostId,action),"POST",undefined,`${action.replace("_"," ")} queued`);return}if(button.dataset.deleteHost){await removeHost(button,button.dataset.deleteHost);return}if(button.dataset.editHost)openHostDialog(state.hosts.find(value=>value.id===button.dataset.editHost))}
async function taskClick(event){const button=event.target.closest("button");if(!button)return;const host=button.dataset.host;if(button.dataset.task&&host){if(await confirmAction("Run custom task?",`Run ${state.custom_tasks.find(task=>task.id===button.dataset.task)?.name||"this task"} on ${state.hosts.find(item=>item.id===host)?.name||"this host"}? Prerequisites will be checked again.`,[],"Run task"))await mutate(button,customTaskPath(host,button.dataset.task),"POST",undefined,"Task queued");return}if(button.dataset.checkTask){await run(button,async()=>{await request(`hosts/${host}/tasks/${button.dataset.checkTask}/check`,{method:"POST"});await loadView();render()},"Compatibility checked");return}if(button.dataset.assignTask){const result=currentHostTasks.find(c=>c.task_id===button.dataset.assignTask);await mutate(button,`hosts/${host}/tasks/${button.dataset.assignTask}/assignment`,"PUT",{enabled:!result?.enabled},"Assignment updated");return}if(button.dataset.unassignTask){await mutate(button,`hosts/${host}/tasks/${button.dataset.unassignTask}/assignment`,"DELETE",undefined,"Task unassigned");return}if(button.dataset.toggleTask){const task=state.custom_tasks.find(t=>t.id===button.dataset.toggleTask);await mutate(button,`custom-tasks/${task.id}`,"PATCH",{enabled:!task.enabled},"Task updated");return}if(button.dataset.deleteTask){if(await confirmAction("Delete task?",`Delete ${state.custom_tasks.find(task=>task.id===button.dataset.deleteTask)?.name||"this task"}?`,[],"Delete task"))await mutate(button,`custom-tasks/${button.dataset.deleteTask}`,"DELETE",undefined,"Task deleted");return}if(button.dataset.editTask)openTaskDialog(state.custom_tasks.find(value=>value.id===button.dataset.editTask))}
async function reviewJob(button){await run(button,async()=>{await request(`jobs/${button.dataset.reviewJob}/review`,{method:"POST"});await refreshDashboard();await loadJobRoute(true)},"Job marked as reviewed")}
async function jobClick(event){const button=event.target.closest("button[data-job-log]");if(!button)return;const target=`#/jobs/${button.dataset.jobLog}`;if(location.hash===target)await run(button,()=>loadJobRoute(true),"Job loaded");else location.hash=target}

async function previewLog(button){
  const id=button.dataset.previewLog;element("log-preview-output").textContent="Loading log…";element("log-preview-link").href=`#/jobs/${id}`;element("log-preview").showModal();
  try{const log=await request(`jobs/${id}/log`);element("log-preview-output").textContent=log.output.slice(0,3000)+(log.output.length>3000||log.truncated?"\n… Open the full job for more.":"")||"No output recorded."}catch(error){element("log-preview-output").textContent=error.message}
}
document.addEventListener("DOMContentLoaded",()=>{
  decorateIcons();
  element("connect-form").addEventListener("submit",connect);element("disconnect").addEventListener("click",disconnect);
  element("host-form").addEventListener("submit",addHost);element("task-form").addEventListener("submit",addTask);
  element("host-retry-icons").addEventListener("click",()=>{if(!editingHost)return;clearWebsiteIcons(editingHost.id);render();element("website-icon-status").textContent="Retrying saved website icons. Unsaved changes are not used."});
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
  const applyJobFilters=()=>{const values={offset:null,state:element("job-state").value,host_id:element("job-host").value,action:element("job-action").value,sort:element("job-sort").value,range:element("history-range").value};if(values.range==="custom"){const start=new Date(element("history-start").value),end=new Date(element("history-end").value);if(!Number.isFinite(+start)||!Number.isFinite(+end)||start>=end||end-start>366*86400000){message("Choose a valid period of at most 366 days.","error");return}values.start=start.toISOString();values.end=end.toISOString()}else{values.start=null;values.end=null}if(values.range==="all")values.display="table";updateRoute(values)};
  element("job-filters").addEventListener("submit",event=>{event.preventDefault();applyJobFilters()});
  for(const id of ["history-start","history-end"])element(id).addEventListener("change",()=>{if(element("history-start").value&&element("history-end").value)applyJobFilters()});
  for(const id of ["job-state","job-host","job-action","job-sort"])element(id).addEventListener("change",applyJobFilters);
  element("history-range").addEventListener("change",()=>{if(element("history-range").value==="custom"){element("history-custom").hidden=false;if(element("history-start").value&&element("history-end").value)applyJobFilters();element("history-start").focus()}else applyJobFilters()});
  element("history-toggle").addEventListener("click",()=>updateRoute({display:historyMode()==="graph"?"table":"graph",offset:null,...(element("history-range").value==="all"?{range:"7d"}:{})}));
  element("history-reset").addEventListener("click",()=>updateRoute({start:null,end:null,state:null,host_id:null,action:null,sort:null,offset:null,range:view().name==="jobs"?"all":"7d"}));
  const pageJobs=delta=>updateRoute({offset:Math.max(0,currentJobPage.offset+delta*currentJobPage.limit)});element("jobs-previous").addEventListener("click",()=>pageJobs(-1));element("jobs-next").addEventListener("click",()=>pageJobs(1));
  const hostControls=()=>updateRoute({filter:element("host-filter").value,h_search:element("host-search").value,h_sort:element("host-sort").value});
  element("host-controls").addEventListener("submit",event=>{event.preventDefault();hostControls()});for(const id of ["host-filter","host-search","host-sort"])element(id).addEventListener("change",hostControls);
  const taskControls=()=>updateRoute({t_filter:element("task-filter").value,t_search:element("task-search").value,t_sort:element("task-sort").value});
  element("task-controls").addEventListener("submit",event=>{event.preventDefault();taskControls()});for(const id of ["task-filter","task-search","task-sort"])element(id).addEventListener("change",taskControls);
  element("update-shown").addEventListener("click",event=>updateShown(event.currentTarget));
  element("refresh-job").addEventListener("click",event=>run(event.currentTarget,()=>loadJobRoute(true),"Job refreshed"));
  element("copy-job-link").addEventListener("click",event=>run(event.currentTarget,()=>copyText(new URL(`#/jobs/${selectedJobId}`,location.href).href),"Job link copied"));
  element("copy-job-log").addEventListener("click",event=>run(event.currentTarget,()=>copyText(selectedJobLog||""),"Redacted log copied"));
  element("download-job-log").addEventListener("click",downloadJobLog);
  element("rerun-job").addEventListener("click",event=>rerunJob(event.currentTarget).catch(error=>message(error.message,"error")));
  element("job-log-search").addEventListener("input",()=>renderJobLog(true));
  for(const [id,delta] of [["job-log-next",1],["job-log-previous",-1]])element(id).addEventListener("click",()=>{jobLogMatch=(jobLogMatch+delta+jobLogMatches.length)%jobLogMatches.length;updateLogMatch(true)});
  element("job-log-wrap").addEventListener("change",event=>element("log").classList.toggle("wrap-log",event.target.checked));
  element("selection-toggle").addEventListener("click",()=>{const panel=element("selection-panel");panel.hidden=!panel.hidden;element("selection-toggle").setAttribute("aria-expanded",String(!panel.hidden))});
  document.addEventListener("pointerdown",event=>{if(!event.target.closest("#host-context"))closeSelection()});
  element("host-context").addEventListener("keydown",event=>{if(event.key==="Escape"){closeSelection();element("selection-toggle").focus()}});
  document.addEventListener("click",event=>{const button=event.target.closest("[data-copy-address]");if(button){const host=state.hosts.find(item=>item.id===button.dataset.copyAddress);if(host)run(button,()=>copyText(host.address),"Host address copied")}});
  element("reset-view").addEventListener("click",resetView);
  element("message-dismiss").addEventListener("click",()=>message(""));
  element("refresh").addEventListener("click",event=>run(event.currentTarget,refreshDashboard,"Data refreshed"));
  element("history").addEventListener("pointerover",event=>{if(event.pointerType!=="touch")showTimelinePoint(event.target)});element("history").addEventListener("focusin",event=>showTimelinePoint(event.target));
  element("history").addEventListener("click",event=>{if(event.pointerType!=="touch")return;const anchor=event.target.closest("[data-point]");if(anchor&&currentTimeline.points[Number(anchor.dataset.point)]?.total>1){event.preventDefault();showTimelinePoint(anchor)}});
  element("history-chart").addEventListener("pointerleave",closeTimelinePoint);
  document.addEventListener("pointerdown",event=>{if(!event.target.closest("#history-chart"))closeTimelinePoint()});element("history-chart").addEventListener("keydown",event=>{if(event.key==="Escape")closeTimelinePoint()});
  element("auto-host-checks").addEventListener("change",event=>{stopVisibleChecks();state.preferences={enabled:event.target.checked};return run(event.target,async()=>{state.preferences=await request("preferences/host-checks",{method:"PATCH",body:{enabled:event.target.checked}});stopVisibleChecks();render()},"Host check preference saved")});
  document.addEventListener("visibilitychange",syncVisibleChecks);
  element("log-preview-link").addEventListener("click",()=>element("log-preview").close());
  window.addEventListener("hashchange",()=>{if(connected)run(null,async()=>{await loadView();render();await loadJobRoute()})});initialize();
});
window.addEventListener("pagehide",()=>{stopJobPolling();stopVisibleChecks()});
