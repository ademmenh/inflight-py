import os
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "postgres://bench:bench@localhost:5432/bench")
VALKEY_URL = os.getenv("VALKEY_URL", "redis://localhost:6379")
SEED_COUNT = 1_000_000

ROLES = ["admin", "user", "moderator", "guest"]


async def setup(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            age INTEGER NOT NULL,
            role TEXT NOT NULL,
            api_key UUID NOT NULL
        )
    """)

    row = await conn.fetchval("SELECT COUNT(*) FROM users")
    count = int(row)

    if count < SEED_COUNT:
        print(f"seeding {SEED_COUNT} rows...")
        await conn.execute("DELETE FROM users")

        batch = 10_000
        for offset in range(0, SEED_COUNT, batch):
            values = []
            for i in range(batch):
                n = offset + i + 1
                values.append(
                    (
                        n,
                        f"user-{n}",
                        f"user{n}@example.com",
                        18 + (n % 60),
                        ROLES[n % len(ROLES)],
                        str(uuid.uuid4()),
                    )
                )
            await conn.copy_records_to_table(
                "users",
                records=values,
                columns=["id", "name", "email", "age", "role", "api_key"],
            )
            if (offset + batch) % 100_000 == 0 or offset + batch >= SEED_COUNT:
                print(f"  seeded {min(offset + batch, SEED_COUNT)}/{SEED_COUNT}")

        print(f"seeded {SEED_COUNT} rows")
    else:
        print(f"table has {count} rows, skipping seed")


def random_id() -> int:
    import random

    return random.randint(1, SEED_COUNT)
