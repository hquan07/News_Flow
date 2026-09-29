#!/usr/bin/env python3
"""Small dependency-free API smoke/load check for release validation."""

import argparse
import concurrent.futures
import statistics
import time
import urllib.error
import urllib.request


def request_once(url: str, timeout: float) -> tuple[int, float]:
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception:
        status = 0
    return status, (time.monotonic() - started) * 1000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--path", default="/health/ready")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()
    url = f"{args.base_url.rstrip('/')}/{args.path.lstrip('/')}"

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(args.concurrency, 1)
    ) as executor:
        results = list(executor.map(
            lambda _index: request_once(url, args.timeout),
            range(max(args.requests, 1)),
        ))

    statuses = [status for status, _latency in results]
    latencies = sorted(latency for _status, latency in results)
    successful = sum(200 <= status < 400 for status in statuses)
    p95_index = max(int(len(latencies) * 0.95) - 1, 0)
    print(
        f"url={url} requests={len(results)} successful={successful} "
        f"failed={len(results) - successful} "
        f"avg_ms={statistics.fmean(latencies):.1f} "
        f"p95_ms={latencies[p95_index]:.1f} max_ms={max(latencies):.1f}"
    )
    return 0 if successful == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
