#!/usr/bin/env python3
"""
Simple inference measurement script for vLLM.
Measures TTFT and TPOT using the streaming API (SSE format).

Local:  python measure_inference_vllm.py
Nebius: python measure_inference_vllm.py --url http://<node-ip>:30800 --model Qwen/Qwen2.5-0.5B-Instruct
"""

import argparse
import json
import time
import urllib.request

PROMPT = "Explain what a KV cache is in a large language model inference system."


def run_inference(prompt: str, url: str, model: str) -> dict:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
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

            token_text = chunk.get("choices", [{}])[0].get("text", "")
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
        "response_preview": "".join(full_response)[:120] + "...",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="vLLM base URL")
    parser.add_argument("--model", default="mlx-community/Qwen2.5-0.5B-Instruct-4bit", help="Model ID")
    args = parser.parse_args()

    completions_url = f"{args.url.rstrip('/')}/v1/completions"

    print(f"Model: {args.model}")
    print(f"URL:   {completions_url}")
    print(f"Prompt: {PROMPT[:60]}...")
    print("Running inference...\n")

    result = run_inference(PROMPT, completions_url, args.model)

    print(f"TTFT:       {result['ttft_ms']} ms")
    print(f"TPOT:       {result['tpot_ms']} ms/token")
    print(f"Throughput: {result['throughput_tps']} tokens/sec")
    print(f"Tokens:     {result['total_tokens']}")
    print(f"\nResponse preview:\n{result['response_preview']}")