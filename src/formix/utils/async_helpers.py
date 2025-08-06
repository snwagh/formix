# src/formix/utils/async_helpers.py
import asyncio
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
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


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        # If we're already in an async context, create a new thread
        with ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()


class AsyncTimer:
    """Context manager for timing async operations."""

    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time = None
        self.end_time = None

    async def __aenter__(self):
        self.start_time = asyncio.get_event_loop().time()
        return self

    async def __aexit__(self, *args):
        self.end_time = asyncio.get_event_loop().time()
        self.elapsed = self.end_time - self.start_time
        logger.info(f"{self.name} took {self.elapsed:.3f} seconds")

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed * 1000 if hasattr(self, 'elapsed') else 0
