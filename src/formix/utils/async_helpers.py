# src/formix/utils/async_helpers.py
import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar('T')


async def gather_with_concurrency(
    max_concurrent: int,
    tasks: list[Coroutine[Any, Any, T]]
) -> list[T]:
    """Execute tasks with limited concurrency."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_task(task):
        async with semaphore:
            return await task

    return await asyncio.gather(
        *(bounded_task(task) for task in tasks),
        return_exceptions=True
    )
