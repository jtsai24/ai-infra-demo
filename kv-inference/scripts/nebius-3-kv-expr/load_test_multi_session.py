#!/usr/bin/env python3
"""
Concurrent multi-turn chat load generator for vLLM.
Runs N sessions in parallel, each maintaining independent conversation history.
Measures TTFT and TPOT per turn across all sessions.

Local:  python load_test_multi_session.py
Nebius: python load_test_multi_session.py --url http://<node-ip>:30800 --model Qwen/Qwen2.5-0.5B-Instruct
"""

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.request

TURNS = [
    "Explain what a KV cache is in a large language model inference system.",
    "How does the size of the KV cache affect how many concurrent users you can serve?",
    "What is prefix caching and how does it help with multi-turn conversations?",
    "What happens when the KV cache is full?",
    "How would you monitor KV cache utilization in production?",
]


def run_inference(messages: list, url: str, model: str) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 200,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    t_request_sent = time.perf_counter()
    t_first_token = None
    token_times = []
    full_response = []
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

            token_text = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "") or ""
            if token_text:
                if t_first_token is None:
                    t_first_token = now
                token_times.append(now)
                full_response.append(token_text)

    t_done = t_done or time.perf_counter()
    t_first_token = t_first_token or t_done

    ttft_ms = (t_first_token - t_request_sent) * 1000
    total_tokens = len(token_times)
    total_generation_s = (t_done - t_first_token) if total_tokens > 1 else 0
    tpot_ms = (total_generation_s / (total_tokens - 1) * 1000) if total_tokens > 1 else 0

    return {
        "ttft_ms": round(ttft_ms, 1),
        "tpot_ms": round(tpot_ms, 1),
        "total_tokens": total_tokens,
        "response_full": "".join(full_response),
    }


def run_chat_session(session_id: int, url: str, model: str, max_turns: int, think_time: float) -> list:
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    results = []

    for i, user_text in enumerate(TURNS[:max_turns]):
        messages.append({"role": "user", "content": user_text})
        result = run_inference(messages, url, model)
        assistant_reply = result.pop("response_full")
        messages.append({"role": "assistant", "content": assistant_reply})
        result["session"] = session_id
        result["turn"] = i + 1
        result["prompt_messages"] = len(messages) - 1
        results.append(result)

        print(f"[S{session_id} T{i + 1}] TTFT: {result['ttft_ms']} ms  |  TPOT: {result['tpot_ms']} ms/token  |  Tokens: {result['total_tokens']}")

        if think_time > 0 and i < max_turns - 1:
            time.sleep(think_time)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="vLLM base URL")
    parser.add_argument("--model", default="mlx-community/Qwen2.5-0.5B-Instruct-4bit", help="Model ID")
    parser.add_argument("--turns", type=int, default=5, help="Number of turns per session")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of parallel sessions")
    parser.add_argument("--think-time", type=float, default=0.0, help="Seconds to pause between turns")
    args = parser.parse_args()

    url = f"{args.url.rstrip('/')}/v1/chat/completions"

    print(f"Model:       {args.model}")
    print(f"URL:         {url}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Turns:       {args.turns}")
    print(f"Think time:  {args.think_time}s\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(run_chat_session, sid, url, args.model, args.turns, args.think_time)
            for sid in range(1, args.concurrency + 1)
        ]
        all_results = []
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())

    ttfts = [r["ttft_ms"] for r in all_results]
    tpots = [r["tpot_ms"] for r in all_results]

    print(f"\n{'Session':<10} {'Turn':<6} {'TTFT (ms)':<12} {'TPOT (ms)':<12} {'Tokens':<8} {'Msg count'}")
    print("-" * 60)
    for r in sorted(all_results, key=lambda x: (x["session"], x["turn"])):
        print(f"{r['session']:<10} {r['turn']:<6} {r['ttft_ms']:<12} {r['tpot_ms']:<12} {r['total_tokens']:<8} {r['prompt_messages']}")

    print(f"\n--- Summary across {len(all_results)} requests ---")
    print(f"TTFT  p50: {statistics.median(ttfts):.0f} ms  p95: {sorted(ttfts)[int(len(ttfts) * 0.95)]:.0f} ms  max: {max(ttfts):.0f} ms")
    print(f"TPOT  p50: {statistics.median(tpots):.1f} ms/token")