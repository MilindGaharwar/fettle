#!/usr/bin/env python3
"""Run every pytest file across bounded independent processes."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--tests", type=Path, default=Path("tests"))
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    files = sorted(args.tests.glob("test_*.py"))
    if not files:
        print("no test files found", file=sys.stderr)
        return 2

    env = dict(os.environ)

    def run(path: Path) -> tuple[Path, subprocess.CompletedProcess[str]]:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(path), "-q"],
            env=env,
            capture_output=True,
            text=True,
        )
        return path, result

    failures = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run, path): path for path in files}
        for future in concurrent.futures.as_completed(futures):
            path, result = future.result()
            completed += 1
            print(f"[{result.returncode}] {path}", flush=True)
            if result.returncode:
                failures.append((path, result))

    for path, result in sorted(failures):
        print(f"\n===== {path} =====", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
    print(f"completed {completed}/{len(files)} test files", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
