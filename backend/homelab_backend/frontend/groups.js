import {ListState} from "./list-state.js";
import {resourceRows, groupRows} from "./resource-view.js";

/** Resources owns one inventory; groups are filters and focused metadata editors.
 * The legacy shell injects transport/auth/feedback until its own extraction.
 */
export function createResourceWorkspace(ui) {
  const el = id => document.getElementById(id);
  const list = new ListState();
  let resources = [], groups = [], total = 0, groupOffset = 0;
  let editing = null, focused = null, groupFilter = null, previewRevision = 0;
  let managerRevision = 0, sessionRevision = 0, busy = false, available = false, loadFailed = false;
  const fields = ["type", "distro", "tag", "capability", "status", "relationship"];
  const relations = ["runs_service", "hosts_instance", "corresponds_to_host", "managed_by"];
  const options = values => values.map(value => `<option value="${value}">${value.replaceAll("_", " ")}</option>`).join("");
  const isCurrent = revision => list.current(revision) && ui.connected() && ui.active();
  const perform = (button, action, success = "") => ui.run(button, action, success);

  function invalidatePreview() {
    previewRevision++;
    el("group-preview-result").replaceChildren();
  }
  function context() {
    const labels = [];
    if (el("group-resource-query").value) labels.push(`Find resource: ${el("group-resource-query").value}`);
    if (el("group-resource-kind").value) labels.push(`Type: ${el("group-resource-kind").value.replaceAll("_", " ")}`);
    if (el("group-resource-tag").value) labels.push(`Tag: ${el("group-resource-tag").value}`);
    if (groupFilter) labels.push(`Group: ${groupFilter.name}`);
    if (list.selected.size) labels.push(`${list.selected.size} resources selected for grouping`);
    return {labels, changed: labels.length > 0 || list.sort !== "name" || list.direction !== "asc" || list.offset > 0};
  }
  function selection() {
    const visible = resources.filter(resource => list.selected.has(resource.id)).length;
    const hidden = list.selected.size - visible;
    el("resource-selection-summary").textContent = `${list.selected.size} selected${hidden ? ` · ${hidden} outside this page` : ""}`;
    el("group-selection-count").textContent = el("group-kind").value === "manual"
      ? `${list.selected.size} members (maximum 500). ${hidden} outside this page. Save replaces this group's membership.`
      : "Dynamic membership follows these rules; checked rows are not saved.";
    el("resource-select-page").checked = resources.length > 0 && visible === resources.length;
    el("resource-select-page").indeterminate = visible > 0 && visible < resources.length;
    el("resource-select-page").disabled = !available || busy || !resources.length;
    el("group-clear-selection").disabled = !list.selected.size || busy;
    el("resource-filter-count").textContent = context().labels.length - (list.selected.size ? 1 : 0);
    el("resource-group-name").textContent = groupFilter?.name || "All groups";
    ui.selectionChanged();
  }
  function renderInventory() {
    el("group-resources").innerHTML = resourceRows(resources, list.selected, ui.escape, {interactive: available && !busy, details: el("group-editor").hidden});
    el("group-resource-count").textContent = `${list.range(total)} resources`;
    el("group-resources-previous").disabled = !available || list.offset === 0;
    el("group-resources-next").disabled = !available || list.offset + list.limit >= total;
    for (const button of document.querySelectorAll("[data-resource-sort]")) {
      const active = list.sort === button.dataset.resourceSort;
      button.parentElement.setAttribute("aria-sort", active ? (list.direction === "asc" ? "ascending" : "descending") : "none");
      button.textContent = `${button.dataset.resourceSort === "name" ? "Name" : "Type"}${active ? (list.direction === "asc" ? " ↑" : " ↓") : ""}`;
    }
    selection();
    ui.icons();
  }
  function loadState(text, failed = false) {
    el("resource-load-state").hidden = !text;
    el("resource-load-text").textContent = text;
    el("resource-load-state").classList.toggle("error", failed);
    el("resource-retry").hidden = !failed;
    el("group-resources").setAttribute("aria-busy", text === "Loading resources…" ? "true" : "false");
    el("group-resources").classList.toggle("is-stale", !available);
    if (!available) el("group-resources").querySelectorAll("input,button").forEach(control => control.disabled = true);
  }
  async function load() {
    if (!ui.connected() || !ui.active()) return;
    const revision = list.invalidate();
    available = false;
    // Old rows are visible for orientation, but cannot become an actionable selection.
    el("resource-details").querySelector("[data-save-tags]")?.setAttribute("disabled", "");
    loadState("Loading resources…");
    selection();
    const params = new URLSearchParams({query: el("group-resource-query").value, limit: String(list.limit), offset: String(list.offset), sort: list.sort, direction: list.direction});
    if (el("group-resource-kind").value) params.set("kind", el("group-resource-kind").value);
    if (el("group-resource-tag").value) params.set("tag", el("group-resource-tag").value);
    if (groupFilter) params.set("group_id", groupFilter.id);
    try {
      const page = await ui.request(`group-resources?${params}`);
      if (!isCurrent(revision)) return;
      validatePage(page);
      if (page.total > 0 && list.offset >= page.total) {
        list.offset = Math.floor((page.total - 1) / list.limit) * list.limit;
        return load();
      }
      if (!page.total) list.offset = 0;
      resources = page.items;
      total = page.total;
      available = true;
      loadState("");
      ui.loaded(loadFailed);
      loadFailed = false;
      renderInventory();
      if (focused) showResource(focused, false);
    } catch (error) {
      if (!isCurrent(revision)) return;
      loadFailed = true;
      loadState("Resource inventory unavailable. Displayed rows are stale; retry before selecting resources.", true);
      selection();
      throw error;
    }
  }
  function validatePage(page) {
    if (!page || !Number.isInteger(page.total) || page.total < 0 || !Array.isArray(page.items) || page.items.some(resource =>
      !resource || !ui.validId(resource.id) || typeof resource.name !== "string" || typeof resource.kind !== "string" || !Array.isArray(resource.tags) || resource.tags.some(tag => typeof tag !== "string"))) throw ui.invalidResponse();
  }
  async function loadGroups() {
    const revision = ++managerRevision, session = sessionRevision;
    el("group-manager-state").textContent = "Loading groups…";
    el("group-list").replaceChildren();
    try {
      const next = await ui.request(`groups?${new URLSearchParams({query: el("group-search").value, limit: "25", offset: String(groupOffset)})}`);
      if (session !== sessionRevision || revision !== managerRevision || !ui.active()) return;
      if (!Array.isArray(next) || next.some(group => !ui.validId(group?.id) || !Array.isArray(group.members) || !["manual", "smart"].includes(group.kind))) throw ui.invalidResponse();
      groups = next;
      el("group-list").innerHTML = groupRows(groups, ui.escape);
      el("group-manager-state").textContent = "";
      el("group-previous").disabled = groupOffset === 0;
      el("group-next").disabled = groups.length < 25;
      ui.icons();
    } catch (error) {
      if (session !== sessionRevision || revision !== managerRevision || !ui.active()) return;
      el("group-manager-state").textContent = "Groups unavailable. Retry Search groups.";
      el("group-previous").disabled = true;
      el("group-next").disabled = true;
      throw error;
    }
  }
  async function manage() {
    el("group-manager").showModal();
    await loadGroups();
  }
  function addRule(predicate = {field: "type", value: "host"}) {
    if (el("group-rules").children.length >= 16) return;
    const row = document.createElement("div");
    row.className = "group-rule";
    row.innerHTML = `<label>Field<select data-rule-field>${options(fields)}</select></label><label>Value<input data-rule-value required maxlength="128"></label><label data-relationship-label>Relationship<select data-rule-relation>${options(relations)}</select></label><button type="button" data-remove-rule aria-label="Remove rule" data-icon="close"></button>`;
    row.querySelector("[data-rule-field]").value = predicate.field;
    row.querySelector("[data-rule-value]").value = predicate.value;
    if (predicate.relationship) row.querySelector("[data-rule-relation]").value = predicate.relationship;
    row.querySelector("[data-relationship-label]").hidden = predicate.field !== "relationship";
    el("group-rules").append(row);
    invalidatePreview();
    ui.icons();
  }
  function edit(group = null) {
    if (busy) return;
    editing = group?.id || null;
    if (group) list.selected = new Set(group.members);
    focused = null;
    el("group-manager").close();
    el("resource-context").hidden = false;
    el("resource-details").hidden = true;
    el("group-name").value = group?.name || "";
    el("group-description").value = group?.description || "";
    el("group-kind").value = group?.kind || "manual";
    el("group-combine").value = group?.rule?.combine || "all";
    el("group-rules").replaceChildren();
    for (const rule of group?.rule?.predicates || [{field: "type", value: "host"}]) addRule(rule);
    el("group-editor").hidden = false;
    syncKind();
    el("group-editor-title").textContent = group ? `Edit ${group.name}` : "New group";
    invalidatePreview();
    renderInventory();
    el("group-name").focus();
  }
  function syncKind() {
    el("group-rule-editor").hidden = el("group-kind").value !== "smart";
    el("group-rule-editor").disabled = el("group-kind").value !== "smart";
    invalidatePreview();
    selection();
  }
  function closeEditor() {
    editing = null;
    invalidatePreview();
    el("group-editor").hidden = true;
    el("resource-context").hidden = true;
    renderInventory();
    el("group-new").focus();
  }
  function draft() {
    const smart = el("group-kind").value === "smart";
    return {name: el("group-name").value.trim(), description: el("group-description").value, kind: smart ? "smart" : "manual", members: smart ? [] : [...list.selected], rule: smart ? {combine: el("group-combine").value, predicates: [...el("group-rules").children].map(row => ({field: row.querySelector("[data-rule-field]").value, value: row.querySelector("[data-rule-value]").value, ...(row.querySelector("[data-rule-field]").value === "relationship" ? {relationship: row.querySelector("[data-rule-relation]").value} : {})}))} : null};
  }
  async function preview() {
    if (!el("group-editor").reportValidity()) return;
    const revision = ++previewRevision, session = sessionRevision;
    el("group-preview-result").textContent = "Loading preview…";
    try {
      const page = await ui.request("groups/preview?limit=100", {method: "POST", body: draft()});
      if (session !== sessionRevision || revision !== previewRevision || !ui.active()) return;
      validatePage(page);
      el("group-preview-result").textContent = `${page.total} matching resources${page.total > page.items.length ? ` (first ${page.items.length} shown)` : ""}: ${page.items.map(resource => resource.name).join(", ") || "None"}`;
    } catch (error) {
      if (session !== sessionRevision || revision !== previewRevision || !ui.active()) return;
      el("group-preview-result").textContent = "Preview unavailable. Review the error notification and retry.";
      throw error;
    }
  }
  async function save() {
    if (busy) return;
    const session = sessionRevision, body = draft(), id = editing;
    busy = true;
    el("group-editor").inert = true;
    el("group-editor").setAttribute("aria-busy", "true");
    try {
      await ui.request(id ? `groups/${id}` : "groups", {method: id ? "PUT" : "POST", body});
      if (session !== sessionRevision || !ui.active()) return;
      closeEditor();
      list.clear();
      if (groupFilter?.id === id) groupFilter.name = body.name;
      await load();
    } finally {
      busy = false;
      el("group-editor").inert = false;
      el("group-editor").removeAttribute("aria-busy");
      if (session === sessionRevision && ui.active()) renderInventory();
    }
  }
  function showResource(id, focus = true) {
    if (!available || !el("group-editor").hidden) return;
    const resource = resources.find(item => item.id === id);
    if (!resource) { focused = null; el("resource-context").hidden = true; return; }
    if (!focus && focused === id && !el("resource-details").hidden) {
      el("resource-details").querySelector("[data-save-tags]")?.removeAttribute("disabled");
      return; // Polling must not replace a tag draft or its keyboard focus.
    }
    focused = id;
    el("resource-context").hidden = false;
    el("resource-details").hidden = false;
    el("resource-details").innerHTML = `<div class="section-heading"><h3 tabindex="-1" id="resource-detail-title">${ui.escape(resource.name)}</h3><button type="button" id="resource-close" aria-label="Close resource details" data-icon="close"></button></div><p class="sub">${ui.escape(resource.kind.replaceAll("_", " "))} · ${ui.escape(resource.distro || "System unknown")}</p><label>Tags<input data-resource-tags="${id}" maxlength="1600" value="${ui.escape(resource.tags.join(", "))}" aria-label="Tags for ${ui.escape(resource.name)}"></label><button type="button" data-save-tags="${id}" data-icon="save">Save tags</button>${resource.kind === "host" ? `<p><a href="#/hosts/${id}">Open host details and actions →</a></p>` : ""}`;
    ui.icons();
    if (focus) el("resource-detail-title").focus();
  }
  async function saveTags(id) {
    const session = sessionRevision;
    const value = el("resource-details").querySelector("[data-resource-tags]").value;
    await ui.request(`resources/${id}/tags`, {method: "PUT", body: {tags: value.split(",").map(tag => tag.trim()).filter(Boolean)}});
    if (session === sessionRevision && ui.active()) await load();
  }
  function clearFilters() {
    el("group-resource-query").value = "";
    el("group-resource-kind").value = "";
    el("group-resource-tag").value = "";
    groupFilter = null;
    list.firstPage();
    selection();
  }
  function reset() {
    sessionRevision++;
    managerRevision++;
    invalidatePreview();
    list.reset();
    resources = []; groups = []; total = 0; groupOffset = 0;
    editing = null; focused = null; groupFilter = null; available = false; loadFailed = false;
    for (const id of ["group-name", "group-description", "group-search", "group-resource-query", "group-resource-tag"]) el(id).value = "";
    el("group-resource-kind").value = "";
    el("group-kind").value = "manual";
    el("resource-filters").hidden = true;
    el("resource-filter-toggle").setAttribute("aria-expanded", "false");
    for (const id of ["group-rules", "group-list", "group-resources", "resource-details", "group-selection-count", "resource-selection-summary", "group-resource-count", "group-manager-state"]) el(id).replaceChildren();
    for (const id of ["group-editor", "resource-context", "resource-details"]) el(id).hidden = true;
    el("group-manager").close();
    loadState("");
  }
  async function resetContext() {
    clearFilters(); list.reset(); closeEditor(); focused = null;
    await load();
  }
  function choose(id, checked) {
    if (!available || busy || !list.choose(id, checked)) {
      ui.notice("Selection unavailable or the 500-resource limit was reached.");
      renderInventory(); return;
    }
    invalidatePreview(); selection();
  }
  function mount() {
    el("resource-add").addEventListener("click", () => ui.addHost());
    el("group-resource-search").addEventListener("submit", event => {event.preventDefault(); list.firstPage(); perform(null, load);});
    for (const id of ["group-resource-kind", "group-resource-tag"]) el(id).addEventListener("change", () => {list.firstPage(); perform(null, load);});
    el("resource-filter-toggle").addEventListener("click", () => {const open = el("resource-filters").hidden; el("resource-filters").hidden = !open; el("resource-filter-toggle").setAttribute("aria-expanded", String(open));});
    el("resource-clear-filters").addEventListener("click", () => {clearFilters(); perform(null, load);});
    el("resource-clear-group").addEventListener("click", () => {groupFilter = null; list.firstPage(); perform(null, load);});
    for (const id of ["group-manage", "resource-pick-group"]) el(id).addEventListener("click", event => perform(event.currentTarget, manage));
    for (const id of ["group-new", "group-create"]) el(id).addEventListener("click", () => edit());
    el("group-cancel").addEventListener("click", closeEditor);
    el("group-kind").addEventListener("change", syncKind);
    el("group-add-rule").addEventListener("click", () => addRule());
    el("group-rules").addEventListener("click", event => {const button = event.target.closest("[data-remove-rule]"); if (button) {button.closest(".group-rule").remove(); invalidatePreview(); el("group-add-rule").focus();}});
    el("group-rules").addEventListener("change", event => {const row = event.target.closest(".group-rule"); if (row) row.querySelector("[data-relationship-label]").hidden = row.querySelector("[data-rule-field]").value !== "relationship";});
    el("group-editor").addEventListener("input", invalidatePreview);
    el("group-preview").addEventListener("click", event => perform(event.currentTarget, preview));
    el("group-editor").addEventListener("submit", event => {event.preventDefault(); perform(el("group-save"), save, "Group saved");});
    el("group-clear-selection").addEventListener("click", () => {list.clear(); invalidatePreview(); renderInventory();});
    el("resource-select-page").addEventListener("change", event => {
      if (!available || busy || !list.choosePage(resources.map(resource => resource.id), event.target.checked)) ui.notice("Selection unavailable or the 500-resource limit was reached.");
      invalidatePreview(); renderInventory();
    });
    el("group-resources").addEventListener("change", event => {if (event.target.dataset.groupMember) choose(event.target.dataset.groupMember, event.target.checked);});
    el("resource-retry").addEventListener("click", event => perform(event.currentTarget, load));
    for (const [id, delta] of [["group-resources-previous", -1], ["group-resources-next", 1]]) el(id).addEventListener("click", event => {list.page(delta); perform(event.currentTarget, load);});
    el("group-search-form").addEventListener("submit", event => {event.preventDefault(); groupOffset = 0; perform(null, loadGroups);});
    for (const [id, delta] of [["group-previous", -25], ["group-next", 25]]) el(id).addEventListener("click", event => {groupOffset = Math.max(0, groupOffset + delta); perform(event.currentTarget, loadGroups);});
    el("groups-workspace").addEventListener("click", event => {
      const button = event.target.closest("button"); if (!button) return;
      if (button.dataset.resourceSort) {list.order(button.dataset.resourceSort); perform(button, load);}
      if (button.dataset.resourceDetail) showResource(button.dataset.resourceDetail);
      if (button.id === "resource-close") {const id = focused; focused = null; el("resource-context").hidden = true; document.querySelector(`[data-resource-detail="${id}"]`)?.focus();}
      if (button.dataset.saveTags) perform(button, () => saveTags(button.dataset.saveTags), "Tags saved");
      if (button.dataset.editGroup) edit(groups.find(group => group.id === button.dataset.editGroup));
      if (button.dataset.viewGroup) {
        const group = groups.find(item => item.id === button.dataset.viewGroup);
        groupFilter = {id: group.id, name: group.name}; list.firstPage(); el("group-manager").close(); perform(null, load);
      }
      if (button.dataset.deleteGroup) perform(button, async () => {
        const session = sessionRevision, id = button.dataset.deleteGroup;
        if (!await ui.confirm("Delete group?", "Remove this group and its membership metadata? Resources and tags remain.", [], "Delete group")) return;
        if (session !== sessionRevision) return;
        await ui.request(`groups/${id}`, {method: "DELETE"});
        if (session !== sessionRevision || !ui.active()) return;
        if (groupFilter?.id === id) groupFilter = null;
        if (editing === id) closeEditor();
        await Promise.all([loadGroups(), load()]);
      });
    });
  }
  mount();
  return {load, reset, resetContext, context};
}
window.groupWorkspace = createResourceWorkspace(window.operatorUI);
