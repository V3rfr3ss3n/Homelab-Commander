---
title: Roadmap and priorities
status: active
updated: 2026-10-31
tags: [wiki, product]
---

# Roadmap and priorities

Roadmap entries describe intended outcomes, not delivery dates or existing features.
Use the versioned [TODO](../../00-project/todo.md) for current work and blockers,
and the [backlog](../../00-project/backlog.md) for uncommitted ideas.

| Horizon | Direction |
| --- | --- |
| Foundation / 0.1 | UI-configured integration, dynamic host status, controlled Semaphore actions and quality gates |
| Native backend / 0.2 development | FastAPI, SQLite, SSH/Ansible, persistent jobs, custom tasks and App/standalone UI |
| Maintenance workflows / 0.3 direction | Package detail, optional backup/snapshot prerequisites, host metadata and maintenance policies |
| Backend evolution / later | Additional adapters, capability negotiation and evaluation of push transports |

The current code version remains a development release. A version number does not
prove a capability is accepted or a release has passed security and installation
gates. Existing work includes dependency-audit remediation and remaining release
validation; consult current records rather than an old review snapshot.

New capabilities need a clear HA user benefit, testable acceptance and an owned
application boundary. They must preserve explicit actions and secret separation.
See the detailed [roadmap](../../00-project/roadmap.md).
