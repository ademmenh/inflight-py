import asyncio
import json
import time
import uuid

import asyncpg
import valkey.asyncio as aiovalkey

from inflight import InFlight

from .setup import DATABASE_URL, VALKEY_URL, random_id, setup

DURATION_S = 30
CACHE_TTL_S = 5
CONCURRENCY = 1000
UNIQUE_KEYS = 10


async def bench_with_inflight() -> dict:
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    async with pool.acquire() as conn:
        await setup(conn)
    cache = aiovalkey.from_url(VALKEY_URL, decode_responses=True)

    db_inflight = InFlight()
    cache_inflight = InFlight()
    db_calls = 0
    cache_calls = 0

    async def query_db(id):
        async def impl():
            nonlocal db_calls
            db_calls += 1
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", id)
            return {
                k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in dict(row).items()
            }

        return await db_inflight.execute(f"user:{id}:db", impl)

    async def cached_query(id):
        async def impl():
            nonlocal cache_calls
            cache_calls += 1
            cached = await cache.get(f"user:{id}")
            if cached:
                return json.loads(cached)

            result = await query_db(id)
            await cache.set(
                f"user:{id}",
                json.dumps(result),
                ex=CACHE_TTL_S,
            )
            return result

        return await cache_inflight.execute(f"user:{id}:cache", impl)

    print("with inflight:")
    print(
        f"duration: {DURATION_S}s | cache ttl: {CACHE_TTL_S}s | "
        f"concurrency: {CONCURRENCY} | keys: {UNIQUE_KEYS}"
    )

    start = time.perf_counter()
    total_queries = 0
    running = True

    async def stop():
        nonlocal running
        await asyncio.sleep(DURATION_S)
        running = False

    asyncio.create_task(stop())

    while running:
        async def request():
            nonlocal total_queries
            await cached_query((random_id() % UNIQUE_KEYS) + 1)
            total_queries += 1

        await asyncio.gather(*[request() for _ in range(CONCURRENCY)])

    elapsed = time.perf_counter() - start
    qps = int((total_queries / elapsed))

    await cache.flushdb()
    await cache.aclose()
    await pool.close()

    return {
        "totalQueries": total_queries,
        "elapsed": elapsed * 1000,
        "dbCalls": db_calls,
        "cacheCalls": cache_calls,
        "qps": qps,
    }


async def main():
    result = await bench_with_inflight()
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
