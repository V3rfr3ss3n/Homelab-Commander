# AGENTS.md

These instructions apply to the entire repository.

## Mission

Build a production-oriented, public-safe Home Assistant custom integration named
`Homelab Updates` with the domain `homelab_updates`. It starts as a Linux update
frontend backed by a status API and Semaphore, but its boundaries must allow new
Home Assistant homelab capabilities and alternative backends without rewriting
entity platforms.

## Required reading

Before changing code or project behavior, read in this order:

1. `docs/README.md`
2. `docs/00-project/vision-and-scope.md`
3. `docs/01-product/requirements.md`
4. `docs/02-architecture/overview.md`
5. `docs/04-operations/security-and-privacy.md`
6. `docs/03-development/code-rules.md`
7. `docs/03-development/quality-gates.md`
8. `docs/00-project/todo.md`

Read the ADR index before making an architectural change. Update the relevant
documentation in the same change as code. Create an ADR when a decision changes
a public contract, security boundary, persistence model, dependency direction,
or backend abstraction.

## Non-negotiable rules

- Never add real hostnames, IP addresses, URLs, domains, tokens, task IDs,
  project IDs, email addresses, Home Assistant exports, or unredacted logs.
- Use only reserved/generic examples such as `node-01` and
  `https://semaphore.example.invalid`.
- Never contact a real backend, start a Semaphore task, update a host, or reboot
  a host from tests or development automation. Tests use mocks and fixtures.
- Never log authorization headers, tokens, full response bodies, or config entry
  dictionaries. Exceptions must be safe to show to users.
- Configuration belongs in Home Assistant config entries and flows, not constants,
  YAML, fixtures, or committed local files.
- All network I/O is asynchronous and uses Home Assistant's injected shared web
  session. Entity properties do no I/O.
- Entity modules depend on application-facing protocols, never on Semaphore JSON,
  endpoint paths, or status API transport details.
- A reboot is always an explicit action. No implicit reboot or update automation
  is implemented inside the integration.
- Do not add a production dependency without documenting why it is necessary and
  recording its maintenance and security impact.

## Engineering workflow

1. Select an item from `docs/00-project/todo.md` and keep the change focused.
2. Confirm acceptance criteria and architecture boundaries before implementation.
3. Add or update tests with the implementation.
4. Run the complete local quality gate described in
   `docs/03-development/quality-gates.md`.
5. Perform the privacy checks in `docs/04-operations/security-and-privacy.md`.
6. Update TODO, backlog, architecture, and review records where applicable.

Do not mark work complete when tests are skipped or unavailable. Record the exact
unverified command and reason in the handoff.

## Code conventions

- Target the Python and Home Assistant versions pinned by `pyproject.toml` and
  the test environment once those files exist.
- Use modern typing throughout. Avoid `Any`, untyped dictionaries, and casts at
  domain boundaries; parse external data into immutable typed models.
- Prefer small modules with one direction of dependency:
  entities -> application services/protocols -> adapters/clients.
- Use Home Assistant-native config flows, typed `ConfigEntry.runtime_data`,
  `DataUpdateCoordinator`, entity descriptions, translations, diagnostics, and
  config entry lifecycle patterns.
- Use Ruff for formatting/linting and Mypy for strict type checking. Suppressions
  must be narrow and include a reason.
- User-visible behavior and defects require tests. Network and time are controlled
  in tests; do not use real sleeps.

## Documentation conventions

- Public user documentation is written in clear English. Internal project notes
  in `docs/` may be German but should keep identifiers and code terms exact.
- Markdown must render in both GitHub and Obsidian. Prefer relative Markdown links
  for public navigation and Obsidian wikilinks where they improve the vault.
- Use ISO dates (`YYYY-MM-DD`). Separate facts, decisions, assumptions, and open
  questions. Do not silently turn a proposal into a decision.
- No documentation may contain deployment-specific data, even if it seems private
  or harmless.
