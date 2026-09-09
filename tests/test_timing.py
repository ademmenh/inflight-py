import asyncio

import pytest

from inflight import InFlight


async def test_first_completes_as_second_arrives():
    inflight = InFlight()

    async def query():
        return "done"

    p1 = asyncio.create_task(inflight.execute("k", query))
    result1 = await p1

    p2 = asyncio.create_task(inflight.execute("k", query))
    result2 = await p2

    assert result1 == "done"
    assert result2 == "done"
    assert inflight.size == 0


async def test_execute_or_reject_first_completes_as_second_arrives():
    inflight = InFlight()

    async def query():
        return "done"

    result1 = await inflight.execute_or_reject("k", query)
    result2 = await inflight.execute_or_reject("k", query)

    assert result1 == "done"
    assert result2 == "done"
    assert inflight.size == 0


async def test_three_concurrent_callers():
    inflight = InFlight()
    event = asyncio.Event()
    call_count = 0

    async def query():
        nonlocal call_count
        call_count += 1
        await event.wait()
        return "result"

    p1 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)
    p2 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)
    p3 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    assert inflight.size == 1

    event.set()
    r1, r2, r3 = await asyncio.gather(p1, p2, p3)

    assert r1 == r2 == r3 == "result"
    assert call_count == 1
    assert inflight.size == 0


async def test_three_sequential_calls_all_execute():
    inflight = InFlight()
    call_count = 0

    async def query():
        nonlocal call_count
        call_count += 1
        return call_count

    r1 = await inflight.execute("k", query)
    r2 = await inflight.execute("k", query)
    r3 = await inflight.execute("k", query)

    assert r1 == 1
    assert r2 == 2
    assert r3 == 3
    assert call_count == 3
    assert inflight.size == 0


async def test_staggered_arrivals_all_share():
    inflight = InFlight()
    event = asyncio.Event()
    call_count = 0

    async def query():
        nonlocal call_count
        call_count += 1
        await event.wait()
        return "shared"

    p1 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0.01)

    p2 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0.01)

    p3 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    assert inflight.size == 1

    event.set()
    r1, r2, r3 = await asyncio.gather(p1, p2, p3)

    assert r1 is r2 is r3
    assert call_count == 1
    assert inflight.size == 0


async def test_multiple_keys_concurrent_overlap():
    inflight = InFlight()
    event_a = asyncio.Event()
    event_b = asyncio.Event()

    async def query_a():
        await event_a.wait()
        return "a"

    async def query_b():
        await event_b.wait()
        return "b"

    pa1 = asyncio.create_task(inflight.execute("a", query_a))
    await asyncio.sleep(0)
    pb1 = asyncio.create_task(inflight.execute("b", query_b))
    await asyncio.sleep(0)

    pa2 = asyncio.create_task(inflight.execute("a", query_a))
    await asyncio.sleep(0)
    pb2 = asyncio.create_task(inflight.execute("b", query_b))
    await asyncio.sleep(0)

    assert inflight.size == 2

    event_a.set()
    ra1, ra2 = await asyncio.gather(pa1, pa2)
    assert ra1 == ra2 == "a"
    assert inflight.size == 1

    event_b.set()
    rb1, rb2 = await asyncio.gather(pb1, pb2)
    assert rb1 == rb2 == "b"
    assert inflight.size == 0


async def test_execute_or_reject_three_concurrent():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p0 = asyncio.create_task(inflight.execute_or_reject("k", query))
    await asyncio.sleep(0)

    async def noop():
        pass

    p1 = asyncio.create_task(inflight.execute_or_reject("k", noop))
    p2 = asyncio.create_task(inflight.execute_or_reject("k", noop))

    results = await asyncio.gather(p1, p2, return_exceptions=True)
    assert all(
        isinstance(r, Exception) and "conflict" in str(r) for r in results
    )

    event.set()
    await p0
    assert inflight.size == 0
