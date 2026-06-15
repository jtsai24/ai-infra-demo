#!/usr/bin/env python3
"""
Simple inference measurement script for Ollama.
Measures TTFT and TPOT using the streaming API.
"""

import json
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:0.5b"
PROMPT = "Explain what a KV cache is in a large language model inference system."


def run_inference(prompt: str) -> dict:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": True,
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    t_request_sent = time.perf_counter()
    t_first_token = None
    token_times = []
    full_response = []

    with urllib.request.urlopen(req) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue

            chunk = json.loads(line)
            now = time.perf_counter()

            if not chunk.get("done", False):
                token_text = chunk.get("response", "")
                if token_text:
                    if t_first_token is None:
                        t_first_token = now
                    token_times.append(now)
                    full_response.append(token_text)
            else:
                t_done = now

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
    print(f"Model: {MODEL}")
    print(f"Prompt: {PROMPT[:60]}...")
    print("Running inference...\n")

    result = run_inference(PROMPT)

    print(f"TTFT:       {result['ttft_ms']} ms")
    print(f"TPOT:       {result['tpot_ms']} ms/token")
    print(f"Throughput: {result['throughput_tps']} tokens/sec")
    print(f"Tokens:     {result['total_tokens']}")
    print(f"\nResponse preview:\n{result['response_preview']}")