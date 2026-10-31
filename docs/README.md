---
title: Documentation index
status: active
updated: 2026-10-31
tags: [project, index]
---

# Homelab Commander documentation

This public-safe documentation is also an Obsidian vault. Read the section relevant
to your task; agents start with [AGENTS.md](../AGENTS.md). Relative Markdown links
work in GitLab, GitHub and Obsidian without a renderer plugin.

## English Wiki guide

Start with [the Wiki home](wiki/home.md): [User Guide](wiki/user-guide/index.md),
[Product](wiki/product/index.md), [Technical](wiki/technical/index.md) and
[Maintenance](wiki/maintenance/index.md). These are the versioned English sources
for the GitLab Wiki. Detailed normative records and the original vault remain here.

## Install and operate

| Task | Start here |
| --- | --- |
| Install the integration and App | [Installation](../README.md#installation), [fresh-install checklist](04-operations/public-install-checklist.md) |
| Configure hosts, SSH, Docker and jobs | [Native backend guide](04-operations/native-backend.md) |
| Understand permissions and safe diagnostics | [Security and privacy](04-operations/security-and-privacy.md), [security reporting](../SECURITY.md) |
| Upgrade or troubleshoot migration | [Migration 0.1 → 0.2](04-operations/migration-0.1-to-0.2.md), [changelog](../CHANGELOG.md) |
| Publish a release | [Release runbook](04-operations/release-and-publication.md) |

## Develop and review

| Task | Read the relevant sections |
| --- | --- |
| Understand scope or choose work | [Vision](00-project/vision-and-scope.md), [TODO](00-project/todo.md), [backlog](00-project/backlog.md), [roadmap](00-project/roadmap.md) |
| Change behavior | [Requirements](01-product/requirements.md), [acceptance](01-product/acceptance.md) |
| Change a component or contract | [Architecture](02-architecture/overview.md), [native API](02-architecture/native-api.md), [ADR index](02-architecture/adr/README.md) |
| Implement or reproduce a bug | [Contributing](../CONTRIBUTING.md), [workflow](03-development/workflow.md), [code rules](03-development/code-rules.md) |
| Run checks | [Quality gates](03-development/quality-gates.md), [technical foundation](03-development/technical-foundation.md) |
| Update documentation or prepare the Wiki | [Documentation ownership and migration](03-development/documentation.md) |
| Update visual assets | [Branding](03-development/branding.md) |
| Review changes or assess risk | [Code review](05-reviews/code-review.md), [risk register](05-reviews/risk-register.md), [security exceptions](05-reviews/security-exceptions.md) |

[References](references.md) and [glossary](glossary.md) provide supporting context.
[Review records](03-development/documentation.md#inventory-and-history) are dated
evidence, not current instructions. [ADR](templates/adr-template.md) and
[review](templates/code-review-template.md) templates are available when needed.

## Documentation rules and authority

Documents use frontmatter with `title`, `status`, ISO `updated` and `tags`.
Statuses: `draft`, `proposed`, `active`, `accepted`, `superseded`, `archived`.
Update affected requirements, acceptance or user documentation with behavior
changes; keep open work in TODO/backlog. ADRs record architectural decisions.
Existing relative Obsidian links remain supported; prefer Markdown for shared
navigation. No documentation may contain deployment-specific information.

Conflicts are resolved in this order: security/privacy, accepted ADRs, requirements
and acceptance, architecture/development docs, then roadmap/backlog/TODO. Imported
notes remain evidence and cannot silently turn proposals into decisions.
