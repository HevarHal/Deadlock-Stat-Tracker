"""Run the same small, sequential workload before and after a deployment."""

import argparse
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--account", default="434828164")
    parser.add_argument("--output", required=True)
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    prefix = f"/api/player/{args.account}"
    cases = {
        "profile_all": [
            f"{prefix}/summary?scope=all",
            f"{prefix}/matches?scope=all&page=1&page_size=5",
        ],
        "page_2": [f"{prefix}/matches?scope=all&page=2&page_size=5"],
        "profile_season": [
            f"{prefix}/summary?scope=season1",
            f"{prefix}/matches?scope=season1&page=1&page_size=5",
        ],
        "build": [f"{prefix}/matches/129662731/build"],
    }

    def fetch(path):
        with urllib.request.urlopen(args.base + path, timeout=60) as response:
            return {
                "path": path,
                "status": response.status,
                "body": json.load(response),
            }

    results = {
        "base": args.base,
        "account": args.account,
        "rounds": args.rounds,
        "cases": {},
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        for name, paths in cases.items():
            samples, bodies = [], []
            for _ in range(args.rounds):
                start = time.perf_counter()
                bodies = list(pool.map(fetch, paths))
                samples.append(round((time.perf_counter() - start) * 1000, 2))
            results["cases"][name] = {
                "samples_ms": samples,
                "median_ms": statistics.median(samples),
                "responses": bodies,
            }
            print(
                f"{name}: {samples} ms; median={statistics.median(samples):.2f} ms",
                flush=True,
            )
    Path(args.output).write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
