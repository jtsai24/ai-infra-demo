#!/usr/bin/env python3
"""
Multi-turn chat session measurement script for vLLM.
Measures TTFT and TPOT per turn using the streaming chat completions API (SSE format).
Conversation history grows with each turn, stressing the KV cache naturally.

Local:  python measure_chat_session.py
Nebius: python measure_chat_session.py --url http://<node-ip>:30800 --model Qwen/Qwen2.5-0.5B-Instruct
"""

import argparse
import json
import time
import urllib.request

TURNS = [
    "Explain what a KV cache is in a large language model inference system.",
    "How does the size of the KV cache affect how many concurrent users you can serve?",
    "What is prefix caching and how does it help with multi-turn conversations?",
    "What happens when the KV cache is full?",
    "How would you monitor KV cache utilization in production?",
]


def run_chat_session(url: str, model: str, max_turns: int) -> list:
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    results = []

    for i, user_text in enumerate(TURNS[:max_turns]):
        messages.append({"role": "user", "content": user_text})
        result = run_inference(messages, url, model)
        assistant_reply = result.pop("response_full")
        messages.append({"role": "assistant", "content": assistant_reply})
        result["turn"] = i + 1
        result["prompt_messages"] = len(messages) - 1
        result["user_text"] = user_text
        result["response_preview"] = assistant_reply[:120]
        results.append(result)

        print(f"--- Turn {i + 1} ---")
        print(f"User:     {user_text}")
        print(f"Response: {assistant_reply[:120]}...")
        print(f"TTFT: {result['ttft_ms']} ms  |  TPOT: {result['tpot_ms']} ms/token  |  Tokens: {result['total_tokens']}  |  Msg count: {result['prompt_messages']}")
        print()

    return results


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
    throughput_tps = total_tokens / (t_done - t_request_sent)

    return {
        "ttft_ms": round(ttft_ms, 1),
        "tpot_ms": round(tpot_ms, 1),
        "throughput_tps": round(throughput_tps, 1),
        "total_tokens": total_tokens,
        "response_full": "".join(full_response),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="vLLM base URL")
    parser.add_argument("--model", default="mlx-community/Qwen2.5-0.5B-Instruct-4bit", help="Model ID")
    parser.add_argument("--turns", type=int, default=5, help="Number of turns per session")
    args = parser.parse_args()

    url = f"{args.url.rstrip('/')}/v1/chat/completions"

    print(f"Model: {args.model}")
    print(f"URL:   {url}")
    print(f"Turns: {args.turns}\n")

    results = run_chat_session(url, args.model, args.turns)

    print(f"{'Turn':<6} {'TTFT (ms)':<12} {'TPOT (ms)':<12} {'Tokens':<8} {'Msg count'}")
    print("-" * 52)
    for r in results:
        print(f"{r['turn']:<6} {r['ttft_ms']:<12} {r['tpot_ms']:<12} {r['total_tokens']:<8} {r['prompt_messages']}")