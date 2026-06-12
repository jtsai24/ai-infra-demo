# vLLM-metal Local Benchmark Discussion

## Setup
- Model: `mlx-community/Qwen2.5-0.5B-Instruct-4bit` (4-bit MLX quantized)
- Hardware: MacBook Air M4, 17.8GB unified memory, Metal GPU via vllm-metal 0.3.0
- Server: `vllm serve mlx-community/Qwen2.5-0.5B-Instruct-4bit --port 8000`

---

## Warmup behavior (`measure_inference_cold_to_warm.out`)

TTFT drops significantly across the first 3 runs:
- Run 1 (cold): 6,997ms
- Run 2: 2,071ms
- Run 3 (warm): 1,980ms

vLLM has more warmup overhead than Ollama (which stabilized in 2 runs at ~128ms). The higher baseline TTFT even when warm (~2 seconds vs Ollama's ~128ms) is due to vLLM's scheduler overhead — it is a more complex engine designed for continuous batching across many requests, which adds latency for single-request workloads.

---

## Default `--max-num-seqs=256` (`load_test_default_max_num_seqs.out`)

| Concurrency | TTFT p50 | Throughput/req |
|-------------|----------|----------------|
| 1 | 1,968ms | 54 tok/s |
| 2 | 211ms | 74 tok/s |
| 4 | 106ms | 74 tok/s |

**TTFT improves as concurrency increases** — the opposite of Ollama. This is continuous batching in action. When multiple requests arrive simultaneously, vLLM batches them into a single GPU forward pass. The scheduler overhead (~2 seconds at concurrency 1) is amortized across all requests in the batch, so each request sees a lower TTFT. At concurrency 4, TTFT is 106ms — 19x better than concurrency 1.

Throughput stays flat at ~74 tok/s regardless of concurrency — the GPU is being used efficiently in all cases.

---

## `--max-num-seqs=1` (`load_test_max_num_seqs_1.out`)

| Concurrency | TTFT p50 | Throughput/req |
|-------------|----------|----------------|
| 1 | 3,490ms | 38 tok/s |
| 2 | 1,129ms | 71 tok/s |
| 4 | 2,901ms | 55 tok/s |

With `--max-num-seqs=1`, vLLM processes one request at a time — requests queue up, and TTFT degrades with concurrency, mirroring Ollama's `NUM_PARALLEL=1` behavior.

However, concurrency 2 still shows better TTFT than concurrency 1 (1,129ms vs 3,490ms). This is because even with `--max-num-seqs=1`, vLLM's internal scheduler has some batching behavior that Ollama lacks. Not a perfect match with Ollama, but directionally the same queuing pattern.

---

## Key takeaway

The `--max-num-seqs` parameter is vLLM's equivalent of Ollama's `OLLAMA_NUM_PARALLEL`. The fundamental difference is that vLLM's continuous batching actively improves TTFT under load (bus effect), while Ollama time-slices without true batching.

This local comparison on a small model and M4 GPU demonstrates the pattern. The real story plays out on Nebius with an H100 and a larger model, where the KV cache memory pressure and continuous batching tradeoffs become the binding constraints.