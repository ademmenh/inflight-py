import asyncio
from collections.abc import Awaitable
from typing import Any, Callable, Generic, TypeVar

from inflight.errors import InFlightConflictError

T = TypeVar("T")


class InFlight(Generic[T]):
    __slots__ = ("_inflight",)

    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Task[Any]] = {}

    async def execute(
        self, query_key: str, query_function: Callable[[], Awaitable[T]]
    ) -> T:
        existing = self._inflight.get(query_key)
        if existing is not None:
            return await existing  # type: ignore[return-value]

        task = asyncio.ensure_future(query_function())
        self._inflight[query_key] = task
        try:
            return await task
        finally:
            self._inflight.pop(query_key, None)

    async def execute_or_reject(
        self, query_key: str, query_function: Callable[[], Awaitable[T]]
    ) -> T:
        if query_key in self._inflight:
            raise InFlightConflictError(query_key)

        task = asyncio.ensure_future(query_function())
        self._inflight[query_key] = task
        try:
            return await task
        finally:
            self._inflight.pop(query_key, None)

    def has(self, query_key: str) -> bool:
        return query_key in self._inflight

    def clear(self, query_key: str | None = None) -> None:
        if query_key is not None:
            self._inflight.pop(query_key, None)
        else:
            self._inflight.clear()

    @property
    def size(self) -> int:
        return len(self._inflight)
