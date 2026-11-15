"use strict";
// A separate workspace owns group drafts; global inventory refreshes do not erase edits.
window.groupWorkspace = (() => {
  let groups=[], resources=[], editing=null, selected=new Set(), groupOffset=0, resourceOffset=0, resourceTotal=0, generation=0;
  const el=id=>document.getElementById(id);
  const fields=["type","distro","tag","capability","status","relationship"];
  const relations=["runs_service","hosts_instance","corresponds_to_host","managed_by"];
  const options=values=>values.map(value=>`<option value="${value}">${value.replaceAll("_"," ")}</option>`).join("");
  function reset(){generation++;groups=[];resources=[];selected.clear();editing=null;groupOffset=0;resourceOffset=0;el("group-editor").hidden=true;for(const id of ["group-name","group-description","group-search","group-resource-query","group-resource-tag"])el(id).value="";el("group-rules").replaceChildren();el("group-selection-count").textContent="";for(const id of ["group-list","group-resources","group-preview-result"])el(id).replaceChildren()}
  function count(){el("group-selection-count").textContent=el("group-kind").value==="manual"?`${selected.size} selected (maximum 500); selection is retained across resource pages.`:"Membership is recalculated from current inventory when viewed."}
  function resourceRows(){
    const manual=!el("group-editor").hidden&&el("group-kind").value==="manual";el("group-clear-selection").hidden=!manual;
    el("group-resources").innerHTML=resources.map(r=>`<div class="row"><div>${manual?`<label class="check"><input type="checkbox" data-group-member="${r.id}" ${selected.has(r.id)?"checked":""}>${escapeHtml(r.name)}</label>`:`<strong>${escapeHtml(r.name)}</strong>`}<small>${escapeHtml(r.kind.replaceAll("_"," "))}${r.distro?` · ${escapeHtml(r.distro)}`:""}</small></div><div class="actions"><label>Tags<input data-resource-tags="${r.id}" value="${escapeHtml(r.tags.join(", "))}" maxlength="1600" aria-label="Tags for ${escapeHtml(r.name)}"></label><button type="button" data-save-tags="${r.id}" data-icon="save">Save tags</button></div></div>`).join("")||'<p class="empty">No matching resources.</p>';
    el("group-resource-count").textContent=`${resourceOffset+Math.min(1,resourceTotal)}–${Math.min(resourceOffset+25,resourceTotal)} of ${resourceTotal} resources`;
    el("group-resources-previous").disabled=resourceOffset===0;el("group-resources-next").disabled=resourceOffset+25>=resourceTotal;count();decorateIcons();
  }
  async function load(){
    if(!state.info)return;
    const current=++generation,params=new URLSearchParams({query:el("group-resource-query").value,limit:"25",offset:String(resourceOffset)});
    if(el("group-resource-kind").value)params.set("kind",el("group-resource-kind").value);
    if(el("group-resource-tag").value)params.set("tag",el("group-resource-tag").value);
    const [nextGroups,page]=await Promise.all([request(`groups?${new URLSearchParams({query:el("group-search").value,limit:"25",offset:String(groupOffset)})}`),request(`group-resources?${params}`)]);
    if(current!==generation)return;
    groups=nextGroups;resources=page.items;resourceTotal=page.total;
    el("group-list").innerHTML=groups.map(g=>`<article class="row"><div><strong>${escapeHtml(g.name)}</strong><small>${g.kind==="smart"?"Smart group · dynamic rules":`Manual group · ${g.members.length} selected`} · ${escapeHtml(g.description)}</small></div><div class="actions"><button type="button" data-edit-group="${g.id}" data-icon="edit">Edit</button><button type="button" data-view-group="${g.id}">View members</button><button type="button" data-delete-group="${g.id}" data-icon="trash">Delete</button></div></article>`).join("")||'<p class="empty">No groups match. Create your first group.</p>';
    el("group-previous").disabled=groupOffset===0;el("group-next").disabled=groups.length<25;resourceRows();
  }
  function addRule(predicate={field:"type",value:"host",relationship:null}){
    if(el("group-rules").children.length>=16)return;
    const row=document.createElement("div");row.className="group-rule list-toolbar";
    row.innerHTML=`<label>Field<select data-rule-field>${options(fields)}</select></label><label>Value<input data-rule-value required maxlength="128"></label><label data-relationship-label>Relationship<select data-rule-relation>${options(relations)}</select></label><button type="button" data-remove-rule aria-label="Remove rule">×</button>`;
    row.querySelector("[data-rule-field]").value=predicate.field;row.querySelector("[data-rule-value]").value=predicate.value;
    if(predicate.relationship)row.querySelector("[data-rule-relation]").value=predicate.relationship;
    row.querySelector("[data-relationship-label]").hidden=predicate.field!=="relationship";
    el("group-rules").append(row);
  }
  function edit(group=null){editing=group?.id||null;selected=new Set(group?.members||[]);el("group-name").value=group?.name||"";el("group-description").value=group?.description||"";el("group-kind").value=group?.kind||"manual";el("group-combine").value=group?.rule?.combine||"all";el("group-rules").replaceChildren();for(const rule of group?.rule?.predicates||[{field:"type",value:"host"}])addRule(rule);el("group-editor").hidden=false;el("group-rule-editor").hidden=el("group-kind").value!=="smart";el("group-rule-editor").disabled=el("group-kind").value!=="smart";el("group-editor-title").textContent=group?`Edit ${group.name}`:"New group";el("group-preview-result").replaceChildren();resourceRows();el("group-name").focus()}
  function draft(){const smart=el("group-kind").value==="smart";return {name:el("group-name").value.trim(),description:el("group-description").value,kind:smart?"smart":"manual",members:smart?[]:[...selected],rule:smart?{combine:el("group-combine").value,predicates:[...el("group-rules").children].map(row=>({field:row.querySelector("[data-rule-field]").value,value:row.querySelector("[data-rule-value]").value,...(row.querySelector("[data-rule-field]").value==="relationship"?{relationship:row.querySelector("[data-rule-relation]").value}:{})}))}:null}}
  function preview(page){el("group-preview-result").textContent=`${page.total} matching resources${page.total>page.items.length?` (first ${page.items.length} shown)`:""}: ${page.items.map(r=>r.name).join(", ")||"None"}`}
  async function loadPreview(path,options){
    const current=generation;el("group-preview-result").textContent="Loading preview…";
    try{const page=await request(path,options);if(current===generation)preview(page)}
    catch(error){if(current===generation)el("group-preview-result").textContent="Preview unavailable. Review the error notification and retry.";throw error}
  }
  document.addEventListener("DOMContentLoaded",()=>{
    el("group-clear-selection").addEventListener("click",()=>{selected.clear();el("group-preview-result").replaceChildren();resourceRows()});
    el("group-editor").addEventListener("input",()=>el("group-preview-result").replaceChildren());
    el("group-new").addEventListener("click",()=>edit());el("group-cancel").addEventListener("click",()=>{editing=null;el("group-editor").hidden=true;resourceRows()});
    el("group-kind").addEventListener("change",()=>{el("group-rule-editor").hidden=el("group-kind").value!=="smart";el("group-rule-editor").disabled=el("group-kind").value!=="smart";resourceRows()});
    el("group-add-rule").addEventListener("click",()=>addRule());
    el("group-rules").addEventListener("click",event=>{if(event.target.closest("[data-remove-rule]"))event.target.closest(".group-rule").remove()});
    el("group-rules").addEventListener("change",event=>{const row=event.target.closest(".group-rule");row.querySelector("[data-relationship-label]").hidden=row.querySelector("[data-rule-field]").value!=="relationship"});
    el("group-preview").addEventListener("click",event=>run(event.currentTarget,async()=>{if(!el("group-editor").reportValidity())return;await loadPreview("groups/preview?limit=100",{method:"POST",body:draft()})}));
    el("group-editor").addEventListener("submit",event=>{event.preventDefault();run(el("group-save"),async()=>{await request(editing?`groups/${editing}`:"groups",{method:editing?"PUT":"POST",body:draft()});editing=null;el("group-editor").hidden=true;await load()},"Group saved")});
    for(const [id,key] of [["group-search-form","group"],["group-resource-search","resource"]])el(id).addEventListener("submit",event=>{event.preventDefault();if(key==="group")groupOffset=0;else resourceOffset=0;run(null,load)});
    for(const [id,delta,isGroup] of [["group-previous",-25,true],["group-next",25,true],["group-resources-previous",-25,false],["group-resources-next",25,false]])el(id).addEventListener("click",event=>{if(isGroup)groupOffset=Math.max(0,groupOffset+delta);else resourceOffset=Math.max(0,resourceOffset+delta);run(event.currentTarget,load)});
    el("group-resources").addEventListener("change",event=>{const id=event.target.dataset.groupMember;if(id){if(event.target.checked)selected.add(id);else selected.delete(id);count()}});
    el("groups-workspace").addEventListener("click",async event=>{
      const button=event.target.closest("button");if(!button)return;
      if(button.dataset.editGroup)edit(groups.find(g=>g.id===button.dataset.editGroup));
      if(button.dataset.viewGroup)run(button,()=>loadPreview(`groups/${button.dataset.viewGroup}/resources?limit=100`));
      if(button.dataset.deleteGroup&&await confirmAction("Delete group?","Remove this group and its membership metadata? Resources and tags remain.",[],"Delete group"))run(button,async()=>{await request(`groups/${button.dataset.deleteGroup}`,{method:"DELETE"});await load()},"Group deleted");
      if(button.dataset.saveTags)run(button,async()=>{const value=el("group-resources").querySelector(`[data-resource-tags="${button.dataset.saveTags}"]`).value;await request(`resources/${button.dataset.saveTags}/tags`,{method:"PUT",body:{tags:value.split(",").map(t=>t.trim()).filter(Boolean)}});await load()},"Tags saved");
    });
  });
  return {load,reset};
})();
