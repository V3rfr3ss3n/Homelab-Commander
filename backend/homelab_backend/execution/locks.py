"""Single-process, bounded-lifetime resource locks acquired in canonical order."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from ..contracts.resources import ResourceRef


class ResourceLocks:
    def __init__(self) -> None:
        self._locks: dict[ResourceRef, tuple[asyncio.Lock, int]] = {}

    @asynccontextmanager
    async def hold(self, resources: tuple[ResourceRef, ...]) -> AsyncGenerator[None]:
        ordered = sorted(set(resources), key=lambda ref: (ref.kind, ref.id))
        reserved: list[ResourceRef] = []
        try:
            async with AsyncExitStack() as stack:
                for ref in ordered:
                    lock, users = self._locks.get(ref, (asyncio.Lock(), 0))
                    self._locks[ref] = lock, users + 1
                    reserved.append(ref)
                    await stack.enter_async_context(lock)
                yield
        finally:
            for ref in reversed(reserved):
                lock, users = self._locks[ref]
                if users == 1:
                    del self._locks[ref]
                else:
                    self._locks[ref] = lock, users - 1
