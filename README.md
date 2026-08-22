# inflight

Deduplicate concurrent async requests by query_key. When multiple identical coroutines are in-flight, only one executes — the rest wait for and receive the same result.

## Why

In high-concurrency environments, identical queries (same DB row, same cache key) accumulate while each one independently hits the database or cache. inflight collapses these into a single call.

## Install

```bash
pip install inflight
```

## Usage

```python
import json
from inflight import InFlight


class Repo:
    def __init__(self, db, cache):
        self.db = db
        self.cache = cache
        self._inflight = InFlight()

    async def get_user(self, user_id: int):
        cached = await self._inflight.execute(
            f"user:{user_id}:cache",
            lambda: self.cache.get(f"user:{user_id}"),
        )

        if cached:
            return json.loads(cached)

        result = await self._inflight.execute(
            f"user:{user_id}:db",
            lambda: self.db.execute(
                select(users).where(users.c.id == user_id)
            ),
        )

        await self.cache.set(f"user:{user_id}", json.dumps(result), ex=5)
        return result
```

## Benchmarks

See [benchmarks/README.md](./benchmarks/README.md) for performance comparison with and without inflight.

## License

GPL-3.0-only
