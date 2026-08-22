import asyncio

import pytest

from inflight import InFlight


async def test_two_simultaneous_calls_same_key_execute_once():
    inflight = InFlight()
    call_count = 0
    event = asyncio.Event()

    async def query_function():
        nonlocal call_count
        call_count += 1
        await event.wait()
        return "result"

    assert inflight.size == 0

    p1 = asyncio.create_task(inflight.execute("k", query_function))
    await asyncio.sleep(0)
    assert inflight.size == 1

    p2 = asyncio.create_task(inflight.execute("k", query_function))
    await asyncio.sleep(0)
    assert inflight.size == 1

    event.set()
    a, b = await asyncio.gather(p1, p2)

    assert a == "result"
    assert b == "result"
    assert call_count == 1
    assert inflight.size == 0


async def test_different_keys_both_execute():
    inflight = InFlight()
    call_count = 0
    event_a = asyncio.Event()
    event_b = asyncio.Event()

    async def fn_a():
        nonlocal call_count
        call_count += 1
        await event_a.wait()
        return 1

    async def fn_b():
        nonlocal call_count
        call_count += 1
        await event_b.wait()
        return 2

    assert inflight.size == 0

    p_a = asyncio.create_task(inflight.execute("a", fn_a))
    await asyncio.sleep(0)
    assert inflight.size == 1

    p_b = asyncio.create_task(inflight.execute("b", fn_b))
    await asyncio.sleep(0)
    assert inflight.size == 2

    event_a.set()
    a = await p_a
    assert inflight.size == 1

    event_b.set()
    b = await p_b
    assert inflight.size == 0

    assert a == 1
    assert b == 2
    assert call_count == 2


async def test_resolves_key_removed():
    inflight = InFlight()

    assert inflight.size == 0

    async def query_function():
        return 1

    p = asyncio.create_task(inflight.execute("k", query_function))
    await asyncio.sleep(0)
    assert inflight.size == 1

    await p

    assert not inflight.has("k")
    assert inflight.size == 0


async def test_rejects_key_removed():
    inflight = InFlight()

    assert inflight.size == 0

    async def query_function():
        raise RuntimeError("boom")

    p = asyncio.create_task(inflight.execute("k", query_function))
    await asyncio.sleep(0)
    assert inflight.size == 1

    with pytest.raises(RuntimeError, match="boom"):
        await p

    assert not inflight.has("k")
    assert inflight.size == 0


async def test_new_call_after_rejection_executes_again():
    inflight = InFlight()
    call_count = 0

    async def query_function():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("boom")
        return "ok"

    assert inflight.size == 0

    with pytest.raises(RuntimeError, match="boom"):
        await inflight.execute("k", query_function)
    assert inflight.size == 0

    p = asyncio.create_task(inflight.execute("k", query_function))
    await asyncio.sleep(0)
    assert inflight.size == 1
    result = await p

    assert inflight.size == 0
    assert result == "ok"
    assert call_count == 2


async def test_new_call_after_completion_executes_again():
    inflight = InFlight()
    call_count = 0

    async def query_function():
        nonlocal call_count
        call_count += 1
        return call_count

    assert inflight.size == 0

    a = await inflight.execute("k", query_function)
    assert inflight.size == 0

    b = await inflight.execute("k", query_function)
    assert inflight.size == 0

    assert a == 1
    assert b == 2


async def test_concurrent_callers_receive_same_result():
    inflight = InFlight()

    assert inflight.size == 0

    async def query_fn():
        await asyncio.sleep(0.01)
        return "same"

    p1 = asyncio.create_task(inflight.execute("k", query_fn))
    await asyncio.sleep(0)
    p2 = asyncio.create_task(inflight.execute("k", query_fn))
    await asyncio.sleep(0)
    assert inflight.size == 1

    a, b = await asyncio.gather(p1, p2)
    assert a is b
    assert inflight.size == 0

    async def failing():
        raise RuntimeError("boom")

    ep1 = asyncio.create_task(inflight.execute("e", failing))
    await asyncio.sleep(0)
    ep2 = asyncio.create_task(inflight.execute("e", failing))
    await asyncio.sleep(0)
    assert inflight.size == 1

    results = await asyncio.gather(ep1, ep2, return_exceptions=True)
    assert inflight.size == 0
    assert all(isinstance(r, RuntimeError) for r in results)
    assert results[0] is results[1]
