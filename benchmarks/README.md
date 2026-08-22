# Benchmarks

Benchmarks comparing request deduplication with and without `inflight` across PostgreSQL and Valkey (Redis-compatible), written in Python with `asyncpg`, `valkey`, and the `inflight` package.

## Setup (local)

Start the backing services (PostgreSQL + Valkey):

```bash
docker compose -f benchmarks/docker-compose.yml up -d postgres valkey
```

Install the Python dependencies:

```bash
pip install -e ".[dev,bench]"
```

Run the comparison (benchmarks both scenarios back-to-back over 30s each):

```bash
python -m benchmarks.bench
```

## Run (all in Docker)

Build and run the benchmark container together with Postgres and Valkey:

```bash
docker compose -f benchmarks/docker-compose.yml up --build bench
```

The `bench` service runs `python -m benchmarks.bench` and is wired to reach `postgres` and `valkey` on the compose network.

The script seeds 1M rows into the `users` table on first run, then measures total queries completed, QPS, and the number of actual DB and cache calls for each scenario.

## Configuration

The benchmarks read connection settings from environment variables:

- `DATABASE_URL` (default `postgres://bench:bench@localhost:5432/bench`)
- `VALKEY_URL` (default `redis://localhost:6379`)

---

## Experiment 1: Concurrency 100, Keys 10

**Setup:**

- Duration: 30s
- Cache TTL: 5s
- Concurrency: 100
- Unique keys: 10

| Metric        | With Inflight | Without Inflight |
| ------------- | ------------- | ---------------- |
| QPS           | ~10,319       | ~1,741           |
| Total queries | 309,700       | 52,300           |
| DB calls      | 60            | 446              |
| Cache calls   | 30,968        | 52,300           |

**Insights:**

- DB calls saved: **44x**
- Cache calls saved: **10x**
- Total queries growth: **5.9x** (52.3K → 309.7K)

---

## Experiment 2: Concurrency 1000, Keys 10

**Setup:**

- Duration: 30s
- Cache TTL: 5s
- Concurrency: 1000
- Unique keys: 10

| Metric        | With Inflight | Without Inflight |
| ------------- | ------------- | ---------------- |
| QPS           | ~31,562       | ~7,043           |
| Total queries | 948,000       | 212,000          |
| DB calls      | 60            | 3,760            |
| Cache calls   | 9,480         | 212,000          |

**Insights:**

- DB calls saved: **280x**
- Cache calls saved: **100x**
- Total queries growth: **4.5x** (212K → 948K)

---

## Key Takeaways

- **Massive throughput growth**: With inflight, the system handles 4.5x-5.9x more total queries in the same time window because deduplication eliminates redundant wait time
- **Higher concurrency reduces DB pressure**: At concurrency 100, DB calls drop to just 60 vs 446 (44x saved), compared to concurrency 1000 with 60 vs 3,760 (280x saved)
- **Cache efficiency**: 10-100x fewer cache calls by deduplicating concurrent requests
