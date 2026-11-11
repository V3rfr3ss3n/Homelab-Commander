
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
function message(value,kind=""){const target=element("message");target.textContent=value;target.className=kind;target.hidden=!value;target.setAttribute("role",kind==="error"?"alert":"status")}
function confirmAction(title,description,targets=[],confirmLabel="Confirm"){return new Promise(resolve=>{const dialog=element("confirm-dialog"),accept=element("confirm-accept"),cancel=element("confirm-cancel");element("confirm-title").textContent=title;element("confirm-description").textContent=description;element("confirm-targets").replaceChildren(...targets.map(value=>{const item=document.createElement("div");item.textContent=value;return item}));accept.textContent=confirmLabel;const finish=value=>{dialog.close();accept.removeEventListener("click",yes);cancel.removeEventListener("click",no);dialog.removeEventListener("cancel",escape);resolve(value)};const yes=()=>finish(true),no=()=>finish(false),escape=event=>{event.preventDefault();finish(false)};accept.addEventListener("click",yes);cancel.addEventListener("click",no);dialog.addEventListener("cancel",escape);dialog.showModal();cancel.focus()})}
function setBusy(button,busy){if(button)button.disabled=busy}
function backendUnavailable(){state.unavailable=true;element("connection-hint").textContent="Backend unavailable. Displayed data may be out of date.";renderBackendStatus()}
function jobError(errorCode){const labels={apt_lock_unavailable:"APT is locked by another process",check_updates_apt_cache_refresh_failed:"Check updates failed during APT cache refresh",check_updates_facts_failed:"Check updates failed while collecting system facts",check_updates_package_list_failed:"Check updates failed while listing packages",check_updates_reboot_status_failed:"Check updates failed while reading reboot status",invalid_ansible_output:"Ansible returned an invalid structured result",python_interpreter_unavailable:"Python 3 is not available on the host",reboot_failed:"Reboot failed",sudo_unavailable:"Non-interactive sudo is not available",test_connection_failed:"SSH connection test failed",test_connection_facts_failed:"Connection test failed while collecting system facts",update_packages_failed:"Package update failed"};return labels[errorCode]||errorCode.replaceAll("_"," ")}
function hasActiveJobs(){return (state.dashboard?.running_jobs||state.dashboard?.queued_jobs||0)>0||state.jobs.some(job=>ACTIVE_JOB_STATES.has(job.state))}
function stopJobPolling(){if(jobPollTimer!==null)window.clearTimeout(jobPollTimer);jobPollTimer=null;jobPollFailureCount=0}
function scheduleJobPolling(delay=ACTIVE_JOB_POLL_INTERVAL_MS){if(!connected||!hasActiveJobs()||jobPollTimer!==null||jobPollInFlight)return;jobPollTimer=window.setTimeout(pollJobs,delay)}
function syncJobPolling(){if(connected&&hasActiveJobs())scheduleJobPolling();else stopJobPolling()}
function clearProtectedData(){clearWebsiteIcons();stopJobPolling();stopVisibleChecks();document.querySelectorAll("dialog[open]").forEach(d=>d.close());state={info:null,hosts:[],custom_tasks:[],jobs:[],public_key:""};selectedJobId=null;selectedJobLog=null;for(const id of ["backend-status","job-highlights","dashboard","key","hosts","tasks","jobs","job-metadata","log","notices","history","activity","host-info","host-tasks","host-jobs"])element(id).replaceChildren();element("job-detail").hidden=true;element("protected-content").hidden=true;element("connect-placeholder").hidden=false}
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

function renderBackendStatus(){const online=Boolean(state.info&&!state.unavailable);element("backend-status").className=`backend-status ${online?"online":"offline"}`;element("backend-status").textContent=online?"Backend online":"Backend unavailable"}
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
function renderHistory(){
  const graph=historyMode()==="graph",period=historyPeriod(),params=view().params;
  element("history-toggle").textContent=graph?"▤":"⌁";element("history-toggle").setAttribute("aria-label",graph?"Show table":"Show graph");element("history-toggle").title=graph?"Show table":"Show graph";
  element("history-chart").hidden=!graph;element("jobs-section").hidden=graph;element("history-popover").hidden=true;
  element("history-range").value=params.get("range")||(view().name==="jobs"?"all":"7d");
  element("history-custom").hidden=element("history-range").value!=="custom";
  if(period){element("history-start").value=localDateInput(period.start);element("history-end").value=localDateInput(period.end)}
  const dateFormat=new Intl.DateTimeFormat(navigator.language,{dateStyle:"medium",timeStyle:"short"});
  element("history-period").textContent=period?`${dateFormat.format(new Date(period.start))} – ${dateFormat.format(new Date(period.end))}`:"All stored jobs";
  const historyCount=graph?currentTimeline.total:currentJobPage.total;
  element("history-total").textContent=`${historyCount} ${historyCount===1?"job":"jobs"}`;
  if(!graph)return;
  const width=900,height=285,left=42,right=24,top=24,bottom=40,plotHeight=height-top-bottom,points=currentTimeline.points;
  const start=Date.parse(currentTimeline.start),end=Date.parse(currentTimeline.end),max=Math.max(1,...points.map(p=>p.total));
  const x=time=>left+(Date.parse(time)-start)/(end-start)*(width-left-right),y=count=>top+plotHeight-count/max*plotHeight;
  const grid=Array.from({length:5},(_,i)=>{const value=max*i/4;return `<line class="graph-grid" x1="${left}" x2="${width-right}" y1="${y(value)}" y2="${y(value)}"/><text x="${left-8}" y="${y(value)+4}" text-anchor="end">${Number.isInteger(value)?value:value.toFixed(1)}</text>`}).join("");
  const series=["success","failed","cancelled","running","queued"].map(status=>`<g class="graph-series ${status}"><path d="${timelinePath(points,status,x,y)}"/></g>`).join("");
  const markers=points.map((point,index)=>{const single=point.total===1?point.jobs[0]:null;const dominant=Object.entries(point.counts).filter(([,count])=>count>0).sort((left,right)=>right[1]-left[1])[0];const anchorState=single?.state||dominant?.[0]||"success",anchorCount=single?1:dominant?.[1]||0,status=single?.state||anchorState,highlight=point.jobs.some(j=>j.id===state.dashboard?.last_job?.id||j.id===state.dashboard?.last_failed_job?.id);const distribution=Object.entries(point.counts).filter(([,count])=>count>0).map(([name,count])=>`${name} ${count}`).join(", ");const title=single?`${actionName(single.action)} · ${single.host_name||"No host"} · ${single.state} · ${single.finished_at||single.started_at||single.created_at}`:`${point.total} jobs · ${distribution} · anchor ${anchorState} ${anchorCount} · ${point.start} – ${point.end}`;const markerY=y(anchorCount);return `<a href="${single?`#/jobs/${single.id}`:escapeHtml(pointRoute(point))}" data-point="${index}" data-anchor-state="${anchorState}" data-anchor-count="${anchorCount}" aria-label="${escapeHtml(title)}"><g class="timeline-point ${status} ${highlight?"latest-point":""}"><circle cx="${x(point.timestamp)}" cy="${markerY}" r="${point.total>1?Math.min(17,9+Math.log2(point.total)):5}"/><title>${escapeHtml(title)}</title>${point.total>1?`<text x="${x(point.timestamp)}" y="${markerY+4}" text-anchor="middle">${point.total}</text>`:""}</g></a>`}).join("");
  const labels=Array.from({length:5},(_,i)=>{const time=new Date(start+(end-start)*i/4);return `<text x="${x(time.toISOString())}" y="${height-12}" text-anchor="${i===0?"start":i===4?"end":"middle"}"><title>${time.toISOString()}</title>${escapeHtml(new Intl.DateTimeFormat(navigator.language,(end-start)<=86400000?{hour:"2-digit",minute:"2-digit"}:{month:"short",day:"numeric",hour:"2-digit"}).format(time))}</text>`}).join("");
  element("history").innerHTML=`<svg class="history-graph" viewBox="0 0 ${width} ${height}" role="group" aria-label="Job timeline; select a point to open a job or grouped time window">${grid}${series}${markers}${labels}</svg>${points.length?"":'<p class="empty">No jobs in this period. Choose a longer period or adjust the filters.</p>'}`;
}
function showTimelinePoint(target){
  const anchor=target.closest?.("[data-point]");if(!anchor)return;const point=currentTimeline.points[Number(anchor.dataset.point)];if(!point)return;
  const preview=element("history-popover"),single=point.total===1;
  preview.innerHTML=single?`<a href="#/jobs/${point.jobs[0].id}">${escapeHtml(actionName(point.jobs[0].action))} · ${escapeHtml(point.jobs[0].host_name||"No host")}</a><p class="state-${point.jobs[0].state}">${escapeHtml(point.jobs[0].short_error||point.jobs[0].state)}</p>${timeLabel(point.timestamp)}`:`<div class="job-orbit"><a class="orbit-center" href="${escapeHtml(pointRoute(point))}" aria-label="${point.total} jobs at ${escapeHtml(point.timestamp)}. Open these jobs in the table.">${point.total}<span class="sr-only"> jobs · open time window in table</span></a>${point.jobs.map((job,index)=>{const label=`${actionName(job.action)} · ${job.host_name||"No host"} · ${job.state} · ${job.finished_at||job.created_at}`;return `<a class="orbit-job orbit-${index%12} state-${job.state}" href="#/jobs/${job.id}" aria-label="Open job: ${escapeHtml(label)}" title="${escapeHtml(label)}"><span aria-hidden="true">●</span><span class="sr-only">${escapeHtml(label)}</span></a>`}).join("")}</div><small>Showing ${point.jobs.length} of ${point.total} jobs. All jobs remain available in the table.</small>`;
  preview.hidden=false;
}
async function updateShown(button){
  const targets=state.hosts.filter(h=>h.checked_at&&h.updates>0&&!state.jobs.some(j=>j.host_id===h.id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action)));
  if(!targets.length)return;
  if(!await confirmAction(`Update all (${targets.length}) hosts?`,`Run regular system updates on these hosts? No restart is requested.`,targets.map(host=>host.name),"Queue updates"))return;
  await run(button,async()=>{let count=0;const failed=[];for(const host of targets){try{await request(hostActionPath(host.id,"update"),{method:"POST"});count++}catch{failed.push(host.name)}}await refreshDashboard();if(failed.length)throw Error(`${count} updates queued. Could not queue: ${failed.join(", ")}. Review host status before retrying.`)},"Updates queued");
}
function hostRow(host,detail=false){
  const jobs=state.jobs.filter(job=>job.host_id===host.id&&ACTIVE_JOB_STATES.has(job.state));
  const locked=jobs.some(job=>MUTATING_JOB_ACTIONS.has(job.action));
  const action=(name,label,danger=false)=>`<button type="button" ${danger?'class="danger" ':""}data-host="${host.id}" data-action="${name}" aria-label="${name==="check_updates"?"Check for updates":label}" title="${name==="check_updates"?"Check for updates":label}" ${jobs.some(job=>job.action===name)||(MUTATING_JOB_ACTIONS.has(name)&&locked)?"disabled":""}>${name==="check_updates"?`<span class="refresh-glyph ${jobs.some(job=>job.action===name)?"spinning":""}" aria-hidden="true">↻</span>`:jobs.some(job=>job.action===name)?"Running…":label}</button>`;
  const system=[host.distribution,host.distribution_version].filter(Boolean).join(" ")||host.status||"Not checked";
  return `<div class="row"><span>${detail?"":`<a href="#/hosts/${host.id}">${escapeHtml(host.name)}</a>`}<span class="website-links">${websiteLinks(host)}</span><small>${escapeHtml(system)} · ${host.checked_at?`${host.updates} updates · ${host.security_updates} security · reboot ${host.reboot_required?"required":"not required"}`:"Update status unknown · reboot status unknown"}</small></span><span class="actions">${action("check_updates","↻")}${action("update","Update")}${action("reboot","Reboot",true)}${detail?"":`<a href="#/hosts/${host.id}">Details</a>`}</span></div>`;
}
function jobRow(job,detailed=false){
  const type=escapeHtml(actionName(job.type||job.action)),host=escapeHtml(job.host_name||"No host");
  const when=job.finished_at||job.started_at||job.created_at;
  const absolute=when?new Intl.DateTimeFormat(navigator.language,{dateStyle:"medium",timeStyle:"short"}).format(new Date(when)):"Not yet";
  const detail=detailed?`<small title="${escapeHtml(when||"")}">${escapeHtml(absolute)} · ${escapeHtml(job.state)}${typeof job.duration==="number"?` · ${formatDuration(job.duration)}`:""}</small>${job.short_error?`<small class="state-failed">${escapeHtml(job.short_error)}</small>`:""}`:`<small>${host} · ${timeLabel(when)}</small>`;
  return `<div class="row"><span><span title="${escapeHtml(job.type||job.action)}">${type}</span>${detailed?`<small>${host}</small>`:""}${detail}</span><span class="actions"><span class="state-${escapeHtml(job.state)}" title="${escapeHtml(job.error_code||job.state)}">${escapeHtml(job.state==="failed"&&job.error_code?jobError(job.error_code):job.state)}</span><button type="button" data-job-log="${job.id}">Open</button></span></div>`;
}
function staleHost(host){return !host.checked_at||Date.now()-Date.parse(host.checked_at)>86400000}
function render(){
  const route=view(),page=route.name==="hosts"&&route.id?"host":route.name==="jobs"&&route.id?"job":route.name;
  document.querySelectorAll("[data-views]").forEach(section=>section.hidden=!section.dataset.views.split(" ").includes(page));
  const contextId=route.id&&route.name==="hosts"?route.id:route.params.get("host_id");
  const contextHost=state.hosts.find(host=>host.id===contextId);
  document.querySelectorAll("nav a").forEach(link=>{const tab=link.dataset.tab;if(tab){link.href=tab==="hosts"?(contextId?`#/hosts/${encodeURIComponent(contextId)}`:"#/hosts"):`#/${tab}${contextId?`?host_id=${encodeURIComponent(contextId)}`:""}`}if(link.dataset.tab===route.name)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current")});
  const context=element("host-context");context.hidden=!contextHost;context.innerHTML=contextHost?`<strong>Selected host: ${escapeHtml(contextHost.name)}</strong> <a href="#/hosts">Change host or return to all hosts</a>`:"";
  const summary=state.dashboard;
  const latest=state.jobs.find(job=>ACTIVE_JOB_STATES.has(job.state))||summary?.last_job||state.jobs[0],failed=summary?.last_failed_job||state.jobs.find(job=>job.state==="failed");
  renderBackendStatus();
  const scopedHosts=contextHost?[contextHost]:state.hosts,checkedHosts=scopedHosts.filter(host=>host.checked_at),unchecked=scopedHosts.length-checkedHosts.length;
  const updates=checkedHosts.reduce((total,host)=>total+host.updates,0),securityCount=checkedHosts.reduce((total,host)=>total+host.security_updates,0);
  const updateStatus=checkedHosts.length?`${updates} ${unchecked?"known ":""}updates · ${securityCount} ${unchecked?"known ":""}security updates`:scopedHosts.length?"Update status unknown":"No hosts yet";
  const metrics=[["Hosts",contextHost?1:state.hosts.length,updateStatus+(unchecked?` · ${unchecked} unchecked ${unchecked===1?"host":"hosts"}`:"")],["Running jobs",contextHost?state.jobs.filter(job=>job.host_id===contextHost.id&&job.state==="running").length:summary?.running_jobs??0,"Being processed now"],["Queued jobs",contextHost?state.jobs.filter(job=>job.host_id===contextHost.id&&job.state==="queued").length:summary?.queued_jobs??0,"Waiting for a worker"]];
  element("dashboard").innerHTML=metrics.map(([label,value,detail],index)=>`<a class="toolbar-metric" href="${index===0?"#/hosts":index===1?"#/jobs?state=running":"#/jobs?state=queued"}" title="${escapeHtml(detail)}"><small>${label}</small><strong>${escapeHtml(value)}</strong><span>${escapeHtml(detail)}</span></a>`).join("");
  element("job-highlights").innerHTML=highlightJob(latest,"Last job")+highlightJob(failed,"Last failed job");
  element("job-highlights").hidden=page!=="dashboard";
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
  const filtered=filteredHosts();shownHosts=contextId&&page==="dashboard"?state.hosts.filter(host=>host.id===contextId):page==="dashboard"?filtered.slice(0,5):filtered;
  element("host-filter").value=route.params.get("filter")||"";
  element("host-search").value=route.params.get("h_search")||"";element("host-sort").value=route.params.get("h_sort")||"name";
  element("host-section").querySelector("h2").textContent=contextHost&&page==="dashboard"?"Selected host overview":"Hosts";
  element("context-host-tasks").hidden=!contextHost||page!=="tasks";element("context-host-jobs").hidden=!contextHost||page!=="jobs";
  if(contextHost){element("context-tasks-title").textContent=`Tasks for ${contextHost.name}`;element("context-jobs-title").textContent=`Recent jobs for ${contextHost.name}`}
  element("host-count").textContent=`${shownHosts.length} of ${state.hosts.length} hosts`;
  const eligible=state.hosts.filter(h=>h.checked_at&&h.updates>0&&!state.jobs.some(j=>j.host_id===h.id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action)));
  const unknown=state.hosts.filter(h=>!h.checked_at).length,active=state.hosts.filter(h=>state.jobs.some(j=>j.host_id===h.id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action))).length;
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
  const tasks=filteredTasks().filter(task=>!contextId||!task.host_ids.length||task.host_ids.includes(contextId));element("task-search").value=route.params.get("t_search")||"";element("task-filter").value=route.params.get("t_filter")||"";element("task-sort").value=route.params.get("t_sort")||"name";element("task-count").textContent=`${tasks.length} of ${state.custom_tasks.length} tasks`;
  element("tasks").innerHTML=tasks.map(task=>`<div class="row"><span>${escapeHtml(task.name)}<small>${escapeHtml(task.description)} · ${task.enabled?"Enabled":"Globally disabled"} · ${task.host_ids.length} enabled host assignment(s)</small></span><span class="actions"><button data-edit-task="${task.id}">Edit</button><button data-toggle-task="${task.id}">${task.enabled?"Disable globally":"Enable globally"}</button><button class="danger" data-delete-task="${task.id}">Delete</button></span></div>`).join("")||'<p class="empty">No tasks match these filters. Use + to create one.</p>';
  if(page==="host"){element("hosts").replaceChildren();renderHostDetail(route.id)}
  else if(contextHost){renderHostDetail(contextHost.id)}
  else{element("host-info").replaceChildren();element("host-tasks").replaceChildren();element("host-jobs").replaceChildren()}
  syncWebsiteIcons(["dashboard","hosts","host"].includes(page));
  renderSelectedJob();
  syncJobPolling();
  syncVisibleChecks();
}
function renderHostDetail(id){
  const host=state.hosts.find(h=>h.id===id);
  element("host-title").textContent=host?.name||"Host not found";
  if(!host){element("host-info").replaceChildren();element("host-tasks").replaceChildren();element("host-jobs").replaceChildren();return}
  element("host-info").innerHTML=hostRow(host,true)+`<p>${escapeHtml(host.address)}:${host.port} · ${escapeHtml(host.username)} · Kernel ${escapeHtml(host.kernel||"unknown")}</p><p>Last checked: ${timeLabel(host.checked_at)}</p><div class="actions"><button data-host="${id}" data-action="test_connection">Test connection</button><button data-edit-host="${id}">Edit host</button><button class="danger" data-delete-host="${id}">Remove host</button></div>`;
  element("host-tasks").innerHTML=state.custom_tasks.map(task=>{const result=currentHostTasks.find(c=>c.task_id===task.id)||{state:"unchecked",reasons:[],assigned:false,enabled:false};const suitable=result.state==="suitable",busy=state.jobs.some(j=>j.host_id===id&&ACTIVE_JOB_STATES.has(j.state)&&MUTATING_JOB_ACTIONS.has(j.action));return `<div class="host-task"><strong>${escapeHtml(task.name)}</strong> <span class="state-${result.state}">${result.state}</span><p>${result.assigned?(result.enabled?"Assigned and enabled":"Assigned and disabled"):"Not assigned"} · ${task.enabled?"Globally enabled":"Globally disabled"}</p><p>${escapeHtml(result.reasons.join("; "))||(suitable?"Prerequisites verified. Ready when assigned and enabled.":"Check prerequisites before assigning or running this task.")}</p><small>${result.checked_at?`Checked ${timeLabel(result.checked_at)} · valid up to 24 hours`:"Not checked"}</small><div class="actions"><button data-check-task="${task.id}" data-host="${id}">Check compatibility</button><button data-assign-task="${task.id}" data-host="${id}" ${!suitable&&!result.enabled?"disabled":""}>${result.enabled?"Disable for host":result.assigned?"Enable for host":"Assign to host"}</button>${result.assigned?`<button data-unassign-task="${task.id}" data-host="${id}">Unassign</button>`:""}<button data-task="${task.id}" data-host="${id}" ${!suitable||!result.enabled||!task.enabled||busy?"disabled":""}>Run task</button><button data-edit-task="${task.id}">Edit</button></div></div>`}).join("")||'<p class="empty">No tasks yet. Create a task for this host above.</p>';
  element("host-jobs").innerHTML=currentHostJobs.map(jobRow).join("")||'<p class="empty">No jobs for this host.</p>';
  element("host-all-jobs").href=`#/jobs?host_id=${id}`;
}
async function loadView(){
  const route=view(),contextId=route.name==="hosts"&&route.id?route.id:route.params.get("host_id");
  if(contextId){
    const [checks,jobs]=await Promise.all([request(`hosts/${encodeURIComponent(contextId)}/task-compatibility`),request(`jobs/page?host_id=${encodeURIComponent(contextId)}&limit=5`)]);
    currentHostTasks=checks;currentHostJobs=jobs.items;
  }
  if(["dashboard","jobs"].includes(route.name)&&!route.id){
    const params=jobQuery();
    if(historyMode()==="graph"){params.delete("offset");params.delete("sort");currentTimeline=await request(`jobs/timeline?${params}`)}
    else currentJobPage=await request(`jobs/page?${params}`);
  }
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
  for(const id of ["job-state","job-host","job-action","job-sort"])element(id).addEventListener("change",applyJobFilters);
  element("history-range").addEventListener("change",()=>{if(element("history-range").value==="custom"){element("history-custom").hidden=false;element("history-start").focus()}else applyJobFilters()});
  element("history-toggle").addEventListener("click",()=>updateRoute({display:historyMode()==="graph"?"table":"graph",offset:null,...(element("history-range").value==="all"?{range:"7d"}:{})}));
  element("history-reset").addEventListener("click",()=>updateRoute({start:null,end:null,state:null,host_id:null,action:null,sort:null,offset:null,range:view().name==="jobs"?"all":"7d"}));
  const pageJobs=delta=>updateRoute({offset:Math.max(0,currentJobPage.offset+delta*currentJobPage.limit)});element("jobs-previous").addEventListener("click",()=>pageJobs(-1));element("jobs-next").addEventListener("click",()=>pageJobs(1));
  const hostControls=()=>updateRoute({filter:element("host-filter").value,h_search:element("host-search").value,h_sort:element("host-sort").value});
  element("host-controls").addEventListener("submit",event=>{event.preventDefault();hostControls()});for(const id of ["host-filter","host-search","host-sort"])element(id).addEventListener("change",hostControls);
  const taskControls=()=>updateRoute({t_filter:element("task-filter").value,t_search:element("task-search").value,t_sort:element("task-sort").value});
  element("task-controls").addEventListener("submit",event=>{event.preventDefault();taskControls()});for(const id of ["task-filter","task-search","task-sort"])element(id).addEventListener("change",taskControls);
  element("update-shown").addEventListener("click",event=>updateShown(event.currentTarget));
  element("refresh").addEventListener("click",event=>run(event.currentTarget,refreshDashboard,"Data refreshed"));
  element("history").addEventListener("pointerover",event=>{if(element("history-popover").hidden)showTimelinePoint(event.target)});element("history").addEventListener("focusin",event=>showTimelinePoint(event.target));
  document.addEventListener("pointerdown",event=>{if(!event.target.closest("#history-chart, #history-popover"))element("history-popover").hidden=true});element("history-chart").addEventListener("keydown",event=>{if(event.key==="Escape")element("history-popover").hidden=true});
  element("auto-host-checks").addEventListener("change",event=>{stopVisibleChecks();state.preferences={enabled:event.target.checked};return run(event.target,async()=>{state.preferences=await request("preferences/host-checks",{method:"PATCH",body:{enabled:event.target.checked}});stopVisibleChecks();render()},"Host check preference saved")});
  document.addEventListener("visibilitychange",syncVisibleChecks);
  element("log-preview-link").addEventListener("click",()=>element("log-preview").close());
  window.addEventListener("hashchange",()=>{if(connected)run(null,async()=>{await loadView();render();await loadJobRoute()})});initialize();
});
window.addEventListener("pagehide",()=>{stopJobPolling();stopVisibleChecks()});
