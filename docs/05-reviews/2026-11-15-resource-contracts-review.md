---
title: Resource and capability contracts review
status: review
updated: 2026-11-15
tags: [review, contracts, architecture, compatibility]
---

# Resource and capability contracts review (#41)

This is a separate contract-design block after the owner-approved #62/#63 merge.
No version, registry, provider transport, generic executor, policy engine, API
endpoint or Home Assistant configuration changes are introduced here.

## Deliverables and acceptance

| #41 criterion | Review evidence |
| --- | --- |
| ADR and typed contracts with Linux/Pterodactyl examples | [ADR-0022](../02-architecture/adr/0022-resource-and-capability-contracts.md), [normative contracts](../02-architecture/resource-capability-contracts.md), [executable examples](../../backend/tests/test_resource_contracts.py) |
| Distinct unsupported, unavailable and policy-blocked | Four-state immutable assessment; non-supported states require safe reason codes; readiness never grants authority |
| Backward compatibility and migration strategy | Preserve Host/job UUIDs, current persistence, SSH identity and `/api/v1`; explicit staged ownership for #42/#44/#45/#46 |
| Provider contract tests specified, no real side effects | Generic validation/assessment ports, synthetic immutable DTOs and downstream acceptance matrix; no execution method |

The ADR remains proposed until this MR is independently reviewed. Passing the
small contract block is not acceptance of all M1 functionality.

## Tests and boundaries

- Independent service UUID and optional accepted Host association; no fabricated
  host for an API-only service. External provider identifiers stay distinct from
  internal resource and connection identities and are omitted from repr.
- Directional Host/service, infrastructure placement/link and management edges;
  reject same-identity links and invalid endpoint kinds. Global existence/cycle
  checks belong to the future registry transaction.
- Independent contract/schema versions, immutable metadata and typed validators.
  Reject invalid identifiers and unsafe mutation/read/recovery/approval combinations.
- Synthetic Linux and normalized Pterodactyl service examples; four availability
  states, safe error codes, no credentials or network calls.
- Pure projection preserves stored Host JSON, IDs, queued jobs and reviewed failure
  rows. Existing v1 Host/job/key responses remain available; no resources route is
  installed. The API lifespan uses the existing synthetic executor only.
- Full quality/release checks retain independent 95% line and branch gates.

## Actual automated validation

`UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check` passed on 2026-11-15:
**471 tests**, including **26 contract cases**; **98.66% line coverage** and
**96.72% branch coverage**, checked independently. Formatting, lint, strict types,
documentation links, dependency audit (no known vulnerabilities), privacy and
version alignment `0.3.0-dev.5` passed. This is a verification command, not a release
or installation/upgrade approval. Remote CI status is recorded in the MR/PR.

## Review checklist

- [ ] Review resource identity and the reserved VM/container reference semantics.
- [ ] Review capability versioning, schema ownership and the absence of execution
  or authorization tokens in discovery data.
- [ ] Review the explicit additive rollout and uncertain-action recovery boundaries.
- [ ] Accept the contract ADR before implementing #42's registry.

There is intentionally no new user-visible dashboard behavior to accept in this
block. Run the contract examples and review the design; the normal disposable
preview should continue behaving as before. No provider access or real host test
is needed or authorized for automated verification.

## Prior-block handoff

The owner approved #62/#63 and GitLab MR !37 was merged into main at
`83bdd5094ede0509964381adc2d62994d5fc3e43`. The existing mirror propagated that
commit; issues #62/#63 are closed and their project items are Done. No release
was started. Following separate explicit owner approval, exactly four reviewed
Wiki pages were synchronized from that merged commit and read back:
`technical/api`, `technical/development`, `user-guide/troubleshooting` and
`user-guide/updates-and-jobs`. Remote hashes were checked first and page inventory
was preserved. Their source markers distinguish main snapshots from installed
releases.

The architecture Wiki source change in this MR is not published: it is still an
unreviewed proposal. Its live-snapshot update belongs after review/merge with the
appropriate publication authorization. No prior Wiki or publication refusal was
bypassed; the explicit owner approval resolved the scope for those four pages only.
