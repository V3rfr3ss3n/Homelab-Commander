---
title: Documentation ownership and publication
status: active
updated: 2026-10-31
tags: [wiki, maintenance]
---

# Documentation ownership and publication

## One maintenance source

The English Wiki reading path is authored in the repository under `docs/wiki/`.
The published GitLab Wiki is a reviewed presentation snapshot of those files,
not an independently edited second master. Request changes through the source MR. `AGENTS.md` directs Codex/OpenCode to the
Wiki home, requires updates to affected Wiki sources with code and requires
publishing the reviewed snapshot through the existing authorized GitLab access.
Agents must check remote edits first and report any source/publication mismatch.
Detailed requirements, accepted ADRs, security rules and reproducible development
instructions stay beside the code and are linked as normative references.

The User Guide owns practical English user instructions. Product pages explain
domain behavior and scope. Technical pages explain component responsibilities and
link exact contracts. Maintenance pages describe project processes. Historical
review records remain dated evidence and are never automatically current policy.

## Update and publish deliberately

1. Edit affected source pages with code and keep their English, public-safe content
   and frontmatter current. Update detailed contracts when behavior changes.
2. Run `make docs`, relevant tests and privacy review. Inspect the complete diff.
3. Publish only the reviewed Wiki page set using the existing authorized GitLab
   access. Preserve any unexpected remote edits for review; never overwrite them
   blindly. When updating a nested page through the GitLab Wiki API, pass its full
   slug path as `title` (for example, `technical/development`); the returned display
   title alone can lose its parent directory. Verify the returned slug. Do not
   delete old content merely to clean up navigation.
4. Map local `.md` links to Wiki page slugs and detailed repository references to
   an exact source revision. A source marker identifies the published snapshot.
5. Verify returned content, page inventory, nested navigation and sidebar links.

This initial publication was explicitly authorized by the project owner. There is
no new automatic publisher, visibility change or bidirectional synchronization.
Future publication uses the user's existing authorization and the established
review scope; a new audience or protected area is a separate decision.

## Preserve the existing vault

The original `docs/` tree and ADR history remain in place. Relative Markdown links
work locally and in Obsidian; publication transforms links without rewriting the
original vault. There is no mass deletion or claim that every historical German
record has been translated. All published Wiki pages themselves are English.

If confidential organizational documentation is needed, use an independently
permissioned location outside this public project knowledge. A Wiki subsection
alone provides no confidentiality boundary.
