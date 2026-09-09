import asyncio

import pytest

from inflight import InFlight, InFlightConflictError


async def test_cancel_first_caller_second_also_cancelled():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    p2 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)
    assert inflight.size == 1

    p1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await p1

    with pytest.raises(asyncio.CancelledError):
        await p2

    assert inflight.size == 0


async def test_cancel_second_caller_also_cancels_first():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    p2 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    p2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await p2

    with pytest.raises(asyncio.CancelledError):
        await p1

    assert inflight.size == 0


async def test_cancel_first_caller_execute_or_reject_second_rejected():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight.execute_or_reject("k", query))
    await asyncio.sleep(0)

    async def noop():
        pass

    p2 = asyncio.create_task(inflight.execute_or_reject("k", noop))
    await asyncio.sleep(0)

    p1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await p1

    with pytest.raises(InFlightConflictError):
        await p2

    assert inflight.size == 0


async def test_cancel_second_caller_execute_or_reject_first_continues():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight.execute_or_reject("k", query))
    await asyncio.sleep(0)

    async def noop():
        pass

    p2 = asyncio.create_task(inflight.execute_or_reject("k", noop))
    await asyncio.sleep(0)

    with pytest.raises(InFlightConflictError):
        await p2

    event.set()
    result = await p1
    assert result == "done"
    assert inflight.size == 0


async def test_cancel_all_callers_key_removed():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    p2 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)
    assert inflight.size == 1

    p1.cancel()
    p2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await p1
    with pytest.raises(asyncio.CancelledError):
        await p2

    assert inflight.size == 0
    assert not inflight.has("k")


async def test_cancel_task_created_by_execute():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)
    assert inflight.size == 1

    p.cancel()
    with pytest.raises(asyncio.CancelledError):
        await p

    assert inflight.size == 0
    assert not inflight.has("k")


async def test_cancel_task_created_by_execute_or_reject():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p = asyncio.create_task(inflight.execute_or_reject("k", query))
    await asyncio.sleep(0)
    assert inflight.size == 1

    p.cancel()
    with pytest.raises(asyncio.CancelledError):
        await p

    assert inflight.size == 0
    assert not inflight.has("k")


async def test_new_call_after_cancel_executes_again():
    inflight = InFlight()
    call_count = 0

    async def query():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.CancelledError()
        return "ok"

    with pytest.raises(asyncio.CancelledError):
        await inflight.execute("k", query)

    assert inflight.size == 0

    result = await inflight.execute("k", query)
    assert result == "ok"
    assert call_count == 2


async def test_concurrent_cancel_and_complete():
    inflight = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "result"

    p1 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    p2 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    p1.cancel()
    event.set()

    with pytest.raises(asyncio.CancelledError):
        await p1
    with pytest.raises(asyncio.CancelledError):
        await p2

    assert inflight.size == 0
