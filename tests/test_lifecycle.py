import asyncio

import pytest

from inflight import InFlight


async def test_has_true_while_inflight():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    assert not inflight.has("k")

    p = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    assert inflight.has("k")

    event.set()
    await p

    assert not inflight.has("k")


async def test_has_true_while_inflight_execute_or_reject():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    assert not inflight.has("k")

    p = asyncio.create_task(inflight.execute_or_reject("k", query))
    await asyncio.sleep(0)

    assert inflight.has("k")

    event.set()
    await p

    assert not inflight.has("k")


async def test_clear_nonexistent_key():
    inflight = InFlight()

    inflight.clear("nonexistent")
    assert inflight.size == 0


async def test_clear_all_empty():
    inflight = InFlight()

    inflight.clear()
    assert inflight.size == 0


async def test_clear_does_not_cancel_task():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)
    assert inflight.size == 1

    inflight.clear("k")
    assert inflight.size == 0

    event.set()
    result = await p
    assert result == "done"


async def test_clear_all_does_not_cancel_tasks():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight.execute("a", query))
    p2 = asyncio.create_task(inflight.execute("b", query))
    await asyncio.sleep(0)
    assert inflight.size == 2

    inflight.clear()
    assert inflight.size == 0

    event.set()
    r1, r2 = await asyncio.gather(p1, p2)
    assert r1 == "done"
    assert r2 == "done"


async def test_size_after_sequential_operations():
    inflight = InFlight()

    assert inflight.size == 0

    async def quick():
        return 1

    await inflight.execute("a", quick)
    assert inflight.size == 0

    await inflight.execute("b", quick)
    assert inflight.size == 0

    await inflight.execute("a", quick)
    assert inflight.size == 0


async def test_size_after_concurrent_operations():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight.execute("a", query))
    await asyncio.sleep(0)
    assert inflight.size == 1

    p2 = asyncio.create_task(inflight.execute("b", query))
    await asyncio.sleep(0)
    assert inflight.size == 2

    p3 = asyncio.create_task(inflight.execute("c", query))
    await asyncio.sleep(0)
    assert inflight.size == 3

    event.set()
    await asyncio.gather(p1, p2, p3)
    assert inflight.size == 0


async def test_has_tracks_multiple_keys():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight.execute("a", query))
    p2 = asyncio.create_task(inflight.execute("b", query))
    await asyncio.sleep(0)

    assert inflight.has("a")
    assert inflight.has("b")
    assert not inflight.has("c")

    event.set()
    await asyncio.gather(p1, p2)

    assert not inflight.has("a")
    assert not inflight.has("b")
