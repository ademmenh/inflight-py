import asyncio

import pytest

from inflight import InFlight, InFlightConflictError


async def test_first_call_executes():
    inflight = InFlight()

    assert inflight.size == 0

    async def query_function():
        return "ok"

    result = await inflight.execute_or_reject("k", query_function)

    assert result == "ok"
    assert inflight.size == 0


async def test_second_call_inflight_rejects_with_conflict():
    inflight = InFlight()
    event = asyncio.Event()

    async def query_function():
        await event.wait()

    p1 = asyncio.create_task(inflight.execute_or_reject("k", query_function))
    await asyncio.sleep(0)
    assert inflight.size == 1

    async def noop():
        pass

    p2 = asyncio.create_task(inflight.execute_or_reject("k", noop))
    await asyncio.sleep(0)
    assert inflight.size == 1

    with pytest.raises(InFlightConflictError, match='inflight conflict for "k"'):
        await p2

    event.set()
    assert await p1 is None
    assert inflight.size == 0


async def test_rejects_with_correct_query_key():
    inflight = InFlight()
    event = asyncio.Event()

    async def query_function():
        await event.wait()

    p0 = asyncio.create_task(inflight.execute_or_reject("my-key", query_function))
    await asyncio.sleep(0)

    async def noop():
        pass

    with pytest.raises(InFlightConflictError) as exc_info:
        await inflight.execute_or_reject("my-key", noop)

    assert exc_info.value.query_key == "my-key"
    event.set()
    try:
        await p0
    except asyncio.CancelledError:
        pass


async def test_different_keys_both_execute():
    inflight = InFlight()

    async def a():
        return 1

    async def b():
        return 2

    result_a, result_b = await asyncio.gather(
        inflight.execute_or_reject("a", a),
        inflight.execute_or_reject("b", b),
    )

    assert result_a == 1
    assert result_b == 2
    assert inflight.size == 0


async def test_after_completion_can_execute_again():
    inflight = InFlight()
    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        return call_count

    a = await inflight.execute_or_reject("k", fn)
    assert a == 1
    assert inflight.size == 0

    b = await inflight.execute_or_reject("k", fn)
    assert b == 2
    assert inflight.size == 0


async def test_after_rejection_can_execute_again():
    inflight = InFlight()

    async def failing():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await inflight.execute_or_reject("k", failing)
    assert inflight.size == 0

    async def ok():
        return "ok"

    result = await inflight.execute_or_reject("k", ok)
    assert result == "ok"
    assert inflight.size == 0


async def test_concurrent_callers_get_same_rejection():
    inflight = InFlight()
    event = asyncio.Event()

    async def query_function():
        await event.wait()

    p0 = asyncio.create_task(inflight.execute_or_reject("k", query_function))
    await asyncio.sleep(0)

    async def noop():
        pass

    p1 = asyncio.create_task(inflight.execute_or_reject("k", noop))
    p2 = asyncio.create_task(inflight.execute_or_reject("k", noop))

    results = await asyncio.gather(p1, p2, return_exceptions=True)
    assert all(isinstance(r, InFlightConflictError) for r in results)

    e1, e2 = results
    assert e1.query_key == e2.query_key

    event.set()
    try:
        await p0
    except asyncio.CancelledError:
        pass
