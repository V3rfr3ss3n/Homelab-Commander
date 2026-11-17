---
title: Cross-layer architecture inventory
status: proposed
updated: 2026-11-16
tags: [architecture, review, maintainability]
---

# Cross-layer architecture inventory

Focused inspection for #69/PR #68, not a repository-wide refactor or security
certification. Paths identify ownership; priorities indicate sequencing, not a new
issue backlog. Existing normative contracts remain authoritative.

| Area / evidence | Already sound | Concrete risk / boundary | Next action |
| --- | --- | --- | --- |
| `frontend/ui.js` | One request/CSRF/diagnostic path, existing dialogs, active jobs and timeline behavior | Large coupled shell/transport/rendering/operations module; global lifetimes | P1: extract transport and navigation with contract tests, then migrate one legacy list at a time |
| `frontend/groups.js` | Existing metadata workflows preserved | Former global IIFE mixed requests/rendering and presented a separate primary destination | This slice: injected bridge, ES-module controller, pure `resource-view.js`, `list-state.js`, Resources facets/editor |
| `frontend/ui.css` | Shared navy/teal palette and semantic status classes | Dense legacy rules and repeated overrides, multiple breakpoints | This slice: semantic aliases used by new components; P2: consolidate per migrated component, visual regression first |
| Lists / package dialog | Host/task filters, job paging, package selection already work | Different selection persistence and sort affordances; package scope is not a resource scope | This slice: explicit identity/page contract. P1: migrate legacy lists without generalizing away package-manager restrictions |
| `app.py` | Shared auth, CSRF, service composition, separate feature routers | Roughly 1,000 lines also own legacy Host/job/task handlers | P1/#45: extract routers/use cases by feature; this slice extracts the closed static asset allowlist into `ui.py`, no feature rules |
| `groups/` and `resources/` | Immutable values, typed ports, SQLite adapters, DTO/router separation | Group rules have bounded snapshot cost; persisted status may be old; no capability producer | Preserve bounds/unknown semantics. #44/#46 must supply execution snapshots and authority, not trust preview |
| `persistence/sqlite.py`, migrations | Transactional additive schema, stable IDs/tombstones, schema lock | Single process; no distributed locking; preview definition and facts are separate reads | No schema change for UI. Later jobs require authoritative transactional resolution/revalidation |
| `jobs.py`, `automation.py` | Persistent jobs, bounded worker, per-Host serialization, synthetic executors | Host-specific action coupling; recovery cannot promise exactly-once remote effects | P0/#44: generic targets/conflict ordering and uncertain-effect recovery before any group operation |
| `errors.py`, UI diagnostics | Safe code/reference allowlists, redacted output, visible stale history | New modules can accidentally bypass failure mapping or leak response contents | This slice reuses injected request/run boundary; test invalid JSON/shape, stale replies, safe retry. No raw error rendering |
| HA `__init__.py`, `coordinator.py`, `adapters/native.py` | Typed runtime_data, shared injected async session, coordinators/unload, validated adapter boundary | Backend and HA evolve separately; large native adapter; limited recent history is not complete target authority | Preserve IDs and protocols. Later generic actions need adapter compatibility tests; no HA import of backend SQLite/entities |
| Authentication / authorization | External Bearer, UI session/Ingress source checks, CSRF, explicit Host actions | Existing admin gate is not fine-grained resource policy; UI visibility is not authority | P0/#46 before bulk/agent execution. Group/tag membership remains metadata only |
| Packaging / deployment | Same FastAPI backend assets in App and standalone; pinned runtime, no browser build tool | Extra modules could escape Ingress prefix, CSP or wheel packaging | This slice verifies both modes and asset access; existing AMD64/ARM64 runtime gates remain |
| Tests / documentation | Meaningful backend/HA/browser tests and independent 95% Python line/branch thresholds | Python coverage does not measure JS branches; earlier Ingress timing failure cause unconfirmed | Add browser behavior tests and late-response cases; retain full gates. Do not label Python coverage frontend coverage |

## Immediate reusable boundaries

Use the existing safe request/diagnostic and confirmation functions; do not invent
another API client or error toast in each module. `ListState` owns only selection,
page/sort and revision mechanics. Resource renderers own columns; group application
rules stay Python-side. The shell bridge is explicit transitional debt, documented
and small; feature modules must not reach into the shell's mutable `state`.

## Deliberate deferrals

Full sidebar, all-list migration, saved views, optimistic concurrent-edit conflict
UI, transport extraction, localization (#70), generic jobs (#44), policy (#46) and
Linux feature extraction (#45) are separate slices. FastAPI, SQLite, Ports & Adapters,
modular monolith and native HA patterns remain. No new production dependency, ORM,
microservice, framework or runtime plugin loader is justified by this review.
