"""Measure real latency and throughput against a running API.

    python -m scripts.load_test --url http://localhost:8000 --requests 500 --concurrency 8
    python -m scripts.load_test --mode batch --batch-size 32 --api-key $KEY

Reports p50 / p95 / p99 latency, throughput, and any 429s. Note that anonymous callers are
limited to 60 req/min: pass --api-key (300 req/min) or set RATE_LIMIT_ENABLED=false on the
server to measure raw capacity rather than the limiter.
"""

import argparse
import asyncio
import random
import statistics
import time
from collections import Counter

import httpx

REVIEWS = [
    "Best product I have ever bought!",
    "Terrible quality, broke immediately.",
    "Arrived on time and looks nice, but the battery dies in an hour.",
    "Does exactly what it says. No complaints.",
    "This is not what I would call a good product.",
    "Customer service was helpful and the replacement arrived quickly.",
    "Cheap plastic, the hinge snapped after two days of light use.",
    "I was sceptical at first, but this blender is now used every single morning.",
    "Absolutely useless. Returned it.",
    "Five stars. Would buy again for the whole family.",
]


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


async def worker(client, queue, args, latencies, statuses):
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        if args.mode == "batch":
            url, payload = "/api/v1/batch", {"texts": random.choices(REVIEWS, k=args.batch_size)}
        else:
            url, payload = "/api/v1/predict", {"text": random.choice(REVIEWS)}
        started = time.perf_counter()
        try:
            r = await client.post(url, json=payload)
            statuses[r.status_code] += 1
            if r.status_code == 200:
                latencies.append((time.perf_counter() - started) * 1000)
        except httpx.HTTPError as exc:
            statuses[type(exc).__name__] += 1


async def run(args) -> int:
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    async with httpx.AsyncClient(base_url=args.url, headers=headers, timeout=60) as client:
        ready = await client.get("/ready")
        if ready.status_code != 200:
            print(f"API not ready at {args.url}: {ready.status_code} {ready.text}")
            return 1
        print(f"model: {ready.json().get('model_source')}")

        for _ in range(args.warmup):
            await client.post("/api/v1/predict", json={"text": REVIEWS[0]})

        queue: asyncio.Queue = asyncio.Queue()
        for i in range(args.requests):
            queue.put_nowait(i)
        latencies: list[float] = []
        statuses: Counter = Counter()

        started = time.perf_counter()
        await asyncio.gather(
            *(worker(client, queue, args, latencies, statuses) for _ in range(args.concurrency))
        )
        elapsed = time.perf_counter() - started

    ok = len(latencies)
    texts_per_req = args.batch_size if args.mode == "batch" else 1
    print(
        f"\nmode={args.mode}  requests={args.requests}  concurrency={args.concurrency}  "
        f"texts/request={texts_per_req}"
    )
    print(f"status codes: {dict(statuses)}")
    if not ok:
        print("no successful requests")
        return 1
    print(
        f"latency ms   p50={percentile(latencies, 50):.1f}  p95={percentile(latencies, 95):.1f}  "
        f"p99={percentile(latencies, 99):.1f}  mean={statistics.mean(latencies):.1f}  "
        f"max={max(latencies):.1f}"
    )
    print(
        f"throughput   {ok / elapsed:.1f} req/s  ({ok * texts_per_req / elapsed:.1f} texts/s)  "
        f"over {elapsed:.1f}s"
    )
    if statuses.get(429):
        print("note: 429s mean the rate limiter, not the model, capped this run (see --help)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--requests", type=int, default=300)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--mode", choices=["predict", "batch"], default="predict")
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--api-key", default=None)
    return asyncio.run(run(p.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
