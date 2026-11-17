"""Policy choke point shared by legacy and future resource job entrances."""

import hashlib
from uuid import UUID

from ..policy.application import PolicyGuard, current_principal, principal_scope
from ..policy.approvals import ApprovalService
from ..policy.domain import (
    SYSTEM,
    AuthSource,
    Permission,
    Principal,
    PrincipalKind,
    entrance,
)
from .scope import ExecutionContext, JobCaller, JobExecution, OperationScope


def legacy_principal(caller: JobCaller) -> Principal:
    kind, source = {
        JobCaller.EXTERNAL_ADMIN: (PrincipalKind.ADMIN, AuthSource.API),
        JobCaller.UI_ADMIN: (PrincipalKind.HUMAN, AuthSource.UI),
        JobCaller.INGRESS_ADMIN: (PrincipalKind.HUMAN, AuthSource.INGRESS),
        JobCaller.VISIBLE_STATUS: (PrincipalKind.STATUS, AuthSource.INTERNAL),
        JobCaller.LEGACY_ADMIN: (PrincipalKind.ADMIN, AuthSource.LEGACY),
        JobCaller.INTERNAL_ADMIN: (PrincipalKind.SYSTEM, AuthSource.INTERNAL),
    }[caller]
    return SYSTEM if caller is JobCaller.INTERNAL_ADMIN else entrance(kind, source)


def scope_digest(scope: OperationScope) -> str:
    return hashlib.sha256(scope.model_dump_json().encode()).hexdigest()


class JobAuthorization:
    def __init__(
        self, guard: PolicyGuard, approvals: ApprovalService | None = None
    ) -> None:
        self.guard = guard
        self._approvals = approvals

    def capture(self, context: ExecutionContext) -> ExecutionContext:
        actor = current_principal()
        if actor == SYSTEM:
            actor = context.principal or legacy_principal(context.caller)
        elif context.caller is JobCaller.VISIBLE_STATUS and actor.kind in {
            PrincipalKind.ADMIN,
            PrincipalKind.HUMAN,
        }:
            actor = legacy_principal(JobCaller.VISIBLE_STATUS)
        return context.model_copy(update={"principal": actor})

    async def async_require_operation(
        self, context: ExecutionContext, scope: OperationScope
    ) -> None:
        await self.guard.async_require(
            Permission.EXECUTE,
            scope.target,
            principal=context.principal or legacy_principal(context.caller),
            operation=scope.operation,
        )

    async def async_authorize(
        self, execution: JobExecution, *, job_id: UUID | None = None
    ) -> None:
        context, scope = execution.context, execution.scope
        actor = context.principal or legacy_principal(context.caller)
        await self.async_require_operation(context, scope)
        definition = self.guard.engine.operation(scope.operation, scope.target)
        assert definition is not None
        if definition.approval_required:
            if context.approval_id is None or self._approvals is None:
                await self.guard.async_deny(
                    Permission.EXECUTE, scope.target, actor, "human_approval_required"
                )
            assert context.approval_id is not None
            assert self._approvals is not None
            with principal_scope(actor):
                if job_id is None:
                    await self._approvals.async_validate(
                        context.approval_id,
                        scope.target,
                        scope.operation,
                        scope_digest(scope),
                    )
                else:
                    await self._approvals.async_consume(
                        context.approval_id,
                        scope.target,
                        scope.operation,
                        scope_digest(scope),
                        job_id,
                    )
        elif context.approval_id is not None:
            await self.guard.async_deny(
                Permission.EXECUTE, scope.target, actor, "approval_unexpected"
            )
