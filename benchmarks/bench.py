import asyncio


def saved_x(total_with, total_without, calls_with, calls_without):
    return int((total_with / total_without) * (calls_without / calls_with))


async def run():
    from .inflight import bench_with_inflight
    from .no_inflight import bench_without_inflight

    print("\n\n\n\n\n")
    with_inflight = await bench_with_inflight()

    print("\n\n\n\n\n")
    without_inflight = await bench_without_inflight()

    print(
        f"""

Comparison:

with inflight
\tqps:\t\t\t~{with_inflight['qps']}
\ttotal queries:\t\t{with_inflight['totalQueries']}
\tdb calls:\t\t{with_inflight['dbCalls']}
\tcache calls:\t\t{with_inflight['cacheCalls']}

without inflight
\tqps:\t\t\t~{without_inflight['qps']}
\ttotal queries:\t\t{without_inflight['totalQueries']}
\tdb calls:\t\t{without_inflight['dbCalls']}
\tcache calls:\t\t{without_inflight['cacheCalls']}

insights
\tdb calls saved:\t\tx{saved_x(with_inflight['totalQueries'], without_inflight['totalQueries'], with_inflight['dbCalls'], without_inflight['dbCalls'])}
\tcache calls saved:\tx{saved_x(with_inflight['totalQueries'], without_inflight['totalQueries'], with_inflight['cacheCalls'], without_inflight['cacheCalls'])}
"""
    )


if __name__ == "__main__":
    asyncio.run(run())
