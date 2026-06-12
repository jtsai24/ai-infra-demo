#!/usr/bin/env python3
"""
Concurrent load generator for vLLM.
Shows how TTFT and throughput change as concurrency increases.
"""

import json
import time
import urllib.request
import concurrent.futures
import statistics

VLLM_URL = "http://localhost:8000/v1/completions"
MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"
PROMPTS = [
    "What is attention in a transformer model?",
    "Explain CUDA cores vs tensor cores.",
    "What does a GPU memory controller do?",
    "Describe the role of the KV cache in inference.",
    "What is speculative decoding?",
]


def single_request(prompt: str) -> dict:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": True,
        "max_tokens": 200,
    }).encode()
    req = urllib.request.Request(
        VLLM_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    t0 = time.perf_counter()
    t_first = None
    token_count = 0
    t_done = None

    with urllib.request.urlopen(req) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line or not line.startswith("data: "):
                continue

            data = line[len("data: "):]
            if data == "[DONE]":
                t_done = time.perf_counter()
                break

            chunk = json.loads(data)
            now = time.perf_counter()

            token_text = chunk.get("choices", [{}])[0].get("text", "")
            if token_text:
                if t_first is None:
                    t_first = now
                token_count += 1

    t_done = t_done or time.perf_counter()
    t_first = t_first or t_done
    return {
        "ttft_ms": round((t_first - t0) * 1000, 1),
        "total_s": round(t_done - t0, 2),
        "tokens": token_count,
        "tps": round(token_count / (t_done - t0), 1),
    }


def run_load_test(concurrency: int):
    prompts = (PROMPTS * 10)[:concurrency]

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(single_request, prompts))
    elapsed = time.perf_counter() - t_start

    ttfts = [r["ttft_ms"] for r in results]
    tps_vals = [r["tps"] for r in results]

    print(f"\nConcurrency: {concurrency}")
    print(f"  TTFT  — p50: {statistics.median(ttfts):.0f}ms  "
          f"p95: {sorted(ttfts)[int(len(ttfts)*0.95)]:.0f}ms  "
          f"max: {max(ttfts):.0f}ms")
    print(f"  Throughput — avg {statistics.mean(tps_vals):.1f} tok/s per request, "
          f"wall time {elapsed:.1f}s")


if __name__ == "__main__":
    print(f"Load test against {MODEL}")
    print("=" * 50)
    for c in [1, 2, 4]:
        run_load_test(c)