/** Pure presentation: caller supplies validated facts, identity selection and escaping. */
export function resourceRows(resources, selected, escape, {interactive, details}) {
  return resources.map(resource => `<tr>
    <td><input type="checkbox" data-group-member="${resource.id}" aria-label="Select ${escape(resource.name)}" ${selected.has(resource.id) ? "checked" : ""} ${interactive ? "" : "disabled"}></td>
    <td><button type="button" class="text-button" data-resource-detail="${resource.id}" ${interactive && details ? "" : "disabled"}>${escape(resource.name)}</button></td>
    <td>${escape(resource.kind.replaceAll("_", " "))}</td>
    <td>${escape(resource.distro || "Unknown")}</td>
    <td>${resource.tags.map(tag => `<span class="resource-tag">${escape(tag)}</span>`).join(" ") || "—"}</td>
  </tr>`).join("") || '<tr><td colspan="5" class="empty">No matching resources.</td></tr>';
}

export function groupRows(groups, escape) {
  return groups.map(group => `<article class="row"><div><strong>${escape(group.name)}</strong>
    <small>${group.kind === "smart" ? "Smart group · dynamic rules" : `Manual group · ${group.members.length} selected`} · ${escape(group.description)}</small></div>
    <div class="actions"><button type="button" data-view-group="${group.id}" data-icon="filter">View members</button>
    <button type="button" data-edit-group="${group.id}" data-icon="edit">Edit</button>
    <button type="button" data-delete-group="${group.id}" data-icon="trash">Delete</button></div></article>`).join("") || '<p class="empty">No groups match. Create your first group.</p>';
}
