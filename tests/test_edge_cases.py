import asyncio

import pytest

from inflight import InFlight, InFlightConflictError


async def test_empty_string_key():
    inflight = InFlight()

    async def query():
        return "ok"

    result = await inflight.execute("", query)
    assert result == "ok"
    assert inflight.size == 0


async def test_empty_string_key_execute_or_reject():
    inflight = InFlight()

    async def query():
        return "ok"

    result = await inflight.execute_or_reject("", query)
    assert result == "ok"
    assert inflight.size == 0


async def test_return_none():
    inflight = InFlight()

    async def query():
        return None

    result = await inflight.execute("k", query)
    assert result is None
    assert inflight.size == 0


async def test_return_dict():
    inflight = InFlight()

    async def query():
        return {"key": "value", "count": 42}

    result = await inflight.execute("k", query)
    assert result == {"key": "value", "count": 42}


async def test_return_list():
    inflight = InFlight()

    async def query():
        return [1, 2, 3]

    result = await inflight.execute("k", query)
    assert result == [1, 2, 3]


async def test_multiple_instances_isolated():
    inflight1 = InFlight()
    inflight2 = InFlight()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return "done"

    p1 = asyncio.create_task(inflight1.execute("k", query))
    await asyncio.sleep(0)

    p2 = asyncio.create_task(inflight2.execute("k", query))
    await asyncio.sleep(0)

    assert inflight1.size == 1
    assert inflight2.size == 1

    event.set()
    await asyncio.gather(p1, p2)

    assert inflight1.size == 0
    assert inflight2.size == 0


async def test_inflight_conflict_error_is_exception():
    err = InFlightConflictError("key")
    assert isinstance(err, Exception)
    assert isinstance(err, BaseException)


async def test_inflight_conflict_error_str():
    err = InFlightConflictError("my-key")
    assert str(err) == 'inflight conflict for "my-key"'


async def test_inflight_conflict_error_query_key():
    err = InFlightConflictError("test-123")
    assert err.query_key == "test-123"


async def test_long_key():
    inflight = InFlight()
    long_key = "a" * 10000

    async def query():
        return "ok"

    result = await inflight.execute(long_key, query)
    assert result == "ok"
    assert inflight.size == 0


async def test_special_characters_in_key():
    inflight = InFlight()

    async def query():
        return "ok"

    keys = [
        "key with spaces",
        "key/with/slashes",
        "key:with:colons",
        "key.with.dots",
        "key-with-dashes",
        "key_with_underscores",
        "key?with?symbols",
        "key=with=equals",
        "key&with&amps",
    ]

    for key in keys:
        result = await inflight.execute(key, query)
        assert result == "ok"
        assert inflight.size == 0


async def test_execute_return_value_identity():
    inflight = InFlight()
    sentinel = object()

    async def query():
        return sentinel

    result = await inflight.execute("k", query)
    assert result is sentinel


async def test_execute_or_reject_return_value_identity():
    inflight = InFlight()
    sentinel = object()

    async def query():
        return sentinel

    result = await inflight.execute_or_reject("k", query)
    assert result is sentinel


async def test_concurrent_callers_same_identity_execute():
    inflight = InFlight()
    sentinel = object()
    event = asyncio.Event()

    async def query():
        await event.wait()
        return sentinel

    p1 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)
    p2 = asyncio.create_task(inflight.execute("k", query))
    await asyncio.sleep(0)

    event.set()
    r1, r2 = await asyncio.gather(p1, p2)

    assert r1 is r2 is sentinel
