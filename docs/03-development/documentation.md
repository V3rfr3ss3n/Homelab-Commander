---
title: Documentation and Wiki ownership
status: active
updated: 2026-10-31
tags: [development, documentation, wiki, obsidian]
---

# Documentation and Wiki ownership

## Current decision

The owner explicitly authorized an English GitLab Wiki with Technical, Product and
User sections and additional sections where useful. The initial publication contains
26 English content pages plus a custom sidebar. Maintenance is the fourth section.
The project remains public; no visibility, permissions or mirror settings are changed.

The English sources live in [docs/wiki](../wiki/home.md) and are the only editable
maintenance source for these published pages. GitLab is the Wiki reading surface;
its pages are published snapshots, not a second independently maintained master.
The [publication guide](../wiki/maintenance/documentation.md) explains link mapping,
source revisions, review and update responsibilities. No automatic publishing
pipeline or bidirectional synchronization has been introduced.

## Authority and compatibility

Existing requirements, accepted ADRs, security rules and reproducible development
instructions remain versioned beside code. Wiki sections provide English guides and
link these normative references. The practical User Guide is maintained in English;
internal detailed records and historical reviews are not silently translated or
rewritten. Update both an affected normative contract and its explanatory guide
when behavior changes, rather than copying whole records between locations.

The original Obsidian vault, frontmatter and relative links remain intact. Wiki
publication maps local file links to page slugs and repository references to an
exact source commit. Do not replace local links with installation-specific URLs.
No historical content or ADR is deleted as part of publication.

## Inventory

| Source | Responsibility |
| --- | --- |
| Root README, CONTRIBUTING, SECURITY, CHANGELOG | Public introduction, collaboration, reporting and release history |
| `wiki/user-guide/` | English installation, authentication, hosts, operations, tasks, recovery, troubleshooting and FAQ |
| `wiki/product/` | English purpose, supported domain behavior, acceptance and roadmap context |
| `wiki/technical/` | English component architecture, HA, API, execution, persistence, security and development |
| `wiki/maintenance/` | English contribution, documentation ownership and release process |
| `00-project/` | Detailed vision, roadmap, active TODO and backlog |
| `01-product/` | Normative requirements and acceptance |
| `02-architecture/` | Detailed architecture, REST contract and preserved ADR history |
| `03-development/` | Code rules, quality gates, workflow, foundation and branding |
| `04-operations/` | Detailed backend operations, migration, installation, release and privacy |
| `05-reviews/` | Dated evidence and ongoing risk/security registers |
| `templates/`, glossary, references | Reusable templates and supporting knowledge |

Dated reviews describe a particular revision and verification point. They do not
prove current CI or release success. Read the current TODO/security records for
active blockers, and preserve earlier findings as history.

## Privacy and publication boundary

All sections are public-safe. A technical section is not a private area and a
folder name is not an authorization boundary. Real deployment information remains
outside all versioned project documentation, including private Wiki locations.
Separately permissioned organizational documents require an independent access
boundary; no such private area is created by this publication.

Before publishing, review source content, run local link/privacy checks and inspect
existing remote pages. Preserve unexpected remote changes rather than overwriting
them. Publish only the reviewed files, verify inventory/content and rendered links,
and record the source revision. Do not change access rights or enable another
mirror as part of a documentation update.

## Historical assessment

The initial 2026-10-31 API inspection found an enabled but empty Wiki on the public
project. A pre-existing push mirror reported `finished`; no additional mirror was
configured. GitLab had no previous pipeline runs; the MR introduced `make quality`
using existing tools. These were initial findings, not current claims that the
Wiki is empty or that no CI has since run.
