import asyncio

import pytest

from inflight import InFlight, InFlightConflictError


async def test_has_returns_false_initially():
    inflight = InFlight()
    assert not inflight.has("k")
    assert inflight.size == 0


async def test_clear_specific_key():
    inflight = InFlight()
    event = asyncio.Event()

    async def noop():
        await event.wait()

    task = asyncio.create_task(inflight.execute("a", noop))
    await asyncio.sleep(0)
    assert inflight.size == 1

    inflight.clear("a")
    assert inflight.size == 0

    event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_clear_all():
    inflight = InFlight()
    event = asyncio.Event()

    async def noop():
        await event.wait()

    task_a = asyncio.create_task(inflight.execute("a", noop))
    task_b = asyncio.create_task(inflight.execute("b", noop))
    await asyncio.sleep(0)
    assert inflight.size == 2

    inflight.clear()
    assert inflight.size == 0

    event.set()
    for t in (task_a, task_b):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


async def test_size_tracks_tasks():
    inflight = InFlight()
    event = asyncio.Event()

    async def slow():
        await event.wait()

    assert inflight.size == 0

    t1 = asyncio.create_task(inflight.execute("a", slow))
    await asyncio.sleep(0)
    assert inflight.size == 1

    t2 = asyncio.create_task(inflight.execute("b", slow))
    await asyncio.sleep(0)
    assert inflight.size == 2

    event.set()
    await asyncio.gather(t1, t2)
    assert inflight.size == 0


async def test_conflict_error_attributes():
    err = InFlightConflictError("test-key")
    assert err.query_key == "test-key"
    assert 'inflight conflict for "test-key"' in str(err)
