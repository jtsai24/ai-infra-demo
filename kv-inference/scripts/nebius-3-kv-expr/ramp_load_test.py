#!/usr/bin/env python3
"""
Ramp load test: runs load_test_multi_session.py at increasing concurrency levels,
killing and relaunching between stages.

Usage:
  python ramp_load_test.py --url http://<node-ip>:30800 --model qwen-7b
  python ramp_load_test.py --url http://<node-ip>:30800 --model qwen-7b \
      --stages 4 8 16 32 --duration 300 --turns 15 --think-time 0.5
"""

import argparse
import os
import signal
import subprocess
import sys
import time

SCRIPT = os.path.join(os.path.dirname(__file__), "load_test_multi_session.py")


def run_stage(concurrency: int, duration: int, url: str, model: str, turns: int, think_time: float):
    print(f"\n{'='*60}")
    print(f"STAGE: concurrency={concurrency}  duration={duration}s")
    print(f"{'='*60}\n")

    cmd = [
        sys.executable, SCRIPT,
        "--url", url,
        "--model", model,
        "--concurrency", str(concurrency),
        "--turns", str(turns),
        "--think-time", str(think_time),
        "--continuous",
    ]

    proc = subprocess.Popen(cmd)
    try:
        proc.wait(timeout=duration)
    except subprocess.TimeoutExpired:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\n--- Stage concurrency={concurrency} complete ---\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--model", default="qwen-7b")
    parser.add_argument("--stages", type=int, nargs="+", default=[4, 8, 16])
    parser.add_argument("--duration", type=int, default=300, help="Seconds per stage")
    parser.add_argument("--turns", type=int, default=15)
    parser.add_argument("--think-time", type=float, default=0.5)
    args = parser.parse_args()

    print(f"Ramp plan: concurrency {args.stages}, {args.duration}s per stage")
    print(f"Total duration: ~{len(args.stages) * args.duration // 60} min\n")

    for concurrency in args.stages:
        run_stage(concurrency, args.duration, args.url, args.model, args.turns, args.think_time)

    print("Ramp complete.")