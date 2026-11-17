/** Bounded identity selection and request lifetime, independent of DOM/transport.
 * Sorting/filtering change the page, never silently expand a selection.
 */
export class ListState {
  constructor({limit = 25, maximum = 500} = {}) {
    this.limit = limit;
    this.maximum = maximum;
    this.reset();
  }
  reset() {
    this.revision = (this.revision || 0) + 1;
    this.offset = 0;
    this.sort = "name";
    this.direction = "asc";
    this.selected = new Set();
  }
  invalidate() { return ++this.revision; }
  current(revision) { return revision === this.revision; }
  firstPage() { this.offset = 0; this.invalidate(); }
  page(delta) { this.offset = Math.max(0, this.offset + delta * this.limit); }
  order(column) {
    this.direction = this.sort === column && this.direction === "asc" ? "desc" : "asc";
    this.sort = column;
    this.firstPage();
  }
  choose(id, checked) {
    if (checked && !this.selected.has(id) && this.selected.size >= this.maximum) return false;
    if (checked) this.selected.add(id); else this.selected.delete(id);
    return true;
  }
  choosePage(ids, checked) {
    const next = new Set(this.selected);
    for (const id of ids) { if (checked) next.add(id); else next.delete(id); }
    if (next.size > this.maximum) return false;
    this.selected = next;
    return true;
  }
  clear() { this.selected.clear(); }
  range(total) {
    return `${total ? this.offset + 1 : 0}–${Math.min(this.offset + this.limit, total)} of ${total}`;
  }
}
