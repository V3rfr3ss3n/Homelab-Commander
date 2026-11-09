---
title: Unprivileged Ansible controller paths review
status: reviewed
updated: 2026-11-09
tags: [review, backend, execution, regression]
---

# Unprivileged Ansible controller paths review

An App check failed before package collection because Ansible used an inherited
root home for controller directories and SSH control sockets. The existing
`ANSIBLE_LOCAL_TEMP` override did not cover both paths. The shared module runner
now scopes `ANSIBLE_HOME` and `ANSIBLE_SSH_CONTROL_PATH_DIR` to its existing private
invocation directory. No root privileges, remote rights, dependencies or migrations
are added; persistent identity and known-host state retain their paths.

The UI also presented default zero counts and no-reboot status beside an unchecked
host. Those values now remain unknown until a stored successful check exists;
dashboard totals identify unchecked hosts. Valid zero-update results remain zero.

## Validation

- The new configuration regression fails with the original two missing overrides,
  then passes with the fix. It resolves settings through the pinned Ansible
  configuration manager and actual SSH plugin option definitions, with only a
  synthetic process. It verifies writable private paths, concurrent isolation,
  parent-environment preservation and directory cleanup. No module or SSH action
  is dispatched by this regression.
- Browser regression reproduces false-zero rendering and verifies unknown status
  under standalone/nested Ingress, while existing successful-zero checks stay zero.
- `UV_NO_SYNC=1 make quality` passes: 342 tests, 98.41% line and 95.83% branch
  coverage independently checked; formatting, lint, strict types, documentation
  links, unfiltered dependency audit and privacy pass.
- Focused local async tests require permitted local event-loop sockets. Restricted
  runs stalled at executor cleanup; the approved local-test run passes without
  loosening checks or contacting managed infrastructure.

The fix is not installed in an existing App until a new image version is published
and explicitly installed. Real host package counts remain an operator acceptance
step after upgrade; stored failures cannot establish an empty package list.
