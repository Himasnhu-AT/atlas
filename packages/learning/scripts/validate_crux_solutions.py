#!/usr/bin/env python3
"""
Test runner for solutions-{crux}.py files across all courses.

Validates that each crux solution passes its corresponding test.py suite
and properly exercises the test assertions and error handling.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time


def find_crux_solutions(root_dir: str) -> list[tuple[str, str, str]]:
    """
    Find all solutions-*.py files.
    Returns list of (exercise_dir, crux_filename, lib_dir).
    """
    pattern = os.path.join(root_dir, "courses", "*", "modules", "*", "exercises", "*")
    results = []
    for exercise_dir in sorted(glob.glob(pattern)):
        if not os.path.isdir(exercise_dir):
            continue
        # Find course lib
        # exercise_dir is .../courses/<course>/modules/<module>/exercises/<ex>
        parts = exercise_dir.split(os.sep)
        try:
            courses_idx = parts.index("courses")
            course_dir = os.sep.join(parts[: courses_idx + 2])
            lib_dir = os.path.join(course_dir, "lib")
        except (ValueError, IndexError):
            lib_dir = ""

        for file in sorted(os.listdir(exercise_dir)):
            if (file.startswith("solutions-") or file.startswith("solution-")) and file.endswith(".py"):
                results.append((exercise_dir, file, lib_dir))
    return results


def run_one_test(
    exercise_dir: str, crux_file: str, lib_dir: str, timeout: float = 30.0
) -> tuple[str, str, bool, str, float]:
    """
    Run one crux solution against test.py in a clean temporary directory.
    Returns (rel_path, crux_file, passed, output, duration).
    """
    start_time = time.time()
    rel_path = os.path.relpath(exercise_dir)
    scratch = tempfile.mkdtemp(prefix="crux-test-")
    try:
        # Copy exercise directory
        for item in os.listdir(exercise_dir):
            if item == "__pycache__":
                continue
            src = os.path.join(exercise_dir, item)
            dst = os.path.join(scratch, item)
            if os.path.isfile(src):
                shutil.copy(src, dst)

        # Copy lib directory if exists
        if lib_dir and os.path.isdir(lib_dir):
            for item in os.listdir(lib_dir):
                if item == "__pycache__" or item.startswith("."):
                    continue
                src = os.path.join(lib_dir, item)
                dst = os.path.join(scratch, item)
                if os.path.isfile(src):
                    shutil.copy(src, dst)

        # Copy the crux solution as solution.py
        shutil.copy(os.path.join(exercise_dir, crux_file), os.path.join(scratch, "solution.py"))

        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        res = subprocess.run(
            [sys.executable, "test.py"],
            cwd=scratch,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.time() - start_time
        output = (res.stdout + res.stderr).strip()
        passed = (res.returncode == 0) and ("Ran 0 tests" not in output)
        return (rel_path, crux_file, passed, output, duration)
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return (rel_path, crux_file, False, f"Timeout after {timeout}s", duration)
    except Exception as e:
        duration = time.time() - start_time
        return (rel_path, crux_file, False, f"Exception: {e}", duration)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        help="Root directory of packages/learning",
    )
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers")
    parser.add_argument("--timeout", type=float, default=30.0, help="Test timeout in seconds")
    parser.add_argument("--filter", default="", help="Filter exercises matching substring")
    args = parser.parse_args()

    crux_items = find_crux_solutions(args.root)
    if args.filter:
        crux_items = [item for item in crux_items if args.filter in item[0] or args.filter in item[1]]

    if not crux_items:
        print("No solutions-*.py files found to test.")
        return 0

    print(f"Found {len(crux_items)} crux solution(s). Testing in parallel with {args.workers} workers...\n")

    passed_count = 0
    failed_items = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_one_test, ex_dir, filename, lib_dir, args.timeout): (ex_dir, filename)
            for ex_dir, filename, lib_dir in crux_items
        }
        for future in concurrent.futures.as_completed(futures):
            rel_path, crux_file, passed, output, duration = future.result()
            if passed:
                passed_count += 1
                print(f"  [PASS] ({duration:.2f}s) {rel_path}/{crux_file}")
            else:
                failed_items.append((rel_path, crux_file, output))
                print(f"  [FAIL] ({duration:.2f}s) {rel_path}/{crux_file}")

    print(f"\nSummary: {passed_count}/{len(crux_items)} crux solution(s) passed.")

    if failed_items:
        print("\nFailures:")
        for rel_path, crux_file, output in failed_items:
            print(f"\n--- {rel_path}/{crux_file} ---")
            tail = "\n".join(output.splitlines()[-10:])
            print(tail)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
