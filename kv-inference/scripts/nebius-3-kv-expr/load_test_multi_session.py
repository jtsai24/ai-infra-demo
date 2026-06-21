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
import threading
import time
import urllib.request

TURNS = [
    "Explain what a KV cache is in a large language model inference system.",
    "How does the size of the KV cache affect how many concurrent users you can serve?",
    "What is prefix caching and how does it help with multi-turn conversations?",
    "What happens when the KV cache is full?",
    "How would you monitor KV cache utilization in production?",
    "What is the difference between TTFT and TPOT, and why does each matter for user experience?",
    "How does tensor parallelism affect KV cache size across multiple GPUs?",
    "What tradeoffs exist between batch size and KV cache memory usage?",
    "How does chunked prefill help with long-context requests?",
    "What is preemption in vLLM and when does it occur?",
    "How would you design a KV cache eviction policy for a production system?",
    "What is the relationship between model precision and KV cache memory footprint?",
    "How does continuous batching differ from static batching in terms of memory usage?",
    "What metrics would you alert on to detect KV cache pressure before it impacts users?",
    "How would paged attention help with memory fragmentation in a KV cache?",
]


def run_inference(messages: list, url: str, model: str) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 600,
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


def run_chat_session(session_id: int, url: str, model: str, max_turns: int, think_time: float, stop_event: threading.Event) -> list:
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

        if stop_event.is_set():
            break
        if think_time > 0 and i < max_turns - 1:
            stop_event.wait(think_time)  # wakes early if stop_event is set

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="vLLM base URL")
    parser.add_argument("--model", default="mlx-community/Qwen2.5-0.5B-Instruct-4bit", help="Model ID")
    parser.add_argument("--turns", type=int, default=5, help="Number of turns per session")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of parallel sessions")
    parser.add_argument("--think-time", type=float, default=0.0, help="Seconds to pause between turns")
    parser.add_argument("--continuous", action="store_true", help="Keep running until ctrl-C, replacing completed sessions")
    args = parser.parse_args()

    url = f"{args.url.rstrip('/')}/v1/chat/completions"

    print(f"Model:       {args.model}")
    print(f"URL:         {url}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Turns:       {args.turns}")
    print(f"Think time:  {args.think_time}s\n")

    all_results = []
    session_counter = 0
    stop_event = threading.Event()

    def new_session(pool):
        global session_counter
        session_counter += 1
        return pool.submit(run_chat_session, session_counter, url, args.model, args.turns, args.think_time, stop_event)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        active = {new_session(pool) for _ in range(args.concurrency)}
        try:
            if args.continuous:
                while True:
                    done, active = concurrent.futures.wait(active, return_when=concurrent.futures.FIRST_COMPLETED)
                    for f in done:
                        all_results.extend(f.result())
                        active.add(new_session(pool))
            else:
                for f in concurrent.futures.as_completed(active):
                    all_results.extend(f.result())
        except KeyboardInterrupt:
            print("\nStopping — waiting for in-flight requests to finish...")
            stop_event.set()

    if not all_results:
        print("No results collected.")
    else:
        ttfts = [r["ttft_ms"] for r in all_results]
        tpots = [r["tpot_ms"] for r in all_results]

        print(f"\n{'Session':<10} {'Turn':<6} {'TTFT (ms)':<12} {'TPOT (ms)':<12} {'Tokens':<8} {'Msg count'}")
        print("-" * 60)
        for r in sorted(all_results, key=lambda x: (x["session"], x["turn"])):
            print(f"{r['session']:<10} {r['turn']:<6} {r['ttft_ms']:<12} {r['tpot_ms']:<12} {r['total_tokens']:<8} {r['prompt_messages']}")

        print(f"\n--- Summary across {len(all_results)} requests ---")
        print(f"TTFT  p50: {statistics.median(ttfts):.0f} ms  p95: {sorted(ttfts)[int(len(ttfts) * 0.95)]:.0f} ms  max: {max(ttfts):.0f} ms")
        print(f"TPOT  p50: {statistics.median(tpots):.1f} ms/token")